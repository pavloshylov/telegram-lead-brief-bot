"""Unit tests for pure helpers and the text catalog."""
from __future__ import annotations

import string
from datetime import date, time

from app.texts import EN, UK
from app.utils import check_date, parse_date, parse_time
from app.views import day_options


def _placeholders(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def test_every_text_exists_in_both_languages_with_same_placeholders():
    assert EN.keys() == UK.keys()
    for key in EN:
        assert _placeholders(EN[key]) == _placeholders(UK[key]), key


def test_parse_date():
    today = date(2026, 11, 18)
    assert parse_date("20.11", today) == date(2026, 11, 20)
    assert parse_date("5/1", today) == date(2027, 1, 5)  # past day-month rolls to next year
    assert parse_date("01.12.26", today) == date(2026, 12, 1)
    assert parse_date("31.02", today) is None
    assert parse_date("tomorrow", today) is None


def test_check_date():
    today = date(2026, 11, 18)
    assert check_date(date(2026, 11, 17), today) == "date_past"
    assert check_date(date(2027, 6, 1), today) == "date_too_far"
    assert check_date(date(2026, 11, 18), today) is None


def test_parse_time():
    assert parse_time("9:05") == time(9, 5)
    assert parse_time("14.30") == time(14, 30)
    assert parse_time("24:00") is None
    assert parse_time("noon") is None


def test_day_options_business_week():
    monday = date(2026, 11, 16)
    values = dict(day_options(monday))
    assert values["this_week"] == "w:2026-11-18:2026-11-20"
    assert values["next_week"] == "w:2026-11-23:2026-11-27"
    thursday = date(2026, 11, 19)
    assert "this_week" not in dict(day_options(thursday))


def test_csv_text_blocks_spreadsheet_formulas():
    from app.services import csv_text

    assert csv_text('=HYPERLINK("http://x","y")') == '\'=HYPERLINK("http://x","y")'
    assert csv_text("+1") == "'+1" and csv_text("-2") == "'-2" and csv_text("@SUM(A1)") == "'@SUM(A1)"
    assert csv_text("Anna") == "Anna" and csv_text("") == "" and csv_text(None) == ""


def test_test_environment_uses_the_test_bot_api_url():
    from app.config import Settings
    from app.main import make_bot

    token = "1:" + "A" * 35
    prod = make_bot(Settings(bot_token=token))
    test = make_bot(Settings(bot_token=token, telegram_test_env=True))
    assert prod.session.api.base.format(token="T", method="getMe") == "https://api.telegram.org/botT/getMe"
    assert test.session.api.base.format(token="T", method="getMe") == "https://api.telegram.org/botT/test/getMe"
