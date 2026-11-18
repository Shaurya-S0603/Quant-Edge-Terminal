from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
import sqlite3
from threading import Event

import pytest

from quantedge_research.registry import ConsumedWindow, Registry
from quantedge_research.split import Split


def register(registry: Registry, manifest: str, artifact: str, tag: str, end: date) -> dict:
    split = Split.from_month_end(end)
    registry.approve_split(manifest, split, "split-" + tag)
    registry.seal_artifact(manifest, artifact)
    registry.approve_run(manifest, "strategy", "e" * 64, "run-" + tag)
    return dict(approval_id="run-" + tag, manifest_sha256=manifest,
                strategy_id="strategy", candidate_sha256="e" * 64)


def test_exact_approval_and_durable_concurrent_claim(tmp_path: Path):
    path = tmp_path / "ledger.sqlite"
    registry = Registry(path)
    registry.initialize()
    args = register(registry, "a" * 64, "b" * 64, "1", date(2026, 11, 1))
    with pytest.raises(ValueError, match="exact"):
        registry.evaluate_once(**(args | {"candidate_sha256": "d" * 64}), evaluate=lambda _: {})
    assert registry.runs() == []
    start, release = Event(), Event()

    def run(artifact_hash: str) -> dict:
        assert artifact_hash == "b" * 64
        assert Registry(path).runs()[0]["window_status"] == "CONSUMED"
        start.set()
        assert release.wait(10)
        return {"net_return": 0.01}

    with ThreadPoolExecutor(max_workers=2) as pool:
        task = pool.submit(registry.evaluate_once, **args, evaluate=run)
        try:
            assert start.wait(10)
            with pytest.raises(ConsumedWindow, match="CONSUMED"):
                registry.evaluate_once(**args, evaluate=lambda _: pytest.fail("Duplicate evaluator ran."))
        finally:
            release.set()
        assert task.result(timeout=10) == registry.runs()[0]["run_id"]
    assert registry.runs()[0]["status"] == "COMPLETE"


def test_failed_window_overlap_and_adjacent_window(tmp_path: Path):
    registry = Registry(tmp_path / "ledger.sqlite")
    registry.initialize()
    args = register(registry, "a" * 64, "b" * 64, "1", date(2026, 11, 1))

    def fail(_: str) -> dict:
        raise RuntimeError("private evaluator error")

    with pytest.raises(RuntimeError):
        registry.evaluate_once(**args, evaluate=fail)
    assert registry.runs()[0]["result_json"] == '{"error_type": "RuntimeError"}'
    overlap = register(registry, "c" * 64, "d" * 64, "2", date(2027, 11, 1))
    with pytest.raises(ConsumedWindow):
        registry.evaluate_once(**overlap, evaluate=lambda _: {})
    adjacent = register(registry, "f" * 64, "1" * 64, "3", date(2028, 11, 1))
    registry.evaluate_once(**adjacent, evaluate=lambda _: {"gross": 0.0})
    assert [r["status"] for r in registry.runs()] == ["FAILED", "COMPLETE"]


def test_no_run_approval_before_seal_and_ledger_guards(tmp_path: Path):
    path = tmp_path / "ledger.sqlite"
    registry = Registry(path)
    registry.initialize()
    split = Split.from_month_end(date(2026, 11, 1))
    registry.approve_split("a" * 64, split, "split")
    with pytest.raises(sqlite3.IntegrityError):
        registry.approve_run("a" * 64, "research", "b" * 64, "holdout")
    registry.seal_artifact("a" * 64, "c" * 64)
    with pytest.raises(ValueError, match="separate approval"):
        registry.approve_run("a" * 64, "research", "b" * 64, "split")
    registry.approve_run("a" * 64, "research", "b" * 64, "holdout")
    registry.evaluate_once(approval_id="holdout", manifest_sha256="a" * 64,
                           strategy_id="research", candidate_sha256="b" * 64, evaluate=lambda _: {})
    with sqlite3.connect(path) as conn, pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM holdout_runs")
