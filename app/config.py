"""Settings loaded from environment variables (and an optional .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _parse_ids(raw: str) -> frozenset[int]:
    ids = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part:
            ids.add(int(part))
    return frozenset(ids)


def _parse_language(raw: str | None) -> str:
    value = (raw or "en").strip().lower()
    if value not in {"en", "uk", "auto"}:
        raise SystemExit(f"BOT_LANGUAGE must be en, uk or auto, got {raw!r}")
    return value


def _parse_bool(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: frozenset[int] = field(default_factory=frozenset)
    database_url: str = "sqlite+aiosqlite:///data/bot.db"
    company_name: str = "Northwind Studio"
    timezone: str = "Europe/Kyiv"
    # "en" / "uk" = everyone gets that language; "auto" = each user's Telegram language (uk -> Ukrainian, else English)
    language: str = "en"
    # Demo only: lets a manager open their own brief link (to try both roles with one account).
    allow_self_brief: bool = False
    broadcast_rate: float = 20.0  # messages per second, below Telegram's ~30/s limit
    # Payments (optional). Empty provider token = card payments off; PAYMENTS_STARS=on enables Telegram Stars.
    payments_provider_token: str = field(default="", repr=False)
    payments_stars: bool = False
    payments_currency: str = "USD"  # ISO 4217 code with 2 decimals (USD, EUR, PLN, ...); used with the provider token
    # Talk to Telegram's separate test environment (test accounts, test bots, no real money); the token must come from
    # @BotFather on the test server.
    telegram_test_env: bool = False

    @property
    def card_payments(self) -> bool:
        return bool(self.payments_provider_token)

    @property
    def payments_enabled(self) -> bool:
        return self.card_payments or self.payments_stars

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


def load_settings(env_file: str | Path = ".env") -> Settings:
    env = {**_read_env_file(Path(env_file)), **os.environ}
    token = env.get("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN is not set (see .env.example)")
    return Settings(
        bot_token=token,
        admin_ids=_parse_ids(env.get("ADMIN_IDS", "")),
        database_url=env.get("DATABASE_URL") or Settings.database_url,
        company_name=env.get("COMPANY_NAME") or Settings.company_name,
        timezone=env.get("TIMEZONE") or Settings.timezone,
        language=_parse_language(env.get("BOT_LANGUAGE")),
        allow_self_brief=_parse_bool(env.get("ALLOW_SELF_BRIEF")),
        broadcast_rate=float(env.get("BROADCAST_RATE") or Settings.broadcast_rate),
        payments_provider_token=env.get("PAYMENTS_PROVIDER_TOKEN", "").strip(),
        payments_stars=_parse_bool(env.get("PAYMENTS_STARS")),
        payments_currency=(env.get("PAYMENTS_CURRENCY") or Settings.payments_currency).strip().upper(),
        telegram_test_env=_parse_bool(env.get("TELEGRAM_TEST_ENV")),
    )
