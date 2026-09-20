"""Метрики Prometheus. Каждая метрика помечена идентификатором ноды,
поэтому в Grafana видно, как балансировщик распределяет запросы."""
from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.routing import Mount

from app.instance import hostname, instance_id

REQUESTS = Counter(
    "t2_http_requests_total",
    "Число HTTP-запросов, обработанных нодой",
    ["instance_id", "method", "endpoint", "status"],
)

DURATION = Histogram(
    "t2_http_request_duration_seconds",
    "Длительность обработки запроса нодой",
    ["instance_id", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

INFO = Gauge(
    "t2_instance_info",
    "Сведения об экземпляре приложения",
    ["instance_id", "hostname"],
)


def endpoint_label(scope) -> str:
    """Метка маршрута, а не сырого пути.

    Значения параметров сворачиваются обратно в шаблон: путь
    /api/v1/coverage/probe/Казань превращается в /api/v1/coverage/probe/{city}.
    Иначе каждый город создавал бы отдельный временной ряд.
    """
    path = scope.get("path") or "/"
    route = scope.get("route")
    if isinstance(route, Mount):
        return route.path
    if route is None:
        # Отдача статики не всегда проставляет маршрут в scope.
        return "/static/*" if path.startswith("/static/") else "unmatched"

    params = scope.get("path_params") or {}
    if not params:
        return path

    placeholder = {str(value): name for name, value in params.items()}
    return "/".join(
        "{" + placeholder[segment] + "}" if segment in placeholder else segment
        for segment in path.split("/")
    )


def observe(method: str, endpoint: str, status: int, seconds: float) -> None:
    node = instance_id()
    REQUESTS.labels(node, method, endpoint, str(status)).inc()
    DURATION.labels(node, endpoint).observe(seconds)


def mark_instance_up() -> None:
    INFO.labels(instance_id(), hostname()).set(1)


def render() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
