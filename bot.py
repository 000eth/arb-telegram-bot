import asyncio
import os
import random
import re
import aiohttp
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

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

# ---------- Конфигурация бирж ----------

CEX_EXCHANGES = {
    "Bybit": {
        "name": "Bybit",
        "type": "CEX",
        "api_base": "https://api.bybit.com",
        "ticker_endpoint": "/v5/market/tickers",
        "maker_fee": 0.01,
        "taker_fee": 0.06,
        "url_template": "https://www.bybit.com/trade/usdt/{symbol}",
    },
    "OKX": {
        "name": "OKX",
        "type": "CEX",
        "api_base": "https://www.okx.com",
        "ticker_endpoint": "/api/v5/market/ticker",
        "maker_fee": 0.02,
        "taker_fee": 0.05,
        "url_template": "https://www.okx.com/trade-spot/{symbol}-usdt",
    },
    "MEXC": {
        "name": "MEXC",
        "type": "CEX",
        "api_base": "https://api.mexc.com",
        "ticker_endpoint": "/api/v3/ticker/price",
        "maker_fee": 0.0,
        "taker_fee": 0.02,
        "url_template": "https://www.mexc.com/exchange/{symbol}_USDT",
    },
    "Gate": {
        "name": "Gate.io",
        "type": "CEX",
        "api_base": "https://api.gateio.ws",
        "ticker_endpoint": "/api/v4/futures/usdt/tickers",
        "maker_fee": 0.015,
        "taker_fee": 0.05,
        "url_template": "https://www.gate.io/trade/{symbol}_USDT",
    },
}

DEX_EXCHANGES = {
    "Hyperliquid": {
        "name": "Hyperliquid",
        "type": "DEX",
        "api_base": "https://api.hyperliquid.xyz",
        "ticker_endpoint": "/info",
        "maker_fee": 0.02,
        "taker_fee": 0.05,
        "url_template": "https://app.hyperliquid.xyz/exchange/{symbol}-USD",
    },
    "Hibachi": {
        "name": "Hibachi",
        "type": "DEX",
        "api_base": "https://api.hibachi.fi",
        "ticker_endpoint": "/v1/ticker",
        "maker_fee": 0.02,
        "taker_fee": 0.05,
        "url_template": "https://app.hibachi.fi/perpetual/{symbol}",
    },
    "Paradigm": {
        "name": "Paradigm",
        "type": "DEX",
        "api_base": "https://api.paradigm.xyz",
        "ticker_endpoint": "/v1/ticker",
        "maker_fee": 0.02,
        "taker_fee": 0.05,
        "url_template": "https://app.paradigm.xyz/{symbol}",
    },
}

ALL_EXCHANGES = {**CEX_EXCHANGES, **DEX_EXCHANGES}

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
    track_all_exchanges: bool = False
    selected_exchanges: list[str] = field(default_factory=list)
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
    separators = r'[\s,;|/\-_.]+'
    parts = re.split(separators, raw_input.strip())
    
    normalized_coins = []
    
    for part in parts:
        if not part:
            continue
        
        part_upper = part.upper()
        currency_suffixes = ['USDT', 'USD', 'USDC', 'BUSD', 'TUSD', 'DAI', 'EUR', 'BTC', 'ETH']
        
        coin_ticker = part_upper
        
        for suffix in currency_suffixes:
            if part_upper.endswith(suffix) and len(part_upper) > len(suffix):
                coin_ticker = part_upper[:-len(suffix)]
                break
            elif part_upper.startswith(suffix) and len(part_upper) > len(suffix):
                coin_ticker = part_upper[len(suffix):]
                break
        
        if not coin_ticker:
            coin_ticker = part_upper
        
        coin_ticker = re.sub(r'[^A-Z0-9]', '', coin_ticker)
        
        if coin_ticker and coin_ticker not in normalized_coins:
            normalized_coins.append(coin_ticker)
    
    return normalized_coins


POPULAR_COINS = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT", "MATIC", "AVAX",
    "LINK", "UNI", "ATOM", "ETC", "LTC", "BCH", "XLM", "ALGO", "VET", "FIL",
    "TRX", "EOS", "AAVE", "MKR", "COMP", "SNX", "YFI", "SUSHI", "CRV", "1INCH"
]

ALL_COINS = POPULAR_COINS + [
    "ARB", "OP", "APT", "SUI", "TIA", "SEI", "INJ", "NEAR", "FTM", "AVAX",
    "ICP", "HBAR", "QNT", "EGLD", "FLOW", "THETA", "AXS", "SAND", "MANA", "ENJ"
]

