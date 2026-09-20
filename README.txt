GASTRO Catering Telegram Bot

1. Встановіть Python 3.11+.
2. Встановіть залежності:
   pip install -r requirements.txt
3. Задайте змінні середовища:
   BOT_TOKEN — токен від BotFather
   ADMIN_ID — ваш числовий Telegram ID
4. Запустіть:
   python bot.py

Як дізнатися ADMIN_ID:
Напишіть будь-якому Telegram-боту, який показує ваш user ID, або тимчасово додайте логування message.from_user.id.

Адмін-команди:
/admin
/items
/price salmon 280
/toggle salmon

ВАЖЛИВО: не публікуйте BOT_TOKEN і не додавайте його прямо в bot.py.
