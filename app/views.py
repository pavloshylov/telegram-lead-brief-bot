"""Text building: meeting day/time codes, summaries and lead cards.

Answers are stored language-neutral (e.g. "d:2026-11-20", "s:morning", "t:14:30") and rendered in the
reader's language, so a Ukrainian-speaking client and an English-speaking manager both see their own language.
"""
from __future__ import annotations

from datetime import date, timedelta
from html import escape
from zoneinfo import ZoneInfo

from app.db import Brief, User
from app.texts import Translator
from app.utils import format_date, user_link

TIME_SLOTS = ("morning", "afternoon", "evening")
LEAD_ICONS = {"new": "🆕", "contacted": "📞", "closed": "✅"}


# ---------------------------------------------------------------- meeting day / time

def day_options(today: date) -> list[tuple[str, str]]:
    """(value, code) pairs for the day step. 'This week' is offered Mon–Wed only (business days left)."""
    options = [("today", f"d:{today.isoformat()}"), ("tomorrow", f"d:{(today + timedelta(days=1)).isoformat()}")]
    if today.weekday() <= 2:
        start, end = today + timedelta(days=2), today + timedelta(days=4 - today.weekday())
        options.append(("this_week", f"w:{start.isoformat()}:{end.isoformat()}"))
    monday = today + timedelta(days=7 - today.weekday())
    options.append(("next_week", f"w:{monday.isoformat()}:{(monday + timedelta(days=4)).isoformat()}"))
    return options


def format_day(code: str | None, t: Translator) -> str:
    if not code:
        return "—"
    kind, _, rest = code.partition(":")
    if kind == "d":
        return format_date(date.fromisoformat(rest), t.lang)
    if kind == "w":
        start, end = rest.split(":")
        return f"{format_date(date.fromisoformat(start), t.lang)} – {format_date(date.fromisoformat(end), t.lang)}"
    return escape(code)


def format_time(code: str | None, t: Translator) -> str:
    if not code:
        return "—"
    kind, _, rest = code.partition(":")
    if kind == "s" and rest in TIME_SLOTS:
        return t(f"time_{rest}")
    if kind == "t":
        return rest
    return escape(code)


def day_is_today(code: str | None, today: date) -> bool:
    return code == f"d:{today.isoformat()}"


# ---------------------------------------------------------------- summaries

def summary(t: Translator, *, service: str, budget: str, day: str, time: str, office: str) -> str:
    return t(
        "summary",
        service=escape(service),
        budget=escape(budget),
        day=format_day(day, t),
        time=format_time(time, t),
        office=escape(office),
    )


def brief_summary(t: Translator, brief: Brief) -> str:
    return summary(
        t,
        service=brief.service or "—",
        budget=brief.budget or "—",
        day=brief.meet_day or "",
        time=brief.meet_time or "",
        office=brief.office,
    )


def answers_block(t: Translator, brief: Brief) -> str:
    return t(
        "lead_answers",
        client=escape(brief.client_name),
        office=escape(brief.office),
        service=escape(brief.service or "—"),
        budget=escape(brief.budget or "—"),
        day=format_day(brief.meet_day, t),
        time=format_time(brief.meet_time, t),
    )


def lead_icon(brief: Brief) -> str:
    return "⏳" if brief.status != "completed" else LEAD_ICONS.get(brief.lead_status, "🆕")


def new_lead_text(t: Translator, brief: Brief, client: User) -> str:
    text = t("new_lead", client_link=user_link(client.id, client.first_name, client.username), id=brief.id)
    text += "\n\n" + answers_block(t, brief)
    if not client.username:
        text += "\n\n" + t("lead_no_username")
    return text


def lead_card_text(t: Translator, brief: Brief, client: User | None, link: str, tz: str) -> str:
    created = brief.created_at
    if created.tzinfo is None:  # SQLite returns naive datetimes
        created = created.replace(tzinfo=ZoneInfo("UTC"))
    text = t(
        "lead_card",
        icon=lead_icon(brief),
        id=brief.id,
        client=escape(brief.client_name),
        created=created.astimezone(ZoneInfo(tz)).strftime("%d.%m %H:%M"),
        office=escape(brief.office),
    )
    if brief.status != "completed":
        return text + "\n\n" + t("lead_waiting", link=link)
    if client is not None:
        text += "\n" + t("lead_answered_by", client_link=user_link(client.id, client.first_name, client.username))
    text += "\n\n" + answers_block(t, brief)
    text += "\n\n" + t("lead_status_set", status=t(f"status_{brief.lead_status}"))
    return text
