from __future__ import annotations

import time

from volcengine.visual.VisualService import VisualService

from apps.api.settings import settings

TEXT2IMAGE_REQ_KEY = "jimeng_t2i_v40"


def create_text2image_task(prompt: str) -> str:
    if not settings.text2image_access_key_id or not settings.text2image_secret_access_key:
        raise RuntimeError("missing TEXT2IMAGE_ACCESS_KEY_ID or TEXT2IMAGE_SECRET_ACCESS_KEY")
    visual_service = VisualService()
    visual_service.set_ak(settings.text2image_access_key_id)
    visual_service.set_sk(settings.text2image_secret_access_key)

    payload: dict[str, object] = {
        "req_key": TEXT2IMAGE_REQ_KEY,
        "prompt": prompt.strip(),
        "force_single": True,
    }
    if settings.text2image_size is not None:
        payload["size"] = settings.text2image_size

    data = visual_service.cv_sync2async_submit_task(payload)
    if int(data.get("code", 0) or 0) != 10000:
        raise RuntimeError(f"text2image submit failed: {data.get('message') or str(data)[:500]}")
    d = data.get("data")
    task_id = d.get("task_id") if isinstance(d, dict) else None
    if not task_id:
        raise RuntimeError(f"text2image 无 task_id: {str(data)[:500]}")
    return str(task_id)


def poll_text2image_task(task_id: str) -> dict:
    if not settings.text2image_access_key_id or not settings.text2image_secret_access_key:
        raise RuntimeError("missing TEXT2IMAGE_ACCESS_KEY_ID or TEXT2IMAGE_SECRET_ACCESS_KEY")
    visual_service = VisualService()
    visual_service.set_ak(settings.text2image_access_key_id)
    visual_service.set_sk(settings.text2image_secret_access_key)

    payload = {
        "req_key": TEXT2IMAGE_REQ_KEY,
        "task_id": task_id,
        "req_json": '{"return_url":true}',
    }
    return visual_service.cv_get_result(payload)


def generate_text2image_url(
    prompt: str,
    interval_sec: float | None = None,
    max_attempts: int | None = None,
) -> str:
    interval = (
        interval_sec if interval_sec is not None else settings.text2image_poll_interval_sec
    )
    attempts = (
        max_attempts if max_attempts is not None else settings.text2image_poll_max_attempts
    )
    task_id = create_text2image_task(prompt)
    for _ in range(attempts):
        time.sleep(interval)
        data = poll_text2image_task(task_id)
        if int(data.get("code", 0) or 0) != 10000:
            raise RuntimeError(data.get("message") or "图片生成失败")
        payload = data.get("data")
        status = payload.get("status") if isinstance(payload, dict) else None
        if status == "done":
            urls = payload.get("image_urls") if isinstance(payload, dict) else []
            if not urls:
                raise RuntimeError("任务完成但无 image_urls")
            return str(urls[0])
        if status in ("not_found", "expired"):
            raise RuntimeError(f"任务状态异常: {status}")
    raise RuntimeError("文生图轮询超时")
