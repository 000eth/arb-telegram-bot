"""
Hyperliquid API - получение цен с bid/ask через официальный SDK
"""
import asyncio
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
        symbol_upper = symbol.upper()
        
        # Выполняем синхронные вызовы SDK в отдельном потоке
        all_mids = await asyncio.to_thread(info.all_mids)
        
        if not all_mids or not isinstance(all_mids, dict):
            print(f"DEBUG Hyperliquid: all_mids вернул неожиданный формат")
            return None
        
        # ИСПРАВЛЕНИЕ: Ищем точное совпадение или стандартные форматы
        # Пробуем разные варианты имени символа
        possible_keys = [
            symbol_upper,           # SOL
            f"{symbol_upper}USD",   # SOLUSD
            f"{symbol_upper}USDT",  # SOLUSDT
            f"{symbol_upper}-USD",  # SOL-USD
            f"{symbol_upper}-USDT", # SOL-USDT
        ]
        
        price = None
        found_key = None
        
        # Сначала ищем точное совпадение
        for key in possible_keys:
            if key in all_mids:
                value = all_mids[key]
                try:
                    if isinstance(value, str):
                        price = float(value)
                    elif isinstance(value, (int, float)):
                        price = float(value)
                    if price:
                        found_key = key
                        print(f"DEBUG Hyperliquid: ✅ Найден точный ключ '{key}' = {price}")
                        break
                except (ValueError, TypeError):
                    continue
        
        # Если точного совпадения нет, ищем частичное (но с проверкой на разумность)
        if price is None:
            print(f"DEBUG Hyperliquid: Точного совпадения нет, ищем частичное для '{symbol_upper}'...")
            for key, value in all_mids.items():
                # Ищем ключ, который начинается с символа или содержит его как отдельное слово
                key_upper = key.upper()
                if (key_upper == symbol_upper or 
                    key_upper.startswith(symbol_upper) and len(key_upper) <= len(symbol_upper) + 5):
                    try:
                        if isinstance(value, str):
                            candidate_price = float(value)
                        elif isinstance(value, (int, float)):
                            candidate_price = float(value)
                        else:
                            continue
                        
                        # ПРОВЕРКА НА РАЗУМНОСТЬ: цена должна быть в разумных пределах
                        # Для большинства криптовалют цена должна быть > 0.01 и < 1000000
                        # Если цена слишком маленькая (< 0.1) или слишком большая (> 100000), это подозрительно
                        if 0.1 <= candidate_price <= 1000000:
                            price = candidate_price
                            found_key = key
                            print(f"DEBUG Hyperliquid: ✅ Найден ключ '{key}' = {price} (прошёл проверку на разумность)")
                            break
                        else:
                            print(f"DEBUG Hyperliquid: ⚠️ Ключ '{key}' = {candidate_price} не прошёл проверку на разумность")
                    except (ValueError, TypeError):
                        continue
        
        if price is None:
            print(f"DEBUG Hyperliquid: ⚠️ Символ '{symbol_upper}' не найден или цена не прошла проверку")
            # Выводим первые несколько ключей для отладки
            sample_keys = [k for k in list(all_mids.keys())[:20] if symbol_upper in k.upper()]
            if sample_keys:
                print(f"DEBUG Hyperliquid: Похожие ключи: {sample_keys}")
            return None
        
        # Получаем bid/ask (упрощённо, так как orderbook может быть недоступен)
        result = {
            "price": price,
            "bid": price * 0.9999,  # Приблизительный bid (на 0.01% ниже)
            "ask": price * 1.0001   # Приблизительный ask (на 0.01% выше)
        }
        
        print(f"DEBUG Hyperliquid: ✅ Получена цена через SDK: {result}")
        return result
        
    except Exception as e:
        print(f"DEBUG Hyperliquid: ❌ ИСКЛЮЧЕНИЕ для {symbol}: {e}")
        import traceback
        traceback.print_exc()
    
    return None
