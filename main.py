# ================== MultiBotX - ЧАСТЬ 1 ==================
import os, re, random, json, logging, tempfile, shutil, asyncio, traceback
from pathlib import Path
from threading import Thread
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask
import requests, yt_dlp

from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand,
    BotCommandScopeDefault, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats,
    ChatPermissions
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
SAVETUBE_KEY = os.getenv("SAVETUBE_KEY")
COMMANDS_SETUP = os.getenv("COMMANDS_SETUP", "true").lower() in ("1","true","yes")
PORT = int(os.getenv("PORT", "5000"))
MAX_SEND_BYTES = int(os.getenv("MAX_SEND_BYTES", str(50 * 1024 * 1024)))  # default 50 MB

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment variables.")

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger("MultiBotX")

flask_app = Flask(__name__)
@flask_app.route("/", methods=["GET"])
def health_check():
    return "MultiBotX running"

ROOT = Path(".")
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DONKE_FILE = DATA_DIR / "donke.json"
JOKES_FILE = DATA_DIR / "jokes.json"
USAGE_FILE = DATA_DIR / "usage.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
ERROR_LOG = DATA_DIR / "errors.log"

def load_json_safe(path: Path, default=None):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed load_json_safe %s", path)
    return default if default is not None else {}

def save_json_safe(path: Path, data):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logger.exception("Failed save_json_safe %s", path)

donke_db = load_json_safe(DONKE_FILE, {})
jokes_db = load_json_safe(JOKES_FILE, {"jokes":[
    "Почему программисты путают Хэллоуин и Рождество? OCT 31 == DEC 25.",
    "Я бы рассказал шутку про UDP, но не уверен, что ты её получишь.",
    "Debugging — превращение багов в фичи."
]})
usage_db = load_json_safe(USAGE_FILE, {})
settings_db = load_json_safe(SETTINGS_FILE, {"antimat":{}})

def inc_usage(key: str):
    usage_db[key] = usage_db.get(key,0) + 1
    save_json_safe(USAGE_FILE, usage_db)

def log_error(exc):
    logger.exception(exc)
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} - {traceback.format_exc()}\n")
    except Exception:
        pass

def today_iso():
    return datetime.utcnow().date().isoformat()

BOT_COMMANDS = [
    ("start","Привет"),
    ("menu","Открыть меню"),
    ("joke","Случайная шутка"),
    ("addjoke","Добавить шутку"),
    ("donke","Шутка Donke"),
    ("camdonke","Залить в Donke (1x/день)"),
    ("topdonke","Топ Donke"),
    ("cat","Фото кота"),
    ("dog","Фото собаки"),
    ("meme","Случайный мем"),
    ("dice","Кубик"),
    ("download","Скачать по ссылке"),
    ("remindme","Напомнить: /remindme <минуты> <текст>"),
    ("antimat","Вкл/выкл анти-мат"),
    ("stats","Статистика (админ)"),
    ("setcommands","Установить команды (админ)"),
    ("checkcommands","Показать команды"),
]

async def _set_my_commands(bot):
    try:
        cmds = [BotCommand(name, desc) for name,desc in BOT_COMMANDS]
        scopes = [BotCommandScopeDefault(), BotCommandScopeAllPrivateChats(), BotCommandScopeAllGroupChats()]
        for scope in scopes:
            await bot.set_my_commands(cmds, scope=scope)
        logger.info("Bot commands set")
        return True
    except Exception as e:
        logger.warning("set_my_commands failed: %s", e)
        return False

def register_commands_sync(application):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_set_my_commands(application.bot))
        loop.close()
    except Exception:
        logger.exception("register_commands_sync failed")# ================== MultiBotX - ЧАСТЬ 2 ==================
def main_menu():
    kb = [
        [InlineKeyboardButton("🎭 Развлечения", callback_data="menu:fun")],
        [InlineKeyboardButton("🎥 Медиа", callback_data="menu:media")],
        [InlineKeyboardButton("😈 Donke", callback_data="menu:donke")],
        [InlineKeyboardButton("🛡 Модерация", callback_data="menu:mod")],
        [InlineKeyboardButton("🔎 Полезное", callback_data="menu:util")]
    ]
    return InlineKeyboardMarkup(kb)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("start")
    text = "👋 Привет! Я MultiBotX. Нажми кнопку или введи /menu."
    try:
        await update.message.reply_markdown(text, reply_markup=main_menu())
    except Exception:
        await update.message.reply_text("Привет! Напиши /menu чтобы открыть меню.")

