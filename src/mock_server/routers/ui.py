"""UI-роутер: Jinja2 страницы login/rules/archive.

Auth: cookie `api_key`. Без cookie — редирект на /. Защищены только UI-страницы,
не /api/v1 (там — X-API-Key через middleware).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import false, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mock_server.config import get_settings
from mock_server.db import get_session
from mock_server.models import ArchiveItem, Camera, Rule

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["ui"])


def _role_from_cookie(request: Request) -> str | None:
    key = request.cookies.get("api_key")
    if not key:
        return None
    return get_settings().api_keys.get(key)


@router.get("/", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    if _role_from_cookie(request):
        return RedirectResponse(url="/rules", status_code=302)  # type: ignore[return-value]
    return templates.TemplateResponse(request, "login.html", {"role": None})


@router.post("/ui/login")
async def login_submit(request: Request, api_key: str = Form(...)) -> HTMLResponse:
    role = get_settings().api_keys.get(api_key)
    if not role:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"role": None, "error": "Invalid API key"},
            status_code=401,
        )
    response = RedirectResponse(url="/rules", status_code=302)
    response.set_cookie("api_key", api_key, httponly=True, samesite="lax")
    return response  # type: ignore[return-value]


@router.get("/rules", response_class=HTMLResponse)
async def rules_page(
    request: Request, session: AsyncSession = Depends(get_session)
) -> HTMLResponse:
    role = _role_from_cookie(request)
    if not role:
        return RedirectResponse(url="/", status_code=302)  # type: ignore[return-value]
    rules = list((await session.scalars(select(Rule).options(selectinload(Rule.actions)))).all())
    return templates.TemplateResponse(
        request,
        "rules.html",
        {
            "role": role,
            "rules": rules,
            "api_key": request.cookies.get("api_key", ""),
        },
    )


@router.get("/archive", response_class=HTMLResponse)
async def archive_page(
    request: Request,
    camera_id: str | None = Query(default=None),
    object_type: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    role = _role_from_cookie(request)
    if not role:
        return RedirectResponse(url="/", status_code=302)  # type: ignore[return-value]

    stmt = select(ArchiveItem).order_by(ArchiveItem.created_at.desc()).limit(50)
    if camera_id:
        camera = await session.scalar(select(Camera).where(Camera.code == camera_id))
        stmt = stmt.where(ArchiveItem.camera_id == camera.id) if camera else stmt.where(false())

    items = list((await session.scalars(stmt)).all())

    return templates.TemplateResponse(
        request,
        "archive.html",
        {
            "role": role,
            "items": items,
            "total": len(items),
            "camera_id": camera_id,
            "object_type": object_type,
        },
    )
