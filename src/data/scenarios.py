"""Four failure scenario generators producing correlated logs, metrics, and deployments."""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional

from src.core.models import (
    Alert,
    ChangeType,
    DeploymentEvent,
    LogEntry,
    MetricDataPoint,
    MockDataSet,
    ServiceName,
    Severity,
)
from src.data.topology import SERVICE_TOPOLOGY, get_dependents


# ── Helpers ──────────────────────────────────────────────────────


def _ts(base: datetime, delta_minutes: float) -> datetime:
    return base + timedelta(minutes=delta_minutes)


def _normal_metric(
    rng: random.Random,
    service: str,
    metric: str,
    base: datetime,
    minutes: int,
    mean: float,
    std: float,
    interval_seconds: int = 60,
) -> list[MetricDataPoint]:
    points = []
    for i in range(0, minutes * 60, interval_seconds):
        points.append(
            MetricDataPoint(
                timestamp=base + timedelta(seconds=i),
                service=ServiceName(service),
                metric_name=metric,
                value=max(0, rng.gauss(mean, std)),
            )
        )
    return points


# ── Base Scenario ────────────────────────────────────────────────


class BaseScenario(ABC):
    name: str

    @abstractmethod
    def generate(
        self,
        seed: int = 42,
        severity: str = "critical",
        incident_time: Optional[datetime] = None,
    ) -> MockDataSet:
        ...


# ── 1. Latent Configuration Bug ─────────────────────────────────


