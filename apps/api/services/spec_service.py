from __future__ import annotations

import re
from collections.abc import Iterable
from copy import deepcopy

from apps.api.models import ProjectSpec


def _normalize_text(messages: Iterable[str]) -> str:
    return "\n".join([m.strip() for m in messages if m and m.strip()])


def _extract_sample_size(text: str) -> int | None:
    patterns = [
        r"样本(?:量|数)?\s*[：: ]\s*(\d+)",
        r"sample(?:\s*size)?\s*[：: ]\s*(\d+)",
        r"(\d+)\s*份(?:问卷|样本)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _extract_deadline(text: str) -> str:
    match = re.search(r"(\d{1,2}[./-]\d{1,2}(?:\s+\d{1,2}:\d{2})?)", text)
    return match.group(1) if match else ""


def _extract_target_users(text: str) -> list[str]:
    candidates = []
    keyword_groups = [
        ("大学生", ["大学生"]),
        ("职场年轻人", ["职场", "白领", "上班族", "年轻人"]),
        ("银发人群", ["银发", "中老年", "老人"]),
        ("青少年", ["青少年", "中学生", "高中生"]),
    ]
    for label, words in keyword_groups:
        if any(word in text for word in words):
            candidates.append(label)
    return list(dict.fromkeys(candidates))


def _extract_domain(text: str) -> str:
    if "AI陪伴" in text or "陪伴APP" in text or "陪伴app" in text.lower():
        return "AI陪伴APP"
    return ""


def _extract_goal(text: str) -> str:
    if "情绪" in text and "成长" in text:
        return "为目标用户提供情绪支持与日常成长支持"
    if "情绪" in text:
        return "为目标用户提供情绪支持"
    if "成长" in text:
        return "为目标用户提供日常成长支持"
    if "AI陪伴" in text or "陪伴APP" in text or "陪伴app" in text.lower():
        return "围绕AI陪伴场景完成市场验证与产品策略设计"
    return ""


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
    patch = ProjectSpec()

    patch.domain = _extract_domain(text)
    patch.goal = _extract_goal(text)
    patch.target_users = _extract_target_users(text)

    sample_size = _extract_sample_size(text)
    if sample_size is not None:
        patch.constraints.sample_size = sample_size

    deadline = _extract_deadline(text)
    if deadline:
        patch.deliverables.deadline = deadline

    if "credamo" in text.lower():
        patch.constraints.must_use_credamo = True

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
