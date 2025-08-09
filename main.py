#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# MultiBotX — consolidated, tested version (part 1/4)

import os
import logging
import random
import re
import json
import tempfile
import shutil
import asyncio
import uuid
from datetime import datetime, timedelta
from threading import Thread
from pathlib import Path

import requests
import yt_dlp
from flask import Flask
from dotenv import load_dotenv

from telegram import (
    Update,
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters,
)

# Load local .env for dev; on Render environment variables used automatically
load_dotenv()

# ---------------- Config ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
SAVE_TUBE_KEY = os.getenv("SAVE_TUBE_KEY")      # optional (RapidAPI for SaveTube)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")    # optional
ADMIN_ID = os.getenv("ADMIN_ID")                # optional admin id (string)
MAX_SEND_BYTES = int(os.getenv("MAX_SEND_BYTES", 50 * 1024 * 1024))  # default 50MB
COMMANDS_SETUP = os.getenv("COMMANDS_SETUP", "true").lower() in ("1", "true", "yes")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан. Установи BOT_TOKEN в переменных окружения.")

# ---------------- Logging ----------------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("MultiBotX")

# ---------------- Flask health ----------------
app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    return "MultiBotX is running"

# ---------------- Application (PTB) ----------------
# build application now (we will register handlers later)
application = ApplicationBuilder().token(BOT_TOKEN).build()# MultiBotX — part 2/4: storage, content pools, helpers

# ---------------- Storage ----------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DONKE_FILE = DATA_DIR / "donke.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

def load_json(path: Path):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("load_json failed: %s", path)
    return {}

def save_json(path: Path, data):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logger.exception("save_json failed: %s", path)

donke_db = load_json(DONKE_FILE)
settings = load_json(SETTINGS_FILE) or {}
# default: antimat disabled
if "antimat_enabled" not in settings:
    settings["antimat_enabled"] = False
    save_json(SETTINGS_FILE, settings)

# ---------------- Content pools ----------------
JOKES = [
    "Почему программисты путают Хэллоуин и Рождество? OCT 31 == DEC 25.",
    "Я бы рассказал шутку про UDP — но не уверен, дошла ли она.",
    "Debugging: превращение багов в фичи.",
]
DONKE_JOKES = [
    "Donke пришёл и всё поменял — в хорошем смысле... иногда.",
    "Donke легенда, Donke мем.",
    "Donke — причина и следствие.",
]
FACTS = [
    "У осьминога три сердца.",
    "Кошки спят до 20 часов в день.",
    "Мёд не портится.",
]
QUOTES = [
    "«Делай, что должен.»",
    "«Лучше сделать и пожалеть, чем не сделать и жалеть.»",
]

BAD_WORDS = ["бляд", "хуй", "пизд", "сука", "мраз"]  # можно расширить

# ---------------- Helpers ----------------
def today_iso():
    return datetime.utcnow().date().isoformat()

async def run_blocking(func, *args, **kwargs):
    """Run blocking function in thread pool to avoid blocking the event loop."""
    return await asyncio.to_thread(func, *args, **kwargs)

def is_admin_user(update: Update) -> bool:
    """Quick admin check: either ADMIN_ID env or chat admin."""
    try:
        if ADMIN_ID and str(update.effective_user.id) == str(ADMIN_ID):
            return True
        # if in chat, check chat rights (best-effort; may raise in private)
        chat = update.effective_chat
        if chat and chat.get_member:
            member = asyncio.get_event_loop().run_until_complete(chat.get_member(update.effective_user.id))
            if member and (member.status in ("administrator", "creator") or getattr(member, "can_restrict_members", False)):
                return True
    except Exception:
        # fall back to False
        pass
    return False

# ---------------- Download sessions store ----------------
# temporary map request_id -> {'url':url, 'user_id':id, 'chat_id':chat_id}
DOWNLOAD_SESSIONS = {}# MultiBotX — part 3/4: core handlers (start/help/entertainment/donke/moderation/antimat)

