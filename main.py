# ===== MultiBotX — Part 1: config, storage, utils, role system =====
import os, re, json, random, shutil, tempfile, traceback, asyncio, logging
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

# load env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")           # optional super-admin (string)
SAVETUBE_KEY = os.getenv("SAVETUBE_KEY")  # optional
COMMANDS_SETUP = os.getenv("COMMANDS_SETUP", "true").lower() in ("1","true","yes")
PORT = int(os.getenv("PORT", "5000"))
MAX_SEND_BYTES = int(os.getenv("MAX_SEND_BYTES", str(200 * 1024 * 1024)))  # default 200 MB
# NOTE: change MAX_SEND_BYTES in Render env if you want bigger

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment variables.")

# logging
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger("MultiBotX")

# flask for health check
flask_app = Flask(__name__)
@flask_app.route("/", methods=["GET"])
def health():
    return "MultiBotX is alive"

# directories & files
ROOT = Path(".")
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DOWNLOADS_DIR = ROOT / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

DONKE_FILE = DATA_DIR / "donke.json"
JOKES_FILE = DATA_DIR / "jokes.json"
USAGE_FILE = DATA_DIR / "usage.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
ROLES_FILE = DATA_DIR / "roles.json"
ERROR_LOG = DATA_DIR / "errors.log"

# safe json helpers
def load_json_safe(path: Path, default=None):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("load_json_safe failed for %s", path)
    return default if default is not None else {}

def save_json_safe(path: Path, data):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logger.exception("save_json_safe failed for %s", path)

# load stores
donke_db = load_json_safe(DONKE_FILE, {})
jokes_db = load_json_safe(JOKES_FILE, {"jokes": [
    "Почему программисты путают Хэллоуин и Рождество? OCT 31 == DEC 25.",
    "Я бы рассказал шутку про UDP, но она может не дойти.",
    "Debugging: превращение багов в фичи."
]})
usage_db = load_json_safe(USAGE_FILE, {})
settings_db = load_json_safe(SETTINGS_FILE, {"antimat": {}, "role_names": {}})
roles_db = load_json_safe(ROLES_FILE, {})  # structure: { "<chat_id>": { "<user_id>": rank_int } }

# helpers
def inc_usage(key: str):
    usage_db[key] = usage_db.get(key, 0) + 1
    save_json_safe(USAGE_FILE, usage_db)

def log_error(exc: Exception):
    logger.exception(exc)
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} - {traceback.format_exc()}\n")
    except Exception:
        pass

def today_iso():
    return datetime.utcnow().date().isoformat()

# Role system: 5 ranks (0..4). Default names can be customized per chat in settings_db['role_names']
DEFAULT_ROLE_NAMES = {
    "0": "User",
    "1": "Moderator",
    "2": "SeniorMod",
    "3": "Assistant",
    "4": "Owner"
}
# Ensure defaults exist
settings_db.setdefault("role_names", {})
for k, v in DEFAULT_ROLE_NAMES.items():
    settings_db["role_names"].setdefault(k, v)
save_json_safe(SETTINGS_FILE, settings_db)

# roles_db layout: roles_db[chat_id_str][user_id_str] = rank_int
def get_user_rank(chat_id: int, user_id: int) -> int:
    chat_roles = roles_db.get(str(chat_id), {})
    return int(chat_roles.get(str(user_id), 0))

def set_user_rank(chat_id: int, user_id: int, rank: int):
    if rank < 0: rank = 0
    if rank > 4: rank = 4
    roles_db.setdefault(str(chat_id), {})[str(user_id)] = int(rank)
    save_json_safe(ROLES_FILE, roles_db)

def remove_user_rank(chat_id: int, user_id: int):
    chat = roles_db.get(str(chat_id), {})
    if str(user_id) in chat:
        del chat[str(user_id)]
        roles_db[str(chat_id)] = chat
        save_json_safe(ROLES_FILE, roles_db)

