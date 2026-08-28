"""Single-entry FastAPI gateway mounting every quant module's router.

Each backend module owns its own FastAPI ``APIRouter`` (with its own
package-internal service code) and is mounted here under a fixed prefix.
Adding a future module (e.g. Hong Kong stocks) is one line in MOUNTS.

If ``web-portal/dist`` exists, the built frontend is served from this same
process, so one ``uvicorn`` process runs the whole portal::

    .venv\\Scripts\\python -m uvicorn quant_gateway.app:app --host 127.0.0.1 --port 8600

The API stays available under ``/api/...`` and the docs at ``/docs``.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

MOUNTS: list[tuple[str, str]] = [
    # (prefix, module path that exposes create_router() -> APIRouter)
    ("/api/a-share", "ashare_quant.api.routes"),
]

# Repo root / web-portal build output (src/quant_gateway/app.py -> parents[2]).
PORTAL_DIST = Path(__file__).resolve().parents[2] / "web-portal" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Quant Portal API",
        version="0.1.0",
        description="Unified read gateway over quant research modules.",
    )
    app.add_middleware(GZipMiddleware, minimum_size=500)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    import importlib

    loaded: list[str] = []
    for prefix, module_path in MOUNTS:
        module = importlib.import_module(module_path)
        app.include_router(module.create_router(), prefix=prefix)
        loaded.append(prefix)

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "modules": loaded, "portal": PORTAL_DIST.is_dir()}

    if PORTAL_DIST.is_dir():
        # Serve the built Vue app from this process: one process, one port.
        app.mount(
            "/assets",
            StaticFiles(directory=PORTAL_DIST / "assets"),
            name="portal-assets",
        )

        @app.get("/{path:path}", include_in_schema=False)
        def portal(path: str) -> FileResponse:
            candidate = PORTAL_DIST / path
            if path and candidate.is_file():
                # Everything under dist/ is generated output; the run_id
                # prefix in _run_dir-style guards does not apply here.
                resolved = candidate.resolve()
                if resolved.is_relative_to(PORTAL_DIST.resolve()):
                    return FileResponse(resolved)
            # SPA history-mode fallback: deep links render index.html.
            return FileResponse(PORTAL_DIST / "index.html")
    else:

        @app.get("/", include_in_schema=False)
        def index() -> RedirectResponse:
            return RedirectResponse(url="/docs")

    return app


app = create_app()