async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)

async def cmd_joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("joke")
    jokes = jokes_db.get("jokes",[])
    await update.message.reply_text(random.choice(jokes))

async def cmd_addjoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("addjoke")
    text = " ".join(context.args) if context.args else None
    if not text:
        await update.message.reply_text("Использование: /addjoke ТЕКСТ")
        return
    jokes_db.setdefault("jokes",[]).append(text)
    save_json_safe(JOKES_FILE, jokes_db)
    await update.message.reply_text("Шутка добавлена — спасибо!")

async def cmd_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("fact")
    facts = ["У осьминога три сердца.","Кошки спят до 20 часов в день.","Мёд может храниться вечно."]
    await update.message.reply_text(random.choice(facts))

async def cmd_quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("quote")
    quotes = ["«Лучший способ начать — начать.»","«Ошибайтесь быстро и учитесь быстрее.»"]
    await update.message.reply_text(random.choice(quotes))

async def cmd_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("cat")
    try:
        r = requests.get("https://api.thecatapi.com/v1/images/search", timeout=10).json()
        if isinstance(r,list) and r:
            await update.message.reply_photo(r[0]["url"])
        else:
            await update.message.reply_text("Не удалось получить котика.")
    except Exception as e:
        log_error(e)
        await update.message.reply_text("Ошибка при получении котика.")

async def cmd_dog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("dog")
    try:
        r = requests.get("https://dog.ceo/api/breeds/image/random", timeout=10).json()
        await update.message.reply_photo(r["message"])
    except Exception as e:
        log_error(e)
        await update.message.reply_text("Ошибка при получении собаки.")

async def cmd_meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("meme")
    try:
        r = requests.get("https://meme-api.com/gimme", timeout=10).json()
        url = r.get("url"); title = r.get("title","Мем")
        if url:
            await update.message.reply_photo(url, caption=title)
        else:
            await update.message.reply_text("Не удалось получить мем.")
    except Exception as e:
        log_error(e)
        await update.message.reply_text("Не удалось получить мем.")

async def cmd_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("dice")
    await update.message.reply_dice()

DONKE_PHRASES = [
    "Donke — легенда.",
    "Donke улыбается — мир меняется.",
    "Donke написал новый мем."
]

async def cmd_donke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("donke")
    await update.message.reply_text(random.choice(DONKE_PHRASES))

async def cmd_camdonke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("camdonke")
    user = update.effective_user; uid = str(user.id)
    entry = donke_db.get(uid, {"name": user.full_name, "total":0, "last": None})
    if entry.get("last") == today_iso():
        await update.message.reply_text("Сегодня вы уже заливали — приходите завтра.")
        return
    amount = random.randint(1,100)
    entry["total"] = entry.get("total",0) + amount
    entry["last"] = today_iso()
    entry["name"] = user.full_name
    donke_db[uid] = entry
    save_json_safe(DONKE_FILE, donke_db)
    await update.message.reply_text(f"💦 Вы успешно залили в Donke {amount} л! Приходите завтра.")

async def cmd_topdonke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("topdonke")
    if not donke_db:
        await update.message.reply_text("Пока никто не заливал.")
        return
    sorted_list = sorted(donke_db.items(), key=lambda kv: kv[1].get("total",0), reverse=True)[:50]
    lines = [f"{i+1}. {v[1].get('name','?')} — {v[1].get('total',0)} л" for i,(k,v) in enumerate(sorted_list)]
    await update.message.reply_text("\n".join(lines))# ================== MultiBotX - ЧАСТЬ 3 ==================
BAD_WORDS = ["бляд","хуй","пизд","сука","мраз","дурак","идиот"]
MOD_WORDS = {
    "варн":"warn","мут":"mute","размут":"unmute","анмут":"unmute",
    "бан":"ban","анбан":"unban","разбан":"unban"
}

