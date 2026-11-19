import json

from conftest import FIXTURES

from metqc.site import build_site

GEO = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-78.478, 28.86]},
         "properties": {"station": "41010", "name": "Canaveral East", "short_name": "Cabo Canaveral",
                        "data": "https://www.ndbc.noaa.gov/station_page.php?station=41010"}},
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-70.651, 42.346]},
         "properties": {"station": "44013", "name": "Boston"}},  # no data file: must be skipped
    ],
}


def test_build_site_from_real_sample(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    sample = (FIXTURES / "ndbc_41010_sample.txt").read_text(encoding="utf-8")
    (data / "41010.txt").write_text(sample, encoding="utf-8")
    geo = tmp_path / "stations.geojson"
    geo.write_text(json.dumps(GEO), encoding="utf-8")
    out = tmp_path / "dist"

    payload = build_site(data, geo, out)

    assert [s["id"] for s in payload["stations"]] == ["41010"]  # 44013 skipped, not faked
    for f in ("index.html", "app.js", "style.css", "stations.json", "41010/series.json", "41010/status.svg",
              "41010/status-pt.svg", "41010/qc_report.json", "41010/qc_report.md"):
        assert (out / f).exists(), f
    st = payload["stations"][0]
    assert st["name"] == "Cabo Canaveral" and st["records"] > 0 and "PRES" in st["latest"]
    ser = json.loads((out / "41010" / "series.json").read_text(encoding="utf-8"))
    n = len(ser["minutes"])
    assert all(len(v["values"]) == n for v in ser["variables"].values())
    assert all(0 <= i < n and code in (3, 4) for v in ser["variables"].values() for i, code in v["flagged"])