MIN_NOTIFICATION_INTERVAL_MINUTES = 1


# ---------- API функции для получения цен ----------


async def get_price_bybit(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    try:
        url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}USDT"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("retCode") == 0 and data.get("result", {}).get("list"):
                    return float(data["result"]["list"][0]["lastPrice"])
    except Exception as e:
        print(f"Ошибка получения цены с Bybit: {e}")
    return None


async def get_price_okx(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    try:
        url = f"https://www.okx.com/api/v5/market/ticker?instId={symbol}-USDT-SWAP"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("code") == "0" and data.get("data"):
                    return float(data["data"][0]["last"])
    except Exception as e:
        print(f"Ошибка получения цены с OKX: {e}")
    return None


async def get_price_mexc(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    try:
        url = f"https://api.mexc.com/api/v3/ticker/price?symbol={symbol}USDT"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                if "price" in data:
                    return float(data["price"])
    except Exception as e:
        print(f"Ошибка получения цены с MEXC: {e}")
    return None


async def get_price_gate(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    try:
        url = f"https://api.gateio.ws/api/v4/futures/usdt/tickers?contract={symbol}_USDT"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                if data and len(data) > 0:
                    return float(data[0]["last"])
    except Exception as e:
        print(f"Ошибка получения цены с Gate.io: {e}")
    return None


async def get_price_for_exchange(session: aiohttp.ClientSession, exchange_name: str, symbol: str) -> Optional[float]:
    exchange_name_lower = exchange_name.lower()
    
    if exchange_name_lower == "bybit":
        return await get_price_bybit(session, symbol)
    elif exchange_name_lower == "okx":
        return await get_price_okx(session, symbol)
    elif exchange_name_lower == "mexc":
        return await get_price_mexc(session, symbol)
    elif exchange_name_lower == "gate":
        return await get_price_gate(session, symbol)
    else:
        # Для остальных пока возвращаем фейковую цену
        base_prices = {"BTC": 60000, "ETH": 3000, "SOL": 150}
        base = base_prices.get(symbol, 1000)
        return base * (1 + random.uniform(-0.02, 0.02))


# ---------- Расчёт профита с учётом спреда и комиссий ----------


def calculate_profit_with_spread(
    long_price: float,
    short_price: float,
    long_bid: Optional[float],
    long_ask: Optional[float],
    short_bid: Optional[float],
    short_ask: Optional[float],
    position_size_usd: float,
    leverage: float,
    long_exchange: str,
    short_exchange: str,
) -> Dict[str, float]:
    long_exchange_info = ALL_EXCHANGES.get(long_exchange, {})
    short_exchange_info = ALL_EXCHANGES.get(short_exchange, {})
    
    long_maker_fee = long_exchange_info.get("maker_fee", 0.02) / 100
    long_taker_fee = long_exchange_info.get("taker_fee", 0.05) / 100
    short_maker_fee = short_exchange_info.get("maker_fee", 0.02) / 100
    short_taker_fee = short_exchange_info.get("taker_fee", 0.05) / 100
    
    nominal_size = position_size_usd * leverage
    
    # Профит при входе по МАРКЕТУ (тейкер)
    long_entry_market = long_ask if long_ask else long_price
    short_entry_market = short_bid if short_bid else short_price
    
    price_diff_market = short_entry_market - long_entry_market
    gross_profit_market = (price_diff_market / long_entry_market) * nominal_size
    
    fee_long_entry_market = nominal_size * long_taker_fee
    fee_short_entry_market = nominal_size * short_taker_fee
    fee_long_exit_market = nominal_size * long_taker_fee
    fee_short_exit_market = nominal_size * short_taker_fee
    
    total_fees_market = fee_long_entry_market + fee_short_entry_market + fee_long_exit_market + fee_short_exit_market
    net_profit_market = gross_profit_market - total_fees_market
    
    # Профит при входе по ЛИМИТУ (мейкер)
    long_entry_limit = long_bid if long_bid else long_price
    short_entry_limit = short_ask if short_ask else short_price
    
    price_diff_limit = short_entry_limit - long_entry_limit
    gross_profit_limit = (price_diff_limit / long_entry_limit) * nominal_size
    
    fee_long_entry_limit = nominal_size * long_maker_fee
    fee_short_entry_limit = nominal_size * short_maker_fee
    fee_long_exit_limit = nominal_size * long_maker_fee
    fee_short_exit_limit = nominal_size * short_maker_fee
    
    total_fees_limit = fee_long_entry_limit + fee_short_entry_limit + fee_long_exit_limit + fee_short_exit_limit
    net_profit_limit = gross_profit_limit - total_fees_limit
    
    return {
        "market_profit": net_profit_market,
        "market_fees": total_fees_market,
        "limit_profit": net_profit_limit,
        "limit_fees": total_fees_limit,
        "long_entry_market": long_entry_market,
        "short_entry_market": short_entry_market,
        "long_entry_limit": long_entry_limit,
        "short_entry_limit": short_entry_limit,
    }


# ---------- Callback data ----------

CALLBACK_MAIN_MENU = "main_menu"
CALLBACK_SETTINGS = "settings"
CALLBACK_COINS = "coins"
CALLBACK_EXCHANGES = "exchanges"
CALLBACK_POSITION = "position"
CALLBACK_MIN_SPREAD = "min_spread"
CALLBACK_MIN_PROFIT = "min_profit"
CALLBACK_INTERVAL = "interval"
CALLBACK_COINS_ADD = "coins_add"
CALLBACK_COINS_REMOVE = "coins_remove"
CALLBACK_COINS_LIST = "coins_list"
CALLBACK_COINS_ALL = "coins_all"
CALLBACK_COINS_SELECTED = "coins_selected"
CALLBACK_EXCHANGES_CEX = "exchanges_cex"
CALLBACK_EXCHANGES_DEX = "exchanges_dex"
CALLBACK_EXCHANGES_SELECT = "exchanges_select"
CALLBACK_EXCHANGES_ALL = "exchanges_all"
CALLBACK_EXCHANGES_TOGGLE = "exchanges_toggle_"
CALLBACK_EXCHANGES_ALL_ENABLE = "exchanges_all_enable"
CALLBACK_EXCHANGES_ALL_DISABLE = "exchanges_all_disable"
CALLBACK_BACK = "back"
CALLBACK_MANUAL_INPUT = "manual_input"
CALLBACK_SCAN_START = "scan_start"
CALLBACK_SCAN_STOP = "scan_stop"

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
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="⚙️ Настройки"),
                KeyboardButton(text="🪙 Монеты"),
            ],
            [
                KeyboardButton(text="📊 Текущие настройки"),
                KeyboardButton(text="🏦 Биржи"),
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


def get_exchanges_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏢 Только CEX", callback_data=CALLBACK_EXCHANGES_CEX)],
            [InlineKeyboardButton(text="🔷 Только DEX", callback_data=CALLBACK_EXCHANGES_DEX)],
            [InlineKeyboardButton(text="✅ Отслеживать биржи", callback_data=CALLBACK_EXCHANGES_SELECT)],
            [InlineKeyboardButton(text="🌐 Все биржи", callback_data=CALLBACK_EXCHANGES_ALL)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_MAIN_MENU)],
        ]
    )
    return keyboard


