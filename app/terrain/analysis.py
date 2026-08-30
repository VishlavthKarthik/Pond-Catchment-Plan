"""Terrain analysis: priority-flood depression fill, D8 flow direction,
and D8 flow accumulation — all pure NumPy, no GDAL/richdem.

This module is intentionally free of any I/O, projection, or API concerns so
that it is independently unit-testable on small synthetic grids.

D8 Flow Direction Encoding (standard)
--------------------------------------
Each cell's flow direction is encoded as the index (0–7) of one of the eight
neighbours it drains into — the neighbour with the steepest downhill gradient.

    5  6  7
    4  .  0
    3  2  1

So index 0 = East (+col), 1 = SE, 2 = S (+row), 3 = SW,
         4 = W  (-col), 5 = NW, 6 = N (-row), 7 = NE.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

import numpy as np


# ---------------------------------------------------------------------------
# D8 neighbour offset table
# ---------------------------------------------------------------------------

# (dr, dc) for each of the 8 directions (index 0–7)
_D8_DR = np.array([0, 1, 1, 1, 0, -1, -1, -1], dtype=np.int32)
_D8_DC = np.array([1, 1, 0, -1, -1, -1, 0, 1], dtype=np.int32)
# Euclidean weight: cardinal = 1, diagonal = sqrt(2)
_D8_DIST = np.array(
    [1.0, 1.4142, 1.0, 1.4142, 1.0, 1.4142, 1.0, 1.4142], dtype=np.float64
)

# Reverse direction: direction that drains *into* a cell
_D8_REVERSE = np.array([4, 5, 6, 7, 0, 1, 2, 3], dtype=np.int32)


# ---------------------------------------------------------------------------
# Priority-flood depression fill (Barnes et al. 2014)
# ---------------------------------------------------------------------------


def priority_flood_fill(dem: np.ndarray) -> np.ndarray:
    """Return a depression-free DEM using the priority-flood algorithm.

    Cells that form closed depressions (sinks) are raised to the lowest
    neighbouring spill point, eliminating flat areas that would cause
    undefined flow directions.

    Parameters
    ----------
    dem:
        2-D float32/float64 elevation array.  May contain NaN.

    Returns
    -------
    filled:
        2-D float64 array of the same shape, with depressions filled.
        NaN cells in the input remain NaN in the output.
    """
    rows, cols = dem.shape
    filled = dem.astype(np.float64, copy=True)
    visited = np.zeros((rows, cols), dtype=bool)

    # Priority queue: (elevation, row, col)
    heap: list[tuple[float, int, int]] = []

    # Seed the heap with all border cells
    for r in range(rows):
        for c in [0, cols - 1]:
            if not np.isnan(filled[r, c]):
                heapq.heappush(heap, (filled[r, c], r, c))
                visited[r, c] = True
    for c in range(1, cols - 1):
        for r in [0, rows - 1]:
            if not np.isnan(filled[r, c]) and not visited[r, c]:
                heapq.heappush(heap, (filled[r, c], r, c))
                visited[r, c] = True

    while heap:
        elev, r, c = heapq.heappop(heap)
        for d in range(8):
            nr, nc = r + _D8_DR[d], c + _D8_DC[d]
            if 0 <= nr < rows and 0 <= nc < cols and not visited[nr, nc]:
                if np.isnan(filled[nr, nc]):
                    visited[nr, nc] = True
                    continue
                visited[nr, nc] = True
                # Fill neighbour if it is lower than current cell
                if filled[nr, nc] < elev:
                    filled[nr, nc] = elev
                heapq.heappush(heap, (filled[nr, nc], nr, nc))

    return filled


# ---------------------------------------------------------------------------
# D8 flow direction
# ---------------------------------------------------------------------------


def d8_flow_direction(filled: np.ndarray) -> np.ndarray:
    """Compute D8 flow direction from a depression-free DEM.

    Parameters
    ----------
    filled:
        2-D depression-free elevation array (float64).

    Returns
    -------
    flowdir:
        2-D int8 array, values 0–7 indicating the D8 direction.
        Border cells and NaN-adjacent cells get direction 0 by default
        (they will have zero flow accumulation anyway).
    """
    rows, cols = filled.shape
    flowdir = np.zeros((rows, cols), dtype=np.int8)

    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            if np.isnan(filled[r, c]):
                continue
            elev_center = filled[r, c]
            best_dir = -1
            best_drop = -np.inf
            for d in range(8):
                nr, nc = r + _D8_DR[d], c + _D8_DC[d]
                if np.isnan(filled[nr, nc]):
                    continue
                drop = (elev_center - filled[nr, nc]) / _D8_DIST[d]
                if drop > best_drop:
                    best_drop = drop
                    best_dir = d
            if best_dir >= 0:
                flowdir[r, c] = best_dir

    return flowdir


def d8_flow_direction_vectorised(filled: np.ndarray) -> np.ndarray:
    """Faster vectorised D8 flow direction (avoids Python loops).

    Uses np.pad and stacked neighbour arrays — about 8× faster than the
    pure-Python loop version, at the cost of 8× the memory of the DEM.
    Only called when the grid is large enough to warrant it (> 50k cells).
    """
    rows, cols = filled.shape
    padded = np.pad(filled, 1, mode="edge")

    # Stack neighbours: shape [8, rows, cols]
    neighbours = np.stack(
        [
            padded[1 : rows + 1, 2 : cols + 2],  # E  (d=0)
            padded[2 : rows + 2, 2 : cols + 2],  # SE (d=1)
            padded[2 : rows + 2, 1 : cols + 1],  # S  (d=2)
            padded[2 : rows + 2, 0:cols],         # SW (d=3)
            padded[1 : rows + 1, 0:cols],         # W  (d=4)
            padded[0:rows, 0:cols],               # NW (d=5)
            padded[0:rows, 1 : cols + 1],         # N  (d=6)
            padded[0:rows, 2 : cols + 2],         # NE (d=7)
        ]
    )  # [8, rows, cols]

    center = filled[np.newaxis, :, :]  # [1, rows, cols]
    drops = (center - neighbours) / _D8_DIST[:, np.newaxis, np.newaxis]

    # Cells flowing to NaN neighbours shouldn't win → mask them out
    nan_nb = np.isnan(neighbours)
    drops = np.where(nan_nb, -np.inf, drops)

    flowdir = drops.argmax(axis=0).astype(np.int8)

    # Flat/sink cells (max drop ≤ 0) get direction 0 — they won't accumulate
    max_drop = drops.max(axis=0)
    flowdir = np.where(max_drop <= 0, 0, flowdir)

    return flowdir


# ---------------------------------------------------------------------------
# D8 flow accumulation
# ---------------------------------------------------------------------------


def d8_flow_accumulation(flowdir: np.ndarray) -> np.ndarray:
    """Compute the D8 flow accumulation grid.

    Each cell's accumulation value = number of upstream cells that drain into
    it (including itself, i.e. minimum value is 1).

    Uses iterative topological processing: cells are processed in order of
    how many upstream cells contribute (those with no upstream go first).

    Parameters
    ----------
    flowdir:
        2-D int8 D8 flow direction array.

    Returns
    -------
    accum:
        2-D int32 flow accumulation array.
    """
    rows, cols = flowdir.shape
    accum = np.ones((rows, cols), dtype=np.int32)

    # Build in-degree (number of upstream neighbours draining into each cell)
    in_degree = np.zeros((rows, cols), dtype=np.int32)
    for r in range(rows):
        for c in range(cols):
            d = int(flowdir[r, c])
            nr, nc = r + _D8_DR[d], c + _D8_DC[d]
            if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) != (r, c):
                in_degree[nr, nc] += 1

    # Process in topological order (BFS from cells with in_degree == 0)
    from collections import deque

    queue: deque[tuple[int, int]] = deque()
    for r in range(rows):
        for c in range(cols):
            if in_degree[r, c] == 0:
                queue.append((r, c))

    while queue:
        r, c = queue.popleft()
        d = int(flowdir[r, c])
        nr, nc = r + _D8_DR[d], c + _D8_DC[d]
        if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) != (r, c):
            accum[nr, nc] += accum[r, c]
            in_degree[nr, nc] -= 1
            if in_degree[nr, nc] == 0:
                queue.append((nr, nc))

    return accum


def d8_flow_accumulation_vectorised(flowdir: np.ndarray) -> np.ndarray:
    """Vectorised flow accumulation using flat indices and numpy counting.

    This is faster than the pure Python BFS for large grids.
    """
    rows, cols = flowdir.shape
    size = rows * cols
    accum = np.ones(size, dtype=np.int32)

    # Build flat receiver array: each cell drains to receiver[i]
    flat_idx = np.arange(size, dtype=np.int32)
    r_all = flat_idx // cols
    c_all = flat_idx % cols
    dr_all = _D8_DR[flowdir.ravel()]
    dc_all = _D8_DC[flowdir.ravel()]
    nr_all = r_all + dr_all
    nc_all = c_all + dc_all

    # Clamp out-of-bound receivers to self (border cells drain to themselves)
    valid = (nr_all >= 0) & (nr_all < rows) & (nc_all >= 0) & (nc_all < cols)
    recv = np.where(valid, nr_all * cols + nc_all, flat_idx)
    # Cells already pointing to themselves (border/sink)
    recv = np.where(recv == flat_idx, flat_idx, recv)

    # In-degree
    in_deg = np.bincount(recv, minlength=size).astype(np.int32)
    # Cells drain to themselves don't count as incoming
    for i in range(size):
        if recv[i] == i:
            in_deg[i] = 0  # treat as source

    # BFS using numpy queue simulation
    queue = list(np.where(in_deg == 0)[0])
    while queue:
        batch = np.array(queue, dtype=np.int32)
        queue = []
        targets = recv[batch]
        # only propagate to cells that aren't self-draining
        mask = targets != batch
        batch_valid = batch[mask]
        targets_valid = targets[mask]
        if len(batch_valid) == 0:
            continue
        # Accumulate: for each unique target, sum contributions
        np.add.at(accum, targets_valid, accum[batch_valid])
        # Decrement in_degree of targets
        np.subtract.at(in_deg, targets_valid, 1)
        # Add newly zero-degree targets to queue
        newly_zero = targets_valid[in_deg[targets_valid] == 0]
        # Deduplicate
        newly_zero = np.unique(newly_zero)
        queue.extend(newly_zero.tolist())

    return accum.reshape(rows, cols)


# ---------------------------------------------------------------------------
# Slope calculation
# ---------------------------------------------------------------------------


def compute_slope_percent(filled: np.ndarray, resolution_m: float) -> np.ndarray:
    """Return a slope grid in percent rise.

    Uses central differences (interior cells) and forward/backward differences
    at borders.  Result is percent: rise/run × 100.
    """
    dy, dx = np.gradient(filled, resolution_m, resolution_m)
    slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
    return np.tan(slope_rad) * 100.0


# ---------------------------------------------------------------------------
# TerrainAnalysis dataclass
# ---------------------------------------------------------------------------


@dataclass
class TerrainAnalysis:
    """Container that runs and stores all terrain analysis products."""

    raw_dem: np.ndarray

    def __post_init__(self) -> None:
        rows, cols = self.raw_dem.shape
        n_cells = rows * cols
        use_vectorised = n_cells > 50_000

        self.filled_dem: np.ndarray = priority_flood_fill(self.raw_dem)

        if use_vectorised:
            self.flow_dir: np.ndarray = d8_flow_direction_vectorised(self.filled_dem)
            self.flow_accum: np.ndarray = d8_flow_accumulation_vectorised(self.flow_dir)
        else:
            self.flow_dir = d8_flow_direction(self.filled_dem)
            self.flow_accum = d8_flow_accumulation(self.flow_dir)
