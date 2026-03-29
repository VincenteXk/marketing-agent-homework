from __future__ import annotations

import json
import time
from urllib import error, request

from apps.api.settings import settings

MODEL_SCOPE_BASE = "https://api-inference.modelscope.cn"


def _headers_create() -> dict[str, str]:
    key = settings.modelscope_token
    if not key:
        raise RuntimeError("missing MODELSCOPE_TOKEN or MODELSCOPE_API_KEY")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-ModelScope-Async-Mode": "true",
    }


def _headers_poll() -> dict[str, str]:
    key = settings.modelscope_token
    if not key:
        raise RuntimeError("missing MODELSCOPE_TOKEN or MODELSCOPE_API_KEY")
    return {
        "Authorization": f"Bearer {key}",
        "X-ModelScope-Task-Type": "image_generation",
    }


def create_image_task(prompt: str) -> str:
    body = json.dumps(
        {
            "model": settings.modelscope_image_model,
            "prompt": prompt.strip(),
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = request.Request(
        f"{MODEL_SCOPE_BASE}/v1/images/generations",
        data=body,
        method="POST",
        headers=_headers_create(),
    )
    try:
        with request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"modelscope create http {exc.code}: {detail[:800]}") from exc
    data = json.loads(text)
    task_id = data.get("task_id")
    if not task_id:
        raise RuntimeError(f"modelscope 无 task_id: {text[:500]}")
    return str(task_id)


def poll_task(task_id: str) -> dict:
    req = request.Request(
        f"{MODEL_SCOPE_BASE}/v1/tasks/{task_id}",
        method="GET",
        headers=_headers_poll(),
    )
    try:
        with request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"modelscope poll http {exc.code}: {detail[:800]}") from exc
    return json.loads(text)


def generate_image_url(prompt: str, interval_sec: float = 3.0, max_attempts: int = 80) -> str:
    task_id = create_image_task(prompt)
    for _ in range(max_attempts):
        time.sleep(interval_sec)
        data = poll_task(task_id)
        status = data.get("task_status")
        if status == "SUCCEED":
            urls = data.get("output_images") or []
            if not urls:
                raise RuntimeError("任务成功但无 output_images")
            return str(urls[0])
        if status == "FAILED":
            raise RuntimeError(data.get("message") or "图片生成失败")
    raise RuntimeError("文生图轮询超时")
