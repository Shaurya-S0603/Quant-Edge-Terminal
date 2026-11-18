"""Capital-market session exceptions verified against exchange circulars."""

from dataclasses import dataclass
from datetime import date, time

NSE_TIMEZONE = "Asia/Kolkata"


@dataclass(frozen=True)
class SessionOverride:
    session: date
    circular: str
    normal_open: time | None = None
    normal_close: time | None = None

    @property
    def source_url(self) -> str:
        return f"https://nsearchives.nseindia.com/content/circulars/{self.circular}.pdf"

    @property
    def is_closed(self) -> bool:
        return self.normal_open is None


# Times are for the regular cash market in India Standard Time. This list is
# evidence for these dates only. It is not a full exchange calendar audit.
NSE_OVERRIDES = (
    SessionOverride(date(2019, 10, 27), "CMTR42483", time(18, 15), time(19, 15)),
    SessionOverride(date(2020, 11, 14), "CMTR46230", time(18, 15), time(19, 15)),
    SessionOverride(date(2025, 2, 1), "CMTR65729", time(9, 15), time(15, 30)),
    SessionOverride(date(2026, 1, 15), "CMTR72260"),
    SessionOverride(date(2026, 2, 1), "CMTR72349", time(9, 15), time(15, 30)),
)


def overrides_for(market: str, start: date, end: date) -> tuple[SessionOverride, ...]:
    if market != "NSE":
        return ()
    return tuple(item for item in NSE_OVERRIDES if start <= item.session < end)
