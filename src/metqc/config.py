"""Default QC thresholds per variable.

Variable codes follow the NOAA NDBC standard meteorological format
(https://www.ndbc.noaa.gov/faq/measdes.shtml). Thresholds are deliberately broad,
global defaults: ``fail`` bounds are physical/sensor limits, ``suspect`` bounds are
wide climatological limits. Tune them per station and season before relying on them.

Flat-line durations account for sensor resolution: NDBC realtime files report water
temperature in 0.1 degC and wind speed in whole m/s, so a stable tropical sea or a steady
trade wind can legitimately repeat the same value for many hours. On real data from
station 41010 (Oct-Nov 2026) shorter thresholds produced false FAIL flags.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VariableLimits:
    fail_range: tuple[float, float]
    suspect_range: tuple[float, float] | None = None
    # Spike test: deviation from the mean of the two neighbours.
    spike_suspect: float | None = None
    spike_fail: float | None = None
    # Flat-line test: hours with an unchanged value.
    flat_suspect_hours: float | None = None
    flat_fail_hours: float | None = None


DEFAULT_LIMITS: dict[str, VariableLimits] = {
    # air temperature, degC
    "ATMP": VariableLimits((-60, 60), (-30, 45), 2.0, 4.0, 6, 12),
    # sea surface temperature, degC
    "WTMP": VariableLimits((-3, 40), (-2, 35), 1.0, 2.0, 24, 72),
    # dew point, degC
    "DEWP": VariableLimits((-60, 40), (-40, 32), 2.0, 4.0, 6, 12),
    # sea-level pressure, hPa
    "PRES": VariableLimits((850, 1090), (940, 1060), 3.0, 6.0, 6, 12),
    # wind speed and gust, m/s
    "WSPD": VariableLimits((0, 75), (0, 40), 8.0, 15.0, 12, 24),
    "GST": VariableLimits((0, 90), (0, 50), 10.0, 20.0, 12, 24),
    # wind direction, degT (no spike/flat test: circular and often legitimately steady)
    "WDIR": VariableLimits((0, 360)),
    # significant wave height, m
    "WVHT": VariableLimits((0, 25), (0, 15), 2.0, 4.0, None, None),
    # relative humidity, % (not in NDBC files; used by CSV sources such as small weather stations)
    "RH": VariableLimits((0, 100), (5, 100), 15.0, 30.0, 6, 12),
}

# Common column names mapped to the codes above, for CSV sources.
ALIASES: dict[str, str] = {
    "temperature": "ATMP",
    "temperatura": "ATMP",
    "air_temperature": "ATMP",
    "pressure": "PRES",
    "pressao": "PRES",
    "pressão": "PRES",
    "humidity": "RH",
    "umidade": "RH",
    "relative_humidity": "RH",
    "water_temperature": "WTMP",
    "wind_speed": "WSPD",
}
