"""EconWatch GUI (tkinter): live FRED quotes, data table, CSV/PNG export."""

from __future__ import annotations

import base64
import importlib
import re
import socket
import threading
import traceback
from datetime import date, datetime
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import appconfig

# chart (matplotlib) / data_fetcher (pandas, requests) / exporter add ~4-6s of
# import time. They are imported lazily on a background thread right after the
# window is shown, so double-click lands on a visible window in ~1-2s.
_lazies: dict[str, object] = {}


def _lazy(name: str):
    mod = _lazies.get(name)
    if mod is None:
        mod = importlib.import_module(name)
        _lazies[name] = mod
    return mod


FRED_KEY_RE = re.compile(r"^[0-9a-z]{32}$")

REFRESH_MS = 60_000
SEP = " — "
TABLE_MAX_ROWS = 200
SINGLE_INSTANCE_PORT = 45917
ACTIVATE_MSG = b"econwatch-activate"
UP_COLOR = "#c0392b"    # 红涨
DOWN_COLOR = "#1e8449"  # 绿跌

PRESETS = [
    ("DEXUSEU", "美元/欧元", "USD/EUR"),
    ("DEXCHUS", "人民币/美元", "CNY/USD"),
    ("DEXJPUS", "美元/日元", "USD/JPY"),
    ("DEXUSUK", "美元/英镑", "USD/GBP"),
    ("DEXKOUS", "美元/韩元", "USD/KRW"),
    ("FEDFUNDS", "联邦基金利率", "Fed Funds Rate"),
    ("DGS10", "10年期美债收益率", "10Y Treasury Yield"),
    ("CPIAUCSL", "美国CPI", "US CPI"),
    ("UNRATE", "美国失业率", "US Unemployment"),
    ("SP500", "标普500", "S&P 500"),
    ("VIXCLS", "VIX恐慌指数", "VIX Volatility"),
    ("GDPC1", "美国实际GDP", "US Real GDP"),
    ("T10YIE", "10年通胀预期", "10Y Breakeven Inflation"),
]
DEFAULT_SERIES = "DEXUSEU"

