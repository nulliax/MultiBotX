# main.py — PTB v20 compatible (full)
import os
import logging
import random
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from threading import Thread
import asyncio
import traceback

from flask import Flask, request
import requests
import yt_dlp
from dotenv import load_dotenv

from telegram import Update, ChatPermissions
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# optional local .env for dev
load_dotenv()

# config
BOT_TOKEN = os.getenv("BOT_TOKEN")
HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")  # e.g. multibotx.onrender.com
PORT = int(os.getenv("PORT", 5000))
SAVETUBE_KEY = os.getenv("SAVETUBE_KEY", None)
MAX_SEND = 50 * 1024 * 1024  # 50 MB

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment")

# logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MultiBotX")

# data dir
DATA_DIR = Path("data"); DATA_DIR.mkdir(exist_ok=True)
DONKE_FILE = DATA_DIR / "donke.json"

def load_json(path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("load_json failed")
    return {}

def save_json(path, data):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logger.exception("save_json failed")

donke_db = load_json(DONKE_FILE)

# content
JOKES = ["Почему программисты путают Хэллоуин и Рождество? Потому что OCT 31 == DEC 25.", "Я бы рассказал шутку про UDP..."]
FACTS = ["У осьминога три сердца.", "Кошки спят до 20 часов в день."]
QUOTES = ["«Делай, что должен»", "«Лучше начать, чем жалеть»"]
BAD_WORDS = ["бляд", "хуй", "пизд", "сука"]

# helpers
def today_iso(): return datetime.utcnow().date().isoformat()

YTDL_OPTS = {"format": "mp4[ext=mp4]/best", "outtmpl": "tmp.%(ext)s", "noplaylist": True, "quiet": True, "no_warnings": True}
def yt_download(url):
    with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

# Flask
flask_app = Flask(__name__)

# Handlers
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Напиши /menu")

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню: /joke /fact /quote /cat /dog /meme /dice /donke /camdonke /topdonke\nОтправь ссылку на видео — постараюсь скачать.")

async def joke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(JOKES))

async def fact_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(FACTS))

async def quote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(QUOTES))

async def cat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://api.thecatapi.com/v1/images/search", timeout=10).json()
        await update.message.reply_photo(r[0]["url"])
    except Exception:
        await update.message.reply_text("Не удалось получить котика.")

async def dog_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://dog.ceo/api/breeds/image/random", timeout=10).json()
        await update.message.reply_photo(r["message"])
    except Exception:
        await update.message.reply_text("Не удалось получить собаку.")

async def meme_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://meme-api.com/gimme", timeout=10).json()
        await update.message.reply_photo(r["url"], caption=r.get("title", "Мем"))
    except Exception:
        await update.message.reply_text("Не удалось получить мем.")

async def dice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_dice()

# Donke
async def donke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Donke — легенда.")

async def camdonke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; uid = str(user.id)
    e = donke_db.get(uid, {"name": user.full_name, "total":0, "last":None})
    if e.get("last") == today_iso():
        await update.message.reply_text("Сегодня уже заливали.")
        return
    import random
    amount = random.randint(1,100)
    e["total"] = e.get("total",0) + amount
    e["last"] = today_iso()
    e["name"] = user.full_name
    donke_db[uid] = e; save_json(DONKE_FILE, donke_db)
    await update.message.reply_text(f"💦 Залито {amount} л. Приходи завтра!")

async def topdonke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not donke_db:
        await update.message.reply_text("Пусто.")
        return
    lst = sorted(donke_db.items(), key=lambda kv: kv[1].get("total",0), reverse=True)[:50]
    lines = [f"{i+1}. {v[1].get('name','?')} — {v[1].get('total',0)} л" for i,(k,v) in enumerate(lst)]
    await update.message.reply_text("\n".join(lines[:50]))

# moderation by reply text
async def moderation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.reply_to_message: return
    txt = msg.text.lower()
    target = msg.reply_to_message.from_user
    chat = msg.chat
    try:
        member = await chat.get_member(msg.from_user.id)
        if not (member.status in ("administrator","creator") or member.can_restrict_members):
            await msg.reply_text("Нет прав.")
            return
    except Exception:
        pass
    if "варн" in txt:
        # warns storage
        warns = context.bot_data.get("warns", {})
        warns[target.id] = warns.get(target.id,0)+1
        context.bot_data["warns"] = warns
        await msg.reply_text(f"⚠️ Предупреждение ({warns[target.id]})")
        if warns[target.id]>=3:
            await chat.ban_member(target.id); await msg.reply_text("Забанен (3).")
    elif "мут" in txt:
        until = datetime.utcnow()+timedelta(minutes=10)
        await chat.restrict_member(target.id, ChatPermissions(can_send_messages=False), until_date=until)
        await msg.reply_text("🔇 Мут.")
    elif txt in ("размут","анмут"):
        await chat.restrict_member(target.id, ChatPermissions(can_send_messages=True))
        await msg.reply_text("🔊 Размут.")
    elif "бан" in txt:
        await chat.ban_member(target.id); await msg.reply_text("🚫 Бан.")
    elif txt in ("разбан","унбан","анбан"):
        await chat.unban_member(target.id); await msg.reply_text("✅ Разбан.")

