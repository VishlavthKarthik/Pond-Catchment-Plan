"""DEM builder: project contour polylines to local UTM and rasterise them
into an elevation grid via scipy interpolation.

Pipeline
--------
1. Detect the best UTM zone from the dataset's centroid (pyproj).
2. Reproject all (lon, lat) points to (easting, northing) metres.
3. Auto-scale ``resolution_m`` if the resulting grid would exceed
   ``MAX_GRID_CELLS`` (prevents OOM on constrained deploy boxes).
4. Rasterise contour line points onto the grid (each point is a sample).
5. Fill the interior with ``scipy.interpolate.griddata`` (linear).
6. Any remaining NaN cells (outside the convex hull of sample points) are
   filled with a nearest-neighbour pass.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from pyproj import Transformer
from scipy.interpolate import griddata

from app.parser.kml_parser import ContourDataset

# ---------------------------------------------------------------------------
# Tuneable constants
# ---------------------------------------------------------------------------

# Maximum grid cells before auto-coarsening kicks in.
# At 512 MB RAM, a float32 array of ~4 M cells ≈ 16 MB — very manageable.
# D8 accumulation uses an int32 array of the same size — another 16 MB.
# Leave headroom for scipy work arrays and Python overhead → 2 M cells ceiling.
MAX_GRID_CELLS: int = 2_000_000


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------


@dataclass
class DEMResult:
    elevation_grid: np.ndarray
    """2-D float32 array [rows, cols], elevation in metres, NaN where unknown."""

    transform: tuple[float, float, float, float]
    """(origin_east, origin_north, resolution_m, resolution_m) — affine transform.
    Cell (row, col) centre = (origin_east + col*res, origin_north + row*res).
    Note: row 0 is the SOUTH edge (northing increases with row index)."""

    crs_epsg: int
    """EPSG code of the projected CRS (UTM zone)."""

    actual_resolution_m: float
    """The resolution actually used (may differ from requested if auto-adjusted)."""

    auto_adjusted: bool
    """True if the resolution was automatically coarsened to stay within RAM limits."""

    transformer_to_lonlat: Transformer
    """pyproj Transformer: projected CRS → WGS84 lon/lat."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _utm_epsg_for_lonlat(lon: float, lat: float) -> int:
    """Return the EPSG code of the UTM zone best covering (lon, lat)."""
    zone = int((lon + 180) / 6) + 1
    if lat >= 0:
        return 32600 + zone  # WGS84 UTM North
    else:
        return 32700 + zone  # WGS84 UTM South


def _collect_samples(
    dataset: ContourDataset,
    transformer: Transformer,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Reproject all contour points and return (east, north, elev) arrays."""
    east_list: list[float] = []
    north_list: list[float] = []
    elev_list: list[float] = []
    for polyline in dataset.polylines:
        elev = polyline.elevation
        lons = [c[0] for c in polyline.coords]
        lats = [c[1] for c in polyline.coords]
        # pyproj Transformer: always_xy=True means (lon, lat) → (east, north)
        e_arr, n_arr = transformer.transform(lons, lats)
        for e, n in zip(e_arr, n_arr):
            east_list.append(e)
            north_list.append(n)
            elev_list.append(elev)
    return (
        np.array(east_list, dtype=np.float64),
        np.array(north_list, dtype=np.float64),
        np.array(elev_list, dtype=np.float32),
    )


def _make_grid(
    east: np.ndarray,
    north: np.ndarray,
    resolution_m: float,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Build 1-D arrays of grid cell centres (easting, northing)."""
    e_min, e_max = east.min(), east.max()
    n_min, n_max = north.min(), north.max()
    # Add half-cell margin so boundary contours fall inside the grid
    margin = resolution_m * 0.5
    e_min -= margin
    e_max += margin
    n_min -= margin
    n_max += margin
    e_centres = np.arange(e_min, e_max + resolution_m * 0.5, resolution_m)
    n_centres = np.arange(n_min, n_max + resolution_m * 0.5, resolution_m)
    return e_centres, n_centres, e_min, n_min


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_dem(
    dataset: ContourDataset,
    resolution_m: float = 10.0,
    max_grid_cells: int = MAX_GRID_CELLS,
) -> DEMResult:
    """Build a DEM from a ContourDataset.

    Parameters
    ----------
    dataset:
        Parsed contour map.
    resolution_m:
        Requested grid resolution in metres.
    max_grid_cells:
        Upper bound on total grid cells before auto-coarsening.
    """
    # --- pick UTM CRS from dataset centroid ---
    all_lons = [c[0] for pl in dataset.polylines for c in pl.coords]
    all_lats = [c[1] for pl in dataset.polylines for c in pl.coords]
    centroid_lon = float(np.mean(all_lons))
    centroid_lat = float(np.mean(all_lats))
    epsg = _utm_epsg_for_lonlat(centroid_lon, centroid_lat)

    transformer_fwd = Transformer.from_crs(
        "EPSG:4326", f"EPSG:{epsg}", always_xy=True
    )
    transformer_inv = Transformer.from_crs(
        f"EPSG:{epsg}", "EPSG:4326", always_xy=True
    )

    # --- collect reprojected samples ---
    east, north, elev = _collect_samples(dataset, transformer_fwd)

    # --- auto-coarsening guard rail ---
    width_m = east.max() - east.min()
    height_m = north.max() - north.min()
    auto_adjusted = False
    actual_resolution_m = resolution_m

    needed_cells = math.ceil(width_m / resolution_m) * math.ceil(height_m / resolution_m)
    if needed_cells > max_grid_cells:
        # Compute the minimum resolution that keeps us under the ceiling
        min_res = math.sqrt((width_m * height_m) / max_grid_cells)
        # Round up to a "nice" value (nearest 0.5 m step)
        actual_resolution_m = math.ceil(min_res * 2) / 2
        auto_adjusted = True

    # --- build grid ---
    e_centres, n_centres, e_origin, n_origin = _make_grid(east, north, actual_resolution_m)
    cols = len(e_centres)
    rows = len(n_centres)

    # Grid of query points (easting, northing) for each cell centre
    ee, nn = np.meshgrid(e_centres, n_centres)  # shape [rows, cols]
    query_pts = np.column_stack([ee.ravel(), nn.ravel()])
    sample_pts = np.column_stack([east, north])

    # --- interpolate (linear inside convex hull, then nearest for NaN cells) ---
    grid_linear = griddata(sample_pts, elev, query_pts, method="linear")
    nan_mask = np.isnan(grid_linear)
    if nan_mask.any():
        grid_nearest = griddata(sample_pts, elev, query_pts[nan_mask], method="nearest")
        grid_linear[nan_mask] = grid_nearest

    elevation_grid = grid_linear.reshape(rows, cols).astype(np.float32)

    return DEMResult(
        elevation_grid=elevation_grid,
        transform=(e_origin, n_origin, actual_resolution_m, actual_resolution_m),
        crs_epsg=epsg,
        actual_resolution_m=actual_resolution_m,
        auto_adjusted=auto_adjusted,
        transformer_to_lonlat=transformer_inv,
    )
