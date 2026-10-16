import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
import os

doc = docx.Document()

# Page Setup: Standard A4 with 0.8 inch margins
sections = doc.sections
for section in sections:
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.8)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)

# Color Palette
PRIMARY_COLOR = RGBColor(31, 78, 121)   # #1F4E79 Deep Navy
SECONDARY_COLOR = RGBColor(46, 117, 182) # #2E75B6 Steel Blue
DARK_GRAY = RGBColor(51, 51, 51)
LIGHT_BG_HEX = "F2F2F2"
HEADER_BG_HEX = "1F4E79"

def set_cell_background(cell, hex_color):
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('w:top', top), ('w:bottom', bottom), ('w:left', left), ('w:right', right)]:
        node = OxmlElement(m)
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def add_title(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(text)
    run.font.name = 'Calibri'
    run.font.size = Pt(22)
    run.font.bold = True
    run.font.color.rgb = PRIMARY_COLOR

def add_subtitle(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(14)
    run = p.add_run(text)
    run.font.name = 'Calibri'
    run.font.size = Pt(13)
    run.font.bold = True
    run.font.color.rgb = SECONDARY_COLOR

def add_heading1(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = 'Calibri'
    run.font.size = Pt(15)
    run.font.bold = True
    run.font.color.rgb = PRIMARY_COLOR

def add_heading2(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = 'Calibri'
    run.font.size = Pt(12.5)
    run.font.bold = True
    run.font.color.rgb = SECONDARY_COLOR

def add_heading3(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = 'Calibri'
    run.font.size = Pt(11)
    run.font.bold = True
    run.font.color.rgb = DARK_GRAY

def add_p(text, bold=False, italic=False):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.line_spacing = 1.15
    run = p.add_run(text)
    run.font.name = 'Calibri'
    run.font.size = Pt(10.5)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = DARK_GRAY
    return p

def add_bullet(text, bold_prefix="", level=0):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = 'Calibri'
        r_pre.font.size = Pt(10)
        r_pre.font.bold = True
        r_pre.font.color.rgb = DARK_GRAY
    run = p.add_run(text)
    run.font.name = 'Calibri'
    run.font.size = Pt(10)
    run.font.color.rgb = DARK_GRAY
    return p

def add_code_block(code_text):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.cell(0, 0)
    cell.width = Inches(6.67)
    set_cell_background(cell, "F6F8FA")
    set_cell_margins(cell, top=120, bottom=120, left=160, right=160)
    
    # Remove table borders
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(f'''
        <w:tcBorders {nsdecls("w")}>
            <w:top w:val="single" w:sz="4" w:space="0" w:color="D1D5DA"/>
            <w:left w:val="single" w:sz="4" w:space="0" w:color="D1D5DA"/>
            <w:bottom w:val="single" w:sz="4" w:space="0" w:color="D1D5DA"/>
            <w:right w:val="single" w:sz="4" w:space="0" w:color="D1D5DA"/>
        </w:tcBorders>
    ''')
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(code_text)
    run.font.name = 'Consolas'
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGBColor(36, 41, 46)
    
    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(6)

def add_image_figure(image_path, caption_text, width_inches=6.2):
    if not os.path.exists(image_path):
        add_p(f"[Image file not found: {image_path}]", italic=True)
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    run = p.add_run()
    run.add_picture(image_path, width=Inches(width_inches))
    
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_before = Pt(2)
    cap.paragraph_format.space_after = Pt(10)
    cap.paragraph_format.keep_with_next = False
    run_cap = cap.add_run(caption_text)
    run_cap.font.name = 'Calibri'
    run_cap.font.size = Pt(9.5)
    run_cap.font.bold = True
    run_cap.font.italic = True
    run_cap.font.color.rgb = RGBColor(88, 96, 105)

# ----------------- DOCUMENT HEADER & METADATA -----------------
add_title("OpenTelemetry Implementation & Observability Report")
add_subtitle("AI-Based Village Pond & Catchment Planning System (HydroPond AI)")

# Meta Box Table
meta_table = doc.add_table(rows=6, cols=2)
meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
meta_data = [
    ("Course:", "Distributed Systems / Software Engineering Lab"),
    ("Student Name:", "Karthik Vishlavath  |  Roll / Email: vishlavathk@iitbhilai.ac.in"),
    ("Institution:", "Indian Institute of Technology Bhilai"),
    ("Deployment Host / Container:", "http://10.1.75.51:3317/"),
    ("Repository URL:", "https://github.com/VishlavthKarthik/Pond-Catchment-Plan"),
    ("Submission Date:", "October 16, 2026")
]
for idx, (label, val) in enumerate(meta_data):
    row = meta_table.rows[idx]
    cell_lbl, cell_val = row.cells[0], row.cells[1]
    cell_lbl.width = Inches(2.2)
    cell_val.width = Inches(4.47)
    set_cell_background(cell_lbl, "F6F8FA")
    set_cell_background(cell_val, "FAFBFC")
    set_cell_margins(cell_lbl, top=40, bottom=40, left=80, right=80)
    set_cell_margins(cell_val, top=40, bottom=40, left=80, right=80)
    
    p0 = cell_lbl.paragraphs[0]
    p0.paragraph_format.space_before = Pt(0)
    p0.paragraph_format.space_after = Pt(0)
    r0 = p0.add_run(label)
    r0.font.name = 'Calibri'
    r0.font.size = Pt(9.5)
    r0.font.bold = True
    r0.font.color.rgb = PRIMARY_COLOR
    
    p1 = cell_val.paragraphs[0]
    p1.paragraph_format.space_before = Pt(0)
    p1.paragraph_format.space_after = Pt(0)
    r1 = p1.add_run(val)
    r1.font.name = 'Calibri'
    r1.font.size = Pt(9.5)
    r1.font.color.rgb = DARK_GRAY

p_space = doc.add_paragraph()
p_space.paragraph_format.space_before = Pt(6)
p_space.paragraph_format.space_after = Pt(6)

# ----------------- EXECUTIVE SUMMARY -----------------
add_heading1("Executive Summary")
add_p("This report documents the end-to-end integration, deployment, and verification of OpenTelemetry (OTel) into the AI-based Village Pond & Catchment Planning System (HydroPond AI) from Assignment 1, deployed at http://10.1.75.51:3317/.")
add_p("Modern backend systems require comprehensive observability beyond unstructured, isolated log messages. Using OpenTelemetry's vendor-neutral API and SDK, we instrumented all critical backend micro-stages: HTTP ingress routing, KML contour ingestion, Digital Elevation Model (DEM) rasterization, Wang-Liu priority-flood depression filling, D8 flow routing, upstream watershed delineation, and Central Water Commission (CWC) rational runoff calculations.")
add_p("Observability data is continuously collected across the Three Pillars of Observability:")
add_bullet("Exported via OpenTelemetry Protocol (OTLP/HTTP) to a Jaeger distributed tracing engine (http://10.1.75.51:16686), capturing end-to-end span waterfalls, call trees, and custom domain attributes.", bold_prefix="1. Distributed Tracing: ")
add_bullet("Aggregated via the OpenTelemetry MeterProvider and scraped at http://10.1.75.51:3317/metrics by a Prometheus Time-Series Database (http://10.1.75.51:9090), enabling real-time PromQL monitoring and capacity profiling.", bold_prefix="2. Application & Infrastructure Metrics: ")
add_bullet("Embedded with W3C standard 128-bit trace_id and 64-bit span_id to allow instant bi-directional correlation between terminal server logs and Jaeger traces.", bold_prefix="3. Context-Correlated Structured Logs: ")

# ----------------- SECTION 1: IMPLEMENTATION DESCRIPTION -----------------
add_heading1("1. Description of the OpenTelemetry Implementation")

add_heading2("1.1 Architectural Overview")
add_p("HydroPond AI is an asynchronous GIS and hydrological decision-support platform designed to delineate catchment watersheds and calculate harvestable rainwater yield for rural village storage ponds. The computational pipeline processes complex geospatial vector data and high-resolution raster matrices.")
add_p("Without instrumentation, this pipeline operates as a black box: slow requests cannot be attributed to specific algorithms, transient external network delays (e.g., historical climate API queries) remain invisible, and memory allocation spikes cannot be correlated with grid cell dimensions.")

architecture_diagram = (
"+-----------------------------------------------------------------------------------+\n"
"|               HydroPond AI Client (Web GIS HUD: http://10.1.75.51:3317/)          |\n"
"+-----------------------------------------------------------------------------------+\n"
"                                    |  ^  HTTP JSON / GeoJSON\n"
"                                    v  |\n"
"+-----------------------------------------------------------------------------------+\n"
"|                 FastAPI Asynchronous Gateway (http://10.1.75.51:3317/)            |\n"
"|   [Auto-Instrumentation: FastAPIInstrumentor, HTTPXClientInstrumentor, Logging]  |\n"
"+-----------------------------------------------------------------------------------+\n"
"      |\n"
"      |-- (Span: \"kml.parse\")\n"
"      |   --> Agnostic XML parsing of contour Placemarks & coordinates\n"
"      |\n"
"      |-- (Span: \"dem.build\")\n"
"      |   --> UTM projection (pyproj) & SciPy griddata elevation interpolation\n"
"      |\n"
"      |-- (Span: \"terrain.pipeline\" / \"terrain.priority_flood_fill\")\n"
"      |   --> Barnes/Wang-Liu heap priority flood depression fill\n"
"      |   --> D8 flow direction matrix & topological queue flow accumulation\n"
"      |\n"
"      |-- (Span: \"pond.select_and_delineate\")\n"
"      |   --> Heuristic candidate scoring & BFS upstream graph traversal (Shapely)\n"
"      |\n"
"      |-- (Span: \"hydrology.calculate\" & \"hydrology.fetch_historical_rainfall\")\n"
"      |   --> Open-Meteo external climate archive API & CWC Rational Runoff model\n"
"      |\n"
"      +=============================+=============================+\n"
"                                    |                             |\n"
"                       OTLP HTTP Spans (:4318)       Prometheus Scrape (:3317/metrics)\n"
"                                    v                             v\n"
"                        +----------------------+      +----------------------+\n"
"                        |   Jaeger Tracing     |      |   Prometheus TSDB    |\n"
"                        |      Backend         |      |       Server         |\n"
"                        | (10.1.75.51:16686)   |      |  (10.1.75.51:9090)   |\n"
"                        +----------------------+      +----------------------+"
)
add_code_block(architecture_diagram)

add_heading2("1.2 Telemetry Subsystem Implementation Details")
add_p("The implementation resides in a modular telemetry subsystem (app/telemetry.py), ensuring clean separation of concerns and zero tight coupling with business logic:")
add_bullet("Configured with a standardized Resource descriptor identifying the service name (hydrology-pond-system), semantic version (2.0.0), deployment environment, and process ID. Attaches a BatchSpanProcessor coupled to OTLPSpanExporter(endpoint=\"http://10.1.75.51:4318/v1/traces\") to asynchronously dispatch spans to the Jaeger collector without blocking the main event loop.", bold_prefix="1. Tracer Provider (TracerProvider): ")
add_bullet("Every algorithmic phase is instrumented with explicit child spans (tracer.start_as_current_span), creating a rich call tree: api.analyze_contour, kml.parse, dem.build, terrain.priority_flood_fill, pond.select_and_delineate, hydrology.calculate, and hydrology.fetch_historical_rainfall.", bold_prefix="2. Custom Span Hierarchy: ")
add_bullet("Custom spans record critical hydrological attributes: hydrology.annual_rainfall_mm, hydrology.runoff_coefficient, hydrology.runoff_volume_m3, catchment.area_hectares, catchment.mean_slope_pct, and dem.cell_count.", bold_prefix="3. Domain-Specific Semantic Attributes: ")
add_bullet("Registers a PrometheusMetricReader providing a native Prometheus pull endpoint at GET http://10.1.75.51:3317/metrics with custom instruments: hydrology_requests_total (Counter), hydrology_algorithm_duration_seconds (Histogram), hydrology_dem_grid_cells_total (Histogram), and hydrology_active_requests (Gauge).", bold_prefix="4. Metrics Subsystem: ")
add_bullet("Implemented a custom TraceContextFormatter subclassing Python's standard logging.Formatter. Automatically inspects trace.get_current_span().get_span_context() to inject trace_id and span_id into all log records, enabling instant bi-directional correlation between log lines and Jaeger traces.", bold_prefix="5. Trace-Context Correlated Structured Logging: ")

# ----------------- SECTION 2: TOOLS & LIBRARIES -----------------
doc.add_page_break()
add_heading1("2. Tools, Libraries, and Backend Services Used")
add_p("The following table details the comprehensive open-source observability stack integrated into the project:")

tools_table = doc.add_table(rows=12, cols=4)
tools_table.alignment = WD_TABLE_ALIGNMENT.CENTER
headers = ["Component", "Technology", "Version", "Purpose in Project"]
widths = [Inches(1.5), Inches(1.8), Inches(0.8), Inches(2.57)]

hdr_row = tools_table.rows[0]
for idx, h_text in enumerate(headers):
    cell = hdr_row.cells[idx]
    cell.width = widths[idx]
    set_cell_background(cell, HEADER_BG_HEX)
    set_cell_margins(cell, top=80, bottom=80, left=80, right=80)
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(h_text)
    run.font.name = 'Calibri'
    run.font.size = Pt(9.5)
    run.font.bold = True
    run.font.color.rgb = RGBColor(255, 255, 255)

tools_data = [
    ("Telemetry SDK", "opentelemetry-api", "1.45.1", "Core OpenTelemetry interfaces, trace/metric context propagation, and span lifecycle."),
    ("Telemetry Runtime", "opentelemetry-sdk", "1.45.1", "TracerProvider, MeterProvider, batch processors, and resource definitions."),
    ("FastAPI Instrumentation", "opentelemetry-instrumentation-fastapi", "0.66b1", "Automatic HTTP request/response tracing, route identification, and status code tagging."),
    ("HTTP Client Instrumentation", "opentelemetry-instrumentation-httpx", "0.66b1", "Distributed context propagation and span creation for external climate API requests."),
    ("Logging Instrumentation", "opentelemetry-instrumentation-logging", "0.66b1", "Integration between standard Python logging and OpenTelemetry context."),
    ("OTLP Exporter", "opentelemetry-exporter-otlp-proto-http", "1.45.1", "Protocol Buffers over HTTP exporter dispatching traces to Jaeger at :4318/v1/traces."),
    ("Prometheus Exporter", "opentelemetry-exporter-prometheus", "0.66b1", "Bridges OpenTelemetry meter instruments into Prometheus format at /metrics."),
    ("Prometheus Client", "prometheus_client", "0.26.0", "Official client generating metric exposition format and registry storage."),
    ("Tracing Backend", "Jaeger All-in-One", "v1.60.0", "Standalone backend collecting OTLP spans, indexing traces, and UI at http://10.1.75.51:16686."),
    ("Metrics TSDB Backend", "Prometheus Server", "v3.15.0", "Standalone TSDB scraping http://10.1.75.51:3317/metrics with UI at http://10.1.75.51:9090."),
    ("Application Server", "FastAPI + Uvicorn", "0.141 / 0.52", "Asynchronous Web GIS backend serving API endpoints and interactive HUD at http://10.1.75.51:3317/.")
]

for row_idx, data in enumerate(tools_data, start=1):
    row = tools_table.rows[row_idx]
    bg_color = "FAFBFC" if row_idx % 2 == 1 else "FFFFFF"
    for col_idx, text in enumerate(data):
        cell = row.cells[col_idx]
        cell.width = widths[col_idx]
        set_cell_background(cell, bg_color)
        set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(9)
        if col_idx == 0:
            run.font.bold = True
            run.font.color.rgb = PRIMARY_COLOR
        elif col_idx in (1, 2):
            run.font.name = 'Consolas'
            run.font.size = Pt(8.5)
            run.font.color.rgb = DARK_GRAY
        else:
            run.font.color.rgb = DARK_GRAY

# ----------------- SECTION 3: SCREENSHOTS & TECHNICAL ANALYSIS -----------------
doc.add_page_break()
add_heading1("3. Verification Screenshots & Technical Analysis")
add_p("The implementation was rigorously verified across 7 distinct perspectives, demonstrating complete synchronization between the user interface, server logs, distributed traces, and time-series metrics. All screenshots were captured directly from the running project.")

# Figure 1
add_heading2("Figure 1: HydroPond AI Interactive Web GIS Interface (System Under Test)")
add_image_figure("screenshots/fig1_hydropond_gis_ui.png", "Figure 1: HydroPond AI Interactive Web GIS Interface (http://10.1.75.51:3317/)")
add_heading3("Detailed Description:")
add_p("Figure 1 displays the live user-facing Web GIS interface of HydroPond AI (http://10.1.75.51:3317/) executing a farmland parcel analysis near IIT Bhilai and the Shivnath River basin:")
add_bullet("The Leaflet map displays 1-meter elevation contour polylines (blue curves), the user-drawn agricultural land parcel (yellow polygon), the mathematically delineated upstream catchment watershed (blue shaded polygon), and the optimal pond excavation outlet marker.", bold_prefix="Spatial Overlays: ")
add_bullet("Harvestable Rainwater Volume is quantified at 7.28 Million Litres (ML) (7,277 m³ total monsoon runoff volume), estimated to guarantee water security for ~103 rural families for 180+ dry-season days. Optimal Pond Site is located at Lat 21.250448° N, Lon 81.299836° E at a bed elevation of 282m. Delineated catchment area is 2.08 ha (20,800 m²) with a mean slope of 3.93%. Recommended pond dimensions: 55.5m x 37.0m x 3.0m (4,366 m³ capacity).", bold_prefix="Hydrological HUD: ")
add_heading3("What this demonstrates:")
add_p("This screenshot confirms that the baseline Assignment 1 application is fully functional, producing real mathematical and geographical outputs that provide the foundation for our telemetry pipeline.")

# Figure 2
doc.add_page_break()
add_heading2("Figure 2: Jaeger Distributed Tracing — Search & Trace Catalog")
add_image_figure("screenshots/fig2_jaeger_traces_search.png", "Figure 2: Jaeger Distributed Tracing Search & Trace Catalog (http://10.1.75.51:16686/)")
add_heading3("Detailed Description:")
add_p("Figure 2 shows the Jaeger Web UI search dashboard (http://10.1.75.51:16686/search?service=hydrology-pond-system):")
add_bullet("The service selector correctly identifies hydrology-pond-system, confirming that the OpenTelemetry SDK successfully initialized and registered with the Jaeger OTLP collector on port 4318.", bold_prefix="Service Registration: ")
add_bullet("Displays trace executions over time, visually categorizing transaction durations across requests.", bold_prefix="Latency Scatter Plot (Top): ")
add_bullet("Captures incoming API transactions: (1) POST /api/analyze-area (Trace ID: ba71583037de6cb362bc151107e3eba5) with latency of 1.37 s (1369 ms) and 8 spans (matches Figure 1: 7.28 ML analysis and Figure 7 server log!); (2) GET /api/sample-contours (Trace ID: 0842a86...) with latency of 44.07 ms; (3) POST /api/analyze-area (Trace ID: 6c9318f0ab9b75bed2482275e6caab46) with latency of 1.21 s and 8 spans.", bold_prefix="Trace Catalog: ")
add_heading3("What this demonstrates:")
add_p("This confirms that OpenTelemetry captures every incoming API transaction, assigns unique distributed trace identifiers, and exports the transaction graphs to Jaeger without dropped spans or transmission failures.")

# Figure 3
doc.add_page_break()
add_heading2("Figure 3: Jaeger Deep Trace & Custom Domain Attributes (Waterfall View)")
add_image_figure("screenshots/fig3_jaeger_waterfall_attributes.png", "Figure 3: Jaeger Deep Trace & Custom Domain Attributes (Waterfall View)")
add_heading3("Detailed Description:")
add_p("Figure 3 displays the detailed span waterfall and call tree for a comprehensive contour analysis transaction (POST /analyzeContour, Trace ID: a622112a28f2b56608ff30ba65efd3dd), with an end-to-end execution duration of 4.88 s containing 44 total spans across 4 hierarchy levels:")
add_bullet("kml.parse (140.12 ms), dem.build (2.94 s rasterizing 86,390 grid cells using SciPy interpolation), terrain.pipeline (713.34 ms), terrain.priority_flood_fill (667.98 ms running the Wang-Liu heap priority flood), pond.select_and_delineate (36.97 ms scoring outlet cells and BFS graph traversal), and hydrology.calculate / hydrology.fetch_historical_rainfall (997.66 ms fetching Open-Meteo climate data).", bold_prefix="Span Latency Hierarchy: ")
add_bullet("Expanding hydrology.calculate reveals custom tags: hydrology.annual_rainfall_mm = 1595.4, hydrology.monsoon_rainfall_mm = 1356.1, hydrology.catchment_area_m2 = 54100 (5.41 ha), hydrology.mean_slope_pct = 4.26, and hydrology.household_water_days = 50048.", bold_prefix="Expanded Domain Attributes: ")
add_heading3("What this demonstrates:")
add_p("This is the core proof of deep manual instrumentation. Rather than merely showing black-box HTTP latency, OpenTelemetry breaks down internal algorithmic execution and embeds domain-specific hydrology calculations directly inside the trace span.")

# Figure 4
doc.add_page_break()
add_heading2("Figure 4: Jaeger Detailed Span Breakdown & Timeline")
add_image_figure("screenshots/fig4_jaeger_span_breakdown.png", "Figure 4: Jaeger Detailed Span Breakdown & Execution Timeline")
add_heading3("Detailed Description:")
add_p("Figure 4 displays the complete collapsed timeline overview across the 4.88 s execution window:")
add_bullet("SciPy interpolation in dem.build occupies the first 2.94 s of the transaction, followed by depression filling at 667.98 ms, instantaneous pond selection (36.97 ms), and network I/O for historical meteorological data fetching (997.34 ms).", bold_prefix="Relative Timing Breakdown: ")
add_bullet("Child spans correctly reflect parent-child context propagation, demonstrating that the W3C trace context was maintained across asynchronous execution boundaries.", bold_prefix="Context Propagation: ")
add_heading3("What this demonstrates:")
add_p("Demonstrates execution profiling and bottleneck identification. Developers can instantly identify that optimizing the SciPy DEM interpolator or caching meteorological data would yield the highest performance gains.")

# Figure 5
doc.add_page_break()
add_heading2("Figure 5: Prometheus Time-Series Metrics Chart (PromQL Query)")
add_image_figure("screenshots/fig5_prometheus_metrics_graph.png", "Figure 5: Prometheus Time-Series Metrics Chart (http://10.1.75.51:9090/)")
add_heading3("Detailed Description:")
add_p("Figure 5 displays the Prometheus Web UI dashboard (http://10.1.75.51:9090/graph) executing an instant PromQL query on our custom metric: hydrology_requests_total:")
add_bullet("Purple line: hydrology_requests_total{endpoint=\"/api/analyze-area\", ...} increments step-wise from 3.00 to 4.00, and then to 5.00 as multiple farmland parcel requests are processed.", bold_prefix="Parcel Requests: ")
add_bullet("Green line: hydrology_requests_total{cache=\"hit\", endpoint=\"/api/sample-contours\", ...} shows contour preview requests served directly from the in-memory cache, stepping from 2.00 to 3.00.", bold_prefix="Cache Hits: ")
add_bullet("Red line: hydrology_requests_total{endpoint=\"/analyzeContour\", ...} tracks uploaded KML contour maps processed by the system (steady at 1.00).", bold_prefix="KML Uploads: ")
add_heading3("What this demonstrates:")
add_p("Proves successful metric instrument creation, collection, exposition via http://10.1.75.51:3317/metrics, and periodic time-series scraping by Prometheus. It demonstrates that OpenTelemetry provides quantitative operational insight into endpoint usage patterns and caching efficiency.")

# Figure 6
doc.add_page_break()
add_heading2("Figure 6: Prometheus Scrape Target Health Status")
add_image_figure("screenshots/fig6_prometheus_target_health.png", "Figure 6: Prometheus Scrape Target Health Status (http://10.1.75.51:9090/targets)")
add_heading3("Detailed Description:")
add_p("Figure 6 displays the Prometheus Target Health verification console (http://10.1.75.51:9090/targets?search=):")
add_bullet("hydrology-pond-system (1 / 1 targets UP, indicated by the green status glyph).", bold_prefix="Scrape Pool: ")
add_bullet("http://10.1.75.51:3317/metrics", bold_prefix="Target Endpoint: ")
add_bullet("instance=\"10.1.75.51:3317\", job=\"hydrology-pond-system\".", bold_prefix="Attached Labels: ")
add_bullet("State is UP (bright green badge). Last scrape executed 42.467 s ago with an ultra-low scrape duration of only 16 ms, confirming negligible telemetry overhead. Error field is completely empty.", bold_prefix="Health Indicators: ")
add_heading3("What this demonstrates:")
add_p("This screenshot proves that the Prometheus pull-based telemetry pipeline is 100% operational. The OpenTelemetry Prometheus exporter actively serves metric formats adhering to the OpenMetrics standard without timeouts or parsing failures.")

# Figure 7
doc.add_page_break()
add_heading2("Figure 7: Context-Correlated Structured Application Server Logs")
add_image_figure("screenshots/fig7_trace_correlated_logs.png", "Figure 7: Context-Correlated Structured Application Server Logs (tail -n 20 logs/app.log)")
add_heading3("Detailed Description:")
add_p("Figure 7 displays the actual terminal inspection (tail -n 20 logs/app.log) of the live HydroPond AI server logs running at http://10.1.75.51:3317/:")
add_bullet("Each log line contains the W3C standard trace_id (32 hex characters) and span_id (16 hex characters) automatically injected by our custom TraceContextFormatter.", bold_prefix="Trace Context Formatting: ")
add_bullet("In log line 21:23:01, the system records 'catchment=2.08ha, harvest_vol=7.28ML, elapsed=1369ms' with trace_id=ba71583037de6cb362bc151107e3eba5. This matches Figure 1 (UI showing 2.08 ha catchment and 7.28 ML volume) and Figure 2 (Jaeger UI listing Trace ID ba71583037de6cb362bc151107e3eba5 at 1.37 s duration)!", bold_prefix="Direct Cross-Pillar Correlation Proof: ")
add_bullet("In log line 21:10:02, trace_id=6c9318f0ab9b75bed2482275e6caab46 matches the third trace visible in Jaeger Search (Figure 2). In log line 18:27:21, trace_id=a622112a28f2b56608ff30ba65efd3dd matches the exact deep-trace waterfall dissected in Jaeger (Figure 3 and Figure 4).", bold_prefix="Correlated KML Runs: ")
add_heading3("What this demonstrates:")
add_p("Provides absolute proof of the third pillar of observability: Context-Correlated Logging. An engineer inspecting a log message can instantly copy the trace_id and paste it into Jaeger to see the full flamegraph and micro-timing of that request.")

# ----------------- SECTION 4: UNDERSTANDING OF COLLECTED DATA -----------------
doc.add_page_break()
add_heading1("4. Understanding of the Collected Data & Benefits for System Monitoring")

add_heading2("4.1 Latency Profiling & Algorithmic Bottleneck Localization")
add_p("From the Jaeger waterfall trace in Figure 3, we obtain a precise time budget for the 4.88 s execution:")
add_bullet("SciPy bivariate cubic/linear interpolation over 86,390 cells takes 2.94 s. This identifies griddata interpolation as the primary computational bottleneck. Optimization action: Pre-compiling Delaunay triangulation or utilizing GPU-accelerated CuPy interpolation.", bold_prefix="1. DEM Rasterization (dem.build, 60.2% of total time): ")
add_bullet("The outgoing HTTP request to Open-Meteo took 997.34 ms. Optimization action: Caching daily rainfall sums in an in-memory Redis layer keyed by coordinate geohash to eliminate remote round trips.", bold_prefix="2. External API Latency (hydrology.fetch_historical_rainfall, 20.4% of total time): ")
add_bullet("The Barnes/Wang-Liu heap algorithm took 667.98 ms on an 86,390-cell grid. Optimization action: Implementing early termination or hierarchical grid coarsening.", bold_prefix="3. Depression Filling (terrain.priority_flood_fill, 13.7% of total time): ")
add_bullet("Heuristic candidate evaluation and BFS upstream graph traversal took only 36.97 ms, confirming high algorithmic efficiency.", bold_prefix="4. Pond Site Selection & Delineation (pond.select_and_delineate, < 1% of total time): ")

add_heading2("4.2 Proactive Capacity Planning & Operational Reliability")
add_p("Prometheus time-series metrics enable data-driven capacity decisions:")
add_bullet("Figure 5 proves that 60% of /api/sample-contours requests are served from cache in < 45 ms, protecting backend memory from redundant re-computations.", bold_prefix="Throughput & Cache Efficiency: ")
add_bullet("Tracking cumulative volume via hydrology_water_volume_harvestable_m3 allows regional planners to monitor total water capacity planned across multi-village jurisdictions.", bold_prefix="Water Volume Aggregates: ")
add_bullet("Setting automated Prometheus alert rules on http_requests_total error rates (5xx > 1%) and hydrology_algorithm_duration_seconds (p95 > 3 s) allows automated alerting before users experience degraded service.", bold_prefix="SLA & Health Monitoring: ")

add_heading2("4.3 Root-Cause Analysis via Cross-Pillar Correlation")
add_p("Prior to OpenTelemetry, troubleshooting an exception required manually cross-referencing server timestamps with client bug reports. With correlated logging and tracing:")
add_bullet("If an invalid polygon geometry causes a topology error, the log line prints the exact trace_id.")
add_bullet("Clicking the trace in Jaeger reveals the exact polygon vertices (request.polygon_vertices), the elevation grid dimension, and the exact stack trace recorded by span.record_exception(exc) on the failed span.")

# ----------------- SECTION 5: VIVA PREPARATION -----------------
add_heading1("5. VIVA Examination Preparation & Key Concepts")
add_p("The following table contains essential concepts and model answers for evaluation during the viva examination:")

viva_table = doc.add_table(rows=6, cols=2)
viva_table.alignment = WD_TABLE_ALIGNMENT.CENTER
v_headers = ["Viva Question", "Model Technical Answer"]
v_widths = [Inches(2.2), Inches(4.47)]

v_hdr = viva_table.rows[0]
for idx, text in enumerate(v_headers):
    c = v_hdr.cells[idx]
    c.width = v_widths[idx]
    set_cell_background(c, HEADER_BG_HEX)
    set_cell_margins(c, top=80, bottom=80, left=80, right=80)
    p = c.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run(text)
    r.font.name = 'Calibri'
    r.font.size = Pt(9.5)
    r.font.bold = True
    r.font.color.rgb = RGBColor(255, 255, 255)

viva_qa = [
    ("Why use OpenTelemetry instead of writing print statements or loggers?",
     "Print statements and logs lack distributed causality. OpenTelemetry standardizes context propagation using W3C Trace Context headers, linking distributed spans across microservices and providing structured metrics that can be queried mathematically with PromQL, rather than parsed as raw text."),
    ("What is the difference between OpenTelemetry, Jaeger, and Prometheus?",
     "OpenTelemetry is the instrumentation framework that collects observability data. Jaeger is a distributed tracing backend that visualizes call trees and waterfalls. Prometheus is a time-series database that periodically pulls numeric metrics for dashboard graphing and alerting."),
    ("What is the difference between a Trace and a Span?",
     "A Trace represents the entire journey of a single request through the system from start to finish. A Span represents a single unit of contiguous work within that trace (e.g. dem.build), with a name, timestamps, attributes, and optional events."),
    ("How did you correlate logs with traces in your project?",
     "We implemented a custom TraceContextFormatter that extracts trace_id and span_id from trace.get_current_span().get_span_context() during log formatting. This guarantees that every log output in app.log contains the exact 128-bit Trace ID displayed in Jaeger."),
    ("What was the biggest performance bottleneck discovered by tracing?",
     "The Jaeger flamegraph revealed that SciPy elevation grid interpolation (dem.build) accounted for 60.2% (2.94 s) of the total 4.88 s transaction, whereas pond selection and catchment graph traversal took only 36.97 ms.")
]

for row_idx, (q, a) in enumerate(viva_qa, start=1):
    row = viva_table.rows[row_idx]
    bg_color = "FAFBFC" if row_idx % 2 == 1 else "FFFFFF"
    for col_idx, text in enumerate([q, a]):
        cell = row.cells[col_idx]
        cell.width = v_widths[col_idx]
        set_cell_background(cell, bg_color)
        set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(9)
        if col_idx == 0:
            run.font.bold = True
            run.font.color.rgb = PRIMARY_COLOR
        else:
            run.font.italic = True
            run.font.color.rgb = DARK_GRAY

# ----------------- SECTION 6: CONCLUSION -----------------
add_heading1("6. Conclusion")
add_p("The integration of OpenTelemetry into the HydroPond AI Village Pond Planning System deployed at http://10.1.75.51:3317/ was completed successfully. The application captures distributed traces with custom domain-specific hydrological metadata, exposes Prometheus metrics via http://10.1.75.51:3317/metrics, and correlates application logs using W3C standard trace identifiers.")
add_p("The implementation was verified using real geospatial contour datasets and live map interactions across 7 distinct verification perspectives, proving that OpenTelemetry transforms complex hydrological computational workflows from opaque black boxes into transparent, observable, and production-ready distributed services.")

output_file = "/home/karthik/Desktop/Pond-Catchment-Plan/OpenTelemetry_Implementation_Report.docx"
doc.save(output_file)
print(f"Successfully generated DOCX report at: {output_file}")
