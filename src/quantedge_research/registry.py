"""Durable approvals and single-use holdout claims for the offline operator."""

from collections.abc import Callable, Mapping
from contextlib import closing, contextmanager
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from .split import Split

SCHEMA = """
CREATE TABLE IF NOT EXISTS approved_splits (
    manifest_sha256 TEXT PRIMARY KEY,
    starts_on TEXT NOT NULL,
    ends_before TEXT NOT NULL,
    approval_id TEXT NOT NULL UNIQUE,
    approved_at TEXT NOT NULL,
    CHECK (starts_on < ends_before)
);
CREATE TABLE IF NOT EXISTS sealed_artifacts (
    manifest_sha256 TEXT PRIMARY KEY REFERENCES approved_splits,
    holdout_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approved_runs (
    approval_id TEXT PRIMARY KEY,
    manifest_sha256 TEXT NOT NULL REFERENCES sealed_artifacts,
    strategy_id TEXT NOT NULL,
    candidate_sha256 TEXT NOT NULL,
    approved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS holdout_runs (
    run_id TEXT PRIMARY KEY,
    approval_id TEXT NOT NULL UNIQUE REFERENCES approved_runs,
    manifest_sha256 TEXT NOT NULL REFERENCES sealed_artifacts,
    starts_on TEXT NOT NULL,
    ends_before TEXT NOT NULL,
    holdout_sha256 TEXT NOT NULL UNIQUE,
    strategy_id TEXT NOT NULL,
    candidate_sha256 TEXT NOT NULL,
    consumed_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('STARTED', 'COMPLETE', 'FAILED')),
    result_json TEXT
);
CREATE TRIGGER IF NOT EXISTS deny_overlapping_claim BEFORE INSERT ON holdout_runs
WHEN EXISTS (
    SELECT 1 FROM holdout_runs WHERE holdout_sha256 = NEW.holdout_sha256
    OR (starts_on < NEW.ends_before AND ends_before > NEW.starts_on)
)
BEGIN SELECT RAISE(ABORT, 'Holdout window is CONSUMED'); END;
CREATE TRIGGER IF NOT EXISTS deny_run_delete BEFORE DELETE ON holdout_runs
BEGIN SELECT RAISE(ABORT, 'Holdout claims are permanent'); END;
CREATE TRIGGER IF NOT EXISTS deny_run_rewrite BEFORE UPDATE ON holdout_runs
WHEN OLD.status <> 'STARTED' OR NEW.status NOT IN ('COMPLETE', 'FAILED')
    OR NEW.result_json IS NULL
    OR NEW.run_id <> OLD.run_id OR NEW.approval_id <> OLD.approval_id
    OR NEW.manifest_sha256 <> OLD.manifest_sha256 OR NEW.starts_on <> OLD.starts_on
    OR NEW.ends_before <> OLD.ends_before OR NEW.holdout_sha256 <> OLD.holdout_sha256
    OR NEW.strategy_id <> OLD.strategy_id OR NEW.candidate_sha256 <> OLD.candidate_sha256
    OR NEW.consumed_at <> OLD.consumed_at
BEGIN SELECT RAISE(ABORT, 'Only initial result finalization is allowed'); END;
"""


class ConsumedWindow(ValueError):
    """The window already has a permanent evaluation claim."""


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_hash(value: str) -> None:
    if not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("Expected a lowercase SHA-256 digest.")


