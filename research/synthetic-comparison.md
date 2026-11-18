# Fixed-weight comparison backtester

This prototype exercises the approved 16-stock allocation with fabricated prices. It runs offline and accepts no price-file path. The existing development and holdout approval gates still apply to real data.

Run from the repository root after [installing the research environment](README.md#reproduce).

```sh
PYTHONPATH=src .venv-research/bin/python -m quantedge_research.synthetic_comparison   --cash 100000 --fee-bps 5 --slippage-bps 10
```

The report includes the approved baseline hash, deterministic random seed, local currency, gross and net return, turnover, maximum drawdown, fees, slippage and fill count. Each market has its own capital and benchmark. SPY and NIFTYBEES are labels for synthetic reference series in this run. The market schedules are real 2023 exchange calendars, while all prices are simulated.

## Execution model

- Normalize the approved nominal weights within each market. Begin in cash. At the first completed close of each month, size fractional-share orders using the portfolio equity and prices available at that close. At the next session open, use the signed order quantities and reference opening prices to calculate fills. An order sized at the final close has no fill.
- Apply sells first. If the proposed buys and costs exceed cash, scale buy quantities proportionally. This prototype models an opening fill and cash check, rather than asserting that a real opening auction can resize all orders after prices are observed.
- Charge fees and slippage as separate basis-point charges on absolute opening notional. The defaults of 5 and 10 basis points are illustrative and are not market estimates.
- Record close equity and cash without forced liquidation. Gross results rerun with zero costs, so position sizes can differ from the net run. Dollar cost drag can include the resulting exposure difference. Turnover sums two-sided filled notional divided by pre-trade equity at each open, including the initial entry. Maximum drawdown is reported as a nonnegative peak-to-trough fraction.
- The reference portfolio uses the same initial decision and commission model, then holds its reference asset. A favorable opening gap can leave cash from the close-sized order in either portfolio.

This prototype assumes complete, tradable opening prices and fractional shares. Real-data integration must handle corporate actions, including the outstanding ITC event, trading constraints, market-specific lots, and cost calibration. The prototype has no FX aggregation, borrow or capacity estimates. No performance conclusion should be drawn from fabricated data.

Unit tests cover order timing, prefix invariance, sells before buys, cash-constrained fills, fees and slippage, drawdown, late-data rejection, and deterministic outputs for both approved sleeves.
