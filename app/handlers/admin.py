"""Admin panel: stats, broadcasts, catalog editing, team management, CSV export.

Access is limited to Telegram IDs listed in ADMIN_IDS.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import keyboards as kb
from app import repo
from app.config import Settings
from app.db import User
from app.middlewares import IsAdmin
from app.services import briefs_csv, safe_edit, start_broadcast
from app.states import AdminCb, AdminInput
from app.texts import Translator, all_variants
from app.utils import clean_text, deep_link
from app.views import revenue_lines

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(F.text.in_(all_variants("btn_admin")))
@router.message(Command("admin"))
async def admin_menu(message: Message, state: FSMContext, settings: Settings, t: Translator) -> None:
    await state.clear()
    await message.answer(t("admin_menu", company=escape(settings.company_name)), reply_markup=kb.admin_menu(t))


@router.callback_query(AdminCb.filter(F.action == "menu"))
async def admin_menu_cb(cb: CallbackQuery, state: FSMContext, settings: Settings, t: Translator) -> None:
    await state.clear()
    await safe_edit(cb.message, t("admin_menu", company=escape(settings.company_name)), kb.admin_menu(t))
    await cb.answer()


# ---------------------------------------------------------------- stats

@router.callback_query(AdminCb.filter(F.action == "stats"))
async def stats(cb: CallbackQuery, session: AsyncSession, settings: Settings, t: Translator) -> None:
    s = await repo.get_stats(session, settings.admin_ids)
    services = "\n".join(f"• {escape(name)} — {n}" for name, n in s.top_services) or t("none_yet")
    managers = "\n".join(f"• {escape(name)} — {n}" for name, n in s.top_managers) or t("none_yet")
    text = t(
        "stats",
        users=s.users_total,
        new7=s.users_new_7d,
        blocked=s.users_blocked,
        managers=s.managers,
        created=s.briefs_created,
        completed=s.briefs_completed,
        rate=f"{s.completion_rate:.0%}",
        contacted=s.leads_contacted,
        services=services,
        top_managers=managers,
    )
    if settings.payments_enabled:
        lines = await repo.revenue(session)
        text += t("stats_revenue", lines=revenue_lines(t, lines))
    await safe_edit(cb.message, text, kb.admin_back(t))
    await cb.answer()


# ---------------------------------------------------------------- broadcast

@router.callback_query(AdminCb.filter(F.action == "bc"))
async def broadcast_segments(cb: CallbackQuery, session: AsyncSession, user: User, t: Translator) -> None:
    counts = {
        seg: len(await repo.broadcast_targets(session, seg, exclude=user.id)) for seg in ("all", "managers", "clients")
    }
    await safe_edit(cb.message, t("bc_choose_segment"), kb.broadcast_segments(t, counts))
    await cb.answer()


@router.callback_query(AdminCb.filter(F.action == "bcseg"))
async def broadcast_segment(
    cb: CallbackQuery, callback_data: AdminCb, state: FSMContext, session: AsyncSession, user: User, t: Translator
) -> None:
    if not await repo.broadcast_targets(session, callback_data.value, exclude=user.id):
        await cb.answer(t("bc_no_targets"), show_alert=True)
        return
    await state.set_state(AdminInput.broadcast_message)
    await state.update_data(segment=callback_data.value)
    await safe_edit(cb.message, t("bc_ask_message"), kb.admin_back(t, "bccancel"))
    await cb.answer()


@router.message(AdminInput.broadcast_message)
async def broadcast_message(
    message: Message, state: FSMContext, session: AsyncSession, user: User, t: Translator, bot: Bot
) -> None:
    data = await state.get_data()
    targets = await repo.broadcast_targets(session, data["segment"], exclude=user.id)
    await state.update_data(source_message_id=message.message_id)
    await state.set_state(AdminInput.broadcast_confirm)
    await bot.copy_message(message.chat.id, message.chat.id, message.message_id)  # exact preview
    await message.answer(t("bc_preview", n=len(targets)), reply_markup=kb.broadcast_confirm(t))


@router.callback_query(AdminInput.broadcast_confirm, AdminCb.filter(F.action == "bcsend"))
async def broadcast_send(
    cb: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
    user: User,
    settings: Settings,
    t: Translator,
    bot: Bot,
) -> None:
    data = await state.get_data()
    await state.clear()
    targets = await repo.broadcast_targets(session, data["segment"], exclude=user.id)
    await safe_edit(cb.message, t("bc_started", n=len(targets)))
    await cb.answer()
    start_broadcast(bot, session_maker, cb.message.chat.id, data["source_message_id"], targets, settings.broadcast_rate, t)


@router.callback_query(AdminCb.filter(F.action.in_({"bcsend", "bccancel"})))
async def broadcast_cancel(cb: CallbackQuery, state: FSMContext, t: Translator) -> None:
    await state.clear()
    await safe_edit(cb.message, t("bc_cancelled"), kb.admin_back(t))
    await cb.answer()


# ---------------------------------------------------------------- catalogs

@router.callback_query(AdminCb.filter(F.action == "cat"))
async def catalogs(cb: CallbackQuery, state: FSMContext, t: Translator) -> None:
    await state.clear()
    await safe_edit(cb.message, t("cat_choose"), kb.catalog_kinds(t))
    await cb.answer()


async def _show_kind(message: Message, session: AsyncSession, t: Translator, kind: str, edit: bool = True) -> None:
    items = await repo.list_catalog(session, kind, active_only=False)
    text, markup = t("cat_list", title=t(f"cat_{kind}")), kb.catalog_items(t, kind, items)
    if edit:
        await safe_edit(message, text, markup)
    else:
        await message.answer(text, reply_markup=markup)


@router.callback_query(AdminCb.filter(F.action == "catkind"), AdminCb.filter(F.value.in_(repo.CATALOG_KINDS)))
async def catalog_kind(cb: CallbackQuery, callback_data: AdminCb, state: FSMContext, session: AsyncSession, t: Translator) -> None:
    await state.clear()
    await _show_kind(cb.message, session, t, callback_data.value)
    await cb.answer()


async def _show_item(message: Message, t: Translator, item) -> None:
    status = t("item_visible") if item.is_active else t("item_hidden")
    await safe_edit(message, t("cat_item", label=escape(item.label), status=status), kb.catalog_item(t, item))


@router.callback_query(AdminCb.filter(F.action.in_({"catitem", "cattoggle", "catdel", "catdelok"})))
async def catalog_item(cb: CallbackQuery, callback_data: AdminCb, session: AsyncSession, t: Translator) -> None:
    item_id = int(callback_data.value) if callback_data.value.isdigit() else 0
    item = await repo.get_catalog_item(session, item_id)
    if item is None:
        await cb.answer(t("step_expired"), show_alert=True)
        return
    action = callback_data.action
    if action == "cattoggle":
        await repo.toggle_catalog_item(session, item.id)
        await _show_item(cb.message, t, item)
    elif action == "catdel":
        await safe_edit(cb.message, t("cat_confirm_delete", label=escape(item.label)), kb.catalog_delete_confirm(t, item))
    elif action == "catdelok":
        kind = item.kind
        await repo.delete_catalog_item(session, item.id)
        await cb.answer(t("cat_deleted"))
        await _show_kind(cb.message, session, t, kind)
        return
    else:
        await _show_item(cb.message, t, item)
    await cb.answer()


@router.callback_query(AdminCb.filter(F.action == "catadd"), AdminCb.filter(F.value.in_(repo.CATALOG_KINDS)))
async def catalog_add(cb: CallbackQuery, callback_data: AdminCb, state: FSMContext, t: Translator) -> None:
    await state.set_state(AdminInput.catalog_label)
    await state.update_data(kind=callback_data.value)
    await safe_edit(cb.message, t("cat_ask_label"), kb.admin_back(t, "catkind", callback_data.value))
    await cb.answer()


@router.message(AdminInput.catalog_label, F.text)
async def catalog_label(message: Message, state: FSMContext, session: AsyncSession, t: Translator) -> None:
    label = clean_text(message.text)
    if not 1 <= len(label) <= 64 or label.startswith("/"):
        await message.answer(t("cat_bad_label"))
        return
    kind = (await state.get_data())["kind"]
    item = await repo.add_catalog_item(session, kind, label)
    if item is None:
        await message.answer(t("cat_duplicate", label=escape(label)))
        return
    await state.clear()
    await message.answer(t("cat_added", label=escape(label)))
    await _show_kind(message, session, t, kind, edit=False)


# ---------------------------------------------------------------- team

async def _show_team(message: Message, session: AsyncSession, t: Translator) -> None:
    managers = await repo.list_managers(session)
    await safe_edit(message, t("team", n=len(managers)), kb.team(t, managers))


@router.callback_query(AdminCb.filter(F.action == "team"))
async def team(cb: CallbackQuery, session: AsyncSession, t: Translator) -> None:
    await _show_team(cb.message, session, t)
    await cb.answer()


@router.callback_query(AdminCb.filter(F.action == "teaminvite"))
async def team_invite(cb: CallbackQuery, session: AsyncSession, user: User, t: Translator, bot: Bot) -> None:
    invite = await repo.create_manager_invite(session, user.id)
    link = deep_link((await bot.me()).username, f"m_{invite.code}")
    await cb.message.answer(t("team_invite", link=link))
    await cb.answer()


@router.callback_query(AdminCb.filter(F.action == "teamrm"))
async def team_remove(cb: CallbackQuery, callback_data: AdminCb, session: AsyncSession, t: Translator) -> None:
    member = await session.get(User, int(callback_data.value)) if callback_data.value.isdigit() else None
    if member is None:
        await cb.answer(t("step_expired"), show_alert=True)
        return
    await safe_edit(
        cb.message, t("team_confirm_remove", name=escape(member.first_name)), kb.team_remove_confirm(t, member.id)
    )
    await cb.answer()


@router.callback_query(AdminCb.filter(F.action == "teamrmok"))
async def team_remove_ok(cb: CallbackQuery, callback_data: AdminCb, session: AsyncSession, t: Translator) -> None:
    if callback_data.value.isdigit():
        await repo.set_manager(session, int(callback_data.value), False)
    await cb.answer(t("team_removed"))
    await _show_team(cb.message, session, t)


# ---------------------------------------------------------------- export

@router.callback_query(AdminCb.filter(F.action == "export"))
async def export(cb: CallbackQuery, session: AsyncSession, t: Translator) -> None:
    rows = await repo.all_briefs(session)
    if not rows:
        await cb.answer(t("export_empty"), show_alert=True)
        return
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    document = BufferedInputFile(briefs_csv(rows), filename=f"leads_{today}.csv")
    await cb.message.answer_document(document, caption=t("export_caption", n=len(rows), date=today))
    await cb.answer()