def check_id(value: str) -> None:
    if not value.strip() or len(value) > 200:
        raise ValueError("Expected a nonempty ID of at most 200 characters.")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Registry:
    def __init__(self, path: Path):
        self.path = path.resolve()

    def initialize(self) -> None:
        """Explicit provisioning only. Evaluation never creates a new ledger."""
        with closing(sqlite3.connect(self.path, timeout=30)) as connection, connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(SCHEMA)

    @contextmanager
    def _transaction(self, *, write: bool = True):
        mode = "rw" if write else "ro"
        with closing(sqlite3.connect(f"{self.path.as_uri()}?mode={mode}", uri=True, timeout=30)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA recursive_triggers=ON")
            with db:
                if write:
                    db.execute("PRAGMA synchronous=FULL")
                    db.execute("BEGIN IMMEDIATE")
                yield db

    def approve_split(self, manifest_sha256: str, split: Split, approval_id: str) -> None:
        """Record the data custodian's explicit decision for this exact manifest."""
        check_hash(manifest_sha256)
        check_id(approval_id)
        with self._transaction() as db:
            db.execute("INSERT INTO approved_splits VALUES (?, ?, ?, ?, ?)", (
                manifest_sha256, split.holdout_start.isoformat(), split.end_exclusive.isoformat(),
                approval_id, utc_now(),
            ))

    def require_split(self, manifest_sha256: str, split: Split) -> None:
        with self._transaction(write=False) as db:
            row = db.execute(
                "SELECT 1 FROM approved_splits WHERE manifest_sha256=? AND starts_on=? AND ends_before=?",
                (manifest_sha256, split.holdout_start.isoformat(), split.end_exclusive.isoformat()),
            ).fetchone()
            if row is None:
                raise ValueError("This exact split manifest has no recorded approval.")

    def seal_artifact(self, manifest_sha256: str, holdout_sha256: str) -> None:
        check_hash(manifest_sha256)
        check_hash(holdout_sha256)
        with self._transaction() as db:
            row = db.execute("SELECT holdout_sha256 FROM sealed_artifacts WHERE manifest_sha256=?",
                             (manifest_sha256,)).fetchone()
            if row:
                if row["holdout_sha256"] != holdout_sha256:
                    raise ValueError("The approved manifest already has a different holdout artifact.")
                return
            db.execute("INSERT INTO sealed_artifacts VALUES (?, ?)", (manifest_sha256, holdout_sha256))

    def approve_run(self, manifest_sha256: str, strategy_id: str, candidate_sha256: str,
                    approval_id: str) -> None:
        """Called only after human approval of the frozen candidate."""
        check_hash(manifest_sha256)
        check_hash(candidate_sha256)
        check_id(strategy_id)
        check_id(approval_id)
        with self._transaction() as db:
            if db.execute("SELECT 1 FROM approved_splits WHERE approval_id=?", (approval_id,)).fetchone():
                raise ValueError("Holdout evaluation requires a separate approval.")
            db.execute("INSERT INTO approved_runs VALUES (?, ?, ?, ?, ?)",
                       (approval_id, manifest_sha256, strategy_id, candidate_sha256, utc_now()))

    def evaluate_once(
        self,
        *,
        approval_id: str,
        manifest_sha256: str,
        strategy_id: str,
        candidate_sha256: str,
        evaluate: Callable[[str], Mapping[str, object]],
    ) -> str:
        """Commit the claim before allowing the evaluator to access holdout data."""
        run_id = uuid4().hex
        with self._transaction() as db:
            run = db.execute("""
                SELECT s.starts_on, s.ends_before, a.holdout_sha256
                FROM approved_runs r
                JOIN approved_splits s USING(manifest_sha256)
                JOIN sealed_artifacts a USING(manifest_sha256)
                WHERE r.approval_id=? AND r.manifest_sha256=?
                  AND r.strategy_id=? AND r.candidate_sha256=?
            """, (approval_id, manifest_sha256, strategy_id, candidate_sha256)).fetchone()
            if run is None:
                raise ValueError("The exact manifest and frozen candidate have no holdout approval.")
            start, end, data_hash = run
            prior = db.execute("""
                SELECT run_id FROM holdout_runs
                WHERE holdout_sha256=? OR (starts_on < ? AND ends_before > ?)
                ORDER BY consumed_at LIMIT 1
            """, (data_hash, end, start)).fetchone()
            if prior:
                raise ConsumedWindow(
                    f"Holdout window is CONSUMED by run {prior['run_id']}. Open its recorded result."
                )
            db.execute("""
                INSERT INTO holdout_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'STARTED', NULL)
            """, (run_id, approval_id, manifest_sha256, start, end, data_hash,
                  strategy_id, candidate_sha256, utc_now()))

        try:
            result = json.dumps(dict(evaluate(data_hash)), allow_nan=False, sort_keys=True)
        except Exception as error:
            self._finish(run_id, "FAILED", json.dumps({"error_type": type(error).__name__}))
            raise
        self._finish(run_id, "COMPLETE", result)
        return run_id

    def _finish(self, run_id: str, status: str, result: str) -> None:
        with self._transaction() as db:
            db.execute("UPDATE holdout_runs SET status=?, result_json=? WHERE run_id=?",
                       (status, result, run_id))

    def runs(self) -> list[dict]:
        with self._transaction(write=False) as db:
            rows = db.execute("SELECT * FROM holdout_runs ORDER BY consumed_at, run_id")
            return [dict(row) | {"window_status": "CONSUMED"} for row in rows]
