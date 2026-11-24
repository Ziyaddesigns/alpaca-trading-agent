"""One run of the agent: check market, read account, decide, place orders, log.

Render runs this on a schedule (see render.yaml). Run locally with:  python -m agent.main
"""
import json
import sys
from datetime import datetime, timezone

from .alpaca_client import AlpacaClient
from .config import Config
from .strategy import plan


def log(event, **kw):
    print(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "event": event, **kw}), flush=True)


def run(cfg=None, client=None):
    cfg = cfg or Config()
    cfg.validate()
    api = client or AlpacaClient(cfg)

    clock = api.clock()
    if not clock["is_open"]:
        log("market_closed", next_open=clock.get("next_open"))
        return

    account = api.account()
    if account.get("trading_blocked") or account.get("account_blocked"):
        log("account_blocked")
        return

    positions = api.positions()
    busy = {o["symbol"] for o in api.open_orders()}
    symbols = sorted(set(cfg.watchlist) | {p["symbol"] for p in positions})
    bars = api.daily_bars(symbols)

    decision = plan(bars, positions, account, cfg, busy_symbols=busy)
    log("plan", mode="paper" if cfg.is_paper else "LIVE", dry_run=cfg.dry_run,
        equity=account["equity"], cash=account["cash"], positions=len(positions),
        sell=decision["sell"], buy=decision["buy"], notes=decision["notes"])

    if cfg.dry_run:
        return decision

    for sym, reason in decision["sell"]:
        try:
            o = api.close_position(sym)
            log("sell", symbol=sym, reason=reason, order_id=o.get("id"))
        except Exception as e:  # keep going with the other orders
            log("sell_failed", symbol=sym, error=str(e))

    for sym, usd in decision["buy"]:
        try:
            if not api.asset(sym).get("fractionable"):
                log("skip_not_fractionable", symbol=sym)
                continue
            o = api.buy_notional(sym, usd)
            log("buy", symbol=sym, usd=usd, order_id=o.get("id"))
        except Exception as e:
            log("buy_failed", symbol=sym, error=str(e))
    return decision


if __name__ == "__main__":
    try:
        run()
    except SystemExit:
        raise
    except Exception as e:
        log("run_failed", error=repr(e))
        sys.exit(1)
