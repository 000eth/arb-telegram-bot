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
        
        print(f"DEBUG Hibachi: Запрос к {url}")
        
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
            print(f"DEBUG Hibachi: Status = {response.status}")
            text = await response.text()
            print(f"DEBUG Hibachi: Response (первые 500 символов) = {text[:500]}")
            
            if response.status == 200:
                import json
                try:
                    data = json.loads(text)
                    print(f"DEBUG Hibachi: Parsed JSON = {json.dumps(data, indent=2)[:500]}")
                except Exception as e:
                    print(f"DEBUG Hibachi: Ошибка парсинга JSON: {e}")
                
                # Пробуем разные варианты структуры ответа
                if isinstance(data, dict):
                    # Вариант 1: data.price или data.lastPrice
                    if "price" in data:
                        price = float(data["price"])
                        print(f"DEBUG Hibachi: ✅ Найдена цена через data.price = {price}")
                        return price
                    if "lastPrice" in data:
                        price = float(data["lastPrice"])
                        print(f"DEBUG Hibachi: ✅ Найдена цена через data.lastPrice = {price}")
                        return price
                    if "last" in data:
                        price = float(data["last"])
                        print(f"DEBUG Hibachi: ✅ Найдена цена через data.last = {price}")
                        return price
                    # Вариант 2: data.data.price
                    if "data" in data and isinstance(data["data"], dict):
                        if "price" in data["data"]:
                            price = float(data["data"]["price"])
                            print(f"DEBUG Hibachi: ✅ Найдена цена через data.data.price = {price}")
                            return price
                        if "lastPrice" in data["data"]:
                            price = float(data["data"]["lastPrice"])
                            print(f"DEBUG Hibachi: ✅ Найдена цена через data.data.lastPrice = {price}")
                            return price
                    # Вариант 3: data.result.price
                    if "result" in data and isinstance(data["result"], dict):
                        if "price" in data["result"]:
                            price = float(data["result"]["price"])
                            print(f"DEBUG Hibachi: ✅ Найдена цена через data.result.price = {price}")
                            return price
                    print(f"DEBUG Hibachi: ⚠️ Не найдено поле с ценой в ответе. Доступные ключи: {list(data.keys())}")
        
        # Если первый вариант не сработал, пробуем альтернативный эндпоинт
        print(f"DEBUG Hibachi: Пробуем альтернативный endpoint /market/tickers")
        url2 = f"https://data-api.hibachi.xyz/market/tickers"
        async with session.get(url2, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
            print(f"DEBUG Hibachi: Status (tickers) = {response.status}")
            if response.status == 200:
                text2 = await response.text()
                print(f"DEBUG Hibachi: Response (tickers) length = {len(text2)} символов")
                
                try:
                    data = json.loads(text2)
                    print(f"DEBUG Hibachi: Type = {type(data)}")
                    
                    # Ищем нужный символ в списке
                    if isinstance(data, list):
                        print(f"DEBUG Hibachi: List length = {len(data)}")
                        for ticker in data:
                            if isinstance(ticker, dict):
                                symbol_key = ticker.get("symbol", "")
                                if symbol in symbol_key or symbol_formatted in symbol_key:
                                    print(f"DEBUG Hibachi: ✅ Найден символ {symbol} в ticker: {ticker}")
                                    if "price" in ticker:
                                        return float(ticker["price"])
                                    if "lastPrice" in ticker:
                                        return float(ticker["lastPrice"])
                                    if "last" in ticker:
                                        return float(ticker["last"])
                    elif isinstance(data, dict):
                        print(f"DEBUG Hibachi: Dict keys = {list(data.keys())[:10]}")
                        # Если это словарь с ключами-символами
                        if symbol_formatted in data:
                            ticker = data[symbol_formatted]
                            if "price" in ticker:
                                return float(ticker["price"])
                            if "lastPrice" in ticker:
                                return float(ticker["lastPrice"])
                except Exception as e:
                    print(f"DEBUG Hibachi: Ошибка парсинга tickers: {e}")
        
    except Exception as e:
        print(f"DEBUG Hibachi: ❌ Исключение при получении цены для {symbol}: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"DEBUG Hibachi: ❌ Не удалось получить цену для {symbol}")
    return None
