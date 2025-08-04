import os
import telebot
from flask import Flask, request
from threading import Thread
import random

# Получаем токен из переменной окружения
TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

# ========== FLASK ==========
@app.route('/')
def index():
    return "MultiBotX is alive!"

# ========== Старт / помощь ==========
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.chat.id, "👋 Привет! Я бот MultiBotX. Напиши /menu, чтобы увидеть доступные команды.")

# ========== Модерация ==========
@bot.message_handler(commands=['warn'])
def warn_user(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "Ответь на сообщение для предупреждения.")
    bot.reply_to(message.reply_to_message, "⚠️ Предупреждение!")

@bot.message_handler(commands=['mute'])
def mute_user(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "Ответь на сообщение для мута.")
    try:
        bot.restrict_chat_member(
            message.chat.id,
            message.reply_to_message.from_user.id,
            permissions=telebot.types.ChatPermissions(can_send_messages=False)
        )
        bot.reply_to(message.reply_to_message, "🔇 Пользователь замьючен.")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

@bot.message_handler(commands=['unmute'])
def unmute_user(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "Ответь на сообщение для размута.")
    try:
        bot.restrict_chat_member(
            message.chat.id,
            message.reply_to_message.from_user.id,
            permissions=telebot.types.ChatPermissions(can_send_messages=True)
        )
        bot.reply_to(message.reply_to_message, "🔊 Пользователь размьючен.")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

@bot.message_handler(commands=['ban'])
def ban_user(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "Ответь на сообщение для бана.")
    try:
        bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        bot.reply_to(message.reply_to_message, "🚫 Пользователь забанен.")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

@bot.message_handler(commands=['unban'])
def unban_user(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "Ответь на сообщение для разбана.")
    try:
        bot.unban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        bot.reply_to(message.reply_to_message, "✅ Пользователь разбанен.")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

# ========== Развлечения ==========
jokes = [
    "Почему компьютер не может похудеть? Потому что он ест байты!",
    "Программист заходит в бар... и не выходит никогда.",
    "Что скажет Python, когда закончит программу? 'Выход'."
]

@bot.message_handler(commands=['joke'])
def tell_joke(message):
    bot.send_message(message.chat.id, random.choice(jokes))

# ========== Запуск ==========
def run_bot():
    bot.remove_webhook()
    bot.infinity_polling()

if __name__ == '__main__':
    Thread(target=run_bot).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))