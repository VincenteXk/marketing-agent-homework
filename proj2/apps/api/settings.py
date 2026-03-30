from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def bootstrap_env() -> None:
    _load_env_file(ROOT / ".env")
    _load_env_file(ROOT / ".env.local")


bootstrap_env()


def _opt_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _opt_float(name: str) -> float | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


class Settings:
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    text2image_access_key_id: str = os.getenv("TEXT2IMAGE_ACCESS_KEY_ID", "")
    text2image_secret_access_key: str = os.getenv("TEXT2IMAGE_SECRET_ACCESS_KEY", "")
    # text2image size 为面积，默认 2048*2048（2K）
    text2image_size: int | None = _opt_int("TEXT2IMAGE_SIZE") or 2048 * 2048
    text2image_poll_interval_sec: float = _opt_float("TEXT2IMAGE_POLL_INTERVAL_SEC") or 3.0
    text2image_poll_max_attempts: int = _opt_int("TEXT2IMAGE_POLL_MAX_ATTEMPTS") or 80
    vlm_ark_api_key: str = os.getenv("VLM_ARK_API_KEY", "")
    vlm_model: str = os.getenv("VLM_MODEL", "doubao-seed-1-6-flash-250828")


settings = Settings()
