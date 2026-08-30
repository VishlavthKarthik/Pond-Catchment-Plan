"""Pydantic response schemas for the API."""

from __future__ import annotations

from typing import Any

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
    processing_time_ms: int = Field(..., description="Total server-side processing time in ms")
