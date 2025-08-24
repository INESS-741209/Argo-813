"""
Advanced Logging System for ARGO
Provides structured logging, log aggregation, and analysis
"""

import logging
import json
import asyncio
import time
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque, defaultdict
from dataclasses import dataclass, asdict
import threading
import traceback
import gzip
import re


@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: datetime
    level: str
    logger_name: str
    message: str
    module: str
    function: str
    line_number: int
    thread_id: int
    process_id: int
    extra_data: Dict[str, Any] = None
    stack_trace: Optional[str] = None
    
    def __post_init__(self):
        if self.extra_data is None:
            self.extra_data = {}


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = LogEntry(
            timestamp=datetime.fromtimestamp(record.created),
            level=record.levelname,
            logger_name=record.name,
            message=record.getMessage(),
            module=record.module,
            function=record.funcName,
            line_number=record.lineno,
            thread_id=record.thread,
            process_id=record.process,
            extra_data=getattr(record, 'extra_data', {}),
            stack_trace=self.formatException(record.exc_info) if record.exc_info else None
        )
        
        return json.dumps(asdict(log_entry), default=str, ensure_ascii=False)


class LogAggregator:
    """Aggregates and analyzes log entries"""
    
    def __init__(self, max_entries: int = 50000):
        self.max_entries = max_entries
        self.log_entries: deque = deque(maxlen=max_entries)
        self.error_patterns: Dict[str, int] = defaultdict(int)
        self.performance_logs: deque = deque(maxlen=10000)
        self._lock = threading.RLock()
    
    def add_log_entry(self, log_entry: LogEntry):
        """Add log entry to aggregator"""
        with self._lock:
            self.log_entries.append(log_entry)
            
            # Track error patterns
            if log_entry.level in ['ERROR', 'CRITICAL']:
                pattern = self._extract_error_pattern(log_entry.message)
                self.error_patterns[pattern] += 1
            
            # Track performance logs
            if 'duration' in log_entry.extra_data or 'processing_time' in log_entry.extra_data:
                self.performance_logs.append(log_entry)
    
    def _extract_error_pattern(self, message: str) -> str:
        """Extract error pattern from message"""
        # Remove specific values (numbers, IDs, etc.) to identify patterns
        pattern = re.sub(r'\b\d+\b', 'N', message)
        pattern = re.sub(r'\b[a-f0-9]{8,}\b', 'ID', pattern)
        pattern = re.sub(r'\b\w+@\w+\.\w+\b', 'EMAIL', pattern)
        return pattern[:100]  # Limit pattern length
    
    def get_log_entries(self, 
                       level: Optional[str] = None,
                       logger_name: Optional[str] = None,
                       duration: Optional[timedelta] = None,
                       limit: int = 1000) -> List[LogEntry]:
        """Get filtered log entries"""
        with self._lock:
            entries = list(self.log_entries)
        
        # Apply filters
        if duration:
            cutoff_time = datetime.now() - duration
            entries = [e for e in entries if e.timestamp >= cutoff_time]
        
        if level:
            entries = [e for e in entries if e.level == level]
        
        if logger_name:
            entries = [e for e in entries if logger_name in e.logger_name]
        
        # Sort by timestamp (newest first) and limit
        entries.sort(key=lambda x: x.timestamp, reverse=True)
        return entries[:limit]
    
    def get_error_summary(self, duration: Optional[timedelta] = None) -> Dict[str, Any]:
        """Get error summary statistics"""
        error_entries = self.get_log_entries(level='ERROR', duration=duration)
        critical_entries = self.get_log_entries(level='CRITICAL', duration=duration)
        
        # Top error patterns
        pattern_counts = defaultdict(int)
        for entry in error_entries + critical_entries:
            pattern = self._extract_error_pattern(entry.message)
            pattern_counts[pattern] += 1
        
        top_patterns = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            'total_errors': len(error_entries),
            'total_critical': len(critical_entries),
            'error_rate': len(error_entries) / max(len(self.log_entries), 1),
            'top_error_patterns': top_patterns,
            'errors_by_module': self._group_by_module(error_entries),
            'recent_errors': [asdict(e) for e in error_entries[:5]]
        }
    
    def _group_by_module(self, entries: List[LogEntry]) -> Dict[str, int]:
        """Group entries by module"""
        module_counts = defaultdict(int)
        for entry in entries:
            module_counts[entry.module] += 1
        return dict(module_counts)
    
    def get_performance_summary(self, duration: Optional[timedelta] = None) -> Dict[str, Any]:
        """Get performance summary from logs"""
        with self._lock:
            perf_entries = list(self.performance_logs)
        
        if duration:
            cutoff_time = datetime.now() - duration
            perf_entries = [e for e in perf_entries if e.timestamp >= cutoff_time]
        
        if not perf_entries:
            return {}
        
        # Extract timing data
        durations = []
        for entry in perf_entries:
            if 'duration' in entry.extra_data:
                durations.append(entry.extra_data['duration'])
            elif 'processing_time' in entry.extra_data:
                durations.append(entry.extra_data['processing_time'])
        
        if durations:
            durations.sort()
            return {
                'total_operations': len(durations),
                'avg_duration': sum(durations) / len(durations),
                'min_duration': min(durations),
                'max_duration': max(durations),
                'p50_duration': durations[len(durations) // 2],
                'p95_duration': durations[int(len(durations) * 0.95)],
                'p99_duration': durations[int(len(durations) * 0.99)]
            }
        
        return {}


class LogAnalyzer:
    """Analyzes log patterns and anomalies"""
    
    def __init__(self, aggregator: LogAggregator):
        self.aggregator = aggregator
        self.anomaly_thresholds = {
            'error_rate': 0.1,  # 10% error rate
            'avg_response_time': 1.0,  # 1 second
            'memory_usage': 0.8  # 80% memory usage
        }
    
    def detect_anomalies(self, duration: timedelta = timedelta(hours=1)) -> List[Dict[str, Any]]:
        """Detect anomalies in log data"""
        anomalies = []
        
        # Check error rate anomaly
        error_summary = self.aggregator.get_error_summary(duration)
        if error_summary.get('error_rate', 0) > self.anomaly_thresholds['error_rate']:
            anomalies.append({
                'type': 'high_error_rate',
                'severity': 'warning',
                'description': f"Error rate {error_summary['error_rate']:.1%} exceeds threshold",
                'metrics': error_summary
            })
        
        # Check performance anomalies
        perf_summary = self.aggregator.get_performance_summary(duration)
        if perf_summary.get('avg_duration', 0) > self.anomaly_thresholds['avg_response_time']:
            anomalies.append({
                'type': 'high_response_time',
                'severity': 'warning',
                'description': f"Average response time {perf_summary['avg_duration']:.3f}s exceeds threshold",
                'metrics': perf_summary
            })
        
        return anomalies
    
    def analyze_trends(self, duration: timedelta = timedelta(hours=24)) -> Dict[str, Any]:
        """Analyze trends in log data"""
        # Group logs by hour
        hourly_stats = defaultdict(lambda: {'total': 0, 'errors': 0, 'warnings': 0})
        
        entries = self.aggregator.get_log_entries(duration=duration, limit=10000)
        
        for entry in entries:
            hour_key = entry.timestamp.strftime('%Y-%m-%d %H:00')
            hourly_stats[hour_key]['total'] += 1
            
            if entry.level == 'ERROR':
                hourly_stats[hour_key]['errors'] += 1
            elif entry.level == 'WARNING':
                hourly_stats[hour_key]['warnings'] += 1
        
        return {
            'hourly_stats': dict(hourly_stats),
            'peak_hour': max(hourly_stats.items(), key=lambda x: x[1]['total']) if hourly_stats else None,
            'error_trend': self._calculate_trend([stats['errors'] for stats in hourly_stats.values()]),
            'total_trend': self._calculate_trend([stats['total'] for stats in hourly_stats.values()])
        }
    
    def _calculate_trend(self, values: List[int]) -> str:
        """Calculate trend direction"""
        if len(values) < 2:
            return 'stable'
        
        recent_avg = sum(values[-3:]) / min(3, len(values))
        older_avg = sum(values[:-3]) / max(1, len(values) - 3)
        
        if recent_avg > older_avg * 1.2:
            return 'increasing'
        elif recent_avg < older_avg * 0.8:
            return 'decreasing'
        else:
            return 'stable'


class LogRotator:
    """Handles log file rotation and compression"""
    
    def __init__(self, log_dir: Path, max_size_mb: int = 100, max_files: int = 10):
        self.log_dir = Path(log_dir)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_files = max_files
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    async def rotate_logs(self):
        """Rotate log files if they exceed size limit"""
        try:
            log_files = list(self.log_dir.glob("*.log"))
            
            for log_file in log_files:
                if log_file.stat().st_size > self.max_size_bytes:
                    await self._rotate_file(log_file)
            
            # Clean up old rotated files
            await self._cleanup_old_files()
            
        except Exception as e:
            logging.error(f"Error rotating logs: {e}")
    
    async def _rotate_file(self, log_file: Path):
        """Rotate a single log file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rotated_name = f"{log_file.stem}_{timestamp}.log.gz"
        rotated_path = self.log_dir / rotated_name
        
        # Compress and move the file
        with open(log_file, 'rb') as f_in:
            with gzip.open(rotated_path, 'wb') as f_out:
                f_out.writelines(f_in)
        
        # Clear the original file
        with open(log_file, 'w') as f:
            f.write("")
        
        logging.info(f"Rotated log file: {log_file} -> {rotated_path}")
    
    async def _cleanup_old_files(self):
        """Remove old rotated log files"""
        rotated_files = list(self.log_dir.glob("*.log.gz"))
        
        if len(rotated_files) > self.max_files:
            # Sort by modification time and remove oldest
            rotated_files.sort(key=lambda x: x.stat().st_mtime)
            files_to_remove = rotated_files[:-self.max_files]
            
            for file_path in files_to_remove:
                file_path.unlink()
                logging.info(f"Removed old log file: {file_path}")


class LoggingSystem:
    """Main logging system orchestrator"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.log_dir = Path(self.config.get('log_dir', 'C:\\Argo-813\\logs'))
        self.log_level = self.config.get('log_level', 'INFO')
        
        # Initialize components
        self.aggregator = LogAggregator(
            max_entries=self.config.get('max_entries', 50000)
        )
        self.analyzer = LogAnalyzer(self.aggregator)
        self.rotator = LogRotator(
            self.log_dir,
            max_size_mb=self.config.get('max_size_mb', 100),
            max_files=self.config.get('max_files', 10)
        )
        
        # Setup logging
        self._setup_logging()
        
        # Monitoring state
        self.is_running = False
        
        logging.info("Advanced Logging System initialized")
    
    def _setup_logging(self):
        """Setup enhanced logging configuration"""
        # Create logs directory
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.log_level))
        
        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Console handler with structured format
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # File handler with structured format
        file_handler = logging.FileHandler(
            self.log_dir / 'argo_system.log',
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, self.log_level))
        file_formatter = StructuredFormatter()
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Error file handler
        error_handler = logging.FileHandler(
            self.log_dir / 'argo_errors.log',
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)
        
        # Performance file handler
        perf_handler = logging.FileHandler(
            self.log_dir / 'argo_performance.log',
            encoding='utf-8'
        )
        perf_handler.setLevel(logging.DEBUG)
        perf_handler.setFormatter(file_formatter)
        
        # Add filter for performance logs
        perf_handler.addFilter(lambda record: 'performance' in record.getMessage().lower())
        root_logger.addHandler(perf_handler)
        
        # Setup custom log aggregation handler
        aggregation_handler = LogAggregationHandler(self.aggregator)
        aggregation_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(aggregation_handler)
    
    async def start(self):
        """Start the logging system"""
        if self.is_running:
            logging.info("Logging System is already running")
            return
        
        logging.info("Starting Advanced Logging System...")
        self.is_running = True
        
        # Start background tasks
        asyncio.create_task(self._log_rotation_task())
        asyncio.create_task(self._anomaly_detection_task())
        asyncio.create_task(self._log_analysis_task())
        
        logging.info("Advanced Logging System started successfully")
    
    async def stop(self):
        """Stop the logging system"""
        if not self.is_running:
            return
        
        logging.info("Stopping Advanced Logging System...")
        self.is_running = False
        logging.info("Advanced Logging System stopped")
    
    async def _log_rotation_task(self):
        """Background task for log rotation"""
        while self.is_running:
            try:
                await self.rotator.rotate_logs()
                await asyncio.sleep(3600)  # Check every hour
            except Exception as e:
                logging.error(f"Error in log rotation task: {e}")
                await asyncio.sleep(3600)
    
    async def _anomaly_detection_task(self):
        """Background task for anomaly detection"""
        while self.is_running:
            try:
                anomalies = self.analyzer.detect_anomalies()
                
                for anomaly in anomalies:
                    logging.warning(f"ANOMALY DETECTED: {anomaly['description']}")
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logging.error(f"Error in anomaly detection: {e}")
                await asyncio.sleep(300)
    
    async def _log_analysis_task(self):
        """Background task for log analysis and reporting"""
        while self.is_running:
            try:
                # Generate periodic reports
                await self._generate_log_report()
                
                await asyncio.sleep(1800)  # Generate report every 30 minutes
                
            except Exception as e:
                logging.error(f"Error in log analysis: {e}")
                await asyncio.sleep(1800)
    
    async def _generate_log_report(self):
        """Generate comprehensive log report"""
        try:
            error_summary = self.aggregator.get_error_summary(timedelta(hours=1))
            perf_summary = self.aggregator.get_performance_summary(timedelta(hours=1))
            trends = self.analyzer.analyze_trends(timedelta(hours=24))
            
            report = {
                'timestamp': datetime.now().isoformat(),
                'error_summary': error_summary,
                'performance_summary': perf_summary,
                'trends': trends,
                'system_health': self._assess_system_health(error_summary, perf_summary)
            }
            
            # Save report
            report_file = self.log_dir / f"log_report_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logging.info(f"Log report generated: {report_file}")
            
        except Exception as e:
            logging.error(f"Error generating log report: {e}")
    
    def _assess_system_health(self, error_summary: Dict, perf_summary: Dict) -> str:
        """Assess overall system health based on logs"""
        error_rate = error_summary.get('error_rate', 0)
        avg_duration = perf_summary.get('avg_duration', 0)
        
        if error_rate > 0.1 or avg_duration > 2.0:
            return 'unhealthy'
        elif error_rate > 0.05 or avg_duration > 1.0:
            return 'degraded'
        else:
            return 'healthy'
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for logging dashboard"""
        return {
            'error_summary': self.aggregator.get_error_summary(timedelta(hours=1)),
            'performance_summary': self.aggregator.get_performance_summary(timedelta(hours=1)),
            'recent_errors': [asdict(e) for e in self.aggregator.get_log_entries('ERROR', limit=10)],
            'anomalies': self.analyzer.detect_anomalies(),
            'trends': self.analyzer.analyze_trends(),
            'system_health': self._assess_system_health(
                self.aggregator.get_error_summary(timedelta(hours=1)),
                self.aggregator.get_performance_summary(timedelta(hours=1))
            )
        }


class LogAggregationHandler(logging.Handler):
    """Custom logging handler for log aggregation"""
    
    def __init__(self, aggregator: LogAggregator):
        super().__init__()
        self.aggregator = aggregator
    
    def emit(self, record: logging.LogRecord):
        """Emit log record to aggregator"""
        try:
            log_entry = LogEntry(
                timestamp=datetime.fromtimestamp(record.created),
                level=record.levelname,
                logger_name=record.name,
                message=record.getMessage(),
                module=record.module,
                function=record.funcName,
                line_number=record.lineno,
                thread_id=record.thread,
                process_id=record.process,
                extra_data=getattr(record, 'extra_data', {}),
                stack_trace=self.format(record) if record.exc_info else None
            )
            
            self.aggregator.add_log_entry(log_entry)
            
        except Exception:
            self.handleError(record)


# Global logging system instance
logging_system = LoggingSystem()


async def get_logging_system() -> LoggingSystem:
    """Get global logging system instance"""
    return logging_system


# Utility functions
def log_with_extra(logger: logging.Logger, level: str, message: str, **extra_data):
    """Log message with extra structured data"""
    record = logger.makeRecord(
        logger.name, getattr(logging, level.upper()), 
        "", 0, message, (), None
    )
    record.extra_data = extra_data
    logger.handle(record)


def log_performance(logger: logging.Logger, operation: str, duration: float, **extra_data):
    """Log performance metric"""
    extra_data.update({
        'operation': operation,
        'duration': duration,
        'performance': True
    })
    log_with_extra(logger, 'INFO', f"Performance: {operation} completed in {duration:.3f}s", **extra_data)
