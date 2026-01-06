import asyncio
import os
import random
import re
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
    ReplyKeyboardMarkup,
    KeyboardButton,
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
    coins: list[str] = field(default_factory=list)
    min_spread: float = 2.0
    min_profit_usd: float = 10.0
    sources: list[str] = field(default_factory=list)
    position_size_usd: float = 100.0
    leverage: float = 1.0
    interval_seconds: int = 60
    paused: bool = False
    scan_active: bool = False
    track_all_coins: bool = False
    pending_action: str | None = None
    menu_message_id: int | None = None


user_settings: dict[int, UserSettings] = {}
last_notifications: dict[int, dict[str, datetime]] = {}


def get_user_settings(user_id: int) -> UserSettings:
    if user_id not in user_settings:
        user_settings[user_id] = UserSettings()
    if user_id not in last_notifications:
        last_notifications[user_id] = {}
    return user_settings[user_id]


# ---------- Функция нормализации монет ----------


def normalize_coin_input(raw_input: str) -> list[str]:
    """
    Нормализует ввод монет:
    - Игнорирует регистр (BTC, btc, Btc -> BTC)
    - Извлекает тикер из пар (BTCUSDT, BTC/USDT, BTC-USDT -> BTC)
    - Поддерживает различные разделители (пробел, запятая, точка, слэш, дефис и т.д.)
    """
    # Разбиваем по различным разделителям
    separators = r'[\s,;|/\-_.]+'
    parts = re.split(separators, raw_input.strip())
    
    normalized_coins = []
    
    for part in parts:
        if not part:
            continue
        
        # Приводим к верхнему регистру
        part_upper = part.upper()
        
        # Убираем USDT, USD и другие валютные суффиксы из конца
        # Обрабатываем форматы: BTCUSDT, BTC/USDT, BTC-USDT и т.д.
        # Сначала пробуем найти тикер в начале строки
        
        # Убираем общие валютные суффиксы
        currency_suffixes = ['USDT', 'USD', 'USDC', 'BUSD', 'TUSD', 'DAI', 'EUR', 'BTC', 'ETH']
        
        coin_ticker = part_upper
        
        # Если строка содержит один из суффиксов, извлекаем тикер до него
        for suffix in currency_suffixes:
            if part_upper.endswith(suffix) and len(part_upper) > len(suffix):
                coin_ticker = part_upper[:-len(suffix)]
                break
            elif part_upper.startswith(suffix) and len(part_upper) > len(suffix):
                # Если начинается с валюты (редкий случай), берём то что после
                coin_ticker = part_upper[len(suffix):]
                break
        
        # Если после обработки осталась пустая строка, используем исходную
        if not coin_ticker:
            coin_ticker = part_upper
        
        # Убираем лишние символы (если остались)
        coin_ticker = re.sub(r'[^A-Z0-9]', '', coin_ticker)
        
        if coin_ticker and coin_ticker not in normalized_coins:
            normalized_coins.append(coin_ticker)
    
    return normalized_coins


# ---------- Конфигурация ----------

DEX_FEES = {
    "Nado": {"maker": 0.02, "taker": 0.05},
    "Ethereal": {"maker": 0.02, "taker": 0.05},
    "Pacifica": {"maker": 0.02, "taker": 0.05},
    "Extended": {"maker": 0.02, "taker": 0.05},
    "Variational": {"maker": 0.02, "taker": 0.05},
}

AVAILABLE_SOURCES = list(DEX_FEES.keys())
MIN_NOTIFICATION_INTERVAL_MINUTES = 1

POPULAR_COINS = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT", "MATIC", "AVAX",
    "LINK", "UNI", "ATOM", "ETC", "LTC", "BCH", "XLM", "ALGO", "VET", "FIL",
    "TRX", "EOS", "AAVE", "MKR", "COMP", "SNX", "YFI", "SUSHI", "CRV", "1INCH"
]

ALL_COINS = POPULAR_COINS + [
    "ARB", "OP", "APT", "SUI", "TIA", "SEI", "INJ", "NEAR", "FTM", "AVAX",
    "ICP", "HBAR", "QNT", "EGLD", "FLOW", "THETA", "AXS", "SAND", "MANA", "ENJ"
]


