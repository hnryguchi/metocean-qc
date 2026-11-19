"""Deterministic QC tests. Each test returns findings; none of them modifies data.

Test families follow IOOS QARTOD (gross range, spike, flat line) plus a timing/gap
check. Simplified on purpose; thresholds come from ``config.VariableLimits``.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta

from .config import VariableLimits
from .models import Finding, Flag, Series


def gross_range(series: Series, var: str, lim: VariableLimits) -> Iterable[Finding]:
    lo, hi = lim.fail_range
    for i, v in enumerate(series.values[var]):
        if v is None:
            continue
        if v < lo or v > hi:
            yield Finding(var, i, series.times[i], "gross_range", Flag.FAIL, v,
                          f"outside physical/sensor range [{lo}, {hi}]")
        elif lim.suspect_range and not (lim.suspect_range[0] <= v <= lim.suspect_range[1]):
            s_lo, s_hi = lim.suspect_range
            yield Finding(var, i, series.times[i], "gross_range", Flag.SUSPECT, v,
                          f"outside climatological range [{s_lo}, {s_hi}]")


def spike(series: Series, var: str, lim: VariableLimits) -> Iterable[Finding]:
    """|x[i] - mean(x[i-1], x[i+1])| above threshold, using the nearest valid neighbours.

    A spike also inflates its neighbours' deviation, so a point is flagged only when its
    deviation is the local maximum; otherwise the values next to a spike would be flagged too.
    """
    if lim.spike_suspect is None:
        return
    vals = series.values[var]
    valid = [i for i, v in enumerate(vals) if v is not None]
    devs: dict[int, float] = {}
    for k in range(1, len(valid) - 1):
        i_prev, i, i_next = valid[k - 1], valid[k], valid[k + 1]
        devs[i] = abs(vals[i] - (vals[i_prev] + vals[i_next]) / 2)  # type: ignore[operator]
    for k in range(1, len(valid) - 1):
        i = valid[k]
        dev = devs[i]
        if dev < devs.get(valid[k - 1], 0.0) or dev < devs.get(valid[k + 1], 0.0):
            continue
        if lim.spike_fail is not None and dev > lim.spike_fail:
            flag = Flag.FAIL
        elif dev > lim.spike_suspect:
            flag = Flag.SUSPECT
        else:
            continue
        yield Finding(var, i, series.times[i], "spike", flag, vals[i],
                      f"deviates {dev:.2f} from neighbour mean")


def flat_line(series: Series, var: str, lim: VariableLimits) -> Iterable[Finding]:
    """Unchanged value for longer than the configured number of hours."""
    if lim.flat_suspect_hours is None:
        return
    vals, times = series.values[var], series.times
    run_start = None
    for i, v in enumerate(vals):
        if v is None:
            run_start = None
            continue
        if run_start is None or vals[run_start] != v:
            run_start = i
            continue
        hours = (times[i] - times[run_start]).total_seconds() / 3600
        if lim.flat_fail_hours is not None and hours >= lim.flat_fail_hours:
            flag = Flag.FAIL
        elif hours >= lim.flat_suspect_hours:
            flag = Flag.SUSPECT
        else:
            continue
        yield Finding(var, i, times[i], "flat_line", flag, v,
                      f"unchanged for {hours:.1f} h")


def gaps(series: Series, max_gap: timedelta) -> Iterable[Finding]:
    """Intervals between consecutive records longer than ``max_gap`` (station-level)."""
    t = series.times
    for i in range(1, len(t)):
        delta = t[i] - t[i - 1]
        if delta > max_gap:
            yield Finding("*", i, t[i], "gap", Flag.SUSPECT, None,
                          f"no records for {delta.total_seconds() / 3600:.1f} h before this time")


VALUE_TESTS = (gross_range, spike, flat_line)
