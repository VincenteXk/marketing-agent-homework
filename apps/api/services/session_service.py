from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apps.api.models import ProjectSpec
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


def _business_ack(spec: ProjectSpec, errors: list[str], warnings: list[str]) -> str:
    if errors:
        return (
            "已记录你的业务需求，但还不能启动完整分析。"
            "请继续补充：赛道、目标用户、核心目标、样本量或截止时间。"
        )
    message = (
        f"已收到需求：{spec.domain or '未指定赛道'} / {spec.goal or '未指定目标'}。"
        "你可以直接点击“开始分析”，我会自动完成市场探索、画像、联合分析与策略建议。"
    )
    if warnings:
        message += " 另外建议补充截止时间等细节，结果会更稳。"
    return message


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

    with _LOCK:
        state.spec = updated_spec
        state.chat_history.append(text)
        state.updated_at = _now()
        state.last_error = ""
        _STORE[sid] = state

    return {
        "session_id": sid,
        "assistant_message": _business_ack(updated_spec, readiness["errors"], readiness["warnings"]),
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
