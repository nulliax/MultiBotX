import os
import logging
import random
import datetime
import re
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext

app = Flask(__name__)
TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, update_queue=None, workers=4, use_context=True)
SAVETUBE_KEY = os.getenv("SAVETUBE_KEY")

admins = {}
warns = {}
donke_stats = {}
user_cam_time = {}

# ------------------ Основные функции ------------------ #

def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "👋 Привет! Я — многофункциональный бот MultiBotX!\n"
        "Вот что я умею:\n"
        "🔹 Модерация (без /): мут, варн, бан...\n"
        "🔹 Развлечения: шутки, донке, факты, цитаты\n"
        "🔹 Кошки, собаки, кубик 🎲\n"
        "🔹 Видео из TikTok и YouTube\n"
        "🔹 Пасхалки и многое другое!\n\n"
        "Напиши /help чтобы узнать все команды."
    )

def help_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "📖 Список команд:\n"
        "/start — запустить бота\n"
        "/help — помощь\n"
        "/joke — рандомная шутка\n"
        "/donke — шутка про Donke\n"
        "/fact — интересный факт\n"
        "/quote — цитата\n"
        "/cat — случайная кошка\n"
        "/dog — случайная собака\n"
        "/dice — бросить кубик 🎲\n"
        "/camdonke — залить в Донке\n"
        "/topdonke — топ донатеров в Донке\n"
        "🎬 Просто отправь ссылку на TikTok или YouTube"
    )

# ------------------ Развлечения ------------------ #

jokes = [
    "— Что делает программист в туалете?\n— Коммит 💩",
    "Если не запускается — перезапусти. Если не работает — удали прод.",
    "— Почему фронтендер не смог найти работу?\n— У него не было стилей 😅",
    "Умереть от шутки — это фатальная ошибка.",
    "Всё работает? Не трогай. Не работает? Всё равно не трогай."
]

donke_jokes = [
    "Donke пытался выучить Python, но написал вирус на Pascal.",
    "Donke думает, что HTML — это вирус от микроволновки.",
    "Donke поставил Linux… на бумагу.",
    "Donke учит JS 3-й год и всё ещё пишет alert('Привет!').",
    "Donke открыл TikTok и подумал, что это текстовый редактор."
]

facts = [
    "🔍 Люди моргают примерно 20 раз в минуту.",
    "🐙 У осьминога три сердца.",
    "🌌 Свет от Солнца доходит до Земли за 8 минут.",
    "🦋 Бабочки пробуют вкус лапками.",
    "🧠 Мозг потребляет 20% энергии тела."
]

quotes = [
    "💡 «Тот, кто хочет — ищет возможности, кто не хочет — ищет причины.»",
    "🔥 «Успех приходит к тем, кто действует, а не ждёт.»",
    "🚀 «Каждый шаг — это шанс стать лучше.»",
    "🧠 «Мудр тот, кто умеет слушать.»",
    "🌟 «Верить в себя — значит быть непобедимым.»"
]

def get_random(update: Update, items, label):
    update.message.reply_text(f"{label}\n\n{random.choice(items)}")

def joke(update: Update, context: CallbackContext):
    get_random(update, jokes, "😂 Шутка:")

def donke(update: Update, context: CallbackContext):
    get_random(update, donke_jokes, "🦍 Donke-юмор:")

def fact(update: Update, context: CallbackContext):
    get_random(update, facts, "📘 Факт:")

def quote(update: Update, context: CallbackContext):
    get_random(update, quotes, "📝 Цитата:")

def cat(update: Update, context: CallbackContext):
    r = requests.get("https://api.thecatapi.com/v1/images/search").json()
    update.message.reply_photo(r[0]["url"])

def dog(update: Update, context: CallbackContext):
    r = requests.get("https://dog.ceo/api/breeds/image/random").json()
    update.message.reply_photo(r["message"])

def dice(update: Update, context: CallbackContext):
    update.message.reply_dice()

# ------------------ Donke Cam ------------------ #

def camdonke(update: Update, context: CallbackContext):
    user = update.message.from_user
    uid = user.id
    today = datetime.date.today()

    if user_cam_time.get(uid) == today:
        update.message.reply_text("🤚 Сегодня ты уже заливал в Донке. Возвращайся завтра.")
        return

    amount = random.randint(1, 100)
    user_cam_time[uid] = today
    donke_stats[uid] = donke_stats.get(uid, 0) + amount

    update.message.reply_text(
        f"💦 Вы успешно залили в Donke {amount} литров спермы!\n"
        "🫃 Благодарим за вклад в генофонд Donke Nation™️."
    )

