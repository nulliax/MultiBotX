import os
import telebot
import requests
from flask import Flask, request
from threading import Thread

TOKEN = os.getenv("TOKEN")
SAVETUBE_KEY = os.getenv("SAVETUBE_KEY")
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

# ===================== Flask ping =====================
@app.route('/')
def home():
    return "MultiBotX is running!"

# ===================== Модерация =====================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.chat.id, "👋 Привет! Я многофункциональный бот MultiBotX. Напиши /menu, чтобы увидеть все возможности.")

@bot.message_handler(commands=['warn'])
def warn_user(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "Ответь на сообщение пользователя, чтобы выдать предупреждение.")
    bot.reply_to(message.reply_to_message, "⚠️ Предупреждение!")

@bot.message_handler(commands=['mute'])
def mute_user(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "Ответь на сообщение пользователя для мута.")
    try:
        bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id,
                                 permissions=telebot.types.ChatPermissions(can_send_messages=False))
        bot.reply_to(message.reply_to_message, "🔇 Пользователь был замьючен.")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

@bot.message_handler(commands=['unmute'])
def unmute_user(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "Ответь на сообщение пользователя для размута.")
    try:
        bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id,
                                 permissions=telebot.types.ChatPermissions(can_send_messages=True))
        bot.reply_to(message.reply_to_message, "🔊 Пользователь размьючен.")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

@bot.message_handler(commands=['ban'])
def ban_user(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "Ответь на сообщение пользователя для бана.")
    try:
        bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        bot.reply_to(message.reply_to_message, "🚫 Пользователь забанен.")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

@bot.message_handler(commands=['unban'])
def unban_user(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "Ответь на сообщение пользователя для разбанивания.")
    try:
        bot.unban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        bot.reply_to(message.reply_to_message, "✅ Пользователь разбанен.")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

# ===================== Развлечения =====================
import random

jokes = [
    "Почему компьютер не может похудеть? Потому что он ест байты!",
    "Что скажет Python, когда закончит программу? 'Выход'.",
    "Программист заходит в бар... и не выходит никогда.",
]

@bot.message_handler(commands=['joke'])
def tell_joke(message):
    bot.send_message(message.chat.id, random.choice(jokes))

# ===================== Авто TikTok / YouTube =====================
def download_video_from_url(url):
    api_url = "https://save-tube-video-download.p.rapidapi.com/download"
    headers = {
        "X-RapidAPI-Key": SAVETUBE_KEY,
        "X-RapidAPI-Host": "save-tube-video-download.p.rapidapi.com"
    }
    params = {"url": url}
    try:
        response = requests.get(api_url, headers=headers, params=params, timeout=10)
        data = response.json()
        if 'links' in data and data['links']:
            return data['links'][0]['url']
    except Exception as e:
        print("Ошибка при скачивании:", e)
    return None

@bot.message_handler(func=lambda message: 'tiktok.com' in message.text or 'youtu' in message.text)
def handle_video_links(message):
    url = message.text.strip()
    bot.send_chat_action(message.chat.id, 'upload_video')
    bot.send_message(message.chat.id, "⏬ Скачиваю видео...")

    video_url = download_video_from_url(url)
    if video_url:
        bot.send_video(message.chat.id, video_url)
    else:
        bot.send_message(message.chat.id, "❌ Не удалось скачать видео. Попробуйте другую ссылку.")

# ===================== Запуск =====================
def start_bot():
    bot.remove_webhook()
    bot.infinity_polling()

if __name__ == '__main__':
    Thread(target=start_bot).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))