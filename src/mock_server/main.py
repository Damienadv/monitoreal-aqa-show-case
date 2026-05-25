"""FastAPI mock-сервер для AQA-шоукейса.

Имитирует Edge AI security платформу: камеры → детекции → правила → действия → архив.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from mock_server.auth import auth_middleware
from mock_server.db import Base, engine, session_scope
from mock_server.models import Camera
from mock_server.routers import actions, archive, cameras, detections, events, media, rules, ui


async def seed_cameras() -> None:
    """Создаёт две дефолтные камеры, если их ещё нет."""
    defaults = [
        ("cam-01", "Front Door", "Entrance"),
        ("cam-02", "Back Yard", "Backyard"),
    ]
    async with session_scope() as session:
        for code, name, location in defaults:
            existing = await session.scalar(select(Camera).where(Camera.code == code))
            if existing is None:
                session.add(Camera(code=code, name=name, location=location))


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    os.makedirs("data", exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_cameras()
    yield
    await engine.dispose()


app = FastAPI(
    title="Monitoreal Mock API",
    description="AQA showcase mock for Edge AI video surveillance domain",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

app.middleware("http")(auth_middleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """RFC 7807 Problem Details для HTTPException."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": "about:blank",
            "title": _title_for(exc.status_code),
            "status": exc.status_code,
            "detail": str(exc.detail),
            "instance": request.url.path,
        },
        media_type="application/problem+json",
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "type": "about:blank",
            "title": "Unprocessable Entity",
            "status": 422,
            "detail": "Request validation failed",
            "instance": request.url.path,
            "errors": exc.errors(),
        },
        media_type="application/problem+json",
    )


def _title_for(status_code: int) -> str:
    return {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        409: "Conflict",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
    }.get(status_code, "Error")


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Health check без auth — используется Docker healthcheck и CI smoke."""
    return {"status": "ok"}


app.include_router(cameras.router)
app.include_router(rules.router)
app.include_router(detections.router)
app.include_router(events.router)
app.include_router(actions.router)
app.include_router(archive.router)
app.include_router(media.router)
app.include_router(ui.router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
