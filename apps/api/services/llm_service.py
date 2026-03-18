from __future__ import annotations

import json
from urllib import error, request

from apps.api.settings import settings


def deepseek_ping(prompt: str = "ping") -> dict[str, str]:
    if not settings.deepseek_api_key:
        return {"ok": "false", "message": "missing DEEPSEEK_API_KEY"}

    url = f"{settings.deepseek_base_url.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": settings.deepseek_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 64,
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=25) as resp:
            body = resp.read().decode("utf-8")
            parsed = json.loads(body)
            content = (
                parsed.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            return {"ok": "true", "message": content or "empty response"}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return {"ok": "false", "message": f"http {exc.code}: {detail[:500]}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": "false", "message": f"request failed: {exc}"}
