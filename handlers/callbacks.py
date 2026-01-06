# ... (все импорты остаются те же, но убираем CALLBACK_LEVERAGE_*)

# В функции register_callback_handlers() замени обработчики:

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
    
    
    # УБРАТЬ все обработчики CALLBACK_LEVERAGE_* (lev_1, lev_5, lev_10)
    
    
    # ... (остальные обработчики остаются без изменений)
    
    
    # В обработчике ручного ввода для position:
    @dp.callback_query(F.data.startswith(f"{CALLBACK_MANUAL_INPUT}_"))
    async def handle_manual_input(callback: CallbackQuery):
        s = get_user_settings(callback.from_user.id)
        action_type = callback.data.split("_", 1)[1]
        
        # ВАЖНО: Устанавливаем pending_action ПЕРЕД отправкой сообщения
        s.pending_action = action_type
        
        if action_type == "position":
            text = (
                "💰 Объём позиции (ручной ввод)\n\n"
                "Введи объём позиции в долларах.\n"
                "Пример: 1000"
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
