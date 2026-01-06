import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, MenuButtonCommands
from dotenv import load_dotenv

from handlers.commands import register_commands
from handlers.messages import register_message_handlers
from handlers.callbacks import register_callback_handlers
from services.spread_checker import check_spreads_task

# ---------- Загрузка токена ----------

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "Не найден BOT_TOKEN в переменных окружения. "
        "Создай .env файл на сервере/локально и укажи BOT_TOKEN."
    )

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------- Регистрация всех обработчиков ----------

register_commands(dp)
register_message_handlers(dp)
register_callback_handlers(dp)


# ---------- Настройка Menu Button ----------


async def setup_menu_button():
    try:
        commands = [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="help", description="Помощь"),
            BotCommand(command="pause", description="Пауза уведомлений"),
            BotCommand(command="resume", description="Возобновить уведомления"),
        ]
        await bot.set_my_commands(commands)
        
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        print("Menu Button настроен успешно")
    except Exception as e:
        print(f"Ошибка настройки Menu Button: {e}")


# ---------- Точка входа ----------


async def main():
    print("Бот запускается...")
    
    await setup_menu_button()
    
    # Запускаем фоновую задачу проверки спредов
    asyncio.create_task(check_spreads_task(bot))
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
