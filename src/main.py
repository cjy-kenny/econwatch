"""EconWatch entry point.

Bare launch (double-click) opens the live-quote GUI. With arguments it runs
as a CLI: fetch a FRED series (World Bank fallback), render a PNG trend chart
and export the observations as CSV.

Usage:
    econwatch.exe                      -> GUI
    python main.py --series CPIAUCSL --start 2015 --end 2025
"""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import date
from pathlib import Path

# Sibling imports: -I isolated runs and some frozen layouts do not put the
# script/bundle directory on sys.path, so add it explicitly.
if __package__ in (None, ""):
    _here = str(Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)))
    if _here not in sys.path:
        sys.path.insert(0, _here)

# NOTE: pandas/matplotlib (chart, data_fetcher, exporter) are deliberately NOT
# imported here. The GUI path only needs tkinter to show the window in ~1-2s;
# run_cli imports the heavy modules locally.


def is_windowed() -> bool:
    """True when there is no usable console stream (windowed build / pythonw)."""
    return sys.stdout is None or sys.stderr is None


def default_outdir() -> Path:
    """Double-click friendly: frozen builds write next to the exe."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def _message_box(text: str, icon: int) -> None:
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, "EconWatch", icon)


def report_error(message: str, as_dialog: bool = False) -> None:
    """Surface an error even in a --windowed build where there is no console."""
    if not as_dialog and not is_windowed():
        print(message, file=sys.stderr)
        return
    try:
        (default_outdir() / "econwatch_error.log").write_text(message, encoding="utf-8")
    except OSError:
        pass
    _message_box(message, 0x10)  # MB_ICONERROR


class _Parser(argparse.ArgumentParser):
    """argparse that survives windowed builds, where stdout/stderr may be None."""

    def _print_message(self, message, file=None):
        if not message:
            return
        if file is not None and hasattr(file, "write"):
            file.write(message)
            return
        if sys.stderr is not None:
            sys.stderr.write(message)
        else:
            _message_box(message, 0x10)

    def error(self, message: str):
        report_error(f"{self.prog}: {message}\n\n{self.format_usage()}")
        raise SystemExit(2)


def parse_args(argv) -> argparse.Namespace:
    parser = _Parser(
        prog="econwatch",
        description="Fetch a FRED time series and export a PNG trend chart plus CSV.",
    )
    parser.add_argument(
        "--series",
        required=True,
        help="FRED series id, e.g. CPIAUCSL, DEXUSEU, FEDFUNDS",
    )
    parser.add_argument("--start", type=int, default=2015, help="first year (inclusive), default 2015")
    parser.add_argument("--end", type=int, default=date.today().year, help="last year (inclusive), default current year")
    parser.add_argument(
        "--outdir",
        type=Path,
        default=None,
        help="output directory (default: next to the exe, or the current directory)",
    )
    return parser.parse_args(argv)


def run_cli(args: argparse.Namespace) -> int:
    from chart import plot_series  # heavy: matplotlib
    from data_fetcher import DataFetchError, fetch_data  # heavy: pandas
    from exporter import export_csv

    want_dialog = is_windowed()  # shortcut-with-args launches must not fail silently
    if args.start > args.end:
        report_error(f"--start ({args.start}) must not be after --end ({args.end}).", as_dialog=want_dialog)
        return 2

    outdir = args.outdir or default_outdir()
    outdir.mkdir(parents=True, exist_ok=True)

    try:
        series, source, fred_error = fetch_data(args.series, args.start, args.end)
        png_path = outdir / f"econwatch_{args.series}.png"
        csv_path = outdir / f"econwatch_{args.series}.csv"
        plot_series(series, title=f"{args.series} ({args.start}-{args.end})", source=f"Source: {source}", out_path=png_path)
        export_csv(series, out_path=csv_path)
    except DataFetchError as exc:
        report_error(f"EconWatch could not fetch data: {exc}", as_dialog=want_dialog)
        return 1
    except Exception:  # unexpected: keep a windowed build from dying silently
        report_error("EconWatch failed:\n" + traceback.format_exc(), as_dialog=want_dialog)
        return 1

    if fred_error:
        report_error(f"FRED failed, showing World Bank fallback data. Reason: {fred_error}", as_dialog=False)

    if sys.stdout is not None:
        print(f"[econwatch] source : {source}")
        print(f"[econwatch] chart  : {png_path}")
        print(f"[econwatch] export : {csv_path}")
    if want_dialog:
        _message_box(
            f"EconWatch 完成!\n\n数据源: {source}\n图表: {png_path}\nCSV: {csv_path}",
            0x40,  # MB_ICONINFORMATION
        )
    return 0


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        # Bare launch (double-click): open the live-quote GUI.
        from gui import run_gui

        try:
            return run_gui()
        except BaseException:
            report_error("EconWatch 启动失败:\n" + traceback.format_exc(), as_dialog=True)
            return 1

    return run_cli(parse_args(argv))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:  # startup errors must not vanish in a windowed build
        report_error("EconWatch 启动失败:\n" + traceback.format_exc(), as_dialog=True)
        sys.exit(1)
