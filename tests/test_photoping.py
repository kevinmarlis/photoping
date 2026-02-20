"""
Tests for photoping.py — focuses on _years_ago_label, which is pure logic.
"""
from datetime import date
from unittest.mock import MagicMock

import pytest

import photoping
from photoping import _years_ago_label

FIXED_TODAY = date(2026, 2, 20)


@pytest.fixture
def fixed_today(monkeypatch):
    """Patch photoping.date_type so .today() returns FIXED_TODAY (2026-02-20)."""
    mock_date_type = MagicMock()
    mock_date_type.today.return_value = FIXED_TODAY
    monkeypatch.setattr("photoping.date_type", mock_date_type)
    return FIXED_TODAY


def test__years_ago_label__one_year_singular(fixed_today):
    assert _years_ago_label("2025-02-20") == "On this day, 1 year ago"


def test__years_ago_label__multiple_years_plural(fixed_today):
    assert _years_ago_label("2021-02-20") == "On this day, 5 years ago"


def test__years_ago_label__invalid_date_fallback():
    assert _years_ago_label("not-a-date") == "On this day"


def test__years_ago_label__empty_string_fallback():
    assert _years_ago_label("") == "On this day"
