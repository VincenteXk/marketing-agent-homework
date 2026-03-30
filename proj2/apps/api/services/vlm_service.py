from __future__ import annotations

import base64
import json
import re
from typing import Any
from urllib import error, parse, request

from apps.api.settings import settings

ARK_BASE = "https://ark.cn-beijing.volces.com/api/v3"
VLM_DEFAULT_MODEL = "doubao-seed-1-6-flash-250828"

_QA_SYSTEM = (
    "你是推广素材画面验收员。给定「生图提示词」与成品图，你只评估：画面内可见的**专名与文字**"
    "（品牌名、产品名、人名、店名、标语字等）是否与提示词要求一致，是否存在**错字、别字、明显乱码**。"
    "不评价美感、构图、色彩。若提示词未要求具体文字，则仅检查是否出现明显错误乱码式文案。"
    "字段 pass 必须与 reason 语义一致：reason 若指出名称不符、错字、无法辨认或无法确认是否满足提示词，则 pass 必须为 false。"
    "只输出一行合法 JSON，不要 markdown，格式："
    '{"pass":true或false,"reason":"不超过80字的中文简述"}'
)


def _allowed_image_host(hostname: str) -> bool:
    h = hostname.lower()
    return "modelscope" in h or h.endswith(".cn") or "aliyuncs.com" in h


def fetch_image_as_data_url(https_url: str) -> str:
    try:
        parsed = parse.urlparse(https_url)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("invalid image url") from exc
    if parsed.scheme != "https":
        raise RuntimeError("only https image urls")
    if not _allowed_image_host(parsed.hostname or ""):
        raise RuntimeError("image host not allowed")
    req = request.Request(https_url, method="GET", headers={"User-Agent": "proj2-vlm/1.0"})
    with request.urlopen(req, timeout=90) as resp:
        data = resp.read()
        ct = resp.headers.get("Content-Type", "image/jpeg")
    mime = ct.split(";")[0].strip() or "image/jpeg"
    if not mime.startswith("image/"):
        mime = "image/jpeg"
    b64 = base64.standard_b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _extract_ark_text(data: dict[str, Any]) -> str | None:
    out = data.get("output")
    if isinstance(out, list):
        for item in out:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "message" and isinstance(item.get("content"), list):
                for p in item["content"]:
                    if not isinstance(p, dict):
                        continue
                    if p.get("type") in ("output_text", "text") and p.get("text"):
                        return str(p["text"]).strip()
        if out and isinstance(out[0], dict):
            first = out[0]
            if isinstance(first.get("text"), str):
                return first["text"].strip()
            if isinstance(first.get("content"), list):
                for x in first["content"]:
                    if isinstance(x, dict) and x.get("type") in ("output_text", "text") and x.get("text"):
                        return str(x["text"]).strip()
    if isinstance(out, dict):
        t = out.get("text")
        if isinstance(t, str):
            return t.strip()
        choices = out.get("choices")
        if isinstance(choices, list) and choices:
            m = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(m, dict) and isinstance(m.get("content"), str):
                return m["content"].strip()
    ch = data.get("choices")
    if isinstance(ch, list) and ch:
        m = ch[0].get("message") if isinstance(ch[0], dict) else None
        if isinstance(m, dict) and isinstance(m.get("content"), str):
            return m["content"].strip()
    raw_out = data.get("output")
    if isinstance(raw_out, str) and raw_out.strip():
        return raw_out.strip()
    return None


def _parse_verdict_json(text: str) -> tuple[bool, str]:
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```\s*$", "", s)
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{[^{}]*\"pass\"[^{}]*\}", s, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(0))
            except json.JSONDecodeError:
                return False, "验收模型返回无法解析"
        else:
            return False, "验收模型返回无法解析"
    if not isinstance(obj, dict):
        return False, "验收模型返回无法解析"
    passed = obj.get("pass")
    if isinstance(passed, str):
        passed = passed.strip().lower() in ("true", "1", "yes")
    reason = str(obj.get("reason") or "").strip()[:200]
    if not isinstance(passed, bool):
        return False, reason or "验收模型返回无法解析"
    return passed, reason or ("通过" if passed else "不通过")


def vlm_validate_image(image_https_url: str, generation_prompt: str) -> tuple[bool, str]:
    if not settings.vlm_ark_api_key:
        raise RuntimeError("missing VLM_ARK_API_KEY")
    data_url = fetch_image_as_data_url(image_https_url)
    user_text = (
        "【生图提示词】\n"
        + generation_prompt.strip()
        + "\n\n请根据画面内容给出 JSON 验收结果。"
    )
    body: dict[str, Any] = {
        "model": settings.vlm_model,
        "thinking": {"type": "disabled"},
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": data_url, "detail": "low"},
                    {"type": "input_text", "text": _QA_SYSTEM + "\n\n" + user_text},
                ],
            }
        ],
    }
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        f"{ARK_BASE}/responses",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.vlm_ark_api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"VLM http {exc.code}: {detail[:400]}") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"VLM 响应非 JSON: {raw[:300]}") from exc
    text = _extract_ark_text(parsed)
    if not text:
        return False, "未能从验收模型解析出结论"
    return _parse_verdict_json(text)
