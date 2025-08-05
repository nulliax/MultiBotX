#!/usr/bin/env python3
# main.py — MultiBotX (upgraded, polling + Flask health)
# Requirements: python-telegram-bot>=21.0, Flask, requests, yt_dlp, python-dotenv

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
from telegram import (
    Update,
    ChatPermissions,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Local .env for dev only (do not commit .env with secrets)
load_dotenv()

# ---------------- Config ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME", "")
SAVETUBE_KEY = os.getenv("SAVETUBE_KEY", None)  # optional
PORT = int(os.getenv("PORT", 5000))
MAX_SEND_BYTES = int(os.getenv("MAX_SEND_BYTES", 50 * 1024 * 1024))  # 50 MB default
COMMANDS_SETUP = True  # set bot commands on startup

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set. Add it to Environment variables on Render.")

# ---------------- Logging ----------------
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger("MultiBotX")

# ---------------- Storage ----------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DONKE_FILE = DATA_DIR / "donke.json"
JOKES_FILE = DATA_DIR / "jokes.json"
USAGE_FILE = DATA_DIR / "usage.json"

def load_json(path: Path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to load JSON %s", path)
    return {}

def save_json(path: Path, data):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logger.exception("Failed to save JSON %s", path)

donke_db = load_json(DONKE_FILE)
joke_db = load_json(JOKES_FILE) or []
usage_db = load_json(USAGE_FILE) or {}

# initial joke list if empty
if not joke_db:
    joke_db.extend([
        "Почему программисты путают Хэллоуин и Рождество? OCT 31 == DEC 25.",
        "Я бы рассказал шутку про UDP, но не уверен, что ты её получишь.",
        "Debugging: превращение багов в фичи."
    ])
    save_json(JOKES_FILE, joke_db)

# ---------------- Content banks (expanded) ----------------
FACTS = [
    "У осьминога три сердца.",
    "Кошки могут спать до 20 часов в день.",
    "Мёд не портится."
]

QUOTES = [
    "«Лучший способ предсказать будущее — создать его.»",
    "«Действуй — пока другие мечтают.»",
    "«Ошибка — это шанс сделать лучше.»"
]

BAD_WORDS = ["бляд", "хуй", "пизд", "сука", "мраз"]  # расширяй по желанию

# ---------------- yt_dlp helper ----------------
YTDL_COMMON = {
    "format": "bestvideo+bestaudio/best",
    "outtmpl": "tmp_video.%(ext)s",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "ignoreerrors": True,
    "cachedir": False,
}

def yt_download_file(url: str, audio_only: bool = False) -> Optional[str]:
    """
    Downloads media via yt_dlp.
    If audio_only True tries to extract audio (may need ffmpeg).
    Returns path to file or None.
    """
    opts = dict(YTDL_COMMON)
    if audio_only:
        # prefer best audio and try to convert to mp3 (requires ffmpeg)
        opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "outtmpl": "tmp_audio.%(ext)s",
        })
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # if audio_only and postprocessor converted -> extension may be mp3
            # try to find resulting file
            if audio_only:
                possible = [p for p in Path(".").glob("tmp_audio.*")]
                if possible:
                    return str(possible[0])
            return filename
    except Exception:
        logger.exception("yt_dlp download failed for %s (audio_only=%s)", url, audio_only)
        return None

# ---------------- Utilities ----------------
def today_iso() -> str:
    return datetime.utcnow().date().isoformat()

def safe_remove(path: str):
    try:
        os.remove(path)
    except Exception:
        pass

def inc_usage(command: str):
    usage_db[command] = usage_db.get(command, 0) + 1
    save_json(USAGE_FILE, usage_db)

# ---------------- Flask health ----------------
app = Flask(__name__)
@app.route("/", methods=["GET"])
def home():
    return "MultiBotX is running."

# ---------------- Telegram handlers ----------------

# Setup bot commands (so users see them when typing '/')
async def set_commands_on_startup(app):
    try:
        commands = [
            BotCommand("start", "Приветствие"),
            BotCommand("menu", "Главное меню"),
            BotCommand("joke", "Шутка"),
            BotCommand("donke", "Шутка про Donke"),
            BotCommand("camdonke", "Залить в Donke (раз в сутки)"),
            BotCommand("topdonke", "Топ Donke"),
            BotCommand("meme", "Мем"),
            BotCommand("cat", "Фото кота"),
            BotCommand("dog", "Фото собаки"),
            BotCommand("dice", "Кубик"),
            BotCommand("download", "Скачать видео/аудио по ссылке"),
            BotCommand("searchimage", "Поиск изображения"),
            BotCommand("trivia", "Случайный факт/вопрос"),
            BotCommand("stats", "Статистика (админы)"),
            BotCommand("addjoke", "Добавить шутку"),
        ]
        await app.bot.set_my_commands(commands)
        logger.info("Commands set")
    except Exception:
        logger.exception("Failed to set commands")

