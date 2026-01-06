import asyncio
import aiohttp
from datetime import datetime, timedelta

from models import user_settings, last_notifications
from config import ALL_EXCHANGES, ALL_COINS, MIN_NOTIFICATION_INTERVAL_MINUTES
from services.price_fetcher import get_price_for_exchange
from services.profit_calculator import calculate_profit_with_spread
from keyboards import get_settings_keyboard


async def send_spread_notification(
    user_id: int,
    coin: str,
    prices: dict[str, float],
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
    
    prices_text = "\n".join([f"  • {dex}: {price:.2f} USDT" for dex, price in prices.items()])
    
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
                    if not settings.scan_active:
                        continue
                    
                    if settings.paused:
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
                    
                    if not exchanges_to_check:
                        continue
                    
                    for coin in coins_to_check:
                        try:
                            prices = {}
                            for exchange_name in exchanges_to_check:
                                price = await get_price_for_exchange(session, exchange_name, coin)
                                if price:
                                    prices[exchange_name] = price
                            
                            if len(prices) < 2:
                                continue
                            
                            min_exchange = min(prices, key=prices.get)
                            max_exchange = max(prices, key=prices.get)
                            min_price = prices[min_exchange]
                            max_price = prices[max_exchange]
                            
                            if min_price == 0:
                                continue
                            
                            spread_percent = ((max_price - min_price) / min_price) * 100
                            
                            if spread_percent < settings.min_spread:
                                continue
                            
                            profit_data = calculate_profit_with_spread(
                                min_price,
                                max_price,
                                None,  # long_bid
                                None,  # long_ask
                                None,  # short_bid
                                None,  # short_ask
                                settings.position_size_usd,
                                settings.leverage,
                                min_exchange,
                                max_exchange,
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
                                prices,
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
                            print(f"Ошибка при проверке монеты {coin} для пользователя {user_id}: {e}")
                            continue
                
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"Ошибка в фоновой задаче проверки спредов: {e}")
                await asyncio.sleep(5)
