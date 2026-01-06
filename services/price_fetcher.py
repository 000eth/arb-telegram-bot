"""
Диспетчер для получения цен с разных бирж
"""
import aiohttp
from typing import Optional, Dict

from services.bybit import get_price as get_price_bybit
from services.okx import get_price as get_price_okx
from services.mexc import get_price as get_price_mexc
from services.gate import get_price as get_price_gate
from services.hibachi import get_price_data as get_price_data_hibachi
from services.hyperliquid import get_price_data as get_price_data_hyperliquid


async def get_price_for_exchange(session: aiohttp.ClientSession, exchange_name: str, symbol: str) -> Optional[float]:
    """Получает цену (для обратной совместимости)"""
    data = await get_price_data_for_exchange(session, exchange_name, symbol)
    return data.get("price") if data else None


async def get_price_data_for_exchange(session: aiohttp.ClientSession, exchange_name: str, symbol: str) -> Optional[Dict[str, float]]:
    """
    Получает данные о цене с биржи (цена, bid, ask)
    Возвращает: {"price": float, "bid": float, "ask": float} или None
    """
    exchange_name_lower = exchange_name.lower()
    
    print(f"DEBUG price_fetcher: Запрос к {exchange_name} для {symbol}")
    
    try:
        if exchange_name_lower == "hibachi":
            print(f"DEBUG price_fetcher: Вызываем get_price_data_hibachi для {symbol}")
            result = await get_price_data_hibachi(session, symbol)
            print(f"DEBUG price_fetcher: Hibachi вернул: {result}")
            return result
        elif exchange_name_lower == "hyperliquid":
            print(f"DEBUG price_fetcher: Вызываем get_price_data_hyperliquid для {symbol}")
            result = await get_price_data_hyperliquid(session, symbol)
            print(f"DEBUG price_fetcher: Hyperliquid вернул: {result}")
            return result
        elif exchange_name_lower == "bybit":
            price = await get_price_bybit(session, symbol)
            if price:
                return {"price": price, "bid": price * 0.9999, "ask": price * 1.0001}
        elif exchange_name_lower == "okx":
            price = await get_price_okx(session, symbol)
            if price:
                return {"price": price, "bid": price * 0.9999, "ask": price * 1.0001}
        elif exchange_name_lower == "mexc":
            price = await get_price_mexc(session, symbol)
            if price:
                return {"price": price, "bid": price * 0.9999, "ask": price * 1.0001}
        elif exchange_name_lower == "gate":
            price = await get_price_gate(session, symbol)
            if price:
                return {"price": price, "bid": price * 0.9999, "ask": price * 1.0001}
    except Exception as e:
        print(f"DEBUG price_fetcher: ❌ ИСКЛЮЧЕНИЕ при получении цены с {exchange_name} для {symbol}: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"DEBUG price_fetcher: ❌ Не удалось получить цену с {exchange_name} для {symbol}")
    return None