I18N = {
    "zh": {
        "title": "EconWatch 实时行情",
        "loading": "正在加载…",
        "ready": "就绪",
        "series": "序列:",
        "custom": "自定义ID:",
        "from": "起:",
        "to": "止:",
        "refresh": "查询",
        "auto": "自动刷新(60s)",
        "range_1y": "1年",
        "range_3y": "3年",
        "range_5y": "5年",
        "range_10y": "10年",
        "lang": "语言",
        "export_csv": "导出 CSV",
        "export_png": "导出 PNG",
        "key": "FRED Key:",
        "show": "显示",
        "save": "保存",
        "latest": "最新",
        "source": "数据源",
        "updated": "更新于",
        "wb_short": "世界银行(回退)",
        "wb_footer": "数据来源: 世界银行开放数据 - FP.CPI.TOTL.ZG（全球CPI通胀，年度%）",
        "table_title": "最近数据",
        "collapse": "收起数据",
        "expand": "展开数据",
        "col_date": "日期",
        "col_value": "数值",
        "col_chg": "涨跌",
        "col_pct": "涨跌幅",
        "fetching": "正在获取 {sid} ({s}-{e}) …",
        "fetch_failed": "获取失败: {sid}",
        "unchanged": "数据无变化",
        "fred_error": "FRED 错误: {err}",
        "fallback_dialog": "FRED 获取失败：\n{err}\n\n当前显示的是世界银行回退数据（世界年度通胀，非实时）。\n请检查：Key 是否为 32 位小写字母数字；网络能否访问 api.stlouisfed.org。",
        "no_key_hint": "尚未保存任何 Key：在窗口底部的 FRED Key 框粘贴后，直接点“查询”即可自动保存并使用。",
        "bad_key_format": "Key 格式不像 FRED 的 32 位小写字母数字。已保存并尝试；若仍回退，请重新复制 Key。",
        "bad_year": "年份格式不正确，请输入四位年份。",
        "bad_range": "起始年份 ({a}) 不能晚于结束年份 ({b})。",
        "fetch_fail": "获取 {sid} 失败:\n{exc}",
        "ui_error": "界面发生错误:\n{tb}",
        "saved": "FRED Key 已保存 ✓",
        "cleared": "FRED Key 已清除",
        "need_query": "请先查询一个序列。",
        "export_fail": "导出失败:\n{exc}",
        "exported": "已导出: {path}",
        "csv_ft": "CSV 文件",
        "png_ft": "PNG 图片",
    },
    "en": {
        "title": "EconWatch Live Quotes",
        "loading": "Loading…",
        "ready": "Ready",
        "series": "Series:",
        "custom": "Custom ID:",
        "from": "From:",
        "to": "To:",
        "refresh": "Fetch",
        "auto": "Auto refresh (60s)",
        "range_1y": "1Y",
        "range_3y": "3Y",
        "range_5y": "5Y",
        "range_10y": "10Y",
        "lang": "Language",
        "export_csv": "Export CSV",
        "export_png": "Export PNG",
        "key": "FRED Key:",
        "show": "Show",
        "save": "Save",
        "latest": "Latest",
        "source": "Source",
        "updated": "Updated",
        "wb_short": "World Bank (fallback)",
        "wb_footer": "Source: World Bank Open Data - FP.CPI.TOTL.ZG (world CPI inflation, annual %)",
        "table_title": "Recent data",
        "collapse": "Hide table",
        "expand": "Show table",
        "col_date": "Date",
        "col_value": "Value",
        "col_chg": "Change",
        "col_pct": "Change %",
        "fetching": "Fetching {sid} ({s}-{e}) …",
        "fetch_failed": "Fetch failed: {sid}",
        "unchanged": "data unchanged",
        "fred_error": "FRED error: {err}",
        "fallback_dialog": "FRED fetch failed:\n{err}\n\nShowing World Bank fallback data (world annual CPI inflation, not live).\nCheck that the key is 32 lowercase alphanumerics and that api.stlouisfed.org is reachable.",
        "no_key_hint": "No saved key detected: paste it into the FRED Key box at the bottom, then press Fetch — it is saved and applied automatically.",
        "bad_key_format": "That key doesn't look like FRED's 32 lowercase alphanumeric characters. Saved anyway; if it still falls back, re-copy the key.",
        "bad_year": "Invalid year, please enter a 4-digit year.",
        "bad_range": "Start year ({a}) must not be after end year ({b}).",
        "fetch_fail": "Failed to fetch {sid}:\n{exc}",
        "ui_error": "UI error:\n{tb}",
        "saved": "FRED key saved ✓",
        "cleared": "FRED key cleared",
        "need_query": "Fetch a series first.",
        "export_fail": "Export failed:\n{exc}",
        "exported": "Exported: {path}",
        "csv_ft": "CSV files",
        "png_ft": "PNG images",
    },
}


def _preset_name(sid: str, lang: str) -> str:
    for code, zh, en in PRESETS:
        if code == sid:
            return zh if lang == "zh" else en
    return ""


def _fmt(v: float) -> str:
    if abs(v) >= 10_000:
        return f"{v:,.1f}"
    if abs(v) >= 100:
        return f"{v:,.2f}"
    return f"{v:,.4f}"


