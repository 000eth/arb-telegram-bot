"""
OKX API - получение цен
Документация: https://www.okx.com/docs-v5/en/
"""
import aiohttp
from typing import Optional


async def get_price(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    """
    Получает цену с OKX для перпетуальных свопов
    
    Args:
        session: aiohttp сессия
        symbol: Тикер монеты (например, "BTC")
    
    Returns:
        Цена в USDT или None при ошибке
    """
    try:
        url = f"https://www.okx.com/api/v5/market/ticker?instId={symbol}-USDT-SWAP"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("code") == "0" and data.get("data"):
                    return float(data["data"][0]["last"])
    except Exception as e:
        print(f"Ошибка получения цены с OKX для {symbol}: {e}")
    return None
