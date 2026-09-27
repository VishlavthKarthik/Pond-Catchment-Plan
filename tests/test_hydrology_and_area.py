"""Tests for hydrology calculations and area-based analysis endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.hydrology.calculator import (
    calculate_hydrology,
    compute_runoff_coefficient,
    fetch_historical_rainfall,
)
from app.main import app

client = TestClient(app)


def test_index_serves_html():
    """Verify frontend HTML dashboard is served at root GET /."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "HydroPond AI" in resp.text
    assert "<div id=\"map\">" in resp.text


def test_sample_contours_api():
    """Verify sample contour preview API returns valid GeoJSON."""
    resp = client.get("/api/sample-contours")
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0
    assert "elevation" in data["features"][0]["properties"]


def test_runoff_coefficient_scaling():
    """Verify runoff coefficient scales properly with terrain slope."""
    c_flat = compute_runoff_coefficient(1.0, "medium")
    c_medium = compute_runoff_coefficient(4.5, "medium")
    c_steep = compute_runoff_coefficient(12.0, "medium")

    assert 0.15 <= c_flat <= 0.25
    assert c_flat < c_medium < c_steep
    assert c_steep <= 0.60


def test_hydrology_calculation_metrics():
    """Verify water volume and sizing calculations."""
    res = calculate_hydrology(
        catchment_area_m2=50000.0,
        mean_slope_pct=4.0,
        lat=21.257,
        lon=81.309,
        override_rainfall_mm=1000.0,
        soil_type="medium",
        target_pond_depth_m=3.0,
    )

    assert res.annual_rainfall_mm == 1000.0
    assert res.monsoon_rainfall_mm == 850.0
    assert res.expected_water_volume_m3 > 0
    assert res.expected_water_volume_megaliters > 0
    assert res.recommended_pond_area_m2 > 0
    assert res.estimated_household_days > 0
    assert "m ×" in res.recommended_dimensions


def test_analyze_area_endpoint():
    """Verify POST /api/analyze-area with a drawn land polygon."""
    sample_poly = [
        [21.255, 81.307],
        [21.260, 81.307],
        [21.260, 81.312],
        [21.255, 81.312],
    ]

    resp = client.post(
        "/api/analyze-area",
        json={
            "coordinates": sample_poly,
            "resolution_m": 10.0,
            "min_catchment_area_m2": 2000.0,
            "soil_type": "medium",
            "target_depth_m": 3.0,
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "selected_land_geojson" in data
    assert data["selected_area_m2"] > 0
    assert "pond_site" in data
    assert "catchment" in data
    assert "hydrology" in data
    assert data["hydrology"]["expected_water_volume_m3"] > 0
    assert data["hydrology"]["expected_water_volume_megaliters"] > 0
