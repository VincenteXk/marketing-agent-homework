from __future__ import annotations

import json
import re
from urllib import error, request

from apps.api.services.llm_service import deepseek_chat_text
from apps.api.settings import settings

FIXED_QUERY_SUFFIX = (
    "，告诉我："
    "1.该行业的主要消费者痛点； "
    "2.现有产品的主要不足； "
    "3.可能的创新方向或机会点"
)


def _require_metaso_key() -> None:
    if not settings.metaso_api_key:
        raise RuntimeError("missing METASO_API_KEY")


def _metaso_endpoint() -> str:
    return f"{settings.metaso_base_url.rstrip('/')}/v1/chat/completions"


def _make_request(payload: dict, timeout: int = 80):
    _require_metaso_key()
    req = request.Request(
        url=_metaso_endpoint(),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.metaso_api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    return request.urlopen(req, timeout=timeout)


def _sanitize_intro_sentence(text: str, domain: str) -> str:
    cleaned = (text or "").strip().replace("\n", "")
    if cleaned.startswith(("“", "\"", "'")) and cleaned.endswith(("”", "\"", "'")):
        cleaned = cleaned[1:-1].strip()
    if not cleaned:
        cleaned = f"分析{domain}市场"
    if not cleaned.startswith("分析"):
        cleaned = f"分析{domain}市场"
    # 第一段 query 要求只做“第一句”，去掉尾部问号/句号后统一成陈述句
    cleaned = cleaned.rstrip("。！？!?")
    return cleaned


def build_query_first_sentence(domain: str) -> str:
    lane = (domain or "").strip()
    if not lane:
        raise ValueError("domain 不能为空")
    messages = [
        {
            "role": "system",
            "content": (
                "你是营销研究查询改写助手。"
                "你的任务是把用户给出的业务描述，提炼成“赛道搜索词第一句”。"
                f"这句话会与以下固定后缀拼接：{FIXED_QUERY_SUFFIX}"
                "所以你只需要输出一个准确、简洁、可检索的赛道名词短句。"
                "要求："
                "1) 只输出一句中文，不要解释、不要编号、不要引号；"
                "2) 形式优先为“分析{赛道}市场”；"
                "3) 如果输入过宽或过散，收敛成最核心赛道名词；"
                "4) 不要包含“痛点/不足/机会点”等后缀内容。"
            ),
        },
        {
            "role": "user",
            "content": f"原始赛道描述：{lane}\n请输出用于市场调研检索的第一句。",
        },
    ]
    try:
        content = deepseek_chat_text(messages=messages, max_tokens=64, temperature=0.15)
        return _sanitize_intro_sentence(content, lane)
    except Exception:
        return _sanitize_intro_sentence("", lane)


def compose_market_research_query(domain: str) -> tuple[str, str]:
    first_sentence = build_query_first_sentence(domain)
    full_query = f"{first_sentence}{FIXED_QUERY_SUFFIX}"
    return first_sentence, full_query


def _extract_structured(full_text: str) -> dict:
    text = (full_text or "").strip()
    if not text:
        return {
            "industry_pain_points": [],
            "product_gaps": [],
            "opportunities": [],
            "conclusion": "",
        }

    pain_lines: list[str] = []
    gap_lines: list[str] = []
    opp_lines: list[str] = []
    current: str | None = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        normalized = line
        # 去掉 markdown 标题符号，避免把 "### 1. xxx" 当成普通内容写入结构化数组
        normalized = re.sub(r"^\s*#{1,6}\s*", "", normalized).strip()
        # 去掉常见列表前缀（-、*、编号）
        normalized = re.sub(r"^\s*[-*•\d\.\)、]+\s*", "", normalized).strip()
        if not normalized:
            continue

        if ("痛点" in normalized) or ("消费者痛点" in normalized):
            current = "pain"
            continue
        if ("不足" in normalized) or ("产品短板" in normalized) or ("现有产品" in normalized):
            current = "gap"
            continue
        if ("创新方向" in normalized) or ("机会点" in normalized) or ("机会" in normalized):
            current = "opp"
            continue

        if current == "pain":
            pain_lines.append(normalized)
        elif current == "gap":
            gap_lines.append(normalized)
        elif current == "opp":
            opp_lines.append(normalized)

    if not pain_lines and not gap_lines and not opp_lines:
        # 兜底：按句号切分，避免前端无结构可展示。
        sentences = [s.strip() for s in re.split(r"[。；;\n]+", text) if s.strip()]
        pain_lines = sentences[:3]
        gap_lines = sentences[3:6]
        opp_lines = sentences[6:9]

    conclusion = text[:320].strip()
    return {
        "industry_pain_points": pain_lines[:24],
        "product_gaps": gap_lines[:24],
        "opportunities": opp_lines[:24],
        "conclusion": conclusion,
    }


def _iter_stream_events(messages: list[dict[str, str]]):
    payload = {
        "model": settings.metaso_model,
        "stream": True,
        "messages": messages,
    }
    try:
        with _make_request(payload, timeout=120) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line or not line.startswith("data:"):
                    continue
                data_part = line[5:].strip()
                if not data_part:
                    continue
                if data_part == "[DONE]":
                    yield {"type": "done"}
                    break
                try:
                    payload_obj = json.loads(data_part)
                except json.JSONDecodeError:
                    continue
                yield {"type": "chunk", "payload": payload_obj}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"http {exc.code}: {detail[:500]}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"metaso stream failed: {exc}") from exc


def run_market_research_once(domain: str) -> dict:
    first_sentence, full_query = compose_market_research_query(domain)
    answer_parts: list[str] = []
    thinking_parts: list[str] = []
    citations: list[dict] = []
    for event in _iter_stream_events(messages=[{"role": "user", "content": full_query}]):
        if event["type"] != "chunk":
            continue
        payload_obj = event["payload"]
        choices = payload_obj.get("choices", [])
        if not choices:
            continue
        delta = choices[0].get("delta", {})
        if delta.get("citations") and not citations:
            citations = delta.get("citations", [])
        answer_piece = str(delta.get("content") or "").strip()
        thinking_piece = str(delta.get("reasoning_content") or "").strip()
        if answer_piece:
            answer_parts.append(answer_piece)
        if thinking_piece:
            thinking_parts.append(thinking_piece)
    full_text = "\n".join(answer_parts).strip() or "\n".join(thinking_parts).strip()
    structured = _extract_structured(full_text)
    return {
        "first_sentence": first_sentence,
        "full_query": full_query,
        "full_text": full_text,
        "citations": citations,
        "structured": structured,
    }


def stream_market_research_events(domain: str):
    first_sentence, full_query = compose_market_research_query(domain)
    yield {"type": "meta", "first_sentence": first_sentence, "full_query": full_query}

    answer_parts: list[str] = []
    thinking_parts: list[str] = []
    citations: list[dict] = []
    for event in _iter_stream_events(messages=[{"role": "user", "content": full_query}]):
        if event["type"] == "done":
            continue
        payload_obj = event["payload"]
        choices = payload_obj.get("choices", [])
        if not choices:
            continue
        delta = choices[0].get("delta", {})
        if delta.get("citations") and not citations:
            citations = delta.get("citations", [])
            yield {"type": "citations", "citations": citations}
        thinking_piece = str(delta.get("reasoning_content") or "")
        answer_piece = str(delta.get("content") or "")
        if thinking_piece:
            thinking_parts.append(thinking_piece)
            yield {"type": "delta", "delta_kind": "thinking", "content": thinking_piece}
        if answer_piece:
            answer_parts.append(answer_piece)
            yield {"type": "delta", "delta_kind": "answer", "content": answer_piece}

    full_text = "".join(answer_parts).strip() or "".join(thinking_parts).strip()
    structured = _extract_structured(full_text)
    yield {
        "type": "done",
        "full_text": full_text,
        "structured": structured,
        "citations": citations,
    }
