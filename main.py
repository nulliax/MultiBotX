import os import telebot from telebot import types from flask import Flask, request from dotenv import load_dotenv import random import time

Загрузка переменных окружения

load_dotenv() TOKEN = os.getenv("TOKEN") bot = telebot.TeleBot(TOKEN)

app = Flask(name)

Хранилища данных

user_stats = {} logs = []

📌 Основное меню

@bot.message_handler(commands=['start', 'help', 'menu']) def send_welcome(message): markup = types.ReplyKeyboardMarkup(resize_keyboard=True) btn1 = types.KeyboardButton("🎲 Кинуть кубик") btn2 = types.KeyboardButton("😂 Шутка") btn3 = types.KeyboardButton("📸 Фото котика") btn4 = types.KeyboardButton("💬 Цитата") btn5 = types.KeyboardButton("🧠 Факт") btn6 = types.KeyboardButton("🦍 Donke") markup.add(btn1, btn2, btn3, btn4, btn5, btn6) bot.send_message(message.chat.id, "👋 Привет! Я многофункциональный бот MultiBotX. Выбери опцию ниже:", reply_markup=markup) log_command(message, "/start")

📊 Статистика для админов

@bot.message_handler(commands=['stats']) def stats(message): if is_admin(message): total_users = len(user_stats) total_logs = len(logs) text = f"📊 <b>Статистика:</b>\n👤 Пользователей: {total_users}\n📝 Команд обработано: {total_logs}" bot.send_message(message.chat.id, text, parse_mode='HTML') log_command(message, "/stats")

🧾 Логирование

def log_command(message, command): logs.append({ 'user': message.from_user.id, 'command': command, 'time': time.strftime('%Y-%m-%d %H:%M:%S') }) user_stats[message.from_user.id] = user_stats.get(message.from_user.id, 0) + 1

🛡 Проверка на админа

def is_admin(message): chat_member = bot.get_chat_member(message.chat.id, message.from_user.id) return chat_member.status in ['administrator', 'creator']

🎲 Кубик

@bot.message_handler(func=lambda msg: msg.text == "🎲 Кинуть кубик") def roll_dice(message): bot.send_dice(message.chat.id) log_command(message, "dice")

😂 Шутки

jokes = [ "Почему программисты путают Хэллоуин и Рождество? Потому что OCT 31 = DEC 25.", "У меня был программистский юмор, но он не скомпилировался.", "Как зовут собаку программиста? Гит!", "404: Шутка не найдена." ]

@bot.message_handler(func=lambda msg: msg.text == "😂 Шутка") def joke(message): bot.send_message(message.chat.id, random.choice(jokes)) log_command(message, "joke")

📸 Фото котика

@bot.message_handler(func=lambda msg: msg.text == "📸 Фото котика") def cat(message): photos = [ "https://cataas.com/cat", "https://cataas.com/cat/cute", "https://cataas.com/cat/says/Hello" ] bot.send_photo(message.chat.id, random.choice(photos)) log_command(message, "cat")

💬 Цитаты

quotes = [ "Тот, кто хочет – ищет возможности, кто не хочет – ищет причины.", "Будь тем изменением, которое хочешь видеть в мире.", "Сложности делают нас сильнее.", "Путь в тысячу ли начинается с одного шага.", "Иногда лучший способ что-то сделать — просто начать." ]

@bot.message_handler(func=lambda msg: msg.text == "💬 Цитата") def quote(message): bot.send_message(message.chat.id, random.choice(quotes)) log_command(message, "quote")

🧠 Факты

facts = [ "Кровь в венах синяя только на рисунках, в реальности — она всегда красная.", "Пчёлы могут узнавать лица людей.", "Осьминоги имеют три сердца.", "Мозг состоит на 75% из воды." ]

@bot.message_handler(func=lambda msg: msg.text == "🧠 Факт") def fact(message): bot.send_message(message.chat.id, random.choice(facts)) log_command(message, "fact")

🦍 Donke — токсичные шутки

@bot.message_handler(func=lambda msg: msg.text == "🦍 Donke") def donke(message): donke_jokes = [ "Donke настолько глуп, что пытался поесть Wi-Fi.", "Donke думает, что RAM — это барашек.", "Donke установил антивирус на холодильник. На всякий случай.", "Donke просит бота скачать себе мозг." ] bot.send_message(message.chat.id, random.choice(donke_jokes)) log_command(message, "donke")

⚒️ Модерация (без /)

@bot.message_handler(func=lambda msg: msg.reply_to_message is not None) def moderation(message): cmd = message.text.lower() target = message.reply_to_message.from_user.id chat_id = message.chat.id if not is_admin(message): return

if "мут" in cmd:
    bot.restrict_chat_member(chat_id, target, until_date=time.time()+600)
    bot.reply_to(message, "🔇 Пользователь замучен на 10 минут.")
elif "размут" in cmd or "анмут" in cmd:
    bot.restrict_chat_member(chat_id, target, can_send_messages=True)
    bot.reply_to(message, "🔊 Пользователь размучен.")
elif "варн" in cmd:
    bot.reply_to(message, "⚠️ Предупреждение выдано.")
elif "бан" in cmd:
    bot.ban_chat_member(chat_id, target)
    bot.reply_to(message, "⛔ Пользователь забанен.")
elif "разбан" in cmd or "унбан" in cmd:
    bot.unban_chat_member(chat_id, target)
    bot.reply_to(message, "✅ Пользователь разбанен.")

log_command(message, cmd)

🧠 Автообработка ссылок (подготовка к TikTok/YouTube)

@bot.message_handler(func=lambda msg: "tiktok.com" in msg.text or "youtube.com" in msg.text or "youtu.be" in msg.text) def try_download(message): bot.reply_to(message, "⏬ Пытаюсь скачать видео... (функция временно отключена)") log_command(message, "video_link")

🌐 Flask сервер

@app.route('/', methods=['GET', 'POST']) def index(): if request.method == 'POST': update = telebot.types.Update.de_json(request.stream.read().decode("utf-8")) bot.process_new_updates([update]) return "", 200 return "MultiBotX запущен!"

🔄 Удаляем вебхук и запускаем бота

bot.remove_webhook() bot.set_webhook(url=os.getenv("RENDER_EXTERNAL_URL"))

