import asyncio
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

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


# ---------- Кнопки меню настроек ----------

BTN_POSITION = "Объём и плечо"
BTN_MIN_SPREAD = "Минимальный спред"
BTN_MIN_PROFIT = "Минимальный профит"
BTN_INTERVAL = "Интервал проверки"
BTN_COINS = "Монеты"
BTN_CANCEL = "Отмена"

settings_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_COINS)],
        [KeyboardButton(text=BTN_POSITION)],
        [KeyboardButton(text=BTN_MIN_SPREAD)],
        [KeyboardButton(text=BTN_MIN_PROFIT)],
        [KeyboardButton(text=BTN_INTERVAL)],
        [KeyboardButton(text=BTN_CANCEL)],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)

coins_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Добавить монету")],
        [KeyboardButton(text="Удалить монету")],
        [KeyboardButton(text="Список монет")],
        [KeyboardButton(text=BTN_CANCEL)],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)


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
    
    Логика арбитража:
    - Лонг на DEX с минимальной ценой (покупаем дешевле)
    - Шорт на DEX с максимальной ценой (продаём дороже)
    
    Комиссии учитываются:
    - На вход: мейкер/тейкер (берём тейкер как худший сценарий)
    - На выход: мейкер/тейкер (берём тейкер)
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
    s = get_user_settings(message.from_user.id)
    text = (
        "Привет! 👋\n\n"
        "Я бот для отслеживания арбитражных возможностей на perp‑DEX.\n"
        "Я автоматически проверяю спреды и отправляю уведомления, когда нахожу подходящие возможности.\n\n"
        "Основные команды:\n"
        "/help — список команд\n"
        "/settings — меню настроек с кнопками\n"
        "/coins — управление монетами\n"
        "/pause и /resume — пауза уведомлений\n\n"
        "Попробуй: нажми /settings и настрой параметры, затем добавь монеты через /coins."
    )
    await message.answer(text)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "Доступные команды:\n"
        "/start - приветственное сообщение\n"
        "/help - эта помощь\n"
        "/settings - меню настроек с кнопками\n"
        "/coins - управление монетами\n"
        "/pause - поставить уведомления на паузу\n"
        "/resume - возобновить уведомления\n\n"
        "Через команды (альтернатива кнопкам):\n"
        "/coins add <тикер> - добавить монету (пример: /coins add BTC)\n"
        "/coins remove <тикер> - удалить монету (пример: /coins remove BTC)\n"
        "/coins list - показать список монет\n"
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
        f"- Источники: {', '.join(s.sources) if s.sources else 'все доступные'}\n"
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


# ---------- Команды для монет ----------


@dp.message(Command("coins"))
async def cmd_coins(message: Message):
    """
    /coins [add|remove|list] [тикер]
    """
    s = get_user_settings(message.from_user.id)
    parts = message.text.split()

    if len(parts) == 1:
        await show_coins_menu(message, s)
        return

    if len(parts) == 2:
        if parts[1].lower() == "list":
            await show_coins_list(message, s)
            return
        else:
            await message.answer(
                "Использование:\n"
                "/coins - меню монет\n"
                "/coins add <тикер> - добавить монету\n"
                "/coins remove <тикер> - удалить монету\n"
                "/coins list - список монет"
            )
            return

    if len(parts) == 3:
        action = parts[1].lower()
        ticker = parts[2].upper()

        if action == "add":
            await add_coin(message, s, ticker)
        elif action == "remove":
            await remove_coin(message, s, ticker)
        else:
            await message.answer("Неизвестная команда. Используй: add, remove или list")
        return


async def show_coins_menu(message: Message, s: UserSettings):
    """Показываем меню управления монетами"""
    coins_text = ', '.join(s.coins) if s.coins else "пока не заданы"
    text = (
        f"Текущие монеты: {coins_text}\n\n"
        "Выбери действие:"
    )
    await message.answer(text, reply_markup=coins_keyboard)


async def show_coins_list(message: Message, s: UserSettings):
    """Показываем список монет"""
    if not s.coins:
        await message.answer("Список монет пуст. Добавь монеты через /coins add <тикер> или через меню.")
        return

    text = f"Отслеживаемые монеты ({len(s.coins)}):\n" + "\n".join(f"- {coin}" for coin in s.coins)
    await message.answer(text)


async def add_coin(message: Message, s: UserSettings, ticker: str):
    """Добавляем монету в список"""
    if ticker in s.coins:
        await message.answer(f"Монета {ticker} уже есть в списке.")
        return

    s.coins.append(ticker)
    await message.answer(f"Монета {ticker} добавлена. Всего монет: {len(s.coins)}")


async def remove_coin(message: Message, s: UserSettings, ticker: str):
    """Удаляем монету из списка"""
    if ticker not in s.coins:
        await message.answer(f"Монеты {ticker} нет в списке.")
        return

    s.coins.remove(ticker)
    await message.answer(f"Монета {ticker} удалена. Осталось монет: {len(s.coins)}")


# ---------- Обработка нажатий на кнопки меню ----------


@dp.message(Text(BTN_CANCEL))
async def handle_cancel(message: Message):
    s = get_user_settings(message.from_user.id)
    s.pending_action = None
    await message.answer("Отменено. Настройки не изменены.", reply_markup=ReplyKeyboardRemove())


@dp.message(Text(BTN_COINS))
async def handle_btn_coins(message: Message):
    s = get_user_settings(message.from_user.id)
    await show_coins_menu(message, s)


@dp.message(Text("Добавить монету"))
async def handle_add_coin_btn(message: Message):
    s = get_user_settings(message.from_user.id)
    s.pending_action = "add_coin"
    await message.answer(
        "Введи тикер монеты (например: BTC, ETH, SOL).\n"
        "Можно ввести несколько через пробел: BTC ETH SOL",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(Text("Удалить монету"))
async def handle_remove_coin_btn(message: Message):
    s = get_user_settings(message.from_user.id)
    if not s.coins:
        await message.answer("Список монет пуст. Нечего удалять.", reply_markup=ReplyKeyboardRemove())
        return

    s.pending_action = "remove_coin"
    coins_text = ', '.join(s.coins)
    await message.answer(
        f"Текущие монеты: {coins_text}\n\n"
        "Введи тикер монеты, которую хочешь удалить (например: BTC)",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(Text("Список монет"))
async def handle_list_coins_btn(message: Message):
    s = get_user_settings(message.from_user.id)
    await show_coins_list(message, s)


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
        await message.answer("Я тебя не понял. Используй /settings, чтобы открыть меню настроек.")
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
        await message.answer("Неизвестное действие. Попробуй ещё раз через /settings.")
        s.pending_action = None
        return

    if s.pending_action is None:
        return
    s.pending_action = None
    await message.answer("Готово. Можешь открыть /settings, чтобы проверить настройки.")


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
    await message.answer("\n".join(response_parts) + f"\n\nВсего монет: {len(s.coins)}")


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
    await message.answer(f"Монета {ticker} удалена. Осталось монет: {len(s.coins)}")


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
    
    # Запускаем фоновую задачу проверки спредов
    asyncio.create_task(check_spreads_task())
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
