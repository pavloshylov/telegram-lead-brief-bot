"""Data access layer. Handlers never build SQL themselves."""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Brief, CatalogItem, ManagerInvite, User, utcnow

CATALOG_KINDS = ("office", "service", "budget")

DEFAULT_CATALOG: dict[str, list[str]] = {
    "office": ["Online call", "Kyiv office", "Warsaw office", "Berlin office"],
    "service": ["Web development", "Mobile app", "Data & analytics", "Marketing automation", "Design / UX"],
    "budget": ["Under $1k", "$1k – 5k", "$5k – 15k", "$15k+", "Not sure yet"],
}

MANAGER_INVITE_TTL = timedelta(days=7)


# ---------------------------------------------------------------- users

async def upsert_user(
    session: AsyncSession, user_id: int, username: str | None, first_name: str, language: str
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        user = User(id=user_id, username=username, first_name=first_name, language=language)
        session.add(user)
    else:
        user.username = username
        user.first_name = first_name
        user.language = language
        user.last_seen_at = utcnow()
        user.is_blocked = False  # they are writing to us, so not blocked
    await session.flush()
    return user


async def mark_blocked(session: AsyncSession, user_id: int) -> None:
    await session.execute(update(User).where(User.id == user_id).values(is_blocked=True))


async def list_managers(session: AsyncSession) -> list[User]:
    rows = await session.scalars(select(User).where(User.is_manager.is_(True)).order_by(User.created_at))
    return list(rows)


async def set_manager(session: AsyncSession, user_id: int, value: bool) -> bool:
    result = await session.execute(update(User).where(User.id == user_id).values(is_manager=value))
    return result.rowcount == 1


async def broadcast_targets(session: AsyncSession, segment: str, exclude: int | None = None) -> list[int]:
    """segment: all | managers | clients (users who completed at least one brief).
    `exclude` is the sender: they already saw the preview."""
    query = select(User.id).where(User.is_blocked.is_(False))
    if exclude is not None:
        query = query.where(User.id != exclude)
    if segment == "managers":
        query = query.where(User.is_manager.is_(True))
    elif segment == "clients":
        query = query.where(User.id.in_(select(Brief.client_id).where(Brief.client_id.is_not(None))))
    return list(await session.scalars(query.order_by(User.id)))


# ---------------------------------------------------------------- catalog

async def seed_defaults(session: AsyncSession) -> None:
    has_items = await session.scalar(select(func.count()).select_from(CatalogItem))
    if has_items:
        return
    for kind, labels in DEFAULT_CATALOG.items():
        for pos, label in enumerate(labels):
            session.add(CatalogItem(kind=kind, label=label, position=pos))
    await session.flush()


async def list_catalog(session: AsyncSession, kind: str, active_only: bool = True) -> list[CatalogItem]:
    query = select(CatalogItem).where(CatalogItem.kind == kind)
    if active_only:
        query = query.where(CatalogItem.is_active.is_(True))
    return list(await session.scalars(query.order_by(CatalogItem.position, CatalogItem.id)))


async def get_catalog_item(session: AsyncSession, item_id: int) -> CatalogItem | None:
    return await session.get(CatalogItem, item_id)


async def add_catalog_item(session: AsyncSession, kind: str, label: str) -> CatalogItem | None:
    """Returns None if an item with the same label already exists (case-insensitive)."""
    exists = await session.scalar(
        select(CatalogItem.id).where(CatalogItem.kind == kind, func.lower(CatalogItem.label) == label.lower())
    )
    if exists:
        return None
    last = await session.scalar(select(func.max(CatalogItem.position)).where(CatalogItem.kind == kind))
    item = CatalogItem(kind=kind, label=label, position=(last or 0) + 1)
    session.add(item)
    await session.flush()
    return item


async def toggle_catalog_item(session: AsyncSession, item_id: int) -> CatalogItem | None:
    item = await session.get(CatalogItem, item_id)
    if item is not None:
        item.is_active = not item.is_active
        await session.flush()
    return item


async def delete_catalog_item(session: AsyncSession, item_id: int) -> bool:
    item = await session.get(CatalogItem, item_id)
    if item is None:
        return False
    await session.delete(item)
    await session.flush()
    return True


# ---------------------------------------------------------------- briefs

def new_code() -> str:
    return secrets.token_urlsafe(8)  # 11 chars of [A-Za-z0-9_-], fits a deep-link payload


async def create_brief(session: AsyncSession, manager_id: int, client_name: str, tone: str, office: str) -> Brief:
    brief = Brief(code=new_code(), manager_id=manager_id, client_name=client_name, tone=tone, office=office)
    session.add(brief)
    await session.flush()
    return brief


async def get_brief(session: AsyncSession, brief_id: int) -> Brief | None:
    return await session.get(Brief, brief_id)


async def get_brief_by_code(session: AsyncSession, code: str) -> Brief | None:
    return await session.scalar(select(Brief).where(Brief.code == code))


async def complete_brief(
    session: AsyncSession, brief_id: int, client_id: int, service: str, budget: str, meet_day: str, meet_time: str
) -> bool:
    """Atomic: only the first submission wins, even if two taps arrive at the same time."""
    result = await session.execute(
        update(Brief)
        .where(Brief.id == brief_id, Brief.status == "open")
        .values(
            status="completed",
            client_id=client_id,
            service=service,
            budget=budget,
            meet_day=meet_day,
            meet_time=meet_time,
            completed_at=utcnow(),
        )
    )
    return result.rowcount == 1


async def set_lead_status(session: AsyncSession, brief_id: int, manager_id: int, status: str) -> Brief | None:
    brief = await session.get(Brief, brief_id)
    if brief is None or brief.manager_id != manager_id:
        return None
    brief.lead_status = status
    await session.flush()
    return brief


async def manager_briefs(session: AsyncSession, manager_id: int, limit: int = 10) -> list[Brief]:
    rows = await session.scalars(
        select(Brief).where(Brief.manager_id == manager_id).order_by(Brief.created_at.desc(), Brief.id.desc()).limit(limit)
    )
    return list(rows)


async def all_briefs(session: AsyncSession) -> list[tuple[Brief, User]]:
    rows = await session.execute(select(Brief, User).join(User, User.id == Brief.manager_id).order_by(Brief.id))
    return [(b, u) for b, u in rows.all()]


# ---------------------------------------------------------------- manager invites

async def create_manager_invite(session: AsyncSession, created_by: int) -> ManagerInvite:
    invite = ManagerInvite(code=new_code(), created_by=created_by)
    session.add(invite)
    await session.flush()
    return invite


async def redeem_manager_invite(session: AsyncSession, code: str, user_id: int) -> bool:
    """One-time and expiring. Returns True if the user became a manager."""
    invite = await session.get(ManagerInvite, code)
    if invite is None or invite.used_by is not None:
        return False
    created = invite.created_at if invite.created_at.tzinfo else invite.created_at.replace(tzinfo=utcnow().tzinfo)
    if utcnow() - created > MANAGER_INVITE_TTL:
        return False
    result = await session.execute(
        update(ManagerInvite)
        .where(ManagerInvite.code == code, ManagerInvite.used_by.is_(None))
        .values(used_by=user_id, used_at=utcnow())
    )
    if result.rowcount != 1:
        return False
    await set_manager(session, user_id, True)
    return True


# ---------------------------------------------------------------- stats

@dataclass
class Stats:
    users_total: int
    users_new_7d: int
    users_blocked: int
    managers: int
    briefs_created: int
    briefs_completed: int
    leads_contacted: int
    top_services: list[tuple[str, int]]
    top_managers: list[tuple[str, int]]

    @property
    def completion_rate(self) -> float:
        return self.briefs_completed / self.briefs_created if self.briefs_created else 0.0


async def get_stats(session: AsyncSession, admin_ids: frozenset[int] = frozenset()) -> Stats:
    """Admins (from ADMIN_IDS) also act as managers, so they are counted as managers."""
    week_ago = utcnow() - timedelta(days=7)
    count = lambda q: session.scalar(q)  # noqa: E731
    users_total = await count(select(func.count()).select_from(User))
    users_new = await count(select(func.count()).select_from(User).where(User.created_at >= week_ago))
    blocked = await count(select(func.count()).select_from(User).where(User.is_blocked.is_(True)))
    managers = await count(
        select(func.count()).select_from(User).where(User.is_manager.is_(True) | User.id.in_(list(admin_ids)))
    )
    created = await count(select(func.count()).select_from(Brief))
    completed = await count(select(func.count()).select_from(Brief).where(Brief.status == "completed"))
    contacted = await count(select(func.count()).select_from(Brief).where(Brief.lead_status != "new"))
    services = await session.execute(
        select(Brief.service, func.count())
        .where(Brief.status == "completed")
        .group_by(Brief.service)
        .order_by(func.count().desc(), Brief.service)
        .limit(3)
    )
    top_managers = await session.execute(
        select(User.first_name, func.count())
        .join(Brief, Brief.manager_id == User.id)
        .where(Brief.status == "completed")
        .group_by(User.id, User.first_name)
        .order_by(func.count().desc(), User.first_name)
        .limit(3)
    )
    return Stats(
        users_total=users_total or 0,
        users_new_7d=users_new or 0,
        users_blocked=blocked or 0,
        managers=managers or 0,
        briefs_created=created or 0,
        briefs_completed=completed or 0,
        leads_contacted=contacted or 0,
        top_services=[(s or "-", n) for s, n in services.all()],
        top_managers=[(m or "-", n) for m, n in top_managers.all()],
    )
