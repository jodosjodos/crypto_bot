"""
Strategy: RSI Crossover (Recovery / Exhaustion)
-------------------------------------------------
BUY  when: RSI crosses UPWARD through the oversold threshold
           — price was beaten down too hard, market is recovering

SELL when: RSI crosses UPWARD through the overbought threshold
           — price has run up too hard, market is overheated
       OR: stop-loss / take-profit hit (handled by paper_trader.py)

Why crossover (not just "RSI < X"):
  - Entering ON the cross gives a timing signal, not just a zone
  - Avoids holding a position while RSI stays oversold for many candles (catching a falling knife)
  - "Wait for confirmation" is standard in RSI strategies

Defaults: oversold=35, overbought=65 (wider than classic 30/70 to get enough signals)
"""

import pandas as pd


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


def get_signal(df: pd.DataFrame, rsi_oversold: int, rsi_overbought: int,
               ema_fast: int, ema_slow: int, rsi_period: int) -> str:
    """
    Returns 'BUY', 'SELL', or 'HOLD'.
    df must have a 'close' column with at least (rsi_period + 5) rows.
    """
    if len(df) < rsi_period + 5:
        return "HOLD"

    rsi = compute_rsi(df["close"], rsi_period)

    prev_rsi    = rsi.iloc[-2]
    current_rsi = rsi.iloc[-1]

    # BUY: RSI crosses upward through oversold threshold (recovery confirmed)
    if prev_rsi < rsi_oversold and current_rsi >= rsi_oversold:
        return "BUY"

    # SELL: RSI crosses upward through overbought threshold (exhaustion signal)
    if prev_rsi < rsi_overbought and current_rsi >= rsi_overbought:
        return "SELL"

    return "HOLD"