# ---------- Callback data ----------

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
CALLBACK_COINS_ALL = "coins_all"
CALLBACK_COINS_SELECTED = "coins_selected"
CALLBACK_BACK = "back"
CALLBACK_MANUAL_INPUT = "manual_input"
CALLBACK_SCAN_START = "scan_start"
CALLBACK_SCAN_STOP = "scan_stop"

# Быстрые значения
CALLBACK_POSITION_SIZE_1000 = "pos_size_1000"
CALLBACK_POSITION_SIZE_5000 = "pos_size_5000"
CALLBACK_POSITION_SIZE_10000 = "pos_size_10000"
CALLBACK_LEVERAGE_1 = "lev_1"
CALLBACK_LEVERAGE_5 = "lev_5"
CALLBACK_LEVERAGE_10 = "lev_10"

CALLBACK_SPREAD_005 = "spread_0.05"
CALLBACK_SPREAD_01 = "spread_0.1"
CALLBACK_SPREAD_025 = "spread_0.25"
CALLBACK_SPREAD_05 = "spread_0.5"

CALLBACK_PROFIT_5 = "profit_5"
CALLBACK_PROFIT_10 = "profit_10"
CALLBACK_PROFIT_20 = "profit_20"
CALLBACK_PROFIT_50 = "profit_50"
CALLBACK_PROFIT_100 = "profit_100"

CALLBACK_INTERVAL_10 = "interval_10"
CALLBACK_INTERVAL_30 = "interval_30"
CALLBACK_INTERVAL_60 = "interval_60"
CALLBACK_INTERVAL_300 = "interval_300"
CALLBACK_INTERVAL_CONSTANT = "interval_constant"


# ---------- Функции для создания клавиатур ----------


def get_main_menu_reply_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню - ReplyKeyboardMarkup (кнопки всегда видны над полем ввода)"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="⚙️ Настройки"),
                KeyboardButton(text="🪙 Монеты"),
            ],
            [
                KeyboardButton(text="📊 Текущие настройки"),
            ],
            [
                KeyboardButton(text="▶️ Активировать скан"),
                KeyboardButton(text="⏹ Остановить скан"),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )
    return keyboard


def get_settings_keyboard() -> InlineKeyboardMarkup:
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


def get_position_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1000$", callback_data=CALLBACK_POSITION_SIZE_1000),
                InlineKeyboardButton(text="5000$", callback_data=CALLBACK_POSITION_SIZE_5000),
                InlineKeyboardButton(text="10000$", callback_data=CALLBACK_POSITION_SIZE_10000),
            ],
            [
                InlineKeyboardButton(text="1x", callback_data=CALLBACK_LEVERAGE_1),
                InlineKeyboardButton(text="5x", callback_data=CALLBACK_LEVERAGE_5),
                InlineKeyboardButton(text="10x", callback_data=CALLBACK_LEVERAGE_10),
            ],
            [InlineKeyboardButton(text="✏️ Ввести вручную", callback_data=f"{CALLBACK_MANUAL_INPUT}_position")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_SETTINGS)],
        ]
    )
    return keyboard


def get_spread_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="0.05%", callback_data=CALLBACK_SPREAD_005),
                InlineKeyboardButton(text="0.1%", callback_data=CALLBACK_SPREAD_01),
            ],
            [
                InlineKeyboardButton(text="0.25%", callback_data=CALLBACK_SPREAD_025),
                InlineKeyboardButton(text="0.5%", callback_data=CALLBACK_SPREAD_05),
            ],
            [InlineKeyboardButton(text="✏️ Ввести вручную", callback_data=f"{CALLBACK_MANUAL_INPUT}_spread")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_SETTINGS)],
        ]
    )
    return keyboard


def get_profit_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="5$", callback_data=CALLBACK_PROFIT_5),
                InlineKeyboardButton(text="10$", callback_data=CALLBACK_PROFIT_10),
                InlineKeyboardButton(text="20$", callback_data=CALLBACK_PROFIT_20),
            ],
            [
                InlineKeyboardButton(text="50$", callback_data=CALLBACK_PROFIT_50),
                InlineKeyboardButton(text="100$", callback_data=CALLBACK_PROFIT_100),
            ],
            [InlineKeyboardButton(text="✏️ Ввести вручную", callback_data=f"{CALLBACK_MANUAL_INPUT}_profit")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_SETTINGS)],
        ]
    )
    return keyboard


