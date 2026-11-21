# © 2026 Henry Noguchi (github.com/hnryguchi). Todos os direitos reservados / All rights reserved. Ver/see LICENSE.
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from metqc.models import Series

FIXTURES = Path(__file__).parent / "fixtures"


def make_series(values: dict[str, list], step_minutes: int = 10, start=None) -> Series:
    """SYNTHETIC series for unit tests (not real measurements)."""
    n = len(next(iter(values.values())))
    t0 = start or datetime(2026, 1, 1, tzinfo=timezone.utc)
    times = [t0 + timedelta(minutes=step_minutes * i) for i in range(n)]
    return Series(station="synthetic", times=times, values=values, source="synthetic")


@pytest.fixture
def ndbc_text() -> str:
    """Real NOAA NDBC station 41010 sample (public domain), 150 records."""
    return (FIXTURES / "ndbc_41010_sample.txt").read_text(encoding="utf-8")
