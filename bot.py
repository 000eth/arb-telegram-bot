import asyncio
import os
from dataclasses import dataclass, field

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command, Text
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from dotenv import load_dotenv

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

# ---------- Модель настроек пользователя ----------


@dataclass
class UserSettings:
    coins: list[str] = field(default_factory=list)   # список монет/пар (позже сделаем)
    min_spread: float = 2.0                          # минимальный спред в %
    min_profit_usd: float = 10.0                     # минимальный профит в $
    sources: list[str] = field(default_factory=list) # источники (позже)
    position_size_usd: float = 100.0                 # объём сделки в $
    leverage: float = 1.0                            # плечо
    interval_seconds: int = 60                       # интервал проверки в секундах
    paused: bool = False                             # пауза уведомлений
    pending_action: str | None = None               # что сейчас ждём от пользователя


user_settings: dict[int, UserSettings] = {}


def get_user_settings(user_id: int) -> UserSettings:
    """
    Возвращает настройки пользователя, создаёт с дефолтами, если их ещё нет.
    """
    if user_id not in user_settings:
        user_settings[user_id] = UserSettings()
    return user_settings[user_id]


# ---------- Кнопки меню настроек ----------

BTN_POSITION = "Объём и плечо"
BTN_MIN_SPREAD = "Минимальный спред"
BTN_MIN_PROFIT = "Минимальный профит"
BTN_INTERVAL = "Интервал проверки"
BTN_CANCEL = "Отмена"

settings_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_POSITION)],
        [KeyboardButton(text=BTN_MIN_SPREAD)],
        [KeyboardButton(text=BTN_MIN_PROFIT)],
        [KeyboardButton(text=BTN_INTERVAL)],
        [KeyboardButton(text=BTN_CANCEL)],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)


# ---------- Команды ----------


@dp.message(CommandStart())
async def cmd_start(message: Message):
    s = get_user_settings(message.from_user.id)
    text = (
        "Привет! 👋\n\n"
        "Я бот для отслеживания арбитражных возможностей на perp‑DEX.\n"
        "Сейчас я умею базовые настройки.\n\n"
        "Основные команды:\n"
        "/help — список команд\n"
        "/settings — меню настроек с кнопками\n"
        "/pause и /resume — пауза уведомлений\n\n"
        "Попробуй: нажми /settings и выбери, что хочешь настроить."
    )
    await message.answer(text)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "Доступные команды:\n"
        "/start - приветственное сообщение\n"
        "/help - эта помощь\n"
        "/settings - меню настроек с кнопками\n"
        "/pause - поставить уведомления на паузу\n"
        "/resume - возобновить уведомления\n\n"
        "Через команды (альтернатива кнопкам):\n"
        "/spread <число> - минимальный спред в %\n"
        "/minprofit <число> - минимальный профит в $\n"
        "/position <объём_в_$> <плечо> - объём и плечо\n"
        "/interval <секунды> - интервал проверки\n"
    )
    await message.answer(text)