def get_exchanges_select_keyboard(selected_exchanges: List[str]) -> InlineKeyboardMarkup:
    keyboard_buttons = []
    cex_buttons = []
    dex_buttons = []
    
    for exchange_name in ALL_EXCHANGES.keys():
        is_selected = exchange_name in selected_exchanges
        button_text = f"{'✅' if is_selected else '⚪'} {exchange_name}"
        callback_data = f"{CALLBACK_EXCHANGES_TOGGLE}{exchange_name}"
        
        if ALL_EXCHANGES[exchange_name]["type"] == "CEX":
            cex_buttons.append(InlineKeyboardButton(text=button_text, callback_data=callback_data))
        else:
            dex_buttons.append(InlineKeyboardButton(text=button_text, callback_data=callback_data))
    
    for i in range(0, len(cex_buttons), 2):
        if i + 1 < len(cex_buttons):
            keyboard_buttons.append([cex_buttons[i], cex_buttons[i + 1]])
        else:
            keyboard_buttons.append([cex_buttons[i]])
    
    for i in range(0, len(dex_buttons), 2):
        if i + 1 < len(dex_buttons):
            keyboard_buttons.append([dex_buttons[i], dex_buttons[i + 1]])
        else:
            keyboard_buttons.append([dex_buttons[i]])
    
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_EXCHANGES)])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


def get_exchanges_all_keyboard(track_all: bool) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Включить" if not track_all else "⚪ Выключить",
                    callback_data=CALLBACK_EXCHANGES_ALL_DISABLE if track_all else CALLBACK_EXCHANGES_ALL_ENABLE
                ),
            ],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_EXCHANGES)],
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