class LatentConfigBugScenario(BaseScenario):
    """Config deployment to checkout-service 15 min before latency spike.

    Story: A DB connection pool config change reduces max_connections from 100
    to 10.  Under load the pool exhausts, causing connection timeouts and
    p99 latency spikes on checkout-service.
    """

    name = "latent_config_bug"

    def generate(
        self,
        seed: int = 42,
        severity: str = "critical",
        incident_time: Optional[datetime] = None,
    ) -> MockDataSet:
        rng = random.Random(seed)
        now = incident_time or datetime.utcnow()
        deploy_time = _ts(now, -15)
        window_start = _ts(now, -30)

        logs: list[LogEntry] = []
        metrics: list[MetricDataPoint] = []
        deployments: list[DeploymentEvent] = []

        # ── Deployment event (T-15 min) ─────────────────────────
        deployments.append(
            DeploymentEvent(
                deploy_id=f"deploy-{rng.randint(1000,9999)}",
                timestamp=deploy_time,
                service=ServiceName.CHECKOUT_SERVICE,
                change_type=ChangeType.CONFIG_CHANGE,
                description="Updated db_pool_config: max_connections 100 -> 10",
                commit_sha=f"{rng.getrandbits(160):040x}"[:12],
                author="platform-team",
            )
        )

        # ── Normal metrics before incident (T-30 to T-5) ───────
        for svc in ["checkout-service", "api-gateway", "payment-gateway"]:
            metrics.extend(
                _normal_metric(rng, svc, "p99_latency_ms", window_start, 25, 120, 20)
            )
            metrics.extend(
                _normal_metric(rng, svc, "cpu_percent", window_start, 25, 35, 8)
            )

        # ── Latency spike on checkout-service (T-5 to T+5) ─────
        for i in range(-5, 6):
            t = _ts(now, i)
            spike = 200 + abs(i - 0) * 50  # peaks at T=0
            latency = 2000 - spike if i != 0 else 2100 + rng.uniform(-50, 50)
            metrics.append(
                MetricDataPoint(
                    timestamp=t,
                    service=ServiceName.CHECKOUT_SERVICE,
                    metric_name="p99_latency_ms",
                    value=max(latency, 800),
                )
            )
            # Connections saturated
            metrics.append(
                MetricDataPoint(
                    timestamp=t,
                    service=ServiceName.CHECKOUT_SERVICE,
                    metric_name="connections_active",
                    value=10.0,  # maxed out at new limit
                )
            )

        # ── API gateway upstream errors ─────────────────────────
        for i in range(-3, 6):
            metrics.append(
                MetricDataPoint(
                    timestamp=_ts(now, i),
                    service=ServiceName.API_GATEWAY,
                    metric_name="error_rate",
                    value=rng.uniform(0.05, 0.15),
                )
            )

        # ── Log entries ─────────────────────────────────────────
        # Normal logs (T-30 to T-5)
        for _ in range(rng.randint(40, 60)):
            logs.append(
                LogEntry(
                    timestamp=_ts(window_start, rng.uniform(0, 25)),
                    service=ServiceName.CHECKOUT_SERVICE,
                    level="INFO",
                    message=f"Order processed successfully. trace_id={rng.randint(10000,99999)}",
                    trace_id=f"trace-{rng.randint(10000,99999)}",
                )
            )

        # DB connection timeout errors around incident
        for i in range(rng.randint(20, 35)):
            t = _ts(now, rng.uniform(-3, 5))
            trace = f"trace-{rng.randint(10000,99999)}"
            logs.append(
                LogEntry(
                    timestamp=t,
                    service=ServiceName.CHECKOUT_SERVICE,
                    level="ERROR",
                    message=f"DB connection timeout after 5000ms — pool exhausted (active=10/10)",
                    trace_id=trace,
                    stack_trace=(
                        "java.sql.SQLTransientConnectionException: "
                        "HikariPool-1 - Connection is not available, request timed out after 5000ms.\n"
                        "\tat com.zaxxer.hikari.pool.HikariPool.createTimeoutException(HikariPool.java:696)\n"
                        "\tat com.zaxxer.hikari.pool.HikariPool.getConnection(HikariPool.java:197)\n"
                        "\tat com.checkout.service.OrderController.createOrder(OrderController.java:45)\n"
                        "\tat org.springframework.web.servlet.FrameworkServlet.service(FrameworkServlet.java:897)"
                    ),
                )
            )

        # API gateway 502 errors
        for _ in range(rng.randint(10, 20)):
            logs.append(
                LogEntry(
                    timestamp=_ts(now, rng.uniform(-2, 5)),
                    service=ServiceName.API_GATEWAY,
                    level="ERROR",
                    message="502 Bad Gateway: upstream checkout-service timed out",
                    trace_id=f"trace-{rng.randint(10000,99999)}",
                )
            )

        # ── Alert ───────────────────────────────────────────────
        alert = Alert(
            service=ServiceName.CHECKOUT_SERVICE,
            metric="p99_latency_ms",
            value=2000.0,
            threshold=500.0,
            severity=Severity(severity),
            timestamp=now,
            description="Checkout service p99 latency spiked to 2000ms",
        )

        # Sort by timestamp
        logs.sort(key=lambda x: x.timestamp)
        metrics.sort(key=lambda x: x.timestamp)
        deployments.sort(key=lambda x: x.timestamp)

        return MockDataSet(
            scenario_name=self.name,
            logs=logs,
            metrics=metrics,
            deployments=deployments,
            alert=alert,
        )


# ── 2. Memory Leak ──────────────────────────────────────────────


