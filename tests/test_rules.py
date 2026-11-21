# © 2026 Henry Noguchi (github.com/hnryguchi). Todos os direitos reservados / All rights reserved. Ver/see LICENSE.
from datetime import timedelta

from conftest import make_series

from metqc.config import DEFAULT_LIMITS
from metqc.engine import group_events, run_qc, summarize
from metqc.models import Flag
from metqc.rules import flat_line, gaps, gross_range, spike
from metqc.sources import parse_ndbc

ATMP = DEFAULT_LIMITS["ATMP"]
PRES = DEFAULT_LIMITS["PRES"]


def test_gross_range_fail_and_suspect():
    s = make_series({"ATMP": [20.0, 70.0, 44.0, 46.0, None]})
    found = {f.index: f.flag for f in gross_range(s, "ATMP", ATMP)}
    assert found == {1: Flag.FAIL, 3: Flag.SUSPECT}


def test_spike_detects_isolated_jump_and_ignores_trend():
    trend = [20.0 + 0.1 * i for i in range(10)]
    assert list(spike(make_series({"ATMP": trend}), "ATMP", ATMP)) == []

    jumpy = [20.0, 20.1, 25.0, 20.2, 20.3]
    found = list(spike(make_series({"ATMP": jumpy}), "ATMP", ATMP))
    assert [(f.index, f.flag) for f in found] == [(2, Flag.FAIL)]


def test_spike_skips_missing_neighbours():
    s = make_series({"ATMP": [20.0, None, 20.1, 20.2]})
    assert list(spike(s, "ATMP", ATMP)) == []


def test_flat_line_escalates_with_duration():
    # 10-min steps: 6 h unchanged -> SUSPECT, 12 h -> FAIL
    s = make_series({"PRES": [1012.0] * 80})
    found = list(flat_line(s, "PRES", PRES))
    first_suspect = min(f.index for f in found if f.flag == Flag.SUSPECT)
    first_fail = min(f.index for f in found if f.flag == Flag.FAIL)
    assert first_suspect == 36  # 36 * 10 min = 6 h
    assert first_fail == 72  # 12 h


def test_gaps():
    s = make_series({"ATMP": [20.0, 20.1, 20.2]}, step_minutes=240)
    assert len(list(gaps(s, timedelta(hours=3)))) == 2


def test_run_qc_keeps_worst_flag_and_skips_unknown_variables():
    s = make_series({"ATMP": [20.0, 20.1, 99.0, 20.2, 20.3], "XYZ": [1, 2, 3, 4, 5]})
    r = run_qc(s)
    assert r.flags["ATMP"][2] == Flag.FAIL
    assert r.skipped_variables == ["XYZ"]
    assert set(r.flags["XYZ"]) == {Flag.NOT_EVALUATED}
    counts = summarize(r)
    assert counts["ATMP"]["FAIL"] >= 1


def test_group_events_merges_nearby_findings():
    vals = [1012.0] * 80  # one long flat line -> many findings, one event
    r = run_qc(make_series({"PRES": vals}))
    events = group_events(r)
    assert len(events) == 1
    assert events[0].worst == Flag.FAIL
    assert events[0].tests == ["flat_line"]


def test_real_sample_runs_end_to_end(ndbc_text):
    r = run_qc(parse_ndbc(ndbc_text, station="41010"))
    # every evaluated value received exactly one flag
    for var, flags in r.flags.items():
        assert len(flags) == len(r.series.times), var
