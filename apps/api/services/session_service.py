from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apps.api.models import ProjectSpec
from apps.api.services.llm_service import deepseek_chat_json
from apps.api.services.spec_service import extract_spec_from_chat, validate_spec
from apps.api.services.workflow_service import run_workflow

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS_DIR = ROOT / "artifacts"

STEP_ORDER = [
    "market_exploration",
    "persona_generation",
    "conjoint_design",
    "simulation_analysis",
    "reflection",
]

ERROR_TO_FIELD = {
    "domain 不能为空": "domain",
    "goal 不能为空": "goal",
    "target_users 至少需要 1 个用户群体": "target_users",
    "constraints.sample_size 必须大于 0": "sample_size",
}

FIELD_QUESTION = {
    "domain": "你想分析的行业或赛道是什么？比如：AI 陪伴、茶饮、在线教育。",
    "goal": "这次最核心的业务目标是什么？比如：验证付费模式、提高留存、优化定价。",
    "target_users": "目标用户是谁？请至少说 1-2 类人群。",
    "sample_size": "计划样本量是多少？建议至少 50。",
}

OPTIONAL_GUIDE = {
    "deliverables.deadline 为空，建议补充": "你希望什么时候前交付结果（可选）？",
}


@dataclass
class SessionState:
    session_id: str
    spec: ProjectSpec = field(default_factory=ProjectSpec)
    chat_history: list[str] = field(default_factory=list)
    status: str = "idle"
    step_status: dict[str, str] = field(default_factory=lambda: {k: "pending" for k in STEP_ORDER})
    step_summary: dict[str, str] = field(default_factory=dict)
    last_error: str = ""
    last_run_id: str = ""
    run_log_path: str = ""
    artifact_path: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


_STORE: dict[str, SessionState] = {}
_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_session(session_id: str) -> SessionState:
    if session_id not in _STORE:
        raise ValueError("session_id 不存在，请先发送第一条业务需求")
    return _STORE[session_id]


def _first_missing_field(errors: list[str]) -> str | None:
    for err in errors:
        field = ERROR_TO_FIELD.get(err)
        if field:
            return field
    return None


def _spec_snapshot(spec: ProjectSpec) -> str:
    users = "、".join(spec.target_users[:2]) if spec.target_users else "未填写"
    return (
        f"当前已知：赛道={spec.domain or '未填写'}；"
        f"目标={spec.goal or '未填写'}；"
        f"用户={users}；"
        f"样本量={spec.constraints.sample_size if spec.constraints.sample_size > 0 else '未填写'}。"
    )


def _known_info(spec: ProjectSpec) -> dict[str, Any]:
    return {
        "domain": spec.domain or "",
        "goal": spec.goal or "",
        "target_users": spec.target_users,
        "sample_size": spec.constraints.sample_size if spec.constraints.sample_size > 0 else None,
        "deadline": spec.deliverables.deadline or "",
    }


def _fallback_guesses(field: str, spec: ProjectSpec) -> list[str]:
    if field == "domain":
        return [
            "AI 应用（如 AI 陪伴 / 学习 / 生产力）",
            "快消零售（如饮品 / 零食 / 美妆）",
            "互联网服务（如内容社区 / 工具订阅）",
        ]
    if field == "goal":
        return [
            "验证目标用户是否愿意付费",
            "提升留存与复购，找到关键杠杆",
            "优化定价与套餐组合，提高转化率",
        ]
    if field == "target_users":
        domain_hint = spec.domain or "该赛道"
        return [
            f"{domain_hint} 的大学生用户",
            f"{domain_hint} 的 22-30 岁职场新人",
            f"{domain_hint} 的重度兴趣用户",
        ]
    if field == "sample_size":
        return ["100", "200", "300"]
    return []


def _guess_question_with_llm(spec: ProjectSpec, field: str, chat_history: list[str]) -> tuple[str, list[str]]:
    messages = [
        {
            "role": "system",
            "content": (
                "你是营销研究顾问。"
                "请基于当前已知项目信息，针对一个缺失字段提出下一问，并给出 2-3 个高质量猜测答案，"
                "帮助用户快速确认。"
                "输出必须是 JSON："
                "{"
                "\"question\": string,"
                "\"guesses\": string[]"
                "}"
                "要求：问题简洁、业务化；猜测要具体可执行，不能空泛。"
                "不要输出任何非 JSON 文本。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "missing_field": field,
                    "spec_snapshot": spec.model_dump(),
                    "latest_messages": chat_history[-4:],
                },
                ensure_ascii=False,
            ),
        },
    ]
    try:
        data = deepseek_chat_json(messages=messages, max_tokens=420)
        question = str(data.get("question", "")).strip() or FIELD_QUESTION[field]
        guesses_raw = data.get("guesses", [])
        guesses = [str(item).strip() for item in guesses_raw if str(item).strip()][:3]
        if not guesses:
            guesses = _fallback_guesses(field, spec)
        return question, guesses
    except Exception:  # noqa: BLE001
        return FIELD_QUESTION[field], _fallback_guesses(field, spec)


