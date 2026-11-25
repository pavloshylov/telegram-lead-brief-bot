"""Small pure helpers: date/time parsing and formatting, links, escaping."""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from html import escape
from zoneinfo import ZoneInfo

from app.texts import MONTHS, WEEKDAYS

MAX_DAYS_AHEAD = 183
_DATE_RE = re.compile(r"^\s*(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2}|\d{4}))?\s*$")
_TIME_RE = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*$")


def now_local(tz: str) -> datetime:
    return datetime.now(ZoneInfo(tz))


def parse_date(text: str, today: date) -> date | None:
    """DD.MM or DD.MM.YYYY (also / or -). Without a year: the nearest such date that is not in the past."""
    match = _DATE_RE.match(text or "")
    if not match:
        return None
    day, month, year = int(match.group(1)), int(match.group(2)), match.group(3)
    try:
        if year:
            full_year = int(year) + (2000 if len(year) == 2 else 0)
            return date(full_year, month, day)
        candidate = date(today.year, month, day)
        if candidate < today:
            candidate = date(today.year + 1, month, day)
        return candidate
    except ValueError:
        return None


def check_date(value: date, today: date) -> str | None:
    """Returns a text key describing the problem, or None if the date is fine."""
    if value < today:
        return "date_past"
    if value > today + timedelta(days=MAX_DAYS_AHEAD):
        return "date_too_far"
    return None


def parse_time(text: str) -> time | None:
    match = _TIME_RE.match(text or "")
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 23 or minutes > 59:
        return None
    return time(hours, minutes)


def format_date(value: date, lang: str) -> str:
    return f"{WEEKDAYS[lang][value.weekday()]}, {value.day} {MONTHS[lang][value.month - 1]}"


def example_date(today: date) -> str:
    return (today + timedelta(days=3)).strftime("%d.%m")


def progress_bar(step: int, total: int = 4) -> str:
    return "●" * step + "○" * (total - step)


def deep_link(bot_username: str, payload: str) -> str:
    return f"https://t.me/{bot_username}?start={payload}"


def user_link(user_id: int, name: str, username: str | None) -> str:
    """HTML mention. tg://user works without a username (subject to the user's privacy settings)."""
    href = f"https://t.me/{username}" if username else f"tg://user?id={user_id}"
    label = escape(name or (f"@{username}" if username else str(user_id)))
    suffix = f" (@{escape(username)})" if username else ""
    return f'<a href="{href}">{label}</a>{suffix}'


def clean_text(text: str | None) -> str:
    return " ".join((text or "").split())


def format_money(amount: int, currency: str) -> str:
    """Minor units -> text. Stars (XTR) are whole numbers; everything else has 2 decimals."""
    if currency == "XTR":
        return f"{amount} ⭐"
    return f"{amount / 100:.2f} {currency}"


def parse_price(text: str | None) -> int | None:
    """'25', '25.5', '25,50' -> cents. None if it is not a price from 0 to 10000 (0 = not offered)."""
    value = (text or "").strip().replace(",", ".")
    try:
        number = round(float(value) * 100)
    except (ValueError, OverflowError):
        return None
    return number if 0 <= number <= 1_000_000 and len(value) <= 10 else None


def parse_stars(text: str | None) -> int | None:
    """Whole Stars, 0 = no Stars option. None if invalid (negative, text, more than 100000)."""
    value = (text or "").strip()
    if not value.isdigit():
        return None
    number = int(value)
    return number if number <= 100_000 else None
