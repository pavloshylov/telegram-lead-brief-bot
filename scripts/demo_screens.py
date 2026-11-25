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
from app.handlers import routers  # noqa: E402
from app.main import build_dispatcher  # noqa: E402
from app.services import running_broadcasts  # noqa: E402
from tests.fake_telegram import Harness, FakeTelegram  # noqa: E402

OUT = ROOT / "docs" / "screens"
# Android Telegram look (default "Day" theme): Roboto + Noto Color Emoji, blue app bar, flat SVG icons.
FONTS = ('<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&family=Noto+Color+Emoji&display=block" '
         'rel="stylesheet">')
_ICON = ('<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" '
         'stroke-linecap="round" stroke-linejoin="round">{d}</svg>')
ICON_BACK = _ICON.format(s=24, c="#fff", d='<path d="M20 12H5"/><path d="M11 5l-7 7 7 7"/>')
ICON_MORE = ('<svg width="24" height="24" viewBox="0 0 24 24" fill="#fff"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/>'
             '<circle cx="12" cy="19" r="2"/></svg>')
ICON_SMILE = _ICON.format(s=26, c="#8a959e", d='<circle cx="12" cy="12" r="9.5"/><path d="M8 14.5a5 5 0 0 0 8 0"/>'
                          '<path d="M9 9.5h.01M15 9.5h.01" stroke-width="3"/>')
ICON_CLIP = _ICON.format(s=26, c="#8a959e", d='<path d="M21 11.5l-8.6 8.6a5.5 5.5 0 0 1-7.8-7.8l8.6-8.6a3.7 3.7 0 0 1 5.2 5.2'
                         'l-8.6 8.6a1.8 1.8 0 0 1-2.6-2.6l7.9-7.9"/>')
ICON_MIC = _ICON.format(s=26, c="#8a959e", d='<rect x="9" y="2.5" width="6" height="11.5" rx="3"/>'
                        '<path d="M5.5 10.5a6.5 6.5 0 0 0 13 0"/><path d="M12 17v4"/>')
STATUS_ICONS = (
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="#fff"><path d="M12 21l11.5-14.3A18.6 18.6 0 0 0 12 2.6 18.6 18.6 0 0 0 .5 6.7z"/></svg>'
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="#fff"><path d="M2 22h20V2z"/></svg>'
    '<svg width="9" height="15" viewBox="0 0 12 20" fill="#fff"><rect x="3.5" y="0" width="5" height="2" rx="1"/>'
    '<rect x="0" y="2" width="12" height="18" rx="2"/></svg>')
CHECKS = ('<svg width="16" height="10" viewBox="0 0 16 10" fill="none" stroke="#4fae4e" stroke-width="1.6" stroke-linecap="round" '
          'stroke-linejoin="round"><path d="M1 5.5l3 3 6-7"/><path d="M7 8.5l1 0 6-7"/></svg>')
