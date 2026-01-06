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
    
    Args:
        session: aiohttp сессия
        symbol: Тикер монеты (например, "BTC")
    
    Returns:
        Словарь с ценой, bid и ask или None при ошибке
    """
    try:
        cache_key = f"hibachi_{symbol}"
        if cache_key in _price_cache:
            cached_data, cached_time = _price_cache[cache_key]
            if datetime.now() - cached_time < timedelta(seconds=5):
                return cached_data
        
        if "hibachi" in _last_request_time:
            time_since_last = (datetime.now() - _last_request_time["hibachi"]).total_seconds()
            if time_since_last < _min_request_interval:
                wait_time = _min_request_interval - time_since_last
                await asyncio.sleep(wait_time)
        
        _last_request_time["hibachi"] = datetime.now()
        
        symbol_formatted = f"{symbol}/USDT-P"
        url = "https://data-api.hibachi.xyz/market/data/prices"
        params = {"symbol": symbol_formatted}
        
        headers = {
            "User-Agent": "TelegramBot/1.0",
            "Accept": "application/json"
        }
        
        async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 429:
                await asyncio.sleep(5)
                async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response2:
                    if response2.status != 200:
                        return None
                    response = response2
            
            if response.status == 200:
                import json
                data = json.loads(await response.text())
                
                if isinstance(data, dict):
                    # Извлекаем bid, ask и price
                    bid = None
                    ask = None
                    price = None
                    
                    if data.get("bidPrice") is not None:
                        try:
                            bid = float(data["bidPrice"])
                        except (ValueError, TypeError):
                            pass
                    
                    if data.get("askPrice") is not None:
                        try:
                            ask = float(data["askPrice"])
                        except (ValueError, TypeError):
                            pass
                    
                    # Приоритет для цены: tradePrice > markPrice > среднее bid/ask
                    if data.get("tradePrice") is not None:
                        try:
                            price = float(data["tradePrice"])
                        except (ValueError, TypeError):
                            pass
                    
                    if price is None and data.get("markPrice") is not None:
                        try:
                            price = float(data["markPrice"])
                        except (ValueError, TypeError):
                            pass
                    
                    if price is None and bid is not None and ask is not None:
                        price = (bid + ask) / 2.0
                    
                    if price is not None:
                        result = {"price": price}
                        if bid is not None:
                            result["bid"] = bid
                        if ask is not None:
                            result["ask"] = ask
                        
                        _price_cache[cache_key] = (result, datetime.now())
                        return result
            
            elif response.status == 404:
                return None
        
    except Exception as e:
        print(f"DEBUG Hibachi: ❌ Ошибка для {symbol}: {e}")
    
    return None
