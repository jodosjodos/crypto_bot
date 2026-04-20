#!/usr/bin/env python3
"""
Daily Parameter Optimizer
---------------------------
Runs every day. Tests hundreds of parameter combinations on recent market data,
finds the best-performing set, and updates config.py automatically.

Usage:
    python3 optimizer.py              # optimize and update config
    python3 optimizer.py --dry-run    # optimize but DON'T update config (just print)

What it optimizes:
  - RSI oversold threshold  (20–40)
  - RSI overbought threshold (60–80)
  - EMA fast period (5–15)
  - EMA slow period (15–30)
  - Stop loss % (1–3%)
  - Take profit % (2–6%)
"""

import argparse
import itertools
import logging
import sys
from dataclasses import dataclass
from typing import Optional

import ccxt
import pandas as pd

import config
from paper_trader import Portfolio
from strategy import get_signal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("optimizer")


@dataclass
class Params:
    rsi_oversold:    int
    rsi_overbought:  int
    ema_fast:        int
    ema_slow:        int
    stop_loss_pct:   float
    take_profit_pct: float


@dataclass
class Result:
    params: Params
    total_pnl:  float
    win_rate:   float
    num_trades: int
    score:      float   # composite: pnl * win_rate * sqrt(trades)


def backtest_params(df: pd.DataFrame, params: Params, capital: float) -> Result:
    portfolio = Portfolio.__new__(Portfolio)
    portfolio.cash = capital
    portfolio.positions = {}
    portfolio.closed_trades = []

    # Monkey-patch config values for this run
    import config as cfg
    orig = (cfg.STOP_LOSS_PCT, cfg.TAKE_PROFIT_PCT, cfg.MAX_POSITION_PCT, cfg.MAX_OPEN_TRADES)
    cfg.STOP_LOSS_PCT   = params.stop_loss_pct
    cfg.TAKE_PROFIT_PCT = params.take_profit_pct

    min_rows = params.rsi_oversold + params.ema_slow + 10  # rough min data needed
    min_rows = max(min_rows, 40)

    import logging
    null_logger = logging.getLogger("null")
    null_logger.addHandler(logging.NullHandler())
    null_logger.propagate = False

    for i in range(min_rows, len(df)):
        window = df.iloc[:i]
        price = window["close"].iloc[-1]
        signal = get_signal(
            window,
            rsi_oversold=params.rsi_oversold,
            rsi_overbought=params.rsi_overbought,
            ema_fast=params.ema_fast,
            ema_slow=params.ema_slow,
            rsi_period=14,
        )
        portfolio.check_exits("SYM", price, signal, null_logger)
        if signal == "BUY":
            portfolio.open_position("SYM", price, signal, null_logger)

    # Restore config
    cfg.STOP_LOSS_PCT, cfg.TAKE_PROFIT_PCT, cfg.MAX_POSITION_PCT, cfg.MAX_OPEN_TRADES = orig

    summary = portfolio.summary()
    pnl     = summary["total_pnl_usd"]
    wr      = summary["win_rate_pct"] / 100
    n       = summary["closed_trades"]

    # Score: reward profit AND win rate AND number of trades (need at least 2 trades to score)
    score = 0.0
    if n >= 2 and pnl > 0:
        score = pnl * wr * (n ** 0.5)

    return Result(params=params, total_pnl=pnl, win_rate=wr * 100, num_trades=n, score=score)


