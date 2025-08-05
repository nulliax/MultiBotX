#!/usr/bin/env python3
# main.py — MultiBotX final (reads secrets from environment only)

import os
import json
import logging
import random
import asyncio
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests
import yt_dlp
from flask import Flask, request
from dotenv import load_dotenv  # only for local dev, Render uses env vars
from telegram import Update, ChatPermissions
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Load .env for local development (safe: do NOT commit .env)
load_dotenv()

# ---------------- Config ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")  # e.g. multibotx.onrender.com
SAVETUBE_KEY = os.getenv("SAVETUBE_KEY")  # optional
PORT = int(os.getenv("PORT", 5000))
MAX_SEND_BYTES = 50 * 1024 * 1024  # 50 MB safety threshold

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment. Set it in Render Environment variables.")

# ---------------- Logging ----------------
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger("MultiBotX")

# ---------------- Persistence ----------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DONKE_FILE = DATA_DIR / "donke.json"

def load_donke():
    try:
        if DONKE_FILE.exists():
            return json.loads(DONKE_FILE.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Can't load donke.json")
    return {}

def save_donke(db):
    try:
        DONKE_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logger.exception("Can't save donke.json")

donke_db = load_donke()  # { user_id_str: {"name": str, "total": int, "last": "YYYY-MM-DD"} }

# ---------------- Content banks ----------------
JOKES = [
    "— Почему программист не может похудеть? — Потому что он ест байты.",
    "Я бы рассказал шутку про UDP, но не уверен, что ты её получишь.",
    "Debugging: превращение багов в фичи."
]

DONKE_PHRASES = [
    "Donke пошёл в бар и забыл зачем — бар счастлив.",
    "Donke — живой мем.",
    "Donke сегодня в ударе."
]

FACTS = [
    "У осьминога три сердца.",
    "Коты спят около 70% жизни.",
    "Мёд не портится."
]

QUOTES = [
    "«Делай, что должен, и будь, что будет.»",
    "«Лучший способ — начать.»",
    "«Не бойся ошибок — бойся не пробовать.»"
]

BAD_WORDS = ["бляд", "хуй", "пизд", "сука", "мраз"]  # простейший фильтр, расширяй по необходимости

# ---------------- Flask app ----------------
flask_app = Flask(__name__)

# ---------------- yt_dlp helper ----------------
YTDL_OPTS = {
    "format": "mp4[ext=mp4]/best",
    "outtmpl": "tmp_vid.%(ext)s",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
}

def download_with_yt_dlp(url: str) -> str:
    """Download video and return filename. Raises on error."""
    with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename

# ---------------- Utilities ----------------
def today_iso() -> str:
    return datetime.utcnow().date().isoformat()

async def safe_send_video(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, file_path: str, caption: Optional[str]=None):
    """Send video if size <= MAX_SEND_BYTES, else inform user."""
    try:
        size = os.path.getsize(file_path)
        if size <= MAX_SEND_BYTES:
            with open(file_path, "rb") as f:
                await ctx.bot.send_video(chat_id=chat_id, video=f, caption=caption or "")
            return True
        else:
            await ctx.bot.send_message(chat_id=chat_id, text="Видео слишком большое для отправки через бота (больше 50 MB).")
            return False
    except Exception:
        logger.exception("Error while sending video")
        return False
    finally:
        try:
            os.remove(file_path)
        except Exception:
            pass

# ---------------- Handlers ----------------

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Я MultiBotX. Напиши /menu, чтобы увидеть функции.")

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 *Меню MultiBotX*\n\n"
        "Развлечения:\n"
        "/joke, /fact, /quote, /cat, /dog, /meme, /dice\n\n"
        "Donke:\n"
        "/donke — шутка про Donke\n"
        "/camdonke — залить в Donke (раз в сутки)\n"
        "/topdonke — топ 50\n\n"
        "Видео:\n"
        "Просто отправь ссылку на YouTube или TikTok — бот попробует скачать.\n\n"
        "Модерация:\n"
        "Ответь на сообщение и напиши: варн / мут / размут / бан / анбан\n"
    )
    await update.message.reply_text(text)

# Entertainment
async def joke_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(JOKES))

async def fact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(FACTS))

async def quote_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(QUOTES))

