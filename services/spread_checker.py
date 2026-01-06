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
    prices: dict[str, dict],  # {"exchange": {"price": float, "bid": float, "ask": float}}
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
            disable_web_page_preview=False
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
                    if not settings.scan_active or settings.paused:
                        continue
                    
                    if settings.track_all_coins:
                        coins_to_check = ALL_COINS
                    else:
                        coins_to_check = settings.coins
                    
                    if not coins_to_check:
                        continue
                    
                    if settings.track_all_exchanges:
                        exchanges_to_check = list(ALL_EXCHANGES.keys())
                    else:
                        exchanges_to_check = settings.selected_exchanges if settings.selected_exchanges else list(ALL_EXCHANGES.keys())
                    
                    if not exchanges_to_check or len(exchanges_to_check) < 2:
                        continue
                    
                    for coin in coins_to_check:
                        try:
                            # Получаем данные с bid/ask
                            prices_data = {}
                            for exchange_name in exchanges_to_check:
                                data = await get_price_data_for_exchange(session, exchange_name, coin)
                                if data and data.get("price"):
                                    prices_data[exchange_name] = data
                                
                                if exchange_name.lower() == "hibachi":
                                    await asyncio.sleep(0.5)
                                else:
                                    await asyncio.sleep(0.1)
                            
                            if len(prices_data) < 2:
                                continue
                            
                            # Находим минимальную и максимальную цену
                            min_exchange = min(prices_data, key=lambda x: prices_data[x].get("price", float('inf')))
                            max_exchange = max(prices_data, key=lambda x: prices_data[x].get("price", 0))
                            
                            min_price = prices_data[min_exchange].get("price", 0)
                            max_price = prices_data[max_exchange].get("price", 0)
                            
                            if min_price == 0:
                                continue
                            
                            spread_percent = ((max_price - min_price) / min_price) * 100
                            
                            if spread_percent < settings.min_spread:
                                continue
                            
                            # Рассчитываем профит с учётом bid/ask
                            profit_data = calculate_profit_with_spread(
                                min_exchange,  # ЛОНГ на дешевой бирже
                                max_exchange,  # ШОРТ на дорогой бирже
                                prices_data[min_exchange],
                                prices_data[max_exchange],
                                settings.position_size_usd,
                                settings.leverage,
                            )
                            
                            best_profit = max(profit_data["market_profit"], profit_data["limit_profit"])
                            
                            if best_profit < settings.min_profit_usd:
                                continue
                            
                            last_notif = last_notifications.get(user_id, {}).get(coin)
                            if last_notif:
                                time_since_last = datetime.now() - last_notif
                                if time_since_last < timedelta(minutes=MIN_NOTIFICATION_INTERVAL_MINUTES):
                                    continue
                            
                            await send_spread_notification(
                                user_id,
                                coin,
                                prices_data,
                                spread_percent,
                                profit_data,
                                min_exchange,  # ЛОНГ
                                max_exchange,  # ШОРТ
                                settings,
                                bot_instance,
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
