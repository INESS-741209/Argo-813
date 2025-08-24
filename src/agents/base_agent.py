"""
Base Agent Framework for ARGO Phase 2
Abstract base class for all specialized agents
"""

import asyncio
import logging
import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Callable
from dataclasses import dataclass
import redis

# Import our custom modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.context.shared_context_fabric import SharedContextFabric
from shared.messaging.agent_protocol import (
    AgentMessage, MessageType, Priority, MessageRouter
)
from infrastructure.locks.distributed_lock import DistributedLockManager

logger = logging.getLogger(__name__)


@dataclass
class AgentCapability:
    """Defines a capability of an agent"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    
    def matches(self, required: str) -> bool:
        """Check if this capability matches a requirement"""
        return required.lower() in self.name.lower() or required.lower() in self.description.lower()


@dataclass
class AgentState:
    """Current state of an agent"""
    status: str  # idle, busy, error, shutdown
    current_task: Optional[Dict[str, Any]] = None
    task_queue: List[Dict[str, Any]] = None
    completed_tasks: int = 0
    failed_tasks: int = 0
    last_heartbeat: datetime = None
    
    def __post_init__(self):
        if self.task_queue is None:
            self.task_queue = []
        if self.last_heartbeat is None:
            self.last_heartbeat = datetime.now()


class BaseAgent(ABC):
    """
    Abstract base class for all ARGO agents
    Provides core functionality for communication, context, and task management
    """
    
    def __init__(self, 
                 agent_id: str,
                 agent_type: str,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize the base agent
        
        Args:
            agent_id: Unique identifier for this agent
            agent_type: Type of agent (orchestrator, technical, creative, etc.)
            config: Configuration dictionary
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.config = config or {}
        
        # Initialize state
        self.state = AgentState(status="initializing")
        
        # Initialize capabilities
        self.capabilities: List[AgentCapability] = []
        self._register_capabilities()
        
        # Initialize Redis connection
        self.redis = self._init_redis()
        
        # Initialize components
        self.context_fabric = SharedContextFabric(self.redis, config.get('context', {}))
        self.message_router = MessageRouter(self.redis)
        self.lock_manager = DistributedLockManager(self.redis, config.get('locks', {}))
        
        # Task processing
        self.task_handlers: Dict[str, Callable] = {}
        self._register_task_handlers()
        
        # Lifecycle management
        self.running = False
        self.tasks: List[asyncio.Task] = []
        
        # Statistics
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'total_processing_time': 0
        }
        
        logger.info(f"Agent {agent_id} ({agent_type}) initialized")
    
    def _init_redis(self) -> redis.Redis:
        """Initialize Redis connection"""
        return redis.Redis(
            host=os.getenv('REDIS_HOST', self.config.get('redis', {}).get('host', 'localhost')),
            port=int(os.getenv('REDIS_PORT', self.config.get('redis', {}).get('port', 6379))),
            password=os.getenv('REDIS_PASSWORD', self.config.get('redis', {}).get('password', None)),
            decode_responses=True
        )
    
    @abstractmethod
    def _register_capabilities(self):
        """Register agent capabilities - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def _register_task_handlers(self):
        """Register task handlers - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a task - must be implemented by subclasses
        
        Args:
            task: Task to process
            
        Returns:
            Task result
        """
        pass
    
    async def start(self):
        """Start the agent"""
        logger.info(f"Starting agent {self.agent_id}")
        
        self.running = True
        self.state.status = "idle"
        
        # Register with the system
        await self._register_agent()
        
        # Subscribe to relevant message types
        await self._subscribe_to_messages()
        
        # Start background tasks
        self.tasks.append(asyncio.create_task(self._heartbeat_loop()))
        self.tasks.append(asyncio.create_task(self._message_processing_loop()))
        self.tasks.append(asyncio.create_task(self._task_processing_loop()))
        
        logger.info(f"Agent {self.agent_id} started successfully")
    
    async def stop(self):
        """Stop the agent"""
        logger.info(f"Stopping agent {self.agent_id}")
        
        self.running = False
        self.state.status = "shutdown"
        
        # Cancel all background tasks
        for task in self.tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Release all locks
        self.lock_manager.release_all(self.agent_id)
        
        # Unregister from the system
        await self._unregister_agent()
        
        logger.info(f"Agent {self.agent_id} stopped")
    
    async def _register_agent(self):
        """Register agent with the system"""
        registration_data = {
            'agent_id': self.agent_id,
            'agent_type': self.agent_type,
            'capabilities': [
                {
                    'name': cap.name,
                    'description': cap.description
                }
                for cap in self.capabilities
            ],
            'status': self.state.status,
            'registered_at': datetime.now().isoformat()
        }
        
        # Store in Redis
        agent_key = f"agent:{self.agent_id}"
        self.redis.hset(agent_key, mapping={
            k: json.dumps(v) if isinstance(v, (list, dict)) else v
            for k, v in registration_data.items()
        })
        self.redis.expire(agent_key, 3600)  # 1 hour TTL
        
        # Add to agent index
        self.redis.sadd(f"agents:{self.agent_type}", self.agent_id)
        
        logger.debug(f"Agent {self.agent_id} registered")
    
    async def _unregister_agent(self):
        """Unregister agent from the system"""
        # Remove from Redis
        agent_key = f"agent:{self.agent_id}"
        self.redis.delete(agent_key)
        
        # Remove from agent index
        self.redis.srem(f"agents:{self.agent_type}", self.agent_id)
        
        logger.debug(f"Agent {self.agent_id} unregistered")
    
    async def _subscribe_to_messages(self):
        """Subscribe to relevant message types"""
        # Default subscriptions for all agents
        default_types = [
            MessageType.REQUEST,
            MessageType.BROADCAST,
            MessageType.CONSENSUS,
            MessageType.ESCALATION
        ]
        
        self.message_router.subscribe(self.agent_id, default_types)
        
        # Subscribe to agent-specific message types
        if self.agent_type == "orchestrator":
            self.message_router.subscribe(self.agent_id, [
                MessageType.PROPOSAL,
                MessageType.STATUS
            ])
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats"""
        while self.running:
            try:
                # Update heartbeat timestamp
                self.state.last_heartbeat = datetime.now()
                
                # Send heartbeat message
                heartbeat = AgentMessage(
                    sender_agent=self.agent_id,
                    recipient_agents=["orchestrator"],
                    message_type=MessageType.HEARTBEAT,
                    priority=Priority.LOW,
                    content={
                        'agent_id': self.agent_id,
                        'status': self.state.status,
                        'stats': self.stats,
                        'timestamp': self.state.last_heartbeat.isoformat()
                    }
                )
                
                await self.message_router.send_message(heartbeat)
                
                # Update registration TTL
                agent_key = f"agent:{self.agent_id}"
                self.redis.expire(agent_key, 3600)
                
                await asyncio.sleep(30)  # Heartbeat every 30 seconds
                
            except Exception as e:
                logger.error(f"Heartbeat error for {self.agent_id}: {e}")
                await asyncio.sleep(5)
    
    async def _message_processing_loop(self):
        """Process incoming messages"""
        while self.running:
            try:
                # Receive messages
                messages = await self.message_router.receive_messages(self.agent_id, max_messages=10)
                
                for message in messages:
                    self.stats['messages_received'] += 1
                    
                    # Process based on message type
                    if message.message_type == MessageType.REQUEST:
                        await self._handle_request(message)
                    elif message.message_type == MessageType.BROADCAST:
                        await self._handle_broadcast(message)
                    elif message.message_type == MessageType.CONSENSUS:
                        await self._handle_consensus(message)
                    else:
                        logger.debug(f"Unhandled message type: {message.message_type.value}")
                
                await asyncio.sleep(0.1)  # Brief pause between checks
                
            except Exception as e:
                logger.error(f"Message processing error for {self.agent_id}: {e}")
                await asyncio.sleep(1)
    
    async def _task_processing_loop(self):
        """Process tasks from the queue"""
        while self.running:
            try:
                if self.state.task_queue and self.state.status == "idle":
                    # Get next task
                    task = self.state.task_queue.pop(0)
                    
                    # Update state
                    self.state.status = "busy"
                    self.state.current_task = task
                    
                    # Process task
                    start_time = datetime.now()
                    
                    try:
                        result = await self.process_task(task)
                        
                        # Record success
                        self.state.completed_tasks += 1
                        self.stats['tasks_completed'] += 1
                        
                        # Send result
                        await self._send_task_result(task, result, success=True)
                        
                    except Exception as e:
                        logger.error(f"Task processing error: {e}")
                        
                        # Record failure
                        self.state.failed_tasks += 1
                        self.stats['tasks_failed'] += 1
                        
                        # Send error
                        await self._send_task_result(task, {'error': str(e)}, success=False)
                    
                    finally:
                        # Update stats
                        processing_time = (datetime.now() - start_time).total_seconds()
                        self.stats['total_processing_time'] += processing_time
                        
                        # Update state
                        self.state.status = "idle"
                        self.state.current_task = None
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Task processing loop error for {self.agent_id}: {e}")
                await asyncio.sleep(1)
    
    async def _handle_request(self, message: AgentMessage):
        """Handle request message"""
        content = message.content
        
        # Check if we can handle this request
        if self._can_handle_request(content):
            # Add to task queue
            task = {
                'task_id': message.message_id,
                'type': content.get('action', 'unknown'),
                'parameters': content.get('parameters', {}),
                'requester': message.sender_agent,
                'priority': message.priority
            }
            
            self.state.task_queue.append(task)
            
            # Send acknowledgment
            ack = AgentMessage(
                sender_agent=self.agent_id,
                recipient_agents=[message.sender_agent],
                message_type=MessageType.RESPONSE,
                correlation_id=message.message_id,
                content={
                    'status': 'accepted',
                    'queue_position': len(self.state.task_queue)
                }
            )
            
            await self.message_router.send_message(ack)
    
    async def _handle_broadcast(self, message: AgentMessage):
        """Handle broadcast message"""
        # Log broadcast
        logger.info(f"Received broadcast from {message.sender_agent}: {message.content}")
        
        # Store in context if relevant
        if message.content.get('type') == 'context_update':
            session_id = message.content.get('session_id', 'global')
            self.context_fabric.store_event(session_id, message.content)
    
    async def _handle_consensus(self, message: AgentMessage):
        """Handle consensus request"""
        # This would be implemented based on specific consensus mechanism
        logger.debug(f"Consensus request from {message.sender_agent}")
    
    def _can_handle_request(self, content: Dict[str, Any]) -> bool:
        """Check if agent can handle a request"""
        required_capabilities = content.get('required_capabilities', [])
        
        for required in required_capabilities:
            for capability in self.capabilities:
                if capability.matches(required):
                    return True
        
        return False
    
    async def _send_task_result(self, task: Dict[str, Any], result: Dict[str, Any], success: bool):
        """Send task result"""
        response = AgentMessage(
            sender_agent=self.agent_id,
            recipient_agents=[task.get('requester', 'orchestrator')],
            message_type=MessageType.RESPONSE,
            correlation_id=task.get('task_id'),
            content={
                'task_id': task.get('task_id'),
                'success': success,
                'result': result,
                'agent_id': self.agent_id,
                'timestamp': datetime.now().isoformat()
            }
        )
        
        await self.message_router.send_message(response)
        self.stats['messages_sent'] += 1
    
    async def send_message(self, message: AgentMessage):
        """Send a message"""
        message.sender_agent = self.agent_id
        await self.message_router.send_message(message)
        self.stats['messages_sent'] += 1
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get agent statistics"""
        return {
            'agent_id': self.agent_id,
            'agent_type': self.agent_type,
            'state': {
                'status': self.state.status,
                'completed_tasks': self.state.completed_tasks,
                'failed_tasks': self.state.failed_tasks,
                'queue_size': len(self.state.task_queue)
            },
            'stats': self.stats,
            'capabilities': [cap.name for cap in self.capabilities]
        }
    
    def get_context(self, session_id: str) -> Dict[str, Any]:
        """Get current context"""
        return self.context_fabric.get_full_context(session_id)
    
    async def acquire_lock(self, resource_id: str, ttl: int = 30) -> bool:
        """Acquire a lock on a resource"""
        return self.lock_manager.acquire(resource_id, self.agent_id, ttl)
    
    async def release_lock(self, resource_id: str) -> bool:
        """Release a lock on a resource"""
        return self.lock_manager.release(resource_id, self.agent_id)
    
    def get_capabilities(self) -> List[AgentCapability]:
        """Get list of agent capabilities"""
        return self.capabilities.copy()
    
    def has_capability(self, capability_name: str) -> bool:
        """Check if agent has specific capability"""
        return any(cap.name == capability_name for cap in self.capabilities)