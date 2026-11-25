"""Payments: optional paid step after the brief, card (provider) and Telegram Stars, admin revenue/CSV/refunds.

Everything runs against the fake Bot API (tests/fake_telegram.py), which enforces the same invoice rules as
Telegram (Stars: XTR, no provider token, one price item; first button = Pay; title/description/payload limits).
"""
from __future__ import annotations

import csv
import io

from sqlalchemy import func, select

from app.config import Settings
from app.db import Package, Payment
from app.utils import format_money, parse_price, parse_stars
from tests.conftest import ADMIN_ID
from tests.test_flows import fill_brief, make_brief

CARD_PKG = "Paid consultation · 25.00 USD / 250 ⭐"
CARD_BTN = "💳 Card · 25.00 USD"
STARS_BTN = "⭐ Telegram Stars · 250 ⭐"
OFFER = "💳 Reserve a paid session"


def admin_of(env):
    return env.user(ADMIN_ID, "Max", "max_northwind")


async def finished_brief(env, anna=None):
    """Admin (as manager) creates a brief, the client completes it. Returns (admin, client, code)."""
    admin = admin_of(env)
    await env.start(admin)
    code = await make_brief(env, admin)
    anna = anna or env.user(201, "Anna", "anna_k")
    await fill_brief(env, anna, code)
    await env.click(anna, "✅ Send")
    return admin, anna, code


async def open_invoice(env, anna, package=CARD_PKG, method=CARD_BTN):
    await env.click(anna, OFFER)
    await env.click(anna, package)
    if method:
        await env.click(anna, method)
    bubble = env.last(anna)
    assert bubble.invoice is not None, bubble.text
    return bubble


async def payments(env) -> list[Payment]:
    async with env.session_maker() as session:
        return list(await session.scalars(select(Payment).order_by(Payment.id)))


# ---------------------------------------------------------------- the optional step

async def test_no_paid_step_when_payments_are_off(env):
    admin, anna, _ = await finished_brief(env)
    assert "Thank you, Anna Kowalska" in env.last(anna).text
    assert env.last(anna).button_texts() == []
    assert "💳" not in env.last(anna).text


async def test_paid_step_is_offered_after_the_brief(env_pay):
    admin, anna, _ = await finished_brief(env_pay)
    bubble = env_pay.last(anna)
    assert "Thank you, Anna Kowalska" in bubble.text and "Optional" in bubble.text
    assert bubble.button_texts() == [OFFER]
    await env_pay.click(anna, OFFER)
    assert "optional" in env_pay.last(anna).text
    assert env_pay.last(anna).button_texts() == [CARD_PKG, "Project discovery · 90.00 USD / 900 ⭐", "✖️ Not now"]


async def test_not_now_dismisses_and_the_link_offers_it_again(env_pay):
    admin, anna, code = await finished_brief(env_pay)
    await env_pay.click(anna, OFFER)
    await env_pay.click(anna, "✖️ Not now")
    assert "No problem" in env_pay.last(anna).text
    assert await payments(env_pay) == []
    await env_pay.start(anna, f"b_{code}")  # opening the finished link again brings the offer back
    assert "already sent" in env_pay.last(anna).text
    assert env_pay.last(anna).button_texts() == [OFFER]


# ---------------------------------------------------------------- successful payments

async def test_card_payment_end_to_end(env_pay):
    admin, anna, code = await finished_brief(env_pay)
    invoice = await open_invoice(env_pay, anna)
    assert invoice.invoice["currency"] == "USD" and invoice.invoice["total"] == 2500
    assert invoice.invoice["payload"] == "pay:1" and invoice.invoice["provider_token"] == "TEST:provider-token"
    assert invoice.button_texts() == ["Pay 25.00 USD"]
    assert (await payments(env_pay))[0].status == "pending"

    ok, error = await env_pay.pay(anna, invoice)
    assert ok and error is None
    assert "Payment received" in env_pay.last(anna).text and "25.00 USD" in env_pay.last(anna).text
    notice = env_pay.last(admin)
    assert "Paid!" in notice.text and "Paid consultation" in notice.text and "25.00 USD" in notice.text and "#1" in notice.text

    [payment] = await payments(env_pay)
    assert payment.status == "paid" and payment.method == "provider" and payment.amount == 2500
    assert payment.telegram_charge_id and payment.provider_charge_id and payment.paid_at is not None

    await env_pay.send(admin, "📋 My leads")
    await env_pay.click(admin, env_pay.last(admin).button_texts()[0])
    assert "💳 Paid: Paid consultation — 25.00 USD" in env_pay.last(admin).text