# ---------- Basic / Menu ----------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🎲 Развлечения", callback_data="menu_fun")],
        [InlineKeyboardButton("📥 Скачать по ссылке", callback_data="menu_download")],
        [InlineKeyboardButton("👮 Модерация", callback_data="menu_mod")],
    ]
    await update.message.reply_text(
        "👋 Привет! Я MultiBotX. Нажми кнопку или /help для списка команд.",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 <b>Команды</b>\n\n"
        "/start — запустить бота\n"
        "/help — справка\n\n"
        "Развлечения: /joke /fact /quote /cat /dog /meme /dice\n"
        "Donke: /donke /camdonke /topdonke\n"
        "Видео: пришли ссылку или /download <url>\n"
        "Модерация: ответь на сообщение и напиши без '/': 'варн','мут','бан','размут','анбан'\n"
        "/antimat_on | /antimat_off — включить/выключить анти-мат (админ)\n"
        "/stats — простая статистика (админ)\n"
    )
    await update.message.reply_text(text, parse_mode="HTML")

# ---------- Entertainment ----------
async def joke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(JOKES))

async def fact_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(FACTS))

async def quote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(QUOTES))

async def meme_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = await run_blocking(requests.get, "https://meme-api.com/gimme", timeout=10)
        j = r.json()
        url = j.get("url")
        title = j.get("title", "Мем")
        if url:
            await update.message.reply_photo(url, caption=title)
        else:
            await update.message.reply_text("Не удалось получить мем.")
    except Exception:
        logger.exception("meme_cmd failed")
        await update.message.reply_text("Ошибка при получении мема.")

async def cat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = await run_blocking(requests.get, "https://api.thecatapi.com/v1/images/search", timeout=10)
        j = r.json()
        if isinstance(j, list) and j:
            await update.message.reply_photo(j[0]["url"])
        else:
            await update.message.reply_text("Не удалось получить кота.")
    except Exception:
        logger.exception("cat_cmd failed")
        await update.message.reply_text("Ошибка при получении кота.")

async def dog_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = await run_blocking(requests.get, "https://dog.ceo/api/breeds/image/random", timeout=10)
        j = r.json()
        await update.message.reply_photo(j.get("message"))
    except Exception:
        logger.exception("dog_cmd failed")
        await update.message.reply_text("Ошибка при получении собаки.")

async def dice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_dice()

# ---------- Donke ----------
async def donke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(DONKE_JOKES))

async def camdonke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)
    entry = donke_db.get(uid, {"name": user.full_name, "total": 0, "last": None})
    if entry.get("last") == today_iso():
        await update.message.reply_text("Сегодня уже заливали — приходи завтра.")
        return
    amount = random.randint(1, 100)
    entry["total"] = entry.get("total", 0) + amount
    entry["last"] = today_iso()
    entry["name"] = user.full_name
    donke_db[uid] = entry
    save_json(DONKE_FILE, donke_db)
    await update.message.reply_text(f"💦 Вы успешно залили в Donke {amount} л. Приходите завтра!")

async def topdonke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not donke_db:
        await update.message.reply_text("Пока никто не заливал.")
        return
    lst = sorted(donke_db.items(), key=lambda kv: kv[1].get("total", 0), reverse=True)[:50]
    lines = []
    for i, (uid, info) in enumerate(lst, 1):
        name = info.get("name", f"@{uid}")
        total = info.get("total", 0)
        lines.append(f"{i}. {name} — {total} л")
    await update.message.reply_text("\n".join(lines))

# ---------- Moderation commands (slash) ----------
async def warn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("Ответь на сообщение, чтобы выдать предупреждение.")
    target = update.message.reply_to_message.from_user
    warns = context.bot_data.get("warns", {})
    warns[target.id] = warns.get(target.id, 0) + 1
    context.bot_data["warns"] = warns
    await update.message.reply_text(f"⚠️ {target.full_name} получил предупреждение ({warns[target.id]}).")
    if warns[target.id] >= 3:
        try:
            await update.effective_chat.ban_member(target.id)
            await update.message.reply_text("🚫 Пользователь забанен (3 предупреждения).")
            warns[target.id] = 0
            context.bot_data["warns"] = warns
        except Exception:
            await update.message.reply_text("Не могу забанить — недостаточно прав.")

