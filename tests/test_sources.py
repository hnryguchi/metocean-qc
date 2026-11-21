# © 2026 Henry Noguchi (github.com/hnryguchi). Todos os direitos reservados / All rights reserved. Ver/see LICENSE.
import pytest

from metqc.sources import parse_ndbc, read_csv


def test_parse_real_ndbc_sample(ndbc_text):
    s = parse_ndbc(ndbc_text, station="41010")
    assert s.station == "41010"
    assert len(s.times) == 150
    assert s.times == sorted(s.times), "rows must be chronological (file is newest-first)"
    assert {"ATMP", "PRES", "WTMP", "WSPD"} <= set(s.variables)
    assert s.units["PRES"] == "hPa"
    # 'MM' means missing in NDBC files
    assert all(v is None for v in s.values["VIS"])


def test_parse_rejects_non_ndbc():
    with pytest.raises(ValueError):
        parse_ndbc("time,temp\n2026-01-01,20\n")


def test_parse_rejects_ragged_row(ndbc_text):
    lines = ndbc_text.splitlines()
    lines[5] = lines[5] + " 1.0"
    with pytest.raises(ValueError):
        parse_ndbc("\n".join(lines))


def test_read_csv_maps_aliases_and_missing(tmp_path):
    p = tmp_path / "station.csv"
    p.write_text(
        "timestamp,temperatura,umidade,pressao\n"
        "2026-01-01T00:10:00Z,25.1,80,1012.0\n"
        "2026-01-01T00:00:00Z,25.0,,1012.1\n",
        encoding="utf-8",
    )
    s = read_csv(p)
    assert s.variables == ["ATMP", "RH", "PRES"]
    assert s.values["ATMP"] == [25.0, 25.1]  # sorted by time
    assert s.values["RH"] == [None, 80.0]
    assert s.times[0].tzinfo is not None
