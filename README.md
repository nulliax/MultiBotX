# MultiBotX (Render Web Service Version)

Это Telegram-бот, работающий на Render как Web Service с Flask.

## Как запустить:
1. Клонируй репозиторий на GitHub
2. Перейди на https://render.com → "New Web Service"
3. Укажи:
   - Build command: `pip install -r requirements.txt`
   - Start command: `python main.py`
4. Добавь переменную окружения: `BOT_TOKEN=твой_токен`