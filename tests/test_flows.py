"""End-to-end scenarios: real handlers + real database, fake Telegram transport."""
from __future__ import annotations

import asyncio
import csv
import io
from datetime import date, timedelta

from sqlalchemy import select

from app.db import Brief, User
from app.services import running_broadcasts
from tests.conftest import link_code


async def make_brief(env, manager, client="Anna Kowalska", tone="😊 Friendly", office="Warsaw office") -> str:
    await env.send(manager, "➕ New brief link")
    await env.send(manager, client)
    await env.click(manager, tone)
    await env.click(manager, office)
    return link_code(env.last(manager).text)


async def fill_brief(env, client, code, service="Data & analytics", budget="$5k – 15k", day="Tomorrow",
                     time="Afternoon (12–17)"):
    await env.start(client, f"b_{code}")
    await env.click(client, "▶️ Start")
    await env.click(client, service)
    await env.click(client, budget)
    await env.click(client, day)
    await env.click(client, time)


async def get_brief(env, code) -> Brief:
    async with env.session_maker() as session:
        return await session.scalar(select(Brief).where(Brief.code == code))


# ---------------------------------------------------------------- happy path

async def test_full_flow_with_typed_date_and_time(env, admin):
    await env.start(admin)
    assert "You're a manager at Northwind Studio" in env.last(admin).text
    code = await make_brief(env, admin)

    anna = env.user(201, "Anna", "anna_k")
    await env.start(anna, f"b_{code}")
    greeting = env.last(anna).text
    assert "Hi Anna Kowalska!" in greeting and "Max from Northwind Studio" in greeting and "Warsaw office" in greeting

    await env.click(anna, "▶️ Start")
    assert "Step 1 of 4" in env.last(anna).text
    await env.click(anna, "Data & analytics")
    assert "Step 2 of 4" in env.last(anna).text
    await env.click(anna, "$5k – 15k")
    await env.click(anna, "📅 Pick a date")
    await env.send(anna, "31.02")
    assert "couldn't read that date" in env.last(anna).text
    future = date.today() + timedelta(days=5)
    await env.send(anna, future.strftime("%d.%m"))
    assert "Step 4 of 4" in env.last(anna).text
    await env.click(anna, "🕐 Exact time")
    await env.send(anna, "25:00")
    assert "HH:MM" in env.last(anna).text
    await env.send(anna, "15:30")
    confirm = env.last(anna).text
    assert "Please check your answers" in confirm and "15:30" in confirm and "Data &amp; analytics" in confirm

    await env.click(anna, "✅ Send")
    assert "Thank you, Anna Kowalska" in env.last(anna).text

    lead = env.last(admin).text
    assert "New lead!" in lead and "@anna_k" in lead
    assert "Data &amp; analytics" in lead and "$5k – 15k" in lead and "15:30" in lead
    assert "📞 Mark contacted" in env.last(admin).button_texts()

    brief = await get_brief(env, code)
    assert brief.status == "completed" and brief.client_id == 201
    assert brief.meet_day == f"d:{future.isoformat()}" and brief.meet_time == "t:15:30"


async def test_link_is_single_use(env, admin):
    code = await make_brief(env, admin)
    anna, bob = env.user(201, "Anna", "anna_k"), env.user(202, "Bob")
    await env.start(anna, f"b_{code}")  # opened the link once earlier: an old greeting stays in the chat
    old_greeting = env.last(anna)
    await fill_brief(env, anna, code)
    await env.click(anna, "✅ Send")

    await env.start(anna, f"b_{code}")
    assert "already sent this brief" in env.last(anna).text
    await env.start(bob, f"b_{code}")
    assert "already been completed" in env.last(bob).text
    await env.click_in(anna, old_greeting, "▶️ Start")  # stale button on an old message
    assert env.alerts(anna)[-1] == "This brief is already sent ✅"


async def test_two_clients_race_only_first_wins(env, admin):
    code = await make_brief(env, admin)
    anna, bob = env.user(201, "Anna", "anna_k"), env.user(202, "Bob", "bob_b")
    await fill_brief(env, anna, code)
    await fill_brief(env, bob, code)  # both reached the confirm screen
    await env.click(anna, "✅ Send")
    await env.click(bob, "✅ Send")
    assert env.alerts(bob)[-1] == "This brief is already sent ✅"
    leads = [t for t in env.texts(admin) if "New lead!" in t]
    assert len(leads) == 1 and "@anna_k" in leads[0]
    assert (await get_brief(env, code)).client_id == 201


async def test_double_tap_on_send_notifies_once(env, admin):
    code = await make_brief(env, admin)
    anna = env.user(201, "Anna", "anna_k")
    await fill_brief(env, anna, code)
    confirm = env.last(anna)
    await asyncio.gather(env.click_in(anna, confirm, "✅ Send"), env.click_in(anna, confirm, "✅ Send"))
    assert len([t for t in env.texts(admin) if "New lead!" in t]) == 1


