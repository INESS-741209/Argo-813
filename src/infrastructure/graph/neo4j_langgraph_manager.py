#!/usr/bin/env python3
"""
Neo4j LangGraph Integration Manager for ARGO System
실제 데이터로 인한 시스템 파괴를 방지하기 위한 견고한 그래프 데이터베이스 관리
"""

import asyncio
import logging
import json
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, TransientError, ConstraintError
# from langgraph.graph import StateGraph, END  # MockNeo4j 사용으로 제거
# from langgraph.prebuilt import ToolExecutor  # 최신 버전에서는 사용 불가
# from langgraph.checkpoint.memory import MemorySaver  # MockNeo4j 사용으로 제거
import redis

logger = logging.getLogger(__name__)

class GraphOperationType(Enum):
    CREATE_NODE = "create_node"
    UPDATE_NODE = "update_node"
    DELETE_NODE = "delete_node"
    CREATE_RELATIONSHIP = "create_relationship"
    UPDATE_RELATIONSHIP = "update_relationship"
    DELETE_RELATIONSHIP = "delete_relationship"
    MERGE_NODE = "merge_node"
    MERGE_RELATIONSHIP = "merge_relationship"
    BATCH_OPERATION = "batch_operation"

@dataclass
class GraphOperation:
    id: str
    operation_type: GraphOperationType
    target_type: str  # 'node' or 'relationship'
    target_id: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    relationship_type: Optional[str] = None
    start_node_id: Optional[str] = None
    end_node_id: Optional[str] = None
    constraints: List[str] = field(default_factory=list)
    validation_rules: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    priority: int = 1  # 1: 높음, 2: 보통, 3: 낮음

