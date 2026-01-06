"""
Bybit API - получение цен
Документация: https://bybit-exchange.github.io/docs/v5/intro
"""
import aiohttp
from typing import Optional


async def get_price(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    """
    Получает цену с Bybit для перпетуальных контрактов
    
    Args:
        session: aiohttp сессия
        symbol: Тикер монеты (например, "BTC")
    
    Returns:
        Цена в USDT или None при ошибке
    """
    try:
        url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}USDT"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("retCode") == 0 and data.get("result", {}).get("list"):
                    return float(data["result"]["list"][0]["lastPrice"])
    except Exception as e:
        print(f"Ошибка получения цены с Bybit для {symbol}: {e}")
    return None
