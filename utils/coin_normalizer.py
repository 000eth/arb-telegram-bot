import re


def normalize_coin_input(raw_input: str) -> list[str]:
    """
    Нормализует ввод монет:
    - Игнорирует регистр (BTC, btc, Btc -> BTC)
    - Извлекает тикер из пар (BTCUSDT, BTC/USDT, BTC-USDT -> BTC)
    - Поддерживает различные разделители (пробел, запятая, точка, слэш, дефис и т.д.)
    """
    separators = r'[\s,;|/\-_.]+'
    parts = re.split(separators, raw_input.strip())
    
    normalized_coins = []
    
    for part in parts:
        if not part:
            continue
        
        part_upper = part.upper()
        currency_suffixes = ['USDT', 'USD', 'USDC', 'BUSD', 'TUSD', 'DAI', 'EUR', 'BTC', 'ETH']
        
        coin_ticker = part_upper
        
        for suffix in currency_suffixes:
            if part_upper.endswith(suffix) and len(part_upper) > len(suffix):
                coin_ticker = part_upper[:-len(suffix)]
                break
            elif part_upper.startswith(suffix) and len(part_upper) > len(suffix):
                coin_ticker = part_upper[len(suffix):]
                break
        
        if not coin_ticker:
            coin_ticker = part_upper
        
        coin_ticker = re.sub(r'[^A-Z0-9]', '', coin_ticker)
        
        if coin_ticker and coin_ticker not in normalized_coins:
            normalized_coins.append(coin_ticker)
    
    return normalized_coins
