import os import logging from flask import Flask, request from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext, CallbackQueryHandler) from telegram.constants import ChatAction from datetime import datetime, timedelta import random import aiohttp import re

Логирование

logging.basicConfig(level=logging.INFO) logger = logging.getLogger(name)

Flask-приложение

app = Flask(name)

Переменные окружения

BOT_TOKEN = os.getenv("BOT_TOKEN") HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME") PORT = int(os.environ.get('PORT', 10000))

Создание приложения Telegram

application = ApplicationBuilder().token(BOT_TOKEN).build()

--- Данные (шутки, цитаты и т.д.) ---

JOKES = [ "Почему программисты не плачут? Потому что они используют try.", "Что говорит ноль восьмёрке? Классный пояс!", "Программисты делятся на 10 типов: тех, кто понимает двоичный код, и тех, кто нет.", "Интерфейс — это то, что когда не работает, виноват ты.", "Сначала было слово. И слово было 'undefined'." ]

QUOTES = [ "Жизнь — как git, иногда нужно сделать reset --hard.", "Ошибки — это часть пути к мастерству.", "Сила кода — в его читаемости, а не в сложности.", "Делай как надо — и будет как надо." ]

FACTS = [ "Питон назван не в честь змеи, а в честь шоу 'Monty Python'.", "Первый программист — Ада Лавлейс, ещё в XIX веке.", "Самый популярный язык 2024 года — Python.", "Слово 'bug' появилось из-за настоящей моли в компьютере." ]

from flask import Flask, request from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler from telegram.constants import ChatMemberStatus import os, re, random, logging, datetime, asyncio, yt_dlp, requests, json from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN") PORT = int(os.environ.get("PORT", 5000)) HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME") APP_URL = f"https://{HOSTNAME}" if HOSTNAME else None

app = Flask(name) logging.basicConfig(level=logging.INFO)

application = ApplicationBuilder().token(TOKEN).build()

--- Развлечения ---

JOKES = [ "Почему программисты не плачут? Потому что они используют try.", "Что говорит ноль восьмёрке? Классный пояс!", "Программисты делятся на 10 типов: тех, кто понимает двоичный код, и тех, кто нет.", "Сколько нужно программистов, чтобы вкрутить лампочку? Ни одного. Это аппаратная проблема.", "Ошибка 404: шутка не найдена!" ]

FACTS = [ "Факт: У жирафа такой же голосовой аппарат, как у человека, но он почти никогда не издаёт звуков.", "Факт: Самое долгое научное исследование длилось более 75 лет и продолжается до сих пор.", "Факт: Кошки спят около 70% своей жизни.", "Факт: В космосе нет звука, потому что там нет воздуха для передачи звуковых волн.", "Факт: Вода может существовать одновременно в трёх состояниях: жидком, твёрдом и газообразном — при определённой температуре и давлении." ]

QUOTES = [ "Будь собой; все остальные роли уже заняты. — Оскар Уайльд", "Логика может привести вас от пункта А к пункту Б. Воображение может привести куда угодно. — Альберт Эйнштейн", "Успех — это идти от неудачи к неудаче, не теряя энтузиазма. — Уинстон Черчилль", "Если хочешь иметь то, что никогда не имел, придётся делать то, что никогда не делал. — Коко Шанель", "Падая семь раз, поднимайся восемь. — Японская пословица" ]

DONKE_QUOTES = [ "Donke — единственное существо, способное бесить на расстоянии Wi-Fi.", "Donke не баг — Donke фича.", "Donke вошёл в чат и IQ вышел.", "Donke может одновременно бесить и не понимать, за что его забанили.", "Donke — это искусство раздражать без усилий." ]

--- Приветствие ---

@app.route('/') def home(): return 'MultiBotX работает!'

--- Webhook ---

@app.route(f'/{TOKEN}', methods=['POST']) def webhook(): if request.method == "POST": update = Update.de_json(request.get_json(force=True), application.bot) asyncio.run(application.process_update(update)) return 'ok'

@app.before_first_request def set_webhook(): if APP_URL: application.bot.delete_webhook() application.bot.set_webhook(url=f"{APP_URL}/{TOKEN}")

# Обработчики команд
@dp.message(Command("start"))
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n"
        "Я — многофункциональный бот MultiBotX.\n"
        "Используй /help, чтобы увидеть, что я умею.",
    )


