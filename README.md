# Telegram Lead-Brief Bot

A Telegram bot that replaces the "so, what do you need and when can we talk?" back-and-forth before a first sales meeting.

A manager creates a **personal brief link** for a client. The client opens it, sees a personal greeting and answers
**4 questions with buttons** (service, budget, meeting day, time). The manager gets a **lead card** right away, and an
**admin panel** inside the bot covers stats, broadcasts, editable answer options, team access and CSV export.

Python 3.10+ (tested on 3.14) · aiogram 3 · SQLAlchemy 2 (async) · SQLite or PostgreSQL · English + Ukrainian · 56 automated tests

| Manager creates a link | Client: personal greeting + step 1 | Manager gets the lead |
|---|---|---|
| ![](docs/screens/01_manager_link.png) | ![](docs/screens/02_client_step1.png) | ![](docs/screens/05_manager_lead.png) |

| Typed date/time, validated | Sent, and single-use | Same flow in Ukrainian |
|---|---|---|
| ![](docs/screens/03_client_confirm.png) | ![](docs/screens/04_client_sent.png) | ![](docs/screens/06_client_ukrainian.png) |

| Admin: stats | Admin: edit options without code | Admin: broadcast |
|---|---|---|
| ![](docs/screens/07_admin_stats.png) | ![](docs/screens/08_admin_catalog.png) | ![](docs/screens/09_admin_broadcast.png) |

Optional paid step (card and/or Telegram Stars):

| After the brief: optional offer | Invoice | Client: payment confirmed |
|---|---|---|
| ![](docs/screens/10_client_offer.png) | ![](docs/screens/11_client_invoice.png) | ![](docs/screens/12_client_paid.png) |

| Manager: "Paid!" + lead card | Admin: revenue, packages, CSV, Stars refunds |
|---|---|
| ![](docs/screens/13_manager_paid.png) | ![](docs/screens/14_admin_payments.png) |

*Screenshots are rendered from a scripted demo run of the real bot code (`scripts/demo_screens.py`); every text and
button is the bot's actual output. Names and data are fictional. The payment screens come from the same fake Bot API,
so the payment in them is simulated; see [docs/PAYMENTS.md](docs/PAYMENTS.md) for what was verified live.*

## Features

**Managers**
- `➕ New brief link`: client name → greeting style (formal / friendly / short) → meeting place → unique deep link
  with a Share button. Any number of links, each with its own ID.
- Instant lead card: all answers, a link to the client's Telegram profile (works without a public @username),
  status buttons (contacted / closed).
- `📋 My leads`: the latest briefs with their status (waiting, new, contacted, closed).

**Clients**
- Personal greeting with the client's name, the manager's name, the company and the meeting place.
- 4 steps on inline buttons with a progress bar, Back and Start over; "Other" and "Pick a date / Exact time" accept typed
  answers, which are validated (real date, not in the past, within 6 months; HH:MM, not earlier today).
- Confirmation screen before sending.
- Single-use links: a second visit shows "already sent" with the answers; another person gets a polite refusal.
  Submission is an atomic conditional `UPDATE`, so a double tap or two people answering at the same moment still produce
  exactly one lead and one notification.

**Admin panel** (`/admin`, Telegram IDs from `ADMIN_IDS`)
- Stats: users (new in 7 days, blocked the bot), managers, links created, completion rate, leads in progress, top
  services and managers.
- Broadcast to everyone / managers / clients: any message (text, photo, video), exact preview, confirmation,
  throttled sending (~20 msg/s), automatic wait on Telegram flood limits, users who blocked the bot are counted and
  skipped next time.
- Catalogs: add, hide or delete offices, services and budget ranges; changes show up for clients immediately.
  Briefs keep the labels the client actually picked.
