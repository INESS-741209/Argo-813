"""
Advanced Performance Monitoring System for ARGO
Provides comprehensive monitoring, alerting, and analytics
"""

import asyncio
import logging
import json
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from collections import deque, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
import statistics
import threading

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Represents a performance metric"""
    name: str
    value: float
    unit: str
    timestamp: datetime
    tags: Dict[str, str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


@dataclass
class Alert:
    """Represents a performance alert"""
    id: str
    severity: str  # critical, warning, info
    message: str
    metric_name: str
    threshold: float
    current_value: float
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class MetricCollector:
    """Collects and aggregates performance metrics"""
    
    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.metric_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = threading.RLock()
    
    def record_metric(self, name: str, value: float, unit: str = "", tags: Dict[str, str] = None):
        """Record a performance metric"""
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            timestamp=datetime.now(),
            tags=tags or {}
        )
        
        with self._lock:
            self.metrics[name].append(metric)
        
        # Notify callbacks
        for callback in self.metric_callbacks.get(name, []):
            try:
                callback(metric)
            except Exception as e:
                logger.error(f"Error in metric callback for {name}: {e}")
    
    def get_metric_history(self, name: str, duration: timedelta = None) -> List[PerformanceMetric]:
        """Get metric history for specified duration"""
        with self._lock:
            if name not in self.metrics:
                return []
            
            if duration is None:
                return list(self.metrics[name])
            
            cutoff_time = datetime.now() - duration
            return [m for m in self.metrics[name] if m.timestamp >= cutoff_time]
    
    def get_metric_stats(self, name: str, duration: timedelta = None) -> Dict[str, float]:
        """Get statistical summary of metric"""
        history = self.get_metric_history(name, duration)
        
        if not history:
            return {}
        
        values = [m.value for m in history]
        
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'std_dev': statistics.stdev(values) if len(values) > 1 else 0,
            'p95': self._percentile(values, 0.95),
            'p99': self._percentile(values, 0.99)
        }
    
    def _percentile(self, values: List[float], p: float) -> float:
        """Calculate percentile"""
        if not values:
            return 0
        
        sorted_values = sorted(values)
        index = int(p * (len(sorted_values) - 1))
        return sorted_values[index]
    
    def register_metric_callback(self, name: str, callback: Callable):
        """Register callback for metric updates"""
        self.metric_callbacks[name].append(callback)


class AlertManager:
    """Manages performance alerts and notifications"""
    
    def __init__(self):
        self.alerts: Dict[str, Alert] = {}
        self.alert_rules: Dict[str, Dict[str, Any]] = {}
        self.alert_callbacks: List[Callable] = []
        self._lock = threading.RLock()
    
    def add_alert_rule(self, metric_name: str, threshold: float, severity: str = "warning", 
                      condition: str = "greater", message: str = None):
        """Add alert rule for metric"""
        rule = {
            'threshold': threshold,
            'severity': severity,
            'condition': condition,  # greater, less, equal
            'message': message or f"{metric_name} threshold exceeded"
        }
        
        with self._lock:
            self.alert_rules[metric_name] = rule
        
        logger.info(f"Added alert rule for {metric_name}: {condition} {threshold} ({severity})")
    
    def check_metric(self, metric: PerformanceMetric):
        """Check metric against alert rules"""
        if metric.name not in self.alert_rules:
            return
        
        rule = self.alert_rules[metric.name]
        threshold = rule['threshold']
        condition = rule['condition']
        
        # Check condition
        triggered = False
        if condition == "greater" and metric.value > threshold:
            triggered = True
        elif condition == "less" and metric.value < threshold:
            triggered = True
        elif condition == "equal" and abs(metric.value - threshold) < 0.001:
            triggered = True
        
        if triggered:
            self._trigger_alert(metric, rule)
        else:
            self._resolve_alert(metric.name)
    
    def _trigger_alert(self, metric: PerformanceMetric, rule: Dict[str, Any]):
        """Trigger an alert"""
        alert_id = f"{metric.name}_{rule['severity']}"
        
        with self._lock:
            if alert_id in self.alerts and not self.alerts[alert_id].resolved:
                return  # Alert already active
            
            alert = Alert(
                id=alert_id,
                severity=rule['severity'],
                message=rule['message'],
                metric_name=metric.name,
                threshold=rule['threshold'],
                current_value=metric.value,
                timestamp=datetime.now()
            )
            
            self.alerts[alert_id] = alert
        
        logger.warning(f"ALERT [{alert.severity.upper()}]: {alert.message} "
                      f"(Current: {alert.current_value}, Threshold: {alert.threshold})")
        
        # Notify callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
    
    def _resolve_alert(self, metric_name: str):
        """Resolve active alerts for metric"""
        with self._lock:
            for alert_id, alert in self.alerts.items():
                if alert.metric_name == metric_name and not alert.resolved:
                    alert.resolved = True
                    alert.resolved_at = datetime.now()
                    
                    logger.info(f"RESOLVED: Alert for {metric_name}")
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        with self._lock:
            return [alert for alert in self.alerts.values() if not alert.resolved]
    
    def register_alert_callback(self, callback: Callable):
        """Register callback for alert notifications"""
        self.alert_callbacks.append(callback)


class PerformanceMonitor:
    """Main performance monitoring system"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.collector = MetricCollector(
            max_history=self.config.get('max_history', 10000)
        )
        self.alert_manager = AlertManager()
        
        # Monitoring state
        self.is_running = False
        self.monitor_interval = self.config.get('monitor_interval', 30)  # seconds
        
        # System metrics
        self.system_metrics = {
            'cpu_usage': 0.0,
            'memory_usage': 0.0,
            'disk_usage': 0.0,
            'network_io': 0.0
        }
        
        # Setup default alert rules
        self._setup_default_alerts()
        
        # Setup metric callbacks
        self.collector.register_metric_callback('*', self.alert_manager.check_metric)
        
        logger.info("Performance Monitor initialized")
    
    def _setup_default_alerts(self):
        """Setup default alert rules"""
        # Error rate alerts
        self.alert_manager.add_alert_rule(
            'error_rate', 0.1, 'warning', 'greater',
            'High error rate detected'
        )
        self.alert_manager.add_alert_rule(
            'error_rate', 0.2, 'critical', 'greater',
            'Critical error rate detected'
        )
        
        # Processing time alerts
        self.alert_manager.add_alert_rule(
            'avg_processing_time', 1.0, 'warning', 'greater',
            'High average processing time'
        )
        self.alert_manager.add_alert_rule(
            'avg_processing_time', 2.0, 'critical', 'greater',
            'Critical processing time'
        )
        
        # Cache hit rate alerts
        self.alert_manager.add_alert_rule(
            'cache_hit_rate', 0.5, 'warning', 'less',
            'Low cache hit rate'
        )
        
        # Memory usage alerts
        self.alert_manager.add_alert_rule(
            'memory_usage', 0.8, 'warning', 'greater',
            'High memory usage'
        )
        self.alert_manager.add_alert_rule(
            'memory_usage', 0.9, 'critical', 'greater',
            'Critical memory usage'
        )
    
    async def start(self):
        """Start performance monitoring"""
        if self.is_running:
            logger.info("Performance Monitor is already running")
            return
        
        logger.info("Starting Performance Monitor...")
        self.is_running = True
        
        # Start monitoring tasks
        asyncio.create_task(self._system_monitor())
        asyncio.create_task(self._alert_processor())
        asyncio.create_task(self._metrics_exporter())
        
        logger.info("Performance Monitor started successfully")
    
    async def stop(self):
        """Stop performance monitoring"""
        if not self.is_running:
            return
        
        logger.info("Stopping Performance Monitor...")
        self.is_running = False
        logger.info("Performance Monitor stopped")
    
    def record_metric(self, name: str, value: float, unit: str = "", tags: Dict[str, str] = None):
        """Record a performance metric"""
        self.collector.record_metric(name, value, unit, tags)
    
    def record_counter(self, name: str, increment: int = 1, tags: Dict[str, str] = None):
        """Record a counter metric"""
        # Get current value and increment
        history = self.collector.get_metric_history(name, timedelta(seconds=1))
        current_value = history[-1].value if history else 0
        new_value = current_value + increment
        
        self.record_metric(name, new_value, "count", tags)
    
    def record_gauge(self, name: str, value: float, unit: str = "", tags: Dict[str, str] = None):
        """Record a gauge metric"""
        self.record_metric(name, value, unit, tags)
    
    def record_histogram(self, name: str, value: float, unit: str = "", tags: Dict[str, str] = None):
        """Record a histogram metric"""
        self.record_metric(f"{name}_value", value, unit, tags)
        
        # Also record statistics
        history = self.collector.get_metric_history(name, timedelta(minutes=1))
        if history:
            values = [m.value for m in history]
            self.record_metric(f"{name}_mean", statistics.mean(values), unit, tags)
            if len(values) > 1:
                self.record_metric(f"{name}_std", statistics.stdev(values), unit, tags)
    
    def record_timing(self, name: str, duration: float, tags: Dict[str, str] = None):
        """Record a timing metric"""
        self.record_histogram(name, duration, "seconds", tags)
    
    async def _system_monitor(self):
        """Monitor system-level metrics"""
        while self.is_running:
            try:
                # Collect system metrics (simplified for demo)
                self.system_metrics['cpu_usage'] = self._get_cpu_usage()
                self.system_metrics['memory_usage'] = self._get_memory_usage()
                self.system_metrics['disk_usage'] = self._get_disk_usage()
                
                # Record system metrics
                for metric_name, value in self.system_metrics.items():
                    self.record_gauge(metric_name, value, "percentage")
                
                await asyncio.sleep(self.monitor_interval)
                
            except Exception as e:
                logger.error(f"Error in system monitor: {e}")
                await asyncio.sleep(self.monitor_interval)
    
    def _get_cpu_usage(self) -> float:
        """Get CPU usage (simplified)"""
        # In a real implementation, use psutil or similar
        return min(0.1 + (time.time() % 10) / 50, 0.95)
    
    def _get_memory_usage(self) -> float:
        """Get memory usage (simplified)"""
        # In a real implementation, use psutil or similar
        return min(0.3 + (time.time() % 20) / 100, 0.95)
    
    def _get_disk_usage(self) -> float:
        """Get disk usage (simplified)"""
        # In a real implementation, use psutil or similar
        return min(0.2 + (time.time() % 30) / 200, 0.95)
    
    async def _alert_processor(self):
        """Process and manage alerts"""
        while self.is_running:
            try:
                active_alerts = self.alert_manager.get_active_alerts()
                
                if active_alerts:
                    logger.debug(f"Active alerts: {len(active_alerts)}")
                    
                    # Check for critical alerts
                    critical_alerts = [a for a in active_alerts if a.severity == 'critical']
                    if critical_alerts:
                        logger.critical(f"CRITICAL: {len(critical_alerts)} critical alerts active!")
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in alert processor: {e}")
                await asyncio.sleep(60)
    
    async def _metrics_exporter(self):
        """Export metrics to external systems"""
        while self.is_running:
            try:
                # Export metrics (simplified)
                await self._export_metrics_to_file()
                
                await asyncio.sleep(300)  # Export every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in metrics exporter: {e}")
                await asyncio.sleep(300)
    
    async def _export_metrics_to_file(self):
        """Export metrics to JSON file"""
        try:
            metrics_data = {
                'timestamp': datetime.now().isoformat(),
                'system_metrics': self.system_metrics.copy(),
                'metric_stats': {},
                'active_alerts': [asdict(alert) for alert in self.alert_manager.get_active_alerts()]
            }
            
            # Add metric statistics
            for metric_name in ['error_rate', 'avg_processing_time', 'cache_hit_rate']:
                stats = self.collector.get_metric_stats(metric_name, timedelta(hours=1))
                if stats:
                    metrics_data['metric_stats'][metric_name] = stats
            
            # Ensure directory exists
            metrics_dir = Path("C:\\Argo-813\\logs\\metrics")
            metrics_dir.mkdir(parents=True, exist_ok=True)
            
            # Write metrics file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            metrics_file = metrics_dir / f"metrics_{timestamp}.json"
            
            with open(metrics_file, 'w') as f:
                json.dump(metrics_data, f, indent=2, default=str)
            
            logger.debug(f"Metrics exported to {metrics_file}")
            
        except Exception as e:
            logger.error(f"Error exporting metrics: {e}")
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for monitoring dashboard"""
        return {
            'system_metrics': self.system_metrics.copy(),
            'active_alerts': [asdict(alert) for alert in self.alert_manager.get_active_alerts()],
            'metric_stats': {
                'error_rate': self.collector.get_metric_stats('error_rate', timedelta(hours=1)),
                'processing_time': self.collector.get_metric_stats('avg_processing_time', timedelta(hours=1)),
                'cache_hit_rate': self.collector.get_metric_stats('cache_hit_rate', timedelta(hours=1)),
                'message_count': self.collector.get_metric_stats('message_count', timedelta(hours=1))
            }
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status"""
        active_alerts = self.alert_manager.get_active_alerts()
        critical_alerts = [a for a in active_alerts if a.severity == 'critical']
        warning_alerts = [a for a in active_alerts if a.severity == 'warning']
        
        # Determine overall health
        if critical_alerts:
            health = 'critical'
        elif warning_alerts:
            health = 'warning'
        else:
            health = 'healthy'
        
        return {
            'status': health,
            'critical_alerts': len(critical_alerts),
            'warning_alerts': len(warning_alerts),
            'total_alerts': len(active_alerts),
            'system_metrics': self.system_metrics.copy(),
            'uptime': time.time() - (self.config.get('start_time', time.time())),
            'last_check': datetime.now().isoformat()
        }


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


async def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance"""
    return performance_monitor


# Decorator for automatic timing measurement
def monitor_performance(metric_name: str = None):
    """Decorator to automatically measure function performance"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            name = metric_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                performance_monitor.record_timing(f"{name}_duration", time.time() - start_time)
                performance_monitor.record_counter(f"{name}_success")
                return result
            except Exception as e:
                performance_monitor.record_timing(f"{name}_duration", time.time() - start_time)
                performance_monitor.record_counter(f"{name}_error")
                raise
        
        def sync_wrapper(*args, **kwargs):
            name = metric_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                performance_monitor.record_timing(f"{name}_duration", time.time() - start_time)
                performance_monitor.record_counter(f"{name}_success")
                return result
            except Exception as e:
                performance_monitor.record_timing(f"{name}_duration", time.time() - start_time)
                performance_monitor.record_counter(f"{name}_error")
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
