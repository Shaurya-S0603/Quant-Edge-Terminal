# QuantEdge Trend + Volatility v1

The [versioned strategy](strategy-trend-volatility-v1.json) is a long-only overlay for the [approved 16-stock portfolio](approved-portfolio-v1.json). The strategy pins that portfolio's exact file hash. Each country has its own sleeve, cash and benchmark. The strategy never transfers risk or cash between the US and NSE sleeves.

## Trading rules

1. Evaluate at the first completed close of each month. For each holding, compare its current signal close with its signal close 63 sessions earlier. Real runs require a causal corporate-action-aware signal series.
2. Keep that name's allocation in cash if the return is flat or negative, or if warm-up history is incomplete.
3. For a positive trend, estimate annualized volatility from the sample standard deviation of 20 daily log returns, scaled by the square root of 252. Set the target to the approved within-sleeve weight times the smaller of one and 20% divided by the estimated volatility. Use the anchor weight if measured volatility is zero. The 20% figure scales individual positions. It is not a promise about portfolio volatility.
4. Size quantities at that close against current equity and raw close prices. At the next open, model sells before buys and reduce buys proportionally if cash after costs is insufficient. Leave unused allocation in cash instead of redistributing it. Target caps apply at rebalancing and realized weights can drift. The model uses fractional shares and illustrative costs of 5 bps fees plus 10 bps slippage per side.

For example, a stock with an 18% sleeve anchor, a positive trend, and 40% trailing annualized volatility has a 9% target. A negative trend gives it a zero target.

## Reproduce the strategy checks

After setting up the [research environment](README.md#reproduce), run from the repository root:

```sh
PYTHONPATH=src .venv-research/bin/python -m quantedge_research.synthetic_strategy > .data/research/synthetic-trend-volatility.json
```

The command takes strategy and portfolio specifications and generates all prices locally. It does not accept a historical price path. The output includes the configuration hashes, training scores, selected settings, validation metrics, and the two local-currency comparators. See the [example report](trend-volatility-v1.synthetic.json). Run the regression suite with `.venv-research/bin/python -m pytest research/tests`.

The framework runs six one-year validation folds per market. It starts with two years of training and expands training annually. Every rule uses the same training scoring dates after a common warm-up. A six-rule grid compares momentum lookbacks of 42, 63 and 126 sessions, each at 15% or 20% volatility scaling. Selection uses the annualized Sharpe of net daily returns through the training cutoff, with zero cash yield. Ties follow the sorted grid. If every training Sharpe is undefined, the default rule is used. Validation receives only earlier completed sessions for warm-up, opens a fresh cash ledger, and runs the selected rule alongside the fixed default, the approved fixed-weight allocation, and the local ETF reference. Compounding the independently restarted validation folds is a diagnostic, not a continuously held portfolio. The synthetic outcomes do not select or change the proposed default.

## Split and evidence status

The user approved the planned development dates of 1 November 2016 through 31 October 2024 and holdout dates of 1 November 2024 through 31 October 2026. There is no complete research-ready raw snapshot or approved manifest in the workspace. The split therefore has no materialized partitions, and the final holdout remains a separate approval. The strategy has been verified using fabricated data and timing tests. Real historical performance, net costs and any statistical edge remain unmeasured. A real run must integrate verified execution data and corporate actions, including ITC Hotels' entitlement, through the research protocol.
