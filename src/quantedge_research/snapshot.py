"""Content-addressed snapshot staging and approved partition export."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import tempfile

import pandas as pd

from .data import Audit
from .registry import Registry, sha256_file
from .split import Split


@dataclass(frozen=True)
class StagedSnapshot:
    split: Split
    parquet_sha256: str
    known_limits: tuple[str, ...]
    audits: tuple[Audit, ...]
    eligible_for_holdout: bool

    def json_bytes(self) -> bytes:
        body = {
            "version": 1,
            "split": self.split.dates(),
            "parquet_sha256": self.parquet_sha256,
            "known_limits": self.known_limits,
            "audits": [audit.report() for audit in self.audits],
            "eligible_for_holdout": self.eligible_for_holdout,
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

    @property
    def manifest_sha256(self) -> str:
        return sha256(self.json_bytes()).hexdigest()


def _write_parquet(frame: pd.DataFrame, directory: Path) -> tuple[str, Path]:
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    file_descriptor, name = tempfile.mkstemp(dir=directory, suffix=".parquet")
    os.close(file_descriptor)
    stage = Path(name)
    try:
        frame.to_parquet(stage, engine="pyarrow", compression="zstd", index=False)
        digest = sha256_file(stage)
        artifact = directory / f"{digest}.parquet"
        try:
            os.link(stage, artifact)
        except FileExistsError:
            if sha256_file(artifact) != digest:
                raise ValueError(f"Content-addressed artifact is corrupt: {artifact.name}")
        return digest, artifact
    finally:
        stage.unlink(missing_ok=True)


def stage_snapshot(
    audited: list[tuple[pd.DataFrame, Audit]], split: Split, quarantine: Path, *,
    point_in_time_membership_verified: bool = False,
    corporate_actions_verified: bool = False,
    exposure_review_complete: bool = False,
    known_limits: tuple[str, ...] = (),
) -> StagedSnapshot:
    """Stage an unsplit file in a data custodian's private directory."""
    if not audited:
        raise ValueError("No audited data.")
    ordered = sorted(audited, key=lambda item: item[1].instrument.instrument_id)
    ids = [audit.instrument.instrument_id for _, audit in ordered]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate instrument IDs.")
    for bars, audit in ordered:
        if (audit.bounds != tuple(split.dates().values())
                or set(bars["instrument_id"]) != {audit.instrument.instrument_id}
                or not bars["price_basis"].eq(audit.price_basis).all()
                or len(bars[bars["session"] < pd.Timestamp(split.holdout_start)]) != audit.development.observed
                or len(bars[bars["session"] >= pd.Timestamp(split.holdout_start)]) != audit.holdout.observed):
            raise ValueError("Staged bars disagree with the instrument coverage audit.")
    panel = pd.concat([bars for bars, _ in ordered], ignore_index=True)
    if panel.duplicated(["instrument_id", "session"]).any():
        raise ValueError("Duplicate instrument/session keys.")
    digest, _ = _write_parquet(panel.sort_values(["instrument_id", "session"]), quarantine)
    audits = tuple(audit for _, audit in ordered)
    strict_coverage = all(
        audit.development.observed > 0
        and audit.holdout.observed > 0
        and not any((
            audit.development.missing, audit.holdout.missing, audit.off_calendar,
            audit.invalid_rows, audit.duplicate_rows, audit.unfinished_rows,
        ))
        for audit in audits
    )
    markets = {audit.instrument.market for audit in audits}
    has_benchmarks = all(
        sum(audit.instrument.market == market and audit.instrument.role == "benchmark"
            for audit in audits) == 1 for market in markets
    )
    eligible = (strict_coverage and has_benchmarks and point_in_time_membership_verified
                and corporate_actions_verified and exposure_review_complete
                and all(audit.price_basis == "raw" for audit in audits))
    snapshot = StagedSnapshot(split, digest, known_limits, audits, eligible)
    manifest = quarantine / f"{snapshot.manifest_sha256}.json"
    descriptor, name = tempfile.mkstemp(dir=quarantine, suffix=".json")
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(snapshot.json_bytes())
        try:
            os.link(temporary, manifest)
        except FileExistsError:
            if sha256_file(manifest) != snapshot.manifest_sha256:
                raise ValueError("Existing manifest checksum does not match.")
    finally:
        temporary.unlink(missing_ok=True)
    return snapshot


def seal_partitions(
    snapshot: StagedSnapshot, registry: Registry, quarantine: Path,
    development_dir: Path, holdout_dir: Path,
) -> tuple[Path, Path]:
    """Materialize only after an approval tied to this manifest is present."""
    if not snapshot.eligible_for_holdout:
        raise ValueError("The snapshot has unresolved data or prior-exposure requirements.")
    registry.require_split(snapshot.manifest_sha256, snapshot.split)
    directories = [path.resolve() for path in (quarantine, development_dir, holdout_dir)]
    for i, left in enumerate(directories):
        if any(left.is_relative_to(right) or right.is_relative_to(left) for right in directories[i + 1:]):
            raise ValueError("Use disjoint quarantine, development and holdout directories.")
    source = quarantine / f"{snapshot.parquet_sha256}.parquet"
    payload = source.read_bytes()
    if sha256(payload).hexdigest() != snapshot.parquet_sha256:
        raise ValueError("Approved source snapshot checksum does not match.")
    panel = pd.read_parquet(io.BytesIO(payload))
    boundary = pd.Timestamp(snapshot.split.holdout_start)
    start, end = pd.Timestamp(snapshot.split.start), pd.Timestamp(snapshot.split.end_exclusive)
    if panel.empty or not panel["session"].between(start, end, inclusive="left").all():
        raise ValueError("Approved source contains rows outside its date bounds.")
    development = panel["session"] < boundary
    if development.all() or not development.any():
        raise ValueError("Approved source is missing one of the partitions.")
    holdout_hash, holdout = _write_parquet(panel.loc[~development], holdout_dir)
    registry.seal_artifact(snapshot.manifest_sha256, holdout_hash)
    _, train = _write_parquet(panel.loc[development], development_dir)
    return train, holdout


def evaluate_sealed_once(
    registry: Registry,
    holdout_dir: Path,
    *,
    approval_id: str,
    manifest_sha256: str,
    strategy_id: str,
    candidate_sha256: str,
    evaluate: Callable[[pd.DataFrame], Mapping[str, object]],
) -> str:
    """Verify the exact bytes before passing the approved holdout to frozen code."""
    def open_after_claim(expected_hash: str) -> Mapping[str, object]:
        payload = (holdout_dir / f"{expected_hash}.parquet").read_bytes()
        if sha256(payload).hexdigest() != expected_hash:
            raise ValueError("Sealed holdout checksum does not match.")
        return evaluate(pd.read_parquet(io.BytesIO(payload)))

    return registry.evaluate_once(
        approval_id=approval_id, manifest_sha256=manifest_sha256,
        strategy_id=strategy_id, candidate_sha256=candidate_sha256, evaluate=open_after_claim,
    )
