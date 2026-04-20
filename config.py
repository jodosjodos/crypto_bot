# ============================================================
#  TRADING BOT CONFIGURATION
#  Start with PAPER_TRADING = True (fake money, zero risk)
#  Only set PAPER_TRADING = False when you understand the risks
# ============================================================

# --- Mode ---
PAPER_TRADING = True          # True = fake money. NEVER set False without understanding the risks.

# --- Capital ---
STARTING_CAPITAL = 50.0       # USD — simulated in paper mode

# --- Assets to trade (crypto pairs on Binance) ---
SYMBOLS = ["BTC/USDT", "ETH/USDT"]

# --- Strategy parameters ---
RSI_PERIOD      = 14
RSI_OVERSOLD    = 40          # Buy signal threshold (lowered to 40 for testing)
RSI_OVERBOUGHT  = 67          # Sell signal threshold
EMA_FAST        = 7
EMA_SLOW        = 18
CANDLE_INTERVAL = "1m"        # 1-minute candles (fast test mode)

# --- Risk management (CRITICAL — do not disable) ---
STOP_LOSS_PCT   = 0.015        # 2%  stop loss per trade
TAKE_PROFIT_PCT = 0.03        # 4%  take profit per trade
MAX_POSITION_PCT = 0.25       # Max 25% of portfolio in one position
MAX_OPEN_TRADES  = 2          # Max simultaneous open trades

# --- Exchange ---
# EXCHANGE options: "binance", "kucoin"
# KuCoin requires much less verification than Binance — good for beginners
# Leave keys blank for paper trading (uses Binance public data either way)
EXCHANGE   = "kucoin"
API_KEY    = "69e4f4fe37bb1400015f8928"
API_SECRET = "47b23ee0-5443-4c70-9110-243306048710"
API_PASSPHRASE = "@Umugabo15jodos"   # KuCoin requires a passphrase in addition to key/secret

# --- Logging ---
LOG_FILE = "trades.log"
