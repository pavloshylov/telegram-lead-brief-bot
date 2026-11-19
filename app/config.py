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


def _parse_bool(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: frozenset[int] = field(default_factory=frozenset)
    database_url: str = "sqlite+aiosqlite:///data/bot.db"
    company_name: str = "Northwind Studio"
    timezone: str = "Europe/Kyiv"
    # Demo only: lets a manager open their own brief link (to try both roles with one account).
    allow_self_brief: bool = False
    broadcast_rate: float = 20.0  # messages per second, below Telegram's ~30/s limit

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
        allow_self_brief=_parse_bool(env.get("ALLOW_SELF_BRIEF")),
        broadcast_rate=float(env.get("BROADCAST_RATE") or Settings.broadcast_rate),
    )
