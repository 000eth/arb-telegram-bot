# ---------- Конфигурация бирж ----------

CEX_EXCHANGES = {
    "Bybit": {
        "name": "Bybit",
        "type": "CEX",
        "api_base": "https://api.bybit.com",
        "ticker_endpoint": "/v5/market/tickers",
        "maker_fee": 0.01,
        "taker_fee": 0.06,
        "url_template": "https://www.bybit.com/trade/usdt/{symbol}",
    },
    "OKX": {
        "name": "OKX",
        "type": "CEX",
        "api_base": "https://www.okx.com",
        "ticker_endpoint": "/api/v5/market/ticker",
        "maker_fee": 0.02,
        "taker_fee": 0.05,
        "url_template": "https://www.okx.com/trade-spot/{symbol}-usdt",
    },
    "MEXC": {
        "name": "MEXC",
        "type": "CEX",
        "api_base": "https://api.mexc.com",
        "ticker_endpoint": "/api/v3/ticker/price",
        "maker_fee": 0.0,
        "taker_fee": 0.02,
        "url_template": "https://www.mexc.com/exchange/{symbol}_USDT",
    },
    "Gate": {
        "name": "Gate.io",
        "type": "CEX",
        "api_base": "https://api.gateio.ws",
        "ticker_endpoint": "/api/v4/futures/usdt/tickers",
        "maker_fee": 0.015,
        "taker_fee": 0.05,
        "url_template": "https://www.gate.io/trade/{symbol}_USDT",
    },
}

DEX_EXCHANGES = {
    "Hyperliquid": {
        "name": "Hyperliquid",
        "type": "DEX",
        "api_base": "https://api.hyperliquid.xyz",
        "ticker_endpoint": "/info",
        "maker_fee": 0.02,
        "taker_fee": 0.05,
        "url_template": "https://app.hyperliquid.xyz/exchange/{symbol}-USD",
    },
    "Hibachi": {
        "name": "Hibachi",
        "type": "DEX",
        "api_base": "https://api.hibachi.fi",
        "ticker_endpoint": "/v1/ticker",
        "maker_fee": 0.02,
        "taker_fee": 0.05,
        "url_template": "https://app.hibachi.fi/perpetual/{symbol}",
    },
    "Paradigm": {
        "name": "Paradigm",
        "type": "DEX",
        "api_base": "https://api.paradigm.xyz",
        "ticker_endpoint": "/v1/ticker",
        "maker_fee": 0.02,
        "taker_fee": 0.05,
        "url_template": "https://app.paradigm.xyz/{symbol}",
    },
}

ALL_EXCHANGES = {**CEX_EXCHANGES, **DEX_EXCHANGES}

POPULAR_COINS = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT", "MATIC", "AVAX",
    "LINK", "UNI", "ATOM", "ETC", "LTC", "BCH", "XLM", "ALGO", "VET", "FIL",
    "TRX", "EOS", "AAVE", "MKR", "COMP", "SNX", "YFI", "SUSHI", "CRV", "1INCH"
]

ALL_COINS = POPULAR_COINS + [
    "ARB", "OP", "APT", "SUI", "TIA", "SEI", "INJ", "NEAR", "FTM", "AVAX",
    "ICP", "HBAR", "QNT", "EGLD", "FLOW", "THETA", "AXS", "SAND", "MANA", "ENJ"
]

MIN_NOTIFICATION_INTERVAL_MINUTES = 1
