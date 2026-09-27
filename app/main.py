"""FastAPI application entry point.

Serves:
- GET /: Interactive Web GIS frontend interface
- POST /analyzeContour: Uploaded KML/KMZ contour map analysis (with hydrology)
- POST /api/analyze-area: User-selected land boundary analysis on map
- GET /api/sample-contours: GeoJSON contour lines for live map preview
- GET /health: Health check
- Static assets at /static/
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from shapely.geometry import Polygon, mapping
from shapely.ops import transform as shp_transform

from app.api.schemas import (
    AnalyzeResponse,
    AreaAnalyzeResponse,
    CatchmentSchema,
    HydrologySchema,
    PondSiteSchema,
    SelectedAreaRequest,
)
from app.dem.builder import DEMResult, build_dem
from app.hydrology.calculator import calculate_hydrology
from app.parser.kml_parser import ContourDataset, parse_kml_file
from app.pond.selector import select_pond_and_catchment
from app.terrain.analysis import TerrainAnalysis

BASE_DIR = Path(__file__).parent.parent
STATIC_DIR = Path(__file__).parent / "static"
SAMPLE_KML_PATH = BASE_DIR / "contours_1m.kml"

app = FastAPI(
    title="HydroPond AI | Precision Village Pond & Catchment Planning",
    description=(
        "Full-stack Web GIS and hydrological decision support system. "
        "Accepts contour maps or user-drawn land boundaries, runs D8 flow routing, "
        "recommends optimal village pond locations, and estimates harvestable rainwater runoff volume."
    ),
    version="2.0.0",
)

# Enable CORS for external API integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static folder
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# In-memory cache for sample contour dataset & DEM to guarantee sub-second responses
_CACHED_SAMPLE_DATASET: ContourDataset | None = None
_CACHED_SAMPLE_DEM: DEMResult | None = None
_CACHED_SAMPLE_TERRAIN: TerrainAnalysis | None = None
_CACHED_CONTOURS_GEOJSON: dict[str, Any] | None = None


def _get_preloaded_sample():
    """Lazily load and cache the sample contour dataset and DEM."""
    global _CACHED_SAMPLE_DATASET, _CACHED_SAMPLE_DEM, _CACHED_SAMPLE_TERRAIN
    if _CACHED_SAMPLE_DATASET is None and SAMPLE_KML_PATH.exists():
        _CACHED_SAMPLE_DATASET = parse_kml_file(SAMPLE_KML_PATH)
        _CACHED_SAMPLE_DEM = build_dem(_CACHED_SAMPLE_DATASET, resolution_m=10.0)
        _CACHED_SAMPLE_TERRAIN = TerrainAnalysis(_CACHED_SAMPLE_DEM.elevation_grid)
    return _CACHED_SAMPLE_DATASET, _CACHED_SAMPLE_DEM, _CACHED_SAMPLE_TERRAIN


# ---------------------------------------------------------------------------
# Frontend Route
# ---------------------------------------------------------------------------


@app.api_route("/", methods=["GET", "HEAD"], summary="Web GIS Frontend")
async def index():
    """Serve the interactive Web GIS dashboard."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse(
        {"status": "ok", "message": "Pond Catchment Analysis API is live. Visit /docs for OpenAPI specs."}
    )


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------


@app.get("/health", summary="Health check")
async def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Sample Contours Overlay
# ---------------------------------------------------------------------------


@app.get("/api/sample-contours", summary="Get GeoJSON contour lines for map overlay")
async def get_sample_contours() -> dict:
    """Return a simplified GeoJSON FeatureCollection of contour lines for map display."""
    global _CACHED_CONTOURS_GEOJSON
    if _CACHED_CONTOURS_GEOJSON is not None:
        return _CACHED_CONTOURS_GEOJSON

    dataset, _, _ = _get_preloaded_sample()
    if not dataset or not dataset.polylines:
        return {"type": "FeatureCollection", "features": []}

    features = []
    # Sample every 2nd or 3rd contour line to keep GeoJSON payload fast (< 250 KB)
    for i, pl in enumerate(dataset.polylines):
        elev = pl.elevation
        # Include all 5m index contours and every 3rd intermediate contour
        if elev % 5 == 0 or i % 3 == 0:
            coords = [[round(pt[0], 5), round(pt[1], 5)] for pt in pl.coords]
            if len(coords) >= 2:
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": coords},
                        "properties": {"elevation": elev},
                    }
                )

    _CACHED_CONTOURS_GEOJSON = {"type": "FeatureCollection", "features": features}
    return _CACHED_CONTOURS_GEOJSON