class MemoryLeakScenario(BaseScenario):
    """Code deploy introduces a memory leak that causes OOM kill 2 hours later."""

    name = "memory_leak"

    def generate(
        self,
        seed: int = 42,
        severity: str = "critical",
        incident_time: Optional[datetime] = None,
    ) -> MockDataSet:
        rng = random.Random(seed)
        now = incident_time or datetime.utcnow()
        deploy_time = _ts(now, -120)  # 2 hours ago
        window_start = _ts(now, -130)

        logs: list[LogEntry] = []
        metrics: list[MetricDataPoint] = []
        deployments: list[DeploymentEvent] = []

        # ── Deployment event (T-120 min) ────────────────────────
        deployments.append(
            DeploymentEvent(
                deploy_id=f"deploy-{rng.randint(1000,9999)}",
                timestamp=deploy_time,
                service=ServiceName.INVENTORY_SERVICE,
                change_type=ChangeType.CODE_DEPLOY,
                description="Deploy v2.14.0: added product recommendation cache layer",
                commit_sha=f"{rng.getrandbits(160):040x}"[:12],
                author="dev-team",
            )
        )

        # ── Memory rising steadily over 2 hours ────────────────
        for i in range(0, 121, 2):  # every 2 minutes
            t = _ts(deploy_time, i)
            # Linear rise from 512 MB to 3800 MB
            mem = 512 + (3300 * i / 120) + rng.gauss(0, 20)
            metrics.append(
                MetricDataPoint(
                    timestamp=t,
                    service=ServiceName.INVENTORY_SERVICE,
                    metric_name="memory_mb",
                    value=max(mem, 512),
                )
            )
            # CPU stays normal until near the end
            cpu = 30 + rng.gauss(0, 5) + (20 if i > 100 else 0)
            metrics.append(
                MetricDataPoint(
                    timestamp=t,
                    service=ServiceName.INVENTORY_SERVICE,
                    metric_name="cpu_percent",
                    value=min(max(cpu, 5), 100),
                )
            )
            # Latency gradually increases
            latency = 80 + (i * 1.5) + rng.gauss(0, 10)
            metrics.append(
                MetricDataPoint(
                    timestamp=t,
                    service=ServiceName.INVENTORY_SERVICE,
                    metric_name="p99_latency_ms",
                    value=max(latency, 50),
                )
            )

        # ── GC warning logs (intermittent, last 30 minutes) ────
        for _ in range(rng.randint(15, 25)):
            t = _ts(now, rng.uniform(-30, -1))
            logs.append(
                LogEntry(
                    timestamp=t,
                    service=ServiceName.INVENTORY_SERVICE,
                    level="WARN",
                    message=f"GC overhead limit exceeded — heap usage {rng.randint(85,98)}%",
                )
            )

        # ── OOM Kill at T=0 ─────────────────────────────────────
        logs.append(
            LogEntry(
                timestamp=now,
                service=ServiceName.INVENTORY_SERVICE,
                level="ERROR",
                message="Process killed by OOM killer: inventory-service (PID 1) used 3.8GB / 4.0GB limit",
                stack_trace=(
                    "java.lang.OutOfMemoryError: Java heap space\n"
                    "\tat com.inventory.cache.RecommendationCache.put(RecommendationCache.java:112)\n"
                    "\tat com.inventory.service.ProductService.getRecommendations(ProductService.java:89)\n"
                    "\tat com.inventory.controller.ProductController.list(ProductController.java:34)"
                ),
            )
        )

        # ── Service restart logs ────────────────────────────────
        logs.append(
            LogEntry(
                timestamp=_ts(now, 0.5),
                service=ServiceName.INVENTORY_SERVICE,
                level="INFO",
                message="Container restarting: inventory-service (restart count: 1)",
            )
        )

        # ── Upstream impact on checkout-service ─────────────────
        for _ in range(rng.randint(5, 10)):
            logs.append(
                LogEntry(
                    timestamp=_ts(now, rng.uniform(0, 3)),
                    service=ServiceName.CHECKOUT_SERVICE,
                    level="ERROR",
                    message="Failed to check inventory: Connection refused — inventory-service:8083",
                    trace_id=f"trace-{rng.randint(10000,99999)}",
                )
            )

        alert = Alert(
            service=ServiceName.INVENTORY_SERVICE,
            metric="memory_mb",
            value=3800.0,
            threshold=3500.0,
            severity=Severity(severity),
            timestamp=now,
            description="Inventory service memory usage exceeded 3.5GB threshold — OOM kill detected",
        )

        logs.sort(key=lambda x: x.timestamp)
        metrics.sort(key=lambda x: x.timestamp)

        return MockDataSet(
            scenario_name=self.name,
            logs=logs,
            metrics=metrics,
            deployments=deployments,
            alert=alert,
        )


# ── 3. Cascading Failure ────────────────────────────────────────


