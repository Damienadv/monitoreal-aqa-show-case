"""Playwright UI-тесты на login-форму (sync API)."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from mock_server.config import get_settings

pytestmark = pytest.mark.ui


def test_login_with_valid_admin_key_redirects_to_rules(page: Page) -> None:
    """Валидный admin-key → редирект на /rules + видна таблица.

    Covers R-AUTH-01 (correct role recognition for UI cookie path).
    """
    page.goto("/")
    page.get_by_test_id("api-key-input").fill(get_settings().api_key_admin)
    page.get_by_test_id("login-submit").click()
    expect(page).to_have_url(re.compile(r".*/rules$"))
    expect(page.get_by_test_id("rules-table")).to_be_visible()
    expect(page.get_by_test_id("role")).to_have_text("role: admin")


def test_login_with_invalid_key_shows_error_and_stays_on_login(page: Page) -> None:
    """Неверный key → 401 + error-сообщение, без редиректа.

    Covers R-AUTH-01 (rejected invalid credentials).
    """
    page.goto("/")
    page.get_by_test_id("api-key-input").fill("nope-not-a-real-key")
    page.get_by_test_id("login-submit").click()
    expect(page.get_by_test_id("login-error")).to_have_text("Invalid API key")
    expect(page).to_have_url(re.compile(r".*(/ui/login|/)$"))
