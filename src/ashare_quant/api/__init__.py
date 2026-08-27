"""HTTP API layer for the A-share module (FastAPI, read-only).

The quant gateway mounts :func:`create_router` under a prefix::

    app.include_router(create_a_share_router(), prefix="/api/a-share")
"""

from __future__ import annotations

from fastapi import APIRouter

from ashare_quant.api.routes import create_router


def create_a_share_router() -> APIRouter:
    """Factory so the gateway can own instantiation."""
    return create_router()


__all__ = ["create_a_share_router"]
