# Trading Bot — Setup Guide

## Before anything else — read this

This bot uses **paper trading by default** (fake money). It will not touch
real money until you deliberately change `PAPER_TRADING = False` in config.py.

Trading involves **real risk of loss**. Never invest money you cannot afford
to lose entirely. This bot is for learning.

---

## Step 1 — Install Python

You need Python 3.9 or newer.

Check if you have it:
```
python3 --version
```

If not, download from: https://www.python.org/downloads/

---

## Step 2 — Install dependencies

Open your terminal in the `bots/` folder and run:

```bash
pip3 install -r requirements.txt
```

This installs:
- `ccxt` — connects to Binance to get live price data (read-only in paper mode)
- `pandas` — for price calculations

---

## Step 3 — Run the backtest first

Before running live, test the strategy on historical data:

```bash
python3 bot.py --backtest
```

This downloads the last 500 candles (no account needed) and shows you:
- How many trades would have been made
- Win rate
- Total profit/loss on paper

**Read the results carefully.** If the backtest shows losses, the live bot
will likely also lose on real money.

---

## Step 4 — Run in paper trading mode (recommended for weeks/months)

```bash
python3 bot.py
```

The bot will:
- Check BTC/USDT and ETH/USDT every 15 minutes
- Print every signal and trade to the terminal AND to `trades.log`
- Never spend real money (PAPER_TRADING = True in config.py)

Let it run for at least 2–4 weeks before evaluating performance.
Press `Ctrl+C` to stop it safely — it prints a final summary.

---

## Step 5 — Keep it running 24/7 (optional)

On Mac, use `screen` or `nohup`:

```bash
# Option A: nohup (simplest)
nohup python3 bot.py > bot_output.log 2>&1 &

# Option B: screen (you can reattach later)
screen -S tradingbot
python3 bot.py
# Press Ctrl+A then D to detach. Run 'screen -r tradingbot' to reattach.
```

---

## Step 6 — Monitor your trades

View the trade log:
```bash
cat trades.log
```

The log shows every signal checked, every trade opened/closed, and portfolio
summaries. Look for patterns in wins vs losses.

---

## What the strategy does

| Indicator | What it measures | Used for |
|-----------|-----------------|----------|
| RSI (14)  | Whether price is oversold or overbought | Timing entries/exits |
| EMA 9     | Fast moving average | Detecting momentum direction |
| EMA 21    | Slow moving average | Confirming trend |

**BUY signal:** RSI below 30 (oversold) AND fast EMA crosses above slow EMA
**SELL signal:** RSI above 70 (overbought) AND fast EMA crosses below slow EMA
**Stop loss:** 2% below entry price (exits automatically to limit loss)
**Take profit:** 4% above entry price (locks in gains)

---

## Adjusting settings (config.py)

| Setting | Default | What it does |
|---------|---------|--------------|
| `STARTING_CAPITAL` | 50.0 | Simulated starting cash |
| `RSI_OVERSOLD` | 30 | Lower = fewer but stronger buy signals |
| `RSI_OVERBOUGHT` | 70 | Higher = fewer but stronger sell signals |
| `STOP_LOSS_PCT` | 0.02 | 2% — increase to give more room, lose more |
| `TAKE_PROFIT_PCT` | 0.04 | 4% — your profit target per trade |
| `CANDLE_INTERVAL` | "15m" | How often to check ("5m", "1h", "4h" etc) |

---

## Going live (only after extensive paper testing)

1. Create a Binance account
2. Enable API access in your Binance account settings
3. Create a **Spot trading only** API key (do NOT enable withdrawals)
4. In `config.py`: set `API_KEY` and `API_SECRET`, then set `PAPER_TRADING = False`

**Start with a tiny amount you are 100% willing to lose completely.**

---

## Honest expectations

- This strategy will have losing trades. That is normal.
- No strategy wins every trade. Professional traders aim for 50–60% win rate.
- Past backtest results do not guarantee future profits.
- Crypto markets are highly volatile.
- Only risk money you can afford to lose entirely.
