"""
Distributed Lock Manager for ARGO Phase 2
Handles resource locking for parallel agent execution
"""

import redis
import uuid
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from threading import Thread
import json

logger = logging.getLogger(__name__)


@dataclass
class LockInfo:
    """Information about an acquired lock"""
    resource_id: str
    agent_id: str
    lock_id: str
    acquired_at: datetime
    ttl_seconds: int
    
    def is_expired(self) -> bool:
        """Check if lock has expired"""
        expiry_time = self.acquired_at + timedelta(seconds=self.ttl_seconds)
        return datetime.now() > expiry_time


class DistributedLockManager:
    """
    Manages distributed locks for resource access control
    Uses Redis for atomic operations and prevents race conditions
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None, config: Dict[str, Any] = None):
        """
        Initialize the lock manager
        
        Args:
            redis_client: Redis client instance (optional)
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_ttl = self.config.get('default_ttl_seconds', 30)
        self.max_wait_time = self.config.get('max_wait_time_seconds', 60)
        self.deadlock_interval = self.config.get('deadlock_detection_interval', 5)
        
        # Initialize Redis client if not provided
        if redis_client:
            self.redis = redis_client
        else:
            # Create Redis client from environment variables
            import os
            self.redis = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                password=os.getenv('REDIS_PASSWORD', None),
                decode_responses=True
            )
        
        # Local registry of locks held by this instance
        self.locks: Dict[str, LockInfo] = {}
        
        # Start deadlock detection thread
        self.deadlock_detector_running = True
        self.deadlock_thread = Thread(target=self._deadlock_detector, daemon=True)
        self.deadlock_thread.start()
        
        logger.info("DistributedLockManager initialized")
    
    def acquire(self, 
                resource_id: str, 
                agent_id: str, 
                ttl: Optional[int] = None,
                wait: bool = True) -> bool:
        """
        Acquire a lock on a resource
        
        Args:
            resource_id: The resource to lock
            agent_id: The agent requesting the lock
            ttl: Time-to-live in seconds (optional)
            wait: Whether to wait for lock if not immediately available
            
        Returns:
            True if lock acquired, False otherwise
        """
        ttl = ttl or self.default_ttl
        lock_key = f"lock:{resource_id}"
        lock_id = f"{agent_id}:{uuid.uuid4()}"
        
        start_time = time.time()
        
        while True:
            # Try to acquire lock atomically using SET NX EX
            acquired = self.redis.set(
                lock_key,
                lock_id,
                nx=True,  # Only set if not exists
                ex=ttl    # Expiration time
            )
            
            if acquired:
                # Record lock in local registry
                lock_info = LockInfo(
                    resource_id=resource_id,
                    agent_id=agent_id,
                    lock_id=lock_id,
                    acquired_at=datetime.now(),
                    ttl_seconds=ttl
                )
                self.locks[resource_id] = lock_info
                
                # Record lock metadata
                meta_key = f"lock:meta:{resource_id}"
                self.redis.hset(meta_key, mapping={
                    'agent_id': agent_id,
                    'acquired_at': lock_info.acquired_at.isoformat(),
                    'ttl': ttl
                })
                self.redis.expire(meta_key, ttl)
                
                logger.debug(f"Lock acquired: {resource_id} by {agent_id}")
                return True
            
            # Check if we should wait
            if not wait:
                return False
            
            # Check timeout
            if time.time() - start_time > self.max_wait_time:
                logger.warning(f"Lock acquisition timeout: {resource_id} for {agent_id}")
                return False
            
            # Wait before retrying
            time.sleep(0.1)
    
    def release(self, resource_id: str, agent_id: str) -> bool:
        """
        Release a lock on a resource
        
        Args:
            resource_id: The resource to unlock
            agent_id: The agent releasing the lock
            
        Returns:
            True if lock released, False if not held by this agent
        """
        if resource_id not in self.locks:
            logger.warning(f"Attempted to release unheld lock: {resource_id}")
            return False
        
        lock_info = self.locks[resource_id]
        if lock_info.agent_id != agent_id:
            logger.warning(f"Agent {agent_id} cannot release lock held by {lock_info.agent_id}")
            return False
        
        lock_key = f"lock:{resource_id}"
        
        # Lua script for atomic check-and-delete
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            redis.call("del", KEYS[1])
            redis.call("del", KEYS[2])
            return 1
        else
            return 0
        end
        """
        
        meta_key = f"lock:meta:{resource_id}"
        result = self.redis.eval(
            lua_script,
            2,
            lock_key,
            meta_key,
            lock_info.lock_id
        )
        
        if result:
            del self.locks[resource_id]
            logger.debug(f"Lock released: {resource_id} by {agent_id}")
            return True
        
        logger.error(f"Failed to release lock: {resource_id}")
        return False
    
    def extend(self, resource_id: str, agent_id: str, additional_ttl: int) -> bool:
        """
        Extend the TTL of an existing lock
        
        Args:
            resource_id: The locked resource
            agent_id: The agent holding the lock
            additional_ttl: Additional seconds to extend
            
        Returns:
            True if extended, False otherwise
        """
        if resource_id not in self.locks:
            return False
        
        lock_info = self.locks[resource_id]
        if lock_info.agent_id != agent_id:
            return False
        
        lock_key = f"lock:{resource_id}"
        
        # Extend the expiration
        self.redis.expire(lock_key, additional_ttl)
        
        # Update metadata
        meta_key = f"lock:meta:{resource_id}"
        self.redis.expire(meta_key, additional_ttl)
        
        # Update local registry
        lock_info.ttl_seconds += additional_ttl
        
        logger.debug(f"Lock extended: {resource_id} by {additional_ttl}s")
        return True
    
    def is_locked(self, resource_id: str) -> bool:
        """Check if a resource is locked"""
        lock_key = f"lock:{resource_id}"
        return self.redis.exists(lock_key) > 0
    
    def get_lock_info(self, resource_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a lock"""
        meta_key = f"lock:meta:{resource_id}"
        info = self.redis.hgetall(meta_key)
        return info if info else None
    
    def release_all(self, agent_id: str) -> int:
        """
        Release all locks held by an agent
        
        Args:
            agent_id: The agent whose locks to release
            
        Returns:
            Number of locks released
        """
        released = 0
        resources_to_release = [
            resource_id for resource_id, lock_info in self.locks.items()
            if lock_info.agent_id == agent_id
        ]
        
        for resource_id in resources_to_release:
            if self.release(resource_id, agent_id):
                released += 1
        
        return released
    
    def _deadlock_detector(self):
        """Background thread to detect and resolve deadlocks"""
        while self.deadlock_detector_running:
            try:
                # Check for expired locks in local registry
                expired_locks = [
                    resource_id for resource_id, lock_info in self.locks.items()
                    if lock_info.is_expired()
                ]
                
                for resource_id in expired_locks:
                    logger.warning(f"Expired lock detected: {resource_id}")
                    # Clean up expired lock from local registry
                    del self.locks[resource_id]
                
                # Check for circular dependencies (simplified)
                self._check_circular_dependencies()
                
            except Exception as e:
                logger.error(f"Deadlock detector error: {e}")
            
            time.sleep(self.deadlock_interval)
    
    def _check_circular_dependencies(self):
        """Check for circular lock dependencies"""
        # This is a simplified implementation
        # In production, would need more sophisticated graph analysis
        
        # Get all active locks from Redis
        lock_pattern = "lock:meta:*"
        all_locks = {}
        
        for key in self.redis.scan_iter(match=lock_pattern):
            resource_id = key.replace("lock:meta:", "")
            lock_info = self.redis.hgetall(key)
            if lock_info:
                all_locks[resource_id] = lock_info
        
        # Log if too many locks are held (potential deadlock indicator)
        if len(all_locks) > 10:
            logger.warning(f"High number of active locks: {len(all_locks)}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get lock manager statistics"""
        return {
            'active_locks': len(self.locks),
            'lock_details': [
                {
                    'resource': resource_id,
                    'agent': lock_info.agent_id,
                    'acquired_at': lock_info.acquired_at.isoformat(),
                    'ttl': lock_info.ttl_seconds
                }
                for resource_id, lock_info in self.locks.items()
            ]
        }
    
    def shutdown(self):
        """Gracefully shutdown the lock manager"""
        logger.info("Shutting down DistributedLockManager")
        self.deadlock_detector_running = False
        
        # Release all locks held by this instance
        for resource_id in list(self.locks.keys()):
            lock_info = self.locks[resource_id]
            self.release(resource_id, lock_info.agent_id)
        
        logger.info("DistributedLockManager shutdown complete")