# © 2026 Henry Noguchi (github.com/hnryguchi). Todos os direitos reservados / All rights reserved. Ver/see LICENSE.
"""Deterministic QC tests. Each test returns findings; none of them modifies data.

Test families follow IOOS QARTOD (gross range, spike, flat line, rate of change) plus a timing/gap
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


def spike(
    series: Series, var: str, lim: VariableLimits, max_step: timedelta = timedelta(hours=3)
) -> Iterable[Finding]:
    """|x[i] - mean(x[i-1], x[i+1])| above threshold, using the nearest valid neighbours.

    A spike also inflates its neighbours' deviation, so a point is flagged only when its
    deviation is the local maximum; otherwise the values next to a spike would be flagged too.

    Thresholds in ``config`` are for 10-minute data. For coarser records they scale with the
    square root of the step (hourly data: x2.45), because the weather moves more between two
    records an hour apart: on real hourly INMET data, a 5 degC fall during a 7 mm shower was a
    FAIL with the 10-minute limits. A neighbour further away than ``max_step`` is not used: a value
    isolated between gaps cannot be judged against readings from hours before or after.
    """
    if lim.spike_suspect is None:
        return
    vals, times = series.values[var], series.times
    scale = _step_scale(series)
    valid = [i for i, v in enumerate(vals) if v is not None]
    devs: dict[int, float] = {}
    for k in range(1, len(valid) - 1):
        i_prev, i, i_next = valid[k - 1], valid[k], valid[k + 1]
        if times[i] - times[i_prev] > max_step or times[i_next] - times[i] > max_step:
            continue
        devs[i] = abs(vals[i] - (vals[i_prev] + vals[i_next]) / 2)  # type: ignore[operator]
    for k in range(1, len(valid) - 1):
        i = valid[k]
        if i not in devs:
            continue
        dev = devs[i]
        if dev < devs.get(valid[k - 1], 0.0) or dev < devs.get(valid[k + 1], 0.0):
            continue
        if lim.spike_fail is not None and dev > lim.spike_fail * scale:
            flag = Flag.FAIL
        elif dev > lim.spike_suspect * scale:
            flag = Flag.SUSPECT
        else:
            continue
        yield Finding(var, i, series.times[i], "spike", flag, vals[i],
                      f"deviates {dev:.2f} from neighbour mean")


def _step_scale(series: Series) -> float:
    """sqrt(median record interval / 10 min), never below 1 (the defaults are for 10-minute data)."""
    t = series.times
    if len(t) < 3:
        return 1.0
    steps = sorted((t[i] - t[i - 1]).total_seconds() for i in range(1, len(t)))
    median = steps[len(steps) // 2]
    return max(1.0, (median / 600) ** 0.5)


def flat_line(series: Series, var: str, lim: VariableLimits) -> Iterable[Finding]:
    """Unchanged value for longer than the configured number of hours.

    A value sitting exactly on a physical bound is not tested: calm wind (0 m/s) and saturated air
    (100 % relative humidity, fog or rain at night) legitimately stay constant for many hours, and
    hourly station data showed both as false flat lines.
    """
    if lim.flat_suspect_hours is None:
        return
    vals, times = series.values[var], series.times
    bounds = set(lim.fail_range)
    ceiling = lim.flat_ignore_above
    run_start = None
    for i, v in enumerate(vals):
        if v is None or v in bounds or (ceiling is not None and v >= ceiling):
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


def rate_of_change(
    series: Series, var: str, lim: VariableLimits, max_step: timedelta = timedelta(hours=3)
) -> Iterable[Finding]:
    """Sustained change over about one hour above a per-hour limit (QARTOD rate of change).

    Each value is compared with the latest valid value at least one hour earlier (for hourly data,
    the previous record). Comparing over one hour instead of record to record matters for 10-minute
    buoy data: wind and gust legitimately jump a few m/s between 10-minute samples, and dividing that
    by 1/6 h turned normal turbulence into "changes" of 20-30 m/s per hour on real NDBC files.

    Pairs further apart than ``max_step`` are skipped: across a long gap the weather itself changed,
    and the gap test already reports the interruption. Single-point spikes are left to the spike
    test: a value that comes straight back is not flagged here and is never used as a reference.
    """
    if lim.roc_suspect_per_hour is None:
        return
    vals, times = series.values[var], series.times
    valid = [i for i, v in enumerate(vals) if v is not None]
    hour = timedelta(hours=1)
    spikes: set[int] = set()
    for k, i in enumerate(valid):
        if 0 < k < len(valid) - 1:
            prev, nxt = vals[valid[k - 1]], vals[valid[k + 1]]
            up, back = vals[i] - prev, nxt - vals[i]  # type: ignore[operator]
            # a spike goes out and comes back near where it started; a fall followed by a larger
            # rise (pressure ahead of and behind a front) is weather, not a spike
            if up * back < 0 and abs(up) > 0 and abs(nxt - prev) <= 0.5 * abs(up):  # type: ignore[operator]
                spikes.add(i)
    ref_k = 0
    for k in range(1, len(valid)):
        i = valid[k]
        if i in spikes:
            continue
        # latest earlier record at least one hour back that is not itself a spike
        while ref_k + 1 < k and times[i] - times[valid[ref_k + 1]] >= hour:
            ref_k += 1
        j = None
        for kk in range(ref_k, -1, -1):
            if times[i] - times[valid[kk]] >= hour or kk == k - 1:
                if valid[kk] not in spikes:
                    j = valid[kk]
                    break
            if times[i] - times[valid[kk]] > max_step:
                break
        if j is None or j == i:
            continue
        dt = times[i] - times[j]
        if dt > max_step or dt.total_seconds() <= 0:
            continue
        hours = max(dt.total_seconds() / 3600, 1.0)
        rate = abs(vals[i] - vals[j]) / hours  # type: ignore[operator]
        if lim.roc_fail_per_hour is not None and rate > lim.roc_fail_per_hour:
            flag = Flag.FAIL
        elif rate > lim.roc_suspect_per_hour:
            flag = Flag.SUSPECT
        else:
            continue
        yield Finding(var, i, times[i], "rate_of_change", flag, vals[i],
                      f"changed {rate:.2f} per hour over the last {dt.total_seconds() / 3600:.1f} h")


def gaps(series: Series, max_gap: timedelta) -> Iterable[Finding]:
    """Intervals between consecutive records longer than ``max_gap`` (station-level).

    A record where every variable is missing counts as no record: INMET files keep one row per hour
    and fill an outage with -9999, so the gap is in the values, not in the timestamps (Macae 2024
    has 883 such hours).
    """
    t = series.times
    present = [i for i in range(len(t)) if any(col[i] is not None for col in series.values.values())]
    for a, b in zip(present, present[1:], strict=False):
        delta = t[b] - t[a]
        if delta > max_gap:
            yield Finding("*", b, t[b], "gap", Flag.SUSPECT, None,
                          f"no records for {delta.total_seconds() / 3600:.1f} h before this time")


VALUE_TESTS = (gross_range, spike, flat_line, rate_of_change)