class EconWatchApp:
    """Main window: pick a series, watch the trend, read the table, export."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.lang = appconfig.load_config().get("language", "zh")
        if self.lang not in I18N:
            self.lang = "zh"

        self._series: pd.Series | None = None
        self._png_bytes: bytes | None = None
        self._photo: tk.PhotoImage | None = None  # keep a reference, else Tk GCs it
        self._current_id = DEFAULT_SERIES
        self._last: tuple[str, int, int, str] | None = None  # (sid, start, end, source)
        self._updated_str = ""
        self._fetch_params: tuple[str, int, int] | None = None
        self._refetch_pending = False
        self._note: str | None = None
        self._user_initiated = False
        self._table_collapsed = False
        self._fetching = False
        self._auto_job: str | None = None

        self._build_ui()
        self._apply_language()
        root.report_callback_exception = self._on_tk_error

        # A fullscreen app (e.g. a maximized browser) can hold the foreground
        # lock, so a freshly launched window may open BEHIND it and look like
        # a dead double-click. Force visibility for the first two seconds.
        root.update_idletasks()
        self._raise_to_front()

        root.after(100, self._preload_and_refresh)

    @property
    def L(self) -> dict:
        return I18N[self.lang]

    # ---- UI construction ----
    def _build_ui(self) -> None:
        style = ttk.Style()
        for theme in ("vista", "windows10", "clam"):
            try:
                style.theme_use(theme)
                break
            except tk.TclError:
                continue
        style.configure("Chart.TFrame", background="white")
        style.configure("Chart.TLabel", background="white")

        self.root.geometry("1080x620")
        self.root.minsize(920, 540)
        self.root.update_idletasks()
        # center the window, leaving room for the Windows taskbar
        x = max(0, (self.root.winfo_screenwidth() - 1080) // 2)
        y = max(0, (self.root.winfo_screenheight() - 620 - 40) // 2)
        self.root.geometry(f"+{x}+{y}")

        # -- toolbar, row 1: series selection --
        top1 = ttk.Frame(self.root, padding=(10, 8, 10, 0))
        top1.pack(fill="x")
        self.lbl_series = ttk.Label(top1)
        self.lbl_series.pack(side="left")
        self.combo = ttk.Combobox(top1, state="readonly", width=18)
        self.combo.pack(side="left", padx=(4, 12))
        self.lbl_custom = ttk.Label(top1)
        self.lbl_custom.pack(side="left")
        self.custom = ttk.Entry(top1, width=12)
        self.custom.pack(side="left", padx=(4, 12))
        self.go_btn = ttk.Button(top1, command=lambda: self.refresh(True))
        self.go_btn.pack(side="left", padx=(4, 12))
        self.auto_var = tk.BooleanVar(value=True)
        self.auto_check = ttk.Checkbutton(top1, variable=self.auto_var)
        self.auto_check.pack(side="left")

        # -- toolbar, row 2: years, quick ranges, language --
        top2 = ttk.Frame(self.root, padding=(10, 6, 10, 0))
        top2.pack(fill="x")
        this_year = date.today().year
        self.lbl_from = ttk.Label(top2)
        self.lbl_from.pack(side="left")
        self.start_var = tk.StringVar(value=str(this_year - 5))
        ttk.Spinbox(top2, from_=1900, to=this_year, textvariable=self.start_var, width=6).pack(side="left", padx=(2, 8))
        self.lbl_to = ttk.Label(top2)
        self.lbl_to.pack(side="left")
        self.end_var = tk.StringVar(value=str(this_year))
        ttk.Spinbox(top2, from_=1900, to=this_year + 1, textvariable=self.end_var, width=6).pack(side="left", padx=(2, 8))

        self.range_btns = []
        for years in (1, 3, 5, 10):
            btn = ttk.Button(top2, width=4, command=lambda y=years: self._set_range(y))
            btn.pack(side="left", padx=(2, 0))
            self.range_btns.append(btn)

        self.toggle_btn = ttk.Button(top2, command=self._toggle_table)
        self.toggle_btn.pack(side="left", padx=(12, 0))

        self.lbl_lang = ttk.Label(top2)
        self.lbl_lang.pack(side="right")
        self.lang_combo = ttk.Combobox(top2, state="readonly", width=9, values=["中文", "English"])
        self.lang_combo.pack(side="right", padx=(0, 4))
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language)

        # -- main area: chart (left) + data table (right) --
        self.table_pane = ttk.PanedWindow(self.root, orient="horizontal")
        self.table_pane.pack(fill="both", expand=True, padx=10, pady=(6, 0))

        left = ttk.Frame(self.table_pane, style="Chart.TFrame")
        self.table_pane.add(left, weight=3)
        self.chart_label = ttk.Label(left, style="Chart.TLabel", anchor="center")
        self.chart_label.pack(fill="both", expand=True)

        value_row = ttk.Frame(self.root, padding=(10, 2))
        value_row.pack(fill="x")
        self.value_label = ttk.Label(value_row, font=("Microsoft YaHei", 13, "bold"))
        self.value_label.pack(side="left", padx=(6, 12))
        self.change_label = ttk.Label(value_row, font=("Microsoft YaHei", 12, "bold"))
        self.change_label.pack(side="left")

        self.right_frame = ttk.Frame(self.table_pane)
        self.table_pane.add(self.right_frame, weight=2)
        self.table_title = ttk.Label(self.right_frame)
        self.table_title.pack(anchor="w", pady=(0, 2))
        table_wrap = ttk.Frame(self.right_frame)
        table_wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            table_wrap,
            columns=("date", "value", "chg", "pct"),
            show="headings",
            height=15,
        )
        for col, width, anchor in (("date", 100, "w"), ("value", 100, "e"), ("chg", 90, "e"), ("pct", 75, "e")):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor=anchor)
        self.tree.tag_configure("up", foreground=UP_COLOR)
        self.tree.tag_configure("down", foreground=DOWN_COLOR)
        vsb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # -- bottom bar: exports, FRED key, status --
        bottom = ttk.Frame(self.root, padding=(10, 6))
        bottom.pack(fill="x")
        self.btn_csv = ttk.Button(bottom, command=self._export_csv)
        self.btn_csv.pack(side="left")
        self.btn_png = ttk.Button(bottom, command=self._export_png)
        self.btn_png.pack(side="left", padx=(8, 0))

        self.lbl_key = ttk.Label(bottom)
        self.lbl_key.pack(side="left", padx=(16, 2))
        self.key_var = tk.StringVar(value=appconfig.get_api_key() or "")
        self.key_entry = ttk.Entry(bottom, textvariable=self.key_var, width=22, show="•")
        self.key_entry.pack(side="left")
        self.key_entry.bind("<Return>", lambda _e: self._save_key())
        self.show_key_var = tk.BooleanVar(value=False)
        self.show_check = ttk.Checkbutton(bottom, variable=self.show_key_var, command=self._toggle_key)
        self.show_check.pack(side="left", padx=(2, 0))
        self.save_btn = ttk.Button(bottom, width=5, command=self._save_key)
        self.save_btn.pack(side="left", padx=(4, 0))

        self.status_var = tk.StringVar()
        ttk.Label(bottom, textvariable=self.status_var).pack(side="right")

    def _raise_to_front(self) -> None:
        """Bring the window to the front, even over a fullscreen foreground app."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.root.attributes("-topmost", True)
        self.root.after(2000, lambda: self.root.attributes("-topmost", False))

    def _preload_and_refresh(self) -> None:
        """Warm the heavy imports off the UI thread, then start the first fetch."""
        def boot():
            _lazy("chart")
            _lazy("data_fetcher")
            _lazy("exporter")
            self.root.after(0, self.refresh)

        threading.Thread(target=boot, daemon=True).start()

    # ---- language ----
    def _apply_language(self) -> None:
        L = self.L
        self.root.title(L["title"])
        self.lbl_series.config(text=L["series"])
        self.lbl_custom.config(text=L["custom"])
        self.go_btn.config(text=L["refresh"])
        self.auto_check.config(text=L["auto"])
        self.toggle_btn.config(text=L["expand"] if self._table_collapsed else L["collapse"])
        self.lbl_from.config(text=L["from"])
        self.lbl_to.config(text=L["to"])
        for btn, years in zip(self.range_btns, (1, 3, 5, 10)):
            btn.config(text=L[f"range_{years}y"])
        self.lbl_lang.config(text=L["lang"])
        self.lang_combo.current(1 if self.lang == "en" else 0)
        self.btn_csv.config(text=L["export_csv"])
        self.btn_png.config(text=L["export_png"])
        self.lbl_key.config(text=L["key"])
        self.show_check.config(text=L["show"])
        self.save_btn.config(text=L["save"])
        for col, key in (("date", "col_date"), ("value", "col_value"), ("chg", "col_chg"), ("pct", "col_pct")):
            self.tree.heading(col, text=L[key])

        # rebuild preset display strings, keeping the current selection
        sid = self._selected_series()
        self.combo.config(values=[f"{p[0]}{SEP}{p[1] if self.lang == 'zh' else p[2]}" for p in PRESETS])
        idx = next((i for i, p in enumerate(PRESETS) if p[0] == sid), 0)
        self.combo.current(idx)

        if self._last:
            self._render_results()
        else:
            self.value_label.config(text=L["loading"])
            self.change_label.config(text="")
            self._update_table_title(0)
            self.status_var.set(L["ready"])

        if self._fetching and self._fetch_params:
            sid, s, e = self._fetch_params
            self.status_var.set(self.L["fetching"].format(sid=sid, s=s, e=e))

    def _on_language(self, event=None) -> None:
        lang = "en" if self.lang_combo.current() == 1 else "zh"
        if lang == self.lang:
            return
        self.lang = lang
        config = appconfig.load_config()
        config["language"] = lang
        appconfig.save_config(config)
        self._apply_language()

    # ---- actions ----
    def _selected_series(self) -> str:
        custom = self.custom.get().strip().upper()
        if custom:
            return custom
        return self.combo.get().split(SEP)[0].strip()

    def refresh(self, user_initiated: bool = False) -> None:
        """Start a background fetch for the currently selected series."""
        if self._fetching:
            return
        L = self.L
        self._user_initiated = user_initiated
        sid = self._selected_series()
        try:
            start = int(self.start_var.get())
            end = int(self.end_var.get())
        except ValueError:
            messagebox.showerror("EconWatch", L["bad_year"])
            return
        if start > end:
            messagebox.showerror("EconWatch", L["bad_range"].format(a=start, b=end))
            return
        # Auto-apply whatever is in the key field: filling it in and pressing
        # 查询 must work without the extra 保存 click.
        key_field = self.key_var.get().strip()
        try:
            if key_field != (appconfig.get_api_key() or ""):
                appconfig.save_api_key(key_field)
        except OSError:
            pass
        self._fetching = True
        self._fetch_params = (sid, start, end)
        self.go_btn.config(state="disabled")
        self.status_var.set(L["fetching"].format(sid=sid, s=start, e=end))
        threading.Thread(target=self._worker, args=(sid, start, end), daemon=True).start()
        self._schedule_auto()

    def _set_range(self, years: int) -> None:
        this_year = date.today().year
        self.start_var.set(str(this_year - years))
        self.end_var.set(str(this_year))
        self.refresh(True)

    def _toggle_table(self) -> None:
        """Hide/show the recent-data pane; the chart re-renders to fill the space."""
        L = self.L
        self._table_collapsed = not self._table_collapsed
        if self._table_collapsed:
            self.table_pane.remove(self.right_frame)
            self.toggle_btn.config(text=L["expand"])
        else:
            try:
                self.table_pane.insert(1, self.right_frame, weight=2)
            except tk.TclError:  # pane forgotten entirely
                self.table_pane.add(self.right_frame, weight=2)
            self.toggle_btn.config(text=L["collapse"])
        if self._last:
            self._render_results()

    def _worker(self, sid: str, start: int, end: int) -> None:
        try:
            series, source, note = _lazy('data_fetcher').fetch_data(sid, start, end)
        except Exception as exc:  # surfaced on the UI thread
            self.root.after(0, self._on_error, sid, exc)
        else:
            self.root.after(0, self._on_data, sid, start, end, series, source, note)

    def _on_data(self, sid: str, start: int, end: int, series: pd.Series, source: str, note: str | None) -> None:
        L = self.L
        user_refresh = self._user_initiated
        self._user_initiated = False
        self._fetching = False
        self._fetch_params = None
        self.go_btn.config(state="normal")
        self._current_id = sid

        # Auto-refreshes usually return identical data: skip the chart/table
        # rebuild so the user's table scroll position and selection survive.
        unchanged = (
            self._series is not None
            and self._last is not None
            and self._last[0] == sid
            and self._last[1] == start
            and self._last[2] == end
            and self._series.equals(series)
        )
        self._series = series
        self._last = (sid, start, end, source)
        self._note = note
        self._updated_str = datetime.now().strftime("%H:%M:%S")

        if unchanged:
            self.status_var.set(self._compose_status(source, f"{L['updated']} {self._updated_str} ({L['unchanged']})"))
        else:
            self._render_results()

        if note and user_refresh:
            # a deliberate fetch (查询/保存 Key/区间按钮) fell back: explain why
            msg = L["fallback_dialog"].format(err=note[:220])
            if "no FRED API key" in note:
                msg += "\n\n" + L["no_key_hint"]
            messagebox.showwarning("EconWatch", msg)

        if self._refetch_pending:  # a key saved while this fetch was running
            self._refetch_pending = False
            self.root.after(300, lambda: self.refresh(True))

    def _on_error(self, sid: str, exc: Exception) -> None:
        L = self.L
        self._fetching = False
        self._fetch_params = None
        self.go_btn.config(state="normal")
        self.status_var.set(L["fetch_failed"].format(sid=sid))
        messagebox.showerror("EconWatch", L["fetch_fail"].format(sid=sid, exc=exc))
        if self._refetch_pending:
            self._refetch_pending = False
            self.root.after(300, self.refresh)
        self._schedule_auto()

    # ---- rendering of the loaded series ----
    def _render_results(self) -> None:
        sid, start, end, source = self._last
        L = self.L
        name = _preset_name(sid, self.lang)
        years = f"({start}-{end})"
        title = f"{sid} — {name} {years}" if name else f"{sid} {years}"
        footer = L["wb_footer"] if "World Bank" in source else f"FRED ({sid})"

        fig_w = 9.4 if self._table_collapsed else 6.1  # fill the freed space when collapsed
        render_png = _lazy('chart').render_png
        self._png_bytes = render_png(self._series, title=title, source=footer, figsize=(fig_w, 4.15), dpi=100)
        self._photo = tk.PhotoImage(data=base64.b64encode(self._png_bytes).decode("ascii"))
        self.chart_label.config(image=self._photo, text="")
        self._set_value_bar()
        self._fill_table()
        self.status_var.set(self._compose_status(source, f"{L['updated']} {self._updated_str}"))

    def _set_value_bar(self) -> None:
        L = self.L
        series = self._series
        last = float(series.iloc[-1])
        stamp = series.index[-1].strftime("%Y-%m-%d")
        self.value_label.config(text=f"{L['latest']}  {_fmt(last)}  ({stamp})")
        if len(series) >= 2:
            prev = float(series.iloc[-2])
            diff = last - prev
            pct = diff / prev * 100 if prev else None
            arrow = "↑" if diff > 0 else ("↓" if diff < 0 else "→")
            color = UP_COLOR if diff > 0 else (DOWN_COLOR if diff < 0 else "#666666")
            pct_text = f"({pct:+.2f}%)" if pct is not None else ""
            self.change_label.config(text=f"{arrow} {_fmt(abs(diff))} {pct_text}".strip(), foreground=color)
        else:
            self.change_label.config(text="", foreground="#666666")

    def _fill_table(self) -> None:
        series = self._series.dropna()
        rows = []  # chronological, then displayed newest-first
        prev = None
        for ts, raw in series.items():
            v = float(raw)
            diff = None if prev is None else v - prev
            pct = None if not (prev and diff is not None) else diff / prev * 100
            rows.append((ts, v, diff, pct))
            prev = v
        shown = list(reversed(rows[-TABLE_MAX_ROWS:]))

        self.tree.delete(*self.tree.get_children())
        for ts, v, diff, pct in shown:
            stamp = ts.strftime("%Y-%m-%d")
            if diff is None:
                chg_text, pct_text, tag = "—", "—", ""
            else:
                sign = "+" if diff > 0 else ("-" if diff < 0 else "")
                chg_text = f"{sign}{_fmt(abs(diff))}"
                pct_text = f"{pct:+.2f}%" if pct is not None else "—"
                tag = "up" if diff > 0 else ("down" if diff < 0 else "")
            self.tree.insert("", "end", values=(stamp, _fmt(v), chg_text, pct_text), tags=(tag,) if tag else ())
        self._update_table_title(len(shown))

    def _compose_status(self, source: str, extra: str = "") -> str:
        """One-line status: data source, why FRED fell back (if it did), extra."""
        short = self.L["wb_short"] if "World Bank" in source else "FRED"
        parts = [f"{self.L['source']}: {short}"]
        if self._note:
            parts.append(self.L["fred_error"].format(err=self._note[:70]))
        if extra:
            parts.append(extra)
        return " | ".join(parts)

    def _update_table_title(self, n: int) -> None:
        self.table_title.config(text=f"{self.L['table_title']} ({n})")

    # ---- key / exports ----
    def _toggle_key(self) -> None:
        self.key_entry.config(show="" if self.show_key_var.get() else "•")

    def _save_key(self) -> None:
        L = self.L
        key = self.key_var.get().strip()
        if key and not FRED_KEY_RE.match(key):
            messagebox.showwarning("EconWatch", L["bad_key_format"])
        appconfig.save_api_key(key)
        self.status_var.set(L["saved"] if key else L["cleared"])
        if self._fetching:
            self._refetch_pending = True  # apply as soon as the current fetch lands
        else:
            self.refresh(True)

    def _export_csv(self) -> None:
        if self._series is None:
            messagebox.showinfo("EconWatch", self.L["need_query"])
            return
        L = self.L
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"econwatch_{self._current_id}.csv",
            filetypes=[(L["csv_ft"], "*.csv")],
        )
        if not path:
            return
        try:
            _lazy('exporter').export_csv(self._series, Path(path))
        except OSError as exc:
            messagebox.showerror("EconWatch", L["export_fail"].format(exc=exc))
            return
        self.status_var.set(L["exported"].format(path=path))

    def _export_png(self) -> None:
        if self._png_bytes is None:
            messagebox.showinfo("EconWatch", self.L["need_query"])
            return
        L = self.L
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=f"econwatch_{self._current_id}.png",
            filetypes=[(L["png_ft"], "*.png")],
        )
        if not path:
            return
        try:
            Path(path).write_bytes(self._png_bytes)
        except OSError as exc:
            messagebox.showerror("EconWatch", L["export_fail"].format(exc=exc))
            return
        self.status_var.set(L["exported"].format(path=path))

    # ---- background loop / error surfacing ----
    def _schedule_auto(self) -> None:
        if self._auto_job is not None:
            try:
                self.root.after_cancel(self._auto_job)
            except Exception:
                pass
        self._auto_job = self.root.after(REFRESH_MS, self._auto_tick)

    def _auto_tick(self) -> None:
        self._auto_job = None
        if self.auto_var.get():
            self.refresh()  # may skip while another fetch is in flight
        if self._auto_job is None:
            # refresh() early-returned on a busy fetch; keep the loop alive
            self._schedule_auto()

    def _on_tk_error(self, exc_type, exc, tb) -> None:
        messagebox.showerror("EconWatch", self.L["ui_error"].format(tb="".join(traceback.format_exception(exc_type, exc, tb))))


