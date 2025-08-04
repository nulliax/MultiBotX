main.py

import os import random import datetime import logging from flask import Flask, request import telebot import requests from threading import Thread

TOKEN = os.getenv("BOT_TOKEN") SAVETUBE_KEY = os.getenv("SAVETUBE_KEY") ADMIN_IDS = [123456789]  # Заменить на реальные Telegram ID админов

bot = telebot.TeleBot(TOKEN) app = Flask(name)

logging.basicConfig(level=logging.INFO) logger = logging.getLogger(name)

====== ПЕРЕМЕННЫЕ ДЛЯ ХРАНЕНИЯ ДАННЫХ =======

user_warns = {} camdonke_data = {}

====== ФУНКЦИИ УТИЛИТЫ =======

def is_admin(user_id): return user_id in ADMIN_IDS

def get_random_joke(): jokes = [ "Как программист чинит лампочку? Он меняет весь дом.", "Почему айтишники любят зиму? Потому что снег – это фича, а не баг.", "Почему Java-разработчики носят очки? Потому что они не C#", # ... добавь больше ] return random.choice(jokes)

def get_donke_joke(): jokes = [ "Donke настолько тупой, что его даже ИИ не хочет оскорблять.", "Donke - это баг, который никто не стал фиксить.", "Donke не тормозит, он просто ещё не загрузился...", # ... добавь ещё ] return random.choice(jokes)

def get_quote(): quotes = [ "Никогда не сдавайся! Даже если ты Donke.", "Сила в терпении... и в mute.", "Падая семь раз — поднимайся восемь.", # ... больше мотивации ] return random.choice(quotes)

def get_fact(): facts = [ "Коты спят в среднем 70% своей жизни.", "Вода может существовать в трёх состояниях: жидкость, лёд и пар.", "Самый длинный фильм длится более 85 часов.", # ... больше фактов ] return random.choice(facts)

====== КОМАНДЫ =======

@bot.message_handler(commands=['start']) def start(message): bot.reply_to(message, "Привет! Я MultiBotX. Пиши /help для списка команд.")

@bot.message_handler(commands=['help']) def help_cmd(message): bot.reply_to(message, "/joke — шутка\n/quote — цитата\n/fact — факт\n/cat — фото кота\n/dog — фото собаки\n/dice — бросить кубик\n/donke — шутка про Donke\n/camdonke — залить в Donke\n/topdonke — топ Donke\n/youtube <ссылка>\n/tiktok <ссылка>")

@bot.message_handler(commands=['joke']) def joke(message): bot.reply_to(message, get_random_joke())

@bot.message_handler(commands=['quote']) def quote(message): bot.reply_to(message, get_quote())

@bot.message_handler(commands=['fact']) def fact(message): bot.reply_to(message, get_fact())

@bot.message_handler(commands=['cat']) def cat(message): r = requests.get("https://api.thecatapi.com/v1/images/search").json() bot.send_photo(message.chat.id, r[0]['url'])

@bot.message_handler(commands=['dog']) def dog(message): r = requests.get("https://dog.ceo/api/breeds/image/random").json() bot.send_photo(message.chat.id, r['message'])

@bot.message_handler(commands=['dice']) def dice(message): bot.send_dice(message.chat.id)

@bot.message_handler(commands=['donke']) def donke_joke(message): bot.reply_to(message, get_donke_joke())

@bot.message_handler(commands=['camdonke']) def camdonke(message): user_id = message.from_user.id today = datetime.date.today() if user_id in camdonke_data and camdonke_data[user_id]['date'] == today: bot.reply_to(message, "Сегодня вы уже залили в Donke. Приходите завтра!") else: amount = random.randint(1, 100) if user_id not in camdonke_data: camdonke_data[user_id] = {'total': 0} camdonke_data[user_id]['total'] += amount camdonke_data[user_id]['date'] = today bot.reply_to(message, f"Вы успешно влили {amount} литров в Donke! Donke захлёбывается от счастья.")

@bot.message_handler(commands=['topdonke']) def top_donke(message): if not camdonke_data: bot.reply_to(message, "Donke ещё пуст...") return sorted_users = sorted(camdonke_data.items(), key=lambda x: x[1]['total'], reverse=True) text = "🏆 ТОП-50 заливальщиков в Donke:\n" for i, (uid, data) in enumerate(sorted_users[:50], 1): text += f"{i}. {uid} — {data['total']} л.\n" bot.reply_to(message, text)

@bot.message_handler(commands=['youtube']) def youtube_dl(message): try: url = message.text.split(" ", 1)[1] bot.reply_to(message, "⏬ Пытаюсь скачать видео с YouTube...") r = requests.get(f"https://api.savetube.me/ytdl?key={SAVETUBE_KEY}&url={url}").json() video_url = r.get("url") if video_url: bot.send_video(message.chat.id, video_url) else: bot.reply_to(message, "Не удалось скачать видео.") except: bot.reply_to(message, "Неверная команда. Пример: /youtube <ссылка>")

@bot.message_handler(commands=['tiktok']) def tiktok_dl(message): try: url = message.text.split(" ", 1)[1] bot.reply_to(message, "⏬ Пытаюсь скачать видео из TikTok...") r = requests.get(f"https://api.savetube.me/ttdl?key={SAVETUBE_KEY}&url={url}").json() video_url = r.get("url") if video_url: bot.send_video(message.chat.id, video_url) else: bot.reply_to(message, "Не удалось скачать видео.") except: bot.reply_to(message, "Неверная команда. Пример: /tiktok <ссылка>")

====== ЗАПУСК ФЛАСК =======

@app.route(f"/{TOKEN}", methods=['POST']) def webhook(): bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))]) return "OK", 200

@app.route("/") def index(): return "MultiBotX online."

def run(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

if name == "main": Thread(target=run).start() bot.remove_webhook() bot.set_webhook(url=f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/{TOKEN}")