async def test_stars_payment_end_to_end(env_pay):
    admin, anna, _ = await finished_brief(env_pay)
    invoice = await open_invoice(env_pay, anna, method=STARS_BTN)
    assert invoice.invoice["currency"] == "XTR" and invoice.invoice["total"] == 250
    assert invoice.invoice["provider_token"] == ""  # Stars never carry a provider token
    ok, _ = await env_pay.pay(anna, invoice)
    assert ok
    assert "250 ⭐" in env_pay.last(anna).text and "250 ⭐" in env_pay.last(admin).text
    [payment] = await payments(env_pay)
    assert (payment.status, payment.method, payment.currency, payment.amount) == ("paid", "stars", "XTR", 250)
    assert payment.provider_charge_id is None  # Telegram sends an empty provider id for Stars


async def _straight_to_invoice(env) -> dict:
    admin, anna, _ = await finished_brief(env)
    await env.click(anna, OFFER)
    await env.click(anna, [b for b in env.last(anna).button_texts() if b.startswith("Paid consultation")][0])
    return env.last(anna).invoice  # no «card or Stars?» question when only one method is enabled


async def test_card_only_skips_the_method_question(env_card):
    invoice = await _straight_to_invoice(env_card)
    assert invoice["currency"] == "USD" and invoice["total"] == 2500


async def test_stars_only_skips_the_method_question(env_stars):
    invoice = await _straight_to_invoice(env_stars)
    assert invoice["currency"] == "XTR" and invoice["total"] == 250


async def test_paid_brief_cannot_be_paid_twice(env_pay):
    admin, anna, code = await finished_brief(env_pay)
    await env_pay.pay(anna, await open_invoice(env_pay, anna))
    await env_pay.start(anna, f"b_{code}")
    assert "💳 Paid: Paid consultation — 25.00 USD" in env_pay.last(anna).text
    assert env_pay.last(anna).button_texts() == []


async def test_old_offer_button_after_payment_is_refused(env_pay):
    admin, anna, _ = await finished_brief(env_pay)
    offer = env_pay.last(anna)
    await env_pay.pay(anna, await open_invoice(env_pay, anna))
    await env_pay.click_in(anna, offer, CARD_BTN)  # the same message still shows the method buttons
    assert "already paid" in env_pay.alerts(anna)[-1]
    assert len(await payments(env_pay)) == 1


# ---------------------------------------------------------------- pre-checkout refusals

async def test_pre_checkout_refuses_a_package_hidden_after_the_invoice(env_pay):
    admin, anna, _ = await finished_brief(env_pay)
    invoice = await open_invoice(env_pay, anna)
    async with env_pay.session_maker() as session:
        (await session.scalar(select(Package).where(Package.title == "Paid consultation"))).is_active = False
        await session.commit()
    ok, error = await env_pay.pay(anna, invoice)
    assert not ok and "no longer available" in error
    assert "Payment received" not in env_pay.last(anna).text
    assert (await payments(env_pay))[0].status == "pending"  # nothing was charged or recorded as paid


async def test_pre_checkout_refuses_a_changed_price(env_pay):
    admin, anna, _ = await finished_brief(env_pay)
    invoice = await open_invoice(env_pay, anna)
    async with env_pay.session_maker() as session:
        (await session.scalar(select(Package).where(Package.title == "Paid consultation"))).price_cents = 3000
        await session.commit()
    ok, error = await env_pay.pay(anna, invoice)
    assert not ok and "price has changed" in error


async def test_pre_checkout_refuses_a_replaced_invoice(env_pay):
    """Choosing again cancels the previous invoice: only one open invoice per brief."""
    admin, anna, _ = await finished_brief(env_pay)
    first = await open_invoice(env_pay, anna)
    await env_pay.click(anna, STARS_BTN)  # the method buttons are still on the screen: choose again
    second = env_pay.last(anna)
    assert second.invoice["currency"] == "XTR"
    ok, error = await env_pay.pay(anna, first)
    assert not ok and "expired" in error
    assert [p.status for p in await payments(env_pay)] == ["cancelled", "pending"]
    ok, _ = await env_pay.pay(anna, second)
    assert ok
    assert [p.status for p in await payments(env_pay)] == ["cancelled", "paid"]


