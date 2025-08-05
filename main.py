#!/usr/bin/env python3
# main.py — MultiBotX (final)
# Требует: python-telegram-bot==20.8, Flask, python-dotenv, requests, yt_dlp

import os
import json
import logging
import random
import asyncio
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, request
from dotenv import load_dotenv

# Telegram
from telegram import Update, ChatPermissions
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Video downloader
import yt_dlp
import requests

# Load local .env for dev (Render uses its own env vars)
load_dotenv()

# ----------------- Config & logging -----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")  # e.g. multibotx.onrender.com
PORT = int(os.getenv("PORT", 5000))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден. Установи переменную окружения BOT_TOKEN в Render или .env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MultiBotX")

# ----------------- Flask app (webhook receive) -----------------
flask_app = Flask(__name__)

# ----------------- Persistence (Donke DB) -----------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DONKE_FILE = DATA_DIR / "donke.json"

def load_donke_db():
    if DONKE_FILE.exists():
        try:
            return json.loads(DONKE_FILE.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Не удалось загрузить donke.json — пересоздаю")
            return {}
    return {}

def save_donke_db(db):
    DONKE_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

donke_db = load_donke_db()  # { user_id_str: {"name": str, "total": int, "last_date": "YYYY-MM-DD"} }

# ----------------- Content banks -----------------
JOKES = [
    "— Почему программист не может похудеть? — Потому что он ест байты.",
    "Я бы рассказал шутку про UDP, но не уверен, что ты её получишь.",
    "Debugging: превращение багов в фичи."
]

DONKE_JOKES = [
    "Donke пошёл в бар и забыл, зачем пришёл — бар счастлив.",
    "Donke такой редкий баг, что его ещё не успели задокументировать.",
    "Donke — живой мем."
]

FACTS = [
    "У осьминога три сердца.",
    "Кошки спят около 70% своей жизни.",
    "Мёд не портится."
]

QUOTES = [
    "«Действуй — пока другие мечтают».",
    "«Лучший способ предсказать будущее — создать его.»",
    "«Маленькие шаги ведут к большим результатам.»"
]

BAD_WORDS = ["бляд", "хуй", "пизд", "сука", "мраз"]  # простейший фильтр (дополни при желании)

# ----------------- Utils -----------------
def today_str():
    return datetime.utcnow().date().isoformat()

def is_admin_chat(user_id: int, chat):
    """Проверяет, имеет ли пользователь права ограничения в текущем чате."""
    try:
        member = chat.get_member(user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

# ----------------- yt_dlp helper -----------------
YTDL_OPTS = {
    "format": "mp4[ext=mp4]/best",
    "outtmpl": "tmp_video.%(ext)s",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
}

def download_video_with_yt_dlp(url: str) -> str:
    """Скачивает видео через yt_dlp и возвращает путь к файлу (или raises)."""
    with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename

# ----------------- Handlers -----------------

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /start от %s", update.effective_user.id)
    text = ("👋 Привет! Я MultiBotX — многофункциональный бот.\n"
            "Напиши /menu чтобы увидеть главное меню.")
    await update.message.reply_text(text)

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 *Меню MultiBotX*\n\n"
        "Развлечения:\n"
        "/joke — шутка\n"
        "/donke — шутка про Donke\n"
        "/fact — факт\n"
        "/quote — цитата\n"
        "/cat — фото кота\n"
        "/dog — фото собаки\n"
        "/meme — мем\n"
        "/dice — кубик\n\n"
        "Donke:\n"
        "/camdonke — залить в Donke (раз в сутки)\n"
        "/topdonke — топ 50\n\n"
        "Видео:\n"
        "Просто пришли ссылку на YouTube или TikTok — бот попытается скачать.\n\n"
        "Модерация:\n"
        "Ответь на сообщение и напиши: варн / мут / размут / бан / анбан\n"
    )
    await update.message.reply_text(text)

# Entertainment handlers
async def joke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(JOKES))

async def donke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(DONKE_JOKES))

async def fact_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(FACTS))

async def quote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(QUOTES))

async def cat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://api.thecatapi.com/v1/images/search", timeout=10).json()
        await update.message.reply_photo(r[0]["url"])
    except Exception:
        await update.message.reply_text("Не удалось получить фото котика.")

async def dog_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://dog.ceo/api/breeds/image/random", timeout=10).json()
        await update.message.reply_photo(r["message"])
    except Exception:
        await update.message.reply_text("Не удалось получить фото собаки.")

