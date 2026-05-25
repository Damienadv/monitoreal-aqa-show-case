"""API-key auth: middleware считывает X-API-Key, depend'ы проверяют роль."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response

from mock_server.config import get_settings

OPEN_PATHS: set[str] = {"/", "/ui/login", "/health", "/docs", "/redoc", "/api/v1/openapi.json"}
UI_PREFIXES: tuple[str, ...] = ("/rules", "/archive", "/cameras/", "/static")


async def auth_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Кладёт в request.state роль по X-API-Key. Открытые пути пропускает без проверки."""
    path = request.url.path
    if path in OPEN_PATHS or path.startswith(UI_PREFIXES):
        # UI-страницы делают свой role-check через cookie в роутере.
        return await call_next(request)

    # Для API: X-API-Key из header, либо cookie (фолбэк для UI → /api/v1/* вызовов).
    key = (
        request.headers.get("X-API-Key")
        or request.headers.get("x-api-key")
        or request.cookies.get("api_key")
    )
    role = get_settings().api_keys.get(key) if key else None
    if role is None:
        return JSONResponse(
            status_code=401,
            content={
                "type": "about:blank",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Missing or invalid API key",
                "instance": path,
            },
            media_type="application/problem+json",
        )

    request.state.role = role
    return await call_next(request)


def require_role(*roles: str) -> Callable[..., Awaitable[str]]:
    """FastAPI dependency: пускает только если роль клиента входит в allowlist."""

    async def _checker(request: Request) -> str:
        role: str | None = getattr(request.state, "role", None)
        if role is None:
            raise HTTPException(status_code=401, detail="Unauthorized")
        if role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' is not allowed (need one of: {', '.join(roles)})",
            )
        return role

    return _checker


_AnyDep: Any = None  # для подавления mypy attr-defined warning ниже


def get_current_role(request: Request) -> str:
    role: str | None = getattr(request.state, "role", None)
    if role is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return role


require_any_authenticated = Depends(get_current_role)
require_admin = Depends(require_role("admin"))
require_camera_or_admin = Depends(require_role("camera", "admin"))
