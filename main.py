from flask import Flask
import telebot
from telebot import types
from telebot.types import ChatPermissions
import os
import time
import requests

app = Flask(__name__)

@app.route('/')
def home():
    return 'MultiBotX is running!'

# Токен Telegram-бота
TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# ✅ Заменить на твой ключ SaveTube
SAVETUBE_API_KEY = "382735d147msh533d7dec3c4d3abp12b125jsnfa97a86f84db"

# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, f"Привет, {message.from_user.first_name}! Я — MultiBotX.\nНапиши /help для списка команд.")

# Команда /help
@bot.message_handler(commands=['help'])
def help(message):
    help_text = (
        "📋 Доступные команды:\n"
        "/warn — Предупреждение\n"
        "/mute — Мут на 1 час\n"
        "/unmute — Размут\n"
        "/ban — Бан\n"
        "/unban — Разбан\n"
        "/yt <ссылка> — Скачать видео с YouTube\n"
        "/tt <ссылка> — Скачать видео из TikTok\n"
    )
    bot.send_message(message.chat.id, help_text)

# /warn
@bot.message_handler(commands=['warn'])
def warn(message):
    if message.reply_to_message:
        user = message.reply_to_message.from_user
        bot.send_message(message.chat.id, f"⚠️ {user.first_name} получил предупреждение!")
    else:
        bot.reply_to(message, "Команда должна быть ответом на сообщение.")

# /mute
@bot.message_handler(commands=['mute'])
def mute(message):
    if message.reply_to_message:
        try:
            until_time = time.time() + 60 * 60
            bot.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=message.reply_to_message.from_user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_time
            )
            bot.send_message(message.chat.id, "🔇 Пользователь замучен на 1 час.")
        except Exception as e:
            bot.send_message(message.chat.id, f"Ошибка: {e}")
    else:
        bot.reply_to(message, "Ответь на сообщение пользователя.")

# /unmute
@bot.message_handler(commands=['unmute'])
def unmute(message):
    if message.reply_to_message:
        try:
            bot.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=message.reply_to_message.from_user.id,
                permissions=ChatPermissions(can_send_messages=True)
            )
            bot.send_message(message.chat.id, "🔊 Пользователь размучен.")
        except Exception as e:
            bot.send_message(message.chat.id, f"Ошибка: {e}")
    else:
        bot.reply_to(message, "Ответь на сообщение пользователя.")

# /ban
@bot.message_handler(commands=['ban'])
def ban(message):
    if message.reply_to_message:
        try:
            bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
            bot.send_message(message.chat.id, "⛔ Пользователь забанен.")
        except Exception as e:
            bot.send_message(message.chat.id, f"Ошибка: {e}")
    else:
        bot.reply_to(message, "Ответь на сообщение пользователя.")

# /unban
@bot.message_handler(commands=['unban'])
def unban(message):
    if message.reply_to_message:
        try:
            bot.unban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
            bot.send_message(message.chat.id, "✅ Пользователь разбанен.")
        except Exception as e:
            bot.send_message(message.chat.id, f"Ошибка: {e}")
    else:
        bot.reply_to(message, "Ответь на сообщение пользователя.")

# 📥 /yt — Скачать видео с YouTube
@bot.message_handler(commands=['yt'])
def download_youtube(message):
    try:
        url = message.text.split(' ', 1)[1]
    except:
        return bot.reply_to(message, "Укажи ссылку: /yt <ссылка>")

    headers = {
        "X-RapidAPI-Key": SAVETUBE_API_KEY,
        "X-RapidAPI-Host": "save-tube-video.p.rapidapi.com"
    }
    params = {"url": url}

    r = requests.get("https://save-tube-video.p.rapidapi.com/download", headers=headers, params=params)
    data = r.json()

    if "video_url" in data:
        video = data["video_url"]
        bot.send_message(message.chat.id, f"🎬 Видео с YouTube:\n{video}")
    else:
        bot.send_message(message.chat.id, "❌ Не удалось получить ссылку на видео.")

# 📥 /tt — Скачать видео из TikTok
@bot.message_handler(commands=['tt'])
def download_tiktok(message):
    try:
        url = message.text.split(' ', 1)[1]
    except:
        return bot.reply_to(message, "Укажи ссылку: /tt <ссылка>")

    headers = {
        "X-RapidAPI-Key": SAVETUBE_API_KEY,
        "X-RapidAPI-Host": "save-tube-video.p.rapidapi.com"
    }
    params = {"url": url}

    r = requests.get("https://save-tube-video.p.rapidapi.com/download", headers=headers, params=params)
    data = r.json()

    if "video_url" in data:
        video = data["video_url"]
        bot.send_message(message.chat.id, f"📹 Видео из TikTok:\n{video}")
    else:
        bot.send_message(message.chat.id, "❌ Не удалось получить ссылку на видео.")

# 🌀 Запуск бота
if __name__ == '__main__':
    bot.remove_webhook()
    bot.polling(none_stop=True)