def get_interval_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="10 сек", callback_data=CALLBACK_INTERVAL_10),
                InlineKeyboardButton(text="30 сек", callback_data=CALLBACK_INTERVAL_30),
            ],
            [
                InlineKeyboardButton(text="1 мин", callback_data=CALLBACK_INTERVAL_60),
                InlineKeyboardButton(text="5 мин", callback_data=CALLBACK_INTERVAL_300),
            ],
            [InlineKeyboardButton(text="⚡ Постоянно", callback_data=CALLBACK_INTERVAL_CONSTANT)],
            [InlineKeyboardButton(text="✏️ Ввести вручную", callback_data=f"{CALLBACK_MANUAL_INPUT}_interval")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_SETTINGS)],
        ]
    )
    return keyboard


def get_coins_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Все монеты", callback_data=CALLBACK_COINS_ALL)],
            [InlineKeyboardButton(text="✅ Только выбранные", callback_data=CALLBACK_COINS_SELECTED)],
            [InlineKeyboardButton(text="📋 Список монет", callback_data=CALLBACK_COINS_LIST)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_MAIN_MENU)],
        ]
    )
    return keyboard


def get_coins_selected_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить монету", callback_data=CALLBACK_COINS_ADD)],
            [InlineKeyboardButton(text="➖ Удалить монету", callback_data=CALLBACK_COINS_REMOVE)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_COINS)],
        ]
    )
    return keyboard


# ---------- Функции для работы с ценами ----------


async def get_fake_price(dex_name: str, coin: str) -> float:
    base_prices = {
        "BTC": 60000,
        "ETH": 3000,
        "SOL": 150,
    }
    
    base = base_prices.get(coin, 1000)
    variation = random.uniform(-0.02, 0.02)
    return base * (1 + variation)


async def get_prices_for_coin(coin: str, sources: list[str]) -> dict[str, float]:
    prices = {}
    for source in sources:
        if source in AVAILABLE_SOURCES:
            price = await get_fake_price(source, coin)
            prices[source] = price
    return prices


def calculate_spread(prices: dict[str, float]) -> tuple[float, str, str]:
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
    fee_min_dex = DEX_FEES.get(min_dex, {}).get("taker", 0.0005) / 100
    fee_max_dex = DEX_FEES.get(max_dex, {}).get("taker", 0.0005) / 100
    
    nominal_size = position_size_usd * leverage
    price_diff = max_price - min_price
    gross_profit = (price_diff / min_price) * nominal_size
    
    fee_entry_long = nominal_size * fee_min_dex
    fee_entry_short = nominal_size * fee_max_dex
    fee_exit_long = nominal_size * fee_min_dex
    fee_exit_short = nominal_size * fee_max_dex
    
    total_fees = fee_entry_long + fee_entry_short + fee_exit_long + fee_exit_short
    net_profit = gross_profit - total_fees
    
    return net_profit


# ---------- Фоновая задача для проверки спредов ----------


