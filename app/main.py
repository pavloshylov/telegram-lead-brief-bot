"""Entry point: python -m app"""
from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import repo
from app.config import Settings, load_settings
from app.db import init_db, make_engine, make_session_maker
from app.handlers import routers
from app.middlewares import ContextMiddleware
from app.texts import LANGS, Translator

log = logging.getLogger("brief_bot")


def build_dispatcher(
    settings: Settings, session_maker: async_sessionmaker[AsyncSession], storage: BaseStorage | None = None
) -> Dispatcher:
    dp = Dispatcher(storage=storage or MemoryStorage())
    dp.update.outer_middleware(ContextMiddleware(session_maker, settings))
    dp.include_routers(*routers())
    return dp


def make_bot(settings: Settings) -> Bot:
    session = None
    if settings.telegram_test_env:  # https://core.telegram.org/bots/features#testing-your-bot
        session = AiohttpSession(
            api=TelegramAPIServer(
                base="https://api.telegram.org/bot{token}/test/{method}",
                file="https://api.telegram.org/file/bot{token}/test/{path}",
            )
        )
    return Bot(
        settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )


async def set_commands(bot: Bot, settings: Settings) -> None:
    fixed = settings.language != "auto"
    for lang in LANGS:
        code = None if lang == "en" else lang
        if fixed and code is not None:  # one language for everyone: drop per-language command lists
            await bot.delete_my_commands(scope=BotCommandScopeDefault(), language_code=code)
            continue
        t = Translator(settings.language if fixed else lang)
        base = [BotCommand(command=c, description=t(f"cmd_{c}")) for c in ("start", "help", "cancel")]
        await bot.set_my_commands(base, scope=BotCommandScopeDefault(), language_code=code)
    for admin_id in settings.admin_ids:  # admins also see /admin
        t = Translator(settings.language if fixed else "en")
        commands = [BotCommand(command=c, description=t(f"cmd_{c}")) for c in ("start", "admin", "help", "cancel")]
        try:
            await bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception:  # noqa: BLE001 — admin has not started the bot yet
            log.warning("could not set admin commands for %s (has the admin started the bot?)", admin_id)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings(os.environ.get("ENV_FILE") or ".env")  # ENV_FILE: run another config side by side
    engine = make_engine(settings.database_url)
    await init_db(engine)
    session_maker = make_session_maker(engine)
    async with session_maker() as session:
        await repo.seed_defaults(session)
        await session.commit()

    bot = make_bot(settings)
    dp = build_dispatcher(settings, session_maker)
    await set_commands(bot, settings)
    me = await bot.me()
    log.info("started as @%s, admins: %s, db: %s", me.username, sorted(settings.admin_ids), engine.url.render_as_string())
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await engine.dispose()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
