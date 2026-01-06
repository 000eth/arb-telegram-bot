import asyncio
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    BotCommand,
    MenuButtonCommands,
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
    coins: list[str] = field(default_factory=list)   # список монет/пар
    min_spread: float = 2.0                          # минимальный спред в %
    min_profit_usd: float = 10.0                     # минимальный профит в $
    sources: list[str] = field(default_factory=list) # источники (позже)
    position_size_usd: float = 100.0                 # объём сделки в $
    leverage: float = 1.0                            # плечо
    interval_seconds: int = 60                       # интервал проверки в секундах
    paused: bool = False                             # пауза уведомлений
    pending_action: str | None = None               # что сейчас ждём от пользователя


user_settings: dict[int, UserSettings] = {}

# Словарь для отслеживания последних уведомлений (анти-спам)
# Формат: {user_id: {coin: datetime}}
last_notifications: dict[int, dict[str, datetime]] = {}


def get_user_settings(user_id: int) -> UserSettings:
    """
    Возвращает настройки пользователя, создаёт с дефолтами, если их ещё нет.
    """
    if user_id not in user_settings:
        user_settings[user_id] = UserSettings()
    if user_id not in last_notifications:
        last_notifications[user_id] = {}
    return user_settings[user_id]


# ---------- Конфигурация комиссий perp-DEX (пока захардкожены) ----------
# Формат: {dex_name: {"maker": %, "taker": %}}
DEX_FEES = {
    "Nado": {"maker": 0.02, "taker": 0.05},      # 0.02% мейкер, 0.05% тейкер
    "Ethereal": {"maker": 0.02, "taker": 0.05},
    "Pacifica": {"maker": 0.02, "taker": 0.05},
    "Extended": {"maker": 0.02, "taker": 0.05},
    "Variational": {"maker": 0.02, "taker": 0.05},
}

# Список доступных источников (пока для теста)
AVAILABLE_SOURCES = list(DEX_FEES.keys())

# Минимальный интервал между уведомлениями по одной монете (в минутах)
MIN_NOTIFICATION_INTERVAL_MINUTES = 5


# ---------- Callback data для inline-кнопок ----------

CALLBACK_MAIN_MENU = "main_menu"
CALLBACK_SETTINGS = "settings"
CALLBACK_COINS = "coins"
CALLBACK_POSITION = "position"
CALLBACK_MIN_SPREAD = "min_spread"
CALLBACK_MIN_PROFIT = "min_profit"
CALLBACK_INTERVAL = "interval"
CALLBACK_COINS_ADD = "coins_add"
CALLBACK_COINS_REMOVE = "coins_remove"
CALLBACK_COINS_LIST = "coins_list"
CALLBACK_BACK = "back"


# ---------- Функции для создания клавиатур ----------


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data=CALLBACK_SETTINGS)],
            [InlineKeyboardButton(text="🪙 Монеты", callback_data=CALLBACK_COINS)],
            [InlineKeyboardButton(text="📊 Текущие настройки", callback_data="show_settings")],
        ]
    )
    return keyboard


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Меню настроек"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 Объём и плечо", callback_data=CALLBACK_POSITION)],
            [InlineKeyboardButton(text="📈 Минимальный спред", callback_data=CALLBACK_MIN_SPREAD)],
            [InlineKeyboardButton(text="💵 Минимальный профит", callback_data=CALLBACK_MIN_PROFIT)],
            [InlineKeyboardButton(text="⏱ Интервал проверки", callback_data=CALLBACK_INTERVAL)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_MAIN_MENU)],
        ]
    )
    return keyboard


