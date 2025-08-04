import os
import json
import random
from flask import Flask, request
from datetime import datetime, timedelta
from threading import Thread
from telebot import TeleBot, types

app = Flask(__name__)
bot = TeleBot(os.getenv("TOKEN"))
bot.remove_webhook()

# === ФАЙЛ ДЛЯ СТАТИСТИКИ DONKE ===
DONKE_FILE = "donke_stats.json"
if not os.path.exists(DONKE_FILE):
    with open(DONKE_FILE, "w") as f:
        json.dump({}, f)

def load_donke():
    with open(DONKE_FILE, "r") as f:
        return json.load(f)

def save_donke(data):
    with open(DONKE_FILE, "w") as f:
        json.dump(data, f, indent=2)

# === DONKE ===
@bot.message_handler(commands=["camdonke"])
def cam_donke(message):
    user_id = str(message.from_user.id)
    name = message.from_user.first_name
    data = load_donke()
    today = datetime.utcnow().date().isoformat()

    if user_id in data and data[user_id]["last"] == today:
        bot.reply_to(message, f"😈 {name}, Донке устал... приходи завтра.")
        return

    liters = random.randint(1, 100)
    if user_id not in data:
        data[user_id] = {"name": name, "liters": 0, "last": ""}

    data[user_id]["liters"] += liters
    data[user_id]["last"] = today
    save_donke(data)

    bot.reply_to(message, f"💦 *Донке слизывает последние капли...*\n"
                          f"Вы влили аж *{liters}* литров!\n"
                          f"_До завтра, чемпион!_", parse_mode="Markdown")

@bot.message_handler(commands=["topdonke"])
def top_donke(message):
    data = load_donke()
    ranking = sorted(data.items(), key=lambda x: x[1]["liters"], reverse=True)[:50]
    text = "🏆 *ТОП 50 донкеров:*\n\n"
    for i, (uid, udata) in enumerate(ranking, 1):
        text += f"{i}. {udata['name']} — {udata['liters']}л\n"
    bot.reply_to(message, text, parse_mode="Markdown")

# === МОДЕРАЦИЯ ===
@bot.message_handler(func=lambda m: m.reply_to_message is not None and m.text.lower() in ["мут", "варн", "бан", "размут", "анмут", "унбан"])
def moder_action(message):
    if not message.from_user.id in [admin.user.id for admin in bot.get_chat_administrators(message.chat.id)]:
        return bot.reply_to(message, "⛔ Только для админов.")
    cmd = message.text.lower()
    user_id = message.reply_to_message.from_user.id
    if cmd == "мут":
        bot.restrict_chat_member(message.chat.id, user_id, until_date=datetime.now().timestamp() + 3600)
        bot.reply_to(message, "🔇 Пользователь замучен на 1 час.")
    elif cmd == "варн":
        bot.reply_to(message, "⚠️ Пользователю выдано предупреждение.")
    elif cmd == "бан":
        bot.ban_chat_member(message.chat.id, user_id)
        bot.reply_to(message, "🔨 Пользователь забанен.")
    elif cmd in ["размут", "анмут"]:
        bot.restrict_chat_member(message.chat.id, user_id, can_send_messages=True)
        bot.reply_to(message, "🔈 Пользователь размучен.")
    elif cmd == "унбан":
        bot.unban_chat_member(message.chat.id, user_id)
        bot.reply_to(message, "✅ Пользователь разбанен.")

# === ФАН/РАЗВЛЕЧЕНИЯ ===
jokes = [
    "Почему у Донке нет друзей? Потому что он — Donke.",
    "Знаешь кто хуже спама? Donke.",
    "Если ты читаешь это — Donke рядом.",
    "Donke настолько туп, что его игнорирует ИИ.",
    "Donke — это диагноз, а не имя.",
    # ещё добавим позже...
]

facts = [
    "🧠 Факт: У улиток есть 14,000 зубов.",
    "🧠 Факт: Медузы бессмертны. В отличие от Донке.",
    "🧠 Факт: Слоны боятся пчёл.",
    "🧠 Факт: Люди делятся на тех, кто знает Donke… и остальных.",
]

quotes = [
    "🌟 Никогда не сдавайся. Кроме как с Donke.",
    "🌟 Делай добро и бросай его в Donke.",
    "🌟 Donke — это путь. Но в тупик.",
]

@bot.message_handler(commands=["joke", "fact", "quote", "donke"])
def reply_fun(message):
    if message.text == "/joke":
        bot.reply_to(message, random.choice(jokes))
    elif message.text == "/fact":
        bot.reply_to(message, random.choice(facts))
    elif message.text == "/quote":
        bot.reply_to(message, random.choice(quotes))
    elif message.text == "/donke":
        bot.reply_to(message, random.choice(jokes + facts))

# === ЛОГ И СТАТИСТИКА ===
@bot.message_handler(commands=["log"])
def admin_log(message):
    if not message.from_user.id in [admin.user.id for admin in bot.get_chat_administrators(message.chat.id)]:
        return
    data = load_donke()
    total = sum(u["liters"] for u in data.values())
    users = len(data)
    bot.reply_to(message, f"📊 В базе: {users} донкеров\n💦 Всего слито: {total} литров.")

# === START ===
@bot.message_handler(commands=["start", "help"])
def start(message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("/joke", "/fact", "/quote")
    kb.row("/camdonke", "/topdonke")
    bot.send_message(message.chat.id,
                     "👋 Привет, я *MultiBotX* — твой универсальный бот!\n\n"
                     "⚙️ Доступные команды:\n"
                     "• /joke – шутка\n"
                     "• /fact – факт\n"
                     "• /quote – цитата\n"
                     "• /camdonke – слить в Донке\n"
                     "• /topdonke – рейтинг Донке\n"
                     "• /donke – всё и сразу\n"
                     "• /log – статистика (для админов)\n\n"
                     "И просто пиши: мут, бан, анмут (при ответе на сообщение)", parse_mode="Markdown", reply_markup=kb)

# === FLASK ХОСТИНГ ===
@app.route('/', methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        bot.process_new_updates([types.Update.de_json(request.stream.read().decode("utf-8"))])
        return 'ok', 200
    else:
        bot.remove_webhook()
        bot.set_webhook(url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}")
        return 'Webhook set', 200

def run():
    app.run(host='0.0.0.0', port=10000)

Thread(target=run).start()