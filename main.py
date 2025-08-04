import os
import telebot
from flask import Flask, request
from threading import Thread
import random

TOKEN = os.getenv("TOKEN")
if TOKEN is None:
    raise ValueError("❌ Переменная окружения TOKEN не задана.")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ===================== Flask Ping =====================
@app.route('/')
def index():
    return "✅ MultiBotX работает!"

# ===================== Команды =====================
@bot.message_handler(commands=['start', 'help'])
def start_help(message):
    bot.send_message(message.chat.id, "👋 Привет! Я многофункциональный бот MultiBotX.\n\nНапиши /menu, чтобы увидеть всё, что я умею.")

# ===================== Модерация =====================
@bot.message_handler(commands=['warn'])
def warn_user(message):
    if not message.reply_to_message:
        return bot.send_message(message.chat.id, "⚠️ Ответь на сообщение пользователя, чтобы выдать предупреждение.")
    bot.send_message(message.chat.id, f"⚠️ Предупреждение для {message.reply_to_message.from_user.first_name}")

@bot.message_handler(commands=['mute'])
def mute_user(message):
    if not message.reply_to_message:
        return bot.send_message(message.chat.id, "🔇 Ответь на сообщение пользователя для мута.")
    try:
        bot.restrict_chat_member(
            message.chat.id,
            message.reply_to_message.from_user.id,
            permissions=telebot.types.ChatPermissions(can_send_messages=False)
        )
        bot.send_message(message.chat.id, "🔇 Пользователь замьючен.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")

@bot.message_handler(commands=['unmute'])
def unmute_user(message):
    if not message.reply_to_message:
        return bot.send_message(message.chat.id, "🔊 Ответь на сообщение пользователя для размута.")
    try:
        bot.restrict_chat_member(
            message.chat.id,
            message.reply_to_message.from_user.id,
            permissions=telebot.types.ChatPermissions(can_send_messages=True)
        )
        bot.send_message(message.chat.id, "🔊 Пользователь размьючен.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")

@bot.message_handler(commands=['ban'])
def ban_user(message):
    if not message.reply_to_message:
        return bot.send_message(message.chat.id, "🚫 Ответь на сообщение пользователя для бана.")
    try:
        bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        bot.send_message(message.chat.id, "🚫 Пользователь забанен.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")

@bot.message_handler(commands=['unban'])
def unban_user(message):
    if not message.reply_to_message:
        return bot.send_message(message.chat.id, "✅ Ответь на сообщение пользователя для разбанивания.")
    try:
        bot.unban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        bot.send_message(message.chat.id, "✅ Пользователь разбанен.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")

# ===================== Шутки =====================
jokes = [
    "Почему компьютер не может похудеть? Потому что он ест байты! 😂",
    "Что говорит Python после выполнения программы? 'Выход' 🐍",
    "Программист заходит в бар... и не выходит никогда. 🍻",
]

@bot.message_handler(commands=['joke'])
def send_joke(message):
    bot.send_message(message.chat.id, random.choice(jokes))

# ===================== Запуск =====================
def start_bot():
    bot.remove_webhook()
    bot.infinity_polling()

if __name__ == '__main__':
    Thread(target=start_bot).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))