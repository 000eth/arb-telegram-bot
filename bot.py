import asyncio
import os
from dataclasses import dataclass, field

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "Не найден BOT_TOKEN в переменных окружения. "
        "Создай .env файл на сервере/локально и укажи BOT_TOKEN."
    )

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ---------- Простая модель настроек пользователя (в памяти) ----------

@dataclass
class UserSettings:
    coins: list[str] = field(default_factory=list)   # список монет/пар
    min_spread: float = 2.0                          # минимальный спред в %
    min_profit_usd: float = 10.0                     # минимальный профит в $
    sources: list[str] = field(default_factory=list) # список источников (пока просто строки)
    position_size_usd: float = 100.0                 # объём сделки в $
    leverage: float = 1.0                            # плечо
    interval_seconds: int = 60                       # интервал опроса в секундах
    paused: bool = False                             # отправлять уведомления или нет


# Здесь мы временно храним настройки в памяти, по user_id
user_settings: dict[int, UserSettings] = {}


def get_user_settings(user_id: int) -> UserSettings:
    """
    Возвращает настройки пользователя, создаёт с дефолтами, если их ещё нет.
    """
    if user_id not in user_settings:
        user_settings[user_id] = UserSettings()
    return user_settings[user_id]


# ---------- Команды бота ----------

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """
    Обработчик команды /start
    """
    text = (
        "Привет! 👋\n\n"
        "Я бот для отслеживания арбитражных возможностей на perp‑DEX.\n"
        "Сейчас я на ранней стадии: умею базовые команды и храню настройки пользователей в памяти.\n\n"
        "Основные команды:\n"
        "/help — список команд\n"
        "/settings — показать текущие настройки\n"
        "/spread — задать минимальный спред в %\n"
        "/minprofit — задать минимальный профит в $\n"
        "/position — задать объём и плечо\n"
        "/interval — интервал проверки\n"
        "/pause и /resume — пауза уведомлений\n"
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
        "/help - эта помощь\n"
        "/settings - показать текущие настройки\n"
        "/spread <число> - установить минимальный спред в процентах\n"
        "/minprofit <число> - установить минимальный профит в долларах\n"
        "/position <объём_в_$> <плечо> - задать параметры позиции\n"
        "/interval <секунды> - задать интервал проверки\n"
        "/pause - поставить уведомления на паузу\n"
        "/resume - возобновить уведомления\n"
        "\nПримеры:\n"
        "/spread 2.5\n"
        "/minprofit 15\n"
        "/position 1000 3\n"
        "/interval 60\n"
    )
    await message.answer(text)


@dp.message(Command("settings"))
async def cmd_settings(message: Message):
    """
    Показать текущие настройки пользователя
    """
    s = get_user_settings(message.from_user.id)
    text = (
        "Текущие настройки:\n"
        f"- Монеты/пары: {', '.join(s.coins) if s.coins else 'пока не заданы'}\n"
        f"- Минимальный спред: {s.min_spread}%\n"
        f"- Минимальный профит: {s.min_profit_usd}$\n"
        f"- Источники: {', '.join(s.sources) if s.sources else 'пока не заданы'}\n"
        f"- Объём позиции: {s.position_size_usd}$\n"
        f"- Плечо: x{s.leverage}\n"
        f"- Интервал проверки: {s.interval_seconds} сек.\n"
        f"- Пауза уведомлений: {'Да' if s.paused else 'Нет'}\n"
        "\nНастройки пока хранятся только в памяти и пропадут при перезапуске бота. "
        "Позже перенесём их в базу данных."
    )
    await message.answer(text)


@dp.message(Command("spread"))
async def cmd_spread(message: Message):
    """
    /spread <число>
    """
    s = get_user_settings(message.from_user.id)

    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /spread <число>, например: /spread 2.5")
        return

    try:
        value = float(parts[1].replace(",", "."))
    except ValueError:
        await message.answer("Не получилось прочитать число. Пример: /spread 2.5")
        return

    if value <= 0:
        await message.answer("Значение должно быть больше нуля.")
        return

    s.min_spread = value
    await message.answer(f"Минимальный спред установлен: {s.min_spread}%.")


@dp.message(Command("minprofit"))
async def cmd_minprofit(message: Message):
    """
    /minprofit <число>
    """
    s = get_user_settings(message.from_user.id)

    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /minprofit <число>, например: /minprofit 10")
        return

    try:
        value = float(parts[1].replace(",", "."))
    except ValueError:
        await message.answer("Не получилось прочитать число. Пример: /minprofit 15")
        return

    if value <= 0:
        await message.answer("Значение должно быть больше нуля.")
        return

    s.min_profit_usd = value
    await message.answer(f"Минимальный профит установлен: {s.min_profit_usd}$.")


@dp.message(Command("position"))
async def cmd_position(message: Message):
    """
    /position <объём_в_$> <плечо>
    """
    s = get_user_settings(message.from_user.id)

    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Использование: /position <объём_в_$> <плечо>, пример: /position 1000 3")
        return

    try:
        size = float(parts[1].replace(",", "."))
        leverage = float(parts[2].replace(",", "."))
    except ValueError:
        await message.answer("Не получилось прочитать параметры. Пример: /position 1000 3")
        return

    if size <= 0 or leverage <= 0:
        await message.answer("Объём и плечо должны быть больше нуля.")
        return

    s.position_size_usd = size
    s.leverage = leverage
    await message.answer(
        f"Параметры позиции установлены:\n"
        f"- Объём: {s.position_size_usd}$\n"
        f"- Плечо: x{s.leverage}"
    )


@dp.message(Command("interval"))
async def cmd_interval(message: Message):
    """
    /interval <секунды>
    """
    s = get_user_settings(message.from_user.id)

    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /interval <секунды>, пример: /interval 60")
        return

    try:
        value = int(parts[1])
    except ValueError:
        await message.answer("Не получилось прочитать целое число секунд. Пример: /interval 60")
        return

    if value < 10:
        await message.answer("Интервал не должен быть меньше 10 секунд.")
        return

    s.interval_seconds = value
    await message.answer(f"Интервал проверки установлен: {s.interval_seconds} сек.")


@dp.message(Command("pause"))
async def cmd_pause(message: Message):
    s = get_user_settings(message.from_user.id)
    s.paused = True
    await message.answer("Уведомления поставлены на паузу.")


@dp.message(Command("resume"))
async def cmd_resume(message: Message):
    s = get_user_settings(message.from_user.id)
    s.paused = False
    await message.answer("Уведомления возобновлены.")


async def main():
    """
    Точка входа: запускаем бота в режиме long polling
    """
    print("Бот запускается...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