async def meme_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://meme-api.com/gimme", timeout=10).json()
        await update.message.reply_photo(r["url"], caption=r.get("title", "Мем"))
    except Exception:
        await update.message.reply_text("Не удалось получить мем.")

async def dice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_dice()

# Donke
async def camdonke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)
    db = donke_db  # alias

    today = today_str()
    user_entry = db.get(uid, {"name": user.full_name, "total": 0, "last": None})
    if user_entry.get("last") == today:
        await update.message.reply_text("❗ Сегодня вы уже заливали в Donke — заходите завтра.")
        return

    amount = random.randint(1, 100)
    user_entry["total"] = user_entry.get("total", 0) + amount
    user_entry["last"] = today
    user_entry["name"] = user.full_name
    db[uid] = user_entry
    save_donke_db(db)

    await update.message.reply_text(f"💦 Вы успешно залили в Donke {amount} литров! Спасибо — приходите завтра.")

async def topdonke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not donke_db:
        await update.message.reply_text("Пока никто не заливал в Donke.")
        return
    # sort desc by total
    sorted_list = sorted(donke_db.items(), key=lambda kv: kv[1].get("total", 0), reverse=True)[:50]
    text_lines = ["🏆 Топ Donke (топ 50):"]
    for i, (uid, entry) in enumerate(sorted_list, 1):
        name = entry.get("name", f"@{uid}")
        total = entry.get("total", 0)
        text_lines.append(f"{i}. {name} — {total} л")
    await update.message.reply_text("\n".join(text_lines))

# Moderation: when a user replies to a message and writes the command without slash
async def moderation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.reply_to_message:
        return
    cmd_text = msg.text.strip().lower()
    target = msg.reply_to_message.from_user
    chat = msg.chat

    # Only allow admins/moderators to perform moderation
    try:
        member = await chat.get_member(msg.from_user.id)
        if not (member.status in ("administrator", "creator") or member.can_restrict_members):
            await msg.reply_text("У вас нет прав модератора.")
            return
    except Exception:
        logger.exception("Не удалось получить статус участника")

    if "варн" in cmd_text:
        warns[target.id] = warns.get(target.id, 0) + 1
        await msg.reply_text(f"⚠️ {target.full_name} получил предупреждение. ({warns[target.id]})")
        if warns[target.id] >= 3:
            await chat.ban_member(target.id)
            await msg.reply_text(f"🚫 {target.full_name} забанен (3 варна).")
    elif "мут" in cmd_text:
        until = datetime.utcnow() + timedelta(minutes=10)
        await chat.restrict_member(target.id, ChatPermissions(can_send_messages=False), until_date=until)
        await msg.reply_text(f"🔇 {target.full_name} замучен на 10 минут.")
    elif cmd_text in ("размут", "анмут"):
        await chat.restrict_member(target.id, ChatPermissions(can_send_messages=True))
        await msg.reply_text(f"🔊 {target.full_name} размучен.")
    elif "бан" in cmd_text:
        await chat.ban_member(target.id)
        await msg.reply_text(f"🚫 {target.full_name} забанен.")
    elif cmd_text in ("разбан", "унбан", "анбан"):
        await chat.unban_member(target.id)
        await msg.reply_text(f"✅ {target.full_name} разбанен.")

# Auto actions: welcome, profanity filter, anti-flood
LAST_MESSAGES = {}  # {(chat_id, user_id): [timestamps]}

async def welcome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.new_chat_members:
        for member in update.message.new_chat_members:
            await update.message.reply_text(f"👋 Добро пожаловать, {member.full_name}!")

async def profanity_and_flood_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    text = msg.text.lower()

    # profanity
    for bad in BAD_WORDS:
        if bad in text:
            try:
                await msg.delete()
                await msg.reply_text(f"{msg.from_user.first_name}, не ругайся пожалуйста.")
            except Exception:
                pass
            return

    # flood: simple sliding window
    key = (msg.chat.id, msg.from_user.id)
    now = datetime.utcnow().timestamp()
    arr = LAST_MESSAGES.get(key, [])
    arr = [t for t in arr if now - t < 10]  # keep last 10 sec
    arr.append(now)
    LAST_MESSAGES[key] = arr
    if len(arr) > 6:  # more than 6 messages in 10 seconds
        try:
            await msg.chat.restrict_member(msg.from_user.id,
                                           ChatPermissions(can_send_messages=False),
                                           until_date=datetime.utcnow() + timedelta(minutes=1))
            await msg.reply_text(f"🤐 Антифлуд: {msg.from_user.first_name} замучен на 1 минуту.")
        except Exception:
            pass

