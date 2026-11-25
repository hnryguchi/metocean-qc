# © 2026 Henry Noguchi (github.com/hnryguchi). Todos os direitos reservados / All rights reserved. Ver/see LICENSE.
"""Data sources: NOAA NDBC realtime text files, INMET automatic-station CSV and generic CSV."""

from __future__ import annotations

import csv
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .config import ALIASES
from .models import Series

NDBC_REALTIME_URL = "https://www.ndbc.noaa.gov/data/realtime2/{station}.txt"
NDBC_MISSING = {"MM", "999", "999.0", "99.0", "9999.0"}


def parse_ndbc(text: str, station: str = "") -> Series:
    """Parse an NDBC 'standard meteorological' realtime file.

    Format reference: https://www.ndbc.noaa.gov/faq/measdes.shtml
    Line 1: ``#YY MM DD hh mm WDIR ...``; line 2: units; then newest-first rows.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2 or not lines[0].startswith("#"):
        raise ValueError("not an NDBC standard meteorological file (missing '#' header)")

    header = lines[0].lstrip("#").split()
    units_line = lines[1].lstrip("#").split()
    if header[:5] != ["YY", "MM", "DD", "hh", "mm"]:
        raise ValueError(f"unexpected NDBC header: {header[:5]}")
    variables = header[5:]
    units = dict(zip(variables, units_line[5:], strict=False))

    rows: list[tuple[datetime, list[float | None]]] = []
    for line in lines[2:]:
        if line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != len(header):
            raise ValueError(f"row has {len(parts)} fields, header has {len(header)}: {line!r}")
        y, mo, d, h, mi = (int(p) for p in parts[:5])
        when = datetime(y, mo, d, h, mi, tzinfo=timezone.utc)
        vals = [None if p in NDBC_MISSING else float(p) for p in parts[5:]]
        rows.append((when, vals))

    rows.sort(key=lambda r: r[0])  # files are newest-first
    times = [r[0] for r in rows]
    values = {var: [r[1][i] for r in rows] for i, var in enumerate(variables)}
    return Series(station=station, times=times, values=values, units=units, source="ndbc")


def fetch_ndbc(station: str, timeout: float = 30.0) -> str:
    """Download the last ~45 days of realtime data for an NDBC station (public domain)."""
    url = NDBC_REALTIME_URL.format(station=station.upper())
    req = urllib.request.Request(url, headers={"User-Agent": "metocean-qc"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https host)
        return resp.read().decode("utf-8")


def read_csv(path: str | Path, time_column: str = "timestamp", station: str = "") -> Series:
    """Read a CSV with one ISO-8601 time column and one column per variable.

    Column names are mapped to variable codes through ``config.ALIASES`` (e.g.
    ``temperatura`` -> ``ATMP``); unknown columns keep their own name. Empty cells
    and non-numeric cells become missing values.
    """
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or time_column not in reader.fieldnames:
            raise ValueError(f"CSV must have a {time_column!r} column")
        names = [c for c in reader.fieldnames if c != time_column]
        codes = {c: ALIASES.get(c.strip().lower(), c.strip()) for c in names}
        rows = []
        for row in reader:
            when = datetime.fromisoformat(row[time_column].strip().replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            rows.append((when, [_to_float(row[c]) for c in names]))

    rows.sort(key=lambda r: r[0])
    times = [r[0] for r in rows]
    values = {codes[c]: [r[1][i] for r in rows] for i, c in enumerate(names)}
    return Series(station=station or Path(path).stem, times=times, values=values, source="csv")


INMET_MISSING = {"", "-9999", "-9999,0", "-9999.0", "null", "nan", "F"}


def _plain(text: str) -> str:
    """Upper case without accents, for matching INMET column names across years."""
    import unicodedata

    norm = unicodedata.normalize("NFKD", text)
    return "".join(c for c in norm if not unicodedata.combining(c)).upper().strip()


def parse_inmet(text: str, station: str = "") -> Series:
    """Parse an INMET automatic-station historical CSV (portal.inmet.gov.br/dadoshistoricos).

    Layout: 8 metadata lines (``REGIAO:;SE``, ``UF:;RJ``, ``ESTACAO:;...``, ``CODIGO (WMO):;A652``,
    latitude, longitude, altitude, foundation date), then a ``;``-separated header and hourly rows.
    Decimals use a comma, ``-9999`` marks a missing value, and the date/time columns come either as
    ``2019/01/01`` + ``0000 UTC`` (2019 onwards) or ``2018-01-01`` + ``00:00`` (older files).
    Pressure is at station level, so it maps to ``PRES_STN``, not the sea-level ``PRES``.
    """
    from .config import INMET_COLUMNS

    lines = text.splitlines()
    meta: dict[str, str] = {}
    header_at = None
    for n, line in enumerate(lines[:20]):
        cells = line.split(";")
        key = _plain(cells[0])
        if key.startswith("DATA") and len(cells) > 3:
            header_at = n
            break
        if key.endswith(":") and len(cells) > 1:
            meta[key.rstrip(":")] = cells[1].strip()
    if header_at is None:
        raise ValueError("not an INMET station file (no DATA/HORA header in the first 20 lines)")

    header = [c.strip() for c in lines[header_at].split(";")]
    date_col, time_col = 0, 1
    columns: dict[int, str] = {}
    for idx, name in enumerate(header[2:], start=2):
        plain = _plain(name)
        for prefix, code in INMET_COLUMNS.items():
            if plain.startswith(prefix):
                columns[idx] = code
                break

    rows: list[tuple[datetime, list[float | None]]] = []
    for line in lines[header_at + 1:]:
        if not line.strip():
            continue
        cells = line.split(";")
        when = _inmet_time(cells[date_col], cells[time_col])
        rows.append((when, [_inmet_float(cells[i]) if i < len(cells) else None for i in columns]))

    rows.sort(key=lambda r: r[0])
    times = [r[0] for r in rows]
    values = {code: [r[1][k] for r in rows] for k, code in enumerate(columns.values())}
    name = station or meta.get("CODIGO (WMO)") or meta.get("ESTACAO", "inmet")
    units = {"ATMP": "degC", "DEWP": "degC", "RH": "%", "PRES_STN": "hPa", "WSPD": "m/s",
             "GST": "m/s", "WDIR": "degT", "PREC": "mm", "RAD": "kJ/m2"}
    return Series(station=name, times=times, values=values,
                  units={k: v for k, v in units.items() if k in values}, source="inmet")


def read_inmet(path: str | Path, station: str = "") -> Series:
    """Read an INMET CSV from disk (the files are Latin-1 encoded)."""
    return parse_inmet(Path(path).read_text(encoding="latin-1"), station=station)


def _inmet_time(date: str, hour: str) -> datetime:
    d = date.strip().replace("/", "-")
    h = hour.strip().upper().replace("UTC", "").strip()
    if ":" not in h:  # "0000" -> "00:00"
        h = f"{h[:2]}:{h[2:4]}"
    return datetime.fromisoformat(f"{d}T{h}").replace(tzinfo=timezone.utc)


def _inmet_float(cell: str) -> float | None:
    c = cell.strip()
    if c in INMET_MISSING:
        return None
    try:
        v = float(c.replace(",", "."))
    except ValueError:
        return None
    return None if v <= -9999 else v


def _to_float(cell: str | None) -> float | None:
    if cell is None or not cell.strip():
        return None
    try:
        return float(cell)
    except ValueError:
        return None
