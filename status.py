#!/usr/bin/env python3
"""
Quick status check — run anytime to see exactly what the bot is doing.
Usage: python3 status.py
"""

import json, os, sys
import ccxt
import config

STATE_FILE = "portfolio_state.json"

def main():
    # Check if bot process is running
    import subprocess
    running = subprocess.run(["pgrep", "-f", "bot.py"], capture_output=True).returncode == 0
    bot_status = "RUNNING ✓" if running else "STOPPED ✗  ← restart with: nohup python3 bot.py > bot_output.log 2>&1 &"

    # Load portfolio state
    if not os.path.exists(STATE_FILE):
        print()
        print("=" * 52)
        print("  BOT STATUS REPORT")
        print("=" * 52)
        print(f"  Bot process:   {bot_status}")
        print(f"  Trades:        None yet — bot is watching the market")
        print(f"  Mode:          PAPER TRADING (fake money)")
        print(f"  Starting cash: ${config.STARTING_CAPITAL:.2f}")
        print(f"  Strategy:      RSI({config.RSI_OVERSOLD}/{config.RSI_OVERBOUGHT}) — waits for price dip then buys recovery")
        print()
        print("  The bot fires a BUY only when RSI dips below")
        print(f"  {config.RSI_OVERSOLD} then recovers. This might take hours or days.")
        print("  That is normal — a patient bot beats a trigger-happy one.")
        print("=" * 52)
        print()
        sys.exit(0)

    with open(STATE_FILE) as f:
        state = json.load(f)

    cash           = state.get("cash", 0)
    positions      = state.get("positions", {})
    closed_trades  = state.get("closed_trades", [])

    # Get live prices
    try:
        ex = ccxt.kucoin({
            "apiKey": config.API_KEY, "secret": config.API_SECRET,
            "password": config.API_PASSPHRASE, "enableRateLimit": True,
        }) if config.API_KEY else ccxt.binance({"enableRateLimit": True})
        prices = {s: ex.fetch_ticker(s)["last"] for s in config.SYMBOLS}
    except Exception as e:
        prices = {}
        print(f"Warning: could not fetch live prices ({e})")

    # Calculate unrealised P&L on open positions
    unrealised = 0
    for sym, pos in positions.items():
        if sym in prices:
            unrealised += (prices[sym] - pos["entry_price"]) * pos["quantity"]

    total_value = cash + unrealised + sum(
        pos["entry_price"] * pos["quantity"] for pos in positions.values()
    )

    # Closed trade stats
    total_pnl = sum(t["pnl_usd"] for t in closed_trades)
    wins   = [t for t in closed_trades if t["pnl_usd"] > 0]
    losses = [t for t in closed_trades if t["pnl_usd"] <= 0]
    win_rate = (len(wins) / len(closed_trades) * 100) if closed_trades else 0

    print()
    print("=" * 52)
    print("  BOT STATUS REPORT")
    print("=" * 52)
    print(f"  Bot process:   {bot_status}")
    print(f"  Mode:          PAPER TRADING (fake money)")
    print(f"  Starting:      ${config.STARTING_CAPITAL:.2f}")
    print(f"  Cash left:     ${cash:.2f}")
    print(f"  Total value:   ${total_value:.2f}  ({total_value - config.STARTING_CAPITAL:+.2f} vs start)")
    print()
    print(f"  Open positions:   {len(positions)}")
    for sym, pos in positions.items():
        cur = prices.get(sym, 0)
        if cur:
            unreal = (cur - pos["entry_price"]) * pos["quantity"]
            pct    = (cur - pos["entry_price"]) / pos["entry_price"] * 100
            status = "PROFIT" if unreal >= 0 else "LOSS  "
            print(f"    {sym}")
            print(f"      Bought:  ${pos['entry_price']:,.2f}  |  Now: ${cur:,.2f}  ({pct:+.2f}%)")
            print(f"      P&L:     {status} ${unreal:+.4f}")
            print(f"      Stop:    ${pos['stop_loss']:,.2f}  |  Target: ${pos['take_profit']:,.2f}")
    print()
    print(f"  Closed trades:    {len(closed_trades)}")
    print(f"  Realised P&L:     ${total_pnl:+.4f}")
    print(f"  Win rate:         {win_rate:.1f}%  ({len(wins)}W / {len(losses)}L)")
    if closed_trades:
        best  = max(closed_trades, key=lambda t: t["pnl_usd"])
        worst = min(closed_trades, key=lambda t: t["pnl_usd"])
        print(f"  Best trade:       +${best['pnl_usd']:.4f} ({best['symbol']})")
        print(f"  Worst trade:      ${worst['pnl_usd']:.4f} ({worst['symbol']})")
    print("=" * 52)
    print()

if __name__ == "__main__":
    main()
