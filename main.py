# ================== MultiBotX - Усовершенствованная версия ==================
# Разработано для python-telegram-bot v21+ и Flask
# Автор: ChatGPT + Archangel_MichaeI
# ============================================================================

import os
import re
import random
import logging
import json
import threading
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request
from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
import yt_dlp
import requests

# ================= Загрузка переменных окружения =================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
MAX_SEND_BYTES = int(os.getenv("MAX_SEND_BYTES", str(1024 * 1024 * 1024)))  # до 1 ГБ
COMMANDS_SETUP = os.getenv("COMMANDS_SETUP", "true").lower() in ("1", "true", "yes")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан в переменных окружения!")

# ================= Логирование =================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= Flask =================
flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return "MultiBotX is running!"

# ================= Глобальные переменные =================
antimat_enabled = False
warns = {}
donke_jokes = [
    "Donke пошёл в магазин, а вернулся без самооценки.",
    "Donke смеётся только над шутками Donke.",
    "Donke придумал новый закон физики: закон лени."
]
bad_words = ["дурак", "идиот", "тупой", "осёл", "козёл", "мудак", "пидор", "лох", "мразь", "гандон"]

# Список команд для меню Telegram
BOT_COMMANDS = [
    BotCommand("start", "Запуск бота"),
    BotCommand("help", "Показать помощь"),
    BotCommand("menu", "Красивое меню с кнопками"),
    BotCommand("joke", "Случайная шутка"),
    BotCommand("fact", "Интересный факт"),
    BotCommand("quote", "Цитата дня"),
    BotCommand("cat", "Фото кота"),
    BotCommand("dog", "Фото собаки"),
    BotCommand("meme", "Случайный мем"),
    BotCommand("dice", "Бросить кубик"),
    BotCommand("donke", "Шутка про Donke"),
    BotCommand("camdonke", "Добавить свою шутку Donke"),
    BotCommand("topdonke", "Топ шуток Donke"),
    BotCommand("antimat", "Включить/выключить анти-мат"),
]# ================= Часть 2: Развлечения, мемы, факты, хранилище =================

from pathlib import Path
import json
import asyncio

# Папка для данных
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

JOKES_FILE = DATA_DIR / "jokes.json"
DONKE_FILE = DATA_DIR / "donke.json"
USAGE_FILE = DATA_DIR / "usage.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

# Загрузка/сохранение JSON утилиты
def load_json_safe(path: Path, default=None):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.exception("load_json_safe error: %s", e)
    return default if default is not None else {}

def save_json_safe(path: Path, data):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.exception("save_json_safe error: %s", e)

# Инициализация баз
jokes_store = load_json_safe(JOKES_FILE, {"jokes": [
    "Почему программисты путают Хэллоуин и Рождество? OCT 31 == DEC 25.",
    "Я бы рассказал шутку про UDP, но она может не дойти.",
    "Debugging — превращение багов в фичи."
]})
donke_store = load_json_safe(DONKE_FILE, {})
usage_store = load_json_safe(USAGE_FILE, {})
settings_store = load_json_safe(SETTINGS_FILE, {"antimat": {}})

# Помощник для статистики использования
def inc_usage(key: str):
    usage_store[key] = usage_store.get(key, 0) + 1
    save_json_safe(USAGE_FILE, usage_store)

# ----------------- Развлекательные команды -----------------
async def cmd_joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет случайную шутку"""
    inc_usage("joke")
    joke = random.choice(jokes_store.get("jokes", []))
    await update.message.reply_text(joke)

async def cmd_addjoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляет шутку в базу: /addjoke Текст"""
    inc_usage("addjoke")
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Использование: /addjoke ТЕКСТ_ШУТКИ")
        return
    jokes_store.setdefault("jokes", []).append(text)
    save_json_safe(JOKES_FILE, jokes_store)
    await update.message.reply_text("Спасибо! Шутка добавлена.")

async def cmd_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("fact")
    facts = [
        "У осьминога три сердца.",
        "Пчёлы видят ультрафиолет.",
        "Мёд не портится."
    ]
    await update.message.reply_text(random.choice(facts))

async def cmd_quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("quote")
    quotes = [
        "«Лучший способ начать — начать.»",
        "«Ошибки — доказательство попыток.»",
        "«Делай сегодня то, что другие не хотят, завтра будешь жить как другие не могут.»"
    ]
    await update.message.reply_text(random.choice(quotes))

