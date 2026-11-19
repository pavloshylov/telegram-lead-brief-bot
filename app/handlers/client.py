"""Client side: personalised greeting, 4-step brief on inline buttons, confirmation, submission."""
from __future__ import annotations

from datetime import date
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app import keyboards as kb
from app import repo
from app.config import Settings
from app.db import Brief, User
from app.services import notify_manager, safe_edit
from app.states import CLIENT_BUTTON_STEPS, ClientBrief, ClientCb
from app.texts import Translator
from app.utils import check_date, clean_text, example_date, now_local, parse_date, parse_time, progress_bar
from app.views import TIME_SLOTS, brief_summary, day_is_today, day_options, summary

router = Router(name="client")

STEP_NUMBER = {"service": 1, "budget": 2, "day": 3, "time": 4}
STEP_STATE = {
    "service": ClientBrief.service,
    "budget": ClientBrief.budget,
    "day": ClientBrief.day,
    "time": ClientBrief.time,
    "confirm": ClientBrief.confirm,
}
STATE_STEP = {state.state: step for step, state in STEP_STATE.items()}
ANSWER_KEYS = ("service", "budget", "day", "time")


# ---------------------------------------------------------------- entry point (called from /start b_<code>)

async def open_brief(
    message: Message, state: FSMContext, session: AsyncSession, user: User, settings: Settings, t: Translator, code: str
) -> None:
    brief = await repo.get_brief_by_code(session, code)
    if brief is None:
        await message.answer(t("link_invalid"))
        return
    manager = await session.get(User, brief.manager_id)
    manager_name = escape(manager.first_name if manager else settings.company_name)
    if brief.status == "completed":
        if brief.client_id == user.id:
            await message.answer(t("already_answered_self", manager=manager_name, summary=brief_summary(t, brief)))
        else:
            await message.answer(t("already_answered_other", company=escape(settings.company_name)))
        return
    if brief.manager_id == user.id and not settings.allow_self_brief:
        await message.answer(t("self_brief"))
        return
    await state.set_data({"brief_id": brief.id})
    greeting = t(
        f"greet_{brief.tone}",
        client=escape(brief.client_name),
        manager=manager_name,
        company=escape(settings.company_name),
        office=escape(brief.office),
    )
    await message.answer(greeting, reply_markup=kb.client_start(t, brief.id))


# ---------------------------------------------------------------- step rendering

async def render_step(
    step: str, brief: Brief, data: dict, session: AsyncSession, t: Translator, today: date
) -> tuple[str, InlineKeyboardMarkup]:
    if step == "confirm":
        text = t(
            "confirm",
            summary=summary(
                t, service=data["service"], budget=data["budget"], day=data["day"], time=data["time"], office=brief.office
            ),
        )
        return text, kb.client_confirm(t, brief.id)
    header = t("step_header", n=STEP_NUMBER[step], bar=progress_bar(STEP_NUMBER[step]))
    if step == "service":
        markup = kb.client_services(t, brief.id, await repo.list_catalog(session, "service"))
    elif step == "budget":
        markup = kb.client_budgets(t, brief.id, await repo.list_catalog(session, "budget"))
    elif step == "day":
        markup = kb.client_days(t, brief.id, [value for value, _ in day_options(today)])
    else:
        markup = kb.client_times(t, brief.id)
    return f"{header}\n\n{t('q_' + step)}", markup


async def go_to_step(
    step: str,
    target: Message,
    state: FSMContext,
    brief: Brief,
    session: AsyncSession,
    t: Translator,
    today: date,
    edit: bool,
) -> None:
    data = await state.get_data()
    text, markup = await render_step(step, brief, data, session, t, today)
    await state.set_state(STEP_STATE[step])
    if edit:
        await safe_edit(target, text, markup)
    else:
        await target.answer(text, reply_markup=markup)


def _prompt(t: Translator, step: str, key: str, **kwargs: object) -> str:
    return f"{t('step_header', n=STEP_NUMBER[step], bar=progress_bar(STEP_NUMBER[step]))}\n\n{t(key, **kwargs)}"


# ---------------------------------------------------------------- button presses

@router.callback_query(ClientCb.filter())
async def client_button(
    cb: CallbackQuery,
    callback_data: ClientCb,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    settings: Settings,
    t: Translator,
    bot: Bot,
) -> None:
    brief = await repo.get_brief(session, callback_data.brief_id)
    if brief is None:
        await cb.answer(t("link_invalid"), show_alert=True)
        return
    if brief.status == "completed":
        await cb.answer(t("brief_already_sent"), show_alert=True)
        return
    data = await state.get_data()
    if data.get("brief_id") != brief.id:
        await cb.answer(t("step_expired"), show_alert=True)
        return

    step, value = callback_data.step, callback_data.value
    today = now_local(settings.timezone).date()
    go = lambda name, edit=True: go_to_step(name, cb.message, state, brief, session, t, today, edit)  # noqa: E731

    if step == "go":
        await cb.message.edit_reply_markup(reply_markup=None)  # keep the greeting, drop its button
        await go("service", edit=False)
    elif step == "svc":
        if value == "other":
            await state.set_state(ClientBrief.service_text)
            await safe_edit(cb.message, _prompt(t, "service", "ask_service_text"))
        else:
            item = await repo.get_catalog_item(session, int(value)) if value.isdigit() else None
            if item is None or not item.is_active or item.kind != "service":
                await go("service")
            else:
                await state.update_data(service=item.label)
                await go("budget")
    elif step == "bud":
        item = await repo.get_catalog_item(session, int(value)) if value.isdigit() else None
        if item is None or not item.is_active or item.kind != "budget":
            await go("budget")
        else:
            await state.update_data(budget=item.label)
            await go("day")
    elif step == "day":
        if value == "pick":
            await state.set_state(ClientBrief.date_text)
            await safe_edit(cb.message, _prompt(t, "day", "ask_date", example=example_date(today)))
        else:
            code = dict(day_options(today)).get(value)
            if code is None:  # e.g. "later this week" pressed after the week moved on
                await go("day")
            else:
                await state.update_data(day=code)
                await go("time")
    elif step == "time":
        if value == "exact":
            await state.set_state(ClientBrief.time_text)
            await safe_edit(cb.message, _prompt(t, "time", "ask_time"))
        elif value in TIME_SLOTS:
            await state.update_data(time=f"s:{value}")
            await go("confirm")
    elif step == "back" and value in STEP_NUMBER:
        await go(value)
    elif step == "restart":
        await state.set_data({"brief_id": brief.id})
        await go("service")
    elif step == "send":
        if any(key not in data for key in ANSWER_KEYS):
            await go("service")
        else:
            await submit(cb, state, session, user, t, bot, brief, data)
            return  # submit answers the callback itself
    await cb.answer()