async def moderation_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return
    txt = (update.message.text or "").strip().lower()
    action = MOD_WORDS.get(txt)
    if not action:
        return
    target = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    try:
        member = await update.effective_chat.get_member(update.message.from_user.id)
        if not (member.status in ("administrator","creator") or member.can_restrict_members):
            await update.message.reply_text("У вас нет прав модератора.")
            return
    except Exception:
        await update.message.reply_text("Не удалось проверить права.")
        return
    try:
        if action == "warn":
            ctx_warns = context.bot_data.setdefault("warns", {})
            ctx_warns[target.id] = ctx_warns.get(target.id,0) + 1
            await update.message.reply_text(f"⚠️ {target.full_name} получил предупреждение ({ctx_warns[target.id]}).")
            if ctx_warns[target.id] >= 3:
                await update.effective_chat.ban_member(target.id)
                await update.message.reply_text(f"🚫 {target.full_name} забанен за 3 предупреждения.")
                ctx_warns[target.id] = 0
        elif action == "mute":
            until = datetime.utcnow() + timedelta(minutes=10)
            await update.effective_chat.restrict_member(target.id, ChatPermissions(can_send_messages=False), until_date=until)
            await update.message.reply_text(f"🔇 {target.full_name} замучен на 10 минут.")
        elif action == "unmute":
            await update.effective_chat.restrict_member(target.id, ChatPermissions(can_send_messages=True))
            await update.message.reply_text(f"🔊 {target.full_name} размучен.")
        elif action == "ban":
            await update.effective_chat.ban_member(target.id)
            await update.message.reply_text(f"🚫 {target.full_name} забанен.")
        elif action == "unban":
            await update.effective_chat.unban_member(target.id)
            await update.message.reply_text(f"✅ {target.full_name} разбанен.")
    except Exception as e:
        log_error(e)
        await update.message.reply_text(f"Ошибка модерации: {e}")

async def cmd_antimat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    settings_db.setdefault("antimat", {})
    cur = settings_db["antimat"].get(chat_id, False)
    settings_db["antimat"][chat_id] = not cur
    save_json_safe(SETTINGS_FILE, settings_db)
    await update.message.reply_text(f"Анти-мат {'включён' if settings_db['antimat'][chat_id] else 'выключен'} в этом чате.")

async def profanity_and_flood_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return
    chat_id = str(msg.chat.id)
    antimat_on = settings_db.get("antimat", {}).get(chat_id, False)
    txt = msg.text.lower()
    if antimat_on:
        for bad in BAD_WORDS:
            if bad in txt:
                try:
                    await msg.delete()
                    await msg.reply_text("Сообщение удалено: запрещённая лексика.")
                except Exception:
                    pass
                return
    key = (msg.chat.id, msg.from_user.id)
    now_ts = datetime.utcnow().timestamp()
    last = context.bot_data.setdefault("last_msgs", {})
    arr = last.get(key, [])
    arr = [t for t in arr if now_ts - t < 10]
    arr.append(now_ts)
    last[key] = arr
    if len(arr) > 6:
        try:
            await msg.chat.restrict_member(msg.from_user.id, ChatPermissions(can_send_messages=False),
                                           until_date=datetime.utcnow() + timedelta(minutes=1))
            await msg.reply_text("Антифлуд: замьючен на 1 минуту.")
        except Exception:
            pass

# ---------- yt_dlp helper ----------
YTDL_COMMON = {"format":"bestvideo+bestaudio/best","noplaylist":True,"quiet":True,"no_warnings":True,"cachedir":False}
def _run_yt_dlp(url: str, audio_only: bool=False) -> str|None:
    tmpdir = tempfile.mkdtemp(prefix="mbx_")
    opts = YTDL_COMMON.copy()
    if audio_only:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"192"}]
    outtmpl = str(Path(tmpdir) / "%(id)s.%(ext)s")
    opts["outtmpl"] = outtmpl
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            files = list(Path(tmpdir).glob("*"))
            if not files:
                shutil.rmtree(tmpdir, ignore_errors=True)
                return None
            return str(files[0])
    except Exception as e:
        logger.exception("yt_dlp error: %s", e)
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None

