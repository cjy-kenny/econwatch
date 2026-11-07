# EconWatch

Live FRED market/macro quotes in a desktop GUI, plus a CLI that exports PNG trend charts and CSVs.
Ships as a single Windows `.exe` (no console window).

## Double-click = GUI

Launching the exe with no arguments opens **EconWatch 实时行情**:

- **序列下拉框** — 汇率（美元/欧元、人民币/美元、美元/日元、美元/英镑、美元/韩元）与宏观指标（联邦基金利率、10年期美债、美国CPI、失业率、标普500、VIX、实际GDP、通胀预期）
- **自定义ID** — 任意 FRED 序列 ID
- **起止年份 + 快捷区间** — 默认最近 5 年，另有 1年/3年/5年/10年 一键切换
- **查询 / 自动刷新(60s)** — 打开窗口即自动加载，勾选后每 60 秒自动拉取最新数据
- **实时数值条** — 最新值、日期、与上一期的涨跌（↑/↓ 及百分比，红涨绿跌）
- **最近数据表格** — 右侧表格列出最近 200 条观测：日期、数值、涨跌、涨跌幅（最新在前，红涨绿跌）
- **导出 CSV / 导出 PNG** — 另存为对话框，导出当前查询结果
- **FRED Key 输入框** — 窗口底部直接粘贴 Key，点"保存"写入 `~/.econwatch/config.json` 并立即重新拉取；"显示"可切换明文
- **中英文切换** — 右上角"语言"下拉框，中文/English 即时切换，选择保存在配置文件中
- **单实例** — 程序已打开时再次双击 exe，不会新开窗口，而是把已开的窗口唤起到最前
- **状态栏** — 数据来源（FRED 或世界银行 fallback）、最近更新时间

> FRED 免费数据最高到日频（汇率等），GUI 的"实时"指定期自动拉取最新发布值。

### 配置 FRED Key（推荐）

无 Key 时会回退到世界银行**年度**世界通胀数据（非实时，且与所选序列无关）。
要看到真正的行情，请申请免费 Key: https://fred.stlouisfed.org/docs/api/api_key.html

- 环境变量 `FRED_API_KEY`，或
- GUI 底部的 **FRED Key 输入框**（保存后写到 `C:\Users\<你>\.econwatch\config.json`），或
- 手动编辑 `C:\Users\<你>\.econwatch\config.json`：

```json
{ "fred_api_key": "your-32-char-key" }
```

窗口底部的 Key 输入框会自动带出已保存的 Key（默认打码，勾选"显示"可查看）。

## CLI

```
econwatch.exe --series CPIAUCSL --start 2015 --end 2025
econwatch.exe --series DEXUSEU --start 2020 --end 2025
econwatch.exe --series FEDFUNDS --start 2018
```

| Flag | Meaning |
|---|---|
| `--series` | FRED series id, e.g. `CPIAUCSL`, `DEXUSEU`, `FEDFUNDS` (required) |
| `--start` | First year, inclusive (default `2015`) |
| `--end` | Last year, inclusive (default: current year) |
| `--outdir` | Output directory (default: folder containing the exe) |

Output (next to the exe, or `--outdir`):

- `econwatch_<series>.png` — trend chart
- `econwatch_<series>.csv` — `date,value` rows; missing observations are **not** interpolated

If both FRED and the World Bank fallback fail, the error shows in a dialog plus
`econwatch_error.log`, and the process exits with code `1`.

## Build the exe

```
cd econwatch
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pyinstaller --clean --noconfirm build\econwatch.spec
```

The build lands in `dist\econwatch\` (**onedir** mode: `econwatch.exe` +
`_internal\` dependencies, ~122 MB on disk). Double-click `econwatch.exe`
inside — startup is instant because there is no per-launch unpacking; the
window appears in ~2-3s (first run after an update: ~7s while the
antivirus scans the new files) while pandas/matplotlib warm up behind it.

For a desktop icon, create a shortcut:

```
powershell -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(\"$env:USERPROFILE\Desktop\EconWatch.lnk\"); $s.TargetPath=\"$env:USERPROFILE\Desktop\EconWatch\econwatch.exe\"; $s.WorkingDirectory=\"$env:USERPROFILE\Desktop\EconWatch\"; $s.Save()"
```

(Onefile packaging — a single ~57 MB exe that unpacks itself on every launch,
costing 5-10s of startup — is still possible via the one-liner at the end of
this file; onedir is the recommended default.)

## Run from source

```
pip install -r requirements.txt
python src\main.py                     # GUI
python src\main.py --series CPIAUCSL --start 2015 --end 2025   # CLI
```

Chart rendering always uses the headless **Agg** backend; the GUI shows the
rendered PNG directly (tkinter PhotoImage), so no interactive matplotlib
backend is ever needed.

## Project layout

```
econwatch/
├── src/main.py          # entry point: GUI (bare launch) or CLI (with args)
├── src/gui.py           # tkinter live-quote window (fetch thread, exports)
├── src/data_fetcher.py  # FRED API + World Bank fallback
├── src/chart.py         # PNG trend chart (Agg)
├── src/exporter.py      # CSV export (date,value)
├── build/econwatch.spec # PyInstaller config
├── requirements.txt
└── README.md
```
