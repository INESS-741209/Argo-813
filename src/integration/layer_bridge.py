"""
Layer 1 (TypeScript) and Layer 2 (Python) Integration Bridge
Provides data exchange and synchronization between the two layers
Enhanced with performance optimizations, caching, and error recovery
"""

import json
import asyncio
import logging
from typing import Dict, Any, List, Optional, Union, Deque
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque, defaultdict
import time
import hashlib
import os

# Import mock Redis for local development
from infrastructure.mocks.mock_redis import get_mock_redis

logger = logging.getLogger(__name__)


class LayerBridge:
    """
    Enhanced Bridge between TypeScript Layer 1 and Python Layer 2
    Handles data exchange, synchronization, event routing with performance optimizations
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.redis = get_mock_redis()
        
        # Layer communication channels
        self.layer1_to_layer2_channel = "layer1_to_layer2"
        self.layer2_to_layer1_channel = "layer2_to_layer1"
        self.sync_channel = "layer_sync"
        
        # Event handlers
        self.event_handlers: Dict[str, callable] = {}
        
        # Data synchronization state
        self.last_sync_time = datetime.now()
        self.sync_interval = 5  # seconds
        
        # Performance optimizations
        self.batch_size = self.config.get('batch_size', 10)
        self.batch_timeout = self.config.get('batch_timeout', 1.0)  # seconds
        self.message_cache_size = self.config.get('cache_size', 1000)
        self.cache_ttl = self.config.get('cache_ttl', 3600)  # seconds
        
        # Message batching
        self.layer1_batch: Deque[Dict[str, Any]] = deque()
        self.layer2_batch: Deque[Dict[str, Any]] = deque()
        self.batch_timer = None
        
        # Message caching
        self.message_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_access_times: Dict[str, float] = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
        
        # Performance metrics
        self.metrics = {
            'messages_sent': 0,
            'messages_received': 0,
            'messages_batched': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'processing_times': deque(maxlen=100),
            'error_count': 0,
            'last_error_time': None
        }
        
        # Error recovery
        self.retry_config = {
            'max_retries': self.config.get('max_retries', 3),
            'retry_delay': self.config.get('retry_delay', 1.0),
            'exponential_backoff': self.config.get('exponential_backoff', True)
        }
        self.failed_messages: Deque[Dict[str, Any]] = deque(maxlen=100)
        
        logger.info("Enhanced Layer Bridge initialized with performance optimizations")
    
    async def start(self):
        """Start the enhanced bridge service with optimizations"""
        logger.info("Starting Enhanced Layer Bridge...")
        
        # Start background sync task
        asyncio.create_task(self._background_sync())
        
        # Start event listener
        asyncio.create_task(self._event_listener())
        
        # Start batch processing
        asyncio.create_task(self._batch_processor())
        
        # Start cache maintenance
        asyncio.create_task(self._cache_maintenance())
        
        # Start performance monitoring
        asyncio.create_task(self._performance_monitor())
        
        logger.info("Enhanced Layer Bridge started successfully")
    
    async def stop(self):
        """Stop the bridge service"""
        logger.info("Stopping Layer Bridge...")
        # Cleanup tasks would go here
        logger.info("Layer Bridge stopped")
    
    # Layer 1 → Layer 2 Communication
    
    async def send_to_layer2(self, event_type: str, data: Dict[str, Any]) -> str:
        """Send data from Layer 1 to Layer 2"""
        message = {
            "id": f"msg_{datetime.now().timestamp()}",
            "timestamp": datetime.now().isoformat(),
            "source": "layer1",
            "target": "layer2",
            "event_type": event_type,
            "data": data
        }
        
        # Store in Redis for Layer 2 to pick up
        key = f"{self.layer1_to_layer2_channel}:{message['id']}"
        self.redis.setex(key, 3600, json.dumps(message))  # 1 hour TTL
        
        # Add to queue
        self.redis.sadd(f"{self.layer1_to_layer2_channel}:queue", message['id'])
        
        logger.info(f"Sent to Layer 2: {event_type}")
        return message['id']
    
    async def receive_from_layer1(self) -> Optional[Dict[str, Any]]:
        """Receive data sent from Layer 1"""
        # Get next message from queue
        queue_key = f"{self.layer1_to_layer2_channel}:queue"
        message_ids = self.redis.smembers(queue_key)
        
        if not message_ids:
            return None
        
        # Get first message
        message_id = list(message_ids)[0]
        message_key = f"{self.layer1_to_layer2_channel}:{message_id}"
        
        message_data = self.redis.get(message_key)
        if not message_data:
            return None
        
        message = json.loads(message_data)
        
        # Remove from queue and storage
        self.redis.srem(queue_key, message_id)
        self.redis.delete(message_key)
        
        logger.info(f"Received from Layer 1: {message['event_type']}")
        return message
    
    # Layer 2 → Layer 1 Communication
    
    async def send_to_layer1(self, event_type: str, data: Dict[str, Any]) -> str:
        """Send data from Layer 2 to Layer 1"""
        message = {
            "id": f"msg_{datetime.now().timestamp()}",
            "timestamp": datetime.now().isoformat(),
            "source": "layer2",
            "target": "layer1",
            "event_type": event_type,
            "data": data
        }
        
        # Store in Redis for Layer 1 to pick up
        key = f"{self.layer2_to_layer1_channel}:{message['id']}"
        self.redis.setex(key, 3600, json.dumps(message))
        
        # Add to queue
        self.redis.sadd(f"{self.layer2_to_layer1_channel}:queue", message['id'])
        
        logger.info(f"Sent to Layer 1: {event_type}")
        return message['id']
    
    async def receive_from_layer2(self) -> Optional[Dict[str, Any]]:
        """Receive data sent from Layer 2"""
        # Get next message from queue
        queue_key = f"{self.layer2_to_layer1_channel}:queue"
        message_ids = self.redis.smembers(queue_key)
        
        if not message_ids:
            return None
        
        # Get first message
        message_id = list(message_ids)[0]
        message_key = f"{self.layer2_to_layer1_channel}:{message_id}"
        
        message_data = self.redis.get(message_key)
        if not message_data:
            return None
        
        message = json.loads(message_data)
        
        # Remove from queue and storage
        self.redis.srem(queue_key, message_id)
        self.redis.delete(message_key)
        
        logger.info(f"Received from Layer 2: {message['event_type']}")
        return message
    
    # Event Handling
    
    def register_event_handler(self, event_type: str, handler: callable):
        """Register event handler for specific event type"""
        self.event_handlers[event_type] = handler
        logger.info(f"Registered handler for event: {event_type}")
    
    async def _event_listener(self):
        """Background task to listen for events"""
        while True:
            try:
                # Check for Layer 1 events
                message = await self.receive_from_layer1()
                if message:
                    await self._handle_layer1_event(message)
                
                # Check for Layer 2 events
                message = await self.receive_from_layer2()
                if message:
                    await self._handle_layer2_event(message)
                
                await asyncio.sleep(0.1)  # 100ms interval
                
            except Exception as e:
                logger.error(f"Error in event listener: {e}")
                await asyncio.sleep(1)
    
    async def _handle_layer1_event(self, message: Dict[str, Any]):
        """Handle event from Layer 1"""
        event_type = message['event_type']
        
        if event_type in self.event_handlers:
            try:
                await self.event_handlers[event_type](message['data'])
            except Exception as e:
                logger.error(f"Error handling Layer 1 event {event_type}: {e}")
        else:
            logger.debug(f"No handler for Layer 1 event: {event_type}")
    
    async def _handle_layer2_event(self, message: Dict[str, Any]):
        """Handle event from Layer 2"""
        event_type = message['event_type']
        
        if event_type in self.event_handlers:
            try:
                await self.event_handlers[event_type](message['data'])
            except Exception as e:
                logger.error(f"Error handling Layer 2 event {event_type}: {e}")
        else:
            logger.debug(f"No handler for Layer 2 event: {event_type}")
    
    # Data Synchronization
    
    async def _background_sync(self):
        """Background task for data synchronization"""
        while True:
            try:
                await self._sync_data()
                await asyncio.sleep(self.sync_interval)
            except Exception as e:
                logger.error(f"Error in background sync: {e}")
                await asyncio.sleep(self.sync_interval)
    
    async def _sync_data(self):
        """Synchronize data between layers"""
        current_time = datetime.now()
        
        # Check if sync is needed
        if (current_time - self.last_sync_time).seconds < self.sync_interval:
            return
        
        try:
            # Perform data synchronization
            sync_data = {
                "timestamp": current_time.isoformat(),
                "layer1_status": await self._get_layer1_status(),
                "layer2_status": await self._get_layer2_status(),
                "sync_metrics": await self._get_sync_metrics()
            }
            
            # Store sync data
            sync_key = f"{self.sync_channel}:{current_time.timestamp()}"
            self.redis.setex(sync_key, 86400, json.dumps(sync_data))  # 24 hours TTL
            
            self.last_sync_time = current_time
            logger.debug("Data synchronization completed")
            
        except Exception as e:
            logger.error(f"Data synchronization failed: {e}")
    
    async def _get_layer1_status(self) -> Dict[str, Any]:
        """Get Layer 1 status (would connect to actual Layer 1)"""
        return {
            "status": "active",
            "services": ["embedding", "search", "tagging", "sync", "drive"],
            "last_activity": datetime.now().isoformat()
        }
    
    async def _get_layer2_status(self) -> Dict[str, Any]:
        """Get Layer 2 status"""
        return {
            "status": "active",
            "agents": ["orchestrator", "technical", "research", "creative"],
            "last_activity": datetime.now().isoformat()
        }
    
    async def _get_sync_metrics(self) -> Dict[str, Any]:
        """Get synchronization metrics"""
        return {
            "messages_sent": len(self.redis.smembers(f"{self.layer1_to_layer2_channel}:queue")) + 
                           len(self.redis.smembers(f"{self.layer2_to_layer1_channel}:queue")),
            "last_sync": self.last_sync_time.isoformat(),
            "sync_interval": self.sync_interval
        }
    
    # Utility Methods
    
    def get_bridge_status(self) -> Dict[str, Any]:
        """Get bridge status information"""
        return {
            "status": "active",
            "layer1_queue_size": len(self.redis.smembers(f"{self.layer1_to_layer2_channel}:queue")),
            "layer2_queue_size": len(self.redis.smembers(f"{self.layer2_to_layer1_channel}:queue")),
            "last_sync": self.last_sync_time.isoformat(),
            "event_handlers": list(self.event_handlers.keys())
        }
    
    def clear_queues(self):
        """Clear all message queues (for testing)"""
        self.redis.delete(f"{self.layer1_to_layer2_channel}:queue")
        self.redis.delete(f"{self.layer2_to_layer1_channel}:queue")
        logger.info("Message queues cleared")
    
    # ==================== Performance Optimization Methods ====================
    
    async def _batch_processor(self):
        """Background task for batch processing messages"""
        while True:
            try:
                await asyncio.sleep(self.batch_timeout)
                
                # Process Layer 1 batch
                if self.layer1_batch:
                    batch = list(self.layer1_batch)
                    self.layer1_batch.clear()
                    await self._process_message_batch(batch, "layer1")
                
                # Process Layer 2 batch
                if self.layer2_batch:
                    batch = list(self.layer2_batch)
                    self.layer2_batch.clear()
                    await self._process_message_batch(batch, "layer2")
                    
            except Exception as e:
                logger.error(f"Error in batch processor: {e}")
                await asyncio.sleep(1)
    
    async def _process_message_batch(self, batch: List[Dict[str, Any]], source: str):
        """Process a batch of messages efficiently"""
        if not batch:
            return
        
        start_time = time.time()
        
        try:
            # Process all messages in the batch
            for message in batch:
                await self._process_single_message_optimized(message, source)
            
            processing_time = time.time() - start_time
            self.metrics['processing_times'].append(processing_time)
            self.metrics['messages_batched'] += len(batch)
            
            logger.debug(f"Processed batch of {len(batch)} messages from {source} in {processing_time:.3f}s")
            
        except Exception as e:
            logger.error(f"Error processing message batch from {source}: {e}")
            # Add failed messages to retry queue
            for message in batch:
                self.failed_messages.append({
                    'message': message,
                    'source': source,
                    'failed_at': datetime.now(),
                    'retry_count': 0
                })
    
    async def _process_single_message_optimized(self, message: Dict[str, Any], source: str):
        """Process a single message with caching and optimization"""
        message_id = message.get('id', 'unknown')
        
        # Check cache first
        cache_key = self._get_cache_key(message)
        cached_result = self._get_from_cache(cache_key)
        
        if cached_result:
            self.metrics['cache_hits'] += 1
            logger.debug(f"Cache hit for message {message_id}")
            return cached_result
        
        # Process message
        self.metrics['cache_misses'] += 1
        result = await self._process_message_with_retry(message, source)
        
        # Cache result if successful
        if result:
            self._put_in_cache(cache_key, result)
        
        return result
    
    def _get_cache_key(self, message: Dict[str, Any]) -> str:
        """Generate cache key for message"""
        # Create deterministic key based on message content
        content = json.dumps(message.get('data', {}), sort_keys=True)
        event_type = message.get('event_type', '')
        return hashlib.md5(f"{event_type}:{content}".encode()).hexdigest()
    
    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get item from cache with TTL check"""
        if key not in self.message_cache:
            return None
        
        # Check TTL
        if key in self.cache_access_times:
            if time.time() - self.cache_access_times[key] > self.cache_ttl:
                self._evict_from_cache(key)
                return None
        
        # Update access time
        self.cache_access_times[key] = time.time()
        self.cache_stats['hits'] += 1
        return self.message_cache[key]
    
    def _put_in_cache(self, key: str, value: Dict[str, Any]):
        """Put item in cache with size management"""
        # Check cache size limit
        if len(self.message_cache) >= self.message_cache_size:
            self._evict_oldest_cache_item()
        
        self.message_cache[key] = value
        self.cache_access_times[key] = time.time()
    
    def _evict_from_cache(self, key: str):
        """Evict item from cache"""
        if key in self.message_cache:
            del self.message_cache[key]
        if key in self.cache_access_times:
            del self.cache_access_times[key]
        self.cache_stats['evictions'] += 1
    
    def _evict_oldest_cache_item(self):
        """Evict oldest item from cache"""
        if not self.cache_access_times:
            return
        
        oldest_key = min(self.cache_access_times.keys(), 
                        key=lambda k: self.cache_access_times[k])
        self._evict_from_cache(oldest_key)
    
    async def _cache_maintenance(self):
        """Background task for cache maintenance"""
        while True:
            try:
                current_time = time.time()
                keys_to_evict = []
                
                # Find expired keys
                for key, access_time in self.cache_access_times.items():
                    if current_time - access_time > self.cache_ttl:
                        keys_to_evict.append(key)
                
                # Evict expired keys
                for key in keys_to_evict:
                    self._evict_from_cache(key)
                
                if keys_to_evict:
                    logger.debug(f"Cache maintenance: evicted {len(keys_to_evict)} expired items")
                
                await asyncio.sleep(60)  # Run every minute
                
            except Exception as e:
                logger.error(f"Error in cache maintenance: {e}")
                await asyncio.sleep(60)
    
    # ==================== Error Recovery Methods ====================
    
    async def _process_message_with_retry(self, message: Dict[str, Any], source: str) -> Optional[Dict[str, Any]]:
        """Process message with retry logic"""
        last_error = None
        
        for attempt in range(self.retry_config['max_retries'] + 1):
            try:
                # Process the message
                if source == "layer1":
                    return await self._handle_layer1_event_safe(message)
                else:
                    return await self._handle_layer2_event_safe(message)
                    
            except Exception as e:
                last_error = e
                self.metrics['error_count'] += 1
                self.metrics['last_error_time'] = datetime.now()
                
                if attempt < self.retry_config['max_retries']:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(f"Message processing failed (attempt {attempt + 1}), retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Message processing failed after {self.retry_config['max_retries']} retries: {e}")
                    self.failed_messages.append({
                        'message': message,
                        'source': source,
                        'failed_at': datetime.now(),
                        'error': str(last_error),
                        'retry_count': self.retry_config['max_retries']
                    })
        
        return None
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff"""
        base_delay = self.retry_config['retry_delay']
        
        if self.retry_config['exponential_backoff']:
            return base_delay * (2 ** attempt)
        else:
            return base_delay
    
    async def _handle_layer1_event_safe(self, message: Dict[str, Any]):
        """Safely handle Layer 1 event with error handling"""
        event_type = message['event_type']
        
        if event_type in self.event_handlers:
            return await self.event_handlers[event_type](message['data'])
        else:
            logger.debug(f"No handler for Layer 1 event: {event_type}")
            return None
    
    async def _handle_layer2_event_safe(self, message: Dict[str, Any]):
        """Safely handle Layer 2 event with error handling"""
        event_type = message['event_type']
        
        if event_type in self.event_handlers:
            return await self.event_handlers[event_type](message['data'])
        else:
            logger.debug(f"No handler for Layer 2 event: {event_type}")
            return None
    
    # ==================== Performance Monitoring Methods ====================
    
    async def _performance_monitor(self):
        """Background task for performance monitoring"""
        while True:
            try:
                await asyncio.sleep(30)  # Monitor every 30 seconds
                
                # Calculate performance metrics
                metrics = self.get_performance_metrics()
                
                # Log performance summary
                if metrics['total_messages'] > 0:
                    logger.info(f"Performance Summary: "
                              f"Messages: {metrics['total_messages']}, "
                              f"Avg Processing Time: {metrics['avg_processing_time']:.3f}s, "
                              f"Cache Hit Rate: {metrics['cache_hit_rate']:.1%}, "
                              f"Error Rate: {metrics['error_rate']:.1%}")
                
                # Check for performance issues
                await self._check_performance_issues(metrics)
                
            except Exception as e:
                logger.error(f"Error in performance monitor: {e}")
                await asyncio.sleep(30)
    
    async def _check_performance_issues(self, metrics: Dict[str, Any]):
        """Check for performance issues and alert"""
        # High error rate
        if metrics['error_rate'] > 0.1:  # 10%
            logger.warning(f"High error rate detected: {metrics['error_rate']:.1%}")
        
        # Low cache hit rate
        if metrics['cache_hit_rate'] < 0.5 and metrics['total_messages'] > 100:  # 50%
            logger.warning(f"Low cache hit rate: {metrics['cache_hit_rate']:.1%}")
        
        # High processing time
        if metrics['avg_processing_time'] > 1.0:  # 1 second
            logger.warning(f"High average processing time: {metrics['avg_processing_time']:.3f}s")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics"""
        total_cache_operations = self.cache_stats['hits'] + self.cache_stats['misses']
        cache_hit_rate = self.cache_stats['hits'] / total_cache_operations if total_cache_operations > 0 else 0
        
        total_messages = self.metrics['messages_sent'] + self.metrics['messages_received']
        error_rate = self.metrics['error_count'] / total_messages if total_messages > 0 else 0
        
        processing_times = list(self.metrics['processing_times'])
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
        
        return {
            'total_messages': total_messages,
            'messages_sent': self.metrics['messages_sent'],
            'messages_received': self.metrics['messages_received'],
            'messages_batched': self.metrics['messages_batched'],
            'cache_hit_rate': cache_hit_rate,
            'cache_stats': self.cache_stats.copy(),
            'error_count': self.metrics['error_count'],
            'error_rate': error_rate,
            'failed_messages': len(self.failed_messages),
            'avg_processing_time': avg_processing_time,
            'last_error_time': self.metrics['last_error_time'],
            'cache_size': len(self.message_cache),
            'cache_memory_usage': len(json.dumps(self.message_cache))
        }
    
    async def retry_failed_messages(self):
        """Retry failed messages"""
        if not self.failed_messages:
            return
        
        logger.info(f"Retrying {len(self.failed_messages)} failed messages...")
        retry_count = 0
        
        while self.failed_messages and retry_count < 10:  # Limit retries per call
            failed_item = self.failed_messages.popleft()
            
            try:
                await self._process_message_with_retry(
                    failed_item['message'], 
                    failed_item['source']
                )
                retry_count += 1
                logger.debug(f"Successfully retried failed message: {failed_item['message'].get('id')}")
                
            except Exception as e:
                logger.error(f"Retry failed for message {failed_item['message'].get('id')}: {e}")
                # Put back in queue with incremented retry count
                failed_item['retry_count'] = failed_item.get('retry_count', 0) + 1
                if failed_item['retry_count'] < 5:  # Max 5 total retries
                    self.failed_messages.append(failed_item)


# Global bridge instance
layer_bridge = LayerBridge()


async def get_layer_bridge() -> LayerBridge:
    """Get global layer bridge instance"""
    return layer_bridge
