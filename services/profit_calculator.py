from typing import Optional, Dict
from config import ALL_EXCHANGES


def calculate_profit_with_spread(
    long_price: float,
    short_price: float,
    long_bid: Optional[float],
    long_ask: Optional[float],
    short_bid: Optional[float],
    short_ask: Optional[float],
    position_size_usd: float,
    leverage: float,
    long_exchange: str,
    short_exchange: str,
) -> Dict[str, float]:
    """
    Рассчитывает профит с учётом спреда стакана и комиссий.
    Возвращает словарь с профитом для маркета и лимита.
    """
    long_exchange_info = ALL_EXCHANGES.get(long_exchange, {})
    short_exchange_info = ALL_EXCHANGES.get(short_exchange, {})
    
    long_maker_fee = long_exchange_info.get("maker_fee", 0.02) / 100
    long_taker_fee = long_exchange_info.get("taker_fee", 0.05) / 100
    short_maker_fee = short_exchange_info.get("maker_fee", 0.02) / 100
    short_taker_fee = short_exchange_info.get("taker_fee", 0.05) / 100
    
    nominal_size = position_size_usd * leverage
    
    # Профит при входе по МАРКЕТУ (тейкер)
    long_entry_market = long_ask if long_ask else long_price
    short_entry_market = short_bid if short_bid else short_price
    
    price_diff_market = short_entry_market - long_entry_market
    gross_profit_market = (price_diff_market / long_entry_market) * nominal_size
    
    fee_long_entry_market = nominal_size * long_taker_fee
    fee_short_entry_market = nominal_size * short_taker_fee
    fee_long_exit_market = nominal_size * long_taker_fee
    fee_short_exit_market = nominal_size * short_taker_fee
    
    total_fees_market = fee_long_entry_market + fee_short_entry_market + fee_long_exit_market + fee_short_exit_market
    net_profit_market = gross_profit_market - total_fees_market
    
    # Профит при входе по ЛИМИТУ (мейкер)
    long_entry_limit = long_bid if long_bid else long_price
    short_entry_limit = short_ask if short_ask else short_price
    
    price_diff_limit = short_entry_limit - long_entry_limit
    gross_profit_limit = (price_diff_limit / long_entry_limit) * nominal_size
    
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
