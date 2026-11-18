# Historical research protocol

Phase 1 provides an offline research package and a coverage audit. It is separate from the existing Streamlit and Next.js/FastAPI runtimes. The audit command cannot register an approval or run a strategy. The [fixed-weight comparison prototype](synthetic-comparison.md) is an offline synthetic smoke run for the next development phase. The [Trend + Volatility v1 strategy](trend-volatility-strategy.md) includes a pinned configuration and an expanding-window runner.

## Reproduce

Create a dedicated Python 3.12 environment. From the repository root on Linux or macOS:

```sh
python3.12 -m venv .venv-research
.venv-research/bin/python -m pip install --require-hashes -r research/requirements-py312.lock
.venv-research/bin/python -m pytest research/tests
mkdir -p .data/research
PYTHONPATH=src .venv-research/bin/python -m quantedge_research --end-exclusive 2026-11-01 > .data/research/coverage.json
```

For PowerShell, use `py -3.12 -m venv .venv-research`, invoke `.\.venv-research\Scripts\python.exe`, and set `$env:PYTHONPATH = "src"` before running the audit. The GitHub job validates Linux. The checkout excludes local research data and environments.

The default command reproduces the original [starter-list audit](coverage-audit-2026-11-18.md). To audit the [approved 16-stock comparison portfolio](approved-portfolio-v1.json) and its two local benchmarks, pass the versioned configuration instead.

```sh
PYTHONPATH=src .venv-research/bin/python -m quantedge_research --baseline research/approved-portfolio-v1.json --end-exclusive 2026-11-01 > .data/research/portfolio-coverage.json
```

Both commands request fixed historical dates and emit coverage, action counts, and quality flags. The baseline audit includes the configuration SHA-256 and checks that the screening dates fit inside development. See the [full-window source readiness report](source-readiness-2026-11-18.md) for the custodian audit, verified identifier changes, and ITC valuation evidence. Provider history can change between fetches. See the [approved baseline audit](approved-portfolio-audit-2026-11-18.md), [NSE reconciliation](nse-calendar-reconciliation-2026-11-18.md), and [raw-price pilot and entitlement accounting](nse-raw-source-pilot-2026-11-18.md) for the coverage and source verification. Each instrument audit includes the calendar version, schedule hash, and applicable exchange circulars.

### Local historical data contract

Supply `--prices-dir /private/input --universe /private/instruments.csv --source-name "source/version"` to audit supplied files. The universe CSV header is `instrument_id,ticker,market,currency,role`. Supported markets are `US` and `NSE`, and roles are `equity` and `benchmark`. Maintain a permanent identifier and symbol mapping in the source manifest. The example IDs represent a starter list only.

Provide one `TICKER.csv` per row with these columns:

| Fields | Contract |
|---|---|
| `session` | ISO trading date in the exchange's local calendar |
| `open,high,low,close` | Prices in the instrument currency, with consistent high/low bounds |
| `volume` | Nonnegative whole shares. Zero volume is flagged and cannot support a fill. |
| `split_ratio` | New shares per old share. Use 1 on days with no split. |
| `cash_dividend` | Cash per post-split share on the effective date. Use 0 on days with no cash dividend. |

Use raw unadjusted OHLC for the causal total-return index. Declare split-adjusted provider data with `--price-basis provider_split_adjusted`. Yahoo's `auto_adjust=False` does not certify raw pre-split prices. The code therefore labels Yahoo results as exploratory. Calendar close plus 30 minutes is a conservative availability assumption for this daily audit. A final source must support verified session exceptions and point-in-time availability. The early implementation requires complete coverage per selected symbol before sealing and needs lifecycle-aware handling before a study can admit mid-window IPOs, delistings, or documented halts. Corporate-action types outside split and cash dividend also require an explicit mapping.

### Approval boundaries

1. A custodian validates raw bars, action provenance, membership/delisting coverage and prior exposure. Stage the canonical unsplit Parquet and manifest with `stage_snapshot` in a private quarantine directory. Supply review evidence alongside the manifest. The coverage CLI only produces a proposal.
2. Record explicit approval for the exact manifest SHA-256 in the operator's SQLite registry. `seal_partitions` then checks that approval and validates the full snapshot bytes. It produces content-addressed development and holdout Parquet in disjoint stores. Keep the approved registry and original snapshot with the custodian. Grant research jobs access to the development store only.
3. Freeze the candidate and record separate approval of its strategy ID, candidate digest, and sealed manifest. The later evaluator will use `evaluate_sealed_once`, which commits a claim before opening the holdout, checks its checksum, and hands verified bytes to the evaluator. Process interruption leaves a durable `STARTED` claim and every claimed date range remains consumed.

The included registry is intended for a single durable local evaluator. The approved CLI/API integration and production storage permissions remain future work. Python methods are operator interfaces, so a separate custodian account and storage controls must enforce access in deployment. No real snapshot or approval is checked into Git. Shared calendars and metadata can be audited before confirmation. No holdout price data is required by CI.