# Chat wallpaper: own doodle tile (simple line icons, low opacity) over the green gradient, like Telegram's default.
_DOODLES = [
    # (x, y, rotate, path in a 24x24 box)
    (8, 10, -15, "M12 3l2.6 5.6 6 .6-4.5 4 1.3 6-5.4-3.1-5.4 3.1 1.3-6-4.5-4 6-.6z"),            # star
    (70, 6, 10, "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"),          # heart
    (132, 14, -8, "M5 8h11v6a5 5 0 0 1-5 5h-1a5 5 0 0 1-5-5zM16 10h2a2 2 0 0 1 0 4h-2M8 3v3M11 3v3"),  # cup
    (190, 4, 20, "M4 20c8 0 16-6 16-16C10 4 4 10 4 20zM4 20l9-9"),                               # leaf
    (30, 66, 0, "M3 12a9 9 0 1 0 18 0 9 9 0 1 0-18 0M12 7v5l3 2"),                                # clock
    (98, 60, -20, "M4 6h16v10H8l-4 4z"),                                                          # chat bubble
    (160, 70, 15, "M12 3v18M3 12h18M6 6l12 12M18 6L6 18"),                                        # sparkle
    (214, 58, -10, "M6 3h12v18l-6-4-6 4z"),                                                       # bookmark
    (6, 128, 25, "M3 17l6-6 4 4 8-8M15 7h6v6"),                                                   # chart
    (64, 118, -5, "M12 2a6 6 0 0 1 6 6c0 4.5-6 12-6 12S6 12.5 6 8a6 6 0 0 1 6-6zM12 6a2 2 0 1 0 0 4 2 2 0 1 0 0-4"),  # pin
    (126, 130, 12, "M3 7h18v12H3zM8 7V5h8v2"),                                                    # bag
    (188, 120, -18, "M9 18V6l10-2v12M9 18a3 3 0 1 1-6 0 3 3 0 1 1 6 0M19 16a3 3 0 1 1-6 0 3 3 0 1 1 6 0"),  # note
    (36, 184, 8, "M2 12c3-4 6-4 10 0s7 4 10 0"),                                                  # wave
    (100, 186, -12, "M4 4h16v12H4zM2 20h20"),                                                     # laptop
    (160, 182, 18, "M12 2l3 7h7l-5.5 4.5L18 21l-6-4-6 4 1.5-7.5L2 9h7z"),                         # star 2
    (216, 178, -6, "M12 4a8 8 0 1 0 0 16 8 8 0 1 0 0-16M9 10h.01M15 10h.01M8.5 14.5a4.5 4.5 0 0 0 7 0"),  # smile
]
_TILE = ('<svg xmlns="http://www.w3.org/2000/svg" width="248" height="236" viewBox="0 0 248 236">'
         + "".join(f'<g transform="translate({x} {y}) rotate({r} 12 12) scale(1.05)" fill="none" stroke="#2f5a2a" '
                   f'stroke-opacity=".16" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="{d}"/></g>'
                   for x, y, r, d in _DOODLES)
         + "</svg>")
import base64 as _b64  # noqa: E402
WALLPAPER = "data:image/svg+xml;base64," + _b64.b64encode(_TILE.encode()).decode()
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


async def payments_scenario(env: Harness) -> list[Snapshot]:
    """Optional paid step. Runs on the fake Bot API, so the payment itself is simulated (not a real charge)."""
    shots: list[Snapshot] = []
    max_ = env.user(ADMIN_ID, "Max", "max_northwind")
    anna = env.user(201, "Anna", "anna_k")
    await env.start(max_)
    code = await make_brief(env, max_, "Anna Kowalska", "😊 Friendly", "Warsaw office")
    await answer(env, anna, code, "Data & analytics", "$5k – 15k", "Tomorrow", "Afternoon (12–17)")
    shots.append(snap(env, anna, "10_client_offer", "After the brief: an optional paid session", last_n=1))

    await env.click(anna, "💳 Reserve a paid session")
    await env.click(anna, "Paid consultation · 25.00 USD / 250 ⭐")
    await env.click(anna, "💳 Card · 25.00 USD")
    invoice = env.last(anna)
    shots.append(snap(env, anna, "11_client_invoice", "Invoice: pay by card or with Telegram Stars", last_n=3))

    await env.pay(anna, invoice)
    shots.append(snap(env, anna, "12_client_paid", "Payment confirmed to the client", last_n=2))
    shots.append(snap(env, max_, "13_manager_paid", "Manager is notified, the lead card shows the payment", last_n=2))

    await env.send(max_, "/admin")
    await env.click(max_, "💳 Payments")
    shots.append(snap(env, max_, "14_admin_payments", "Admin: revenue, packages, payments CSV, Stars refunds", last_n=2))
    return shots


# ---------------------------------------------------------------- rendering

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 390px; height: 844px; overflow: hidden; font-family: Roboto, "Noto Color Emoji", sans-serif;
  -webkit-font-smoothing: antialiased; }
