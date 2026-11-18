# Raw-history and ITC entitlement verification

## Ten-year coverage

The private custodian audit requested all 2,474 NSE sessions from 1 November 2016 through 31 October 2026 using the corrected reference calendar. The workspace had 18 official files, covering 162 validated rows for the eight approved NSE stocks and NIFTYBEES. The remaining 2,456 daily files were absent. There were no parsing failures or unexpected identifier changes in the available files. Coverage is incomplete. The US sleeve still has no verified unadjusted source package in the workspace. Complete calendar coverage from Yahoo did not establish raw-price provenance.

The offline custodian mode inspects only local archive files and emits session coverage, archive hashes, and identity metadata. It cannot certify completeness for a sample, seal a split, or run a strategy. The ordinary command remains development-only. Keep the input in private storage. NSE's public website terms prohibit systematic automated collection. The exchange separately describes academic and non-commercial data access, including a request route for larger datasets. Use an authorized archive export or a licensed provider. [NSE website terms](https://betanseapi.nseindia.com/static/nse-terms-of-use) · [NSE research data access](https://betanseapi.nseindia.com/static/research/initiatives-data-for-research) · [US data coverage candidate](https://norgatedata.com/data-content-tables.php)

With an authorized local collection, purchase or credential management is outside this command:

```sh
PYTHONPATH=src .venv-research/bin/python -m quantedge_research.nse_raw \
  --baseline research/approved-portfolio-v1.json \
  --archive-dir /private/nse-archive \
  --end-exclusive 2026-11-01 --custodian-full-window
```

## Resolved archive identity changes

Official circulars establish the split dates and ratios. Official EQ rows on each ex-date and the following session establish the identifiers actually printed in the daily files. These dates describe different events. Apply economic split adjustments on the ex-date, and use the archive transition to join physical source rows. The audit checks both verified identifiers without rewriting prices or treating identifier changes as automatic splits.

| Ticker | Economic ex-date | Split | Old archive ISIN on ex-date | New archive ISIN observed next day | Evidence |
|---|---|---:|---|---|---|
| HDFCBANK.NS | 19 September 2019 | 2 for 1 | `INE040A01026` | `INE040A01034` on 20 September | [Listing split circular](https://nsearchives.nseindia.com/content/circulars/CML41992.pdf) · [Clearing circular](https://nsearchives.nseindia.com/content/circulars/CMPT42091.pdf) |
| NIFTYBEES.NS | 19 December 2019 | 10 for 1 | `INF732E01011` | `INF204KB14I2` on 20 December | [Listing ISIN circular](https://archives.nseindia.com/content/circulars/CML42888.pdf) · [Clearing circular](https://nsearchives.nseindia.com/content/circulars/CMPT42889.pdf) |

These mappings resolve the two transitions found in the [pilot](nse-raw-source-pilot-2026-11-18.md). They do not establish that no other corporate actions occurred. If an identifier appears outside the verified bounds or a third identifier appears, the audit reports a mismatch and returns failure.

## ITC Hotels valuation evidence

| Input | Verified evidence | Open item |
|---|---|---|
| Prelisting reference | Exchange methodology uses the last cum-entitlement close and the parent price discovered in the special pre-open session. The two official ITC EQ archives produced a positive ratio-scaled reference from the prior close and ex-day open. It agreed with contemporaneous reporting. The ex-day previous-close field did not represent the discovered parent price. [Exchange circular](https://nsearchives.nseindia.com/content/circulars/CMTR65845.pdf) · [Index methodology notice](https://www.niftyindices.com/Press_Release/ind_prs26042023.pdf) · [Contemporaneous corroboration](https://www.fortuneindia.com/investing/itchotelsshares-debut-at-188-down-30-over-last-discovered-price/120204) | A timed record of the actual auction outcome is needed to certify the mark's point-in-time availability. |
| Traded market marks | Verified nonzero-volume ITC Hotels archive rows on 29 January 2025 (BE listing session) and 11 February 2025 (first EQ session), both with ISIN `INE379A01028`. [Listing notice](https://nsearchives.nseindia.com/web/sites/default/files/2025-01/PR_list_27012025.pdf) · [Series transition](https://nsearchives.nseindia.com/content/circulars/CML66367.pdf) | The remaining child daily series and document-verified availability are needed for a continuous valuation series. |
| Fractional settlement | The issuer confirms sale of the consolidated shares and pro rata net distribution after expenses and applicable taxes. [Issuer notice](https://www.itchotels.com/dividend-iepf) | The reviewed documents did not establish net cash and credit time for a specified fractional entitlement. Use a trustee or registrar statement with its date and applicable treatment. |

The verification tool reads four authorized local archives and reports identifiers and archive hashes. It supplies neither a trusted price timestamp nor a cash receipt. Actual holdout prices stay in private source material. The strategy and entitlement valuation helpers were not run on real holdout data.

```sh
PYTHONPATH=src .venv-research/bin/python -m quantedge_research.entitlement_evidence \
  --archive-dir /private/nse-entitlement-archives
```

The holdout remains unsealed. A continuous authorized raw source, complete action and membership evidence, and the exposure review are prerequisites for submitting the split for approval.
