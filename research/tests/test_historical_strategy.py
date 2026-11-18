from datetime import date

import numpy as np
import pandas as pd
import pytest

from quantedge_research.historical_strategy import adjusted_prices, bootstrap


START = date(2016, 11, 1)
END = date(2024, 11, 1)


def test_development_cutoff_rejects_holdout_bar():
    bars = pd.DataFrame({
        "session": ["2024-10-31", "2024-11-01"],
        "Open": [100, 100], "High": [105, 105], "Low": [99, 99],
        "Close": [102, 102], "Adj Close": [51, 51], "Volume": [1000, 1000],
    })
    with pytest.raises(ValueError, match="only development dates"):
        adjusted_prices(bars, START, END, ticker="SPY")
    prices, adjusted = adjusted_prices(bars.iloc[:1], START, END, ticker="SPY")
    quote = prices[date(2024, 10, 31)]
    assert (quote.open, quote.close, adjusted) == (50, 51, [])


def test_nifty_basis_uses_only_exchange_reconciled_rows():
    snapshot = pd.DataFrame({
        "session": ["2019-12-18", "2019-12-19", "2019-12-20", "2019-12-23"],
        "Open": [128.995, 12.92, 13.495, 131.2],
        "High": [129.432, 13.033, 13.495, 131.25],
        "Low": [128.21, 12.905, 12.978, 129.28],
        "Close": [129.254, 13.02, 13.034, 129.93],
        "Adj Close": [129.254, 13.02, 13.034, 129.93],
        "Volume": [1000, 1000, 1000, 1000],
    })
    prices, adjusted = adjusted_prices(snapshot, START, END, ticker="NIFTYBEES.NS")
    assert adjusted == ["2019-12-19", "2019-12-20"]
    assert prices[date(2019, 12, 19)].close == pytest.approx(130.20)
    assert prices[date(2019, 12, 20)].open == pytest.approx(134.95)
    assert snapshot.loc[1, "Close"] == 13.02
    snapshot.loc[1, "High"] = 14.1
    with pytest.raises(ValueError, match="Unexpected NIFTYBEES"):
        adjusted_prices(snapshot, START, END, ticker="NIFTYBEES.NS")


def test_block_bootstrap_preserves_paired_series_and_starts_at_100():
    returns = np.array([.10, -.10, .05, -.06, .05])
    report = bootstrap(returns, returns, block=2, paths=20, steps=7, seed=2)
    assert report == bootstrap(returns, returns, block=2, paths=20, steps=7, seed=2)
    assert report["bands"]["p50"] == report["fixed_median"]
    assert report["fraction_beating_fixed"] == 0
    assert all(len(band) == 8 and band[0] == 100 for band in report["bands"].values())
