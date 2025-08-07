import os
import logging
from flask import Flask, request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ChatPermissions
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes
)
from telegram.constants import ParseMode
from yt_dlp import YoutubeDL
from datetime import datetime, timedelta
import asyncio
import re
import random
import requests

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask-приложение
app = Flask(__name__)

# Токен и переменные окружения
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 8443))
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")

# Инициализация бота
application = Application.builder().token(TOKEN).build()

# Словарь каст админов
admin_ranks = {}  # {chat_id: {user_id: "Supreme"|"Commander"|...}}

RANKS = ["Default", "Guard", "Captain", "Commander", "Supreme"]
RANK_EMOJIS = {
    "Supreme": "👑", "Commander": "🦾",
    "Captain": "⚔️", "Guard": "🛡", "Default": "👤"
}

# Права для мута
NO_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_media_messages=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
    can_change_info=False,
    can_invite_users=False,
    can_pin_messages=False
)

# Статусы
antimat_status = {}  # {chat_id: True/False}# Главное меню
def get_main_menu():
    keyboard = [
        [KeyboardButton("🎲 Кубик"), KeyboardButton("📸 Мем")],
        [KeyboardButton("😸 Кот"), KeyboardButton("🐶 Пёс")],
        [KeyboardButton("🧠 Факт"), KeyboardButton("💬 Цитата")],
        [KeyboardButton("🎭 Шутка"), KeyboardButton("🤬 Donke")],
        [KeyboardButton("📥 YouTube"), KeyboardButton("📥 TikTok")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_html(
        f"👋 Привет, <b>{user.first_name}</b>!\n\n"
        f"Я <b>MultiBotX</b> — универсальный бот с модерацией, мемами, видео, AI и шутками.",
        reply_markup=get_main_menu()
    )

# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Команды:\n"
        "/start — Запуск\n"
        "/help — Помощь\n"
        "/warn, /mute, /ban — Модерация\n"
        "/unmute, /unban — Разблокировка\n"
        "/remindme — Напоминание\n"
        "📩 Отправь ссылку на YouTube/TikTok или нажми кнопку"
    )

    # Здесь можно объявить JOKES, если нужно использовать только в этой функции:
    JOKES = [
        "Почему программисты не плачут? Потому что они используют try.",
        "Что говорит ноль восьмёрке? Классный пояс!",
        "Программисты делятся на 10 типов: тех, кто понимает двоичный код, и тех, кто нет."
    ]
FACTS = [
    "🐙 Осьминоги имеют три сердца.",
    "🌋 На Венере день длиннее года.",
    "💡 Первым программистом была женщина — Ада Лавлейс."
]

QUOTES = [
    "💬 «Будь собой — остальные роли уже заняты.» — Оскар Уайльд",
    "💬 «Жизнь — это 10% того, что с тобой происходит, и 90% — как ты на это реагируешь.»"
]

DONKE_JOKES = [
    "Donke настолько глуп, что думает, что GPT — это GPS с ошибкой.",
    "Donke пытался удалить system32 на телефоне…",
    "Donke играет в шахматы с голубями — всё равно проиграет и обосрёт доску."
]

async def handle_fun_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    if "мем" in text:
        await send_random_meme(update)
    elif "шутк" in text:
        await update.message.reply_text(random.choice(JOKES))
    elif "факт" in text:
        await update.message.reply_text(random.choice(FACTS))
    elif "цитат" in text:
        await update.message.reply_text(random.choice(QUOTES))
    elif "donke" in text:
        await update.message.reply_text(random.choice(DONKE_JOKES))
    elif "кот" in text:
        await send_photo(update, "https://cataas.com/cat")
    elif "пёс" in text or "собак" in text:
        await send_photo(update, "https://random.dog/woof.json", json_key="url")
    elif "кубик" in text:
        await update.message.reply_dice()async def send_photo(update: Update, url: str, json_key: str = None):
    try:
        if json_key:
            response = requests.get(url).json()
            photo_url = response[json_key]
        else:
            photo_url = url
        await update.message.reply_photo(photo_url)
    except Exception as e:
        await update.message.reply_text("⚠️ Не удалось получить изображение.")

async def send_random_meme(update: Update):
    try:
        meme_url = f"https://meme-api.com/gimme"
        data = requests.get(meme_url).json()
        await update.message.reply_photo(data["url"], caption=data["title"])
    except:
        await update.message.reply_text("⚠️ Мем не найден.")async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("⚠️ Ответь на сообщение, чтобы выдать предупреждение.")
    await update.message.reply_text("⚠️ Пользователь получил предупреждение.")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("⚠️ Ответь на сообщение для мута.")
    until_date = datetime.now() + timedelta(minutes=60)
    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        update.message.reply_to_message.from_user.id,
        permissions=NO_PERMISSIONS,
        until_date=until_date
    )
    await update.message.reply_text("🔇 Пользователь замьючен на 60 минут.")

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("⚠️ Ответь на сообщение для размьюта.")
    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        update.message.reply_to_message.from_user.id,
        permissions=ChatPermissions(can_send_messages=True)
    )
    await update.message.reply_text("🔊 Пользователь размьючен.")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("⚠️ Ответь на сообщение для бана.")
    await update.message.chat.ban_member(update.message.reply_to_message.from_user.id)
    await update.message.reply_text("⛔ Пользователь забанен.")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("⚠️ Ответь на сообщение для разбанивания.")
    await update.message.chat.unban_member(update.message.reply_to_message.from_user.id)
    await update.message.reply_text("✅ Пользователь разбанен.")# === Команда /remindme ===
