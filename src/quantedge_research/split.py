"""Calendar split proposal and time-ordered label eligibility."""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Split:
    start: date
    holdout_start: date
    end_exclusive: date

    @classmethod
    def from_month_end(cls, end_exclusive: date) -> "Split":
        if end_exclusive.day != 1:
            raise ValueError("Use the first day following a completed month.")
        return cls(end_exclusive.replace(year=end_exclusive.year - 10),
                   end_exclusive.replace(year=end_exclusive.year - 2), end_exclusive)

    def __post_init__(self) -> None:
        end = self.end_exclusive
        if (end.day != 1 or self.start != end.replace(year=end.year - 10)
                or self.holdout_start != end.replace(year=end.year - 2)):
            raise ValueError("Split must contain exactly eight development and two holdout years.")

    def dates(self) -> dict[str, str]:
        return {key: value.isoformat() for key, value in vars(self).items()}


def fit_label_is_eligible(decision_at: datetime, label_available_at: datetime,
                          validation_starts_at: datetime) -> bool:
    times = (decision_at, label_available_at, validation_starts_at)
    if any(value.utcoffset() is None for value in times):
        raise ValueError("Decision, label and fold timestamps must include time zones.")
    return decision_at < label_available_at < validation_starts_at
