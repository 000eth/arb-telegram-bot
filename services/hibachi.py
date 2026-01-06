"""
Hibachi API - получение цен
Документация: https://api-doc.hibachi.xyz/
GitHub SDK: https://github.com/hibachi-xyz/hibachi_sdk
"""
import aiohttp
from typing import Optional


async def get_price(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    """
    Получает цену с Hibachi (perp-DEX)
    
    Args:
        session: aiohttp сессия
        symbol: Тикер монеты (например, "BTC")
    
    Returns:
        Цена в USDT или None при ошибке
    """
    try:
        # Формат символа для Hibachi: BTC/USDT-P
        symbol_formatted = f"{symbol}/USDT-P"
        
        # Пробуем data-api endpoint (для market data, не требует авторизации)
        url = f"https://data-api.hibachi.xyz/market/ticker/{symbol_formatted}"
        
        headers = {
            "User-Agent": "TelegramBot/1.0",
            "Accept": "application/json"
        }
        
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                
                # Пробуем разные варианты структуры ответа
                if isinstance(data, dict):
                    # Вариант 1: data.price или data.lastPrice
                    if "price" in data:
                        return float(data["price"])
                    if "lastPrice" in data:
                        return float(data["lastPrice"])
                    if "last" in data:
                        return float(data["last"])
                    # Вариант 2: data.data.price
                    if "data" in data and isinstance(data["data"], dict):
                        if "price" in data["data"]:
                            return float(data["data"]["price"])
                        if "lastPrice" in data["data"]:
                            return float(data["data"]["lastPrice"])
                    # Вариант 3: data.result.price
                    if "result" in data and isinstance(data["result"], dict):
                        if "price" in data["result"]:
                            return float(data["result"]["price"])
        
        # Если первый вариант не сработал, пробуем альтернативный эндпоинт
        url2 = f"https://data-api.hibachi.xyz/market/tickers"
        async with session.get(url2, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                # Ищем нужный символ в списке
                if isinstance(data, list):
                    for ticker in data:
                        if isinstance(ticker, dict):
                            symbol_key = ticker.get("symbol", "")
                            if symbol in symbol_key or symbol_formatted in symbol_key:
                                if "price" in ticker:
                                    return float(ticker["price"])
                                if "lastPrice" in ticker:
                                    return float(ticker["lastPrice"])
                                if "last" in ticker:
                                    return float(ticker["last"])
                elif isinstance(data, dict):
                    # Если это словарь с ключами-символами
                    if symbol_formatted in data:
                        ticker = data[symbol_formatted]
                        if "price" in ticker:
                            return float(ticker["price"])
                        if "lastPrice" in ticker:
                            return float(ticker["lastPrice"])
        
    except Exception as e:
        print(f"Ошибка получения цены с Hibachi для {symbol}: {e}")
    
    return None
