"""Manager side: create personal brief links, browse leads, update lead status."""
from __future__ import annotations

from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app import keyboards as kb
from app import repo
from app.config import Settings
from app.db import User
from app.middlewares import IsManager
from app.services import safe_edit
from app.states import LeadCb, MgrCb, NewBrief, OfficeCb, ToneCb
from app.texts import Translator, all_variants
from app.utils import clean_text, deep_link
from app.views import lead_card_text

router = Router(name="manager")
router.message.filter(IsManager())
router.callback_query.filter(IsManager())

# Reply-keyboard buttons must never be swallowed as free-text answers.
MENU_TEXTS = all_variants("btn_new_brief") | all_variants("btn_my_leads") | all_variants("btn_admin")


# ---------------------------------------------------------------- new brief link

@router.message(F.text.in_(all_variants("btn_new_brief")))
@router.message(Command("new"))
async def new_brief(message: Message, state: FSMContext, t: Translator) -> None:
    await state.clear()
    await state.set_state(NewBrief.client_name)
    await message.answer(t("ask_client_name"))


@router.callback_query(MgrCb.filter(F.action == "new"))
async def new_brief_cb(cb: CallbackQuery, state: FSMContext, t: Translator) -> None:
    await state.clear()
    await state.set_state(NewBrief.client_name)
    await cb.message.answer(t("ask_client_name"))
    await cb.answer()


@router.message(NewBrief.client_name, F.text, ~F.text.in_(MENU_TEXTS))
async def got_client_name(message: Message, state: FSMContext, t: Translator) -> None:
    name = clean_text(message.text)
    if not 2 <= len(name) <= 64 or name.startswith("/"):
        await message.answer(t("bad_client_name"))
        return
    await state.update_data(client_name=name)
    await state.set_state(NewBrief.tone)
    await message.answer(t("ask_tone", client=escape(name)), reply_markup=kb.tones(t))


@router.callback_query(NewBrief.tone, ToneCb.filter(F.tone.in_(kb.TONES)))
async def got_tone(cb: CallbackQuery, callback_data: ToneCb, state: FSMContext, session: AsyncSession, t: Translator) -> None:
    offices = await repo.list_catalog(session, "office")
    if not offices:
        await state.clear()
        await safe_edit(cb.message, t("no_offices"))
        await cb.answer()
        return
    await state.update_data(tone=callback_data.tone)
    await state.set_state(NewBrief.office)
    await safe_edit(cb.message, t("ask_office"), kb.offices(offices))
    await cb.answer()


@router.callback_query(NewBrief.office, OfficeCb.filter())
async def got_office(
    cb: CallbackQuery,
    callback_data: OfficeCb,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    settings: Settings,
    t: Translator,
    bot: Bot,
) -> None:
    item = await repo.get_catalog_item(session, callback_data.item_id)
    if item is None or not item.is_active:
        await safe_edit(cb.message, t("ask_office"), kb.offices(await repo.list_catalog(session, "office")))
        await cb.answer()
        return
    data = await state.get_data()
    brief = await repo.create_brief(session, user.id, data["client_name"], data["tone"], item.label)
    await state.clear()
    link = deep_link((await bot.me()).username, f"b_{brief.code}")
    share = t("share_text", client=brief.client_name, company=settings.company_name)
    await safe_edit(
        cb.message,
        t("brief_ready", client=escape(brief.client_name), link=link),
        kb.brief_ready(t, link, share),
    )
    await cb.answer()


@router.message(StateFilter(NewBrief.tone, NewBrief.office), ~F.text.in_(MENU_TEXTS))
async def expected_button(message: Message, t: Translator) -> None:
    await message.answer(t("use_buttons"))


@router.callback_query(ToneCb.filter())
@router.callback_query(OfficeCb.filter())
async def stale_brief_button(cb: CallbackQuery, t: Translator) -> None:
    await cb.answer(t("step_expired"), show_alert=True)


# ---------------------------------------------------------------- leads

@router.message(F.text.in_(all_variants("btn_my_leads")))
@router.message(Command("leads"))
async def my_leads(message: Message, state: FSMContext, session: AsyncSession, user: User, t: Translator) -> None:
    await state.clear()
    briefs = await repo.manager_briefs(session, user.id)
    if not briefs:
        await message.answer(t("leads_empty"))
        return
    await message.answer(t("leads_header"), reply_markup=kb.leads_list(briefs))


@router.callback_query(MgrCb.filter(F.action == "leads"))
async def my_leads_cb(cb: CallbackQuery, session: AsyncSession, user: User, t: Translator) -> None:
    briefs = await repo.manager_briefs(session, user.id)
    await safe_edit(cb.message, t("leads_header") if briefs else t("leads_empty"), kb.leads_list(briefs))
    await cb.answer()


@router.callback_query(LeadCb.filter())
async def lead_action(
    cb: CallbackQuery,
    callback_data: LeadCb,
    session: AsyncSession,
    user: User,
    settings: Settings,
    t: Translator,
    bot: Bot,
) -> None:
    brief = await repo.get_brief(session, callback_data.brief_id)
    if brief is None or brief.manager_id != user.id:
        await cb.answer(t("not_your_lead"), show_alert=True)
        return
    with_back = callback_data.action == "open" or _has_back_button(cb)
    if callback_data.action == "set" and callback_data.value in ("new", "contacted", "closed"):
        await repo.set_lead_status(session, brief.id, user.id, callback_data.value)
        await cb.answer(t("lead_status_set", status=t(f"status_{callback_data.value}")))
    else:
        await cb.answer()
    client = await session.get(User, brief.client_id) if brief.client_id else None
    link = deep_link((await bot.me()).username, f"b_{brief.code}")
    await safe_edit(
        cb.message,
        lead_card_text(t, brief, client, link, settings.timezone, await repo.brief_payment(session, brief.id)),
        kb.lead_actions(t, brief, client, with_back=with_back),
    )


def _has_back_button(cb: CallbackQuery) -> bool:
    markup = cb.message.reply_markup if cb.message else None
    if markup is None:
        return False
    back = MgrCb(action="leads").pack()
    return any(button.callback_data == back for row in markup.inline_keyboard for button in row)
