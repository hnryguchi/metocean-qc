# © 2026 Henry Noguchi (github.com/hnryguchi). Todos os direitos reservados / All rights reserved. Ver/see LICENSE.
"""Deterministic physical context for QC events: real weather or sensor fault?

Threshold tests look at one variable at a time, so a sharp pressure fall during a cold front is
flagged exactly like a broken barometer. Meteorology says what else must happen when the event is
real: a front brings a pressure change together with stronger wind and a temperature drop; a
convective shower drops the temperature while humidity rises and rain falls. This module checks
those co-occurrences in the other variables recorded around the event and labels each event:

- ``likely_real``: other variables changed in the way the physics of a known phenomenon predicts;
- ``likely_sensor``: the pattern only makes sense as an instrument problem (a value stuck while the
  rest of the station keeps varying, or a jump no other variable follows);
- ``undetermined``: not enough evidence either way.

The label never changes a flag: flags come only from the threshold tests, and a person decides.
Thresholds below are deliberately conservative and documented next to each rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from .engine import Event
from .models import Series

LIKELY_REAL = "likely_real"
LIKELY_SENSOR = "likely_sensor"
UNDETERMINED = "undetermined"

PRESSURE = ("PRES", "PRES_STN")


@dataclass
class Context:
    event_id: str
    label: str
    reason: str
    evidence: list[str] = field(default_factory=list)


def _window(series: Series, var: str, event: Event, hours: float) -> list[float]:
    if var not in series.values:
        return []
    lo, hi = event.start - timedelta(hours=hours), event.end + timedelta(hours=hours)
    return [v for t, v in zip(series.times, series.values[var], strict=True)
            if v is not None and lo <= t <= hi]


def _change(series: Series, var: str, event: Event, hours: float) -> float | None:
    """Last minus first valid value in the window (signed), or None without data."""
    w = _window(series, var, event, hours)
    return w[-1] - w[0] if len(w) >= 2 else None


def _span(series: Series, var: str, event: Event, hours: float) -> float | None:
    w = _window(series, var, event, hours)
    return max(w) - min(w) if len(w) >= 2 else None


def _peak_rise(series: Series, var: str, event: Event, hours: float) -> float | None:
    """Largest value in the window minus the first one (how much the variable went up)."""
    w = _window(series, var, event, hours)
    return max(w) - w[0] if len(w) >= 2 else None


def explain(event: Event, series: Series, hours: float = 3.0) -> Context:
    """Label one event from what the other variables did within ``hours`` of it."""
    var = event.variable
    if var == "*":
        return Context(event.id, UNDETERMINED, "transmission gap: no data to judge")

    evidence: list[str] = []

    def note(name: str, value: float | None, unit: str) -> float | None:
        if value is not None:
            evidence.append(f"{name} {value:+.1f} {unit} within {hours:g} h")
        return value

    if "flat_line" in event.tests and var == "WTMP":
        # The sea has far more thermal inertia than the air: air temperature and dew point move
        # every hour while a stable tropical sea, reported in 0.1 degC steps, repeats one value for a
        # day. Comparing it with atmospheric variables would call a healthy sensor stuck (seen on
        # NDBC 41010, Nov 2026).
        return Context(event.id, UNDETERMINED,
                       "water temperature changes slowly; a long constant run at 0.1 degC resolution "
                       "is common in a stable sea and needs a check against a nearby buoy or satellite SST")

    if "flat_line" in event.tests:
        # A stuck sensor repeats one value while the weather keeps moving the other variables.
        others = [v for v in ("ATMP", "DEWP", "RH", *PRESSURE, "WSPD") if v != var and v in series.values]
        moving = [v for v in others if (_span(series, v, event, 0) or 0) > _MOVING.get(v, 1.0)]
        if moving:
            return Context(event.id, LIKELY_SENSOR,
                           "value stuck while other variables kept changing: " + ", ".join(moving),
                           [f"{v} varied during the event" for v in moving])
        return Context(event.id, UNDETERMINED, "value stuck, but the whole station was calm too")

    if var in PRESSURE:
        p = note("pressure", _change(series, var, event, hours), "hPa")
        w = note("wind (max rise)", _peak_rise(series, "WSPD", event, hours), "m/s")
        g = note("gust (max rise)", _peak_rise(series, "GST", event, hours), "m/s")
        t = note("air temperature", _change(series, "ATMP", event, hours), "degC")
        windy = (w is not None and w >= 3.0) or (g is not None and g >= 5.0)
        cooler = t is not None and t <= -2.0
        if p is not None and abs(p) >= 2.0 and (windy or cooler):
            return Context(event.id, LIKELY_REAL,
                           "pressure change with stronger wind or cooling: front or storm passage",
                           evidence)
        if p is not None and abs(p) < 1.0 and "spike" in event.tests:
            return Context(event.id, LIKELY_SENSOR,
                           "isolated pressure jump: the pressure returned at once and nothing else moved",
                           evidence)

    if var in ("ATMP", "DEWP"):
        t = note("air temperature", _change(series, "ATMP", event, hours), "degC")
        rh = note("relative humidity", _change(series, "RH", event, hours), "%")
        rain = _window(series, "PREC", event, hours)
        if rain:
            evidence.append(f"rain {sum(rain):.1f} mm within {hours:g} h")
        w = note("wind (max rise)", _peak_rise(series, "WSPD", event, hours), "m/s")
        p = note("pressure", next((c for c in (_change(series, v, event, hours) for v in PRESSURE)
                                   if c is not None), None), "hPa")
        if t is not None and t <= -2.0 and ((rh is not None and rh >= 10) or sum(rain) > 0):
            return Context(event.id, LIKELY_REAL,
                           "cooling with rising humidity or rain: shower or convective downdraft", evidence)
        if t is not None and t <= -2.0 and ((w is not None and w >= 3.0) or (p is not None and p >= 1.5)):
            return Context(event.id, LIKELY_REAL,
                           "cooling with stronger wind or rising pressure: cold front", evidence)

    if var in ("WSPD", "GST"):
        g = note("gust (max rise)", _peak_rise(series, "GST" if var == "WSPD" else "WSPD", event, hours),
                 "m/s")
        p = note("pressure", next((c for c in (_change(series, v, event, hours) for v in PRESSURE)
                                   if c is not None), None), "hPa")
        t = note("air temperature", _change(series, "ATMP", event, hours), "degC")
        if (g is not None and g >= 3.0) and ((p is not None and abs(p) >= 1.0) or (t is not None and t <= -1.5)):
            return Context(event.id, LIKELY_REAL,
                           "wind and gust rose together with a pressure or temperature change", evidence)

    if "spike" in event.tests and not any(
        (_span(series, v, event, 1.0) or 0) > _MOVING.get(v, 1.0) * 2
        for v in series.values if v != var
    ):
        return Context(event.id, LIKELY_SENSOR,
                       "single-point jump that no other variable followed", evidence)

    return Context(event.id, UNDETERMINED, "no clear physical signature in the other variables", evidence)


# How much a variable must vary during an event to count as "the station kept changing".
_MOVING: dict[str, float] = {"ATMP": 0.5, "DEWP": 0.5, "RH": 3.0, "PRES": 0.5, "PRES_STN": 0.5,
                             "WSPD": 1.0, "GST": 1.5, "WTMP": 0.2, "WVHT": 0.2, "WDIR": 30.0,
                             "PREC": 0.2, "RAD": 200.0}


def explain_all(events: list[Event], series: Series, hours: float = 3.0) -> list[Context]:
    return [explain(e, series, hours) for e in events]
