#!/usr/bin/env python3
# main.py — MultiBotX (single-file)
# Requires: python-telegram-bot==20.8, Flask, requests, python-dotenv (optional), yt_dlp

import os
import json
import logging
import random
import re
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from threading import Thread
from typing import Optional

import requests
import yt_dlp
from flask import Flask, request
from dotenv import load_dotenv  # optional: only for local dev
from telegram import Update, ChatPermissions
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Optional: load local .env for development. On Render use Environment variables instead.
load_dotenv()

# ----------------- Config -----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")  # e.g. multibotx.onrender.com
SAVETUBE_KEY = os.getenv("SAVETUBE_KEY")  # optional: SaveTube / RapidAPI key for TikTok
PORT = int(os.getenv("PORT", 5000))
MAX_SEND_BYTES = 50 * 1024 * 1024  # 50 MB threshold for safe sending via Telegram

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Add it to environment variables (Render Environment).")

# ----------------- Logging -----------------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("MultiBotX")

# ----------------- Flask -----------------
flask_app = Flask(__name__)

# ----------------- Persistence -----------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DONKE_FILE = DATA_DIR / "donke.json"

def load_json(path: Path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to load JSON %s", path)
            return {}
    return {}

def save_json(path: Path, data):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logger.exception("Failed to save JSON %s", path)

donke_db = load_json(DONKE_FILE)  # {str(user_id): {"name": str, "total": int, "last": "YYYY-MM-DD"}}

# ----------------- Content banks -----------------
JOKES = [
    "— Почему программист не может похудеть? — Потому что он ест байты.",
    "Я бы рассказал шутку про UDP, но не уверен, что получишь её.",
    "Debugging: превращение багов в фичи."
]

DONKE_PHRASES = [
    "Donke пошёл в бар и забыл зачем — бар счастлив.",
    "Donke — живой мем.",
    "Donke сегодня в ударе."
]

FACTS = [
    "У осьминога три сердца.",
    "Кошки могут спать до 20 часов в день.",
    "Мёд не портится."
]

QUOTES = [
    "«Лучший способ начать — просто начать.»",
    "«Ошибки — это доказательство попыток.»",
    "«Маленькие шаги ведут к большим результатам.»"
]

BAD_WORDS = ["бляд", "хуй", "пизд", "сука", "мраз"]  # расширяй по необходимости

# ----------------- yt_dlp helper -----------------
YTDL_OPTS = {
    "format": "mp4[ext=mp4]/best",
    "outtmpl": "tmp_video.%(ext)s",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
}

def download_with_yt_dlp(url: str) -> str:
    """Downloads video and returns filepath. May raise."""
    with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename

# ----------------- Utilities -----------------
def today_iso() -> str:
    return datetime.utcnow().date().isoformat()

def safe_remove(path: str):
    try:
        os.remove(path)
    except Exception:
        pass

async def send_video_or_warn(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, file_path: str, caption: Optional[str] = None):
    """Send video file if size <= MAX_SEND_BYTES, else inform user and delete file."""
    try:
        size = os.path.getsize(file_path)
        if size <= MAX_SEND_BYTES:
            with open(file_path, "rb") as f:
                await ctx.bot.send_video(chat_id=chat_id, video=f, caption=caption or "")
            return True
        else:
            await ctx.bot.send_message(chat_id=chat_id, text="Видео слишком большое для отправки (больше 50 MB).")
            return False
    except Exception:
        logger.exception("Error sending video")
        return False
    finally:
        safe_remove(file_path)

# ----------------- Handlers -----------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Я MultiBotX. Напиши /menu чтобы увидеть возможности.")

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
        "/dice — бросить кубик\n\n"
        "Donke:\n"
        "/camdonke — залить в Donke (раз в сутки)\n"
        "/topdonke — топ 50\n\n"
        "Видео:\n"
        "Просто пришли ссылку на YouTube или TikTok — бот попытается скачать.\n\n"
        "Модерация:\n"
        "Ответь на сообщение и напиши: варн / мут / размут / бан / анбан\n"
    )
    await update.message.reply_text(text)

# Entertainment
async def joke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(JOKES))

async def donke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(DONKE_PHRASES))

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

# Donke actions
async def camdonke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    save_json(DONKE_FILE, donke_db)
    await update.message.reply_text(f"💦 Вы успешно залили в Donke {amount} литров! Возвращайтесь завтра.")

async def topdonke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not donke_db:
        await update.message.reply_text("Пока никто не заливал в Donke.")
        return
    sorted_list = sorted(donke_db.items(), key=lambda kv: kv[1].get("total", 0), reverse=True)[:50]
    lines = ["🏆 Топ Donke:"]
    for i, (uid, e) in enumerate(sorted_list, 1):
        name = e.get("name", f"@{uid}")
        total = e.get("total", 0)
        lines.append(f"{i}. {name} — {total} л")
    await update.message.reply_text("\n".join(lines))

# Moderation (reply + free-text like "мут", "варн")
warns = {}

