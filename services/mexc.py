"""
MEXC API - получение цен
Документация: https://mexcdevelop.github.io/apidocs/spot_v3_en/
"""
import aiohttp
from typing import Optional


async def get_price(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    """
    Получает цену с MEXC
    
    Args:
        session: aiohttp сессия
        symbol: Тикер монеты (например, "BTC")
    
    Returns:
        Цена в USDT или None при ошибке
    """
    try:
        url = f"https://api.mexc.com/api/v3/ticker/price?symbol={symbol}USDT"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                if "price" in data:
                    return float(data["price"])
    except Exception as e:
        print(f"Ошибка получения цены с MEXC для {symbol}: {e}")
    return None
