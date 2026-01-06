from aiogram import Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from models import get_user_settings
from keyboards import get_main_menu_reply_keyboard


def register_commands(dp: Dispatcher):
    """Регистрирует обработчики команд"""
    
    @dp.message(CommandStart())
    async def cmd_start(message: Message):
        s = get_user_settings(message.from_user.id)
        text = (
            "Привет! 👋\n\n"
            "Я бот для отслеживания арбитражных возможностей на perp‑DEX.\n"
            "Я автоматически проверяю спреды и отправляю уведомления, когда нахожу подходящие возможности.\n\n"
            "Используй кнопки меню для навигации."
        )
        await message.answer(text, reply_markup=get_main_menu_reply_keyboard())
    
    
    @dp.message(Command("help"))
    async def cmd_help(message: Message):
        text = (
            "Доступные команды:\n"
            "/start - главное меню\n"
            "/help - эта помощь\n"
            "/pause - поставить уведомления на паузу\n"
            "/resume - возобновить уведомления\n\n"
            "Используй кнопки меню для навигации и настройки бота."
        )
        await message.answer(text, reply_markup=get_main_menu_reply_keyboard())
    
    
    @dp.message(Command("pause"))
    async def cmd_pause(message: Message):
        s = get_user_settings(message.from_user.id)
        s.paused = True
        await message.answer("Уведомления поставлены на паузу.", reply_markup=get_main_menu_reply_keyboard())
    
    
    @dp.message(Command("resume"))
    async def cmd_resume(message: Message):
        s = get_user_settings(message.from_user.id)
        s.paused = False
        await message.answer("Уведомления возобновлены.", reply_markup=get_main_menu_reply_keyboard())
