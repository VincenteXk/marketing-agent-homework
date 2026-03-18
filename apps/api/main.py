from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from apps.api.models import (
    ApiResponse,
    ExtractRequest,
    FreezeRequest,
    ValidateRequest,
    WorkflowRunRequest,
)
from apps.api.services.llm_service import deepseek_ping
from apps.api.services.spec_service import extract_spec_from_chat, validate_spec
from apps.api.services.workflow_service import freeze_spec, list_artifacts, run_workflow

app = FastAPI(title="AI Marketing Lab API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT / "web"

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
