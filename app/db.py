"""Database models and engine setup (SQLAlchemy 2.x, async).

SQLite (aiosqlite) by default; PostgreSQL works by switching DATABASE_URL to
postgresql+asyncpg://... — no code changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)  # Telegram user id
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(128), default="")
    language: Mapped[str] = mapped_column(String(8), default="en")
    is_manager: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)  # user blocked the bot
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CatalogItem(Base):
    """Admin-editable answer options: offices, services, budget ranges."""

    __tablename__ = "catalog_items"
    __table_args__ = (UniqueConstraint("kind", "label", name="uq_catalog_kind_label"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)
    label: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


class Brief(Base):
    """One personal brief link. Answers are stored as label snapshots, so later
    catalog edits never change what a client actually picked."""

    __tablename__ = "briefs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    manager_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    client_name: Mapped[str] = mapped_column(String(64))
    tone: Mapped[str] = mapped_column(String(16))
    office: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | completed
    lead_status: Mapped[str] = mapped_column(String(16), default="new")  # new | contacted | closed
    client_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    service: Mapped[str | None] = mapped_column(String(128))
    budget: Mapped[str | None] = mapped_column(String(64))
    meet_day: Mapped[str | None] = mapped_column(String(64))
    meet_time: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ManagerInvite(Base):
    """One-time link that turns whoever opens it into a manager."""

    __tablename__ = "manager_invites"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    created_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    used_by: Mapped[int | None] = mapped_column(BigInteger)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def make_engine(database_url: str) -> AsyncEngine:
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    return create_async_engine(database_url, pool_pre_ping=True)


def make_session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
