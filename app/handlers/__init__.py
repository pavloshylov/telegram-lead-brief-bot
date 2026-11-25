from aiogram import Router

from app.handlers import admin, admin_payments, client, fallback, manager, payments, start


def routers() -> list[Router]:
    """Order matters: commands first, then role-specific routers, the catch-all last."""
    return [start.router, manager.router, admin.router, admin_payments.router, client.router, payments.router, fallback.router]
