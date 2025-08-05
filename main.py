import os
import random
import logging
import requests
from flask import Flask, request
from telegram import Bot, Update, ChatPermissions, InputFile
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, filters, CallbackContext
from dotenv import load_dotenv

load_dotenv()

# --- Настройки ---
TOKEN = os.getenv("BOT_TOKEN")
API = os.getenv("SAVE_TUBE_API_KEY")
HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME")

bot = Bot(token=TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot=bot, update_queue=None, workers=4, use_context=True)

# --- Логгинг ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- Хранилище ---
warns = {}
donke_rating = {}

# --- Команды ---

def start(update: Update, context: CallbackContext):
    update.message.reply_text("👋 Привет! Я бот MultiBotX. Напиши /help, чтобы узнать, что я умею.")

def help_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🛠 Команды:\n"
        "/joke – шутка\n"
        "/fact – факт\n"
        "/quote – цитата\n"
        "/cat – котик\n"
        "/dog – пёсик\n"
        "/meme – мем\n"
        "/dice – кубик 🎲\n"
        "/donke – пасхалка\n"
        "/camdonke – мой рейтинг donke\n"
        "/topdonke – топ donke\n"
        "/yt <ссылка> – скачать YouTube\n"
        "/tt <ссылка> – скачать TikTok\n"
        "\n🛡 Модерация (в ответ на сообщение):\n"
        "варн / мут / бан / размут / анмут / унбан"
    )

# --- Развлечения ---

def joke(update: Update, context: CallbackContext):
    jokes = [
        "Почему компьютер не может играть в футбол? Он боится вирусов!",
        "Программисты не плачут — они делают бэкапы эмоций.",
        "Упал сервер? Главное — не паниковать. Это просто шанс начать всё с нуля.",
        "Я бы рассказал тебе шутку про UDP... но ты мог бы её не получить.",
        "Чёрный юмор как интернет — не у всех работает."
    ]
    update.message.reply_text(random.choice(jokes))

def fact(update: Update, context: CallbackContext):
    facts = [
        "Осьминоги имеют три сердца.",
        "Медузы существуют уже более 600 миллионов лет.",
        "Самый большой живой организм — гриб в Орегоне.",
        "Google обрабатывает более 99 000 запросов в секунду.",
        "Первый e-mail был отправлен в 1971 году."
    ]
    update.message.reply_text(random.choice(facts))

def quote(update: Update, context: CallbackContext):
    quotes = [
        "«Логика может привести вас от пункта А к пункту Б. Воображение — куда угодно.» – Эйнштейн",
        "«Будь изменением, которое хочешь видеть в мире.» – Ганди",
        "«Кто хочет — ищет возможности. Кто не хочет — ищет причины.»",
        "«Чем больше узнаёшь, тем больше понимаешь, как мало знаешь.» – Сократ"
    ]
    update.message.reply_text(random.choice(quotes))

def cat(update: Update, context: CallbackContext):
    url = "https://cataas.com/cat"
    update.message.reply_photo(url)

def dog(update: Update, context: CallbackContext):
    res = requests.get("https://random.dog/woof.json").json()
    update.message.reply_photo(res['url'])

def meme(update: Update, context: CallbackContext):
    res = requests.get("https://meme-api.com/gimme").json()
    update.message.reply_photo(res['url'], caption=res['title'])

def dice(update: Update, context: CallbackContext):
    update.message.reply_dice()

# --- Пасхалки и рейтинг ---

