"""
Telegram-бот управления. Запускается параллельно со scheduler.

Кнопки главного меню:
  🗂 Категории   📋 Статус   🔍 Тест   ⏸ Пауза   📊 Статистика   🕐 Последние
"""

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, ContextTypes,
)

from app.config import TELEGRAM_BOT_TOKEN, OWNER_ID
from app.database import (
    ALL_CATEGORIES, get_active_categories, set_active_categories,
    is_paused, set_paused, get_last_sent, get_stats,
)

logging.basicConfig(level=logging.WARNING)

# Флаг для scheduler — нужно запустить цикл немедленно
_trigger_now = False

def trigger_immediate_cycle():
    global _trigger_now
    _trigger_now = True

def consume_trigger() -> bool:
    global _trigger_now
    if _trigger_now:
        _trigger_now = False
        return True
    return False


def is_owner(update: Update) -> bool:
    return update.effective_user.id == OWNER_ID


# ─── Клавиатуры ──────────────────────────────────────────────────────────────

def build_main_menu() -> InlineKeyboardMarkup:
    paused = is_paused()
    pause_label = "▶️ Возобновить" if paused else "⏸ Пауза"
    pause_cb = "action:resume" if paused else "action:pause"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗂 Категории", callback_data="menu:filters"),
            InlineKeyboardButton("📋 Статус",    callback_data="menu:status"),
        ],
        [
            InlineKeyboardButton("🔍 Запустить цикл", callback_data="action:test"),
            InlineKeyboardButton(pause_label,          callback_data=pause_cb),
        ],
        [
            InlineKeyboardButton("📊 Статистика",  callback_data="menu:stats"),
            InlineKeyboardButton("🕐 Последние",   callback_data="menu:last"),
        ],
    ])


def build_filters_keyboard(active: set) -> InlineKeyboardMarkup:
    buttons = []
    for key, label in ALL_CATEGORIES.items():
        icon = "✅" if key in active else "☑️"
        buttons.append([InlineKeyboardButton(
            f"{icon} {label}", callback_data=f"toggle:{key}"
        )])
    buttons.append([
        InlineKeyboardButton("✅ Все",      callback_data="all:on"),
        InlineKeyboardButton("☑️ Сбросить", callback_data="all:off"),
    ])
    buttons.append([InlineKeyboardButton("💾 Сохранить", callback_data="save")])
    buttons.append([InlineKeyboardButton("◀️ Назад",     callback_data="menu:back")])
    return InlineKeyboardMarkup(buttons)


# ─── Тексты ──────────────────────────────────────────────────────────────────

def text_status() -> str:
    active = get_active_categories()
    paused = is_paused()
    state = "⏸ <b>Пауза</b>" if paused else "▶️ <b>Работает</b>"

    if active == set(ALL_CATEGORIES.keys()):
        cats = "все категории"
    else:
        cats = "\n" + "\n".join(ALL_CATEGORIES[k] for k in ALL_CATEGORIES if k in active)

    return f"📋 <b>Статус бота</b>\n\nСостояние: {state}\nКатегории: {cats}"


def text_stats() -> str:
    s = get_stats()
    lines = [f"📊 <b>Статистика</b>\n"]
    lines.append(f"Всего проверено URL: <b>{s['total']}</b>")
    lines.append(f"Отправлено новостей: <b>{s['sent']}</b>")
    if s["by_source"]:
        lines.append("\nПо источникам:")
        for src, cnt in sorted(s["by_source"].items(), key=lambda x: -x[1]):
            lines.append(f"  • {src}: {cnt}")
    return "\n".join(lines)


def text_last() -> str:
    items = get_last_sent(5)
    if not items:
        return "🕐 <b>Последние новости</b>\n\nПока ничего не отправлено."
    lines = ["🕐 <b>Последние 5 отправленных новостей</b>\n"]
    for i, item in enumerate(items, 1):
        title = item["original_title"][:60] + ("…" if len(item["original_title"]) > 60 else "")
        cat = f" [{item['category']}]" if item.get("category") else ""
        lines.append(f"{i}. <a href=\"{item['url']}\">{title}</a>{cat}")
    return "\n".join(lines)


# ─── Команды ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    await update.message.reply_text(
        "👋 <b>Бот новостей Словении</b>\n\nВыбери действие:",
        parse_mode="HTML",
        reply_markup=build_main_menu()
    )


# ─── Callback ────────────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != OWNER_ID:
        return

    data = query.data

    async def edit_text(text, keyboard=None):
        try:
            await query.edit_message_text(
                text, parse_mode="HTML",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        except Exception:
            pass

    async def edit_markup(keyboard):
        try:
            await query.edit_message_reply_markup(reply_markup=keyboard)
        except Exception:
            pass

    # ── Навигация ─────────────────────────────────────────────────────────────
    if data == "menu:back":
        await edit_text("👋 <b>Бот новостей Словении</b>\n\nВыбери действие:", build_main_menu())

    elif data == "menu:status":
        await edit_text(text_status(), build_main_menu())

    elif data == "menu:stats":
        await edit_text(text_stats(), build_main_menu())

    elif data == "menu:last":
        await edit_text(text_last(), build_main_menu())

    elif data == "menu:filters":
        active = get_active_categories()
        context.user_data["pending_categories"] = set(active)
        await edit_text(
            "🗂 <b>Категории новостей</b>\n\n✅ включена  ☑️ выключена\nНажми <b>Сохранить</b> когда готово.",
            build_filters_keyboard(active)
        )

    # ── Действия ──────────────────────────────────────────────────────────────
    elif data == "action:test":
        trigger_immediate_cycle()
        await edit_text(
            "🔍 <b>Запускаю цикл проверки...</b>\n\nНовости придут в течение минуты.",
            build_main_menu()
        )

    elif data == "action:pause":
        set_paused(True)
        await edit_text("⏸ <b>Бот на паузе.</b>\n\nСбор новостей остановлен.", build_main_menu())

    elif data == "action:resume":
        set_paused(False)
        await edit_text("▶️ <b>Бот возобновлён.</b>\n\nСледующий цикл — по расписанию.", build_main_menu())

    # ── Фильтры ───────────────────────────────────────────────────────────────
    elif data.startswith("toggle:"):
        pending = context.user_data.get("pending_categories", get_active_categories())
        key = data.split(":")[1]
        pending.discard(key) if key in pending else pending.add(key)
        context.user_data["pending_categories"] = pending
        await edit_markup(build_filters_keyboard(pending))

    elif data == "all:on":
        pending = set(ALL_CATEGORIES.keys())
        context.user_data["pending_categories"] = pending
        await edit_markup(build_filters_keyboard(pending))

    elif data == "all:off":
        pending = set()
        context.user_data["pending_categories"] = pending
        await edit_markup(build_filters_keyboard(pending))

    elif data == "save":
        pending = context.user_data.get("pending_categories", set())
        if not pending:
            await query.answer("⚠️ Нельзя сохранить пустой список!", show_alert=True)
            return
        set_active_categories(pending)
        if pending == set(ALL_CATEGORIES.keys()):
            summary = "все категории"
        else:
            summary = ", ".join(
                ALL_CATEGORIES[k].split(" ", 1)[1]
                for k in ALL_CATEGORIES if k in pending
            )
        context.user_data.pop("pending_categories", None)
        await edit_text(
            f"✅ <b>Сохранено!</b>\n\nАктивные категории: {summary}\n\n"
            "Вступит в силу в следующем цикле.",
            build_main_menu()
        )


# ─── Запуск ──────────────────────────────────────────────────────────────────

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("Telegram bot запущен")
    app.run_polling(drop_pending_updates=True)
