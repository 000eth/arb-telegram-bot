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
    print(f"DEBUG Hyperliquid get_price_data: Начало для {symbol}")
    
    try:
        url = "https://api.hyperliquid.xyz/info"
        payload = {
            "type": "allMids"
        }
        headers = {
            "Content-Type": "application/json"
        }
        
        print(f"DEBUG Hyperliquid: Запрос к {url} с payload={payload}")
        
        async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
            print(f"DEBUG Hyperliquid: Status = {response.status}")
            
            if response.status == 200:
                text = await response.text()
                print(f"DEBUG Hyperliquid: Response text (первые 500 символов) = {text[:500]}")
                
                import json
                data = json.loads(text)
                
                if isinstance(data, dict):
                    print(f"DEBUG Hyperliquid: Parsed JSON type = dict, keys count = {len(data.keys())}")
                    symbol_upper = symbol.upper()
                    print(f"DEBUG Hyperliquid: Ищем символ '{symbol_upper}' в ключах...")
                    
                    for key, value in data.items():
                        if symbol_upper in key.upper():
                            print(f"DEBUG Hyperliquid: ✅ Найден ключ '{key}' для символа '{symbol_upper}'")
                            print(f"DEBUG Hyperliquid: Значение type = {type(value)}, value = {value}")
                            
                            # ИСПРАВЛЕНИЕ: Обрабатываем и строковые значения тоже
                            try:
                                if isinstance(value, (int, float)):
                                    price = float(value)
                                elif isinstance(value, str):
                                    # Пробуем преобразовать строку в float
                                    price = float(value)
                                    print(f"DEBUG Hyperliquid: Преобразовали строку '{value}' в float {price}")
                                else:
                                    print(f"DEBUG Hyperliquid: Неподдерживаемый тип значения: {type(value)}")
                                    continue
                                
                                result = {
                                    "price": price,
                                    "bid": price * 0.9999,
                                    "ask": price * 1.0001
                                }
                                print(f"DEBUG Hyperliquid: ✅ Возвращаем результат: {result}")
                                return result
                            except (ValueError, TypeError) as e:
                                print(f"DEBUG Hyperliquid: Ошибка преобразования значения '{value}': {e}")
                                continue
                            
                            # Если значение - словарь
                            if isinstance(value, dict):
                                print(f"DEBUG Hyperliquid: Значение - словарь, keys = {list(value.keys())}")
                                if "mid" in value:
                                    try:
                                        mid_value = value["mid"]
                                        if isinstance(mid_value, str):
                                            price = float(mid_value)
                                        else:
                                            price = float(mid_value)
                                        result = {
                                            "price": price,
                                            "bid": price * 0.9999,
                                            "ask": price * 1.0001
                                        }
                                        print(f"DEBUG Hyperliquid: ✅ Возвращаем результат: {result}")
                                        return result
                                    except (ValueError, TypeError) as e:
                                        print(f"DEBUG Hyperliquid: Ошибка преобразования mid: {e}")
                    
                    print(f"DEBUG Hyperliquid: ⚠️ Символ '{symbol_upper}' не найден в ответе")
                    print(f"DEBUG Hyperliquid: Первые 10 ключей: {list(data.keys())[:10]}")
            else:
                text = await response.text()
                print(f"DEBUG Hyperliquid: ❌ HTTP {response.status}. Response: {text[:200]}")
    except Exception as e:
        print(f"DEBUG Hyperliquid: ❌ ИСКЛЮЧЕНИЕ для {symbol}: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"DEBUG Hyperliquid: ❌ Возвращаем None для {symbol}")
    return None