async def cat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://api.thecatapi.com/v1/images/search", timeout=10).json()
        await update.message.reply_photo(r[0]["url"])
    except Exception:
        await update.message.reply_text("Не удалось получить фото котика.")

async def dog_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://dog.ceo/api/breeds/image/random", timeout=10).json()
        await update.message.reply_photo(r["message"])
    except Exception:
        await update.message.reply_text("Не удалось получить фото собаки.")

async def meme_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://meme-api.com/gimme", timeout=10).json()
        await update.message.reply_photo(r["url"], caption=r.get("title", "Мем"))
    except Exception:
        await update.message.reply_text("Не удалось получить мем.")

async def dice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_dice()

# Donke
async def donke_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(DONKE_PHRASES))

async def camdonke_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)
    entry = donke_db.get(uid, {"name": user.full_name, "total": 0, "last": None})
    if entry.get("last") == today_iso():
        await update.message.reply_text("❗ Сегодня вы уже заливали в Donke — заходите завтра.")
        return
    amount = random.randint(1, 100)
    entry["total"] = entry.get("total", 0) + amount
    entry["last"] = today_iso()
    entry["name"] = user.full_name
    donke_db[uid] = entry
    save_donke(donke_db)
    await update.message.reply_text(f"💦 Вы успешно залили в Donke {amount} литров! Спасибо — приходите завтра.")

async def topdonke_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not donke_db:
        await update.message.reply_text("Пока никто не заливал в Donke.")
        return
    sorted_list = sorted(donke_db.items(), key=lambda kv: kv[1].get("total", 0), reverse=True)[:50]
    lines = ["🏆 Топ Donke:"]
    for i, (uid, entry) in enumerate(sorted_list, 1):
        name = entry.get("name", f"@{uid}")
        total = entry.get("total", 0)
        lines.append(f"{i}. {name} — {total} л")
    await update.message.reply_text("\n".join(lines))

# Moderation (reply + free text)
async def moderation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.reply_to_message:
        return
    txt = msg.text.strip().lower()
    target = msg.reply_to_message.from_user
    chat = msg.chat

    # allow only admins/moderators
    try:
        member = await chat.get_member(msg.from_user.id)
        if not (member.status in ("administrator", "creator") or member.can_restrict_members):
            await msg.reply_text("У вас нет прав модератора.")
            return
    except Exception:
        logger.exception("Cannot check member status")

    if "варн" in txt:
        warns[target.id] = warns.get(target.id, 0) + 1
        await msg.reply_text(f"⚠️ {target.full_name} получил предупреждение ({warns[target.id]}).")
        if warns[target.id] >= 3:
            await chat.ban_member(target.id)
            await msg.reply_text(f"🚫 {target.full_name} забанен (3 предупреждения).")
    elif "мут" in txt:
        until = datetime.utcnow() + timedelta(minutes=10)
        await chat.restrict_member(target.id, ChatPermissions(can_send_messages=False), until_date=until)
        await msg.reply_text(f"🔇 {target.full_name} замучен на 10 минут.")
    elif txt in ("размут", "анмут"):
        await chat.restrict_member(target.id, ChatPermissions(can_send_messages=True))
        await msg.reply_text(f"🔊 {target.full_name} размучен.")
    elif "бан" in txt:
        await chat.ban_member(target.id)
        await msg.reply_text(f"🚫 {target.full_name} забанен.")
    elif txt in ("разбан", "унбан", "анбан"):
        await chat.unban_member(target.id)
        await msg.reply_text(f"✅ {target.full_name} разбанен.")

# Welcome, profanity filter and anti-flood
LAST_MSG_TIMES = {}  # {(chat_id, user_id): [timestamps]}

async def welcome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.new_chat_members:
        for m in update.message.new_chat_members:
            await update.message.reply_text(f"👋 Добро пожаловать, {m.full_name}!")

