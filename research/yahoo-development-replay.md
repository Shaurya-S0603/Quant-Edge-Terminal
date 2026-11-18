# QuantEdge Strategy Lab

Made by Shaurya Singhal.

The [hosted Strategy Lab](https://quantedge-strategy-lab.skippingepoch8.chatgpt.site) presents the replay and simulation controls. The Site is owner-private.

This historical replay covers the approved eight-year development window from 2016-11-01 inclusive to 2024-11-01 exclusive. The two-year window from 2024-11-01 through 2026-10-31 was excluded from all replay inputs and simulations. The run neither registers a research-grade raw-price snapshot nor claims the single-use holdout. The website presents development analysis.

## Data and adjustments

The run downloaded one Yahoo Finance daily history for each of 16 approved stocks and two local ETF references, SPY and NIFTYBEES.NS. A private CSV folder preserves Yahoo's delivered Open, High, Low, Close, Adjusted Close, Volume and action fields with exchange-local session labels. The full derived report records each input SHA-256 and the pinned strategy and basket digests. Yahoo's split-adjusted OHLC is a vendor history, so it cannot establish original prices, order quantities or entitlement cash flows. The engine uses `adjusted open = Open × Adj Close / Close` and Yahoo's adjusted close as a consistent total-return proxy, with no separate dividend or split cash flows. The data can be revised by the vendor. [Yahoo Finance adjusted close](https://help.yahoo.com/kb/SLN28256.html) · [yfinance history options](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html)

Validation checked unique and ordered dates, the exclusive boundary, finite positive OHLC and adjusted close, bar ranges, nonnegative volume, and an outlier review threshold of 40% absolute close-to-close return. US traded on 2,013 of 2,013 expected sessions. NSE covered 1,978 of 1,980 and omitted 2019-02-13 and 2019-03-29 across the full panel. Values were never forward-filled. Calendar logic and NSE session amendments are shared with the project data audit.

### Nifty BeES split reconciliation

The NSE face-value split notice and official daily EQ rows show that Yahoo's 2019-12-19 and 2019-12-20 prices were scaled down an extra factor of ten. The surrounding 2019-12-18 and 2019-12-23 rows reconcile to the common post-split basis. The loader multiplies the two affected rows' OHLC and adjusted close by 10 only when observed OHLC numerically matches the official row on the lower scale. It does not change the CSV snapshot or any other symbol or session. If Yahoo corrects the two rows to the verified scale, the adjustment is skipped. The exchange reports a change from ISIN `INF732E01011` to `INF204KB14I2`. Volume plays no role in strategy sizing or fills. [NSE circular CML42873](https://archives.nseindia.com/content/circulars/CML42873.pdf) · [Fund factsheet](https://mf.nipponindiaim.com/investorservices/factsheetsdocuments/fundamentals-august-2021/Innerpage/ETF-Nifty-BeES.html)

| Official archive session | Exchange archive |
| --- | --- |
| 2019-12-18 | [cm18DEC2019bhav.csv.zip](https://nsearchives.nseindia.com/content/historical/EQUITIES/2019/DEC/cm18DEC2019bhav.csv.zip) |
| 2019-12-19 | [cm19DEC2019bhav.csv.zip](https://nsearchives.nseindia.com/content/historical/EQUITIES/2019/DEC/cm19DEC2019bhav.csv.zip) |
| 2019-12-20 | [cm20DEC2019bhav.csv.zip](https://nsearchives.nseindia.com/content/historical/EQUITIES/2019/DEC/cm20DEC2019bhav.csv.zip) |
| 2019-12-23 | [cm23DEC2019bhav.csv.zip](https://nsearchives.nseindia.com/content/historical/EQUITIES/2019/DEC/cm23DEC2019bhav.csv.zip) |

## Strategy and evaluation

1. Use the approved within-market basket weights as caps. Start with 100,000 units of local currency. After 64 warm-up closes, start each continuous ledger on the same session for that market (2017-02-03 US and 2017-02-01 NSE).
2. Use nonpositive 63-session total return as a cash signal. For a positive signal, scale the cap by the lesser of one and 20% divided by the 20-session annualized log-return sample standard deviation.
3. Set order quantities from the completed close on the first observed session of a month. Execute at the next observed open with fractional units, sells first and pro-rata scaling if buys exceed cash. Model 5 bps fees and 10 bps slippage per side, zero cash yield, and local currencies without FX aggregation. Ignore taxes, market impact, spreads beyond the modeled slippage and capacity. Final holdings are marked at closing proxy prices.
4. Compare gross and net strategy returns with the net fixed-weight monthly basket and local buy-and-hold ETF. Compute CAGR using elapsed calendar time through the exclusive end date, annualized realized volatility and zero-rate Sharpe using 252 observations per year, and daily mark-to-market peak-to-trough drawdown. Run six annually restarted checks with six parameter pairs selected using earlier development sessions only. [Strategy specification and sources](trend-volatility-strategy.md)
5. Draw 2,000 moving-block paths of 252 returns using a fixed seed of 41321. Pair the overlay and fixed-basket paths by resampling identical dates within each contiguous block. The page shows pointwise 5th–95th and 25th–75th wealth bands, medians and terminal path comparisons. The display allows 10-, 20- and 60-session blocks. These are descriptive scenarios conditional on the observed development sample. [Künsch, 1989](https://doi.org/10.1214/aos/1176347265)

## Net continuous results

| Market | Strategy CAGR | Fixed basket CAGR | Strategy max drawdown | Fixed basket max drawdown | Strategy Sharpe | Fixed basket Sharpe |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| US (USD) | 9.98% | 23.68% | 17.89% | 29.16% | 1.00 | 1.22 |
| NSE (INR) | 8.61% | 20.28% | 14.64% | 33.97% | 1.03 | 1.23 |

The overlay reduced drawdown and volatility in both markets. It also held 40.58% average closing cash in the US and 44.59% in NSE, and trailed the fixed basket on return and Sharpe. Retrospective universe selection, surviving listings, vendor restatements, unverified actions beyond the targeted split and the simplified fill model limit attribution. The replay does not establish a multiple-testing-adjusted edge. This run does not report a probabilistic or deflated Sharpe, a Reality Check or a final holdout result.

## Reproduce

Use Python 3.12 and install the pinned dependencies from `research/requirements-py312.lock`. From the project root, run the command below. On Windows PowerShell, set `$env:PYTHONPATH = 'src'` and run the Python command on one line.

```bash
PYTHONPATH=src python -m quantedge_research.historical_strategy --fetch \
  --snapshot .data/research/yahoo-development-v1 \
  --output .data/research/yahoo-development-v1-report.json \
  --site-output .data/research/quantedge-site/report.json
```

Remove `--fetch` to rerun entirely from the saved input CSVs. Keep those files private. Copy the three files from `research/site/` into `.data/research/quantedge-site/` and serve that directory with any static HTTP server. The Sites deployment contains the same frontend and the portfolio-only JSON. It contains no Yahoo CSVs or individual price series. Site access follows its configured audience.
