import os import telebot import requests import random from flask import Flask, request from threading import Thread from telebot import types

TOKEN = os.getenv("TOKEN") bot = telebot.TeleBot(TOKEN) app = Flask(name)

===================== Flask Ping =====================

@app.route('/') def home(): return "MultiBotX is running!"

===================== Команды /start /help =====================

@bot.message_handler(commands=['start', 'help']) def send_welcome(message): bot.send_message(message.chat.id, "👋 Привет! Я многофункциональный бот MultiBotX. Вот что я умею:\n/menu – Главное меню\n/joke – Шутка\n/fact – Интересный факт\n/quote – Цитата\n/meme – Мем\n/cat – Кот\n/dice – Бросить кубик")

===================== Главное меню =====================

@bot.message_handler(commands=['menu']) def menu(message): markup = types.ReplyKeyboardMarkup(resize_keyboard=True) buttons = ["🎲 Кубик", "😹 Котик", "🧠 Факт", "🤣 Шутка", "📜 Цитата", "🖼 Мем"] markup.add(*buttons) bot.send_message(message.chat.id, "Выбери опцию:", reply_markup=markup)

===================== Модерация =====================

@bot.message_handler(commands=['warn']) def warn_user(message): if not message.reply_to_message: return bot.reply_to(message, "Ответь на сообщение пользователя, чтобы выдать предупреждение.") bot.reply_to(message.reply_to_message, "⚠️ Предупреждение!")

@bot.message_handler(commands=['mute']) def mute_user(message): if not message.reply_to_message: return bot.reply_to(message, "Ответь на сообщение пользователя для мута.") try: bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id, permissions=types.ChatPermissions(can_send_messages=False)) bot.reply_to(message.reply_to_message, "🔇 Пользователь был замьючен.") except Exception as e: bot.reply_to(message, f"Ошибка: {e}")

@bot.message_handler(commands=['unmute']) def unmute_user(message): if not message.reply_to_message: return bot.reply_to(message, "Ответь на сообщение пользователя для размута.") try: bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id, permissions=types.ChatPermissions(can_send_messages=True)) bot.reply_to(message.reply_to_message, "🔊 Пользователь размьючен.") except Exception as e: bot.reply_to(message, f"Ошибка: {e}")

@bot.message_handler(commands=['ban']) def ban_user(message): if not message.reply_to_message: return bot.reply_to(message, "Ответь на сообщение пользователя для бана.") try: bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id) bot.reply_to(message.reply_to_message, "🚫 Пользователь забанен.") except Exception as e: bot.reply_to(message, f"Ошибка: {e}")

@bot.message_handler(commands=['unban']) def unban_user(message): if not message.reply_to_message: return bot.reply_to(message, "Ответь на сообщение пользователя для разбанивания.") try: bot.unban_chat_member(message.chat.id, message.reply_to_message.from_user.id) bot.reply_to(message.reply_to_message, "✅ Пользователь разбанен.") except Exception as e: bot.reply_to(message, f"Ошибка: {e}")

===================== Развлечения =====================

@bot.message_handler(commands=['joke']) def tell_joke(message): jokes = [ "Почему компьютер не может похудеть? Потому что он ест байты!", "Что скажет Python, когда закончит программу? 'Выход'.", "Программист заходит в бар... и не выходит никогда." ] bot.send_message(message.chat.id, random.choice(jokes))

@bot.message_handler(commands=['fact']) def fact(message): facts = [ "Земля вращается со скоростью 1670 км/ч.", "Мозг человека на 75% состоит из воды.", "Осьминоги имеют три сердца." ] bot.send_message(message.chat.id, random.choice(facts))

@bot.message_handler(commands=['quote']) def quote(message): quotes = [ "Будь изменением, которое хочешь видеть в мире. – Махатма Ганди", "Тот, кто хочет – ищет возможности, кто не хочет – ищет причины.", "Сложности делают нас сильнее." ] bot.send_message(message.chat.id, random.choice(quotes))

@bot.message_handler(commands=['meme']) def meme(message): try: url = requests.get("https://meme-api.com/gimme").json()["url"] bot.send_photo(message.chat.id, url) except: bot.send_message(message.chat.id, "Не удалось загрузить мем 😞")

@bot.message_handler(commands=['cat']) def cat(message): try: url = requests.get("https://api.thecatapi.com/v1/images/search").json()[0]["url"] bot.send_photo(message.chat.id, url) except: bot.send_message(message.chat.id, "Не удалось загрузить котика 🐱")

@bot.message_handler(commands=['dice']) def roll_dice(message): bot.send_dice(message.chat.id)

===================== Обработка кнопок =====================

@bot.message_handler(func=lambda m: True) def handle_buttons(message): text = message.text.lower() if "котик" in text: cat(message) elif "мем" in text: meme(message) elif "шутка" in text: tell_joke(message) elif "цитата" in text: quote(message) elif "факт" in text: fact(message) elif "кубик" in text: roll_dice(message)

===================== Приветствие новых =====================

@bot.chat_member_handler() def greet_new_member(update): if update.new_chat_member: bot.send_message(update.chat.id, f"👋 Добро пожаловать, {update.new_chat_member.user.first_name}!")

===================== Запуск =====================

def start_bot(): bot.remove_webhook() bot.infinity_polling()

if name == 'main': Thread(target=start_bot).start() app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