# ---------------------------------------------------------------------------
# Selected Land Area Analysis
# ---------------------------------------------------------------------------


@app.post("/api/analyze-area", response_model=AreaAnalyzeResponse, summary="Analyze user-selected land area")
async def analyze_area(req: SelectedAreaRequest) -> AreaAnalyzeResponse:
    """Analyze a land polygon selected by the user on the map.
    
    Identifies the optimal pond location inside or draining the land parcel,
    delineates the upstream catchment, and calculates expected rainwater runoff volume.
    """
    t0 = time.perf_counter()

    if len(req.coordinates) < 3:
        raise HTTPException(
            status_code=400,
            detail="A polygon must contain at least 3 coordinate points.",
        )

    # Coordinates are sent as [lat, lon] from Leaflet. Shapely expects (lon, lat).
    poly_pts = [(p[1], p[0]) for p in req.coordinates]
    # Ensure polygon is closed
    if poly_pts[0] != poly_pts[-1]:
        poly_pts.append(poly_pts[0])

    try:
        land_poly = Polygon(poly_pts)
        if not land_poly.is_valid:
            land_poly = land_poly.buffer(0)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid polygon geometry: {exc}") from exc

    dataset, dem_result, terrain = _get_preloaded_sample()
    if not dataset or not dem_result or not terrain:
        raise HTTPException(status_code=500, detail="Base terrain model not available.")

    # Calculate area of the user's selected land in projected UTM space
    def _to_proj(lon, lat, z=None):
        return dem_result.transformer_to_proj.transform(lon, lat)

    poly_proj = shp_transform(_to_proj, land_poly)
    selected_area_m2 = round(float(poly_proj.area), 2)
    selected_area_ha = round(selected_area_m2 / 10000.0, 4)

    # Run pond selection constrained to the user's land parcel
    try:
        result = select_pond_and_catchment(
            terrain=terrain,
            dem_result=dem_result,
            dataset=dataset,
            min_catchment_area_m2=req.min_catchment_area_m2,
            land_polygon=land_poly,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Run Hydrology & Water Volume calculations
    hydro = calculate_hydrology(
        catchment_area_m2=result.catchment.area_m2,
        mean_slope_pct=result.catchment.mean_slope_pct,
        lat=result.pond_site.lat,
        lon=result.pond_site.lon,
        override_rainfall_mm=req.override_rainfall_mm,
        soil_type=req.soil_type,
        target_pond_depth_m=req.target_depth_m,
    )

    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    return AreaAnalyzeResponse(
        selected_land_geojson=dict(mapping(land_poly)),
        selected_area_m2=selected_area_m2,
        selected_area_hectares=selected_area_ha,
        pond_site=PondSiteSchema(
            lat=result.pond_site.lat,
            lon=result.pond_site.lon,
            elevation_m=result.pond_site.elevation_m,
            flow_accumulation_cells=result.pond_site.flow_accumulation_cells,
        ),
        catchment=CatchmentSchema(
            area_m2=result.catchment.area_m2,
            area_hectares=result.catchment.area_hectares,
            mean_slope_pct=result.catchment.mean_slope_pct,
            max_slope_pct=result.catchment.max_slope_pct,
            min_elevation_m=result.catchment.min_elevation_m,
            max_elevation_m=result.catchment.max_elevation_m,
            relief_m=result.catchment.relief_m,
            watershed_cell_count=result.catchment.watershed_cell_count,
            boundary_geojson=result.catchment.boundary_geojson,
        ),
        hydrology=HydrologySchema(
            annual_rainfall_mm=hydro.annual_rainfall_mm,
            monsoon_rainfall_mm=hydro.monsoon_rainfall_mm,
            runoff_coefficient=hydro.runoff_coefficient,
            expected_water_volume_m3=hydro.expected_water_volume_m3,
            expected_water_volume_liters=hydro.expected_water_volume_liters,
            expected_water_volume_megaliters=hydro.expected_water_volume_megaliters,
            recommended_pond_depth_m=hydro.recommended_pond_depth_m,
            recommended_pond_area_m2=hydro.recommended_pond_area_m2,
            recommended_pond_storage_capacity_m3=hydro.recommended_pond_storage_capacity_m3,
            recommended_dimensions=hydro.recommended_dimensions,
            estimated_household_days=hydro.estimated_household_days,
            rainfall_source=hydro.rainfall_source,
        ),
        processing_time_ms=elapsed_ms,
    )


# ---------------------------------------------------------------------------
# Upload Contour Map Analysis (KML / KMZ)
# ---------------------------------------------------------------------------


@app.post(
    "/analyzeContour",
    response_model=AnalyzeResponse,
    summary="Analyse a contour map and return pond site + catchment",
)
async def analyze_contour(
    contour_map: UploadFile = File(..., description="KML or KMZ contour map"),
    resolution_m: float = Form(10.0, description="DEM grid resolution in metres"),
    min_catchment_area_m2: float = Form(10000.0, description="Minimum catchment area (m²)"),
) -> AnalyzeResponse:
    t0 = time.perf_counter()

    filename = contour_map.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in (".kml", ".kmz"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Upload a .kml or .kmz file.",
        )

    suffix = ext
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name
            while chunk := await contour_map.read(1 << 20):  # 1 MB chunks
                tmp.write(chunk)

        # [1] Parse
        try:
            dataset = parse_kml_file(tmp_path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # [2+3] Project + build DEM
        dem_result = build_dem(dataset, resolution_m=resolution_m)

        # [4] Terrain analysis
        terrain = TerrainAnalysis(dem_result.elevation_grid)

        # [5+6] Pond selection + catchment delineation
        try:
            result = select_pond_and_catchment(
                terrain=terrain,
                dem_result=dem_result,
                dataset=dataset,
                min_catchment_area_m2=min_catchment_area_m2,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        # Hydrology calculation
        hydro = calculate_hydrology(
            catchment_area_m2=result.catchment.area_m2,
            mean_slope_pct=result.catchment.mean_slope_pct,
            lat=result.pond_site.lat,
            lon=result.pond_site.lon,
        )

        elapsed_ms = round((time.perf_counter() - t0) * 1000)

        rows, cols = dem_result.elevation_grid.shape
        return AnalyzeResponse(
            contour_interval_m=dataset.contour_interval_m,
            elevation_range_m=[dataset.elevation_min, dataset.elevation_max],
            total_contour_lines=len(dataset.polylines),
            grid_resolution_m=dem_result.actual_resolution_m,
            grid_shape=[rows, cols],
            resolution_auto_adjusted=dem_result.auto_adjusted,
            pond_site=PondSiteSchema(
                lat=result.pond_site.lat,
                lon=result.pond_site.lon,
                elevation_m=result.pond_site.elevation_m,
                flow_accumulation_cells=result.pond_site.flow_accumulation_cells,
            ),
            catchment=CatchmentSchema(
                area_m2=result.catchment.area_m2,
                area_hectares=result.catchment.area_hectares,
                mean_slope_pct=result.catchment.mean_slope_pct,
                max_slope_pct=result.catchment.max_slope_pct,
                min_elevation_m=result.catchment.min_elevation_m,
                max_elevation_m=result.catchment.max_elevation_m,
                relief_m=result.catchment.relief_m,
                watershed_cell_count=result.catchment.watershed_cell_count,
                boundary_geojson=result.catchment.boundary_geojson,
            ),
            hydrology=HydrologySchema(
                annual_rainfall_mm=hydro.annual_rainfall_mm,
                monsoon_rainfall_mm=hydro.monsoon_rainfall_mm,
                runoff_coefficient=hydro.runoff_coefficient,
                expected_water_volume_m3=hydro.expected_water_volume_m3,
                expected_water_volume_liters=hydro.expected_water_volume_liters,
                expected_water_volume_megaliters=hydro.expected_water_volume_megaliters,
                recommended_pond_depth_m=hydro.recommended_pond_depth_m,
                recommended_pond_area_m2=hydro.recommended_pond_area_m2,
                recommended_pond_storage_capacity_m3=hydro.recommended_pond_storage_capacity_m3,
                recommended_dimensions=hydro.recommended_dimensions,
                estimated_household_days=hydro.estimated_household_days,
                rainfall_source=hydro.rainfall_source,
            ),
            processing_time_ms=elapsed_ms,
        )

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Processing error: {exc}") from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
