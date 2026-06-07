"""
Observabilidade — OpenTelemetry (tracing) + Prometheus (métricas).

Tracing:  instrumenta chamadas ao LLM e às tools com spans OTel.
          Exporta para console (dev) e arquivo data/logs/traces.log.

Métricas: expõe contadores e histogramas via prometheus-client.
          Consumidos pelo endpoint GET /metrics da API.
"""

import functools
import logging
import time
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# ── File exporter (escreve traces em data/logs/traces.log) ─────────────────────

class FileSpanExporter(SpanExporter):
    """Exporta spans OTel para um arquivo de log legível."""

    def __init__(self, path: str = "data/logs/traces.log"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path

    def export(self, spans):
        with open(self.path, "a", encoding="utf-8") as f:
            for span in spans:
                duration_ms = (span.end_time - span.start_time) / 1_000_000
                status = span.status.status_code.name
                attrs = dict(span.attributes or {})
                f.write(
                    f"[SPAN] {span.name} | "
                    f"status={status} | "
                    f"duration={duration_ms:.1f}ms | "
                    f"attrs={attrs}\n"
                )
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


# ── Configuração do tracer ─────────────────────────────────────────────────────

def _setup_tracer() -> trace.Tracer:
    resource = Resource.create({"service.name": "compliance-viewer"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(FileSpanExporter()))
    trace.set_tracer_provider(provider)
    return trace.get_tracer("compliance-viewer")


tracer = _setup_tracer()


# ── Decorator @traced ──────────────────────────────────────────────────────────

def traced(operation_name: str = None, **extra_attrs):
    """
    Decorator que envolve uma função com um span OTel.

    Registra: nome da operação, duração, status (ok/erro) e atributos extras.

    Uso:
        @traced("llm.invoke", model="gpt-4o")
        def invoke(...): ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = operation_name or func.__name__
            with tracer.start_as_current_span(name) as span:
                for k, v in extra_attrs.items():
                    span.set_attribute(k, str(v))
                start = time.time()
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("status", "ok")
                    return result
                except Exception as exc:
                    span.set_attribute("status", "error")
                    span.set_attribute("error.message", str(exc))
                    raise
                finally:
                    span.set_attribute("duration_ms", round((time.time() - start) * 1000, 1))
        return wrapper
    return decorator


# ── Métricas Prometheus ────────────────────────────────────────────────────────

# Contadores de análise
ANALYSES_TOTAL = Counter(
    "compliance_analyses_total",
    "Total de análises realizadas",
    ["result", "client_profile"],
)

# Histograma de duração
ANALYSIS_DURATION = Histogram(
    "compliance_analysis_duration_seconds",
    "Duração das análises em segundos",
    buckets=[1, 5, 10, 20, 30, 60],
)

# Decisões do agente
AGENT_DECISIONS = Counter(
    "compliance_agent_decisions_total",
    "Total de decisões tomadas pelo agente",
    ["decision"],
)

# Taxa de automação (atualizada a cada decisão do agente)
AUTOMATION_RATE = Gauge(
    "compliance_automation_rate",
    "Taxa de automação atual (decisões automáticas / total)",
)

# Contadores de tokens (quando disponível no response)
TOKENS_TOTAL = Counter(
    "compliance_llm_tokens_total",
    "Total de tokens usados nas chamadas ao LLM",
    ["operation"],
)

# ── Funções auxiliares de métricas ─────────────────────────────────────────────

_decisions_auto = 0
_decisions_total = 0


def record_analysis(is_compliant: bool, client_profile: str, duration_seconds: float):
    """Registra métricas de uma análise concluída."""
    result = "compliant" if is_compliant else "non_compliant"
    ANALYSES_TOTAL.labels(result=result, client_profile=client_profile).inc()
    ANALYSIS_DURATION.observe(duration_seconds)


def record_agent_decision(decision: str):
    """Registra a decisão do agente e atualiza a taxa de automação."""
    global _decisions_auto, _decisions_total
    AGENT_DECISIONS.labels(decision=decision).inc()
    _decisions_total += 1
    if decision in ("approved", "rejected"):
        _decisions_auto += 1
    if _decisions_total > 0:
        AUTOMATION_RATE.set(_decisions_auto / _decisions_total)