from datetime import datetime, timedelta
import asyncio

user_reminders = {}

async def remindme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("Использование: /remindme [через_время] [напоминание]\nПример: /remindme 10m Выпить воду")
            return

        delay_str = args[0]
        reminder_text = " ".join(args[1:])

        delay = parse_delay(delay_str)
        if delay is None:
            await update.message.reply_text("Неверный формат времени. Используйте '10s', '5m', '2h', и т.п.")
            return

        await update.message.reply_text(f"⏰ Напоминание установлено через {delay_str}: {reminder_text}")

        user_id = update.effective_user.id
        reminder_time = datetime.now() + delay
        if user_id not in user_reminders:
            user_reminders[user_id] = []
        user_reminders[user_id].append((reminder_time, reminder_text))

        asyncio.create_task(schedule_reminder(context.bot, update.effective_chat.id, delay.total_seconds(), reminder_text))

    except Exception as e:
        print("Ошибка в remindme:", e)

def parse_delay(time_str):
    try:
        unit = time_str[-1]
        amount = int(time_str[:-1])
        if unit == "s":
            return timedelta(seconds=amount)
        elif unit == "m":
            return timedelta(minutes=amount)
        elif unit == "h":
            return timedelta(hours=amount)
        else:
            return None
    except:
        return None

async def schedule_reminder(bot: Bot, chat_id: int, delay: float, text: str):
    await asyncio.sleep(delay)
    try:
        await bot.send_message(chat_id=chat_id, text=f"🔔 Напоминание: {text}")
    except Exception as e:
        print("Не удалось отправить напоминание:", e)

# === Обработка всех входящих сообщений ===
@restricted
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    text = update.message.text.lower()

    # Автоматическая фильтрация
    if contains_profanity(text):
        try:
            await update.message.delete()
            await update.message.reply_text("⚠️ Не используйте нецензурные слова.")
        except:
            pass

    # Обработка слов без "/"
    if update.message.reply_to_message:
        replied_user = update.message.reply_to_message.from_user.id
        if "мут" in text:
            await mute_user(update, context, replied_user)
        elif "размут" in text or "анмут" in text:
            await unmute_user(update, context, replied_user)
        elif "варн" in text:
            await warn_user(update, context, replied_user)
        elif "бан" in text:
            await ban_user(update, context, replied_user)
        elif "разбан" in text or "анбан" in text or "унбан" in text:
            await unban_user(update, context, replied_user)

# === Flask-приложение ===
def build_application():
    application = Application.builder().token(os.getenv("BOT_TOKEN")).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("joke", joke_command))
    application.add_handler(CommandHandler("fact", fact_command))
    application.add_handler(CommandHandler("quote", quote_command))
    application.add_handler(CommandHandler("cat", cat_command))
    application.add_handler(CommandHandler("dog", dog_command))
    application.add_handler(CommandHandler("meme", meme_command))
    application.add_handler(CommandHandler("dice", dice_command))
    application.add_handler(CommandHandler("donke", donke_command))
    application.add_handler(CommandHandler("topdonke", topdonke_command))
    application.add_handler(CommandHandler("camdonke", camdonke_command))
    application.add_handler(CommandHandler("yt", yt_command))
    application.add_handler(CommandHandler("tt", tt_command))
    application.add_handler(CommandHandler("remindme", remindme))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    return application# === Flask сервер для хостинга на Render.com ===
import threading
from flask import Flask, request

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return '🤖 MultiBotX работает!'

@flask_app.route('/webhook', methods=['POST'])
def webhook():
    return "Webhook endpoint"

def run_flask():
    flask_app.run(host="0.0.0.0", port=8080)

# === Запуск ===
if __name__ == '__main__':
    import asyncio

    # Flask в отдельном потоке
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Запуск Telegram-бота
    app = build_application()
    asyncio.run(app.initialize())
    app.run_polling()