def _bind_single_instance() -> tuple[socket.socket | None, bool]:
    """Claim the single-instance port, or wake the existing window instead.

    Returns (listener, activated_existing):
      - (socket, False): this process owns the port; run normally.
      - (None, True): an already-running instance was activated; exit.
      - (None, False): the port is held by an unrelated app; run without
        single-instance behavior rather than refusing to start.
    """
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
        listener.listen(2)
        return listener, False
    except OSError:
        listener.close()
    try:  # port taken: poke the running instance so it raises its window
        with socket.create_connection(("127.0.0.1", SINGLE_INSTANCE_PORT), timeout=1.5) as conn:
            conn.sendall(ACTIVATE_MSG)
        return None, True
    except OSError:  # unrelated software holds the port
        return None, False


def _listen_for_activate(listener: socket.socket, on_activate) -> None:
    """Daemon loop: raise the window whenever a second instance says hello."""
    listener.settimeout(2.0)
    while True:
        try:
            conn, _ = listener.accept()
        except socket.timeout:
            if listener.fileno() == -1:  # closed by the app on shutdown
                return
            continue
        except OSError:
            return
        try:
            if conn.recv(128).startswith(ACTIVATE_MSG):
                on_activate()
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass


def run_gui() -> int:
    listener, activated_existing = _bind_single_instance()
    if activated_existing:
        return 0  # the running instance's window was raised instead
    root = tk.Tk()
    app = EconWatchApp(root)
    if listener is not None:
        threading.Thread(
            target=_listen_for_activate,
            args=(listener, lambda: root.after(0, app._raise_to_front)),
            daemon=True,
        ).start()
    try:
        root.mainloop()
    finally:
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass
    return 0
