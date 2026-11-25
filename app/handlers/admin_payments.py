"""Admin side of payments: revenue, payments CSV, package editing, Stars refunds. Access: ADMIN_IDS only."""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app import keyboards as kb
from app import payments, repo
from app.config import Settings
from app.db import User
from app.middlewares import IsAdmin
from app.services import payments_csv, safe_edit
from app.states import AdminCb, AdminInput
from app.texts import Translator
from app.utils import clean_text, format_money, parse_price, parse_stars
from app.views import revenue_lines

router = Router(name="admin_payments")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def _on_off(t: Translator, value: bool) -> str:
    return t("mode_on") if value else t("mode_off")


# ---------------------------------------------------------------- overview and CSV

@router.callback_query(AdminCb.filter(F.action == "pay"))
async def payments_menu(cb: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings, t: Translator) -> None:
    await state.clear()
    text = t(
        "pay_menu",
        revenue=t("revenue_title") + "\n" + revenue_lines(t, await repo.revenue(session)),
        modes=t("pay_modes", card=_on_off(t, settings.card_payments), stars=_on_off(t, settings.payments_stars)),
    )
    if not settings.payments_enabled:
        text += "\n\n" + t("pay_off_note")
    await safe_edit(cb.message, text, kb.payments_menu(t))
    await cb.answer()


@router.callback_query(AdminCb.filter(F.action == "paycsv"))
async def payments_export(cb: CallbackQuery, session: AsyncSession, t: Translator) -> None:
    rows = await repo.all_payments(session)
    if not rows:
        await cb.answer(t("pay_export_empty"), show_alert=True)
        return
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    document = BufferedInputFile(payments_csv(rows), filename=f"payments_{today}.csv")
    await cb.message.answer_document(document, caption=t("pay_export_caption", n=len(rows), date=today))
    await cb.answer()


# ---------------------------------------------------------------- packages

def _price_text(package, settings: Settings, t: Translator) -> tuple[str, str]:
    card = format_money(package.price_cents, settings.payments_currency) if package.price_cents else t("pkg_not_offered")
    stars = format_money(package.price_stars, "XTR") if package.price_stars else t("pkg_not_offered")
    return card, stars


async def _show_packages(message: Message, session: AsyncSession, t: Translator, edit: bool = True) -> None:
    packages = await repo.list_packages(session, active_only=False)
    markup = kb.packages_list(t, packages)
    if edit:
        await safe_edit(message, t("pkg_list"), markup)
    else:
        await message.answer(t("pkg_list"), reply_markup=markup)


async def _show_package(message: Message, package, settings: Settings, t: Translator) -> None:
    card, stars = _price_text(package, settings, t)
    status = t("item_visible") if package.is_active else t("item_hidden")
    text = t(
        "pkg_item", title=escape(package.title), description=escape(package.description), card=card, stars=stars, status=status
    )
    await safe_edit(message, text, kb.package_item(t, package))


@router.callback_query(AdminCb.filter(F.action == "pkgs"))
async def packages(cb: CallbackQuery, state: FSMContext, session: AsyncSession, t: Translator) -> None:
    await state.clear()
    await _show_packages(cb.message, session, t)
    await cb.answer()


@router.callback_query(AdminCb.filter(F.action.in_({"pkg", "pkgtoggle", "pkgdel", "pkgdelok"})))
async def package_action(
    cb: CallbackQuery, callback_data: AdminCb, session: AsyncSession, settings: Settings, t: Translator
) -> None:
    package = await repo.get_package(session, int(callback_data.value)) if callback_data.value.isdigit() else None
    if package is None:
        await cb.answer(t("step_expired"), show_alert=True)
        return
    action = callback_data.action
    if action == "pkgtoggle":
        await repo.toggle_package(session, package.id)
    elif action == "pkgdel":
        await safe_edit(cb.message, t("pkg_confirm_delete", title=escape(package.title)), kb.package_delete_confirm(t, package))
        await cb.answer()
        return
    elif action == "pkgdelok":
        await repo.delete_package(session, package.id)
        await cb.answer(t("cat_deleted"))
        await _show_packages(cb.message, session, t)
        return
    await _show_package(cb.message, package, settings, t)
    await cb.answer()


@router.callback_query(AdminCb.filter(F.action == "pkgadd"))
async def package_add(cb: CallbackQuery, state: FSMContext, t: Translator) -> None:
    await state.clear()
    await state.set_state(AdminInput.pkg_title)
    await safe_edit(cb.message, t("pkg_ask_title"), kb.admin_back(t, "pkgs"))
    await cb.answer()


@router.callback_query(AdminCb.filter(F.action == "pkgedit"))
async def package_edit(cb: CallbackQuery, callback_data: AdminCb, state: FSMContext, session: AsyncSession, settings: Settings, t: Translator) -> None:
    package = await repo.get_package(session, int(callback_data.value)) if callback_data.value.isdigit() else None
    if package is None:
        await cb.answer(t("step_expired"), show_alert=True)
        return
    await state.clear()
    await state.update_data(package_id=package.id)
    await state.set_state(AdminInput.pkg_price)
    await safe_edit(cb.message, t("pkg_ask_price", currency=settings.payments_currency), kb.admin_back(t, "pkg", str(package.id)))
    await cb.answer()


