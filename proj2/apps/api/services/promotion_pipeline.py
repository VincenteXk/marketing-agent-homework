from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Literal

from apps.api.services.llm_service import deepseek_chat_json
from apps.api.services.modelscope_image import generate_image_url
from apps.api.services.vlm_service import vlm_validate_image

ItemKind = Literal["slogan", "copy", "image_prompt_pair"]


def _ctx_block(c: dict[str, str]) -> str:
    return (
        f"【产品描述】\n{c['product'].strip()}\n\n"
        f"【推广目标】\n{c['goal'].strip()}\n\n"
        f"【总预算】\n{(c.get('budget') or '').strip() or '未指定'}\n\n"
        f"【渠道】\n{(c.get('channels') or '').strip() or '未指定'}\n"
    )


def _clamp_score(v: Any) -> int:
    try:
        n = int(round(float(v)))
        return max(1, min(10, n))
    except (TypeError, ValueError):
        return 5


def _score_messages(
    c: dict[str, str],
    item_kind: ItemKind,
    item_text: str,
    dimension: Literal["product", "channel", "creative"],
) -> list[dict[str, str]]:
    ctx = _ctx_block(c)
    dim_rubric = {
        "product": (
            "产品契合度：内容是否准确传达产品核心价值、卖点与推广目标，是否存在偏离或信息错误。"
        ),
        "channel": (
            "渠道/社区适配：结合用户给出的渠道，评估语气、信息密度与互动方式是否适合该平台生态与投放习惯。"
        ),
        "creative": (
            "创意与传播力：是否易记、有辨识度、表达简洁有力，并避免夸大宣传与明显违规表述。"
        ),
    }[dimension]

    if item_kind == "image_prompt_pair":
        if dimension == "product":
            dim_rubric = (
                "产品契合度（双图整体）：两条提示词共同呈现的意象是否准确传达产品、卖点与推广目标，是否协调一致。"
            )
        elif dimension == "channel":
            dim_rubric = (
                "渠道适配（双图整体）：在中国大陆主流投放环境（如小红书、抖音、电商详情等）下，"
                "画面气质与信息密度是否合适、可执行。"
            )
        else:
            dim_rubric = (
                "创意与执行（双图整体）：两图是否形成一套完整主视觉（如主图+场景/种草图），风格统一且互补，"
                "有辨识度；避免低俗、虚假宣传；场景应符合中国大陆日常真实环境，避免明显异国地标。"
            )
        kind_label = "中文双图生图提示词（图一+图二为同一套推广图，须整体评价）"
        pair_note = (
            "\n【说明】以下两段为同一套素材的两条中文文生图描述，请将它们视为一个整体打分。\n"
        )
    else:
        kind_label = {"slogan": "推广标语", "copy": "广告正文"}[item_kind]
        pair_note = "\n"

    system = (
        "你是严格、一致的营销评审。只输出 JSON，键为 score（1-10 整数）与 brief（一句中文理由，不超过 80 字）。"
    )
    user = (
        f"{ctx}{pair_note}"
        f"【待评{kind_label}】\n{item_text.strip()}\n\n"
        f"【评审维度】{dim_rubric}\n"
        "请仅输出 JSON：{\"score\":7,\"brief\":\"...\"}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _run_single_score(
    c: dict[str, str],
    item_kind: ItemKind,
    item_text: str,
    dimension: Literal["product", "channel", "creative"],
) -> dict[str, Any]:
    data = deepseek_chat_json(
        _score_messages(c, item_kind, item_text, dimension),
        max_tokens=256,
        temperature=0.15,
    )
    return {
        "score": _clamp_score(data.get("score")),
        "brief": str(data.get("brief") or "")[:200],
    }


def triple_mean_score(
    c: dict[str, str],
    item_kind: ItemKind,
    item_text: str,
) -> tuple[float, dict[str, dict[str, Any]]]:
    dims: tuple[Literal["product", "channel", "creative"], ...] = ("product", "channel", "creative")
    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        future_map = {
            pool.submit(_run_single_score, c, item_kind, item_text, d): d for d in dims
        }
        for fut in as_completed(future_map):
            d = future_map[fut]
            results[d] = fut.result()
    avg = sum(r["score"] for r in results.values()) / 3.0
    return avg, results


