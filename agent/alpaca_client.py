"""Thin wrapper over Alpaca's REST API (trading + market data)."""
from datetime import datetime, timedelta, timezone

import requests


class AlpacaClient:
    def __init__(self, cfg):
        self.cfg = cfg
        self.s = requests.Session()
        self.s.headers.update({
            "APCA-API-KEY-ID": cfg.key_id,
            "APCA-API-SECRET-KEY": cfg.secret_key,
        })

    def _get(self, url, **params):
        r = self.s.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    # ---- trading API ----
    def clock(self):
        return self._get(f"{self.cfg.base_url}/v2/clock")

    def account(self):
        return self._get(f"{self.cfg.base_url}/v2/account")

    def positions(self):
        return self._get(f"{self.cfg.base_url}/v2/positions")

    def open_orders(self):
        return self._get(f"{self.cfg.base_url}/v2/orders", status="open", limit=500)

    def asset(self, symbol):
        return self._get(f"{self.cfg.base_url}/v2/assets/{symbol}")

    def buy_notional(self, symbol, usd):
        return self._order({"symbol": symbol, "notional": f"{usd:.2f}", "side": "buy",
                            "type": "market", "time_in_force": "day"})

    def close_position(self, symbol):
        r = self.s.delete(f"{self.cfg.base_url}/v2/positions/{symbol}", timeout=30)
        r.raise_for_status()
        return r.json()

    def _order(self, body):
        r = self.s.post(f"{self.cfg.base_url}/v2/orders", json=body, timeout=30)
        r.raise_for_status()
        return r.json()

    # ---- market data ----
    def daily_bars(self, symbols, days=150):
        """Return {symbol: [close, close, ...]} oldest -> newest."""
        start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
        out, token = {s: [] for s in symbols}, None
        while True:
            params = {"symbols": ",".join(symbols), "timeframe": "1Day", "start": start,
                      "limit": 10000, "adjustment": "all", "feed": self.cfg.data_feed}
            if token:
                params["page_token"] = token
            data = self._get(f"{self.cfg.data_url}/v2/stocks/bars", **params)
            for sym, bars in (data.get("bars") or {}).items():
                out.setdefault(sym, []).extend(b["c"] for b in bars)
            token = data.get("next_page_token")
            if not token:
                return out
