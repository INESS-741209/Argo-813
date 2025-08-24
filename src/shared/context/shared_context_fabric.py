"""
Shared Context Fabric for ARGO Phase 2
Implements triple memory system mimicking human cognitive structure
"""

import json
import redis
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, asdict
from collections import deque
import hashlib
import pickle

logger = logging.getLogger(__name__)


@dataclass
class MemoryItem:
    """Base class for memory items"""
    id: str
    timestamp: datetime
    content: Any
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'content': self.content,
            'metadata': self.metadata
        }


class EpisodicMemory:
    """
    Short-term working memory for current session
    Maintains sliding window of recent activities
    """
    
    def __init__(self, redis_client: redis.Redis, max_size: int = 1000, ttl_hours: int = 48):
        self.redis = redis_client
        self.max_size = max_size
        self.ttl_seconds = ttl_hours * 3600
        self.buffer = deque(maxlen=max_size)
        self.namespace = "episodic"
        logger.info(f"EpisodicMemory initialized (max_size={max_size}, ttl={ttl_hours}h)")
    
    def store(self, session_id: str, item: Dict[str, Any]) -> str:
        """Store an item in episodic memory"""
        memory_id = f"{self.namespace}:{session_id}:{datetime.now().timestamp()}"
        
        memory_item = MemoryItem(
            id=memory_id,
            timestamp=datetime.now(),
            content=item.get('content'),
            metadata={
                'session_id': session_id,
                'type': item.get('type', 'general'),
                'source': item.get('source', 'unknown')
            }
        )
        
        # Store in Redis with TTL
        key = f"memory:{memory_id}"
        self.redis.setex(
            key,
            self.ttl_seconds,
            json.dumps(memory_item.to_dict())
        )
        
        # Add to session index
        session_key = f"session:{session_id}:episodic"
        self.redis.sadd(session_key, memory_id)
        self.redis.expire(session_key, self.ttl_seconds)
        
        # Update local buffer
        self.buffer.append(memory_item)
        
        logger.debug(f"Stored episodic memory: {memory_id}")
        return memory_id
    
    def retrieve(self, session_id: str, limit: int = 10) -> List[Dict]:
        """Retrieve recent memories for a session"""
        session_key = f"session:{session_id}:episodic"
        memory_ids = self.redis.smembers(session_key)
        
        memories = []
        for memory_id in list(memory_ids)[:limit]:
            key = f"memory:{memory_id}"
            data = self.redis.get(key)
            if data:
                memories.append(json.loads(data))
        
        # Sort by timestamp (most recent first)
        memories.sort(key=lambda x: x['timestamp'], reverse=True)
        return memories
    
    def get_context_window(self, session_id: str, window_size: int = 5) -> Dict[str, Any]:
        """Get sliding window context for current work"""
        recent_memories = self.retrieve(session_id, window_size)
        
        return {
            'current_goal': self._extract_current_goal(recent_memories),
            'active_tasks': self._extract_active_tasks(recent_memories),
            'recent_decisions': self._extract_decisions(recent_memories),
            'conversation_buffer': recent_memories
        }
    
    def _extract_current_goal(self, memories: List[Dict]) -> Optional[str]:
        """Extract current goal from memories"""
        for memory in memories:
            if memory.get('metadata', {}).get('type') == 'goal':
                return memory.get('content')
        return None
    
    def _extract_active_tasks(self, memories: List[Dict]) -> List[str]:
        """Extract active tasks from memories"""
        tasks = []
        for memory in memories:
            if memory.get('metadata', {}).get('type') == 'task':
                tasks.append(memory.get('content'))
        return tasks
    
    def _extract_decisions(self, memories: List[Dict]) -> List[Dict]:
        """Extract recent decisions from memories"""
        decisions = []
        for memory in memories:
            if memory.get('metadata', {}).get('type') == 'decision':
                decisions.append({
                    'decision': memory.get('content'),
                    'timestamp': memory.get('timestamp')
                })
        return decisions


