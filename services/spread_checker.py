"""
Фоновая задача для проверки спредов
"""
import asyncio
import aiohttp
from datetime import datetime, timedelta

from models import user_settings, last_notifications
from config import ALL_EXCHANGES, ALL_COINS, MIN_NOTIFICATION_INTERVAL_MINUTES
from services.price_fetcher import get_price_data_for_exchange
from services.profit_calculator import calculate_profit_with_spread
from keyboards import get_settings_keyboard


async def send_spread_notification(
    user_id: int,
    coin: str,
    prices: dict[str, dict],
    spread_percent: float,
    profit_data: dict,
    long_exchange: str,
    short_exchange: str,
    settings,
    bot_instance,
):
    """Отправляет уведомление с кликабельными ссылками"""
    time_str = datetime.now().strftime("%H:%M:%S UTC")
    
    long_exchange_info = ALL_EXCHANGES.get(long_exchange, {})
    short_exchange_info = ALL_EXCHANGES.get(short_exchange, {})
    
    long_url = long_exchange_info.get("url_template", "").format(symbol=coin)
    short_url = short_exchange_info.get("url_template", "").format(symbol=coin)
    
    prices_text = "\n".join([
        f"  • {exch}: {data.get('price', 0):.2f} USDT" 
        for exch, data in prices.items()
    ])
    
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
        await bot_instance.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        
        if settings.menu_message_id:
            try:
                await bot_instance.edit_message_reply_markup(
                    chat_id=user_id,
                    message_id=settings.menu_message_id,
                    reply_markup=get_settings_keyboard()
                )
            except:
                pass
                
    except Exception as e:
        print(f"Ошибка отправки уведомления пользователю {user_id}: {e}")


async def check_spreads_task(bot_instance):
    """Фоновая задача для проверки спредов"""
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                for user_id, settings in user_settings.items():
                    # ДИАГНОСТИКА: Проверяем настройки пользователя
                    print(f"\n=== Проверка пользователя {user_id} ===")
                    print(f"  scan_active: {settings.scan_active}")
                    print(f"  paused: {settings.paused}")
                    print(f"  track_all_coins: {settings.track_all_coins}")
                    print(f"  coins: {settings.coins}")
                    print(f"  track_all_exchanges: {settings.track_all_exchanges}")
                    print(f"  selected_exchanges: {settings.selected_exchanges}")
                    print(f"  min_spread: {settings.min_spread}%")
                    print(f"  min_profit_usd: {settings.min_profit_usd}$")
                    print(f"  position_size_usd: {settings.position_size_usd}$")
                    print(f"  leverage: {settings.leverage}x")
                    
                    if not settings.scan_active:
                        print(f"  ⚠️ Скан НЕ активирован для пользователя {user_id}")
                        continue
                    
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
                    max_coins_to_check = min(5, len(coins_to_check))  # Проверяем первые 5 для диагностики
                    
                    for coin in coins_to_check[:max_coins_to_check]:
                        coins_checked += 1
                        try:
                            print(f"\n  🔍 Проверка монеты {coin} ({coins_checked}/{max_coins_to_check})...")
                            
                            # Получаем данные с bid/ask
                            prices_data = {}
                            for exchange_name in exchanges_to_check:
                                print(f"    📡 Запрос цены с {exchange_name}...")
                                try:
                                    # Добавляем таймаут для каждого запроса (максимум 3 секунды)
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
                                    print(f"    ⚠️ {exchange_name}: timeout (превышено 3 сек), пропускаем")
                                except Exception as e:
                                    print(f"    ⚠️ {exchange_name}: ошибка {type(e).__name__}: {e}, пропускаем")
                                
                                # Задержка только для Hibachi (увеличена до 0.5 сек)
                                if exchange_name.lower() == "hibachi":
                                    await asyncio.sleep(0.5)
                                else:
                                    await asyncio.sleep(0.1)
                            
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
                            
                            # Рассчитываем профит с учётом bid/ask
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
