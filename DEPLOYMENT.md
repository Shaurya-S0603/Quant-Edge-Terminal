# QuantEdge research deployment plan

Ready for review. Approval of this plan starts Phase 1. The data split and final evaluation each require separate approval.

## Architecture

```text
Historical sources -> Ingestion and audit -> Immutable Parquet + manifest
                                               |                 |
                                      Development subset     Sealed holdout
                                               |                 |
                                   Python research CLI      Isolated evaluator
                                               |                 ^
                                Walk-forward + trial log        |
                                               |                 |
                                    Candidate freeze -> Approval + registry claim
                                                                 |
                                                         Immutable report
                                                                 |
                                         Next.js -> FastAPI read-only views
```

Use the existing Next.js and FastAPI applications for presentation, PostgreSQL for existing authenticated watchlists, and Redis for request limits where needed. The research CLI owns the holdout. Start with one durable SQLite registry on local storage accessible only to the single evaluator, plus immutable Parquet and result artifacts. Hosted web and CI receive synthetic fixtures or explicitly approved read-only exports. They receive no holdout credentials, registry write access, or arbitrary strategy execution. Move the registry to a transactional service only if multiple evaluator hosts become necessary.

## Phases and acceptance gates

| Phase | Deliverable | Release condition |
|---|---|---|
| 0. Audit and cleanup | Inventory current code, legacy releases, notebook ideas, data and deployment dependencies. Archive superseded documentation. | Review this plan and the [baseline audit](docs/RESEARCH_BASELINE.md). |
| 1. Historical data and protocol | Add locked Python environment, import contracts, exchange calendars, raw corporate actions, validation reports, immutable snapshots, and registry migrations. Audit a candidate ten-year window using source, currency, adjustment, missing/delisted security coverage and prior exposure. | Integrity, corporate action and registry tests pass. **Pause for split approval** with dates, coverage, exclusions, exposure findings and manifest hash. |
| 2. Development-only research | Add causal features, risk-adjusted forward labels, grouped purged walk-forward folds, factor and boosted-tree baselines, a trial ledger, and a multi-asset cost-aware simulator. Publish development-only diagnostics and candidate comparisons. | Prefix-invariance and next-open fill tests pass. Gross-to-net accounting reconciles. Development evidence is reproducible from a clean checkout without holdout access. |
| 3. Private staging | Build pinned Next.js and FastAPI images. Run production builds and cross-service smoke tests with synthetic fixtures. Exercise migrations, access boundaries, backups, and restore. | Browser verifies market/data and reports, including the registry status view. API readiness, DB migrations, Redis requirements and fixture-only exposure are verified. No paid service is provisioned without a hosting decision. |
| 4. Final evaluation | Freeze one candidate with code revision, trained artifact, parameters, benchmark, cost model, trial log and decision rules. Produce the dry-run report and preflight verification on synthetic or development data. | **Pause for separate written approval of this candidate and holdout.** Atomically consume the window before opening its data, run once, then store the report and checksums. A crash after the claim does not reopen the window. |
| 5. Portfolio release | Publish reproducible code, architecture and methodology, limitations, an approved report summary, and resume bullets supported by the evidence. Publish the optional reviewer demo only after acceptance. | A clean-checkout replay reproduces development evidence. The recorded holdout report can be reread without rerunning it. Public assets pass data-license and privacy review. |

## Deployment sequence and recovery

1. Use a dedicated research branch and phase-by-phase pull requests with automated checks. Verify that the legacy release workflow stays scoped to v2 before changing version metadata or merging deployment configuration.
2. Run the initial stack locally with Docker Compose and persistent volumes. Pin Python and Node dependencies, add an npm lockfile, and build images in CI. Validate application startup with no private data configured. Apply database migrations once as a release step with a database backup and a restore rehearsal.
3. Use a private staging environment before publishing anything. Keep PostgreSQL and Redis private, set server-only service and OAuth secrets, require Redis for authenticated writes where enabled, and configure TLS and the staging OAuth callback. Existing Compose credentials are for local use. Run readiness and authenticated ownership checks before cutover.
4. Offer a public read-only portfolio demo with synthetic data and approved published reports. Keep paid hosting, public publishing, provider-license approval, and transfer of any private data as separate release decisions. Pick a host only when current availability, persistence and cost fit the agreed deployment scope.
5. Promote the exact verified commit and image digests. Roll back application images and configuration to the prior release if necessary. Recover watchlist data via the verified backup. The holdout registry is backed up separately and only restored with consumed-window records reconciled forward. Rolling back a deployment must never reopen a research window.

## Research and data boundaries

- Use historical files or a one-time historical import. The 8-year development and 2-year holdout split depends on verified coverage, prior exposure, and available point-in-time universe history. Current constituents alone produce a survivorship-biased exploratory study. US and Indian sleeves initially use their own sessions, currencies, and benchmarks.
- Data quality checks must catch duplicate sessions, incomplete bars, invalid OHLCV, corporate action mismatches and unverifiable membership history. Market data and model inputs carry availability times. Development labels must mature before each validation boundary. Selection and preprocessing are fit inside the development folds.
- Keep simple baselines and log all candidate trials. The simulator reports gross and net performance, lagged execution, costs and liquidity sensitivity. Risk reports cover drawdowns, VaR/CVaR, factor and regime exposure, and capacity assumptions.
- The registry records date range, canonical data hash, approval IDs, strategy ID, code/model hashes, UTC timestamp and result. An atomic claim rejects concurrent, repeated and overlapping evaluations even if the data is revised. Result collection and backups never remove claims.
- Report probabilistic and deflated Sharpe, White's Reality Check, block-bootstrap uncertainty, and Holm-adjusted candidate tests on the aligned development trial family. Report the frozen candidate once on the holdout. Report no statistically significant edge if the predeclared criteria fail.

## Design sources

| Component | Source used |
|---|---|
| Provider adapters and research presentation | [OpenBB](https://github.com/openbq-org/OpenBB), [AlgoTrading101 guide](https://algotrading101.com/learn/openbb-guide/) |
| Dataset, model and experiment contracts | [Qlib](https://github.com/microsoft/qlib), [Gu, Kelly and Xiu](https://www.nber.org/papers/w25398) |
| Labels, features and validation boundaries | [Jansen](https://github.com/stefan-jansen/machine-learning-for-trading), [López de Prado](https://www.wiley.com/en-us/advances-in-financial-machine-learning-p-9781119482086), [Jegadeesh and Titman](https://doi.org/10.1111/j.1540-6261.1993.tb04702.x), [Amihud](https://doi.org/10.1016/S1386-4181(01)00024-6) |
| Portfolio and execution | [Moreira and Muir](https://www.nber.org/papers/w22208), [LEAN](https://github.com/QuantConnect/Lean), [FinRL](https://github.com/AI4Finance-Foundation/FinRL) for policy and environment separation |
| Statistical and risk reporting | [Bailey and López de Prado](https://doi.org/10.3905/jpm.2014.40.5.094), [White](https://doi.org/10.1111/1468-0262.00152), [Politis and Romano](https://doi.org/10.1080/01621459.1994.10476870), [Holm](https://www.jstor.org/stable/4615733), [Fama and French](https://doi.org/10.1016/0304-405X%2893%2990023-5) |

The previous [Streamlit deployment guide](docs/archive/v2/DEPLOYMENT.md) is retained for v2.1.1 recovery.
