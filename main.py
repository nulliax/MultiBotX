#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MultiBotX — полный файл main.py
Функции: красивые меню, регистрация команд, скачивание видео/аудио (yt_dlp), Donke, модерация,
анти-мат (включается командой /antimat), статистика, напоминания, мемы, котики/собаки, добавление шуток и т.д.
"""

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
from typing import Optional

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

# Load .env locally for development (do not commit .env)
load_dotenv()

# ---------------- Config ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")  # optional admin id
SAVETUBE_KEY = os.getenv("SAVETUBE_KEY")  # optional RapidAPI key for SaveTube
MAX_SEND_BYTES = int(os.getenv("MAX_SEND_BYTES", 50 * 1024 * 1024))  # default 50MB
COMMANDS_SETUP = os.getenv("COMMANDS_SETUP", "1") not in ("0", "false", "False")
PORT = int(os.getenv("PORT", 5000))
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME", "")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Add it to environment variables.")

# ---------------- Logging ----------------
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger("MultiBotX")

# ---------------- Data storage ----------------
ROOT = Path(".")
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DONKE_FILE = DATA_DIR / "donke.json"
JOKES_FILE = DATA_DIR / "jokes.json"
USAGE_FILE = DATA_DIR / "usage.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
ERROR_LOG = DATA_DIR / "errors.log"

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
joke_data = load_json(JOKES_FILE)
joke_db = joke_data.get("jokes", []) if isinstance(joke_data, dict) else []
usage_db = load_json(USAGE_FILE)
settings_db = load_json(SETTINGS_FILE)

# bootstrap jokes
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

def log_error(e: Exception):
    logger.exception(e)
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} - {traceback.format_exc()}\n")
    except Exception:
        pass

# ---------------- Antimat ----------------
ANTIMAT_WORDS = [
    # core expanded list (short sample; you can extend)
    "бляд", "блядь", "хуй", "хер", "пизд", "пиздец", "сука", "мраз", "ебал", "ебать",
    "соси", "гандон", "мудак", "тварь", "долбоёб", "кретин", "идиот"
]
if "antimat" not in settings_db:
    settings_db["antimat"] = {}  # chat_id -> bool
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
YTDL_VIDEO_OPTS["outtmpl"] = "%(id)s.%(ext)s"

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
    tmpdir = tempfile.mkdtemp(prefix="mbx_")
    opts = YTDL_AUDIO_OPTS.copy() if audio_only else YTDL_VIDEO_OPTS.copy()
    opts["outtmpl"] = str(Path(tmpdir) / opts.get("outtmpl", "%(id)s.%(ext)s"))
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                shutil.rmtree(tmpdir, ignore_errors=True)
                return None
            # find any file in tmpdir
            files = list(Path(tmpdir).glob("*"))
            if not files:
                shutil.rmtree(tmpdir, ignore_errors=True)
                return None
            return str(files[0])
    except Exception as e:
        log_error(e)
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None

def cleanup_path(path: str):
    try:
        base = Path(path).parent
        if base.exists():
            shutil.rmtree(base, ignore_errors=True)
    except Exception:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

# ---------------- Flask health ----------------
flask_app = Flask(__name__)
@flask_app.route("/", methods=["GET"])
def index():
    return "MultiBotX is running."

# ---------------- Bot commands list ----------------
BOT_COMMANDS_DETAILED = [
    ("start", "Приветствие"),
    ("menu", "Главное меню"),
    ("joke", "Шутка"),
    ("addjoke", "Добавить шутку"),
    ("donke", "Donke шутка"),
    ("camdonke", "Залить в Donke (1x/сутки)"),
    ("topdonke", "Топ Donke"),
    ("meme", "Мем"),
    ("cat", "Фото кота"),
    ("dog", "Фото собаки"),
    ("dice", "Кубик"),
    ("download", "Скачать видео/аудио по ссылке"),
    ("searchimage", "Поиск изображения"),
    ("trivia", "Случайный факт"),
    ("stats", "Статистика (админ)"),
    ("antimat", "Вкл/выкл анти-мат (модераторы)"),
    ("motivate", "Мотивация"),
    ("compliment", "Комплимент"),
    ("remindme", "Напоминание: /remindme <минуты> <текст>"),
]

# ---------------- Helpers ----------------
def today_iso():
    return datetime.utcnow().date().isoformat()

def is_chat_admin(user_id: int, chat) -> bool:
    # allow ADMIN_ID, chat admin/creator
    if ADMIN_ID and str(user_id) == str(ADMIN_ID):
        return True
    try:
        member = chat.get_member(user_id)
        if member.status in ("administrator", "creator"):
            return True
    except Exception:
        pass
    return False

# ---------------- Menu UI ----------------
def main_menu_markup():
    kb = [
        [InlineKeyboardButton("🎭 Развлечения", callback_data="menu:entertain")],
        [InlineKeyboardButton("🎥 Медиа", callback_data="menu:media")],
        [InlineKeyboardButton("😈 Donke", callback_data="menu:donke")],
        [InlineKeyboardButton("🛡 Модерация", callback_data="menu:moderation")],
        [InlineKeyboardButton("🔎 Полезное", callback_data="menu:useful")],
    ]
    return InlineKeyboardMarkup(kb)

# ---------------- Handlers ----------------

# Start / Menu
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("start")
    text = (
        "👋 *MultiBotX* — многофункциональный бот.\n\n"
        "Нажми кнопку ниже, чтобы открыть удобное меню (или используй `/menu`)."
    )
    try:
        await update.message.reply_markdown(text, reply_markup=main_menu_markup())
    except Exception:
        await update.message.reply_text("Привет! Напиши /menu чтобы открыть меню.")

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("menu")
    try:
        await update.message.reply_text("📋 Главное меню:", reply_markup=main_menu_markup())
    except Exception:
        await update.message.reply_text("Меню: /joke /donke /download /cat /dog /meme /stats")

# Menu callbacks
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    if data == "menu:entertain":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("😂 /joke", callback_data="ent:joke"),
             InlineKeyboardButton("💬 /trivia", callback_data="ent:trivia")],
            [InlineKeyboardButton("💡 /motivate", callback_data="ent:motivate"),
             InlineKeyboardButton("➕ /addjoke", callback_data="ent:addjoke")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu:back")]
        ])
        await q.edit_message_text("🎭 Развлечения:", reply_markup=kb)
    elif data == "menu:media":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📹 Скачать по ссылке", callback_data="media:download")],
            [InlineKeyboardButton("🐱 /cat", callback_data="media:cat"),
             InlineKeyboardButton("🐶 /dog", callback_data="media:dog")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu:back")]
        ])
        await q.edit_message_text("🎥 Медиа:", reply_markup=kb)
    elif data == "menu:donke":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("😈 /donke", callback_data="donke:donke"),
             InlineKeyboardButton("💦 /camdonke", callback_data="donke:camdonke")],
            [InlineKeyboardButton("🏆 /topdonke", callback_data="donke:topdonke"),
             InlineKeyboardButton("⬅️ Назад", callback_data="menu:back")]
        ])
        await q.edit_message_text("Donke:", reply_markup=kb)
    elif data == "menu:moderation":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚠️ Подсказки модерации", callback_data="mod:hint")],
            [InlineKeyboardButton("🧯 /antimat", callback_data="mod:antimat")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu:back")]
        ])
        await q.edit_message_text("Модерация:", reply_markup=kb)
    elif data == "menu:useful":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 /searchimage", callback_data="useful:searchimage"),
             InlineKeyboardButton("⏰ /remindme", callback_data="useful:remindme")],
            [InlineKeyboardButton("📊 /stats", callback_data="useful:stats"),
             InlineKeyboardButton("⬅️ Назад", callback_data="menu:back")]
        ])
        await q.edit_message_text("Полезное:", reply_markup=kb)
    elif data == "menu:back":
        await q.edit_message_text("📋 Главное меню:", reply_markup=main_menu_markup())
    # sub callbacks (simple)
    elif data.startswith("ent:"):
        action = data.split(":", 1)[1]
        if action == "joke":
            await q.edit_message_text(random.choice(joke_db))
        elif action == "trivia":
            await q.edit_message_text("Факт: " + random.choice(["У осьминога 3 сердца.", "Мёд не портится."]))
        elif action == "motivate":
            await q.edit_message_text(random.choice(["Действуй!", "Маленькие шаги — большие изменения."]))
        elif action == "addjoke":
            await q.edit_message_text("Чтобы добавить шутку — используй команду /addjoke ТЕКСТ")
    elif data.startswith("media:"):
        action = data.split(":", 1)[1]
        if action == "download":
            await q.edit_message_text("Отправь ссылку в чат, и я предложу скачать видео или только звук.")
        elif action == "cat":
            await q.edit_message_text("Используй /cat чтобы получить фото кота.")
    elif data.startswith("donke:"):
        action = data.split(":", 1)[1]
        if action == "donke":
            await q.edit_message_text(random.choice(["Donke — легенда.", "Donke forever."]))
        elif action == "camdonke":
            await q.edit_message_text("Вызовите /camdonke чтобы залить в Donke.")
        elif action == "topdonke":
            await q.edit_message_text("Вызовите /topdonke чтобы увидеть рейтинг.")
    else:
        await q.edit_message_text("Опция пока не реализована.")

# ---------------- Entertainment ----------------
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
    await update.message.reply_text("Спасибо — шутка добавлена!")

async def trivia_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("trivia")
    await update.message.reply_text(random.choice(["Факт:", "Интересно:"]) + " " + random.choice(["У осьминога 3 сердца.", "Кошки спят много."]))

async def motivate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("motivate")
    await update.message.reply_text(random.choice(["Действуй прямо сейчас.", "Ты способен на большее."]))

async def compliment_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("compliment")
    await update.message.reply_text(random.choice(["Ты молодец!", "У тебя хорошее чувство юмора."]))

# ---------------- Images / memes ----------------
async def cat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("cat")
    try:
        r = requests.get("https://api.thecatapi.com/v1/images/search", timeout=10).json()
        await update.message.reply_photo(r[0]["url"])
    except Exception as e:
        log_error(e)
        await update.message.reply_text("Не удалось получить котика.")

async def dog_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("dog")
    try:
        r = requests.get("https://dog.ceo/api/breeds/image/random", timeout=10).json()
        await update.message.reply_photo(r["message"])
    except Exception as e:
        log_error(e)
        await update.message.reply_text("Не удалось получить собаку.")

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

# ---------------- Donke ----------------
async def donke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("donke")
    await update.message.reply_text(random.choice(["Donke — легенда.", "Donke forever."]))

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
        lines.append(f"{i}. {e.get('name', '?')} — {e.get('total', 0)} л")
    await update.message.reply_text("\n".join(lines))

# ---------------- Moderation (reply-based) ----------------
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
        pass
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

# ---------------- Welcome + profanity + anti-flood ----------------
LAST_MSG = {}  # {(chat_id,user_id): [timestamps]}

async def welcome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.new_chat_members:
        for u in update.message.new_chat_members:
            await update.message.reply_text(f"👋 Добро пожаловать, {u.full_name}!")

async def profanity_and_flood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return
    text = msg.text.lower()
    chat_id = str(msg.chat.id)
    antimat_on = settings_db.get("antimat", {}).get(chat_id, False)
    if antimat_on:
        for bad in ANTIMAT_WORDS:
            if bad in text:
                try:
                    await msg.delete()
                    await msg.reply_text("🚫 Нецензурная лексика запрещена в этом чате.")
                except Exception:
                    pass
                return
    # anti-flood
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

# ---------------- Antimat toggle command ----------------
async def antimat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # only allow chat admin or ADMIN_ID
    user = update.effective_user
    chat = update.effective_chat
    try:
        member = await chat.get_member(user.id)
        if member.status not in ("administrator", "creator") and str(user.id) != str(ADMIN_ID):
     