def _pick_best(
    c: dict[str, str],
    items: list[str],
    item_kind: Literal["slogan", "copy"],
) -> tuple[str, float, list[dict[str, Any]]]:
    best_text = ""
    best_avg = -1.0
    details: list[dict[str, Any]] = []
    for i, text in enumerate(items):
        t = text.strip()
        if not t:
            continue
        avg, breakdown = triple_mean_score(c, item_kind, t)
        details.append({"index": i + 1, "text": t, "avg": round(avg, 2), "breakdown": breakdown})
        if avg > best_avg:
            best_avg = avg
            best_text = t
    if not best_text:
        raise RuntimeError("没有可用的候选文本通过评分")
    return best_text, best_avg, details


def _format_pair_for_score(image_1: str, image_2: str) -> str:
    return (
        "【主视觉｜图一】\n"
        + image_1.strip()
        + "\n\n【辅视觉｜图二】\n"
        + image_2.strip()
        + "\n\n（以上两条为同一套推广主图，请整体评价。）"
    )


def _pick_best_pair(
    c: dict[str, str],
    pairs: list[tuple[str, str]],
) -> tuple[tuple[str, str], float, list[dict[str, Any]]]:
    best: tuple[str, str] = ("", "")
    best_avg = -1.0
    details: list[dict[str, Any]] = []
    for i, (a, b) in enumerate(pairs):
        a, b = a.strip(), b.strip()
        if not a or not b:
            continue
        block = _format_pair_for_score(a, b)
        avg, breakdown = triple_mean_score(c, "image_prompt_pair", block)
        details.append(
            {
                "index": i + 1,
                "image_1": a,
                "image_2": b,
                "avg": round(avg, 2),
                "breakdown": breakdown,
            }
        )
        if avg > best_avg:
            best_avg = avg
            best = (a, b)
    if not best[0]:
        raise RuntimeError("没有可用的双图提示词组通过评分")
    return best, best_avg, details


def _generate_five_slogans(c: dict[str, str]) -> list[str]:
    user = (
        _ctx_block(c)
        + "\n请生成 5 条互不重复、适合上述产品与渠道的推广标语（Slogan），"
        "每条建议不超过 24 个汉字，语气积极、具体。\n"
        '输出严格 JSON：{"slogans":["标语1","标语2","标语3","标语4","标语5"]}'
    )
    data = deepseek_chat_json(
        [
            {"role": "system", "content": "你是资深中文营销文案，只输出合法 JSON。"},
            {"role": "user", "content": user},
        ],
        max_tokens=512,
        temperature=0.85,
    )
    slogans = data.get("slogans")
    if not isinstance(slogans, list):
        raise RuntimeError("标语 JSON 缺少 slogans 数组")
    out = [str(x).strip() for x in slogans if str(x).strip()]
    if len(out) < 5:
        raise RuntimeError(f"标语数量不足 5（实际 {len(out)}）")
    return out[:5]


def _generate_five_copies(c: dict[str, str], slogan: str) -> list[str]:
    user = (
        _ctx_block(c)
        + f"\n【已定标语】{slogan}\n\n"
        "请基于上述信息，写 5 段**不同切入点**的广告正文，每段 **50–120 个汉字**（含标点），"
        "适合给定渠道传播，可含一句行动号召。\n"
        '输出严格 JSON：{"copies":["正文1","正文2","正文3","正文4","正文5"]}'
    )
    data = deepseek_chat_json(
        [
            {"role": "system", "content": "你是资深中文广告文案，只输出合法 JSON。每段字数必须在 50–120 汉字之间。"},
            {"role": "user", "content": user},
        ],
        max_tokens=1800,
        temperature=0.75,
    )
    copies = data.get("copies")
    if not isinstance(copies, list):
        raise RuntimeError("正文 JSON 缺少 copies 数组")
    out = [str(x).strip() for x in copies if str(x).strip()]
    if len(out) < 5:
        raise RuntimeError(f"正文数量不足 5（实际 {len(out)}）")
    return out[:5]


def _parse_pair_item(raw: Any) -> tuple[str, str] | None:
    if isinstance(raw, dict):
        a = str(raw.get("image_1") or raw.get("图一") or raw.get("primary") or "").strip()
        b = str(raw.get("image_2") or raw.get("图二") or raw.get("secondary") or "").strip()
        if a and b:
            return (a, b)
    if isinstance(raw, list) and len(raw) >= 2:
        a, b = str(raw[0]).strip(), str(raw[1]).strip()
        if a and b:
            return (a, b)
    return None


