import json
from types import SimpleNamespace

import pytest
from conftest import make_series

from metqc.cli import main
from metqc.engine import group_events, run_qc
from metqc.report import to_json, to_markdown
from metqc.review import ClaudeReviewer, event_context, parse_review

GOOD_PAYLOAD = {
    "verdict": "sensor_fault",
    "confidence": "high",
    "rationale": "Single-point jump not reflected in pressure or wind.",
    "evidence": ["01-01 00:20 ATMP 25.0 vs neighbours ~20.1"],
    "recommended_action": "keep_flag",
}


class FakeMessages:
    """Stands in for client.beta.messages; records the request, returns a canned reply."""

    def __init__(self, payload=GOOD_PAYLOAD, stop_reason="end_turn"):
        self.payload, self.stop_reason, self.calls = payload, stop_reason, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        block = SimpleNamespace(type="text", text=json.dumps(self.payload))
        return SimpleNamespace(content=[block], stop_reason=self.stop_reason, model=kwargs["model"])


def fake_client(**kw):
    return SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages(**kw)))


@pytest.fixture
def spiky():
    s = make_series({
        "ATMP": [20.0, 20.1, 25.0, 20.2, 20.3],
        "PRES": [1012.0, 1012.1, 1012.0, 1011.9, 1012.0],
    })
    r = run_qc(s)
    return s, r, group_events(r)


def test_context_contains_other_variables_and_marks_flagged_rows(spiky):
    s, _, events = spiky
    ctx = event_context(events[0], s)
    assert "PRES" in ctx and "ATMP" in ctx
    assert any(line.startswith("*") for line in ctx.splitlines())


def test_claude_reviewer_request_shape_and_parsing(spiky):
    s, _, events = spiky
    client = fake_client()
    review = ClaudeReviewer(client=client).review(events[0], s)
    assert review.verdict == "sensor_fault"
    call = client.beta.messages.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["fallbacks"] == "default"


def test_refusal_becomes_uncertain_needing_human(spiky):
    s, _, events = spiky
    review = ClaudeReviewer(client=fake_client(stop_reason="refusal")).review(events[0], s)
    assert review.verdict == "uncertain"
    assert review.recommended_action == "needs_human_review"


def test_parse_review_rejects_bad_payload():
    with pytest.raises(ValueError):
        parse_review("x", {"verdict": "sensor_fault"})
    with pytest.raises(ValueError):
        parse_review("x", {**GOOD_PAYLOAD, "verdict": "aliens"})


def test_reports(spiky):
    s, r, events = spiky
    data = to_json(r, events, [])
    assert data["records"] == 5 and data["events"]
    md = to_markdown(r, events, [])
    assert "not reviewed" in md and "a person decides" in md


def test_cli_check_without_llm(tmp_path, ndbc_text):
    f = tmp_path / "41010.txt"
    f.write_text(ndbc_text, encoding="utf-8")
    out = tmp_path / "reports"
    assert main(["check", str(f), "--out", str(out)]) == 0
    report = json.loads((out / "qc_report.json").read_text(encoding="utf-8"))
    assert report["station"] == "41010"
    assert report["reviews"] == []
