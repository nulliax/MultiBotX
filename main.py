import os
import logging
import random
import re
import threading
from flask import Flask, request
from dotenv import load_dotenv
from telegram import Update, ChatPermissions, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackContext
)
import requests
import yt_dlp

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME")
PORT = int(os.environ.get("PORT", 8443))

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask сервер
flask_app = Flask(__name__)

# Telegram Application
app = ApplicationBuilder().token(TOKEN).build()

# ============================
#        МОДЕРАЦИЯ
# ============================

warns = {}

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
        warns[user_id] = warns.get(user_id, 0) + 1
        await update.message.reply_text(f"⚠️ Предупреждение выдано. Всего: {warns[user_id]}")
        if warns[user_id] >= 3:
            await update.effective_chat.ban_member(user_id)
            await update.message.reply_text("❌ Пользователь забанен за 3 предупреждения.")
            warns[user_id] = 0
    else:
        await update.message.reply_text("⚠️ Используй команду в ответ на сообщение.")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        await update.effective_chat.restrict_member(
            update.message.reply_to_message.from_user.id,
            ChatPermissions(can_send_messages=False)
        )
        await update.message.reply_text("🔇 Пользователь замучен.")
    else:
        await update.message.reply_text("Ответь на сообщение пользователя для мута.")

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        await update.effective_chat.restrict_member(
            update.message.reply_to_message.from_user.id,
            ChatPermissions(can_send_messages=True,
                            can_send_media_messages=True,
                            can_send_other_messages=True,
                            can_add_web_page_previews=True)
        )
        await update.message.reply_text("🔊 Пользователь размучен.")
    else:
        await update.message.reply_text("Ответь на сообщение пользователя.")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        await update.effective_chat.ban_member(update.message.reply_to_message.from_user.id)
        await update.message.reply_text("🚫 Пользователь забанен.")
    else:
        await update.message.reply_text("Ответь на сообщение пользователя.")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        await update.effective_chat.unban_member(update.message.reply_to_message.from_user.id)
        await update.message.reply_text("✅ Пользователь разбанен.")
    else:
        await update.message.reply_text("Ответь на сообщение пользователя.")

# ============================
#        РАЗВЛЕЧЕНИЯ
# ============================

jokes = [
    "Почему программисты путают Хэллоуин и Рождество? Потому что OCT 31 == DEC 25!",
    "Как поймать белого медведя? Проруби в льду прорубь и рассыпь горох. Когда медведь придет собрать горох — бей его ледорубом!",
    "Я бы пошутил про UDP… но ты не получишь."
]

facts = [
    "Факт: У улиток три сердца.",
    "Факт: Самая длинная зарегистрированная продолжительность жизни у медузы – бессмертие.",
    "Факт: У осьминога три сердца и синяя кровь."
]

quotes = [
    "“Жизнь — это то, что с тобой происходит, пока ты строишь планы.” — Джон Леннон",
    "“Будь собой. Прочие роли уже заняты.” — Оскар Уайльд",
    "“Лучшая месть — огромный успех.” — Фрэнк Синатра"
]

donke_jokes = [
    "Donke пришёл в бар... Бар сломался.",
    "Donke настолько тупой, что его IQ можно измерить отрицательными числами.",
    "Если бы тупость была профессией, Donke получил бы Нобелевку."
]

async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(jokes))

async def fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(facts))

async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(quotes))

async def cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = "https://cataas.com/cat"
    await update.message.reply_photo(photo=url)

async def dog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = requests.get("https://random.dog/woof.json").json()["url"]
    await update.message.reply_photo(photo=url)

async def meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = "https://meme-api.com/gimme"
    meme = requests.get(url).json()
    await update.message.reply_photo(photo=meme["url"], caption=meme["title"])

async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_dice()

# ============================
#        ВИДЕО СКАЧИВАНИЕ
# ============================

def download_video(url):
    ydl_opts = {
        'outtmpl': 'video.%(ext)s',
        'format': 'mp4',
        'quiet': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ Укажи ссылку на TikTok или YouTube.")
        return
    url = context.args[0]
    msg = await update.message.reply_text("⏬ Загружаю видео, подожди...")

    try:
        video_path = download_video(url)
        with open(video_path, 'rb') as video_file:
            await update.message.reply_video(video=video_file)
        os.remove(video_path)
    except Exception as e:
        await msg.edit_text("❌ Ошибка загрузки видео.")
        logger.error(f"Ошибка при скачивании: {e}")

# ============================
#        ПАСХАЛКА
# ============================

async def donke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(donke_jokes))

# ============================
#       АВТОФУНКЦИИ
# ============================

async def greet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(f"👋 Добро пожаловать, {member.mention_html()}", parse_mode='HTML')

# Фильтр мата
banned_words = ["плохое", "слово", "мат"]

async def filter_bad_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if any(word in update.message.text.lower() for word in banned_words):
        await update.message.delete()

# ============================
#        ОБРАБОТЧИКИ
# ============================

app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Привет! Я MultiBotX.")))
app.add_handler(CommandHandler("help", lambda u, c: u.message.reply_text("/joke /fact /quote /cat /dog /meme /dice /download [url]")))
app.add_handler(CommandHandler("warn", warn))
app.add_handler(CommandHandler("mute", mute))
app.add_handler(CommandHandler("unmute", unmute))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("unban", unban))
app.add_handler(CommandHandler("joke", joke))
app.add_handler(CommandHandler("fact", fact))
app.add_handler(CommandHandler("quote", quote))
app.add_handler(CommandHandler("cat", cat))
app.add_handler(CommandHandler("dog", dog))
app.add_handler(CommandHandler("meme", meme))
app.add_handler(CommandHandler("dice", dice))
app.add_handler(CommandHandler("download", download))
app.add_handler(CommandHandler("donke", donke))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, greet))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), filter_bad_words))

# ============================
#       FLASK + POLLING
# ============================

@flask_app.route("/")
def home():
    return "MultiBotX is alive!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

def run_polling():
    app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    run_polling()