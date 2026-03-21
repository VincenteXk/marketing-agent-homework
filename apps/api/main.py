from __future__ import annotations

from pathlib import Path
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from itertools import product

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


@app.post("/simulation/generate")
async def simulation_generate(data: dict):
    personas = data.get("personas", []) or []
    conjoint_design = data.get("conjoint_design", {}) or {}
    sample_size = int(data.get("sample_size", 120) or 120)

    attributes = conjoint_design.get("attributes", []) or []
    personas = normalize_personas(personas)
    attributes = normalize_attributes(attributes)

    profiles = build_profile_candidates(attributes)
    respondents = build_respondents(personas=personas, sample_size=sample_size)
    choices = build_choices(respondents=respondents, personas=personas, profiles=profiles, attributes=attributes)
    profile_summary = build_profile_summary(choices=choices, profiles=profiles)
    segment_summary = build_segment_summary(choices=choices, personas=personas, attributes=attributes)

    return {
        "data": {
            "step": {
                "step": "simulation_data",
                "summary": "已基于最新消费者画像重建模拟消费者样本、候选方案与选择结果",
                "outputs": {
                    "respondents": respondents,
                    "profiles": profiles,
                    "choices": choices,
                    "profile_summary": profile_summary,
                    "segment_summary": segment_summary,
                    "logic_notes": [
                        "先按最新画像占比扩展 respondent 样本，并保留年龄、职业、城市层级与价格敏感度等字段。",
                        "再围绕联合分析属性生成候选 profile，避免全量组合过多，只保留用于课堂展示的核心方案。",
                        "最后根据不同画像的价格、隐私、服务深度、反馈机制偏好计算效用，并加入轻微个体波动，形成更像真实问卷的选择结果。",
                    ],
                },
            }
        }
    }