# ---------- Фоновая задача для проверки спредов ----------


async def check_spreads_task():
    async with aiohttp.ClientSession() as session:
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
                    
                    # Определяем список бирж для проверки
                    if settings.track_all_exchanges:
                        exchanges_to_check = list(ALL_EXCHANGES.keys())
                    else:
                        exchanges_to_check = settings.selected_exchanges if settings.selected_exchanges else list(ALL_EXCHANGES.keys())
                    
                    if not exchanges_to_check:
                        continue
                    
                    for coin in coins_to_check:
                        try:
                            # Получаем цены со всех бирж
                            prices = {}
                            for exchange_name in exchanges_to_check:
                                price = await get_price_for_exchange(session, exchange_name, coin)
                                if price:
                                    prices[exchange_name] = price
                            
                            if len(prices) < 2:
                                continue
                            
                            # Находим минимальную и максимальную цену
                            min_exchange = min(prices, key=prices.get)
                            max_exchange = max(prices, key=prices.get)
                            min_price = prices[min_exchange]
                            max_price = prices[max_exchange]
                            
                            if min_price == 0:
                                continue
                            
                            spread_percent = ((max_price - min_price) / min_price) * 100
                            
                            if spread_percent < settings.min_spread:
                                continue
                            
                            # Рассчитываем профит
                            profit_data = calculate_profit_with_spread(
                                min_price,
                                max_price,
                                None,  # bid для лонга (пока None, позже добавим стакан)
                                None,  # ask для лонга
                                None,  # bid для шорта
                                None,  # ask для шорта
                                settings.position_size_usd,
                                settings.leverage,
                                min_exchange,
                                max_exchange,
                            )
                            
                            # Проверяем условие по профиту (берём лучший из маркета или лимита)
                            best_profit = max(profit_data["market_profit"], profit_data["limit_profit"])
                            
                            if best_profit < settings.min_profit_usd:
                                continue
                            
                            # Анти-спам
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
                                profit_data,
                                min_exchange,
                                max_exchange,
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
    profit_data: dict,
    long_exchange: str,
    short_exchange: str,
    settings: UserSettings,
):
    time_str = datetime.now().strftime("%H:%M:%S UTC")
    
    long_exchange_info = ALL_EXCHANGES.get(long_exchange, {})
    short_exchange_info = ALL_EXCHANGES.get(short_exchange, {})
    
    long_url = long_exchange_info.get("url_template", "").format(symbol=coin)
    short_url = short_exchange_info.get("url_template", "").format(symbol=coin)
    
    prices_text = "\n".join([f"  • {dex}: {price:.2f} USDT" for dex, price in prices.items()])
    
    text = (
        f"🔔 Найден арбитраж!\n\n"
        f"Монета: {coin}/USDT\n"
        f"Спред: {spread_percent:.2f}%\n\n"
        f"Цены на биржах:\n{prices_text}\n\n"
        f"📈 ЛОНГ: [{long_exchange}]({long_url}) — {profit_data['long_entry_market']:.2f} USDT\n"
        f"📉 ШОРТ: [{short_exchange}]({short_url}) — {profit_data['short_entry_market']:.2f} USDT\n\n"
        f"💰 Профит при входе по МАРКЕТУ:\n"
        f"  • Профит: {profit_data['market_profit']:.2f} $\n"
        f"  • Комиссии: {profit_data['market_fees']:.2f} $\n\n"
        f"💰 Профит при входе по ЛИМИТУ:\n"
        f"  • Профит: {profit_data['limit_profit']:.2f} $\n"
        f"  • Комиссии: {profit_data['limit_fees']:.2f} $\n\n"
        f"Время: {time_str}"
    )
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="Markdown",
            disable_web_page_preview=False
        )
        
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


@dp.message(F.text == "🏦 Биржи")
async def handle_exchanges_button(message: Message):
    s = get_user_settings(message.from_user.id)
    exchanges_text = "Все биржи" if s.track_all_exchanges else f"Выбрано: {len(s.selected_exchanges)}"
    text = (
        f"🏦 Управление биржами\n\n"
        f"Режим: {exchanges_text}\n\n"
        f"Выбери действие:"
    )
    msg = await message.answer(text, reply_markup=get_exchanges_keyboard())
    s.menu_message_id = msg.message_id


