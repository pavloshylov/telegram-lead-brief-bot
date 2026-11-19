"""Renders README / portfolio screenshots from a scripted demo run.

The bot runs its real handlers and database against the in-process fake Telegram API used by the
tests; every message and button on the screenshots is the bot's actual output. Names are fictional.

Usage: python scripts/demo_screens.py  ->  docs/screens/*.png (1170x2532, phone-sized)
Needs Google Chrome (headless) for the PNG step.
"""
from __future__ import annotations

import asyncio
import copy
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import repo  # noqa: E402
from app.config import Settings  # noqa: E402
from app.db import init_db, make_engine, make_session_maker  # noqa: E402
from app.main import build_dispatcher  # noqa: E402
from app.services import running_broadcasts  # noqa: E402
from tests.fake_telegram import Harness, FakeTelegram  # noqa: E402

OUT = ROOT / "docs" / "screens"
CHROME = os.environ.get("CHROME", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
ADMIN_ID = 100


@dataclass
class Snapshot:
    name: str
    title: str
    bubbles: list
    reply_keyboard: list[list[str]] | None
    alert: str | None = None


def snap(env: Harness, user, name: str, title: str, last_n: int | None = None, alert: str | None = None) -> Snapshot:
    chat = env.chat(user)
    bubbles = copy.deepcopy(chat.bubbles[-last_n:] if last_n else chat.bubbles)
    kb = [[b.text for b in row] for row in chat.reply_keyboard.keyboard] if chat.reply_keyboard else None
    return Snapshot(name, title, bubbles, kb, alert)


async def make_brief(env, manager, client, tone, office):
    await env.send(manager, "➕ New brief link")
    await env.send(manager, client)
    await env.click(manager, tone)
    await env.click(manager, office)
    return re.search(r"start=b_([A-Za-z0-9_-]+)", env.last(manager).text).group(1)


async def answer(env, client, code, service, budget, day, time, start="▶️ Start", send="✅ Send"):
    await env.start(client, f"b_{code}")
    await env.click(client, start)
    await env.click(client, service)
    await env.click(client, budget)
    await env.click(client, day)
    await env.click(client, time)
    await env.click(client, send)


async def scenario(env: Harness) -> list[Snapshot]:
    shots: list[Snapshot] = []
    max_ = env.user(ADMIN_ID, "Max", "max_northwind")
    anna = env.user(201, "Anna", "anna_k")

    # 1. Manager creates a personal link
    await env.start(max_)
    code = await make_brief(env, max_, "Anna Kowalska", "😊 Friendly", "Warsaw office")
    shots.append(snap(env, max_, "01_manager_link", "Manager creates a personal brief link"))

    # 2–4. Client answers
    await env.start(anna, f"b_{code}")
    await env.click(anna, "▶️ Start")
    shots.append(snap(env, anna, "02_client_step1", "Client opens the link: personal greeting + step 1"))
    await env.click(anna, "Data & analytics")
    await env.click(anna, "$5k – 15k")
    await env.click(anna, "📅 Pick a date")
    meet = date.today() + timedelta(days=6)
    await env.send(anna, meet.strftime("%d.%m"))
    await env.click(anna, "🕐 Exact time")
    await env.send(anna, "15:30")
    shots.append(snap(env, anna, "03_client_confirm", "Typed date and time are validated, then confirmed", last_n=5))
    await env.click(anna, "✅ Send")
    await env.start(anna, f"b_{code}")
    shots.append(snap(env, anna, "04_client_sent", "Sent, and the link can't be answered twice", last_n=4))

    # 5. Manager gets the lead card
    shots.append(snap(env, max_, "05_manager_lead", "Manager instantly gets the lead card", last_n=1))

    # Some more activity for the admin screens
    sofia = env.user(202, "Sofia", "sofia_n")
    await env.send(max_, "/admin")
    await env.click(max_, "👥 Team")
    await env.click(max_, "➕ Invite a manager")
    invite = re.search(r"start=m_([A-Za-z0-9_-]+)", env.last(max_).text).group(1)
    await env.start(sofia, f"m_{invite}")
    clients = [
        (env.user(301, "Daniel", "dan_w"), "Web development", "$15k+", "Tomorrow", "Morning (9–12)", "en"),
        (env.user(302, "Olena", None, "uk"), "Data & analytics", "$1k – 5k", "Завтра", "Вечір (17–20)", "uk"),
        (env.user(303, "Marta", "marta_s"), "Data & analytics", "$5k – 15k", "Next week", "Afternoon (12–17)", "en"),
        (env.user(304, "Tom", "tom_r"), "Mobile app", "Not sure yet", "Tomorrow", "Afternoon (12–17)", "en"),
    ]
    for i, (client, service, budget, day, time, lang) in enumerate(clients):
        manager = sofia if i % 2 else max_
        code_i = await make_brief(env, manager, client.first_name, "🎩 Formal", "Online call")
        if lang == "uk":
            await answer(env, client, code_i, service, budget, day, time, start="▶️ Почати", send="✅ Надіслати")
        else:
            await answer(env, client, code_i, service, budget, day, time)
    await env.click(max_, "📞 Mark contacted")
    await env.click(sofia, "✅ Close lead")
    await make_brief(env, sofia, "Pending client", "⚡ Short & direct", "Berlin office")
    await env.send(env.user(305, "Ivan", "ivan_p"), "/start")

    # 6. Ukrainian client view
    olena2 = env.user(306, "Олена", None, "uk")
    code_uk = await make_brief(env, max_, "Олена", "🎩 Formal", "Kyiv office")
    await env.start(olena2, f"b_{code_uk}")
    await env.click(olena2, "▶️ Почати")
    await env.click(olena2, "Web development")
    shots.append(snap(env, olena2, "06_client_ukrainian", "Same flow in Ukrainian (from Telegram language)"))

    # 7. Admin: stats
    await env.send(max_, "/admin")
    await env.click(max_, "📊 Stats")
    shots.append(snap(env, max_, "07_admin_stats", "Admin panel: stats", last_n=2))

    # 8. Admin: catalog editing
    await env.send(max_, "/admin")
    await env.click(max_, "🗂 Catalogs")
    await env.click(max_, "🛠 Services")
    await env.click(max_, "Design / UX")
    await env.click(max_, "🙈 Hide")
    await env.click(max_, "◀️ Back")
    await env.click(max_, "➕ Add")
    await env.send(max_, "AI chatbots")
    shots.append(snap(env, max_, "08_admin_catalog", "Admin edits answer options without code", last_n=5))

    # 9. Admin: broadcast with a blocked user
    env.api.blocked.add(305)
    await env.send(max_, "/admin")
    await env.click(max_, "📣 Broadcast")
    await env.click(max_, next(b for b in env.last(max_).button_texts() if b.startswith("Everyone")))
    await env.send(max_, "📍 Our Lisbon office opens on 1 December — meetings there can be booked from today.")
    await env.click(max_, "🚀 Send")
    await asyncio.gather(*running_broadcasts)
    shots.append(snap(env, max_, "09_admin_broadcast", "Broadcast with preview, throttling and blocked-user handling", last_n=5))
    return shots


# ---------------------------------------------------------------- rendering

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 390px; height: 844px; overflow: hidden; font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif; }
.phone { width: 390px; height: 844px; display: flex; flex-direction: column; background: #8aa982;
  background: linear-gradient(160deg, #c8d9a8 0%, #9fc09a 45%, #86b2a0 100%); }
.status { height: 44px; background: #fff; display: flex; align-items: center; justify-content: space-between; padding: 0 22px;
  font-size: 15px; font-weight: 600; color: #000; }
.header { height: 56px; background: #fff; border-bottom: 1px solid #e3e3e3; display: flex; align-items: center; gap: 10px; padding: 0 12px; }
.header .back { color: #2f8de4; font-size: 26px; width: 18px; }
.avatar { width: 38px; height: 38px; border-radius: 50%; background: linear-gradient(135deg, #3d6fd8, #23a3c9);
  color: #fff; font-weight: 700; display: flex; align-items: center; justify-content: center; font-size: 15px; }
.header .name { font-size: 16px; font-weight: 600; color: #000; }
.header .sub { font-size: 13px; color: #8e8e93; }
.chat { flex: 1; overflow: hidden; display: flex; flex-direction: column; justify-content: flex-end; padding: 8px 8px 6px; gap: 6px; }
.row { display: flex; flex-direction: column; }
.row.user { align-items: flex-end; }
.row.bot { align-items: flex-start; }
.bubble { max-width: 82%; padding: 7px 10px 6px; border-radius: 16px; font-size: 15px; line-height: 1.33; color: #000;
  box-shadow: 0 1px 1px rgba(0,0,0,.12); word-wrap: break-word; overflow-wrap: anywhere; }
.row.bot .bubble { background: #fff; border-bottom-left-radius: 5px; }
.row.user .bubble { background: #e1fec6; border-bottom-right-radius: 5px; }
.bubble a { color: #2f8de4; text-decoration: none; }
.bubble .meta { float: right; font-size: 11px; color: #8e8e93; margin: 6px 0 0 10px; }
.row.user .bubble .meta { color: #5fa34f; }
.doc { display: flex; gap: 10px; align-items: center; margin-bottom: 4px; }
.doc .ico { width: 40px; height: 40px; border-radius: 50%; background: #3f9be3; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 18px; }
.doc .fn { font-weight: 600; font-size: 14px; }
.ikb { max-width: 82%; width: 82%; margin-top: 3px; display: flex; flex-direction: column; gap: 3px; }
.ikb .r { display: flex; gap: 3px; }
.ikb .b { flex: 1; background: rgba(40, 70, 50, .32); color: #fff; font-size: 14px; font-weight: 500; text-align: center;
  padding: 9px 6px; border-radius: 9px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ikb .b.url::after { content: " ↗"; font-size: 11px; opacity: .85; }
.input { height: 50px; background: #fff; border-top: 1px solid #e3e3e3; display: flex; align-items: center; gap: 10px; padding: 0 12px; color: #8e8e93; font-size: 16px; }
.input .field { flex: 1; height: 34px; border: 1px solid #dcdcdc; border-radius: 17px; padding: 0 14px; display: flex; align-items: center; }
.rkb { background: #d4d7dc; padding: 6px 4px 10px; display: flex; flex-direction: column; gap: 6px; }
.rkb .r { display: flex; gap: 6px; }
.rkb .b { flex: 1; background: #fff; border-radius: 7px; padding: 11px 4px; text-align: center; font-size: 15px; color: #000;
  box-shadow: 0 1px 0 rgba(0,0,0,.25); }
.alert { position: absolute; left: 50%; top: 42%; transform: translateX(-50%); background: rgba(30,30,30,.86); color: #fff;
  font-size: 15px; padding: 12px 18px; border-radius: 12px; max-width: 300px; text-align: center; }
"""


def render_html(shot: Snapshot, clock: datetime) -> str:
    rows = []
    t = clock
    for bubble in shot.bubbles:
        t += timedelta(minutes=1) if bubble.sender == "user" else timedelta(seconds=20)
        meta = ("edited " if bubble.edited else "") + t.strftime("%H:%M")
        if bubble.sender == "user":
            text = "/start" if bubble.text.startswith("/start ") else bubble.text  # Telegram hides the payload
            body = html.escape(text).replace("\n", "<br>")
        else:
            # Telegram auto-links bare URLs
            body = re.sub(r'(?<!href=")(https://t\.me/\S+)', r'<a href="\1">\1</a>', bubble.text).replace("\n", "<br>")
        doc = ""
        if bubble.document:
            size = len(bubble.document[1])
            doc = f'<div class="doc"><div class="ico">⬇</div><div><div class="fn">{html.escape(bubble.document[0])}</div><div style="font-size:12px;color:#8e8e93">{size / 1024:.1f} KB</div></div></div>'
        kb = ""
        if bubble.markup:
            kb_rows = []
            for row in bubble.markup.inline_keyboard:
                cells = "".join(
                    f'<div class="b{" url" if b.url else ""}">{html.escape(b.text)}</div>' for b in row
                )
                kb_rows.append(f'<div class="r">{cells}</div>')
            kb = f'<div class="ikb">{"".join(kb_rows)}</div>'
        rows.append(
            f'<div class="row {bubble.sender}"><div class="bubble">{doc}{body}<span class="meta">{meta}</span></div>{kb}</div>'
        )
    bottom = '<div class="input"><span style="font-size:22px">📎</span><div class="field">Message</div><span style="font-size:20px">🎤</span></div>'
    if shot.reply_keyboard:
        rk = "".join(
            '<div class="r">' + "".join(f'<div class="b">{html.escape(x)}</div>' for x in row) + "</div>"
            for row in shot.reply_keyboard
        )
        bottom += f'<div class="rkb">{rk}</div>'
    alert = f'<div class="alert">{html.escape(shot.alert)}</div>' if shot.alert else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="phone">
  <div class="status"><span>{t.strftime("%H:%M")}</span><span>▮▮▮ ◔</span></div>
  <div class="header"><span class="back">‹</span><div class="avatar">NB</div>
    <div><div class="name">Northwind Brief</div><div class="sub">bot</div></div></div>
  <div class="chat">{"".join(rows)}</div>
  {bottom}
</div>{alert}</body></html>"""


def screenshot(html_path: Path, png_path: Path, profile: Path) -> None:
    subprocess.run(
        [
            CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={profile}",
            "--force-device-scale-factor=3", "--window-size=390,844", f"--screenshot={png_path}",
            html_path.as_uri(),
        ],
        check=True, capture_output=True, timeout=60,
    )


async def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="brief_demo_"))
    engine = make_engine(f"sqlite+aiosqlite:///{(tmp / 'demo.db').as_posix()}")
    await init_db(engine)
    session_maker = make_session_maker(engine)
    async with session_maker() as session:
        await repo.seed_defaults(session)
        await session.commit()
    settings = Settings(bot_token="42:DEMO", admin_ids=frozenset({ADMIN_ID}), company_name="Northwind Studio",
                        broadcast_rate=20)
    env = Harness(build_dispatcher(settings, session_maker), FakeTelegram())
    shots = await scenario(env)
    await engine.dispose()

    OUT.mkdir(parents=True, exist_ok=True)
    html_dir = tmp / "html"
    html_dir.mkdir()
    clock = datetime.now().replace(hour=10, minute=12, second=0, microsecond=0)
    for shot in shots:
        page = html_dir / f"{shot.name}.html"
        page.write_text(render_html(shot, clock), encoding="utf-8")
        screenshot(page, OUT / f"{shot.name}.png", tmp / "chrome")
        print(f"{shot.name}.png  {shot.title}")
    (OUT / "captions.txt").write_text("\n".join(f"{s.name}: {s.title}" for s in shots) + "\n", encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
