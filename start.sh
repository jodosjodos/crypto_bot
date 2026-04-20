#!/bin/bash
# Safe bot starter — always kills existing processes before starting a new one
cd /Users/jodos/Documents/codes/EXPERIMENTS/bots
source venv/bin/activate

# Kill any existing bot processes
PIDS=$(ps aux | grep "bot.py" | grep -v grep | awk '{print $2}')
if [ -n "$PIDS" ]; then
    echo "Stopping existing bot processes: $PIDS"
    kill $PIDS 2>/dev/null
    sleep 2
fi

# Confirm all dead
REMAINING=$(ps aux | grep "bot.py" | grep -v grep | wc -l | tr -d ' ')
if [ "$REMAINING" -gt "0" ]; then
    echo "Force killing..."
    kill -9 $PIDS 2>/dev/null
    sleep 1
fi

echo "Starting fresh bot..."
nohup python3 bot.py > bot_output.log 2>&1 &
echo "Bot started. PID: $!"
echo "Run 'python3 status.py' to check status"