@app.post("/analysis/generate")
async def analysis_generate(data: dict):
    simulation_data = data.get("simulation_data", {}) or {}
    choices = simulation_data.get("choices", []) or []
    profiles = simulation_data.get("profiles", []) or []
    conjoint_design = data.get("conjoint_design", {}) or {}
    attributes = normalize_attributes(conjoint_design.get("attributes", []) or [])
    personas = normalize_personas(data.get("personas", []) or [])

    if not choices or not attributes:
        return {
            "data": {
                "step": {
                    "step": "conjoint_analysis",
                    "summary": "缺少模拟选择数据或联合分析属性，无法完成分析",
                    "outputs": {
                        "attribute_importance": [],
                        "partworth_summary": [],
                        "recommended_product": {},
                        "persona_preference_summary": [],
                        "profile_choice_summary": [],
                        "strategy_suggestions": ["请先生成完整的消费者模拟数据。"],
                    },
                }
            }
        }

    total_n = len(choices)
    partworth_summary = []
    attribute_importance = []

    for attr in attributes:
        attr_name = str(attr.get("name", "")).strip()
        levels = [str(level) for level in attr.get("levels", []) or []]
        counts = {level: 0 for level in levels}

        for row in choices:
            value = str(row.get(attr_name, ""))
            if value in counts:
                counts[value] += 1

        shares = []
        for level in levels:
            pct = round(counts[level] / total_n * 100, 1)
            shares.append(pct)
            partworth_summary.append({
                "attribute": attr_name,
                "level": level,
                "chosen_count": counts[level],
                "chosen_pct": pct,
            })

        spread = max(shares) - min(shares) if shares else 0.0
        top_level = max(counts, key=counts.get) if counts else ""
        attribute_importance.append({
            "attribute": attr_name,
            "importance_score": round(spread, 1),
            "top_level": top_level,
        })

    attribute_importance.sort(key=lambda item: item["importance_score"], reverse=True)

    recommended_product = {}
    for attr in attributes:
        attr_name = str(attr.get("name", "")).strip()
        rows = [row for row in partworth_summary if row["attribute"] == attr_name]
        if rows:
            best = max(rows, key=lambda item: item["chosen_count"])
            recommended_product[attr_name] = best["level"]

    persona_preference_summary = []
    persona_types = [persona["type"] for persona in personas]
    for persona_type in persona_types:
        subset = [row for row in choices if row.get("persona_type") == persona_type]
        if not subset:
            continue
        row = {"persona_type": persona_type, "sample_size": len(subset)}
        for attr in attributes:
            attr_name = str(attr.get("name", "")).strip()
            level_counts = {}
            for item in subset:
                level = str(item.get(attr_name, ""))
                level_counts[level] = level_counts.get(level, 0) + 1
            if level_counts:
                best_level = max(level_counts, key=level_counts.get)
                best_pct = round(level_counts[best_level] / len(subset) * 100, 1)
                row[f"{attr_name}_top"] = best_level
                row[f"{attr_name}_top_pct"] = f"{best_pct}%"
        persona_preference_summary.append(row)

    profile_choice_summary = build_profile_summary(choices=choices, profiles=profiles)

    strategy_suggestions = []
    if attribute_importance:
        top_attr = attribute_importance[0]
        strategy_suggestions.append(
            f"当前对选择影响最大的属性是“{top_attr['attribute']}”，最受欢迎的水平是“{top_attr['top_level']}”，产品首发时应优先把这一维做对。"
        )

    price_key = next((attr["name"] for attr in attributes if "定价" in attr["name"] or "价格" in attr["name"]), None)
    privacy_key = next((attr["name"] for attr in attributes if "隐私" in attr["name"]), None)
    support_key = next((attr["name"] for attr in attributes if "支持" in attr["name"] or "服务" in attr["name"]), None)
    feedback_key = next((attr["name"] for attr in attributes if "反馈" in attr["name"] or "预警" in attr["name"]), None)

    if price_key and recommended_product.get(price_key):
        strategy_suggestions.append(
            f"定价建议以“{recommended_product[price_key]}”作为主推版本，同时保留更高阶套餐去承接价格不敏感的高价值人群。"
        )
    if privacy_key and recommended_product.get(privacy_key):
        strategy_suggestions.append(
            f"隐私策略建议默认采用“{recommended_product[privacy_key]}”，因为心理健康场景里隐私感知会直接影响转化。"
        )
    if support_key and recommended_product.get(support_key):
        strategy_suggestions.append(
            f"服务形态建议围绕“{recommended_product[support_key]}”搭建默认体验，并给高压职场与慢性困扰人群保留升级路径。"
        )
    if feedback_key and recommended_product.get(feedback_key):
        strategy_suggestions.append(
            f"反馈机制建议优先提供“{recommended_product[feedback_key]}”，把‘看得见效果’做成留存抓手。"
        )

    heterogeneity_notes = summarize_heterogeneity(persona_preference_summary=persona_preference_summary, attributes=attributes)
    strategy_suggestions.extend(heterogeneity_notes)

    return {
        "data": {
            "step": {
                "step": "conjoint_analysis",
                "summary": "已基于最新画像的模拟选择结果完成联合分析，并输出属性重要性、分群偏好和产品策略",
                "outputs": {
                    "attribute_importance": attribute_importance,
                    "partworth_summary": partworth_summary,
                    "recommended_product": recommended_product,
                    "persona_preference_summary": persona_preference_summary,
                    "profile_choice_summary": profile_choice_summary,
                    "strategy_suggestions": strategy_suggestions,
                },
            }
        }
    }


