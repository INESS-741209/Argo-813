#!/usr/bin/env python3
"""
Transaction Manager for Redis-Neo4j Data Synchronization
실제 데이터로 인한 시스템 파괴를 방지하기 위한 견고한 트랜잭션 관리
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import redis
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, TransientError

logger = logging.getLogger(__name__)

class TransactionStatus(Enum):
    PENDING = "pending"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"

@dataclass
class SyncOperation:
    id: str
    operation_type: str  # 'create', 'update', 'delete'
    entity_type: str     # 'node', 'relationship', 'property'
    entity_id: str
    data: Dict[str, Any]
    timestamp: datetime
    dependencies: List[str] = None
    retry_count: int = 0
    max_retries: int = 3

class DataSyncTransactionManager:
    """
    Redis와 Neo4j 간 데이터 동기화를 위한 트랜잭션 관리자
    실제 데이터로 인한 시스템 파괴를 방지하기 위한 견고한 메커니즘
    """
    
    def __init__(self, redis_config: Dict, neo4j_config: Dict):
        self.redis_config = redis_config
        self.neo4j_config = neo4j_config
        
        # Redis 연결 (MockRedis 자동 전환 포함)
        self.redis_client = self._get_redis_client()
        
        # Neo4j 연결
        self.neo4j_driver = self._get_neo4j_driver()
        
        # 트랜잭션 상태 관리
        self.active_transactions: Dict[str, Dict] = {}
        self.operation_queue: List[SyncOperation] = []
        self.failed_operations: List[SyncOperation] = []
        
        # 동기화 설정
        self.sync_batch_size = 100
        self.sync_timeout = 30  # 초
        self.max_retry_delay = 300  # 초
        
        # 이벤트 핸들러
        self.event_handlers: Dict[str, List[Callable]] = {
            'sync_started': [],
            'sync_completed': [],
            'sync_failed': [],
            'rollback_required': [],
            'data_conflict': []
        }
        
        logger.info("DataSyncTransactionManager initialized")
    
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
    
    def register_event_handler(self, event_type: str, handler: Callable):
        """이벤트 핸들러 등록"""
        if event_type in self.event_handlers:
            self.event_handlers[event_type].append(handler)
            logger.debug(f"이벤트 핸들러 등록: {event_type}")
    
    def _emit_event(self, event_type: str, data: Any = None):
        """이벤트 발생"""
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    handler(data)
                except Exception as e:
                    logger.error(f"이벤트 핸들러 실행 실패: {e}")
    
    async def begin_transaction(self, transaction_id: str) -> bool:
        """트랜잭션 시작"""
        try:
            # Redis에 트랜잭션 상태 저장
            transaction_state = {
                'id': transaction_id,
                'status': TransactionStatus.PENDING.value,
                'started_at': datetime.utcnow().isoformat(),
                'operations_count': 0,
                'retry_count': 0
            }
            
            self.redis_client.hset(
                f"transaction:{transaction_id}",
                mapping=transaction_state
            )
            self.redis_client.expire(f"transaction:{transaction_id}", 3600)  # 1시간 TTL
            
            self.active_transactions[transaction_id] = transaction_state
            logger.info(f"트랜잭션 시작: {transaction_id}")
            
            self._emit_event('sync_started', {'transaction_id': transaction_id})
            return True
            
        except Exception as e:
            logger.error(f"트랜잭션 시작 실패: {e}")
            return False
    
    async def add_operation(self, transaction_id: str, operation: SyncOperation) -> bool:
        """트랜잭션에 동기화 작업 추가"""
        try:
            if transaction_id not in self.active_transactions:
                logger.error(f"활성 트랜잭션이 아님: {transaction_id}")
                return False
            
            # Redis에 작업 저장
            operation_key = f"operation:{transaction_id}:{operation.id}"
            operation_data = {
                'id': operation.id,
                'operation_type': operation.operation_type,
                'entity_type': operation.entity_type,
                'entity_id': operation.entity_id,
                'data': json.dumps(operation.data),
                'timestamp': operation.timestamp.isoformat(),
                'dependencies': json.dumps(operation.dependencies or []),
                'retry_count': operation.retry_count,
                'max_retries': operation.max_retries
            }
            
            self.redis_client.hset(operation_key, mapping=operation_data)
            self.redis_client.expire(operation_key, 3600)
            
            # 트랜잭션 작업 수 증가
            self.redis_client.hincrby(f"transaction:{transaction_id}", "operations_count", 1)
            
            self.operation_queue.append(operation)
            logger.debug(f"작업 추가: {operation.id} to {transaction_id}")
            return True
            
        except Exception as e:
            logger.error(f"작업 추가 실패: {e}")
            return False
    
    async def commit_transaction(self, transaction_id: str) -> bool:
        """트랜잭션 커밋"""
        try:
            if transaction_id not in self.active_transactions:
                logger.error(f"활성 트랜잭션이 아님: {transaction_id}")
                return False
            
            logger.info(f"트랜잭션 커밋 시작: {transaction_id}")
            
            # 1단계: Redis에서 모든 작업 수집
            operations = await self._get_transaction_operations(transaction_id)
            if not operations:
                logger.warning(f"커밋할 작업이 없음: {transaction_id}")
                return await self._rollback_transaction(transaction_id)
            
            # 2단계: 의존성 검증
            if not await self._validate_dependencies(operations):
                logger.error(f"의존성 검증 실패: {transaction_id}")
                return await self._rollback_transaction(transaction_id)
            
            # 3단계: Neo4j에 배치 실행
            success = await self._execute_neo4j_batch(operations)
            
            if success:
                # 4단계: Redis 상태 업데이트
                await self._update_transaction_status(transaction_id, TransactionStatus.COMMITTED)
                logger.info(f"✅ 트랜잭션 커밋 성공: {transaction_id}")
                self._emit_event('sync_completed', {'transaction_id': transaction_id})
                return True
            else:
                # 5단계: 실패 시 롤백
                logger.error(f"Neo4j 실행 실패, 롤백 시작: {transaction_id}")
                return await self._rollback_transaction(transaction_id)
                
        except Exception as e:
            logger.error(f"트랜잭션 커밋 실패: {e}")
            return await self._rollback_transaction(transaction_id)
    
    async def _get_transaction_operations(self, transaction_id: str) -> List[SyncOperation]:
        """트랜잭션의 모든 작업 수집"""
        try:
            operation_keys = self.redis_client.keys(f"operation:{transaction_id}:*")
            operations = []
            
            for key in operation_keys:
                operation_data = self.redis_client.hgetall(key)
                if operation_data:
                    operation = SyncOperation(
                        id=operation_data['id'],
                        operation_type=operation_data['operation_type'],
                        entity_type=operation_data['entity_type'],
                        entity_id=operation_data['entity_id'],
                        data=json.loads(operation_data['data']),
                        timestamp=datetime.fromisoformat(operation_data['timestamp']),
                        dependencies=json.loads(operation_data['dependencies']),
                        retry_count=int(operation_data['retry_count']),
                        max_retries=int(operation_data['max_retries'])
                    )
                    operations.append(operation)
            
            return sorted(operations, key=lambda x: x.timestamp)
            
        except Exception as e:
            logger.error(f"작업 수집 실패: {e}")
            return []
    
    async def _validate_dependencies(self, operations: List[SyncOperation]) -> bool:
        """작업 간 의존성 검증"""
        try:
            # 의존성 그래프 생성
            dependency_graph = {}
            for op in operations:
                dependency_graph[op.id] = op.dependencies or []
            
            # 순환 의존성 검사
            visited = set()
            rec_stack = set()
            
            def has_cycle(node):
                visited.add(node)
                rec_stack.add(node)
                
                for neighbor in dependency_graph.get(node, []):
                    if neighbor not in visited:
                        if has_cycle(neighbor):
                            return True
                    elif neighbor in rec_stack:
                        return True
                
                rec_stack.remove(node)
                return False
            
            # 모든 노드에 대해 순환 검사
            for node in dependency_graph:
                if node not in visited:
                    if has_cycle(node):
                        logger.error(f"순환 의존성 발견: {node}")
                        return False
            
            logger.debug("의존성 검증 통과")
            return True
            
        except Exception as e:
            logger.error(f"의존성 검증 실패: {e}")
            return False
    
    async def _execute_neo4j_batch(self, operations: List[SyncOperation]) -> bool:
        """Neo4j에 배치 작업 실행"""
        try:
            with self.neo4j_driver.session() as session:
                # 트랜잭션 내에서 배치 실행
                with session.begin_transaction() as tx:
                    for operation in operations:
                        try:
                            if operation.operation_type == 'create':
                                await self._execute_create_operation(tx, operation)
                            elif operation.operation_type == 'update':
                                await self._execute_update_operation(tx, operation)
                            elif operation.operation_type == 'delete':
                                await self._execute_delete_operation(tx, operation)
                            
                            logger.debug(f"작업 실행 성공: {operation.id}")
                            
                        except Exception as e:
                            logger.error(f"작업 실행 실패: {operation.id} - {e}")
                            # 개별 작업 실패 시 전체 롤백
                            raise
                    
                    # 모든 작업이 성공하면 커밋
                    tx.commit()
                    logger.info(f"Neo4j 배치 실행 성공: {len(operations)}개 작업")
                    return True
                    
        except Exception as e:
            logger.error(f"Neo4j 배치 실행 실패: {e}")
            return False
    
    async def _execute_create_operation(self, tx, operation: SyncOperation):
        """생성 작업 실행"""
        if operation.entity_type == 'node':
            # 노드 생성
            labels = operation.data.get('labels', [])
            properties = operation.data.get('properties', {})
            
            label_str = ':'.join(labels) if labels else ''
            query = f"CREATE (n{':' + label_str if label_str else ''} $properties) RETURN n"
            tx.run(query, properties=properties)
            
        elif operation.entity_type == 'relationship':
            # 관계 생성
            start_node_id = operation.data.get('start_node_id')
            end_node_id = operation.data.get('end_node_id')
            rel_type = operation.data.get('type')
            properties = operation.data.get('properties', {})
            
            query = """
            MATCH (a), (b) 
            WHERE id(a) = $start_id AND id(b) = $end_id
            CREATE (a)-[r:$rel_type $properties]->(b)
            RETURN r
            """
            tx.run(query, start_id=start_node_id, end_id=end_node_id, 
                   rel_type=rel_type, properties=properties)
    
    async def _execute_update_operation(self, tx, operation: SyncOperation):
        """업데이트 작업 실행"""
        if operation.entity_type == 'node':
            # 노드 속성 업데이트
            node_id = operation.entity_id
            properties = operation.data.get('properties', {})
            
            query = """
            MATCH (n) WHERE id(n) = $node_id
            SET n += $properties
            RETURN n
            """
            tx.run(query, node_id=node_id, properties=properties)
    
    async def _execute_delete_operation(self, tx, operation: SyncOperation):
        """삭제 작업 실행"""
        if operation.entity_type == 'node':
            # 노드 삭제 (관계도 함께)
            node_id = operation.entity_id
            
            query = """
            MATCH (n) WHERE id(n) = $node_id
            DETACH DELETE n
            """
            tx.run(query, node_id=node_id)
    
    async def _update_transaction_status(self, transaction_id: str, status: TransactionStatus):
        """트랜잭션 상태 업데이트"""
        try:
            update_data = {
                'status': status.value,
                'completed_at': datetime.utcnow().isoformat()
            }
            
            self.redis_client.hset(f"transaction:{transaction_id}", mapping=update_data)
            
            if status == TransactionStatus.COMMITTED:
                # 성공한 작업들 정리
                operation_keys = self.redis_client.keys(f"operation:{transaction_id}:*")
                for key in operation_keys:
                    self.redis_client.delete(key)
                
                # 트랜잭션 정보도 정리
                self.redis_client.delete(f"transaction:{transaction_id}")
                
                if transaction_id in self.active_transactions:
                    del self.active_transactions[transaction_id]
            
            logger.debug(f"트랜잭션 상태 업데이트: {transaction_id} -> {status.value}")
            
        except Exception as e:
            logger.error(f"상태 업데이트 실패: {e}")
    
    async def _rollback_transaction(self, transaction_id: str) -> bool:
        """트랜잭션 롤백"""
        try:
            logger.warning(f"트랜잭션 롤백 시작: {transaction_id}")
            
            # Redis에서 작업들 복구
            operations = await self._get_transaction_operations(transaction_id)
            
            # 롤백 작업 실행
            for operation in reversed(operations):  # 역순으로 롤백
                try:
                    await self._rollback_operation(operation)
                except Exception as e:
                    logger.error(f"작업 롤백 실패: {operation.id} - {e}")
            
            # 상태 업데이트
            await self._update_transaction_status(transaction_id, TransactionStatus.ROLLED_BACK)
            
            # 실패한 작업들을 재시도 큐에 추가
            for operation in operations:
                if operation.retry_count < operation.max_retries:
                    operation.retry_count += 1
                    operation.timestamp = datetime.utcnow()
                    self.failed_operations.append(operation)
                    logger.info(f"재시도 큐에 추가: {operation.id} (시도: {operation.retry_count})")
            
            self._emit_event('rollback_required', {
                'transaction_id': transaction_id,
                'operations_count': len(operations)
            })
            
            logger.info(f"✅ 트랜잭션 롤백 완료: {transaction_id}")
            return True
            
        except Exception as e:
            logger.error(f"트랜잭션 롤백 실패: {e}")
            return False
    
    async def _rollback_operation(self, operation: SyncOperation):
        """개별 작업 롤백"""
        try:
            with self.neo4j_driver.session() as session:
                with session.begin_transaction() as tx:
                    if operation.operation_type == 'create':
                        # 생성된 노드/관계 삭제
                        if operation.entity_type == 'node':
                            query = """
                            MATCH (n) WHERE id(n) = $node_id
                            DETACH DELETE n
                            """
                            tx.run(query, node_id=operation.entity_id)
                    
                    elif operation.operation_type == 'delete':
                        # 삭제된 노드/관계 복구
                        if operation.entity_type == 'node':
                            properties = operation.data.get('properties', {})
                            labels = operation.data.get('labels', [])
                            
                            label_str = ':'.join(labels) if labels else ''
                            query = f"CREATE (n{':' + label_str if label_str else ''} $properties) RETURN n"
                            tx.run(query, properties=properties)
                    
                    elif operation.operation_type == 'update':
                        # 업데이트된 속성을 원래 값으로 복구
                        original_properties = operation.data.get('original_properties', {})
                        node_id = operation.entity_id
                        
                        query = """
                        MATCH (n) WHERE id(n) = $node_id
                        SET n += $properties
                        RETURN n
                        """
                        tx.run(query, node_id=node_id, properties=original_properties)
                    
                    tx.commit()
                    logger.debug(f"작업 롤백 성공: {operation.id}")
                    
        except Exception as e:
            logger.error(f"작업 롤백 실패: {operation.id} - {e}")
            raise
    
    async def retry_failed_operations(self) -> int:
        """실패한 작업들 재시도"""
        if not self.failed_operations:
            return 0
        
        logger.info(f"실패한 작업 재시도 시작: {len(self.failed_operations)}개")
        
        retry_count = 0
        still_failed = []
        
        for operation in self.failed_operations:
            try:
                # 지수 백오프로 재시도 지연
                delay = min(2 ** operation.retry_count, self.max_retry_delay)
                await asyncio.sleep(delay)
                
                # 재시도 실행
                success = await self._retry_single_operation(operation)
                if success:
                    retry_count += 1
                    logger.info(f"재시도 성공: {operation.id}")
                else:
                    still_failed.append(operation)
                    
            except Exception as e:
                logger.error(f"재시도 실패: {operation.id} - {e}")
                still_failed.append(operation)
        
        self.failed_operations = still_failed
        logger.info(f"재시도 완료: 성공 {retry_count}개, 실패 {len(still_failed)}개")
        
        return retry_count
    
    async def _retry_single_operation(self, operation: SyncOperation) -> bool:
        """단일 작업 재시도"""
        try:
            with self.neo4j_driver.session() as session:
                with session.begin_transaction() as tx:
                    if operation.operation_type == 'create':
                        await self._execute_create_operation(tx, operation)
                    elif operation.operation_type == 'update':
                        await self._execute_update_operation(tx, operation)
                    elif operation.operation_type == 'delete':
                        await self._execute_delete_operation(tx, operation)
                    
                    tx.commit()
                    return True
                    
        except Exception as e:
            logger.error(f"단일 작업 재시도 실패: {operation.id} - {e}")
            return False
    
    async def get_transaction_status(self, transaction_id: str) -> Optional[Dict]:
        """트랜잭션 상태 조회"""
        try:
            transaction_data = self.redis_client.hgetall(f"transaction:{transaction_id}")
            if transaction_data:
                return transaction_data
            return None
        except Exception as e:
            logger.error(f"상태 조회 실패: {e}")
            return None
    
    async def cleanup_expired_transactions(self):
        """만료된 트랜잭션 정리"""
        try:
            # 1시간 이상 된 트랜잭션들 찾기
            expired_keys = self.redis_client.keys("transaction:*")
            cleaned_count = 0
            
            for key in expired_keys:
                transaction_data = self.redis_client.hgetall(key)
                if transaction_data:
                    started_at = datetime.fromisoformat(transaction_data.get('started_at', ''))
                    if datetime.utcnow() - started_at > timedelta(hours=1):
                        # 관련 작업들도 정리
                        transaction_id = key.split(':')[1]
                        operation_keys = self.redis_client.keys(f"operation:{transaction_id}:*")
                        for op_key in operation_keys:
                            self.redis_client.delete(op_key)
                        
                        self.redis_client.delete(key)
                        cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"만료된 트랜잭션 정리 완료: {cleaned_count}개")
                
        except Exception as e:
            logger.error(f"만료된 트랜잭션 정리 실패: {e}")
    
    async def shutdown(self):
        """정상 종료"""
        try:
            # 활성 트랜잭션들 롤백
            for transaction_id in list(self.active_transactions.keys()):
                await self._rollback_transaction(transaction_id)
            
            # Neo4j 연결 종료
            if self.neo4j_driver:
                self.neo4j_driver.close()
            
            # Redis 연결 종료
            if hasattr(self.redis_client, 'close'):
                self.redis_client.close()
            
            logger.info("DataSyncTransactionManager 정상 종료")
            
        except Exception as e:
            logger.error(f"종료 중 오류: {e}")

# 사용 예시
async def main():
    # 설정
    redis_config = {
        'host': 'localhost',
        'port': 6379,
        'db': 0
    }
    
    neo4j_config = {
        'uri': 'bolt://localhost:7687',
        'username': 'neo4j',
        'password': 'password'
    }
    
    # 트랜잭션 매니저 초기화
    manager = DataSyncTransactionManager(redis_config, neo4j_config)
    
    try:
        # 트랜잭션 시작
        transaction_id = "tx_001"
        await manager.begin_transaction(transaction_id)
        
        # 작업 추가
        operation = SyncOperation(
            id="op_001",
            operation_type="create",
            entity_type="node",
            entity_id="user_123",
            data={
                'labels': ['User'],
                'properties': {
                    'name': 'Test User',
                    'email': 'test@example.com'
                }
            },
            timestamp=datetime.utcnow()
        )
        
        await manager.add_operation(transaction_id, operation)
        
        # 트랜잭션 커밋
        success = await manager.commit_transaction(transaction_id)
        
        if success:
            print("✅ 트랜잭션 성공")
        else:
            print("❌ 트랜잭션 실패")
    
    finally:
        await manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