class CascadingFailureScenario(BaseScenario):
    """postgres-db goes down, causing cascading failures upstream."""

    name = "cascading_failure"

    def generate(
        self,
        seed: int = 42,
        severity: str = "critical",
        incident_time: Optional[datetime] = None,
    ) -> MockDataSet:
        rng = random.Random(seed)
        now = incident_time or datetime.utcnow()
        window_start = _ts(now, -10)

        logs: list[LogEntry] = []
        metrics: list[MetricDataPoint] = []
        deployments: list[DeploymentEvent] = []

        # ── postgres-db crash at T=0 ────────────────────────────
        logs.append(
            LogEntry(
                timestamp=now,
                service=ServiceName.POSTGRES_DB,
                level="ERROR",
                message="FATAL: could not open file \"base/16384/2619\": No such file or directory",
            )
        )
        logs.append(
            LogEntry(
                timestamp=_ts(now, 0.1),
                service=ServiceName.POSTGRES_DB,
                level="ERROR",
                message="LOG: database system is shut down",
            )
        )

        # ── Normal metrics before crash ─────────────────────────
        for svc in ["checkout-service", "payment-gateway", "inventory-service", "user-auth"]:
            metrics.extend(
                _normal_metric(rng, svc, "p99_latency_ms", window_start, 10, 100, 15)
            )
            metrics.extend(
                _normal_metric(rng, svc, "error_rate", window_start, 10, 0.001, 0.0005)
            )

        # ── Cascading failures (T=0 to T+5 min) ────────────────
        dependent_services = get_dependents("postgres-db")
        for minute in range(6):
            t = _ts(now, minute)

            # DB-dependent services fail first
            for svc in dependent_services:
                metrics.append(
                    MetricDataPoint(
                        timestamp=t,
                        service=ServiceName(svc),
                        metric_name="error_rate",
                        value=min(0.1 + minute * 0.15, 0.95),
                    )
                )
                metrics.append(
                    MetricDataPoint(
                        timestamp=t,
                        service=ServiceName(svc),
                        metric_name="p99_latency_ms",
                        value=200 + minute * 400,
                    )
                )

                # Connection refused logs
                for _ in range(rng.randint(3, 8)):
                    logs.append(
                        LogEntry(
                            timestamp=_ts(t, rng.uniform(0, 0.9)),
                            service=ServiceName(svc),
                            level="ERROR",
                            message="Connection refused: postgres-db:5432 — Is the server running?",
                            trace_id=f"trace-{rng.randint(10000,99999)}",
                            stack_trace=(
                                f"psycopg2.OperationalError: could not connect to server: Connection refused\n"
                                f"\tIs the server running on host \"postgres-db\" (172.18.0.2) and accepting\n"
                                f"\tTCP/IP connections on port 5432?"
                            ),
                        )
                    )

            # API gateway sees upstream failures after ~1 min
            if minute >= 1:
                metrics.append(
                    MetricDataPoint(
                        timestamp=t,
                        service=ServiceName.API_GATEWAY,
                        metric_name="error_rate",
                        value=min(0.05 + (minute - 1) * 0.1, 0.8),
                    )
                )
                for _ in range(rng.randint(5, 12)):
                    svc = rng.choice(dependent_services)
                    logs.append(
                        LogEntry(
                            timestamp=_ts(t, rng.uniform(0, 0.9)),
                            service=ServiceName.API_GATEWAY,
                            level="ERROR",
                            message=f"503 Service Unavailable: upstream {svc} returned error",
                        )
                    )

        alert = Alert(
            service=ServiceName.API_GATEWAY,
            metric="error_rate",
            value=0.65,
            threshold=0.05,
            severity=Severity(severity),
            timestamp=_ts(now, 2),
            description="API gateway error rate spiked to 65% — multiple upstream services failing",
        )

        logs.sort(key=lambda x: x.timestamp)
        metrics.sort(key=lambda x: x.timestamp)

        return MockDataSet(
            scenario_name=self.name,
            logs=logs,
            metrics=metrics,
            deployments=deployments,
            alert=alert,
        )


# ── 4. Traffic Spike / DDoS ─────────────────────────────────────


