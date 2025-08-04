import os
import random
import logging
from flask import Flask, request
from telegram import Update, ChatPermissions, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import requests
from datetime import datetime, timedelta
from collections import defaultdict

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "MultiBotX_bot")

# Flask
app = Flask(__name__)

# Донке рейтинг
donke_ratings = defaultdict(int)
last_camdonke_time = {}

# База шуток
jokes = [
    "Почему программисты любят зиму? Потому что можно ставить снежные точки.",
    "Какая разница между политиком и котом? Кот хотя бы не врёт в глаза.",
    "Я спросил у Siri: «Где моя девушка?» Она ответила: «В параллельной реальности».",
    "Системный администратор — это волшебник, только без мантии и с кофе.",
    "Если не работает — перезагрузи. Не помогает? Перезагрузи ещё раз.",
    "Google знает о тебе больше, чем твоя мама.",
    "Главное в жизни — не сдаваться. Особенно интернету.",
    "Python — это когда всё просто. До момента, пока не станет сложно.",
    "Не бейся головой об клавиатуру... хотя... может получиться пароль.",
    "Работаешь? Молодец. Не работаешь? Молодец, отдыхать тоже надо."
]

quotes = [
    "«Будь собой. Прочие роли уже заняты.» — Оскар Уайльд",
    "«Мудрый человек требует всего от себя, ничтожный — от других.» — Лев Толстой",
    "«Падая, поднимайся. Проигрывая, учись.» — Конфуций",
    "«Лучше сделать и пожалеть, чем не сделать и пожалеть.» — Неизвестный философ",
    "«Глуп тот, кто не учится на своих ошибках. Умён тот, кто учится на чужих.»",
    "«Если долго смотреть в бездну, бездна начнёт смотреть в тебя.» — Ницше",
]

facts = [
    "Муравьи никогда не спят.",
    "У улиток три сердца.",
    "Самая сильная мышца в теле — язык.",
    "Шоколад может убить собаку.",
    "Глаза страуса больше его мозга.",
    "Крысы смеются, когда их щекотать.",
    "Мёд не портится. Его можно есть спустя тысячи лет.",
    "У осьминога три сердца и синяя кровь.",
]

donke_phrases = [
    "Donke разозлился и пошёл искать тебя.",
    "Donke теперь знает, где ты живёшь.",
    "Donke засмеялся, но это был последний смех в этом чате.",
    "Donke съел Wi-Fi и теперь ты в оффлайне.",
    "Donke... просто Donke.",
    "Donke уже рядом.",
    "Donke идёт за тобой, он уже в пути.",
]

banned_words = ["дурак", "тупой", "идиот", "лох", "петух"]  # и т.д.

# Приветствие
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.new_chat_members:
        for user in update.message.new_chat_members:
            await update.message.reply_text(f"👋 Добро пожаловать, {user.full_name}!")

# Антимат
async def filter_bad_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if any(word in text for word in banned_words):
        await update.message.reply_text("🚫 Не ругайся! Мат запрещён.")

# Команды развлечений
async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(jokes))

async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(quotes))

async def fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(facts))

async def cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = "https://cataas.com/cat"
    await update.message.reply_photo(photo=url)

async def dog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = "https://random.dog/woof.json"
    data = requests.get(url).json()
    await update.message.reply_photo(photo=data["url"])

async def meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = "https://meme-api.com/gimme"
    data = requests.get(url).json()
    await update.message.reply_photo(photo=data["url"])

async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_dice()

# Donke
async def donke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(donke_phrases))

async def camdonke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    now = datetime.utcnow()
    last_time = last_camdonke_time.get(user_id)

    if last_time and now - last_time < timedelta(days=1):
        await update.message.reply_text("🥵 Вы уже сегодня кончили в Донке. Попробуйте завтра.")
        return

    amount = random.randint(1, 100)
    donke_ratings[user_id] += amount
    last_camdonke_time[user_id] = now
    await update.message.reply_text(f"💦 Вы успешно залили в Donke {amount} литров спермы. Donke вами доволен. Возвращайтесь завтра.")