def get_role_name(rank: int, chat_id: int=None) -> str:
    rn = settings_db.get("role_names", {})
    return rn.get(str(rank), DEFAULT_ROLE_NAMES.get(str(rank), f"Rank{rank}"))

# permission helper: checks if invoking user has required minimum rank OR Telegram chat admin OR is global ADMIN_ID
async def has_permission(update: Update, context: ContextTypes.DEFAULT_TYPE, min_rank:int=1) -> bool:
    """Return True if user can perform admin action (rank >= min_rank)"""
    user = update.effective_user
    chat = update.effective_chat
    # global OWNER
    if ADMIN_ID and str(user.id) == str(ADMIN_ID):
        return True
    # check stored roles
    try:
        rank = get_user_rank(chat.id, user.id)
        if rank >= min_rank:
            return True
    except Exception:
        logger.exception("has_permission roles check failed")
    # check Telegram admin status as fallback
    try:
        member = await chat.get_member(user.id)
        if member.status in ("administrator", "creator"):
            return True
    except Exception:
        logger.exception("has_permission telegram check failed")
    return False

# convenience: map descriptive names to ranks (you can change names per chat with /setrolenames)
ROLE_LABELS = {
    "owner": 4,
    "assistant": 3,
    "seniormod": 2,
    "mod": 1,
    "user": 0
}

# save initial stores (just in case)
save_json_safe(DONKE_FILE, donke_db)
save_json_safe(JOKES_FILE, jokes_db)
save_json_safe(USAGE_FILE, usage_db)
save_json_safe(SETTINGS_FILE, settings_db)
save_json_safe(ROLES_FILE, roles_db)

# ready — часть 1 окончена# ===== MultiBotX — ЧАСТЬ 2: развлечения, Donke, фото/мемы =====
# entertainment commands: joke, addjoke, fact, quote, cat, dog, meme, dice
async def cmd_joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("joke")
    jokes = jokes_db.get("jokes", [])
    if not jokes:
        await update.message.reply_text("Пока шуток нет. Добавьте /addjoke")
        return
    await update.message.reply_text(random.choice(jokes))

async def cmd_addjoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("addjoke")
    text = " ".join(context.args) if context.args else None
    if not text:
        await update.message.reply_text("Использование: /addjoke ТЕКСТ")
        return
    jokes_db.setdefault("jokes", []).append(text)
    save_json_safe(JOKES_FILE, jokes_db)
    await update.message.reply_text("Шутка добавлена. Спасибо!")

async def cmd_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("fact")
    facts = [
        "У осьминога три сердца.",
        "Мёд может храниться тысячи лет.",
        "Космическое пространство почти полностью пустое."
    ]
    await update.message.reply_text(random.choice(facts))

async def cmd_quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("quote")
    quotes = [
        "«Лучший способ начать — начать.»",
        "«Ошибки — это доказательство попыток.»",
        "«Если не знаешь, что делать — делай шаг.»"
    ]
    await update.message.reply_text(random.choice(quotes))

async def cmd_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("cat")
    try:
        r = requests.get("https://api.thecatapi.com/v1/images/search", timeout=10)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            await update.message.reply_photo(data[0]["url"])
            return
    except Exception as e:
        log_error(e)
    await update.message.reply_text("Не удалось получить котика. Попробуйте позже.")

async def cmd_dog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("dog")
    try:
        r = requests.get("https://dog.ceo/api/breeds/image/random", timeout=10)
        r.raise_for_status()
        data = r.json()
        url = data.get("message")
        if url:
            await update.message.reply_photo(url)
            return
    except Exception as e:
        log_error(e)
    await update.message.reply_text("Не удалось получить собаку. Попробуйте позже.")

