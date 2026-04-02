"""Operational reporting tier for dashboard and monitoring outputs.

Generates real-time dashboards, performance metrics, and operational insights
for system monitoring and decision-making.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import json


@dataclass
class PerformanceMetric:
    """A single performance metric with trend information."""
    name: str
    current_value: float
    previous_value: Optional[float] = None
    unit: str = ""
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None

    @property
    def trend(self) -> str:
        """Calculate trend direction."""
        if self.previous_value is None:
            return "stable"
        if self.current_value > self.previous_value:
            return "up"
        if self.current_value < self.previous_value:
            return "down"
        return "stable"

    @property
    def trend_percentage(self) -> Optional[float]:
        """Calculate trend percentage change."""
        if self.previous_value is None or self.previous_value == 0:
            return None
        return ((self.current_value - self.previous_value) / self.previous_value) * 100

    @property
    def status(self) -> str:
        """Get metric status based on thresholds."""
        if self.threshold_critical and self.current_value >= self.threshold_critical:
            return "critical"
        if self.threshold_warning and self.current_value >= self.threshold_warning:
            return "warning"
        return "healthy"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "current_value": self.current_value,
            "previous_value": self.previous_value,
            "unit": self.unit,
            "trend": self.trend,
            "trend_percentage": self.trend_percentage,
            "status": self.status
        }


@dataclass
class EngineStatus:
    """Status information for a single engine."""
    engine_name: str
    engine_version: str
    is_active: bool
    last_execution: Optional[str] = None
    success_rate: float = 100.0
    avg_execution_time_ms: float = 0.0
    error_count: int = 0
    metrics: List[PerformanceMetric] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "engine_name": self.engine_name,
            "engine_version": self.engine_version,
            "is_active": self.is_active,
            "last_execution": self.last_execution,
            "success_rate": self.success_rate,
            "avg_execution_time_ms": self.avg_execution_time_ms,
            "error_count": self.error_count,
            "metrics": [m.to_dict() for m in self.metrics]
        }


@dataclass
class SystemHealth:
    """Overall system health status."""
    status: str  # "healthy", "degraded", "critical"
    uptime_seconds: float
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    active_engines: int
    total_engines: int
    last_updated: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status,
            "uptime_seconds": self.uptime_seconds,
            "cpu_usage_percent": self.cpu_usage_percent,
            "memory_usage_percent": self.memory_usage_percent,
            "disk_usage_percent": self.disk_usage_percent,
            "active_engines": self.active_engines,
            "total_engines": self.total_engines,
            "last_updated": self.last_updated
        }


class OperationalReport:
    """Dashboard-ready operational report.

    Generates real-time insights for system monitoring, including
    performance metrics, engine status, and system health.
    """

    def __init__(
        self,
        report_id: str,
        timestamp: str,
        system_health: SystemHealth,
        engine_statuses: List[EngineStatus],
        performance_metrics: List[PerformanceMetric],
        alerts: Optional[List[Dict[str, Any]]] = None,
        recommendations: Optional[List[str]] = None
    ):
        """Initialize operational report.

        Args:
            report_id: Unique report identifier
            timestamp: Report generation timestamp
            system_health: Overall system health
            engine_statuses: Status of each engine
            performance_metrics: Key performance metrics
            alerts: Active alerts
            recommendations: System recommendations
        """
        self.report_id = report_id
        self.timestamp = timestamp
        self.system_health = system_health
        self.engine_statuses = engine_statuses
        self.performance_metrics = performance_metrics
        self.alerts = alerts or []
        self.recommendations = recommendations or []

    def get_engine_by_name(self, name: str) -> Optional[EngineStatus]:
        """Get engine status by name.

        Args:
            name: Engine name

        Returns:
            Engine status if found, None otherwise
        """
        for engine in self.engine_statuses:
            if engine.engine_name == name:
                return engine
        return None

    def get_critical_alerts(self) -> List[Dict[str, Any]]:
        """Get only critical alerts.

        Returns:
            List of critical alerts
        """
        return [a for a in self.alerts if a.get("severity") == "critical"]

    def get_warning_alerts(self) -> List[Dict[str, Any]]:
        """Get only warning alerts.

        Returns:
            List of warning alerts
        """
        return [a for a in self.alerts if a.get("severity") == "warning"]

    def to_dashboard_json(self) -> str:
        """Generate JSON for dashboard consumption.

        Returns:
            JSON string optimized for dashboard rendering
        """
        dashboard_data = {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "summary": {
                "system_status": self.system_health.status,
                "active_engines": self.system_health.active_engines,
                "total_engines": self.system_health.total_engines,
                "critical_alerts": len(self.get_critical_alerts()),
                "warning_alerts": len(self.get_warning_alerts())
            },
            "system_health": self.system_health.to_dict(),
            "engines": [e.to_dict() for e in self.engine_statuses],
            "metrics": [m.to_dict() for m in self.performance_metrics],
            "alerts": self.alerts,
            "recommendations": self.recommendations
        }
        return json.dumps(dashboard_data, indent=2)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary.

        Returns:
            Dictionary representation of the report
        """
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "system_health": self.system_health.to_dict(),
            "engine_statuses": [e.to_dict() for e in self.engine_statuses],
            "performance_metrics": [m.to_dict() for m in self.performance_metrics],
            "alerts": self.alerts,
            "recommendations": self.recommendations
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OperationalReport':
        """Create report from dictionary.

        Args:
            data: Dictionary containing report data

        Returns:
            OperationalReport instance
        """
        system_health = SystemHealth(
            status=data["system_health"]["status"],
            uptime_seconds=data["system_health"]["uptime_seconds"],
            cpu_usage_percent=data["system_health"]["cpu_usage_percent"],
            memory_usage_percent=data["system_health"]["memory_usage_percent"],
            disk_usage_percent=data["system_health"]["disk_usage_percent"],
            active_engines=data["system_health"]["active_engines"],
            total_engines=data["system_health"]["total_engines"],
            last_updated=data["system_health"]["last_updated"]
        )

        engine_statuses = [
            EngineStatus(
                engine_name=e["engine_name"],
                engine_version=e["engine_version"],
                is_active=e["is_active"],
                last_execution=e.get("last_execution"),
                success_rate=e.get("success_rate", 100.0),
                avg_execution_time_ms=e.get("avg_execution_time_ms", 0.0),
                error_count=e.get("error_count", 0),
                metrics=[
                    PerformanceMetric(
                        name=m["name"],
                        current_value=m["current_value"],
                        previous_value=m.get("previous_value"),
                        unit=m.get("unit", ""),
                        threshold_warning=m.get("threshold_warning"),
                        threshold_critical=m.get("threshold_critical")
                    )
                    for m in e.get("metrics", [])
                ]
            )
            for e in data["engine_statuses"]
        ]

        performance_metrics = [
            PerformanceMetric(
                name=m["name"],
                current_value=m["current_value"],
                previous_value=m.get("previous_value"),
                unit=m.get("unit", ""),
                threshold_warning=m.get("threshold_warning"),
                threshold_critical=m.get("threshold_critical")
            )
            for m in data["performance_metrics"]
        ]

        return cls(
            report_id=data["report_id"],
            timestamp=data["timestamp"],
            system_health=system_health,
            engine_statuses=engine_statuses,
            performance_metrics=performance_metrics,
            alerts=data.get("alerts", []),
            recommendations=data.get("recommendations", [])
        )