"""Pond site selector and catchment delineator.

Heuristic scoring
-----------------
For each candidate cell (not on the grid boundary), compute a score:

    score = w_accum * norm(log1p(flow_accum))
          + w_low   * norm(1 / (1 + elevation_rank_within_local_window))

where ``norm`` rescales the quantity to [0, 1].

The top-scoring cell is chosen as the pond outlet.  Cells whose upstream
catchment area is smaller than ``min_catchment_area_m2`` are excluded.

Catchment delineation
---------------------
Starting from the outlet cell, walk upstream along the D8 flow direction
grid (BFS), collecting all cells that ultimately drain into the outlet.
The union of those cells' bounding boxes is traced into a Shapely polygon
in the projected CRS, then reprojected to WGS84.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np
from shapely.geometry import MultiPoint, mapping
from shapely.ops import unary_union

from app.dem.builder import DEMResult
from app.parser.kml_parser import ContourDataset
from app.terrain.analysis import (
    TerrainAnalysis,
    _D8_DR,
    _D8_DC,
    _D8_REVERSE,
    compute_slope_percent,
)


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PondSite:
    lat: float
    lon: float
    elevation_m: float
    flow_accumulation_cells: int


@dataclass
class CatchmentInfo:
    area_m2: float
    area_hectares: float
    mean_slope_pct: float
    max_slope_pct: float
    min_elevation_m: float
    max_elevation_m: float
    relief_m: float
    watershed_cell_count: int
    boundary_geojson: dict[str, Any]


@dataclass
class PondResult:
    pond_site: PondSite
    catchment: CatchmentInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise(arr: np.ndarray) -> np.ndarray:
    """Min-max normalise arr to [0, 1], handling degenerate (constant) case."""
    lo, hi = arr.min(), arr.max()
    if hi == lo:
        return np.zeros_like(arr, dtype=np.float64)
    return (arr - lo) / (hi - lo)


def _upstream_cells(
    outlet_r: int,
    outlet_c: int,
    flow_dir: np.ndarray,
) -> list[tuple[int, int]]:
    """BFS upstream from (outlet_r, outlet_c) using reversed D8 flow directions.

    Returns a list of all (row, col) cells in the upstream catchment,
    including the outlet cell itself.
    """
    rows, cols = flow_dir.shape
    visited = np.zeros((rows, cols), dtype=bool)
    visited[outlet_r, outlet_c] = True
    queue: deque[tuple[int, int]] = deque([(outlet_r, outlet_c)])
    cells: list[tuple[int, int]] = []

    while queue:
        r, c = queue.popleft()
        cells.append((r, c))
        # Check all 8 neighbours to see if they drain into (r, c)
        for d in range(8):
            nr, nc = r + _D8_DR[d], c + _D8_DC[d]
            if 0 <= nr < rows and 0 <= nc < cols and not visited[nr, nc]:
                # Neighbour drains into (r, c) if its flow direction is the
                # reverse of d (i.e. it points toward r,c)
                if int(flow_dir[nr, nc]) == int(_D8_REVERSE[d]):
                    visited[nr, nc] = True
                    queue.append((nr, nc))

    return cells


def _cells_to_polygon(
    cells: list[tuple[int, int]],
    transform: tuple[float, float, float, float],
) -> Any:  # shapely.geometry.Polygon | MultiPolygon
    """Convert upstream cell list to a Shapely polygon in projected coordinates.

    Each cell contributes a small square tile.  The union of all tiles forms
    the catchment polygon.

    Parameters
    ----------
    cells:
        List of (row, col) indices.
    transform:
        (origin_east, origin_north, res, res) — same as DEMResult.transform.
    """
    from shapely.geometry import box

    origin_e, origin_n, res, _ = transform
    polys = []
    for r, c in cells:
        # Cell centre
        e = origin_e + c * res
        n = origin_n + r * res
        half = res / 2.0
        polys.append(box(e - half, n - half, e + half, n + half))

    if not polys:
        raise ValueError("No upstream cells — cannot build catchment polygon.")

    merged = unary_union(polys)
    return merged


def _reproject_polygon(geom: Any, transformer_to_lonlat) -> Any:
    """Reproject a Shapely geometry from projected CRS to WGS84 lon/lat."""
    from shapely.geometry import shape, mapping
    from shapely.ops import transform as shp_transform

    def _transform_coords(x, y, z=None):
        lons, lats = transformer_to_lonlat.transform(x, y)
        return lons, lats

    return shp_transform(_transform_coords, geom)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def select_pond_and_catchment(
    terrain: TerrainAnalysis,
    dem_result: DEMResult,
    dataset: ContourDataset,
    min_catchment_area_m2: float = 500.0,
    w_accum: float = 0.7,
    w_low: float = 0.3,
    border_margin: int = 2,
) -> PondResult:
    """Select the best pond outlet and delineate its catchment.

    Parameters
    ----------
    terrain:
        Pre-computed TerrainAnalysis (filled DEM, flow direction, accumulation).
    dem_result:
        DEMResult carrying the affine transform and inverse transformer.
    dataset:
        Original ContourDataset (used only for metadata).
    min_catchment_area_m2:
        Cells whose upstream catchment area is below this threshold are
        excluded from consideration as pond outlets.
    w_accum, w_low:
        Weighting factors for the scoring heuristic.
    border_margin:
        Number of cells to exclude from the border (prevents selecting cells
        right at the edge of the DEM where flow routing is unreliable).

    Returns
    -------
    PondResult with pond site coordinates and catchment statistics.

    Raises
    ------
    ValueError if no valid pond outlet can be identified.
    """
    rows, cols = terrain.flow_accum.shape
    res = dem_result.actual_resolution_m
    cell_area_m2 = res * res

    # --- build candidate mask (interior cells only) ---
    mask = np.zeros((rows, cols), dtype=bool)
    mask[border_margin : rows - border_margin, border_margin : cols - border_margin] = True

    # Exclude cells with too-small catchments
    catchment_area = terrain.flow_accum.astype(np.float64) * cell_area_m2
    mask &= catchment_area >= min_catchment_area_m2

    if not mask.any():
        raise ValueError(
            f"No cells meet the minimum catchment area of {min_catchment_area_m2} m². "
            "Try lowering min_catchment_area_m2 or using a finer resolution."
        )

    # --- scoring ---
    # Normalise log-accumulation against the GLOBAL grid max so that the
    # truly highest-drainage-area cell always scores close to 1.0, regardless
    # of which cells are in the candidate set.
    log_accum = np.log1p(terrain.flow_accum.astype(np.float64))
    global_log_max = log_accum.max()
    if global_log_max > 0:
        score_accum = log_accum / global_log_max  # [0, 1] globally
    else:
        score_accum = np.zeros_like(log_accum)
    score_accum = np.where(mask, score_accum, 0.0)

    # Elevation component: normalise within candidates (lower is better)
    elevation_score = _normalise(np.where(mask, terrain.filled_dem, np.nan))
    score_low = 1.0 - elevation_score  # invert: lower elev → higher score
    score_low = np.nan_to_num(score_low, nan=0.0)

    total_score = w_accum * score_accum + w_low * score_low
    total_score = np.where(mask, total_score, -1.0)

    # --- select outlet ---
    flat_idx = int(total_score.argmax())
    outlet_r, outlet_c = divmod(flat_idx, cols)

    # --- pond site in WGS84 ---
    origin_e, origin_n, res_e, res_n = dem_result.transform
    outlet_e = origin_e + outlet_c * res_e
    outlet_n = origin_n + outlet_r * res_n
    outlet_lon, outlet_lat = dem_result.transformer_to_lonlat.transform(outlet_e, outlet_n)
    outlet_elev = float(terrain.filled_dem[outlet_r, outlet_c])

    # --- upstream catchment cells ---
    upstream = _upstream_cells(outlet_r, outlet_c, terrain.flow_dir)

    if len(upstream) * cell_area_m2 < min_catchment_area_m2:
        raise ValueError(
            "Best candidate pond site has a catchment area smaller than "
            f"min_catchment_area_m2={min_catchment_area_m2} m². "
            "Try a lower threshold or a different resolution."
        )

    # --- catchment polygon ---
    catchment_poly_proj = _cells_to_polygon(upstream, dem_result.transform)
    catchment_poly_wgs84 = _reproject_polygon(
        catchment_poly_proj, dem_result.transformer_to_lonlat
    )

    n_cells = len(upstream)
    area_m2 = float(n_cells * cell_area_m2)
    area_ha = area_m2 / 10_000.0

    # --- slope and elevation stats over catchment cells ---
    slope_grid = compute_slope_percent(terrain.filled_dem, res)
    rows_up = np.array([r for r, c in upstream], dtype=np.int32)
    cols_up = np.array([c for r, c in upstream], dtype=np.int32)

    catchment_slopes = slope_grid[rows_up, cols_up]
    catchment_elevs  = terrain.filled_dem[rows_up, cols_up]

    mean_slope = float(np.mean(catchment_slopes))
    max_slope  = float(np.max(catchment_slopes))
    min_elev   = float(np.min(catchment_elevs))
    max_elev   = float(np.max(catchment_elevs))
    relief     = round(max_elev - min_elev, 2)

    # Flow accumulation value at the outlet cell
    outlet_accum = int(terrain.flow_accum[outlet_r, outlet_c])

    # --- GeoJSON representation ---
    geojson_dict = dict(mapping(catchment_poly_wgs84))

    return PondResult(
        pond_site=PondSite(
            lat=round(float(outlet_lat), 6),
            lon=round(float(outlet_lon), 6),
            elevation_m=round(outlet_elev, 2),
            flow_accumulation_cells=outlet_accum,
        ),
        catchment=CatchmentInfo(
            area_m2=round(area_m2, 2),
            area_hectares=round(area_ha, 4),
            mean_slope_pct=round(mean_slope, 2),
            max_slope_pct=round(max_slope, 2),
            min_elevation_m=round(min_elev, 2),
            max_elevation_m=round(max_elev, 2),
            relief_m=relief,
            watershed_cell_count=n_cells,
            boundary_geojson=geojson_dict,
        ),
    )