# ----------------- Картинки: котики, собаки, мемы -----------------
async def cmd_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("cat")
    try:
        r = requests.get("https://api.thecatapi.com/v1/images/search", timeout=10).json()
        if isinstance(r, list) and r:
            await update.message.reply_photo(r[0]["url"])
        else:
            await update.message.reply_text("Не удалось получить котика. Попробуйте снова.")
    except Exception as e:
        logger.exception("cat error: %s", e)
        await update.message.reply_text("Ошибка при получении котика.")

async def cmd_dog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("dog")
    try:
        r = requests.get("https://dog.ceo/api/breeds/image/random", timeout=10).json()
        await update.message.reply_photo(r["message"])
    except Exception as e:
        logger.exception("dog error: %s", e)
        await update.message.reply_text("Ошибка при получении собаки.")

async def cmd_meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("meme")
    try:
        r = requests.get("https://meme-api.com/gimme", timeout=10).json()
        url = r.get("url")
        title = r.get("title", "Мем")
        if url:
            await update.message.reply_photo(url, caption=title)
        else:
            await update.message.reply_text("Не удалось получить мем.")
    except Exception as e:
        logger.exception("meme error: %s", e)
        await update.message.reply_text("Ошибка при получении мема.")

async def cmd_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("dice")
    await update.message.reply_dice()

# ----------------- Donke: шутки и система camdonke -----------------
async def cmd_donke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("donke")
    await update.message.reply_text(random.choice(donke_jokes))

async def cmd_camdonke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь раз в день может 'залить' в Donke случайное количество литров"""
    inc_usage("camdonke")
    user = update.effective_user
    uid = str(user.id)
    entry = donke_store.get(uid, {"name": user.full_name, "total": 0, "last": None})
    if entry.get("last") == datetime.utcnow().date().isoformat():
        await update.message.reply_text("Сегодня вы уже заливали в Donke. Приходите завтра.")
        return
    amount = random.randint(1, 100)
    entry["total"] = entry.get("total", 0) + amount
    entry["last"] = datetime.utcnow().date().isoformat()
    entry["name"] = user.full_name
    donke_store[uid] = entry
    save_json_safe(DONKE_FILE, donke_store)
    await update.message.reply_text(f"💦 Вы успешно залили в Donke {amount} л. Приходите завтра!")

async def cmd_topdonke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("topdonke")
    if not donke_store:
        await update.message.reply_text("Пока никто не заливал.")
        return
    lst = sorted(donke_store.items(), key=lambda kv: kv[1].get("total", 0), reverse=True)[:50]
    lines = [f"{i+1}. {v[1].get('name','?')} — {v[1].get('total',0)} л" for i,(k,v) in enumerate(lst)]
    await update.message.reply_text("\n".join(lines))

# ----------------- Helper: register core command handlers (to call later) -----------------
def register_entertainment_handlers(app: Application):
    app.add_handler(CommandHandler("joke", cmd_joke))
    app.add_handler(CommandHandler("addjoke", cmd_addjoke))
    app.add_handler(CommandHandler("fact", cmd_fact))
    app.add_handler(CommandHandler("quote", cmd_quote))
    app.add_handler(CommandHandler("cat", cmd_cat))
    app.add_handler(CommandHandler("dog", cmd_dog))
    app.add_handler(CommandHandler("meme", cmd_meme))
    app.add_handler(CommandHandler("dice", cmd_dice))
    app.add_handler(CommandHandler("donke", cmd_donke))
    app.add_handler(CommandHandler("camdonke", cmd_camdonke))
    app.add_handler(CommandHandler("topdonke", cmd_topdonke))# ================= Часть 3: Модерация, анти-мат, скачивание видео =================

# ----- Модерация (работает без /, по ключевым словам) -----
MOD_WORDS = {
    "варн": "warn",
    "мут": "mute",
    "размут": "unmute",
    "анмут": "unmute",
    "бан": "ban",
    "анбан": "unban",
    "разбан": "unban"
}

async def handle_moderation_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Реакция на слова-модерацию в ответ на сообщение"""
    if not update.message.reply_to_message:
        return
    text = update.message.text.lower().strip()
    action = MOD_WORDS.get(text)
    if not action:
        return
    chat_id = update.effective_chat.id
    target_user = update.message.reply_to_message.from_user
    try:
        if action == "warn":
            await update.message.reply_text(f"⚠️ {target_user.full_name} получил предупреждение!")
        elif action == "mute":
            until = datetime.utcnow() + timedelta(hours=1)
            await context.bot.restrict_chat_member(chat_id, target_user.id, ChatPermissions(can_send_messages=False), until_date=until)
            await update.message.reply_text(f"🔇 {target_user.full_name} замьючен на 1 час!")
        elif action == "unmute":
            await context.bot.restrict_chat_member(chat_id, target_user.id, ChatPermissions(can_send_messages=True))
            await update.message.reply_text(f"🔊 {target_user.full_name} размьючен!")
        elif action == "ban":
            await context.bot.ban_chat_member(chat_id, target_user.id)
            await update.message.reply_text(f"⛔ {target_user.full_name} забанен!")
        elif action == "unban":
            await context.bot.unban_chat_member(chat_id, target_user.id)
            await update.message.reply_text(f"♻️ {target_user.full_name} разбанен!")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