def _business_ack(
    spec: ProjectSpec,
    errors: list[str],
    warnings: list[str],
    chat_history: list[str],
) -> tuple[str, str, bool, list[str], list[str]]:
    missing_fields = [ERROR_TO_FIELD[e] for e in errors if e in ERROR_TO_FIELD]
    next_field = _first_missing_field(errors)
    if next_field:
        question, guesses = _guess_question_with_llm(spec, next_field, chat_history)
        guesses_text = f" 可参考：{'; '.join(guesses)}。" if guesses else ""
        message = (
            "收到，我来一步步带你补全需求。"
            f"{_spec_snapshot(spec)}"
            f"下一步请直接回答：{question}{guesses_text}"
        )
        return message, question, False, missing_fields, guesses

    optional_question = ""
    if warnings:
        optional_question = OPTIONAL_GUIDE.get(warnings[0], "如果方便，可补充截止时间和预算。")
    message = (
        "信息已足够启动分析。"
        f"{_spec_snapshot(spec)}"
        "你现在可以直接点击“开始一键分析”。"
    )
    if optional_question:
        message += f" 若想让结果更贴合业务，还可补充：{optional_question}"
    return message, optional_question, True, [], []


def add_user_message(session_id: str | None, message: str) -> dict[str, Any]:
    text = (message or "").strip()
    if not text:
        raise ValueError("message 不能为空")

    with _LOCK:
        sid = session_id or uuid.uuid4().hex[:12]
        if sid not in _STORE:
            _STORE[sid] = SessionState(session_id=sid)
        state = _STORE[sid]

    updated_spec = extract_spec_from_chat(chat_messages=[text], current_spec=state.spec)
    readiness = validate_spec(updated_spec)
    assistant_message, next_question, ready_to_run, missing_fields, answer_guesses = _business_ack(
        updated_spec,
        readiness["errors"],
        readiness["warnings"],
        state.chat_history + [text],
    )

    with _LOCK:
        state.spec = updated_spec
        state.chat_history.append(text)
        state.updated_at = _now()
        state.last_error = ""
        _STORE[sid] = state

    return {
        "session_id": sid,
        "assistant_message": assistant_message,
        "next_question": next_question,
        "ready_to_run": ready_to_run,
        "missing_fields": missing_fields,
        "answer_guesses": answer_guesses,
        "known_info": _known_info(updated_spec),
        "readiness": readiness,
        "status": state.status,
    }


def _update_step(session_id: str, step_name: str, status: str, summary: str) -> None:
    with _LOCK:
        state = _require_session(session_id)
        state.step_status[step_name] = status
        if summary:
            state.step_summary[step_name] = summary
        state.updated_at = _now()
        _STORE[session_id] = state


def _run_in_background(session_id: str) -> None:
    with _LOCK:
        state = _require_session(session_id)
        spec = state.spec

    try:
        result = run_workflow(spec=spec, progress_callback=lambda n, s, m: _update_step(session_id, n, s, m))
        with _LOCK:
            state = _require_session(session_id)
            state.status = "completed"
            state.last_run_id = str(result["run_id"])
            state.run_log_path = str(result["run_log_path"])
            state.artifact_path = str(result["artifact_path"])
            state.updated_at = _now()
            _STORE[session_id] = state
    except Exception as exc:  # noqa: BLE001
        with _LOCK:
            state = _require_session(session_id)
            state.status = "failed"
            state.last_error = str(exc)
            state.updated_at = _now()
            _STORE[session_id] = state


def run_session(session_id: str) -> dict[str, Any]:
    with _LOCK:
        state = _require_session(session_id)
        if state.status == "running":
            raise ValueError("当前会话正在分析中，请稍后刷新状态")
        readiness = validate_spec(state.spec)
        if readiness["errors"]:
            raise ValueError(f"需求信息不足，无法启动分析：{'; '.join(readiness['errors'])}")
        state.status = "running"
        state.last_error = ""
        state.step_status = {k: "pending" for k in STEP_ORDER}
        state.step_summary = {}
        state.updated_at = _now()
        _STORE[session_id] = state

    worker = threading.Thread(target=_run_in_background, args=(session_id,), daemon=True)
    worker.start()
    return {"session_id": session_id, "status": "running"}


def get_session_status(session_id: str) -> dict[str, Any]:
    with _LOCK:
        state = _require_session(session_id)
        return {
            "session_id": state.session_id,
            "status": state.status,
            "steps": [{"name": k, "status": state.step_status.get(k, "pending"), "summary": state.step_summary.get(k, "")} for k in STEP_ORDER],
            "last_error": state.last_error,
            "updated_at": state.updated_at,
            "last_run_id": state.last_run_id,
        }


def get_session_result(session_id: str) -> dict[str, Any]:
    with _LOCK:
        state = _require_session(session_id)
        if state.status != "completed":
            raise ValueError("分析尚未完成，请稍后查看结果")
        artifact_path = state.artifact_path
        run_log_path = state.run_log_path

    payload = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
    return {
        "session_id": session_id,
        "run_id": payload.get("run_id", ""),
        "status": payload.get("status", ""),
        "steps": payload.get("steps", []),
        "artifact_path": artifact_path,
        "run_log_path": run_log_path,
    }


def get_session_exports(session_id: str) -> dict[str, Any]:
    with _LOCK:
        state = _require_session(session_id)
        if not state.last_run_id:
            raise ValueError("当前会话还没有可导出的分析结果")
        run_id = state.last_run_id
        run_log_path = state.run_log_path
        artifact_path = state.artifact_path

    related = sorted([str(p) for p in ARTIFACTS_DIR.glob(f"*{run_id}*")], reverse=True)
    return {
        "session_id": session_id,
        "run_id": run_id,
        "run_log_path": run_log_path,
        "artifact_path": artifact_path,
        "related_artifacts": related,
    }
