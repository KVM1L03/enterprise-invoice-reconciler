"""Shared FastAPI dependencies — tenant resolution for demo isolation."""

from __future__ import annotations

import os

from fastapi import Header, HTTPException, status

GLOBAL_TENANT = "global"
DEMO_SESSION_PREFIX = "demo_"


def is_demo_mode() -> bool:
    """``DEMO_MODE=true`` flips the whole instance into multi-tenant demo mode."""
    return os.environ.get("DEMO_MODE", "false").strip().lower() == "true"


def get_tenant_id(
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> str:
    """Resolve the tenant for the current request.

    - Local dev (``DEMO_MODE=false``): always returns ``"global"``.
    - Demo mode: ``X-Session-Id`` header is required and must be a
      ``demo_<uuid>`` value previously minted by ``/demo/init``.
    """
    if not is_demo_mode():
        return GLOBAL_TENANT

    if not x_session_id or not x_session_id.startswith(DEMO_SESSION_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Demo mode is active. Call POST /demo/init first and resend "
                "the returned session_id in the X-Session-Id header."
            ),
        )
    return x_session_id