def fetch_data(symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
    exchange = ccxt.binance({"enableRateLimit": True})
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df


def update_config(best: Params):
    """Rewrite key lines in config.py with the best parameters."""
    with open("config.py", "r") as f:
        content = f.read()

    replacements = {
        "RSI_OVERSOLD":    best.rsi_oversold,
        "RSI_OVERBOUGHT":  best.rsi_overbought,
        "EMA_FAST":        best.ema_fast,
        "EMA_SLOW":        best.ema_slow,
        "STOP_LOSS_PCT":   best.stop_loss_pct,
        "TAKE_PROFIT_PCT": best.take_profit_pct,
    }

    import re
    for key, val in replacements.items():
        pattern = rf"^({key}\s*=\s*)[\d.]+(.*)$"
        replacement = rf"\g<1>{val}\2"
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

    with open("config.py", "w") as f:
        f.write(content)


def run_optimizer(dry_run: bool = False):
    logger.info("=" * 60)
    logger.info("Daily Optimizer — searching best parameters")
    logger.info("=" * 60)

    # Fetch data for both symbols, concatenate for a broader test
    logger.info("Fetching market data...")
    dfs = []
    for sym in config.SYMBOLS:
        try:
            df = fetch_data(sym, config.CANDLE_INTERVAL, limit=500)
            dfs.append(df)
            logger.info(f"  {sym}: {len(df)} candles loaded")
        except Exception as e:
            logger.warning(f"  {sym}: failed ({e})")

    if not dfs:
        logger.error("No data fetched. Check internet connection.")
        sys.exit(1)

    # Parameter search space
    rsi_oversold_vals    = [30, 33, 35, 38, 40]
    rsi_overbought_vals  = [60, 62, 65, 67, 70]
    ema_fast_vals        = [7, 9, 12]
    ema_slow_vals        = [18, 21, 26]
    stop_loss_vals       = [0.015, 0.02, 0.025]
    take_profit_vals     = [0.03, 0.04, 0.05]

    combos = list(itertools.product(
        rsi_oversold_vals, rsi_overbought_vals,
        ema_fast_vals, ema_slow_vals,
        stop_loss_vals, take_profit_vals,
    ))
    # Filter invalid (fast >= slow)
    combos = [c for c in combos if c[2] < c[3] and c[0] < c[1]]

    logger.info(f"Testing {len(combos)} parameter combinations...")

    best: Optional[Result] = None
    tested = 0

    for (ro, rob, ef, es, sl, tp) in combos:
        params = Params(
            rsi_oversold=ro, rsi_overbought=rob,
            ema_fast=ef, ema_slow=es,
            stop_loss_pct=sl, take_profit_pct=tp,
        )
        # Average score across all symbols
        scores = []
        for df in dfs:
            r = backtest_params(df, params, capital=config.STARTING_CAPITAL)
            scores.append(r)

        avg_score = sum(s.score for s in scores) / len(scores)
        avg_pnl   = sum(s.total_pnl for s in scores) / len(scores)
        avg_wr    = sum(s.win_rate for s in scores) / len(scores)
        avg_n     = sum(s.num_trades for s in scores) / len(scores)

        result = Result(params=params, total_pnl=avg_pnl, win_rate=avg_wr,
                        num_trades=int(avg_n), score=avg_score)

        if best is None or result.score > best.score:
            best = result
            logger.info(
                f"  New best: RSI({ro}/{rob}) EMA({ef}/{es}) "
                f"SL={sl*100:.1f}% TP={tp*100:.1f}% | "
                f"PnL=${avg_pnl:.3f} WR={avg_wr:.1f}% n={int(avg_n)} score={avg_score:.4f}"
            )

        tested += 1
        if tested % 50 == 0:
            logger.info(f"  Progress: {tested}/{len(combos)}")

    logger.info("=" * 60)
    logger.info("OPTIMIZATION COMPLETE")
    logger.info("=" * 60)
    if best:
        logger.info(f"  Best RSI oversold:    {best.params.rsi_oversold}")
        logger.info(f"  Best RSI overbought:  {best.params.rsi_overbought}")
        logger.info(f"  Best EMA fast:        {best.params.ema_fast}")
        logger.info(f"  Best EMA slow:        {best.params.ema_slow}")
        logger.info(f"  Best stop loss:       {best.params.stop_loss_pct*100:.1f}%")
        logger.info(f"  Best take profit:     {best.params.take_profit_pct*100:.1f}%")
        logger.info(f"  Avg trades:           {best.num_trades}")
        logger.info(f"  Avg win rate:         {best.win_rate:.1f}%")
        logger.info(f"  Avg PnL:              ${best.total_pnl:.4f}")
        logger.info("=" * 60)
        logger.warning("These are best params on RECENT data. May not predict future.")

        if dry_run:
            logger.info("Dry run — config.py NOT updated.")
        else:
            update_config(best.params)
            logger.info("config.py updated with best parameters.")
    else:
        logger.warning("No valid parameter set found (need >= 5 trades to score).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily parameter optimizer")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run optimization but do not update config.py")
    args = parser.parse_args()
    run_optimizer(dry_run=args.dry_run)