# welcome/profanity/flood
LAST = {}
async def welcome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.new_chat_members:
        for u in update.message.new_chat_members:
            await update.message.reply_text(f"Добро пожаловать, {u.full_name}!")

async def profanity_and_flood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text: return
    t = msg.text.lower()
    for b in BAD_WORDS:
        if b in t:
            try:
                await msg.delete(); await msg.reply_text("Не ругайся.")
            except: pass
            return
    key = (msg.chat.id, msg.from_user.id); now = datetime.utcnow().timestamp()
    arr = LAST.get(key,[]); arr = [x for x in arr if now-x<10]; arr.append(now); LAST[key]=arr
    if len(arr)>6:
        try:
            await msg.chat.restrict_member(msg.from_user.id, ChatPermissions(can_send_messages=False),
                                           until_date=datetime.utcnow()+timedelta(minutes=1))
            await msg.reply_text("Антифлуд: замучен на 1 минуту.")
        except: pass

# download (command or plain url)
async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = None
    if context.args: text=context.args[0]
    elif update.message and update.message.text:
        m=re.search(r"https?://\S+", update.message.text)
        if m: text=m.group(0)
    if not text: return
    url=text.strip()
    m=await update.message.reply_text("Пытаюсь скачать...")
    try:
        # try SaveTube for tiktok if key set
        if "tiktok.com" in url and SAVETUBE_KEY:
            try:
                headers={"X-RapidAPI-Key":SAVETUBE_KEY}
                api="https://save-tube-video-download.p.rapidapi.com/download"
                r=requests.get(api, headers=headers, params={"url":url}, timeout=15)
                j=r.json()
                if j.get("links"):
                    v=j["links"][0].get("url")
                    if v:
                        await update.message.reply_video(v); await m.delete(); return
            except:
                logger.exception("SaveTube failed")
        # fallback to yt_dlp
        fname=yt_download(url)
        size=os.path.getsize(fname)
        if size>MAX_SEND:
            await update.message.reply_text("Файл слишком большой для отправки.")
            os.remove(fname)
            await m.delete(); return
        with open(fname,"rb") as f:
            await update.message.reply_video(f)
        os.remove(fname); await m.delete()
    except Exception as e:
        logger.exception("Download error: %s", e)
        try:
            await m.edit_text("Ошибка скачивания.")
        except:
            pass

# error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Handler error: %s", context.error)
    try:
        tb="".join(traceback.format_exception(None, context.error, context.error.__traceback__))
        logger.error(tb)
    except Exception:
        pass

# build app
def build_app():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    # commands
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("menu", menu_cmd))
    application.add_handler(CommandHandler("joke", joke_cmd))
    application.add_handler(CommandHandler("fact", fact_cmd))
    application.add_handler(CommandHandler("quote", quote_cmd))
    application.add_handler(CommandHandler("cat", cat_cmd))
    application.add_handler(CommandHandler("dog", dog_cmd))
    application.add_handler(CommandHandler("meme", meme_cmd))
    application.add_handler(CommandHandler("dice", dice_cmd))
    application.add_handler(CommandHandler("donke", donke_cmd))
    application.add_handler(CommandHandler("camdonke", camdonke_cmd))
    application.add_handler(CommandHandler("topdonke", topdonke_cmd))
    application.add_handler(CommandHandler("download", download_handler))
    # messages
    application.add_handler(MessageHandler(filters.Regex(r"https?://"), download_handler))
    application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, moderation_handler))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, profanity_and_flood))
    application.add_error_handler(error_handler)
    return application

application = build_app()

# webhook endpoint
@flask_app.route("/", methods=["GET"])
def index_page():
    return "OK"

@flask_app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook_endpoint():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.update_queue.put_nowait(update)
    except Exception:
        logger.exception("Webhook failed")
    return "OK"

def run():
    if HOSTNAME:
        webhook_url=f"https://{HOSTNAME}/{BOT_TOKEN}"
        logger.info("Setting webhook %s", webhook_url)
        try:
            asyncio.run(application.bot.set_webhook(webhook_url))
        except Exception:
            logger.exception("set_webhook failed")
    # run flask
    t=Thread(target=lambda: flask_app.run(host="0.0.0.0", port=PORT))
    t.start()
    application.run_polling()

if __name__ == "__main__":
    run() 