@app.post("/conjoint/design")
async def conjoint_design(data: dict):
    concept = str(data.get("confirmed_concept", "")).strip()

    return {
        "data": {
            "step": {
                "step": "conjoint_design",
                "summary": "已基于前序阶段结果生成联合分析框架",
                "outputs": {
                    "attributes": [
                        {
                            "name": "定价方案",
                            "levels": ["免费基础版", "19元/月轻享版", "59元/月增强版"],
                            "reason": "用于区分不同消费者的价格敏感度与付费意愿。"
                        },
                        {
                            "name": "隐私模式",
                            "levels": ["匿名云端", "本地优先存储", "实名档案+长期追踪"],
                            "reason": "用于刻画用户对匿名性、数据安全与长期管理的偏好。"
                        },
                        {
                            "name": "支持方式",
                            "levels": ["纯AI日常陪伴", "AI+每周情绪报告", "AI+人工咨询转接"],
                            "reason": "用于区分用户对低成本陪伴、信息反馈与专业支持的需求差异。"
                        },
                        {
                            "name": "反馈机制",
                            "levels": ["每日情绪记录", "每周成长报告", "风险预警+干预建议"],
                            "reason": "用于衡量用户对效果可见性与主动干预强度的偏好。"
                        }
                    ],
                    "design_notes": f"本轮设计围绕产品概念“{concept}”，重点检验价格、隐私、支持深度和反馈机制四类属性的权衡关系。"
                }
            }
        }
    }


DEFAULT_PERSONAS = [
    {
        "type": "高压职场奋斗者",
        "share": 35,
        "price_sensitivity": 3,
        "demographics": {
            "age": "25-35岁",
            "gender": "男女比例均衡",
            "occupation": "互联网/金融/咨询等行业白领",
            "city_tier": "一线及新一线城市",
            "income_level": "中高收入（月薪15k-40k）",
        },
    },
    {
        "type": "青少年与大学生群体",
        "share": 30,
        "price_sensitivity": 4,
        "demographics": {
            "age": "16-24岁",
            "gender": "女性略多于男性",
            "occupation": "学生（高中生、大学生）",
            "city_tier": "各线城市分布均匀",
            "income_level": "低收入或依赖家庭（月可支配收入0-3k）",
        },
    },
    {
        "type": "慢性心理困扰者",
        "share": 25,
        "price_sensitivity": 3,
        "demographics": {
            "age": "30-50岁",
            "gender": "女性略多",
            "occupation": "自由职业者、家庭主妇、普通职员等",
            "city_tier": "二三线城市为主",
            "income_level": "中等收入（月薪8k-20k）",
        },
    },
    {
        "type": "企业EAP用户",
        "share": 10,
        "price_sensitivity": 2,
        "demographics": {
            "age": "22-60岁",
            "gender": "男女比例均衡",
            "occupation": "各类企业员工（覆盖基层至管理层）",
            "city_tier": "一线至三线城市",
            "income_level": "收入与企业层级相关",
        },
    },
]

DEFAULT_ATTRIBUTES = [
    {"name": "定价方案", "levels": ["免费基础版", "19元/月轻享版", "59元/月增强版"]},
    {"name": "隐私模式", "levels": ["匿名云端", "本地优先存储", "实名档案+长期追踪"]},
    {"name": "支持方式", "levels": ["纯AI日常陪伴", "AI+每周情绪报告", "AI+人工咨询转接"]},
    {"name": "反馈机制", "levels": ["每日情绪记录", "每周成长报告", "风险预警+干预建议"]},
]


def normalize_personas(personas: list[dict]) -> list[dict]:
    source = personas or DEFAULT_PERSONAS
    normalized = []
    for item in source:
        demographics = item.get("demographics", {}) or {}
        normalized.append({
            "type": str(item.get("type", "未命名画像")).strip() or "未命名画像",
            "share": float(item.get("share", 0) or 0),
            "price_sensitivity": float(item.get("price_sensitivity", 3) or 3),
            "demographics": {
                "age": str(demographics.get("age", "未知")),
                "gender": str(demographics.get("gender", "未知")),
                "occupation": str(demographics.get("occupation", "未知")),
                "city_tier": str(demographics.get("city_tier", "未知")),
                "income_level": str(demographics.get("income_level", "未知")),
            },
        })
    if not normalized:
        normalized = DEFAULT_PERSONAS.copy()
    total_share = sum(item["share"] for item in normalized) or 100.0
    for item in normalized:
        item["share"] = round(item["share"] / total_share * 100, 1)
    return normalized


