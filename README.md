# Pond Catchment Analysis API

A FastAPI backend that accepts a contour map (KML/KMZ), analyses terrain, identifies a suitable pond location, and returns the corresponding catchment area as structured JSON.

## Architecture

```
Upload (KML/KMZ)
      |
      v
[1] Parser layer        -> ContourDataset (elevation, list of polylines in lon/lat)
      |
      v
[2] Projection layer    -> reproject lon/lat to local UTM meters (pyproj)
      |
      v
[3] DEM builder layer   -> rasterize contours + scipy.interpolate.griddata
      |                     => elevation grid (numpy array), config: resolution_m
      v
[4] Terrain analysis    -> depression fill, D8 flow direction, flow accumulation
      |
      v
[5] Pond site selector  -> heuristic scoring over candidate cells
      |
      v
[6] Catchment delineator -> watershed trace from chosen outlet -> boundary polygon
      |
      v
[7] Response builder    -> JSON (pond site, catchment polygon, area, stats)
```

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs`

## API

### `POST /analyzeContour`

**Form fields:**

| Field | Type | Default | Description |
|---|---|---|---|
| `file` | file | required | `.kml` or `.kmz` contour map |
| `resolution_m` | float | 10.0 | DEM grid resolution in metres |
| `min_catchment_area_m2` | float | 500.0 | Minimum catchment area to consider |

**Response 200:**
```json
{
  "contour_interval_m": 1.0,
  "elevation_range_m": [267.0, 298.0],
  "grid_resolution_m": 10.0,
  "resolution_auto_adjusted": false,
  "pond_site": {
    "lat": 21.2521,
    "lon": 81.2934,
    "elevation_m": 274.0
  },
  "catchment": {
    "area_m2": 184500.2,
    "area_hectares": 18.45,
    "mean_slope_pct": 6.7,
    "boundary_geojson": { "type": "Polygon", "coordinates": [[[...]]] }
  },
  "processing_time_ms": 842
}
```

**Error responses:**
- `400` — invalid/corrupt file or unsupported format
- `422` — no valid pond site found (e.g. perfectly flat terrain)
- `500` — unexpected processing failure

### `GET /health`

```json
{ "status": "ok" }
```

## Deployment (Constrained Box: 512 MB RAM / 1 vCPU / 1.5 GB disk)

```bash
# Set up swap (recommended safety net)
sudo fallocate -l 512M /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Install and start
git clone <repo> pond-api && cd pond-api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
sudo cp deploy/pond-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pond-api
```

## Running Tests

```bash
pytest tests/ -v
```

## Resource Constraints & Design Decisions

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for full rationale.

Key choices:
- `resolution_m` is a required config knob (default 10 m on constrained deploy, 2–5 m on laptop)
- Auto-coarsening guard rail prevents OOM on large phase-2 maps
- No GDAL/rasterio/richdem/pysheds — pure numpy/scipy/shapely instead
- Single uvicorn worker (1 vCPU), systemd + optional Nginx
