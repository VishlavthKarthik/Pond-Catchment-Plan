"""Traffic generation script for HydroPond AI OpenTelemetry demonstration.

Generates realistic user interactions:
- Web GIS dashboard loads
- Contour overlays fetching
- Farmland parcel analyses with different soil profiles and rainfall scenarios
- Full KML file upload and analysis
- Metrics scraping
"""

import time
import requests
from pathlib import Path

BASE_URL = "http://localhost:3000"
KML_PATH = Path(__file__).parent.parent / "contours_1m.kml"

def run_traffic():
    print("=" * 60)
    print(" Generating Observability Traffic for HydroPond AI...")
    print("=" * 60)

    # 1. Health check & Frontend
    print("\n[1] Accessing Web GIS Frontend (GET /)...")
    r = requests.get(f"{BASE_URL}/")
    print(f"    Status: {r.status_code}, Length: {len(r.text)} bytes")

    # 2. Sample Contours (Miss then Hit)
    print("\n[2] Fetching Contour Overlays (GET /api/sample-contours)...")
    for i in range(2):
        t0 = time.time()
        r = requests.get(f"{BASE_URL}/api/sample-contours")
        elapsed = (time.time() - t0) * 1000
        print(f"    Request {i+1}: Status {r.status_code}, Features: {len(r.json().get('features', []))}, Latency: {elapsed:.1f}ms")

    # 3. Analyze Farmland Parcels (POST /api/analyze-area)
    parcels = [
        {
            "name": "Farmland Parcel 1 (Central Loam)",
            "coords": [[21.255, 81.307], [21.260, 81.307], [21.260, 81.312], [21.255, 81.312]],
            "soil": "loamy",
            "depth": 3.0,
            "rainfall": None,
        },
        {
            "name": "Farmland Parcel 2 (North Clay - Monsoon High)",
            "coords": [[21.258, 81.305], [21.263, 81.305], [21.263, 81.310], [21.258, 81.310]],
            "soil": "clayey",
            "depth": 3.5,
            "rainfall": 1350.0,
        },
        {
            "name": "Farmland Parcel 3 (South Sandy Soil)",
            "coords": [[21.252, 81.308], [21.256, 81.308], [21.256, 81.313], [21.252, 81.313]],
            "soil": "sandy",
            "depth": 2.5,
            "rainfall": 1100.0,
        },
    ]

    for p in parcels:
        print(f"\n[3] Analyzing {p['name']} (POST /api/analyze-area)...")
        payload = {
            "coordinates": p["coords"],
            "resolution_m": 10.0,
            "min_catchment_area_m2": 2500.0,
            "soil_type": p["soil"],
            "target_depth_m": p["depth"],
        }
        if p["rainfall"]:
            payload["override_rainfall_mm"] = p["rainfall"]

        t0 = time.time()
        r = requests.post(f"{BASE_URL}/api/analyze-area", json=payload)
        elapsed = (time.time() - t0) * 1000

        if r.status_code == 200:
            data = r.json()
            pond = data["pond_site"]
            hydro = data["hydrology"]
            catchment = data["catchment"]
            print(f"    ✓ Status: 200 OK ({elapsed:.1f}ms)")
            print(f"      Pond Site: ({pond['lat']:.4f}, {pond['lon']:.4f}) @ {pond['elevation_m']}m elev")
            print(f"      Catchment Area: {catchment['area_hectares']} ha ({catchment['watershed_cell_count']} cells)")
            print(f"      Harvestable Water: {hydro['expected_water_volume_megaliters']} Megalitres ({hydro['expected_water_volume_m3']:,} m³)")
            print(f"      Recommended Pond: {hydro['recommended_dimensions']}")
            print(f"      Water Security: {hydro['estimated_household_days']} household-days")
        else:
            print(f"    ✗ Failed ({r.status_code}): {r.text}")

    # 4. Upload KML Contour Map (POST /analyzeContour)
    if KML_PATH.exists():
        print(f"\n[4] Uploading & Analyzing KML File: {KML_PATH.name} (POST /analyzeContour)...")
        t0 = time.time()
        with open(KML_PATH, "rb") as f:
            files = {"contour_map": (KML_PATH.name, f, "application/vnd.google-earth.kml+xml")}
            data = {"resolution_m": "10.0", "min_catchment_area_m2": "10000.0"}
            r = requests.post(f"{BASE_URL}/analyzeContour", files=files, data=data)
        elapsed = (time.time() - t0) * 1000
        if r.status_code == 200:
            res = r.json()
            print(f"    ✓ Status: 200 OK ({elapsed:.1f}ms)")
            print(f"      DEM Grid Shape: {res['grid_shape']}, Contour Lines: {res['total_contour_lines']}")
            print(f"      Pond Elevation: {res['pond_site']['elevation_m']}m, Catchment: {res['catchment']['area_hectares']} ha")
            print(f"      Water Harvest: {res['hydrology']['expected_water_volume_megaliters']} ML")
        else:
            print(f"    ✗ Failed ({r.status_code}): {r.text}")

    # 5. Check Prometheus /metrics endpoint
    print("\n[5] Scraping OpenTelemetry Metrics (GET /metrics)...")
    r = requests.get(f"{BASE_URL}/metrics")
    metrics_text = r.text
    print(f"    ✓ Scraped {len(metrics_text.splitlines())} metric lines")
    
    # Print some key metrics lines
    for line in metrics_text.splitlines():
        if any(k in line for k in ("hydrology_requests_total", "hydrology_water_volume", "dem_grid_cells", "watershed_cells")):
            if not line.startswith("#"):
                print(f"      {line}")

    print("\n" + "=" * 60)
    print(" Traffic generation completed successfully!")
    print(" Observability data is now available in Jaeger and Prometheus.")
    print("=" * 60)

if __name__ == "__main__":
    run_traffic()