def normalize_attributes(attributes: list[dict]) -> list[dict]:
    source = attributes or DEFAULT_ATTRIBUTES
    normalized = []
    for item in source:
        levels = [str(level).strip() for level in item.get("levels", []) if str(level).strip()]
        if not levels:
            continue
        normalized.append({"name": str(item.get("name", "")).strip(), "levels": levels})
    return normalized or DEFAULT_ATTRIBUTES.copy()


def build_profile_candidates(attributes: list[dict]) -> list[dict]:
    if not attributes:
        attributes = DEFAULT_ATTRIBUTES
    attr_map = {item["name"]: item["levels"] for item in attributes}
    curated_combos = [
        [attr_map["定价方案"][0], attr_map["隐私模式"][0], attr_map["支持方式"][0], attr_map["反馈机制"][0]],
        [attr_map["定价方案"][1], attr_map["隐私模式"][0], attr_map["支持方式"][0], attr_map["反馈机制"][1]],
        [attr_map["定价方案"][1], attr_map["隐私模式"][1], attr_map["支持方式"][1], attr_map["反馈机制"][1]],
        [attr_map["定价方案"][1], attr_map["隐私模式"][1], attr_map["支持方式"][2], attr_map["反馈机制"][2]],
        [attr_map["定价方案"][2], attr_map["隐私模式"][1], attr_map["支持方式"][2], attr_map["反馈机制"][2]],
        [attr_map["定价方案"][2], attr_map["隐私模式"][2], attr_map["支持方式"][2], attr_map["反馈机制"][2]],
        [attr_map["定价方案"][0], attr_map["隐私模式"][1], attr_map["支持方式"][1], attr_map["反馈机制"][0]],
        [attr_map["定价方案"][1], attr_map["隐私模式"][2], attr_map["支持方式"][2], attr_map["反馈机制"][1]],
        [attr_map["定价方案"][0], attr_map["隐私模式"][0], attr_map["支持方式"][1], attr_map["反馈机制"][2]],
    ]
    profiles = []
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    attr_names = [item["name"] for item in attributes]
    for idx, combo in enumerate(curated_combos):
        row = {"profile_id": labels[idx]}
        for name, level in zip(attr_names, combo):
            row[name] = level
        profiles.append(row)
    return profiles


def allocate_counts(personas: list[dict], sample_size: int) -> list[int]:
    raw = [sample_size * item["share"] / 100 for item in personas]
    base = [int(value) for value in raw]
    remainder = sample_size - sum(base)
    order = sorted(range(len(raw)), key=lambda idx: raw[idx] - base[idx], reverse=True)
    for idx in order[:remainder]:
        base[idx] += 1
    return base


def build_respondents(personas: list[dict], sample_size: int) -> list[dict]:
    counts = allocate_counts(personas, sample_size)
    respondents = []
    respondent_id = 1
    for persona, count in zip(personas, counts):
        for i in range(count):
            demographics = persona["demographics"]
            respondents.append({
                "respondent_id": respondent_id,
                "persona_type": persona["type"],
                "age_group": demographics["age"],
                "gender": demographics["gender"],
                "occupation": demographics["occupation"],
                "city_tier": demographics["city_tier"],
                "income_level": demographics["income_level"],
                "price_sensitivity": persona["price_sensitivity"],
                "digital_engagement": round(3 + ((respondent_id + i) % 3) * 0.5, 1),
                "privacy_concern": estimate_privacy_concern(persona["type"]),
            })
            respondent_id += 1
    return respondents


