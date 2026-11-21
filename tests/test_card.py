# © 2026 Henry Noguchi (github.com/hnryguchi). Todos os direitos reservados / All rights reserved. Ver/see LICENSE.
import xml.etree.ElementTree as ET

from conftest import FIXTURES, make_series

from metqc.card import status_svg
from metqc.cli import main
from metqc.engine import group_events, run_qc
from metqc.sources import parse_ndbc


def test_card_from_real_sample_is_valid_svg(ndbc_text):
    series = parse_ndbc(ndbc_text, station="41010")
    result = run_qc(series)
    svg = status_svg(result, group_events(result))
    root = ET.fromstring(svg)  # well-formed XML
    assert root.tag.endswith("svg")
    assert "Buoy 41010" in svg and "°C" in svg and "degC" not in svg
    assert "<polyline" in svg


def test_card_plots_flagged_variable_and_marks_the_spike():
    """SYNTHETIC: a single air temperature spike must be circled on the chart."""
    atmp = [20.0 + 0.01 * i for i in range(60)]
    atmp[30] = 29.0
    series = make_series({"ATMP": atmp, "PRES": [1013.0 + 0.1 * (i % 7) for i in range(60)]})
    series.units = {"ATMP": "degC", "PRES": "hPa"}
    result = run_qc(series)
    events = group_events(result)
    assert any(e.variable == "ATMP" for e in events)
    svg = status_svg(result, events, title="Test")
    assert "ATMP (°C), last 72 h" in svg
    assert 'stroke="#d29922"' in svg or 'stroke="#cf222e"' in svg  # suspect or fail marker


def test_cli_writes_card(tmp_path):
    card = tmp_path / "card" / "status.svg"
    rc = main(["check", str(FIXTURES / "ndbc_41010_sample.txt"), "--out", str(tmp_path / "r"),
               "--card", str(card), "--title", "Buoy 41010"])
    assert rc == 0 and card.read_text(encoding="utf-8").startswith("<svg")


def test_portuguese_card(ndbc_text):
    series = parse_ndbc(ndbc_text, station="41010")
    result = run_qc(series)
    svg = status_svg(result, group_events(result), lang="pt")
    ET.fromstring(svg)
    assert "Boia 41010: controle de qualidade automático" in svg and "Água" in svg and "Últimos 7 dias" in svg


def test_brand_palette(ndbc_text):
    from metqc.card import brand

    series = parse_ndbc(ndbc_text, station="41010")
    result = run_qc(series)
    svg = brand(status_svg(result, group_events(result), lang="pt"))
    ET.fromstring(svg)
    assert "#081a2e" in svg and "prefers-color-scheme" not in svg
