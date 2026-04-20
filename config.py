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
RSI_OVERSOLD    = 40          # Buy signal threshold (testing mode)
RSI_OVERBOUGHT  = 67          # Sell signal threshold
EMA_FAST        = 7
EMA_SLOW        = 18
CANDLE_INTERVAL = "1m"        # 1-minute candles (testing mode)

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

# ============================================================
#  FEATURE FLAGS — set False to disable any feature
# ============================================================

# Feature 1: EMA trend gate — BUY only when EMA_FAST > EMA_SLOW
USE_EMA_GATE = True

# Feature 2: Circuit breaker — pause trading on losing streaks
USE_CIRCUIT_BREAKER    = True
MAX_CONSECUTIVE_LOSSES = 3      # pause after N losses in a row
MAX_DAILY_LOSS_PCT     = 5.0    # halt day if daily P&L < -X% of starting capital
COOLDOWN_MINUTES       = 15     # min minutes between trades per symbol

# Feature 3: MACD confirmation — BUY only when MACD histogram > 0
USE_MACD_CONFIRM = True
MACD_FAST        = 12
MACD_SLOW        = 26
MACD_SIGNAL      = 9

# Feature 4: ATR-based SL/TP — replace fixed % with volatility-scaled levels
USE_ATR_EXITS  = True
ATR_PERIOD     = 14
ATR_SL_MULT    = 1.5            # SL = entry - (ATR * 1.5)
ATR_TP_MULT    = 2.5            # TP = entry + (ATR * 2.5)

# Feature 5: Volume confirmation — BUY only on above-average volume
USE_VOLUME_CONFIRM  = True
VOLUME_MA_PERIOD    = 20
VOLUME_MULTIPLIER   = 1.2       # volume must be 20% above its 20-EMA