# Start & menu
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("start")
    await update.message.reply_text("👋 Привет! Я MultiBotX. Напиши /menu чтобы увидеть функции.")

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("menu")
    text = (
        "📋 *Меню MultiBotX*\n\n"
        "Развлечения:\n"
        "/joke /fact /quote /cat /dog /meme /dice\n\n"
        "Donke:\n"
        "/donke /camdonke /topdonke\n\n"
        "Видео:\n"
        "/download <url> или просто отправь ссылку — появится выбор: Видео / Аудио\n\n"
        "Прочее:\n"
        "/searchimage <запрос> — найти картинку\n"
        "/trivia — факт/вопрос\n"
        "/stats — статистика (админы)\n"
    )
    await update.message.reply_text(text)

# Entertainment
async def joke_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("joke")
    await update.message.reply_text(random.choice(joke_db))

async def addjoke_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("addjoke")
    text = " ".join(context.args) if context.args else (update.message.text or "")
    # expected: /addjoke some joke here
    if not text:
        await update.message.reply_text("Использование: /addjoke ТЕКСТ_ШУТКИ")
        return
    # remove command part if exists
    if text.lower().startswith("/addjoke"):
        text = text[len("/addjoke"):].strip()
    joke_db.append(text)
    save_json(JOKES_FILE, joke_db)
    await update.message.reply_text("Добавил шутку — спасибо!")

async def donke_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("donke")
    await update.message.reply_text(random.choice(["Donke легенда.", "Donke в деле.", "Donke forever."]))

async def camdonke_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("camdonke")
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
    inc_usage("topdonke")
    if not donke_db:
        await update.message.reply_text("Пока никто не заливал.")
        return
    sorted_list = sorted(donke_db.items(), key=lambda kv: kv[1].get("total", 0), reverse=True)[:50]
    lines = ["🏆 Топ Donke:"]
    for i, (uid, e) in enumerate(sorted_list, 1):
        lines.append(f"{i}. {e.get('name','?')} — {e.get('total',0)} л")
    await update.message.reply_text("\n".join(lines))

async def fact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("fact")
    await update.message.reply_text(random.choice(FACTS))

async def quote_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("quote")
    await update.message.reply_text(random.choice(QUOTES))

async def cat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("cat")
    try:
        r = requests.get("https://api.thecatapi.com/v1/images/search", timeout=10).json()
        await update.message.reply_photo(r[0]["url"])
    except Exception:
        await update.message.reply_text("Не удалось получить фото котика.")

async def dog_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("dog")
    try:
        r = requests.get("https://dog.ceo/api/breeds/image/random", timeout=10).json()
        await update.message.reply_photo(r["message"])
    except Exception:
        await update.message.reply_text("Не удалось получить фото собаки.")

async def meme_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("meme")
    try:
        r = requests.get("https://meme-api.com/gimme", timeout=10).json()
        await update.message.reply_photo(r["url"], caption=r.get("title", "Мем"))
    except Exception:
        await update.message.reply_text("Не удалось получить мем.")

async def dice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("dice")
    await update.message.reply_dice()

# trivia
TRIVIA = [
    "Сколько сердец у осьминога? — Три.",
    "Какой язык программирования назван в честь змеи? — Python.",
]
async def trivia_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("trivia")
    await update.message.reply_text(random.choice(TRIVIA))

# search image (simple unsplash source)
async def searchimage_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("searchimage")
    query = " ".join(context.args) if context.args else None
    if not query:
        await update.message.reply_text("Использование: /searchimage <запрос>")
        return
    try:
        # unsplash source allows simple random images without API key
        url = f"https://source.unsplash.com/800x600/?{requests.utils.requote_uri(query)}"
        await update.message.reply_photo(url)
    except Exception:
        await update.message.reply_text("Не удалось найти изображение.")

# stats (admin)
async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # only chat owner / specific id allowed — for simplicity, allow user id match ENV ADMIN_ID or chat creator
    ADMIN_ID = os.getenv("ADMIN_ID")
    if ADMIN_ID and str(user.id) != str(ADMIN_ID):
        await update.message.reply_text("Недостаточно прав.")
        return
    inc_usage("stats")
    lines = ["📊 Статистика использования:"]
    for k, v in sorted(usage_db.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"{k}: {v}")
    await update.message.reply_text("\n".join(lines) if len(lines) > 1 else "Пока нет статистики.")

