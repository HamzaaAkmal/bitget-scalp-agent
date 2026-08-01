"""Coinbase Exchange public candle loader for crypto spot markets."""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

import pandas as pd
import requests

from backtest.loaders.base import (
    cached_loader_fetch,
    check_budget,
    positive_env_float,
    positive_env_int,
    retry_with_budget,
    validate_date_range,
    validate_ohlc,
)
from backtest.loaders.registry import register

logger = logging.getLogger(__name__)

BASE_URL = "https://api.exchange.coinbase.com"
CANDLES_URL = f"{BASE_URL}/products/{{product_id}}/candles"

_INTERVAL_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "1H": 3600,
    "6h": 21600,
    "6H": 21600,
    "1d": 86400,
    "1D": 86400,
}
_MAX_CANDLES_PER_REQUEST = 300
_COINBASE_TIMEOUT = positive_env_int("COINBASE_TIMEOUT_S", 15)
_COINBASE_FETCH_BUDGET_S = positive_env_float("COINBASE_FETCH_BUDGET_S", 75.0)
_COINBASE_PROBE_TIMEOUT = positive_env_int("COINBASE_PROBE_TIMEOUT_S", 6)


def _timestamp_utc(value: str) -> pd.Timestamp:
    """Parse a date/datetime string as a UTC timestamp."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _is_date_only(value: str) -> bool:
    text = value.strip()
    return "T" not in text and " " not in text


def normalize_coinbase_product_id(code: str) -> str:
    """Map project crypto symbols to Coinbase Exchange product IDs."""
    value = code.strip().upper().replace("/", "-")
    if value.endswith("-USDT"):
        return value.removesuffix("-USDT") + "-USD"
    return value


@register
class DataLoader:
    """Coinbase Exchange public OHLCV loader."""

    name = "coinbase"
    markets = {"crypto"}
    requires_auth = False

    def is_available(self) -> bool:
        try:
            resp = requests.get(
                CANDLES_URL.format(product_id="BTC-USD"),
                params={"granularity": 86400},
                timeout=_COINBASE_PROBE_TIMEOUT,
                headers={"User-Agent": "Vibe-Trading/0.1"},
            )
            return resp.status_code == 200
        except Exception as exc:  # noqa: BLE001
            logger.warning("Coinbase probe failed: %s", exc)
            return False

    def fetch(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        *,
        interval: str = "1D",
        fields: Optional[List[str]] = None,
    ) -> Dict[str, pd.DataFrame]:
        validate_date_range(start_date, end_date)
        if fields:
            logger.warning("Coinbase ignores extra fields: %s", fields)

        granularity = _INTERVAL_SECONDS.get(interval.strip())
        if granularity is None:
            logger.warning(
                "unsupported Coinbase interval %r; supported: %s",
                interval,
                sorted(_INTERVAL_SECONDS),
            )
            return {}

        start = _timestamp_utc(start_date)
        end = _timestamp_utc(end_date)
        if _is_date_only(end_date):
            end += pd.Timedelta(days=1)
        now = pd.Timestamp.now(tz="UTC").floor("s")
        if end > now:
            end = now
        if start >= end:
            logger.warning("Coinbase date range is empty after capping future end: %s -> %s", start, end)
            return {}
        result: Dict[str, pd.DataFrame] = {}
        session = requests.Session()
        session.headers.update({"User-Agent": "Vibe-Trading/0.1"})

        for code in codes:
            product_id = normalize_coinbase_product_id(code)
            try:
                df = cached_loader_fetch(
                    source=self.name,
                    symbol=f"{code}:{product_id}",
                    timeframe=str(granularity),
                    start_date=start_date,
                    end_date=end_date,
                    fields=None,
                    fetch=lambda product_id=product_id: self._fetch_product(
                        session,
                        product_id,
                        start,
                        end,
                        granularity,
                    ),
                )
                if df is not None and not df.empty:
                    result[code.strip().upper().replace("/", "-")] = df
            except Exception as exc:  # noqa: BLE001
                logger.warning("Coinbase failed for %s (%s): %s", code, product_id, exc)
        return result

    @staticmethod
    def _fetch_product(
        session: requests.Session,
        product_id: str,
        start: pd.Timestamp,
        end: pd.Timestamp,
        granularity: int,
    ) -> Optional[pd.DataFrame]:
        rows: list[list[float]] = []
        cursor = start
        deadline = time.monotonic() + _COINBASE_FETCH_BUDGET_S
        label = f"Coinbase fetch for {product_id}"
        step = pd.Timedelta(seconds=granularity * _MAX_CANDLES_PER_REQUEST)

        while cursor < end:
            check_budget(deadline, label, budget_s=_COINBASE_FETCH_BUDGET_S)
            window_end = min(cursor + step, end)
            params = {
                "start": cursor.isoformat().replace("+00:00", "Z"),
                "end": window_end.isoformat().replace("+00:00", "Z"),
                "granularity": str(granularity),
            }

            def _request() -> list:
                resp = session.get(
                    CANDLES_URL.format(product_id=product_id),
                    params=params,
                    timeout=_COINBASE_TIMEOUT,
                )
                if resp.status_code in {429, 500, 502, 503, 504}:
                    raise requests.HTTPError(f"Coinbase HTTP {resp.status_code}", response=resp)
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, list):
                    raise requests.RequestException(f"Coinbase returned non-list payload: {data!r}")
                return data

            page = retry_with_budget(
                _request,
                transient=(requests.RequestException, TimeoutError),
                deadline=deadline,
                label=label,
            )
            rows.extend(page)
            cursor = window_end

        if not rows:
            return None

        frame = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
        frame["trade_date"] = pd.to_datetime(frame["time"], unit="s", utc=True).dt.tz_convert(None)
        for column in ("open", "high", "low", "close", "volume"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.set_index("trade_date").sort_index()
        frame = frame[~frame.index.duplicated(keep="last")]
        frame = frame[(frame.index >= start.tz_convert(None)) & (frame.index < end.tz_convert(None))]
        frame = frame[["open", "high", "low", "close", "volume"]].dropna(
            subset=["open", "high", "low", "close"]
        )
        frame = validate_ohlc(frame)
        return frame if not frame.empty else None
