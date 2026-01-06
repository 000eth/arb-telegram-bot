   import asyncio
   import os

   from aiogram import Bot, Dispatcher
   from aiogram.filters import CommandStart, Command
   from aiogram.types import Message
   from dotenv import load_dotenv

   # Загружаем переменные из .env
   load_dotenv()
   BOT_TOKEN = os.getenv("BOT_TOKEN")


   # Проверяем, что токен есть
   if not BOT_TOKEN:
       raise RuntimeError("Не найден BOT_TOKEN в переменных окружения. "
                          "Создай .env файл на сервере/локально и укажи BOT_TOKEN.")


   # Создаём объекты бота и диспетчера
   bot = Bot(token=BOT_TOKEN)
   dp = Dispatcher()


   @dp.message(CommandStart())
   async def cmd_start(message: Message):
       """
       Обработчик команды /start
       """
       text = (
           "Привет! 👋\n\n"
           "Я бот для отслеживания арбитражных возможностей на perp‑DEX.\n"
           "Пока что я умею немного, но мы будем постепенно добавлять функционал.\n\n"
           "Команда /help — посмотреть, что я уже умею."
       )
       await message.answer(text)


   @dp.message(Command("help"))
   async def cmd_help(message: Message):
       """
       Обработчик команды /help
       """
       text = (
           "Доступные команды:\n"
           "/start - приветственное сообщение\n"
           "/help - эта помощь\n\n"
           "В будущем здесь появятся:\n"
           "- /settings - настройки\n"
           "- /coins - список монет\n"
           "- /spread - минимальный спред\n"
           "- /minprofit - минимальный доход в долларах\n"
           "- /sources - выбор perp‑DEX\n"
           "- /position - объём и плечо\n"
       )
       await message.answer(text)


   async def main():
       """
       Точка входа: запускаем бота в режиме long polling
       """
       print("Бот запускается...")
       await dp.start_polling(bot)


   if __name__ == "__main__":
       asyncio.run(main())