async def cmd_meme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("meme")
    try:
        r = requests.get("https://meme-api.com/gimme", timeout=10)
        r.raise_for_status()
        data = r.json()
        url = data.get("url")
        title = data.get("title", "Мем")
        if url:
            await update.message.reply_photo(url, caption=title)
            return
    except Exception as e:
        log_error(e)
    await update.message.reply_text("Не удалось получить мем.")

async def cmd_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("dice")
    await update.message.reply_dice()

# Donke commands (separate set; not mixed with /joke)
DONKE_PHRASES = [
    "Donke — легенда, чья слава вечно ширится.",
    "Donke сделал это лучше всех — просто феномен.",
    "Некоторые называют Donke именем, некоторые — мемом."
]

async def cmd_donke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("donke")
    await update.message.reply_text(random.choice(DONKE_PHRASES))

async def cmd_camdonke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("camdonke")
    user = update.effective_user
    uid = str(user.id)
    entry = donke_db.get(uid, {"name": user.full_name, "total": 0, "last": None})
    if entry.get("last") == today_iso():
        await update.message.reply_text("Сегодня вы уже заливали — заходите завтра.")
        return
    amount = random.randint(1, 100)
    entry["total"] = entry.get("total", 0) + amount
    entry["last"] = today_iso()
    entry["name"] = user.full_name
    donke_db[uid] = entry
    save_json_safe(DONKE_FILE, donke_db)
    await update.message.reply_text(f"💦 Вы успешно залили в Donke {amount} литров! Благодарим, приходите завтра.")

async def cmd_topdonke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("topdonke")
    if not donke_db:
        await update.message.reply_text("Пока никто не заливал.")
        return
    sorted_list = sorted(donke_db.items(), key=lambda kv: kv[1].get("total", 0), reverse=True)[:50]
    lines = []
    for i, (uid, val) in enumerate(sorted_list, start=1):
        name = val.get("name") or f"@{uid}"
        total = val.get("total", 0)
        lines.append(f"{i}. {name} — {total} л")
    await update.message.reply_text("\n".join(lines))# ===== MultiBotX — ЧАСТЬ 3: модерация, анти-мат, роли =====
# Moderation by replying with keywords (no slash). Actions separated and permission-checked.

MOD_WORDS = {
    "варн": "warn",
    "мут": "mute",
    "размут": "unmute", "анмут": "unmute",
    "бан": "ban",
    "анбан": "unban", "разбан": "unban"
}

async def moderation_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only act when message is a reply to another message
    msg = update.message
    if not msg or not msg.reply_to_message or not msg.text:
        return
    txt = msg.text.strip().lower()
    if txt not in MOD_WORDS:
        return
    target = msg.reply_to_message.from_user
    # permission: require rank >=1 OR telegram admin OR global ADMIN_ID
    allowed = await has_permission(update, context, min_rank=1)
    if not allowed:
        await msg.reply_text("У вас нет прав модератора (нужен ранг или права администратора).")
        return
    action = MOD_WORDS[txt]
    try:
        if action == "warn":
            warns = context.bot_data.setdefault("warns", {})
            warns[target.id] = warns.get(target.id, 0) + 1
            await msg.reply_text(f"⚠️ {target.full_name} предупреждён ({warns[target.id]}).")
            if warns[target.id] >= 3:
                await update.effective_chat.ban_member(target.id)
                await msg.reply_text(f"🚫 {target.full_name} забанен за 3 варна.")
                warns[target.id] = 0
        elif action == "mute":
            until = datetime.utcnow() + timedelta(minutes=10)
            await update.effective_chat.restrict_member(target.id, ChatPermissions(can_send_messages=False), until_date=until)
            await msg.reply_text(f"🔇 {target.full_name} замучен на 10 минут.")
        elif action == "unmute":
            await update.effective_chat.restrict_member(target.id, ChatPermissions(can_send_messages=True))
            await msg.reply_text(f"🔊 {target.full_name} размучен.")
        elif action == "ban":
            await update.effective_chat.ban_member(target.id)
            await msg.reply_text(f"🚫 {target.full_name} забанен.")
        elif action == "unban":
            await update.effective_chat.unban_member(target.id)
            await msg.reply_text(f"✅ {target.full_name} разбанен.")
    except Exception as e:
        log_error(e)
        await msg.reply_text(f"Ошибка модерации: {e}")