def estimate_privacy_concern(persona_type: str) -> float:
    if "青少年" in persona_type:
        return 4.8
    if "EAP" in persona_type:
        return 4.5
    if "高压职场" in persona_type:
        return 4.0
    if "慢性" in persona_type:
        return 4.2
    return 4.0


def build_choices(respondents: list[dict], personas: list[dict], profiles: list[dict], attributes: list[dict]) -> list[dict]:
    persona_map = {item["type"]: item for item in personas}
    attr_names = [item["name"] for item in attributes]
    choices = []

    for respondent in respondents:
        persona = persona_map.get(respondent["persona_type"], personas[0])
        scored_profiles = []
        for profile in profiles:
            utility, reasons = calc_utility(persona=persona, respondent=respondent, profile=profile)
            scored_profiles.append((utility, reasons, profile))
        scored_profiles.sort(key=lambda item: item[0], reverse=True)
        best_utility, best_reasons, best_profile = scored_profiles[0]
        second_best = scored_profiles[1][0] if len(scored_profiles) > 1 else best_utility
        choice_row = {
            "respondent_id": respondent["respondent_id"],
            "persona_type": respondent["persona_type"],
            "chosen_profile": best_profile["profile_id"],
            "utility_score": round(best_utility, 2),
            "utility_gap_vs_second": round(best_utility - second_best, 2),
            "choice_reason": "；".join(best_reasons[:3]) if best_reasons else "综合偏好匹配",
        }
        for attr_name in attr_names:
            choice_row[attr_name] = best_profile.get(attr_name, "")
        choices.append(choice_row)
    return choices


def calc_utility(persona: dict, respondent: dict, profile: dict):
    persona_type = persona["type"]
    price_sensitivity = float(persona.get("price_sensitivity", 3) or 3)
    privacy_concern = float(respondent.get("privacy_concern", 4) or 4)
    digital_engagement = float(respondent.get("digital_engagement", 3.5) or 3.5)

    price = str(profile.get("定价方案", ""))
    privacy = str(profile.get("隐私模式", ""))
    support = str(profile.get("支持方式", ""))
    feedback = str(profile.get("反馈机制", ""))

    utility = 0.0
    reasons = []

    if "免费" in price:
        score = 3.4 if price_sensitivity >= 4 else 1.5
        utility += score
        if score >= 2.5:
            reasons.append("对低门槛价格敏感")
    elif "19元" in price:
        score = 2.8 if 2.5 <= price_sensitivity <= 4 else 1.8
        utility += score
        if score >= 2.5:
            reasons.append("可接受轻度订阅付费")
    elif "59元" in price:
        score = 2.7 if price_sensitivity <= 2.5 else 0.9
        utility += score
        if score >= 2.3:
            reasons.append("高客单价并未显著劝退")

    if "匿名" in privacy:
        score = 2.4 if privacy_concern >= 4.2 else 1.4
        utility += score
        if score >= 2.2:
            reasons.append("偏好匿名表达与低暴露风险")
    elif "本地优先" in privacy:
        score = 2.6 if privacy_concern >= 4 else 1.8
        utility += score
        if score >= 2.3:
            reasons.append("重视更稳妥的数据控制")
    elif "实名" in privacy:
        score = 1.8 if ("EAP" in persona_type or "慢性" in persona_type) else 0.6
        utility += score
        if score >= 1.5:
            reasons.append("能接受长期追踪式管理")

    if "高压职场" in persona_type:
        if support == "AI+人工咨询转接":
            utility += 3.1
            reasons.append("需要高压场景下的专业升级服务")
        elif support == "AI+每周情绪报告":
            utility += 2.2
        if feedback == "风险预警+干预建议":
            utility += 2.5
            reasons.append("希望及时识别情绪风险")
        elif feedback == "每周成长报告":
            utility += 1.7
    elif "青少年" in persona_type or "大学生" in persona_type:
        if support == "纯AI日常陪伴":
            utility += 2.8
            reasons.append("更偏好低压力、可随时使用的陪伴")
        elif support == "AI+每周情绪报告":
            utility += 2.0
        if feedback == "每日情绪记录":
            utility += 2.4
            reasons.append("喜欢即时记录与表达")
        elif feedback == "每周成长报告":
            utility += 1.4
    elif "慢性" in persona_type:
        if support == "AI+人工咨询转接":
            utility += 3.2
            reasons.append("长期困扰更需要人工兜底")
        elif support == "AI+每周情绪报告":
            utility += 2.4
        if feedback == "风险预警+干预建议":
            utility += 2.8
            reasons.append("重视复发预警和持续追踪")
        elif feedback == "每周成长报告":
            utility += 1.9
    elif "EAP" in persona_type:
        if support == "AI+人工咨询转接":
            utility += 3.4
            reasons.append("企业场景更依赖专业服务闭环")
        elif support == "AI+每周情绪报告":
            utility += 2.1
        if feedback == "风险预警+干预建议":
            utility += 2.6
            reasons.append("企业更关注筛查与风险干预")
        elif feedback == "每周成长报告":
            utility += 1.5

    utility += (digital_engagement - 3.5) * 0.3
    utility += deterministic_noise(respondent_id=int(respondent["respondent_id"]), profile_id=str(profile["profile_id"]))

    return utility, reasons


