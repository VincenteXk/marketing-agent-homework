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
    modelscope_token: str = os.getenv("MODELSCOPE_API_KEY", "") or os.getenv("MODELSCOPE_TOKEN", "")
    modelscope_image_model: str = os.getenv("MODELSCOPE_IMAGE_MODEL", "Tongyi-MAI/Z-Image-Turbo")
    # 见仓库内 `生图.md`：Z-Image-Turbo 适合 1024 级分辨率与固定步数；魔搭 HTTP 若不支持某字段可留空省略
    modelscope_image_size: str = os.getenv("MODELSCOPE_IMAGE_SIZE", "1024x1024").strip()
    modelscope_image_steps: int | None = _opt_int("MODELSCOPE_IMAGE_STEPS")
    modelscope_image_guidance: float | None = _opt_float("MODELSCOPE_IMAGE_GUIDANCE")
    vlm_ark_api_key: str = os.getenv("VLM_ARK_API_KEY", "")
    vlm_model: str = os.getenv("VLM_MODEL", "doubao-seed-1-6-flash-250828")


settings = Settings()
