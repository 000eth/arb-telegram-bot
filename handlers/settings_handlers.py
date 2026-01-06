from aiogram.types import Message
from models import UserSettings
from keyboards import get_main_menu_reply_keyboard
from utils.coin_normalizer import normalize_coin_input


async def apply_min_spread(message: Message, s: UserSettings, raw_value: str):
    try:
        value = float(raw_value.replace(",", "."))
    except ValueError:
        await message.answer("Не получилось прочитать число. Пример: 2.5")
        return

    if value <= 0:
        await message.answer("Значение должно быть больше нуля.")
        return

    s.min_spread = value
    s.pending_action = None
    await message.answer(f"✅ Минимальный спред установлен: {s.min_spread}%.", reply_markup=get_main_menu_reply_keyboard())


async def apply_min_profit(message: Message, s: UserSettings, raw_value: str):
    try:
        value = float(raw_value.replace(",", "."))
    except ValueError:
        await message.answer("Не получилось прочитать число. Пример: 20")
        return

    if value <= 0:
        await message.answer("Значение должно быть больше нуля.")
        return

    s.min_profit_usd = value
    s.pending_action = None
    await message.answer(f"✅ Минимальный профит установлен: {s.min_profit_usd}$.", reply_markup=get_main_menu_reply_keyboard())


async def apply_position(message: Message, s: UserSettings, raw_size: str, raw_lev: str):
    try:
        size = float(raw_size.replace(",", "."))
        leverage = float(raw_lev.replace(",", "."))
    except ValueError:
        await message.answer("Не получилось прочитать объём и плечо. Пример: 1000 3")
        return

    if size <= 0 or leverage <= 0:
        await message.answer("Объём и плечо должны быть больше нуля.")
        return

    s.position_size_usd = size
    s.leverage = leverage
    s.pending_action = None
    await message.answer(
        f"✅ Параметры позиции установлены:\n"
        f"- Объём: {s.position_size_usd}$\n"
        f"- Плечо: x{s.leverage}",
        reply_markup=get_main_menu_reply_keyboard()
    )


async def apply_interval(message: Message, s: UserSettings, raw_value: str):
    try:
        value = int(raw_value)
    except ValueError:
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
