"""
Hyperliquid API - получение цен с bid/ask через официальный SDK
"""
from typing import Optional, Dict
from hyperliquid.info import Info
from hyperliquid.utils import constants

# Создаём один экземпляр Info для переиспользования
_info_instance = None

def get_info_instance():
    """Получает или создаёт экземпляр Info"""
    global _info_instance
    if _info_instance is None:
        _info_instance = Info(constants.MAINNET_API_URL, skip_ws=True)
    return _info_instance


async def get_price(session, symbol: str) -> Optional[float]:
    """Получает цену (для обратной совместимости)"""
    data = await get_price_data(session, symbol)
    return data.get("price") if data else None


async def get_price_data(session, symbol: str) -> Optional[Dict[str, float]]:
    """
    Получает данные о цене с Hyperliquid через официальный SDK
    Возвращает: {"price": float, "bid": float, "ask": float} или None
    """
    try:
        info = get_info_instance()
        
        # Получаем все цены через SDK
        all_mids = info.all_mids()
        
        if not all_mids or not isinstance(all_mids, dict):
            print(f"DEBUG Hyperliquid: all_mids вернул неожиданный формат")
            return None
        
        symbol_upper = symbol.upper()
        
        # Ищем символ в ответе
        for key, value in all_mids.items():
            if symbol_upper in key.upper():
                try:
                    # Преобразуем значение в float (может быть строка или число)
                    if isinstance(value, str):
                        price = float(value)
                    elif isinstance(value, (int, float)):
                        price = float(value)
                    else:
                        continue
                    
                    # Получаем bid/ask из orderbook
                    try:
                        # Получаем стакан для символа
                        # Формат символа для Hyperliquid может быть разным
                        # Пробуем получить orderbook
                        orderbook = info.orderbook(symbol_upper)
                        
                        if orderbook and isinstance(orderbook, dict):
                            # Извлекаем bid и ask из стакана
                            bids = orderbook.get("levels", [])
                            asks = orderbook.get("levels", [])
                            
                            # Берем лучшие bid и ask
                            if bids and len(bids) > 0:
                                best_bid = float(bids[0][0]) if isinstance(bids[0], list) else float(bids[0].get("px", price * 0.9999))
                            else:
                                best_bid = price * 0.9999
                            
                            if asks and len(asks) > 0:
                                best_ask = float(asks[0][0]) if isinstance(asks[0], list) else float(asks[0].get("px", price * 1.0001))
                            else:
                                best_ask = price * 1.0001
                            
                            result = {
                                "price": price,
                                "bid": best_bid,
                                "ask": best_ask
                            }
                            print(f"DEBUG Hyperliquid: ✅ Получены данные через SDK: {result}")
                            return result
                    except Exception as e:
                        print(f"DEBUG Hyperliquid: Не удалось получить orderbook, используем приблизительные bid/ask: {e}")
                    
                    # Если не удалось получить orderbook, используем приблизительные значения
                    result = {
                        "price": price,
                        "bid": price * 0.9999,
                        "ask": price * 1.0001
                    }
                    print(f"DEBUG Hyperliquid: ✅ Получена цена через SDK (приблизительные bid/ask): {result}")
                    return result
                    
                except (ValueError, TypeError) as e:
                    print(f"DEBUG Hyperliquid: Ошибка преобразования значения '{value}': {e}")
                    continue
        
        print(f"DEBUG Hyperliquid: ⚠️ Символ '{symbol_upper}' не найден")
        return None
        
    except Exception as e:
        print(f"DEBUG Hyperliquid: ❌ ИСКЛЮЧЕНИЕ для {symbol}: {e}")
        import traceback
        traceback.print_exc()
    
    return None
