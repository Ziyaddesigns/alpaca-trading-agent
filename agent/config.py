"""Settings, read from environment variables (set them in Render, never in code)."""
import os
from dataclasses import dataclass, field

PAPER_URL = "https://paper-api.alpaca.markets"
LIVE_URL = "https://api.alpaca.markets"


def _f(name, default):
    return float(os.getenv(name, default))


def _b(name, default="false"):
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


@dataclass
class Config:
    key_id: str = field(default_factory=lambda: os.getenv("ALPACA_API_KEY_ID", ""))
    secret_key: str = field(default_factory=lambda: os.getenv("ALPACA_API_SECRET_KEY", ""))
    base_url: str = field(default_factory=lambda: os.getenv("ALPACA_BASE_URL", PAPER_URL).rstrip("/"))
    data_url: str = field(default_factory=lambda: os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets").rstrip("/"))
    data_feed: str = field(default_factory=lambda: os.getenv("DATA_FEED", "iex"))  # iex is free; sip needs a paid data plan

    watchlist: list = field(default_factory=lambda: [
        s.strip().upper() for s in os.getenv(
            "WATCHLIST", "SPY,QQQ,AAPL,MSFT,NVDA,AMZN,GOOGL,META,JPM,XOM"
        ).split(",") if s.strip()
    ])

    # Risk limits
    max_position_pct: float = field(default_factory=lambda: _f("MAX_POSITION_PCT", 0.10))      # of equity, per stock
    max_positions: int = field(default_factory=lambda: int(_f("MAX_POSITIONS", 5)))
    max_invested_pct: float = field(default_factory=lambda: _f("MAX_INVESTED_PCT", 0.80))      # keep >=20% cash
    stop_loss_pct: float = field(default_factory=lambda: _f("STOP_LOSS_PCT", 0.05))
    take_profit_pct: float = field(default_factory=lambda: _f("TAKE_PROFIT_PCT", 0.12))
    daily_loss_limit_pct: float = field(default_factory=lambda: _f("DAILY_LOSS_LIMIT_PCT", 0.03))
    min_order_usd: float = field(default_factory=lambda: _f("MIN_ORDER_USD", 10))

    dry_run: bool = field(default_factory=lambda: _b("DRY_RUN"))
    allow_live: bool = field(default_factory=lambda: _b("ALLOW_LIVE_TRADING"))

    @property
    def is_paper(self):
        return "paper-api" in self.base_url

    def validate(self):
        if not self.key_id or not self.secret_key:
            raise SystemExit("Missing ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY")
        if not self.is_paper and not self.allow_live:
            raise SystemExit(
                f"Refusing to trade on {self.base_url}: live trading needs ALLOW_LIVE_TRADING=true"
            )