@dp.message(Command("help"))
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Команды:\n"
        "/start — Запуск\n"
        "/help — Помощь\n"
        "/warn, /mute, /ban — Модерация\n"
        "/unmute, /unban — Разблокировка\n"
        "/remindme — Напоминание\n"
        "🎲 /joke, /fact, /quote, /donke\n"
        "🐱 /cat, 🐶 /dog, 😂 /meme, 🎲 /dice\n"
        "📩 Отправь ссылку на YouTube/TikTok или нажми кнопку"
    )


@dp.message(Command("joke"))
async def joke_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(JOKES))


@dp.message(Command("fact"))
async def fact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(FACTS))


@dp.message(Command("quote"))
async def quote_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(QUOTES))


@dp.message(Command("donke"))
async def donke_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(DONKE_QUOTES))


@dp.message(Command("dice"))
async def dice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_dice()


# Вспомогательная функция отправки фото с API
async def send_photo(update: Update, url: str, json_key: str = None):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()
            if json_key:
                photo_url = data[json_key]
            else:
                photo_url = data["url"]
            await update.message.reply_photo(photo_url)
    except Exception as e:
        await update.message.reply_text("Ошибка при получении фото.")


@dp.message(Command("cat"))
async def cat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_photo(update, "https://api.thecatapi.com/v1/images/search", json_key=None)


@dp.message(Command("dog"))
async def dog_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_photo(update, "https://dog.ceo/api/breeds/image/random", json_key="message")


@dp.message(Command("meme"))
async def meme_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_photo(update, "https://meme-api.com/gimme", json_key="url")# МОДЕРАЦИЯ
async def extract_user_id(message: Message):
    if message.reply_to_message:
        return message.reply_to_message.from_user.id
    return None


async def is_admin(chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except:
        return False


@dp.message(Command("warn"))
async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("Ответь на сообщение пользователя для выдачи предупреждения.")
    user_id = update.message.reply_to_message.from_user.id
    warns = user_warnings.get(user_id, 0) + 1
    user_warnings[user_id] = warns
    if warns >= 3:
        await update.message.reply_text("3 предупреждения! Пользователь будет замучен.")
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=timedelta(minutes=10)
        )
        user_warnings[user_id] = 0
    else:
        await update.message.reply_text(f"Выдано предупреждение. Сейчас: {warns}/3")


@dp.message(Command("mute"))
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("Ответь на сообщение пользователя, чтобы замутить.")
    user_id = update.message.reply_to_message.from_user.id
    await context.bot.restrict_chat_member(
        chat_id=update.effective_chat.id,
        user_id=user_id,
        permissions=ChatPermissions(can_send_messages=False),
        until_date=timedelta(minutes=30),
    )
    await update.message.reply_text("Пользователь замучен на 30 минут.")


@dp.message(Command("unmute"))
async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("Ответь на сообщение пользователя для размут.")
    user_id = update.message.reply_to_message.from_user.id
    await context.bot.restrict_chat_member(
        chat_id=update.effective_chat.id,
        user_id=user_id,
        permissions=ChatPermissions(can_send_messages=True),
    )
    await update.message.reply_text("Пользователь размучен.")


@dp.message(Command("ban"))
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("Ответь на сообщение пользователя для бана.")
    user_id = update.message.reply_to_message.from_user.id
    await context.bot.ban_chat_member(update.effective_chat.id, user_id)
    await update.message.reply_text("Пользователь забанен.")


@dp.message(Command("unban"))
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("Ответь на сообщение пользователя для разбана.")
    user_id = update.message.reply_to_message.from_user.id
    await context.bot.unban_chat_member(update.effective_chat.id, user_id)
    await update.message.reply_text("Пользователь разбанен.")# РАБОТА С СЛОВАМИ МОДЕРАЦИИ (мут, бан и т.д.)
@dp.message()
async def moderation_by_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    reply = update.message.reply_to_message
    if not reply:
        return

    user_id = reply.from_user.id

    if "варн" in text:
        warns = user_warnings.get(user_id, 0) + 1
        user_warnings[user_id] = warns
        if warns >= 3:
            await context.bot.restrict_chat_member(
                chat_id=update.effective_chat.id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=timedelta(minutes=10)
            )
            user_warnings[user_id] = 0
            return await update.message.reply_text("Пользователь получил 3/3 предупреждений и замучен.")
        else:
            return await update.message.reply_text(f"Выдано предупреждение. Сейчас: {warns}/3")

    elif "мут" in text:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=timedelta(minutes=30)
        )
        return await update.message.reply_text("Пользователь замучен на 30 минут.")

    elif "размут" in text or "анмут" in text:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=True),
        )
        return await update.message.reply_text("Пользователь размучен.")

    elif "бан" in text:
        await context.bot.ban_chat_member(update.effective_chat.id, user_id)
        return await update.message.reply_text("Пользователь забанен.")

    elif "разбан" in text or "анбан" in text or "унбан" in text:
        await context.bot.unban_chat_member(update.effective_chat.id, user_id)
        return await update.message.reply_text("Пользователь разбанен.")# НАПОМИНАНИЕ
