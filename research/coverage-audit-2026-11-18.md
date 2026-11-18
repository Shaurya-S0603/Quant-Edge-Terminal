# Historical coverage proposal

Ran on 18 November 2026 at 11:59 Singapore time against Yahoo Finance through yfinance with a locked Python environment. This is an **unsealed coverage audit**. It stores no Yahoo price observations in the repository and contains no model results.

| Partition | Inclusive start | Exclusive end |
|---|---|---|
| Development | 2016-11-01 | 2024-11-01 |
| Proposed holdout | 2024-11-01 | 2026-11-01 |

All 22 symbols returned history. Across the audited window, validation found no malformed OHLCV rows, duplicate session keys, or unfinished candles. Counts below are matched observations relative to the pinned exchange calendar. The holdout dates are shown only as metadata.

| Ticker | Role | Development sessions | Proposed holdout sessions | Off-calendar dates | Zero volume rows |
|---|---|---|---|---|---|
| AAPL | equity | 2013/2013 | 500/500 | 0 | 0 |
| MSFT | equity | 2013/2013 | 500/500 | 0 | 0 |
| NVDA | equity | 2013/2013 | 500/500 | 0 | 0 |
| AMZN | equity | 2013/2013 | 500/500 | 0 | 0 |
| GOOGL | equity | 2013/2013 | 500/500 | 0 | 0 |
| META | equity | 2013/2013 | 500/500 | 0 | 0 |
| TSLA | equity | 2013/2013 | 500/500 | 0 | 0 |
| JPM | equity | 2013/2013 | 500/500 | 0 | 0 |
| V | equity | 2013/2013 | 500/500 | 0 | 0 |
| JNJ | equity | 2013/2013 | 500/500 | 0 | 0 |
| XOM | equity | 2013/2013 | 500/500 | 0 | 0 |
| SPY | benchmark | 2013/2013 | 500/500 | 0 | 0 |
| RELIANCE.NS | equity | 1976/1978 | 492/492 | 4 | 1 |
| TCS.NS | equity | 1976/1978 | 492/492 | 4 | 1 |
| INFY.NS | equity | 1976/1978 | 492/492 | 4 | 1 |
| HDFCBANK.NS | equity | 1976/1978 | 492/492 | 4 | 1 |
| ICICIBANK.NS | equity | 1976/1978 | 492/492 | 4 | 1 |
| SBIN.NS | equity | 1976/1978 | 492/492 | 4 | 1 |
| ITC.NS | equity | 1976/1978 | 492/492 | 4 | 0 |
| BHARTIARTL.NS | equity | 1976/1978 | 492/492 | 4 | 1 |
| LT.NS | equity | 1976/1978 | 492/492 | 4 | 1 |
| NIFTYBEES.NS | benchmark | 1976/1978 | 491/492 | 4 | 3 |

## Split readiness

- **US.** All twelve instruments matched the NYSE reference calendar completely. That does not verify symbol histories, point-in-time universe membership or corporate-action coverage.
- **NSE provider gaps.** Every symbol missed 2019-02-13 and 2019-03-29 relative to the pinned calendar. NIFTYBEES.NS also missed 2025-10-24. The official cash-market archives returned a valid file and contained NIFTYBEES on all three dates. This is evidence of a source coverage discrepancy. The audit checked symbol presence without exposing or storing prices. [13 February archive](https://nsearchives.nseindia.com/content/historical/EQUITIES/2019/FEB/cm13FEB2019bhav.csv.zip) · [29 March archive](https://nsearchives.nseindia.com/content/historical/EQUITIES/2019/MAR/cm29MAR2019bhav.csv.zip) · [24 October archive](https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20251024_F_0000.csv.zip)
- **NSE calendar exceptions.** Every symbol contained 2019-10-27, 2020-11-14 and 2025-02-01, which the pinned calendar omitted. NSE documents special live sessions on the first and third dates, and a valid cash-market file confirms trading on the second. Yahoo also returned 2026-01-15, which NSE lists as an equity trading holiday. Reconcile exact session timing against a sourced override file before using these dates for simulated fills. [October 2019 circular](https://nsearchives.nseindia.com/content/circulars/CMTR42483.pdf) · [November 2020 archive](https://nsearchives.nseindia.com/content/historical/EQUITIES/2020/NOV/cm14NOV2020bhav.csv.zip) · [February 2025 circular](https://nsearchives.nseindia.com/content/circulars/CMTR65729.pdf) · [January 2026 circular](https://nsearchives.nseindia.com/content/circulars/CMPL72311.pdf)
- **Source adjustment and membership.** Yahoo's split-adjusted history is useful for coverage and exploratory work. Execution-grade modeling requires original prices, audited distributions/actions, and historically eligible instruments including delistings. The supplied starter list contains present-day names only. [yfinance adjustment notes](https://ranaroussi.github.io/yfinance/advanced/price_repair.html)
- **Prior exposure.** The legacy notebook downloaded GOOG from 2021 to its runtime date. GOOG and GOOGL are distinct share classes of the same issuer. The related exposure and the date coverage previously explored in either QuantEdge app must be documented before treating this interval as blind. See the [baseline audit](../docs/RESEARCH_BASELINE.md).

The candidate dates are suitable for discussing coverage. The current Yahoo snapshot is **ineligible for sealing**. The next approvable manifest needs verified inputs, explicit exclusions, and a prior-exposure review. Norgate documents historical US constituents and delisted equities, with coverage dependent on subscription. For NSE, the exchange documents historical cash-market security/trade files. Both are leads to verify, and neither solves prior exposure. Confirm raw price basis, actions, membership, licensing, and terminal handling before selecting a source. [Norgate coverage](https://norgatedata.com/data-content-tables.php) · [NSE historical coverage](https://nsearchives.nseindia.com/content/press/Data_details_CM.pdf) · [NSE research data policy](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Data%20list%20under%20NSE%20Data%20Sharing%20Policy%20for%20Research%20and%20Analysis_20250728.pdf)
