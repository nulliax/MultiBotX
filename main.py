#!/usr/bin/env python3
# main.py — MultiBotX (ultimate upgrade)
# Requires: python-telegram-bot>=21.0, Flask, requests, yt_dlp, python-dotenv (for local dev).
# Environment variables:
#   BOT_TOKEN (required)
#   ADMIN_ID (optional)
#   SAVETUBE_KEY (optional)
#   MAX_SEND_BYTES (optional)
#   COMMANDS_SETUP (optional, default true)

import os
import json
import logging
import random
import re
import shutil
import tempfile
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from threading import Thread
from typing import Optional, Dict, Any

import requests
import yt_dlp
from flask import Flask
from dotenv import load_dotenv
from telegram import (
    Update,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Load .env locally (do not commit .env to repo)
load_dotenv()

# ---------------- Config ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")  # optional, string
SAVETUBE_KEY = os.getenv("SAVETUBE_KEY")
MAX_SEND_BYTES = int(os.getenv("MAX_SEND_BYTES", 50 * 1024 * 1024))
COMMANDS_SETUP = os.getenv("COMMANDS_SETUP", "1") not in ("0", "false", "False")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Set it in environment variables.")

PORT = int(os.getenv("PORT", 5000))

# ---------------- Logging ----------------
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger("MultiBotX")

# ---------------- Data paths ----------------
ROOT = Path(".")
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DONKE_FILE = DATA_DIR / "donke.json"
JOKES_FILE = DATA_DIR / "jokes.json"
USAGE_FILE = DATA_DIR / "usage.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
LOG_FILE = DATA_DIR / "errors.log"

def load_json(p: Path) -> dict:
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to load JSON %s", p)
    return {}

def save_json(p: Path, data: dict):
    try:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logger.exception("Failed to save JSON %s", p)

donke_db = load_json(DONKE_FILE)
joke_db = load_json(JOKES_FILE).get("jokes", []) if JOKES_FILE.exists() else []
usage_db = load_json(USAGE_FILE)
settings_db = load_json(SETTINGS_FILE)

# bootstrap jokes if empty
if not joke_db:
    joke_db = [
        "Почему программисты путают Хэллоуин и Рождество? OCT 31 == DEC 25.",
        "Я бы рассказал шутку про UDP, но не уверен, что ты её получишь.",
        "Debugging: превращение багов в фичи."
    ]
    save_json(JOKES_FILE, {"jokes": joke_db})

def inc_usage(key: str):
    usage_db[key] = usage_db.get(key, 0) + 1
    save_json(USAGE_FILE, usage_db)

def log_error(exc: Exception):
    logger.exception(exc)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} - {traceback.format_exc()}\n")
    except Exception:
        pass

# ---------------- Antimat (disabled by default) ----------------
# Large list of rude words — kept here but only acted on if /antimat ON for chat
ANTIMAT_BIG_LIST = [
    # short sample expanded; user can extend
    "бляд", "блядь", "хуй", "хер", "пизд", "пиздец", "сука", "мраз", "ебал", "ебать",
    "соси", "гандон", "мудак", "тварь", "чмыр", "уебище", "долбоёб", "кретин", "ид_иот"
]
# store per-chat flag: settings_db["antimat"][chat_id] = True/False
if "antimat" not in settings_db:
    settings_db["antimat"] = {}
    save_json(SETTINGS_FILE, settings_db)

# ---------------- yt_dlp helpers ----------------
YTDL_COMMON = {
    "format": "bestvideo+bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "ignoreerrors": True,
    "cachedir": False,
}

YTDL_VIDEO_OPTS = dict(YTDL_COMMON)
YTDL_VIDEO_OPTS.update({"outtmpl": "%(id)s.%(ext)s"})

YTDL_AUDIO_OPTS = dict(YTDL_COMMON)
YTDL_AUDIO_OPTS.update({
    "format": "bestaudio/best",
    "outtmpl": "%(id)s.%(ext)s",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }],
})