async def mute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("Ответь на сообщение, чтобы замутить.")
    target = update.message.reply_to_message.from_user
    try:
        until = datetime.utcnow() + timedelta(minutes=30)
        await update.effective_chat.restrict_member(target.id, permissions=ChatPermissions(can_send_messages=False), until_date=until)
        await update.message.reply_text(f"🔇 {target.full_name} замучен на 30 минут.")
    except Exception:
        await update.message.reply_text("Не удалось замутить — недостаточно прав.")

async def unmute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("Ответь на сообщение, чтобы размутить.")
    target = update.message.reply_to_message.from_user
    try:
        await update.effective_chat.restrict_member(target.id, permissions=ChatPermissions(can_send_messages=True))
        await update.message.reply_text(f"🔊 {target.full_name} размучен.")
    except Exception:
        await update.message.reply_text("Не удалось размучить — недостаточно прав.")

async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("Ответь на сообщение, чтобы забанить.")
    target = update.message.reply_to_message.from_user
    try:
        await update.effective_chat.ban_member(target.id)
        await update.message.reply_text(f"🚫 {target.full_name} забанен.")
    except Exception:
        await update.message.reply_text("Не удалось забанить — недостаточно прав.")

async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("Ответь на сообщение, чтобы разбанить.")
    target = update.message.reply_to_message.from_user
    try:
        await update.effective_chat.unban_member(target.id)
        await update.message.reply_text(f"✅ {target.full_name} разбанен.")
    except Exception:
        await update.message.reply_text("Не удалось разбанить — недостаточно прав.")

# ---------- Reply-moderation without slash ----------
async def reply_moderation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.reply_to_message or not update.message.text:
        return
    txt = update.message.text.lower().strip()
    if txt in ("варн", "warn"):
        await warn_cmd(update, context)
    elif txt in ("мут", "mute"):
        await mute_cmd(update, context)
    elif txt in ("размут", "анмут", "unmute"):
        await unmute_cmd(update, context)
    elif txt in ("бан", "ban"):
        await ban_cmd(update, context)
    elif txt in ("разбан", "анбан", "унбан", "unban"):
        await unban_cmd(update, context)

# ---------- Antimat toggle ----------
async def antimat_on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_user(update):
        return await update.message.reply_text("Только админ может включать анти-мат.")
    settings["antimat_enabled"] = True
    save_json(SETTINGS_FILE, settings)
    await update.message.reply_text("Анти-мат включён.")

async def antimat_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_user(update):
        return await update.message.reply_text("Только админ может выключать анти-мат.")
    settings["antimat_enabled"] = False
    save_json(SETTINGS_FILE, settings)
    await update.message.reply_text("Анти-мат выключён.")# MultiBotX — part 4/4: downloads (yt_dlp), callback handling, AI, registration, main

# ---------- yt_dlp helpers ----------
YTDL_OPTS_BASE = {
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
}

def yt_download_sync(url: str, audio: bool = False) -> str:
    """Blocking download via yt_dlp. Returns path to downloaded file."""
    tmpdir = tempfile.mkdtemp(prefix="multibotx_")
    opts = YTDL_OPTS_BASE.copy()
    if audio:
        # prefer best audio; try mp3 extraction if ffmpeg present
        opts["format"] = "bestaudio/best"
        # attempt to extract to mp3 if ffmpeg exists
        opts["outtmpl"] = os.path.join(tmpdir, "%(id)s.%(ext)s")
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        opts["format"] = "mp4[ext=mp4]/best"
        opts["outtmpl"] = os.path.join(tmpdir, "%(id)s.%(ext)s")
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # If postprocessor changed extension to mp3, find mp3 file
        if audio:
            # look for mp3 file (postprocessor may produce .mp3)
            base = os.path.splitext(filename)[0]
            possible = [base + ".mp3", filename]
            for p in possible:
                if os.path.exists(p):
                    return p
        return filename

