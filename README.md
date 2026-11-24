# Alpaca Trading Agent

An autonomous stock-trading agent for an Alpaca **paper trading** account, run as a Render cron job every 15 minutes during US market hours.

## What it does each run
1. Checks Alpaca's market clock and exits if the market is closed.
2. Reads the account, open positions and open orders.
3. Pulls ~150 days of daily bars for the watchlist and anything it holds.
4. **Sells** a position on stop-loss (-5%), take-profit (+12%), price falling below its 20-day average, or RSI above 80.
5. **Buys** stocks in an uptrend (price above 50-day avg, 20-day above 50-day, RSI 50–70), strongest 20-day momentum first.
6. Logs every decision as one JSON line (Render → service → Logs).

## Risk limits (Render env vars)
| Variable | Default | Meaning |
|---|---|---|
| `MAX_POSITION_PCT` | 0.10 | Max size of one position, share of equity |
| `MAX_POSITIONS` | 5 | Max number of stocks held |
| `MAX_INVESTED_PCT` | 0.80 | Always keep at least 20% cash |
| `STOP_LOSS_PCT` | 0.05 | Sell at -5% |
| `TAKE_PROFIT_PCT` | 0.12 | Sell at +12% |
| `DAILY_LOSS_LIMIT_PCT` | 0.03 | No new buys after a -3% day |
| `WATCHLIST` | SPY,QQQ,… | Symbols it may buy |
| `DRY_RUN` | false | `true` = log decisions, place no orders |
| `ALLOW_LIVE_TRADING` | false | Must be `true` before a live (non-paper) URL is accepted |

## Deploy
1. In Alpaca (Paper account) → Home → **API Keys** → Generate. Copy the Key ID and Secret.
2. In Render → **New → Blueprint** → pick this repo. Render reads `render.yaml`.
3. Paste the key into `ALPACA_API_KEY_ID` and the secret into `ALPACA_API_SECRET_KEY` → Apply.
4. Render → the cron job → **Trigger Run** to test now (outside market hours it just logs `market_closed`).

Cron jobs on Render are paid per use (Starter instance; a few dollars a month at most for this schedule).

## Run locally
```bash
pip install -r requirements.txt
export ALPACA_API_KEY_ID=... ALPACA_API_SECRET_KEY=... DRY_RUN=true
python -m agent.main
python -m unittest      # offline tests, no keys needed
```

This is a rule-based starting point, not a proven strategy. Keep it on paper until it has a track record you trust.
