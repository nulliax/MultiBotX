import os
import telebot
from flask import Flask, request
from threading import Thread
import random

TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

# ========== Flask Ping ==========
@app.route('/')
def home():
    return "✅ MultiBotX работает!"

# ========== Команды: старт / помощь ==========
@bot.message_handler(commands=['start', 'help', 'menu'])
def send_welcome(message):
    bot.send_message(message.chat.id, "👋 Привет! Я бот MultiBotX.\n\nДоступные команды:\n"
                                      "/warn – Выдать предупреждение\n"
                                      "/mute – Замьютить пользователя\n"
                                      "/unmute – Размьютить пользователя\n"
                                      "/ban – Забанить\n"
                                      "/unban – Разбанить\n"
                                      "/joke – Получить шутку")

# ========== Модерация ==========
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

# ========== Развлечения ==========
jokes = [
    "Почему компьютер не может похудеть? Потому что он ест байты!",
    "Что скажет Python, когда закончит программу? 'Выход'.",
    "Программист заходит в бар... и не выходит никогда.",
]

@bot.message_handler(commands=['joke'])
def tell_joke(message):
    bot.send_message(message.chat.id, random.choice(jokes))

# ========== Запуск ==========
def start_bot():
    bot.remove_webhook()
    bot.infinity_polling()

if __name__ == '__main__':
    Thread(target=start_bot).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))