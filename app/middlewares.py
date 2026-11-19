"""Per-update context: one DB session, the current user (upserted), settings and a translator."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.filters import Filter
from aiogram.types import TelegramObject, User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import repo
from app.config import Settings
from app.db import User
from app.texts import Translator, pick_lang


class ContextMiddleware(BaseMiddleware):
    def __init__(self, session_maker: async_sessionmaker[AsyncSession], settings: Settings):
        self.session_maker = session_maker
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        async with self.session_maker() as session:
            data["session"] = session
            data["settings"] = self.settings
            data["session_maker"] = self.session_maker
            if tg_user is not None and not tg_user.is_bot:
                lang = pick_lang(tg_user.language_code)
                data["user"] = await repo.upsert_user(
                    session, tg_user.id, tg_user.username, tg_user.full_name, lang
                )
                data["t"] = Translator(lang)
            else:
                data["user"] = None
                data["t"] = Translator("en")
            try:
                result = await handler(event, data)
            except Exception:
                await session.rollback()
                raise
            await session.commit()
            return result


class IsManager(Filter):
    """Managers and admins."""

    async def __call__(self, event: TelegramObject, user: User | None, settings: Settings) -> bool:
        return user is not None and (user.is_manager or settings.is_admin(user.id))


class IsAdmin(Filter):
    async def __call__(self, event: TelegramObject, user: User | None, settings: Settings) -> bool:
        return user is not None and settings.is_admin(user.id)
