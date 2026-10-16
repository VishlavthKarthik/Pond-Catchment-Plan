"""OpenTelemetry instrumentation and observability module for HydroPond AI.

Provides:
- Distributed Tracing (TracerProvider, OTLP HTTP Exporter to Jaeger on port 4318)
- Application & Business Metrics (MeterProvider, PrometheusMetricReader, custom histograms & counters)
- Metrics HTTP Endpoint (/metrics for Prometheus scraping)
- Context-Correlated Structured Logging (injects W3C trace_id and span_id into log records)
- Automatic Instrumentation for FastAPI, HTTPX, and Python Logging
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any, Optional

from fastapi import FastAPI, Response
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

# ---------------------------------------------------------------------------
# Configuration & Constants
# ---------------------------------------------------------------------------

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "hydrology-pond-system")
SERVICE_VERSION = os.getenv("OTEL_SERVICE_VERSION", "2.0.0")
ENVIRONMENT = os.getenv("OTEL_ENVIRONMENT", "production")
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")

# ---------------------------------------------------------------------------
# Resource Definition
# ---------------------------------------------------------------------------

resource = Resource.create(
    {
        "service.name": SERVICE_NAME,
        "service.version": SERVICE_VERSION,
        "deployment.environment": ENVIRONMENT,
        "service.instance.id": f"{SERVICE_NAME}-{os.getpid()}",
    }
)

# ---------------------------------------------------------------------------
# Logging Setup with Trace Context Injection
# ---------------------------------------------------------------------------


class TraceContextFormatter(logging.Formatter):
    """Custom logging formatter injecting W3C trace_id and span_id into logs."""

    def format(self, record: logging.LogRecord) -> str:
        span = trace.get_current_span()
        span_context = span.get_span_context() if span else None
        if span_context and span_context.is_valid:
            record.trace_id = trace.format_trace_id(span_context.trace_id)
            record.span_id = trace.format_span_id(span_context.span_id)
        else:
            record.trace_id = "0" * 32
            record.span_id = "0" * 16
        return super().format(record)


def setup_correlated_logging():
    """Configure system-wide logging with trace correlation and file output."""
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, "app.log")

    log_format = (
        "[%(asctime)s] [%(levelname)s] [trace_id=%(trace_id)s span_id=%(span_id)s] "
        "[%(name)s]: %(message)s"
    )
    formatter = TraceContextFormatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Console handler
    has_console = any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root_logger.handlers)
    if not has_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    else:
        for h in root_logger.handlers:
            if not isinstance(h, logging.FileHandler):
                h.setFormatter(formatter)

    # File handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Instrument python logging with OpenTelemetry
    LoggingInstrumentor().instrument(set_logging_format=False)


# ---------------------------------------------------------------------------
# Tracing Setup
# ---------------------------------------------------------------------------

tracer_provider = TracerProvider(resource=resource)

# Add OTLP HTTP Span Exporter (sending traces to Jaeger OTLP receiver at 4318)
try:
    otlp_exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT)
    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)
except Exception as e:
    logging.warning(f"Could not initialize OTLP Span Exporter: {e}")

# Also add ConsoleSpanExporter if OTEL_DEBUG=1
if os.getenv("OTEL_DEBUG", "0") == "1":
    tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer("hydrology.planner", SERVICE_VERSION)

# ---------------------------------------------------------------------------
# Metrics Setup
# ---------------------------------------------------------------------------

# Prometheus Metric Reader registers with prometheus_client default registry
prometheus_reader = PrometheusMetricReader()
meter_provider = MeterProvider(resource=resource, metric_readers=[prometheus_reader])
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter("hydrology.metrics", SERVICE_VERSION)

# Custom Metric Instruments
requests_counter = meter.create_counter(
    name="hydrology_requests_total",
    description="Total count of analysis requests handled by the system",
    unit="1",
)

active_requests_gauge = meter.create_up_down_counter(
    name="hydrology_active_requests",
    description="Current number of in-flight active analysis requests",
    unit="1",
)

algorithm_duration_histogram = meter.create_histogram(
    name="hydrology_algorithm_duration_seconds",
    description="Execution duration of hydrological and terrain processing algorithms",
    unit="s",
)

dem_grid_cells_histogram = meter.create_histogram(
    name="hydrology_dem_grid_cells_total",
    description="Total elevation grid cells rasterized in DEM generation",
    unit="1",
)

watershed_cells_histogram = meter.create_histogram(
    name="hydrology_watershed_cells_total",
    description="Total cells included in delineated watershed catchment",
    unit="1",
)

water_volume_harvestable_histogram = meter.create_histogram(
    name="hydrology_water_volume_harvestable_m3",
    description="Expected harvestable rainwater runoff volume in cubic meters",
    unit="m3",
)

# ---------------------------------------------------------------------------
# App Instrumentation Function
# ---------------------------------------------------------------------------


def instrument_app(app: FastAPI):
    """Attach OpenTelemetry instrumentation, middlewares, and /metrics to FastAPI."""
    setup_correlated_logging()

    # Auto-instrument outgoing HTTP requests (e.g. Open-Meteo climate API)
    HTTPXClientInstrumentor().instrument()

    # Auto-instrument FastAPI incoming requests
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        excluded_urls="health,metrics,static/.*",
    )

    # Expose Prometheus /metrics endpoint
    @app.get("/metrics", summary="OpenTelemetry & Prometheus Observability Metrics")
    async def metrics_endpoint():
        """Scrape endpoint for Prometheus server."""
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    logging.info(
        f"OpenTelemetry initialized: service='{SERVICE_NAME}', "
        f"otlp='{OTLP_ENDPOINT}', metrics_path='/metrics'"
    )


# Export convenience handles
__all__ = [
    "tracer",
    "meter",
    "instrument_app",
    "requests_counter",
    "active_requests_gauge",
    "algorithm_duration_histogram",
    "dem_grid_cells_histogram",
    "watershed_cells_histogram",
    "water_volume_harvestable_histogram",
]
