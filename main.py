import os
import logging
import random
import re
import time
from datetime import datetime, timedelta

import requests
from flask import Flask, request
from telebot import TeleBot, types
from dotenv import load_dotenv

# Загрузка .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SAVE_TUBE_API_KEY = os.getenv("SAVE_TUBE_API_KEY")
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")

# Проверка переменных
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")
if not RENDER_EXTERNAL_HOSTNAME:
    raise ValueError("RENDER_EXTERNAL_HOSTNAME не найден")

# Flask
app = Flask(__name__)
bot = TeleBot(BOT_TOKEN)

# Логгер
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Установка вебхука
WEBHOOK_URL = f"https://{RENDER_EXTERNAL_HOSTNAME}/"
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

# Хранилище варнов и мута
warns = {}
mutes = {}
admins = []

# Фильтры
bad_words = ['badword1', 'badword2', 'сука', 'бля', 'нахуй']

# Обработчики команд
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "👋 Привет! Я — MultiBotX. Напиши /help, чтобы увидеть, что я умею.")

@bot.message_handler(commands=['help'])
def help_cmd(message):
    text = (
        "🤖 <b>Команды MultiBotX:</b>\n"
        "\n<b>👮 Модерация</b>\n"
        "мут, размут, бан, разбан, варн (как ответ на сообщение)\n"
        "\n<b>🎉 Развлечения</b>\n"
        "/joke – шутка\n"
        "/fact – факт\n"
        "/quote – цитата\n"
        "/meme – мем\n"
        "/cat – кот\n"
        "/dog – собака\n"
        "/dice – 🎲\n"
        "\n<b>📥 Скачивание</b>\n"
        "Отправь ссылку на TikTok или YouTube\n"
        "\n<b>👻 Пасхалки</b>\n"
        "donke, camdonke, topdonke\n"
    )
    bot.send_message(message.chat.id, text, parse_mode="HTML")

# Модерация без /
@bot.message_handler(func=lambda m: m.reply_to_message and m.text and m.text.lower() in ['мут', 'размут', 'бан', 'разбан', 'варн'])
def handle_moderation(message):
    if message.from_user.id not in admins:
        return bot.reply_to(message, "❌ У тебя нет прав.")
    command = message.text.lower()
    target = message.reply_to_message.from_user
    if command == 'варн':
        warns[target.id] = warns.get(target.id, 0) + 1
        bot.reply_to(message, f"⚠️ {target.first_name} получил предупреждение ({warns[target.id]}/3)")
        if warns[target.id] >= 3:
            bot.ban_chat_member(message.chat.id, target.id)
            bot.send_message(message.chat.id, f"⛔ {target.first_name} забанен за 3 предупреждения.")
            warns[target.id] = 0
    elif command == 'мут':
        until = datetime.utcnow() + timedelta(minutes=30)
        bot.restrict_chat_member(message.chat.id, target.id, permissions=types.ChatPermissions(can_send_messages=False), until_date=until)
        bot.reply_to(message, f"🔇 {target.first_name} замучен на 30 минут.")
    elif command == 'размут':
        bot.restrict_chat_member(message.chat.id, target.id, permissions=types.ChatPermissions(can_send_messages=True))
        bot.reply_to(message, f"🔊 {target.first_name} размучен.")
    elif command == 'бан':
        bot.ban_chat_member(message.chat.id, target.id)
        bot.reply_to(message, f"⛔ {target.first_name} забанен.")
    elif command == 'разбан':
        bot.unban_chat_member(message.chat.id, target.id)
        bot.reply_to(message, f"✅ {target.first_name} разбанен.")

# Автоприветствие
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_user(message):
    for user in message.new_chat_members:
        bot.send_message(message.chat.id, f"👋 Добро пожаловать, {user.first_name}!")

# Антимат
@bot.message_handler(func=lambda message: True)
def check_message(message):
    if message.text:
        if any(bad in message.text.lower() for bad in bad_words):
            bot.delete_message(message.chat.id, message.message_id)
        if message.text.lower() == "donke":
            bot.reply_to(message, "🦍 Donke detected! Спрячьте бананы!")
        elif 'youtube.com' in message.text or 'tiktok.com' in message.text:
            download_video(message)

# Развлечения
@bot.message_handler(commands=['joke'])
def joke(message):
    jokes = ["Почему утка перешла дорогу? Потому что она donke!", "Как зовут осла без шуток? Неинтересно."]
    bot.reply_to(message, random.choice(jokes))

@bot.message_handler(commands=['fact'])
def fact(message):
    facts = ["🐘 Слоны не умеют прыгать.", "🚀 Свет от Солнца доходит за 8 минут."]
    bot.reply_to(message, random.choice(facts))

@bot.message_handler(commands=['quote'])
def quote(message):
    quotes = ["«Будь собой. Прочие роли уже заняты.» – Оскар Уайльд", "«Успех — это 1% вдохновения и 99% пота.» – Эдисон"]
    bot.reply_to(message, random.choice(quotes))

@bot.message_handler(commands=['meme'])
def meme(message):
    memes = [
        "https://i.imgflip.com/4/4t0m5.jpg",
        "https://i.redd.it/qw3l1d9bx0v51.jpg"
    ]
    bot.send_photo(message.chat.id, random.choice(memes))

@bot.message_handler(commands=['cat'])
def cat(message):
    bot.send_photo(message.chat.id, "https://cataas.com/cat")

@bot.message_handler(commands=['dog'])
def dog(message):
    bot.send_photo(message.chat.id, "https://random.dog/woof.jpg")

@bot.message_handler(commands=['dice'])
def dice(message):
    bot.send_dice(message.chat.id)

# donke рейтинг
donke_stats = {}

@bot.message_handler(commands=['camdonke'])
def camdonke(message):
    user_id = message.from_user.id
    donke_stats[user_id] = donke_stats.get(user_id, 0) + 1
    bot.reply_to(message, f"👊 Donke +1! Теперь у тебя {donke_stats[user_id]} очков донке.")

@bot.message_handler(commands=['topdonke'])
def topdonke(message):
    if not donke_stats:
        return bot.reply_to(message, "😐 Пока никто не donke.")
    top = sorted(donke_stats.items(), key=lambda x: x[1], reverse=True)[:5]
    leaderboard = [f"{i+1}. {bot.get_chat_member(message.chat.id, uid).user.first_name} — {score}" for i, (uid, score) in enumerate(top)]
    bot.send_message(message.chat.id, "🏆 Топ Donke:\n" + "\n".join(leaderboard))

# Скачивание видео
def download_video(message):
    url = message.text.strip()
    api = "https://api.savetube.me/info"
    headers = {"X-API-KEY": SAVE_TUBE_API_KEY}
    try:
        r = requests.post(api, json={"url": url}, headers=headers)
        data = r.json()
        video_url = data["medias"][0]["url"]
        title = data.get("title", "Видео")
        bot.send_message(message.chat.id, f"🎬 {title}\n{video_url}")
    except Exception as e:
        bot.send_message(message.chat.id, "⚠️ Не удалось скачать видео.")

# Flask хук
@app.route('/', methods=['POST'])
def webhook():
    bot.process_new_updates([types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK", 200

@app.route('/')
def root():
    return 'MultiBotX работает!'

# Запуск
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))