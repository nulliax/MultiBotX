#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# MultiBotX — part 1/7: imports, config, flask health

import os
import logging
import random
import re
import json
import tempfile
import shutil
import asyncio
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
    filters,
)

# Load .env locally; Render uses Environment variables set in dashboard
load_dotenv()

# ------------- Config -------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
SAVE_TUBE_KEY = os.getenv("SAVE_TUBE_KEY")        # optional RapidAPI SaveTube key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")      # optional OpenAI key
MAX_SEND_BYTES = int(os.getenv("MAX_SEND_BYTES", 50 * 1024 * 1024))  # bytes
COMMANDS_SETUP = os.getenv("COMMANDS_SETUP", "true").lower() in ("1", "true", "yes")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Add it to environment variables.")

# ------------- Logging -------------
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    level=logging.INFO)
logger = logging.getLogger("MultiBotX")

# ------------- Flask health -------------
app = Flask(__name__)

@app.route("/", methods=["GET"])
def healthcheck():
    return "MultiBotX is running"# MultiBotX — part 2/7: app, storage, content, helpers

# Telegram application (will be built later)
application = ApplicationBuilder().token(BOT_TOKEN).build()

# Data directory and files
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DONKE_FILE = DATA_DIR / "donke.json"

def load_json(path: Path):
    try:
        if path.exists():
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

# Content pools (expandable)
JOKES = [
    "Почему программисты путают Хэллоуин и Рождество? OCT 31 == DEC 25.",
    "Я бы рассказал шутку про UDP — но не уверен, что она дошла.",
    "Debugging: превращение багов в фичи.",
]
DONKE_PHRASES = [
    "Donke вошёл в чат и всё пошло по-плану.",
    "Donke — живой мем.",
    "Donke сделал свое дело снова.",
]
FACTS = ["У осьминога три сердца.", "Мёд не портится.", "Кошки спят до 20 часов в день."]
QUOTES = ["«Делай, что должен»", "«Лучше начать, чем жалеть»"]

# words for anti-mat filter (non-exhaustive). You may edit or localize.
BAD_WORDS = ["бляд", "хуй", "пизд", "сука"]

# Helpers
def today_iso():
    return datetime.utcnow().date().isoformat()

async def run_blocking(func, *args, **kwargs):
    """Run blocking function in thread pool to avoid blocking event loop."""
    return await asyncio.to_thread(func, *args, **kwargs)# MultiBotX — part 3/7: basic commands, entertainment, donke

# Start / Help / Menu
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🎲 Развлечения", callback_data="menu_fun")],
        [InlineKeyboardButton("📥 Скачать видео (вставь ссылку)", callback_data="menu_download")],
        [InlineKeyboardButton("👮 Модерация", callback_data="menu_mod")],
    ]
    await update.message.reply_text(
        "👋 Привет! Я — MultiBotX.\nНажми кнопку или используй /help.",
        reply_markup=InlineKeyboardMarkup(kb),
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📋 <b>Команды MultiBotX</b>\n\n"
        "Развлечения:\n"
        "/joke — шутка\n"
        "/fact — факт\n"
        "/quote — цитата\n"
        "/cat — фото кота\n"
        "/dog — фото собаки\n"
        "/meme — мем\n"
        "/dice — кубик\n\n"
        "Donke:\n"
        "/donke — шутка\n"
        "/camdonke — залить в Donke (раз в сутки)\n"
        "/topdonke — топ 50\n\n"
        "/download <url> — скачать видео (или просто пришли ссылку)\n"
        "/ai <вопрос> — AI (если настроен)\n\n"
        "Модерация: ответь на сообщение и напиши без '/' — 'варн', 'мут', 'бан', 'размут', 'анбан'."
    )
    await update.message.reply_text(msg, parse_mode="HTML")

# Entertainment handlers
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
        url = j.get("message")
        if url:
            await update.message.reply_photo(url)
        else:
            await update.message.reply_text("Не удалось получить собаку.")
    except Exception:
        logger.exception("dog_cmd failed")
        await update.message.reply_text("Ошибка при получении собаки.")

