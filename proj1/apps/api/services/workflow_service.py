from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from apps.api.models import ProjectSpec
from apps.api.services.llm_service import deepseek_chat_json
from apps.api.services.metaso_service import run_market_research_once

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


def _safe_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clean_list(value: Any, max_items: int = 6, fallback: str = "待补充") -> list[str]:
    items = [str(item).strip() for item in _safe_list(value) if str(item).strip()]
    if not items:
        items = [fallback]
    return items[:max_items]


def _clip(text: str, max_len: int = 120) -> str:
    source = _safe_text(text)
    if len(source) <= max_len:
        return source
    return f"{source[:max_len - 1]}…"


def _parse_score(value: Any, default: int = 3) -> int:
    text = str(value or "").strip()
    if text.isdigit():
        num = int(text)
        return max(1, min(5, num))
    if any(token in text for token in ("高", "偏高", "high")):
        return 4
    if any(token in text for token in ("低", "偏低", "low")):
        return 2
    return default


def _parse_share(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip().replace("%", "")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _normalize_share(personas: list[dict[str, Any]]) -> None:
    raw_sum = sum(max(0.0, _parse_share(item.get("share", 0))) for item in personas)
    if raw_sum <= 0:
        even = round(100 / len(personas), 1) if personas else 0.0
        for item in personas:
            item["share"] = even
        if personas:
            personas[-1]["share"] = round(100 - even * (len(personas) - 1), 1)
        return
    normalized_sum = 0.0
    for idx, item in enumerate(personas):
        if idx == len(personas) - 1:
            item["share"] = round(100 - normalized_sum, 1)
            break
        ratio = max(0.0, _parse_share(item.get("share", 0))) / raw_sum
        item["share"] = round(ratio * 100, 1)
        normalized_sum += item["share"]


def _call_llm_json(messages: list[dict[str, str]], max_tokens: int = 1800) -> dict[str, Any]:
    data = deepseek_chat_json(messages=messages, max_tokens=max_tokens)
    if not isinstance(data, dict):
        raise RuntimeError("llm 返回结构异常：非 JSON 对象")
    return data


def _run_market_exploration_step(spec: ProjectSpec) -> dict[str, Any]:
    research = run_market_research_once(spec.domain)
    structured = research.get("structured", {}) if isinstance(research, dict) else {}
    product_gaps = _clean_list(
        structured.get("product_gaps") or structured.get("existing_shortcomings"),
        max_items=6,
        fallback="现有方案同质化，价值点不清晰",
    )
    outputs = {
        "industry_pain_points": _clean_list(
            structured.get("industry_pain_points"),
            max_items=6,
            fallback="用户需求未被充分满足",
        ),
        "product_gaps": product_gaps,
        "existing_shortcomings": product_gaps,
        "opportunities": _clean_list(
            structured.get("opportunities"),
            max_items=6,
            fallback="通过差异化定位切入细分人群",
        ),
        "conclusion": _safe_text(structured.get("conclusion"), "已完成赛道初步调研。"),
        "query_first_sentence": _safe_text(research.get("first_sentence") if isinstance(research, dict) else ""),
        "full_query": _safe_text(research.get("full_query") if isinstance(research, dict) else ""),
        "raw_text": _safe_text(research.get("full_text") if isinstance(research, dict) else ""),
        "citations": _safe_list(research.get("citations") if isinstance(research, dict) else []),
    }
    return {
        "step": "market_exploration",
        "status": "done",
        "summary": _clip(outputs["conclusion"], max_len=120) or "已完成赛道初步市场调研。",
        "outputs": outputs,
    }


def _build_default_personas(spec: ProjectSpec) -> list[dict[str, Any]]:
    domain = _safe_text(spec.domain, "当前赛道")
    return [
        {
            "type": "效率优先型",
            "share": 40.0,
            "demographics": {"age": "22-30", "occupation": "初中级职场人", "city_tier": "一二线"},
            "needs": [f"{domain}场景下快速完成核心任务", "低学习成本、即时可用"],
            "motivation": ["节省时间", "提高日常效率"],
            "pain_points": ["现有方案操作复杂", "信息过载导致选择困难"],
            "behaviors": ["偏好移动端", "愿意尝试轻量工具"],
            "price_sensitivity": 4,
        },
        {
            "type": "品质稳健型",
            "share": 35.0,
            "demographics": {"age": "26-35", "occupation": "成熟白领", "city_tier": "一二线"},
            "needs": ["稳定可靠", "结果可解释且可信"],
            "motivation": ["降低决策风险", "追求长期价值"],
            "pain_points": ["功能碎片化", "缺少持续服务保障"],
            "behaviors": ["重视口碑与案例", "有明确预算评估"],
            "price_sensitivity": 3,
        },
        {
            "type": "体验尝新型",
            "share": 25.0,
            "demographics": {"age": "20-28", "occupation": "学生/新职场", "city_tier": "新一线及以上"},
            "needs": ["体验有趣", "差异化明显"],
            "motivation": ["获得新鲜感", "社交表达与分享"],
            "pain_points": ["产品同质化", "缺少情绪价值"],
            "behaviors": ["受内容平台影响大", "尝新频率高"],
            "price_sensitivity": 3,
        },
    ]


def _normalize_personas(raw_personas: Any, spec: ProjectSpec) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in _safe_list(raw_personas):
        if not isinstance(item, dict):
            continue
        demographics_raw = item.get("demographics", {}) if isinstance(item.get("demographics"), dict) else {}
        needs = _clean_list(item.get("needs"), max_items=5, fallback="满足核心使用需求")
        motivation = _clean_list(item.get("motivation"), max_items=4, fallback="提升效率/体验")
        pain_points = _clean_list(item.get("pain_points"), max_items=4, fallback="现有方案匹配度不足")
        behaviors = _clean_list(item.get("behaviors"), max_items=4, fallback="通过线上渠道决策")
        persona_type = _safe_text(item.get("type"), "未命名画像")
        price_sensitivity = _parse_score(item.get("price_sensitivity"), default=3)
        key_features = (needs[:2] + motivation[:1] + pain_points[:1] + behaviors[:1])[:6]
        normalized.append(
            {
                "type": persona_type,
                "share": _parse_share(item.get("share")),
                "demographics": {
                    "age": _safe_text(demographics_raw.get("age"), "待补充"),
                    "gender": _safe_text(demographics_raw.get("gender"), "不限"),
                    "occupation": _safe_text(demographics_raw.get("occupation"), "待补充"),
                    "city_tier": _safe_text(demographics_raw.get("city_tier"), "待补充"),
                    "income_level": _safe_text(demographics_raw.get("income_level"), "待补充"),
                },
                "needs": needs,
                "motivation": motivation,
                "pain_points": pain_points,
                "behaviors": behaviors,
                "price_sensitivity": price_sensitivity,
                "key_features": key_features,
            }
        )
    if len(normalized) < 3:
        defaults = _build_default_personas(spec)
        for item in defaults:
            if len(normalized) >= 3:
                break
            item["key_features"] = (item["needs"][:2] + item["motivation"][:1] + item["pain_points"][:1] + item["behaviors"][:1])[:6]
            normalized.append(item)
    return normalized[:5]


def _run_persona_generation_step(spec: ProjectSpec, market_outputs: dict[str, Any]) -> dict[str, Any]:
    messages = [
        {
            "role": "system",
            "content": (
                "你是消费者研究专家。"
                "请基于项目目标与市场调研信息，设计模拟消费者画像。"
                "必须返回 JSON，且只返回 JSON。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "task": "构建模拟消费者画像，至少三类，并体现需求、动机、人口特征与行为特征。",
                    "constraints": [
                        "至少输出3类画像",
                        "每类都包含 type/share/demographics/needs/motivation/pain_points/behaviors/price_sensitivity",
                        "share 建议是百分比，可不精确，系统会归一化",
                    ],
                    "spec": spec.model_dump(),
                    "market_context": {
                        "industry_pain_points": market_outputs.get("industry_pain_points", []),
                        "product_gaps": market_outputs.get("product_gaps", []),
                        "opportunities": market_outputs.get("opportunities", []),
                    },
                    "output_schema": {
                        "personas": [
                            {
                                "type": "string",
                                "share": "number|string",
                                "demographics": {
                                    "age": "string",
                                    "gender": "string",
                                    "occupation": "string",
                                    "city_tier": "string",
                                    "income_level": "string",
                                },
                                "needs": ["string"],
                                "motivation": ["string"],
                                "pain_points": ["string"],
                                "behaviors": ["string"],
                                "price_sensitivity": "1-5 或高/中/低",
                            }
                        ],
                        "design_notes": "string",
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]
    raw = _call_llm_json(messages=messages, max_tokens=2200)
    personas = _normalize_personas(raw.get("personas"), spec)
    _normalize_share(personas)
    avg_price = round(sum(item["price_sensitivity"] for item in personas) / len(personas), 2) if personas else 0
    outputs = {
        "personas": personas,
        "segment_distribution": [{"segment": item["type"], "percentage": item["share"]} for item in personas],
        "persona_comparison_table": [
            {
                "persona": item["type"],
                "primary_need": item["needs"][0] if item["needs"] else "",
                "primary_motivation": item["motivation"][0] if item["motivation"] else "",
                "price_sensitivity": item["price_sensitivity"],
                "share": item["share"],
            }
            for item in personas
        ],
        "design_notes": _safe_text(raw.get("design_notes"), "基于市场痛点与目标用户，构建了可用于后续联合分析的三类以上画像。"),
        "stats": {
            "persona_count": len(personas),
            "share_sum": round(sum(item["share"] for item in personas), 1),
            "avg_price_sensitivity": avg_price,
        },
    }
    summary = f"已生成{len(personas)}类消费者画像，覆盖需求、动机、人口特征，并给出分群占比。"
    return {"step": "persona_generation", "status": "done", "summary": summary, "outputs": outputs}


def generate_persona_from_concept(
    lane: str,
    confirmed_concept: str,
    research_context: str = "",
    research_structured: dict[str, Any] | None = None,
    target_users: list[str] | None = None,
    sample_size: int = 120,
) -> dict[str, Any]:
    lane_text = _safe_text(lane, "未命名赛道")
    concept_text = _safe_text(confirmed_concept)
    if not concept_text:
        raise ValueError("confirmed_concept 不能为空")

    users = [str(item).strip() for item in (target_users or []) if str(item).strip()]
    market_structured = research_structured if isinstance(research_structured, dict) else {}
    market_outputs = {
        "industry_pain_points": _clean_list(
            market_structured.get("industry_pain_points"),
            max_items=6,
            fallback="用户需求存在未被满足空间",
        ),
        "product_gaps": _clean_list(
            market_structured.get("product_gaps") or market_structured.get("existing_shortcomings"),
            max_items=6,
            fallback="现有方案同质化，缺少差异化价值",
        ),
        "opportunities": _clean_list(
            market_structured.get("opportunities"),
            max_items=6,
            fallback="可以从细分人群切入形成差异化",
        ),
    }

    spec = ProjectSpec(
        domain=lane_text,
        goal=f"围绕已确认概念进行模拟画像设计：{concept_text}",
        target_users=users,
    )
    spec.constraints.sample_size = max(30, int(sample_size or 120))
    spec.notes = (
        "当前步骤承接产品概念设计。"
        f"已确认概念：{concept_text}。"
        f"{'调研上下文：' + _clip(research_context, 220) if _safe_text(research_context) else ''}"
    )
    return _run_persona_generation_step(spec=spec, market_outputs=market_outputs)


def _default_conjoint_attributes() -> list[dict[str, Any]]:
    return [
        {
            "name": "价格",
            "levels": ["低", "中", "高"],
            "reason": "用于评估价格敏感度差异。",
        },
        {
            "name": "核心功能强度",
            "levels": ["基础", "均衡", "增强"],
            "reason": "用于评估用户对性能/价值的偏好。",
        },
        {
            "name": "使用便捷性",
            "levels": ["一般", "较高", "极高"],
            "reason": "用于衡量效率型用户的偏好。",
        },
        {
            "name": "品牌与信任",
            "levels": ["新品牌", "成熟品牌"],
            "reason": "用于衡量稳健型用户的风险偏好。",
        },
    ]


def _run_conjoint_design_step(spec: ProjectSpec, persona_outputs: dict[str, Any]) -> dict[str, Any]:
    messages = [
        {
            "role": "system",
            "content": (
                "你是联合分析设计专家。"
                "请输出用于后续模拟的属性设计。"
                "必须返回 JSON，且只返回 JSON。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "task": "根据画像设计联合分析属性与水平",
                    "constraints": [
                        "输出4-6个属性",
                        "每个属性2-4个水平",
                        "每个属性给出简短理由",
                    ],
                    "spec": spec.model_dump(),
                    "personas": persona_outputs.get("personas", []),
                    "output_schema": {
                        "attributes": [{"name": "string", "levels": ["string"], "reason": "string"}],
                        "design_notes": "string",
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]
    raw = _call_llm_json(messages=messages, max_tokens=1600)
    attributes: list[dict[str, Any]] = []
    for item in _safe_list(raw.get("attributes")):
        if not isinstance(item, dict):
            continue
        name = _safe_text(item.get("name"))
        levels = _clean_list(item.get("levels"), max_items=4, fallback="待补充")
        reason = _safe_text(item.get("reason"), "用于区分不同画像偏好。")
        if not name:
            continue
        attributes.append({"name": name, "levels": levels, "reason": reason})
    if len(attributes) < 4:
        attributes = _default_conjoint_attributes()
    outputs = {
        "attributes": attributes[:6],
        "design_notes": _safe_text(
            raw.get("design_notes"),
            "属性基于画像差异构建，兼顾可解释性与样本可承载度。",
        ),
    }
    return {
        "step": "conjoint_design",
        "status": "done",
        "summary": "已完成联合分析属性设计，并给出属性水平与设计理由。",
        "outputs": outputs,
    }


def _normalize_sim_segments(personas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for item in personas:
        segments.append(
            {
                "segment": _safe_text(item.get("type"), "未命名画像"),
                "percentage": round(float(item.get("share", 0)), 1),
                "characteristics": "；".join((_clean_list(item.get("needs"), 2, "需求待补充") + _clean_list(item.get("motivation"), 1, "动机待补充"))[:3]),
            }
        )
    return segments


def _extract_sim_points(attributes: list[dict[str, Any]]) -> list[str]:
    points = ["画像类型", "购买意向评分", "价格敏感度", "转化概率"]
    for item in attributes[:4]:
        name = _safe_text(item.get("name"))
        if name:
            points.append(f"{name}偏好")
    uniq: list[str] = []
    for item in points:
        if item not in uniq:
            uniq.append(item)
    return uniq[:10]


def _run_simulation_analysis_step(
    spec: ProjectSpec,
    persona_outputs: dict[str, Any],
    conjoint_outputs: dict[str, Any],
) -> dict[str, Any]:
    personas = _safe_list(persona_outputs.get("personas"))
    attributes = _safe_list(conjoint_outputs.get("attributes"))
    sample_size = max(30, int(spec.constraints.sample_size or 100))
    messages = [
        {
            "role": "system",
            "content": (
                "你是营销模拟分析专家。"
                "请输出模拟样本结构和策略建议。"
                "必须返回 JSON，且只返回 JSON。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "task": "构建模拟样本结构并给出策略建议",
                    "spec": spec.model_dump(),
                    "personas": personas,
                    "attributes": attributes,
                    "output_schema": {
                        "simulated_sample_structure": {
                            "sample_size": "int",
                            "data_collection_methods": ["string"],
                            "simulated_data_points": ["string"],
                        },
                        "strategy_recommendations": {
                            "product_strategy": "string",
                            "channel_strategy": "string",
                            "marketing_strategy": "string",
                            "iteration_suggestions": "string",
                        },
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]
    raw = _call_llm_json(messages=messages, max_tokens=1800)
    sample = raw.get("simulated_sample_structure", {}) if isinstance(raw.get("simulated_sample_structure"), dict) else {}
    strategy = raw.get("strategy_recommendations", {}) if isinstance(raw.get("strategy_recommendations"), dict) else {}
    outputs = {
        "simulated_sample_structure": {
            "sample_size": int(sample.get("sample_size") or sample_size),
            "user_segments": _normalize_sim_segments(personas),
            "data_collection_methods": _clean_list(
                sample.get("data_collection_methods"),
                max_items=4,
                fallback="在线问卷 + 小样本访谈",
            ),
            "simulated_data_points": _clean_list(
                sample.get("simulated_data_points"),
                max_items=10,
                fallback="基础偏好标签",
            )
            or _extract_sim_points(attributes),
        },
        "strategy_recommendations": {
            "product_strategy": _safe_text(strategy.get("product_strategy"), "围绕高占比画像优先打磨核心价值主张。"),
            "channel_strategy": _safe_text(strategy.get("channel_strategy"), "按分群决策路径配置线上线下触点。"),
            "marketing_strategy": _safe_text(strategy.get("marketing_strategy"), "针对不同动机设计差异化沟通话术。"),
            "iteration_suggestions": _safe_text(strategy.get("iteration_suggestions"), "通过小规模AB测试滚动优化方案。"),
        },
    }
    return {
        "step": "simulation_analysis",
        "status": "done",
        "summary": "已完成模拟样本结构设计，并输出可执行的策略建议。",
        "outputs": outputs,
    }


def _run_reflection_step(spec: ProjectSpec, previous_steps: list[dict[str, Any]]) -> dict[str, Any]:
    messages = [
        {
            "role": "system",
            "content": "你是营销项目复盘顾问。请输出反思与改进建议。必须返回 JSON，且只返回 JSON。",
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "task": "评估本次模拟流程的可靠性、成本收益、潜在损失，并提出改进建议",
                    "spec": spec.model_dump(),
                    "steps": previous_steps,
                    "output_schema": {
                        "reliability": "string",
                        "cost_benefit": "string",
                        "potential_losses": "string",
                        "improvement_suggestions": "string",
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]
    raw = _call_llm_json(messages=messages, max_tokens=1000)
    outputs = {
        "reliability": _safe_text(raw.get("reliability"), "可靠性中等，建议补充真实数据校准。"),
        "cost_benefit": _safe_text(raw.get("cost_benefit"), "投入较低、迭代快，适合前期探索。"),
        "potential_losses": _safe_text(raw.get("potential_losses"), "若分群假设偏差较大，可能造成策略误判。"),
        "improvement_suggestions": _safe_text(raw.get("improvement_suggestions"), "增加真实样本验证，并持续迭代画像。"),
    }
    return {
        "step": "reflection",
        "status": "done",
        "summary": _clip(outputs["improvement_suggestions"], max_len=80) or "已输出反思与改进建议。",
        "outputs": outputs,
    }


def run_workflow(
    spec: ProjectSpec,
    progress_callback: Callable[[str, str, str], None] | None = None,
) -> dict[str, str | list[dict]]:
    _ensure_dirs()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_log_path = RUNS_DIR / f"run_{run_id}.md"
    artifact_path = ARTIFACTS_DIR / f"summary_{run_id}.json"

    step_results: list[dict[str, Any]] = []
    market_step_name = "market_exploration"
    persona_step_name = "persona_generation"
    conjoint_step_name = "conjoint_design"
    simulation_step_name = "simulation_analysis"
    reflection_step_name = "reflection"

    def _exec(step_name: str, runner: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        if progress_callback:
            progress_callback(step_name, "running", "")
        try:
            result = runner()
            if progress_callback:
                progress_callback(step_name, "done", _safe_text(result.get("summary")))
            return result
        except Exception as exc:  # noqa: BLE001
            if progress_callback:
                progress_callback(step_name, "failed", str(exc))
            raise

    market_step = _exec(market_step_name, lambda: _run_market_exploration_step(spec))
    step_results.append(market_step)

    persona_step = _exec(
        persona_step_name,
        lambda: _run_persona_generation_step(spec, market_step.get("outputs", {})),
    )
    step_results.append(persona_step)

    conjoint_step = _exec(
        conjoint_step_name,
        lambda: _run_conjoint_design_step(spec, persona_step.get("outputs", {})),
    )
    step_results.append(conjoint_step)

    simulation_step = _exec(
        simulation_step_name,
        lambda: _run_simulation_analysis_step(
            spec,
            persona_step.get("outputs", {}),
            conjoint_step.get("outputs", {}),
        ),
    )
    step_results.append(simulation_step)

    reflection_step = _exec(
        reflection_step_name,
        lambda: _run_reflection_step(spec, step_results),
    )
    step_results.append(reflection_step)

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
        "steps": step_results,
    }


def list_artifacts() -> dict[str, list[str]]:
    _ensure_dirs()
    runs = sorted([str(p) for p in RUNS_DIR.glob("*")], reverse=True)
    artifacts = sorted([str(p) for p in ARTIFACTS_DIR.glob("*")], reverse=True)
    specs = sorted([str(p) for p in PROJECTS_DIR.glob("*")], reverse=True)
    return {"runs": runs, "artifacts": artifacts, "specs": specs}
