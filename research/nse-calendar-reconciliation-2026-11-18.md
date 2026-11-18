# NSE session and archive audit

The original [portfolio coverage audit](approved-portfolio-audit-2026-11-18.md) used the pinned package calendar. This update applies exchange-confirmed cash-market exceptions and reruns coverage for the same approved 16-stock configuration and two market benchmarks. It records ticker presence and timestamps. No prices or strategy results are published.

| NSE date | Calendar action | Normal market hours, India time | Exchange source |
|---|---|---|---|
| 27 October 2019 | Add Muhurat session | 18:15–19:15 | [NSE/CMTR/42483](https://nsearchives.nseindia.com/content/circulars/CMTR42483.pdf) |
| 14 November 2020 | Add Muhurat session | 18:15–19:15 | [NSE/CMTR/46230](https://nsearchives.nseindia.com/content/circulars/CMTR46230.pdf) |
| 1 February 2025 | Add Union Budget session | 09:15–15:30 | [NSE/CMTR/65729](https://nsearchives.nseindia.com/content/circulars/CMTR65729.pdf) |
| 15 January 2026 | Mark closed for election holiday | Closed | [NSE/CMTR/72260](https://nsearchives.nseindia.com/content/circulars/CMTR72260.pdf) |
| 1 February 2026 | Add Union Budget session | 09:15–15:30 | [NSE/CMTR/72349](https://nsearchives.nseindia.com/content/circulars/CMTR72349.pdf) |

The audit retains the 30-minute delay from the scheduled normal market close. That delay is a modeling assumption, and source-specific availability still needs verification. These are targeted corrections, not a certification of every NSE session over ten years.

## Updated coverage

All 18 instrument queries succeeded. The corrected NSE schedule has 1,980 development sessions and 494 proposed holdout sessions. Yahoo matched 1,978 and 493 respectively for each of the eight approved Indian stocks. NIFTYBEES matched 1,978 and 492. The nine US series still matched their reference calendar completely. Yahoo returned an off-calendar row for the 15 January 2026 holiday in all nine NSE series. These rows are excluded.

| Confirmed Yahoo gap | Missing from Yahoo | NSE archive check |
|---|---|---|
| 13 February 2019 | All nine NSE series | All nine present in the EQ series. [Official daily file](https://nsearchives.nseindia.com/content/historical/EQUITIES/2019/FEB/cm13FEB2019bhav.csv.zip) |
| 29 March 2019 | All nine NSE series | All nine present in the EQ series. [Official daily file](https://nsearchives.nseindia.com/content/historical/EQUITIES/2019/MAR/cm29MAR2019bhav.csv.zip) |
| 24 October 2025 | NIFTYBEES | NIFTYBEES and all eight equities present in the EQ series. [Official daily file](https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20251024_F_0000.csv.zip) |
| 1 February 2026 | All nine NSE series | All nine present in the EQ series. [Official daily file](https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20260201_F_0000.csv.zip) |

The archive check validates trading dates and separates EQ from other series. It emits coverage and hashes. It does not patch Yahoo with official prices, which would mix price bases. For reproducibility, the corrected NSE schedule checksum is `931b8c1aadb2fbcaf4a2eeb3abaef3b5abc460f32cd7086f8560b10813e1388a` and the configuration ID is `us-nse-four-profile-v1`.

Run the Yahoo audit using the [research quickstart](README.md). Run the official evidence check separately.

```sh
PYTHONPATH=src .venv-research/bin/python -m quantedge_research.nse_archive \
  --baseline research/approved-portfolio-v1.json \
  --session 2019-02-13 --session 2019-03-29 \
  --session 2025-10-24 --session 2026-02-01
```

Pass `--archive-dir` to review local copies of the original official ZIPs by filename. A SHA-256 binds that report to the inspected bytes. File provenance still depends on where the ZIP was obtained.

## Corporate-action finding

ITC's hotel demerger became effective on 1 January 2025. Shareholders of record on 6 January received ITC Hotels shares. This case needs share-entitlement and valuation handling beyond the current split and cash-dividend schema. The audit now flags this known action and the snapshot staging logic marks it unresolved even when the ordinary action fields are populated. The event list covers verified cases entered so far. [ITC 2025 annual report](https://itcportal.com/content/dam/itc-corporate/pdfs/report-and-accounts/ITC-Report-and-Accounts-2025.pdf)

An eligible split manifest still needs a consistent raw-price series, verified actions, point-in-time membership and delisting information, and a prior-exposure review. No approval was registered by these checks. The draft PR remains at the split checkpoint.