# Antimat ON/OFF per chat (default: OFF)
async def cmd_antimat_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # require rank >=1
    if not await has_permission(update, context, min_rank=1):
        await update.message.reply_text("Недостаточно прав для включения анти-мата.")
        return
    chat_id = str(update.effective_chat.id)
    settings_db.setdefault("antimat", {})[chat_id] = True
    save_json_safe(SETTINGS_FILE, settings_db)
    await update.message.reply_text("Анти-мат включён в этом чате.")

async def cmd_antimat_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_permission(update, context, min_rank=1):
        await update.message.reply_text("Недостаточно прав для выключения анти-мата.")
        return
    chat_id = str(update.effective_chat.id)
    settings_db.setdefault("antimat", {})[chat_id] = False
    save_json_safe(SETTINGS_FILE, settings_db)
    await update.message.reply_text("Анти-мат выключен в этом чате.")

# profanity filter that only acts if antimat enabled for this chat
async def profanity_and_flood_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return
    chat_id = str(msg.chat.id)
    antimat_on = settings_db.get("antimat", {}).get(chat_id, False)
    text = msg.text.lower()
    if antimat_on:
        for bad in BAD_WORDS:
            if bad in text:
                try:
                    await msg.delete()
                    await msg.reply_text("Сообщение удалено: запрещённая лексика.")
                except Exception:
                    pass
                return
    # anti-flood (simple): allow up to 6 msgs / 10s
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
            await msg.reply_text("Антифлуд: вы замучены на 1 минуту.")
        except Exception:
            pass

# Role management commands: setrole, removerole, showrole, setrolenames
async def cmd_setrole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # usage: /setrole <user_id or @username> <rank 0-4>
    if not await has_permission(update, context, min_rank=3):  # only higher roles can set roles
        await update.message.reply_text("Недостаточно прав. Требуется ранг 3+.")
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Использование: /setrole <user_id|@username> <rank 0-4>")
        return
    target = context.args[0]
    try:
        rank = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Ранг должен быть числом 0..4.")
        return
    # resolve target id
    uid = None
    if target.isdigit():
        uid = int(target)
    elif target.startswith("@"):
        try:
            user = await context.bot.get_chat(target)
            uid = user.id
        except Exception:
            uid = None
    else:
        await update.message.reply_text("Укажите user_id или @username.")
        return
    if not uid:
        await update.message.reply_text("Не удалось найти пользователя.")
        return
    set_user_rank(update.effective_chat.id, uid, rank)
    await update.message.reply_text(f"Роль установлена: {get_role_name(rank, update.effective_chat.id)} для {uid}")

async def cmd_removerole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_permission(update, context, min_rank=3):
        await update.message.reply_text("Недостаточно прав.")
        return
    if not context.args:
        await update.message.reply_text("Использование: /removerole <user_id>")
        return
    try:
        uid = int(context.args[0])
    except Exception:
        await update.message.reply_text("Неверный user_id.")
        return
    remove_user_rank(update.effective_chat.id, uid)
    await update.message.reply_text("Роль удалена.")

async def cmd_showrole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # show rank for user or self
    if context.args:
        try:
            uid = int(context.args[0])
        except:
            await update.message.reply_text("Использование: /showrole <user_id>")
            return
    else:
        uid = update.effective_user.id
    rank = get_user_rank(update.effective_chat.id, uid)
    await update.message.reply_text(f"Ранг: {rank} — {get_role_name(rank, update.effective_chat.id)}")