def _generate_five_image_pairs(c: dict[str, str], slogan: str, copy_text: str) -> list[tuple[str, str]]:
    user = (
        _ctx_block(c)
        + f"\n【已定标语】{slogan}\n【已定广告正文】\n{copy_text}\n\n"
        "请设计 **5 套** 互不重复的中文文生图方案。每一套必须包含 **2 条** 提示词，共同组成同一套推广主图：\n"
        "· 图一：主视觉，突出产品/品类识别与记忆点；\n"
        "· 图二：与图一配套，侧重真实使用场景、种草氛围或细节特写，与图一风格统一、叙事互补。\n\n"
        "场景、人物与建筑须符合 **中国大陆** 日常真实环境（居家、商圈、地铁、办公室、公园等），"
        "避免明显异国街景或地标；光线与审美贴合国内主流社交/电商素材。\n"
        "不要要求在画面内绘制水印、Logo 或大字标语。\n"
        '输出严格 JSON：{"pairs":[{"image_1":"图一中文提示词","image_2":"图二中文提示词"}, ...]}，pairs 长度必须为 5。'
    )
    data = deepseek_chat_json(
        [
            {
                "role": "system",
                "content": "你是资深视觉创意与美术指导，只输出合法 JSON。提示词为中文，供文生图模型使用。",
            },
            {"role": "user", "content": user},
        ],
        max_tokens=2800,
        temperature=0.75,
    )
    raw_pairs = data.get("pairs")
    if not isinstance(raw_pairs, list):
        raise RuntimeError("生图 JSON 缺少 pairs 数组")
    out: list[tuple[str, str]] = []
    for item in raw_pairs:
        p = _parse_pair_item(item)
        if p:
            out.append(p)
    if len(out) < 5:
        raise RuntimeError(f"有效双图组不足 5（实际 {len(out)}）")
    return out[:5]


def _format_slogan_report(slogans: list[str], best: str, avg: float, details: list[dict[str, Any]]) -> str:
    lines = ["【候选标语（5 条）】"]
    for i, s in enumerate(slogans, 1):
        lines.append(f"{i}. {s}")
    lines.append("")
    lines.append("【三维度评分规则】产品契合度 / 渠道适配 / 创意与传播力；每条候选取三者均分。")
    lines.append("")
    lines.append("【各条均分】")
    for d in details:
        br = d["breakdown"]
        lines.append(
            f"  · 第{d['index']}条 均分 {d['avg']}  "
            f"(产品{br['product']['score']} 渠道{br['channel']['score']} 创意{br['creative']['score']})"
        )
    lines.append("")
    lines.append(f"【选用标语】{best}")
    lines.append(f"（均分 {round(avg, 2)}）")
    return "\n".join(lines)


def _format_copy_report(copies: list[str], best: str, avg: float, details: list[dict[str, Any]]) -> str:
    lines = ["【候选正文（5 段，50–120 字）】"]
    for i, s in enumerate(copies, 1):
        lines.append(f"--- 第 {i} 段 ---\n{s}\n")
    lines.append("【各段均分】")
    for d in details:
        br = d["breakdown"]
        lines.append(
            f"  · 第{d['index']}段 均分 {d['avg']}  "
            f"(产品{br['product']['score']} 渠道{br['channel']['score']} 创意{br['creative']['score']})"
        )
    lines.append("")
    lines.append("【选用正文】")
    lines.append(best)
    lines.append(f"（均分 {round(avg, 2)}；字数 {len(best)}）")
    return "\n".join(lines)


def _format_pair_report(
    pairs: list[tuple[str, str]],
    best: tuple[str, str],
    avg: float,
    details: list[dict[str, Any]],
) -> str:
    lines = ["【候选中文双图提示词（5 套，每套图一+图二）】"]
    for i, (a, b) in enumerate(pairs, 1):
        lines.append(f"--- 第 {i} 套 ---")
        lines.append(f"图一：{a}")
        lines.append(f"图二：{b}")
        lines.append("")
    lines.append("【三维度评分】对每套双图作整体评价后取均分（产品契合 / 渠道适配 / 创意与双图协调性）。")
    lines.append("")
    lines.append("【各套均分】")
    for d in details:
        br = d["breakdown"]
        lines.append(
            f"  · 第{d['index']}套 均分 {d['avg']}  "
            f"(产品{br['product']['score']} 渠道{br['channel']['score']} 创意{br['creative']['score']})"
        )
    lines.append("")
    lines.append("【选用一套双图提示词】")
    lines.append(f"图一：{best[0]}")
    lines.append(f"图二：{best[1]}")
    lines.append(f"（均分 {round(avg, 2)}）")
    return "\n".join(lines)