def deterministic_noise(respondent_id: int, profile_id: str) -> float:
    profile_score = sum(ord(ch) for ch in profile_id)
    raw = (respondent_id * 17 + profile_score * 13) % 11
    return round((raw - 5) / 20, 2)


def build_profile_summary(choices: list[dict], profiles: list[dict]) -> list[dict]:
    total_n = max(len(choices), 1)
    counts = {}
    for row in choices:
        pid = str(row.get("chosen_profile", ""))
        counts[pid] = counts.get(pid, 0) + 1
    summary = []
    for profile in profiles:
        pid = profile["profile_id"]
        cnt = counts.get(pid, 0)
        entry = {"profile_id": pid, "chosen_count": cnt, "chosen_pct": round(cnt / total_n * 100, 1)}
        for key, value in profile.items():
            if key != "profile_id":
                entry[key] = value
        summary.append(entry)
    summary.sort(key=lambda item: item["chosen_count"], reverse=True)
    return summary


def build_segment_summary(choices: list[dict], personas: list[dict], attributes: list[dict]) -> list[dict]:
    summary = []
    for persona in personas:
        persona_type = persona["type"]
        subset = [row for row in choices if row.get("persona_type") == persona_type]
        if not subset:
            continue
        row = {
            "persona_type": persona_type,
            "sample_size": len(subset),
            "avg_utility": round(sum(float(item.get("utility_score", 0) or 0) for item in subset) / len(subset), 2),
        }
        for attr in attributes:
            attr_name = attr["name"]
            counter = {}
            for item in subset:
                level = str(item.get(attr_name, ""))
                counter[level] = counter.get(level, 0) + 1
            if counter:
                best_level = max(counter, key=counter.get)
                row[f"{attr_name}_top"] = best_level
        summary.append(row)
    return summary


def summarize_heterogeneity(persona_preference_summary: list[dict], attributes: list[dict]) -> list[str]:
    notes = []
    for attr in attributes:
        attr_name = attr["name"]
        top_levels = {row.get(f"{attr_name}_top", "") for row in persona_preference_summary if row.get(f"{attr_name}_top", "")}
        if len(top_levels) >= 2:
            notes.append(f"不同画像在“{attr_name}”上的偏好并不一致，后续更适合做分群版本而不是单一统一方案。")
            break
    if persona_preference_summary:
        notes.append("从分群结果看，高压职场奋斗者、慢性心理困扰者和企业EAP用户更偏向更强服务深度，而青少年与大学生群体更看重低门槛与匿名感。")
    return notes
