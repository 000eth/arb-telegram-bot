"""
Hibachi API - получение цен
Документация: https://api-doc.hibachi.xyz/
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
        
        # Endpoint: /market/data/prices?symbol=
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
                    print(f"DEBUG Hibachi: Parsed JSON keys = {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
                except Exception as e:
                    print(f"DEBUG Hibachi: Ошибка парсинга JSON: {e}")
                    return None
                
                # Парсим ответ Hibachi API
                if isinstance(data, dict):
                    # Приоритет: tradePrice (последняя цена сделки) > markPrice (маркировочная) > среднее bid/ask
                    # ВАЖНО: Проверяем на None перед преобразованием в float
                    if "tradePrice" in data and data["tradePrice"] is not None:
                        try:
                            price = float(data["tradePrice"])
                            print(f"DEBUG Hibachi: ✅ Найдена цена через tradePrice = {price}")
                            _price_cache[cache_key] = (price, datetime.now())
                            return price
                        except (ValueError, TypeError) as e:
                            print(f"DEBUG Hibachi: ⚠️ Ошибка преобразования tradePrice: {e}")
                    
                    if "markPrice" in data and data["markPrice"] is not None:
                        try:
                            price = float(data["markPrice"])
                            print(f"DEBUG Hibachi: ✅ Найдена цена через markPrice = {price}")
                            _price_cache[cache_key] = (price, datetime.now())
                            return price
                        except (ValueError, TypeError) as e:
                            print(f"DEBUG Hibachi: ⚠️ Ошибка преобразования markPrice: {e}")
                    
                    if "askPrice" in data and "bidPrice" in data:
                        ask = data["askPrice"]
                        bid = data["bidPrice"]
                        if ask is not None and bid is not None:
                            try:
                                ask_float = float(ask)
                                bid_float = float(bid)
                                price = (ask_float + bid_float) / 2.0
                                print(f"DEBUG Hibachi: ✅ Найдена цена через среднее bid/ask = {price}")
                                _price_cache[cache_key] = (price, datetime.now())
                                return price
                            except (ValueError, TypeError) as e:
                                print(f"DEBUG Hibachi: ⚠️ Ошибка преобразования bid/ask: {e}")
                    
                    if "spotPrice" in data and data["spotPrice"] is not None:
                        try:
                            price = float(data["spotPrice"])
                            print(f"DEBUG Hibachi: ✅ Найдена цена через spotPrice = {price}")
                            _price_cache[cache_key] = (price, datetime.now())
                            return price
                        except (ValueError, TypeError) as e:
                            print(f"DEBUG Hibachi: ⚠️ Ошибка преобразования spotPrice: {e}")
                    
                    print(f"DEBUG Hibachi: ⚠️ Все поля цен равны None или отсутствуют. Доступные ключи: {list(data.keys())}")
            elif response.status == 404:
                # Монета не найдена на Hibachi - это нормально, просто возвращаем None
                text = await response.text()
                print(f"DEBUG Hibachi: ℹ️ Монета {symbol} не найдена на Hibachi (404). Response: {text[:200]}")
                return None
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