async def cmd_setrolenames(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # usage: /setrolenames 0:User,1:Mod,2:Lead,3:Assist,4:Owner
    if not await has_permission(update, context, min_rank=4):
        await update.message.reply_text("Только главный админ (ранг 4) может менять названия ролей.")
        return
    if not context.args:
        await update.message.reply_text("Использование: /setrolenames 0:User,1:Mod,2:Lead,3:Assist,4:Owner")
        return
    raw = " ".join(context.args)
    parts = raw.split(",")
    for p in parts:
        if ":" in p:
            idx, name = p.split(":", 1)
            idx = idx.strip()
            name = name.strip()
            if idx.isdigit() and 0 <= int(idx) <= 4:
                settings_db.setdefault("role_names", {})[idx] = name
    save_json_safe(SETTINGS_FILE, settings_db)
    await update.message.reply_text("Названия ролей обновлены.")# ===== MultiBotX — ЧАСТЬ 4: загрузчик медиа (yt_dlp) =====
# yt_dlp options — аккуратно, создаём временную директорию для каждого скачивания
YTDL_BASE_OPTS = {
    "format": "bestvideo+bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "cachedir": False,
    # avoid printing progress to stdout
}

def _yt_dlp_download(url: str, audio_only: bool=False) -> str|None:
    tmpdir = tempfile.mkdtemp(prefix="mbx_")
    opts = dict(YTDL_BASE_OPTS)
    if audio_only:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    outtmpl = str(Path(tmpdir) / "%(id)s.%(ext)s")
    opts["outtmpl"] = outtmpl
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # find downloaded file
            files = list(Path(tmpdir).glob("*"))
            if not files:
                shutil.rmtree(tmpdir, ignore_errors=True)
                return None
            # choose the largest file (video) or the first (audio)
            files = sorted(files, key=lambda p: p.stat().st_size, reverse=True)
            return str(files[0])
    except Exception as e:
        logger.exception("yt_dlp failed: %s", e)
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None

async def yt_download_async(url: str, audio_only: bool=False) -> str|None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _yt_dlp_download, url, audio_only)

# entry point: /download <url> or auto when user sends link (url_auto_handler defined later)
async def download_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # get url from args or message
    url = None
    if context.args:
        url = context.args[0]
    elif update.message and update.message.text:
        m = re.search(r"https?://\S+", update.message.text)
        if m:
            url = m.group(0)
    if not url:
        await update.message.reply_text("Пришлите ссылку на YouTube/TikTok/Instagram или используйте /download <url>")
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📹 Скачать видео", callback_data=f"dl|video|{url}")],
        [InlineKeyboardButton("🎧 Скачать звук (MP3)", callback_data=f"dl|audio|{url}")],
        [InlineKeyboardButton("❌ Отмена", callback_data="dl|cancel|none")]
    ])
    await update.message.reply_text("Выберите формат для скачивания:", reply_markup=kb)

async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    if not data.startswith("dl|"):
        return
    _, kind, url = data.split("|", 2)
    if kind == "cancel":
        try:
            await q.edit_message_text("Отменено.")
        except:
            pass
        return
    await q.edit_message_text("⏳ Скачиваю, подождите... Это может занять время.")
    audio_only = (kind == "audio")
    # First try SaveTube for TikTok if available and not audio-only
    if "tiktok.com" in url and SAVETUBE_KEY and not audio_only:
        try:
            headers = {"X-RapidAPI-Key": SAVETUBE_KEY}
            api = "https://save-tube-video-download.p.rapidapi.com/download"
            r = requests.get(api, headers=headers, params={"url": url}, timeout=15)
            r.raise_for_status()
            j = r.json()
            if isinstance(j, dict) and j.get("links"):
                v_url = j["links"][0].get("url")
                if v_url:
                    try:
                        await context.bot.send_video(chat_id=q.message.chat_id, video=v_url)
                        await q.delete_message()
                        return
                    except Exception:
                        # continue to yt_dlp fallback
                        pass
        except Exception:
            logger.info("SaveTube attempt failed, falling back to yt_dlp")
    # fallback: yt_dlp
    try:
        path = await yt_download_async(url, audio_only=audio_only)
        if not path:
            await q.edit_message_text("❌ Не удалось скачать файл (yt_dlp).")
            return
        size = os.path.getsize(path)
        if size > MAX_SEND_BYTES:
            await q.edit_message_text("Файл превышает лимит отправки (случайный лимит сервера).")
            # optionally: upload to external host — not implemented
            shutil.rmtree(Path(path).parent, ignore_errors=True)
            return
        with open(path, "rb") as fh:
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
        shutil.rmtree(Path(path).parent, ignore_errors=True)
        try:
            await q.delete_message()
        except Exception:
            pass
    except Exception as e:
        log_error(e)
        try:
            await q.edit_message_text("Ошибка при скачивании.")
        except Exception:
            pass