async def test_pre_checkout_refuses_someone_elses_invoice(env_pay):
    admin, anna, _ = await finished_brief(env_pay)
    invoice = await open_invoice(env_pay, anna)
    bob = env_pay.user(202, "Bob")
    ok, error = await env_pay.pay(bob, invoice)
    assert not ok and "expired" in error


async def test_pre_checkout_refuses_when_the_brief_is_already_paid(env_pay):
    admin, anna, _ = await finished_brief(env_pay)
    invoice = await open_invoice(env_pay, anna)
    async with env_pay.session_maker() as session:  # a second pending row, as if created in a race
        first = (await session.scalars(select(Payment))).one()
        session.add(Payment(brief_id=first.brief_id, package_id=first.package_id, user_id=first.user_id, title="x",
                            method="stars", currency="XTR", amount=250, status="paid", telegram_charge_id="other"))
        await session.commit()
    ok, error = await env_pay.pay(anna, invoice)
    assert not ok and "already paid" in error


async def test_other_users_cannot_press_the_pay_buttons(env_pay):
    admin, anna, _ = await finished_brief(env_pay)
    offer = env_pay.last(anna)
    bob = env_pay.user(202, "Bob")
    await env_pay.click_in(bob, offer, OFFER)
    assert env_pay.alerts(bob) and "expired" in env_pay.alerts(bob)[-1]
    assert await payments(env_pay) == []


# ---------------------------------------------------------------- idempotency and failures

async def test_duplicate_successful_payment_is_recorded_once(env_pay):
    admin, anna, _ = await finished_brief(env_pay)
    invoice = await open_invoice(env_pay, anna, method=STARS_BTN)
    await env_pay.pay(anna, invoice)
    thanks_before = sum("Payment received" in text for text in env_pay.texts(anna))
    notices_before = sum("Paid!" in text for text in env_pay.texts(admin))
    charge = (await payments(env_pay))[0].telegram_charge_id
    await env_pay.deliver_payment(anna, invoice.invoice, charge_id=charge)  # Telegram redelivers the same update
    assert sum("Payment received" in text for text in env_pay.texts(anna)) == thanks_before == 1
    assert sum("Paid!" in text for text in env_pay.texts(admin)) == notices_before == 1
    assert len(await payments(env_pay)) == 1


async def test_second_charge_for_an_already_paid_invoice_is_not_double_counted(env_pay):
    admin, anna, _ = await finished_brief(env_pay)
    invoice = await open_invoice(env_pay, anna)
    await env_pay.pay(anna, invoice)
    await env_pay.deliver_payment(anna, invoice.invoice)  # a different charge id for the same invoice
    assert sum("Paid!" in text for text in env_pay.texts(admin)) == 1
    async with env_pay.session_maker() as session:
        assert await session.scalar(select(func.count()).select_from(Payment).where(Payment.status == "paid")) == 1


async def test_successful_payment_for_an_unknown_invoice_does_not_crash(env_pay):
    admin, anna, _ = await finished_brief(env_pay)
    before = len(env_pay.texts(anna))
    await env_pay.deliver_payment(anna, {"currency": "XTR", "total": 5, "payload": "pay:999"})
    assert len(env_pay.texts(anna)) == before and await payments(env_pay) == []


async def test_invoice_refused_by_telegram_is_reported_and_cancelled(env_pay):
    admin, anna, _ = await finished_brief(env_pay)
    env_pay.api.fail_invoices = "PAYMENT_PROVIDER_INVALID"
    await env_pay.click(anna, OFFER)
    await env_pay.click(anna, CARD_PKG)
    await env_pay.click(anna, CARD_BTN)
    assert "not available" in env_pay.alerts(anna)[-1]
    assert [p.status for p in await payments(env_pay)] == ["cancelled"]


async def test_paying_while_payments_are_off_is_refused(env):
    admin, anna, _ = await finished_brief(env)
    from app.states import PayCb

    bubble = env.last(anna)
    await env._press(anna, bubble, PayCb(action="menu", brief_id=1).pack())
    assert "not available" in env.alerts(anna)[-1]


# ---------------------------------------------------------------- admin

