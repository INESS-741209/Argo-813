"""
Mock Redis for local development without actual Redis server
Provides in-memory storage that mimics Redis behavior
"""

import json
import time
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict, deque
import threading


class MockRedis:
    """Mock Redis client for local development"""
    
    def __init__(self):
        self._storage = defaultdict(dict)
        self._sets = defaultdict(set)
        self._lists = defaultdict(list)
        self._expiry = defaultdict(float)
        self._lock = threading.RLock()
    
    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set key to value with optional expiry"""
        with self._lock:
            if isinstance(value, (dict, list)):
                self._storage[key] = json.dumps(value)
            else:
                self._storage[key] = str(value)
            
            if ex:
                self._expiry[key] = time.time() + ex
            
            return True
    
    def setex(self, key: str, ex: int, value: Any) -> bool:
        """Set key to value with expiry"""
        return self.set(key, value, ex)
    
    def get(self, key: str) -> Optional[str]:
        """Get value for key"""
        with self._lock:
            if key in self._expiry and time.time() > self._expiry[key]:
                self.delete(key)
                return None
            return self._storage.get(key)
    
    def hset(self, key: str, mapping: Dict[str, Any]) -> int:
        """Set hash fields"""
        with self._lock:
            if key not in self._storage:
                self._storage[key] = {}
            
            count = 0
            for field, value in mapping.items():
                if isinstance(value, (dict, list)):
                    self._storage[key][field] = json.dumps(value)
                else:
                    self._storage[key][field] = str(value)
                count += 1
            
            return count
    
    def hget(self, key: str, field: str) -> Optional[str]:
        """Get hash field value"""
        with self._lock:
            if key in self._storage and field in self._storage[key]:
                return self._storage[key][field]
            return None
    
    def hgetall(self, key: str) -> Dict[str, str]:
        """Get all hash fields"""
        with self._lock:
            if key in self._storage:
                return self._storage[key].copy()
            return {}
    
    def sadd(self, key: str, *members: str) -> int:
        """Add members to set"""
        with self._lock:
            if key not in self._sets:
                self._sets[key] = set()
            
            added = 0
            for member in members:
                if member not in self._sets[key]:
                    self._sets[key].add(member)
                    added += 1
            
            return added
    
    def smembers(self, key: str) -> Set[str]:
        """Get set members"""
        with self._lock:
            return self._sets.get(key, set()).copy()
    
    def srem(self, key: str, *members: str) -> int:
        """Remove members from set"""
        with self._lock:
            if key not in self._sets:
                return 0
            
            removed = 0
            for member in members:
                if member in self._sets[key]:
                    self._sets[key].remove(member)
                    removed += 1
            
            return removed
    
    def hincrby(self, key: str, field: str, amount: int = 1) -> int:
        """Hash field 값 증가"""
        with self._lock:
            if key not in self._storage:
                self._storage[key] = {}
            
            if not isinstance(self._storage[key], dict):
                self._storage[key] = {}
            
            if field not in self._storage[key]:
                self._storage[key][field] = 0
            
            if isinstance(self._storage[key][field], (int, str)):
                try:
                    current_value = int(self._storage[key][field])
                    new_value = current_value + amount
                    self._storage[key][field] = new_value
                    return new_value
                except (ValueError, TypeError):
                    self._storage[key][field] = amount
                    return amount
            else:
                self._storage[key][field] = amount
                return amount
    
    def keys(self, pattern: str = "*") -> List[str]:
        """키 패턴 매칭 (간단한 구현)"""
        with self._lock:
            all_keys = list(self._storage.keys()) + list(self._sets.keys())
            
            if pattern == "*":
                return all_keys
            
            # 간단한 패턴 매칭 (정확한 매칭만)
            matched_keys = []
            for key in all_keys:
                if pattern == key:
                    matched_keys.append(key)
            
            return matched_keys
    
    def delete(self, *keys: str) -> int:
        """Delete keys"""
        with self._lock:
            deleted = 0
            for key in keys:
                if key in self._storage:
                    del self._storage[key]
                    deleted += 1
                if key in self._sets:
                    del self._sets[key]
                    deleted += 1
                if key in self._expiry:
                    del self._expiry[key]
                    deleted += 1
            return deleted
    
    def exists(self, *keys: str) -> int:
        """Check if keys exist"""
        with self._lock:
            count = 0
            for key in keys:
                if key in self._storage or key in self._sets:
                    count += 1
            return count
    
    def expire(self, key: str, seconds: int) -> bool:
        """Set key expiry"""
        with self._lock:
            if key in self._storage or key in self._sets:
                self._expiry[key] = time.time() + seconds
                return True
            return False
    
    def ttl(self, key: str) -> int:
        """Get key TTL"""
        with self._lock:
            if key in self._expiry:
                remaining = self._expiry[key] - time.time()
                return max(0, int(remaining))
            return -1
    
    def flushdb(self) -> bool:
        """Clear all data"""
        with self._lock:
            self._storage.clear()
            self._sets.clear()
            self._expiry.clear()
            return True
    
    def ping(self) -> bool:
        """Always return True for mock"""
        return True
    
    def close(self):
        """Close mock connection"""
        pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Global mock Redis instance
mock_redis = MockRedis()


def get_mock_redis():
    """Get mock Redis instance"""
    return mock_redis
