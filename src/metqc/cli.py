"""Command-line interface: ``metqc fetch`` and ``metqc check``."""

from __future__ import annotations

import argparse
import sys
import urllib.error
from datetime import timedelta
from pathlib import Path

from .engine import group_events, run_qc
from .report import write_reports
from .sources import fetch_ndbc, parse_ndbc, read_csv


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="metqc", description="Quality control for metocean time series.")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download NOAA NDBC realtime data for a station")
    f.add_argument("station", help="NDBC station id, e.g. 41010")
    f.add_argument("-o", "--output", type=Path, help="output file (default: data/<station>.txt)")

    c = sub.add_parser("check", help="run QC on a file and write JSON + Markdown reports")
    c.add_argument("file", type=Path)
    c.add_argument("--source", choices=["ndbc", "csv"], default="ndbc")
    c.add_argument("--station", default="", help="station name for the report")
    c.add_argument("--time-column", default="timestamp", help="CSV time column")
    c.add_argument("--max-gap-hours", type=float, default=3.0)
    c.add_argument("--out", type=Path, default=Path("reports"))
    c.add_argument("--review", choices=["none", "claude"], default="none",
                   help="LLM second opinion on events (default: none; 'claude' calls a paid API)")
    c.add_argument("--max-reviews", type=int, default=10, help="cap on reviewed events per run")
    c.add_argument("--model", default="claude-opus-5-5")
    c.add_argument("--card", type=Path, help="also write an SVG status card (latest readings, 72 h chart)")
    c.add_argument("--title", default="", help="title for the status card")

    args = p.parse_args(argv)
    if args.cmd == "fetch":
        out = args.output or Path("data") / f"{args.station}.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = fetch_ndbc(args.station)
        except urllib.error.HTTPError as exc:
            hint = " (station inactive or wrong id?)" if exc.code == 404 else ""
            print(f"error: NDBC returned HTTP {exc.code} for station {args.station}{hint}", file=sys.stderr)
            return 1
        except urllib.error.URLError as exc:
            print(f"error: could not reach NDBC: {exc.reason}", file=sys.stderr)
            return 1
        out.write_text(text, encoding="utf-8")
        print(f"saved {out}")
        return 0

    if args.source == "ndbc":
        series = parse_ndbc(args.file.read_text(encoding="utf-8"), station=args.station or args.file.stem)
    else:
        series = read_csv(args.file, time_column=args.time_column, station=args.station)

    result = run_qc(series, max_gap=timedelta(hours=args.max_gap_hours))
    events = group_events(result)

    reviews = []
    if args.review == "claude" and events:
        from .review import ClaudeReviewer

        reviewer = ClaudeReviewer(model=args.model)
        to_review = events[: max(args.max_reviews, 0)]
        print(f"requesting LLM second opinion on {len(to_review)} of {len(events)} events", file=sys.stderr)
        for ev in to_review:
            reviews.append(reviewer.review(ev, series))

    paths = write_reports(args.out, result, events, reviews)
    if args.card:
        from .card import status_svg

        args.card.parent.mkdir(parents=True, exist_ok=True)
        args.card.write_text(status_svg(result, events, title=args.title), encoding="utf-8")
        paths.append(args.card)
    print(f"{series.station}: {len(series.times)} records, {len(result.findings)} findings, "
          f"{len(events)} events -> " + ", ".join(str(x) for x in paths))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