class SemanticMemory:
    """
    Long-term knowledge storage
    Maintains permanent knowledge base with vector embeddings
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.namespace = "semantic"
        self.index_name = "knowledge_index"
        logger.info("SemanticMemory initialized")
    
    def store(self, knowledge_id: str, content: Dict[str, Any], embeddings: Optional[List[float]] = None) -> str:
        """Store knowledge in semantic memory"""
        memory_id = f"{self.namespace}:{knowledge_id}"
        
        knowledge_item = {
            'id': memory_id,
            'timestamp': datetime.now().isoformat(),
            'content': content,
            'embeddings': embeddings or [],
            'metadata': {
                'type': content.get('type', 'knowledge'),
                'domain': content.get('domain', 'general'),
                'confidence': content.get('confidence', 1.0)
            }
        }
        
        # Store in Redis (permanent)
        key = f"knowledge:{memory_id}"
        self.redis.set(key, json.dumps(knowledge_item))
        
        # Add to knowledge index
        index_key = f"index:{self.index_name}"
        self.redis.sadd(index_key, memory_id)
        
        # Store embeddings separately for vector search
        if embeddings:
            embedding_key = f"embedding:{memory_id}"
            self.redis.set(embedding_key, pickle.dumps(embeddings))
        
        logger.debug(f"Stored semantic memory: {memory_id}")
        return memory_id
    
    def retrieve(self, query: str, limit: int = 5) -> List[Dict]:
        """Retrieve relevant knowledge (simplified without actual vector search)"""
        # In production, would use vector similarity search
        # For now, return recent knowledge items
        
        index_key = f"index:{self.index_name}"
        knowledge_ids = self.redis.smembers(index_key)
        
        results = []
        for knowledge_id in list(knowledge_ids)[:limit]:
            key = f"knowledge:{knowledge_id}"
            data = self.redis.get(key)
            if data:
                results.append(json.loads(data))
        
        return results
    
    def update_knowledge_graph(self, entity1: str, relation: str, entity2: str):
        """Update knowledge graph relationships"""
        # Simplified graph storage using Redis sets
        graph_key = f"graph:{entity1}:{relation}"
        self.redis.sadd(graph_key, entity2)
        
        # Store reverse relation for bidirectional queries
        reverse_key = f"graph:{entity2}:related_to"
        self.redis.sadd(reverse_key, entity1)
        
        logger.debug(f"Updated knowledge graph: {entity1} -{relation}-> {entity2}")
    
    def get_related_knowledge(self, entity: str, relation_type: Optional[str] = None) -> List[str]:
        """Get related knowledge entities"""
        if relation_type:
            graph_key = f"graph:{entity}:{relation_type}"
        else:
            graph_key = f"graph:{entity}:*"
        
        related = set()
        for key in self.redis.scan_iter(match=graph_key):
            related.update(self.redis.smembers(key))
        
        return list(related)


class ProceduralMemory:
    """
    Learned patterns and skills
    Stores successful patterns and optimization rules
    """
    
    def __init__(self, redis_client: redis.Redis, learning_rate: float = 0.1):
        self.redis = redis_client
        self.namespace = "procedural"
        self.learning_rate = learning_rate
        self.pattern_threshold = 3  # Minimum occurrences to learn pattern
        logger.info(f"ProceduralMemory initialized (learning_rate={learning_rate})")
    
    def record_pattern(self, pattern_type: str, pattern_data: Dict[str, Any], success: bool = True):
        """Record a pattern occurrence"""
        pattern_id = self._generate_pattern_id(pattern_type, pattern_data)
        pattern_key = f"pattern:{pattern_id}"
        
        # Get existing pattern data
        existing = self.redis.get(pattern_key)
        if existing:
            pattern_info = json.loads(existing)
            pattern_info['occurrences'] += 1
            pattern_info['success_count'] += 1 if success else 0
            pattern_info['success_rate'] = pattern_info['success_count'] / pattern_info['occurrences']
        else:
            pattern_info = {
                'id': pattern_id,
                'type': pattern_type,
                'pattern': pattern_data,
                'occurrences': 1,
                'success_count': 1 if success else 0,
                'success_rate': 1.0 if success else 0.0,
                'first_seen': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat()
            }
        
        pattern_info['last_seen'] = datetime.now().isoformat()
        
        # Store updated pattern
        self.redis.set(pattern_key, json.dumps(pattern_info))
        
        # Add to pattern index if threshold met
        if pattern_info['occurrences'] >= self.pattern_threshold:
            index_key = f"patterns:{pattern_type}"
            self.redis.sadd(index_key, pattern_id)
            logger.info(f"Pattern learned: {pattern_id} (occurrences={pattern_info['occurrences']})")
    
    def get_applicable_patterns(self, context: Dict[str, Any]) -> List[Dict]:
        """Get patterns applicable to current context"""
        applicable = []
        
        # Check each pattern type
        pattern_types = ['task_execution', 'optimization', 'error_recovery', 'decision_making']
        
        for pattern_type in pattern_types:
            index_key = f"patterns:{pattern_type}"
            pattern_ids = self.redis.smembers(index_key)
            
            for pattern_id in pattern_ids:
                pattern_key = f"pattern:{pattern_id}"
                pattern_data = self.redis.get(pattern_key)
                
                if pattern_data:
                    pattern = json.loads(pattern_data)
                    # Check if pattern is applicable (simplified)
                    if pattern['success_rate'] > 0.7:  # Only use successful patterns
                        applicable.append(pattern)
        
        # Sort by success rate
        applicable.sort(key=lambda x: x['success_rate'], reverse=True)
        return applicable[:5]  # Return top 5 patterns
    
    def learn_optimization(self, optimization_type: str, before_metrics: Dict, after_metrics: Dict):
        """Learn from optimization results"""
        improvement = self._calculate_improvement(before_metrics, after_metrics)
        
        if improvement > 0:
            optimization_data = {
                'type': optimization_type,
                'improvement': improvement,
                'before': before_metrics,
                'after': after_metrics,
                'timestamp': datetime.now().isoformat()
            }
            
            # Store as successful pattern
            self.record_pattern('optimization', optimization_data, success=True)
            
            # Update optimization rules
            rule_key = f"optimization_rule:{optimization_type}"
            self.redis.set(rule_key, json.dumps(optimization_data))
            
            logger.info(f"Learned optimization: {optimization_type} (improvement={improvement:.2%})")
    
    def _generate_pattern_id(self, pattern_type: str, pattern_data: Dict) -> str:
        """Generate unique pattern ID"""
        pattern_str = f"{pattern_type}:{json.dumps(pattern_data, sort_keys=True)}"
        return hashlib.md5(pattern_str.encode()).hexdigest()[:16]
    
    def _calculate_improvement(self, before: Dict, after: Dict) -> float:
        """Calculate improvement percentage"""
        # Simplified calculation - in production would be more sophisticated
        before_score = sum(before.values()) if isinstance(list(before.values())[0], (int, float)) else 0
        after_score = sum(after.values()) if isinstance(list(after.values())[0], (int, float)) else 0
        
        if before_score == 0:
            return 0
        
        return (after_score - before_score) / before_score


class SharedContextFabric:
    """
    Main context fabric combining all three memory systems
    Provides unified interface for context management
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None, config: Optional[Dict] = None):
        """Initialize the shared context fabric"""
        import os
        
        # Initialize Redis client if not provided
        if redis_client:
            self.redis = redis_client
        else:
            self.redis = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                password=os.getenv('REDIS_PASSWORD', None),
                decode_responses=True
            )
        
        config = config or {}
        
        # Initialize memory systems
        self.episodic_memory = EpisodicMemory(
            self.redis,
            max_size=config.get('episodic_max_size', 1000),
            ttl_hours=config.get('episodic_ttl_hours', 48)
        )
        
        self.semantic_memory = SemanticMemory(self.redis)
        
        self.procedural_memory = ProceduralMemory(
            self.redis,
            learning_rate=config.get('learning_rate', 0.1)
        )
        
        logger.info("SharedContextFabric initialized with triple memory system")
    
    def store_event(self, session_id: str, event: Dict[str, Any]) -> Dict[str, str]:
        """Store an event across appropriate memory systems"""
        results = {}
        
        # Always store in episodic memory
        episodic_id = self.episodic_memory.store(session_id, event)
        results['episodic_id'] = episodic_id
        
        # Store in semantic memory if it's knowledge
        if event.get('type') in ['knowledge', 'fact', 'definition']:
            semantic_id = self.semantic_memory.store(
                event.get('id', episodic_id),
                event,
                event.get('embeddings')
            )
            results['semantic_id'] = semantic_id
        
        # Record pattern if it's a task or decision
        if event.get('type') in ['task', 'decision', 'action']:
            self.procedural_memory.record_pattern(
                event.get('type'),
                event,
                event.get('success', True)
            )
            results['pattern_recorded'] = True
        
        return results
    
    def get_full_context(self, session_id: str, query: Optional[str] = None) -> Dict[str, Any]:
        """Get complete context from all memory systems"""
        
        # Get episodic context (current session)
        episodic_context = self.episodic_memory.get_context_window(session_id)
        
        # Get relevant semantic knowledge
        semantic_context = []
        if query:
            semantic_context = self.semantic_memory.retrieve(query)
        
        # Get applicable procedural patterns
        procedural_context = self.procedural_memory.get_applicable_patterns(episodic_context)
        
        return {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'episodic': episodic_context,
            'semantic': semantic_context,
            'procedural': procedural_context,
            'summary': self._generate_context_summary(episodic_context, semantic_context, procedural_context)
        }
    
    def _generate_context_summary(self, episodic: Dict, semantic: List, procedural: List) -> Dict:
        """Generate summary of current context"""
        return {
            'current_goal': episodic.get('current_goal'),
            'active_tasks_count': len(episodic.get('active_tasks', [])),
            'available_knowledge_count': len(semantic),
            'applicable_patterns_count': len(procedural),
            'recommended_pattern': procedural[0] if procedural else None
        }
    
    def learn_from_outcome(self, session_id: str, task_id: str, outcome: Dict[str, Any]):
        """Learn from task outcome"""
        # Record in episodic memory
        self.episodic_memory.store(session_id, {
            'type': 'outcome',
            'task_id': task_id,
            'content': outcome
        })
        
        # Learn pattern if successful
        if outcome.get('success'):
            self.procedural_memory.record_pattern(
                'successful_task',
                {
                    'task_id': task_id,
                    'approach': outcome.get('approach'),
                    'metrics': outcome.get('metrics')
                },
                success=True
            )
        
        # Update knowledge if new insights gained
        if outcome.get('insights'):
            for insight in outcome.get('insights', []):
                self.semantic_memory.store(
                    f"insight_{task_id}_{insight.get('id')}",
                    insight
                )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        return {
            'episodic': {
                'buffer_size': len(self.episodic_memory.buffer),
                'max_size': self.episodic_memory.max_size
            },
            'semantic': {
                'knowledge_count': self.redis.scard(f"index:{self.semantic_memory.index_name}")
            },
            'procedural': {
                'learned_patterns': sum(
                    self.redis.scard(f"patterns:{ptype}")
                    for ptype in ['task_execution', 'optimization', 'error_recovery', 'decision_making']
                )
            }
        }