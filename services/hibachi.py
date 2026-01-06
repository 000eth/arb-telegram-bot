"""
Hibachi API - получение цен
Документация: https://api-doc.hibachi.xyz/
GitHub SDK: https://github.com/hibachi-xyz/hibachi_sdk
"""
import aiohttp
import asyncio
from typing import Optional
from datetime import datetime, timedelta

# Кэш для хранения цен и времени последнего запроса
_price_cache = {}
_last_request_time = {}
_min_request_interval = 2  # Минимальный интервал между запросами (секунды)


async def get_price(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    """
    Получает цену с Hibachi (perp-DEX)
    С обработкой rate limit и кэшированием
    
    Args:
        session: aiohttp сессия
        symbol: Тикер монеты (например, "BTC")
    
    Returns:
        Цена в USDT или None при ошибке
    """
    try:
        # Проверяем кэш (кэш на 5 секунд)
        cache_key = f"hibachi_{symbol}"
        if cache_key in _price_cache:
            cached_price, cached_time = _price_cache[cache_key]
            if datetime.now() - cached_time < timedelta(seconds=5):
                print(f"DEBUG Hibachi: Используем кэш для {symbol} = {cached_price}")
                return cached_price
        
        # Проверяем rate limit - делаем задержку между запросами
        if "hibachi" in _last_request_time:
            time_since_last = (datetime.now() - _last_request_time["hibachi"]).total_seconds()
            if time_since_last < _min_request_interval:
                wait_time = _min_request_interval - time_since_last
                print(f"DEBUG Hibachi: Задержка {wait_time:.2f} сек для избежания rate limit")
                await asyncio.sleep(wait_time)
        
        _last_request_time["hibachi"] = datetime.now()
        
        # Формат символа для Hibachi: BTC/USDT-P
        symbol_formatted = f"{symbol}/USDT-P"
        
        # ПРАВИЛЬНЫЙ endpoint: /market/data/prices?symbol=
        url = "https://data-api.hibachi.xyz/market/data/prices"
        params = {"symbol": symbol_formatted}
        
        headers = {
            "User-Agent": "TelegramBot/1.0",
            "Accept": "application/json"
        }
        
        print(f"DEBUG Hibachi: Запрос к {url} с параметром symbol={symbol_formatted}")
        
        async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
            print(f"DEBUG Hibachi: Status = {response.status}")
            
            # Обработка rate limit
            if response.status == 429:
                print(f"DEBUG Hibachi: ⚠️ Rate limit! Ждём 5 секунд...")
                await asyncio.sleep(5)
                # Пробуем ещё раз
                async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response2:
                    if response2.status != 200:
                        print(f"DEBUG Hibachi: ❌ Повторный запрос тоже вернул {response2.status}")
                        return None
                    response = response2
            
            if response.status == 200:
                text = await response.text()
                print(f"DEBUG Hibachi: Response (первые 500 символов) = {text[:500]}")
                
                import json
                try:
                    data = json.loads(text)
                    print(f"DEBUG Hibachi: Parsed JSON type = {type(data)}")
                    if isinstance(data, dict):
                        print(f"DEBUG Hibachi: JSON keys = {list(data.keys())}")
                    elif isinstance(data, list):
                        print(f"DEBUG Hibachi: List length = {len(data)}")
                except Exception as e:
                    print(f"DEBUG Hibachi: Ошибка парсинга JSON: {e}")
                    return None
                
                # Пробуем разные варианты структуры ответа
                if isinstance(data, dict):
                    # Вариант 1: data.price или data.lastPrice
                    if "price" in data:
                        price = float(data["price"])
                        print(f"DEBUG Hibachi: ✅ Найдена цена через data.price = {price}")
                        _price_cache[cache_key] = (price, datetime.now())
                        return price
                    if "lastPrice" in data:
                        price = float(data["lastPrice"])
                        print(f"DEBUG Hibachi: ✅ Найдена цена через data.lastPrice = {price}")
                        _price_cache[cache_key] = (price, datetime.now())
                        return price
                    if "last" in data:
                        price = float(data["last"])
                        print(f"DEBUG Hibachi: ✅ Найдена цена через data.last = {price}")
                        _price_cache[cache_key] = (price, datetime.now())
                        return price
                    # Вариант 2: data.data.price
                    if "data" in data and isinstance(data["data"], dict):
                        if "price" in data["data"]:
                            price = float(data["data"]["price"])
                            print(f"DEBUG Hibachi: ✅ Найдена цена через data.data.price = {price}")
                            _price_cache[cache_key] = (price, datetime.now())
                            return price
                        if "lastPrice" in data["data"]:
                            price = float(data["data"]["lastPrice"])
                            print(f"DEBUG Hibachi: ✅ Найдена цена через data.data.lastPrice = {price}")
                            _price_cache[cache_key] = (price, datetime.now())
                            return price
                    # Вариант 3: data.result.price
                    if "result" in data and isinstance(data["result"], dict):
                        if "price" in data["result"]:
                            price = float(data["result"]["price"])
                            print(f"DEBUG Hibachi: ✅ Найдена цена через data.result.price = {price}")
                            _price_cache[cache_key] = (price, datetime.now())
                            return price
                    print(f"DEBUG Hibachi: ⚠️ Не найдено поле с ценой. Доступные ключи: {list(data.keys())}")
                elif isinstance(data, list) and len(data) > 0:
                    # Если ответ - список, берём первый элемент
                    first_item = data[0]
                    if isinstance(first_item, dict):
                        if "price" in first_item:
                            price = float(first_item["price"])
                            print(f"DEBUG Hibachi: ✅ Найдена цена через list[0].price = {price}")
                            _price_cache[cache_key] = (price, datetime.now())
                            return price
                        if "lastPrice" in first_item:
                            price = float(first_item["lastPrice"])
                            print(f"DEBUG Hibachi: ✅ Найдена цена через list[0].lastPrice = {price}")
                            _price_cache[cache_key] = (price, datetime.now())
                            return price
            elif response.status == 404:
                print(f"DEBUG Hibachi: ❌ 404 - Endpoint не найден. Пробуем альтернативные варианты...")
                # Пробуем альтернативные endpoints
                alternative_urls = [
                    f"https://data-api.hibachi.xyz/market/ticker/{symbol_formatted}",
                    f"https://data-api.hibachi.xyz/market/prices?symbol={symbol_formatted}",
                    f"https://api.hibachi.xyz/market/data/prices?symbol={symbol_formatted}",
                ]
                for alt_url in alternative_urls:
                    print(f"DEBUG Hibachi: Пробуем альтернативный URL: {alt_url}")
                    try:
                        async with session.get(alt_url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as alt_response:
                            if alt_response.status == 200:
                                alt_data = await alt_response.json()
                                print(f"DEBUG Hibachi: ✅ Альтернативный URL сработал! Response: {alt_data}")
                                # Парсим ответ аналогично
                                if isinstance(alt_data, dict) and "price" in alt_data:
                                    price = float(alt_data["price"])
                                    _price_cache[cache_key] = (price, datetime.now())
                                    return price
                    except:
                        continue
            else:
                print(f"DEBUG Hibachi: ❌ Ошибка HTTP {response.status}")
                text = await response.text()
                print(f"DEBUG Hibachi: Response = {text[:200]}")
        
    except Exception as e:
        print(f"DEBUG Hibachi: ❌ Исключение при получении цены для {symbol}: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"DEBUG Hibachi: ❌ Не удалось получить цену для {symbol}")
    return None