async def check_spreads_task():
    while True:
        try:
            for user_id, settings in user_settings.items():
                if not settings.scan_active:
                    continue
                
                if settings.paused:
                    continue
                
                if settings.track_all_coins:
                    coins_to_check = ALL_COINS
                else:
                    coins_to_check = settings.coins
                
                if not coins_to_check:
                    continue
                
                sources = settings.sources if settings.sources else AVAILABLE_SOURCES
                
                if not sources:
                    continue
                
                check_interval = 0 if settings.interval_seconds == 0 else settings.interval_seconds
                
                for coin in coins_to_check:
                    try:
                        prices = await get_prices_for_coin(coin, sources)
                        
                        if len(prices) < 2:
                            continue
                        
                        spread_percent, min_dex, max_dex = calculate_spread(prices)
                        
                        if spread_percent < settings.min_spread:
                            continue
                        
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
                        
                        if profit_usd < settings.min_profit_usd:
                            continue
                        
                        if check_interval > 0:
                            last_notif = last_notifications.get(user_id, {}).get(coin)
                            if last_notif:
                                time_since_last = datetime.now() - last_notif
                                if time_since_last < timedelta(minutes=MIN_NOTIFICATION_INTERVAL_MINUTES):
                                    continue
                        
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
                            settings,
                        )
                        
                        if user_id not in last_notifications:
                            last_notifications[user_id] = {}
                        last_notifications[user_id][coin] = datetime.now()
                        
                    except Exception as e:
                        print(f"Ошибка при проверке монеты {coin} для пользователя {user_id}: {e}")
                        continue
            
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Ошибка в фоновой задаче проверки спредов: {e}")
            await asyncio.sleep(5)


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
    settings: UserSettings,
):
    time_str = datetime.now().strftime("%H:%M:%S UTC")
    
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
        
        if settings.menu_message_id:
            try:
                await bot.edit_message_reply_markup(
                    chat_id=user_id,
                    message_id=settings.menu_message_id,
                    reply_markup=get_settings_keyboard()
                )
            except:
                pass
                
    except Exception as e:
        print(f"Ошибка отправки уведомления пользователю {user_id}: {e}")


# ---------- Команды ----------


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


# Обработчик для первого сообщения (когда пользователь только зашёл в бот)
@dp.message(F.text == "⚙️ Настройки")
async def handle_settings_button(message: Message):
    s = get_user_settings(message.from_user.id)
    text = "⚙️ Настройки\n\nВыбери параметр для изменения:"
    msg = await message.answer(text, reply_markup=get_settings_keyboard())
    s.menu_message_id = msg.message_id


@dp.message(F.text == "🪙 Монеты")
async def handle_coins_button(message: Message):
    s = get_user_settings(message.from_user.id)
    mode_text = "Все монеты" if s.track_all_coins else f"Только выбранные ({len(s.coins)} монет)"
    text = (
        f"🪙 Управление монетами\n\n"
        f"Режим отслеживания: {mode_text}\n\n"
        f"Выбери действие:"
    )
    msg = await message.answer(text, reply_markup=get_coins_keyboard())
    s.menu_message_id = msg.message_id


@dp.message(F.text == "📊 Текущие настройки")
async def handle_show_settings_button(message: Message):
    s = get_user_settings(message.from_user.id)
    coins_mode = "Все монеты" if s.track_all_coins else f"Только выбранные ({len(s.coins)} монет)"
    interval_text = "Постоянно" if s.interval_seconds == 0 else f"{s.interval_seconds} сек."
    text = (
        "📊 Текущие настройки:\n\n"
        f"- Монеты: {coins_mode}\n"
        f"- Минимальный спред: {s.min_spread}%\n"
        f"- Минимальный профит: {s.min_profit_usd}$\n"
        f"- Источники: {', '.join(s.sources) if s.sources else 'все доступные'}\n"
        f"- Объём позиции: {s.position_size_usd}$\n"
        f"- Плечо: x{s.leverage}\n"
        f"- Интервал проверки: {interval_text}\n"
        f"- Скан активен: {'Да' if s.scan_active else 'Нет'}\n"
        f"- Пауза уведомлений: {'Да' if s.paused else 'Нет'}"
    )
    await message.answer(text, reply_markup=get_main_menu_reply_keyboard())


@dp.message(F.text == "▶️ Активировать скан")
async def handle_scan_start_button(message: Message):
    s = get_user_settings(message.from_user.id)
    s.scan_active = True
    await message.answer("✅ Скан активирован! Бот начал отслеживание.", reply_markup=get_main_menu_reply_keyboard())


@dp.message(F.text == "⏹ Остановить скан")
async def handle_scan_stop_button(message: Message):
    s = get_user_settings(message.from_user.id)
    s.scan_active = False
    await message.answer("⏹ Скан остановлен. Уведомления не будут отправляться.", reply_markup=get_main_menu_reply_keyboard())


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


# ---------- Обработчики callback-кнопок ----------