# ---------- Download flow ----------
async def prompt_download_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered on plain message with URL or /download <url>"""
    text = None
    if context.args:
        text = context.args[0]
    elif update.message and update.message.text:
        m = re.search(r"https?://\S+", update.message.text)
        if m:
            text = m.group(0)
    if not text:
        return
    # create session id, store url with requesting user
    req_id = str(uuid.uuid4())
    DOWNLOAD_SESSIONS[req_id] = {
        "url": text,
        "user_id": update.effective_user.id,
        "chat_id": update.effective_chat.id if update.effective_chat else None,
    }
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📹 Скачать видео", callback_data=f"dl|{req_id}|video"),
         InlineKeyboardButton("🔊 Скачать аудио", callback_data=f"dl|{req_id}|audio")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"dl|{req_id}|cancel")]
    ])
    await update.message.reply_text("Выбери формат для скачивания:", reply_markup=kb)

async def download_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()  # acknowledge quickly
    try:
        parts = query.data.split("|")
        if len(parts) != 3:
            return await query.edit_message_text("Неверный формат запроса.")
        _prefix, req_id, action = parts
        session = DOWNLOAD_SESSIONS.pop(req_id, None)
        if not session:
            return await query.edit_message_text("Сессия не найдена или истекла.")
        if session.get("user_id") != query.from_user.id:
            return await query.edit_message_text("Только пользователь, запросивший скачивание, может выбирать формат.")
        url = session.get("url")
        msg = await query.edit_message_text("⏬ Скачиваю — это может занять время...")
        # download
        if action == "cancel":
            return await query.edit_message_text("Отменено.")
        audio = (action == "audio")
        try:
            fname = await run_blocking(yt_download_sync, url, audio)
        except Exception:
            logger.exception("yt_dlp failed")
            return await query.edit_message_text("Ошибка при скачивании (yt_dlp).")
        size = os.path.getsize(fname) if os.path.exists(fname) else 0
        if size > MAX_SEND_BYTES:
            # cleanup and send link
            try:
                os.remove(fname)
                shutil.rmtree(os.path.dirname(fname), ignore_errors=True)
            except Exception:
                pass
            await query.edit_message_text("Файл слишком большой для отправки. Я оставлю ссылку на источник.")
            await context.bot.send_message(chat_id=session.get("chat_id"), text=f"Источник: {url}")
            return
        # send file
        try:
            with open(fname, "rb") as f:
                if audio:
                    await context.bot.send_audio(chat_id=session.get("chat_id"), audio=f)
                else:
                    await context.bot.send_video(chat_id=session.get("chat_id"), video=f)
        finally:
            try:
                os.remove(fname)
                shutil.rmtree(os.path.dirname(fname), ignore_errors=True)
            except Exception:
                pass
        await query.edit_message_text("Готово ✅")
    except Exception:
        logger.exception("download_callback_handler error")
        try:
            await query.edit_message_text("Произошла ошибка при обработке запроса.")
        except Exception:
            pass

# ---------- AI command (optional) ----------
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

def call_openai(prompt: str, model: str = "gpt-3.5-turbo", max_tokens: int = 512) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0.8}
    r = requests.post(OPENAI_CHAT_URL, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    j = r.json()
    return j["choices"][0]["message"]["content"].strip()

async def ai_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not OPENAI_API_KEY:
        return await update.message.reply_text("AI не настроен. Добавь OPENAI_API_KEY.")
    prompt = " ".join(context.args) if context.args else ""
    if not prompt:
        return await update.message.reply_text("Использование: /ai <вопрос>")
    await update.message.reply_text("🤖 Думаю...")
    try:
        res = await run_blocking(call_openai, prompt)
        for i in range(0, len(res), 3900):
            await update.message.reply_text(res[i:i+3900])
    except Exception:
        logger.exception("AI call failed")
        await update.message.reply_text("Ошибка при вызове AI.")

# ---------- Stats (admin) ----------
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID and str(update.effective_user.id) != str(ADMIN_ID):
        return await update.message.reply_text("Только админ может вызвать статистику.")
    total = len(donke_db)
    await update.message.reply_text(f"Donke entries: {total}")

# ---------- Error handler ----------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled error: %s", context.error)

# ---------- Setup bot commands on startup ----------
async def setup_bot_commands(application):
    if not COMMANDS_SETUP:
        return
    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("help", "Справка"),
        BotCommand("joke", "Шутка"),
        BotCommand("fact", "Факт"),
        BotCommand("quote", "Цитата"),
        BotCommand("cat", "Фото кота"),
        BotCommand("dog", "Фото собаки"),
        BotCommand("meme", "Мем"),
        BotCommand("dice", "Кубик"),
        BotCommand("donke", "Donke шутка"),
        BotCommand("camdonke", "Залить в Donke"),
        BotCommand("topdonke", "Топ Donke"),
        BotCommand("download", "Скачать видео по ссылке"),
        BotCommand("ai", "AI (если настроен)"),
        BotCommand("antimat_on", "Включить анти-мат (админ)"),
        BotCommand("antimat_off", "Выключить анти-мат (админ)"),
        BotCommand("stats", "Статистика (админ)"),
    ]
    try:
        await application.bot.set_my_commands(commands)
        logger.info("Bot commands registered.")
    except Exception:
        logger.exception("Failed to register commands.")

# ---------- Register handlers ----------
def register_handlers():
    # Commands
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("joke", joke_cmd))
    application.add_handler(CommandHandler("fact", fact_cmd))
    application.add_handler(CommandHandler("quote", quote_cmd))
    application.add_handler(CommandHandler("meme", meme_cmd))
    application.add_handler(CommandHandler("cat", cat_cmd))
    application.add_handler(CommandHandler("dog", dog_cmd))
    application.add_handler(CommandHandler("dice", dice_cmd))
    application.add_handler(CommandHandler("donke", donke_cmd))
    application.add_handler(CommandHandler("camdonke", camdonke_cmd))
    application.add_handler(CommandHandler("topdonke", topdonke_cmd))
    application.add_handler(CommandHandler("warn", warn_cmd))
    application.add_handler(CommandHandler("mute", mute_cmd))
    application.add_handler(CommandHandler("unmute", unmute_cmd))
    application.add_handler(CommandHandler("ban", ban_cmd))
    application.add_handler(CommandHandler("unban", unban_cmd))
    application.add_handler(CommandHandler("download", prompt_download_choice))
    application.add_handler(CommandHandler("ai", ai_cmd))
    application.add_handler(CommandHandler("stats", stats_cmd))
    application.add_handler(CommandHandler("antimat_on", antimat_on_cmd))
    application.add_handler(CommandHandler("antimat_off", antimat_off_cmd))

    # Callbacks for download choices
    application.add_handler(CallbackQueryHandler(download_callback_handler, pattern=r"^dl\|"))

    # URL auto-catch
    application.add_handler(MessageHandler(filters.Regex(r"https?://"), prompt_download_choice))

    # Reply moderation (no slash)
    application.add_handler(MessageHandler(
        filters.Regex(r"^(варн|мут|размут|анмут|бан|разбан|анбан|унбан|warn|mute|unmute|ban|unban)$") & filters.REPLY,
        reply_moderation_handler))

    # Auto filters (anti-mat & anti-flood) — only run if antimat enabled
    async def auto_filters_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if settings.get("antimat_enabled", False):
            await auto_filters_inner(update, context)

    # define inner anti-flood/mat function
    LAST_MSG = {}
    async def auto_filters_inner(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return
        msg = update.message
        text = msg.text.lower()
        # profanity
        for bad in BAD_WORDS:
            if bad in text:
                try:
                    await msg.delete()
                    await msg.reply_text("⚠️ Пожалуйста, не ругайтесь.")
                except Exception:
                    pass
                return
        # flood
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
                await msg.reply_text("Антифлуд: замучен на 1 минуту.")
            except Exception:
                pass

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_filters_wrapper))

    # Error handler
    application.add_error_handler(error_handler)

# ---------- Main ----------
def main():
    register_handlers()
    # set post_init to register commands after event loop started
    async def on_startup(app):
        await setup_bot_commands(app)
    application.post_init = on_startup

    # Flask health endpoint in background thread
    flask_thread = Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))), daemon=True)
    flask_thread.start()

    logger.info("Starting polling...")
    application.run_polling(allowed_updates=None)

if __name__ == "__main__":
    main()