/**
 * HydroPond AI - Frontend Web GIS Logic
 */

let map;
let baseLayers = {};
let currentBasemap = "satellite";
let selectedLandPolygon = null;
let catchmentLayer = null;
let pondMarker = null;
let landLayer = null;
let contourLayer = null;
let currentResults = null;

// Default sample village parcel coordinates (WGS84 lat, lon)
const SAMPLE_VILLAGE_BOUNDARY = [
  [21.2545, 81.3055],
  [21.2610, 81.3055],
  [21.2610, 81.3135],
  [21.2545, 81.3135]
];

document.addEventListener("DOMContentLoaded", () => {
  initMap();
  setupDrawing();
  setupUIEvents();
  loadSampleContours();
});

/* -------------------------------------------------------------------------- */
/* Map Initialization                                                         */
/* -------------------------------------------------------------------------- */

function initMap() {
  map = L.map("map", {
    center: [21.2572, 81.3098],
    zoom: 16,
    zoomControl: true,
  });

  // Basemaps
  baseLayers.satellite = L.layerGroup([
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
      attribution: "Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community",
      maxZoom: 19
    }),
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", {
      maxZoom: 19
    })
  ]).addTo(map);

  baseLayers.osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 19
  });

  // Mouse coordinate HUD
  map.on("mousemove", (e) => {
    document.getElementById("hud-coords").textContent = 
      `${e.latlng.lat.toFixed(4)}° N, ${e.latlng.lng.toFixed(4)}° E`;
  });
}

/* -------------------------------------------------------------------------- */
/* Geoman Drawing Setup for Land Selection                                    */
/* -------------------------------------------------------------------------- */

function setupDrawing() {
  map.pm.setGlobalOptions({
    snappable: true,
    snapDistance: 20,
    allowSelfIntersection: false,
    pathOptions: {
      color: "#f59e0b",
      fillColor: "#f59e0b",
      fillOpacity: 0.25,
      weight: 2,
      dashArray: "5, 5"
    }
  });

  // Listen for newly drawn polygon / rectangle
  map.on("pm:create", (e) => {
    if (landLayer) {
      map.removeLayer(landLayer);
    }
    landLayer = e.layer;
    processDrawnPolygon(landLayer);
  });
}

function processDrawnPolygon(layer) {
  const latLngs = layer.getLatLngs()[0];
  selectedLandPolygon = latLngs.map(pt => [pt.lat, pt.lng]);
  
  // Calculate approximate area
  const areaM2 = computePolygonArea(selectedLandPolygon);
  const areaHa = (areaM2 / 10000).toFixed(2);
  
  document.getElementById("selected-area-text").textContent = 
    `Land Selected: ${areaHa} ha (${Math.round(areaM2).toLocaleString()} m²)`;
  document.getElementById("selected-area-summary").style.display = "block";
}

function computePolygonArea(coords) {
  // Rough planar area approximation in meters
  let area = 0;
  const n = coords.length;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    const x1 = coords[i][1] * 111320 * Math.cos(coords[i][0] * Math.PI / 180);
    const y1 = coords[i][0] * 110540;
    const x2 = coords[j][1] * 111320 * Math.cos(coords[j][0] * Math.PI / 180);
    const y2 = coords[j][0] * 110540;
    area += x1 * y2 - x2 * y1;
  }
  return Math.abs(area / 2);
}

/* -------------------------------------------------------------------------- */
/* UI Events & Actions                                                        */
/* -------------------------------------------------------------------------- */

