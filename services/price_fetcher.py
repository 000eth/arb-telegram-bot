"""
Главный файл для получения цен с различных бирж
Импортирует функции из отдельных файлов для каждой биржи
"""
import random
import aiohttp
from typing import Optional

# Импортируем функции из отдельных файлов бирж
from services.bybit import get_price as get_price_bybit
from services.okx import get_price as get_price_okx
from services.mexc import get_price as get_price_mexc
from services.gate import get_price as get_price_gate
from services.hibachi import get_price as get_price_hibachi
from services.hyperliquid import get_price as get_price_hyperliquid


async def get_price_for_exchange(session: aiohttp.ClientSession, exchange_name: str, symbol: str) -> Optional[float]:
    """
    Получает цену для конкретной биржи
    
    Args:
        session: aiohttp сессия
        exchange_name: Название биржи (например, "Bybit", "OKX")
        symbol: Тикер монеты (например, "BTC")
    
    Returns:
        Цена в USDT или None при ошибке
    """
    exchange_name_lower = exchange_name.lower()
    
    if exchange_name_lower == "bybit":
        return await get_price_bybit(session, symbol)
    elif exchange_name_lower == "okx":
        return await get_price_okx(session, symbol)
    elif exchange_name_lower == "mexc":
        return await get_price_mexc(session, symbol)
    elif exchange_name_lower == "gate":
        return await get_price_gate(session, symbol)
    elif exchange_name_lower == "hibachi":
        return await get_price_hibachi(session, symbol)
    elif exchange_name_lower == "hyperliquid":
        return await get_price_hyperliquid(session, symbol)
    else:
        # Для остальных пока возвращаем фейковую цену
        base_prices = {"BTC": 60000, "ETH": 3000, "SOL": 150}
        base = base_prices.get(symbol, 1000)
        return base * (1 + random.uniform(-0.02, 0.02))
