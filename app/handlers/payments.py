"""Client side of payments: package choice, invoice, pre-checkout check, successful payment.

The step is optional and starts from a button under the "brief sent" message (or when the client opens
their finished brief link again). Nothing is delivered before successful_payment arrives.
"""
from __future__ import annotations

import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app import keyboards as kb
from app import payments, repo
from app.config import Settings
from app.db import Brief, User
from app.services import notify_manager_paid, safe_edit
from app.states import PayCb
from app.texts import Translator
from app.utils import format_money

router = Router(name="payments")
log = logging.getLogger(__name__)


@router.callback_query(PayCb.filter())
async def pay_button(
    cb: CallbackQuery,
    callback_data: PayCb,
    session: AsyncSession,
    user: User,
    settings: Settings,
    t: Translator,
    bot: Bot,
) -> None:
    brief = await repo.get_brief(session, callback_data.brief_id)
    if brief is None or brief.status != "completed" or brief.client_id != user.id:
        await cb.answer(t("step_expired"), show_alert=True)
        return
    if await repo.brief_is_paid(session, brief.id):
        await cb.answer(t("pay_already_paid"), show_alert=True)
        return
    action = callback_data.action
    if action == "cancel":
        await safe_edit(cb.message, t("pay_dismissed"))
        await cb.answer()
        return
    packages = await payments.available_packages(session, settings)
    if not packages:
        await cb.answer(t("pay_not_available"), show_alert=True)
        return
    if action == "menu":
        await safe_edit(cb.message, t("pay_choose_package"), kb.pay_packages(t, brief.id, packages, settings))
        await cb.answer()
        return

    package = next((p for p in packages if p.id == callback_data.package_id), None)
    if package is None:  # hidden, deleted or repriced to 0 since the list was shown
        await safe_edit(cb.message, t("pay_choose_package"), kb.pay_packages(t, brief.id, packages, settings))
        await cb.answer(t("pay_package_gone"), show_alert=True)
        return
    methods = payments.offered_methods(package, settings)
    if action == "pkg" and len(methods) > 1:
        text = t("pay_choose_method", title=escape(package.title), description=escape(package.description))
        await safe_edit(cb.message, text, kb.pay_methods(t, brief.id, package, settings))
        await cb.answer()
        return
    method = callback_data.method if action == "m" else methods[0]
    if method not in methods:
        await cb.answer(t("pay_package_gone"), show_alert=True)
        return
    await _send_invoice(cb, session, user, settings, t, bot, brief, package, method)


async def _send_invoice(cb, session, user, settings, t, bot, brief: Brief, package, method: str) -> None:
    payment = await repo.create_payment(session, brief, user.id, package, method, settings.payments_currency)
    await session.commit()  # the pending row must exist before Telegram can call back with pre_checkout_query
    try:
        await payments.send_invoice(bot, cb.message.chat.id, payment, package.description, settings, t)
    except TelegramAPIError:
        log.exception("could not send the invoice for payment %s", payment.id)
        await repo.set_payment_status(session, payment.id, "cancelled")
        await cb.answer(t("pay_not_available"), show_alert=True)
        return
    await cb.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, session: AsyncSession, settings: Settings, t: Translator) -> None:
    """Must answer within 10 seconds, so this only checks the database."""
    problem = await payments.check_pre_checkout(
        session, settings, query.from_user.id, query.invoice_payload, query.currency, query.total_amount
    )
    if problem is None:
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message=t(problem))


@router.message(F.successful_payment)
async def successful_payment(
    message: Message, session: AsyncSession, user: User, settings: Settings, t: Translator, bot: Bot
) -> None:
    paid = message.successful_payment
    payment_id = payments.payment_id_from_payload(paid.invoice_payload)
    payment = await repo.get_payment(session, payment_id) if payment_id else None
    if payment is None:
        # Money was taken for an invoice we cannot find: never drop this silently.
        log.error("successful_payment for unknown payload %r, charge %s", paid.invoice_payload, paid.telegram_payment_charge_id)
        return
    if (paid.total_amount, paid.currency) != (payment.amount, payment.currency):
        log.warning("payment %s: Telegram charged %s %s, expected %s %s", payment.id, paid.total_amount, paid.currency, payment.amount, payment.currency)
    first = await repo.mark_paid(session, payment.id, paid.telegram_payment_charge_id, paid.provider_payment_charge_id or None)
    if not first:  # Telegram redelivered the update: already recorded, do not notify twice
        return
    await session.commit()  # persist the money first, notifications come second
    brief = await repo.get_brief(session, payment.brief_id)
    manager = await session.get(User, brief.manager_id) if brief else None
    price = format_money(payment.amount, payment.currency)
    await message.answer(
        t("pay_thanks", title=escape(payment.title), price=price, manager=escape(manager.first_name if manager else ""))
    )
    if brief is not None:
        await notify_manager_paid(bot, session, brief, user, payment)