function setupUIEvents() {
  // Draw Area Button
  document.getElementById("btn-draw-poly").addEventListener("click", () => {
    map.pm.enableDraw("Polygon", {
      snappable: true,
      cursorMarker: true
    });
  });

  // Load Sample Land Button
  document.getElementById("btn-load-sample").addEventListener("click", () => {
    clearMapLayers();
    landLayer = L.polygon(SAMPLE_VILLAGE_BOUNDARY, {
      color: "#f59e0b",
      fillColor: "#f59e0b",
      fillOpacity: 0.25,
      weight: 2,
      dashArray: "6, 6"
    }).addTo(map);

    selectedLandPolygon = SAMPLE_VILLAGE_BOUNDARY;
    const areaM2 = computePolygonArea(selectedLandPolygon);
    const areaHa = (areaM2 / 10000).toFixed(2);

    document.getElementById("selected-area-text").textContent = 
      `Land Selected: ${areaHa} ha (Sample Village Boundary)`;
    document.getElementById("selected-area-summary").style.display = "block";

    map.fitBounds(landLayer.getBounds(), { padding: [50, 50] });
  });

  // Clear Map
  document.getElementById("btn-clear-selection").addEventListener("click", () => {
    clearMapLayers();
    selectedLandPolygon = null;
    document.getElementById("selected-area-summary").style.display = "none";
    document.getElementById("results-container").style.display = "none";
  });

  // Run Analysis Button
  document.getElementById("btn-run-analysis").addEventListener("click", runAnalysis);

  // Basemap Toggle
  document.getElementById("btn-toggle-basemap").addEventListener("click", () => {
    if (currentBasemap === "satellite") {
      map.removeLayer(baseLayers.satellite);
      baseLayers.osm.addTo(map);
      currentBasemap = "osm";
    } else {
      map.removeLayer(baseLayers.osm);
      baseLayers.satellite.addTo(map);
      currentBasemap = "satellite";
    }
  });

  // Zoom to Fit
  document.getElementById("btn-zoom-fit").addEventListener("click", () => {
    const group = new L.featureGroup([
      catchmentLayer,
      landLayer,
      pondMarker
    ].filter(Boolean));
    if (group.getLayers().length > 0) {
      map.fitBounds(group.getBounds(), { padding: [40, 40] });
    }
  });

  // Layer Visibility Checkboxes
  document.getElementById("layer-pond").addEventListener("change", (e) => {
    if (pondMarker) e.target.checked ? map.addLayer(pondMarker) : map.removeLayer(pondMarker);
  });
  document.getElementById("layer-catchment").addEventListener("change", (e) => {
    if (catchmentLayer) e.target.checked ? map.addLayer(catchmentLayer) : map.removeLayer(catchmentLayer);
  });
  document.getElementById("layer-land").addEventListener("change", (e) => {
    if (landLayer) e.target.checked ? map.addLayer(landLayer) : map.removeLayer(landLayer);
  });
  document.getElementById("layer-contours").addEventListener("change", (e) => {
    if (contourLayer) e.target.checked ? map.addLayer(contourLayer) : map.removeLayer(contourLayer);
  });

  // Export GeoJSON
  document.getElementById("btn-export-geojson").addEventListener("click", exportGeoJSON);

  // Print Report
  document.getElementById("btn-print-report").addEventListener("click", () => window.print());

  // Toggle Raw JSON
  document.getElementById("btn-toggle-json").addEventListener("click", () => {
    const el = document.getElementById("json-viewer-container");
    el.style.display = el.style.display === "none" ? "block" : "none";
  });

  // Upload Modal Events
  setupUploadModal();
}

function clearMapLayers() {
  if (landLayer) { map.removeLayer(landLayer); landLayer = null; }
  if (catchmentLayer) { map.removeLayer(catchmentLayer); catchmentLayer = null; }
  if (pondMarker) { map.removeLayer(pondMarker); pondMarker = null; }
}

/* -------------------------------------------------------------------------- */
/* Load Sample Contour Lines                                                  */
/* -------------------------------------------------------------------------- */

async function loadSampleContours() {
  try {
    const res = await fetch("/api/sample-contours");
    if (!res.ok) return;
    const data = await res.json();
    
    if (data.features && data.features.length > 0) {
      contourLayer = L.geoJSON(data, {
        style: (feature) => {
          const elev = feature.properties.elevation || 280;
          return {
            color: elev % 5 === 0 ? "#38bdf8" : "#94a3b8",
            weight: elev % 5 === 0 ? 1.5 : 0.8,
            opacity: elev % 5 === 0 ? 0.6 : 0.35
          };
        },
        onEachFeature: (feature, layer) => {
          layer.bindTooltip(`Elevation: ${feature.properties.elevation} m`, { sticky: true });
        }
      }).addTo(map);
    }
  } catch (err) {
    console.log("Contour preview preview skipped:", err);
  }
}

/* -------------------------------------------------------------------------- */
/* Analysis Execution                                                         */
/* -------------------------------------------------------------------------- */

