from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from models import get_user_settings
from config import ALL_EXCHANGES, CEX_EXCHANGES, DEX_EXCHANGES, ALL_COINS
from keyboards import (
    get_main_menu_reply_keyboard,
    get_settings_keyboard,
    get_coins_keyboard,
    get_coins_selected_keyboard,
    get_exchanges_keyboard,
    get_exchanges_select_keyboard,
    get_exchanges_all_keyboard,
    get_position_keyboard,
    get_spread_keyboard,
    get_profit_keyboard,
    get_interval_keyboard,
    CALLBACK_MAIN_MENU,
    CALLBACK_SETTINGS,
    CALLBACK_COINS,
    CALLBACK_COINS_ALL,
    CALLBACK_COINS_SELECTED,
    CALLBACK_COINS_ADD,
    CALLBACK_COINS_REMOVE,
    CALLBACK_COINS_LIST,
    CALLBACK_EXCHANGES,
    CALLBACK_EXCHANGES_CEX,
    CALLBACK_EXCHANGES_DEX,
    CALLBACK_EXCHANGES_SELECT,
    CALLBACK_EXCHANGES_ALL,
    CALLBACK_EXCHANGES_TOGGLE,
    CALLBACK_EXCHANGES_ALL_ENABLE,
    CALLBACK_EXCHANGES_ALL_DISABLE,
    CALLBACK_POSITION,
    CALLBACK_POSITION_SIZE_1000,
    CALLBACK_POSITION_SIZE_5000,
    CALLBACK_POSITION_SIZE_10000,
    CALLBACK_MIN_SPREAD,
    CALLBACK_SPREAD_005,
    CALLBACK_SPREAD_01,
    CALLBACK_SPREAD_025,
    CALLBACK_SPREAD_05,
    CALLBACK_MIN_PROFIT,
    CALLBACK_PROFIT_5,
    CALLBACK_PROFIT_10,
    CALLBACK_PROFIT_20,
    CALLBACK_PROFIT_50,
    CALLBACK_PROFIT_100,
    CALLBACK_INTERVAL,
    CALLBACK_INTERVAL_10,
    CALLBACK_INTERVAL_30,
    CALLBACK_INTERVAL_60,
    CALLBACK_INTERVAL_300,
    CALLBACK_INTERVAL_CONSTANT,
    CALLBACK_MANUAL_INPUT,
)


def register_callback_handlers(dp: Dispatcher):
    """Регистрирует обработчики callback-кнопок"""
    
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
    
    
    # ---------- Обработчики монет ----------
    
    
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
    
    
    # ---------- Обработчики бирж ----------
    
    
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
    
    
    # ---------- Обработчики быстрых кнопок для объёма позиции ----------
    
    
    @dp.callback_query(F.data == CALLBACK_POSITION)
    async def handle_position(callback: CallbackQuery):
        s = get_user_settings(callback.from_user.id)
        text = (
            "💰 Объём позиции\n\n"
            f"Текущее значение: {s.position_size_usd}$\n\n"
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
    
    
    # В функции handle_manual_input добавь отладку:

@dp.callback_query(F.data.startswith(f"{CALLBACK_MANUAL_INPUT}_"))
async def handle_manual_input(callback: CallbackQuery):
    s = get_user_settings(callback.from_user.id)
    action_type = callback.data.split("_", 1)[1]
    
    # ВАЖНО: Устанавливаем pending_action ПЕРЕД отправкой сообщения
    s.pending_action = action_type
    print(f"DEBUG handle_manual_input: user_id={callback.from_user.id}, установлен pending_action='{action_type}'")
    
    if action_type == "position":
        text = (
            "💰 Объём позиции (ручной ввод)\n\n"
            "Введи объём позиции в долларах.\n"
            "Пример: 1000 или 1,000 или 1000$"
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
        s.pending_action = None
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_SETTINGS)],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    s.menu_message_id = callback.message.message_id
    await callback.answer()
