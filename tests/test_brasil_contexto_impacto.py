# © 2026 Henry Noguchi (github.com/hnryguchi). Todos os direitos reservados / All rights reserved. Ver/see LICENSE.
"""Rate of change, INMET parser, physical context and QC impact.

All series here are SYNTHETIC, built to exercise one behaviour each. The INMET text reproduces the
layout of the official historical files (8 metadata lines, ';' separator, decimal comma, -9999 for
missing) with invented values; it is not a real station record.
"""

import json

from conftest import make_series

from metqc.cli import main
from metqc.config import DEFAULT_LIMITS
from metqc.context import LIKELY_REAL, LIKELY_SENSOR, explain
from metqc.engine import group_events, run_qc
from metqc.impact import qc_impact
from metqc.models import Flag
from metqc.rules import flat_line, rate_of_change
from metqc.sources import parse_inmet

ATMP = DEFAULT_LIMITS["ATMP"]


# ---------- rate of change ----------

def test_rate_of_change_flags_a_persistent_step_hourly():
    # hourly data: +10 degC in one hour that stays -> SUSPECT (limit 8 degC/h), not a spike
    s = make_series({"ATMP": [20.0, 20.5, 30.5, 30.4, 30.6]}, step_minutes=60)
    found = list(rate_of_change(s, "ATMP", ATMP))
    assert [(f.index, f.flag) for f in found] == [(2, Flag.SUSPECT)]


def test_rate_of_change_leaves_single_point_spikes_to_the_spike_test():
    s = make_series({"ATMP": [20.0, 20.1, 35.0, 20.2, 20.3]}, step_minutes=60)
    assert list(rate_of_change(s, "ATMP", ATMP)) == []


def test_rate_of_change_skips_pairs_across_long_gaps():
    s = make_series({"ATMP": [20.0, 35.0]}, step_minutes=300)  # 5 h apart
    assert list(rate_of_change(s, "ATMP", ATMP)) == []


def test_flat_line_ignores_values_on_a_physical_bound():
    calm = make_series({"WSPD": [0.0] * 30}, step_minutes=60)  # 30 h of calm wind
    fog = make_series({"RH": [100.0] * 30}, step_minutes=60)   # 30 h of saturated air
    assert list(flat_line(calm, "WSPD", DEFAULT_LIMITS["WSPD"])) == []
    assert list(flat_line(fog, "RH", DEFAULT_LIMITS["RH"])) == []


# ---------- INMET ----------

INMET_2019 = (
    "REGIAO:;SE\n"
    "UF:;RJ\n"
    "ESTACAO:;EXEMPLO SINTETICO\n"
    "CODIGO (WMO):;A999\n"
    "LATITUDE:;-22,90\n"
    "LONGITUDE:;-43,20\n"
    "ALTITUDE:;11,1\n"
    "DATA DE FUNDACAO:;2007-05-01\n"
    "Data;Hora UTC;PRECIPITAÇÃO TOTAL, HORÁRIO (mm);PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO, HORARIA (mB);"
    "PRESSÃO ATMOSFERICA MAX.NA HORA ANT. (AUT) (mB);RADIACAO GLOBAL (Kj/m²);"
    "TEMPERATURA DO AR - BULBO SECO, HORARIA (°C);TEMPERATURA DO PONTO DE ORVALHO (°C);"
    "UMIDADE RELATIVA DO AR, HORARIA (%);VENTO, DIREÇÃO HORARIA (gr) (° (gr));"
    "VENTO, RAJADA MAXIMA (m/s);VENTO, VELOCIDADE HORARIA (m/s);\n"
    "2019/01/01;0000 UTC;0;1008,4;1008,9;-9999;25,1;21,3;79;130;4,2;1,8;\n"
    "2019/01/01;0100 UTC;0,2;1008,1;1008,5;-9999;24,6;21,4;82;140;3,9;1,5;\n"
    "2019/01/01;0200 UTC;-9999;-9999;-9999;-9999;-9999;-9999;-9999;-9999;-9999;-9999;\n"
)


def test_parse_inmet_maps_columns_units_and_missing_values():
    s = parse_inmet(INMET_2019)
    assert s.station == "A999"
    assert s.source == "inmet"
    assert set(s.values) == {"PREC", "PRES_STN", "RAD", "ATMP", "DEWP", "RH", "WDIR", "GST", "WSPD"}
    assert s.values["ATMP"] == [25.1, 24.6, None]
    assert s.values["PREC"] == [0.0, 0.2, None]
    assert s.values["RAD"] == [None, None, None]
    assert s.times[1].isoformat() == "2019-01-01T01:00:00+00:00"
    assert s.units["PRES_STN"] == "hPa"


