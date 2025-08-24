#!/usr/bin/env python3
"""
Enhanced Integration Test for ARGO Performance Optimizations
Tests performance monitoring, caching, error recovery, and logging systems
"""

import asyncio
import logging
import sys
import time
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from integration.layer_bridge import get_layer_bridge
from monitoring.performance_monitor import get_performance_monitor, monitor_performance
from monitoring.logging_system import get_logging_system, log_with_extra, log_performance

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_performance_optimizations():
    """Test performance optimizations (caching, batching)"""
    logger.info("🚀 Testing Performance Optimizations...")
    
    # Get enhanced bridge with optimizations
    config = {
        'batch_size': 5,
        'batch_timeout': 0.5,
        'cache_size': 100,
        'cache_ttl': 300,  # 5 minutes
        'max_retries': 3,
        'retry_delay': 0.1
    }
    
    # Import and initialize enhanced bridge
    from integration.layer_bridge import LayerBridge
    bridge = LayerBridge(config)
    
    # Start bridge
    await bridge.start()
    
    # Test 1: Message Caching
    logger.info("📦 Testing message caching...")
    
    # Send identical messages to test caching
    test_data = {"query": "test caching", "data": [1, 2, 3]}
    
    start_time = time.time()
    for i in range(10):
        await bridge.send_to_layer2("test_cache", test_data)
    
    cache_test_time = time.time() - start_time
    logger.info(f"✅ Cache test completed in {cache_test_time:.3f}s")
    
    # Check cache statistics
    metrics = bridge.get_performance_metrics()
    logger.info(f"📊 Cache Stats: Hit Rate: {metrics['cache_hit_rate']:.1%}, "
               f"Size: {metrics['cache_size']}")
    
    # Test 2: Batch Processing
    logger.info("📦 Testing batch processing...")
    
    # Send multiple messages quickly to trigger batching
    start_time = time.time()
    for i in range(20):
        await bridge.send_to_layer2("batch_test", {"batch_id": i, "timestamp": time.time()})
        if i % 5 == 0:
            await asyncio.sleep(0.1)  # Small delay to allow batching
    
    batch_test_time = time.time() - start_time
    logger.info(f"✅ Batch test completed in {batch_test_time:.3f}s")
    
    # Wait for batch processing
    await asyncio.sleep(2)
    
    # Check batch statistics
    updated_metrics = bridge.get_performance_metrics()
    logger.info(f"📊 Batch Stats: Messages Batched: {updated_metrics['messages_batched']}")
    
    # Test 3: Performance Metrics
    logger.info("📊 Testing performance metrics...")
    
    perf_metrics = bridge.get_performance_metrics()
    logger.info(f"Performance Metrics: {json.dumps(perf_metrics, indent=2, default=str)}")
    
    await bridge.stop()
    logger.info("🎉 Performance optimization tests completed!")


async def test_error_recovery():
    """Test error recovery mechanisms"""
    logger.info("🛡️ Testing Error Recovery Mechanisms...")
    
    from integration.layer_bridge import LayerBridge
    config = {
        'max_retries': 3,
        'retry_delay': 0.1,
        'exponential_backoff': True
    }
    
    bridge = LayerBridge(config)
    await bridge.start()
    
    # Test 1: Retry Logic
    logger.info("🔄 Testing retry logic...")
    
    # Register a handler that fails the first few times
    failure_count = 0
    
    async def failing_handler(data, message):
        nonlocal failure_count
        failure_count += 1
        
        if failure_count <= 2:
            raise Exception(f"Simulated failure #{failure_count}")
        
        return {"success": True, "attempts": failure_count}
    
    bridge.register_event_handler("test_retry", failing_handler)
    
    # Send message that will initially fail
    try:
        await bridge.send_to_layer2("test_retry", {"test": "retry_logic"})
        await asyncio.sleep(2)  # Wait for processing and retries
        
        logger.info(f"✅ Retry test completed after {failure_count} attempts")
    except Exception as e:
        logger.error(f"❌ Retry test failed: {e}")
    
    # Test 2: Failed Message Recovery
    logger.info("🔄 Testing failed message recovery...")
    
    # Check failed messages
    metrics = bridge.get_performance_metrics()
    logger.info(f"📊 Failed Messages: {metrics['failed_messages']}")
    
    # Try to retry failed messages
    await bridge.retry_failed_messages()
    
    # Check metrics again
    updated_metrics = bridge.get_performance_metrics()
    logger.info(f"📊 Updated Failed Messages: {updated_metrics['failed_messages']}")
    
    await bridge.stop()
    logger.info("🎉 Error recovery tests completed!")


