import telebot
from telebot import types
from datetime import datetime, timedelta
import random

# 🔐 Токен бота (не показывай другим)
TOKEN = "7870127808:AAGLq533QE63G8ZxrIlddfTaV_I3fnWNN3k"

bot = telebot.TeleBot(TOKEN)

# 📦 Словари
warns = {}
muted_users = {}
bad_words = ["дурак", "идиот", "тупой", "блин", "черт"]  # добавь свои

# 🎛 Главное меню
def main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🎲 Развлечения", "🛠 Модерация")
    markup.row("🤖 AI (в будущем)", "ℹ️ Помощь")
    bot.send_message(chat_id, "📋 Главное меню:", reply_markup=markup)

# 🟢 /start и /help
@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    bot.reply_to(message, "👋 Привет! Я — *MultiBotX*, универсальный помощник!\n\nВыбери действие из меню ⬇️", parse_mode="Markdown")
    main_menu(message.chat.id)

# 🛠 Модерация
@bot.message_handler(commands=["warn"])
def warn_user(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "⚠️ Ответь на сообщение пользователя, чтобы выдать предупреждение.")
    user_id = message.reply_to_message.from_user.id
    warns[user_id] = warns.get(user_id, 0) + 1
    if warns[user_id] >= 3:
        bot.kick_chat_member(message.chat.id, user_id)
        bot.send_message(message.chat.id, "🚫 Пользователь забанен за 3 предупреждения.")
    else:
        bot.send_message(message.chat.id, f"⚠️ Пользователю выдано предупреждение ({warns[user_id]}/3)")

@bot.message_handler(commands=["mute"])
def mute_user(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "🔇 Ответь на сообщение пользователя, чтобы замутить.")
    user_id = message.reply_to_message.from_user.id
    until = datetime.utcnow() + timedelta(minutes=5)
    bot.restrict_chat_member(message.chat.id, user_id, until_date=until, can_send_messages=False)
    muted_users[user_id] = until
    bot.send_message(message.chat.id, "🔇 Пользователь замучен на 5 минут.")

@bot.message_handler(commands=["unmute"])
def unmute_user(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "🔊 Ответь на сообщение пользователя, чтобы размутить.")
    user_id = message.reply_to_message.from_user.id
    bot.restrict_chat_member(message.chat.id, user_id, can_send_messages=True)
    muted_users.pop(user_id, None)
    bot.send_message(message.chat.id, "🔊 Пользователь размучен.")

@bot.message_handler(commands=["ban"])
def ban_user(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "🚫 Ответь на сообщение пользователя, чтобы забанить.")
    user_id = message.reply_to_message.from_user.id
    bot.kick_chat_member(message.chat.id, user_id)
    bot.send_message(message.chat.id, "🚫 Пользователь забанен.")

@bot.message_handler(commands=["unban"])
def unban_user(message):
    if not message.reply_to_message:
        return bot.reply_to(message, "🔓 Ответь на сообщение пользователя, чтобы разбанить.")
    user_id = message.reply_to_message.from_user.id
    bot.unban_chat_member(message.chat.id, user_id)
    bot.send_message(message.chat.id, "🔓 Пользователь разбанен.")

@bot.message_handler(commands=["admins"])
def list_admins(message):
    chat_admins = bot.get_chat_administrators(message.chat.id)
    text = "👮‍♂️ Список админов:\n"
    for admin in chat_admins:
        text += f"• {admin.user.first_name}\n"
    bot.send_message(message.chat.id, text)

# 🎮 Развлечения
@bot.message_handler(commands=["coin"])
def coin(message):
    result = random.choice(["Орел 🦅", "Решка 💰"])
    bot.send_message(message.chat.id, f"🪙 Монета: *{result}*", parse_mode="Markdown")

@bot.message_handler(commands=["dice"])
def dice(message):
    bot.send_dice(message.chat.id)

@bot.message_handler(commands=["joke"])
def joke(message):
    jokes = [
        "Почему программист путает Хэллоуин и Рождество? Потому что OCT 31 == DEC 25!",
        "Как зовут программиста, который потерял память? Алгозабудка.",
        "— Сколько программистов нужно, чтобы вкрутить лампочку?\n— Ни одного, это аппаратная проблема!"
    ]
    bot.send_message(message.chat.id, random.choice(jokes))

@bot.message_handler(commands=["meme"])
def meme(message):
    memes = [
        "https://i.imgflip.com/1bij.jpg",
        "https://i.redd.it/a0v87gwzoge61.jpg",
        "https://i.redd.it/qn7f9oqu7o501.jpg"
    ]
    bot.send_photo(message.chat.id, random.choice(memes))

# 🤖 AI-функция (заготовка)
@bot.message_handler(commands=["ask"])
def ai_answer(message):
    bot.send_message(message.chat.id, "🤖 Эта функция будет доступна позже, когда будет подключён AI.")

# 👋 Приветствие новых
@bot.message_handler(content_types=["new_chat_members"])
def welcome_new(message):
    for user in message.new_chat_members:
        bot.send_message(message.chat.id, f"👋 Добро пожаловать, {user.first_name}!")

# 🧹 Автоматическое удаление мата
@bot.message_handler(func=lambda m: True)
def check_message(message):
    for word in bad_words:
        if word in message.text.lower():
            bot.delete_message(message.chat.id, message.message_id)
            bot.send_message(message.chat.id, "🚫 Не ругайся!")
            break

    # Обработка кнопок
    if message.text == "🎲 Развлечения":
        bot.send_message(message.chat.id, "🎮 Команды:\n/coin — монетка\n/dice — кубик\n/joke — шутка\n/meme — мем")
    elif message.text == "🛠 Модерация":
        bot.send_message(message.chat.id, "🛡 Модерация:\n/warn\n/mute\n/unmute\n/ban\n/unban\n/admins")
    elif message.text == "🤖 AI (в будущем)":
        bot.send_message(message.chat.id, "🧠 В будущем будет поддержка ChatGPT!")
    elif message.text == "ℹ️ Помощь":
        bot.send_message(message.chat.id, "💬 Просто используй команды или кнопки ниже.")

# 🧹 Удаляем вебхук (важно для polling)
bot.remove_webhook()
bot.polling(none_stop=True)