async def topdonke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not donke_ratings:
        await update.message.reply_text("Donke пока пуст. Залей спермы первым!")
        return
    top = sorted(donke_ratings.items(), key=lambda x: x[1], reverse=True)[:50]
    text = "🏆 ТОП Донкеров:\n\n"
    for i, (uid, amount) in enumerate(top, 1):
        user = await context.bot.get_chat(uid)
        text += f"{i}. {user.first_name}: {amount} л\n"
    await update.message.reply_text(text)

# Модерация
async def moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    reply = update.message.reply_to_message
    if not reply:
        return

    chat_id = update.message.chat.id
    user_id = reply.from_user.id

    if "мут" in text:
        await context.bot.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=False))
        await update.message.reply_text("🔇 Пользователь замучен.")
    elif "размут" in text or "анмут" in text:
        await context.bot.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=True))
        await update.message.reply_text("🔊 Пользователь размучен.")
    elif "бан" in text:
        await context.bot.ban_chat_member(chat_id, user_id)
        await update.message.reply_text("⛔ Пользователь забанен.")
    elif "разбан" in text or "унбан" in text:
        await context.bot.unban_chat_member(chat_id, user_id)
        await update.message.reply_text("✅ Пользователь разбанен.")
    elif "варн" in text:
        await update.message.reply_text("⚠️ Пользователь получил предупреждение.")

# Загрузка видео
async def tiktok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        url = context.args[0]
        if "tiktok.com" not in url:
            await update.message.reply_text("❌ Это не ссылка на TikTok.")
            return
        await update.message.reply_text("⏳ Скачиваю видео...")
        api_url = f"https://tikwm.com/api/?url={url}"
        res = requests.get(api_url).json()
        video_url = res.get("data", {}).get("play")
        if video_url:
            await update.message.reply_video(video=video_url)
        else:
            await update.message.reply_text("⚠️ Не удалось получить видео.")

async def youtube(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        url = context.args[0]
        if "youtube.com" not in url and "youtu.be" not in url:
            await update.message.reply_text("❌ Это не ссылка на YouTube.")
            return
        await update.message.reply_text("⏳ Обрабатываю видео...")
        api_url = f"https://ytmate.guru/api/ytvideo?url={url}"
        res = requests.get(api_url).json()
        link = res.get("download_url")
        if link:
            await update.message.reply_text(f"📥 Вот ссылка для скачивания:\n{link}")
        else:
            await update.message.reply_text("⚠️ Не удалось получить видео.")

# /start и /help
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Я многофункциональный бот MultiBotX.\n\n🛠 Доступные команды:\n/joke, /quote, /fact, /cat, /dog, /meme, /dice\n/donke, /camdonke, /topdonke\n/tiktok <ссылка>\n/youtube <ссылка>\n\n🔧 Просто напиши в ответ на сообщение: мут, размут, бан, разбан, варн.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🆘 Команды помощи:\n/start — Запуск\n/joke — Шутка\n/cat — Котик\n/donke — Donke\n/tiktok <ссылка> — Скачать TikTok\n/youtube <ссылка> — Скачать YouTube")

# Flask webhook
@app.route("/")
def home():
    return "MultiBotX is running!"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok"

# Запуск бота
application = ApplicationBuilder().token(TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_cmd))
application.add_handler(CommandHandler("joke", joke))
application.add_handler(CommandHandler("quote", quote))
application.add_handler(CommandHandler("fact", fact))
application.add_handler(CommandHandler("cat", cat))
application.add_handler(CommandHandler("dog", dog))
application.add_handler(CommandHandler("meme", meme))
application.add_handler(CommandHandler("dice", dice))
application.add_handler(CommandHandler("donke", donke))
application.add_handler(CommandHandler("camdonke", camdonke))
application.add_handler(CommandHandler("topdonke", topdonke))
application.add_handler(CommandHandler("tiktok", tiktok))
application.add_handler(CommandHandler("youtube", youtube))

application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, filter_bad_words))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, moderation))

if __name__ == "__main__":
    import threading

    def run_flask():
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

    threading.Thread(target=run_flask).start()
    application.run_polling()