# ----- Анти-мат -----
BAD_WORDS = {"лох", "дурак", "идиот", "тупой", "дебил", "сука", "блядь", "хуй", "пидор", "шлюха", "гандон"}

async def cmd_antimat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Включает/выключает фильтр мата для чата"""
    chat_id = str(update.effective_chat.id)
    settings_store.setdefault("antimat", {})
    settings_store["antimat"][chat_id] = not settings_store["antimat"].get(chat_id, False)
    save_json_safe(SETTINGS_FILE, settings_store)
    state = "включён" if settings_store["antimat"][chat_id] else "выключен"
    await update.message.reply_text(f"🛡 Анти-мат теперь {state} в этом чате.")

async def check_antimat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка на мат"""
    chat_id = str(update.effective_chat.id)
    if not settings_store.get("antimat", {}).get(chat_id, False):
        return
    if any(bad in update.message.text.lower() for bad in BAD_WORDS):
        try:
            await update.message.delete()
            await update.message.reply_text("🛑 Сообщение удалено: запрещённая лексика.")
        except:
            pass

# ----- Скачивание видео/аудио -----
async def download_media(url: str, audio_only=False):
    """Скачивание медиа (видео или только аудио) через yt_dlp"""
    ydl_opts = {
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "format": "bestaudio/best" if audio_only else "best",
        "quiet": True,
        "noplaylist": True,
    }
    Path("downloads").mkdir(exist_ok=True)
    loop = asyncio.get_event_loop()
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
            file_path = Path(ydl.prepare_filename(info))
        return file_path
    except Exception as e:
        logger.exception("download_media error: %s", e)
        return None

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """При получении ссылки — предлагаем выбрать формат"""
    url = update.message.text.strip()
    if not any(host in url for host in ["youtube.com", "youtu.be", "tiktok.com"]):
        return
    keyboard = [
        [InlineKeyboardButton("📹 Видео", callback_data=f"video|{url}")],
        [InlineKeyboardButton("🎵 Аудио", callback_data=f"audio|{url}")]
    ]
    await update.message.reply_text("Что хотите скачать?", reply_markup=InlineKeyboardMarkup(keyboard))

async def process_download_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice, url = query.data.split("|", 1)
    audio_only = choice == "audio"
    msg = await query.edit_message_text("⏳ Скачивание, подождите...")
    file_path = await download_media(url, audio_only=audio_only)
    if not file_path:
        await msg.edit_text("❌ Не удалось скачать файл.")
        return
    try:
        with open(file_path, "rb") as f:
            if audio_only:
                await query.message.reply_audio(f)
            else:
                await query.message.reply_video(f)
        os.remove(file_path)
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"Ошибка отправки файла: {e}")

# ----------------- Регистрация модерации/анти-мата/скачивания -----------------
def register_moderation_handlers(app: Application):
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_moderation_keywords))
    app.add_handler(CommandHandler("antimat", cmd_antimat))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_antimat))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(process_download_choice))# ================= Часть 4: Меню, регистрация команд, запуск =================

import asyncio
from telegram import BotCommandScopeDefault, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats

# ---------- UI: start / menu ----------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("start")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎭 Развлечения", callback_data="menu:entertain")],
        [InlineKeyboardButton("🎥 Медиа (скачать)", callback_data="menu:media")],
        [InlineKeyboardButton("😈 Donke", callback_data="menu:donke")],
        [InlineKeyboardButton("🛡 Модерация", callback_data="menu:moderation")],
        [InlineKeyboardButton("🔎 Полезное", callback_data="menu:useful")],
    ])
    text = "👋 *MultiBotX* — привет! Нажми на кнопку ниже, чтобы открыть меню или введи /menu."
    try:
        await update.message.reply_markdown(text, reply_markup=kb)
    except Exception:
        await update.message.reply_text("Привет! Введи /menu для показа меню.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Я MultiBotX — бот с развлечениями, модерацией и скачиванием медиа.\n"
        "Введи /menu или нажми кнопку в меню."
    )

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # повторяем стартовое меню (воспользуемся той же разметкой)
    await start_cmd(update, context)

