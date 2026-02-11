"""Microservice topology definition for the simulated infrastructure."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ServiceInfo:
    name: str
    depends_on: tuple[str, ...]
    default_port: int
    description: str


# ── 8 Realistic Microservices ───────────────────────────────────

SERVICE_TOPOLOGY: dict[str, ServiceInfo] = {
    "api-gateway": ServiceInfo(
        name="api-gateway",
        depends_on=("checkout-service", "user-auth", "inventory-service"),
        default_port=8080,
        description="NGINX-based API gateway routing external traffic to internal services",
    ),
    "checkout-service": ServiceInfo(
        name="checkout-service",
        depends_on=("payment-gateway", "inventory-service", "postgres-db", "redis-cache"),
        default_port=8081,
        description="Handles cart checkout, order creation, and payment orchestration",
    ),
    "payment-gateway": ServiceInfo(
        name="payment-gateway",
        depends_on=("postgres-db",),
        default_port=8082,
        description="Processes credit card charges and manages payment state",
    ),
    "inventory-service": ServiceInfo(
        name="inventory-service",
        depends_on=("postgres-db", "redis-cache"),
        default_port=8083,
        description="Manages product stock levels and reservation locks",
    ),
    "user-auth": ServiceInfo(
        name="user-auth",
        depends_on=("postgres-db", "redis-cache"),
        default_port=8084,
        description="JWT-based authentication and session management",
    ),
    "notification-service": ServiceInfo(
        name="notification-service",
        depends_on=("redis-cache",),
        default_port=8085,
        description="Sends order confirmation emails and push notifications",
    ),
    "postgres-db": ServiceInfo(
        name="postgres-db",
        depends_on=(),
        default_port=5432,
        description="Primary PostgreSQL database for transactional data",
    ),
    "redis-cache": ServiceInfo(
        name="redis-cache",
        depends_on=(),
        default_port=6379,
        description="Redis cache for sessions, rate limiting, and hot data",
    ),
}


def get_dependents(service_name: str) -> list[str]:
    """Return services that depend on the given service (upstream callers)."""
    return [
        name
        for name, info in SERVICE_TOPOLOGY.items()
        if service_name in info.depends_on
    ]


def get_dependencies(service_name: str) -> list[str]:
    """Return services that the given service depends on (downstream deps)."""
    info = SERVICE_TOPOLOGY.get(service_name)
    if info is None:
        return []
    return list(info.depends_on)


ALL_SERVICE_NAMES = list(SERVICE_TOPOLOGY.keys())