async def download_media_async(url: str, audio_only: bool=False) -> str|None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_yt_dlp, url, audio_only)

async def download_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = None
    if context.args:
        text = context.args[0]
    elif update.message and update.message.text:
        m = re.search(r"https?://\S+", update.message.text)
        if m:
            text = m.group(0)
    if not text:
        await update.message.reply_text("Пришлите ссылку на YouTube / TikTok / Instagram или используйте /download <url>")
        return
    url = text.strip()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📹 Скачать видео", callback_data=f"dl|video|{url}")],
        [InlineKeyboardButton("🎧 Скачать звук (mp3)", callback_data=f"dl|audio|{url}")],
        [InlineKeyboardButton("❌ Отмена", callback_data="dl|cancel|none")]
    ])
    await update.message.reply_text("Выберите формат:", reply_markup=kb)

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    if not data.startswith("dl|"):
        return
    _, kind, url = data.split("|",2)
    if kind == "cancel":
        try: await q.edit_message_text("Отменено.")
        except: pass
        return
    await q.edit_message_text("⏳ Скачиваю, подождите...")
    audio_only = (kind == "audio")
    if "tiktok.com" in url and SAVETUBE_KEY and not audio_only:
        try:
            headers = {"X-RapidAPI-Key":SAVETUBE_KEY}
            api = "https://save-tube-video-download.p.rapidapi.com/download"
            r = requests.get(api, headers=headers, params={"url":url}, timeout=15)
            j = r.json()
            if isinstance(j,dict) and j.get("links"):
                v_url = j["links"][0].get("url")
                if v_url:
                    await context.bot.send_video(chat_id=q.message.chat_id, video=v_url)
                    await q.delete_message()
                    return
        except Exception:
            logger.warning("SaveTube fallback failed")
    fpath = None
    try:
        fpath = await download_media_async(url, audio_only=audio_only)
        if not fpath:
            await q.edit_message_text("❌ Не удалось скачать файл.")
            return
        size = os.path.getsize(fpath)
        if size > MAX_SEND_BYTES:
            await q.edit_message_text("Файл слишком большой для отправки ботом.")
            shutil.rmtree(Path(fpath).parent, ignore_errors=True)
            return
        with open(fpath,"rb") as fh:
            if audio_only:
                try:
                    await context.bot.send_audio(chat_id=q.message.chat_id, audio=fh)
                except Exception:
                    fh.seek(0)
                    await context.bot.send_document(chat_id=q.message.chat_id, document=fh)
            else:
                fh.seek(0)
                try:
                    await context.bot.send_video(chat_id=q.message.chat_id, video=fh)
                except Exception:
                    fh.seek(0)
                    await context.bot.send_document(chat_id=q.message.chat_id, document=fh)
        shutil.rmtree(Path(fpath).parent, ignore_errors=True)
        try: await q.delete_message()
        except: pass
    except Exception as e:
        log_error(e)
        try: await q.edit_message_text("Ошибка при скачивании.")
        except: pass

async def url_auto_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    m = re.search(r"https?://\S+", text)
    if m:
        await download_prompt(update, context)# ================== MultiBotX - ЧАСТЬ 4 ==================
async def remindme_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("remindme")
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Использование: /remindme <минуты> <текст>")
        return
    try:
        minutes = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Первый аргумент — количество минут (число).")
        return
    text = " ".join(context.args[1:])
    await update.message.reply_text(f"Напомню через {minutes} минут.")
    async def _sleep_and_send():
        try:
            await asyncio.sleep(minutes * 60)
            await context.bot.send_message(chat_id=update.effective_user.id, text=f"⏰ Напоминание: {text}")
        except Exception as e:
            log_error(e)
    asyncio.create_task(_sleep_and_send())