async def dice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_dice()

# Donke features
async def donke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(DONKE_PHRASES))

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
    await update.message.reply_text("\n".join(lines))# MultiBotX — part 4/7: moderation commands + reply-moderation

# Warn / mute / unmute / ban / unban via commands
async def warn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("Ответь на сообщение пользователя, чтобы выдать предупреждение.")
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
        return await update.message.reply_text("Ответь на сообщение пользователя для мута.")
    target = update.message.reply_to_message.from_user
    try:
        until = datetime.utcnow() + timedelta(minutes=30)
        await update.effective_chat.restrict_member(target.id, permissions=ChatPermissions(can_send_messages=False), until_date=until)
        await update.message.reply_text(f"🔇 {target.full_name} замучен на 30 минут.")
    except Exception:
        await update.message.reply_text("Не удалось замутить — недостаточно прав.")

async def unmute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("Ответь на сообщение пользователя для размута.")
    target = update.message.reply_to_message.from_user
    try:
        await update.effective_chat.restrict_member(target.id, permissions=ChatPermissions(can_send_messages=True))
        await update.message.reply_text(f"🔊 {target.full_name} размучен.")
    except Exception:
        await update.message.reply_text("Не удалось размучить — недостаточно прав.")

async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("Ответь на сообщение пользователя для бана.")
    target = update.message.reply_to_message.from_user
    try:
        await update.effective_chat.ban_member(target.id)
        await update.message.reply_text(f"🚫 {target.full_name} забанен.")
    except Exception:
        await update.message.reply_text("Не удалось забанить — недостаточно прав.")

async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return await update.message.reply_text("Ответь на сообщение пользователя для разбанивания.")
    target = update.message.reply_to_message.from_user
    try:
        await update.effective_chat.unban_member(target.id)
        await update.message.reply_text(f"✅ {target.full_name} разбанен.")
    except Exception:
        await update.message.reply_text("Не удалось разбанить — недостаточно прав.")

# Reply-moderation: when moderator replies with short words (no slash)
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
        await unban_cmd(update, context)# MultiBotX — part 5/7: auto-filters, anti-mat, anti-flood, admin stats

LAST_MSG = {}  # {(chat_id,user_id): [timestamps]}

