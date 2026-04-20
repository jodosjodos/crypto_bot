#!/usr/bin/env python3
"""
Daily Report — prints a clean summary of today's activity.
Run manually anytime, or add to crontab to get a report every evening.

Usage:
    python3 daily_report.py
"""

import re
from collections import defaultdict
from datetime import datetime, timezone


LOG_FILE = "trades.log"


def parse_log():
    trades = []
    signals = []
    portfolio_snapshots = []

    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"No log file found at {LOG_FILE}. Start the bot first.")
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for line in lines:
        if today not in line:
            continue

        if "OPENED position" in line or "BOUGHT" in line:
            trades.append({"type": "open", "line": line.strip()})
        elif "CLOSED" in line or "SOLD" in line:
            pnl_match = re.search(r"PnL=([+-]?\$[\d.]+)\s*\(([+-]?[\d.]+)%\)", line)
            reason_match = re.search(r"\((\w+)\)", line)
            trades.append({
                "type":   "close",
                "pnl":    pnl_match.group(1) if pnl_match else "?",
                "pnl_pct": pnl_match.group(2) if pnl_match else "?",
                "reason": reason_match.group(1) if reason_match else "?",
                "line":   line.strip(),
            })
        elif "PORTFOLIO" in line:
            portfolio_snapshots.append(line.strip())
        elif "signal=" in line:
            sig_match = re.search(r"\[(\S+)\].*signal=(\w+)", line)
            if sig_match and sig_match.group(2) != "HOLD":
                signals.append(f"{sig_match.group(1)}: {sig_match.group(2)}")

    # Print report
    print("=" * 55)
    print(f"  DAILY TRADING REPORT — {today}")
    print("=" * 55)

    closed = [t for t in trades if t["type"] == "close"]
    opened = [t for t in trades if t["type"] == "open"]

    print(f"\n  Positions opened today:  {len(opened)}")
    print(f"  Positions closed today:  {len(closed)}")

    if closed:
        print("\n  Closed trades:")
        wins = losses = 0
        for t in closed:
            pct = t["pnl_pct"]
            tag = "WIN " if not pct.startswith("-") else "LOSS"
            if tag == "WIN ": wins += 1
            else: losses += 1
            print(f"    [{tag}] {t['pnl']} ({pct}%) — {t['reason']}")
        print(f"\n  Win rate today: {wins}/{wins+losses} = {int(wins/(wins+losses)*100) if wins+losses else 0}%")

    if signals:
        print(f"\n  Signals fired today:")
        for s in signals:
            print(f"    {s}")

    if portfolio_snapshots:
        print(f"\n  Latest portfolio snapshot:")
        print(f"    {portfolio_snapshots[-1].split('INFO')[-1].strip()}")

    print("\n  Log file: trades.log")
    print("  Config:   config.py")
    print("=" * 55)
    print("  Remember: past results do not guarantee future profit.")
    print("=" * 55)


if __name__ == "__main__":
    parse_log()
