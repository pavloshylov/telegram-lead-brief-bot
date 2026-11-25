"""Keyboard builders. All texts come from the translator, all callback data from app.states."""
from __future__ import annotations

from urllib.parse import quote

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import Settings
from app.db import Brief, CatalogItem, Package, Payment, User
from app.payments import offered_methods, price_of, price_summary
from app.states import AdminCb, ClientCb, LeadCb, MgrCb, OfficeCb, PayCb, ToneCb
from app.texts import Translator
from app.views import TIME_SLOTS, lead_icon

TONES = ("formal", "friendly", "short")


def manager_menu(t: Translator, is_admin: bool) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=t("btn_new_brief")), KeyboardButton(text=t("btn_my_leads"))]]
    if is_admin:
        rows.append([KeyboardButton(text=t("btn_admin"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)


# ---------------------------------------------------------------- manager

def tones(t: Translator) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for tone in TONES:
        kb.button(text=t(f"tone_{tone}"), callback_data=ToneCb(tone=tone))
    return kb.adjust(1).as_markup()


def offices(items: list[CatalogItem]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for item in items:
        kb.button(text=item.label, callback_data=OfficeCb(item_id=item.id))
    return kb.adjust(2).as_markup()


def brief_ready(t: Translator, link: str, share_text: str) -> InlineKeyboardMarkup:
    share_url = f"https://t.me/share/url?url={quote(link, safe='')}&text={quote(share_text, safe='')}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_share"), url=share_url)],
            [InlineKeyboardButton(text=t("btn_another"), callback_data=MgrCb(action="new").pack())],
        ]
    )


