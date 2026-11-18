# NSE raw-price pilot and ITC Hotels entitlement

The [source-readiness follow-up](source-readiness-2026-11-18.md) resolves the two identifier changes and checks actual archive inputs for the entitlement.

The official NSE cash-market archive is a plausible single exchange source for unadjusted NSE fills. This pilot checked six selected trading sessions within the proposed development period. It parsed official prices and quantities, with archive hashes and security identifiers. The report contains metadata only. No holdout price file was read by this pilot.

## Raw-price validation

Nine expected EQ instruments were present on each of the six dates. OHLC bounds, positive finite prices, whole-share volume, trading date, and ISIN syntax passed validation. The two Yahoo gaps from 2019 were present in the official source. The pilot read sample files from either side of the legacy-to-UDiFF format transition. It did not combine exchange prices with Yahoo-adjusted data.

| Development date | Archive format | Instruments |
|---|---|---:|
| 1 November 2016 | Legacy | 9/9 |
| 13 February 2019 | Legacy | 9/9 |
| 29 March 2019 | Legacy | 9/9 |
| 5 July 2024 | Legacy | 9/9 |
| 8 July 2024 | UDiFF | 9/9 |
| 31 October 2024 | UDiFF | 9/9 |

The pilot observed two ticker-level identifier changes.

| Ticker | Identifiers observed |
|---|---|
| HDFCBANK.NS | `INE040A01026`, `INE040A01034` |
| NIFTYBEES.NS | `INF732E01011`, `INF204KB14I2` |

These observations flag a need for dated mappings before chaining returns. The audit does not infer an action ratio or effective date from the identifier change. Validate the full archive, map each identifier and effective-date change to official documentation, and obtain corporate actions separately. The archive is a daily trading record and is insufficient by itself for point-in-time membership or delisting treatment. A lawfully accessible US raw-price source still needs separate validation.

Reproduce using authentic official ZIPs in a private directory. Preserve the filenames and keep the source separate from adjusted data. The CLI emits metadata and returns a nonzero status for missing or failed requested coverage.

```sh
PYTHONPATH=src .venv-research/bin/python -m quantedge_research.nse_raw \
  --baseline research/approved-portfolio-v1.json \
  --archive-dir .data/research/nse-raw-pilot \
  --end-exclusive 2026-11-01 \
  --session 2016-11-01 --session 2019-02-13 --session 2019-03-29 \
  --session 2024-07-05 --session 2024-07-08 --session 2024-10-31
```

The metadata report includes the archive hash for each session. The command defaults to auditing every development session from local files. It rejects explicit requests for a holdout session before opening any price file. Authenticity relies on acquisition from the exchange or another verified custodian. [NSE historical reports](https://www.nseindia.com/resources/historical-reports-capital-market-daily-monthly-archives) · [NSE historical data specification](https://nsearchives.nseindia.com/content/press/Data_details_CM.pdf)

## ITC Hotels entitlement accounting

For ITC, the scheme took effect on 1 January 2025. The ex-date and record date were 6 January. Eligible holders received one ITC Hotels share per ten ITC shares. Allotment took place on 11 January and listing on 29 January. ITC Hotels began trading in the NSE BE series and moved to EQ on 11 February. Fractional entitlements were handled through trustee sale proceeds. [ITC annual report](https://itcportal.com/content/dam/itc-corporate/pdfs/report-and-accounts/ITC-Report-and-Accounts-2025.pdf) · [Exchange ex-date and ratio circular](https://nsearchives.nseindia.com/content/circulars/FAOP65846.pdf) · [NSE listing release](https://nsearchives.nseindia.com/web/sites/default/files/2025-01/PR_list_27012025.pdf) · [NSE series transition](https://nsearchives.nseindia.com/content/circulars/CML66367.pdf) · [ITC entitlement and fractions](https://itcportal.com/content/dam/itc-corporate/open-pdfs/investor/proposed-demerger-of-hotels-business/lodr-14aug23c.pdf)

The valuation helper takes the eligible settled parent-share count from the future position engine. For example, 105 eligible ITC shares create a claim to ten whole ITC Hotels shares plus a fractional claim of one-half share. Before listing, value is unknown until a sourced reference mark becomes available. After listing, a timestamped market mark is required. Verified trustee cash replaces the fractional claim when available. The helper keeps the parent position intact, does not round away fractions, and does not produce fills. The simple split-and-dividend total-return index refuses to cross this event.

All entitlement calculations in tests use synthetic amounts. The real prelisting mark, traded mark series, and trustee cash records must still be sourced and bound to the approved snapshot. ITC Hotels is an entitlement instrument for valuation, outside the approved target-weight universe. A later runner must integrate its position movements and trading constraints. Until these inputs are verified, the manifest still flags the demerger as unresolved. No split approval or holdout evaluation took place.
