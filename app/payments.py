"""Payment logic that does not depend on handlers: which methods a package offers, invoices, pre-checkout rules.

Two modes, both optional (see docs/PAYMENTS.md):
- "provider": card payment through the provider token connected in @BotFather (a test provider in this demo);
- "stars": Telegram Stars (currency XTR, no provider token).
"""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from sqlalchemy.ext.asyncio import AsyncSession

from app import repo
from app.config import Settings
from app.db import Package, Payment
from app.texts import Translator
from app.utils import format_money

log = logging.getLogger(__name__)

PAYLOAD_PREFIX = "pay:"


def offered_methods(package: Package, settings: Settings) -> list[str]:
    """Methods this package can be paid with: enabled in .env and priced above 0."""
    methods = []
    if settings.card_payments and package.price_cents > 0:
        methods.append("provider")
    if settings.payments_stars and package.price_stars > 0:
        methods.append("stars")
    return methods


def price_of(package: Package, method: str, settings: Settings) -> str:
    if method == "stars":
        return format_money(package.price_stars, "XTR")
    return format_money(package.price_cents, settings.payments_currency)


def price_summary(package: Package, settings: Settings) -> str:
    return " / ".join(price_of(package, method, settings) for method in offered_methods(package, settings))


async def available_packages(session: AsyncSession, settings: Settings) -> list[Package]:
    """Active packages that can be paid right now (empty list = do not show the paid step at all)."""
    if not settings.payments_enabled:
        return []
    return [p for p in await repo.list_packages(session) if offered_methods(p, settings)]


def payload_for(payment: Payment) -> str:
    return f"{PAYLOAD_PREFIX}{payment.id}"


def payment_id_from_payload(payload: str | None) -> int | None:
    if not payload or not payload.startswith(PAYLOAD_PREFIX):
        return None
    value = payload[len(PAYLOAD_PREFIX):]
    return int(value) if value.isdigit() else None


async def send_invoice(bot: Bot, chat_id: int, payment: Payment, description: str, settings: Settings, t: Translator) -> None:
    """Sends the invoice message. Telegram rules (docs: bots/payments, payments-stars):
    Stars use currency XTR, no provider token and exactly one price item; the first button must be Pay."""
    price = format_money(payment.amount, payment.currency)
    pay_button = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("btn_pay_now", price=price), pay=True)]])
    common = dict(
        chat_id=chat_id,
        title=payment.title[:32],
        description=description[:255] or payment.title,
        payload=payload_for(payment),
        currency=payment.currency,
        prices=[LabeledPrice(label=payment.title[:32], amount=payment.amount)],
        reply_markup=pay_button,
    )
    if payment.method == "stars":
        await bot.send_invoice(**common)
    else:
        await bot.send_invoice(provider_token=settings.payments_provider_token, **common)


async def check_pre_checkout(
    session: AsyncSession, settings: Settings, user_id: int, payload: str, currency: str, total_amount: int
) -> str | None:
    """Returns None when the payment may go ahead, else the text key of the refusal shown to the client.

    Telegram gives the bot 10 seconds to answer, so this only reads the database.
    """
    payment_id = payment_id_from_payload(payload)
    payment = await repo.get_payment(session, payment_id) if payment_id else None
    if payment is None or payment.user_id != user_id or payment.status != "pending":
        return "pay_pre_expired"
    if await repo.brief_is_paid(session, payment.brief_id):
        return "pay_pre_paid"
    package = await repo.get_package(session, payment.package_id) if payment.package_id else None
    if package is None or not package.is_active or payment.method not in offered_methods(package, settings):
        return "pay_pre_gone"
    expected = package.price_stars if payment.method == "stars" else package.price_cents
    expected_currency = "XTR" if payment.method == "stars" else settings.payments_currency
    if (payment.amount, payment.currency) != (expected, expected_currency) or (total_amount, currency) != (expected, expected_currency):
        return "pay_pre_gone"  # the package price (or currency) changed after the invoice was sent
    return None


async def refund_stars(bot: Bot, payment: Payment) -> str | None:
    """Asks Telegram to return the Stars. None = done, otherwise the error text."""
    try:
        await bot.refund_star_payment(user_id=payment.user_id, telegram_payment_charge_id=payment.telegram_charge_id)
    except TelegramAPIError as exc:
        log.warning("refund of payment %s failed: %s", payment.id, exc)
        return exc.message
    return None
