# Approved comparison portfolio coverage

This report records the original calendar comparison. See the [reconciled NSE audit](nse-calendar-reconciliation-2026-11-18.md) for verified trading-session corrections and updated coverage.

The [portfolio configuration](approved-portfolio-v1.json) records the 16 stocks and weights approved on 18 November 2026. The weights are fixed research targets and the ticker list is the candidate universe. Compare each market in local currency. SPY and NIFTYBEES.NS are reference benchmarks and carry no target allocation.

| Profile | Weight across both markets | Weight per holding |
|---|---:|---:|
| High-volatility movers | 12% | 3% |
| Liquid large caps | 36% | 9% |
| Slow-moving stocks | 24% | 6% |
| Dividend and stability | 28% | 7% |

The configuration assigns 50% to each market. For local-currency sleeve comparisons, normalize each sleeve to 100%. Candidate screening used daily returns from 1 November 2021 through 31 October 2024. Freeze this configuration alongside future strategy trials. Rebalance timing, costs, and a combined currency accounting policy still require implementation. Selecting these names is a present-day decision using historical development-period prices, so the portfolio remains a selected basket with survivorship and selection limitations.

## Coverage

Audited 18 November 2026 at 12:47 Singapore time with Yahoo Finance. Configuration ID `us-nse-four-profile-v1` and SHA-256 `e1eaa112ec21e1a43c5728347ac04d58300f5ed4291b20eee98826d15556f59f`.

The unsealed candidate dates are 1 November 2016 through 31 October 2024 for development and 1 November 2024 through 31 October 2026 for the holdout. No prices or strategy results are included here. The counts compare valid observations to the pinned reference calendar, which omits known NSE special sessions.

| Ticker | Role | Development sessions | Proposed holdout sessions | Off-calendar dates | Zero-volume rows |
|---|---|---:|---:|---:|---:|
| NVDA | equity | 2013/2013 | 500/500 | 0 | 0 |
| TSLA | equity | 2013/2013 | 500/500 | 0 | 0 |
| ADANIPORTS.NS | equity | 1976/1978 | 492/492 | 4 | 1 |
| HINDALCO.NS | equity | 1976/1978 | 492/492 | 4 | 1 |
| MSFT | equity | 2013/2013 | 500/500 | 0 | 0 |
| AMZN | equity | 2013/2013 | 500/500 | 0 | 0 |
| RELIANCE.NS | equity | 1976/1978 | 492/492 | 4 | 1 |
| HDFCBANK.NS | equity | 1976/1978 | 492/492 | 4 | 1 |
| WM | equity | 2013/2013 | 500/500 | 0 | 0 |
| JNJ | equity | 2013/2013 | 500/500 | 0 | 0 |
| HINDUNILVR.NS | equity | 1976/1978 | 492/492 | 4 | 1 |
| SUNPHARMA.NS | equity | 1976/1978 | 492/492 | 4 | 1 |
| KO | equity | 2013/2013 | 500/500 | 0 | 0 |
| DUK | equity | 2013/2013 | 500/500 | 0 | 0 |
| POWERGRID.NS | equity | 1976/1978 | 492/492 | 4 | 1 |
| ITC.NS | equity | 1976/1978 | 492/492 | 4 | 0 |
| SPY | benchmark | 2013/2013 | 500/500 | 0 | 0 |
| NIFTYBEES.NS | benchmark | 1976/1978 | 491/492 | 4 | 3 |

## Interpretation

- Yahoo returned all 18 requested series. No malformed bars, duplicate session rows, or unfinished bars were flagged. All nine US series matched the reference calendar.
- All nine NSE series missed 13 February and 29 March 2019. Yahoo also omitted NIFTYBEES.NS on 24 October 2025. Official files and the interpretation of three special sessions and one trading holiday are linked in the [original reconciliation](coverage-audit-2026-11-18.md#split-readiness).
- Clean US calendar matches do not resolve corporate-action provenance, point-in-time membership, or prior exposure. The expanded NSE basket needs the same coverage and calendar reconciliation as the starter universe.
- Approval of these tickers authorizes their use as research inputs. Split approval still requires an eligible, reviewed data manifest. Holdout execution requires a later approval of a frozen candidate. The audit registered neither approval and performed no evaluation.