async def test_admin_revenue_stats_and_csv(env_pay):
    admin, anna, _ = await finished_brief(env_pay)
    await env_pay.pay(anna, await open_invoice(env_pay, anna))

    await env_pay.send(admin, "/admin")
    await env_pay.click(admin, "📊 Stats")
    assert "Revenue" in env_pay.last(admin).text and "Card USD: <b>25.00 USD</b>" in env_pay.last(admin).text

    await env_pay.click(admin, "◀️ Back")
    await env_pay.click(admin, "💳 Payments")
    assert "Card USD: <b>25.00 USD</b>" in env_pay.last(admin).text and "1 paid, 0 refunded" in env_pay.last(admin).text
    assert "Card payments: <b>on</b>" in env_pay.last(admin).text and "Stars: <b>on</b>" in env_pay.last(admin).text

    await env_pay.click(admin, "📥 Payments (CSV)")
    name, data = env_pay.last(admin).document
    assert name.startswith("payments_") and name.endswith(".csv")
    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    assert rows[0][:4] == ["payment_id", "created_at_utc", "paid_at_utc", "brief_id"]
    assert rows[1][4] == "Anna Kowalska" and rows[1][6:11] == ["Paid consultation", "provider", "USD", "25.00", "paid"]


async def test_admin_payments_screen_when_payments_are_off(env):
    admin = admin_of(env)
    await env.send(admin, "/admin")
    await env.click(admin, "💳 Payments")
    assert "Payments are off" in env.last(admin).text and "no payments yet" in env.last(admin).text
    await env.click(admin, "📥 Payments (CSV)")
    assert "nothing to export" in env.alerts(admin)[-1]
    await env.click(admin, "◀️ Back")
    await env.click(admin, "📊 Stats")
    assert "Revenue" not in env.last(admin).text  # stats unchanged for bots without payments


async def test_admin_refunds_stars_and_the_client_is_told(env_pay):
    admin, anna, _ = await finished_brief(env_pay)
    await env_pay.pay(anna, await open_invoice(env_pay, anna, method=STARS_BTN))
    charge = (await payments(env_pay))[0].telegram_charge_id

    await env_pay.send(admin, "/admin")
    await env_pay.click(admin, "💳 Payments")
    await env_pay.click(admin, "↩️ Refund Stars")
    await env_pay.click(admin, "↩️ #1 Paid consultation · 250 ⭐")
    assert "Refund <b>250 ⭐</b>" in env_pay.last(admin).text
    await env_pay.click(admin, "↩️ Yes, refund")

    assert env_pay.api.refunded == [charge]
    assert "No Stars payments to refund" in env_pay.last(admin).text
    assert "refunded" in env_pay.texts(anna)[-1] and "250 ⭐" in env_pay.texts(anna)[-1]
    assert (await payments(env_pay))[0].status == "refunded"

    await env_pay.click(admin, "◀️ Back")
    assert "Stars: <b>0 ⭐</b> · 1 paid, 1 refunded" in env_pay.last(admin).text

    await env_pay.send(admin, "📋 My leads")
    await env_pay.click(admin, env_pay.last(admin).button_texts()[0])
    assert "↩️ Refunded: Paid consultation — 250 ⭐" in env_pay.last(admin).text


async def test_refund_failure_keeps_the_payment_paid(env_pay):
    admin, anna, _ = await finished_brief(env_pay)
    await env_pay.pay(anna, await open_invoice(env_pay, anna, method=STARS_BTN))
    env_pay.api.fail_refunds = "CHARGE_ALREADY_REFUNDED"
    await env_pay.send(admin, "/admin")
    await env_pay.click(admin, "💳 Payments")
    await env_pay.click(admin, "↩️ Refund Stars")
    await env_pay.click(admin, "↩️ #1 Paid consultation · 250 ⭐")
    await env_pay.click(admin, "↩️ Yes, refund")
    assert "did not refund" in env_pay.alerts(admin)[-1]
    assert (await payments(env_pay))[0].status == "paid"


async def test_card_payments_are_not_in_the_stars_refund_list(env_pay):
    admin, anna, _ = await finished_brief(env_pay)
    await env_pay.pay(anna, await open_invoice(env_pay, anna))
    await env_pay.send(admin, "/admin")
    await env_pay.click(admin, "💳 Payments")
    await env_pay.click(admin, "↩️ Refund Stars")
    assert "No Stars payments to refund" in env_pay.last(admin).text


