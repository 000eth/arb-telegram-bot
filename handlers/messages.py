from aiogram import Dispatcher, F
from aiogram.types import Message

from models import get_user_settings
from keyboards import (
    get_main_menu_reply_keyboard,
    get_settings_keyboard,
    get_coins_keyboard,
    get_exchanges_keyboard,
)
from handlers.settings_handlers import (
    apply_min_spread,
    apply_min_profit,
    apply_position,
    apply_interval,
    handle_add_coin_input,
    handle_remove_coin_input,
)


def register_message_handlers(dp: Dispatcher):
    """Регистрирует обработчики текстовых сообщений"""
    
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
    
    
    @dp.message()
    async def handle_free_text(message: Message):
        """Обработчик всех текстовых сообщений"""
        s = get_user_settings(message.from_user.id)

        # Проверяем, есть ли pending_action
        if not s.pending_action:
            await message.answer(
                "Я тебя не понял. Используй кнопки меню для навигации.",
                reply_markup=get_main_menu_reply_keyboard()
            )
            return

        action = s.pending_action

        try:
            if action == "add_coin":
                await handle_add_coin_input(message, s, message.text)
            elif action == "remove_coin":
                await handle_remove_coin_input(message, s, message.text)
            elif action == "spread":
                await apply_min_spread(message, s, message.text)
            elif action == "profit":
                await apply_min_profit(message, s, message.text)
            elif action == "position":
                # Теперь только объём, не нужно два числа
                await apply_position(message, s, message.text)
            elif action == "interval":
                await apply_interval(message, s, message.text)
            else:
                await message.answer("Неизвестное действие. Попробуй ещё раз через меню.")
                s.pending_action = None
                return
        except Exception as e:
            print(f"Ошибка обработки действия {action}: {e}")
            await message.answer(
                f"Произошла ошибка при обработке. Попробуй ещё раз или используй кнопки меню.",
                reply_markup=get_main_menu_reply_keyboard()
            )
            # НЕ сбрасываем pending_action при ошибке, чтобы пользователь мог попробовать ещё раз
            return

        # pending_action сбрасывается внутри функций apply_* при успехе