.phone { width: 390px; height: 844px; display: flex; flex-direction: column;
  background: url("{WALLPAPER}") repeat, linear-gradient(165deg, #d5e3b0 0%, #a9cba0 40%, #8fbcaa 75%, #7fb0ac 100%);
  background-size: 196px 186px, auto; }
.status { height: 26px; background: #436d8c; display: flex; align-items: center; justify-content: space-between;
  padding: 0 14px 0 16px; font-size: 13px; font-weight: 500; color: #fff; }
.status .icons { display: flex; gap: 5px; align-items: center; }
.header { height: 56px; background: #517da2; display: flex; align-items: center; gap: 14px; padding: 0 12px 0 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,.18); z-index: 1; }
.header .back, .header .more { display: flex; align-items: center; }
.header .more { margin-left: auto; }
.avatar { width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(180deg, #72d5fd, #2a9ef1);
  color: #fff; font-weight: 500; display: flex; align-items: center; justify-content: center; font-size: 16px; }
.header .name { font-size: 18px; font-weight: 500; color: #fff; line-height: 1.2; }
.header .sub { font-size: 14px; color: #d7e4ef; }
.chat { flex: 1; overflow: hidden; display: flex; flex-direction: column; justify-content: flex-end; padding: 8px 8px 8px; gap: 5px; }
.row { display: flex; flex-direction: column; }
.row.user { align-items: flex-end; }
.row.bot { align-items: flex-start; }
.bubble { max-width: 84%; padding: 6px 9px 6px 10px; border-radius: 12px; font-size: 15.5px; line-height: 1.32; color: #000;
  box-shadow: 0 1px 1.5px rgba(0,0,0,.16); word-wrap: break-word; overflow-wrap: anywhere; }
.row.bot .bubble { background: #fff; border-bottom-left-radius: 4px; }
.row.user .bubble { background: #effedd; border-bottom-right-radius: 4px; }
.bubble a { color: #2678b6; text-decoration: none; }
.bubble .meta { float: right; font-size: 12px; color: #a1aab3; margin: 7px 0 -2px 10px; display: inline-flex; gap: 3px; align-items: center; }
.row.user .bubble .meta { color: #6aaf5e; }
.doc { display: flex; gap: 10px; align-items: center; margin-bottom: 4px; }
.doc .ico { width: 44px; height: 44px; border-radius: 50%; background: #4fa4e8; color: #fff; display: flex; align-items: center;
  justify-content: center; font-size: 20px; }
.doc .fn { font-weight: 500; font-size: 14.5px; }
.ikb { max-width: 84%; width: 84%; margin-top: 3px; display: flex; flex-direction: column; gap: 3px; }
.ikb .r { display: flex; gap: 3px; }
.ikb .b { flex: 1; background: rgba(40, 72, 60, .30); color: #fff; font-size: 14.5px; font-weight: 500; text-align: center;
  padding: 10px 6px; border-radius: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; position: relative; }
.ikb .b.url::after { content: ""; position: absolute; top: 5px; right: 5px; width: 6px; height: 6px;
  border-top: 1.5px solid #fff; border-right: 1.5px solid #fff; }
.input { height: 52px; background: #fff; display: flex; align-items: center; gap: 12px; padding: 0 12px;
  box-shadow: 0 -1px 2px rgba(0,0,0,.08); }
.input .field { flex: 1; color: #a3abb3; font-size: 17px; }
.rkb { background: #f0f2f4; padding: 6px 6px 10px; display: flex; flex-direction: column; gap: 6px; border-top: 1px solid #e1e4e7; }
.rkb .r { display: flex; gap: 6px; }
.rkb .b { flex: 1; background: #fff; border-radius: 6px; padding: 12px 4px; text-align: center; font-size: 15px; color: #222;
  box-shadow: 0 1px 1px rgba(0,0,0,.18); }
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
            f'<div class="row {bubble.sender}"><div class="bubble">{doc}{body}<span class="meta">{meta}{CHECKS if bubble.sender == "user" else ""}</span></div>{kb}</div>'
        )
    bottom = f'<div class="input">{ICON_SMILE}<div class="field">Message</div>{ICON_CLIP}{ICON_MIC}</div>'
    if shot.reply_keyboard:
        rk = "".join(
            '<div class="r">' + "".join(f'<div class="b">{html.escape(x)}</div>' for x in row) + "</div>"
            for row in shot.reply_keyboard
        )
        bottom += f'<div class="rkb">{rk}</div>'
    alert = f'<div class="alert">{html.escape(shot.alert)}</div>' if shot.alert else ""
    return f"""<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>{CSS.replace("{WALLPAPER}", WALLPAPER)}</style></head><body>
<div class="phone">
  <div class="status"><span>{t.strftime("%H:%M")}</span><span class="icons">{STATUS_ICONS}</span></div>
  <div class="header"><span class="back">{ICON_BACK}</span><div class="avatar">NB</div>
    <div><div class="name">Northwind Brief</div><div class="sub">bot</div></div><span class="more">{ICON_MORE}</span></div>
  <div class="chat">{"".join(rows)}</div>
  {bottom}
</div>{alert}</body></html>"""


def screenshot(html_path: Path, png_path: Path, profile: Path) -> None:
    subprocess.run(
        [
            CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={profile}",
            "--force-device-scale-factor=3", "--window-size=390,844", "--virtual-time-budget=8000",
            f"--screenshot={png_path}",
            html_path.as_uri(),
        ],
        check=True, capture_output=True, timeout=60,
    )


async def run_scenario(tmp: Path, name: str, scenario_fn, **extra) -> list[Snapshot]:
    engine = make_engine(f"sqlite+aiosqlite:///{(tmp / f'{name}.db').as_posix()}")
    await init_db(engine)
    session_maker = make_session_maker(engine)
    async with session_maker() as session:
        await repo.seed_defaults(session)
        await session.commit()
    settings = Settings(bot_token="42:DEMO", admin_ids=frozenset({ADMIN_ID}), company_name="Northwind Studio",
                        broadcast_rate=20, language="auto", **extra)  # auto: to show the Ukrainian screen too
    env = Harness(build_dispatcher(settings, session_maker), FakeTelegram())
    env.settings = settings
    try:
        return await scenario_fn(env)
    finally:
        await engine.dispose()
        for router in routers():  # module-level routers belong to one dispatcher at a time
            router._parent_router = None


async def main() -> None:
    """`python scripts/demo_screens.py` renders everything; `... payments` only the payment screens."""
    only_payments = "payments" in sys.argv[1:]
    tmp = Path(tempfile.mkdtemp(prefix="brief_demo_"))
    shots: list[Snapshot] = []
    if not only_payments:
        shots += await run_scenario(tmp, "demo", scenario)
    shots += await run_scenario(
        tmp, "demo_payments", payments_scenario, payments_provider_token="TEST:demo-provider", payments_stars=True
    )

    OUT.mkdir(parents=True, exist_ok=True)
    html_dir = tmp / "html"
    html_dir.mkdir()
    clock = datetime.now().replace(hour=10, minute=12, second=0, microsecond=0)
    for shot in shots:
        page = html_dir / f"{shot.name}.html"
        page.write_text(render_html(shot, clock), encoding="utf-8")
        screenshot(page, OUT / f"{shot.name}.png", tmp / "chrome")
        print(f"{shot.name}.png  {shot.title}")
    captions = OUT / "captions.txt"
    known = {}
    if captions.exists():
        for line in captions.read_text(encoding="utf-8").splitlines():
            name, _, title = line.partition(": ")
            known[name] = title
    known.update({s.name: s.title for s in shots})
    captions.write_text("".join(f"{n}: {known[n]}\n" for n in sorted(known)), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
