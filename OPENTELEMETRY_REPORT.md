# OpenTelemetry Implementation & Observability Report
## AI-Based Village Pond & Catchment Planning System (HydroPond AI)

**Course:** Distributed Systems / Software Engineering Lab  
**Student Name:** Karthik Vishlavath  
**Roll Number / Email:** vishlavathk@iitbhilai.ac.in  
**Institution:** Indian Institute of Technology Bhilai  
**Deployment Host / Container:** `http://10.1.75.51:3317/`  
**Repository:** [https://github.com/VishlavthKarthik/Pond-Catchment-Plan](https://github.com/VishlavthKarthik/Pond-Catchment-Plan)  
**Date:** October 16, 2026  

---

## Executive Summary

This report documents the end-to-end integration, deployment, and verification of **OpenTelemetry (OTel)** into the **AI-based Village Pond & Catchment Planning System (HydroPond AI)** from Assignment 1, deployed at `http://10.1.75.51:3317/`.

Modern backend systems require comprehensive observability beyond unstructured, isolated log messages. Using OpenTelemetry's vendor-neutral API and SDK, we instrumented all critical backend micro-stages: HTTP ingress routing, KML contour ingestion, Digital Elevation Model (DEM) rasterization, Wang-Liu priority-flood depression filling, D8 flow routing, upstream watershed delineation, and Central Water Commission (CWC) rational runoff calculations.

Observability data is continuously collected across the **Three Pillars of Observability**:
1. **Distributed Tracing:** Exported via OpenTelemetry Protocol (OTLP/HTTP) to a **Jaeger** distributed tracing engine (`http://10.1.75.51:16686`), capturing end-to-end span waterfalls, call trees, and custom domain attributes.
2. **Application & Infrastructure Metrics:** Aggregated via the OpenTelemetry `MeterProvider` and scraped at `http://10.1.75.51:3317/metrics` by a **Prometheus** Time-Series Database (`http://10.1.75.51:9090`), enabling real-time PromQL monitoring and capacity profiling.
3. **Context-Correlated Structured Logs:** Embedded with W3C standard 128-bit `trace_id` and 64-bit `span_id` to allow instant bi-directional correlation between terminal server logs and Jaeger traces.

---

## 1. Description of the OpenTelemetry Implementation

### 1.1 Architectural Overview

HydroPond AI is an asynchronous GIS and hydrological decision-support platform designed to delineate catchment watersheds and calculate harvestable rainwater yield for rural village storage ponds. The computational pipeline processes complex geospatial vector data and high-resolution raster matrices. 

Without instrumentation, this pipeline operates as a black box: slow requests cannot be attributed to specific algorithms, transient external network delays (e.g., historical climate API queries) remain invisible, and memory allocation spikes cannot be correlated with grid cell dimensions.

```
+-----------------------------------------------------------------------------------+
|               HydroPond AI Client (Web GIS HUD: http://10.1.75.51:3317/)          |
+-----------------------------------------------------------------------------------+
                                    |  ^  HTTP JSON / GeoJSON
                                    v  |
+-----------------------------------------------------------------------------------+
|                 FastAPI Asynchronous Gateway (http://10.1.75.51:3317/)            |
|   [Auto-Instrumentation: FastAPIInstrumentor, HTTPXClientInstrumentor, Logging]  |
+-----------------------------------------------------------------------------------+
      |
      |-- (Span: "kml.parse")
      |   --> Agnostic XML parsing of contour Placemarks & coordinates
      |
      |-- (Span: "dem.build")
      |   --> UTM projection (pyproj) & SciPy griddata elevation interpolation
      |
      |-- (Span: "terrain.pipeline" / "terrain.priority_flood_fill")
      |   --> Barnes/Wang-Liu heap priority flood depression fill
      |   --> D8 flow direction matrix & topological queue flow accumulation
      |
      |-- (Span: "pond.select_and_delineate")
      |   --> Heuristic candidate scoring & BFS upstream graph traversal (Shapely)
      |
      |-- (Span: "hydrology.calculate" & "hydrology.fetch_historical_rainfall")
      |   --> Open-Meteo external climate archive API & CWC Rational Runoff model
      |
      +=============================+=============================+
                                    |                             |
                       OTLP HTTP Spans (:4318)       Prometheus Scrape (:3317/metrics)
                                    v                             v
                        +----------------------+      +----------------------+
                        |   Jaeger Tracing     |      |   Prometheus TSDB    |
                        |      Backend         |      |       Server         |
                        | (10.1.75.51:16686)   |      |  (10.1.75.51:9090)   |
                        +----------------------+      +----------------------+
```

### 1.2 Telemetry Architecture & Implementation Details

The implementation resides in a modular telemetry subsystem (`app/telemetry.py`), ensuring clean separation of concerns and zero tight coupling with business logic:

1. **Tracer Provider (`TracerProvider`):**
   - Configured with a standardized `Resource` descriptor identifying the service name (`hydrology-pond-system`), semantic version (`2.0.0`), deployment environment (`production`), and process instance ID.
   - Attaches a `BatchSpanProcessor` coupled to `OTLPSpanExporter(endpoint="http://10.1.75.51:4318/v1/traces")` to asynchronously dispatch spans to the Jaeger collector without blocking the main event loop.

2. **Custom Span Hierarchy:**
   - Every algorithmic phase is instrumented with explicit child spans (`tracer.start_as_current_span`), creating a rich call tree:
     - `api.analyze_contour` / `api.analyze_area`: Parent HTTP transaction span.
     - `kml.parse`: Measures XML parsing and polyline extraction latency.
     - `dem.build`: Captures resolution adjustments, projection EPSG, and grid dimensions.
     - `terrain.priority_flood_fill`: Profiles sink-filling priority queue operations.
     - `pond.select_and_delineate`: Profiles heuristic scoring and BFS upstream graph traversal.
     - `hydrology.calculate`: Tracks runoff calculation, pond sizing, and socio-economic water security days.
     - `hydrology.fetch_historical_rainfall`: Profiles external HTTP calls to Open-Meteo with automatic fallback recording.

3. **Domain-Specific Semantic Attributes & Span Events:**
   Rather than capturing only generic HTTP metadata, custom spans record critical hydrological attributes:
   - `hydrology.annual_rainfall_mm`, `hydrology.runoff_coefficient`, `hydrology.runoff_volume_m3`, `hydrology.household_water_days`
   - `catchment.area_m2`, `catchment.area_hectares`, `catchment.mean_slope_pct`, `catchment.watershed_cell_count`
   - `dem.resolution_actual`, `dem.grid_rows`, `dem.grid_cols`, `dem.cell_count`
   - `span.add_event("hydrology_computation_completed", {...})` emits milestone events with structured event payloads.

4. **Metrics Subsystem (`MeterProvider` & `PrometheusMetricReader`):**
   - Registers a `PrometheusMetricReader` providing a native Prometheus pull endpoint at `GET http://10.1.75.51:3317/metrics`.
   - Defined custom metric instruments:
     - `hydrology_requests_total` (Counter): Counts total analysis requests labeled by endpoint (`/analyzeContour`, `/api/analyze-area`, `/api/sample-contours`), status, and cache state (`hit`/`miss`).
     - `hydrology_algorithm_duration_seconds` (Histogram): Captures duration distributions across discrete algorithm stages (`dem_rasterization`, `priority_flood_fill`, `pond_selection`, `hydrology_calculation`).
     - `hydrology_dem_grid_cells_total` (Histogram): Tracks grid cell scale distributions.
     - `hydrology_watershed_cells_total` (Histogram): Tracks watershed cell count distributions.
     - `hydrology_water_volume_harvestable_m3` (Histogram): Tracks expected rainwater volume distributions.
     - `hydrology_active_requests` (UpDownCounter / Gauge): Monitors in-flight concurrent requests.

5. **Trace-Context Correlated Structured Logging:**
   - Implemented a custom `TraceContextFormatter` subclassing Python's standard `logging.Formatter`.
   - Automatically inspects `trace.get_current_span().get_span_context()` on every log call. If active, extracts the 32-character hexadecimal `trace_id` and 16-character `span_id`.
   - Injects them into structured log outputs formatted as:
     `[%(asctime)s] [%(levelname)s] [trace_id=%(trace_id)s span_id=%(span_id)s] [%(name)s]: %(message)s`
   - Enables instant cross-linking between application server logs and Jaeger traces.

---

## 2. Tools, Libraries, and Backend Services Used

| Component | Technology | Version | Purpose in Project |
| :--- | :--- | :--- | :--- |
| **Telemetry SDK** | `opentelemetry-api` | `1.45.1` | Core OpenTelemetry interfaces, trace/metric context propagation, and span lifecycle. |
| **Telemetry Runtime** | `opentelemetry-sdk` | `1.45.1` | TracerProvider, MeterProvider, batch processors, and resource definitions. |
| **FastAPI Instrumentation** | `opentelemetry-instrumentation-fastapi` | `0.66b1` | Automatic HTTP request/response tracing, route identification, and status code tagging. |
| **HTTP Client Instrumentation**| `opentelemetry-instrumentation-httpx` | `0.66b1` | Distributed context propagation and span creation for external climate API requests. |
| **Logging Instrumentation** | `opentelemetry-instrumentation-logging` | `0.66b1` | Integration between standard Python `logging` and OpenTelemetry context. |
| **OTLP Exporter** | `opentelemetry-exporter-otlp-proto-http`| `1.45.1` | Protocol Buffers over HTTP exporter dispatching traces to Jaeger at `:4318/v1/traces`. |
| **Prometheus Exporter** | `opentelemetry-exporter-prometheus` | `0.66b1` | Bridges OpenTelemetry meter instruments into Prometheus format at `/metrics`. |
| **Prometheus Client** | `prometheus_client` | `0.26.0` | Official client generating metric exposition format and registry storage. |
| **Tracing Backend** | **Jaeger All-in-One** | `v1.60.0` | Standalone backend collecting OTLP spans, indexing traces, and UI at `http://10.1.75.51:16686`. |
| **Metrics TSDB Backend** | **Prometheus Server** | `v3.15.0` | Standalone TSDB scraping `http://10.1.75.51:3317/metrics` with UI at `http://10.1.75.51:9090`. |
| **Application Server** | **FastAPI + Uvicorn** | `0.141 / 0.52` | Asynchronous Web GIS backend serving API endpoints and interactive HUD at `http://10.1.75.51:3317/`. |

---

## 3. Verification Screenshots & Technical Analysis

The implementation was validated by generating workloads across the system and inspecting the live observability interfaces. All 7 screenshots below are captured directly from our running environment.

```carousel
![Figure 1: HydroPond AI Interactive Web GIS Interface](/home/karthik/Desktop/Pond-Catchment-Plan/screenshots/fig1_hydropond_gis_ui.png)
<!-- slide -->
![Figure 2: Jaeger Tracing Catalog and Search View](/home/karthik/Desktop/Pond-Catchment-Plan/screenshots/fig2_jaeger_traces_search.png)
<!-- slide -->
![Figure 3: Jaeger Deep Trace & Custom Domain Attributes](/home/karthik/Desktop/Pond-Catchment-Plan/screenshots/fig3_jaeger_waterfall_attributes.png)
<!-- slide -->
![Figure 4: Jaeger Detailed Span Breakdown & Timeline](/home/karthik/Desktop/Pond-Catchment-Plan/screenshots/fig4_jaeger_span_breakdown.png)
<!-- slide -->
![Figure 5: Prometheus Time-Series Metrics Chart](/home/karthik/Desktop/Pond-Catchment-Plan/screenshots/fig5_prometheus_metrics_graph.png)
<!-- slide -->
![Figure 6: Prometheus Scrape Target Health Status](/home/karthik/Desktop/Pond-Catchment-Plan/screenshots/fig6_prometheus_target_health.png)
<!-- slide -->
![Figure 7: Context-Correlated Structured Application Logs](/home/karthik/Desktop/Pond-Catchment-Plan/screenshots/fig7_trace_correlated_logs.png)
```

---

### Figure 1: HydroPond AI Interactive Web GIS Interface (System Under Test)

![Figure 1: HydroPond AI Interactive Web GIS Interface](file:///home/karthik/Desktop/Pond-Catchment-Plan/screenshots/fig1_hydropond_gis_ui.png)

#### Detailed Description:
Figure 1 shows the live user-facing Web GIS interface of HydroPond AI (`http://10.1.75.51:3317/`) executing a farmland parcel analysis near IIT Bhilai and the Shivnath River basin:
- **Spatial Overlays:** The Leaflet map displays 1-meter elevation contour polylines (blue curves), the user-drawn agricultural land parcel (yellow polygon), the mathematically delineated upstream catchment watershed (blue shaded polygon), and the optimal pond excavation outlet marker.
- **Hydrological HUD (Left Panel):**
  - **Harvestable Rainwater Volume:** Quantified at **7.28 Million Litres (ML)** ($7,277\text{ m}^3$ total monsoon runoff volume), estimated to guarantee water security for **~103 rural families for 180+ dry-season days**.
  - **Optimal Pond Site:** Selected at Latitude **$21.250448^\circ\text{ N}$**, Longitude **$81.299836^\circ\text{ E}$** at a bed elevation of **$282\text{ m}$**, with a local flow accumulation of **206 grid cells**.
  - **Catchment Characteristics:** Delineated catchment area of **$2.08\text{ ha}$ ($20,800\text{ m}^2$)**, a mean terrain slope of **$3.93\%$**, and an elevation relief of **$5\text{ m}$**.
  - **Engineering Pond Dimensions:** Recommended trapezoidal pond ($1.5:1$ side slopes) of dimensions **$55.5\text{ m} \times 37.0\text{ m} \times 3.0\text{ m}$ ($L \times W \times D$)**, yielding a storage capacity of **$4,366\text{ m}^3$** and a surface footprint of **$2,055\text{ m}^2$**.

#### What this demonstrates:
This screenshot confirms that the baseline Assignment 1 application is fully functional, producing real mathematical and geographical outputs that provide the foundation for our telemetry pipeline.

---

### Figure 2: Jaeger Distributed Tracing — Search & Trace Catalog

![Figure 2: Jaeger Distributed Tracing Search & Overview](file:///home/karthik/Desktop/Pond-Catchment-Plan/screenshots/fig2_jaeger_traces_search.png)

#### Detailed Description:
Figure 2 shows the Jaeger Web UI search dashboard (`http://10.1.75.51:16686/search?service=hydrology-pond-system`):
- **Service Registration:** The service selector correctly identifies `hydrology-pond-system`, confirming that the OpenTelemetry SDK successfully initialized and registered with the Jaeger OTLP HTTP collector on port `4318`.
- **Latency Scatter Plot (Top):** Displays trace executions over time, visually categorizing transaction durations across requests.
- **Trace Catalog:** Captures distinct user interactions with precise latency and span counts:
  1. `POST /api/analyze-area (Trace ID: ba71583037de6cb362bc151107e3eba5)`: Latency of **$1.37\text{ s}$**, comprising **8 Spans**. *(Note: This exactly corresponds to the 7.28 ML analysis seen in Figure 1 and logged in Figure 7!)*
  2. `GET /api/sample-contours (Trace ID: 0842a86...)`: Latency of **$44.07\text{ ms}$**, comprising **4 Spans**.
  3. `POST /api/analyze-area (Trace ID: 6c9318f0ab9b75bed2482275e6caab46)`: Latency of **$1.21\text{ s}$**, comprising **8 Spans**.

#### What this demonstrates:
This confirms that OpenTelemetry captures every incoming API transaction, assigns unique distributed trace identifiers, and exports the transaction graphs to Jaeger without dropped spans or transmission failures.

---

### Figure 3: Jaeger Deep Trace & Custom Domain Attributes (Waterfall View)

![Figure 3: Jaeger Deep Trace & Custom Domain Attributes](file:///home/karthik/Desktop/Pond-Catchment-Plan/screenshots/fig3_jaeger_waterfall_attributes.png)

#### Detailed Description:
Figure 3 displays the detailed span waterfall and call tree for a comprehensive contour analysis transaction (`POST /analyzeContour`, Trace ID: `a622112a28f2b56608ff30ba65efd3dd`), with an end-to-end execution duration of **$4.88\text{ s}$** containing **44 total spans across 4 hierarchy levels**:
- **Span Hierarchy & Latency Breakdown:**
  - `api.analyze_contour`: Root business transaction span.
  - `kml.parse`: **$140.12\text{ ms}$** — Ingesting XML and extracting contour polylines.
  - `dem.build`: **$2.94\text{ s}$** — Reprojecting WGS84 coordinates to UTM Zone 44N and rasterizing $86,390$ grid cells using SciPy interpolation.
  - `terrain.pipeline`: **$713.34\text{ ms}$** — Supervising terrain analysis.
  - `terrain.priority_flood_fill`: **$667.98\text{ ms}$** — Running the Barnes/Wang-Liu heap priority flood depression elimination.
  - `pond.select_and_delineate`: **$36.97\text{ ms}$** — Heuristic outlet cell scoring and BFS upstream graph traversal.
  - `hydrology.calculate`: **$997.66\text{ ms}$** — Rational runoff computation and pond volume sizing.
  - `hydrology.fetch_historical_rainfall`: **$997.34\text{ ms}$** — Outgoing HTTP request to the Open-Meteo archive API.
- **Expanded Span Tags (Domain Attributes):**
  Expanding the `hydrology.calculate` span displays custom OpenTelemetry tags:
  - `hydrology.annual_rainfall_mm = 1595.4`
  - `hydrology.monsoon_rainfall_mm = 1356.1`
  - `hydrology.catchment_area_m2 = 54100` ($5.41\text{ ha}$)
  - `hydrology.mean_slope_pct = 4.26`
  - `hydrology.household_water_days = 50048`
  - OpenTelemetry process metadata: `service.name = hydrology-pond-system`, `service.version = 2.0.0`, `telemetry.sdk.language = python`.

#### What this demonstrates:
This is the core proof of deep manual instrumentation. Rather than merely showing black-box HTTP latency, OpenTelemetry breaks down internal algorithmic execution and embeds domain-specific hydrology calculations directly inside the trace span.

---

### Figure 4: Jaeger Detailed Span Breakdown & Timeline

![Figure 4: Jaeger Detailed Span Breakdown & Timeline](file:///home/karthik/Desktop/Pond-Catchment-Plan/screenshots/fig4_jaeger_span_breakdown.png)

#### Detailed Description:
Figure 4 displays the complete collapsed timeline overview across the $4.88\text{ s}$ execution window:
- Visually correlates relative timing: SciPy interpolation in `dem.build` occupies the first $2.94\text{ s}$ of the transaction, followed by depression filling at $667.98\text{ ms}$, instantaneous pond selection ($36.97\text{ ms}$), and network I/O for historical meteorological data fetching ($997.34\text{ ms}$).
- Child spans correctly reflect parent-child context propagation, demonstrating that the W3C trace context was maintained across asynchronous execution boundaries.

#### What this demonstrates:
Demonstrates execution profiling and bottleneck identification. Developers can instantly identify that optimizing the SciPy DEM interpolator or caching meteorological data would yield the highest performance gains.

---

### Figure 5: Prometheus Time-Series Metrics Chart (PromQL Query)

![Figure 5: Prometheus Time-Series Metrics Chart](file:///home/karthik/Desktop/Pond-Catchment-Plan/screenshots/fig5_prometheus_metrics_graph.png)

#### Detailed Description:
Figure 5 displays the Prometheus Web UI dashboard (`http://10.1.75.51:9090/graph`) executing an instant PromQL query on our custom metric:
$$\text{Query: } \texttt{hydrology\_requests\_total}$$
- **Time-Series Curves:**
  - **Purple line:** `hydrology_requests_total{endpoint="/api/analyze-area", ...}` — Increments step-wise from $3.00$ to $4.00$, and then to $5.00$ as multiple farmland parcel requests are processed.
  - **Green line:** `hydrology_requests_total{cache="hit", endpoint="/api/sample-contours", ...}` — Shows contour preview requests served directly from the in-memory cache, stepping from $2.00$ to $3.00$.
  - **Red line:** `hydrology_requests_total{endpoint="/analyzeContour", ...}` — Tracks uploaded KML contour maps processed by the system (steady at $1.00$).
  - **Cyan line:** `hydrology_requests_total{cache="miss", ...}` — Tracks cold-start cache misses during initial dataset preloading.

#### What this demonstrates:
Proves successful metric instrument creation, collection, exposition via `http://10.1.75.51:3317/metrics`, and periodic time-series scraping by Prometheus. It demonstrates that OpenTelemetry provides quantitative operational insight into endpoint usage patterns and caching efficiency.

---

### Figure 6: Prometheus Scrape Target Health Status

![Figure 6: Prometheus Scrape Target Health Status](file:///home/karthik/Desktop/Pond-Catchment-Plan/screenshots/fig6_prometheus_target_health.png)

#### Detailed Description:
Figure 6 displays the Prometheus **Target Health** verification console (`http://10.1.75.51:9090/targets?search=`):
- **Scrape Pool Name:** `hydrology-pond-system` (1 / 1 targets UP, indicated by the vibrant green status glyph).
- **Target Endpoint:** `http://10.1.75.51:3317/metrics`
- **Labels Attached:** `instance="10.1.75.51:3317"`, `job="hydrology-pond-system"`.
- **Health Indicators:**
  - **State:** **`UP`** (highlighted in bright green badge).
  - **Last Scrape:** Executed $42.467\text{ s}$ ago.
  - **Scrape Duration:** Ultra-low latency of only **$16\text{ ms}$**, confirming negligible overhead of the OpenTelemetry metric exposition pipeline.
  - **Error Field:** Completely empty / no scrape errors reported.

#### What this demonstrates:
This screenshot proves that the Prometheus pull-based telemetry pipeline is 100% operational. The OpenTelemetry Prometheus exporter actively serves metric formats adhering to the OpenMetrics standard, allowing the Prometheus TSDB to reliably pull metrics without timeouts or parsing failures.

---

### Figure 7: Context-Correlated Structured Application Server Logs

![Figure 7: Context-Correlated Structured Application Server Logs](file:///home/karthik/Desktop/Pond-Catchment-Plan/screenshots/fig7_trace_correlated_logs.png)

#### Detailed Description:
Figure 7 displays the actual terminal inspection (`tail -n 20 logs/app.log`) of the live HydroPond AI server logs running at `http://10.1.75.51:3317/`:
- **Trace Context Formatting:** Each log line contains the W3C standard `trace_id` (32 hex characters) and `span_id` (16 hex characters) automatically injected by our custom `TraceContextFormatter`:
  ```log
  [2026-10-16 21:23:01] [INFO] [trace_id=ba71583037de6cb362bc151107e3eba5 span_id=a9ba24433bf52a64] [hydrology.api]: Area Analysis Complete: parcel=60.51ha, catchment=2.08ha, harvest_vol=7.28ML, elapsed=1369ms
  ```
- **Direct Cross-Pillar Correlation Proof:**
  - In log line `21:23:01`, the system records `catchment=2.08ha, harvest_vol=7.28ML, elapsed=1369ms` with `trace_id=ba71583037de6cb362bc151107e3eba5`.
  - This matches **Figure 1** (UI showing $2.08\text{ ha}$ catchment and $7.28\text{ ML}$ harvest volume) and **Figure 2** (Jaeger UI listing Trace ID `ba71583037de6cb362bc151107e3eba5` at $1.37\text{ s}$ duration)!
  - In log line `21:10:02`, `trace_id=6c9318f0ab9b75bed2482275e6caab46` matches the third trace visible in Jaeger Search (Figure 2).
  - In log line `18:27:21`, `trace_id=a622112a28f2b56608ff30ba65efd3dd` matches the exact deep-trace waterfall dissected in Jaeger (Figure 3 and Figure 4).

#### What this demonstrates:
This provides absolute proof of the third pillar of observability: **Context-Correlated Logging**. An engineer inspecting a log message can instantly copy the `trace_id` and paste it into Jaeger to see the full flamegraph and micro-timing of that request.

---

## 4. Understanding of the Collected Data & Benefits for System Monitoring

Implementing OpenTelemetry in HydroPond AI provides clear operational and engineering insights:

### 4.1 Latency Profiling & Algorithmic Bottleneck Localization
From the Jaeger waterfall trace in Figure 3, we obtain a precise time budget for the $4.88\text{ s}$ execution:
1. **DEM Rasterization (`dem.build`, 60.2% of total time):** SciPy bivariate cubic/linear interpolation over $86,390$ cells takes $2.94\text{ s}$. This identifies `griddata` interpolation as the primary computational bottleneck. Optimization action: Pre-compiling Delaunay triangulation or utilizing GPU-accelerated CuPy interpolation.
2. **External API Latency (`hydrology.fetch_historical_rainfall`, 20.4% of total time):** The outgoing HTTP request to Open-Meteo took $997.34\text{ ms}$. Optimization action: Caching daily rainfall sums in an in-memory Redis layer keyed by coordinate geohash to eliminate remote round trips.
3. **Depression Filling (`terrain.priority_flood_fill`, 13.7% of total time):** The Barnes/Wang-Liu heap algorithm took $667.98\text{ ms}$ on an $86,390$-cell grid. Optimization action: Implementing early termination or hierarchical grid coarsening.
4. **Pond Site Selection & Delineation (`pond.select_and_delineate`, < 1% of total time):** Heuristic candidate evaluation and BFS upstream graph traversal took only $36.97\text{ ms}$, confirming high algorithmic efficiency.

### 4.2 Proactive Capacity Planning & Operational Reliability
Prometheus time-series metrics enable data-driven capacity decisions:
- **Throughput & Cache Efficiency:** Figure 5 proves that $60\%$ of `/api/sample-contours` requests are served from cache in $< 45\text{ ms}$, protecting backend memory from redundant re-computations.
- **Water Volume Aggregates:** Tracking cumulative volume via `hydrology_water_volume_harvestable_m3` allows regional planners to monitor total water capacity planned across multi-village jurisdictions.
- **SLA & Health Monitoring:** Setting automated Prometheus alert rules on `http_requests_total` error rates ($5\text{xx} > 1\%$) and `hydrology_algorithm_duration_seconds` ($p95 > 3\text{ s}$) allows automated alerting before users experience degraded service.

### 4.3 Root-Cause Analysis via Cross-Pillar Correlation
Prior to OpenTelemetry, troubleshooting an exception required manually cross-referencing server timestamps with client bug reports. With correlated logging and tracing:
- If an invalid polygon geometry causes a topology error, the log line prints the exact `trace_id`.
- Clicking the trace in Jaeger reveals the exact polygon vertices (`request.polygon_vertices`), the elevation grid dimension, and the exact stack trace recorded by `span.record_exception(exc)` on the failed span.

---

## 5. VIVA Examination Preparation & Key Concepts

| Question | Model Viva Answer |
| :--- | :--- |
| **Why use OpenTelemetry instead of writing print statements or loggers?** | *Print statements and logs lack distributed causality. OpenTelemetry standardizes context propagation using W3C Trace Context headers, linking distributed spans across microservices and providing structured metrics that can be queried mathematically with PromQL, rather than parsed as raw text.* |
| **What is the difference between OpenTelemetry, Jaeger, and Prometheus?** | *OpenTelemetry is the instrumentation framework that collects observability data. Jaeger is a distributed tracing backend that visualizes call trees and waterfalls. Prometheus is a time-series database that periodically pulls numeric metrics for dashboard graphing and alerting.* |
| **What is the difference between a Trace and a Span?** | *A Trace represents the entire journey of a single request through the system from start to finish. A Span represents a single unit of contiguous work within that trace (e.g. `dem.build`), with a name, timestamps, attributes, and optional events.* |
| **How did you correlate logs with traces in your project?** | *We implemented a custom `TraceContextFormatter` that extracts `trace_id` and `span_id` from `trace.get_current_span().get_span_context()` during log formatting. This guarantees that every log output in `app.log` contains the exact 128-bit Trace ID displayed in Jaeger.* |
| **What was the biggest performance bottleneck discovered by tracing?** | *The Jaeger flamegraph revealed that SciPy elevation grid interpolation (`dem.build`) accounted for $60.2\%$ ($2.94\text{ s}$) of the total $4.88\text{ s}$ transaction, whereas pond selection and catchment graph traversal took only $36.97\text{ ms}$.* |

---

## 6. Conclusion

The integration of OpenTelemetry into the HydroPond AI Village Pond Planning System deployed at `http://10.1.75.51:3317/` was completed successfully. The application captures distributed traces with custom domain-specific hydrological metadata, exposes Prometheus metrics via `http://10.1.75.51:3317/metrics`, and correlates application logs using W3C standard trace identifiers. 

The implementation was verified using real geospatial contour datasets and live map interactions across 7 distinct verification perspectives, proving that OpenTelemetry transforms complex hydrological computational workflows from opaque black boxes into transparent, observable, and production-ready distributed services.
