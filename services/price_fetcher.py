import random
import aiohttp
from typing import Optional


async def get_price_bybit(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    """Получает цену с Bybit"""
    try:
        url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}USDT"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("retCode") == 0 and data.get("result", {}).get("list"):
                    return float(data["result"]["list"][0]["lastPrice"])
    except Exception as e:
        print(f"Ошибка получения цены с Bybit: {e}")
    return None


async def get_price_okx(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    """Получает цену с OKX"""
    try:
        url = f"https://www.okx.com/api/v5/market/ticker?instId={symbol}-USDT-SWAP"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("code") == "0" and data.get("data"):
                    return float(data["data"][0]["last"])
    except Exception as e:
        print(f"Ошибка получения цены с OKX: {e}")
    return None


async def get_price_mexc(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    """Получает цену с MEXC"""
    try:
        url = f"https://api.mexc.com/api/v3/ticker/price?symbol={symbol}USDT"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                if "price" in data:
                    return float(data["price"])
    except Exception as e:
        print(f"Ошибка получения цены с MEXC: {e}")
    return None


async def get_price_gate(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    """Получает цену с Gate.io"""
    try:
        url = f"https://api.gateio.ws/api/v4/futures/usdt/tickers?contract={symbol}_USDT"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                if data and len(data) > 0:
                    return float(data[0]["last"])
    except Exception as e:
        print(f"Ошибка получения цены с Gate.io: {e}")
    return None


async def get_price_for_exchange(session: aiohttp.ClientSession, exchange_name: str, symbol: str) -> Optional[float]:
    """Получает цену для конкретной биржи"""
    exchange_name_lower = exchange_name.lower()
    
    if exchange_name_lower == "bybit":
        return await get_price_bybit(session, symbol)
    elif exchange_name_lower == "okx":
        return await get_price_okx(session, symbol)
    elif exchange_name_lower == "mexc":
        return await get_price_mexc(session, symbol)
    elif exchange_name_lower == "gate":
        return await get_price_gate(session, symbol)
    else:
        # Для остальных пока возвращаем фейковую цену
        base_prices = {"BTC": 60000, "ETH": 3000, "SOL": 150}
        base = base_prices.get(symbol, 1000)
        return base * (1 + random.uniform(-0.02, 0.02))
