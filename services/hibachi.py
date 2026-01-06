"""
Hibachi API - получение цен с bid/ask
"""
import aiohttp
import asyncio
from typing import Optional, Dict
from datetime import datetime, timedelta

# Кэш для хранения цен и времени последнего запроса
_price_cache = {}
_last_request_time = {}
_min_request_interval = 2


async def get_price(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    """Получает цену (для обратной совместимости)"""
    data = await get_price_data(session, symbol)
    return data.get("price") if data else None


async def get_price_data(session: aiohttp.ClientSession, symbol: str) -> Optional[Dict[str, float]]:
    """
    Получает данные о цене с Hibachi (perp-DEX)
    Возвращает: {"price": float, "bid": float, "ask": float} или None
    """
    print(f"DEBUG Hibachi get_price_data: Начало для {symbol}")
    
    try:
        cache_key = f"hibachi_{symbol}"
        if cache_key in _price_cache:
            cached_data, cached_time = _price_cache[cache_key]
            if datetime.now() - cached_time < timedelta(seconds=5):
                print(f"DEBUG Hibachi: Используем кэш для {symbol}")
                return cached_data
        
        if "hibachi" in _last_request_time:
            time_since_last = (datetime.now() - _last_request_time["hibachi"]).total_seconds()
            if time_since_last < _min_request_interval:
                wait_time = _min_request_interval - time_since_last
                print(f"DEBUG Hibachi: Задержка {wait_time:.2f} сек")
                await asyncio.sleep(wait_time)
        
        _last_request_time["hibachi"] = datetime.now()
        
        symbol_formatted = f"{symbol}/USDT-P"
        url = "https://data-api.hibachi.xyz/market/data/prices"
        params = {"symbol": symbol_formatted}
        
        headers = {
            "User-Agent": "TelegramBot/1.0",
            "Accept": "application/json"
        }
        
        print(f"DEBUG Hibachi: Запрос к {url} с params={params}")
        
        async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
            print(f"DEBUG Hibachi: Status = {response.status}")
            
            if response.status == 429:
                print(f"DEBUG Hibachi: Rate limit, ждём 5 сек...")
                await asyncio.sleep(5)
                async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response2:
                    if response2.status != 200:
                        print(f"DEBUG Hibachi: Повторный запрос вернул {response2.status}")
                        return None
                    response = response2
            
            if response.status == 200:
                text = await response.text()
                print(f"DEBUG Hibachi: Response text (первые 200 символов) = {text[:200]}")
                
                import json
                try:
                    data = json.loads(text)
                    print(f"DEBUG Hibachi: Parsed JSON type = {type(data)}")
                    if isinstance(data, dict):
                        print(f"DEBUG Hibachi: JSON keys = {list(data.keys())}")
                except Exception as e:
                    print(f"DEBUG Hibachi: Ошибка парсинга JSON: {e}")
                    return None
                
                if isinstance(data, dict):
                    bid = None
                    ask = None
                    price = None
                    
                    if data.get("bidPrice") is not None:
                        try:
                            bid = float(data["bidPrice"])
                            print(f"DEBUG Hibachi: bid = {bid}")
                        except (ValueError, TypeError) as e:
                            print(f"DEBUG Hibachi: Ошибка преобразования bidPrice: {e}")
                    
                    if data.get("askPrice") is not None:
                        try:
                            ask = float(data["askPrice"])
                            print(f"DEBUG Hibachi: ask = {ask}")
                        except (ValueError, TypeError) as e:
                            print(f"DEBUG Hibachi: Ошибка преобразования askPrice: {e}")
                    
                    if data.get("tradePrice") is not None:
                        try:
                            price = float(data["tradePrice"])
                            print(f"DEBUG Hibachi: tradePrice = {price}")
                        except (ValueError, TypeError) as e:
                            print(f"DEBUG Hibachi: Ошибка преобразования tradePrice: {e}")
                    
                    if price is None and data.get("markPrice") is not None:
                        try:
                            price = float(data["markPrice"])
                            print(f"DEBUG Hibachi: markPrice = {price}")
                        except (ValueError, TypeError) as e:
                            print(f"DEBUG Hibachi: Ошибка преобразования markPrice: {e}")
                    
                    if price is None and bid is not None and ask is not None:
                        price = (bid + ask) / 2.0
                        print(f"DEBUG Hibachi: price = среднее bid/ask = {price}")
                    
                    if price is not None:
                        result = {"price": price}
                        if bid is not None:
                            result["bid"] = bid
                        if ask is not None:
                            result["ask"] = ask
                        
                        print(f"DEBUG Hibachi: ✅ Возвращаем результат: {result}")
                        _price_cache[cache_key] = (result, datetime.now())
                        return result
                    else:
                        print(f"DEBUG Hibachi: ⚠️ price = None, не можем вернуть результат")
            
            elif response.status == 404:
                text = await response.text()
                print(f"DEBUG Hibachi: 404 - Монета не найдена. Response: {text[:200]}")
                return None
            else:
                text = await response.text()
                print(f"DEBUG Hibachi: ❌ HTTP {response.status}. Response: {text[:200]}")
        
    except Exception as e:
        print(f"DEBUG Hibachi: ❌ ИСКЛЮЧЕНИЕ для {symbol}: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"DEBUG Hibachi: ❌ Возвращаем None для {symbol}")
    return None
