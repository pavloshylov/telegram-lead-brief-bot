# Payments

An optional paid step after the brief: once a client has sent their answers, the bot offers to **reserve a paid session**
(a package such as a consultation or a discovery call). It is off unless payments are configured, and there is no extra
menu entry for managers: the offer only appears to the client, right after the brief (or when they reopen their finished
link).

Two payment modes can be switched on independently:

| Mode | What the client pays with | Needs |
|---|---|---|
| **Card (provider)** | Any card, through a Telegram payment provider | `PAYMENTS_PROVIDER_TOKEN` from @BotFather → Payments |
| **Telegram Stars** | Stars (currency `XTR`) | `PAYMENTS_STARS=on`, no provider needed |

If both are on, the client picks the method. With neither configured the bot behaves exactly as before.

## Configuration (`.env`)

```
PAYMENTS_PROVIDER_TOKEN=      # token from BotFather → Payments; leave empty to turn card payments off
PAYMENTS_STARS=off            # on = accept Telegram Stars
PAYMENTS_CURRENCY=USD         # currency of card prices
```

The token is read from the environment only; it is never logged and is hidden from the settings object's `repr`.

## What the bot does

- **Packages** (admin → 💳 Payments → 📦 Packages): title, description, a card price and a Stars price. Setting a price
  to `0` means the package is not offered in that mode. Packages can be hidden or deleted. Two defaults are seeded on
  first start (Paid consultation 25.00 USD / 250 ⭐, Project discovery 90.00 USD / 900 ⭐).
- **Invoice**: the client taps a package, then the Pay button. The invoice payload is `pay:<payment id>`.
- **Pre-checkout**: the bot answers every `pre_checkout_query` within Telegram's 10 s window, and refuses a payment whose
  package was removed, whose payment record is gone or that is already paid.
- **Successful payment**: the payment is marked paid and **committed first**, then the client gets a confirmation and the
  manager gets a notification. `telegram_payment_charge_id` is unique, so a repeated delivery of the same
  `successful_payment` does not create a second payment or a second notification.
- **Lead card**: shows a "paid" line (or "refunded") under the answers.
- **Admin**: revenue (net of refunds, per method and currency) in 💳 Payments and in 📊 Stats; export of all payments to
  CSV; **Refund Stars** (`refundStarPayment`) for Stars payments.
- **CSV safety**: text typed by people (client name, "Other" answers) is prefixed with `'` if it starts with `=`, `+`,
  `-` or `@`, so a spreadsheet does not run it as a formula.

## Verification status (2026-11-24)

**Checked live, in a real Telegram chat, with the bot @northwind_brief_bot and the Smart Glocal test provider:**
- brief → "Reserve a paid session" → package → invoice (shown by Telegram as a test invoice) → *Checkout (Test)* →
  Visa test card `4242 4242 4242 4242` → payment accepted for **25.00 USD**;
- the client received the confirmation, the manager received the "Paid!" notification with the lead buttons;
- the database row: status `paid`, `telegram_payment_charge_id` and the provider's charge id stored, amount `2500`;
- admin → 💳 Payments showed revenue `Card USD: 25.00 USD · 1 paid, 0 refunded`; 📊 Stats showed the same;
  the payments CSV contained one correct row; 📦 Packages listed both packages.

**Checked only on the in-process fake Telegram Bot API** (`tests/fake_telegram.py`, which enforces Telegram's invoice
rules such as one price item for Stars and a payload of at most 128 bytes) **and not in a live chat:**
- the whole **Telegram Stars** flow: invoice, payment, notification, revenue, **refund**;
- declined / expired / already-paid pre-checkout answers, repeated delivery of a payment, an invoice that Telegram
  rejects;
- the 3-D Secure test card (`4000 0000 0000 0002`) and a declined card were **not** tried live;
- the packages editor (add, edit prices, hide, delete) and the Stars-refund button were not exercised live.

**Test suite:** 56 tests (31 of them about payments) run on SQLite by default and on a real PostgreSQL server:
`python scripts/test_postgres.py` starts a throw-away embedded PostgreSQL (`pip install pixeltable-pgserver`) and runs
the same suite against it. Payments were **not** run live against PostgreSQL, only through the tests.

> Wording to use: "tested live with the Smart Glocal **test** provider" for card payments; "covered by automated tests
> against a fake Bot API" for Stars. It was not tested with any other provider, and no real money or real Stars were spent.

## Limits and notes

- **Card refunds are not done by the bot.** Telegram has no API to refund a provider payment; refund in the provider's
  dashboard. The bot only refunds Stars. A refunded card payment stays `paid` in the bot's records.
- **Test mode:** a test provider token (it contains `:TEST:`) produces test invoices and moves no money. The provider's
  documentation lists an amount range of $10–$1000; both default packages are inside it. It does not say whether that
  range also applies in test mode, and it does not document the test cards for use through a Telegram bot, so the live
  run above is the evidence that they work.
- **Going live:** get a production token from the payment provider through BotFather, replace the test token, and read
  the provider's terms (fees, payouts, supported countries, receipts and taxes). None of that is handled by this bot.
- **Not a shop:** there is no cart, no stock, no receipts, no invoices for accounting. One payment = one package for one
  brief. A brief that already has a paid payment cannot be paid again (after a Stars refund it can).
- **Currencies:** card prices are stored in minor units (cents) in `PAYMENTS_CURRENCY`; Stars prices are whole Stars.
- **One bot instance:** the bot uses long polling and in-memory FSM state. Running the same token from two machines makes
  Telegram answer `Conflict: terminated by other getUpdates request` and updates are split between the processes. Run one.
