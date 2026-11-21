# © 2026 Henry Noguchi (github.com/hnryguchi). Todos os direitos reservados / All rights reserved. Ver/see LICENSE.
"""JSON and Markdown reports."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .engine import Event, QCResult, summarize
from .review import Review


def to_json(result: QCResult, events: list[Event], reviews: list[Review]) -> dict:
    s = result.series
    return {
        "station": s.station,
        "source": s.source,
        "period_utc": [s.times[0].isoformat(), s.times[-1].isoformat()] if s.times else None,
        "records": len(s.times),
        "flag_counts": summarize(result),
        "not_evaluated_variables": result.skipped_variables,
        "events": [
            {
                "id": e.id,
                "variable": e.variable,
                "start": e.start.isoformat(),
                "end": e.end.isoformat(),
                "worst_flag": e.worst.name,
                "tests": e.tests,
                "findings": [
                    {"time": f.time.isoformat(), "test": f.test, "flag": f.flag.name,
                     "value": f.value, "detail": f.detail}
                    for f in e.findings
                ],
            }
            for e in events
        ],
        "reviews": [asdict(r) for r in reviews],
    }


def to_markdown(result: QCResult, events: list[Event], reviews: list[Review], max_rows: int = 25) -> str:
    s = result.series
    by_id = {r.event_id: r for r in reviews}
    out = [f"# QC report: {s.station}", ""]
    if s.times:
        out.append(f"Source: `{s.source}` · {len(s.times)} records · "
                   f"{s.times[0]:%Y-%m-%d %H:%M} to {s.times[-1]:%Y-%m-%d %H:%M} UTC")
    out += ["", "## Flags per variable", "", "| Variable | GOOD | SUSPECT | FAIL | MISSING | NOT_EVALUATED |",
            "|---|---|---|---|---|---|"]
    for var, c in summarize(result).items():
        out.append(f"| {var} | {c.get('GOOD', 0)} | {c.get('SUSPECT', 0)} | {c.get('FAIL', 0)} "
                   f"| {c.get('MISSING', 0)} | {c.get('NOT_EVALUATED', 0)} |")
    out += ["", f"## Events ({len(events)})", ""]
    if not events:
        out.append("No QC events.")
    else:
        out += ["| Event | Worst flag | Tests | Points | LLM second opinion |", "|---|---|---|---|---|"]
        for e in events[:max_rows]:
            r = by_id.get(e.id)
            opinion = f"{r.verdict} ({r.confidence}): {r.rationale}" if r else "not reviewed"
            out.append(f"| {e.id} | {e.worst.name} | {', '.join(e.tests)} | {len(e.findings)} | "
                       f"{opinion.replace('|', '/')} |")
        if len(events) > max_rows:
            out.append(f"\n{len(events) - max_rows} more events in the JSON report.")
    out += ["", "_Flags come only from the deterministic tests. LLM opinions are advisory; "
            "a person decides._", ""]
    return "\n".join(out)


def write_reports(
    out_dir: str | Path, result: QCResult, events: list[Event], reviews: list[Review]
) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    j = out / "qc_report.json"
    m = out / "qc_report.md"
    j.write_text(json.dumps(to_json(result, events, reviews), indent=2), encoding="utf-8")
    m.write_text(to_markdown(result, events, reviews), encoding="utf-8")
    return [j, m]
