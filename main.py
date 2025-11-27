import os
import json
import random
from datetime import datetime, timedelta
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
)

# -------------------------------
# Настройка переменных окружения
# -------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SAVE_TUBE_API_KEY = os.environ.get("SAVE_TUBE_API_KEY", "")
RANDOM_HOST = os.environ.get("RENDER_EXTERNAL_HOSTNAME")

# -------------------------------
# Настройка Flask
# -------------------------------
app = Flask(__name__)# -------------------------------
# Файл для хранения данных участников cumdonke
# -------------------------------
DATA_FILE = "cumdonke_data.json"

# Загрузка данных
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        cum_data = json.load(f)
else:
    cum_data = {
        "players": {},  # user_id: {"name": "Имя", "total": 0, "last_date": "YYYY-MM-DD"}
        "donke_name": "Донке"
    }

# Сохранение данных
def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(cum_data, f, ensure_ascii=False, indent=2)# -------------------------------
# Список пасхалок для реакции на слово cumdonke
# -------------------------------
CUM_PHRASES = [
    "{name} облизывается…",
    "{name} хищно облизывается и благодарит вас за очередную порцию",
    "{name} посмотрел на вас как на добычу…",
    "{name} высунул язык… опасно.",
    "{name} сделал *шлёп*",
    "{name} злорадно улыбается",
    "{name} метко присмотрелся к вам",
    "{name} хмыкнул и поднял бровь",
]

# -------------------------------
# Команда для установки имени Донке
# -------------------------------
async def setdonke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        new_name = " ".join(context.args)
        cum_data["donke_name"] = new_name
        save_data()
        await update.message.reply_text(f"Имя Донке установлено: {new_name}")
    else:
        await update.message.reply_text("Использование: /setdonke <имя>")

# -------------------------------
# Реакция на ключевое слово в чате
# -------------------------------
async def word_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "cumdonke" in text:
        phrase = random.choice(CUM_PHRASES).format(name=cum_data["donke_name"])
        await update.message.reply_text(phrase)

# -------------------------------
# Команда cumdonke — залив семени
# -------------------------------
async def cumdonke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    today = datetime.now().strftime("%Y-%m-%d")

    player = cum_data["players"].get(user_id, {"name": update.message.from_user.first_name, "total": 0, "last_date": ""})

    # Проверка, заливал ли сегодня
    if player["last_date"] == today:
        await update.message.reply_text("Ты уже заливал семя сегодня! Попробуй завтра.")
        return

    # Рандомное количество залитого семени (-30% шанс на минус)
    if random.randint(1, 100) <= 30:
        amount = -random.randint(1, 50)
    else:
        amount = random.randint(1, 100)

    player["total"] += amount
    player["last_date"] = today
    cum_data["players"][user_id] = player
    save_data()

    await update.message.reply_text(f"{cum_data['donke_name']} принял {amount} литров! Твой общий результат: {player['total']} литров.")# -------------------------------
# Команда топдонке — топ 100 участников
# -------------------------------
async def topdonke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    players = cum_data["players"]
    if not players:
        await update.message.reply_text("Пока нет участников.")
        return

    # Сортировка по total, убывание
    sorted_players = sorted(players.items(), key=lambda x: x[1]["total"], reverse=True)[:100]

    text = "🏆 Топ 100 участников по залитому семени:\n\n"
    for i, (user_id, info) in enumerate(sorted_players, 1):
        text += f"{i}. {info['name']} — {info['total']} литров\n"

    await update.message.reply_text(text)

# -------------------------------
# Пример простых развлекательных функций
# -------------------------------
JOKES = [
    "Почему программисты не любят природу? Слишком много багов.",
    "Я сегодня не опаздываю, я просто тестирую закон относительности.",
]

FACTS = [
    "Кот может спать до 16 часов в день.",
    "Медузы существуют уже более 500 миллионов лет.",
]

async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(JOKES))

async def fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(FACTS))# -------------------------------
# Инициализация Telegram бота
# -------------------------------
app_telegram = ApplicationBuilder().token(BOT_TOKEN).build()

