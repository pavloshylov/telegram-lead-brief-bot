"""In-process fake of the Telegram Bot API for end-to-end tests.

The bot runs its real handlers, middlewares and database; only the HTTP layer is replaced.
Every API call is recorded, and each chat's visible state (messages, edits, inline keyboards,
reply keyboard, alerts) is kept, so tests can "click" buttons exactly as a user would.
"""
from __future__ import annotations

import itertools
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import (
    AnswerCallbackQuery,
    CopyMessage,
    EditMessageReplyMarkup,
    EditMessageText,
    GetMe,
    SendDocument,
    SendMessage,
    TelegramMethod,
)
from aiogram.types import (
    CallbackQuery,
    Chat,
    InlineKeyboardMarkup,
    Message,
    MessageId,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
    User,
)

BOT_USER = User(id=42, is_bot=True, first_name="Northwind Brief", username="northwind_brief_bot")


@dataclass
class Bubble:
    id: int
    sender: str  # "bot" | "user"
    text: str = ""
    markup: InlineKeyboardMarkup | None = None
    document: tuple[str, bytes] | None = None
    edited: bool = False

    def buttons(self) -> list[list[Any]]:
        return self.markup.inline_keyboard if self.markup else []

    def button_texts(self) -> list[str]:
        return [b.text for row in self.buttons() for b in row]


@dataclass
class ChatState:
    bubbles: list[Bubble] = field(default_factory=list)
    reply_keyboard: ReplyKeyboardMarkup | None = None
    alerts: list[tuple[str, bool]] = field(default_factory=list)

    def find(self, message_id: int) -> Bubble:
        return next(b for b in self.bubbles if b.id == message_id)

    def bot_bubbles(self) -> list[Bubble]:
        return [b for b in self.bubbles if b.sender == "bot"]


class FakeTelegram(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod] = []
        self.chats: dict[int, ChatState] = defaultdict(ChatState)
        self.blocked: set[int] = set()  # chats that "blocked the bot"
        self._ids = itertools.count(1000)
        self._callback_chat: dict[str, int] = {}

    async def close(self) -> None:
        return None

    async def stream_content(self, *args: Any, **kwargs: Any):  # pragma: no cover - not used
        raise NotImplementedError
        yield b""

    def next_id(self) -> int:
        return next(self._ids)

    async def make_request(self, bot: Bot, method: TelegramMethod, timeout: int | None = None) -> Any:
        self.calls.append(method)
        chat_id = getattr(method, "chat_id", None)
        if isinstance(method, (SendMessage, CopyMessage, SendDocument)) and chat_id in self.blocked:
            raise TelegramForbiddenError(method=method, message="Forbidden: bot was blocked by the user")

        if isinstance(method, GetMe):
            return BOT_USER
        if isinstance(method, SendMessage):
            bubble = self._add_bot_bubble(chat_id, method.text, method.reply_markup)
            return self._message(bot, chat_id, bubble)
        if isinstance(method, EditMessageText):
            bubble = self.chats[method.chat_id].find(method.message_id)
            bubble.text, bubble.markup, bubble.edited = method.text, _inline(method.reply_markup), True
            return self._message(bot, method.chat_id, bubble)
        if isinstance(method, EditMessageReplyMarkup):
            bubble = self.chats[method.chat_id].find(method.message_id)
            bubble.markup = _inline(method.reply_markup)
            return self._message(bot, method.chat_id, bubble)
        if isinstance(method, CopyMessage):
            source = self.chats[method.from_chat_id].find(method.message_id)
            bubble = self._add_bot_bubble(chat_id, source.text, method.reply_markup)
            return MessageId(message_id=bubble.id)
        if isinstance(method, SendDocument):
            doc = method.document
            bubble = self._add_bot_bubble(chat_id, method.caption or "", method.reply_markup)
            bubble.document = (doc.filename, doc.data)
            return self._message(bot, chat_id, bubble)
        if isinstance(method, AnswerCallbackQuery):
            if method.text:
                self.chats[self._callback_chat.get(method.callback_query_id, 0)].alerts.append(
                    (method.text, bool(method.show_alert))
                )
            return True
        return True  # SetMyCommands and other fire-and-forget calls

    # ------------------------------------------------------------ helpers

    def _add_bot_bubble(self, chat_id: int, text: str, markup: Any) -> Bubble:
        chat = self.chats[chat_id]
        if isinstance(markup, ReplyKeyboardMarkup):
            chat.reply_keyboard = markup
        elif isinstance(markup, ReplyKeyboardRemove):
            chat.reply_keyboard = None
        bubble = Bubble(id=self.next_id(), sender="bot", text=text, markup=_inline(markup))
        chat.bubbles.append(bubble)
        return bubble

    def _message(self, bot: Bot, chat_id: int, bubble: Bubble) -> Message:
        return Message(
            message_id=bubble.id,
            date=datetime.now(timezone.utc),
            chat=Chat(id=chat_id, type="private"),
            from_user=BOT_USER,
            text=bubble.text or None,
            reply_markup=bubble.markup,
        ).as_(bot)


