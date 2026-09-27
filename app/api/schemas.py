"""Pydantic response and request schemas for the API."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class PondSiteSchema(BaseModel):
    lat: float = Field(..., description="Latitude (WGS84) of the recommended pond outlet")
    lon: float = Field(..., description="Longitude (WGS84) of the recommended pond outlet")
    elevation_m: float = Field(..., description="Elevation at the pond outlet in metres")
    flow_accumulation_cells: int = Field(
        ..., description="D8 flow accumulation at the outlet (number of upstream cells)"
    )


class CatchmentSchema(BaseModel):
    area_m2: float = Field(..., description="Catchment area in square metres")
    area_hectares: float = Field(..., description="Catchment area in hectares")
    mean_slope_pct: float = Field(..., description="Mean slope of the catchment in percent rise")
    max_slope_pct: float = Field(..., description="Maximum slope within the catchment in percent rise")
    min_elevation_m: float = Field(..., description="Minimum elevation within the catchment in metres")
    max_elevation_m: float = Field(..., description="Maximum elevation within the catchment in metres")
    relief_m: float = Field(..., description="Elevation relief (max − min) within the catchment in metres")
    watershed_cell_count: int = Field(..., description="Number of DEM grid cells in the watershed")
    boundary_geojson: dict[str, Any] = Field(
        ..., description="GeoJSON Polygon/MultiPolygon of the catchment boundary (WGS84)"
    )


class HydrologySchema(BaseModel):
    annual_rainfall_mm: float = Field(..., description="Historical annual precipitation in mm")
    monsoon_rainfall_mm: float = Field(..., description="Design monsoon precipitation in mm (June-Sept)")
    runoff_coefficient: float = Field(..., description="Dimensionless runoff coefficient C (0.12 - 0.60)")
    expected_water_volume_m3: float = Field(..., description="Annual expected runoff volume in cubic metres")
    expected_water_volume_liters: float = Field(..., description="Expected harvest volume in Litres")
    expected_water_volume_megaliters: float = Field(..., description="Expected harvest volume in Million Litres (ML)")
    recommended_pond_depth_m: float = Field(..., description="Recommended excavation water depth in metres")
    recommended_pond_area_m2: float = Field(..., description="Recommended surface water spread area in m²")
    recommended_pond_storage_capacity_m3: float = Field(..., description="Recommended active storage capacity in m³")
    recommended_dimensions: str = Field(..., description="Suggested pond physical dimensions (Length × Width × Depth)")
    estimated_household_days: int = Field(..., description="Estimated rural household water security days supported")
    rainfall_source: str = Field(..., description="Data source for rainfall statistics")


class AnalyzeResponse(BaseModel):
    contour_interval_m: float = Field(..., description="Detected contour interval in metres")
    elevation_range_m: list[float] = Field(
        ..., description="[min_elevation_m, max_elevation_m] of the contour map"
    )
    total_contour_lines: int = Field(..., description="Total number of contour polylines parsed")
    grid_resolution_m: float = Field(..., description="Actual DEM grid resolution used")
    grid_shape: list[int] = Field(..., description="[rows, cols] of the internal DEM grid")
    resolution_auto_adjusted: bool = Field(
        ...,
        description="True if the resolution was coarsened to stay within RAM limits",
    )
    pond_site: PondSiteSchema
    catchment: CatchmentSchema
    hydrology: Optional[HydrologySchema] = Field(
        None, description="Rainfall, harvestable runoff volume, and pond sizing"
    )
    processing_time_ms: int = Field(..., description="Total server-side processing time in ms")


class SelectedAreaRequest(BaseModel):
    coordinates: list[list[float]] = Field(
        ...,
        description="Coordinates of the selected land polygon as [[lat, lon], ...] or GeoJSON polygon coordinates",
    )
    resolution_m: float = Field(10.0, description="Grid resolution for analysis")
    min_catchment_area_m2: float = Field(5000.0, description="Minimum catchment area constraint")
    override_rainfall_mm: Optional[float] = Field(None, description="Optional custom rainfall value in mm")
    soil_type: str = Field("medium", description="Soil classification: sandy, medium, loamy, clayey, rocky")
    target_depth_m: float = Field(3.0, description="Target pond depth in metres")


class AreaAnalyzeResponse(BaseModel):
    selected_land_geojson: dict[str, Any] = Field(..., description="GeoJSON Polygon of user-selected land area")
    selected_area_m2: float = Field(..., description="Total area of the selected land in m²")
    selected_area_hectares: float = Field(..., description="Total area of the selected land in hectares")
    pond_site: PondSiteSchema
    catchment: CatchmentSchema
    hydrology: HydrologySchema
    processing_time_ms: int
