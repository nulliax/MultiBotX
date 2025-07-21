import telebot

bot = telebot.TeleBot("7870127808:AAGLq533QE63G8ZxrIlddfTaV_I3fnWNN3k")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 Привет! Я — MultiBotX. Готов к работе!")

bot.remove_webhook()
bot.polling(none_stop=True)
