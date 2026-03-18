from __future__ import annotations

from pathlib import Path
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from apps.api.models import (
    ApiResponse,
    ConceptChatRequest,
    ExtractRequest,
    FreezeRequest,
    MarketResearchRequest,
    PersonaGenerateRequest,
    SessionMessageRequest,
    SessionRunRequest,
    ValidateRequest,
    WorkflowRunRequest,
)
from apps.api.services.llm_service import deepseek_ping
from apps.api.services.concept_service import run_concept_turn, stream_concept_turn_events
from apps.api.services.metaso_service import stream_market_research_events
from apps.api.services.session_service import (
    add_user_message,
    get_session_exports,
    get_session_result,
    get_session_status,
    run_session,
)
from apps.api.services.spec_service import extract_spec_from_chat, validate_spec
from apps.api.services.workflow_service import freeze_spec, generate_persona_from_concept, list_artifacts, run_workflow

app = FastAPI(title="AI Marketing Lab API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT / "apps" / "web"

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health", response_model=ApiResponse)
def health() -> ApiResponse:
    return ApiResponse(message="ok", data={"service": "api"})


@app.get("/llm/ping", response_model=ApiResponse)
def llm_ping(prompt: str = "请回复pong") -> ApiResponse:
    try:
        result = deepseek_ping(prompt=prompt)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(message="llm ping finished", data=result)


@app.post("/research/stream")
def research_stream(payload: MarketResearchRequest) -> StreamingResponse:
    domain = payload.domain.strip()
    if not domain:
        raise HTTPException(status_code=400, detail="domain 不能为空")

    def event_stream():
        try:
            for event in stream_market_research_events(domain):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001
            error_event = {"type": "error", "message": str(exc)}
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/concept/chat", response_model=ApiResponse)
def concept_chat(payload: ConceptChatRequest) -> ApiResponse:
    try:
        result = run_concept_turn(
            lane=payload.lane,
            research_context=payload.research_context,
            opening_message=payload.opening_message,
            current_concept=payload.current_concept,
            messages=[item.model_dump() for item in payload.messages],
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(message="concept turn finished", data=result)


@app.post("/concept/stream")
def concept_stream(payload: ConceptChatRequest) -> StreamingResponse:
    def event_stream():
        try:
            for event in stream_concept_turn_events(
                lane=payload.lane,
                research_context=payload.research_context,
                opening_message=payload.opening_message,
                current_concept=payload.current_concept,
                messages=[item.model_dump() for item in payload.messages],
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001
            error_event = {"type": "error", "message": str(exc)}
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/persona/generate", response_model=ApiResponse)
def persona_generate(payload: PersonaGenerateRequest) -> ApiResponse:
    try:
        step = generate_persona_from_concept(
            lane=payload.lane,
            confirmed_concept=payload.confirmed_concept,
            research_context=payload.research_context,
            research_structured=payload.research_structured,
            target_users=payload.target_users,
            sample_size=payload.sample_size,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(message="persona generated", data={"step": step})


@app.post("/spec/extract", response_model=ApiResponse)
def spec_extract(payload: ExtractRequest) -> ApiResponse:
    try:
        spec = extract_spec_from_chat(payload.chat_messages, payload.current_spec)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(message="spec extracted", data={"spec": spec.model_dump()})


@app.post("/spec/validate", response_model=ApiResponse)
def spec_validate(payload: ValidateRequest) -> ApiResponse:
    result = validate_spec(payload.spec)
    return ApiResponse(message="spec validated", data=result)


@app.post("/spec/freeze", response_model=ApiResponse)
def spec_freeze(payload: FreezeRequest) -> ApiResponse:
    result = freeze_spec(payload.spec)
    return ApiResponse(message="spec frozen", data=result)


@app.post("/workflow/run", response_model=ApiResponse)
def workflow_run(payload: WorkflowRunRequest) -> ApiResponse:
    try:
        result = run_workflow(payload.spec)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(message="workflow submitted", data=result)


@app.get("/artifacts", response_model=ApiResponse)
def artifacts() -> ApiResponse:
    result = list_artifacts()
    return ApiResponse(message="artifact list", data=result)


@app.post("/session/message", response_model=ApiResponse)
def session_message(payload: SessionMessageRequest) -> ApiResponse:
    try:
        result = add_user_message(session_id=payload.session_id, message=payload.message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(message="session message accepted", data=result)


@app.post("/session/run", response_model=ApiResponse)
def session_run(payload: SessionRunRequest) -> ApiResponse:
    try:
        result = run_session(session_id=payload.session_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(message="session workflow started", data=result)


@app.get("/session/status", response_model=ApiResponse)
def session_status(session_id: str) -> ApiResponse:
    try:
        result = get_session_status(session_id=session_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(message="session status", data=result)


@app.get("/session/result", response_model=ApiResponse)
def session_result(session_id: str) -> ApiResponse:
    try:
        result = get_session_result(session_id=session_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(message="session result", data=result)


@app.get("/session/export", response_model=ApiResponse)
def session_export(session_id: str) -> ApiResponse:
    try:
        result = get_session_exports(session_id=session_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(message="session export", data=result)
