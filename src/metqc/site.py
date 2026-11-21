# © 2026 Henry Noguchi (github.com/hnryguchi). Todos os direitos reservados / All rights reserved. Ver/see LICENSE.
"""Build the static dashboard: one QC run per station, JSON for the browser, reports and status cards.

    metqc site --data data --stations stations.geojson --out dist
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .card import brand, status_svg
from .engine import Event, QCResult, group_events, run_qc, summarize
from .models import Flag
from .report import write_reports
from .sources import parse_ndbc

SITE_SRC = Path(__file__).resolve().parent / "site"  # shipped as package data
PLOT_VARS = ["PRES", "WTMP", "ATMP", "DEWP", "WSPD", "GST", "WVHT", "DPD"]
BAD = (Flag.SUSPECT, Flag.FAIL)


def _r(v: float | None) -> float | None:
    return None if v is None else round(v, 2)


def series_payload(result: QCResult, events: list[Event]) -> dict:
    """Per-station time series for the charts: values, flagged indices, events (with gap starts)."""
    s = result.series
    t0 = s.times[0]
    minutes = [int((t - t0).total_seconds() // 60) for t in s.times]
    variables = {}
    for var in PLOT_VARS:
        col = s.values.get(var)
        if not col or all(v is None for v in col):
            continue
        fl = result.flags[var]
        variables[var] = {
            "unit": s.units.get(var, ""),
            "values": [_r(v) for v in col],
            "flagged": [[i, int(f)] for i, f in enumerate(fl) if f in BAD],
        }
    ev_out = []
    for e in sorted(events, key=lambda e: e.start):
        start = e.start
        if e.variable == "*":  # a gap is reported at the first record after it
            i = e.findings[0].index
            start = s.times[i - 1] if i > 0 else e.start
        ev_out.append({
            "variable": e.variable, "start": start.isoformat(), "end": e.end.isoformat(),
            "tests": e.tests, "worst": e.worst.name.lower(), "n": len(e.findings),
        })
    return {"t0": t0.isoformat(), "minutes": minutes, "variables": variables, "events": ev_out}


def station_summary(result: QCResult, events: list[Event], meta: dict) -> dict:
    s = result.series
    last = s.times[-1]
    week = last - timedelta(days=7)
    latest = {}
    for var in PLOT_VARS:
        col = s.values.get(var)
        if not col:
            continue
        for i in range(len(col) - 1, -1, -1):
            if col[i] is not None:
                latest[var] = {"value": _r(col[i]), "flag": result.flags[var][i].name.lower(),
                               "unit": s.units.get(var, ""), "time": s.times[i].isoformat()}
                break
    flagged = sum(1 for fl in result.flags.values() for f in fl if f in BAD)
    flagged_7d = sum(1 for fl in result.flags.values() for i, f in enumerate(fl)
                     if f in BAD and s.times[i] >= week)
    return {
        **meta,
        "period": [s.times[0].isoformat(), last.isoformat()],
        "records": len(s.times),
        "flagged": flagged,
        "flagged_7d": flagged_7d,
        "events": len(events),
        "events_7d": sum(1 for e in events if e.end >= week),
        "flag_counts": summarize(result),
        "latest": latest,
    }


def build_site(data_dir: Path, stations_geojson: Path, out_dir: Path) -> dict:
    geo = json.loads(stations_geojson.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.iterdir():
        shutil.rmtree(old) if old.is_dir() else old.unlink()
    shutil.copytree(SITE_SRC, out_dir, dirs_exist_ok=True)
    stations = []
    for feat in geo["features"]:
        p = feat["properties"]
        sid = p["station"]
        f = data_dir / f"{sid}.txt"
        if not f.exists():
            continue  # fetch failed today: leave it out rather than show stale data
        series = parse_ndbc(f.read_text(encoding="utf-8"), station=sid)
        if not series.times:
            continue
        result = run_qc(series)
        events = group_events(result)
        lon, lat = feat["geometry"]["coordinates"]
        meta = {"id": sid, "name": p.get("short_name") or p["name"], "lat": lat, "lon": lon,
                "url": p.get("data", "")}
        sdir = out_dir / sid
        write_reports(sdir, result, events, [])
        (sdir / "series.json").write_text(json.dumps(series_payload(result, events), separators=(",", ":")),
                                          encoding="utf-8")
        (sdir / "status.svg").write_text(status_svg(result, events, title=f"Buoy {sid} · {meta['name']}"),
                                         encoding="utf-8")
        pt_card = status_svg(result, events, title=f"Boia {sid} · {meta['name']}", lang="pt")
        (sdir / "status-pt.svg").write_text(brand(pt_card), encoding="utf-8")
        stations.append(station_summary(result, events, meta))
    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "source": "NOAA National Data Buoy Center (NDBC), realtime standard meteorological data",
        "stations": stations,
    }
    (out_dir / "stations.json").write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return payload
