import telebot
from telebot import types
import random
import requests

bot = telebot.TeleBot("7870127808:AAGLq533QE63G8ZxrIlddfTaV_I3fnWNN3k")

# Главное меню
def main_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎮 Развлечения", "🛡 Модерация", "ℹ️ О боте")
    bot.send_message(message.chat.id, "Выбери раздел:", reply_markup=markup)

# /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "👋 Привет! Я — MultiBotX, твой универсальный помощник.")
    main_menu(message)

# /help
@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id, "🧠 Доступные команды:\n/start — запустить бота\n/help — помощь")

# 🎮 Развлечения
@bot.message_handler(func=lambda message: message.text == "🎮 Развлечения")
def entertainment_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎲 Шутка", "🐱 Котик", "🧠 Факт", "📷 Мем", "⬅️ Назад")
    bot.send_message(message.chat.id, "Выбери категорию:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "⬅️ Назад")
def back_to_main(message):
    main_menu(message)

# Шутка
@bot.message_handler(func=lambda message: message.text == "🎲 Шутка")
def send_joke(message):
    jokes = [
        "Почему программисты любят тёмную тему? Потому что светлая — баг.",
        "— Почему курица перешла дорогу?\n— Потому что она была в цикле!",
        "Айтишник пошёл в бар. <br /> Вернул пива. <br /> Ошибка: null beer exception."
    ]
    bot.send_message(message.chat.id, random.choice(jokes))

# Котик
@bot.message_handler(func=lambda message: message.text == "🐱 Котик")
def send_cat(message):
    try:
        res = requests.get("https://api.thecatapi.com/v1/images/search").json()
        bot.send_photo(message.chat.id, res[0]['url'])
    except:
        bot.send_message(message.chat.id, "🐾 Не удалось загрузить котика.")

# Факт
@bot.message_handler(func=lambda message: message.text == "🧠 Факт")
def send_fact(message):
    try:
        res = requests.get("https://uselessfacts.jsph.pl/random.json?language=ru").json()
        bot.send_message(message.chat.id, f"🧠 Факт: {res['text']}")
    except:
        bot.send_message(message.chat.id, "Не удалось загрузить факт.")

# Мем
@bot.message_handler(func=lambda message: message.text == "📷 Мем")
def send_meme(message):
    try:
        res = requests.get("https://meme-api.com/gimme").json()
        bot.send_photo(message.chat.id, res['url'], caption=res['title'])
    except:
        bot.send_message(message.chat.id, "Не удалось загрузить мем.")

# Защита от ошибок
@bot.message_handler(func=lambda message: True)
def fallback(message):
    bot.send_message(message.chat.id, "❓ Я не понял команду. Используй /start для меню.")

bot.remove_webhook()
bot.polling(none_stop=True)