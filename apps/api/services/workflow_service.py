from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from apps.api.models import ProjectSpec
from apps.api.services.llm_service import deepseek_chat_json

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


def _run_agent_step(spec: ProjectSpec, run_id: str, step_name: str, instruction: str) -> dict:
    messages = [
        {
            "role": "system",
            "content": (
                "你是营销项目 agent。"
                "根据输入 spec 完成当前 step。"
                "必须返回 JSON，格式："
                "{"
                "\"step\": string,"
                "\"status\": \"done\","
                "\"summary\": string,"
                "\"outputs\": object"
                "}"
                "不要输出任何非 JSON 文本。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "run_id": run_id,
                    "step_name": step_name,
                    "instruction": instruction,
                    "spec": spec.model_dump(),
                },
                ensure_ascii=False,
            ),
        },
    ]
    result = deepseek_chat_json(messages=messages, max_tokens=1800)
    if result.get("status") != "done":
        raise RuntimeError(f"step {step_name} failed with status: {result.get('status')}")
    return result


def run_workflow(spec: ProjectSpec) -> dict[str, str]:
    _ensure_dirs()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_log_path = RUNS_DIR / f"run_{run_id}.md"
    artifact_path = ARTIFACTS_DIR / f"summary_{run_id}.json"

    steps = [
        ("market_exploration", "输出行业痛点、现有不足、机会点，并给出结论。"),
        ("persona_generation", "至少输出三类消费者画像，并给出关键特征。"),
        ("conjoint_design", "设计联合分析属性与取值，解释设计理由。"),
        ("simulation_analysis", "基于设计生成模拟样本结构并输出策略建议。"),
        ("reflection", "输出可靠性、成本收益、潜在损失与改进建议。"),
    ]

    step_results: list[dict] = []
    for step_name, instruction in steps:
        step_results.append(_run_agent_step(spec=spec, run_id=run_id, step_name=step_name, instruction=instruction))

    run_log_lines = [
        f"# Workflow Run {run_id}",
        "",
        "## Project",
        f"- project_id: {spec.project_id}",
        f"- version: {spec.version}",
        f"- domain: {spec.domain}",
        f"- goal: {spec.goal}",
        "",
        "## Steps",
    ]
    for idx, item in enumerate(step_results, start=1):
        run_log_lines.append(f"{idx}. {item.get('step', 'unknown')}: {item.get('status', 'unknown')}")
        run_log_lines.append(f"   - summary: {item.get('summary', '')}")
    run_log_path.write_text("\n".join(run_log_lines), encoding="utf-8")

    artifact_payload = {
        "run_id": run_id,
        "status": "done",
        "spec_snapshot": spec.model_dump(),
        "steps": step_results,
    }
    artifact_path.write_text(
        json.dumps(artifact_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

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
