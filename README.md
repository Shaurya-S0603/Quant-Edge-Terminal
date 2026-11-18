# QuantEdge

Historical strategy backtesting and quantitative equity research for US and Indian NSE markets. Built by Shaurya Singhal.

[Open the private Strategy Lab](https://quantedge-strategy-lab.skippingepoch8.chatgpt.site) · [Backtest methodology](research/yahoo-development-replay.md) · [Data and holdout protocol](research/README.md)

## Test your own symbols

1. Open **Test your own symbols** and enter up to five Yahoo tickers. Try `AAPL, MSFT` for US equities or `INFY.NS, TCS.NS` for NSE. Use one market per run.
2. Select **Trend and volatility**, **Moving-average crossover**, or **Buy and hold**. Set the dates, strategy parameters, and modeled costs per trade side.
3. On the hosted Site, select one CSV per ticker. Name each file after its symbol, such as `AAPL.csv`, and include `Date` or `session`, `Open`, `Close`, and `Adj Close`. Your files stay in your browser. In the local app, leave the file picker blank to fetch historical bars directly from Yahoo Finance.
4. Run the test to see net and gross equity, drawdown, total return, CAGR for windows of at least a year, trade count, and a net equal-weight buy-and-hold comparison. Edit the ticker field to add, replace, or remove symbols and run again.

The tester accepts dates from **November 1, 2016 through October 31, 2024**. It can use earlier eligible closes for warm-up and reports the actual shared scoring dates. When a price is missing for part of the basket, the tester omits that date across the basket. Uploaded files must be restricted to the development window.

## Run locally with Yahoo Finance

Use Python 3.12. Open the repository folder in VS Code and run the commands in its terminal.

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r research/requirements-py312.lock
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -m quantedge_research.lab serve
```

**macOS and Linux**

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r research/requirements-py312.lock
PYTHONPATH=src .venv/bin/python -m quantedge_research.lab serve
```

Open [localhost:8765](http://127.0.0.1:8765). The app includes the frozen historical report and fetches data for custom symbols on demand. Yahoo can rate-limit requests or lack history for specific symbols. CSV input works in either version.

To export ticker CSVs into the ignored `.data/exports/` directory, run the same Python command with `export AAPL MSFT` in place of `serve`. Use Yahoo symbol syntax, including the `.NS` suffix for NSE and `BRK-B` for Berkshire Hathaway Class B.

## Research design

| Path | Role |
| --- | --- |
| [`research/site/`](research/site/) | Strategy Lab, browser replay engine, and frozen portfolio-only chart data |
| [`src/quantedge_research/`](src/quantedge_research/) | Local Yahoo adapter, data audits, next-open portfolio ledger, walk-forward evaluation, bootstrap, and single-use holdout registry |
| [`research/`](research/) | Pinned strategy and universe, source audits, reproducibility instructions, and tests |

The custom tester uses equal starting weights. Trend and volatility holds an allocation in cash after nonpositive momentum and scales down volatile positions. Moving-average crossover holds an allocation when the fast average exceeds the slow one. Both rules rebalance monthly after a completed close, with modeled fills at the next shared open. The benchmark buys once after the first scoring close. Adjusted prices approximate total returns. Cash earns zero.

The frozen study uses an approved 16-stock universe, two local ETFs, six walk-forward checks, and a 2,000-path moving-block bootstrap. It showed lower drawdowns and lower returns than the fixed-weight basket in both markets. That exploratory study did not establish a statistical edge. Provider adjustments, survivorship and selection bias, gaps, and the simplified fill model limit both analyses. The custom tester cannot access the November 2024–October 2026 holdout, which remains outside interactive research.

## Verify

After installing the locked Python dependencies, run `python -m pytest` with the environment’s Python. With Node.js 22 or newer, run `node --test research/tests/test_symbol_replay.mjs`. Both checks are offline.

The earlier Streamlit and Next.js/FastAPI implementations are available in [Git history](https://github.com/Shaurya-S0603/Quant-Edge-Terminal/commit/42ed37c8e8e5dc686d8a1d93856bb1dab449f58c) and the [release archive](https://github.com/Shaurya-S0603/Quant-Edge-Terminal/releases).
