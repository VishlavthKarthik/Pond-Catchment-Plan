"""Unit tests for the KML/KMZ parser."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.parser.kml_parser import (
    ContourDataset,
    ContourPolyline,
    parse_kml_bytes,
    parse_kml_file,
)

SAMPLE_KML = Path(__file__).parent.parent / "contours_1m.kml"


# ---------------------------------------------------------------------------
# Minimal synthetic KML
# ---------------------------------------------------------------------------

def _make_kml(placemarks: str) -> bytes:
    """Wrap placemark XML inside a minimal KML document."""
    return textwrap.dedent(f"""<?xml version="1.0" encoding="UTF-8"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
          <Document>
            {placemarks}
          </Document>
        </kml>
    """).encode()


SINGLE_PLACEMARK = _make_kml("""
    <Placemark>
      <name>274</name>
      <LineString>
        <coordinates>81.2934,21.2521,274 81.2950,21.2535,274 81.2970,21.2550,274</coordinates>
      </LineString>
    </Placemark>
""")

TWO_ELEVATIONS = _make_kml("""
    <Placemark>
      <name>274</name>
      <LineString>
        <coordinates>81.29,21.25,274 81.30,21.26,274 81.31,21.27,274</coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>275</name>
      <LineString>
        <coordinates>81.29,21.28,275 81.30,21.29,275 81.31,21.30,275</coordinates>
      </LineString>
    </Placemark>
""")

CORRUPT_XML = b"<not valid xml <<<"

NO_PLACEMARKS = _make_kml("")


# ---------------------------------------------------------------------------
# Tests — parse_kml_bytes
# ---------------------------------------------------------------------------


class TestParseKmlBytes:
    def test_single_placemark(self):
        ds = parse_kml_bytes(SINGLE_PLACEMARK)
        assert isinstance(ds, ContourDataset)
        assert len(ds.polylines) == 1
        pl = ds.polylines[0]
        assert pl.elevation == pytest.approx(274.0)
        assert len(pl.coords) == 3
        assert pl.coords[0] == pytest.approx((81.2934, 21.2521))

    def test_two_elevations_stats(self):
        ds = parse_kml_bytes(TWO_ELEVATIONS)
        assert len(ds.polylines) == 2
        assert ds.elevation_min == pytest.approx(274.0)
        assert ds.elevation_max == pytest.approx(275.0)
        assert ds.contour_interval_m == pytest.approx(1.0)

    def test_corrupt_xml_raises_value_error(self):
        with pytest.raises(ValueError, match="XML parse error"):
            parse_kml_bytes(CORRUPT_XML)

    def test_no_placemarks_raises_value_error(self):
        with pytest.raises(ValueError, match="No contour polylines"):
            parse_kml_bytes(NO_PLACEMARKS)


# ---------------------------------------------------------------------------
# Tests — parse_kml_file (sample file)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not SAMPLE_KML.exists(), reason="contours_1m.kml not present")
class TestParseSampleKml:
    def test_returns_dataset(self):
        ds = parse_kml_file(str(SAMPLE_KML))
        assert isinstance(ds, ContourDataset)

    def test_polyline_count(self):
        ds = parse_kml_file(str(SAMPLE_KML))
        # The sample file has ~2711 contour lines
        assert len(ds.polylines) > 100, f"Expected many polylines, got {len(ds.polylines)}"

    def test_elevation_range(self):
        ds = parse_kml_file(str(SAMPLE_KML))
        # Known approximate range from the plan doc: 267–298 m
        assert ds.elevation_min >= 260.0
        assert ds.elevation_max <= 310.0
        assert ds.elevation_max > ds.elevation_min

    def test_contour_interval(self):
        ds = parse_kml_file(str(SAMPLE_KML))
        # Sample file is a 1-m interval map
        assert ds.contour_interval_m == pytest.approx(1.0, abs=0.5)

    def test_all_polylines_have_coords(self):
        ds = parse_kml_file(str(SAMPLE_KML))
        for pl in ds.polylines:
            assert len(pl.coords) >= 2, f"Polyline at elev {pl.elevation} has < 2 points"

    def test_wgs84_coords_in_range(self):
        ds = parse_kml_file(str(SAMPLE_KML))
        for pl in ds.polylines:
            for lon, lat in pl.coords:
                assert -180 <= lon <= 180, f"lon={lon} out of range"
                assert -90 <= lat <= 90, f"lat={lat} out of range"


class TestParseKmlFileErrors:
    def test_unsupported_extension(self, tmp_path):
        f = tmp_path / "bad.tif"
        f.write_bytes(b"garbage")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            parse_kml_file(str(f))

    def test_missing_file(self):
        with pytest.raises(ValueError, match="Cannot read file"):
            parse_kml_file("/nonexistent/path/to/file.kml")
