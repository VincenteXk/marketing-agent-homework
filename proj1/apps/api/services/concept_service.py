from __future__ import annotations

from typing import Any

from apps.api.services.llm_service import deepseek_chat_json, deepseek_chat_json_stream


def _normalize_history(messages: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for item in messages:
        role = str(item.get("role") or "").strip().lower()
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        if role not in {"user", "agent"}:
            role = "user"
        rows.append(f"{role}: {text}")
    return "\n".join(rows)


def _build_prompt(
    lane: str,
    research_context: str,
    opening_message: str,
    current_concept: str,
    history_text: str,
) -> list[dict[str, str]]:
    safe_lane = lane.strip() or "未命名赛道"
    safe_opening = opening_message.strip() or f"你选定了{safe_lane}赛道，现在我们来一起完善一下你的产品概念吧。"
    safe_research = research_context.strip() or "（暂无调研正文）"
    safe_current_concept = current_concept.strip() or "（尚未确认）"
    safe_history = history_text.strip() or "（暂无历史对话）"
    system = (
        "你是产品创新与价值主张专家，负责辅助用户打磨可落地的最终产品概念。"
        "请严格输出 JSON，不要输出任何 JSON 之外的内容。"
    )
    user = f"""
<context>
  <objective>辅助用户提出最终产品概念，清楚描述核心价值主张。</objective>
  <lane>{safe_lane}</lane>
  <research_context>{safe_research}</research_context>
  <opening_already_asked>{safe_opening}</opening_already_asked>
  <current_concept>{safe_current_concept}</current_concept>
  <conversation_history>{safe_history}</conversation_history>
</context>

<rules>
1) 优先输出可执行的“概念草案”，不要把提问当成唯一动作；只有在确实必要时才追问。
2) 若信息尚不明确，最多只追问 1 个关键缺口，且不要连续两轮追问同一问题。
3) 当用户表现出不想继续回答或让你直接给方案时，不再追问，直接给出“带假设的概念草案”，并在 missing_items 中列出假设点。
4) 若信息已较清晰，则输出可供用户敲定的“最终产品概念”并明确请用户确认。
5) 是否确认由你基于上下文自主判断：仅在用户明确敲定时将 is_confirmed 置为 true。
6) 除非用户主动把产品拆得很细，否则 assistant_reply 不要超过90字。
7) 一旦 is_confirmed 为 true，final_concept 必须给出清晰完整版本。
8) 当 is_confirmed 为 true 时，assistant_reply 必须为空字符串。
</rules>

请按以下 JSON 格式输出：
{{
  "assistant_reply": "给用户展示的回复内容",
  "mode": "ask|propose|confirmed",
  "is_confirmed": false,
  "final_concept": "若未确认可为空字符串，若确认必须填写",
  "missing_items": ["最多3项缺口，若无可空数组"]
}}
""".strip()
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def run_concept_turn(
    lane: str,
    research_context: str,
    opening_message: str,
    current_concept: str,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    history_text = _normalize_history(messages)
    payload = _build_prompt(
        lane=lane,
        research_context=research_context,
        opening_message=opening_message,
        current_concept=current_concept,
        history_text=history_text,
    )
    parsed = deepseek_chat_json(messages=payload, max_tokens=900)
    return _normalize_concept_output(parsed=parsed)


def stream_concept_turn_events(
    lane: str,
    research_context: str,
    opening_message: str,
    current_concept: str,
    messages: list[dict[str, Any]],
):
    history_text = _normalize_history(messages)
    payload = _build_prompt(
        lane=lane,
        research_context=research_context,
        opening_message=opening_message,
        current_concept=current_concept,
        history_text=history_text,
    )
    for event in deepseek_chat_json_stream(messages=payload, max_tokens=900):
        if event.get("type") == "delta":
            yield {"type": "delta", "content": str(event.get("content") or "")}
            continue
        if event.get("type") == "done":
            normalized = _normalize_concept_output(parsed=event.get("parsed") or {})
            yield {"type": "done", **normalized}
            continue


def _normalize_concept_output(parsed: dict[str, Any]) -> dict[str, Any]:
    reply = str(parsed.get("assistant_reply") or "").strip()
    mode = str(parsed.get("mode") or "").strip().lower()
    is_confirmed = bool(parsed.get("is_confirmed"))
    final_concept = str(parsed.get("final_concept") or "").strip()
    missing_items_raw = parsed.get("missing_items")
    missing_items: list[str] = []
    if isinstance(missing_items_raw, list):
        missing_items = [str(item).strip() for item in missing_items_raw if str(item).strip()][:3]

    if mode not in {"ask", "propose", "confirmed"}:
        mode = "propose" if reply else "ask"
    if is_confirmed and not final_concept:
        is_confirmed = False
        if mode == "confirmed":
            mode = "propose"
    if is_confirmed:
        mode = "confirmed"
        reply = ""

    if not reply:
        if not is_confirmed:
            reply = "我先给你一版可执行概念草案，并标注关键假设，确认后再精修。"
            mode = "propose"

    return {
        "assistant_reply": reply,
        "mode": mode,
        "is_confirmed": is_confirmed,
        "final_concept": final_concept if is_confirmed else "",
        "missing_items": missing_items,
    }
