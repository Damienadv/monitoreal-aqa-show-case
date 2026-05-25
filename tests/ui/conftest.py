"""Фикстуры UI-тестов: реальный uvicorn-subprocess + sync Playwright.

Зачем sync, а не async: pytest-asyncio с session-scoped Browser-фикстурой
и function-scoped Page плохо дружит. Sync API убирает event-loop проблемы целиком —
UI-тесты не латентность-критичные, синхронный браузер быстрее в setup/teardown.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return int(port)


@pytest.fixture(scope="session")
def ui_server_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Поднимает uvicorn-subprocess с временной SQLite-БД и ждёт /health."""
    port = _free_port()
    tmp_db = tmp_path_factory.mktemp("ui-db") / "ui.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_db}"

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "mock_server.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        env=env,
        cwd=str(Path(__file__).resolve().parent.parent.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    ready = False
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base_url}/health", timeout=1.0)
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            time.sleep(0.2)
    if not ready:
        proc.terminate()
        out = proc.stdout.read().decode() if proc.stdout else ""
        raise RuntimeError(f"uvicorn не поднялся за 20s. Лог:\n{out}")

    try:
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            yield b
        finally:
            b.close()


@pytest.fixture
def context(browser: Browser, ui_server_url: str) -> Iterator[BrowserContext]:
    ctx = browser.new_context(base_url=ui_server_url)
    ctx.set_default_timeout(10_000)
    try:
        yield ctx
    finally:
        ctx.close()


@pytest.fixture
def page(context: BrowserContext) -> Iterator[Page]:
    p = context.new_page()
    try:
        yield p
    finally:
        p.close()


@pytest.fixture
def auth_page(page: Page, ui_server_url: str) -> Page:
    """Page с admin api_key cookie — пропускает форму логина."""
    from mock_server.config import get_settings

    admin_key = get_settings().api_key_admin
    page.context.add_cookies([{"name": "api_key", "value": admin_key, "url": ui_server_url}])
    return page
