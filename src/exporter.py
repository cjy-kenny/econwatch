"""CSV export: date,value columns only; missing observations are skipped, never interpolated."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd


def export_csv(series: pd.Series, out_path: Path) -> None:
    """Write the observations as date,value rows; NaN values are dropped as-is."""
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "value"])
        for timestamp, value in series.dropna().items():
            writer.writerow([timestamp.strftime("%Y-%m-%d"), value])
