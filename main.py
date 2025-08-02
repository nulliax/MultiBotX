import telebot from telebot import types import requests import random from datetime import datetime, timedelta

🔐 Токен бота

TOKEN = 'YOUR_BOT_TOKEN_HERE' bot = telebot.TeleBot(TOKEN)

🚫 Хранение предупреждений и мутов

warns = {} mutes = {}

🎉 Развлекательные данные

jokes = [ "Почему программисты путают Хэллоуин и Рождество? Потому что OCT 31 = DEC 25!", "Что говорит один бит другому? - До встречи на шине!", "Баг не баг, а фича — штука вечная!" ]

facts = [ "Пчёлы могут узнавать лица людей.", "Осьминоги имеют три сердца.", "Самая тяжёлая планета — Юпитер." ]

📦 API-ключи

SAVETUBE_API_KEY = '382735d147msh533d7dec3c4d3abp12b125jsnfa97a86f84db'

📌 Команда старт/хелп

@bot.message_handler(commands=['start', 'help']) def send_welcome(message): markup = types.ReplyKeyboardMarkup(resize_keyboard=True) markup.add("/joke", "/fact", "/meme", "/youtube", "/tiktok") bot.send_message(message.chat.id, "👋 Привет! Я — MultiBotX. Вот что я умею:", reply_markup=markup)

⚠️ Предупреждение

@bot.message_handler(commands=['warn']) def warn_user(message): if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение пользователя, чтобы выдать предупреждение.") user_id = message.reply_to_message.from_user.id warns[user_id] = warns.get(user_id, 0) + 1 bot.reply_to(message, f"⚠️ Пользователю выдано предупреждение ({warns[user_id]}).")

🔇 Мут

@bot.message_handler(commands=['mute']) def mute_user(message): if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение пользователя, чтобы выдать мут.") user_id = message.reply_to_message.from_user.id until_date = datetime.now() + timedelta(minutes=10) bot.restrict_chat_member(message.chat.id, user_id, until_date=until_date, permissions=types.ChatPermissions(can_send_messages=False)) mutes[user_id] = until_date bot.reply_to(message, "🔇 Пользователь замучен на 10 минут.")

🔈 Размут

@bot.message_handler(commands=['unmute']) def unmute_user(message): if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение пользователя, чтобы размутить.") user_id = message.reply_to_message.from_user.id bot.restrict_chat_member(message.chat.id, user_id, permissions=types.ChatPermissions(can_send_messages=True)) mutes.pop(user_id, None) bot.reply_to(message, "🔈 Пользователь размучен.")

⛔️ Бан

@bot.message_handler(commands=['ban']) def ban_user(message): if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение пользователя, чтобы забанить.") user_id = message.reply_to_message.from_user.id bot.ban_chat_member(message.chat.id, user_id) bot.reply_to(message, "⛔️ Пользователь забанен.")

✅ Разбан

@bot.message_handler(commands=['unban']) def unban_user(message): if not message.reply_to_message: return bot.reply_to(message, "Ответьте на сообщение пользователя, чтобы разбанить.") user_id = message.reply_to_message.from_user.id bot.unban_chat_member(message.chat.id, user_id) bot.reply_to(message, "✅ Пользователь разбанен.")

😂 Шутка

@bot.message_handler(commands=['joke']) def send_joke(message): bot.send_message(message.chat.id, random.choice(jokes))

🤓 Факт

@bot.message_handler(commands=['fact']) def send_fact(message): bot.send_message(message.chat.id, random.choice(facts))

📷 Мем (рандомное изображение кота как мем)

@bot.message_handler(commands=['meme']) def send_meme(message): url = "https://cataas.com/cat" bot.send_photo(message.chat.id, url, caption="Вот тебе мем 😹")

📥 Скачивание YouTube

@bot.message_handler(commands=['youtube']) def download_youtube(message): bot.send_message(message.chat.id, "🔗 Отправь ссылку на видео YouTube") bot.register_next_step_handler(message, process_youtube)

def process_youtube(message): url = message.text api_url = f"https://save-tube.p.rapidapi.com/download" headers = { "X-RapidAPI-Key": SAVETUBE_API_KEY, "X-RapidAPI-Host": "save-tube.p.rapidapi.com" } params = {"url": url} try: response = requests.get(api_url, headers=headers, params=params) data = response.json() video_url = data.get("video", [{}])[0].get("url") if video_url: bot.send_message(message.chat.id, f"Вот ссылка на скачивание: {video_url}") else: bot.send_message(message.chat.id, "❌ Не удалось получить видео.") except Exception as e: bot.send_message(message.chat.id, f"⚠️ Ошибка: {e}")

📥 Скачивание TikTok

@bot.message_handler(commands=['tiktok']) def download_tiktok(message): bot.send_message(message.chat.id, "🔗 Отправь ссылку на видео TikTok") bot.register_next_step_handler(message, process_tiktok)

def process_tiktok(message): url = message.text api_url = f"https://save-tube.p.rapidapi.com/download" headers = { "X-RapidAPI-Key": SAVETUBE_API_KEY, "X-RapidAPI-Host": "save-tube.p.rapidapi.com" } params = {"url": url} try: response = requests.get(api_url, headers=headers, params=params) data = response.json() video_url = data.get("video", [{}])[0].get("url") if video_url: bot.send_message(message.chat.id, f"Вот ссылка на скачивание: {video_url}") else: bot.send_message(message.chat.id, "❌ Не удалось получить видео.") except Exception as e: bot.send_message(message.chat.id, f"⚠️ Ошибка: {e}")

🚀 Запуск бота

bot.remove_webhook() bot.polling(none_stop=True)

