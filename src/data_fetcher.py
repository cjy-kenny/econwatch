"""Data acquisition: FRED API first, World Bank Open Data as fallback."""

from __future__ import annotations

import sys
from datetime import date

import pandas as pd
import requests

from appconfig import get_api_key  # lightweight: stdlib-only config module

FRED_OBS_FMT = "%Y-%m-%d"
WORLD_BANK_URL = "https://api.worldbank.org/v2/country/WLD/indicator/FP.CPI.TOTL.ZG"
WORLD_BANK_LABEL = "World Bank Open Data - FP.CPI.TOTL.ZG (world CPI inflation, annual %)"


class DataFetchError(Exception):
    """Neither FRED nor the World Bank fallback could serve usable data."""


def _warn(message: str) -> None:
    if sys.stderr is not None:
        print(f"[econwatch] {message}", file=sys.stderr)


def fetch_from_fred(series_id: str, start: int, end: int) -> tuple[pd.Series, str]:
    """Fetch from FRED. Raises on missing/invalid key, network errors, empty data."""
    from fredapi import Fred  # deferred so a fredapi failure cannot break the fallback

    key = get_api_key()
    if not key:
        raise DataFetchError("no FRED API key (set FRED_API_KEY or ~/.econwatch/config.json)")
    fred = Fred(api_key=key)
    series = fred.get_series(
        series_id,
        observation_start=date(start, 1, 1).strftime(FRED_OBS_FMT),
        observation_end=date(end, 12, 31).strftime(FRED_OBS_FMT),
    )
    series = series.dropna()
    if series.empty:
        raise DataFetchError(f"FRED returned no observations for {series_id}")
    return series, f"FRED ({series_id})"


def fetch_from_worldbank(start: int, end: int) -> tuple[pd.Series, str]:
    """Fetch world CPI inflation (FP.CPI.TOTL.ZG) from the World Bank, no key required."""
    response = requests.get(
        WORLD_BANK_URL,
        params={"format": "json", "date": f"{start}:{end}", "per_page": 20000},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
    records = sorted(
        (row["date"], row["value"]) for row in rows if row.get("value") is not None
    )
    if not records:
        raise DataFetchError("World Bank returned no observations")
    index = pd.to_datetime([f"{year}-12-31" for year, _ in records])
    series = pd.Series([value for _, value in records], index=index, name="value")
    return series, WORLD_BANK_LABEL


def fetch_data(series_id: str, start: int, end: int) -> tuple[pd.Series, str, str | None]:
    """FRED first; on any failure (bad key, network, empty) fall back to the World Bank.

    Returns (series, source, fred_error) where fred_error is the reason FRED
    failed (None when FRED succeeded) so the UI can surface it.
    """
    try:
        series, source = fetch_from_fred(series_id, start, end)
        return series, source, None
    except Exception as fred_error:
        note = f"{type(fred_error).__name__}: {fred_error}"
        _warn(f"FRED failed ({note}); falling back to World Bank Open Data ...")
    try:
        series, source = fetch_from_worldbank(start, end)
        return series, source, note
    except Exception as wb_error:
        raise DataFetchError(
            f"FRED failed and the World Bank fallback failed too ({wb_error})"
        ) from wb_error