@dp.message(F.text == "📊 Текущие настройки")
async def handle_show_settings_button(message: Message):
    s = get_user_settings(message.from_user.id)
    coins_mode = "Все монеты" if s.track_all_coins else f"Только выбранные ({len(s.coins)} монет)"
    exchanges_mode = "Все биржи" if s.track_all_exchanges else f"Выбрано: {len(s.selected_exchanges)}"
    interval_text = "Постоянно" if s.interval_seconds == 0 else f"{s.interval_seconds} сек."
    text = (
        "📊 Текущие настройки:\n\n"
        f"- Монеты: {coins_mode}\n"
        f"- Биржи: {exchanges_mode}\n"
        f"- Минимальный спред: {s.min_spread}%\n"
        f"- Минимальный профит: {s.min_profit_usd}$\n"
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


# ---------- Обработчики callback-кнопок для бирж ----------


@dp.callback_query(F.data == CALLBACK_EXCHANGES)
async def handle_exchanges(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    exchanges_text = "Все биржи" if s.track_all_exchanges else f"Выбрано: {len(s.selected_exchanges)}"
    text = (
        f"🏦 Управление биржами\n\n"
        f"Режим: {exchanges_text}\n\n"
        f"Выбери действие:"
    )
    await callback.message.edit_text(text, reply_markup=get_exchanges_keyboard())
    s.menu_message_id = callback.message.message_id
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_EXCHANGES_SELECT)
async def handle_exchanges_select(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    text = (
        "✅ Отслеживать биржи\n\n"
        "Выбери биржи для отслеживания (зелёная галочка = выбрано):"
    )
    await callback.message.edit_text(text, reply_markup=get_exchanges_select_keyboard(s.selected_exchanges))
    s.menu_message_id = callback.message.message_id
    await callback.answer()


@dp.callback_query(F.data.startswith(CALLBACK_EXCHANGES_TOGGLE))
async def handle_exchange_toggle(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    exchange_name = callback.data.replace(CALLBACK_EXCHANGES_TOGGLE, "")
    
    if exchange_name in s.selected_exchanges:
        s.selected_exchanges.remove(exchange_name)
        await callback.answer(f"{exchange_name} убрана из списка")
    else:
        s.selected_exchanges.append(exchange_name)
        await callback.answer(f"{exchange_name} добавлена в список")
    
    await handle_exchanges_select(callback)


@dp.callback_query(F.data == CALLBACK_EXCHANGES_ALL)
async def handle_exchanges_all(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    text = (
        "🌐 Все биржи\n\n"
        f"Статус: {'✅ Включено' if s.track_all_exchanges else '⚪ Выключено'}\n\n"
        "Если включено, будут отслеживаться все биржи (имеет приоритет над выбранными)."
    )
    await callback.message.edit_text(text, reply_markup=get_exchanges_all_keyboard(s.track_all_exchanges))
    s.menu_message_id = callback.message.message_id
    await callback.answer()


@dp.callback_query(F.data == CALLBACK_EXCHANGES_ALL_ENABLE)
async def handle_exchanges_all_enable(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.track_all_exchanges = True
    await callback.answer("✅ Все биржи включены")
    await handle_exchanges_all(callback)


@dp.callback_query(F.data == CALLBACK_EXCHANGES_ALL_DISABLE)
async def handle_exchanges_all_disable(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.track_all_exchanges = False
    await callback.answer("⚪ Все биржи выключены")
    await handle_exchanges_all(callback)


@dp.callback_query(F.data == CALLBACK_EXCHANGES_CEX)
async def handle_exchanges_cex(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.selected_exchanges = [name for name in CEX_EXCHANGES.keys()]
    s.track_all_exchanges = False
    await callback.answer("✅ Выбраны только CEX биржи")
    await handle_exchanges_select(callback)


@dp.callback_query(F.data == CALLBACK_EXCHANGES_DEX)
async def handle_exchanges_dex(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    s.selected_exchanges = [name for name in DEX_EXCHANGES.keys()]
    s.track_all_exchanges = False
    await callback.answer("✅ Выбраны только DEX биржи")
    await handle_exchanges_select(callback)


# ---------- Обработчики для монет и настроек (остальные остаются как были) ----------


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


# ---------- Обработчики быстрых кнопок (остальные остаются как были) ----------


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
    normalized_coins = normalize_coin_input(raw_input)
    
    if not normalized_coins:
        await message.answer("Не получилось прочитать тикер. Попробуй ещё раз.")
        s.pending_action = "remove_coin"
        return
    
    ticker = normalized_coins[0]

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