def yt_download(url: str, audio_only: bool = False) -> Optional[str]:
    """
    Downloads media using yt_dlp into a temp dir and returns file path or None.
    Caller must delete the file (and the dir).
    """
    tmpdir = tempfile.mkdtemp(prefix="mbx_")
    opts = YTDL_AUDIO_OPTS.copy() if audio_only else YTDL_VIDEO_OPTS.copy()
    opts["outtmpl"] = os.path.join(tmpdir, opts.get("outtmpl", "%(id)s.%(ext)s"))
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                return None
            filename = ydl.prepare_filename(info)
            # yt_dlp may produce different ext for postprocessed audio (mp3)
            # Attempt to find file in tmpdir
            files = list(Path(tmpdir).glob("*"))
            if files:
                return str(files[0])
            return filename
    except Exception as e:
        logger.exception("yt_dlp error for %s", url)
        log_error(e)
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass
        return None

def cleanup_path(path: str):
    try:
        base = Path(path).parent
        if base.exists():
            shutil.rmtree(base)
    except Exception:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

# ---------------- Flask health ----------------
flask_app = Flask(__name__)

@flask_app.route("/", methods=["GET"])
def home():
    return "MultiBotX is running (polling)."

# ---------------- Commands list (for / menu and set_my_commands) ----------------
BOT_COMMANDS_DETAILED = [
    ("start", "Приветствие"),
    ("menu", "Открыть меню"),
    ("joke", "Шутка"),
    ("addjoke", "Добавить шутку"),
    ("donke", "Donke шутка"),
    ("camdonke", "Залить в Donke (1x/сутки)"),
    ("topdonke", "Топ Donke"),
    ("meme", "Мем"),
    ("cat", "Фото кота"),
    ("dog", "Фото собаки"),
    ("dice", "Кубик"),
    ("download", "Скачать видео / аудио по ссылке"),
    ("searchimage", "Поиск изображения"),
    ("trivia", "Случайный факт"),
    ("stats", "Статистика (админ)"),
    ("antimat", "Включить/выключить анти-мат (админ/модераторы)"),
    ("motivate", "Мотивация"),
    ("compliment", "Комплимент"),
    ("8ball", "Шар судьбы"),
    ("fortune", "Печенье судьбы"),
]

# ---------------- Handlers ----------------

# Utility guards
def is_admin_user(user_id: int, chat) -> bool:
    # allow private chat owner or ADMIN_ID or chat admin
    if ADMIN_ID and str(user_id) == str(ADMIN_ID):
        return True
    try:
        member = chat.get_member(user_id)
        if member.status in ("administrator", "creator"):
            return True
    except Exception:
        pass
    return False

# Start
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("start")
    text = "👋 Привет! Я MultiBotX. Напиши /menu чтобы открыть удобное главное меню."
    await update.message.reply_text(text)

# Menu (improved, categories)
def build_main_menu() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton("🎭 Развлечения", callback_data="menu:entertain")],
        [InlineKeyboardButton("🎥 Медиа (видео/аудио)", callback_data="menu:media")],
        [InlineKeyboardButton("😈 Donke", callback_data="menu:donke")],
        [InlineKeyboardButton("🛠️ Модерация", callback_data="menu:moderation")],
        [InlineKeyboardButton("🔎 Полезное", callback_data="menu:useful")],
    ]
    return InlineKeyboardMarkup(kb)

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("menu")
    text = "📋 Главное меню MultiBotX — выбери категорию:"
    await update.message.reply_text(text, reply_markup=build_main_menu())

