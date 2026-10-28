"""How long an entry takes the shopkeeper ("Gore ekta hisab: 8 second" on the dashboard).

The app measures from the first keystroke or mic press until the entry is saved and sends the
number with the save. Only the numbers are kept, per shop: no text, no customer.
"""

from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EntryTiming
from app.schemas.dashboard import EntrySpeed
from app.schemas.parse import EntryTimingIn

# The dashboard shows the median of this many latest entries.
RECENT_ENTRIES = 50
# Longer than this, the phone was put down halfway: not a measure of writing an entry.
MAX_DURATION_MS = 60 * 60 * 1000


def record(db: Session, shop_id: int, timing: EntryTimingIn, *, entry_count: int) -> None:
    """Add the timing to the session (committed with the entries it measured)."""
    if not 0 < timing.duration_ms <= MAX_DURATION_MS:
        return
    db.add(
        EntryTiming(
            shop_id=shop_id,
            duration_ms=timing.duration_ms,
            input_method=timing.input,
            entry_count=entry_count,
        )
    )


def recent_speed(db: Session, shop_id: int) -> EntrySpeed:
    stmt = (
        select(EntryTiming.duration_ms)
        .where(EntryTiming.shop_id == shop_id)
        .order_by(EntryTiming.created_at.desc(), EntryTiming.id.desc())
        .limit(RECENT_ENTRIES)
    )
    durations = list(db.scalars(stmt))
    return EntrySpeed(
        median_seconds=round(median(durations) / 1000, 1) if durations else None,
        samples=len(durations),
    )