def leads_list(briefs: list[Brief]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for brief in briefs:
        detail = brief.service or brief.office
        kb.button(
            text=f"{lead_icon(brief)} #{brief.id} {brief.client_name} · {detail}",
            callback_data=LeadCb(action="open", brief_id=brief.id),
        )
    return kb.adjust(1).as_markup()


def lead_actions(t: Translator, brief: Brief, client: User | None, with_back: bool) -> InlineKeyboardMarkup | None:
    rows: list[list[InlineKeyboardButton]] = []
    if brief.status == "completed":
        if client is not None and client.username:
            rows.append([InlineKeyboardButton(text=t("btn_open_chat"), url=f"https://t.me/{client.username}")])
        status_row = []
        if brief.lead_status == "new":
            status_row.append(_lead_btn(t("btn_contacted"), brief, "contacted"))
        if brief.lead_status in ("new", "contacted"):
            status_row.append(_lead_btn(t("btn_close_lead"), brief, "closed"))
        if brief.lead_status == "closed":
            status_row.append(_lead_btn(t("btn_reopen"), brief, "contacted"))
        rows.append(status_row)
    if with_back:
        rows.append([InlineKeyboardButton(text=t("btn_back"), callback_data=MgrCb(action="leads").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def _lead_btn(text: str, brief: Brief, value: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=LeadCb(action="set", brief_id=brief.id, value=value).pack())


# ---------------------------------------------------------------- client

def client_start(t: Translator, brief_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_start_brief"), callback_data=ClientCb(brief_id=brief_id, step="go"))
    return kb.as_markup()


def _back(t: Translator, brief_id: int, to: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=t("btn_back"), callback_data=ClientCb(brief_id=brief_id, step="back", value=to).pack())


def client_services(t: Translator, brief_id: int, items: list[CatalogItem]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for item in items:
        kb.button(text=item.label, callback_data=ClientCb(brief_id=brief_id, step="svc", value=str(item.id)))
    kb.button(text=t("btn_other_service"), callback_data=ClientCb(brief_id=brief_id, step="svc", value="other"))
    return kb.adjust(1).as_markup()


def client_budgets(t: Translator, brief_id: int, items: list[CatalogItem]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for item in items:
        kb.button(text=item.label, callback_data=ClientCb(brief_id=brief_id, step="bud", value=str(item.id)))
    kb.adjust(2)
    kb.row(_back(t, brief_id, "service"))
    return kb.as_markup()


def client_days(t: Translator, brief_id: int, values: list[str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for value in values:
        kb.button(text=t(f"day_{value}"), callback_data=ClientCb(brief_id=brief_id, step="day", value=value))
    kb.button(text=t("btn_pick_date"), callback_data=ClientCb(brief_id=brief_id, step="day", value="pick"))
    kb.adjust(2, 2, 1, 1) if len(values) == 4 else kb.adjust(2, 1, 1)
    kb.row(_back(t, brief_id, "budget"))
    return kb.as_markup()


def client_times(t: Translator, brief_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for slot in TIME_SLOTS:
        kb.button(text=t(f"time_{slot}"), callback_data=ClientCb(brief_id=brief_id, step="time", value=slot))
    kb.button(text=t("btn_exact_time"), callback_data=ClientCb(brief_id=brief_id, step="time", value="exact"))
    kb.adjust(1)
    kb.row(_back(t, brief_id, "day"))
    return kb.as_markup()


def client_confirm(t: Translator, brief_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_send"), callback_data=ClientCb(brief_id=brief_id, step="send"))
    kb.button(text=t("btn_restart"), callback_data=ClientCb(brief_id=brief_id, step="restart"))
    return kb.adjust(1).as_markup()


# ---------------------------------------------------------------- client payments

def pay_offer(t: Translator, brief_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_pay_offer"), callback_data=PayCb(action="menu", brief_id=brief_id))
    return kb.as_markup()


def pay_packages(t: Translator, brief_id: int, packages: list[Package], settings: Settings) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for package in packages:
        kb.button(
            text=f"{package.title} · {price_summary(package, settings)}",
            callback_data=PayCb(action="pkg", brief_id=brief_id, package_id=package.id),
        )
    kb.button(text=t("btn_pay_not_now"), callback_data=PayCb(action="cancel", brief_id=brief_id))
    return kb.adjust(1).as_markup()


def pay_methods(t: Translator, brief_id: int, package: Package, settings: Settings) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for method in offered_methods(package, settings):
        key = "btn_pay_stars" if method == "stars" else "btn_pay_card"
        kb.button(
            text=t(key, price=price_of(package, method, settings)),
            callback_data=PayCb(action="m", brief_id=brief_id, package_id=package.id, method=method),
        )
    kb.button(text=t("btn_back"), callback_data=PayCb(action="menu", brief_id=brief_id))
    return kb.adjust(1).as_markup()


# ---------------------------------------------------------------- admin

def _adm(text: str, action: str, value: str = "") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=AdminCb(action=action, value=value).pack())


def admin_menu(t: Translator) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_adm(t("btn_stats"), "stats"), _adm(t("btn_broadcast"), "bc")],
            [_adm(t("btn_catalogs"), "cat"), _adm(t("btn_team"), "team")],
            [_adm(t("btn_export"), "export"), _adm(t("btn_payments"), "pay")],
        ]
    )


def admin_back(t: Translator, to: str = "menu", value: str = "") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_adm(t("btn_back"), to, value)]])


def broadcast_segments(t: Translator, counts: dict[str, int]) -> InlineKeyboardMarkup:
    rows = [[_adm(t(f"seg_{seg}", n=counts[seg]), "bcseg", seg)] for seg in ("all", "managers", "clients")]
    rows.append([_adm(t("btn_back"), "menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def broadcast_confirm(t: Translator) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_adm(t("btn_bc_send"), "bcsend"), _adm(t("btn_cancel"), "bccancel")]])


def catalog_kinds(t: Translator) -> InlineKeyboardMarkup:
    rows = [[_adm(t(f"cat_{kind}"), "catkind", kind)] for kind in ("office", "service", "budget")]
    rows.append([_adm(t("btn_back"), "menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def catalog_items(t: Translator, kind: str, items: list[CatalogItem]) -> InlineKeyboardMarkup:
    rows = [[_adm(("" if item.is_active else "🙈 ") + item.label, "catitem", str(item.id))] for item in items]
    rows.append([_adm(t("btn_add"), "catadd", kind), _adm(t("btn_back"), "cat")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def catalog_item(t: Translator, item: CatalogItem) -> InlineKeyboardMarkup:
    toggle = t("btn_hide") if item.is_active else t("btn_show")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_adm(toggle, "cattoggle", str(item.id)), _adm(t("btn_delete"), "catdel", str(item.id))],
            [_adm(t("btn_back"), "catkind", item.kind)],
        ]
    )


def catalog_delete_confirm(t: Translator, item: CatalogItem) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_adm(t("btn_yes_delete"), "catdelok", str(item.id)), _adm(t("btn_cancel"), "catitem", str(item.id))]]
    )


def team(t: Translator, managers: list[User]) -> InlineKeyboardMarkup:
    rows = [
        [_adm(f"🧑‍💼 {m.first_name}" + (f" (@{m.username})" if m.username else ""), "teamrm", str(m.id))]
        for m in managers
    ]
    rows.append([_adm(t("btn_invite_manager"), "teaminvite")])
    rows.append([_adm(t("btn_back"), "menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def team_remove_confirm(t: Translator, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_adm(t("btn_yes_remove"), "teamrmok", str(user_id)), _adm(t("btn_cancel"), "team")]]
    )


# ---------------------------------------------------------------- admin payments

def payments_menu(t: Translator) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_adm(t("btn_pay_csv"), "paycsv"), _adm(t("btn_packages"), "pkgs")],
            [_adm(t("btn_refunds"), "refunds")],
            [_adm(t("btn_back"), "menu")],
        ]
    )


def packages_list(t: Translator, packages: list[Package]) -> InlineKeyboardMarkup:
    rows = [[_adm(("" if p.is_active else "🙈 ") + p.title, "pkg", str(p.id))] for p in packages]
    rows.append([_adm(t("btn_add"), "pkgadd"), _adm(t("btn_back"), "pay")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def package_item(t: Translator, package: Package) -> InlineKeyboardMarkup:
    toggle = t("btn_hide") if package.is_active else t("btn_show")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_adm(toggle, "pkgtoggle", str(package.id)), _adm(t("btn_edit_prices"), "pkgedit", str(package.id))],
            [_adm(t("btn_delete"), "pkgdel", str(package.id)), _adm(t("btn_back"), "pkgs")],
        ]
    )


def package_delete_confirm(t: Translator, package: Package) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_adm(t("btn_yes_delete"), "pkgdelok", str(package.id)), _adm(t("btn_cancel"), "pkg", str(package.id))]]
    )


def refunds_list(t: Translator, payments: list[Payment]) -> InlineKeyboardMarkup:
    rows = [[_adm(f"↩️ #{p.id} {p.title} · {p.amount} ⭐", "refund", str(p.id))] for p in payments]
    rows.append([_adm(t("btn_back"), "pay")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def refund_confirm(t: Translator, payment: Payment) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_adm(t("btn_yes_refund"), "refundok", str(payment.id)), _adm(t("btn_cancel"), "refunds")]]
    )
