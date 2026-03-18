from __future__ import annotations

import json
from urllib import error, request

from apps.api.settings import settings


def _deepseek_chat(
    messages: list[dict[str, str]],
    max_tokens: int = 512,
    temperature: float = 0.2,
    force_json: bool = False,
) -> dict:
    if not settings.deepseek_api_key:
        raise RuntimeError("missing DEEPSEEK_API_KEY")

    url = f"{settings.deepseek_base_url.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": settings.deepseek_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if force_json:
        payload["response_format"] = {"type": "json_object"}
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
    with request.urlopen(req, timeout=40) as resp:
        body = resp.read().decode("utf-8")
        parsed = json.loads(body)
        if "choices" not in parsed or not parsed["choices"]:
            raise RuntimeError(f"invalid llm response: {body[:500]}")
        return parsed


def deepseek_chat_text(messages: list[dict[str, str]], max_tokens: int = 512, temperature: float = 0.2) -> str:
    try:
        parsed = _deepseek_chat(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            force_json=False,
        )
        content = parsed["choices"][0]["message"]["content"].strip()
        if not content:
            raise RuntimeError("empty llm content")
        return content
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"http {exc.code}: {detail[:500]}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"request failed: {exc}") from exc


def deepseek_chat_json(messages: list[dict[str, str]], max_tokens: int = 1024) -> dict:
    try:
        parsed = _deepseek_chat(
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.1,
            force_json=True,
        )
        raw = parsed["choices"][0]["message"]["content"].strip()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"http {exc.code}: {detail[:500]}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"request failed: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"llm returned non-json content: {raw[:300]}") from exc


def deepseek_chat_json_stream(messages: list[dict[str, str]], max_tokens: int = 1024):
    if not settings.deepseek_api_key:
        raise RuntimeError("missing DEEPSEEK_API_KEY")

    url = f"{settings.deepseek_base_url.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": settings.deepseek_model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "stream": True,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
    )
    try:
        with request.urlopen(req, timeout=90) as resp:
            raw_parts: list[str] = []
            for raw in resp:
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line or not line.startswith("data:"):
                    continue
                data_part = line[5:].strip()
                if not data_part:
                    continue
                if data_part == "[DONE]":
                    break
                try:
                    payload_obj = json.loads(data_part)
                except json.JSONDecodeError:
                    continue
                choices = payload_obj.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                piece = str(delta.get("content") or "")
                if piece:
                    raw_parts.append(piece)
                    yield {"type": "delta", "content": piece}
            full_raw = "".join(raw_parts).strip()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"http {exc.code}: {detail[:500]}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"request failed: {exc}") from exc

    try:
        parsed = json.loads(full_raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"llm returned non-json content: {full_raw[:300]}") from exc

    yield {"type": "done", "raw": full_raw, "parsed": parsed}


def deepseek_ping(prompt: str = "ping") -> dict[str, str]:
    content = deepseek_chat_text(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=64,
        temperature=0.2,
    )
    return {"ok": "true", "message": content}
