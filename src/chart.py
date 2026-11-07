"""Trend chart rendering (matplotlib, Agg backend only)."""

from __future__ import annotations

import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

# Windows ships Microsoft YaHei; without it CJK titles render as tofu boxes.
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

import pandas as pd  # noqa: E402


def render_png(series: pd.Series, title: str, source: str, *, figsize=(9.5, 4.6), dpi=110) -> bytes:
    """Render the trend chart and return it as PNG bytes (no file needed)."""
    locator = mdates.AutoDateLocator()
    formatter = mdates.ConciseDateFormatter(locator)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.plot(series.index, series.to_numpy(), color="#1f77b4", linewidth=1.8)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_ylabel(series.name or "value")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    fig.text(0.99, 0.01, source, ha="right", va="bottom", fontsize=8, color="gray")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png")
    plt.close(fig)
    return buffer.getvalue()


def plot_series(series: pd.Series, title: str, source: str, out_path: Path) -> None:
    """Render the trend chart and save it as a PNG file."""
    Path(out_path).write_bytes(render_png(series, title, source))
