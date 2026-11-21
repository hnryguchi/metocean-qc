# © 2026 Henry Noguchi (github.com/hnryguchi). Todos os direitos reservados / All rights reserved. Ver/see LICENSE.
"""Run the QC tests, aggregate per-value flags and group findings into events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .config import DEFAULT_LIMITS, VariableLimits
from .models import Finding, Flag, Series
from .rules import VALUE_TESTS, gaps


@dataclass
class QCResult:
    series: Series
    findings: list[Finding]
    flags: dict[str, list[Flag]]
    skipped_variables: list[str] = field(default_factory=list)


@dataclass
class Event:
    """Consecutive flagged values of one variable (or one gap), to be reviewed together."""

    variable: str
    start: datetime
    end: datetime
    worst: Flag
    tests: list[str]
    findings: list[Finding]

    @property
    def id(self) -> str:
        return f"{self.variable}@{self.start:%Y-%m-%dT%H:%MZ}"


def run_qc(
    series: Series,
    limits: dict[str, VariableLimits] | None = None,
    max_gap: timedelta = timedelta(hours=3),
) -> QCResult:
    limits = DEFAULT_LIMITS if limits is None else limits
    findings: list[Finding] = []
    flags: dict[str, list[Flag]] = {}
    skipped: list[str] = []

    for var, vals in series.values.items():
        lim = limits.get(var)
        if lim is None:
            skipped.append(var)
            flags[var] = [Flag.MISSING if v is None else Flag.NOT_EVALUATED for v in vals]
            continue
        var_flags = [Flag.MISSING if v is None else Flag.GOOD for v in vals]
        for test in VALUE_TESTS:
            for f in test(series, var, lim):
                findings.append(f)
                var_flags[f.index] = max(var_flags[f.index], f.flag)
        flags[var] = var_flags

    findings.extend(gaps(series, max_gap))
    findings.sort(key=lambda f: (f.time, f.variable, f.test))
    return QCResult(series=series, findings=findings, flags=flags, skipped_variables=skipped)


def group_events(result: QCResult, join_within: timedelta = timedelta(hours=1)) -> list[Event]:
    """Merge findings of the same variable that are close in time into one event."""
    events: list[Event] = []
    open_by_var: dict[str, Event] = {}
    for f in result.findings:
        ev = open_by_var.get(f.variable)
        if ev is not None and f.variable != "*" and f.time - ev.end <= join_within:
            ev.end = f.time
            ev.worst = max(ev.worst, f.flag)
            ev.findings.append(f)
            if f.test not in ev.tests:
                ev.tests.append(f.test)
            continue
        ev = Event(f.variable, f.time, f.time, f.flag, [f.test], [f])
        events.append(ev)
        open_by_var[f.variable] = ev
    # most severe first, then chronological
    events.sort(key=lambda e: (-int(e.worst), e.start))
    return events


def summarize(result: QCResult) -> dict[str, dict[str, int]]:
    """Count of values per flag, per variable."""
    out: dict[str, dict[str, int]] = {}
    for var, fl in result.flags.items():
        counts: dict[str, int] = {}
        for f in fl:
            counts[f.name] = counts.get(f.name, 0) + 1
        out[var] = counts
    return out