class Neo4jLangGraphManager:
    """
    Neo4j와 LangGraph를 통합한 고급 그래프 데이터베이스 관리자
    실제 데이터로 인한 시스템 파괴를 방지하기 위한 견고한 메커니즘
    """
    
    def __init__(self, neo4j_config: Dict, redis_config: Dict = None):
        self.neo4j_config = neo4j_config
        self.redis_config = redis_config or {
            'host': 'localhost',
            'port': 6379,
            'db': 0
        }
        
        # Neo4j 연결
        self.driver = self._get_neo4j_driver()
        
        # Redis 연결 (MockRedis 자동 전환 포함)
        self.redis_client = self._get_redis_client()
        
        # LangGraph 상태 그래프 (MockNeo4j 사용으로 제거)
        # self.state_graph = self._create_state_graph()
        
        # 작업 큐
        self.operation_queue: List[GraphOperation] = []
        self.failed_operations: List[GraphOperation] = []
        
        # 스키마 및 제약 조건
        self.node_constraints: Dict[str, List[str]] = {}
        self.relationship_constraints: Dict[str, List[str]] = {}
        self.indexes: Dict[str, List[str]] = {}
        
        # 성능 모니터링
        self.query_stats: Dict[str, Dict] = {}
        self.performance_metrics: Dict[str, float] = {}
        
        # 초기화
        self._initialize_schema()
        
        logger.info("Neo4jLangGraphManager initialized")
    
    def _get_neo4j_driver(self):
        """Neo4j 드라이버 생성 (실패 시 MockNeo4j로 자동 전환)"""
        try:
            driver = GraphDatabase.driver(
                self.neo4j_config.get('uri', 'bolt://localhost:7687'),
                auth=(
                    self.neo4j_config.get('username', 'neo4j'),
                    self.neo4j_config.get('password', 'password')
                )
            )
            # 연결 테스트
            with driver.session() as session:
                session.run("RETURN 1")
            logger.info("✅ Neo4j 연결 성공")
            return driver
        except Exception as e:
            logger.warning(f"⚠️ Neo4j 연결 실패, MockNeo4j로 전환: {e}")
            from src.infrastructure.mocks.mock_neo4j import create_mock_neo4j_driver
            return create_mock_neo4j_driver()
    
    def _get_redis_client(self) -> redis.Redis:
        """Redis 클라이언트 생성 (실패 시 MockRedis로 자동 전환)"""
        try:
            client = redis.Redis(
                host=self.redis_config.get('host', 'localhost'),
                port=self.redis_config.get('port', 6379),
                db=self.redis_config.get('db', 0),
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # 연결 테스트
            client.ping()
            logger.info("✅ Redis 연결 성공")
            return client
        except Exception as e:
            logger.warning(f"⚠️ Redis 연결 실패, MockRedis로 전환: {e}")
            from src.infrastructure.mocks.mock_redis import MockRedis
            return MockRedis()
    
    def _create_state_graph(self):
        """LangGraph 상태 그래프 생성 (MockNeo4j 사용으로 제거)"""
        logger.info("🔧 MockNeo4j 사용으로 LangGraph 상태 그래프 생성 생략")
        return None
    
    async def _execute_create_operation(self, operation: GraphOperation) -> Dict[str, Any]:
        """노드 생성 작업 실행"""
        try:
            with self.driver.session() as session:
                # 노드 생성 쿼리
                query = f"""
                CREATE (n:{':'.join(operation.labels)} {{
                    id: $id,
                    {', '.join([f'{k}: ${k}' for k in operation.properties.keys()])}
                }})
                RETURN n
                """
                
                result = session.run(query, operation.properties)
                node = result.single()
                
                if node:
                    logger.info(f"✅ 노드 생성 성공: {operation.id}")
                    return {
                        "success": True,
                        "data": {"node_id": operation.id},
                        "operation_id": operation.id
                    }
                else:
                    return {
                        "success": False,
                        "errors": ["노드 생성 실패"],
                        "operation_id": operation.id
                    }
                    
        except Exception as e:
            logger.error(f"❌ 노드 생성 실패: {e}")
            return {
                "success": False,
                "errors": [str(e)],
                "operation_id": operation.id
            }
    
    async def _execute_update_operation(self, operation: GraphOperation) -> Dict[str, Any]:
        """노드 업데이트 작업 실행"""
        try:
            with self.driver.session() as session:
                # 노드 업데이트 쿼리
                query = f"""
                MATCH (n:{':'.join(operation.labels)} {{id: $id}})
                SET n += $properties
                RETURN n
                """
                
                result = session.run(query, {
                    "id": operation.target_id,
                    "properties": operation.properties
                })
                node = result.single()
                
                if node:
                    logger.info(f"✅ 노드 업데이트 성공: {operation.id}")
                    return {
                        "success": True,
                        "data": {"node_id": operation.target_id},
                        "operation_id": operation.id
                    }
                else:
                    return {
                        "success": False,
                        "errors": ["노드를 찾을 수 없음"],
                        "operation_id": operation.id
                    }
                    
        except Exception as e:
            logger.error(f"❌ 노드 업데이트 실패: {e}")
            return {
                "success": False,
                "errors": [str(e)],
                "operation_id": operation.id
            }
    
    async def _execute_delete_operation(self, operation: GraphOperation) -> Dict[str, Any]:
        """노드 삭제 작업 실행"""
        try:
            with self.driver.session() as session:
                # 노드 삭제 쿼리
                query = f"""
                MATCH (n:{':'.join(operation.labels)} {{id: $id}})
                DETACH DELETE n
                RETURN count(n) as deleted
                """
                
                result = session.run(query, {"id": operation.target_id})
                deleted = result.single()
                
                if deleted and deleted["deleted"] > 0:
                    logger.info(f"✅ 노드 삭제 성공: {operation.id}")
                    return {
                        "success": True,
                        "data": {"deleted": True},
                        "operation_id": operation.id
                    }
                else:
                    return {
                        "success": False,
                        "errors": ["노드를 찾을 수 없음"],
                        "operation_id": operation.id
                    }
                    
        except Exception as e:
            logger.error(f"❌ 노드 삭제 실패: {e}")
            return {
                "success": False,
                "errors": [str(e)],
                "operation_id": operation.id
            }
    
    async def _execute_create_relationship_operation(self, operation: GraphOperation) -> Dict[str, Any]:
        """관계 생성 작업 실행"""
        try:
            with self.driver.session() as session:
                # 관계 생성 쿼리
                query = f"""
                MATCH (a), (b)
                WHERE a.id = $start_id AND b.id = $end_id
                CREATE (a)-[r:{operation.relationship_type} {{
                    {', '.join([f'{k}: ${k}' for k in operation.properties.keys()])}
                }}]->(b)
                RETURN r
                """
                
                result = session.run(query, {
                    "start_id": operation.start_node_id,
                    "end_id": operation.end_node_id,
                    **operation.properties
                })
                relationship = result.single()
                
                if relationship:
                    logger.info(f"✅ 관계 생성 성공: {operation.id}")
                    return {
                        "success": True,
                        "data": {"relationship_id": operation.id},
                        "operation_id": operation.id
                    }
                else:
                    return {
                        "success": False,
                        "errors": ["노드를 찾을 수 없음"],
                        "operation_id": operation.id
                    }
                    
        except Exception as e:
            logger.error(f"❌ 관계 생성 실패: {e}")
            return {
                "success": False,
                "errors": [str(e)],
                "operation_id": operation.id
            }
    
    async def _execute_merge_node_operation(self, operation: GraphOperation) -> Dict[str, Any]:
        """노드 병합 작업 실행"""
        try:
            with self.driver.session() as session:
                # 노드 병합 쿼리
                query = f"""
                MERGE (n:{':'.join(operation.labels)} {{id: $id}})
                SET n += $properties
                RETURN n
                """
                
                result = session.run(query, {
                    "id": operation.target_id,
                    "properties": operation.properties
                })
                node = result.single()
                
                if node:
                    logger.info(f"✅ 노드 병합 성공: {operation.id}")
                    return {
                        "success": True,
                        "data": {"node_id": operation.target_id},
                        "operation_id": operation.id
                    }
                else:
                    return {
                        "success": False,
                        "errors": ["노드 병합 실패"],
                        "operation_id": operation.id
                    }
                    
        except Exception as e:
            logger.error(f"❌ 노드 병합 실패: {e}")
            return {
                "success": False,
                "errors": [str(e)],
                "operation_id": operation.id
            }
    
    def _initialize_schema(self):
        """Neo4j 스키마 초기화"""
        try:
            with self.driver.session() as session:
                # 노드 제약 조건 생성
                self._create_node_constraints(session)
                
                # 관계 제약 조건 생성
                self._create_relationship_constraints(session)
                
                # 인덱스 생성
                self._create_indexes(session)
                
                # 기본 데이터 구조 생성
                self._create_base_structure(session)
                
            logger.info("✅ Neo4j 스키마 초기화 완료")
            
        except Exception as e:
            logger.error(f"❌ 스키마 초기화 실패: {e}")
            raise
    
    def _create_node_constraints(self, session):
        """노드 제약 조건 생성"""
        constraints = [
            # User 노드 제약 조건
            "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
            "CREATE CONSTRAINT user_email_unique IF NOT EXISTS FOR (u:User) REQUIRE u.email IS UNIQUE",
            
            # Document 노드 제약 조건
            "CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT document_path_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.path IS UNIQUE",
            
            # Tag 노드 제약 조건
            "CREATE CONSTRAINT tag_name_unique IF NOT EXISTS FOR (t:Tag) REQUIRE t.name IS UNIQUE",
            
            # Concept 노드 제약 조건
            "CREATE CONSTRAINT concept_id_unique IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE",
            
            # Project 노드 제약 조건
            "CREATE CONSTRAINT project_id_unique IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE"
        ]
        
        for constraint in constraints:
            try:
                session.run(constraint)
                logger.debug(f"제약 조건 생성: {constraint}")
            except Exception as e:
                logger.warning(f"제약 조건 생성 실패: {constraint} - {e}")
    
    def _create_relationship_constraints(self, session):
        """관계 제약 조건 생성"""
        constraints = [
            # 관계 타입 제약 조건
            "CREATE CONSTRAINT relationship_type_exists IF NOT EXISTS FOR ()-[r]-() REQUIRE r.type IS NOT NULL",
            
            # 관계 속성 제약 조건
            "CREATE CONSTRAINT relationship_timestamp_exists IF NOT EXISTS FOR ()-[r]-() REQUIRE r.timestamp IS NOT NULL"
        ]
        
        for constraint in constraints:
            try:
                session.run(constraint)
                logger.debug(f"관계 제약 조건 생성: {constraint}")
            except Exception as e:
                logger.warning(f"관계 제약 조건 생성 실패: {constraint} - {e}")
    
    def _create_indexes(self, session):
        """인덱스 생성"""
        indexes = [
            # User 인덱스
            "CREATE INDEX user_name_index IF NOT EXISTS FOR (u:User) ON (u.name)",
            "CREATE INDEX user_created_at_index IF NOT EXISTS FOR (u:User) ON (u.created_at)",
            
            # Document 인덱스
            "CREATE INDEX document_type_index IF NOT EXISTS FOR (d:Document) ON (d.type)",
            "CREATE INDEX document_created_at_index IF NOT EXISTS FOR (d:Document) ON (d.created_at)",
            "CREATE INDEX document_modified_at_index IF NOT EXISTS FOR (d:Document) ON (d.modified_at)",
            
            # Tag 인덱스
            "CREATE INDEX tag_category_index IF NOT EXISTS FOR (t:Tag) ON (t.category)",
            
            # Concept 인덱스
            "CREATE INDEX concept_name_index IF NOT EXISTS FOR (c:Concept) ON (c.name)",
            "CREATE INDEX concept_category_index IF NOT EXISTS FOR (c:Concept) ON (c.category)",
            
            # 관계 인덱스
            "CREATE INDEX relationship_timestamp_index IF NOT EXISTS FOR ()-[r]-() ON (r.timestamp)",
            "CREATE INDEX relationship_weight_index IF NOT EXISTS FOR ()-[r]-() ON (r.weight)"
        ]
        
        for index in indexes:
            try:
                session.run(index)
                logger.debug(f"인덱스 생성: {index}")
            except Exception as e:
                logger.warning(f"인덱스 생성 실패: {index} - {e}")
    
    def _create_base_structure(self, session):
        """기본 데이터 구조 생성"""
        try:
            # 시스템 사용자 생성
            system_user_query = """
            MERGE (u:User {id: 'system', email: 'system@argo.local'})
            SET u.name = 'ARGO System',
                u.role = 'system',
                u.created_at = datetime(),
                u.is_active = true
            RETURN u
            """
            session.run(system_user_query)
            
            # 기본 태그 카테고리 생성
            tag_categories = [
                'documentation', 'code', 'design', 'meeting_notes',
                'planning', 'research', 'personal', 'reference'
            ]
            
            for category in tag_categories:
                tag_query = """
                MERGE (t:Tag {name: $category})
                SET t.category = 'content_type',
                    t.created_at = datetime(),
                    t.is_system = true
                RETURN t
                """
                session.run(tag_query, category=category)
            
            # 기본 프로젝트 생성
            project_query = """
            MERGE (p:Project {id: 'default', name: 'Default Project'})
            SET p.description = 'Default ARGO project',
                p.created_at = datetime(),
                p.is_active = true
            RETURN p
            """
            session.run(project_query)
            
            logger.info("✅ 기본 데이터 구조 생성 완료")
            
        except Exception as e:
            logger.error(f"❌ 기본 데이터 구조 생성 실패: {e}")
    
    async def execute_graph_operation(self, operation: GraphOperation) -> Dict[str, Any]:
        """그래프 작업 실행 (MockNeo4j 호환)"""
        try:
            logger.info(f"그래프 작업 실행 시작: {operation.operation_type.value}")
            
            # MockNeo4j를 사용하여 직접 작업 실행
            if operation.operation_type == GraphOperationType.CREATE_NODE:
                result = await self._execute_create_operation(operation)
            elif operation.operation_type == GraphOperationType.UPDATE_NODE:
                result = await self._execute_update_operation(operation)
            elif operation.operation_type == GraphOperationType.DELETE_NODE:
                result = await self._execute_delete_operation(operation)
            elif operation.operation_type == GraphOperationType.CREATE_RELATIONSHIP:
                result = await self._execute_create_relationship_operation(operation)
            elif operation.operation_type == GraphOperationType.MERGE_NODE:
                result = await self._execute_merge_node_operation(operation)
            else:
                result = {"success": False, "errors": [f"지원하지 않는 작업 타입: {operation.operation_type.value}"]}
            
            # Redis에 결과 저장
            if result.get("success"):
                result_key = f"graph_operation_result:{operation.id}"
                self.redis_client.setex(
                    result_key,
                    3600,  # 1시간 TTL
                    json.dumps({
                        "success": True,
                        "result": result.get("data", []),
                        "timestamp": datetime.utcnow().isoformat()
                    })
                )
            
            logger.info(f"✅ 그래프 작업 실행 완료: {operation.operation_type.value}")
            return result
            
        except Exception as e:
            logger.error(f"그래프 작업 실행 실패: {e}")
            return {
                "success": False,
                "errors": [str(e)],
                "operation_id": operation.id
            }
    
    async def _validate_operation(self, state: Dict) -> Dict:
        """작업 검증 (LangGraph 노드)"""
        operation = state["current_operation"]
        validation_results = []
        
        try:
            # 기본 검증
            if not operation.id:
                validation_results.append("작업 ID가 없습니다")
            
            if not operation.operation_type:
                validation_results.append("작업 타입이 지정되지 않았습니다")
            
            # 노드 생성 검증
            if operation.operation_type == GraphOperationType.CREATE_NODE:
                if not operation.labels:
                    validation_results.append("노드 라벨이 지정되지 않았습니다")
                
                if not operation.properties:
                    validation_results.append("노드 속성이 지정되지 않았습니다")
            
            # 관계 생성 검증
            elif operation.operation_type == GraphOperationType.CREATE_RELATIONSHIP:
                if not operation.relationship_type:
                    validation_results.append("관계 타입이 지정되지 않았습니다")
                
                if not operation.start_node_id or not operation.end_node_id:
                    validation_results.append("시작/끝 노드 ID가 지정되지 않았습니다")
            
            # 제약 조건 검증
            for constraint in operation.constraints:
                if not self._validate_constraint(operation, constraint):
                    validation_results.append(f"제약 조건 검증 실패: {constraint}")
            
            # 검증 규칙 검증
            for rule in operation.validation_rules:
                if not self._validate_rule(operation, rule):
                    validation_results.append(f"검증 규칙 실패: {rule}")
            
            if validation_results:
                state["validation_results"] = validation_results
                state["errors"].append("검증 실패")
                return state
            
            state["validation_results"] = ["검증 통과"]
            return state
            
        except Exception as e:
            state["errors"].append(f"검증 중 오류: {str(e)}")
            return state
    
    async def _execute_operation(self, state: Dict) -> Dict:
        """작업 실행 (LangGraph 노드)"""
        operation = state["current_operation"]
        execution_results = []
        
        try:
            if operation.operation_type == GraphOperationType.CREATE_NODE:
                result = await self._create_node(operation)
                execution_results.append(result)
                
            elif operation.operation_type == GraphOperationType.UPDATE_NODE:
                result = await self._update_node(operation)
                execution_results.append(result)
                
            elif operation.operation_type == GraphOperationType.DELETE_NODE:
                result = await self._delete_node(operation)
                execution_results.append(result)
                
            elif operation.operation_type == GraphOperationType.CREATE_RELATIONSHIP:
                result = await self._create_relationship(operation)
                execution_results.append(result)
                
            elif operation.operation_type == GraphOperationType.MERGE_NODE:
                result = await self._merge_node(operation)
                execution_results.append(result)
                
            elif operation.operation_type == GraphOperationType.BATCH_OPERATION:
                result = await self._execute_batch_operation(operation)
                execution_results.append(result)
            
            state["execution_results"] = execution_results
            return state
            
        except Exception as e:
            state["errors"].append(f"실행 중 오류: {str(e)}")
            return state
    
    async def _create_node(self, operation: GraphOperation) -> Dict[str, Any]:
        """노드 생성"""
        try:
            with self.driver.session() as session:
                # 라벨 문자열 생성
                label_str = ':'.join(operation.labels) if operation.labels else ''
                
                # 속성에 타임스탬프 추가
                properties = operation.properties.copy()
                properties.update({
                    'id': operation.target_id or str(uuid.uuid4()),
                    'created_at': datetime.utcnow().isoformat(),
                    'modified_at': datetime.utcnow().isoformat()
                })
                
                # 노드 생성 쿼리
                query = f"""
                CREATE (n{':' + label_str if label_str else ''} $properties)
                RETURN n
                """
                
                result = session.run(query, properties=properties)
                node = result.single()["n"]
                
                logger.info(f"✅ 노드 생성 완료: {node.get('id')}")
                
                return {
                    "operation": "create_node",
                    "node_id": node.get('id'),
                    "labels": list(node.labels),
                    "properties": dict(node),
                    "success": True
                }
                
        except Exception as e:
            logger.error(f"❌ 노드 생성 실패: {e}")
            return {
                "operation": "create_node",
                "success": False,
                "error": str(e)
            }
    
    async def _update_node(self, operation: GraphOperation) -> Dict[str, Any]:
        """노드 업데이트"""
        try:
            with self.driver.session() as session:
                # 기존 노드 조회
                query = """
                MATCH (n) WHERE n.id = $node_id
                RETURN n
                """
                
                result = session.run(query, node_id=operation.target_id)
                existing_node = result.single()
                
                if not existing_node:
                    return {
                        "operation": "update_node",
                        "success": False,
                        "error": "노드를 찾을 수 없습니다"
                    }
                
                # 속성 업데이트
                properties = operation.properties.copy()
                properties['modified_at'] = datetime.utcnow().isoformat()
                
                update_query = """
                MATCH (n) WHERE n.id = $node_id
                SET n += $properties
                RETURN n
                """
                
                result = session.run(update_query, 
                                  node_id=operation.target_id, 
                                  properties=properties)
                
                updated_node = result.single()["n"]
                
                logger.info(f"✅ 노드 업데이트 완료: {operation.target_id}")
                
                return {
                    "operation": "update_node",
                    "node_id": operation.target_id,
                    "properties": dict(updated_node),
                    "success": True
                }
                
        except Exception as e:
            logger.error(f"❌ 노드 업데이트 실패: {e}")
            return {
                "operation": "update_node",
                "success": False,
                "error": str(e)
            }
    
    async def _delete_node(self, operation: GraphOperation) -> Dict[str, Any]:
        """노드 삭제"""
        try:
            with self.driver.session() as session:
                # 노드와 관련된 모든 관계 삭제
                query = """
                MATCH (n) WHERE n.id = $node_id
                OPTIONAL MATCH (n)-[r]-()
                DELETE r, n
                RETURN count(n) as deleted_count
                """
                
                result = session.run(query, node_id=operation.target_id)
                deleted_count = result.single()["deleted_count"]
                
                logger.info(f"✅ 노드 삭제 완료: {operation.target_id}")
                
                return {
                    "operation": "delete_node",
                    "node_id": operation.target_id,
                    "deleted_count": deleted_count,
                    "success": True
                }
                
        except Exception as e:
            logger.error(f"❌ 노드 삭제 실패: {e}")
            return {
                "operation": "delete_node",
                "success": False,
                "error": str(e)
            }
    
    async def _create_relationship(self, operation: GraphOperation) -> Dict[str, Any]:
        """관계 생성"""
        try:
            with self.driver.session() as session:
                # 시작/끝 노드 존재 확인
                start_query = "MATCH (n) WHERE n.id = $node_id RETURN n"
                end_query = "MATCH (n) WHERE n.id = $node_id RETURN n"
                
                start_result = session.run(start_query, node_id=operation.start_node_id)
                end_result = session.run(end_query, node_id=operation.end_node_id)
                
                if not start_result.single() or not end_result.single():
                    return {
                        "operation": "create_relationship",
                        "success": False,
                        "error": "시작 또는 끝 노드를 찾을 수 없습니다"
                    }
                
                # 관계 속성에 타임스탬프 추가
                properties = operation.properties.copy()
                properties.update({
                    'created_at': datetime.utcnow().isoformat(),
                    'weight': properties.get('weight', 1.0)
                })
                
                # 관계 생성
                rel_query = """
                MATCH (a), (b) 
                WHERE a.id = $start_id AND b.id = $end_id
                CREATE (a)-[r:$rel_type $properties]->(b)
                RETURN r
                """
                
                result = session.run(rel_query,
                                  start_id=operation.start_node_id,
                                  end_id=operation.end_node_id,
                                  rel_type=operation.relationship_type,
                                  properties=properties)
                
                relationship = result.single()["r"]
                
                logger.info(f"✅ 관계 생성 완료: {operation.start_node_id} -> {operation.end_node_id}")
                
                return {
                    "operation": "create_relationship",
                    "relationship_id": id(relationship),
                    "start_node": operation.start_node_id,
                    "end_node": operation.end_node_id,
                    "type": operation.relationship_type,
                    "properties": dict(relationship),
                    "success": True
                }
                
        except Exception as e:
            logger.error(f"❌ 관계 생성 실패: {e}")
            return {
                "operation": "create_relationship",
                "success": False,
                "error": str(e)
            }
    
    async def _merge_node(self, operation: GraphOperation) -> Dict[str, Any]:
        """노드 병합 (MERGE)"""
        try:
            with self.driver.session() as session:
                # 라벨 문자열 생성
                label_str = ':'.join(operation.labels) if operation.labels else ''
                
                # 속성에 타임스탬프 추가
                properties = operation.properties.copy()
                properties.update({
                    'id': operation.target_id or str(uuid.uuid4()),
                    'modified_at': datetime.utcnow().isoformat()
                })
                
                # MERGE 쿼리 (기존 노드가 있으면 업데이트, 없으면 생성)
                merge_query = f"""
                MERGE (n{':' + label_str if label_str else ''} {{id: $id}})
                ON CREATE SET n += $properties, n.created_at = datetime()
                ON MATCH SET n += $properties
                RETURN n
                """
                
                result = session.run(merge_query, 
                                  id=properties['id'],
                                  properties=properties)
                
                node = result.single()["n"]
                
                logger.info(f"✅ 노드 병합 완료: {node.get('id')}")
                
                return {
                    "operation": "merge_node",
                    "node_id": node.get('id'),
                    "labels": list(node.labels),
                    "properties": dict(node),
                    "success": True
                }
                
        except Exception as e:
            logger.error(f"❌ 노드 병합 실패: {e}")
            return {
                "operation": "merge_node",
                "success": False,
                "error": str(e)
            }
    
    async def _execute_batch_operation(self, operation: GraphOperation) -> Dict[str, Any]:
        """배치 작업 실행"""
        try:
            batch_data = operation.properties.get('batch_data', [])
            if not batch_data:
                return {
                    "operation": "batch_operation",
                    "success": False,
                    "error": "배치 데이터가 없습니다"
                }
            
            results = []
            with self.driver.session() as session:
                with session.begin_transaction() as tx:
                    for item in batch_data:
                        try:
                            if item['type'] == 'create_node':
                                result = await self._create_node_in_transaction(tx, item)
                            elif item['type'] == 'create_relationship':
                                result = await self._create_relationship_in_transaction(tx, item)
                            else:
                                result = {"success": False, "error": f"지원하지 않는 작업 타입: {item['type']}"}
                            
                            results.append(result)
                            
                        except Exception as e:
                            results.append({"success": False, "error": str(e)})
                    
                    # 모든 작업이 성공하면 커밋
                    if all(r.get('success', False) for r in results):
                        tx.commit()
                        logger.info(f"✅ 배치 작업 완료: {len(results)}개 작업")
                    else:
                        tx.rollback()
                        logger.error(f"❌ 배치 작업 실패, 롤백됨")
            
            logger.info(f"✅ 배치 작업 완료: {len(batch_data)}개 작업")
            
            return {
                "operation": "batch_operation",
                "results": results,
                "total_count": len(batch_data),
                "success_count": sum(1 for r in results if r.get('success', False)),
                "success": True
            }
            
        except Exception as e:
            logger.error(f"❌ 배치 작업 실패: {e}")
            return {
                "operation": "batch_operation",
                "success": False,
                "error": str(e)
            }
    
    async def _create_node_in_transaction(self, tx, item: Dict) -> Dict[str, Any]:
        """트랜잭션 내에서 노드 생성"""
        labels = item.get('labels', [])
        properties = item.get('properties', {})
        
        label_str = ':'.join(labels) if labels else ''
        properties.update({
            'id': str(uuid.uuid4()),
            'created_at': datetime.utcnow().isoformat(),
            'modified_at': datetime.utcnow().isoformat()
        })
        
        query = f"CREATE (n{':' + label_str if label_str else ''} $properties) RETURN n"
        result = tx.run(query, properties=properties)
        node = result.single()["n"]
        
        return {
            "type": "create_node",
            "node_id": node.get('id'),
            "success": True
        }
    
    async def _create_relationship_in_transaction(self, tx, item: Dict) -> Dict[str, Any]:
        """트랜잭션 내에서 관계 생성"""
        start_id = item.get('start_node_id')
        end_id = item.get('end_node_id')
        rel_type = item.get('relationship_type')
        properties = item.get('properties', {})
        
        properties.update({
            'created_at': datetime.utcnow().isoformat(),
            'weight': properties.get('weight', 1.0)
        })
        
        query = """
        MATCH (a), (b) 
        WHERE a.id = $start_id AND b.id = $end_id
        CREATE (a)-[r:$rel_type $properties]->(b)
        RETURN r
        """
        
        result = tx.run(query,
                      start_id=start_id,
                      end_id=end_id,
                      rel_type=rel_type,
                      properties=properties)
        
        return {
            "type": "create_relationship",
            "success": True
        }
    
    def _validate_constraint(self, operation: GraphOperation, constraint: str) -> bool:
        """제약 조건 검증"""
        try:
            # 간단한 제약 조건 검증 로직
            if constraint == "unique_id":
                return operation.target_id is not None
            elif constraint == "required_properties":
                required_props = ['name', 'type']
                return all(prop in operation.properties for prop in required_props)
            elif constraint == "valid_labels":
                valid_labels = ['User', 'Document', 'Tag', 'Concept', 'Project']
                return all(label in valid_labels for label in operation.labels)
            
            return True
            
        except Exception as e:
            logger.error(f"제약 조건 검증 실패: {constraint} - {e}")
            return False
    
    def _validate_rule(self, operation: GraphOperation, rule: str) -> bool:
        """검증 규칙 검증"""
        try:
            # 간단한 검증 규칙 로직
            if rule == "max_properties":
                max_props = 20
                return len(operation.properties) <= max_props
            elif rule == "valid_property_types":
                valid_types = [str, int, float, bool]
                return all(isinstance(v, tuple(valid_types)) for v in operation.properties.values())
            
            return True
            
        except Exception as e:
            logger.error(f"검증 규칙 실패: {rule} - {e}")
            return False
    
    async def _update_metrics(self, state: Dict) -> Dict:
        """성능 메트릭 업데이트 (LangGraph 노드)"""
        try:
            operation = state["current_operation"]
            
            # 실행 시간 측정
            start_time = datetime.utcnow()
            execution_time = (start_time - operation.timestamp).total_seconds()
            
            # 성능 메트릭 저장
            self.performance_metrics[operation.id] = {
                "execution_time": execution_time,
                "operation_type": operation.operation_type.value,
                "timestamp": start_time.isoformat()
            }
            
            state["performance_metrics"] = self.performance_metrics
            return state
            
        except Exception as e:
            state["errors"].append(f"메트릭 업데이트 실패: {str(e)}")
            return state
    
    async def _handle_errors(self, state: Dict) -> Dict:
        """에러 처리 (LangGraph 노드)"""
        try:
            operation = state["current_operation"]
            
            # 실패한 작업을 재시도 큐에 추가
            if operation.id not in [op.id for op in self.failed_operations]:
                self.failed_operations.append(operation)
                
                # Redis에 실패 정보 저장
                error_key = f"graph_operation_error:{operation.id}"
                self.redis_client.setex(
                    error_key,
                    7200,  # 2시간 TTL
                    json.dumps({
                        "operation_id": operation.id,
                        "errors": state.get("errors", []),
                        "timestamp": datetime.utcnow().isoformat()
                    })
                )
            
            logger.error(f"작업 실패: {operation.id} - {state.get('errors', [])}")
            return state
            
        except Exception as e:
            state["errors"].append(f"에러 처리 실패: {str(e)}")
            return state
    
    async def execute_cypher_query(self, query: str, parameters: Dict = None) -> Dict[str, Any]:
        """Cypher 쿼리 실행"""
        try:
            start_time = datetime.utcnow()
            
            with self.driver.session() as session:
                result = session.run(query, parameters or {})
                
                # 결과 처리
                records = []
                for record in result:
                    try:
                        # MockNeo4j 결과를 안전하게 처리
                        if hasattr(record, 'data'):
                            records.append(record.data)
                        else:
                            records.append(dict(record))
                    except Exception as e:
                        logger.warning(f"레코드 처리 중 오류: {e}")
                        # 기본값으로 처리
                        records.append({"raw_record": str(record)})
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                logger.info(f"✅ Cypher 쿼리 실행 완료: {execution_time:.3f}초")
                
                return {
                    "success": True,
                    "records": records,
                    "count": len(records),
                    "execution_time": execution_time
                }
                
        except Exception as e:
            logger.error(f"❌ Cypher 쿼리 실행 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 조회"""
        return {
            "performance_metrics": self.performance_metrics,
            "operation_queue_size": len(self.operation_queue),
            "failed_operations_count": len(self.failed_operations)
        }
    
    async def cleanup_failed_operations(self) -> int:
        """실패한 작업 정리"""
        cleaned_count = 0
        
        for operation in self.failed_operations[:]:
            # 24시간 이상 된 실패 작업 제거
            if datetime.utcnow() - operation.timestamp > timedelta(hours=24):
                self.failed_operations.remove(operation)
                cleaned_count += 1
                
                # Redis에서도 제거
                error_key = f"graph_operation_error:{operation.id}"
                self.redis_client.delete(error_key)
        
        if cleaned_count > 0:
            logger.info(f"실패한 작업 정리 완료: {cleaned_count}개")
        
        return cleaned_count
    
    async def shutdown(self):
        """정상 종료"""
        try:
            # 실패한 작업 정리
            await self.cleanup_failed_operations()
            
            # Neo4j 연결 종료
            if self.driver:
                self.driver.close()
            
            logger.info("Neo4jLangGraphManager 정상 종료")
            
        except Exception as e:
            logger.error(f"종료 중 오류: {e}")

# 사용 예시
async def main():
    # 설정
    neo4j_config = {
        'uri': 'bolt://localhost:7687',
        'username': 'neo4j',
        'password': 'password'
    }
    
    redis_config = {
        'host': 'localhost',
        'port': 6379,
        'db': 0
    }
    
    # 매니저 초기화
    manager = Neo4jLangGraphManager(neo4j_config, redis_config)
    
    try:
        # 노드 생성 작업
        create_node_op = GraphOperation(
            id="op_001",
            operation_type=GraphOperationType.CREATE_NODE,
            target_type="node",
            labels=["User"],
            properties={
                "name": "Test User",
                "email": "test@example.com",
                "role": "developer"
            }
        )
        
        # 작업 실행
        result = await manager.execute_graph_operation(create_node_op)
        print(f"작업 결과: {json.dumps(result, indent=2, default=str)}")
        
        # 성능 메트릭 조회
        metrics = manager.get_performance_metrics()
        print(f"성능 메트릭: {json.dumps(metrics, indent=2, default=str)}")
        
    finally:
        await manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
