# © 2026 Henry Noguchi (github.com/hnryguchi). Todos os direitos reservados / All rights reserved. Ver/see LICENSE.
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
    # Rate-of-change test: change between consecutive valid records, per hour. Catches steps and
    # drifts that last more than one record (the spike test only sees isolated single points).
    roc_suspect_per_hour: float | None = None
    roc_fail_per_hour: float | None = None
    # Flat-line test is skipped for runs at or above this value (see RH below).
    flat_ignore_above: float | None = None


# Rate-of-change limits (per hour) are set above what real weather does at a fixed station:
# a strong cold front or gust front drops air temperature 5-10 degC in an hour and pressure rises
# or falls 3-5 hPa/h in intense storms, so those values are SUSPECT, not FAIL. FAIL is reserved for
# changes no sensor in a working state reports. Water temperature changes far more slowly.
DEFAULT_LIMITS: dict[str, VariableLimits] = {
    # air temperature, degC
    "ATMP": VariableLimits((-60, 60), (-30, 45), 2.0, 4.0, 6, 12, 8.0, 15.0),
    # sea surface temperature, degC
    "WTMP": VariableLimits((-3, 40), (-2, 35), 1.0, 2.0, 24, 72, 3.0, 6.0),
    # dew point, degC
    "DEWP": VariableLimits((-60, 40), (-40, 32), 2.0, 4.0, 6, 12, 10.0, 20.0),
    # sea-level pressure, hPa
    "PRES": VariableLimits((850, 1090), (940, 1060), 3.0, 6.0, 6, 12, 5.0, 10.0),
    # station-level pressure, hPa (INMET reports pressure at the station's altitude, not reduced to
    # sea level: a station at 1,000 m reads about 900 hPa, so the sea-level ranges above do not apply)
    "PRES_STN": VariableLimits((500, 1090), (700, 1060), 3.0, 6.0, 6, 12, 5.0, 10.0),
    # wind speed and gust, m/s
    "WSPD": VariableLimits((0, 75), (0, 40), 8.0, 15.0, 12, 24, 15.0, 30.0),
    "GST": VariableLimits((0, 90), (0, 50), 10.0, 20.0, 12, 24, 20.0, 40.0),
    # wind direction, degT (no spike/flat test: circular and often legitimately steady)
    "WDIR": VariableLimits((0, 360)),
    # significant wave height, m
    "WVHT": VariableLimits((0, 25), (0, 15), 2.0, 4.0, None, None, 3.0, 6.0),
    # relative humidity, % (not in NDBC files; used by CSV sources such as small weather stations)
    # Runs at 94 % or more are not flat-line tested: in rain or fog the air is saturated and capacitive
    # humidity sensors settle a few percent below 100. On real INMET data (Paraty and Macae, 2024) RH
    # held 95-98 % for 12 h or more during night rain; those are real conditions, not stuck sensors.
    "RH": VariableLimits((0, 100), (5, 100), 15.0, 30.0, 6, 12, 40.0, 70.0, 94.0),
    # hourly precipitation, mm (INMET). No spike/flat/rate tests: rain is intermittent by nature and
    # zero for days on end. 100 mm in one hour happens in extreme convective events in Brazil.
    "PREC": VariableLimits((0, 150), (0, 100)),
    # global radiation, kJ/m2 per hour (INMET). One hour of clear-sky noon sun is about 3,600-4,000.
    "RAD": VariableLimits((0, 5000), (0, 4500)),
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
    "precipitacao": "PREC",
    "precipitação": "PREC",
    "precipitation": "PREC",
    "chuva": "PREC",
}

# INMET automatic station columns (historical CSV files) mapped to the codes above. Matching is done
# on the start of the column name, upper-cased and without accents, because INMET spells the same
# column in slightly different ways across years (e.g. "RADIACAO GLOBAL (Kj/m²)" and "(KJ/m²)").
# The "max/min in the previous hour" columns are left out on purpose: they duplicate the hourly value.
INMET_COLUMNS: dict[str, str] = {
    "PRECIPITACAO TOTAL, HORARIO": "PREC",
    "PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO": "PRES_STN",
    "RADIACAO GLOBAL": "RAD",
    "TEMPERATURA DO AR - BULBO SECO": "ATMP",
    "TEMPERATURA DO PONTO DE ORVALHO": "DEWP",
    "UMIDADE RELATIVA DO AR, HORARIA": "RH",
    "VENTO, DIRECAO HORARIA": "WDIR",
    "VENTO, RAJADA MAXIMA": "GST",
    "VENTO, VELOCIDADE HORARIA": "WSPD",
}
