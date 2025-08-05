#!/usr/bin/env python3
# main.py — MultiBotX (polling + Flask health) — PTB v20 compatible

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
from flask import Flask
from dotenv import load_dotenv
from telegram import Update, ChatPermissions
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# -- load .env for local dev (Render uses Environment vars) --
load_dotenv()

# ---------------- Config ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")  # optional (we're using polling)
SAVETUBE_KEY = os.getenv("SAVETUBE_KEY")  # optional
PORT = int(os.getenv("PORT", 5000))
MAX_SEND_BYTES = 50 * 1024 * 1024  # 50 MB threshold

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set. Add it to Render Environment variables.")

# ---------------- Logging ----------------
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger("MultiBotX")

# ---------------- Storage ----------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DONKE_FILE = DATA_DIR / "donke.json"

def load_json(p: Path):
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to load JSON %s", p)
    return {}

def save_json(p: Path, data):
    try:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logger.exception("Failed to save JSON %s", p)

donke_db = load_json(DONKE_FILE)

# ---------------- Content ----------------
JOKES = [
    "Почему программисты путают Хэллоуин и Рождество? OCT 31 == DEC 25.",
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
    "Кошки спят до 20 часов в день.",
    "Мёд не портится."
]
QUOTES = [
    "«Лучший способ начать — просто начать.»",
    "«Ошибки — это доказательство попыток.»"
]
BAD_WORDS = ["бляд", "хуй", "пизд", "сука", "мраз"]  # расширяй по желанию

# ---------------- yt_dlp helper ----------------
YTDL_OPTS = {
    "format": "mp4[ext=mp4]/best",
    "outtmpl": "tmp_video.%(ext)s",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
}

def download_with_yt_dlp(url: str) -> str:
    with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

# ---------------- Utilities ----------------
def today_iso() -> str:
    return datetime.utcnow().date().isoformat()

def safe_remove(path: str):
    try:
        os.remove(path)
    except Exception:
        pass

# ---------------- Flask (health) ----------------
flask_app = Flask(__name__)

@flask_app.route("/", methods=["GET"])
def index():
    return "MultiBotX is running (polling mode)."

# ---------------- Handlers (Telegram) ----------------

# Start / Menu
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Я MultiBotX. /menu — главное меню.")

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 Меню MultiBotX:\n\n"
        "Развлечения:\n"
        "/joke, /fact, /quote, /cat, /dog, /meme, /dice\n\n"
        "Donke:\n"
        "/donke — шутка\n"
        "/camdonke — залить в Donke (раз в сутки)\n"
        "/topdonke — топ 50\n\n"
        "Видео: пришли ссылку на YouTube/TikTok — бот попробует скачать.\n\n"
        "Модерация: ответь на сообщение и напиши: варн / мут / размут / бан / анбан"
    )
    await update.message.reply_text(text)

# Entertainment
async def joke_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(JOKES))

async def donke_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(DONKE_PHRASES))

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

# Donke (camdonke / topdonke)
async def camdonke_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)
    entry = donke_db.get(uid, {"name": user.full_name, "total": 0, "last": None})
    if entry.get("last") == today_iso():
        await update.message.reply_text("❗ Сегодня вы уже заливали — заходите завтра.")
        return
    amount = random.randint(1, 100)
    entry["total"] = entry.get("total", 0) + amount
    entry["last"] = today_iso()
    entry["name"] = user.full_name
    donke_db[uid] = entry
    save_json(DONKE_FILE, donke_db)
    await update.message.reply_text(f"💦 Вы успешно залили в Donke {amount} литров! Приходите завтра.")

async def topdonke_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not donke_db:
        await update.message.reply_text("Пока никто не заливал.")
        return
    sorted_list = sorted(donke_db.items(), key=lambda kv: kv[1].get("total", 0), reverse=True)[:50]
    lines = ["🏆 Топ Donke:"]
    for i, (uid, e) in enumerate(sorted_list, 1):
        name = e.get("name", f"@{uid}")
        total = e.get("total", 0)
        lines.append(f"{i}. {name} — {total} л")
    await update.message.reply_text("\n".join(lines))

