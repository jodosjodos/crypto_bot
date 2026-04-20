"""
Paper Trader — simulates trades with fake money.
Tracks portfolio, open positions, P&L, and logs every action.
State is saved to disk so restarts don't lose open positions.

New in v2:
  - Circuit breaker: pauses trading after N consecutive losses,
    daily loss limit, and per-symbol cooldown (Feature 2)
  - ATR-based SL/TP via optional atr param in open_position() (Feature 4)
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple

import config

STATE_FILE = "portfolio_state.json"


@dataclass
class Position:
    symbol: str
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    opened_at: str


class Portfolio:
    def __init__(self):
        self.cash: float = config.STARTING_CAPITAL
        self.positions: Dict[str, Position] = {}
        self.closed_trades: list = []
        self._last_closed: Dict[str, datetime] = {}   # in-memory only, never persisted
        self._load_state()
        self._rebuild_last_closed()

    def _load_state(self):
        """Load saved state from disk so restarts don't lose positions."""
        if not os.path.exists(STATE_FILE):
            return
        try:
            with open(STATE_FILE) as f:
                data = json.load(f)
            self.cash = data.get("cash", config.STARTING_CAPITAL)
            self.closed_trades = data.get("closed_trades", [])
            for sym, p in data.get("positions", {}).items():
                self.positions[sym] = Position(**p)
            print(f"[STATE] Restored: cash=${self.cash:.2f}, "
                  f"open={len(self.positions)}, closed={len(self.closed_trades)}")
        except Exception as e:
            print(f"[STATE] Could not load state: {e} — starting fresh")

    def _rebuild_last_closed(self):
        """Reconstruct cooldown state from saved trade history after restart."""
        for trade in self.closed_trades:
            sym = trade["symbol"]
            try:
                closed_at = datetime.fromisoformat(trade["closed_at"])
                if sym not in self._last_closed or closed_at > self._last_closed[sym]:
                    self._last_closed[sym] = closed_at
            except (KeyError, ValueError):
                pass

    def _save_state(self):
        """Save current state to disk."""
        data = {
            "cash": self.cash,
            "closed_trades": self.closed_trades,
            "positions": {
                sym: {
                    "symbol": p.symbol, "entry_price": p.entry_price,
                    "quantity": p.quantity, "stop_loss": p.stop_loss,
                    "take_profit": p.take_profit, "opened_at": p.opened_at,
                }
                for sym, p in self.positions.items()
            },
        }
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, indent=2)

    @property
    def total_value(self) -> float:
        return self.cash

    # ── Circuit Breaker ────────────────────────────────────────────────────────

    def is_trading_paused(self, symbol: str) -> Tuple[bool, str]:
        """
        Returns (paused: bool, reason: str).
        Called by bot.py before open_position() on every BUY signal.
        Returns (False, "") when USE_CIRCUIT_BREAKER is False.
        """
        if not config.USE_CIRCUIT_BREAKER:
            return False, ""

        now = datetime.utcnow()

        # 1. Consecutive loss streak (portfolio-wide)
        consecutive = 0
        for trade in reversed(self.closed_trades):
            if trade["pnl_usd"] < 0:
                consecutive += 1
            else:
                break
        if consecutive >= config.MAX_CONSECUTIVE_LOSSES:
            return True, (f"Circuit breaker: {consecutive} consecutive losses "
                          f"— waiting for market to recover")

        # 2. Daily loss limit
        today_str = now.strftime("%Y-%m-%d")
        daily_pnl = sum(
            t["pnl_usd"] for t in self.closed_trades
            if t.get("closed_at", "").startswith(today_str)
        )
        daily_pnl_pct = (daily_pnl / config.STARTING_CAPITAL) * 100
        if daily_pnl_pct < -config.MAX_DAILY_LOSS_PCT:
            return True, (f"Daily loss limit hit ({daily_pnl_pct:.1f}%) "
                          f"— no more trades today")

        # 3. Per-symbol cooldown (minimum time between trades on same symbol)
        if symbol in self._last_closed:
            elapsed_minutes = (now - self._last_closed[symbol]).total_seconds() / 60
            if elapsed_minutes < config.COOLDOWN_MINUTES:
                remaining = config.COOLDOWN_MINUTES - elapsed_minutes
                return True, f"Cooldown: {remaining:.1f}min remaining for {symbol}"

        return False, ""

    # ── Position Management ────────────────────────────────────────────────────

    def open_position(self, symbol: str, price: float, signal: str,
                      logger: logging.Logger, atr: float = None):
        """
        Open a new position.
        atr: optional ATR value for volatility-adaptive SL/TP (Feature 4).
             If provided and USE_ATR_EXITS=True, uses ATR-based levels.
             Default None keeps backward compatibility with optimizer.py (4-arg call).
        """
        if symbol in self.positions:
            return
        if len(self.positions) >= config.MAX_OPEN_TRADES:
            logger.info(f"[{symbol}] Max open trades reached, skipping BUY")
            return

        # Use STARTING_CAPITAL for sizing so each trade gets equal allocation
        # regardless of how much cash is left
        allocation = config.STARTING_CAPITAL * config.MAX_POSITION_PCT
        if self.cash < allocation:
            allocation = self.cash  # use whatever is left if not enough
        if allocation < 1.0:
            logger.warning(f"[{symbol}] Not enough cash to open position (${self.cash:.2f})")
            return

        quantity = allocation / price

        # Feature 4: ATR-based or fixed % SL/TP
        if atr and config.USE_ATR_EXITS and atr > 0:
            stop_loss   = max(price - atr * config.ATR_SL_MULT, price * 0.001)
            take_profit = price + atr * config.ATR_TP_MULT
            sl_tp_mode  = f"ATR={atr:.2f}"
        else:
            stop_loss   = price * (1 - config.STOP_LOSS_PCT)
            take_profit = price * (1 + config.TAKE_PROFIT_PCT)
            sl_tp_mode  = "fixed%"

        self.positions[symbol] = Position(
            symbol=symbol,
            entry_price=price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            opened_at=datetime.utcnow().isoformat(),
        )
        self.cash -= allocation
        self._save_state()

        logger.info(
            f"[{symbol}] OPENED position | price=${price:.4f} | qty={quantity:.6f} "
            f"| SL=${stop_loss:.4f} | TP=${take_profit:.4f} "
            f"| exits={sl_tp_mode} | cash=${self.cash:.2f}"
        )

    def check_exits(self, symbol: str, current_price: float, signal: str,
                    logger: logging.Logger):
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

        if reason:
            proceeds = pos.quantity * current_price
            pnl = proceeds - (pos.quantity * pos.entry_price)
            pnl_pct = (pnl / (pos.quantity * pos.entry_price)) * 100
            self.cash += proceeds

            trade_record = {
                "symbol": symbol,
                "entry": pos.entry_price,
                "exit": current_price,
                "quantity": pos.quantity,
                "pnl_usd": round(pnl, 4),
                "pnl_pct": round(pnl_pct, 2),
                "reason": reason,
                "opened_at": pos.opened_at,
                "closed_at": datetime.utcnow().isoformat(),
            }
            self.closed_trades.append(trade_record)
            del self.positions[symbol]

            # Update cooldown tracker (guard: optimizer uses __new__ without __init__)
            if hasattr(self, '_last_closed'):
                self._last_closed[symbol] = datetime.utcnow()

            self._save_state()

            emoji = "+" if pnl >= 0 else "-"
            logger.info(
                f"[{symbol}] CLOSED ({reason}) | exit=${current_price:.4f} "
                f"| PnL={emoji}${abs(pnl):.4f} ({pnl_pct:+.2f}%) | cash=${self.cash:.2f}"
            )

    def summary(self) -> dict:
        total_pnl = sum(t["pnl_usd"] for t in self.closed_trades)
        wins   = [t for t in self.closed_trades if t["pnl_usd"] > 0]
        losses = [t for t in self.closed_trades if t["pnl_usd"] <= 0]
        win_rate = (len(wins) / len(self.closed_trades) * 100) if self.closed_trades else 0

        return {
            "cash": round(self.cash, 4),
            "open_positions": len(self.positions),
            "closed_trades": len(self.closed_trades),
            "total_pnl_usd": round(total_pnl, 4),
            "win_rate_pct": round(win_rate, 1),
            "wins": len(wins),
            "losses": len(losses),
        }