def iter_promotion_events(c: dict[str, str]) -> Iterator[dict[str, Any]]:
    yield {"event": "stage", "stage": "strategy", "status": "active"}
    yield {"event": "stage", "stage": "strategy", "status": "update", "text": "正在生成 5 条标语…"}

    slogans = _generate_five_slogans(c)
    yield {
        "event": "stage",
        "stage": "strategy",
        "status": "update",
        "text": "已生成 5 条标语，三模型并行评分中（产品契合 / 渠道适配 / 创意）…",
    }

    best_slogan, avg_s, detail_s = _pick_best(c, slogans, "slogan")
    text_s = _format_slogan_report(slogans, best_slogan, avg_s, detail_s)
    yield {"event": "stage", "stage": "strategy", "status": "done", "text": text_s}

    yield {"event": "stage", "stage": "copy", "status": "active"}
    yield {"event": "stage", "stage": "copy", "status": "update", "text": "正在生成 5 段广告正文…"}

    copies = _generate_five_copies(c, best_slogan)
    yield {"event": "stage", "stage": "copy", "status": "update", "text": "已生成 5 段正文，并行评分中…"}

    best_copy, avg_c, detail_c = _pick_best(c, copies, "copy")
    text_c = _format_copy_report(copies, best_copy, avg_c, detail_c)
    yield {"event": "stage", "stage": "copy", "status": "done", "text": text_c}

    yield {"event": "stage", "stage": "visual_plan", "status": "active"}
    yield {"event": "stage", "stage": "visual_plan", "status": "update", "text": "正在生成 5 套中文双图生图提示词…"}

    pairs = _generate_five_image_pairs(c, best_slogan, best_copy)
    yield {"event": "stage", "stage": "visual_plan", "status": "update", "text": "已生成 5 套双图 prompt，按「一套两张」整体并行评分中…"}

    best_pair, avg_p, detail_p = _pick_best_pair(c, pairs)
    text_p = _format_pair_report(pairs, best_pair, avg_p, detail_p)
    yield {"event": "stage", "stage": "visual_plan", "status": "done", "text": text_p}

    yield {"event": "stage", "stage": "visual_iterate", "status": "active"}
    yield {
        "event": "stage",
        "stage": "visual_iterate",
        "status": "update",
        "text": "已选用最高分的一套双图提示词；每轮并行验收图一、图二，未通过侧用相同提示词重绘，"
        "已通过侧沿用且不重复送验；整流程最多 **5 版**（首版 + 4 轮迭代）。",
    }

    p1, p2 = best_pair
    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(generate_image_url, p1)
        f2 = pool.submit(generate_image_url, p2)
        url1 = f1.result()
        url2 = f2.result()

    urls: list[str] = [url1, url2]
    prompts = [p1, p2]
    passed_locked: list[bool] = [False, False]
    qa_log: list[str] = []
    version = 1
    max_versions = 5
    before_regen = urls.copy()

    while True:
        kept = [False, False] if version == 1 else [urls[s] == before_regen[s] for s in (0, 1)]
        yield {
            "event": "stage",
            "stage": "visual_iterate",
            "status": "round_images",
            "round": version,
            "image_urls": list(urls),
            "kept": kept,
        }

        results_payload: list[dict[str, object]] = []
        for slot in (0, 1):
            label = "推广图一" if slot == 0 else "推广图二"
            if passed_locked[slot]:
                results_payload.append(
                    {
                        "slot": slot,
                        "passed": True,
                        "skipped": True,
                        "reason": "该图已在之前轮次通过验收，本版沿用且未重复送验。",
                    }
                )
                continue
            ok, reason = vlm_validate_image(urls[slot], prompts[slot])
            if ok:
                passed_locked[slot] = True
            qa_log.append(f"{label}（第 {version} 版）：{'通过' if ok else '未通过'} — {reason}")
            results_payload.append(
                {
                    "slot": slot,
                    "passed": ok,
                    "skipped": False,
                    "reason": reason,
                }
            )

        yield {
            "event": "stage",
            "stage": "visual_iterate",
            "status": "round_qa",
            "round": version,
            "results": results_payload,
        }

        if passed_locked[0] and passed_locked[1]:
            break
        if version >= max_versions:
            break

        before_regen = urls.copy()
        for s in (0, 1):
            if not passed_locked[s]:
                urls[s] = generate_image_url(prompts[s])
        version += 1

    yield {
        "event": "stage",
        "stage": "visual_iterate",
        "status": "done",
        "text": "\n".join(qa_log),
    }

    final_urls = list(urls)

    yield {
        "event": "done",
        "data": {
            "slogan": best_slogan,
            "copy": best_copy,
            "image_prompt_1": p1,
            "image_prompt_2": p2,
            "image_urls": final_urls,
        },
    }