async def auto_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Anti-mat and anti-flood run on every text message (except commands)."""
    if not update.message or not update.message.text:
        return
    msg = update.message
    text = msg.text.lower()
    # simple profanity filter
    for bad in BAD_WORDS:
        if bad in text:
            try:
                await msg.delete()
                await msg.reply_text("⚠️ Пожалуйста, не ругайтесь.")
            except Exception:
                pass
            return
    # anti-flood — more than 6 messages in 10 sec => mute 1 minute
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

# Admin stats command (simple)
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only allow if user is chat admin or if ADMIN_ID env is set and matches
    ADMIN_ID = os.getenv("ADMIN_ID")
    if ADMIN_ID and str(update.effective_user.id) != str(ADMIN_ID):
        return await update.message.reply_text("Только админ может вызвать статистику.")
    total_users = len(donke_db)
    lines = [f"Donke entries: {total_users}"]
    await update.message.reply_text("\n".join(lines))# MultiBotX — part 6/7: download helpers and handler

YTDL_OPTS_BASE = {
    "format": "mp4[ext=mp4]/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    # avoid console output; we use exceptions for errors
}

def yt_download_sync(url: str) -> str:
    """Blocking download via yt_dlp. Returns local filename."""
    tmpdir = tempfile.mkdtemp(prefix="multibotx_")
    opts = YTDL_OPTS_BASE.copy()
    opts["outtmpl"] = os.path.join(tmpdir, "%(id)s.%(ext)s")
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename

async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Accepts: /download <url> or plain message containing url
    text = None
    if context.args:
        text = context.args[0]
    elif update.message and update.message.text:
        m = re.search(r"https?://\S+", update.message.text)
        if m:
            text = m.group(0)
    if not text:
        return
    status = await update.message.reply_text("⏬ Пытаюсь скачать видео... (это может занять время)")
    logger.info("Download requested: %s", text)
    try:
        # 1) If tiktok and SaveTube key exists — try API
        if SAVE_TUBE_KEY and "tiktok" in text:
            try:
                headers = {"X-RapidAPI-Key": SAVE_TUBE_KEY, "X-RapidAPI-Host": "save-tube-video-download.p.rapidapi.com"}
                api = "https://save-tube-video-download.p.rapidapi.com/download"
                r = await run_blocking(requests.get, api, headers=headers, params={"url": text}, timeout=15)
                j = r.json()
                if isinstance(j, dict) and j.get("links"):
                    v = j["links"][0].get("url")
                    if v:
                        await update.message.reply_video(v)
                        await status.delete()
                        return
            except Exception:
                logger.exception("SaveTube attempt failed, fallback to yt_dlp")

        # 2) Fallback: yt_dlp
        fname = await run_blocking(yt_download_sync, text)
        size = os.path.getsize(fname)
        logger.info("Downloaded file: %s size=%d", fname, size)
        if size > MAX_SEND_BYTES:
            await update.message.reply_text("Файл слишком большой для отправки через Telegram. Отправляю ссылку на источник.")
            await update.message.reply_text(text)
            try:
                os.remove(fname)
                shutil.rmtree(os.path.dirname(fname), ignore_errors=True)
            except Exception:
                pass
            await status.delete()
            return
        # send
        with open(fname, "rb") as f:
            await update.message.reply_video(f)
        # cleanup
        try:
            os.remove(fname)
            shutil.rmtree(os.path.dirname(fname), ignore_errors=True)
        except Exception:
            pass
        await status.delete()
    except Exception:
        logger.exception("download_handler failed")
        try:
            await status.edit_text("❌ Ошибка при скачивании. Попробуйте другую ссылку.")
        except Exception:
            pass# MultiBotX — part 7/7: AI, commands setup, handlers registration, run

# OpenAI simple call (optional)
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
        await update.message.reply_text("AI не настроен. Добавь OPENAI_API_KEY в переменные окружения.")
        return
    prompt = " ".join(context.args) if context.args else ""
    if not prompt:
        await update.message.reply_text("Использование: /ai <вопрос>")
        return
    await update.message.reply_text("🤖 Думаю...")
    try:
        res = await run_blocking(call_openai, prompt)
        for i in range(0, len(res), 3900):
            await update.message.reply_text(res[i : i + 3900])
    except Exception:
        logger.exception("AI call failed")
        await update.message.reply_text("Ошибка при вызове AI.")

# Setup commands to show when user types '/'
async def setup_bot_commands():
    if not COMMANDS_SETUP:
        return
    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("help", "Помощь"),
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
        BotCommand("stats", "Статистика (админ)"),
    ]
    try:
        await application.bot.set_my_commands(commands)
        logger.info("Bot commands set")
    except Exception:
        logger.exception("Failed to set bot commands")

# Register handlers
def register_handlers():
    # commands
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
    application.add_handler(CommandHandler("download", download_handler))
    application.add_handler(CommandHandler("ai", ai_cmd))
    application.add_handler(CommandHandler("stats", stats_cmd))

    # automatic url catch (plain links)
    application.add_handler(MessageHandler(filters.Regex(r"https?://"), download_handler))

    # reply-moderation (no slash)
    application.add_handler(MessageHandler(
        filters.Regex(r"^(варн|мут|размут|анмут|бан|разбан|анбан|унбан|warn|mute|unmute|ban|unban)$") & filters.REPLY,
        reply_moderation_handler))

    # auto filters (anti-mat / anti-flood) — apply to all text that's not a command
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_filters))

def main():
    register_handlers()
    # async set commands
    async def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрируем хендлеры
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    # ... другие хендлеры

    # Устанавливаем команды при старте
    async def post_init(app: Application):
        await setup_bot_commands(app)

    application.post_init = post_init

    await application.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())