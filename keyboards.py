from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from typing import List
from config import ALL_EXCHANGES, CEX_EXCHANGES, DEX_EXCHANGES

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
