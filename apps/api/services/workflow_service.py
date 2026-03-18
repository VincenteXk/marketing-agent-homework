from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from apps.api.models import ProjectSpec

ROOT = Path(__file__).resolve().parents[3]
PROJECTS_DIR = ROOT / "projects"
RUNS_DIR = ROOT / "runs"
ARTIFACTS_DIR = ROOT / "artifacts"


def _ensure_dirs() -> None:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def freeze_spec(spec: ProjectSpec) -> dict[str, str]:
    _ensure_dirs()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    version = f"v{ts}"
    frozen = spec.model_copy(deep=True)
    frozen.version = version

    output_path = PROJECTS_DIR / f"{spec.project_id}_{version}.json"
    output_path.write_text(
        json.dumps(frozen.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"version": version, "path": str(output_path)}


def run_workflow(spec: ProjectSpec) -> dict[str, str]:
    _ensure_dirs()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    run_log_path = RUNS_DIR / f"run_{run_id}.md"
    artifact_path = ARTIFACTS_DIR / f"summary_{run_id}.json"

    run_log = f"""# Workflow Run {run_id}

## Project
- project_id: {spec.project_id}
- version: {spec.version}
- domain: {spec.domain}
- goal: {spec.goal}

## Steps
1. market exploration: queued
2. persona generation: queued
3. conjoint design: queued
4. simulation + analysis: queued
5. reflection: queued

## Notes
- This is a scaffold run for pipeline verification.
"""
    run_log_path.write_text(run_log, encoding="utf-8")

    artifact_payload = {
        "run_id": run_id,
        "status": "queued",
        "next_action": "replace scaffold tasks with real agent executors",
        "spec_snapshot": spec.model_dump(),
    }
    artifact_path.write_text(json.dumps(artifact_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "run_id": run_id,
        "run_log_path": str(run_log_path),
        "artifact_path": str(artifact_path),
    }


def list_artifacts() -> dict[str, list[str]]:
    _ensure_dirs()
    runs = sorted([str(p) for p in RUNS_DIR.glob("*")], reverse=True)
    artifacts = sorted([str(p) for p in ARTIFACTS_DIR.glob("*")], reverse=True)
    specs = sorted([str(p) for p in PROJECTS_DIR.glob("*")], reverse=True)
    return {"runs": runs, "artifacts": artifacts, "specs": specs}
