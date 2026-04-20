"""
Live Trader — executes real orders on Binance.
Only used when PAPER_TRADING = False in config.py.

Safety rules enforced here:
  - Market orders only (fills immediately, no slippage risk from limit orders timing out)
  - Position size capped at MAX_POSITION_PCT of portfolio
  - Max open trades enforced
  - Stop loss and take profit are tracked in software (not exchange orders) to avoid
    partial-fill edge cases on small accounts
"""

import logging
from datetime import datetime
from typing import Dict, Optional

import ccxt

import config


class LivePosition:
    def __init__(self, symbol: str, entry_price: float, quantity: float,
                 stop_loss: float, take_profit: float):
        self.symbol      = symbol
        self.entry_price = entry_price
        self.quantity    = quantity
        self.stop_loss   = stop_loss
        self.take_profit = take_profit
        self.opened_at   = datetime.utcnow().isoformat()


class LiveTrader:
    def __init__(self, exchange: ccxt.Exchange, logger: logging.Logger):
        self.exchange  = exchange
        self.logger    = logger
        self.positions: Dict[str, LivePosition] = {}
        self.closed_trades = []

    def get_balance(self) -> float:
        """Return available USDT balance."""
        balance = self.exchange.fetch_balance()
        return float(balance["USDT"]["free"])

    def get_current_price(self, symbol: str) -> float:
        ticker = self.exchange.fetch_ticker(symbol)
        return float(ticker["last"])

    def open_position(self, symbol: str, signal: str):
        if symbol in self.positions:
            self.logger.info(f"[{symbol}] Already in position, skipping BUY")
            return
        if len(self.positions) >= config.MAX_OPEN_TRADES:
            self.logger.info(f"[{symbol}] Max open trades reached, skipping BUY")
            return

        usdt_balance = self.get_balance()
        allocation   = usdt_balance * config.MAX_POSITION_PCT

        if allocation < 5.0:
            self.logger.warning(f"[{symbol}] Allocation too small (${allocation:.2f}), need at least $5")
            return

        # Place market buy order
        base_currency = symbol.split("/")[0]
        current_price = self.get_current_price(symbol)
        quantity = allocation / current_price

        # Round quantity to exchange precision
        market = self.exchange.market(symbol)
        quantity = self.exchange.amount_to_precision(symbol, quantity)

        self.logger.info(f"[{symbol}] Placing BUY order: qty={quantity} @ ~${current_price:.4f}")

        try:
            order = self.exchange.create_market_buy_order(symbol, quantity)
            fill_price = float(order.get("average") or order.get("price") or current_price)
            filled_qty = float(order.get("filled") or quantity)

            stop_loss   = fill_price * (1 - config.STOP_LOSS_PCT)
            take_profit = fill_price * (1 + config.TAKE_PROFIT_PCT)

            self.positions[symbol] = LivePosition(
                symbol=symbol,
                entry_price=fill_price,
                quantity=filled_qty,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

            self.logger.info(
                f"[{symbol}] BOUGHT {filled_qty} @ ${fill_price:.4f} | "
                f"SL=${stop_loss:.4f} | TP=${take_profit:.4f}"
            )

        except ccxt.InsufficientFunds as e:
            self.logger.error(f"[{symbol}] Insufficient funds: {e}")
        except ccxt.ExchangeError as e:
            self.logger.error(f"[{symbol}] Exchange error on buy: {e}")

    def check_exits(self, symbol: str, current_price: float, signal: str):
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        reason = None

        if current_price <= pos.stop_loss:
            reason = "STOP_LOSS"
        elif current_price >= pos.take_profit:
            reason = "TAKE_PROFIT"
        elif signal == "SELL":
            reason = "STRATEGY_SELL"

        if not reason:
            return

        # Place market sell order
        quantity = self.exchange.amount_to_precision(symbol, pos.quantity)
        self.logger.info(f"[{symbol}] Placing SELL order ({reason}): qty={quantity} @ ~${current_price:.4f}")

        try:
            order = self.exchange.create_market_sell_order(symbol, quantity)
            fill_price = float(order.get("average") or order.get("price") or current_price)
            filled_qty = float(order.get("filled") or pos.quantity)

            pnl     = (fill_price - pos.entry_price) * filled_qty
            pnl_pct = ((fill_price - pos.entry_price) / pos.entry_price) * 100

            trade = {
                "symbol":    symbol,
                "entry":     pos.entry_price,
                "exit":      fill_price,
                "quantity":  filled_qty,
                "pnl_usd":   round(pnl, 4),
                "pnl_pct":   round(pnl_pct, 2),
                "reason":    reason,
                "opened_at": pos.opened_at,
                "closed_at": datetime.utcnow().isoformat(),
            }
            self.closed_trades.append(trade)
            del self.positions[symbol]

            sign = "+" if pnl >= 0 else ""
            self.logger.info(
                f"[{symbol}] SOLD ({reason}) @ ${fill_price:.4f} | "
                f"PnL={sign}${pnl:.4f} ({pnl_pct:+.2f}%)"
            )

        except ccxt.ExchangeError as e:
            self.logger.error(f"[{symbol}] Exchange error on sell: {e}")

    def summary(self) -> dict:
        total_pnl = sum(t["pnl_usd"] for t in self.closed_trades)
        wins   = [t for t in self.closed_trades if t["pnl_usd"] > 0]
        losses = [t for t in self.closed_trades if t["pnl_usd"] <= 0]
        win_rate = (len(wins) / len(self.closed_trades) * 100) if self.closed_trades else 0
        balance = self.get_balance()

        return {
            "usdt_balance":   round(balance, 4),
            "open_positions": len(self.positions),
            "closed_trades":  len(self.closed_trades),
            "total_pnl_usd":  round(total_pnl, 4),
            "win_rate_pct":   round(win_rate, 1),
            "wins":           len(wins),
            "losses":         len(losses),
        }