@dp.callback_query(F.data == CALLBACK_MAIN_MENU)
async def handle_main_menu(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    text = "Главное меню\n\nВыбери раздел:"
    await callback.message.edit_text(text, reply_markup=get_settings_keyboard())
    s.menu_message_id = callback.message.message_id
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_SETTINGS)
async def handle_settings(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    text = "⚙️ Настройки\n\nВыбери параметр для изменения:"
    await callback.message.edit_text(text, reply_markup=get_settings_keyboard())
    s.menu_message_id = callback.message.message_id
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_COINS)
async def handle_coins(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    mode_text = "Все монеты" if s.track_all_coins else f"Только выбранные ({len(s.coins)} монет)"
    text = (
        f"🪙 Управление монетами\n\n"
        f"Режим отслеживания: {mode_text}\n\n"
        f"Выбери действие:"
    )
    await callback.message.edit_text(text, reply_markup=get_coins_keyboard())
    s.menu_message_id = callback.message.message_id
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_COINS_ALL)
async def handle_coins_all(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.track_all_coins = True
    await callback.answer("Режим: Все монеты")
    await handle_coins(callback)


@dp.callback_query(F.data == CALLBACK_COINS_SELECTED)
async def handle_coins_selected(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.track_all_coins = False
    text = (
        "✅ Только выбранные монеты\n\n"
        f"Текущие монеты: {', '.join(s.coins) if s.coins else 'пока не заданы'}\n\n"
        "Выбери действие:"
    )
    await callback.message.edit_text(text, reply_markup=get_coins_selected_keyboard())
    s.menu_message_id = callback.message.message_id
    await callback.answer()


@dp.callback_query(F.data == "show_settings")
async def handle_show_settings(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    coins_mode = "Все монеты" if s.track_all_coins else f"Только выбранные ({len(s.coins)} монет)"
    interval_text = "Постоянно" if s.interval_seconds == 0 else f"{s.interval_seconds} сек."
    text = (
        "📊 Текущие настройки:\n\n"
        f"- Монеты: {coins_mode}\n"
        f"- Минимальный спред: {s.min_spread}%\n"
        f"- Минимальный профит: {s.min_profit_usd}$\n"
        f"- Источники: {', '.join(s.sources) if s.sources else 'все доступные'}\n"
        f"- Объём позиции: {s.position_size_usd}$\n"
        f"- Плечо: x{s.leverage}\n"
        f"- Интервал проверки: {interval_text}\n"
        f"- Скан активен: {'Да' if s.scan_active else 'Нет'}\n"
        f"- Пауза уведомлений: {'Да' if s.paused else 'Нет'}"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_MAIN_MENU)],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    s.menu_message_id = callback.message.message_id
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_SCAN_START)
async def handle_scan_start(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.scan_active = True
    await callback.answer("✅ Скан активирован! Бот начал отслеживание.")
    await handle_main_menu(callback)


@dp.callback_query(F.data == CALLBACK_SCAN_STOP)
async def handle_scan_stop(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.scan_active = False
    await callback.answer("⏹ Скан остановлен. Уведомления не будут отправляться.")
    await handle_main_menu(callback)


# ---------- Обработчики быстрых кнопок для объёма и плеча ----------


@dp.callback_query(F.data == CALLBACK_POSITION)
async def handle_position(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    text = (
        "💰 Объём и плечо\n\n"
        f"Текущие значения:\n"
        f"- Объём: {s.position_size_usd}$\n"
        f"- Плечо: x{s.leverage}\n\n"
        "Выбери быстрый вариант или введи вручную:"
    )
    await callback.message.edit_text(text, reply_markup=get_position_keyboard())
    s.menu_message_id = callback.message.message_id
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_POSITION_SIZE_1000)
async def handle_position_size_1000(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.position_size_usd = 1000.0
    await callback.answer(f"Объём установлен: 1000$")
    await handle_position(callback)


@dp.callback_query(F.data == CALLBACK_POSITION_SIZE_5000)
async def handle_position_size_5000(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.position_size_usd = 5000.0
    await callback.answer(f"Объём установлен: 5000$")
    await handle_position(callback)


@dp.callback_query(F.data == CALLBACK_POSITION_SIZE_10000)
async def handle_position_size_10000(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.position_size_usd = 10000.0
    await callback.answer(f"Объём установлен: 10000$")
    await handle_position(callback)


@dp.callback_query(F.data == CALLBACK_LEVERAGE_1)
async def handle_leverage_1(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.leverage = 1.0
    await callback.answer(f"Плечо установлено: 1x")
    await handle_position(callback)


@dp.callback_query(F.data == CALLBACK_LEVERAGE_5)
async def handle_leverage_5(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.leverage = 5.0
    await callback.answer(f"Плечо установлено: 5x")
    await handle_position(callback)


@dp.callback_query(F.data == CALLBACK_LEVERAGE_10)
async def handle_leverage_10(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.leverage = 10.0
    await callback.answer(f"Плечо установлено: 10x")
    await handle_position(callback)


# ---------- Обработчики быстрых кнопок для спреда ----------


@dp.callback_query(F.data == CALLBACK_MIN_SPREAD)
async def handle_min_spread(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    text = (
        "📈 Минимальный спред\n\n"
        f"Текущее значение: {s.min_spread}%\n\n"
        "Выбери быстрый вариант или введи вручную:"
    )
    await callback.message.edit_text(text, reply_markup=get_spread_keyboard())
    s.menu_message_id = callback.message.message_id
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_SPREAD_005)
async def handle_spread_005(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.min_spread = 0.05
    await callback.answer(f"Спред установлен: 0.05%")
    await handle_min_spread(callback)


@dp.callback_query(F.data == CALLBACK_SPREAD_01)
async def handle_spread_01(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.min_spread = 0.1
    await callback.answer(f"Спред установлен: 0.1%")
    await handle_min_spread(callback)


@dp.callback_query(F.data == CALLBACK_SPREAD_025)
async def handle_spread_025(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.min_spread = 0.25
    await callback.answer(f"Спред установлен: 0.25%")
    await handle_min_spread(callback)


@dp.callback_query(F.data == CALLBACK_SPREAD_05)
async def handle_spread_05(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.min_spread = 0.5
    await callback.answer(f"Спред установлен: 0.5%")
    await handle_min_spread(callback)


# ---------- Обработчики быстрых кнопок для профита ----------


@dp.callback_query(F.data == CALLBACK_MIN_PROFIT)
async def handle_min_profit(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    text = (
        "💵 Минимальный профит\n\n"
        f"Текущее значение: {s.min_profit_usd}$\n\n"
        "Выбери быстрый вариант или введи вручную:"
    )
    await callback.message.edit_text(text, reply_markup=get_profit_keyboard())
    s.menu_message_id = callback.message.message_id
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_PROFIT_5)
async def handle_profit_5(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.min_profit_usd = 5.0
    await callback.answer(f"Профит установлен: 5$")
    await handle_min_profit(callback)


@dp.callback_query(F.data == CALLBACK_PROFIT_10)
async def handle_profit_10(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.min_profit_usd = 10.0
    await callback.answer(f"Профит установлен: 10$")
    await handle_min_profit(callback)


@dp.callback_query(F.data == CALLBACK_PROFIT_20)
async def handle_profit_20(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.min_profit_usd = 20.0
    await callback.answer(f"Профит установлен: 20$")
    await handle_min_profit(callback)


@dp.callback_query(F.data == CALLBACK_PROFIT_50)
async def handle_profit_50(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.min_profit_usd = 50.0
    await callback.answer(f"Профит установлен: 50$")
    await handle_min_profit(callback)


@dp.callback_query(F.data == CALLBACK_PROFIT_100)
async def handle_profit_100(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.min_profit_usd = 100.0
    await callback.answer(f"Профит установлен: 100$")
    await handle_min_profit(callback)


# ---------- Обработчики быстрых кнопок для интервала ----------


@dp.callback_query(F.data == CALLBACK_INTERVAL)
async def handle_interval(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    interval_text = "Постоянно" if s.interval_seconds == 0 else f"{s.interval_seconds} сек."
    text = (
        "⏱ Интервал проверки\n\n"
        f"Текущее значение: {interval_text}\n\n"
        "Выбери быстрый вариант или введи вручную:"
    )
    await callback.message.edit_text(text, reply_markup=get_interval_keyboard())
    s.menu_message_id = callback.message.message_id
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_INTERVAL_10)
async def handle_interval_10(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.interval_seconds = 10
    await callback.answer(f"Интервал установлен: 10 сек")
    await handle_interval(callback)


@dp.callback_query(F.data == CALLBACK_INTERVAL_30)
async def handle_interval_30(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.interval_seconds = 30
    await callback.answer(f"Интервал установлен: 30 сек")
    await handle_interval(callback)


@dp.callback_query(F.data == CALLBACK_INTERVAL_60)
async def handle_interval_60(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.interval_seconds = 60
    await callback.answer(f"Интервал установлен: 60 сек")
    await handle_interval(callback)


@dp.callback_query(F.data == CALLBACK_INTERVAL_300)
async def handle_interval_300(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.interval_seconds = 300
    await callback.answer(f"Интервал установлен: 300 сек")
    await handle_interval(callback)


@dp.callback_query(F.data == CALLBACK_INTERVAL_CONSTANT)
async def handle_interval_constant(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.interval_seconds = 0
    await callback.answer("⚡ Режим 'Постоянно' активирован!")
    await handle_interval(callback)


# ---------- Обработчики ручного ввода ----------


@dp.callback_query(F.data.startswith(f"{CALLBACK_MANUAL_INPUT}_"))
async def handle_manual_input(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    action_type = callback.data.split("_", 1)[1]
    
    s.pending_action = action_type
    
    if action_type == "position":
        text = (
            "💰 Объём и плечо (ручной ввод)\n\n"
            "Введи объём и плечо через пробел.\n"
            "Пример: 1000 3  (это объём 1000$ и плечо x3)"
        )
    elif action_type == "spread":
        text = (
            "📈 Минимальный спред (ручной ввод)\n\n"
            "Введи минимальный спред в процентах.\n"
            "Пример: 2.5"
        )
    elif action_type == "profit":
        text = (
            "💵 Минимальный профит (ручной ввод)\n\n"
            "Введи минимальный профит в долларах.\n"
            "Пример: 20"
        )
    elif action_type == "interval":
        text = (
            "⏱ Интервал проверки (ручной ввод)\n\n"
            "Введи интервал проверки в секундах.\n"
            "Пример: 60\n\n"
            "Для режима 'Постоянно' введи 0"
        )
    else:
        text = "Неизвестное действие"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_SETTINGS)],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    s.menu_message_id = callback.message.message_id
    await callback.answer()


# ---------- Обработчики монет ----------


@dp.callback_query(F.data == CALLBACK_COINS_ADD)
async def handle_coins_add(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.pending_action = "add_coin"
    text = (
        "➕ Добавить монету\n\n"
        "Введи тикер монеты (например: BTC, ETH, SOL).\n"
        "Можно ввести несколько через пробел: BTC ETH SOL"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_COINS_SELECTED)],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    s.menu_message_id = callback.message.message_id
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_COINS_REMOVE)
async def handle_coins_remove(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    if not s.coins:
        text = "Список монет пуст. Нечего удалять."
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_COINS_SELECTED)],
            ]
        )
        await callback.message.edit_text(text, reply_markup=keyboard)
        s.menu_message_id = callback.message.message_id
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
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_COINS_SELECTED)],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    s.menu_message_id = callback.message.message_id
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_COINS_LIST)
async def handle_coins_list(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    if s.track_all_coins:
        text = f"🌐 Отслеживаются все монеты ({len(ALL_COINS)} монет)"
    elif not s.coins:
        text = "Список монет пуст. Добавь монеты через меню."
    else:
        text = f"📋 Отслеживаемые монеты ({len(s.coins)}):\n" + "\n".join(f"- {coin}" for coin in s.coins)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_COINS)],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    s.menu_message_id = callback.message.message_id
    await callback.answer()


# ---------- Общий обработчик "следующего ввода" ----------


@dp.message()
async def handle_free_text(message: Message):
    s = get_user_settings(message.from_user.id)

    if not s.pending_action:
        await message.answer(
            "Я тебя не понял. Используй кнопки меню для навигации.",
            reply_markup=get_main_menu_reply_keyboard()
        )
        return

    action = s.pending_action

    if action == "add_coin":
        await handle_add_coin_input(message, s, message.text)
    elif action == "remove_coin":
        await handle_remove_coin_input(message, s, message.text)
    elif action == "spread":
        await apply_min_spread(message, s, message.text)
    elif action == "profit":
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
        await message.answer("Неизвестное действие. Попробуй ещё раз через меню.")
        s.pending_action = None
        return

    if s.pending_action is None:
        return
    s.pending_action = None
    await message.answer("Готово! Используй кнопки меню для дальнейшей настройки.", reply_markup=get_main_menu_reply_keyboard())


# ---------- Обработка ввода монет ----------


async def handle_add_coin_input(message: Message, s: UserSettings, raw_input: str):
    """Обрабатываем ввод монет с нормализацией"""
    # Используем функцию нормализации
    normalized_coins = normalize_coin_input(raw_input)
    
    if not normalized_coins:
        await message.answer("Не получилось прочитать тикеры. Попробуй ещё раз.")
        s.pending_action = "add_coin"
        return

    added = []
    already_exists = []

    for ticker in normalized_coins:
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
    await message.answer("\n".join(response_parts) + f"\n\nВсего монет: {len(s.coins)}", reply_markup=get_main_menu_reply_keyboard())


async def handle_remove_coin_input(message: Message, s: UserSettings, raw_input: str):
    """Обрабатываем удаление монеты с нормализацией"""
    normalized_coins = normalize_coin_input(raw_input)
    
    if not normalized_coins:
        await message.answer("Не получилось прочитать тикер. Попробуй ещё раз.")
        s.pending_action = "remove_coin"
        return
    
    ticker = normalized_coins[0]  # Берём первую монету

    if ticker not in s.coins:
        await message.answer(f"Монеты {ticker} нет в списке.")
        s.pending_action = None
        return

    s.coins.remove(ticker)
    s.pending_action = None
    await message.answer(f"Монета {ticker} удалена. Осталось монет: {len(s.coins)}", reply_markup=get_main_menu_reply_keyboard())


# ---------- Функции применения настроек ----------


async def apply_min_spread(message: Message, s: UserSettings, raw_value: str):
    try:
        value = float(raw_value.replace(",", "."))
    except ValueError:
        await message.answer("Не получилось прочитать число. Пример: 2.5")
        s.pending_action = "spread"
        return

    if value <= 0:
        await message.answer("Значение должно быть больше нуля.")
        s.pending_action = "spread"
        return

    s.min_spread = value
    s.pending_action = None
    await message.answer(f"Минимальный спред установлен: {s.min_spread}%.", reply_markup=get_main_menu_reply_keyboard())


async def apply_min_profit(message: Message, s: UserSettings, raw_value: str):
    try:
        value = float(raw_value.replace(",", "."))
    except ValueError:
        await message.answer("Не получилось прочитать число. Пример: 20")
        s.pending_action = "profit"
        return

    if value <= 0:
        await message.answer("Значение должно быть больше нуля.")
        s.pending_action = "profit"
        return

    s.min_profit_usd = value
    s.pending_action = None
    await message.answer(f"Минимальный профит установлен: {s.min_profit_usd}$.", reply_markup=get_main_menu_reply_keyboard())


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
        reply_markup=get_main_menu_reply_keyboard()
    )


async def apply_interval(message: Message, s: UserSettings, raw_value: str):
    try:
        value = int(raw_value)
    except ValueError:
        await message.answer("Не получилось прочитать целое число секунд. Пример: 60 (или 0 для режима 'Постоянно')")
        s.pending_action = "interval"
        return

    if value < 0:
        await message.answer("Значение не должно быть отрицательным.")
        s.pending_action = "interval"
        return

    s.interval_seconds = value
    interval_text = "Постоянно" if value == 0 else f"{value} сек."
    s.pending_action = None
    await message.answer(f"Интервал проверки установлен: {interval_text}", reply_markup=get_main_menu_reply_keyboard())


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
    
    asyncio.create_task(check_spreads_task())
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
