from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from quantedge_research.data import Instrument, audit_bars, session_schedule
from quantedge_research.registry import Registry
from quantedge_research.snapshot import evaluate_sealed_once, seal_partitions, stage_snapshot
from quantedge_research.split import Split


def test_partitions_require_approved_manifest_and_keep_holdout_separate(tmp_path: Path):
    split = Split.from_month_end(date(2026, 11, 1))
    sessions = session_schedule("US", split.start, split.end_exclusive).index
    source = pd.DataFrame({
        "session": sessions.strftime("%Y-%m-%d"),
        "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.0, "volume": 100,
        "split_ratio": 1.0, "cash_dividend": 0.0,
    })
    pair = audit_bars(
        source, Instrument("bench", "TEST", "US", "USD", "benchmark"),
        provider="fixture", price_basis="raw", start=split.start, boundary=split.holdout_start,
        end=split.end_exclusive, as_of=datetime(2026, 11, 2, tzinfo=UTC),
    )
    quarantine, train_dir, holdout_dir = [tmp_path / name for name in ("raw", "train", "holdout")]
    flags = dict(point_in_time_membership_verified=True, corporate_actions_verified=True,
                 exposure_review_complete=True)
    snapshot = stage_snapshot([pair], split, quarantine, **flags)
    assert snapshot.eligible_for_holdout
    assert stage_snapshot([pair], split, quarantine, **flags).manifest_sha256 == snapshot.manifest_sha256
    registry = Registry(tmp_path / "ledger.sqlite")
    registry.initialize()
    with pytest.raises(ValueError, match="no recorded approval"):
        seal_partitions(snapshot, registry, quarantine, train_dir, holdout_dir)
    assert not train_dir.exists() and not holdout_dir.exists()
    registry.approve_split(snapshot.manifest_sha256, split, "fixture-split")
    train, test = seal_partitions(snapshot, registry, quarantine, train_dir, holdout_dir)
    assert pd.read_parquet(train).session.max() < pd.Timestamp(split.holdout_start)
    assert pd.read_parquet(test).session.min() >= pd.Timestamp(split.holdout_start)
    assert pd.read_parquet(train).shape[0] + pd.read_parquet(test).shape[0] == len(sessions)
    assert registry.runs() == []
    unverified = stage_snapshot([pair], split, quarantine)
    assert not unverified.eligible_for_holdout
    with pytest.raises(ValueError, match="unresolved"):
        seal_partitions(unverified, registry, quarantine, train_dir, holdout_dir)

    registry.approve_run(snapshot.manifest_sha256, "fixture", "f" * 64, "fixture-evaluation")
    call = dict(approval_id="fixture-evaluation", manifest_sha256=snapshot.manifest_sha256,
                strategy_id="fixture", candidate_sha256="f" * 64)
    with test.open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        evaluate_sealed_once(registry, holdout_dir, **call,
                             evaluate=lambda _: pytest.fail("Tampered inputs reached the evaluator."))
    assert registry.runs()[0]["status"] == "FAILED"