# Menu callbacks
async def menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    if not data.startswith("menu:"):
        return
    cat = data.split(":", 1)[1]
    if cat == "entertain":
        kb = [
            [InlineKeyboardButton("😂 /joke", callback_data="menu_ent:joke"),
             InlineKeyboardButton("📚 /trivia", callback_data="menu_ent:trivia")],
            [InlineKeyboardButton("💬 /quote", callback_data="menu_ent:quote"),
             InlineKeyboardButton("💡 /motivate", callback_data="menu_ent:motivate")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu:back")],
        ]
        await q.edit_message_text("🎭 Развлечения — выбирай:", reply_markup=InlineKeyboardMarkup(kb))
    elif cat == "media":
        kb = [
            [InlineKeyboardButton("📹 Ссылка → Видео/Аудио", callback_data="menu_media:download")],
            [InlineKeyboardButton("🐱 /cat", callback_data="menu_media:cat"),
             InlineKeyboardButton("🐶 /dog", callback_data="menu_media:dog")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu:back")],
        ]
        await q.edit_message_text("🎥 Медиа — опции:", reply_markup=InlineKeyboardMarkup(kb))
    elif cat == "donke":
        kb = [
            [InlineKeyboardButton("😈 /donke", callback_data="menu_donke:donke"),
             InlineKeyboardButton("💦 /camdonke", callback_data="menu_donke:camdonke")],
            [InlineKeyboardButton("🏆 /topdonke", callback_data="menu_donke:topdonke"),
             InlineKeyboardButton("⬅️ Назад", callback_data="menu:back")],
        ]
        await q.edit_message_text("Donke — выбирай:", reply_markup=InlineKeyboardMarkup(kb))
    elif cat == "moderation":
        kb = [
            [InlineKeyboardButton("⚠️ Модерация (reply: 'варн/мут/бан')", callback_data="menu_mod:hint")],
            [InlineKeyboardButton("🧯 /antimat (вкл/выкл)", callback_data="menu_mod:antimat")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu:back")],
        ]
        await q.edit_message_text("Модерация — подсказки:", reply_markup=InlineKeyboardMarkup(kb))
    elif cat == "useful":
        kb = [
            [InlineKeyboardButton("🔎 /searchimage", callback_data="menu_useful:searchimage"),
             InlineKeyboardButton("📊 /stats", callback_data="menu_useful:stats")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu:back")],
        ]
        await q.edit_message_text("Полезное — выбирай:", reply_markup=InlineKeyboardMarkup(kb))
    elif cat == "back":
        await q.edit_message_text("📋 Главное меню:", reply_markup=build_main_menu())
    else:
        await q.edit_message_text("Неизвестная категория.")

# Entertainment commands
async def joke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("joke")
    await update.message.reply_text(random.choice(joke_db))

async def addjoke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("addjoke")
    text = " ".join(context.args) if context.args else None
    if not text:
        await update.message.reply_text("Использование: /addjoke ТЕКСТ_ШУТКИ")
        return
    joke_db.append(text)
    save_json(JOKES_FILE, {"jokes": joke_db})
    await update.message.reply_text("Шутка добавлена — спасибо!")

async def trivia_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("trivia")
    await update.message.reply_text(random.choice(["Знаете ли вы?", "Факт: "]) + " " + random.choice(["У осьминога три сердца.", "Кошки спят до 20 часов."]))

async def motivate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("motivate")
    choices = [
        "Ты можешь всё, что захочешь начать.",
        "Маленький шаг каждый день приводит к большим результатам.",
        "Не жди идеального момента — создавай его."
    ]
    await update.message.reply_text(random.choice(choices))

async def compliment_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("compliment")
    await update.message.reply_text(random.choice(["Ты сегодня сияешь!", "У тебя отличный вкус.", "Ты крутой человек."]))

async def quote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("quote")
    await update.message.reply_text(random.choice(QUOTES if 'QUOTES' in globals() else ["Делай."]))

# Images / memes
async def cat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("cat")
    try:
        r = requests.get("https://api.thecatapi.com/v1/images/search", timeout=10).json()
        await update.message.reply_photo(r[0]["url"])
    except Exception as e:
        log_error(e)
        await update.message.reply_text("Не удалось получить фото котика.")

async def dog_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("dog")
    try:
        r = requests.get("https://dog.ceo/api/breeds/image/random", timeout=10).json()
        await update.message.reply_photo(r["message"])
    except Exception as e:
        log_error(e)
        await update.message.reply_text("Не удалось получить фото собаки.")

async def meme_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("meme")
    try:
        r = requests.get("https://meme-api.com/gimme", timeout=10).json()
        await update.message.reply_photo(r["url"], caption=r.get("title", "Мем"))
    except Exception as e:
        log_error(e)
        await update.message.reply_text("Не удалось получить мем.")

async def dice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("dice")
    await update.message.reply_dice()

# Donke system
async def donke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("donke")
    await update.message.reply_text(random.choice(["Donke — легенда.", "Donke делает мир смешнее."]))

async def camdonke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("camdonke")
    user = update.effective_user
    uid = str(user.id)
    entry = donke_db.get(uid, {"name": user.full_name, "total": 0, "last": None})
    if entry.get("last") == today_iso():
        await update.message.reply_text("Сегодня уже заливали — заходите завтра.")
        return
    amount = random.randint(1, 100)
    entry["total"] = entry.get("total", 0) + amount
    entry["last"] = today_iso()
    entry["name"] = user.full_name
    donke_db[uid] = entry
    save_json(DONKE_FILE, donke_db)
    await update.message.reply_text(f"💦 Вы успешно залили в Donke {amount} литров! Приходите завтра.")

async def topdonke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("topdonke")
    if not donke_db:
        await update.message.reply_text("Пока никто не заливал.")
        return
    sorted_list = sorted(donke_db.items(), key=lambda kv: kv[1].get("total", 0), reverse=True)[:50]
    lines = ["🏆 Топ Donke:"]
    for i, (uid, e) in enumerate(sorted_list, 1):
        lines.append(f"{i}. {e.get('name','?')} — {e.get('total', 0)} л")
    await update.message.reply_text("\n".join(lines))

# Moderation: reply-based commands without slash
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
    warns = context.bot_data.setdefault("warns", {})
    if "варн" in cmd:
        warns[target.id] = warns.get(target.id, 0) + 1
        await msg.reply_text(f"⚠️ {target.full_name} получил предупреждение ({warns[target.id]}).")
        if warns[target.id] >= 3:
            await chat.ban_member(target.id)
            await msg.reply_text(f"🚫 {target.full_name} забанен (3 предупреждения).")
            warns[target.id] = 0
    elif "мут" in cmd:
        until = datetime.utcnow() + timedelta(minutes=10)
        await chat.restrict_member(target.id, ChatPermissions(can_send_messages=False), until_date=until)
        await msg.reply_text(f"🔇 {target.full_name} замучен на 10 минут.")
    elif cmd in ("размут", "анмут"):
        await chat.restrict_member(target.id, ChatPermissions(can_send_messages=True))
        await msg.reply_text(f"🔊 {target.full_name} размучен.")
    elif "бан" in cmd:
        await chat.ban_member(target.id)
        await msg.reply_text(f"🚫 {target.full_name} забанен.")
    elif cmd in ("разбан", "унбан", "анбан"):
        await chat.unban_member(target.id)
        await msg.reply_text(f"✅ {target.full_name} разбанен.")

# Welcome / profanity / anti-flood
LAST_MSG = {}  # {(chat_id,user_id): [timestamps]}
def today_iso(): return datetime.utcnow().date().isoformat()

async def welcome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.new_chat_members:
        for u in update.message.new_chat_members:
            await update.message.reply_text(f"👋 Добро пожаловать, {u.full_name}!")

async def profanity_and_flood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return
    text = msg.text.lower()
    # antimat per chat
    chat_id = str(msg.chat.id)
    antimat_on = settings_db.get("antimat", {}).get(chat_id, False)
    if antimat_on:
        for bad in ANTIMAT_BIG_LIST:
            if bad in text:
                try:
                    await msg.delete()
                    await msg.reply_text("🚫 Нецензурная лексика запрещена в этом чате.")
                except Exception:
                    pass
                return
    # anti-flood
    key = (msg.chat.id, msg.from_user.id)
    now_t = datetime.utcnow().timestamp()
    arr = LAST_MSG.get(key, [])
    arr = [t for t in arr if now_t - t < 10]
    arr.append(now_t)
    LAST_MSG[key] = arr
    if len(arr) > 6:
        try:
            await msg.chat.restrict_member(msg.from_user.id, ChatPermissions(can_send_messages=False),
                                           until_date=datetime.utcnow() + timedelta(minutes=1))
            await msg.reply_text("🤐 Антифлуд: замучен на 1 минуту.")
        except Exception:
            pass

# Antimat toggle command (chat-level)
async def antimat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only admins can toggle
    user = update.effective_user
    chat = update.effective_chat
    try:
        member = await chat.get_member(user.id)
        if member.status not in ("administrator", "creator") and str(user.id) != str(ADMIN_ID):
            await update.message.reply_text("Только администраторы могут менять настройки анти-мата.")
            return
    except Exception:
        # In private chats, allow user (owner)
        pass
    args = context.args
    chat_id = str(chat.id)
    if args and args[0].lower() in ("off", "0", "disable", "выкл"):
        settings_db.setdefault("antimat", {})[chat_id] = False
        save_json(SETTINGS_FILE, settings_db)
        await update.message.reply_text("Анти-мат отключён для этого чата.")
        return
    # toggle
    cur = settings_db.setdefault("antimat", {}).get(chat_id, False)
    new = not cur
    settings_db.setdefault("antimat", {})[chat_id] = new
    save_json(SETTINGS_FILE, settings_db)
    await update.message.reply_text(f"Анти-мат {'включён' if new else 'выключен'} для этого чата.")

# ---------------- Download flow ----------------
# /download or plain URL message 