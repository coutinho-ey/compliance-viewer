"""
Observabilidade — OpenTelemetry (tracing) + Prometheus (métricas).

Tracing:  spans escritos em data/logs/traces.log via FileSpanExporter.
Métricas: contadores e histogramas expostos em GET /metrics da API.

Design deliberado: métricas registradas no processo da API apenas.
O monitor usa o mesmo tracing via arquivo (process-independent).
"""

import functools
import logging
import time
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

LOGS_DIR = Path("data/logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)


# ── File Span Exporter ─────────────────────────────────────────────────────────

class FileSpanExporter(SpanExporter):
    """Escreve cada span em data/logs/traces.log — sem dependência de rede."""

    def __init__(self, path: str = "data/logs/traces.log"):
        self.path = path

    def export(self, spans):
        with open(self.path, "a", encoding="utf-8") as f:
            for span in spans:
                duration_ms = (span.end_time - span.start_time) / 1_000_000
                attrs = dict(span.attributes or {})
                status = span.status.status_code.name
                f.write(
                    f"[TRACE] {span.name} | status={status} | "
                    f"duration={duration_ms:.1f}ms | {attrs}\n"
                )
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


# ── Tracer ─────────────────────────────────────────────────────────────────────

def _build_tracer() -> trace.Tracer:
    resource = Resource.create({"service.name": "compliance-viewer"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(FileSpanExporter()))
    trace.set_tracer_provider(provider)
    return trace.get_tracer("compliance-viewer")


tracer = _build_tracer()


# ── Decorator @traced ──────────────────────────────────────────────────────────

def traced(operation_name: str = None):
    """
    Decorator que envolve uma função com um span OTel.
    Registra: nome da operação, duração e status (ok/error).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = operation_name or func.__name__
            with tracer.start_as_current_span(name) as span:
                start = time.time()
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("status", "ok")
                    return result
                except Exception as exc:
                    span.set_attribute("status", "error")
                    span.set_attribute("error", str(exc))
                    raise
                finally:
                    span.set_attribute("duration_ms", round((time.time() - start) * 1000, 1))
        return wrapper
    return decorator


# ── Métricas Prometheus ────────────────────────────────────────────────────────

ANALYSES_TOTAL = Counter(
    "compliance_analyses_total",
    "Total de análises realizadas via API",
    ["result", "client_profile"],
)

ANALYSIS_DURATION = Histogram(
    "compliance_analysis_duration_seconds",
    "Duração das análises em segundos",
    buckets=[1, 5, 10, 20, 30, 60],
)

AUTOMATION_RATE = Gauge(
    "compliance_automation_rate",
    "Taxa de automação acumulada (aprovados+rejeitados / total)",
)

TOKENS_TOTAL = Counter(
    "compliance_llm_tokens_total",
    "Total de tokens usados nas chamadas ao LLM",
    ["operation"],
)

# ── Helpers ────────────────────────────────────────────────────────────────────

_auto = 0
_total = 0


def record_analysis(is_compliant: bool, client_profile: str, duration_seconds: float):
    """Registra uma análise concluída via API."""
    global _auto, _total
    result = "compliant" if is_compliant else "non_compliant"
    ANALYSES_TOTAL.labels(result=result, client_profile=client_profile).inc()
    ANALYSIS_DURATION.observe(duration_seconds)
    _total += 1
    _auto += 1
    AUTOMATION_RATE.set(_auto / _total)