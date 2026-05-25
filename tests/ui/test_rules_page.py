"""Playwright UI-тесты на /rules — создание правила через модалку (sync API)."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.ui


def test_create_rule_via_modal_appears_in_table(auth_page: Page) -> None:
    """Создание правила через модалку → запись в таблице после reload.

    Covers R-AC-01 (UI flow для multiple actions per rule sanity).
    """
    page = auth_page
    page.goto("/rules")
    initial_rows = page.get_by_test_id("rule-row").count()

    page.get_by_test_id("open-create-modal").click()
    page.get_by_test_id("field-name").fill("UI Created Rule")
    page.get_by_test_id("field-camera").fill("cam-01")
    page.get_by_test_id("submit").click()

    page.wait_for_load_state("networkidle")
    rows = page.get_by_test_id("rule-row")
    expect(rows).to_have_count(initial_rows + 1)
    expect(page.get_by_text("UI Created Rule")).to_be_visible()
