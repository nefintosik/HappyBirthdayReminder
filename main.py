import sqlite3
import logging
import pytz
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv()

# Конфигурация
TOKEN=os.getenv('TOKEN')
GROUP_ID=os.getenv('GROUP_ID')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)


def escape_markdown(text: str) -> str:
    escape_chars = '_*[]()~`>#+-=|{}.!'
    return ''.join(['\\' + char if char in escape_chars else char for char in text])

# Подключение к БД
conn = sqlite3.connect('birthdays.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS birthdays
               (id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                date TEXT NOT NULL)''')
conn.commit()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def get_numbered_birthdays():
    cursor.execute("SELECT rowid, name, date FROM birthdays ORDER BY rowid")
    return cursor.fetchall()

@dp.message(Command("start"))
async def start_command(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    help_text = (
        "🎉 *Доступные команды:*\n\n"
        "➕ Добавить день рождения:\n"
        "`/add ФИО ДД\\.ММ\\.ГГГГ`\n\n"
        "❌ Удалить день рождения:\n"
        "`/remove номер`\n\n"
        "📅 Список дней рождений:\n"
        "`/list`\n\n"
        
    )
    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN_V2)


@dp.message(Command("add"))
async def add_birthday(message: Message):
    if not is_admin(message.from_user.id):
        return

    try:
        _, *parts = message.text.split()
        date_str = parts[-1]
        name = ' '.join(parts[:-1])
        
        # Проверка формата даты
        datetime.strptime(date_str, "%d.%m.%Y")
        
        cursor.execute("INSERT INTO birthdays (name, date) VALUES (?, ?)", (name, date_str))
        conn.commit()
        
        await message.answer(
            f"🎉 *{escape_markdown(name)}* добавлен\\(а\\)\\!\nДата: `{escape_markdown(date_str)}`", 
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except Exception as e:
        await message.answer(
            "❌ Ошибка: Неверный формат\\. Используйте:\n`/add ФИО ДД\\.ММ\\.ГГГГ`", 
            parse_mode=ParseMode.MARKDOWN_V2
        )

@dp.message(Command("list"))
async def list_birthdays(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    birthdays = get_numbered_birthdays()
    if not birthdays:
        await message.answer("📭 Список дней рождений пуст")
        return
    
    response = "📅 *Список дней рождений:*\n\n"
    for idx, (rowid, name, date) in enumerate(birthdays):
        response += f"🔹 *{idx}*: {escape_markdown(name)} \\- {escape_markdown(date)}\n"
    
    await message.answer(response, parse_mode=ParseMode.MARKDOWN_V2)

@dp.message(Command("remove"))
async def remove_birthday(message: Message):
    if not is_admin(message.from_user.id):
        return

    try:
        _, number_str = message.text.split()
        number = int(number_str)
        
        birthdays = get_numbered_birthdays()
        if number < 0 or number >= len(birthdays):
            raise ValueError
        
        rowid = birthdays[number][0]
        cursor.execute("DELETE FROM birthdays WHERE rowid = ?", (rowid,))
        conn.commit()
        
        await message.answer(f"✅ Запись *{number}* удалена", parse_mode=ParseMode.MARKDOWN_V2)
    except:
        await message.answer("❌ Неверный номер\\. Используйте `/list` для просмотра номеров", parse_mode=ParseMode.MARKDOWN_V2)

async def check_birthdays():
    now = datetime.now(MOSCOW_TZ)
    today = now.date()
    
    for rowid, name, date_str in get_numbered_birthdays():
        try:
            birth_date = MOSCOW_TZ.localize(
                datetime.strptime(date_str, "%d.%m.%Y")
            ).date()
            
            next_date = birth_date.replace(year=today.year)
            
            # Уведомление за 1 день
            if (next_date - today).days == 1:
                msg = (
                    "🚨 *Внимание\\!* Завтра \\({}\\)\n"
                    "🎂 День рождения у *{}*\\!\n"
                    "_Не забудьте поздравить\\!_ 🎁"
                ).format(
                    escape_markdown(next_date.strftime("%d.%m.%Y")),
                    escape_markdown(name)
                )
                await bot.send_message(GROUP_ID, msg, parse_mode=ParseMode.MARKDOWN_V2)
            
            # Уведомление в день рождения
            if next_date == today:
                msg = (
                    "🎈 *Сегодня {}* отмечает день рождения\\!\n"
                    "🎊 Поздравляем и желаем счастья\\! 🥳"
                ).format(escape_markdown(name))
                await bot.send_message(GROUP_ID, msg, parse_mode=ParseMode.MARKDOWN_V2)
                
        except Exception as e:
            logging.error(f"Ошибка в проверке дня рождения: {str(e)}")

async def main():
    scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)
    scheduler.add_job(check_birthdays, 'cron', hour=12, minute=0)
    scheduler.start()
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