# ---------------------------------------------------------------- validation and navigation

async def test_text_instead_of_buttons_reshows_step(env, admin):
    code = await make_brief(env, admin)
    anna = env.user(201, "Anna")
    await env.start(anna, f"b_{code}")
    await env.click(anna, "▶️ Start")
    await env.send(anna, "hello?")
    texts = env.texts(anna)
    assert texts[-2] == "Please tap one of the buttons 👇"
    assert "Step 1 of 4" in texts[-1] and "Data & analytics" in env.last(anna).button_texts()


async def test_back_restart_and_other_service(env, admin):
    code = await make_brief(env, admin)
    anna = env.user(201, "Anna")
    await env.start(anna, f"b_{code}")
    await env.click(anna, "▶️ Start")
    await env.click(anna, "Mobile app")
    await env.click(anna, "◀️ Back")
    assert "Step 1 of 4" in env.last(anna).text
    await env.click(anna, "✏️ Other — I'll type it")
    await env.send(anna, "x")
    assert "2 to 100 characters" in env.last(anna).text
    await env.send(anna, "Telegram   bot for HR")
    await env.click(anna, "Under $1k")
    await env.click(anna, "Tomorrow")
    await env.click(anna, "Morning (9–12)")
    assert "Telegram bot for HR" in env.last(anna).text
    await env.click(anna, "✏️ Start over")
    assert "Step 1 of 4" in env.last(anna).text


async def test_past_date_rejected(env, admin):
    code = await make_brief(env, admin)
    anna = env.user(201, "Anna")
    await env.start(anna, f"b_{code}")
    await env.click(anna, "▶️ Start")
    await env.click(anna, "Mobile app")
    await env.click(anna, "Not sure yet")
    await env.click(anna, "📅 Pick a date")
    past = date.today() - timedelta(days=400)
    await env.send(anna, past.strftime("%d.%m.%Y"))
    assert "already passed" in env.last(anna).text


async def test_invalid_and_own_links(env, admin):
    anna = env.user(201, "Anna")
    await env.start(anna, "b_doesnotexist")
    assert "not valid" in env.last(anna).text
    code = await make_brief(env, admin)
    await env.start(admin, f"b_{code}")
    assert "your own brief link" in env.last(admin).text


async def test_manager_menu_button_not_taken_as_client_name(env, admin):
    await env.send(admin, "➕ New brief link")
    await env.send(admin, "📋 My leads")
    assert "No briefs yet" in env.last(admin).text


# ---------------------------------------------------------------- languages

async def test_ukrainian_client_english_manager(env, admin):
    code = await make_brief(env, admin, client="Олена", tone="🎩 Formal", office="Kyiv office")
    olena = env.user(203, "Олена", None, lang="uk")
    await env.start(olena, f"b_{code}")
    assert "Доброго дня, Олена!" in env.last(olena).text
    await env.click(olena, "▶️ Почати")
    assert "Крок 1 з 4" in env.last(olena).text
    await env.click(olena, "Web development")
    await env.click(olena, "$1k – 5k")
    await env.click(olena, "Завтра")
    await env.click(olena, "Вечір (17–20)")
    await env.click(olena, "✅ Надіслати")
    assert "Дякуємо, Олена" in env.last(olena).text
    lead = env.last(admin).text
    assert "New lead!" in lead and "Evening (17–20)" in lead  # manager reads it in English
    assert 'href="tg://user?id=203"' in lead and "no public @username" in lead


# ---------------------------------------------------------------- manager tools

async def test_lead_status_and_list(env, admin):
    code = await make_brief(env, admin)
    anna = env.user(201, "Anna", "anna_k")
    await fill_brief(env, anna, code)
    await env.click(anna, "✅ Send")
    await env.click(admin, "📞 Mark contacted")
    assert "Status: 📞 contacted" in env.last(admin).text
    assert (await get_brief(env, code)).lead_status == "contacted"
    await env.send(admin, "📋 My leads")
    assert any(t.startswith("📞 #") for t in env.last(admin).button_texts())
    await env.click(admin, env.last(admin).button_texts()[0])
    await env.click(admin, "✅ Close lead")
    assert (await get_brief(env, code)).lead_status == "closed"
    assert "◀️ Back" in env.last(admin).button_texts()


# ---------------------------------------------------------------- admin

async def test_non_admin_has_no_admin_panel(env):
    anna = env.user(201, "Anna")
    await env.send(anna, "/admin")
    assert "didn't get that" in env.last(anna).text
    await env.send(anna, "➕ New brief link")  # not a manager either
    assert "didn't get that" in env.last(anna).text