class TrafficSpikeScenario(BaseScenario):
    """Sudden 10x traffic surge, no recent deployments."""

    name = "traffic_spike"

    def generate(
        self,
        seed: int = 42,
        severity: str = "critical",
        incident_time: Optional[datetime] = None,
    ) -> MockDataSet:
        rng = random.Random(seed)
        now = incident_time or datetime.utcnow()
        window_start = _ts(now, -15)

        logs: list[LogEntry] = []
        metrics: list[MetricDataPoint] = []
        deployments: list[DeploymentEvent] = []

        # ── No recent deployments (important for differential diagnosis) ──

        # ── Normal traffic before spike (T-15 to T-1) ──────────
        frontend_services = ["api-gateway", "checkout-service", "user-auth"]
        for svc in frontend_services:
            metrics.extend(
                _normal_metric(rng, svc, "requests_per_second", window_start, 14, 500, 50)
            )
            metrics.extend(
                _normal_metric(rng, svc, "p99_latency_ms", window_start, 14, 80, 10)
            )
            metrics.extend(
                _normal_metric(rng, svc, "cpu_percent", window_start, 14, 40, 8)
            )

        # ── Traffic spike at T=0 (10x surge) ───────────────────
        for minute in range(8):
            t = _ts(now, minute)
            multiplier = 10 if minute < 5 else 10 - (minute - 5) * 2  # tapers off

            for svc in frontend_services:
                metrics.append(
                    MetricDataPoint(
                        timestamp=t,
                        service=ServiceName(svc),
                        metric_name="requests_per_second",
                        value=500 * max(multiplier, 1) + rng.gauss(0, 100),
                    )
                )
                metrics.append(
                    MetricDataPoint(
                        timestamp=t,
                        service=ServiceName(svc),
                        metric_name="cpu_percent",
                        value=min(40 * max(multiplier, 1) / 4 + rng.gauss(0, 5), 100),
                    )
                )
                metrics.append(
                    MetricDataPoint(
                        timestamp=t,
                        service=ServiceName(svc),
                        metric_name="p99_latency_ms",
                        value=80 * max(multiplier, 1) / 2 + rng.gauss(0, 30),
                    )
                )

        # ── Rate limiting kicks in ──────────────────────────────
        for _ in range(rng.randint(30, 50)):
            logs.append(
                LogEntry(
                    timestamp=_ts(now, rng.uniform(0, 5)),
                    service=ServiceName.API_GATEWAY,
                    level="WARN",
                    message=f"Rate limit exceeded for client IP {rng.randint(1,255)}.{rng.randint(1,255)}.{rng.randint(1,255)}.{rng.randint(1,255)} — returning 429",
                )
            )

        # ── Request queue full errors ───────────────────────────
        for _ in range(rng.randint(15, 25)):
            svc = rng.choice(frontend_services)
            logs.append(
                LogEntry(
                    timestamp=_ts(now, rng.uniform(1, 5)),
                    service=ServiceName(svc),
                    level="ERROR",
                    message=f"Request queue full — rejecting request (queue_size=1000, max=1000)",
                    trace_id=f"trace-{rng.randint(10000,99999)}",
                )
            )

        # ── Thread pool exhaustion ──────────────────────────────
        for _ in range(rng.randint(8, 15)):
            logs.append(
                LogEntry(
                    timestamp=_ts(now, rng.uniform(2, 5)),
                    service=ServiceName.CHECKOUT_SERVICE,
                    level="ERROR",
                    message="Thread pool exhausted — all 200 threads in use, rejecting new connections",
                    stack_trace=(
                        "java.util.concurrent.RejectedExecutionException: "
                        "Task rejected from java.util.concurrent.ThreadPoolExecutor\n"
                        "\tat org.apache.tomcat.util.threads.TaskQueue.force(TaskQueue.java:175)\n"
                        "\tat org.apache.tomcat.util.threads.ThreadPoolExecutor.execute(ThreadPoolExecutor.java:152)"
                    ),
                )
            )

        alert = Alert(
            service=ServiceName.API_GATEWAY,
            metric="requests_per_second",
            value=5000.0,
            threshold=1000.0,
            severity=Severity(severity),
            timestamp=now,
            description="API gateway traffic surge — 10x normal request volume detected (possible DDoS)",
        )

        logs.sort(key=lambda x: x.timestamp)
        metrics.sort(key=lambda x: x.timestamp)

        return MockDataSet(
            scenario_name=self.name,
            logs=logs,
            metrics=metrics,
            deployments=deployments,
            alert=alert,
        )


# ── Scenario Registry ───────────────────────────────────────────

SCENARIOS: dict[str, BaseScenario] = {
    "latent_config_bug": LatentConfigBugScenario(),
    "memory_leak": MemoryLeakScenario(),
    "cascading_failure": CascadingFailureScenario(),
    "traffic_spike": TrafficSpikeScenario(),
}
