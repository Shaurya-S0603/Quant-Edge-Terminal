# QuantEdge research baseline

Audited on 18 November 2026. The GitHub checkout started from `main` at [42ed37c8](https://github.com/Shaurya-S0603/Quant-Edge-Terminal/commit/42ed37c8e8e5dc686d8a1d93856bb1dab449f58c). [Python CI](https://github.com/Shaurya-S0603/Quant-Edge-Terminal/actions/runs/38701915950) and [full-stack connectivity CI](https://github.com/Shaurya-S0603/Quant-Edge-Terminal/actions/runs/38701916013) passed on that commit.

| Existing asset | Decision for the research rebuild |
|---|---|
| `apps/web`, `apps/api`, `infra` | Keep the Next.js presentation and same-origin API routes, FastAPI integration, GitHub sign-in, PostgreSQL watchlists, Redis limits, migration and CI checks. Keep evaluation in a separate Python process. |
| `src/stockmarket/workspace/strategy_backtest.py` and its tests | Retain as a legacy compatibility engine and an independent next-open test reference. The preview imports it. The new engine needs multi-asset accounting, corporate actions, and a benchmark with explicit costs. |
| Indicators, historical adapters, CSV import and archive tooling | Preserve the useful validation and regression cases. The existing real-data API is opt-in, caps history at one year, and cannot certify the final candle is complete. Its responses are unsuitable as ten-year snapshots. |
| Streamlit v2.1.1 | Keep shared code, entry points, release notes, recovery tools and CI tests through migration. GitHub already has a published release at `fbd640d`. Superseded docs move into the archive. |
| Local holdings and account history | The repository has no tracked portfolio database. An existing local database or backup would require a separate private import with a verified backup. It is not needed for the historical research prototype. |
| Historical dataset | No tracked OHLCV CSV, Parquet snapshot, or database was found. Git history also yielded no tracked files in these formats. Synthetic fixtures, saved notebook outputs and screenshots cannot supply ten years of audited bars. Use the conversation's US and NSE universe as a seed and verify coverage before proposing a split. |

## Notebook concepts

Two notebooks remain in Git history. Review covered the [later notebook](https://github.com/Shaurya-S0603/Quant-Edge-Terminal/blob/30c2346/STOCK_MARKET_ANALYSIS.ipynb) and [an earlier variant](https://github.com/Shaurya-S0603/Quant-Edge-Terminal/blob/42292de/STOCK_MARKET_ANALYSIS%20(1).ipynb). The ideas worth preserving are a moving-average baseline, lagged features, and comparison against gradient boosting. GOOG is one explicitly referenced ticker. The later notebook requests GOOG history from 1 January 2021 through its runtime date. An earlier variant contains saved output dated June 2025. Treat this as evidence of possible overlap with a proposed holdout. The notebooks do not provide the underlying audited dataset. The later version fits its parameter search on the full feature matrix before the chronological split. Its reported test result cannot serve as independent validation. Carry the concepts into the new architecture using independently written code. Check the notebook's actual data dates and any other previously viewed dates during the data audit before labeling an interval as blind.

## Cleanup boundary

The active README and deployment plan distinguish research development from legacy operation. Historical phase notes and deployment instructions are archived. The checkout retains shared engine code and previously released entry points because removing them now would break the preview or its regression tests. Later removal requires a passing replacement, a verified migration where relevant, and a rollback release. Checkout history and published tags supply the original docs and notebook versions.
