"""Trading rules. Pure functions, no API calls, so they can be tested offline.

Approach: trend-following momentum on daily bars.
  BUY   when price > 50-day average, 20-day avg > 50-day avg, and RSI(14) is 50-70
        (uptrend with momentum, not yet overbought). Candidates ranked by 20-day return.
  SELL  when price falls below the 20-day average, RSI(14) > 80,
        or the position hits the stop-loss / take-profit.
"""


def sma(closes, n):
    return sum(closes[-n:]) / n if len(closes) >= n else None


def rsi(closes, n=14):
    if len(closes) < n + 1:
        return None
    gains = losses = 0.0
    for a, b in zip(closes[-n - 1:-1], closes[-n:]):
        d = b - a
        gains += max(d, 0)
        losses += max(-d, 0)
    if losses == 0:
        return 100.0
    rs = (gains / n) / (losses / n)
    return 100 - 100 / (1 + rs)


def signals(closes):
    """Indicators for one symbol, or None if not enough history."""
    if len(closes) < 51:
        return None
    return {
        "price": closes[-1],
        "sma20": sma(closes, 20),
        "sma50": sma(closes, 50),
        "rsi": rsi(closes),
        "mom20": closes[-1] / closes[-21] - 1,
    }


def is_buy(sig):
    return (sig["price"] > sig["sma50"] and sig["sma20"] > sig["sma50"]
            and 50 <= sig["rsi"] <= 70)


def exit_reason(sig, entry_price, cfg):
    """Why to sell a held position, or None to keep it."""
    pnl = sig["price"] / entry_price - 1
    if pnl <= -cfg.stop_loss_pct:
        return f"stop-loss ({pnl:.1%})"
    if pnl >= cfg.take_profit_pct:
        return f"take-profit ({pnl:.1%})"
    if sig["price"] < sig["sma20"]:
        return "trend broke (price < 20-day avg)"
    if sig["rsi"] > 80:
        return f"overbought (RSI {sig['rsi']:.0f})"
    return None


def plan(bars, positions, account, cfg, busy_symbols=()):
    """Decide what to sell and buy.

    bars: {symbol: [closes]}; positions: Alpaca position dicts; account: Alpaca account dict.
    Returns {"sell": [(symbol, reason)], "buy": [(symbol, usd)], "notes": [...]}.
    """
    equity = float(account["equity"])
    last_equity = float(account.get("last_equity") or equity)
    cash = float(account["cash"])
    result = {"sell": [], "buy": [], "notes": []}

    held = {p["symbol"]: p for p in positions}
    invested = sum(float(p["market_value"]) for p in positions)

    # 1) exits
    for sym, p in held.items():
        if sym in busy_symbols:
            continue
        sig = signals(bars.get(sym, []))
        if sig is None:
            # Not in the watchlist data: still enforce stop-loss / take-profit from Alpaca's numbers
            pnl = float(p["unrealized_plpc"])
            if pnl <= -cfg.stop_loss_pct or pnl >= cfg.take_profit_pct:
                result["sell"].append((sym, f"risk limit ({pnl:.1%})"))
            continue
        reason = exit_reason(sig, float(p["avg_entry_price"]), cfg)
        if reason:
            result["sell"].append((sym, reason))

    selling = {s for s, _ in result["sell"]}
    for s in selling:
        invested -= float(held[s]["market_value"])

    # 2) circuit breaker: no new buys after a bad day
    day_change = equity / last_equity - 1 if last_equity else 0
    if day_change <= -cfg.daily_loss_limit_pct:
        result["notes"].append(f"daily loss {day_change:.2%} hit limit; no new buys today")
        return result

    # 3) entries
    slots = cfg.max_positions - (len(held) - len(selling))
    budget = min(cash, equity * cfg.max_invested_pct - invested)
    per_trade = equity * cfg.max_position_pct
    candidates = []
    for sym, closes in bars.items():
        if sym in held or sym in busy_symbols:
            continue
        sig = signals(closes)
        if sig and is_buy(sig):
            candidates.append((sig["mom20"], sym))
    candidates.sort(reverse=True)

    for _, sym in candidates:
        if slots <= 0:
            break
        usd = min(per_trade, budget)
        if usd < cfg.min_order_usd:
            result["notes"].append("no budget left for new positions")
            break
        result["buy"].append((sym, round(usd, 2)))
        budget -= usd
        slots -= 1
    if not candidates:
        result["notes"].append("no buy signals")
    return result
