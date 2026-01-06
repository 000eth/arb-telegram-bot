"""
Gate.io API - получение цен
Документация: https://www.gate.io/docs/developers/apiv4/
"""
import aiohttp
from typing import Optional


async def get_price(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    """
    Получает цену с Gate.io для перпетуальных контрактов
    
    Args:
        session: aiohttp сессия
        symbol: Тикер монеты (например, "BTC")
    
    Returns:
        Цена в USDT или None при ошибке
    """
    try:
        url = f"https://api.gateio.ws/api/v4/futures/usdt/tickers?contract={symbol}_USDT"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                if data and len(data) > 0:
                    return float(data[0]["last"])
    except Exception as e:
        print(f"Ошибка получения цены с Gate.io для {symbol}: {e}")
    return None