async function runAnalysis() {
  const btn = document.getElementById("btn-run-analysis");
  const origHtml = btn.innerHTML;
  btn.innerHTML = `<div class="spinner"></div> <span>Analyzing Hydrology & Catchment...</span>`;
  btn.disabled = true;

  try {
    // If user hasn't drawn an area, default to the sample village area
    const coords = selectedLandPolygon || SAMPLE_VILLAGE_BOUNDARY;
    if (!selectedLandPolygon) {
      document.getElementById("btn-load-sample").click();
    }

    const payload = {
      coordinates: coords,
      resolution_m: 10.0,
      min_catchment_area_m2: 2000.0,
      override_rainfall_mm: parseFloat(document.getElementById("rainfall-override").value) || null,
      soil_type: document.getElementById("soil-select").value,
      target_depth_m: parseFloat(document.getElementById("target-depth").value) || 3.0
    };

    const res = await fetch("/api/analyze-area", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Analysis failed");
    }

    const data = await res.json();
    currentResults = data;
    renderResults(data);

  } catch (err) {
    alert("Error running analysis: " + err.message);
  } finally {
    btn.innerHTML = origHtml;
    btn.disabled = false;
  }
}

/* -------------------------------------------------------------------------- */
/* Render Results on Map & Dashboard                                          */
/* -------------------------------------------------------------------------- */

function renderResults(data) {
  // 1. Remove old catchment and pond marker
  if (catchmentLayer) map.removeLayer(catchmentLayer);
  if (pondMarker) map.removeLayer(pondMarker);

  // 2. Render Catchment Area GeoJSON Polygon
  catchmentLayer = L.geoJSON(data.catchment.boundary_geojson, {
    style: {
      color: "#06b6d4",
      fillColor: "#0284c7",
      fillOpacity: 0.35,
      weight: 2.5,
      dashArray: "4, 4"
    }
  }).addTo(map);

  // 3. Render Custom Pulsing Marker for Recommended Pond Location
  const customIcon = L.divIcon({
    className: "custom-pond-icon",
    html: `
      <div class="pulse-marker-container">
        <div class="pulse-ring"></div>
        <div class="pulse-pin">
          <i class="fa-solid fa-water"></i>
        </div>
      </div>
    `,
    iconSize: [36, 36],
    iconAnchor: [18, 18],
    popupAnchor: [0, -18]
  });

  const pond = data.pond_site;
  const hydro = data.hydrology;

  pondMarker = L.marker([pond.lat, pond.lon], { icon: customIcon }).addTo(map);
  
  const popupHtml = `
    <div style="font-family: sans-serif; min-width: 220px; line-height: 1.5;">
      <h4 style="margin: 0 0 6px 0; color: #0284c7; display: flex; align-items: center; gap: 6px;">
        <i class="fa-solid fa-droplet"></i> Recommended Pond Site
      </h4>
      <div style="font-size: 12px; margin-bottom: 4px;"><strong>Coordinates:</strong> ${pond.lat.toFixed(5)}°, ${pond.lon.toFixed(5)}°</div>
      <div style="font-size: 12px; margin-bottom: 4px;"><strong>Elevation:</strong> ${pond.elevation_m} m</div>
      <div style="font-size: 12px; margin-bottom: 4px;"><strong>Natural Inflow:</strong> ${pond.flow_accumulation_cells} upstream cells</div>
      <div style="margin-top: 8px; padding-top: 6px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #059669; font-weight: 600;">
        💧 Expected Volume: ${hydro.expected_water_volume_megaliters} ML (${hydro.expected_water_volume_m3.toLocaleString()} m³)
      </div>
    </div>
  `;
  pondMarker.bindPopup(popupHtml).openPopup();

  // 4. Update Dashboard Stats Cards
  document.getElementById("res-volume-ml").textContent = hydro.expected_water_volume_megaliters.toFixed(2);
  document.getElementById("res-volume-m3").textContent = Math.round(hydro.expected_water_volume_m3).toLocaleString();
  document.getElementById("res-household-days").textContent = 
    `Provides dry-season water for ~${Math.round(hydro.estimated_household_days / 180)} families for 180+ days`;

  document.getElementById("res-pond-lat").textContent = `${pond.lat.toFixed(6)}°`;
  document.getElementById("res-pond-lon").textContent = `${pond.lon.toFixed(6)}°`;
  document.getElementById("res-pond-elev").textContent = `${pond.elevation_m} m`;
  document.getElementById("res-pond-accum").textContent = `${pond.flow_accumulation_cells} cells`;

  document.getElementById("res-catchment-ha").textContent = `${data.catchment.area_hectares.toFixed(2)} ha`;
  document.getElementById("res-catchment-m2").textContent = `${Math.round(data.catchment.area_m2).toLocaleString()} m²`;
  document.getElementById("res-mean-slope").textContent = `${data.catchment.mean_slope_pct.toFixed(2)} %`;
  document.getElementById("res-relief").textContent = `${data.catchment.relief_m} m`;

  document.getElementById("res-dimensions").textContent = hydro.recommended_dimensions;
  document.getElementById("res-storage-cap").textContent = `${Math.round(hydro.recommended_pond_storage_capacity_m3).toLocaleString()} m³`;
  document.getElementById("res-surface-area").textContent = `${Math.round(hydro.recommended_pond_area_m2).toLocaleString()} m²`;

  // Raw JSON display
  document.getElementById("raw-json-output").textContent = JSON.stringify(data, null, 2);

  // Show results section
  document.getElementById("results-container").style.display = "flex";

  // Fit map view
  const bounds = catchmentLayer.getBounds();
  if (landLayer) bounds.extend(landLayer.getBounds());
  map.fitBounds(bounds, { padding: [50, 50] });
}