def test_parse_inmet_accepts_the_older_date_and_time_format():
    old = INMET_2019.replace("Data;Hora UTC", "DATA (YYYY-MM-DD);HORA (UTC)")
    old = old.replace("2019/01/01;0000 UTC", "2018-01-01;00:00").replace("2019/01/01;0100 UTC", "2018-01-01;01:00")
    old = old.replace("2019/01/01;0200 UTC", "2018-01-01;02:00")
    s = parse_inmet(old)
    assert s.times[0].isoformat() == "2018-01-01T00:00:00+00:00"
    assert len(s.times) == 3


def test_cli_checks_an_inmet_file_end_to_end(tmp_path):
    f = tmp_path / "INMET_SE_RJ_A999.CSV"
    f.write_text(INMET_2019, encoding="latin-1")
    out = tmp_path / "rep"
    assert main(["check", str(f), "--source", "inmet", "--out", str(out)]) == 0
    report = json.loads((out / "qc_report.json").read_text(encoding="utf-8"))
    assert report["source"] == "inmet"
    assert "qc_impact" in report
    md = (out / "qc_report.md").read_text(encoding="utf-8")
    assert "QC impact on the numbers" in md


# ---------- physical context ----------

def _front():
    """SYNTHETIC cold front, hourly: pressure falls 4 hPa then jumps, wind and gust rise, it cools."""
    pres = [1012.0, 1011.0, 1010.0, 1008.0, 1014.5, 1015.0, 1015.2, 1015.3]  # +6.5 hPa/h -> rate flag
    wspd = [2.0, 2.5, 3.0, 4.0, 9.0, 7.0, 5.0, 4.0]
    gst = [4.0, 4.5, 5.0, 7.0, 16.0, 12.0, 9.0, 7.0]
    atmp = [28.0, 27.8, 27.5, 27.0, 22.0, 21.5, 21.0, 21.0]
    return make_series({"PRES": pres, "WSPD": wspd, "GST": gst, "ATMP": atmp}, step_minutes=60)


def test_context_labels_a_front_as_likely_real():
    s = _front()
    events = [e for e in group_events(run_qc(s)) if e.variable == "PRES"]
    assert events, "the synthetic front should trigger a pressure rate-of-change flag"
    c = explain(events[0], s)
    assert c.label == LIKELY_REAL
    assert "front" in c.reason


def test_context_labels_a_stuck_sensor_while_the_station_varies():
    n = 30
    s = make_series({
        "ATMP": [24.0] * n,                                    # stuck for 30 h
        "RH": [60.0 + (i % 12) * 2 for i in range(n)],         # keeps moving
        "PRES": [1010.0 + (i % 6) * 0.4 for i in range(n)],
    }, step_minutes=60)
    events = [e for e in group_events(run_qc(s)) if e.variable == "ATMP"]
    assert events
    assert explain(events[0], s).label == LIKELY_SENSOR


def test_context_labels_an_isolated_jump_as_likely_sensor():
    s = make_series({"PRES": [1010.0, 1010.1, 1018.0, 1010.2, 1010.2],
                     "ATMP": [25.0, 25.0, 25.1, 25.0, 25.0]}, step_minutes=60)
    events = [e for e in group_events(run_qc(s)) if e.variable == "PRES"]
    assert events
    assert explain(events[0], s).label == LIKELY_SENSOR


# ---------- QC impact ----------

def test_qc_impact_reports_changed_mean_and_correlation():
    # SYNTHETIC: two correlated variables; one FAIL value (99 degC) distorts mean and correlation
    atmp = [20.0 + i * 0.1 for i in range(20)]
    rh = [80.0 - i * 0.5 for i in range(20)]
    atmp[10] = 99.0
    r = run_qc(make_series({"ATMP": atmp, "RH": rh}, step_minutes=60))
    variables, pairs = qc_impact(r)
    v = next(x for x in variables if x.variable == "ATMP")
    assert v.raw.n - v.cleaned["fail"].n >= 1
    assert v.cleaned["fail"].maximum < 60
    p = pairs[0]
    assert p.r_cleaned["fail"] is not None and p.r_raw is not None
    assert p.r_cleaned["fail"] < p.r_raw  # cleaning restores the strong negative correlation
    assert p.r_cleaned["fail"] < -0.99
