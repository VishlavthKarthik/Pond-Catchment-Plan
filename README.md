# HydroPond AI: Precision Village Pond & Catchment Planning System

An automated Web GIS and hydrological decision-support platform designed for village pond planning, land boundary selection, and precision rainwater harvesting.

🌐 **Live Working Frontend URL:** [http://10.1.75.51:3317/](http://10.1.75.51:3317/)  
📚 **Interactive Swagger API Documentation:** [http://10.1.75.51:3317/docs](http://10.1.75.51:3317/docs)  
📦 **GitHub Repository:** [https://github.com/VishlavthKarthik/Pond-Catchment-Plan](https://github.com/VishlavthKarthik/Pond-Catchment-Plan)

---

## 🌟 Key Capabilities

1. **Interactive Web GIS Map Interface**:
   - High-resolution Esri World Imagery (satellite) and OpenStreetMap basemaps.
   - Built-in drawing tools allowing planners to sketch and select custom farmland/village land parcels.
   - Live visual compositing: 1-meter elevation contours, land boundary, delineated watershed catchment polygon, and animated pulsing pond outlet pin.

2. **Hydrological Flow Routing & Catchment Delineation**:
   - Dynamic metric Universal Transverse Mercator (UTM) projection via `pyproj`.
   - Continuous 10-meter surface rasterization with memory-bounded auto-scaling.
   - Wang & Liu **Priority-Flood depression filling** to eliminate artificial terrain sinks.
   - Deterministic 8-neighbor (**D8**) steepest descent flow direction and accumulation modeling.
   - Upstream graph traversal tracing contributing catchments.

3. **Rainwater Yield & Expected Volume Estimation**:
   - Integrates historical meteorological precipitation records from Open-Meteo.
   - Dynamic slope-adjusted Runoff Coefficient ($C$) based on Central Water Commission (CWC) guidelines.
   - Quantifies total expected harvestable rainwater volume in **Cubic Meters ($\text{m}^3$)** and **Million Litres ($\text{ML}$)**.
   - Sizing recommendations for trapezoidal village storage ponds ($L \times W \times D$) and estimated rural household water security days.

4. **Multi-Source Data Ingestion**:
   - Ingests standard `.kml` and `.kmz` contour exports without hardcoded coordinates.
   - Dynamic GeoJSON export for integration into ArcGIS / QGIS workflows.

---

## 🏗️ Architecture Pipeline

```
[Web GIS Client (Leaflet.js + Geoman)]
       |   ^ (Draw parcel / Upload KML)
       v   | (Catchment Polygon + Hydrology HUD)
[FastAPI Asynchronous Gateway (:3000 -> :3317)]
       |
       +---> [1] KML/KMZ Parser (lxml namespace-agnostic)
       |
       +---> [2] UTM Projection & DEM Rasterizer (pyproj + scipy.interpolate)
       |
       +---> [3] Priority-Flood Depression Filling (Wang-Liu algorithm)
       |
       +---> [4] D8 Flow Routing & Accumulation DAG
       |
       +---> [5] Upstream Catchment BFS Traversal (Shapely unary union)
       |
       +---> [6] Hydrology Engine (Open-Meteo Climate + CWC Rational Runoff)
       |
       v
[Structured Output: GeoJSON Overlays, 14.17 ML Harvest Volume, Pond Sizing]
```

---

## 🚀 Quick Start

### Local Setup

```bash
# Clone the repository
git clone https://github.com/VishlavthKarthik/Pond-Catchment-Plan.git
cd Pond-Catchment-Plan

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run server locally
uvicorn app.main:app --host 0.0.0.0 --port 3000 --reload
```
Open [http://localhost:3000](http://localhost:3000) in your web browser.

---

## 📡 API Endpoints

### 1. `GET /`
Serves the full-featured single-page Web GIS application.

### 2. `POST /api/analyze-area`
Analyzes a user-drawn land boundary polygon on the map.

**Request Body (JSON):**
```json
{
  "coordinates": [
    [21.255, 81.307],
    [21.260, 81.307],
    [21.260, 81.312],
    [21.255, 81.312]
  ],
  "resolution_m": 10.0,
  "min_catchment_area_m2": 2000.0,
  "soil_type": "medium",
  "target_depth_m": 3.0
}
```

**Response (200 OK):**
```json
{
  "selected_area_hectares": 28.71,
  "pond_site": {
    "lat": 21.257206,
    "lon": 81.309778,
    "elevation_m": 288.7,
    "flow_accumulation_cells": 537
  },
  "catchment": {
    "area_m2": 54100.0,
    "area_hectares": 5.41,
    "mean_slope_pct": 4.26,
    "boundary_geojson": { "type": "Polygon", "coordinates": [...] }
  },
  "hydrology": {
    "annual_rainfall_mm": 1150.0,
    "monsoon_rainfall_mm": 977.5,
    "runoff_coefficient": 0.32,
    "expected_water_volume_m3": 14172.6,
    "expected_water_volume_megaliters": 14.17,
    "recommended_dimensions": "77.6m × 51.7m × 3.0m (L × W × D)",
    "recommended_pond_storage_capacity_m3": 8503.6,
    "estimated_household_days": 36075
  },
  "processing_time_ms": 185
}
```

### 3. `POST /analyzeContour`
Ingests an uploaded KML/KMZ contour map.

```bash
curl -X POST \
  -F "contour_map=@contours_1m.kml" \
  http://10.1.75.51:3317/analyzeContour
```

---

## 🧪 Automated Testing

The project includes 45 unit and integration tests with 100% pass rate:

```bash
pytest tests/ -v
```

---

## 📁 Repository Structure

```
├── app/
│   ├── api/             # Pydantic schemas (AnalyzeResponse, HydrologySchema)
│   ├── dem/             # UTM projection and SciPy grid interpolation
│   ├── hydrology/       # Runoff volume, Open-Meteo, pond sizing
│   ├── parser/          # lxml KML/KMZ parser
│   ├── pond/            # Heuristic pond selector & catchment BFS
│   ├── static/          # Web GIS frontend (HTML, CSS, JS)
│   ├── terrain/         # Priority-Flood sink filling & D8 flow accumulation
│   └── main.py          # FastAPI application routes
├── deploy/              # Production startup scripts (start.sh, stop.sh, status.sh)
├── tests/               # 45 automated pytest cases
├── contours_1m.kml      # 1-meter contour benchmark dataset
├── DEMO_VIDEO_SCRIPT.md # Minute-by-minute 5-minute video demo script
├── report_template/     # Complete Overleaf ACM report package
└── README.md
```

---

## 📄 Submission Materials
- **Technical Report:** Ready-to-upload LaTeX package in `report_template/` and `Final_Report_Overleaf_Package.zip`.
- **Demo Video Script:** Formatted in [`DEMO_VIDEO_SCRIPT.md`](file:///home/karthik/Desktop/Pond-Catchment-Plan/DEMO_VIDEO_SCRIPT.md).