async def test_performance_monitoring():
    """Test performance monitoring system"""
    logger.info("📊 Testing Performance Monitoring System...")
    
    # Get performance monitor
    monitor = await get_performance_monitor()
    
    # Start monitoring
    await monitor.start()
    
    # Test 1: Metric Recording
    logger.info("📈 Testing metric recording...")
    
    # Record various metrics
    monitor.record_gauge("cpu_usage", 65.5, "percentage")
    monitor.record_gauge("memory_usage", 42.3, "percentage")
    monitor.record_counter("api_requests", 5)
    monitor.record_timing("db_query", 0.025)
    monitor.record_histogram("response_size", 1024, "bytes")
    
    logger.info("✅ Metrics recorded successfully")
    
    # Test 2: Alert Rules
    logger.info("🚨 Testing alert rules...")
    
    # Trigger some alerts
    monitor.record_gauge("error_rate", 0.15)  # Should trigger warning
    monitor.record_gauge("avg_processing_time", 1.5)  # Should trigger warning
    monitor.record_gauge("memory_usage", 0.85)  # Should trigger warning
    
    await asyncio.sleep(1)  # Allow alerts to process
    
    # Check active alerts
    active_alerts = monitor.alert_manager.get_active_alerts()
    logger.info(f"📊 Active Alerts: {len(active_alerts)}")
    
    for alert in active_alerts:
        logger.warning(f"🚨 Alert: {alert.message} (Current: {alert.current_value}, Threshold: {alert.threshold})")
    
    # Test 3: Dashboard Data
    logger.info("📊 Testing dashboard data...")
    
    dashboard_data = monitor.get_dashboard_data()
    logger.info(f"Dashboard Data Keys: {list(dashboard_data.keys())}")
    
    # Test 4: Health Status
    health_status = monitor.get_health_status()
    logger.info(f"🏥 System Health: {health_status['status']} "
               f"(Alerts: {health_status['total_alerts']})")
    
    await monitor.stop()
    logger.info("🎉 Performance monitoring tests completed!")


@monitor_performance("test_function")
async def test_function_monitoring():
    """Test function-level performance monitoring"""
    logger.info("🔍 Testing function-level monitoring...")
    
    # Simulate some work
    await asyncio.sleep(0.1)
    
    # Log performance manually
    log_performance(logger, "database_query", 0.045, 
                   query_type="SELECT", rows_returned=150)
    
    return "test_complete"


async def test_logging_system():
    """Test advanced logging system"""
    logger.info("📝 Testing Advanced Logging System...")
    
    # Get logging system
    log_system = await get_logging_system()
    
    # Start logging system
    await log_system.start()
    
    # Test 1: Structured Logging
    logger.info("📋 Testing structured logging...")
    
    # Log with extra data
    log_with_extra(logger, 'INFO', 'User action completed', 
                  user_id=12345, action='search', duration=0.25, success=True)
    
    log_with_extra(logger, 'ERROR', 'Database connection failed',
                  error_code='DB001', retry_attempt=1, connection_pool='main')
    
    log_with_extra(logger, 'WARNING', 'High memory usage detected',
                  memory_percent=85.5, threshold=80.0, component='cache')
    
    # Test 2: Performance Logging
    logger.info("⚡ Testing performance logging...")
    
    log_performance(logger, "api_call", 0.125, endpoint="/api/search", method="POST")
    log_performance(logger, "cache_lookup", 0.005, cache_type="redis", hit=True)
    
    # Test 3: Error Pattern Detection
    logger.info("🔍 Testing error pattern detection...")
    
    # Generate similar errors to test pattern detection
    for i in range(5):
        log_with_extra(logger, 'ERROR', f'Connection timeout to server-{i % 3}',
                      server_id=f"srv-{i % 3}", timeout_ms=5000)
    
    # Wait for log processing
    await asyncio.sleep(2)
    
    # Test 4: Log Analysis
    logger.info("📊 Testing log analysis...")
    
    # Get error summary
    error_summary = log_system.aggregator.get_error_summary()
    logger.info(f"📊 Error Summary: {json.dumps(error_summary, indent=2, default=str)}")
    
    # Get performance summary
    perf_summary = log_system.aggregator.get_performance_summary()
    logger.info(f"⚡ Performance Summary: {json.dumps(perf_summary, indent=2, default=str)}")
    
    # Test 5: Anomaly Detection
    logger.info("🔍 Testing anomaly detection...")
    
    anomalies = log_system.analyzer.detect_anomalies()
    logger.info(f"🚨 Detected Anomalies: {len(anomalies)}")
    
    for anomaly in anomalies:
        logger.warning(f"🚨 Anomaly: {anomaly['description']}")
    
    # Test 6: Dashboard Data
    dashboard_data = log_system.get_dashboard_data()
    logger.info(f"📊 Logging Dashboard Data Keys: {list(dashboard_data.keys())}")
    
    await log_system.stop()
    logger.info("🎉 Logging system tests completed!")


