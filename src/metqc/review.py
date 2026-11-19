"""Optional LLM second opinion on QC events. OFF by default.

The rules decide the flags. A reviewer only *explains* each event and says whether it
looks like a sensor fault, a real environmental event, or is uncertain, using the
other variables recorded at the same time (e.g. a pressure drop together with a wind
increase suggests a real front, not a broken barometer). It never changes data or flags.

The Claude reviewer needs the ``anthropic`` package (``pip install metocean-qc[llm]``)
and credentials in the environment (``ANTHROPIC_API_KEY``). Each call costs money; the
CLI caps the number of reviewed events per run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol

from .engine import Event
from .models import Series

VERDICTS = ("sensor_fault", "real_event", "uncertain")

REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "rationale": {"type": "string"},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "recommended_action": {
            "type": "string",
            "enum": ["keep_flag", "consider_downgrade", "needs_human_review"],
        },
    },
    "required": ["verdict", "confidence", "rationale", "evidence", "recommended_action"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You review automated quality-control (QC) alerts on meteorological and \
oceanographic time series from fixed stations and buoys.

For each alert you receive: the variable, the deterministic tests that fired, the flagged \
values, and the station's other variables in a window around the alert.

Decide whether the flagged data most likely reflects a sensor or transmission fault, a \
real environmental event, or cannot be determined from the data given.

Rules:
- Use only the data provided. Do not assume information you were not given.
- Ground every claim in specific values and times from the window, and list them as evidence.
- Physical consistency across variables is the strongest signal (pressure, wind, air and \
water temperature, dew point and waves usually move together during real events).
- Isolated single-point jumps that no other variable reflects point to a fault.
- If the evidence is weak or contradictory, answer "uncertain" and recommend human review.
- You never change flags; a person decides."""


@dataclass
class Review:
    event_id: str
    verdict: str
    confidence: str
    rationale: str
    evidence: list[str]
    recommended_action: str
    model: str = ""


class Reviewer(Protocol):
    def review(self, event: Event, series: Series) -> Review: ...


def event_context(event: Event, series: Series, window: timedelta = timedelta(hours=6)) -> str:
    """Compact text table of all variables around the event, for the reviewer."""
    lo, hi = event.start - window, event.end + window
    idx = [i for i, t in enumerate(series.times) if lo <= t <= hi]
    flagged = {f.index for f in event.findings}
    cols = series.variables
    units = " ".join(f"{c}[{series.units.get(c, '?')}]" for c in cols)
    lines = [
        f"station: {series.station} (source: {series.source})",
        f"alert: variable={event.variable} tests={','.join(event.tests)} "
        f"worst_flag={event.worst.name} from={event.start:%Y-%m-%d %H:%M}Z to={event.end:%Y-%m-%d %H:%M}Z",
        "findings: " + "; ".join(f"{f.time:%m-%d %H:%M} {f.test} {f.flag.name}: {f.detail}"
                                 for f in event.findings[:20]),
        f"window (UTC), '*' marks flagged rows, units: {units}",
        "time " + " ".join(cols),
    ]
    for i in idx:
        row = " ".join("NA" if series.values[c][i] is None else f"{series.values[c][i]:g}" for c in cols)
        mark = "*" if i in flagged else " "
        lines.append(f"{mark}{series.times[i]:%m-%d %H:%M} {row}")
    return "\n".join(lines)


def parse_review(event_id: str, payload: dict[str, Any], model: str = "") -> Review:
    """Validate a reviewer JSON payload against REVIEW_SCHEMA's required fields."""
    missing = [k for k in REVIEW_SCHEMA["required"] if k not in payload]
    if missing:
        raise ValueError(f"review missing fields: {missing}")
    if payload["verdict"] not in VERDICTS:
        raise ValueError(f"unknown verdict {payload['verdict']!r}")
    return Review(
        event_id=event_id,
        verdict=payload["verdict"],
        confidence=payload["confidence"],
        rationale=payload["rationale"],
        evidence=list(payload["evidence"]),
        recommended_action=payload["recommended_action"],
        model=model,
    )


class ClaudeReviewer:
    """Second opinion from Claude with schema-constrained JSON output."""

    def __init__(self, model: str = "claude-opus-5-5", client: Any = None) -> None:
        if client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - depends on optional extra
                raise RuntimeError(
                    "LLM review needs the optional dependency: pip install 'metocean-qc[llm]'"
                ) from exc
            client = anthropic.Anthropic()
        self.client = client
        self.model = model

    def review(self, event: Event, series: Series) -> Review:
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=4000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM_PROMPT,
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": REVIEW_SCHEMA},
            },
            messages=[{"role": "user", "content": event_context(event, series)}],
        )
        if response.stop_reason == "refusal":
            return Review(event.id, "uncertain", "low", "The model declined to review this event.",
                          [], "needs_human_review", getattr(response, "model", self.model))
        if response.stop_reason == "max_tokens":
            raise RuntimeError(f"review of {event.id} was cut off (max_tokens)")
        text = next(b.text for b in response.content if b.type == "text")
        return parse_review(event.id, json.loads(text), getattr(response, "model", self.model))
