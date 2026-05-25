"""Playwright UI-тесты на /archive — фильтр по camera_id (sync API)."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.ui


def test_filter_archive_by_camera_id_updates_url_and_table(auth_page: Page) -> None:
    """Фильтр по camera_id → URL содержит camera_id=cam-01, видна таблица.

    Covers R-LO-01 (UI surface для archive поиска).
    """
    page = auth_page
    page.goto("/archive")
    page.get_by_test_id("filter-camera").fill("cam-01")
    page.get_by_test_id("apply-filter").click()
    page.wait_for_load_state("networkidle")

    expect(page).to_have_url(re.compile(r".*camera_id=cam-01.*"))
    expect(page.get_by_test_id("archive-table")).to_be_visible()