def get_coins_keyboard() -> InlineKeyboardMarkup:
    """Меню управления монетами"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить монету", callback_data=CALLBACK_COINS_ADD)],
            [InlineKeyboardButton(text="➖ Удалить монету", callback_data=CALLBACK_COINS_REMOVE)],
            [InlineKeyboardButton(text="📋 Список монет", callback_data=CALLBACK_COINS_LIST)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_MAIN_MENU)],
        ]
    )
    return keyboard


# ---------- Функции для работы с ценами (пока тестовые) ----------


async def get_fake_price(dex_name: str, coin: str) -> float:
    """
    Получает "фейковую" цену для теста.
    Позже здесь будет реальный запрос к API.
    """
    # Генерируем случайную цену в разумном диапазоне
    base_prices = {
        "BTC": 60000,
        "ETH": 3000,
        "SOL": 150,
    }
    
    base = base_prices.get(coin, 1000)
    # Добавляем случайное отклонение ±2%
    variation = random.uniform(-0.02, 0.02)
    return base * (1 + variation)


async def get_prices_for_coin(coin: str, sources: list[str]) -> dict[str, float]:
    """
    Получает цены для монеты со всех указанных источников.
    Возвращает словарь {dex_name: price}
    """
    prices = {}
    for source in sources:
        if source in AVAILABLE_SOURCES:
            price = await get_fake_price(source, coin)
            prices[source] = price
    return prices


def calculate_spread(prices: dict[str, float]) -> tuple[float, str, str]:
    """
    Рассчитывает спред между минимальной и максимальной ценой.
    Возвращает: (spread_percent, min_dex, max_dex)
    """
    if len(prices) < 2:
        return 0.0, "", ""
    
    min_dex = min(prices, key=prices.get)
    max_dex = max(prices, key=prices.get)
    min_price = prices[min_dex]
    max_price = prices[max_dex]
    
    if min_price == 0:
        return 0.0, min_dex, max_dex
    
    spread_percent = ((max_price - min_price) / min_price) * 100
    return spread_percent, min_dex, max_dex


def calculate_profit(
    min_price: float,
    max_price: float,
    position_size_usd: float,
    leverage: float,
    min_dex: str,
    max_dex: str,
) -> float:
    """
    Рассчитывает ожидаемый профит в долларах с учётом комиссий.
    """
    # Комиссии (в долях, не процентах)
    fee_min_dex = DEX_FEES.get(min_dex, {}).get("taker", 0.0005) / 100
    fee_max_dex = DEX_FEES.get(max_dex, {}).get("taker", 0.0005) / 100
    
    # Номинальный объём позиции с учётом плеча
    nominal_size = position_size_usd * leverage
    
    # Грязная прибыль (разница цен)
    price_diff = max_price - min_price
    gross_profit = (price_diff / min_price) * nominal_size
    
    # Комиссии на вход
    fee_entry_long = nominal_size * fee_min_dex
    fee_entry_short = nominal_size * fee_max_dex
    
    # Комиссии на выход (примерно такие же, упрощённо)
    fee_exit_long = nominal_size * fee_min_dex
    fee_exit_short = nominal_size * fee_max_dex
    
    total_fees = fee_entry_long + fee_entry_short + fee_exit_long + fee_exit_short
    
    # Чистая прибыль
    net_profit = gross_profit - total_fees
    
    return net_profit


# ---------- Фоновая задача для проверки спредов ----------


async def check_spreads_task():
    """
    Фоновая задача, которая периодически проверяет спреды для всех пользователей.
    """
    while True:
        try:
            # Проходим по всем пользователям
            for user_id, settings in user_settings.items():
                if settings.paused:
                    continue
                
                if not settings.coins:
                    continue
                
                # Используем источники пользователя, или дефолтные, если не заданы
                sources = settings.sources if settings.sources else AVAILABLE_SOURCES
                
                if not sources:
                    continue
                
                # Проверяем каждую монету
                for coin in settings.coins:
                    try:
                        # Получаем цены
                        prices = await get_prices_for_coin(coin, sources)
                        
                        if len(prices) < 2:
                            continue
                        
                        # Рассчитываем спред
                        spread_percent, min_dex, max_dex = calculate_spread(prices)
                        
                        # Проверяем условие по спреду
                        if spread_percent < settings.min_spread:
                            continue
                        
                        # Рассчитываем профит
                        min_price = prices[min_dex]
                        max_price = prices[max_dex]
                        profit_usd = calculate_profit(
                            min_price,
                            max_price,
                            settings.position_size_usd,
                            settings.leverage,
                            min_dex,
                            max_dex,
                        )
                        
                        # Проверяем условие по профиту
                        if profit_usd < settings.min_profit_usd:
                            continue
                        
                        # Проверяем анти-спам (не чаще раза в N минут)
                        last_notif = last_notifications.get(user_id, {}).get(coin)
                        if last_notif:
                            time_since_last = datetime.now() - last_notif
                            if time_since_last < timedelta(minutes=MIN_NOTIFICATION_INTERVAL_MINUTES):
                                continue
                        
                        # Отправляем уведомление
                        await send_spread_notification(
                            user_id,
                            coin,
                            prices,
                            spread_percent,
                            profit_usd,
                            min_dex,
                            max_dex,
                            min_price,
                            max_price,
                        )
                        
                        # Обновляем время последнего уведомления
                        if user_id not in last_notifications:
                            last_notifications[user_id] = {}
                        last_notifications[user_id][coin] = datetime.now()
                        
                    except Exception as e:
                        print(f"Ошибка при проверке монеты {coin} для пользователя {user_id}: {e}")
                        continue
            
            # Ждём минимальный интервал перед следующей проверкой
            await asyncio.sleep(10)  # Минимум 10 секунд между проверками
            
        except Exception as e:
            print(f"Ошибка в фоновой задаче проверки спредов: {e}")
            await asyncio.sleep(60)  # При ошибке ждём минуту


async def send_spread_notification(
    user_id: int,
    coin: str,
    prices: dict[str, float],
    spread_percent: float,
    profit_usd: float,
    min_dex: str,
    max_dex: str,
    min_price: float,
    max_price: float,
):
    """
    Отправляет уведомление пользователю о найденном спреде.
    """
    time_str = datetime.now().strftime("%H:%M:%S UTC")
    
    # Формируем список всех цен
    prices_text = "\n".join([f"  • {dex}: {price:.2f} USDT" for dex, price in prices.items()])
    
    text = (
        f"🔔 Найден арбитраж!\n\n"
        f"Монета: {coin}/USDT\n"
        f"Спред: {spread_percent:.2f}%\n\n"
        f"Цены на DEX:\n{prices_text}\n\n"
        f"Лучшая цена для лонга: {min_dex} — {min_price:.2f} USDT\n"
        f"Лучшая цена для шорта: {max_dex} — {max_price:.2f} USDT\n\n"
        f"Ожидаемый профит: {profit_usd:.2f} $\n"
        f"Время: {time_str}"
    )
    
    try:
        await bot.send_message(chat_id=user_id, text=text)
    except Exception as e:
        print(f"Ошибка отправки уведомления пользователю {user_id}: {e}")


# ---------- Команды ----------


@dp.message(CommandStart())
async def cmd_start(message: Message):
    """
    Обработчик команды /start и Menu Button
    """
    s = get_user_settings(message.from_user.id)
    text = (
        "Привет! 👋\n\n"
        "Я бот для отслеживания арбитражных возможностей на perp‑DEX.\n"
        "Я автоматически проверяю спреды и отправляю уведомления, когда нахожу подходящие возможности.\n\n"
        "Выбери действие из меню ниже:"
    )
    await message.answer(text, reply_markup=get_main_menu_keyboard())


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
    await message.answer(text, reply_markup=get_main_menu_keyboard())


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


# ---------- Обработчики callback-кнопок (inline) ----------


@dp.callback_query(F.data == CALLBACK_MAIN_MENU)
async def handle_main_menu(callback: CallbackQuery):
    """Главное меню"""
    text = (
        "Главное меню\n\n"
        "Выбери раздел:"
    )
    await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard())
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_SETTINGS)
async def handle_settings(callback: CallbackQuery):
    """Меню настроек"""
    text = (
        "⚙️ Настройки\n\n"
        "Выбери параметр для изменения:"
    )
    await callback.message.edit_text(text, reply_markup=get_settings_keyboard())
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_COINS)
async def handle_coins(callback: CallbackQuery):
    """Меню управления монетами"""
    s = get_user_settings(callback.from_user.id)
    coins_text = ', '.join(s.coins) if s.coins else "пока не заданы"
    text = (
        f"🪙 Управление монетами\n\n"
        f"Текущие монеты: {coins_text}\n\n"
        f"Выбери действие:"
    )
    await callback.message.edit_text(text, reply_markup=get_coins_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "show_settings")
async def handle_show_settings(callback: CallbackQuery):
    """Показать текущие настройки"""
    s = get_user_settings(callback.from_user.id)
    text = (
        "📊 Текущие настройки:\n\n"
        f"- Монеты/пары: {', '.join(s.coins) if s.coins else 'пока не заданы'}\n"
        f"- Минимальный спред: {s.min_spread}%\n"
        f"- Минимальный профит: {s.min_profit_usd}$\n"
        f"- Источники: {', '.join(s.sources) if s.sources else 'все доступные'}\n"
        f"- Объём позиции: {s.position_size_usd}$\n"
        f"- Плечо: x{s.leverage}\n"
        f"- Интервал проверки: {s.interval_seconds} сек.\n"
        f"- Пауза уведомлений: {'Да' if s.paused else 'Нет'}"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_MAIN_MENU)],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_POSITION)
async def handle_position(callback: CallbackQuery):
    """Настройка объёма и плеча"""
    s = get_user_settings(callback.from_user.id)
    s.pending_action = "position"
    text = (
        "💰 Объём и плечо\n\n"
        f"Текущие значения:\n"
        f"- Объём: {s.position_size_usd}$\n"
        f"- Плечо: x{s.leverage}\n\n"
        "Введи объём и плечо через пробел.\n"
        "Пример: 1000 3  (это объём 1000$ и плечо x3)"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_SETTINGS)],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_MIN_SPREAD)
async def handle_min_spread(callback: CallbackQuery):
    """Настройка минимального спреда"""
    s = get_user_settings(callback.from_user.id)
    s.pending_action = "min_spread"
    text = (
        "📈 Минимальный спред\n\n"
        f"Текущее значение: {s.min_spread}%\n\n"
        "Введи минимальный спред в процентах.\n"
        "Пример: 2.5"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_SETTINGS)],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_MIN_PROFIT)
async def handle_min_profit(callback: CallbackQuery):
    """Настройка минимального профита"""
    s = get_user_settings(callback.from_user.id)
    s.pending_action = "min_profit"
    text = (
        "💵 Минимальный профит\n\n"
        f"Текущее значение: {s.min_profit_usd}$\n\n"
        "Введи минимальный профит в долларах.\n"
        "Пример: 20"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_SETTINGS)],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_INTERVAL)
async def handle_interval(callback: CallbackQuery):
    """Настройка интервала проверки"""
    s = get_user_settings(callback.from_user.id)
    s.pending_action = "interval"
    text = (
        "⏱ Интервал проверки\n\n"
        f"Текущее значение: {s.interval_seconds} сек.\n\n"
        "Введи интервал проверки в секундах.\n"
        "Пример: 60"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_SETTINGS)],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_COINS_ADD)
async def handle_coins_add(callback: CallbackQuery):
    """Добавление монеты"""
    s = get_user_settings(callback.from_user.id)
    s.pending_action = "add_coin"
    text = (
        "➕ Добавить монету\n\n"
        "Введи тикер монеты (например: BTC, ETH, SOL).\n"
        "Можно ввести несколько через пробел: BTC ETH SOL"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_COINS)],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_COINS_REMOVE)
async def handle_coins_remove(callback: CallbackQuery):
    """Удаление монеты"""
    s = get_user_settings(callback.from_user.id)
    if not s.coins:
        text = "Список монет пуст. Нечего удалять."
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_COINS)],
            ]
        )
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
        return

    s.pending_action = "remove_coin"
    coins_text = ', '.join(s.coins)
    text = (
        "➖ Удалить монету\n\n"
        f"Текущие монеты: {coins_text}\n\n"
        "Введи тикер монеты, которую хочешь удалить (например: BTC)"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_COINS)],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_COINS_LIST)
async def handle_coins_list(callback: CallbackQuery):
    """Список монет"""
    s = get_user_settings(callback.from_user.id)
    if not s.coins:
        text = "Список монет пуст. Добавь монеты через меню."
    else:
        text = f"📋 Отслеживаемые монеты ({len(s.coins)}):\n" + "\n".join(f"- {coin}" for coin in s.coins)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_COINS)],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_BACK)
async def handle_back(callback: CallbackQuery):
    """Обработка кнопки Назад (универсальная)"""
    await handle_main_menu(callback)


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
        await message.answer(
            "Я тебя не понял. Используй /start или кнопку меню справа от поля ввода.",
            reply_markup=get_main_menu_keyboard()
        )
        return

    action = s.pending_action

    if action == "add_coin":
        await handle_add_coin_input(message, s, message.text)
    elif action == "remove_coin":
        await handle_remove_coin_input(message, s, message.text)
    elif action == "min_spread":
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
        await message.answer("Неизвестное действие. Попробуй ещё раз через /start.")
        s.pending_action = None
        return

    if s.pending_action is None:
        return
    s.pending_action = None
    await message.answer("Готово! Используй /start для возврата в меню.", reply_markup=get_main_menu_keyboard())


# ---------- Обработка ввода монет ----------


async def handle_add_coin_input(message: Message, s: UserSettings, raw_input: str):
    """Обрабатываем ввод монет (может быть одна или несколько через пробел)"""
    tickers = [t.strip().upper() for t in raw_input.split()]
    
    if not tickers:
        await message.answer("Не получилось прочитать тикеры. Пример: BTC или BTC ETH SOL")
        s.pending_action = "add_coin"
        return

    added = []
    already_exists = []

    for ticker in tickers:
        if not ticker:
            continue
        if ticker in s.coins:
            already_exists.append(ticker)
        else:
            s.coins.append(ticker)
            added.append(ticker)

    response_parts = []
    if added:
        response_parts.append(f"Добавлены монеты: {', '.join(added)}")
    if already_exists:
        response_parts.append(f"Уже есть в списке: {', '.join(already_exists)}")

    s.pending_action = None
    await message.answer("\n".join(response_parts) + f"\n\nВсего монет: {len(s.coins)}", reply_markup=get_main_menu_keyboard())


async def handle_remove_coin_input(message: Message, s: UserSettings, raw_input: str):
    """Обрабатываем удаление монеты"""
    ticker = raw_input.strip().upper()

    if not ticker:
        await message.answer("Не получилось прочитать тикер. Пример: BTC")
        s.pending_action = "remove_coin"
        return

    if ticker not in s.coins:
        await message.answer(f"Монеты {ticker} нет в списке.")
        s.pending_action = None
        return

    s.coins.remove(ticker)
    s.pending_action = None
    await message.answer(f"Монета {ticker} удалена. Осталось монет: {len(s.coins)}", reply_markup=get_main_menu_keyboard())


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
    await message.answer(f"Минимальный спред установлен: {s.min_spread}%.", reply_markup=get_main_menu_keyboard())


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
    await message.answer(f"Минимальный профит установлен: {s.min_profit_usd}$.", reply_markup=get_main_menu_keyboard())


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
        f"- Плечо: x{s.leverage}",
        reply_markup=get_main_menu_keyboard()
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
    await message.answer(f"Интервал проверки установлен: {s.interval_seconds} сек.", reply_markup=get_main_menu_keyboard())


# ---------- Настройка Menu Button ----------


async def setup_menu_button():
    """
    Настраивает Menu Button (виджет справа от поля ввода)
    """
    try:
        # Устанавливаем команды бота
        commands = [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="help", description="Помощь"),
            BotCommand(command="pause", description="Пауза уведомлений"),
            BotCommand(command="resume", description="Возобновить уведомления"),
        ]
        await bot.set_my_commands(commands)
        
        # Устанавливаем Menu Button
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        print("Menu Button настроен успешно")
    except Exception as e:
        print(f"Ошибка настройки Menu Button: {e}")


# ---------- Точка входа ----------


async def main():
    print("Бот запускается...")
    
    # Настраиваем Menu Button
    await setup_menu_button()
    
    # Запускаем фоновую задачу проверки спредов
    asyncio.create_task(check_spreads_task())
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
