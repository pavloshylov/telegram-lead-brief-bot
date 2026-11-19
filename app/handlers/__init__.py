from aiogram import Router

from app.handlers import admin, client, fallback, manager, start


def routers() -> list[Router]:
    """Order matters: commands first, then role-specific routers, the catch-all last."""
    return [start.router, manager.router, admin.router, client.router, fallback.router]