# Download handler: when user sends message containing URL (YouTube/TikTok) or uses /download
async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # accept both command args and plain message text
    text = None
    if context.args:
        text = context.args[0]
    elif update.message and update.message.text:
        text = update.message.text.strip()

    if not text:
        return

    url = text.strip()
    if not (("youtube.com" in url) or ("youtu.be" in url) or ("tiktok.com" in url) or ("vm.tiktok" in url)):
        # not a supported url
        return

    msg = await update.message.reply_text("⏬ Пытаюсь скачать видео... (это может занять время)")
    try:
        # download with yt_dlp (works for YouTube and TikTok)
        filename = download_video_with_yt_dlp(url)
        # send file (if too big, we'll send link or inform user)
        size = os.path.getsize(filename)
        MAX_SEND = 50 * 1024 * 1024  # 50 MB safe threshold for many hosts
        if size > MAX_SEND:
            # don't try to upload huge files — send a note
            await msg.edit_text("Видео слишком большое для отправки через Telegram. Загрузил локально. Попробуй скачать напрямую.")
            # remove file to save space
            try:
                os.remove(filename)
            except Exception:
                pass
            return
        with open(filename, "rb") as f:
            await update.message.reply_video(f)
        await msg.delete()
        try:
            os.remove(filename)
        except Exception:
            pass
    except Exception as e:
        logger.error("Ошибка скачивания видео: %s", e)
        await msg.edit_text("❌ Не удалось скачать видео. Попробуйте другую ссылку или позже.")

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Произошла ошибка: %s", context.error)
    try:
        tb = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
        logger.error(tb)
    except Exception:
        pass

# ----------------- Setup application -----------------
def build_application():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # commands
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("menu", menu_cmd))
    application.add_handler(CommandHandler("joke", joke_cmd))
    application.add_handler(CommandHandler("donke", donke_cmd))
    application.add_handler(CommandHandler("fact", fact_cmd))
    application.add_handler(CommandHandler("quote", quote_cmd))
    application.add_handler(CommandHandler("cat", cat_cmd))
    application.add_handler(CommandHandler("dog", dog_cmd))
    application.add_handler(CommandHandler("meme", meme_cmd))
    application.add_handler(CommandHandler("dice", dice_cmd))

    application.add_handler(CommandHandler("camdonke", camdonke_cmd))
    application.add_handler(CommandHandler("topdonke", topdonke_cmd))

    application.add_handler(CommandHandler("download", download_handler))
    # support plain url messages
    application.add_handler(MessageHandler(filters.Regex(r"https?://"), download_handler))

    # moderation (reply + plain text commands like "мут", "варн")
    application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, moderation_handler))

    # welcome and filters
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, profanity_and_flood_handler))

    application.add_error_handler(error_handler)
    return application

application = build_application()

# ----------------- Flask webhook endpoints -----------------
@flask_app.route("/", methods=["GET"])
def index():
    return "MultiBotX is running."

@flask_app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook_endpoint():
    """Endpoint for Telegram webhook -> push updates into PTB application queue."""
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.update_queue.put_nowait(update)
    except Exception as e:
        logger.exception("Ошибка в webhook_endpoint: %s", e)
    return "OK"

# ----------------- Run -----------------
def run():
    # set webhook on startup (Render uses external hostname)
    if HOSTNAME:
        webhook_url = f"https://{HOSTNAME}/{BOT_TOKEN}"
        logger.info("Setting webhook to %s", webhook_url)
        # set webhook synchronously before starting Flask
        asyncio.run(application.bot.set_webhook(webhook_url))
    else:
        logger.info("No RENDER_EXTERNAL_HOSTNAME set — running in polling mode")

    # start Flask in a thread and then start PTB event loop
    from threading import Thread
    flask_thread = Thread(target=lambda: flask_app.run(host="0.0.0.0", port=PORT))
    flask_thread.start()

    # run the telegram application (polling if no webhook)
    if HOSTNAME:
        # webhook mode — start application (handles update_queue)
        application.run_polling(stop_signals=None)
    else:
        # no hostname — fallback to polling
        application.run_polling()

if __name__ == "__main__":
    run()