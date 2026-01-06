"""
Расчёт профита с учётом проскальзывания и направления сделки
"""
from typing import Optional, Dict
from config import ALL_EXCHANGES


def calculate_profit_with_spread(
    long_exchange: str,
    short_exchange: str,
    long_data: Dict[str, float],  # {"price": float, "bid": float, "ask": float}
    short_data: Dict[str, float],  # {"price": float, "bid": float, "ask": float}
    position_size_usd: float,
    leverage: float,
) -> Dict[str, float]:
    """
    Рассчитывает профит с учётом:
    - Направления сделки (лонг на дешевой бирже, шорт на дорогой)
    - Проскальзывания при входе по маркету (ask для лонга, bid для шорта)
    - Комиссий (maker/taker) на открытие и закрытие
    
    Args:
        long_exchange: Биржа для лонга (дешевле)
        short_exchange: Биржа для шорта (дороже)
        long_data: Данные цены с биржи для лонга
        short_data: Данные цены с биржи для шорта
        position_size_usd: Размер позиции в USD
        leverage: Плечо
    
    Returns:
        Словарь с расчётами профита
    """
    long_exchange_info = ALL_EXCHANGES.get(long_exchange, {})
    short_exchange_info = ALL_EXCHANGES.get(short_exchange, {})
    
    long_maker_fee = long_exchange_info.get("maker_fee", 0.02) / 100
    long_taker_fee = long_exchange_info.get("taker_fee", 0.05) / 100
    short_maker_fee = short_exchange_info.get("maker_fee", 0.02) / 100
    short_taker_fee = short_exchange_info.get("taker_fee", 0.05) / 100
    
    nominal_size = position_size_usd * leverage
    
    # === РАСЧЁТ ДЛЯ МАРКЕТНЫХ ОРДЕРОВ ===
    # ЛОНГ: покупаем по ASK (выше)
    # ШОРТ: продаём по BID (ниже)
    long_entry_market = long_data.get("ask", long_data.get("price", 0))
    short_entry_market = short_data.get("bid", short_data.get("price", 0))
    
    if long_entry_market == 0 or short_entry_market == 0:
        return {
            "market_profit": 0,
            "market_fees": 0,
            "limit_profit": 0,
            "limit_fees": 0,
            "long_entry_market": 0,
            "short_entry_market": 0,
            "long_entry_limit": 0,
            "short_entry_limit": 0,
        }
    
    # Разница в ценах (шорт выше лонга = профит)
    price_diff_market = short_entry_market - long_entry_market
    gross_profit_market = (price_diff_market / long_entry_market) * nominal_size
    
    # Комиссии для маркетных ордеров (taker)
    fee_long_entry_market = nominal_size * long_taker_fee
    fee_short_entry_market = nominal_size * short_taker_fee
    fee_long_exit_market = nominal_size * long_taker_fee
    fee_short_exit_market = nominal_size * short_taker_fee
    total_fees_market = fee_long_entry_market + fee_short_entry_market + fee_long_exit_market + fee_short_exit_market
    
    net_profit_market = gross_profit_market - total_fees_market
    
    # === РАСЧЁТ ДЛЯ ЛИМИТНЫХ ОРДЕРОВ ===
    # ЛОНГ: покупаем по BID (ниже, но нужно ждать)
    # ШОРТ: продаём по ASK (выше, но нужно ждать)
    long_entry_limit = long_data.get("bid", long_data.get("price", 0))
    short_entry_limit = short_data.get("ask", short_data.get("price", 0))
    
    price_diff_limit = short_entry_limit - long_entry_limit
    gross_profit_limit = (price_diff_limit / long_entry_limit) * nominal_size
    
    # Комиссии для лимитных ордеров (maker)
    fee_long_entry_limit = nominal_size * long_maker_fee
    fee_short_entry_limit = nominal_size * short_maker_fee
    fee_long_exit_limit = nominal_size * long_maker_fee
    fee_short_exit_limit = nominal_size * short_maker_fee
    total_fees_limit = fee_long_entry_limit + fee_short_entry_limit + fee_long_exit_limit + fee_short_exit_limit
    
    net_profit_limit = gross_profit_limit - total_fees_limit
    
    return {
        "market_profit": net_profit_market,
        "market_fees": total_fees_market,
        "limit_profit": net_profit_limit,
        "limit_fees": total_fees_limit,
        "long_entry_market": long_entry_market,
        "short_entry_market": short_entry_market,
        "long_entry_limit": long_entry_limit,
        "short_entry_limit": short_entry_limit,
    }
