import os
import random
import time
import logging
import requests
from datetime import datetime, timedelta
from flask import Flask, request
from threading import Thread
from collections import defaultdict
from telegram import Update, ChatPermissions
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackContext
)

# Настройки
TOKEN = os.getenv("TOKEN")
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Данные
warns = defaultdict(int)
donke_data = defaultdict(lambda: {'liters': 0, 'last': None})
log_data = []
start_time = time.time()

# Шутки и цитаты
jokes = [
    "Почему программисты не любят природу? Там слишком много багов.",
    "Интернет без котиков — это просто кабель.",
    "Я не лентяй, я в режиме энергосбережения."
]

donke_jokes = [
    "Donke настолько тупой, что думает, что RAM — это барашек.",
    "Donke попытался сесть в интернет… теперь у него синяк.",
    "Donke — это ошибка 404: интеллект не найден.",
    "Donke — живое доказательство, что деградация возможна."
]

quotes = [
    "Будь собой — прочие роли уже заняты.",
    "Не бойся идти медленно, бойся стоять на месте.",
    "Тот, кто хочет — ищет возможность, кто не хочет — оправдание.",
    "Каждое утро мы рождаемся вновь. Что мы делаем сегодня — важнее всего."
]

facts = [
    "Муравьи никогда не спят.",
    "Осьминоги имеют три сердца.",
    "Самая большая снежинка — 38 см.",
    "Пчёлы могут узнавать лица людей."
]

# Flask
@app.route('/')
def index():
    return "MultiBotX is running!"

@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return 'ok'

# Хэндлеры

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Я — MultiBotX. Напиши /help чтобы узнать, что я умею.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 *Команды:*\n"
        "- /joke — случайная шутка\n"
        "- /donke — чёрный юмор про Donke\n"
        "- /fact — случайный факт\n"
        "- /quote — мотивационная цитата\n"
        "- /cat /dog — фото котиков и собак\n"
        "- /dice — бросок кубика 🎲\n"
        "- /camdonke — 💦 заливка в Донке\n"
        "- /topdonke — рейтинг донкозаливателей\n"
        "- /stats — статистика\n"
        "- /log — лог активности\n"
        "- Просто ответь на сообщение с текстом мут, бан, варн и т.д."
    , parse_mode='Markdown')

async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(jokes))

async def donke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(donke_jokes))

async def fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(facts))

async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(quotes))

async def cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = requests.get("https://api.thecatapi.com/v1/images/search").json()
    await update.message.reply_photo(res[0]['url'])

async def dog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = requests.get("https://dog.ceo/api/breeds/image/random").json()
    await update.message.reply_photo(res['message'])

async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_dice()

# Donke Кампания
async def camdonke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    today = datetime.utcnow().date()
    data = donke_data[user_id]

    if data['last'] == today:
        await update.message.reply_text("💦 Вы уже залили в Донке сегодня! Возвращайтесь завтра.")
        return

    liters = random.randint(1, 100)
    data['liters'] += liters
    data['last'] = today

    await update.message.reply_text(
        f"💦 Вы успешно залили в Донке {liters} литров спермы!\n"
        f"Donke говорит спасибо... и стонет..."
    )

async def topdonke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = sorted(donke_data.items(), key=lambda x: x[1]['liters'], reverse=True)[:50]
    msg = "🏆 *Топ донатеров в Donke:*\n\n"
    for i, (user_id, data) in enumerate(top, start=1):
        msg += f"{i}. [id:{user_id}] — {data['liters']} литров\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

# Видео загрузка
async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "tiktok.com" in url:
        api_url = f"https://api.tikmate.app/api/lookup?url={url}"
    elif "youtube.com" in url or "youtu.be" in url:
        api_url = f"https://api.yt1s.com/api/ajaxSearch/index?q={url}&vt=home"
    else:
        await update.message.reply_text("❌ Это не ссылка на видео.")
        return

    await update.message.reply_text("⏳ Пытаюсь скачать видео...")

    try:
        r = requests.get(api_url)
        if r.status_code == 200:
            await update.message.reply_text("✅ Видео успешно загружено (но функция требует доработки).")
        else:
            await update.message.reply_text("❌ Не удалось скачать. Попробуйте позже.")
    except Exception as e:
        await update.message.reply_text("❌ Ошибка при скачивании.")

# Модерация
async def moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        text = update.message.text.lower()
        target = update.message.reply_to_message.from_user
        chat_id = update.effective_chat.id

        try:
            if "варн" in text:
                warns[target.id] += 1
                await update.message.reply_text(f"⚠️ Предупреждение для {target.first_name} ({warns[target.id]}/3)")
            elif "мут" in text:
                await context.bot.restrict_chat_member(chat_id, target.id, ChatPermissions(can_send_messages=False))
                await update.message.reply_text(f"🔇 {target.first_name} был замучен.")
            elif "размут" in text or "анмут" in text:
                await context.bot.restrict_chat_member(chat_id, target.id, ChatPermissions(can_send_messages=True))
                await update.message.reply_text(f"🔊 {target.first_name} был размучен.")
            elif "бан" in text:
                await context.bot.ban_chat_member(chat_id, target.id)
                await update.message.reply_text(f"⛔ {target.first_name} забанен.")
            elif "разбан" in text or "унбан" in text:
                await context.bot.unban_chat_member(chat_id, target.id)
                await update.message.reply_text(f"✅ {target.first_name} разбанен.")
        except:
            await update.message.reply_text("❌ У меня нет прав для этого.")

# Автофункции
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(f"👋 Добро пожаловать, {member.first_name}!")

async def mat_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.lower()
    if any(mat in msg for mat in ["бляд", "сука", "нах", "чмо", "пид", "хуй"]):
        await update.message.delete()

# Статистика
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = int(time.time() - start_time)
    users = len(donke_data)
    await update.message.reply_text(f"📊 Uptime: {uptime//60} минут\n👤 Пользователей: {users}")

async def log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if log_data:
        await update.message.reply_text("🗂️ Лог:\n" + "\n".join(log_data[-10:]))
    else:
        await update.message.reply_text("📭 Лог пуст.")

async def save_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_data.append(f"{update.effective_user.id}: {update.message.text}")

# Настройка приложения
application = Application.builder().token(TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("joke", joke))
application.add_handler(CommandHandler("donke", donke))
application.add_handler(CommandHandler("fact", fact))
application.add_handler(CommandHandler("quote", quote))
application.add_handler(CommandHandler("cat", cat))
application.add_handler(CommandHandler("dog", dog))
application.add_handler(CommandHandler("dice", dice))
application.add_handler(CommandHandler("camdonke", camdonke))
application.add_handler(CommandHandler("topdonke", topdonke))
application.add_handler(CommandHandler("stats", stats))
application.add_handler(CommandHandler("log", log))

application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, moderation))
application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'https?://'), download_video))
application.add_handler(MessageHandler(filters.TEXT, save_log))
application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
application.add_handler(MessageHandler(filters.TEXT, mat_filter))

# Запуск Flask
def run():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

Thread(target=run).start()
application.run_polling() 