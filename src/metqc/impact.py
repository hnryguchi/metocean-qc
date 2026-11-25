# © 2026 Henry Noguchi (github.com/hnryguchi). Todos os direitos reservados / All rights reserved. Ver/see LICENSE.
"""How much does quality control change the numbers a study reports?

For each variable this compares summary statistics computed on the raw series against the same
statistics after removing flagged values, and for each pair of variables it compares the Pearson
correlation before and after. Two removal levels are reported: FAIL only, and FAIL + SUSPECT.

This is the question that matters when station or buoy data feed a climate analysis: if a handful
of bad values moves a mean, an extreme or a correlation, conclusions drawn from the raw series are
not robust. Standard library only (no numpy), like the rest of the package.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations

from .engine import QCResult
from .models import Flag

LEVELS = {"fail": {Flag.FAIL}, "fail_suspect": {Flag.FAIL, Flag.SUSPECT}}


@dataclass
class Stats:
    n: int
    mean: float | None
    std: float | None
    minimum: float | None
    maximum: float | None


@dataclass
class VariableImpact:
    variable: str
    raw: Stats
    cleaned: dict[str, Stats]  # level -> stats


@dataclass
class PairImpact:
    a: str
    b: str
    n_raw: int
    r_raw: float | None
    r_cleaned: dict[str, float | None]
    n_cleaned: dict[str, int]


def _stats(values: list[float]) -> Stats:
    if not values:
        return Stats(0, None, None, None, None)
    n = len(values)
    mean = sum(values) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1)) if n > 1 else 0.0
    return Stats(n, mean, std, min(values), max(values))


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / math.sqrt(sxx * syy)


def qc_impact(result: QCResult) -> tuple[list[VariableImpact], list[PairImpact]]:
    s = result.series
    evaluated = [v for v in s.values if v not in result.skipped_variables]

    def kept(var: str, level: str | None) -> list[bool]:
        drop = LEVELS[level] if level else set()
        return [val is not None and result.flags[var][i] not in drop
                for i, val in enumerate(s.values[var])]

    variables = []
    for var in evaluated:
        raw = [v for v in s.values[var] if v is not None]
        cleaned = {}
        for level in LEVELS:
            mask = kept(var, level)
            cleaned[level] = _stats([v for v, k in zip(s.values[var], mask, strict=True) if k])
        variables.append(VariableImpact(var, _stats(raw), cleaned))

    pairs = []
    for a, b in combinations(evaluated, 2):
        def paired(level: str | None, a: str = a, b: str = b) -> tuple[list[float], list[float]]:
            ma, mb = kept(a, level), kept(b, level)
            idx = [i for i in range(len(s.times)) if ma[i] and mb[i]]
            return [s.values[a][i] for i in idx], [s.values[b][i] for i in idx]  # type: ignore[misc]

        xr, yr = paired(None)
        r_c, n_c = {}, {}
        for level in LEVELS:
            xc, yc = paired(level)
            r_c[level], n_c[level] = _pearson(xc, yc), len(xc)
        pairs.append(PairImpact(a, b, len(xr), _pearson(xr, yr), r_c, n_c))
    return variables, pairs


def impact_json(result: QCResult) -> dict:
    variables, pairs = qc_impact(result)

    def st(x: Stats) -> dict:
        return {"n": x.n, "mean": x.mean, "std": x.std, "min": x.minimum, "max": x.maximum}

    return {
        "levels": {"fail": "FAIL values removed", "fail_suspect": "FAIL and SUSPECT values removed"},
        "variables": [{"variable": v.variable, "raw": st(v.raw),
                       "cleaned": {k: st(c) for k, c in v.cleaned.items()}} for v in variables],
        "correlations": [{"a": p.a, "b": p.b, "n_raw": p.n_raw, "r_raw": p.r_raw,
                          "n_cleaned": p.n_cleaned, "r_cleaned": p.r_cleaned} for p in pairs],
    }


def impact_markdown(result: QCResult, min_r_change: float = 0.02) -> list[str]:
    """Markdown lines: variables whose statistics changed, and correlations that moved."""
    variables, pairs = qc_impact(result)
    out = ["## QC impact on the numbers", "",
           "Statistics on the raw series against the series with flagged values removed "
           "(FAIL only / FAIL + SUSPECT).", ""]
    changed = [v for v in variables if v.raw.n != v.cleaned["fail_suspect"].n]
    if not changed:
        out.append("No values were removed: QC does not change any statistic for this period.")
    else:
        out += ["| Variable | Removed (FAIL / +SUSPECT) | Mean raw → cleaned | Min raw → cleaned "
                "| Max raw → cleaned |", "|---|---|---|---|---|"]
        for v in changed:
            c = v.cleaned["fail_suspect"]
            out.append(
                f"| {v.variable} | {v.raw.n - v.cleaned['fail'].n} / {v.raw.n - c.n} "
                f"| {_f(v.raw.mean)} → {_f(c.mean)} | {_f(v.raw.minimum)} → {_f(c.minimum)} "
                f"| {_f(v.raw.maximum)} → {_f(c.maximum)} |")
    moved = [p for p in pairs if p.r_raw is not None and p.r_cleaned["fail_suspect"] is not None
             and abs(p.r_cleaned["fail_suspect"] - p.r_raw) >= min_r_change]
    out += ["", f"Correlations that moved by {min_r_change} or more after cleaning: {len(moved)}.", ""]
    if moved:
        out += ["| Pair | r raw | r cleaned | Change |", "|---|---|---|---|"]
        for p in sorted(moved, key=lambda p: -abs(p.r_cleaned["fail_suspect"] - p.r_raw)):  # type: ignore[operator]
            rc = p.r_cleaned["fail_suspect"]
            out.append(f"| {p.a} × {p.b} | {p.r_raw:.3f} | {rc:.3f} | {rc - p.r_raw:+.3f} |")  # type: ignore[operator]
    out.append("")
    return out


def _f(x: float | None) -> str:
    return "–" if x is None else f"{x:.2f}"
