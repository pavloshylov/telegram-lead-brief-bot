"""Side-effect services: safe message edits, manager notifications, broadcasts, CSV export."""
from __future__ import annotations

import asyncio
import csv
import io
import logging
import time
from html import escape
from dataclasses import dataclass, field

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import keyboards as kb
from app import repo
from app.db import Brief, Payment, User
from app.texts import Translator
from app.utils import format_money, user_link
from app.views import format_day, format_time, new_lead_text

log = logging.getLogger(__name__)


async def safe_edit(message: Message, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    """Edit a message, ignoring the harmless 'message is not modified' error (double taps)."""
    try:
        await message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise


# ---------------------------------------------------------------- manager notification

async def notify_manager(bot: Bot, session: AsyncSession, brief: Brief, client: User) -> bool:
    manager = await session.get(User, brief.manager_id)
    if manager is None:
        return False
    t = Translator(manager.language)
    try:
        await bot.send_message(
            manager.id,
            new_lead_text(t, brief, client),
            reply_markup=kb.lead_actions(t, brief, client, with_back=False),
        )
        return True
    except TelegramForbiddenError:
        log.warning("manager %s blocked the bot; brief #%s saved without notification", manager.id, brief.id)
        await repo.mark_blocked(session, manager.id)
    except TelegramAPIError:
        log.exception("could not notify manager %s about brief #%s", manager.id, brief.id)
    return False


async def notify_manager_paid(bot: Bot, session: AsyncSession, brief: Brief, client: User, payment: Payment) -> bool:
    manager = await session.get(User, brief.manager_id)
    if manager is None:
        return False
    t = Translator(manager.language)
    text = t(
        "pay_manager_notice",
        client_link=user_link(client.id, client.first_name, client.username),
        title=escape(payment.title),
        price=format_money(payment.amount, payment.currency),
        id=brief.id,
    )
    try:
        await bot.send_message(manager.id, text, reply_markup=kb.lead_actions(t, brief, client, with_back=False))
        return True
    except TelegramForbiddenError:
        log.warning("manager %s blocked the bot; payment %s saved without notification", manager.id, payment.id)
        await repo.mark_blocked(session, manager.id)
    except TelegramAPIError:
        log.exception("could not notify manager %s about payment %s", manager.id, payment.id)
    return False


# ---------------------------------------------------------------- broadcast

@dataclass
class BroadcastResult:
    delivered: int = 0
    blocked: int = 0
    failed: int = 0
    seconds: float = 0.0
    blocked_ids: list[int] = field(default_factory=list)


running_broadcasts: set[asyncio.Task] = set()  # keeps references so tasks are not garbage-collected


async def broadcast(
    bot: Bot,
    session_maker: async_sessionmaker[AsyncSession],
    from_chat_id: int,
    message_id: int,
    user_ids: list[int],
    rate: float,
) -> BroadcastResult:
    """Copies one message to many users, throttled below Telegram limits.

    Flood control (429) waits the requested time and retries; users who blocked the bot are
    counted and flagged so the next broadcast skips them.
    """
    result = BroadcastResult()
    started = time.monotonic()
    delay = 1.0 / rate if rate > 0 else 0
    for user_id in user_ids:
        for attempt in range(3):
            try:
                await bot.copy_message(chat_id=user_id, from_chat_id=from_chat_id, message_id=message_id)
                result.delivered += 1
                break
            except TelegramRetryAfter as exc:
                if attempt == 2:
                    result.failed += 1
                    break
                await asyncio.sleep(exc.retry_after)
            except TelegramForbiddenError:
                result.blocked += 1
                result.blocked_ids.append(user_id)
                break
            except TelegramAPIError:
                log.warning("broadcast to %s failed", user_id, exc_info=True)
                result.failed += 1
                break
        if delay:
            await asyncio.sleep(delay)
    if result.blocked_ids:
        async with session_maker() as session:
            for user_id in result.blocked_ids:
                await repo.mark_blocked(session, user_id)
            await session.commit()
    result.seconds = round(time.monotonic() - started, 1)
    return result


def start_broadcast(
    bot: Bot,
    session_maker: async_sessionmaker[AsyncSession],
    admin_chat_id: int,
    from_message_id: int,
    user_ids: list[int],
    rate: float,
    t: Translator,
) -> asyncio.Task:
    async def job() -> None:
        res = await broadcast(bot, session_maker, admin_chat_id, from_message_id, user_ids, rate)
        await bot.send_message(
            admin_chat_id,
            t("bc_done", sec=res.seconds, ok=res.delivered, blocked=res.blocked, failed=res.failed),
        )

    task = asyncio.create_task(job())
    running_broadcasts.add(task)
    task.add_done_callback(running_broadcasts.discard)
    return task


# ---------------------------------------------------------------- export

CSV_COLUMNS = [
    "brief_id", "created_at_utc", "manager", "client_name", "office", "tone", "status", "lead_status",
    "client_telegram_id", "service", "budget", "meeting_day", "meeting_time", "completed_at_utc",
]


def csv_text(value: str | None) -> str:
    """Text typed by a person goes into a spreadsheet: a leading = + - @ would be run as a formula (CSV injection)."""
    value = value or ""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def briefs_csv(rows: list[tuple[Brief, User]]) -> bytes:
    t = Translator("en")
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for brief, manager in rows:
        writer.writerow([
            brief.id,
            brief.created_at.strftime("%Y-%m-%d %H:%M"),
            csv_text(manager.first_name),
            csv_text(brief.client_name),
            csv_text(brief.office),
            brief.tone,
            brief.status,
            brief.lead_status if brief.status == "completed" else "",
            brief.client_id or "",
            csv_text(brief.service),
            csv_text(brief.budget),
            format_day(brief.meet_day, t) if brief.meet_day else "",
            format_time(brief.meet_time, t) if brief.meet_time else "",
            brief.completed_at.strftime("%Y-%m-%d %H:%M") if brief.completed_at else "",
        ])
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM so Excel opens UTF-8 correctly


PAYMENT_COLUMNS = [
    "payment_id", "created_at_utc", "paid_at_utc", "brief_id", "client_name", "client_telegram_id",
    "package", "method", "currency", "amount", "status", "refunded_at_utc", "telegram_charge_id",
]


def payments_csv(rows: list[tuple[Payment, Brief]]) -> bytes:
    """Amounts are in major units (25.00 USD, 250 Stars)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(PAYMENT_COLUMNS)
    stamp = lambda value: value.strftime("%Y-%m-%d %H:%M") if value else ""  # noqa: E731
    for payment, brief in rows:
        amount = payment.amount if payment.currency == "XTR" else f"{payment.amount / 100:.2f}"
        writer.writerow([
            payment.id, stamp(payment.created_at), stamp(payment.paid_at), brief.id, csv_text(brief.client_name), payment.user_id,
            csv_text(payment.title), payment.method, payment.currency, amount, payment.status, stamp(payment.refunded_at),
            payment.telegram_charge_id or "",
        ])
    return ("﻿" + buf.getvalue()).encode("utf-8")