def donke(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    donke_rating[user_id] = donke_rating.get(user_id, 0) + 1
    insults = [
        f"{username}, ты donke донкийский! 🤡",
        f"{username}, твою тупость даже AI не может распознать.",
        f"{username}, тебя в шутках никто не переплюнет. По тупости.",
        f"{username}, ты — ходячий баг реальности. 🐛"
    ]
    update.message.reply_text(random.choice(insults))

def camdonke(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    count = donke_rating.get(user_id, 0)
    update.message.reply_text(f"Ты donke {count} раз(а) 🤡")

def topdonke(update: Update, context: CallbackContext):
    if not donke_rating:
        update.message.reply_text("Donke пока нет. Будь первым!")
        return
    top = sorted(donke_rating.items(), key=lambda x: x[1], reverse=True)
    msg = "🏆 ТОП Donke:\n"
    for i, (user_id, count) in enumerate(top[:5], start=1):
        user = bot.get_chat_member(update.effective_chat.id, user_id).user
        msg += f"{i}. {user.first_name} — {count}\n"
    update.message.reply_text(msg)

# --- Модерация (без "/") ---

def moderation_handler(update: Update, context: CallbackContext):
    text = update.message.text.lower()
    reply = update.message.reply_to_message
    if not reply:
        return

    member = update.effective_chat.get_member(update.effective_user.id)
    if not member.can_restrict_members:
        update.message.reply_text("Недостаточно прав.")
        return

    target = reply.from_user.id

    if "варн" in text:
        warns[target] = warns.get(target, 0) + 1
        update.message.reply_text(f"⚠️ Предупреждение. Всего: {warns[target]}")
        if warns[target] >= 3:
            context.bot.ban_chat_member(update.effective_chat.id, target)
            update.message.reply_text("🚫 Пользователь забанен за 3 предупреждения.")

    elif "мут" in text:
        context.bot.restrict_chat_member(update.effective_chat.id, target, ChatPermissions(can_send_messages=False))
        update.message.reply_text("🔇 Мут выдан.")

    elif "размут" in text or "анмут" in text:
        context.bot.restrict_chat_member(update.effective_chat.id, target, ChatPermissions(can_send_messages=True))
        update.message.reply_text("🔊 Размучен.")

    elif "бан" in text:
        context.bot.ban_chat_member(update.effective_chat.id, target)
        update.message.reply_text("🚫 Забанен.")

    elif "унбан" in text:
        context.bot.unban_chat_member(update.effective_chat.id, target)
        update.message.reply_text("✅ Разбанен.")

# --- Видео YouTube / TikTok ---

def download(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("❗ Укажи ссылку: /yt <url> или /tt <url>")
        return

    url = context.args[0]
    msg = update.message.reply_text("⏬ Загружаю видео...")

    api_url = f"https://api.savetube.me/info?url={url}&apikey={API}"
    res = requests.get(api_url).json()

    try:
        title = res['title']
        video_url = res['url'][0]['url']
        caption = f"🎬 <b>{title}</b>"
        update.message.reply_video(video=video_url, caption=caption, parse_mode='HTML')
        msg.delete()
    except:
        msg.edit_text("⚠️ Не удалось скачать видео.")

# --- Хендлеры ---

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_command))
dispatcher.add_handler(CommandHandler("joke", joke))
dispatcher.add_handler(CommandHandler("fact", fact))
dispatcher.add_handler(CommandHandler("quote", quote))
dispatcher.add_handler(CommandHandler("cat", cat))
dispatcher.add_handler(CommandHandler("dog", dog))
dispatcher.add_handler(CommandHandler("meme", meme))
dispatcher.add_handler(CommandHandler("dice", dice))
dispatcher.add_handler(CommandHandler("donke", donke))
dispatcher.add_handler(CommandHandler("camdonke", camdonke))
dispatcher.add_handler(CommandHandler("topdonke", topdonke))
dispatcher.add_handler(CommandHandler("yt", download))
dispatcher.add_handler(CommandHandler("tt", download))
dispatcher.add_handler(MessageHandler(filters.TEXT & filters.REPLY, moderation_handler))

# --- Flask-хостинг ---
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

@app.route("/")
def index():
    return "🤖 MultiBotX работает!"

if __name__ == "__main__":
    bot.delete_webhook()
    bot.set_webhook(f"https://{HOST}/{TOKEN}")
    app.run(host="0.0.0.0", port=8080)