async def test_admin_edits_packages(env_pay):
    admin, anna, code = await finished_brief(env_pay)
    await env_pay.send(admin, "/admin")
    await env_pay.click(admin, "💳 Payments")
    await env_pay.click(admin, "📦 Packages")
    assert env_pay.last(admin).button_texts()[:2] == ["Paid consultation", "Project discovery"]

    await env_pay.click(admin, "➕ Add")  # add a card-only package
    await env_pay.send(admin, "Quick audit")
    await env_pay.send(admin, "A 20-minute look at your funnel.")
    await env_pay.send(admin, "abc")
    assert "like 25 or 25.50" in env_pay.last(admin).text
    await env_pay.send(admin, "12,5")
    await env_pay.send(admin, "0")
    assert "Added «Quick audit»" in env_pay.texts(admin)[-2]
    async with env_pay.session_maker() as session:
        audit = await session.scalar(select(Package).where(Package.title == "Quick audit"))
        assert (audit.price_cents, audit.price_stars) == (1250, 0)

    await env_pay.click(admin, "Quick audit")  # edit prices: stars only now
    await env_pay.click(admin, "✏️ Prices")
    await env_pay.send(admin, "0")
    await env_pay.send(admin, "0")
    assert "At least one price must be above 0" in env_pay.last(admin).text
    await env_pay.send(admin, "0")
    await env_pay.send(admin, "75")
    assert "Prices updated" in env_pay.texts(admin)[-2] and "Card: not offered" in env_pay.last(admin).text

    await env_pay.start(anna, f"b_{code}")  # active packages are offered to the client
    await env_pay.click(anna, OFFER)
    assert "Quick audit · 75 ⭐" in env_pay.last(anna).button_texts()
    await env_pay.click(admin, "🙈 Hide")  # hidden packages disappear from the client's list
    await env_pay.start(anna, f"b_{code}")
    await env_pay.click(anna, OFFER)
    assert "Quick audit · 75 ⭐" not in env_pay.last(anna).button_texts()


async def test_duplicate_package_title_is_rejected(env_pay):
    admin = admin_of(env_pay)
    await env_pay.send(admin, "/admin")
    await env_pay.click(admin, "💳 Payments")
    await env_pay.click(admin, "📦 Packages")
    await env_pay.click(admin, "➕ Add")
    await env_pay.send(admin, "paid consultation")
    await env_pay.send(admin, "Same name, different case.")
    await env_pay.send(admin, "10")
    await env_pay.send(admin, "100")
    assert "already exists" in env_pay.last(admin).text


async def test_deleted_package_keeps_the_payment_snapshot(env_pay):
    admin, anna, _ = await finished_brief(env_pay)
    await env_pay.pay(anna, await open_invoice(env_pay, anna))
    await env_pay.send(admin, "/admin")
    await env_pay.click(admin, "💳 Payments")
    await env_pay.click(admin, "📦 Packages")
    await env_pay.click(admin, "Paid consultation")
    await env_pay.click(admin, "🗑 Delete")
    await env_pay.click(admin, "🗑 Yes, delete")
    [payment] = await payments(env_pay)
    assert payment.title == "Paid consultation" and payment.amount == 2500 and payment.package_id is None


async def test_the_other_package_is_still_offered_after_one_is_hidden(env_pay):
    admin, anna, _ = await finished_brief(env_pay)
    async with env_pay.session_maker() as session:
        (await session.scalar(select(Package).where(Package.title == "Paid consultation"))).is_active = False
        await session.commit()
    await env_pay.click(anna, OFFER)
    assert env_pay.last(anna).button_texts() == ["Project discovery · 90.00 USD / 900 ⭐", "✖️ Not now"]


# ---------------------------------------------------------------- helpers and settings

def test_money_and_price_parsing():
    assert format_money(2500, "USD") == "25.00 USD" and format_money(250, "XTR") == "250 ⭐"
    assert parse_price("25") == 2500 and parse_price("25,5") == 2550 and parse_price("0") == 0
    assert parse_price("-1") is None and parse_price("abc") is None and parse_price("inf") is None
    assert parse_price("nan") is None and parse_price("10001") is None and parse_price("") is None
    assert parse_stars("250") == 250 and parse_stars("0") == 0
    assert parse_stars("-5") is None and parse_stars("2.5") is None and parse_stars("999999") is None


def test_settings_never_print_the_provider_token():
    settings = Settings(bot_token="1:x", payments_provider_token="SECRET:TEST:value", payments_stars=True)
    assert "SECRET" not in repr(settings) and settings.payments_enabled and settings.card_payments
    assert not Settings(bot_token="1:x").payments_enabled
    assert Settings(bot_token="1:x", payments_stars=True).payments_enabled