async def submit(
    cb: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    t: Translator,
    bot: Bot,
    brief: Brief,
    data: dict,
) -> None:
    saved = await repo.complete_brief(
        session, brief.id, user.id, data["service"], data["budget"], data["day"], data["time"]
    )
    if not saved:  # someone (or a second tap) got there first
        await state.clear()
        await cb.answer(t("brief_already_sent"), show_alert=True)
        return
    await session.refresh(brief)
    await state.clear()
    manager = await session.get(User, brief.manager_id)
    await safe_edit(
        cb.message,
        t("sent", client=escape(brief.client_name), manager=escape(manager.first_name if manager else "")),
    )
    await cb.answer()
    await notify_manager(bot, session, brief, user)


# ---------------------------------------------------------------- typed answers

@router.message(ClientBrief.service_text, F.text)
async def typed_service(message: Message, state: FSMContext, session: AsyncSession, settings: Settings, t: Translator) -> None:
    text = clean_text(message.text)
    if not 2 <= len(text) <= 100 or text.startswith("/"):
        await message.answer(t("bad_service_text"))
        return
    brief = await _current_brief(state, session)
    if brief is None:
        await message.answer(t("step_expired"))
        return
    await state.update_data(service=text)
    await go_to_step("budget", message, state, brief, session, t, now_local(settings.timezone).date(), edit=False)


@router.message(ClientBrief.date_text, F.text)
async def typed_date(message: Message, state: FSMContext, session: AsyncSession, settings: Settings, t: Translator) -> None:
    today = now_local(settings.timezone).date()
    value = parse_date(message.text, today)
    if value is None:
        await message.answer(t("bad_date", example=example_date(today)))
        return
    problem = check_date(value, today)
    if problem:
        await message.answer(t(problem))
        return
    brief = await _current_brief(state, session)
    if brief is None:
        await message.answer(t("step_expired"))
        return
    await state.update_data(day=f"d:{value.isoformat()}")
    await go_to_step("time", message, state, brief, session, t, today, edit=False)


@router.message(ClientBrief.time_text, F.text)
async def typed_time(message: Message, state: FSMContext, session: AsyncSession, settings: Settings, t: Translator) -> None:
    now = now_local(settings.timezone)
    value = parse_time(message.text)
    if value is None:
        await message.answer(t("bad_time"))
        return
    data = await state.get_data()
    if day_is_today(data.get("day"), now.date()) and value <= now.time().replace(tzinfo=None):
        await message.answer(t("time_past"))
        return
    brief = await _current_brief(state, session)
    if brief is None:
        await message.answer(t("step_expired"))
        return
    await state.update_data(time=f"t:{value.strftime('%H:%M')}")
    await go_to_step("confirm", message, state, brief, session, t, now.date(), edit=False)


@router.message(StateFilter(*CLIENT_BUTTON_STEPS))
async def expected_button(message: Message, state: FSMContext, session: AsyncSession, settings: Settings, t: Translator) -> None:
    """Free text (or a sticker/photo) where a button is expected: hint and re-show the step below it."""
    brief = await _current_brief(state, session)
    step = STATE_STEP.get(await state.get_state() or "")
    await message.answer(t("use_buttons"))
    if brief is not None and step is not None:
        await go_to_step(step, message, state, brief, session, t, now_local(settings.timezone).date(), edit=False)


@router.message(StateFilter(ClientBrief.service_text, ClientBrief.date_text, ClientBrief.time_text))
async def expected_text(message: Message, state: FSMContext, settings: Settings, t: Translator) -> None:
    """A sticker/photo/voice where a typed answer is expected."""
    current = await state.get_state()
    if current == ClientBrief.date_text.state:
        await message.answer(t("bad_date", example=example_date(now_local(settings.timezone).date())))
    elif current == ClientBrief.time_text.state:
        await message.answer(t("bad_time"))
    else:
        await message.answer(t("bad_service_text"))


async def _current_brief(state: FSMContext, session: AsyncSession) -> Brief | None:
    brief_id = (await state.get_data()).get("brief_id")
    brief = await repo.get_brief(session, brief_id) if brief_id else None
    return brief if brief is not None and brief.status == "open" else None
