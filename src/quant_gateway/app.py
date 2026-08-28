"""Single-entry FastAPI gateway mounting every quant module's router.

Each backend module owns its own FastAPI ``APIRouter`` (with its own
package-internal service code) and is mounted here under a fixed prefix.
Adding a future module (e.g. Hong Kong stocks) is one line in MOUNTS.

Run from this project root::

    .venv\\Scripts\\python -m uvicorn quant_gateway.app:app --host 127.0.0.1 --port 8600
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse

MOUNTS: list[tuple[str, str]] = [
    # (prefix, module path that exposes create_router() -> APIRouter)
    ("/api/a-share", "ashare_quant.api.routes"),
]


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

    @app.get("/", include_in_schema=False)
    def index() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "modules": loaded}

    return app


app = create_app()
