"""/start (plain and with deep-link payloads), /help, /cancel."""
from __future__ import annotations

from html import escape

from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from app import keyboards as kb
from app import repo
from app.config import Settings
from app.db import User
from app.handlers.client import open_brief
from app.texts import Translator

router = Router(name="start")


async def show_home(message: Message, user: User, settings: Settings, t: Translator) -> None:
    is_admin = settings.is_admin(user.id)
    if user.is_manager or is_admin:
        text = t("start_manager", name=escape(user.first_name), company=escape(settings.company_name))
        if is_admin:
            text += t("start_admin_extra")
        await message.answer(text, reply_markup=kb.manager_menu(t, is_admin))
    else:
        await message.answer(
            t("start_client", company=escape(settings.company_name)), reply_markup=ReplyKeyboardRemove()
        )


@router.message(CommandStart(deep_link=True))
async def start_with_payload(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    settings: Settings,
    t: Translator,
) -> None:
    await state.clear()
    payload = command.args or ""
    if payload.startswith("b_"):
        await open_brief(message, state, session, user, settings, t, payload[2:])
    elif payload.startswith("m_"):
        if user.is_manager or settings.is_admin(user.id):
            await message.answer(t("already_manager"))
        elif await repo.redeem_manager_invite(session, payload[2:], user.id):
            user.is_manager = True
            await message.answer(t("became_manager", company=escape(settings.company_name)))
            await show_home(message, user, settings, t)
        else:
            await message.answer(t("invite_invalid"))
    else:
        await show_home(message, user, settings, t)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, user: User, settings: Settings, t: Translator) -> None:
    await state.clear()
    await show_home(message, user, settings, t)


@router.message(Command("help"))
async def help_cmd(message: Message, t: Translator) -> None:
    await message.answer(t("help"))


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext, user: User, settings: Settings, t: Translator) -> None:
    if await state.get_state() is None:
        await message.answer(t("nothing_to_cancel"))
        return
    await state.clear()
    await message.answer(t("cancelled"))
    await show_home(message, user, settings, t)
