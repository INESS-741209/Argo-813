#!/usr/bin/env python3
"""
Mock Neo4j for Local Development
실제 Neo4j 연결 없이 로컬 테스트를 위한 Mock 구현
"""

import logging
import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class MockNode:
    id: str
    labels: List[str]
    properties: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class MockRelationship:
    id: str
    type: str
    start_node_id: str
    end_node_id: str
    properties: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)

class MockNeo4jSession:
    """Mock Neo4j 세션"""
    
    def __init__(self, driver):
        self.driver = driver
        self.closed = False
    
    def run(self, query: str, parameters: Dict = None, **kwargs):
        """Cypher 쿼리 실행 (Mock)"""
        logger.info(f"🔍 Mock Neo4j 쿼리 실행: {query}")
        logger.info(f"   파라미터: {parameters}")
        logger.info(f"   추가 인자: {kwargs}")
        
        # 간단한 쿼리 패턴 매칭
        if "RETURN 1" in query:
            return MockResult([{"1": 1}])
        elif "CREATE" in query:
            # 노드 생성 시뮬레이션
            node_id = str(uuid.uuid4())
            self.driver.nodes[node_id] = MockNode(
                id=node_id,
                labels=["MockNode"],
                properties=parameters or {}
            )
            return MockResult([{"id": node_id}])
        elif "MATCH" in query:
            # 노드 조회 시뮬레이션
            results = []
            for node in self.driver.nodes.values():
                if "RETURN" in query:
                    results.append({"node": node})
            return MockResult(results)
        elif "MERGE" in query:
            # 노드 병합 시뮬레이션
            node_id = str(uuid.uuid4())
            self.driver.nodes[node_id] = MockNode(
                id=node_id,
                labels=["MockNode"],
                properties=parameters or {}
            )
            return MockResult([{"u": {"id": node_id}}])
        else:
            return MockResult([])
    
    def close(self):
        """세션 종료"""
        self.closed = True
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class MockResult:
    """Mock 쿼리 결과"""
    
    def __init__(self, data: List[Dict]):
        self.data = data
        self.index = 0
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self.index < len(self.data):
            result = self.data[self.index]
            self.index += 1
            return MockRecord(result)
        raise StopIteration
    
    def single(self):
        """단일 결과 반환"""
        if self.data:
            return MockRecord(self.data[0])
        return None
    
    def data(self):
        """모든 데이터 반환"""
        return self.data

class MockRecord:
    """Mock 레코드"""
    
    def __init__(self, data: Dict):
        self.data = data
    
    def __getitem__(self, key):
        return self.data.get(key)
    
    def get(self, key, default=None):
        return self.data.get(key, default)
    
    def __contains__(self, key):
        return key in self.data

class MockNeo4jDriver:
    """Mock Neo4j 드라이버"""
    
    def __init__(self):
        self.nodes: Dict[str, MockNode] = {}
        self.relationships: Dict[str, MockRelationship] = {}
        self.closed = False
        logger.info("🔧 MockNeo4j 드라이버 초기화됨")
    
    def session(self, **kwargs):
        """새 세션 생성"""
        return MockNeo4jSession(self)
    
    def close(self):
        """드라이버 종료"""
        self.closed = True
        logger.info("🔧 MockNeo4j 드라이버 종료됨")
    
    def verify_connectivity(self):
        """연결성 확인 (Mock에서는 항상 성공)"""
        return True

def create_mock_neo4j_driver():
    """Mock Neo4j 드라이버 생성"""
    return MockNeo4jDriver()