/* -------------------------------------------------------------------------- */
/* GeoJSON Export & Upload Modal                                              */
/* -------------------------------------------------------------------------- */

function exportGeoJSON() {
  if (!currentResults) {
    alert("Please run an analysis first to export results.");
    return;
  }

  const featureCollection = {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        geometry: currentResults.selected_land_geojson,
        properties: { name: "Selected Land Area", area_ha: currentResults.selected_area_hectares }
      },
      {
        type: "Feature",
        geometry: currentResults.catchment.boundary_geojson,
        properties: { name: "Delineated Catchment", area_ha: currentResults.catchment.area_hectares }
      },
      {
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [currentResults.pond_site.lon, currentResults.pond_site.lat]
        },
        properties: {
          name: "Recommended Pond Outlet",
          elevation_m: currentResults.pond_site.elevation_m,
          harvest_volume_m3: currentResults.hydrology.expected_water_volume_m3
        }
      }
    ]
  };

  const blob = new Blob([JSON.stringify(featureCollection, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `village_pond_plan_${new Date().toISOString().slice(0, 10)}.geojson`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function setupUploadModal() {
  const modal = document.getElementById("upload-modal");
  const openBtn = document.getElementById("btn-open-upload");
  const closeBtn = document.getElementById("btn-close-modal");
  const cancelBtn = document.getElementById("btn-cancel-upload");
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const submitBtn = document.getElementById("btn-submit-upload");
  const fileNameDisplay = document.getElementById("file-chosen-name");

  let selectedFile = null;

  const showModal = () => modal.classList.add("active");
  const hideModal = () => {
    modal.classList.remove("active");
    selectedFile = null;
    fileInput.value = "";
    fileNameDisplay.textContent = "";
    submitBtn.disabled = true;
  };

  openBtn.addEventListener("click", showModal);
  closeBtn.addEventListener("click", hideModal);
  cancelBtn.addEventListener("click", hideModal);

  dropZone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      selectedFile = e.target.files[0];
      fileNameDisplay.textContent = `Selected: ${selectedFile.name} (${(selectedFile.size / 1024).toFixed(1)} KB)`;
      submitBtn.disabled = false;
    }
  });

  submitBtn.addEventListener("click", async () => {
    if (!selectedFile) return;

    submitBtn.disabled = true;
    submitBtn.textContent = "Processing Map...";

    const formData = new FormData();
    formData.append("contour_map", selectedFile);
    formData.append("resolution_m", "10.0");
    formData.append("min_catchment_area_m2", "5000.0");

    try {
      const res = await fetch("/analyzeContour", {
        method: "POST",
        body: formData
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Upload analysis failed");
      }

      const data = await res.json();
      hideModal();

      // Synthesize area response format for unified rendering
      const unifiedData = {
        selected_land_geojson: data.catchment.boundary_geojson,
        selected_area_m2: data.catchment.area_m2,
        selected_area_hectares: data.catchment.area_hectares,
        pond_site: data.pond_site,
        catchment: data.catchment,
        hydrology: data.hydrology,
        processing_time_ms: data.processing_time_ms
      };

      currentResults = unifiedData;
      renderResults(unifiedData);

    } catch (err) {
      alert("Error: " + err.message);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Process Upload";
    }
  });
}