async def cmd_searchimage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("searchimage")
    query = " ".join(context.args) if context.args else None
    if not query:
        await update.message.reply_text("Использование: /searchimage <запрос>")
        return
    try:
        url = f"https://source.unsplash.com/800x600/?{requests.utils.requote_uri(query)}"
        await update.message.reply_photo(url)
    except Exception as e:
        log_error(e)
        await update.message.reply_text("Не удалось найти изображение.")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; allowed = False
    if ADMIN_ID and str(user.id) == str(ADMIN_ID): allowed = True
    try:
        member = await update.effective_chat.get_member(user.id)
        if member.status in ("administrator","creator"): allowed = True
    except Exception:
        if update.effective_chat.type == "private": allowed = True
    if not allowed:
        await update.message.reply_text("Только администраторы могут просматривать статистику.")
        return
    inc_usage("stats")
    lines = ["📊 Статистика использования:"]
    for k,v in sorted(usage_db.items(), key=lambda x:x[1], reverse=True)[:100]:
        lines.append(f"{k}: {v}")
    await update.message.reply_text("\n".join(lines) if len(lines)>1 else "Статистика пуста.")

async def cmd_avatar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    photos = await context.bot.get_user_profile_photos(user.id, limit=1)
    if photos.total_count > 0:
        file = photos.photos[0][-1]
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=file.file_id)
    else:
        await update.message.reply_text("У вас нет аватара.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Handler error: %s", context.error)
    log_error(context.error)

def build_application() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("joke", cmd_joke))
    app.add_handler(CommandHandler("addjoke", cmd_addjoke))
    app.add_handler(CommandHandler("fact", cmd_fact))
    app.add_handler(CommandHandler("quote", cmd_quote))
    app.add_handler(CommandHandler("cat", cmd_cat))
    app.add_handler(CommandHandler("dog", cmd_dog))
    app.add_handler(CommandHandler("meme", cmd_meme))
    app.add_handler(CommandHandler("dice", cmd_dice))
    app.add_handler(CommandHandler("donke", cmd_donke))
    app.add_handler(CommandHandler("camdonke", cmd_camdonke))
    app.add_handler(CommandHandler("topdonke", cmd_topdonke))
    app.add_handler(MessageHandler(filters.TEXT & filters.REPLY, moderation_reply_handler))
    app.add_handler(CommandHandler("antimat", cmd_antimat))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, profanity_and_flood_handler))
    app.add_handler(CommandHandler("download", download_prompt))
    app.add_handler(CallbackQueryHandler(download_callback, pattern=r"^dl\|"))
    app.add_handler(MessageHandler(filters.Regex(r"https?://"), url_auto_handler))
    app.add_handler(CommandHandler("remindme", remindme_cmd))
    app.add_handler(CommandHandler("searchimage", cmd_searchimage))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("avatar", cmd_avatar))

    async def setcommands_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user; allowed = False
        if ADMIN_ID and str(user.id) == str(ADMIN_ID): allowed = True
        try:
            member = await update.effective_chat.get_member(user.id)
            if member.status in ("administrator","creator"): allowed = True
        except Exception:
            if update.effective_chat.type == "private": allowed = True
        if not allowed:
            await update.message.reply_text("Только админы могут обновлять команды."); return
        await update.message.reply_text("Обновляю команды...")
        ok = await _set_my_commands(context.bot)
        await update.message.reply_text("Команды установлены." if ok else "Не удалось установить команды.")

    async def checkcommands_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            cmds = await context.bot.get_my_commands()
            if not cmds:
                await update.message.reply_text("Команды не установлены.")
                return
            lines = [f"/{c.command} — {c.description}" for c in cmds]
            await update.message.reply_text("Установленные команды:\n" + "\n".join(lines))
        except Exception as e:
            log_error(e); await update.message.reply_text("Ошибка при получении команд.")

    app.add_handler(CommandHandler("setcommands", setcommands_handler))
    app.add_handler(CommandHandler("checkcommands", checkcommands_handler))

    app.add_error_handler(error_handler)
    return app

def run():
    app = build_application()
    if COMMANDS_SETUP:
        try: register_commands_sync(app)
        except Exception: logger.exception("register commands failed")
    flask_thr = Thread(target=lambda: flask_app.run(host="0.0.0.0", port=PORT), daemon=True)
    flask_thr.start()
    logger.info("Flask health started on port %s", PORT)
    logger.info("Starting bot polling...")
    app.run_polling()

if __name__ == "__main__":
    run()