async def test_catalog_edit_changes_client_options(env, admin):
    await env.send(admin, "/admin")
    await env.click(admin, "🗂 Catalogs")
    await env.click(admin, "🛠 Services")
    await env.click(admin, "➕ Add")
    await env.send(admin, "AI chatbots")
    assert "Added «AI chatbots»" in env.texts(admin)[-2]
    await env.click(admin, "➕ Add")
    await env.send(admin, "ai CHATBOTS")
    assert "already in the list" in env.last(admin).text
    await env.send(admin, "/cancel")
    await env.send(admin, "/admin")
    await env.click(admin, "🗂 Catalogs")
    await env.click(admin, "🛠 Services")
    await env.click(admin, "Design / UX")
    await env.click(admin, "🙈 Hide")
    assert "hidden" in env.last(admin).text
    await env.click(admin, "◀️ Back")
    await env.click(admin, "Marketing automation")
    await env.click(admin, "🗑 Delete")
    await env.click(admin, "🗑 Yes, delete")

    code = await make_brief(env, admin)
    anna = env.user(201, "Anna")
    await env.start(anna, f"b_{code}")
    await env.click(anna, "▶️ Start")
    options = env.last(anna).button_texts()
    assert "AI chatbots" in options
    assert "Design / UX" not in options and "Marketing automation" not in options


async def test_stats(env, admin):
    code = await make_brief(env, admin)
    await make_brief(env, admin, client="Second client")
    anna = env.user(201, "Anna", "anna_k")
    await fill_brief(env, anna, code)
    await env.click(anna, "✅ Send")
    await env.send(admin, "/admin")
    await env.click(admin, "📊 Stats")
    stats = env.last(admin).text
    assert "Brief links: <b>2</b>" in stats
    assert "Managers: <b>1</b>" in stats  # the admin works as a manager
    assert "Completed: <b>1</b> (50%)" in stats
    assert "Data &amp; analytics — 1" in stats and "Max — 1" in stats


async def test_broadcast_counts_blocked_users(env, admin):
    users = [env.user(300 + i, f"User{i}") for i in range(4)]
    for user in users:
        await env.start(user)
    env.api.blocked.add(users[0].id)
    await env.send(admin, "/admin")
    await env.click(admin, "📣 Broadcast")
    await env.click(admin, "Everyone (4)")  # the admin is not counted: they see the preview
    await env.send(admin, "New office opens in Lisbon next month!")
    assert "Send it to <b>4</b> users?" in env.last(admin).text
    await env.click(admin, "🚀 Send")
    await asyncio.gather(*running_broadcasts)
    done = env.last(admin).text
    assert "Delivered: <b>3</b>" in done and "Blocked the bot: 1" in done
    assert sum("Lisbon" in t for t in env.texts(admin)) == 1  # only the preview, no self-delivery
    for user in users[1:]:
        assert env.last(user).text == "New office opens in Lisbon next month!"
    async with env.session_maker() as session:
        assert (await session.get(User, users[0].id)).is_blocked is True
    await env.send(admin, "/admin")
    await env.click(admin, "📣 Broadcast")
    assert "Everyone (3)" in env.last(admin).button_texts()  # blocked user is skipped next time


async def test_team_invite_is_one_time_and_removal_works(env, admin):
    await env.send(admin, "/admin")
    await env.click(admin, "👥 Team")
    await env.click(admin, "➕ Invite a manager")
    invite = link_code(env.last(admin).text, "m_")
    sofia, eve = env.user(401, "Sofia", "sofia_n"), env.user(402, "Eve")
    await env.start(sofia, f"m_{invite}")
    assert any("Welcome to the team" in t for t in env.texts(sofia))
    await env.start(eve, f"m_{invite}")
    assert "expired or was already used" in env.last(eve).text

    code = await make_brief(env, sofia, client="Client of Sofia")
    assert (await get_brief(env, code)).manager_id == 401

    await env.send(admin, "/admin")
    await env.click(admin, "👥 Team")
    await env.click(admin, "🧑‍💼 Sofia (@sofia_n)")
    await env.click(admin, "Yes, remove")
    await env.send(sofia, "➕ New brief link")
    assert "didn't get that" in env.last(sofia).text


async def test_export_csv(env, admin):
    code = await make_brief(env, admin)
    anna = env.user(201, "Anna", "anna_k")
    await fill_brief(env, anna, code)
    await env.click(anna, "✅ Send")
    await env.send(admin, "/admin")
    await env.click(admin, "📥 Export leads (CSV)")
    filename, data = env.last(admin).document
    assert filename.startswith("leads_") and filename.endswith(".csv")
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    assert len(rows) == 1
    assert rows[0]["client_name"] == "Anna Kowalska" and rows[0]["service"] == "Data & analytics"
    assert rows[0]["meeting_time"] == "Afternoon (12–17)" and rows[0]["lead_status"] == "new"


async def test_manager_who_blocked_bot_does_not_break_submission(env, admin):
    code = await make_brief(env, admin)
    env.api.blocked.add(admin.id)
    anna = env.user(201, "Anna", "anna_k")
    await fill_brief(env, anna, code)
    await env.click(anna, "✅ Send")
    assert "Thank you" in env.last(anna).text
    assert (await get_brief(env, code)).status == "completed"
