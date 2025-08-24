"""
Data Consistency Manager for ARGO Phase 2
Maintains consistency between Redis, Neo4j, BigQuery, and Vector stores
"""

import os
import json
import logging
import asyncio
import redis
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import pickle
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


class DataSource(Enum):
    """Data source types"""
    REDIS = "redis"          # Cache & session data
    NEO4J = "neo4j"         # Graph relationships
    BIGQUERY = "bigquery"   # Data warehouse
    VECTOR = "vector"       # Vector embeddings
    
    
class SyncOperation(Enum):
    """Synchronization operations"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    REFRESH = "refresh"


@dataclass
class SyncEvent:
    """Represents a synchronization event"""
    event_id: str
    timestamp: datetime
    source: DataSource
    operation: SyncOperation
    entity_type: str
    entity_id: str
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'event_id': self.event_id,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source.value,
            'operation': self.operation.value,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'data': self.data,
            'metadata': self.metadata
        }


@dataclass
class ConsistencyCheck:
    """Result of consistency check"""
    entity_type: str
    entity_id: str
    is_consistent: bool
    discrepancies: List[Dict[str, Any]]
    recommendations: List[str]
    
    
class DataConsistencyManager:
    """
    Manages data consistency across all data stores
    Implements event-driven synchronization with eventual consistency
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the consistency manager
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # Initialize connections
        self.redis_client = self._init_redis()
        self.neo4j_manager = None  # Lazy loading
        self.bigquery_manager = None  # Lazy loading
        self.vector_store = None  # Lazy loading
        
        # Sync queue and processing
        self.sync_queue = asyncio.Queue()
        self.processing = False
        self.sync_thread = None
        
        # Consistency tracking
        self.version_map: Dict[str, Dict[str, int]] = defaultdict(dict)  # entity_id -> {source: version}
        self.sync_log: List[SyncEvent] = []
        self.max_sync_log_size = 1000
        
        # Conflict resolution strategies
        self.conflict_strategies = {
            'last_write_wins': self._resolve_last_write_wins,
            'highest_confidence': self._resolve_highest_confidence,
            'manual': self._resolve_manual
        }
        
        # Cache invalidation rules
        self.cache_rules = {
            'knowledge': {'ttl': 3600, 'refresh_on_update': True},
            'context': {'ttl': 1800, 'refresh_on_update': True},
            'pattern': {'ttl': 7200, 'refresh_on_update': False},
            'agent': {'ttl': 300, 'refresh_on_update': True}
        }
        
        logger.info("DataConsistencyManager initialized")
    
    def _init_redis(self) -> redis.Redis:
        """Initialize Redis connection"""
        return redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            password=os.getenv('REDIS_PASSWORD', None),
            decode_responses=True
        )
    
    def _get_neo4j_manager(self):
        """Lazy load Neo4j manager"""
        if not self.neo4j_manager:
            from infrastructure.graph.neo4j_manager import Neo4jManager
            self.neo4j_manager = Neo4jManager()
        return self.neo4j_manager
    
    def _get_bigquery_manager(self):
        """Lazy load BigQuery manager"""
        if not self.bigquery_manager:
            from infrastructure.warehouse.bigquery_manager import BigQueryManager
            self.bigquery_manager = BigQueryManager()
        return self.bigquery_manager
    
    def _get_vector_store(self):
        """Lazy load vector store"""
        if not self.vector_store:
            from infrastructure.vector.vector_store import VectorStore
            self.vector_store = VectorStore()
        return self.vector_store
    
    # Event Publishing
    
    async def publish_change(self, source: DataSource, operation: SyncOperation,
                            entity_type: str, entity_id: str, data: Dict[str, Any]):
        """
        Publish a data change event for synchronization
        
        Args:
            source: Source of the change
            operation: Type of operation
            entity_type: Type of entity (e.g., 'knowledge', 'agent', 'task')
            entity_id: Unique identifier
            data: The data to sync
        """
        event = SyncEvent(
            event_id=self._generate_event_id(),
            timestamp=datetime.utcnow(),
            source=source,
            operation=operation,
            entity_type=entity_type,
            entity_id=entity_id,
            data=data,
            metadata={
                'version': self._get_next_version(entity_id, source.value)
            }
        )
        
        # Add to sync queue
        await self.sync_queue.put(event)
        
        # Log the event
        self._log_sync_event(event)
        
        # Publish to Redis for real-time subscribers
        self.redis_client.publish(
            f"sync:{entity_type}:{operation.value}",
            json.dumps(event.to_dict())
        )
        
        logger.debug(f"Published sync event: {event.event_id}")
    
    # Synchronization Processing
    
    async def start_sync_processor(self):
        """Start the synchronization processor"""
        self.processing = True
        
        while self.processing:
            try:
                # Get event from queue with timeout
                event = await asyncio.wait_for(
                    self.sync_queue.get(),
                    timeout=1.0
                )
                
                # Process the sync event
                await self._process_sync_event(event)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing sync event: {e}")
    
    async def _process_sync_event(self, event: SyncEvent):
        """Process a single sync event"""
        logger.debug(f"Processing sync event: {event.event_id}")
        
        # Determine target sources
        targets = self._get_sync_targets(event.source, event.entity_type)
        
        # Sync to each target
        for target in targets:
            try:
                await self._sync_to_target(event, target)
            except Exception as e:
                logger.error(f"Failed to sync to {target.value}: {e}")
                
                # Add to retry queue
                await self._add_to_retry_queue(event, target)
    
    def _get_sync_targets(self, source: DataSource, entity_type: str) -> List[DataSource]:
        """Determine which targets need synchronization"""
        # Sync matrix based on entity type and source
        sync_matrix = {
            'knowledge': {
                DataSource.REDIS: [DataSource.NEO4J, DataSource.BIGQUERY, DataSource.VECTOR],
                DataSource.NEO4J: [DataSource.REDIS, DataSource.BIGQUERY],
                DataSource.BIGQUERY: [DataSource.REDIS, DataSource.NEO4J],
                DataSource.VECTOR: [DataSource.REDIS]
            },
            'agent': {
                DataSource.REDIS: [DataSource.NEO4J, DataSource.BIGQUERY],
                DataSource.NEO4J: [DataSource.REDIS],
                DataSource.BIGQUERY: [DataSource.REDIS]
            },
            'task': {
                DataSource.REDIS: [DataSource.NEO4J, DataSource.BIGQUERY],
                DataSource.NEO4J: [DataSource.REDIS, DataSource.BIGQUERY],
                DataSource.BIGQUERY: [DataSource.REDIS]
            },
            'context': {
                DataSource.REDIS: [DataSource.BIGQUERY],
                DataSource.BIGQUERY: [DataSource.REDIS]
            },
            'pattern': {
                DataSource.REDIS: [DataSource.NEO4J, DataSource.BIGQUERY],
                DataSource.NEO4J: [DataSource.REDIS, DataSource.BIGQUERY],
                DataSource.BIGQUERY: [DataSource.REDIS, DataSource.NEO4J]
            }
        }
        
        return sync_matrix.get(entity_type, {}).get(source, [])
    
    async def _sync_to_target(self, event: SyncEvent, target: DataSource):
        """Sync event to a specific target"""
        if target == DataSource.REDIS:
            await self._sync_to_redis(event)
        elif target == DataSource.NEO4J:
            await self._sync_to_neo4j(event)
        elif target == DataSource.BIGQUERY:
            await self._sync_to_bigquery(event)
        elif target == DataSource.VECTOR:
            await self._sync_to_vector(event)
    
    async def _sync_to_redis(self, event: SyncEvent):
        """Sync to Redis cache"""
        key = f"{event.entity_type}:{event.entity_id}"
        
        if event.operation == SyncOperation.DELETE:
            self.redis_client.delete(key)
        else:
            # Set with TTL based on entity type
            ttl = self.cache_rules.get(event.entity_type, {}).get('ttl', 3600)
            self.redis_client.setex(
                key,
                ttl,
                json.dumps(event.data)
            )
            
            # Update version
            self._update_version(event.entity_id, DataSource.REDIS.value)
        
        # Invalidate related caches if needed
        if self.cache_rules.get(event.entity_type, {}).get('refresh_on_update'):
            await self._invalidate_related_caches(event.entity_type, event.entity_id)
    
    async def _sync_to_neo4j(self, event: SyncEvent):
        """Sync to Neo4j graph"""
        neo4j = self._get_neo4j_manager()
        
        if event.entity_type == 'knowledge':
            if event.operation == SyncOperation.DELETE:
                # Delete knowledge node
                query = """
                MATCH (k:Knowledge {knowledge_id: $knowledge_id})
                DETACH DELETE k
                """
                with neo4j.driver.session() as session:
                    session.run(query, knowledge_id=event.entity_id)
            else:
                # Create or update knowledge node
                neo4j.create_knowledge_node(
                    knowledge_id=event.entity_id,
                    knowledge_type=event.data.get('type', 'general'),
                    content=event.data,
                    embeddings=event.data.get('embeddings')
                )
        
        elif event.entity_type == 'agent':
            if event.operation != SyncOperation.DELETE:
                neo4j.create_agent_node(
                    agent_id=event.entity_id,
                    agent_type=event.data.get('type', 'unknown'),
                    capabilities=event.data.get('capabilities', [])
                )
        
        elif event.entity_type == 'task':
            if event.operation != SyncOperation.DELETE:
                neo4j.create_task_node(
                    task_id=event.entity_id,
                    task_type=event.data.get('type', 'general'),
                    goal_id=event.data.get('goal_id')
                )
        
        # Update version
        self._update_version(event.entity_id, DataSource.NEO4J.value)
    
    async def _sync_to_bigquery(self, event: SyncEvent):
        """Sync to BigQuery warehouse"""
        bq = self._get_bigquery_manager()
        
        if event.operation != SyncOperation.DELETE:
            if event.entity_type == 'knowledge':
                bq.insert_knowledge(
                    knowledge_type=event.data.get('type', 'general'),
                    content=event.data,
                    embeddings=event.data.get('embeddings'),
                    confidence=event.data.get('confidence', 1.0)
                )
            
            elif event.entity_type == 'agent':
                bq.insert_event(
                    event_type='agent_update',
                    content=event.data,
                    source='sync_manager',
                    agent_id=event.entity_id
                )
            
            elif event.entity_type == 'pattern':
                bq.insert_pattern(
                    pattern_type=event.data.get('type', 'general'),
                    pattern_data=event.data,
                    occurrences=event.data.get('occurrences', 1),
                    success_rate=event.data.get('success_rate')
                )
        
        # Update version
        self._update_version(event.entity_id, DataSource.BIGQUERY.value)
    
    async def _sync_to_vector(self, event: SyncEvent):
        """Sync to vector store"""
        vector_store = self._get_vector_store()
        
        if event.operation == SyncOperation.DELETE:
            await vector_store.delete(event.entity_id)
        else:
            embeddings = event.data.get('embeddings')
            if embeddings:
                await vector_store.upsert(
                    id=event.entity_id,
                    vector=embeddings,
                    metadata={
                        'entity_type': event.entity_type,
                        'content': json.dumps(event.data),
                        'timestamp': event.timestamp.isoformat()
                    }
                )
        
        # Update version
        self._update_version(event.entity_id, DataSource.VECTOR.value)
    
    # Consistency Checking
    
    async def check_consistency(self, entity_type: str, entity_id: str) -> ConsistencyCheck:
        """
        Check consistency of an entity across all data sources
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            
        Returns:
            ConsistencyCheck result
        """
        discrepancies = []
        recommendations = []
        
        # Get data from all sources
        data_sources = {}
        
        # Redis
        redis_key = f"{entity_type}:{entity_id}"
        redis_data = self.redis_client.get(redis_key)
        if redis_data:
            data_sources[DataSource.REDIS] = json.loads(redis_data)
        
        # Neo4j
        neo4j = self._get_neo4j_manager()
        if entity_type == 'knowledge':
            query = """
            MATCH (k:Knowledge {knowledge_id: $entity_id})
            RETURN k
            """
            with neo4j.driver.session() as session:
                result = session.run(query, entity_id=entity_id)
                record = result.single()
                if record:
                    data_sources[DataSource.NEO4J] = dict(record['k'])
        
        # BigQuery
        bq = self._get_bigquery_manager()
        if entity_type == 'knowledge':
            sql = f"""
            SELECT *
            FROM `{bq.project_id}.{bq.dataset_id}.knowledge_base`
            WHERE knowledge_id = '{entity_id}'
            LIMIT 1
            """
            result = bq.query(sql)
            if result.rows:
                data_sources[DataSource.BIGQUERY] = result.rows[0]
        
        # Compare versions
        versions = self.version_map.get(entity_id, {})
        if versions:
            max_version = max(versions.values())
            for source, version in versions.items():
                if version < max_version:
                    discrepancies.append({
                        'source': source,
                        'issue': 'outdated_version',
                        'current_version': version,
                        'latest_version': max_version
                    })
                    recommendations.append(f"Sync {source} to latest version")
        
        # Compare data content
        if len(data_sources) > 1:
            reference_data = list(data_sources.values())[0]
            for source, data in data_sources.items():
                if data != reference_data:
                    discrepancies.append({
                        'source': source.value,
                        'issue': 'data_mismatch',
                        'differences': self._find_differences(reference_data, data)
                    })
        
        is_consistent = len(discrepancies) == 0
        
        return ConsistencyCheck(
            entity_type=entity_type,
            entity_id=entity_id,
            is_consistent=is_consistent,
            discrepancies=discrepancies,
            recommendations=recommendations
        )
    
    def _find_differences(self, data1: Dict, data2: Dict) -> List[str]:
        """Find differences between two data dictionaries"""
        differences = []
        
        all_keys = set(data1.keys()) | set(data2.keys())
        for key in all_keys:
            if key not in data1:
                differences.append(f"Missing key '{key}' in first dataset")
            elif key not in data2:
                differences.append(f"Missing key '{key}' in second dataset")
            elif data1[key] != data2[key]:
                differences.append(f"Different values for '{key}'")
        
        return differences
    
    # Conflict Resolution
    
    async def resolve_conflict(self, entity_type: str, entity_id: str, 
                              strategy: str = 'last_write_wins') -> Dict[str, Any]:
        """
        Resolve conflicts for an entity
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            strategy: Resolution strategy
            
        Returns:
            Resolution result
        """
        if strategy not in self.conflict_strategies:
            raise ValueError(f"Unknown strategy: {strategy}")
        
        # Get all versions of the data
        all_data = await self._get_all_versions(entity_type, entity_id)
        
        # Apply resolution strategy
        resolver = self.conflict_strategies[strategy]
        resolved_data = resolver(all_data)
        
        # Sync resolved data to all sources
        await self.publish_change(
            source=DataSource.REDIS,  # Use Redis as the source for resolved data
            operation=SyncOperation.UPDATE,
            entity_type=entity_type,
            entity_id=entity_id,
            data=resolved_data
        )
        
        return {
            'entity_id': entity_id,
            'strategy': strategy,
            'resolved_data': resolved_data,
            'synced': True
        }
    
    def _resolve_last_write_wins(self, all_data: Dict[DataSource, Dict]) -> Dict:
        """Last write wins resolution"""
        # Find the most recent update
        latest_data = None
        latest_time = datetime.min
        
        for source, data in all_data.items():
            timestamp = data.get('updated_at') or data.get('timestamp')
            if timestamp:
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp)
                if timestamp > latest_time:
                    latest_time = timestamp
                    latest_data = data
        
        return latest_data or {}
    
    def _resolve_highest_confidence(self, all_data: Dict[DataSource, Dict]) -> Dict:
        """Highest confidence resolution"""
        highest_confidence = -1
        best_data = None
        
        for source, data in all_data.items():
            confidence = data.get('confidence', 0)
            if confidence > highest_confidence:
                highest_confidence = confidence
                best_data = data
        
        return best_data or {}
    
    def _resolve_manual(self, all_data: Dict[DataSource, Dict]) -> Dict:
        """Manual resolution (returns conflict info for manual resolution)"""
        return {
            'conflict': True,
            'sources': {source.value: data for source, data in all_data.items()},
            'requires_manual_resolution': True
        }
    
    # Cache Management
    
    async def _invalidate_related_caches(self, entity_type: str, entity_id: str):
        """Invalidate related caches"""
        # Get related entities
        pattern = f"{entity_type}:*:related:{entity_id}"
        related_keys = self.redis_client.keys(pattern)
        
        # Delete related caches
        if related_keys:
            self.redis_client.delete(*related_keys)
            logger.debug(f"Invalidated {len(related_keys)} related caches")
    
    async def refresh_cache(self, entity_type: str, entity_id: str) -> bool:
        """Refresh cache from authoritative source"""
        # Determine authoritative source based on entity type
        auth_source = {
            'knowledge': DataSource.NEO4J,
            'agent': DataSource.NEO4J,
            'task': DataSource.NEO4J,
            'context': DataSource.BIGQUERY,
            'pattern': DataSource.BIGQUERY
        }.get(entity_type, DataSource.NEO4J)
        
        # Get data from authoritative source
        data = await self._get_from_source(auth_source, entity_type, entity_id)
        
        if data:
            # Update cache
            await self._sync_to_redis(SyncEvent(
                event_id=self._generate_event_id(),
                timestamp=datetime.utcnow(),
                source=auth_source,
                operation=SyncOperation.REFRESH,
                entity_type=entity_type,
                entity_id=entity_id,
                data=data
            ))
            return True
        
        return False
    
    async def _get_from_source(self, source: DataSource, entity_type: str, 
                               entity_id: str) -> Optional[Dict]:
        """Get data from a specific source"""
        if source == DataSource.NEO4J:
            neo4j = self._get_neo4j_manager()
            # Implementation depends on entity type
            # ... (query Neo4j)
            
        elif source == DataSource.BIGQUERY:
            bq = self._get_bigquery_manager()
            # Implementation depends on entity type
            # ... (query BigQuery)
            
        return None
    
    async def _get_all_versions(self, entity_type: str, entity_id: str) -> Dict[DataSource, Dict]:
        """Get all versions of an entity from all sources"""
        all_versions = {}
        
        # Get from each source
        for source in DataSource:
            data = await self._get_from_source(source, entity_type, entity_id)
            if data:
                all_versions[source] = data
        
        return all_versions
    
    # Retry Queue Management
    
    async def _add_to_retry_queue(self, event: SyncEvent, target: DataSource):
        """Add failed sync to retry queue"""
        retry_key = f"retry:{target.value}:{event.entity_type}:{event.entity_id}"
        retry_data = {
            'event': event.to_dict(),
            'target': target.value,
            'attempts': 1,
            'next_retry': (datetime.utcnow() + timedelta(seconds=30)).isoformat()
        }
        
        self.redis_client.setex(
            retry_key,
            3600,  # 1 hour TTL
            json.dumps(retry_data)
        )
    
    async def process_retry_queue(self):
        """Process retry queue"""
        retry_keys = self.redis_client.keys("retry:*")
        
        for key in retry_keys:
            retry_data = self.redis_client.get(key)
            if retry_data:
                retry_info = json.loads(retry_data)
                
                # Check if it's time to retry
                next_retry = datetime.fromisoformat(retry_info['next_retry'])
                if datetime.utcnow() >= next_retry:
                    # Recreate event
                    event_dict = retry_info['event']
                    event = SyncEvent(
                        event_id=event_dict['event_id'],
                        timestamp=datetime.fromisoformat(event_dict['timestamp']),
                        source=DataSource(event_dict['source']),
                        operation=SyncOperation(event_dict['operation']),
                        entity_type=event_dict['entity_type'],
                        entity_id=event_dict['entity_id'],
                        data=event_dict['data'],
                        metadata=event_dict.get('metadata', {})
                    )
                    
                    # Retry sync
                    target = DataSource(retry_info['target'])
                    try:
                        await self._sync_to_target(event, target)
                        # Success - remove from retry queue
                        self.redis_client.delete(key)
                    except Exception as e:
                        # Failed again - update retry info
                        retry_info['attempts'] += 1
                        if retry_info['attempts'] < 5:
                            # Exponential backoff
                            delay = 30 * (2 ** retry_info['attempts'])
                            retry_info['next_retry'] = (
                                datetime.utcnow() + timedelta(seconds=delay)
                            ).isoformat()
                            self.redis_client.setex(key, 3600, json.dumps(retry_info))
                        else:
                            # Max retries reached - log and remove
                            logger.error(f"Max retries reached for {key}")
                            self.redis_client.delete(key)
    
    # Utility Methods
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        return hashlib.md5(
            f"{datetime.utcnow().isoformat()}:{os.urandom(16).hex()}".encode()
        ).hexdigest()
    
    def _get_next_version(self, entity_id: str, source: str) -> int:
        """Get next version number for an entity"""
        current = self.version_map[entity_id].get(source, 0)
        next_version = current + 1
        self.version_map[entity_id][source] = next_version
        return next_version
    
    def _update_version(self, entity_id: str, source: str):
        """Update version for an entity"""
        self.version_map[entity_id][source] = self.version_map[entity_id].get(source, 0) + 1
    
    def _log_sync_event(self, event: SyncEvent):
        """Log sync event for audit"""
        self.sync_log.append(event)
        
        # Trim log if too large
        if len(self.sync_log) > self.max_sync_log_size:
            self.sync_log = self.sync_log[-self.max_sync_log_size:]
        
        # Also log to BigQuery for long-term storage
        try:
            bq = self._get_bigquery_manager()
            bq.insert_audit_log(
                action=f"sync_{event.operation.value}",
                actor="consistency_manager",
                resource_type=event.entity_type,
                resource_id=event.entity_id,
                result="pending",
                details=event.to_dict()
            )
        except Exception as e:
            logger.error(f"Failed to log sync event to BigQuery: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get consistency manager statistics"""
        return {
            'sync_queue_size': self.sync_queue.qsize(),
            'total_sync_events': len(self.sync_log),
            'entities_tracked': len(self.version_map),
            'retry_queue_size': len(self.redis_client.keys("retry:*")),
            'cache_rules': self.cache_rules,
            'processing': self.processing
        }
    
    async def shutdown(self):
        """Gracefully shutdown the consistency manager"""
        logger.info("Shutting down DataConsistencyManager")
        
        # Stop processing
        self.processing = False
        
        # Process remaining items in queue
        while not self.sync_queue.empty():
            try:
                event = self.sync_queue.get_nowait()
                await self._process_sync_event(event)
            except:
                break
        
        # Close connections
        if self.neo4j_manager:
            self.neo4j_manager.close()
        
        logger.info("DataConsistencyManager shutdown complete")