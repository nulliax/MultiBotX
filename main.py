import os
import random
import logging
import requests
from flask import Flask, request
from telegram import Update, InputFile
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from datetime import datetime, timedelta
import yt_dlp

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [123456789]  # Замени на свой ID

app = Flask(__name__)
bot_app = Application.builder().token(TOKEN).build()

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Хранилище
warns = {}
mutes = {}
camdonke_db = {}
last_camdonke = {}

# --- УТИЛИТЫ ---

def log_command(user, command):
    logging.info(f"{user.full_name} ({user.id}) использовал: {command}")

def is_admin(user_id):
    return user_id in ADMIN_IDS

# --- ФУНКЦИИ РАЗВЛЕЧЕНИЯ ---

jokes = [
    "Почему программисты путают Хэллоуин и Рождество? Потому что OCT 31 == DEC 25.",
    "Жена: «Ты опять сидишь за компьютером?!» Программист: «Нет, я сижу перед...»",
    "— Сколько нужно программистов, чтобы заменить лампочку?\n— Ни одного. Это аппаратная проблема."
]

facts = [
    "Самая большая снежинка имела диаметр 38 см.",
    "Осьминоги имеют три сердца.",
    "Пчёлы могут видеть ультрафиолетовый свет."
]

quotes = [
    "«Будь собой, остальные роли уже заняты» — Оскар Уайльд.",
    "«Мудрость приходит не с возрастом, а с опытом» — Альберт Эйнштейн.",
    "«Чем больше знаешь, тем больше понимаешь, что ничего не знаешь» — Сократ."
]

donke_jokes = [
    "Donke однажды упал… Земля отскочила.",
    "Если Donke смотрит на тебя — ты уже проиграл.",
    "Donke не пользуется Google, Google пользуется Donke."
]

# --- КОМАНДЫ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_command(update.effective_user, "/start")
    await update.message.reply_text(
        "👋 Привет! Я MultiBotX. Пиши /help, чтобы узнать мои команды!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_command(update.effective_user, "/help")
    await update.message.reply_text("""
📋 *Команды*:
🎉 /joke – Шутка  
📚 /fact – Факт  
🧠 /quote – Цитата  
🐱 /cat – Кот  
🐶 /dog – Пёс  
🎲 /dice – Кинуть кубик  
🧪 /camdonke – Залить в Donke  
🏆 /topdonke – Топ Donke  
🎬 Отправь ссылку на TikTok/YouTube — я скачаю видео

👮 Модерация (ответом): варн, мут, размут, бан, анбан
""", parse_mode="Markdown")

async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(jokes))

async def fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(facts))

async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(quotes))

async def cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = "https://cataas.com/cat"
    await update.message.reply_photo(url)

async def dog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = requests.get("https://dog.ceo/api/breeds/image/random").json()
    await update.message.reply_photo(r['message'])

async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_dice()

# --- DONKE ---

async def camdonke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = datetime.utcnow().date()
    if last_camdonke.get(user_id) == today:
        await update.message.reply_text("💦 Вы уже заливали сегодня в Donke!")
        return

    amount = random.randint(1, 100)
    camdonke_db[user_id] = camdonke_db.get(user_id, 0) + amount
    last_camdonke[user_id] = today
    await update.message.reply_text(
        f"💦 Вы успешно залили {amount} литров в Donke!\n"
        "Спасибо за вклад, возвращайтесь завтра!"
    )

async def topdonke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = sorted(camdonke_db.items(), key=lambda x: x[1], reverse=True)[:50]
    text = "🏆 *ТОП Donke (литры)*:\n"
    for i, (user_id, amount) in enumerate(top, 1):
        text += f"{i}. [id{user_id}|Пользователь] — {amount}л\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# --- МОДЕРАЦИЯ ---

async def moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return

    text = update.message.text.lower()
    user = update.message.reply_to_message.from_user
    chat_id = update.message.chat_id

    if "варн" in text:
        warns[user.id] = warns.get(user.id, 0) + 1
        await update.message.reply_text(f"⚠️ Предупреждение выдано {user.full_name}")
    elif "мут" in text:
        until = datetime.now() + timedelta(minutes=10)
        await context.bot.restrict_chat_member(chat_id, user.id, permissions=telegram.ChatPermissions(), until_date=until)
        await update.message.reply_text(f"🔇 {user.full_name} замучен на 10 минут")
    elif "размут" in text or "анмут" in text:
        await context.bot.restrict_chat_member(chat_id, user.id, permissions=telegram.ChatPermissions(can_send_messages=True))
        await update.message.reply_text(f"🔈 {user.full_name} размучен")
    elif "бан" in text:
        await context.bot.ban_chat_member(chat_id, user.id)
        await update.message.reply_text(f"⛔ {user.full_name} забанен")
    elif "анбан" in text:
        await context.bot.unban_chat_member(chat_id, user.id)
        await update.message.reply_text(f"✅ {user.full_name} разбанен")

# --- ВИДЕО ---

async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "tiktok.com" in url or "youtube.com" in url or "youtu.be" in url:
        await update.message.reply_text("⏬ Пытаюсь скачать видео...")

        ydl_opts = {
            'outtmpl': 'video.%(ext)s',
            'format': 'mp4',
            'quiet': True
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_file = ydl.prepare_filename(info)
                await update.message.reply_video(video=open(video_file, 'rb'))
                os.remove(video_file)
        except Exception as e:
            await update.message.reply_text(f"❌ Не удалось скачать видео.\nОшибка: {e}")

# --- АВТОФУНКЦИИ ---

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(f"👋 Добро пожаловать, {member.full_name}!")

# --- ОБРАБОТЧИКИ ---

bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("help", help_command))
bot_app.add_handler(CommandHandler("joke", joke))
bot_app.add_handler(CommandHandler("fact", fact))
bot_app.add_handler(CommandHandler("quote", quote))
bot_app.add_handler(CommandHandler("cat", cat))
bot_app.add_handler(CommandHandler("dog", dog))
bot_app.add_handler(CommandHandler("dice", dice))
bot_app.add_handler(CommandHandler("camdonke", camdonke))
bot_app.add_handler(CommandHandler("topdonke", topdonke))

bot_app.add_handler(MessageHandler(filters.TEXT & filters.REPLY, moderation))
bot_app.add_handler(MessageHandler(filters.TEXT & filters.Regex("http"), video_handler))
bot_app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

# --- FLASK (для Render) ---

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    bot_app.update_queue.put(update)
    return "ok"

@app.route("/")
def index():
    return "MultiBotX работает!"

if __name__ == "__main__":
    import telegram
    from telegram.constants import ChatAction

    bot_app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get('PORT', 5000)),
        webhook_url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{TOKEN}"
    )