# auto-detect when user sends link: ask for format
async def url_auto_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    m = re.search(r"https?://\S+", update.message.text)
    if m:
        await download_prompt(update, context)# ===== MultiBotX — ЧАСТЬ 5: меню, команды, запуск =====
# prettier menu: categorized with multiple rows and descriptions
def pretty_menu_markup():
    kb = [
        [InlineKeyboardButton("🎭 Развлечения", callback_data="menu:fun")],
        [InlineKeyboardButton("🎥 Медиа (скачать)", callback_data="menu:media"),
         InlineKeyboardButton("🖼 Фото/Мемы", callback_data="menu:images")],
        [InlineKeyboardButton("😈 Donke", callback_data="menu:donke"),
         InlineKeyboardButton("🎲 Разное", callback_data="menu:other")],
        [InlineKeyboardButton("🛡 Модерация", callback_data="menu:mod"),
         InlineKeyboardButton("🔧 Инструменты", callback_data="menu:utils")]
    ]
    return InlineKeyboardMarkup(kb)

async def cmd_start_full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inc_usage("start")
    text = (
        "*MultiBotX*\n"
        "Многофункциональный бот — выберите раздел в меню ниже.\n\n"
        "🔹 Нужна помощь? /menu\n"
    )
    try:
        await update.message.reply_markdown(text, reply_markup=pretty_menu_markup())
    except Exception:
        await update.message.reply_text("Привет! Введите /menu для показа команд.")

# callback handler for menu navigation
async def menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    if data == "menu:fun":
        text = "🎭 *Развлечения*\n/joke — шутка\n/addjoke — добавить шутку\n/fact — факт\n/quote — цитата\n/dice — кубик"
        await q.edit_message_text(text, parse_mode="Markdown")
    elif data == "menu:media":
        text = "🎥 *Медиа*\nОтправьте ссылку на YouTube/TikTok/Instagram и выберите формат.\nИли /download <url>"
        await q.edit_message_text(text, parse_mode="Markdown")
    elif data == "menu:images":
        text = "🖼 *Фото/Мемы*\n/cat — фото кота\n/dog — фото собаки\n/meme — случайный мем"
        await q.edit_message_text(text, parse_mode="Markdown")
    elif data == "menu:donke":
        text = "😈 *Donke*\n/donke — шутка\n/camdonke — один раз в день залить Donke\n/topdonke — топ заливаний"
        await q.edit_message_text(text, parse_mode="Markdown")
    elif data == "menu:mod":
        text = "🛡 *Модерация*\nОтветьте на сообщение и напишите 'мут'/'варн'/'бан' и т.д. (без /).\n/antimat_on — включить анти-мат (только модераторы)\n/antimat_off — выключить."
        await q.edit_message_text(text, parse_mode="Markdown")
    elif data == "menu:utils":
        text = "🔧 *Инструменты*\n/remindme — напоминание\n/searchimage — найти картинку\n/stats — статистика (админ)"
        await q.edit_message_text(text, parse_mode="Markdown")
    else:
        await q.edit_message_text("Раздел временно недоступен.")

