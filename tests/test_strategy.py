import math
import unittest

from agent.config import Config
from agent.strategy import plan, rsi, signals, is_buy
from agent import main as agent_main


def uptrend(n=120, start=100.0):
    # steady climb with small wiggles -> RSI in the 50s-60s
    return [start * (1.0015 ** i) * (1 + 0.02 * math.sin(i)) for i in range(n)]


def downtrend(n=120, start=100.0):
    return [start * (0.997 ** i) * (1 + 0.01 * math.sin(i)) for i in range(n)]


def cfg(**kw):
    c = Config(key_id="k", secret_key="s")
    for k, v in kw.items():
        setattr(c, k, v)
    return c


ACCOUNT = {"equity": "100000", "last_equity": "100000", "cash": "100000"}


class StrategyTests(unittest.TestCase):
    def test_rsi_bounds(self):
        self.assertEqual(rsi(list(range(1, 30))), 100.0)
        self.assertTrue(0 <= rsi(uptrend()) <= 100)

    def test_uptrend_buys_downtrend_doesnt(self):
        self.assertTrue(is_buy(signals(uptrend())), signals(uptrend()))
        self.assertFalse(is_buy(signals(downtrend())))

    def test_plan_buys_within_limits(self):
        bars = {f"S{i}": uptrend(start=50 + i) for i in range(8)}
        bars["BAD"] = downtrend()
        d = plan(bars, [], ACCOUNT, cfg())
        self.assertEqual(len(d["buy"]), 5)                    # MAX_POSITIONS
        self.assertTrue(all(u == 10000 for _, u in d["buy"]))  # 10% each
        self.assertNotIn("BAD", [s for s, _ in d["buy"]])

    def test_invested_cap(self):
        bars = {f"S{i}": uptrend(start=50 + i) for i in range(8)}
        d = plan(bars, [], ACCOUNT, cfg(max_position_pct=0.5))
        self.assertLessEqual(sum(u for _, u in d["buy"]), 80000)

    def test_stop_loss_exit(self):
        closes = uptrend()
        pos = [{"symbol": "AAA", "avg_entry_price": str(closes[-1] / 0.9),
                "market_value": "1000", "unrealized_plpc": "-0.10"}]
        d = plan({"AAA": closes}, pos, ACCOUNT, cfg())
        self.assertEqual(d["sell"][0][0], "AAA")
        self.assertIn("stop-loss", d["sell"][0][1])

    def test_daily_loss_circuit_breaker(self):
        acct = {"equity": "96000", "last_equity": "100000", "cash": "96000"}
        d = plan({"A": uptrend()}, [], acct, cfg())
        self.assertEqual(d["buy"], [])
        self.assertTrue(any("daily loss" in n for n in d["notes"]))

    def test_busy_symbols_skipped(self):
        d = plan({"A": uptrend()}, [], ACCOUNT, cfg(), busy_symbols={"A"})
        self.assertEqual(d["buy"], [])

    def test_live_url_refused_without_flag(self):
        c = cfg(base_url="https://api.alpaca.markets")
        with self.assertRaises(SystemExit):
            c.validate()


class FakeApi:
    def __init__(self, open_=True):
        self.open_ = open_
        self.orders = []

    def clock(self): return {"is_open": self.open_, "next_open": "x"}
    def account(self): return dict(ACCOUNT)
    def positions(self): return []
    def open_orders(self): return []
    def daily_bars(self, symbols): return {s: uptrend(start=50 + i) for i, s in enumerate(symbols)}
    def asset(self, s): return {"fractionable": True}
    def buy_notional(self, s, usd): self.orders.append((s, usd)); return {"id": "1"}
    def close_position(self, s): self.orders.append((s, "close")); return {"id": "2"}


class RunTests(unittest.TestCase):
    def test_market_closed_no_orders(self):
        api = FakeApi(open_=False)
        agent_main.run(cfg(), api)
        self.assertEqual(api.orders, [])

    def test_run_places_orders(self):
        api = FakeApi()
        agent_main.run(cfg(), api)
        self.assertEqual(len(api.orders), 5)

    def test_dry_run_places_nothing(self):
        api = FakeApi()
        agent_main.run(cfg(dry_run=True), api)
        self.assertEqual(api.orders, [])


if __name__ == "__main__":
    unittest.main()
