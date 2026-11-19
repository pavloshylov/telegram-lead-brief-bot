"""All user-facing texts in English and Ukrainian.

The language is taken from the user's Telegram settings (uk -> Ukrainian, anything else -> English).
Every key must exist in both languages (checked by tests/test_texts.py).
"""
from __future__ import annotations

EN: dict[str, str] = {
    # ---------- common
    "start_client": (
        "👋 Hi! I'm the {company} brief bot.\n\n"
        "A manager sends you a personal link, you answer 4 quick questions, "
        "and we come to the first meeting prepared — at a time that suits you.\n\n"
        "If you got here without a link, please ask your manager for one."
    ),
    "start_manager": (
        "👋 Hi, {name}! You're a manager at {company}.\n\n"
        "➕ <b>New brief link</b> — a personal link for a client\n"
        "📋 <b>My leads</b> — briefs you've sent and the answers"
    ),
    "start_admin_extra": "\n⚙️ <b>Admin panel</b> — stats, broadcasts, catalogs, team",
    "help": (
        "<b>How it works</b>\n"
        "1. A manager creates a personal brief link for a client.\n"
        "2. The client opens it and answers 4 questions with buttons.\n"
        "3. The manager instantly gets a lead card with the answers.\n\n"
        "/start — main menu\n/cancel — cancel the current action\n/help — this message"
    ),
    "cancelled": "Cancelled. Nothing was saved.",
    "nothing_to_cancel": "Nothing to cancel 🙂",
    "unknown": "I didn't get that. Please use the buttons or /help.",
    "use_buttons": "Please tap one of the buttons 👇",
    "error": "⚠️ Something went wrong on our side. Please try again, or /cancel to start over.",
    "link_invalid": "This link is not valid. Please ask your manager for a new one.",
    "became_manager": "✅ Welcome to the team! You're now a manager at {company}.",
    "invite_invalid": "This team invite has expired or was already used. Please ask an admin for a new one.",
    "already_manager": "You're already on the team 🙂",
    "btn_back": "◀️ Back",
    "btn_cancel": "✖️ Cancel",
    "cmd_start": "Main menu",
    "cmd_help": "How it works",
    "cmd_cancel": "Cancel the current action",
    "cmd_admin": "Admin panel",
    # ---------- manager
    "btn_new_brief": "➕ New brief link",
    "btn_my_leads": "📋 My leads",
    "btn_admin": "⚙️ Admin panel",
    "ask_client_name": "Who is the brief for? Send the client's name, the way you'd address them.",
    "bad_client_name": "Please send a name from 2 to 64 characters.",
    "ask_tone": "Greeting style for <b>{client}</b>:",
    "tone_formal": "🎩 Formal",
    "tone_friendly": "😊 Friendly",
    "tone_short": "⚡ Short & direct",
    "ask_office": "Where will the meeting take place?",
    "no_offices": "There are no offices in the catalog yet. Ask an admin to add one.",
    "brief_ready": (
        "✅ The brief link for <b>{client}</b> is ready:\n\n{link}\n\n"
        "Send it to the client. You'll get a lead card here as soon as they answer. Each link can be answered once."
    ),
    "btn_share": "📤 Share link",
    "share_text": "Hi {client}! Here's a short brief from {company}: 4 questions, about a minute.",
    "btn_another": "➕ One more link",
    "leads_empty": "No briefs yet. Tap «➕ New brief link» to create the first one.",
    "leads_header": "📋 <b>Your latest briefs</b>\n⏳ waiting · 🆕 new lead · 📞 contacted · ✅ closed",
    "lead_card": "{icon} <b>Brief #{id} · {client}</b>\nCreated {created} · {office}",
    "lead_waiting": "⏳ The client hasn't answered yet.\n🔗 {link}",
    "lead_answered_by": "👤 Answered by {client_link}",
    "new_lead": "🆕 <b>New lead!</b> {client_link} completed brief #{id}",
    "lead_answers": (
        "👤 Name in brief: {client}\n"
        "📍 Meeting: {office}\n"
        "✔️ Service: {service}\n"
        "✔️ Budget: {budget}\n"
        "✔️ Day: {day}\n"
        "✔️ Time: {time}"
    ),
    "lead_no_username": "ℹ️ The client has no public @username: tap their name above to open the chat.",
    "btn_open_chat": "💬 Open chat",
    "btn_contacted": "📞 Mark contacted",
    "btn_close_lead": "✅ Close lead",
    "btn_reopen": "↩️ Reopen",
    "status_new": "🆕 new",
    "status_contacted": "📞 contacted",
    "status_closed": "✅ closed",
    "lead_status_set": "Status: {status}",
    "not_your_lead": "This lead belongs to another manager.",
    # ---------- client
    "greet_formal": (
        "Good day, {client}!\n\n"
        "{manager} from {company} has prepared a short brief so that we come to the first meeting well prepared.\n\n"
        "📍 Meeting: {office}\n⏱ 4 questions, about a minute."
    ),
    "greet_friendly": (
        "Hi {client}! 👋\n\n"
        "It's {manager} from {company}. Tell us a little about your project and pick a time that works for you — "
        "it takes about a minute.\n\n📍 Meeting: {office}"
    ),
    "greet_short": "{client}, 4 quick questions from {company} ({manager}) — about a minute.\n📍 {office}",
    "btn_start_brief": "▶️ Start",
    "self_brief": "This is your own brief link — send it to the client 🙂",
    "already_answered_self": "You've already sent this brief ✅ {manager} will contact you soon.\n\n{summary}",
    "already_answered_other": (
        "This brief has already been completed. If you'd like one too, please ask {company} for a personal link."
    ),
    "step_header": "<b>Step {n} of 4</b>  {bar}",
    "q_service": "What do you need help with?",
    "q_budget": "What budget range are you considering?",
    "q_day": "When would you like to meet?",
    "q_time": "What time suits you?",
    "btn_other_service": "✏️ Other — I'll type it",
    "ask_service_text": "Describe what you need in a few words:",
    "bad_service_text": "Please use 2 to 100 characters.",
    "day_today": "Today",
    "day_tomorrow": "Tomorrow",
    "day_this_week": "Later this week",
    "day_next_week": "Next week",
    "btn_pick_date": "📅 Pick a date",
    "ask_date": "Send a date as DD.MM (for example, {example}).",
    "bad_date": "I couldn't read that date. Please use DD.MM, for example {example}.",
    "date_past": "That date has already passed. Please pick a future date.",
    "date_too_far": "Please pick a date within the next 6 months.",
    "time_morning": "Morning (9–12)",
    "time_afternoon": "Afternoon (12–17)",
    "time_evening": "Evening (17–20)",
    "btn_exact_time": "🕐 Exact time",
    "ask_time": "Send a time as HH:MM (for example, 14:30).",
    "bad_time": "Please send the time as HH:MM, for example 14:30.",
    "time_past": "That time has already passed today. Please pick a later one.",
    "confirm": "<b>Please check your answers</b>\n\n{summary}\n\nIs everything correct?",
    "summary": "🛠 Service: {service}\n💰 Budget: {budget}\n📅 Day: {day}\n🕐 Time: {time}\n📍 Meeting: {office}",
    "btn_send": "✅ Send",
    "btn_restart": "✏️ Start over",
    "sent": "🙌 Thank you, {client}! Your answers are with {manager}, who will confirm the meeting soon.",
    "brief_already_sent": "This brief is already sent ✅",
    "step_expired": "This step has expired. Please open your link again to continue.",
    # ---------- admin
    "admin_menu": "⚙️ <b>Admin panel</b> · {company}",
    "btn_stats": "📊 Stats",
    "btn_broadcast": "📣 Broadcast",
    "btn_catalogs": "🗂 Catalogs",
    "btn_team": "👥 Team",
    "btn_export": "📥 Export leads (CSV)",
    "stats": (
        "📊 <b>Stats</b>\n\n"
        "👥 Users: <b>{users}</b> (+{new7} in 7 days, {blocked} blocked the bot)\n"
        "🧑‍💼 Managers: <b>{managers}</b>\n"
        "🔗 Brief links: <b>{created}</b>\n"
        "✅ Completed: <b>{completed}</b> ({rate})\n"
        "📞 Leads in progress or closed: <b>{contacted}</b>\n\n"
        "<b>Top services</b>\n{services}\n\n"
        "<b>Top managers</b>\n{top_managers}"
    ),
    "none_yet": "— none yet",
    "bc_choose_segment": "📣 Who should get the message?",
    "seg_all": "Everyone ({n})",
    "seg_managers": "Managers ({n})",
    "seg_clients": "Clients ({n})",
    "bc_ask_message": (
        "Send the message to broadcast: text, or a photo/video with a caption. "
        "It will be delivered exactly as you send it.\n/cancel to stop."
    ),
    "bc_preview": "👆 This is the preview. Send it to <b>{n}</b> users?",
    "bc_no_targets": "Nobody to send to in this segment.",
    "btn_bc_send": "🚀 Send",
    "bc_started": "⏳ Sending to {n} users…",
    "bc_done": (
        "✅ Broadcast finished in {sec} s\nDelivered: <b>{ok}</b>\nBlocked the bot: {blocked}\nFailed: {failed}"
    ),
    "bc_cancelled": "Broadcast cancelled.",
    "cat_choose": "🗂 Which list would you like to edit?",
    "cat_office": "📍 Offices",
    "cat_service": "🛠 Services",
    "cat_budget": "💰 Budgets",
    "cat_list": "<b>{title}</b>\nTap an item to hide or delete it. Hidden items 🙈 are not shown to clients.",
    "btn_add": "➕ Add",
    "cat_ask_label": "Send the name of the new item (up to 64 characters):",
    "cat_added": "✅ Added «{label}».",
    "cat_duplicate": "«{label}» is already in the list.",
    "cat_bad_label": "Please use 1 to 64 characters.",
    "cat_item": "<b>{label}</b>\nStatus: {status}",
    "item_visible": "visible to clients",
    "item_hidden": "hidden",
    "btn_hide": "🙈 Hide",
    "btn_show": "👁 Show",
    "btn_delete": "🗑 Delete",
    "cat_confirm_delete": "Delete «{label}»? Briefs that already used it keep their answers.",
    "btn_yes_delete": "🗑 Yes, delete",
    "cat_deleted": "Deleted.",
    "team": "👥 <b>Team</b> · {n} managers\nTap a manager to remove them.",
    "btn_invite_manager": "➕ Invite a manager",
    "team_invite": "🔗 One-time team invite (valid 7 days):\n\n{link}\n\nWhoever opens it becomes a manager.",
    "team_confirm_remove": "Remove <b>{name}</b> from managers? Their briefs stay in the database.",
    "btn_yes_remove": "Yes, remove",
    "team_removed": "Removed.",
    "export_empty": "No briefs yet, nothing to export.",
    "export_caption": "📥 {n} briefs, exported {date}.",
}

