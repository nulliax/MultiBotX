import os
import random
import requests
from flask import Flask, request
from threading import Thread
import telebot
from telebot import types

# ===================== Конфигурация =====================
TOKEN = os.getenv("TOKEN")
SAVETUBE_KEY = os.getenv("SAVETUBE_KEY")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ===================== Главная страница =====================
@app.route('/')
def home():
    return "🤖 MultiBotX работает!"

# ===================== МЕНЮ =====================
@bot.message_handler(commands=['start', 'help', 'menu'])
def send_menu(message):
    menu_text = (
        "👋 Привет! Я *MultiBotX* — универсальный бот с множеством возможностей:\n\n"
        "🎛 *Модерация:*\n"
        "  • /warn – Предупреждение\n"
        "  • /mute – Мут\n"
        "  • /unmute – Размут\n"
        "  • /ban – Бан\n"
        "  • /unban – Разбан\n\n"
        "🎉 *Развлечения:*\n"
        "  • /joke – Шутка\n"
        "  • /fact – Интересный факт\n"
        "  • /quote – Цитата\n"
        "  • /cat – Фото котика\n"
        "  • /dice – Бросить кубик 🎲\n"
        "  • /inspire – Мотивация 💡\n\n"
        "📥 *Скачивание видео:*\n"
        "  Просто отправь ссылку с YouTube или TikTok, и я скачаю видео!"
    )
    bot.send_message(message.chat.id, menu_text, parse_mode="Markdown")

# ===================== Модерация =====================
@bot.message_handler(commands=['warn'])
def warn_user(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "⚠️ Ответь на сообщение пользователя, чтобы выдать предупреждение.")
    bot.reply_to(message.reply_to_message, "⚠️ Предупреждение!")

@bot.message_handler(commands=['mute'])
def mute_user(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "Ответь на сообщение пользователя для мута.")
    try:
        bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id,
                                 permissions=types.ChatPermissions(can_send_messages=False))
        bot.reply_to(message.reply_to_message, "🔇 Пользователь был замьючен.")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

@bot.message_handler(commands=['unmute'])
def unmute_user(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "Ответь на сообщение пользователя для размута.")
    try:
        bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id,
                                 permissions=types.ChatPermissions(can_send_messages=True))
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
jokes = [
    "Почему компьютер не может похудеть? Потому что он ест байты!",
    "Что скажет Python, когда закончит программу? 'Выход'.",
    "Программист заходит в бар... и не выходит никогда.",
]

facts = [
    "💡 Самая длинная программа в мире — это человеческий геном.",
    "💡 Первый компьютер весил более 27 тонн.",
    "💡 Первая электронная почта была отправлена в 1971 году.",
]

quotes = [
    "🔹 «Будь собой, остальные роли уже заняты.» – Оскар Уайльд",
    "🔹 «Жизнь — это то, что с тобой происходит, пока ты строишь планы.» – Джон Леннон",
    "🔹 «Сила не в том, чтобы никогда не падать, а в том, чтобы подниматься каждый раз.» – Конфуций",
]

@bot.message_handler(commands=['joke'])
def tell_joke(message):
    bot.send_message(message.chat.id, random.choice(jokes))

@bot.message_handler(commands=['fact'])
def tell_fact(message):
    bot.send_message(message.chat.id, random.choice(facts))

@bot.message_handler(commands=['quote'])
def tell_quote(message):
    bot.send_message(message.chat.id, random.choice(quotes))

@bot.message_handler(commands=['cat'])
def send_cat_photo(message):
    try:
        r = requests.get("https://api.thecatapi.com/v1/images/search").json()
        bot.send_photo(message.chat.id, r[0]['url'])
    except Exception:
        bot.send_message(message.chat.id, "😿 Не удалось получить котика.")

@bot.message_handler(commands=['inspire'])
def inspire(message):
    inspirations = [
        "🔥 Никогда не сдавайся. Великие дела требуют времени.",
        "🚀 Сегодняшние усилия — это завтрашние результаты.",
        "💪 Самое трудное — начать. Дальше будет легче!"
    ]
    bot.send_message(message.chat.id, random.choice(inspirations))

@bot.message_handler(commands=['dice'])
def roll_dice(message):
    bot.send_dice(message.chat.id)

# ===================== Скачивание видео =====================
def download_video_from_url(url):
    api_url = "https://save-tube-video-download.p.rapidapi.com/download"
    headers = {
        "X-RapidAPI-Key": SAVETUBE_KEY,
        "X-RapidAPI-Host": "save-tube-video-download.p.rapidapi.com"
    }
    params = {"url": url}
    try:
        response = requests.get(api_url, headers=headers, params=params, timeout=15)
        data = response.json()
        if data and isinstance(data.get("links"), list):
            for item in data["links"]:
                if item.get("type") == "mp4" and item.get("url"):
                    return item["url"]
    except Exception as e:
        print("Ошибка скачивания:", e)
    return None

@bot.message_handler(func=lambda m: "tiktok.com" in m.text or "youtu" in m.text)
def handle_video(message):
    bot.send_chat_action(message.chat.id, 'upload_video')
    bot.send_message(message.chat.id, "⏬ Пытаюсь скачать видео...")
    video_link = download_video_from_url(message.text.strip())
    if video_link:
        try:
            bot.send_video(message.chat.id, video_link)
        except Exception:
            bot.send_message(message.chat.id, "🎬 Видео слишком большое. Вот ссылка:\n" + video_link)
    else:
        bot.send_message(message.chat.id, "❌ Не удалось скачать видео. Попробуй другую ссылку.")

# ===================== Запуск =====================
def start_bot():
    bot.remove_webhook()
    bot.infinity_polling()

if __name__ == '__main__':
    Thread(target=start_bot).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))