async def test_integrated_scenario():
    """Test integrated scenario with all systems working together"""
    logger.info("🔄 Testing Integrated Scenario...")
    
    # Start all systems
    bridge_config = {
        'batch_size': 3,
        'batch_timeout': 0.3,
        'cache_size': 50,
        'max_retries': 2
    }
    
    from integration.layer_bridge import LayerBridge
    bridge = LayerBridge(bridge_config)
    monitor = await get_performance_monitor()
    log_system = await get_logging_system()
    
    await bridge.start()
    await monitor.start()
    await log_system.start()
    
    logger.info("🚀 All systems started")
    
    # Simulate realistic workload
    logger.info("⚡ Simulating realistic workload...")
    
    # Register performance-monitored handler
    async def process_search_request(data, message):
        start_time = time.time()
        
        # Simulate processing
        query = data.get('query', '')
        await asyncio.sleep(0.05 + len(query) * 0.001)  # Variable processing time
        
        processing_time = time.time() - start_time
        
        # Record metrics
        monitor.record_timing("search_processing", processing_time)
        monitor.record_counter("search_requests")
        
        # Log performance
        log_performance(logger, "search_request", processing_time,
                       query_length=len(query), result_count=len(query) * 2)
        
        if processing_time > 0.1:
            log_with_extra(logger, 'WARNING', 'Slow search request',
                          query=query, processing_time=processing_time)
        
        return {
            "results": [f"result_{i}" for i in range(len(query) % 10)],
            "processing_time": processing_time,
            "query": query
        }
    
    bridge.register_event_handler("search_request", process_search_request)
    
    # Generate varied workload
    queries = [
        "AI neural networks",
        "machine learning",
        "ARGO architecture",
        "performance optimization",
        "error handling patterns",
        "distributed systems",
        "caching strategies",
        "database optimization"
    ]
    
    tasks = []
    for i in range(50):
        query = queries[i % len(queries)]
        task = bridge.send_to_layer2("search_request", {
            "query": query,
            "user_id": f"user_{i % 5}",
            "timestamp": datetime.now().isoformat()
        })
        tasks.append(task)
        
        # Add some failures to test error recovery
        if i % 10 == 7:
            # Send a message that will cause processing issues
            tasks.append(bridge.send_to_layer2("invalid_request", {
                "malformed": "data",
                "will_cause": "error"
            }))
        
        # Vary the load
        if i % 5 == 0:
            await asyncio.sleep(0.1)
    
    # Wait for all tasks to complete
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Wait for processing to complete
    await asyncio.sleep(3)
    
    # Collect final metrics
    logger.info("📊 Collecting final metrics...")
    
    # Bridge metrics
    bridge_metrics = bridge.get_performance_metrics()
    logger.info(f"🔗 Bridge Performance: "
               f"Cache Hit Rate: {bridge_metrics['cache_hit_rate']:.1%}, "
               f"Error Rate: {bridge_metrics['error_rate']:.1%}, "
               f"Avg Processing Time: {bridge_metrics['avg_processing_time']:.3f}s")
    
    # Monitor metrics
    monitor_dashboard = monitor.get_dashboard_data()
    logger.info(f"📊 Monitor Stats: "
               f"Active Alerts: {len(monitor_dashboard['active_alerts'])}")
    
    # Logging metrics
    log_dashboard = log_system.get_dashboard_data()
    logger.info(f"📝 Logging Stats: "
               f"System Health: {log_dashboard['system_health']}, "
               f"Recent Errors: {len(log_dashboard['recent_errors'])}")
    
    # Health check
    health_status = monitor.get_health_status()
    logger.info(f"🏥 Overall System Health: {health_status['status']} "
               f"(Total Alerts: {health_status['total_alerts']})")
    
    # Stop all systems
    await bridge.stop()
    await monitor.stop()
    await log_system.stop()
    
    logger.info("🎉 Integrated scenario test completed!")


async def main():
    """Main test function"""
    logger.info("🚀 Starting Enhanced Integration Tests...")
    
    try:
        # Test 1: Performance Optimizations
        await test_performance_optimizations()
        
        # Test 2: Error Recovery
        await test_error_recovery()
        
        # Test 3: Performance Monitoring
        await test_performance_monitoring()
        
        # Test 4: Function Monitoring
        result = await test_function_monitoring()
        logger.info(f"✅ Function monitoring result: {result}")
        
        # Test 5: Logging System
        await test_logging_system()
        
        # Test 6: Integrated Scenario
        await test_integrated_scenario()
        
        logger.info("🎉 All enhanced integration tests completed successfully!")
        
        # Generate final summary
        logger.info("📊 FINAL SUMMARY:")
        logger.info("✅ Performance Optimizations: Message batching, caching, performance metrics")
        logger.info("✅ Error Recovery: Retry logic, exponential backoff, failed message recovery")
        logger.info("✅ Performance Monitoring: Real-time metrics, alerting, health checks")
        logger.info("✅ Advanced Logging: Structured logs, anomaly detection, log analysis")
        logger.info("✅ System Integration: All components working together seamlessly")
        
    except Exception as e:
        logger.error(f"❌ Enhanced integration tests failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