# Moderation (reply text: "варн", "мут", "бан", "размут", "анбан")
async def moderation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.reply_to_message:
        return
    cmd = msg.text.strip().lower()
    target = msg.reply_to_message.from_user
    chat = msg.chat

    # проверим права модератора
    try:
        member = await chat.get_member(msg.from_user.id)
        if not (member.status in ("administrator", "creator") or member.can_restrict_members):
            await msg.reply_text("У вас нет прав модератора.")
            return
    except Exception:
        logger.exception("Can't check member status")

    if "варн" in cmd:
        ctx_warns = context.bot_data.setdefault("warns", {})
        ctx_warns[target.id] = ctx_warns.get(target.id, 0) + 1
        await msg.reply_text(f"⚠️ {target.full_name} получил предупреждение ({ctx_warns[target.id]}).")
        if ctx_warns[target.id] >= 3:
            await chat.ban_member(target.id)
            await msg.reply_text(f"🚫 {target.full_name} забанен за 3 предупреждения.")
            ctx_warns[target.id] = 0
    elif "мут" in cmd:
        until = datetime.utcnow() + timedelta(minutes=10)
        try:
            await chat.restrict_member(target.id, ChatPermissions(can_send_messages=False), until_date=until)
            await msg.reply_text(f"🔇 {target.full_name} замучен на 10 минут.")
        except Exception:
            logger.exception("Mute failed")
    elif cmd in ("размут", "анмут"):
        try:
            await chat.restrict_member(target.id, ChatPermissions(can_send_messages=True))
            await msg.reply_text(f"🔊 {target.full_name} размучен.")
        except Exception:
            logger.exception("Unmute failed")
    elif "бан" in cmd:
        try:
            await chat.ban_member(target.id)
            await msg.reply_text(f"🚫 {target.full_name} забанен.")
        except Exception:
            logger.exception("Ban failed")
    elif cmd in ("разбан", "унбан", "анбан"):
        try:
            await chat.unban_member(target.id)
            await msg.reply_text(f"✅ {target.full_name} разбанен.")
        except Exception:
            logger.exception("Unban failed")

# Welcome / profanity / anti-flood
LAST_MSG = {}  # {(chat_id,user_id): [timestamps]}

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
    key = (msg.chat.id, msg.from_user.id)
    now_ts = datetime.utcnow().timestamp()
    arr = LAST_MSG.get(key, [])
    arr = [t for t in arr if now_ts - t < 10]
    arr.append(now_ts)
    LAST_MSG[key] = arr
    if len(arr) > 6:
        try:
            await msg.chat.restrict_member(msg.from_user.id, ChatPermissions(can_send_messages=False),
                                           until_date=datetime.utcnow() + timedelta(minutes=1))
            await msg.reply_text("🤐 Антифлуд: замучен на 1 минуту.")
        except Exception:
            pass

# Download handler (command or plain URL)
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
    status_msg = await update.message.reply_text("⏬ Пытаюсь скачать видео (это займет время)...")
    try:
        # If TikTok and SaveTube key available — try SaveTube API first
        if "tiktok.com" in url and SAVETUBE_KEY:
            try:
                headers = {"X-RapidAPI-Key": SAVETUBE_KEY}
                api = "https://save-tube-video-download.p.rapidapi.com/download"
                r = requests.get(api, headers=headers, params={"url": url}, timeout=15)
                j = r.json()
                if isinstance(j, dict) and j.get("links"):
                    vid_url = j["links"][0].get("url")
                    if vid_url:
                        await update.message.reply_video(vid_url)
                        await status_msg.delete()
                        return
            except Exception:
                logger.exception("SaveTube failed, fallback to yt_dlp")
        # fallback to yt_dlp for any supported URL
        fname = download_with_yt_dlp(url)
        size = os.path.getsize(fname)
        if size > MAX_SEND_BYTES:
            await update.message.reply_text("Видео слишком большое для отправки (больше 50 MB).")
            safe_remove(fname)
            await status_msg.delete()
            return
        with open(fname, "rb") as f:
            await update.message.reply_video(f)
        safe_remove(fname)
        await status_msg.delete()
    except Exception as e:
        logger.exception("Download error: %s", e)
        try:
            await status_msg.edit_text("❌ Не удалось скачать видео. Попробуйте другую ссылку.")
        except Exception:
            pass

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Handler error: %s", context.error)
    try:
        tb = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
        logger.error(tb)
    except Exception:
        pass

# ---------------- Build application ----------------
def build_application():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # commands
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("menu", menu_handler))
    application.add_handler(CommandHandler("joke", joke_handler))
    application.add_handler(CommandHandler("donke", donke_handler))
    application.add_handler(CommandHandler("camdonke", camdonke_handler))
    application.add_handler(CommandHandler("topdonke", topdonke_handler))
    application.add_handler(CommandHandler("fact", fact_handler))
    application.add_handler(CommandHandler("quote", quote_handler))
    application.add_handler(CommandHandler("cat", cat_handler))
    application.add_handler(CommandHandler("dog", dog_handler))
    application.add_handler(CommandHandler("meme", meme_handler))
    application.add_handler(CommandHandler("dice", dice_handler))
    application.add_handler(CommandHandler("download", download_handler))

    # message handlers
    application.add_handler(MessageHandler(filters.Regex(r"https?://"), download_handler))
    application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, moderation_handler))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, profanity_and_flood_handler))

    application.add_error_handler(error_handler)
    return application

application = build_application()

# ---------------- Run (polling + Flask health) ----------------
def run():
    # Flask for health (listening port for Render)
    thread = Thread(target=lambda: flask_app.run(host="0.0.0.0", port=PORT))
    thread.start()

    # run polling for PTB
    application.run_polling()

if __name__ == "__main__":
    run()