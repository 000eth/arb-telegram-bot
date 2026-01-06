"""
Hyperliquid API - получение цен с bid/ask
"""
import aiohttp
from typing import Optional, Dict

async def get_price(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    """Получает цену (для обратной совместимости)"""
    data = await get_price_data(session, symbol)
    return data.get("price") if data else None


async def get_price_data(session: aiohttp.ClientSession, symbol: str) -> Optional[Dict[str, float]]:
    """
    Получает данные о цене с Hyperliquid
    Возвращает: {"price": float, "bid": float, "ask": float} или None
    """
    try:
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
                if isinstance(data, dict):
                    # Ищем символ в ответе
                    symbol_upper = symbol.upper()
                    for key, value in data.items():
                        if symbol_upper in key.upper():
                            if isinstance(value, (int, float)):
                                price = float(value)
                                # Для Hyperliquid используем цену как bid и ask (упрощённо)
                                return {
                                    "price": price,
                                    "bid": price * 0.9999,  # Примерный bid (на 0.01% ниже)
                                    "ask": price * 1.0001   # Примерный ask (на 0.01% выше)
                                }
                            elif isinstance(value, dict):
                                if "mid" in value:
                                    price = float(value["mid"])
                                    return {
                                        "price": price,
                                        "bid": price * 0.9999,
                                        "ask": price * 1.0001
                                    }
    except Exception as e:
        print(f"DEBUG Hyperliquid: ❌ Ошибка для {symbol}: {e}")
        import traceback
        traceback.print_exc()
    
    return None