UK: dict[str, str] = {
    # ---------- common
    "start_client": (
        "👋 Вітаю! Я бот брифів {company}.\n\n"
        "Менеджер надсилає вам персональне посилання, ви відповідаєте на 4 короткі питання, "
        "і ми приходимо на першу зустріч підготовленими — у зручний для вас час.\n\n"
        "Якщо ви потрапили сюди без посилання, попросіть його у свого менеджера."
    ),
    "start_manager": (
        "👋 Вітаю, {name}! Ви менеджер {company}.\n\n"
        "➕ <b>Нове посилання</b> — персональний бриф для клієнта\n"
        "📋 <b>Мої ліди</b> — надіслані брифи та відповіді"
    ),
    "start_admin_extra": "\n⚙️ <b>Адмін-панель</b> — статистика, розсилки, довідники, команда",
    "help": (
        "<b>Як це працює</b>\n"
        "1. Менеджер створює персональне посилання-бриф для клієнта.\n"
        "2. Клієнт відкриває його й відповідає на 4 питання кнопками.\n"
        "3. Менеджер одразу отримує картку ліда з відповідями.\n\n"
        "/start — головне меню\n/cancel — скасувати поточну дію\n/help — ця підказка"
    ),
    "cancelled": "Скасовано. Нічого не збережено.",
    "nothing_to_cancel": "Немає що скасовувати 🙂",
    "unknown": "Не зрозумів. Скористайтеся кнопками або /help.",
    "use_buttons": "Будь ласка, оберіть одну з кнопок 👇",
    "error": "⚠️ Щось пішло не так з нашого боку. Спробуйте ще раз або /cancel, щоб почати спочатку.",
    "link_invalid": "Це посилання недійсне. Попросіть у менеджера нове.",
    "became_manager": "✅ Ласкаво просимо в команду! Тепер ви менеджер {company}.",
    "invite_invalid": "Запрошення в команду прострочене або вже використане. Попросіть у адміністратора нове.",
    "already_manager": "Ви вже в команді 🙂",
    "btn_back": "◀️ Назад",
    "btn_cancel": "✖️ Скасувати",
    "cmd_start": "Головне меню",
    "cmd_help": "Як це працює",
    "cmd_cancel": "Скасувати поточну дію",
    "cmd_admin": "Адмін-панель",
    # ---------- manager
    "btn_new_brief": "➕ Нове посилання",
    "btn_my_leads": "📋 Мої ліди",
    "btn_admin": "⚙️ Адмін-панель",
    "ask_client_name": "Для кого бриф? Надішліть ім'я клієнта так, як ви до нього звертаєтеся.",
    "bad_client_name": "Надішліть ім'я довжиною від 2 до 64 символів.",
    "ask_tone": "Стиль привітання для <b>{client}</b>:",
    "tone_formal": "🎩 Офіційний",
    "tone_friendly": "😊 Дружній",
    "tone_short": "⚡ Коротко й по суті",
    "ask_office": "Де відбудеться зустріч?",
    "no_offices": "У довіднику ще немає жодного офісу. Попросіть адміністратора додати.",
    "brief_ready": (
        "✅ Посилання-бриф для <b>{client}</b> готове:\n\n{link}\n\n"
        "Надішліть його клієнту. Картка ліда прийде сюди одразу після відповіді. На кожне посилання можна відповісти один раз."
    ),
    "btn_share": "📤 Поділитися",
    "share_text": "Вітаю, {client}! Короткий бриф від {company}: 4 питання, приблизно хвилина.",
    "btn_another": "➕ Ще одне посилання",
    "leads_empty": "Брифів ще немає. Натисніть «➕ Нове посилання», щоб створити перший.",
    "leads_header": "📋 <b>Ваші останні брифи</b>\n⏳ очікує · 🆕 новий лід · 📞 на зв'язку · ✅ закрито",
    "lead_card": "{icon} <b>Бриф #{id} · {client}</b>\nСтворено {created} · {office}",
    "lead_waiting": "⏳ Клієнт ще не відповів.\n🔗 {link}",
    "lead_answered_by": "👤 Відповів(-ла) {client_link}",
    "new_lead": "🆕 <b>Новий лід!</b> {client_link} заповнив(-ла) бриф #{id}",
    "lead_answers": (
        "👤 Ім'я в брифі: {client}\n"
        "📍 Зустріч: {office}\n"
        "✔️ Послуга: {service}\n"
        "✔️ Бюджет: {budget}\n"
        "✔️ День: {day}\n"
        "✔️ Час: {time}"
    ),
    "lead_no_username": "ℹ️ У клієнта немає публічного @username: натисніть на ім'я вище, щоб відкрити чат.",
    "btn_open_chat": "💬 Відкрити чат",
    "btn_contacted": "📞 Зв'язався",
    "btn_close_lead": "✅ Закрити лід",
    "btn_reopen": "↩️ Повернути в роботу",
    "status_new": "🆕 новий",
    "status_contacted": "📞 на зв'язку",
    "status_closed": "✅ закрито",
    "lead_status_set": "Статус: {status}",
    "not_your_lead": "Цей лід належить іншому менеджеру.",
    # ---------- client
    "greet_formal": (
        "Доброго дня, {client}!\n\n"
        "{manager} з {company} підготував(-ла) короткий бриф, щоб ми прийшли на першу зустріч підготовленими.\n\n"
        "📍 Зустріч: {office}\n⏱ 4 питання, приблизно хвилина."
    ),
    "greet_friendly": (
        "Привіт, {client}! 👋\n\n"
        "Це {manager} з {company}. Розкажіть трохи про свій проєкт і оберіть зручний час — "
        "це займе близько хвилини.\n\n📍 Зустріч: {office}"
    ),
    "greet_short": "{client}, 4 швидкі питання від {company} ({manager}) — близько хвилини.\n📍 {office}",
    "btn_start_brief": "▶️ Почати",
    "self_brief": "Це ваше власне посилання — надішліть його клієнту 🙂",
    "already_answered_self": "Ви вже надіслали цей бриф ✅ {manager} скоро з вами зв'яжеться.\n\n{summary}",
    "already_answered_other": (
        "Цей бриф уже заповнено. Якщо вам теж потрібен, попросіть у {company} персональне посилання."
    ),
    "step_header": "<b>Крок {n} з 4</b>  {bar}",
    "q_service": "З чим вам потрібна допомога?",
    "q_budget": "На який бюджет ви орієнтуєтеся?",
    "q_day": "Коли вам зручно зустрітися?",
    "q_time": "Який час вам підходить?",
    "btn_other_service": "✏️ Інше — напишу",
    "ask_service_text": "Опишіть кількома словами, що вам потрібно:",
    "bad_service_text": "Будь ласка, від 2 до 100 символів.",
    "day_today": "Сьогодні",
    "day_tomorrow": "Завтра",
    "day_this_week": "Пізніше цього тижня",
    "day_next_week": "Наступного тижня",
    "btn_pick_date": "📅 Обрати дату",
    "ask_date": "Надішліть дату у форматі ДД.ММ (наприклад, {example}).",
    "bad_date": "Не вдалося розпізнати дату. Формат ДД.ММ, наприклад {example}.",
    "date_past": "Ця дата вже минула. Оберіть дату в майбутньому.",
    "date_too_far": "Оберіть дату в межах найближчих 6 місяців.",
    "time_morning": "Ранок (9–12)",
    "time_afternoon": "День (12–17)",
    "time_evening": "Вечір (17–20)",
    "btn_exact_time": "🕐 Точний час",
    "ask_time": "Надішліть час у форматі ГГ:ХХ (наприклад, 14:30).",
    "bad_time": "Надішліть час у форматі ГГ:ХХ, наприклад 14:30.",
    "time_past": "Цей час сьогодні вже минув. Оберіть пізніший.",
    "confirm": "<b>Перевірте, будь ласка, відповіді</b>\n\n{summary}\n\nУсе правильно?",
    "summary": "🛠 Послуга: {service}\n💰 Бюджет: {budget}\n📅 День: {day}\n🕐 Час: {time}\n📍 Зустріч: {office}",
    "btn_send": "✅ Надіслати",
    "btn_restart": "✏️ Почати спочатку",
    "sent": "🙌 Дякуємо, {client}! Відповіді вже в {manager}, зустріч підтвердять найближчим часом.",
    "brief_already_sent": "Цей бриф уже надіслано ✅",
    "step_expired": "Цей крок застарів. Відкрийте своє посилання ще раз, щоб продовжити.",
    # ---------- admin
    "admin_menu": "⚙️ <b>Адмін-панель</b> · {company}",
    "btn_stats": "📊 Статистика",
    "btn_broadcast": "📣 Розсилка",
    "btn_catalogs": "🗂 Довідники",
    "btn_team": "👥 Команда",
    "btn_export": "📥 Вивантажити ліди (CSV)",
    "stats": (
        "📊 <b>Статистика</b>\n\n"
        "👥 Користувачів: <b>{users}</b> (+{new7} за 7 днів, {blocked} заблокували бота)\n"
        "🧑‍💼 Менеджерів: <b>{managers}</b>\n"
        "🔗 Посилань-брифів: <b>{created}</b>\n"
        "✅ Заповнено: <b>{completed}</b> ({rate})\n"
        "📞 Лідів у роботі або закрито: <b>{contacted}</b>\n\n"
        "<b>Топ послуг</b>\n{services}\n\n"
        "<b>Топ менеджерів</b>\n{top_managers}"
    ),
    "none_yet": "— поки немає",
    "bc_choose_segment": "📣 Кому надіслати повідомлення?",
    "seg_all": "Усім ({n})",
    "seg_managers": "Менеджерам ({n})",
    "seg_clients": "Клієнтам ({n})",
    "bc_ask_message": (
        "Надішліть повідомлення для розсилки: текст або фото/відео з підписом. "
        "Його буде доставлено точно в такому вигляді.\n/cancel — зупинити."
    ),
    "bc_preview": "👆 Це попередній перегляд. Надіслати <b>{n}</b> користувачам?",
    "bc_no_targets": "У цьому сегменті нікому надсилати.",
    "btn_bc_send": "🚀 Надіслати",
    "bc_started": "⏳ Надсилаю {n} користувачам…",
    "bc_done": (
        "✅ Розсилку завершено за {sec} с\nДоставлено: <b>{ok}</b>\nЗаблокували бота: {blocked}\nПомилок: {failed}"
    ),
    "bc_cancelled": "Розсилку скасовано.",
    "cat_choose": "🗂 Який довідник редагуємо?",
    "cat_office": "📍 Офіси",
    "cat_service": "🛠 Послуги",
    "cat_budget": "💰 Бюджети",
    "cat_list": "<b>{title}</b>\nНатисніть на пункт, щоб приховати або видалити. Приховані 🙈 клієнти не бачать.",
    "btn_add": "➕ Додати",
    "cat_ask_label": "Надішліть назву нового пункту (до 64 символів):",
    "cat_added": "✅ Додано «{label}».",
    "cat_duplicate": "«{label}» вже є в списку.",
    "cat_bad_label": "Будь ласка, від 1 до 64 символів.",
    "cat_item": "<b>{label}</b>\nСтатус: {status}",
    "item_visible": "бачать клієнти",
    "item_hidden": "приховано",
    "btn_hide": "🙈 Приховати",
    "btn_show": "👁 Показати",
    "btn_delete": "🗑 Видалити",
    "cat_confirm_delete": "Видалити «{label}»? Брифи, де його вже обрали, збережуть відповіді.",
    "btn_yes_delete": "🗑 Так, видалити",
    "cat_deleted": "Видалено.",
    "team": "👥 <b>Команда</b> · менеджерів: {n}\nНатисніть на менеджера, щоб прибрати його з команди.",
    "btn_invite_manager": "➕ Запросити менеджера",
    "team_invite": "🔗 Одноразове запрошення в команду (діє 7 днів):\n\n{link}\n\nХто його відкриє, стане менеджером.",
    "team_confirm_remove": "Прибрати <b>{name}</b> з менеджерів? Їхні брифи залишаться в базі.",
    "btn_yes_remove": "Так, прибрати",
    "team_removed": "Прибрано.",
    "export_empty": "Брифів ще немає, вивантажувати нічого.",
    "export_caption": "📥 Брифів: {n}, вивантажено {date}.",
}

LANGS = {"en": EN, "uk": UK}

WEEKDAYS = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "uk": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"],
}
MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "uk": ["січ", "лют", "бер", "кві", "тра", "чер", "лип", "сер", "вер", "жов", "лис", "гру"],
}


def pick_lang(language_code: str | None) -> str:
    return "uk" if (language_code or "").lower().startswith("uk") else "en"


class Translator:
    def __init__(self, lang: str):
        self.lang = lang if lang in LANGS else "en"

    def __call__(self, key: str, **kwargs: object) -> str:
        template = LANGS[self.lang].get(key) or EN[key]
        return template.format(**kwargs) if kwargs else template


def all_variants(key: str) -> set[str]:
    """The same button in every language — used to match reply-keyboard presses."""
    return {texts[key] for texts in LANGS.values()}
