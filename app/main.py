"""FastAPI application entry point."""

import time
import tempfile
import os
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse

from app.parser.kml_parser import parse_kml_file
from app.dem.builder import build_dem
from app.terrain.analysis import TerrainAnalysis
from app.pond.selector import select_pond_and_catchment
from app.api.schemas import AnalyzeResponse

app = FastAPI(
    title="Pond Catchment Analysis API",
    description=(
        "Accepts a contour map (KML/KMZ), analyses terrain, identifies a suitable pond "
        "location, and returns the corresponding catchment area as structured JSON."
    ),
    version="1.0.0",
)


@app.get("/health", summary="Health check")
async def health() -> dict:
    return {"status": "ok"}


@app.post(
    "/analyzeContour",
    response_model=AnalyzeResponse,
    summary="Analyse a contour map and return pond site + catchment",
)
async def analyze_contour(
    file: UploadFile = File(..., description="KML or KMZ contour map"),
    resolution_m: float = Form(10.0, description="DEM grid resolution in metres"),
    min_catchment_area_m2: float = Form(500.0, description="Minimum catchment area (m²)"),
) -> AnalyzeResponse:
    t0 = time.perf_counter()

    # --- validate extension ---
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in (".kml", ".kmz"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Upload a .kml or .kmz file.",
        )

    # --- stream upload to a temp file (phase-2 files may be large) ---
    suffix = ext
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name
            while chunk := await file.read(1 << 20):  # 1 MB chunks
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

        elapsed_ms = round((time.perf_counter() - t0) * 1000)

        from app.api.schemas import PondSiteSchema, CatchmentSchema

        return AnalyzeResponse(
            contour_interval_m=dataset.contour_interval_m,
            elevation_range_m=[dataset.elevation_min, dataset.elevation_max],
            grid_resolution_m=dem_result.actual_resolution_m,
            resolution_auto_adjusted=dem_result.auto_adjusted,
            pond_site=PondSiteSchema(
                lat=result.pond_site.lat,
                lon=result.pond_site.lon,
                elevation_m=result.pond_site.elevation_m,
            ),
            catchment=CatchmentSchema(
                area_m2=result.catchment.area_m2,
                area_hectares=result.catchment.area_hectares,
                mean_slope_pct=result.catchment.mean_slope_pct,
                boundary_geojson=result.catchment.boundary_geojson,
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
