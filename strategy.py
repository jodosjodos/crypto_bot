"""
Strategy: RSI Crossover + Multi-Indicator Confirmation
-------------------------------------------------------
BUY  when ALL of the following are true:
  1. RSI crosses UPWARD through the oversold threshold (recovery signal)
  2. EMA_FAST > EMA_SLOW (trend is bullish) [if USE_EMA_GATE]
  3. MACD histogram > 0 (momentum is positive) [if USE_MACD_CONFIRM]
  4. Volume > 20-period EMA of volume * multiplier [if USE_VOLUME_CONFIRM]

SELL when: RSI >= overbought threshold
       OR: stop-loss / take-profit hit (handled by paper_trader.py)

SL/TP: ATR-based (volatility-adaptive) if USE_ATR_EXITS, else fixed %

Why multi-confirmation:
  - Each gate filters out a different type of false signal
  - EMA gate: avoids buying into a downtrend
  - MACD gate: avoids buying when momentum is still negative
  - Volume gate: avoids buying on low-participation moves
  - Fewer trades, higher quality — proven by AI trading competition data
"""

import pandas as pd
import config


def compute_rsi(prices: pd.Series, period: int) -> pd.Series:
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_ema(prices: pd.Series, span: int) -> pd.Series:
    return prices.ewm(span=span, adjust=False).mean()


def compute_macd(prices: pd.Series, fast: int, slow: int,
                 signal_period: int) -> tuple:
    """
    Returns (macd_line, signal_line, histogram).
    Requires at least slow + signal_period rows for reliable values.
    """
    ema_fast    = prices.ewm(span=fast, adjust=False).mean()
    ema_slow    = prices.ewm(span=slow, adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_atr_value(df: pd.DataFrame, period: int) -> float:
    """
    Returns the most recent ATR value as a scalar float.
    df must have 'high', 'low', 'close' columns.
    Returns 0.0 if not enough rows.
    """
    if len(df) < period + 1:
        return 0.0
    high       = df["high"]
    low        = df["low"]
    close      = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(com=period - 1, min_periods=period).mean()
    return float(atr.iloc[-1])


def get_signal(df: pd.DataFrame, rsi_oversold: int, rsi_overbought: int,
               ema_fast: int, ema_slow: int, rsi_period: int) -> str:
    """
    Returns 'BUY', 'SELL', or 'HOLD'.
    df must have 'close' and 'volume' columns.
    Signature is unchanged from v1 — optimizer.py and backtest work with no changes.
    Feature gates are read from config flags.
    """
    # Minimum rows: need enough for RSI + MACD warm-up (whichever is larger)
    min_rows = max(rsi_period + 5, config.MACD_SLOW + config.MACD_SIGNAL + 5)
    if len(df) < min_rows:
        return "HOLD"

    rsi = compute_rsi(df["close"], rsi_period)
    prev_rsi    = rsi.iloc[-2]
    current_rsi = rsi.iloc[-1]

    # SELL: no new gates — open positions must always be able to exit
    if current_rsi >= rsi_overbought:
        return "SELL"

    # BUY prerequisite: RSI crosses upward through oversold threshold
    if not (prev_rsi < rsi_oversold and current_rsi >= rsi_oversold):
        return "HOLD"

    # Feature 1: EMA trend gate — only buy in uptrend
    if config.USE_EMA_GATE:
        ema_f = compute_ema(df["close"], ema_fast)
        ema_s = compute_ema(df["close"], ema_slow)
        if ema_f.iloc[-1] <= ema_s.iloc[-1]:
            return "HOLD"

    # Feature 3: MACD confirmation — only buy when momentum is positive
    if config.USE_MACD_CONFIRM:
        _, _, hist = compute_macd(
            df["close"],
            fast=config.MACD_FAST,
            slow=config.MACD_SLOW,
            signal_period=config.MACD_SIGNAL,
        )
        if hist.iloc[-1] <= 0:
            return "HOLD"

    # Feature 5: Volume confirmation — only buy on above-average participation
    if config.USE_VOLUME_CONFIRM:
        vol_ma = compute_ema(df["volume"], config.VOLUME_MA_PERIOD)
        if df["volume"].iloc[-1] <= vol_ma.iloc[-1] * config.VOLUME_MULTIPLIER:
            return "HOLD"

    return "BUY"
