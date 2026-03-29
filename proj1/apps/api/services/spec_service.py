from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy

from apps.api.models import ProjectSpec
from apps.api.services.llm_service import deepseek_chat_json


def _normalize_text(messages: Iterable[str]) -> str:
    return "\n".join([m.strip() for m in messages if m and m.strip()])


def _llm_extract_patch(text: str) -> ProjectSpec:
    messages = [
        {
            "role": "system",
            "content": (
                "你是项目规格抽取器。"
                "请根据用户对话提取 project spec patch，且只输出 JSON。"
                "JSON 结构必须是："
                "{"
                "\"domain\": string,"
                "\"goal\": string,"
                "\"target_users\": string[],"
                "\"constraints\": {\"timeline\": string, \"budget\": string, \"sample_size\": number, \"must_use_credamo\": boolean},"
                "\"deliverables\": {\"deadline\": string},"
                "\"notes\": string"
                "}"
                "若无法确定某字段，返回空字符串或空数组；不要输出解释文本。"
            ),
        },
        {"role": "user", "content": text},
    ]
    patch_json = deepseek_chat_json(messages=messages, max_tokens=1200)
    return ProjectSpec(**patch_json)


def merge_specs(base: ProjectSpec, patch: ProjectSpec) -> ProjectSpec:
    merged = deepcopy(base.model_dump())
    patch_dict = patch.model_dump()
    for key, value in patch_dict.items():
        if isinstance(value, dict):
            merged[key].update({k: v for k, v in value.items() if v not in ("", [], None)})
            continue
        if value not in ("", [], None):
            merged[key] = value
    return ProjectSpec(**merged)


def extract_spec_from_chat(chat_messages: list[str], current_spec: ProjectSpec | None = None) -> ProjectSpec:
    text = _normalize_text(chat_messages)
    if not text:
        raise ValueError("chat_messages 不能为空")
    patch = _llm_extract_patch(text)

    if current_spec is None:
        return patch
    return merge_specs(current_spec, patch)


def validate_spec(spec: ProjectSpec) -> dict[str, list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not spec.domain:
        errors.append("domain 不能为空")
    if not spec.goal:
        errors.append("goal 不能为空")
    if len(spec.target_users) == 0:
        errors.append("target_users 至少需要 1 个用户群体")
    if spec.constraints.sample_size <= 0:
        errors.append("constraints.sample_size 必须大于 0")
    if spec.constraints.sample_size < 50:
        warnings.append("样本量较小，可能影响稳定性")
    if not spec.deliverables.deadline:
        warnings.append("deliverables.deadline 为空，建议补充")

    return {"errors": errors, "warnings": warnings}