async def moderation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.reply_to_message:
        return
    txt = msg.text.strip().lower()
    target = msg.reply_to_message.from_user
    chat = msg.chat

    # only admins/mods can moderate
    try:
        member = await chat.get_member(msg.from_user.id)
        if not (member.status in ("administrator", "creator") or member.can_restrict_members):
            await msg.reply_text("У вас нет прав модератора.")
            return
    except Exception:
        logger.exception("Failed to check moderator status")

    if "варн" in txt:
        warns[target.id] = warns.get(target.id, 0) + 1
        await msg.reply_text(f"⚠️ {target.full_name} получил предупреждение ({warns[target.id]}).")
        if warns[target.id] >= 3:
            try:
                await chat.ban_member(target.id)
                await msg.reply_text(f"🚫 {target.full_name} забанен (3 предупреждения).")
                warns[target.id] = 0
            except Exception:
                logger.exception("Ban failed")
    elif "мут" in txt:
        until = datetime.utcnow() + timedelta(minutes=10)
        try:
            await chat.restrict_member(target.id, ChatPermissions(can_send_messages=False), until_date=until)
            await msg.reply_text(f"🔇 {target.full_name} замучен на 10 минут.")
        except Exception:
            logger.exception("Mute failed")
    elif txt in ("размут", "анмут"):
        try:
            await chat.restrict_member(target.id, ChatPermissions(can_send_messages=True))
            await msg.reply_text(f"🔊 {target.full_name} размучен.")
        except Exception:
            logger.exception("Unmute failed")
    elif "бан" in txt:
        try:
            await chat.ban_member(target.id)
            await msg.reply_text(f"🚫 {target.full_name} забанен.")
        except Exception:
            logger.exception("Ban failed")
    elif txt in ("разбан", "унбан", "анбан"):
        try:
            await chat.unban_member(target.id)
            await msg.reply_text(f"✅ {target.full_name} разбанен.")
        except Exception:
            logger.exception("Unban failed")

# Welcome and filters
LAST_MSG = {}  # {(chat_id, user_id): [timestamps]}

async def welcome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.new_chat_members:
        for m in update.message.new_chat_members:
            await update.message.reply_text(f"👋 Добро пожаловать, {m.full_name}!")

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
    # flood
    key = (msg.chat.id, msg.from_user.id)
    now_ts = datetime.utcnow().timestamp()
    arr = LAST_MSG.get(key, [])
    arr = [t for t in arr if now_ts - t < 10]  # last 10 sec
    arr.append(now_ts)
    LAST_MSG[key] = arr
    if len(arr) > 6:
        try:
            await msg.chat.restrict_member(msg.from_user.id, ChatPermissions(can_send_messages=False),
                                           until_date=datetime.utcnow() + timedelta(minutes=1))
            await msg.reply_text("🤐 Антифлуд: замучен на 1 минуту.")
        except Exception:
            pass

# Download handler: accepts command args or raw URL in message
async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = None
    if context.args:
        text = context.args[0]
    elif update.message and update.message.text:
        m = re.search(r"https?://\S+", update.message.text)
        if m:
            text = m.group(0)
    if not text:
        return

    url = text.strip()
    msg = await update.message.reply_text("⏬ Пытаюсь скачать видео... (может занять время)")
    try:
        # if tiktok and SAVETUBE_KEY provided, try API first
        if "tiktok.com" in url and SAVETUBE_KEY:
            try:
                headers = {"X-RapidAPI-Key": SAVETUBE_KEY}
                api_url = "https://save-tube-video-download.p.rapidapi.com/download"
                r = requests.get(api_url, headers=headers, params={"url": url}, timeout=15)
                j = r.json()
                if isinstance(j, dict) and j.get("links"):
                    vid_url = j["links"][0].get("url")
                    if vid_url:
                        await update.message.reply_video(vid_url)
                        await msg.delete()
                        return
            except Exception:
                logger.exception("SaveTube API failed, will fallback to yt_dlp")
        # fallback: download with yt_dlp (works for many sources)
        fname = download_with_yt_dlp(url)
        sent = await send_video_or_warn(context, update.effective_chat.id, fname)
        if not sent:
            await update.message.reply_text("Видео было загружено, но оно слишком большое для отправки через Telegram.")
        await msg.delete()
    except Exception as e:
        logger.exception("Download failed: %s", e)
        try:
            await msg.edit_text("❌ Не удалось скачать видео. Попробуйте другую ссылку.")
        except Exception:
            pass

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception in handler: %s", context.error)
    try:
        tb = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
        logger.error(tb)
    except Exception:
        pass

# ----------------- Build application -----------------
def build_app():
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
    # also accept plain URLs in messages
    application.add_handler(MessageHandler(filters.Regex(r"https?://"), download_handler))

    # moderation by reply
    application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, moderation_handler))

    # welcome / profanity / anti-flood
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, profanity_and_flood_handler))

    application.add_error_handler(error_handler)
    return application

application = build_app()

# ----------------- Flask webhook endpoints -----------------
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

# ----------------- Run -----------------
def run():
    # if HOSTNAME set, configure webhook
    if HOSTNAME:
        webhook_url = f"https://{HOSTNAME}/{BOT_TOKEN}"
        logger.info("Setting webhook to %s", webhook_url)
        try:
            # set webhook synchronously
            import asyncio
            asyncio.run(application.bot.set_webhook(webhook_url))
        except Exception:
            logger.exception("Failed to set webhook (maybe already set)")

    # run Flask in thread
    flask_thread = Thread(target=lambda: flask_app.run(host="0.0.0.0", port=PORT))
    flask_thread.start()

    # run telegram app (uses update_queue for webhook mode)
    application.run_polling()

if __name__ == "__main__":
    run()