- Team: one-time manager invite links (valid 7 days), remove managers.
- Export all briefs to CSV (opens correctly in Excel; text typed by people can't run as a spreadsheet formula).

**Optional payments** (off unless configured; details and verification status in [docs/PAYMENTS.md](docs/PAYMENTS.md))
- After sending the brief the client can reserve a paid session: a package (title, description, price) paid by card
  through a Telegram payment provider and/or with Telegram Stars.
- The manager gets a "paid" notification and the lead card shows the payment.
- Admin: packages editor, revenue (net of refunds) in stats, payments CSV, Stars refunds. Card refunds are made in the
  provider's dashboard.
- Card payments were tested live with the Smart Glocal **test** provider; Stars are covered by tests against a fake
  Bot API only. See the verification status in the doc.

**Robustness**
- Free text where a button is expected → a hint and the step is shown again; stickers/photos where text is expected →
  format hint; stale buttons on old messages → a short alert instead of a broken state.
- English by default; `BOT_LANGUAGE=uk` switches everyone to Ukrainian, `BOT_LANGUAGE=auto` follows each user's
  Telegram language. Answers are stored language-neutral, so in auto mode a Ukrainian-speaking client and an
  English-speaking manager each read them in their own language.
- A global error handler logs the traceback and tells the user to retry instead of going silent.

## Run

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                               # set BOT_TOKEN (from @BotFather) and ADMIN_IDS
python -m app
```

SQLite is used by default (`data/bot.db`). For PostgreSQL set
`DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname`; tables are created on first start.

Docker (bot + PostgreSQL): `docker compose up -d --build` with `.env` filled in.

To try both roles with a single Telegram account, set `ALLOW_SELF_BRIEF=true` (demo only) and open your own link.

Payments (optional) are configured in `.env`: `PAYMENTS_PROVIDER_TOKEN` (from @BotFather → Payments; a token with
`:TEST:` gives test invoices), `PAYMENTS_STARS=on` for Telegram Stars, `PAYMENTS_CURRENCY=USD`. Run only one instance
per bot token.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q                                    # 56 tests, SQLite
TEST_DATABASE_URL=postgresql+asyncpg://... pytest -q   # same suite on PostgreSQL
python scripts/test_postgres.py              # same suite on a throw-away embedded PostgreSQL, no Docker
                                             # (needs: pip install pixeltable-pgserver)
```

End-to-end tests drive the real dispatcher, handlers, middlewares and database through an in-process fake of the
Telegram Bot API (`tests/fake_telegram.py`) that keeps every chat's messages, edits and buttons, so a test "taps"
buttons exactly as a user would. Covered: the full manager → client → lead flow, typed-input validation, Back / Start
over, single-use links, two clients racing for the same link, double tap on Send, Ukrainian client with English
manager, lead statuses, catalog editing, stats, broadcast with a blocked user, one-time team invites, CSV export,
and a manager who blocked the bot. The fake also enforces Telegram's invoice rules and models Stars charges and
refunds, so the payment flow (card and Stars, pre-checkout, repeated delivery, refunds, revenue, CSV) is tested the same way.

## Structure

```
app/
  main.py            entry point, dispatcher wiring, bot commands
  config.py          settings from environment / .env
  db.py              SQLAlchemy models: users, catalog_items, briefs, manager_invites, packages, payments
  repo.py            all database access (handlers never build SQL)
  middlewares.py     per-update DB session, user upsert, language; role filters
  handlers/          start (deep links), manager, client, admin, admin_payments, payments, fallback + error handler
  payments.py        invoices, pre-checkout checks, Stars refunds
  keyboards.py       inline / reply keyboards
  views.py           summaries and lead cards, day/time formatting
  services.py        lead notification, throttled broadcast, CSV exports
  texts.py           all texts, English + Ukrainian (payment texts in texts_payments.py)
docs/PAYMENTS.md     how payments work, what was verified live and what only in tests
tests/               fake Telegram API, end-to-end and unit tests
scripts/             demo run that renders the screenshots; test_postgres.py runs the tests on embedded PostgreSQL
```

Conversation state uses aiogram's in-memory FSM storage; all briefs and leads are in the database, so a restart only
asks a client who is mid-brief to open the link again. For several bot instances, swap in `RedisStorage`.