@dp.message(Command("settings"))
async def cmd_settings(message: Message):
    """
    Показываем текущие настройки + выводим клавиатуру для изменения.
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
        f"- Пауза уведомлений: {'Да' if s.paused else 'Нет'}\n\n"
        "Выбери, что хочешь изменить, с помощью кнопок ниже."
    )
    await message.answer(text, reply_markup=settings_keyboard)


@dp.message(Command("pause"))
async def cmd_pause(message: Message):
    s = get_user_settings(message.from_user.id)
    s.paused = True
    await message.answer("Уведомления поставлены на паузу.", reply_markup=ReplyKeyboardRemove())


@dp.message(Command("resume"))
async def cmd_resume(message: Message):
    s = get_user_settings(message.from_user.id)
    s.paused = False
    await message.answer("Уведомления возобновлены.", reply_markup=ReplyKeyboardRemove())


# ---------- Обработка нажатий на кнопки меню ----------


@dp.message(Text(BTN_CANCEL))
async def handle_cancel(message: Message):
    s = get_user_settings(message.from_user.id)
    s.pending_action = None
    await message.answer("Отменено. Настройки не изменены.", reply_markup=ReplyKeyboardRemove())


@dp.message(Text(BTN_POSITION))
async def handle_btn_position(message: Message):
    s = get_user_settings(message.from_user.id)
    s.pending_action = "position"
    await message.answer(
        "Введи объём и плечо через пробел.\n"
        "Пример: 1000 3  (это объём 1000$ и плечо x3)",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(Text(BTN_MIN_SPREAD))
async def handle_btn_min_spread(message: Message):
    s = get_user_settings(message.from_user.id)
    s.pending_action = "min_spread"
    await message.answer(
        "Введи минимальный спред в процентах.\n"
        "Пример: 2.5",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(Text(BTN_MIN_PROFIT))
async def handle_btn_min_profit(message: Message):
    s = get_user_settings(message.from_user.id)
    s.pending_action = "min_profit"
    await message.answer(
        "Введи минимальный профит в долларах.\n"
        "Пример: 20",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(Text(BTN_INTERVAL))
async def handle_btn_interval(message: Message):
    s = get_user_settings(message.from_user.id)
    s.pending_action = "interval"
    await message.answer(
        "Введи интервал проверки в секундах.\n"
        "Пример: 60",
        reply_markup=ReplyKeyboardRemove(),
    )


# ---------- Команды через текст (альтернатива кнопкам) ----------


@dp.message(Command("spread"))
async def cmd_spread(message: Message):
    """
    /spread <число>
    """
    s = get_user_settings(message.from_user.id)

    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /spread <число>, пример: /spread 2.5")
        return

    await apply_min_spread(message, s, parts[1])


@dp.message(Command("minprofit"))
async def cmd_minprofit(message: Message):
    """
    /minprofit <число>
    """
    s = get_user_settings(message.from_user.id)

    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /minprofit <число>, пример: /minprofit 20")
        return

    await apply_min_profit(message, s, parts[1])


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

    await apply_position(message, s, parts[1], parts[2])


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

    await apply_interval(message, s, parts[1])


# ---------- Общий обработчик "следующего ввода" ----------


@dp.message()
async def handle_free_text(message: Message):
    """
    Сюда попадают все сообщения, которые не поймали другие хендлеры.
    Если для пользователя выставлен pending_action, трактуем это как ответ на запрос.
    """
    s = get_user_settings(message.from_user.id)

    if not s.pending_action:
        # Ничего не ждём от пользователя — просто подскажем про /settings
        await message.answer("Я тебя не понял. Используй /settings, чтобы открыть меню настроек.")
        return

    action = s.pending_action

    if action == "min_spread":
        await apply_min_spread(message, s, message.text)
    elif action == "min_profit":
        await apply_min_profit(message, s, message.text)
    elif action == "position":
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer("Нужно два числа через пробел. Пример: 1000 3")
            return
        await apply_position(message, s, parts[0], parts[1])
    elif action == "interval":
        await apply_interval(message, s, message.text)
    else:
        await message.answer("Неизвестное действие. Попробуй ещё раз через /settings.")
        s.pending_action = None
        return

    # Если дошли сюда без ошибок — сбрасываем ожидание и можем снова показать меню
    if s.pending_action is None:
        # уже сброшено внутри apply_* в случае ошибки
        return
    s.pending_action = None
    await message.answer("Готово. Можешь открыть /settings, чтобы проверить настройки.")


# ---------- Функции применения настроек ----------


async def apply_min_spread(message: Message, s: UserSettings, raw_value: str):
    try:
        value = float(raw_value.replace(",", "."))
    except ValueError:
        await message.answer("Не получилось прочитать число. Пример: 2.5")
        s.pending_action = "min_spread"
        return

    if value <= 0:
        await message.answer("Значение должно быть больше нуля.")
        s.pending_action = "min_spread"
        return

    s.min_spread = value
    s.pending_action = None
    await message.answer(f"Минимальный спред установлен: {s.min_spread}%.")


async def apply_min_profit(message: Message, s: UserSettings, raw_value: str):
    try:
        value = float(raw_value.replace(",", "."))
    except ValueError:
        await message.answer("Не получилось прочитать число. Пример: 20")
        s.pending_action = "min_profit"
        return

    if value <= 0:
        await message.answer("Значение должно быть больше нуля.")
        s.pending_action = "min_profit"
        return

    s.min_profit_usd = value
    s.pending_action = None
    await message.answer(f"Минимальный профит установлен: {s.min_profit_usd}$.")


async def apply_position(message: Message, s: UserSettings, raw_size: str, raw_lev: str):
    try:
        size = float(raw_size.replace(",", "."))
        leverage = float(raw_lev.replace(",", "."))
    except ValueError:
        await message.answer("Не получилось прочитать объём и плечо. Пример: 1000 3")
        s.pending_action = "position"
        return

    if size <= 0 or leverage <= 0:
        await message.answer("Объём и плечо должны быть больше нуля.")
        s.pending_action = "position"
        return

    s.position_size_usd = size
    s.leverage = leverage
    s.pending_action = None
    await message.answer(
        f"Параметры позиции установлены:\n"
        f"- Объём: {s.position_size_usd}$\n"
        f"- Плечо: x{s.leverage}"
    )


async def apply_interval(message: Message, s: UserSettings, raw_value: str):
    try:
        value = int(raw_value)
    except ValueError:
        await message.answer("Не получилось прочитать целое число секунд. Пример: 60")
        s.pending_action = "interval"
        return

    if value < 10:
        await message.answer("Интервал не должен быть меньше 10 секунд.")
        s.pending_action = "interval"
        return

    s.interval_seconds = value
    s.pending_action = None
    await message.answer(f"Интервал проверки установлен: {s.interval_seconds} сек.")


# ---------- Точка входа ----------


async def main():
    print("Бот запускается...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
