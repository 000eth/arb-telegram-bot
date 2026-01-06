async def check_spreads_task(bot_instance):
    """Фоновая задача для проверки спредов"""
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                for user_id, settings in user_settings.items():
                    # ВАЖНО: Проверяем scan_active СРАЗУ, до всех остальных проверок
                    if not settings.scan_active:
                        # Пропускаем этого пользователя полностью
                        continue
                    
                    # ДИАГНОСТИКА: Проверяем настройки пользователя
                    print(f"\n=== Проверка пользователя {user_id} ===")
                    print(f"  scan_active: {settings.scan_active}")
                    print(f"  paused: {settings.paused}")
                    
                    if settings.paused:
                        print(f"  ⚠️ Уведомления на паузе для пользователя {user_id}")
                        continue
                    
                    if settings.track_all_coins:
                        coins_to_check = ALL_COINS
                    else:
                        coins_to_check = settings.coins
                    
                    if not coins_to_check:
                        print(f"  ⚠️ Нет монет для отслеживания для пользователя {user_id}")
                        continue
                    
                    print(f"  ✅ Монет для проверки: {len(coins_to_check)}")
                    
                    if settings.track_all_exchanges:
                        exchanges_to_check = list(ALL_EXCHANGES.keys())
                    else:
                        exchanges_to_check = settings.selected_exchanges if settings.selected_exchanges else list(ALL_EXCHANGES.keys())
                    
                    if not exchanges_to_check or len(exchanges_to_check) < 2:
                        print(f"  ⚠️ Недостаточно бирж для отслеживания: {len(exchanges_to_check)} (нужно минимум 2)")
                        continue
                    
                    print(f"  ✅ Бирж для проверки: {len(exchanges_to_check)} ({', '.join(exchanges_to_check)})")
                    
                    # Проверяем первые несколько монет для диагностики
                    coins_checked = 0
                    max_coins_to_check = min(5, len(coins_to_check))
                    
                    for coin in coins_to_check[:max_coins_to_check]:
                        # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: убеждаемся, что скан всё ещё активен
                        if not settings.scan_active:
                            print(f"  ⚠️ Скан был выключен во время проверки, останавливаем")
                            break
                        
                        coins_checked += 1
                        try:
                            print(f"\n  🔍 Проверка монеты {coin} ({coins_checked}/{max_coins_to_check})...")
                            
                            # Получаем данные с bid/ask
                            prices_data = {}
                            for exchange_name in exchanges_to_check:
                                # ЕЩЁ ОДНА ПРОВЕРКА перед каждым запросом
                                if not settings.scan_active:
                                    print(f"  ⚠️ Скан выключен, прерываем получение цен")
                                    break
                                
                                print(f"    📡 Запрос цены с {exchange_name}...")
                                try:
                                    data = await asyncio.wait_for(
                                        get_price_data_for_exchange(session, exchange_name, coin),
                                        timeout=3.0
                                    )
                                    if data and data.get("price"):
                                        prices_data[exchange_name] = data
                                        print(f"    ✅ {exchange_name}: {data.get('price'):.2f} USDT")
                                    else:
                                        print(f"    ❌ {exchange_name}: не удалось получить цену")
                                except asyncio.TimeoutError:
                                    print(f"    ⚠️ {exchange_name}: timeout, пропускаем")
                                except Exception as e:
                                    print(f"    ⚠️ {exchange_name}: ошибка {type(e).__name__}: {e}, пропускаем")
                                
                                if exchange_name.lower() == "hibachi":
                                    await asyncio.sleep(0.5)
                                else:
                                    await asyncio.sleep(0.1)
                            
                            # ФИНАЛЬНАЯ ПРОВЕРКА перед отправкой уведомления
                            if not settings.scan_active:
                                print(f"  ⚠️ Скан выключен перед отправкой уведомления, пропускаем")
                                continue
                            
                            if len(prices_data) < 2:
                                print(f"    ⚠️ Получено цен только с {len(prices_data)} бирж (нужно минимум 2)")
                                continue
                            
                            # Находим минимальную и максимальную цену
                            min_exchange = min(prices_data, key=lambda x: prices_data[x].get("price", float('inf')))
                            max_exchange = max(prices_data, key=lambda x: prices_data[x].get("price", 0))
                            
                            min_price = prices_data[min_exchange].get("price", 0)
                            max_price = prices_data[max_exchange].get("price", 0)
                            
                            print(f"    💰 Минимум: {min_exchange} = {min_price:.2f} USDT")
                            print(f"    💰 Максимум: {max_exchange} = {max_price:.2f} USDT")
                            
                            if min_price == 0:
                                print(f"    ⚠️ Минимальная цена = 0, пропускаем")
                                continue
                            
                            spread_percent = ((max_price - min_price) / min_price) * 100
                            print(f"    📊 Спред: {spread_percent:.2f}% (требуется: {settings.min_spread}%)")
                            
                            if spread_percent < settings.min_spread:
                                print(f"    ⚠️ Спред {spread_percent:.2f}% меньше минимального {settings.min_spread}%")
                                continue
                            
                            # Рассчитываем профит
                            profit_data = calculate_profit_with_spread(
                                min_exchange,
                                max_exchange,
                                prices_data[min_exchange],
                                prices_data[max_exchange],
                                settings.position_size_usd,
                                settings.leverage,
                            )
                            
                            best_profit = max(profit_data["market_profit"], profit_data["limit_profit"])
                            print(f"    💵 Профит (маркет): {profit_data['market_profit']:.2f}$")
                            print(f"    💵 Профит (лимит): {profit_data['limit_profit']:.2f}$")
                            print(f"    💵 Лучший профит: {best_profit:.2f}$ (требуется: {settings.min_profit_usd}$)")
                            
                            if best_profit < settings.min_profit_usd:
                                print(f"    ⚠️ Профит {best_profit:.2f}$ меньше минимального {settings.min_profit_usd}$")
                                continue
                            
                            last_notif = last_notifications.get(user_id, {}).get(coin)
                            if last_notif:
                                time_since_last = datetime.now() - last_notif
                                if time_since_last < timedelta(minutes=MIN_NOTIFICATION_INTERVAL_MINUTES):
                                    print(f"    ⚠️ Последнее уведомление было {time_since_last.total_seconds():.0f} сек назад (минимум: {MIN_NOTIFICATION_INTERVAL_MINUTES} мин)")
                                    continue
                            
                            # ПОСЛЕДНЯЯ ПРОВЕРКА перед отправкой
                            if not settings.scan_active:
                                print(f"  ⚠️ Скан выключен в последний момент, НЕ отправляем уведомление")
                                continue
                            
                            print(f"    🎉 ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ!")
                            await send_spread_notification(
                                user_id,
                                coin,
                                prices_data,
                                spread_percent,
                                profit_data,
                                min_exchange,
                                max_exchange,
                                settings,
                                bot_instance,
                            )
                            
                            if user_id not in last_notifications:
                                last_notifications[user_id] = {}
                            last_notifications[user_id][coin] = datetime.now()
                            
                        except Exception as e:
                            print(f"    ❌ Ошибка при проверке монеты {coin}: {e}")
                            import traceback
                            traceback.print_exc()
                            continue
                    
                    print(f"\n  ✅ Проверено {coins_checked} монет для пользователя {user_id}")
                
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ Ошибка в фоновой задаче проверки спредов: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(5)