# ---------- Commands registration (robust, async) ----------
BOT_COMMANDS_LIST = [(c.command, c.description) for c in BOT_COMMANDS]

async def _set_commands_once(bot):
    commands = [BotCommand(name, desc) for name, desc in BOT_COMMANDS_LIST]
    scopes = [BotCommandScopeDefault(), BotCommandScopeAllPrivateChats(), BotCommandScopeAllGroupChats()]
    last_exc = None
    for attempt in range(1, 4):
        try:
            for scope in scopes:
                await bot.set_my_commands(commands, scope=scope)
            logger.info("Commands set (attempt %d)", attempt)
            return True
        except Exception as e:
            last_exc = e
            logger.warning("set_my_commands attempt %d failed: %s", attempt, e)
            await asyncio.sleep(2 * attempt)
    logger.exception("Failed to set commands after attempts: %s", last_exc)
    return False

def register_commands_sync(app_obj):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_set_commands_once(app_obj.bot))
        loop.close()
    except Exception:
        logger.exception("register_commands_sync failed")

# Manual handlers to set/check commands from chat
async def setcommands_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # allow only admin or chat admins
    allowed = False
    if ADMIN_ID and str(user.id) == str(ADMIN_ID):
        allowed = True
    try:
        member = await update.effective_chat.get_member(user.id)
        if member.status in ("administrator", "creator"):
            allowed = True
    except Exception:
        if update.effective_chat.type == "private":
            allowed = True
    if not allowed:
        await update.message.reply_text("Только админы могут обновлять команды.")
        return
    await update.message.reply_text("Обновляю команды... проверь логи.")
    try:
        ok = await _set_commands_once(context.bot)
        await update.message.reply_text("Команды установлены." if ok else "Не удалось установить команды, см. логи.")
    except Exception as e:
        log_error(e)
        await update.message.reply_text("Ошибка при установке команд.")

async def checkcommands_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cmds = await context.bot.get_my_commands()
        if not cmds:
            await update.message.reply_text("Команды не установлены.")
            return
        lines = [f"/{c.command} — {c.description}" for c in cmds]
        await update.message.reply_text("Установленные команды:\n" + "\n".join(lines))
    except Exception as e:
        log_error(e)
        await update.message.reply_text("Ошибка при получении команд.")

# ---------- Register all handlers into application ----------
def build_application():
    app = Application.builder().token(BOT_TOKEN).build()

    # basic commands / menu
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("menu", menu_cmd))

    # entertainment / data
    register_entertainment_handlers(app)

    # moderation / antimat / download
    register_moderation_handlers(app)

    # manual commands for commands management
    app.add_handler(CommandHandler("setcommands", setcommands_cmd))
    app.add_handler(CommandHandler("checkcommands", checkcommands_cmd))

    # other utilities
    app.add_handler(CommandHandler("remindme", remindme_cmd))
    app.add_handler(CommandHandler("searchimage", searchimage_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("avatar", avatar_cmd))

    # ensure error handler registered if exists
    try:
        app.add_error_handler(error_handler)
    except Exception:
        pass

    return app

# ---------- Reminder worker starter ----------
def start_reminder_worker(app):
    thr = threading.Thread(target=lambda: reminder_worker(app), daemon=True)
    thr.start()

# ---------- Run: Flask (health) + Bot (polling) ----------
def run():
    application = build_application()

    # register commands on start (if enabled)
    if COMMANDS_SETUP:
        logger.info("COMMANDS_SETUP enabled — registering commands...")
        register_commands_sync(application)

    # start Flask health server on separate thread
    flask_thr = threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=PORT), daemon=True)
    flask_thr.start()
    logger.info("Flask health server started on port %s", PORT)

    # start reminder worker
    try:
        start_reminder_worker(application)
    except Exception:
        logger.exception("Failed to start reminder worker")

    # run bot polling
    logger.info("Starting bot polling...")
    application.run_polling()

if __name__ == "__main__":
    run()