# moderation (reply-based commands without /)
async def moderation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.reply_to_message:
        return
    cmd = (msg.text or "").strip().lower()
    target = msg.reply_to_message.from_user
    chat = msg.chat
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

# welcome/profanity/anti-flood
LAST_MSG = {}
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
    # flood simple
    key = (msg.chat.id, msg.from_user.id)
    now = datetime.utcnow().timestamp()
    arr = LAST_MSG.get(key, [])
    arr = [t for t in arr if now - t < 10]
    arr.append(now)
    LAST_MSG[key] = arr
    if len(arr) > 6:
        try:
            await msg.chat.restrict_member(msg.from_user.id, ChatPermissions(can_send_messages=False),
                                           until_date=datetime.utcnow() + timedelta(minutes=1))
            await msg.reply_text("🤐 Антифлуд: замучен на 1 минуту.")
        except Exception:
            pass

# Download flow:
# - User can run /download <url> OR just send a message with URL
# - Bot replies with inline buttons: "Видео", "Аудио"
# - On callback query, bot downloads (yt_dlp) and sends file (or link if too big)
async def make_download_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("download_prompt")
    # extract first URL
    text = None
    if context.args:
        text = context.args[0]
    elif update.message and update.message.text:
        m = re.search(r"https?://\S+", update.message.text)
        if m:
            text = m.group(0)
    if not text:
        await update.message.reply_text("Пришлите ссылку на видео (YouTube/TikTok и т.д.) или используйте /download <url>")
        return
    url = text.strip()
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📹 Видео", callback_data=f"dl|video|{url}"),
        InlineKeyboardButton("🎧 Аудио", callback_data=f"dl|audio|{url}")
    ]])
    await update.message.reply_text("Выберите формат для скачивания:", reply_markup=keyboard)

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # acknowledge
    data = query.data or ""
    if not data.startswith("dl|"):
        return
    try:
        _, kind, url = data.split("|", 2)
    except ValueError:
        await query.edit_message_text("Неправильные данные.")
        return

    # inform user
    msg = await query.edit_message_text("⏬ Начинаю скачивание... Это может занять время.")
    # attempt SaveTube for TikTok audio/video if key present and kind=video
    file_path = None
    try:
        if "tiktok.com" in url and SAVETUBE_KEY and kind == "video":
            try:
                headers = {"X-RapidAPI-Key": SAVETUBE_KEY}
                api = "https://save-tube-video-download.p.rapidapi.com/download"
                r = requests.get(api, headers=headers, params={"url": url}, timeout=15)
                j = r.json()
                if isinstance(j, dict) and j.get("links"):
                    vid_url = j["links"][0].get("url")
                    if vid_url:
                        # send direct url if smaller than limit (we don't know size) — try to send as video
                        await context.bot.send_video(chat_id=query.message.chat_id, video=vid_url)
                        await context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
                        return
            except Exception:
                logger.exception("SaveTube attempt failed, falling back to yt_dlp")

        # Use yt_dlp
        audio_only = (kind == "audio")
        file_path = yt_download_file(url, audio_only=audio_only)
        if not file_path:
            await context.bot.send_message(chat_id=query.message.chat_id, text="Не удалось скачать видео/аудио.")
            return

        size = os.path.getsize(file_path)
        if size > MAX_SEND_BYTES:
            await context.bot.send_message(chat_id=query.message.chat_id, text="Файл слишком большой для отправки. Попробуйте другую ссылку или скачайте локально.")
            safe_remove(file_path)
            return

        # send file
        with open(file_path, "rb") as fp:
            if audio_only:
                # try to send as audio or document fallback
                try:
                    await context.bot.send_audio(chat_id=query.message.chat_id, audio=fp)
                except Exception:
                    fp.seek(0)
                    await context.bot.send_document(chat_id=query.message.chat_id, document=fp)
            else:
                fp.seek(0)
                await context.bot.send_video(chat_id=query.message.chat_id, video=fp)
        safe_remove(file_path)
    except Exception:
        logger.exception("Error in callback download")
        try:
            await context.bot.send_message(chat_id=query.message.chat_id, text="Произошла ошибка при скачивании.")
        except Exception:
            pass

# Generic message handler: if contains URL -> show buttons
async def url_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    m = re.search(r"https?://\S+", text)
    if m:
        await make_download_buttons(update, context)
    els