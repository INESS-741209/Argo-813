"""
Agent Message Protocol v2.0 for ARGO Phase 2
Enhanced inter-agent communication protocol with priority handling
"""

import json
import uuid
import redis
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Literal, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
from collections import defaultdict

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Message types for agent communication"""
    # Basic types
    REQUEST = "request"
    RESPONSE = "response"
    BROADCAST = "broadcast"
    
    # Collaboration types
    PROPOSAL = "proposal"
    CHALLENGE = "challenge"
    CONSENSUS = "consensus"
    ESCALATION = "escalation"
    
    # Learning types
    INSIGHT = "insight"
    PATTERN = "pattern"
    OPTIMIZATION = "optimization"
    
    # Control types
    HEARTBEAT = "heartbeat"
    STATUS = "status"
    ERROR = "error"


class Priority(Enum):
    """Message priority levels"""
    CRITICAL = "critical"  # 30 seconds SLA
    URGENT = "urgent"      # 5 minutes SLA
    HIGH = "high"          # 30 minutes SLA
    NORMAL = "normal"      # 2 hours SLA
    LOW = "low"            # 24 hours SLA
    
    @property
    def sla_seconds(self) -> int:
        """Get SLA in seconds"""
        sla_map = {
            Priority.CRITICAL: 30,
            Priority.URGENT: 300,
            Priority.HIGH: 1800,
            Priority.NORMAL: 7200,
            Priority.LOW: 86400
        }
        return sla_map[self]


@dataclass
class AgentMessage:
    """
    Enhanced agent message structure
    """
    # Header
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_agent: str = ""
    recipient_agents: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    priority: Priority = Priority.NORMAL
    
    # Body
    message_type: MessageType = MessageType.REQUEST
    content: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    correlation_id: Optional[str] = None
    requires_approval: bool = False
    ttl_seconds: int = 3600
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict:
        """Convert message to dictionary"""
        return {
            'message_id': self.message_id,
            'sender_agent': self.sender_agent,
            'recipient_agents': self.recipient_agents,
            'timestamp': self.timestamp.isoformat(),
            'priority': self.priority.value,
            'message_type': self.message_type.value,
            'content': self.content,
            'correlation_id': self.correlation_id,
            'requires_approval': self.requires_approval,
            'ttl_seconds': self.ttl_seconds,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentMessage':
        """Create message from dictionary"""
        return cls(
            message_id=data.get('message_id', str(uuid.uuid4())),
            sender_agent=data.get('sender_agent', ''),
            recipient_agents=data.get('recipient_agents', []),
            timestamp=datetime.fromisoformat(data.get('timestamp', datetime.now().isoformat())),
            priority=Priority(data.get('priority', 'normal')),
            message_type=MessageType(data.get('message_type', 'request')),
            content=data.get('content', {}),
            correlation_id=data.get('correlation_id'),
            requires_approval=data.get('requires_approval', False),
            ttl_seconds=data.get('ttl_seconds', 3600),
            retry_count=data.get('retry_count', 0),
            max_retries=data.get('max_retries', 3)
        )
    
    def is_expired(self) -> bool:
        """Check if message has expired"""
        age = (datetime.now() - self.timestamp).total_seconds()
        return age > self.ttl_seconds
    
    def can_retry(self) -> bool:
        """Check if message can be retried"""
        return self.retry_count < self.max_retries


class MessageRouter:
    """
    Routes messages between agents based on type and priority
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """Initialize the message router"""
        import os
        
        if redis_client:
            self.redis = redis_client
        else:
            self.redis = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                password=os.getenv('REDIS_PASSWORD', None),
                decode_responses=True
            )
        
        # Message queues by priority
        self.priority_queues = {
            Priority.CRITICAL: "queue:critical",
            Priority.URGENT: "queue:urgent",
            Priority.HIGH: "queue:high",
            Priority.NORMAL: "queue:normal",
            Priority.LOW: "queue:low"
        }
        
        # Agent subscriptions
        self.subscriptions = defaultdict(set)
        
        # Message handlers
        self.handlers: Dict[MessageType, List[Callable]] = defaultdict(list)
        
        # Statistics
        self.stats = defaultdict(int)
        
        logger.info("MessageRouter initialized")
    
    async def send_message(self, message: AgentMessage) -> str:
        """
        Send a message to recipients
        
        Args:
            message: The message to send
            
        Returns:
            Message ID
        """
        # Validate message
        if not message.sender_agent:
            raise ValueError("Message must have a sender_agent")
        
        # Set timestamp if not set
        if not message.timestamp:
            message.timestamp = datetime.now()
        
        # Route based on recipients
        if "*" in message.recipient_agents:
            # Broadcast message
            await self._broadcast_message(message)
        elif message.recipient_agents:
            # Send to specific agents
            for recipient in message.recipient_agents:
                await self._route_to_agent(message, recipient)
        else:
            # Route based on message type
            await self._route_by_type(message)
        
        # Update statistics
        self.stats[f"sent_{message.priority.value}"] += 1
        self.stats[f"sent_{message.message_type.value}"] += 1
        
        logger.debug(f"Message sent: {message.message_id} from {message.sender_agent}")
        return message.message_id
    
    async def _broadcast_message(self, message: AgentMessage):
        """Broadcast message to all agents"""
        broadcast_key = "broadcast:messages"
        
        # Store message
        self.redis.lpush(broadcast_key, json.dumps(message.to_dict()))
        self.redis.ltrim(broadcast_key, 0, 999)  # Keep last 1000 broadcasts
        
        # Publish to pub/sub channel
        self.redis.publish("broadcast_channel", json.dumps(message.to_dict()))
        
        logger.info(f"Broadcast message: {message.message_id}")
    
    async def _route_to_agent(self, message: AgentMessage, recipient: str):
        """Route message to specific agent"""
        # Get appropriate queue based on priority
        queue_key = f"agent:{recipient}:{self.priority_queues[message.priority]}"
        
        # Add to queue
        self.redis.lpush(queue_key, json.dumps(message.to_dict()))
        
        # Set expiration based on TTL
        self.redis.expire(queue_key, message.ttl_seconds)
        
        # Send notification if critical
        if message.priority == Priority.CRITICAL:
            self.redis.publish(f"agent:{recipient}:notifications", message.message_id)
    
    async def _route_by_type(self, message: AgentMessage):
        """Route message based on type"""
        # Find agents subscribed to this message type
        type_key = f"subscriptions:{message.message_type.value}"
        subscribers = self.redis.smembers(type_key)
        
        for subscriber in subscribers:
            await self._route_to_agent(message, subscriber)
    
    async def receive_messages(self, agent_id: str, max_messages: int = 10) -> List[AgentMessage]:
        """
        Receive messages for an agent
        
        Args:
            agent_id: The agent ID
            max_messages: Maximum number of messages to receive
            
        Returns:
            List of messages
        """
        messages = []
        
        # Check queues in priority order
        for priority in [Priority.CRITICAL, Priority.URGENT, Priority.HIGH, Priority.NORMAL, Priority.LOW]:
            queue_key = f"agent:{agent_id}:{self.priority_queues[priority]}"
            
            # Get messages from queue
            for _ in range(max_messages - len(messages)):
                message_data = self.redis.rpop(queue_key)
                if message_data:
                    try:
                        message = AgentMessage.from_dict(json.loads(message_data))
                        
                        # Check if expired
                        if not message.is_expired():
                            messages.append(message)
                        else:
                            logger.warning(f"Dropped expired message: {message.message_id}")
                            self.stats["expired_messages"] += 1
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                
                if len(messages) >= max_messages:
                    break
            
            if len(messages) >= max_messages:
                break
        
        # Update statistics
        self.stats[f"received_{agent_id}"] += len(messages)
        
        return messages
    
    def subscribe(self, agent_id: str, message_types: List[MessageType]):
        """Subscribe agent to message types"""
        for msg_type in message_types:
            type_key = f"subscriptions:{msg_type.value}"
            self.redis.sadd(type_key, agent_id)
            self.subscriptions[agent_id].add(msg_type)
        
        logger.info(f"Agent {agent_id} subscribed to {[t.value for t in message_types]}")
    
    def unsubscribe(self, agent_id: str, message_types: Optional[List[MessageType]] = None):
        """Unsubscribe agent from message types"""
        if message_types is None:
            message_types = list(self.subscriptions[agent_id])
        
        for msg_type in message_types:
            type_key = f"subscriptions:{msg_type.value}"
            self.redis.srem(type_key, agent_id)
            self.subscriptions[agent_id].discard(msg_type)
        
        logger.info(f"Agent {agent_id} unsubscribed from {[t.value for t in message_types]}")
    
    def register_handler(self, message_type: MessageType, handler: Callable):
        """Register a message handler"""
        self.handlers[message_type].append(handler)
        logger.debug(f"Registered handler for {message_type.value}")
    
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """
        Process a message and generate response if needed
        
        Args:
            message: The message to process
            
        Returns:
            Response message if applicable
        """
        # Get handlers for message type
        handlers = self.handlers.get(message.message_type, [])
        
        response = None
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(message)
                else:
                    result = handler(message)
                
                # If handler returns a response, use it
                if isinstance(result, AgentMessage):
                    response = result
                    break
            except Exception as e:
                logger.error(f"Handler error for {message.message_id}: {e}")
        
        # Create default response if needed
        if not response and message.message_type == MessageType.REQUEST:
            response = AgentMessage(
                sender_agent="system",
                recipient_agents=[message.sender_agent],
                message_type=MessageType.RESPONSE,
                correlation_id=message.message_id,
                content={
                    'status': 'processed',
                    'original_message_id': message.message_id
                }
            )
        
        return response
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get router statistics"""
        stats = dict(self.stats)
        
        # Add queue sizes
        queue_sizes = {}
        for priority in Priority:
            total_size = 0
            for key in self.redis.scan_iter(match=f"agent:*:{self.priority_queues[priority]}"):
                total_size += self.redis.llen(key)
            queue_sizes[priority.value] = total_size
        
        stats['queue_sizes'] = queue_sizes
        stats['total_subscriptions'] = sum(len(subs) for subs in self.subscriptions.values())
        
        return stats
    
    def clear_expired_messages(self):
        """Clear expired messages from all queues"""
        cleared = 0
        
        for key in self.redis.scan_iter(match="agent:*:queue:*"):
            queue_length = self.redis.llen(key)
            
            for _ in range(queue_length):
                message_data = self.redis.rpop(key)
                if message_data:
                    try:
                        message = AgentMessage.from_dict(json.loads(message_data))
                        if not message.is_expired():
                            # Put back non-expired message
                            self.redis.lpush(key, message_data)
                        else:
                            cleared += 1
                    except:
                        cleared += 1
        
        logger.info(f"Cleared {cleared} expired messages")
        return cleared


class MessageBatcher:
    """
    Batches messages for efficient processing
    """
    
    def __init__(self, batch_size: int = 10, batch_timeout: float = 1.0):
        """
        Initialize the message batcher
        
        Args:
            batch_size: Maximum batch size
            batch_timeout: Maximum time to wait for batch (seconds)
        """
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.batches: Dict[str, List[AgentMessage]] = defaultdict(list)
        self.batch_timers: Dict[str, asyncio.Task] = {}
        logger.info(f"MessageBatcher initialized (size={batch_size}, timeout={batch_timeout}s)")
    
    async def add_message(self, message: AgentMessage, batch_key: str = "default") -> Optional[List[AgentMessage]]:
        """
        Add message to batch
        
        Args:
            message: Message to add
            batch_key: Batch identifier
            
        Returns:
            Full batch if ready, None otherwise
        """
        self.batches[batch_key].append(message)
        
        # Start timer if this is the first message
        if len(self.batches[batch_key]) == 1:
            self.batch_timers[batch_key] = asyncio.create_task(
                self._batch_timeout(batch_key)
            )
        
        # Check if batch is full
        if len(self.batches[batch_key]) >= self.batch_size:
            return await self._flush_batch(batch_key)
        
        return None
    
    async def _batch_timeout(self, batch_key: str):
        """Handle batch timeout"""
        await asyncio.sleep(self.batch_timeout)
        await self._flush_batch(batch_key)
    
    async def _flush_batch(self, batch_key: str) -> List[AgentMessage]:
        """Flush a batch"""
        batch = self.batches[batch_key]
        self.batches[batch_key] = []
        
        # Cancel timer if exists
        if batch_key in self.batch_timers:
            self.batch_timers[batch_key].cancel()
            del self.batch_timers[batch_key]
        
        logger.debug(f"Flushed batch {batch_key} with {len(batch)} messages")
        return batch
    
    async def flush_all(self) -> Dict[str, List[AgentMessage]]:
        """Flush all batches"""
        all_batches = {}
        
        for batch_key in list(self.batches.keys()):
            batch = await self._flush_batch(batch_key)
            if batch:
                all_batches[batch_key] = batch
        
        return all_batches