# -------------------------------
# Регистрация команд
# -------------------------------
app_telegram.add_handler(CommandHandler("setdonke", setdonke))
app_telegram.add_handler(CommandHandler("cumdonke", cumdonke_command))
app_telegram.add_handler(CommandHandler("topdonke", topdonke_command))
app_telegram.add_handler(CommandHandler("joke", joke))
app_telegram.add_handler(CommandHandler("fact", fact))

# -------------------------------
# Ловим слово cumdonke без слэша
# -------------------------------
app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, word_trigger))

# -------------------------------
# Flask route для webhook
# -------------------------------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), app_telegram.bot)
    app_telegram.update_queue.put(update)
    return "ok", 200

# -------------------------------
# Главная страница для проверки
# -------------------------------
@app.route("/")
def index():
    return "Bot is running!"if __name__ == "__main__":
    # Устанавливаем webhook для Render
    from telegram import Bot
    bot = Bot(token=BOT_TOKEN)
    bot.set_webhook(url=f"https://{RANDOM_HOST}/{BOT_TOKEN}")

    # Запуск Flask
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))# -------------------------------
# Модерация через обычные слова
# -------------------------------
warned_users = {}  # user_id: количество варнов
muted_users = {}   # user_id: until datetime

# Фильтр слов для мата
BAD_WORDS = ["плохое_слово1", "плохое_слово2"]  # добавь свои слова

async def moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.lower()

    # Проверка на мут
    if user_id in muted_users:
        if datetime.now() < muted_users[user_id]:
            await update.message.delete()
            return
        else:
            del muted_users[user_id]

    # Проверка на мат
    if any(word in text for word in BAD_WORDS):
        warned_users[user_id] = warned_users.get(user_id, 0) + 1
        await update.message.reply_text(f"{update.message.from_user.first_name}, мат запрещен! Варнов: {warned_users[user_id]}")
        if warned_users[user_id] >= 3:
            muted_users[user_id] = datetime.now() + timedelta(minutes=10)
            warned_users[user_id] = 0
            await update.message.reply_text(f"{update.message.from_user.first_name} замучен на 10 минут!")# Приветствие новых участников
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(f"Добро пожаловать, {member.full_name}! 👋")

# Антифлуд — удаляем сообщение, если одно и то же подряд
recent_messages = {}  # user_id: last_text
async def anti_flood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    if recent_messages.get(user_id) == text:
        await update.message.delete()
    recent_messages[user_id] = textimport yt_dlp

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        url = context.args[0]
        await update.message.reply_text("Скачиваю видео...")
        try:
            ydl_opts = {
                'outtmpl': 'downloads/%(title)s.%(ext)s',
                'format': 'bestvideo+bestaudio/best',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
            file_name = f"downloads/{info['title']}.{info['ext']}"
            await update.message.reply_document(document=open(file_name, 'rb'))
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {e}")
    else:
        await update.message.reply_text("Использование: /download <ссылка на видео>")async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Joke 😂", callback_data='joke')],
        [InlineKeyboardButton("Fact 📚", callback_data='fact')],
        [InlineKeyboardButton("Cumdonke 💦", callback_data='cumdonke')],
        [InlineKeyboardButton("TopDonke 🏆", callback_data='topdonke')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Главное меню:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "joke":
        await query.edit_message_text(random.choice(JOKES))
    elif query.data == "fact":
        await query.edit_message_text(random.choice(FACTS))
    elif query.data == "cumdonke":
        await cumdonke_command(update, context)
    elif query.data == "topdonke":
        await topdonke_command(update, context)# -------------------------------
# Регистрация модерации и автофункций
# -------------------------------
app_telegram.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, moderation))
app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, anti_flood))

# Кнопки меню
app_telegram.add_handler(CommandHandler("menu", main_menu))
app_telegram.add_handler(CallbackQueryHandler(button_handler))

# Скачивание видео
app_telegram.add_handler(CommandHandler("download", download_video))