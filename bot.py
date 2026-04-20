#!/usr/bin/env python3
"""
Crypto Trading Bot — RSI + EMA Strategy
Paper trading by default (zero real money risk).

Usage:
    python bot.py              # run live (paper or real depending on config)
    python bot.py --backtest   # backtest on recent historical data
"""

import argparse
import logging
import sys
import time
from datetime import datetime

import ccxt
import pandas as pd

import config
from paper_trader import Portfolio
from live_trader import LiveTrader
from strategy import get_signal, compute_atr_value

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOG_FILE),
    ],
)
logger = logging.getLogger("bot")


# ── Exchange setup ─────────────────────────────────────────────────────────────
def get_exchange() -> ccxt.Exchange:
    creds = {
        "apiKey":  config.API_KEY,
        "secret":  config.API_SECRET,
        "enableRateLimit": True,
    }
    if config.EXCHANGE == "kucoin":
        creds["password"] = config.API_PASSPHRASE   # KuCoin needs this
        exchange = ccxt.kucoin(creds)
    else:
        creds["options"] = {"defaultType": "spot"}
        exchange = ccxt.binance(creds)
    return exchange


def fetch_ohlcv(exchange: ccxt.Exchange, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df


# ── Main loop ──────────────────────────────────────────────────────────────────
def run_bot():
    mode = "PAPER TRADING" if config.PAPER_TRADING else "LIVE TRADING"
    logger.info("=" * 60)
    logger.info(f"  Bot starting  |  Mode: {mode}")
    logger.info(f"  Capital: ${config.STARTING_CAPITAL:.2f}  |  Symbols: {config.SYMBOLS}")
    logger.info("=" * 60)

    if not config.PAPER_TRADING and (not config.API_KEY or not config.API_SECRET):
        logger.error("Live trading requires API_KEY and API_SECRET in config.py")
        sys.exit(1)

    exchange = get_exchange()
    interval_seconds = _timeframe_to_seconds(config.CANDLE_INTERVAL)

    if config.PAPER_TRADING:
        trader = Portfolio()
    else:
        trader = LiveTrader(exchange, logger)
        logger.warning("LIVE TRADING ACTIVE — real money at risk")

    while True:
        try:
            for symbol in config.SYMBOLS:
                df = fetch_ohlcv(exchange, symbol, config.CANDLE_INTERVAL)
                current_price = df["close"].iloc[-1]

                signal = get_signal(
                    df,
                    rsi_oversold=config.RSI_OVERSOLD,
                    rsi_overbought=config.RSI_OVERBOUGHT,
                    ema_fast=config.EMA_FAST,
                    ema_slow=config.EMA_SLOW,
                    rsi_period=config.RSI_PERIOD,
                )

                logger.info(f"[{symbol}] price=${current_price:.4f}  signal={signal}")

                if config.PAPER_TRADING:
                    trader.check_exits(symbol, current_price, signal, logger)
                    if signal == "BUY":
                        # Feature 2: circuit breaker check
                        paused, reason = trader.is_trading_paused(symbol)
                        if paused:
                            logger.info(f"[{symbol}] BUY blocked — {reason}")
                        else:
                            # Feature 4: compute ATR and pass to open_position
                            atr = compute_atr_value(df, config.ATR_PERIOD) if config.USE_ATR_EXITS else None
                            trader.open_position(symbol, current_price, signal, logger, atr=atr)
                else:
                    trader.check_exits(symbol, current_price, signal)
                    if signal == "BUY":
                        trader.open_position(symbol, signal)

            # Print summary every cycle
            summary = trader.summary()
            if config.PAPER_TRADING:
                logger.info(
                    f"  PORTFOLIO | cash=${summary['cash']:.2f} | "
                    f"open={summary['open_positions']} | "
                    f"closed={summary['closed_trades']} | "
                    f"PnL=${summary['total_pnl_usd']:+.4f} | "
                    f"win_rate={summary['win_rate_pct']}%"
                )
                # Show each open position with current P&L
                for sym, pos in trader.positions.items():
                    cur = df["close"].iloc[-1] if sym == symbol else None
                    if cur:
                        unreal_pnl = (cur - pos.entry_price) * pos.quantity
                        logger.info(
                            f"    {sym} | entry=${pos.entry_price:.2f} | "
                            f"now=${cur:.2f} | unrealised=${unreal_pnl:+.4f} | "
                            f"SL=${pos.stop_loss:.2f} | TP=${pos.take_profit:.2f}"
                        )
            else:
                logger.info(
                    f"  LIVE ACCOUNT | balance=${summary['usdt_balance']:.2f} | "
                    f"trades={summary['closed_trades']} | "
                    f"PnL=${summary['total_pnl_usd']:+.4f} | "
                    f"win_rate={summary['win_rate_pct']}%"
                )

        except ccxt.NetworkError as e:
            logger.error(f"Network error: {e} — retrying in 30s")
            time.sleep(30)
            continue
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error: {e}")
            time.sleep(60)
            continue
        except KeyboardInterrupt:
            logger.info("Bot stopped by user.")
            summary = trader.summary()
            logger.info(f"Final summary: {summary}")
            break
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            time.sleep(30)
            continue

        logger.info(f"Sleeping {interval_seconds}s until next candle...")
        time.sleep(interval_seconds)


# ── Backtest ───────────────────────────────────────────────────────────────────
def run_backtest():
    logger.info("Running backtest on last 500 candles...")
    exchange = get_exchange()
    portfolio = Portfolio()

    for symbol in config.SYMBOLS:
        df = fetch_ohlcv(exchange, symbol, config.CANDLE_INTERVAL, limit=500)
        min_rows = config.RSI_PERIOD + config.EMA_SLOW + 10

        for i in range(min_rows, len(df)):
            window = df.iloc[:i].copy()
            current_price = window["close"].iloc[-1]

            signal = get_signal(
                window,
                rsi_oversold=config.RSI_OVERSOLD,
                rsi_overbought=config.RSI_OVERBOUGHT,
                ema_fast=config.EMA_FAST,
                ema_slow=config.EMA_SLOW,
                rsi_period=config.RSI_PERIOD,
            )

            portfolio.check_exits(symbol, current_price, signal, logger)
            if signal == "BUY":
                atr = compute_atr_value(window, config.ATR_PERIOD) if config.USE_ATR_EXITS else None
                portfolio.open_position(symbol, current_price, signal, logger, atr=atr)

    summary = portfolio.summary()
    logger.info("=" * 50)
    logger.info("BACKTEST RESULTS")
    logger.info("=" * 50)
    for k, v in summary.items():
        logger.info(f"  {k}: {v}")
    logger.info(f"  starting_capital: ${config.STARTING_CAPITAL:.2f}")
    logger.info(f"  final_cash:       ${summary['cash']:.2f}")
    logger.info("=" * 50)
    logger.warning("Past performance does NOT predict future results.")


# ── Helpers ────────────────────────────────────────────────────────────────────
def _timeframe_to_seconds(tf: str) -> int:
    mapping = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400}
    return mapping.get(tf, 900)


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crypto Trading Bot")
    parser.add_argument("--backtest", action="store_true", help="Run backtest on historical data")
    args = parser.parse_args()

    if args.backtest:
        run_backtest()
    else:
        run_bot()