def _inline(markup: Any) -> InlineKeyboardMarkup | None:
    return markup if isinstance(markup, InlineKeyboardMarkup) else None


class Harness:
    """Drives the dispatcher as real users would."""

    def __init__(self, dp: Dispatcher, api: FakeTelegram):
        self.dp = dp
        self.api = api
        self.bot = Bot("42:TEST", session=api, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self._updates = itertools.count(1)

    @staticmethod
    def user(user_id: int, first_name: str, username: str | None = None, lang: str = "en") -> User:
        return User(id=user_id, is_bot=False, first_name=first_name, username=username, language_code=lang)

    def chat(self, user: User) -> ChatState:
        return self.api.chats[user.id]

    def last(self, user: User) -> Bubble:
        return self.chat(user).bot_bubbles()[-1]

    def texts(self, user: User) -> list[str]:
        return [b.text for b in self.chat(user).bot_bubbles()]

    def alerts(self, user: User) -> list[str]:
        return [text for text, _ in self.chat(user).alerts]

    async def send(self, user: User, text: str) -> None:
        bubble = Bubble(id=self.api.next_id(), sender="user", text=text)
        self.chat(user).bubbles.append(bubble)
        message = Message(
            message_id=bubble.id,
            date=datetime.now(timezone.utc),
            chat=Chat(id=user.id, type="private", first_name=user.first_name),
            from_user=user,
            text=text,
        )
        await self.dp.feed_update(self.bot, Update(update_id=next(self._updates), message=message))

    async def start(self, user: User, payload: str | None = None) -> None:
        await self.send(user, f"/start {payload}" if payload else "/start")

    async def click(self, user: User, button_text: str) -> None:
        """Press the newest inline button with this exact text in the user's chat."""
        for bubble in reversed(self.chat(user).bot_bubbles()):
            for row in bubble.buttons():
                for button in row:
                    if button.text == button_text and button.callback_data:
                        await self._press(user, bubble, button.callback_data)
                        return
        raise AssertionError(f"button {button_text!r} not found; last message: {self.last(user).text!r}")

    async def click_in(self, user: User, bubble: Bubble, button_text: str) -> None:
        """Press a button on a specific (possibly old) message."""
        for row in bubble.buttons():
            for button in row:
                if button.text == button_text and button.callback_data:
                    await self._press(user, bubble, button.callback_data)
                    return
        raise AssertionError(f"button {button_text!r} not on that message")

    async def _press(self, user: User, bubble: Bubble, data: str) -> None:
        query_id = str(self.api.next_id())
        self.api._callback_chat[query_id] = user.id
        message = Message(
            message_id=bubble.id,
            date=datetime.now(timezone.utc),
            chat=Chat(id=user.id, type="private"),
            from_user=BOT_USER,
            text=bubble.text or None,
            reply_markup=bubble.markup,
        )
        query = CallbackQuery(id=query_id, from_user=user, chat_instance="ci", message=message, data=data)
        await self.dp.feed_update(self.bot, Update(update_id=next(self._updates), callback_query=query))
