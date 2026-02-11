"""Unit tests for src/data/topology.py."""

from __future__ import annotations

from src.data.topology import (
    ALL_SERVICE_NAMES,
    SERVICE_TOPOLOGY,
    ServiceInfo,
    get_dependencies,
    get_dependents,
)


class TestServiceTopology:
    def test_has_8_services(self):
        assert len(SERVICE_TOPOLOGY) == 8

    def test_all_service_names_list(self):
        assert len(ALL_SERVICE_NAMES) == 8
        assert "api-gateway" in ALL_SERVICE_NAMES
        assert "checkout-service" in ALL_SERVICE_NAMES
        assert "postgres-db" in ALL_SERVICE_NAMES

    def test_service_info_structure(self):
        info = SERVICE_TOPOLOGY["api-gateway"]
        assert isinstance(info, ServiceInfo)
        assert info.name == "api-gateway"
        assert info.default_port == 8080
        assert len(info.description) > 0

    def test_postgres_has_no_dependencies(self):
        info = SERVICE_TOPOLOGY["postgres-db"]
        assert info.depends_on == ()

    def test_redis_has_no_dependencies(self):
        info = SERVICE_TOPOLOGY["redis-cache"]
        assert info.depends_on == ()

    def test_checkout_depends_on_postgres(self):
        info = SERVICE_TOPOLOGY["checkout-service"]
        assert "postgres-db" in info.depends_on


class TestGetDependents:
    def test_postgres_dependents(self):
        dependents = get_dependents("postgres-db")
        assert "checkout-service" in dependents
        assert "payment-gateway" in dependents
        assert "inventory-service" in dependents
        assert "user-auth" in dependents

    def test_redis_dependents(self):
        dependents = get_dependents("redis-cache")
        assert "checkout-service" in dependents
        assert "notification-service" in dependents

    def test_leaf_service_no_dependents(self):
        dependents = get_dependents("api-gateway")
        assert len(dependents) == 0

    def test_unknown_service_empty(self):
        dependents = get_dependents("nonexistent")
        assert dependents == []


class TestGetDependencies:
    def test_checkout_dependencies(self):
        deps = get_dependencies("checkout-service")
        assert "payment-gateway" in deps
        assert "postgres-db" in deps
        assert "redis-cache" in deps

    def test_postgres_no_dependencies(self):
        deps = get_dependencies("postgres-db")
        assert deps == []

    def test_unknown_service_empty(self):
        deps = get_dependencies("nonexistent")
        assert deps == []