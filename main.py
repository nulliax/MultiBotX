import telebot
from flask import Flask, request
import requests
import random
import re
import os
import time
from threading import Thread

TOKEN = os.getenv("BOT_TOKEN")
YT_API = os.getenv("YOUTUBE_API")
TT_API = os.getenv("TIKTOK_API")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --------- Главные кнопки ---------
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("🎭 Развлечения"), KeyboardButton("🛡️ Модерация"))
    return markup

# --------- Развлечения ---------
jokes = [
    "Почему программисты путают Хэллоуин и Рождество? Потому что OCT 31 = DEC 25.",
    "Зачем программисту очки? Чтобы видеть C#.",
    "Как программист открывает банку? Alt + F4."
]

facts = [
    "У котов есть более 20 мышц, управляющих их ушами.",
    "Python был назван не в честь змеи, а в честь 'Monty Python’s Flying Circus'.",
    "Самая короткая война в истории длилась 38 минут."
]

def get_cat():
    url = "https://api.thecatapi.com/v1/images/search"
    res = requests.get(url).json()
    return res[0]["url"]

def get_meme():
    res = requests.get("https://meme-api.com/gimme").json()
    return res["url"]

# --------- Модерация ---------
warnings = {}

@bot.message_handler(commands=['warn'])
def warn(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "Ответь на сообщение пользователя.")
    user_id = message.reply_to_message.from_user.id
    chat_id = message.chat.id
    warnings.setdefault(chat_id, {})
    warnings[chat_id][user_id] = warnings[chat_id].get(user_id, 0) + 1
    bot.reply_to(message, f"⚠️ Пользователю выдано предупреждение ({warnings[chat_id][user_id]}/3)")
    if warnings[chat_id][user_id] >= 3:
        bot.ban_chat_member(chat_id, user_id)
        bot.send_message(chat_id, "🚫 Пользователь забанен за 3 предупреждения.")

@bot.message_handler(commands=['mute'])
def mute(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "Ответь на сообщение пользователя.")
    user_id = message.reply_to_message.from_user.id
    until = time.time() + 3600
    bot.restrict_chat_member(message.chat.id, user_id, permissions=telebot.types.ChatPermissions(can_send_messages=False), until_date=until)
    bot.reply_to(message, "🔇 Пользователь замучен на 1 час.")

@bot.message_handler(commands=['unmute'])
def unmute(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "Ответь на сообщение пользователя.")
    user_id = message.reply_to_message.from_user.id
    bot.restrict_chat_member(message.chat.id, user_id, permissions=telebot.types.ChatPermissions(can_send_messages=True))
    bot.reply_to(message, "🔊 Пользователь размучен.")

@bot.message_handler(commands=['ban'])
def ban(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "Ответь на сообщение пользователя.")
    bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
    bot.reply_to(message, "🚫 Пользователь забанен.")

@bot.message_handler(commands=['unban'])
def unban(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "Ответь на сообщение пользователя.")
    user_id = message.reply_to_message.from_user.id
    bot.unban_chat_member(message.chat.id, user_id)
    bot.reply_to(message, "✅ Пользователь разбанен.")

# --------- Обработка сообщений ---------
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, f"Привет, {message.from_user.first_name}!\nЯ — MultiBotX.\nВыбери действие:", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "🎭 Развлечения")
def fun_menu(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("/joke"), KeyboardButton("/fact"))
    markup.row(KeyboardButton("/cat"), KeyboardButton("/meme"))
    markup.row(KeyboardButton("/start"))
    bot.send_message(message.chat.id, "Выбери развлечение:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🛡️ Модерация")
def mod_menu(message):
    bot.send_message(message.chat.id, "🛡️ Команды модерации:\n/warn, /mute, /unmute, /ban, /unban", reply_markup=main_menu())

@bot.message_handler(commands=['joke'])
def send_joke(message):
    bot.reply_to(message, random.choice(jokes))

@bot.message_handler(commands=['fact'])
def send_fact(message):
    bot.reply_to(message, random.choice(facts))

@bot.message_handler(commands=['cat'])
def send_cat(message):
    bot.send_photo(message.chat.id, get_cat())

@bot.message_handler(commands=['meme'])
def send_meme(message):
    bot.send_photo(message.chat.id, get_meme())

# --------- Автоматическое скачивание видео ---------
def is_youtube_link(text):
    return "youtu.be" in text or "youtube.com" in text

def is_tiktok_link(text):
    return "tiktok.com" in text

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_links(message):
    if is_youtube_link(message.text):
        send_youtube_video(message)
    elif is_tiktok_link(message.text):
        send_tiktok_video(message)

def send_youtube_video(message):
    url = "https://save-tube.p.rapidapi.com/download"
    headers = {
        "X-RapidAPI-Key": YT_API,
        "X-RapidAPI-Host": "save-tube.p.rapidapi.com"
    }
    params = {"url": message.text}
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    try:
        video_url = data["video"]["url"]
        bot.send_message(message.chat.id, f"🎬 Вот видео:\n{video_url}")
    except:
        bot.send_message(message.chat.id, "⚠️ Не удалось получить видео с YouTube.")

def send_tiktok_video(message):
    url = "https://save-tube.p.rapidapi.com/download"
    headers = {
        "X-RapidAPI-Key": TT_API,
        "X-RapidAPI-Host": "save-tube.p.rapidapi.com"
    }
    params = {"url": message.text}
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    try:
        video_url = data["video"]["url"]
        bot.send_video(message.chat.id, video_url, caption="🎵 TikTok видео")
    except:
        bot.send_message(message.chat.id, "⚠️ Не удалось получить видео с TikTok.")

# --------- Flask ---------
@app.route('/')
def home():
    return 'Бот работает!'

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return 'ok'

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

def run_bot():
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"https://multibotx.onrender.com/{TOKEN}")

# --------- Запуск ---------
if __name__ == "__main__":
    Thread(target=run_flask).start()
    Thread(target=run_bot).start()