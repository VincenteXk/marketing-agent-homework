from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class Constraints(BaseModel):
    timeline: str = ""
    budget: str = ""
    sample_size: int = 100
    must_use_credamo: bool = True


class Deliverables(BaseModel):
    format: list[str] = Field(default_factory=lambda: ["ppt", "pdf", "excel", "chat_logs"])
    deadline: str = ""


class ProjectSpec(BaseModel):
    project_id: str = "proj1"
    version: str = "draft"
    domain: str = ""
    goal: str = ""
    target_users: list[str] = Field(default_factory=list)
    constraints: Constraints = Field(default_factory=Constraints)
    deliverables: Deliverables = Field(default_factory=Deliverables)
    notes: str = ""


class ExtractRequest(BaseModel):
    chat_messages: list[str] = Field(default_factory=list)
    current_spec: ProjectSpec | None = None


class ValidateRequest(BaseModel):
    spec: ProjectSpec


class FreezeRequest(BaseModel):
    spec: ProjectSpec


class WorkflowRunRequest(BaseModel):
    spec: ProjectSpec


class SessionMessageRequest(BaseModel):
    session_id: str | None = None
    message: str


class SessionRunRequest(BaseModel):
    session_id: str


class ApiResponse(BaseModel):
    ok: bool = True
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
