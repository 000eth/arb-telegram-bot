"""
Hyperliquid API - получение цен
Документация: https://hyperliquid.gitbook.io/hyperliquid-docs/
"""
import aiohttp
from typing import Optional


async def get_price(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    """
    Получает цену с Hyperliquid (perp-DEX)
    
    Args:
        session: aiohttp сессия
        symbol: Тикер монеты (например, "BTC")
    
    Returns:
        Цена в USDT или None при ошибке
    """
    try:
        # Hyperliquid использует POST запросы
        url = "https://api.hyperliquid.xyz/info"
        
        payload = {
            "type": "allMids"
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                # TODO: Реализовать парсинг ответа после проверки реального API
                # Структура ответа может быть: {"BTC": 60000, "ETH": 3000, ...}
                if isinstance(data, dict):
                    # Пробуем найти символ
                    for key, value in data.items():
                        if symbol.upper() in key.upper():
                            if isinstance(value, (int, float)):
                                return float(value)
                            elif isinstance(value, dict) and "mid" in value:
                                return float(value["mid"])
        
    except Exception as e:
        print(f"Ошибка получения цены с Hyperliquid для {symbol}: {e}")
    
    return None