@router.message(AdminInput.pkg_title, F.text)
async def got_title(message: Message, state: FSMContext, t: Translator) -> None:
    title = clean_text(message.text)
    if not 2 <= len(title) <= 32 or title.startswith("/"):
        await message.answer(t("pkg_bad_title"))
        return
    await state.update_data(title=title)
    await state.set_state(AdminInput.pkg_description)
    await message.answer(t("pkg_ask_description"))


@router.message(AdminInput.pkg_description, F.text)
async def got_description(message: Message, state: FSMContext, settings: Settings, t: Translator) -> None:
    description = clean_text(message.text)
    if not 2 <= len(description) <= 255 or description.startswith("/"):
        await message.answer(t("pkg_bad_description"))
        return
    await state.update_data(description=description)
    await state.set_state(AdminInput.pkg_price)
    await message.answer(t("pkg_ask_price", currency=settings.payments_currency))


@router.message(AdminInput.pkg_price, F.text)
async def got_price(message: Message, state: FSMContext, settings: Settings, t: Translator) -> None:
    cents = parse_price(message.text)
    if cents is None:
        await message.answer(t("pkg_bad_price"))
        return
    await state.update_data(price_cents=cents)
    await state.set_state(AdminInput.pkg_stars)
    await message.answer(t("pkg_ask_stars"))


@router.message(AdminInput.pkg_stars, F.text)
async def got_stars(message: Message, state: FSMContext, session: AsyncSession, settings: Settings, t: Translator) -> None:
    stars = parse_stars(message.text)
    if stars is None:
        await message.answer(t("pkg_bad_stars"))
        return
    data = await state.get_data()
    cents = data["price_cents"]
    if cents == 0 and stars == 0:
        await state.set_state(AdminInput.pkg_price)
        await message.answer(t("pkg_need_one") + "\n\n" + t("pkg_ask_price", currency=settings.payments_currency))
        return
    if "package_id" in data:  # editing prices of an existing package
        package = await repo.set_package_prices(session, data["package_id"], cents, stars)
        await state.clear()
        if package is None:
            await message.answer(t("step_expired"))
            return
        await message.answer(t("pkg_updated"))
        card, stars_text = _price_text(package, settings, t)
        status = t("item_visible") if package.is_active else t("item_hidden")
        await message.answer(
            t("pkg_item", title=escape(package.title), description=escape(package.description), card=card, stars=stars_text, status=status),
            reply_markup=kb.package_item(t, package),
        )
        return
    package = await repo.add_package(session, data["title"], data["description"], cents, stars)
    await state.clear()
    if package is None:
        await message.answer(t("pkg_duplicate", title=escape(data["title"])))
        return
    await message.answer(t("pkg_added", title=escape(package.title)))
    await _show_packages(message, session, t, edit=False)


# ---------------------------------------------------------------- Stars refunds

@router.callback_query(AdminCb.filter(F.action == "refunds"))
async def refunds(cb: CallbackQuery, session: AsyncSession, t: Translator) -> None:
    items = await repo.refundable_star_payments(session)
    if not items:
        await safe_edit(cb.message, t("refund_none"), kb.admin_back(t, "pay"))
    else:
        await safe_edit(cb.message, t("refund_list"), kb.refunds_list(t, items))
    await cb.answer()


@router.callback_query(AdminCb.filter(F.action.in_({"refund", "refundok"})))
async def refund(
    cb: CallbackQuery, callback_data: AdminCb, session: AsyncSession, t: Translator, bot: Bot
) -> None:
    payment = await repo.get_payment(session, int(callback_data.value)) if callback_data.value.isdigit() else None
    if payment is None or payment.method != "stars" or payment.status != "paid":
        await cb.answer(t("step_expired"), show_alert=True)
        return
    if callback_data.action == "refund":
        text = t("refund_confirm", price=format_money(payment.amount, payment.currency), title=escape(payment.title), id=payment.brief_id)
        await safe_edit(cb.message, text, kb.refund_confirm(t, payment))
        await cb.answer()
        return
    error = await payments.refund_stars(bot, payment)
    if error is not None:
        await cb.answer(t("refund_failed", error=error), show_alert=True)
        return
    await repo.mark_refunded(session, payment.id)
    await cb.answer(t("refund_done"))
    await session.commit()
    await _notify_client_refund(bot, session, payment, t)
    items = await repo.refundable_star_payments(session)
    if items:
        await safe_edit(cb.message, t("refund_list"), kb.refunds_list(t, items))
    else:
        await safe_edit(cb.message, t("refund_none"), kb.admin_back(t, "pay"))


async def _notify_client_refund(bot: Bot, session: AsyncSession, payment, admin_t: Translator) -> None:
    """Tell the client in their own language; a blocked bot must not break the refund."""
    client = await session.get(User, payment.user_id)
    t = Translator(client.language if client else admin_t.lang)
    try:
        await bot.send_message(
            payment.user_id,
            t("pay_refunded_client", title=escape(payment.title), price=format_money(payment.amount, payment.currency)),
        )
    except TelegramAPIError:
        pass