def topdonke(update: Update, context: CallbackContext):
    if not donke_stats:
        update.message.reply_text("😔 Пока никто не заливал в Donke.")
        return
    top = sorted(donke_stats.items(), key=lambda x: x[1], reverse=True)[:50]
    text = "🔥 Топ 50 заливщиков в Donke:\n\n"
    for i, (uid, amount) in enumerate(top, 1):
        name = bot.get_chat(uid).first_name
        text += f"{i}. {name} — {amount} л.\n"
    update.message.reply_text(text)

# ------------------ Видео из TikTok и YouTube ------------------ #

def download_video(update: Update, context: CallbackContext):
    url = update.message.text.strip()
    if not ("tiktok.com" in url or "youtube.com" in url or "youtu.be" in url):
        return
    update.message.reply_text("🔄 Пытаюсь скачать видео, подождите...")

    try:
        r = requests.post("https://api.savetube.me/info", json={"url": url}, headers={
            "X-API-KEY": SAVETUBE_KEY
        }).json()
        video_url = r["url"]
        title = r.get("title", "Видео")
        update.message.reply_video(video=video_url, caption=title)
    except Exception as e:
        update.message.reply_text("❌ Не удалось скачать видео. Попробуйте позже.")

# ------------------ Модерация без '/' ------------------ #

def moderation(update: Update, context: CallbackContext):
    text = update.message.text.lower()
    if update.message.reply_to_message is None:
        return

    cmd = text.strip()
    user = update.message.reply_to_message.from_user
    chat = update.message.chat

    try:
        if cmd == "мут":
            bot.restrict_chat_member(chat.id, user.id, permissions=telegram.ChatPermissions(can_send_messages=False))
            update.message.reply_text("🔇 Пользователь замучен.")
        elif cmd == "размут" or cmd == "анмут":
            bot.restrict_chat_member(chat.id, user.id, permissions=telegram.ChatPermissions(can_send_messages=True))
            update.message.reply_text("🔊 Пользователь размучен.")
        elif cmd == "варн":
            warns[user.id] = warns.get(user.id, 0) + 1
            update.message.reply_text(f"⚠️ Предупреждение ({warns[user.id]})")
        elif cmd == "бан":
            bot.kick_chat_member(chat.id, user.id)
            update.message.reply_text("⛔ Пользователь забанен.")
        elif cmd == "анбан" or cmd == "разбан":
            bot.unban_chat_member(chat.id, user.id)
            update.message.reply_text("✅ Пользователь разбанен.")
    except:
        update.message.reply_text("❌ Не удалось выполнить действие. У меня нет прав?")

# ------------------ Автофункции ------------------ #

def welcome(update: Update, context: CallbackContext):
    for member in update.message.new_chat_members:
        update.message.reply_text(f"👋 Добро пожаловать, {member.full_name}!")

def filter_swear(update: Update, context: CallbackContext):
    text = update.message.text.lower()
    bad_words = ["блин", "дурак", "идиот", "осёл"]
    if any(word in text for word in bad_words):
        update.message.delete()
        update.message.reply_text("🚫 Без мата!")

# ------------------ Обработка ------------------ #

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(CommandHandler("joke", joke))
dispatcher.add_handler(CommandHandler("donke", donke))
dispatcher.add_handler(CommandHandler("fact", fact))
dispatcher.add_handler(CommandHandler("quote", quote))
dispatcher.add_handler(CommandHandler("cat", cat))
dispatcher.add_handler(CommandHandler("dog", dog))
dispatcher.add_handler(CommandHandler("dice", dice))
dispatcher.add_handler(CommandHandler("camdonke", camdonke))
dispatcher.add_handler(CommandHandler("topdonke", topdonke))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, moderation))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, download_video))
dispatcher.add_handler(MessageHandler(Filters.status_update.new_chat_members, welcome))
dispatcher.add_handler(MessageHandler(Filters.text, filter_swear))

# ------------------ Flask ------------------ #

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    dispatcher.process_update(Update.de_json(request.get_json(force=True), bot))
    return "OK"

@app.route("/")
def index():
    return "MultiBotX работает!"

if __name__ == "__main__":
    bot.delete_webhook()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))