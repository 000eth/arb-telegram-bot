from aiogram.types import Message
from models import UserSettings
from keyboards import get_main_menu_reply_keyboard
from utils.coin_normalizer import normalize_coin_input
import re


async def apply_min_spread(message: Message, s: UserSettings, raw_value: str):
    try:
        cleaned = re.sub(r'[^\d.,]', '', raw_value)
        cleaned = cleaned.replace(',', '.')
        value = float(cleaned)
    except (ValueError, AttributeError):
        await message.answer("Не получилось прочитать число. Пример: 2.5 или 2,5")
        return

    if value <= 0:
        await message.answer("Значение должно быть больше нуля.")
        return

    s.min_spread = value
    # Сбрасываем pending_action ПОСЛЕ успешной обработки
    s.pending_action = None
    await message.answer(f"✅ Минимальный спред установлен: {s.min_spread}%.", reply_markup=get_main_menu_reply_keyboard())


async def apply_min_profit(message: Message, s: UserSettings, raw_value: str):
    try:
        cleaned = re.sub(r'[^\d.,]', '', raw_value)
        cleaned = cleaned.replace(',', '.')
        value = float(cleaned)
    except (ValueError, AttributeError):
        await message.answer("Не получилось прочитать число. Пример: 20 или 20,5")
        return

    if value <= 0:
        await message.answer("Значение должно быть больше нуля.")
        return

    s.min_profit_usd = value
    s.pending_action = None
    await message.answer(f"✅ Минимальный профит установлен: {s.min_profit_usd}$.", reply_markup=get_main_menu_reply_keyboard())


async def apply_position(message: Message, s: UserSettings, raw_value: str):
    try:
        cleaned = re.sub(r'[^\d.,]', '', raw_value.strip())
        if ',' in cleaned and '.' in cleaned:
            cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            parts = cleaned.split(',')
            if len(parts) == 2 and len(parts[1]) <= 2:
                cleaned = cleaned.replace(',', '.')
            else:
                cleaned = cleaned.replace(',', '')
        
        value = float(cleaned)
        print(f"DEBUG apply_position: raw={raw_value}, cleaned={cleaned}, value={value}")
    except (ValueError, AttributeError) as e:
        print(f"DEBUG apply_position ERROR: {e}, raw_value={raw_value}")
        await message.answer("Не получилось прочитать число. Пример: 1000 или 1,000 или 1000$")
        return

    if value <= 0:
        await message.answer("Объём должен быть больше нуля.")
        return

    s.position_size_usd = value
    s.pending_action = None
    print(f"DEBUG apply_position SUCCESS: установлен объём {s.position_size_usd}$")
    await message.answer(
        f"✅ Объём позиции установлен: {s.position_size_usd}$",
        reply_markup=get_main_menu_reply_keyboard()
    )


async def apply_interval(message: Message, s: UserSettings, raw_value: str):
    try:
        cleaned = re.sub(r'[^\d]', '', raw_value.strip())
        value = int(cleaned)
    except (ValueError, AttributeError):
        await message.answer("Не получилось прочитать целое число секунд. Пример: 60 (или 0 для режима 'Постоянно')")
        return

    if value < 0:
        await message.answer("Значение не должно быть отрицательным.")
        return

    s.interval_seconds = value
    interval_text = "Постоянно" if value == 0 else f"{value} сек."
    s.pending_action = None
    await message.answer(f"✅ Интервал проверки установлен: {interval_text}", reply_markup=get_main_menu_reply_keyboard())


async def handle_add_coin_input(message: Message, s: UserSettings, raw_input: str):
    normalized_coins = normalize_coin_input(raw_input)
    
    if not normalized_coins:
        await message.answer("Не получилось прочитать тикеры. Попробуй ещё раз.\nПример: BTC или BTC ETH SOL")
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
        response_parts.append(f"✅ Добавлены монеты: {', '.join(added)}")
    if already_exists:
        response_parts.append(f"ℹ️ Уже есть в списке: {', '.join(already_exists)}")

    s.pending_action = None
    await message.answer("\n".join(response_parts) + f"\n\nВсего монет: {len(s.coins)}", reply_markup=get_main_menu_reply_keyboard())


async def handle_remove_coin_input(message: Message, s: UserSettings, raw_input: str):
    normalized_coins = normalize_coin_input(raw_input)
    
    if not normalized_coins:
        await message.answer("Не получилось прочитать тикер. Попробуй ещё раз.\nПример: BTC")
        return
    
    ticker = normalized_coins[0]

    if ticker not in s.coins:
        await message.answer(f"❌ Монеты {ticker} нет в списке.")
        s.pending_action = None
        return

    s.coins.remove(ticker)
    s.pending_action = None
    await message.answer(f"✅ Монета {ticker} удалена. Осталось монет: {len(s.coins)}", reply_markup=get_main_menu_reply_keyboard())
