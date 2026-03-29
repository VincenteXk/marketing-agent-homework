from __future__ import annotations

import json
from pathlib import Path
from urllib import error, parse, request

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from apps.api.models import PromotionRequest
from apps.api.services.promotion_pipeline import iter_promotion_events

app = FastAPI(title="Proj2 Promotion Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def disable_static_cache(request: Request, call_next):
    """开发/交作业截图时减少 304 缓存命中；静态与首页始终带 no-store。"""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/") or path in ("/", "/index.html"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response


ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT / "apps" / "web"

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(
        WEB_DIR / "index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "proj2"}


def _allowed_image_host(hostname: str) -> bool:
    h = hostname.lower()
    return (
        "modelscope" in h
        or h.endswith(".cn")
        or "aliyuncs.com" in h
    )


@app.get("/promotion/proxy-image")
def proxy_image(url: str = Query(..., description="HTTPS 图片 URL")) -> Response:
    try:
        parsed = parse.urlparse(url)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="invalid url") from exc
    if parsed.scheme != "https":
        raise HTTPException(status_code=400, detail="only https")
    if not _allowed_image_host(parsed.hostname or ""):
        raise HTTPException(status_code=400, detail="host not allowed")

    try:
        req = request.Request(url, method="GET", headers={"User-Agent": "proj2-promotion/1.0"})
        with request.urlopen(req, timeout=60) as resp:
            data = resp.read()
            ct = resp.headers.get("Content-Type", "image/jpeg")
    except error.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"upstream {exc.code}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return Response(content=data, media_type=ct)


@app.post("/promotion/stream")
def promotion_stream(payload: PromotionRequest) -> StreamingResponse:
    ctx = payload.model_dump()

    def event_iter():
        try:
            for ev in iter_promotion_events(ctx):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001
            err = {"event": "error", "message": str(exc)}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_iter(), media_type="text/event-stream")
