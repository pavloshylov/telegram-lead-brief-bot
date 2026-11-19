"""Last-resort handlers: unknown input, stale buttons and errors."""
from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import CallbackQuery, ErrorEvent, Message

from app.texts import Translator

router = Router(name="fallback")
log = logging.getLogger(__name__)


@router.message()
async def unknown_message(message: Message, t: Translator) -> None:
    await message.answer(t("unknown"))


@router.callback_query()
async def unknown_button(cb: CallbackQuery, t: Translator) -> None:
    await cb.answer(t("step_expired"), show_alert=True)


@router.error()
async def on_error(event: ErrorEvent, t: Translator | None = None) -> bool:
    """Log the traceback and tell the user something went wrong instead of staying silent."""
    log.exception("update %s failed", event.update.update_id, exc_info=event.exception)
    t = t or Translator("en")
    try:
        if event.update.callback_query:
            await event.update.callback_query.answer(t("error"), show_alert=True)
        elif event.update.message:
            await event.update.message.answer(t("error"))
    except Exception:  # noqa: BLE001 — never let the error handler raise
        log.warning("could not report the error to the user", exc_info=True)
    return True