async def profanity_and_flood_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return
    text = msg.text.lower()
    for bad in BAD_WORDS:
        if bad in text:
            try:
                await msg.delete()
                await msg.reply_text(f"{msg.from_user.first_name}, не ругайся пожалуйста.")
            except Exception:
                pass
            return

    # flood control: simple heuristic
    key = (msg.chat.id, msg.from_user.id)
    now_ts = datetime.utcnow().timestamp()
    arr = LAST_MSG_TIMES.get(key, [])
    arr = [t for t in arr if now_ts - t < 10]  # last 10 sec
    arr.append(now_ts)
    LAST_MSG_TIMES[key] = arr
    if len(arr) > 6:
        try:
            await msg.chat.restrict_member(msg.from_user.id, ChatPermissions(can_send_messages=False),
                                           until_date=datetime.utcnow() + timedelta(minutes=1))
            await msg.reply_text("🤐 Антифлуд: пользователь замучен на 1 минуту.")
        except Exception:
            pass

# Download handler (command or plain URL message)
async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = None
    if context.args:
        text = context.args[0]
    elif update.message and update.message.text:
        # try to extract first URL in text
        import re
        m = re.search(r"https?://\S+", update.message.text)
        if m:
            text = m.group(0)
    if not text:
        return

    url = text.strip()
    await update.message.reply_text("⏬ Пытаюсь скачать видео (это может занять время)...")
    # prefer SaveTube API for TikTok if key provided
    try:
        if "tiktok.com" in url and SAVETUBE_KEY:
            # Example SaveTube API: change endpoint to your provider's docs
            headers = {"X-RapidAPI-Key": SAVETUBE_KEY}
            api_url = "https://save-tube-video-download.p.rapidapi.com/download"
            r = requests.get(api_url, headers=headers, params={"url": url}, timeout=15)
            j = r.json()
            # try to find usable link
            if isinstance(j, dict) and j.get("links"):
                vid_url = j["links"][0].get("url")
                if vid_url:
                    await update.message.reply_video(vid_url)
                    return
        # fallback: try yt_dlp for any URL (works for many TikTok/YouTube)
        fname = download_with_yt_dlp(url)
        sent = await safe_send_video(context, update.effective_chat.id, fname)
        if not sent:
            await update.message.reply_text("Видео слишком большое для отправки через Telegram.")
    except Exception as e:
        logger.exception("Download error")
        await update.message.reply_text("❌ Не удалось скачать видео. Попробуйте другую ссылку или позже.")

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception in handler: %s", context.error)
    try:
        tb = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
        logger.error(tb)
    except Exception:
        pass

# ---------------- Build application ----------------
def build_app():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # commands
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("menu", menu_handler))
    application.add_handler(CommandHandler("joke", joke_handler))
    application.add_handler(CommandHandler("fact", fact_handler))
    application.add_handler(CommandHandler("quote", quote_handler))
    application.add_handler(CommandHandler("cat", cat_handler))
    application.add_handler(CommandHandler("dog", dog_handler))
    application.add_handler(CommandHandler("meme", meme_handler))
    application.add_handler(CommandHandler("dice", dice_handler))
    application.add_handler(CommandHandler("donke", donke_handler))
    application.add_handler(CommandHandler("camdonke", camdonke_handler))
    application.add_handler(CommandHandler("topdonke", topdonke_handler))
    # download via command
    application.add_handler(CommandHandler("download", download_handler))
    # plain url messages
    application.add_handler(MessageHandler(filters.Regex(r"https?://"), download_handler))

    # moderation by reply-with-text
    application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, moderation_handler))

    # welcome / profanity / flood
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, profanity_and_flood_handler))

    application.add_error_handler(error_handler)
    return application

application = build_app()

# ---------------- Flask webhook endpoints ----------------
@flask_app.route("/", methods=["GET"])
def index():
    return "MultiBotX is running."

@flask_app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook_endpoint():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.update_queue.put_nowait(update)
    except Exception:
        logger.exception("Webhook handling failed")
    return "OK"

# ---------------- Run ----------------
def run():
    # set webhook if HOSTNAME exists
    if HOSTNAME:
        webhook_url = f"https://{HOSTNAME}/{BOT_TOKEN}"
        logger.info("Setting webhook: %s", webhook_url)
        asyncio.run(application.bot.set_webhook(webhook_url))
    else:
        logger.info("No RENDER_EXTERNAL_HOSTNAME set — running with polling")

    # run Flask on separate thread and run PTB event loop
    from threading import Thread
    t = Thread(target=lambda: flask_app.run(host="0.0.0.0", port=PORT))
    t.start()

    # start application (it will handle queued updates)
    application.run_polling()

if __name__ == "__main__":
    run()