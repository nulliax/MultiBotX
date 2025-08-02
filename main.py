import os
import random
import requests
import telebot
from flask import Flask, request
from threading import Thread

# Получение токенов из переменных окружения
TOKEN = os.getenv("TOKEN")
SAVETUBE_KEY = os.getenv("SAVETUBE_KEY")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ===================== Flask ping =====================
@app.route('/')
def home():
    return '✅ MultiBotX работает!'

# ===================== Модерация =====================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.chat.id, "👋 Привет! Я — MultiBotX.\n\n🔧 Мои функции:\n/menu — Главное меню\n/warn, /mute, /ban — Модерация\n/joke — Шутка дня\nПросто отправь ссылку на TikTok или YouTube — я скачаю видео.")

@bot.message_handler(commands=['warn'])
def warn_user(message):
    if not message.reply_to_message:
        return bot.send_message(message.chat.id, "⚠️ Ответь на сообщение пользователя, чтобы выдать предупреждение.")
    bot.send_message(message.chat.id, f"⚠️ Пользователю @{message.reply_to_message.from_user.username or 'без ника'} выдано предупреждение.")

@bot.message_handler(commands=['mute'])
def mute_user(message):
    if not message.reply_to_message:
        return bot.send_message(message.chat.id, "🔇 Ответь на сообщение пользователя для мута.")
    try:
        bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id,
            permissions=telebot.types.ChatPermissions(can_send_messages=False))
        bot.send_message(message.chat.id, "🔇 Пользователь был замьючен.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['unmute'])
def unmute_user(message):
    if not message.reply_to_message:
        return bot.send_message(message.chat.id, "🔊 Ответь на сообщение пользователя для размута.")
    try:
        bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id,
            permissions=telebot.types.ChatPermissions(can_send_messages=True))
        bot.send_message(message.chat.id, "🔊 Пользователь размьючен.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['ban'])
def ban_user(message):
    if not message.reply_to_message:
        return bot.send_message(message.chat.id, "🚫 Ответь на сообщение пользователя для бана.")
    try:
        bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        bot.send_message(message.chat.id, "🚫 Пользователь забанен.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['unban'])
def unban_user(message):
    if not message.reply_to_message:
        return bot.send_message(message.chat.id, "✅ Ответь на сообщение пользователя для разбанивания.")
    try:
        bot.unban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        bot.send_message(message.chat.id, "✅ Пользователь разбанен.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

# ===================== Развлечения =====================
jokes = [
    "Почему программисты любят темноту? Потому что свет притягивает баги!",
    "Как зовут разработчика без девушки? Freelancer!",
    "Что делает программист, если хочет похудеть? Удаляет cookies!",
]

@bot.message_handler(commands=['joke'])
def joke_command(message):
    bot.send_message(message.chat.id, random.choice(jokes))

# ===================== Автозагрузка видео =====================
def download_video_from_url(url):
    try:
        response = requests.get(
            "https://save-tube-video-download.p.rapidapi.com/download",
            headers={
                "X-RapidAPI-Key": SAVETUBE_KEY,
                "X-RapidAPI-Host": "save-tube-video-download.p.rapidapi.com"
            },
            params={"url": url},
            timeout=10
        )
        data = response.json()
        if data and 'links' in data and data['links']:
            video = next((v for v in data['links'] if v.get('url')), None)
            return video['url'] if video else None
    except Exception as e:
        print("❌ Ошибка загрузки видео:", e)
    return None

@bot.message_handler(func=lambda msg: 'tiktok.com' in msg.text or 'youtu' in msg.text)
def auto_video_downloader(message):
    url = message.text.strip()
    bot.send_chat_action(message.chat.id, 'upload_video')
    bot.send_message(message.chat.id, "🔄 Скачиваю видео...")

    video_link = download_video_from_url(url)
    if video_link:
        try:
            bot.send_video(message.chat.id, video_link)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка при отправке видео: {e}")
    else:
        bot.send_message(message.chat.id, "❌ Не удалось получить видео. Попробуйте другую ссылку.")

# ===================== Запуск =====================
def start_bot():
    bot.remove_webhook()
    bot.infinity_polling()

if __name__ == '__main__':
    Thread(target=start_bot).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))