@dp.message(Command("remindme"))
async def remind_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = update.message.text.split(maxsplit=2)
    if len(args) < 3:
        return await update.message.reply_text("Используй: /remindme <время> <сообщение>")
    try:
        time = int(args[1])
        text = args[2]
        await update.message.reply_text(f"Напоминание установлено через {time} секунд.")
        await asyncio.sleep(time)
        await update.message.reply_text(f"🔔 Напоминание: {text}")
    except:
        await update.message.reply_text("Неверный формат. Пример: /remindme 60 Сделать домашку.")# ЗАГРУЗКА ВИДЕО ИЗ YOUTUBE И TIKTOK
SAVE_TUBE_API_KEY = os.getenv("SAVE_TUBE_API_KEY")
SAVE_TUBE_URL = "https://api.savetube.me/info"

@dp.message(Command("yt"))
async def download_youtube(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = update.message.text.split(maxsplit=1)
    if len(args) != 2:
        return await update.message.reply_text("Используй: /yt <ссылка>")
    url = args[1]
    await update.message.reply_text("⏳ Загружаю видео...")

    async with aiohttp.ClientSession() as session:
        async with session.post(SAVE_TUBE_URL, json={"url": url, "apikey": SAVE_TUBE_API_KEY}) as resp:
            data = await resp.json()
            if not data.get("medias"):
                return await update.message.reply_text("❌ Не удалось загрузить видео.")
            best = data["medias"][0]
            video_url = best["url"]
            await update.message.reply_video(video=video_url, caption="🎬 Готово!")

@dp.message(Command("tt"))
async def download_tiktok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = update.message.text.split(maxsplit=1)
    if len(args) != 2:
        return await update.message.reply_text("Используй: /tt <ссылка>")
    url = args[1]
    await update.message.reply_text("⏳ Загружаю видео...")

    async with aiohttp.ClientSession() as session:
        async with session.post(SAVE_TUBE_URL, json={"url": url, "apikey": SAVE_TUBE_API_KEY}) as resp:
            data = await resp.json()
            if not data.get("medias"):
                return await update.message.reply_text("❌ Не удалось загрузить видео.")
            best = data["medias"][0]
            video_url = best["url"]
            await update.message.reply_video(video=video_url, caption="🎬 Готово!")# ПРИВЕТСТВИЕ НОВЫХ
@dp.chat_member()
async def greet_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = update.chat_member
    if member.new_chat_member.status == ChatMember.MEMBER:
        await context.bot.send_message(
            chat_id=update.chat_member.chat.id,
            text=f"👋 Добро пожаловать, {member.new_chat_member.user.mention_html()}!",
            parse_mode="HTML"
        )# ФИЛЬТР МАТА И АНТИФЛУД
BAD_WORDS = ["плохое", "слово", "мат", "идиот", "дурак"]  # сюда добавь любые маты

user_message_times = {}

@dp.message()
async def auto_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id
    now = datetime.now()

    # Антифлуд
    last_time = user_message_times.get(user_id)
    if last_time and (now - last_time).total_seconds() < 1.5:
        await context.bot.delete_message(chat_id, update.message.message_id)
        return
    user_message_times[user_id] = now

    # Фильтр мата
    msg_text = update.message.text.lower()
    if any(bad_word in msg_text for bad_word in BAD_WORDS):
        await context.bot.delete_message(chat_id, update.message.message_id)
        await update.message.reply_text("⚠️ Без мата, пожалуйста!")# AI-ЗАГЛУШКА (будет добавлено позже, когда появится API-ключ)
@dp.message(Command("ai"))
async def ai_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 AI пока недоступен. Функция появится позже.")# FLASK-СЕРВЕР ДЛЯ RENDER
@app.route('/')
def home():
    return "MultiBotX работает!"

@app.route('/webhook', methods=['POST'])
def webhook():
    return "Webhook!"# РЕГИСТРАЦИЯ ВСЕХ ОБРАБОТЧИКОВ
def register_handlers():
    pass  # хендлеры уже зарегистрированы через декораторы выше# ЗАПУСК БОТА И FLASK
if __name__ == '__main__':
    import asyncio

    async def run_bot():
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        print("Бот запущен ✅")

    loop = asyncio.get_event_loop()
    loop.create_task(run_bot())

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)