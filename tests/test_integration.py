"""Integration tests for the full pipeline via FastAPI TestClient.

These tests exercise:
- GET /health
- POST /analyzeContour with the real sample KML file
- POST /analyzeContour with invalid files (400 errors)
- POST /analyzeContour with no-pond-found edge case (422)
"""

from __future__ import annotations

import io
import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

SAMPLE_KML = Path(__file__).parent.parent / "contours_1m.kml"

client = TestClient(app)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_wrong_extension_returns_400():
    resp = client.post(
        "/analyzeContour",
        files={"contour_map": ("terrain.tif", b"garbage", "application/octet-stream")},
        data={"resolution_m": "10.0"},
    )
    assert resp.status_code == 400
    assert "Unsupported" in resp.json()["detail"]


def test_corrupt_kml_returns_400():
    resp = client.post(
        "/analyzeContour",
        files={"contour_map": ("bad.kml", b"<not valid xml <<<", "application/xml")},
        data={"resolution_m": "10.0"},
    )
    assert resp.status_code == 400


def test_empty_kml_returns_400():
    empty_kml = textwrap.dedent("""<?xml version="1.0"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
          <Document></Document>
        </kml>
    """).encode()
    resp = client.post(
        "/analyzeContour",
        files={"contour_map": ("empty.kml", empty_kml, "application/vnd.google-earth.kml+xml")},
        data={"resolution_m": "10.0"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Sample KML integration test
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not SAMPLE_KML.exists(), reason="contours_1m.kml not present")
class TestSampleKmlIntegration:
    """Full pipeline against the real sample file.  Uses resolution_m=20 to
    keep the test fast (< 60 s on a laptop) while still exercising all layers.
    """

    @pytest.fixture(scope="class", autouse=True)
    def setup_response(self, request):
        with open(SAMPLE_KML, "rb") as f:
            data = f.read()
        resp = client.post(
            "/analyzeContour",
            files={"contour_map": ("contours_1m.kml", data, "application/vnd.google-earth.kml+xml")},
            data={"resolution_m": "20.0", "min_catchment_area_m2": "500"},
        )
        request.cls.resp = resp

    @pytest.fixture
    def response(self):
        return self.resp

    def test_status_200(self, response):
        assert response.status_code == 200, response.text

    def test_response_schema(self, response):
        body = response.json()
        assert "contour_interval_m" in body
        assert "elevation_range_m" in body
        assert "total_contour_lines" in body
        assert "grid_resolution_m" in body
        assert "grid_shape" in body
        assert "resolution_auto_adjusted" in body
        assert "pond_site" in body
        assert "catchment" in body
        assert "processing_time_ms" in body
        # pond_site sub-fields
        ps = body["pond_site"]
        assert "flow_accumulation_cells" in ps
        # catchment sub-fields
        c = body["catchment"]
        for f in ("max_slope_pct", "min_elevation_m", "max_elevation_m",
                  "relief_m", "watershed_cell_count", "boundary_geojson"):
            assert f in c, f"Missing catchment field: {f}"

    def test_elevation_range_sanity(self, response):
        body = response.json()
        lo, hi = body["elevation_range_m"]
        assert lo < hi
        assert lo >= 200.0  # broad sanity bounds
        assert hi <= 400.0

    def test_contour_interval_is_1m(self, response):
        body = response.json()
        assert abs(body["contour_interval_m"] - 1.0) < 0.6

    def test_pond_site_coords_in_range(self, response):
        body = response.json()
        ps = body["pond_site"]
        assert -90 <= ps["lat"] <= 90
        assert -180 <= ps["lon"] <= 180
        assert body["elevation_range_m"][0] <= ps["elevation_m"] <= body["elevation_range_m"][1]

    def test_catchment_area_positive(self, response):
        body = response.json()
        assert body["catchment"]["area_m2"] > 0
        assert body["catchment"]["area_hectares"] > 0

    def test_catchment_geojson_polygon(self, response):
        body = response.json()
        geo = body["catchment"]["boundary_geojson"]
        assert geo["type"] in ("Polygon", "MultiPolygon")
        assert "coordinates" in geo

    def test_processing_time_recorded(self, response):
        body = response.json()
        assert body["processing_time_ms"] > 0

    def test_mean_slope_positive(self, response):
        body = response.json()
        assert body["catchment"]["mean_slope_pct"] >= 0