# command wrappers for menu and help
async def cmd_menu_plain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start_full(update, context)

# commands to set/check bot commands (admin)
async def cmd_setcommands_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_permission(update, context, min_rank=4):
        await update.message.reply_text("Только главный админ может обновлять команды.")
        return
    await update.message.reply_text("Обновляю команды...")
    ok = await _set_my_commands(context.bot)
    await update.message.reply_text("Команды обновлены." if ok else "Не удалось обновить команды.")

async def cmd_checkcommands_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cmds = await context.bot.get_my_commands()
        if not cmds:
            await update.message.reply_text("Команды не установлены.")
            return
        lines = [f"/{c.command} — {c.description}" for c in cmds]
        await update.message.reply_text("Установленные команды:\n" + "\n".join(lines))
    except Exception as e:
        log_error(e)
        await update.message.reply_text("Ошибка при получении команд.")

# build/register handlers and app
def build_application():
    application = Application.builder().token(BOT_TOKEN).build()
    # start/menu
    application.add_handler(CommandHandler("start", cmd_start_full))
    application.add_handler(CommandHandler("menu", cmd_menu_plain))
    # entertainment
    application.add_handler(CommandHandler("joke", cmd_joke))
    application.add_handler(CommandHandler("addjoke", cmd_addjoke))
    application.add_handler(CommandHandler("fact", cmd_fact))
    application.add_handler(CommandHandler("quote", cmd_quote))
    application.add_handler(CommandHandler("cat", cmd_cat))
    application.add_handler(CommandHandler("dog", cmd_dog))
    application.add_handler(CommandHandler("meme", cmd_meme))
    application.add_handler(CommandHandler("dice", cmd_dice))
    # donke
    application.add_handler(CommandHandler("donke", cmd_donke))
    application.add_handler(CommandHandler("camdonke", cmd_camdonke))
    application.add_handler(CommandHandler("topdonke", cmd_topdonke))
    # moderation & roles
    application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, moderation_reply_handler))
    application.add_handler(CommandHandler("antimat_on", cmd_antimat_on))
    application.add_handler(CommandHandler("antimat_off", cmd_antimat_off))
    application.add_handler(CommandHandler("setrole", cmd_setrole))
    application.add_handler(CommandHandler("removerole", cmd_removerole))
    application.add_handler(CommandHandler("showrole", cmd_showrole))
    application.add_handler(CommandHandler("setrolenames", cmd_setrolenames))
    # media download
    application.add_handler(CommandHandler("download", download_prompt))
    application.add_handler(CallbackQueryHandler(download_callback, pattern=r"^dl\|"))
    application.add_handler(MessageHandler(filters.Regex(r"https?://"), url_auto_handler))
    # reminders & utils
    application.add_handler(CommandHandler("remindme", remindme_cmd))
    application.add_handler(CommandHandler("searchimage", cmd_searchimage))
    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CommandHandler("avatar", cmd_avatar))
    # commands management
    application.add_handler(CommandHandler("setcommands", cmd_setcommands_manual))
    application.add_handler(CommandHandler("checkcommands", cmd_checkcommands_manual))
    # menu callback
    application.add_handler(CallbackQueryHandler(menu_callback_handler, pattern=r"^menu:"))
    # error handler
    application.add_error_handler(error_handler)
    return application

def run():
    app = build_application()
    # optionally register commands when starting
    if COMMANDS_SETUP:
        try:
            register_commands_sync(app)
        except Exception:
            logger.exception("Failed to register commands on start")
    # start Flask for health checks
    flask_thr = Thread(target=lambda: flask_app.run(host="0.0.0.0", port=PORT), daemon=True)
    flask_thr.start()
    logger.info("Flask health server started on port %s", PORT)
    # run polling (safe)
    try:
        logger.info("Starting polling...")
        app.run_polling()
    except Exception as e:
        logger.exception("Application crashed: %s", e)

if __name__ == "__main__":
    run()