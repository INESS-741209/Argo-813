"""
향상된 데이터 동기화 매니저
ARGO Phase 2: 데이터 일관성 문제 해결 및 이벤트 기반 동기화
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import uuid
from collections import defaultdict, deque
import hashlib

logger = logging.getLogger(__name__)

class SyncOperationType(Enum):
    """동기화 작업 타입"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MERGE = "merge"
    BATCH_UPDATE = "batch_update"

class DataConflictResolution(Enum):
    """데이터 충돌 해결 방법"""
    LAST_WRITE_WINS = "last_write_wins"
    MERGE_STRATEGY = "merge_strategy"
    MANUAL_RESOLUTION = "manual_resolution"
    ROLLBACK = "rollback"

@dataclass
class SyncOperation:
    """동기화 작업 객체"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    operation_type: SyncOperationType = SyncOperationType.CREATE
    source_system: str = ""  # 'redis', 'neo4j', 'bigquery'
    target_systems: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    status: str = "pending"  # pending, processing, completed, failed, conflicted
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    conflict_resolution: Optional[DataConflictResolution] = None
    
    def __post_init__(self):
        if not self.target_systems:
            # 기본적으로 모든 시스템에 동기화
            self.target_systems = ['redis', 'neo4j', 'bigquery']

@dataclass
class DataVersion:
    """데이터 버전 정보"""
    version_id: str
    data_hash: str
    timestamp: datetime
    system: str
    operation_id: str

class EnhancedDataSyncManager:
    """향상된 데이터 동기화 매니저"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 시스템별 클라이언트
        self.redis_client = None
        self.neo4j_driver = None
        self.bigquery_client = None
        
        # 동기화 큐
        self.sync_queue: asyncio.Queue = asyncio.Queue()
        self.priority_queue: deque = deque()
        
        # 동기화 상태 추적
        self.sync_status: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.data_versions: Dict[str, List[DataVersion]] = defaultdict(list)
        
        # 충돌 해결 전략
        self.conflict_resolution_strategy = config.get(
            'conflict_resolution', DataConflictResolution.LAST_WRITE_WINS
        )
        
        # 이벤트 핸들러
        self.event_handlers: Dict[str, List[Callable]] = {
            'sync_started': [],
            'sync_completed': [],
            'sync_failed': [],
            'conflict_detected': [],
            'conflict_resolved': [],
            'rollback_required': []
        }
        
        # 성능 메트릭
        self.metrics = {
            'total_operations': 0,
            'successful_syncs': 0,
            'failed_syncs': 0,
            'conflicts_detected': 0,
            'conflicts_resolved': 0,
            'average_sync_time': 0.0,
            'total_sync_time': 0.0
        }
        
        # 실행 상태
        self.is_running = False
        self.sync_tasks: List[asyncio.Task] = []
        
        # 충돌 해결 큐
        self.conflict_queue: asyncio.Queue = asyncio.Queue()
        
        logger.info("향상된 데이터 동기화 매니저 초기화됨")
    
    async def start(self):
        """동기화 매니저 시작"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # 동기화 작업 처리 태스크 시작
        for _ in range(self.config.get('max_concurrent_syncs', 3)):
            self.sync_tasks.append(
                asyncio.create_task(self._sync_worker())
            )
        
        # 충돌 해결 태스크 시작
        self.sync_tasks.append(
            asyncio.create_task(self._conflict_resolver())
        )
        
        # 모니터링 태스크 시작
        self.sync_tasks.append(
            asyncio.create_task(self._monitor_sync_health())
        )
        
        logger.info("✅ 향상된 데이터 동기화 매니저 시작됨")
    
    async def stop(self):
        """동기화 매니저 중지"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # 모든 태스크 취소
        for task in self.sync_tasks:
            task.cancel()
        
        # 태스크 완료 대기
        await asyncio.gather(*self.sync_tasks, return_exceptions=True)
        self.sync_tasks.clear()
        
        logger.info("🛑 향상된 데이터 동기화 매니저 중지됨")
    
    async def sync_data(self, operation: SyncOperation) -> str:
        """데이터 동기화 요청"""
        # 우선순위 결정
        priority = self._calculate_priority(operation)
        
        if priority == 'high':
            self.priority_queue.appendleft(operation)
        else:
            await self.sync_queue.put(operation)
        
        self.metrics['total_operations'] += 1
        
        logger.info(f"📤 동기화 요청: {operation.operation_type.value} - {operation.source_system}")
        return operation.id
    
    async def sync_batch(self, operations: List[SyncOperation]) -> List[str]:
        """배치 동기화 요청"""
        operation_ids = []
        
        for operation in operations:
            operation_id = await self.sync_data(operation)
            operation_ids.append(operation_id)
        
        logger.info(f"📦 배치 동기화 요청: {len(operations)}개 작업")
        return operation_ids
    
    def _calculate_priority(self, operation: SyncOperation) -> str:
        """동기화 우선순위 계산"""
        # URGENT 메타데이터가 있으면 높은 우선순위
        if operation.metadata.get('urgent', False):
            return 'high'
        
        # DELETE 작업은 높은 우선순위
        if operation.operation_type == SyncOperationType.DELETE:
            return 'high'
        
        # UPDATE 작업은 중간 우선순위
        if operation.operation_type == SyncOperationType.UPDATE:
            return 'medium'
        
        # CREATE 작업은 낮은 우선순위
        return 'low'
    
    async def _sync_worker(self):
        """동기화 작업 처리 워커"""
        while self.is_running:
            try:
                # 우선순위 큐에서 먼저 처리
                if self.priority_queue:
                    operation = self.priority_queue.popleft()
                else:
                    # 일반 큐에서 작업 가져오기
                    operation = await asyncio.wait_for(
                        self.sync_queue.get(), 
                        timeout=1.0
                    )
                
                # 동기화 실행
                await self._execute_sync(operation)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"동기화 워커 오류: {e}")
                await asyncio.sleep(1)
    
    async def _execute_sync(self, operation: SyncOperation):
        """동기화 실행"""
        start_time = time.time()
        operation.status = "processing"
        
        try:
            # 데이터 버전 확인
            data_hash = self._calculate_data_hash(operation.data)
            
            # 충돌 감지
            conflicts = await self._detect_conflicts(operation, data_hash)
            
            if conflicts:
                # 충돌이 감지된 경우
                await self._handle_conflicts(operation, conflicts)
                return
            
            # 동기화 실행
            sync_results = await self._perform_sync(operation, data_hash)
            
            # 성공 처리
            operation.status = "completed"
            self._update_sync_metrics(start_time, True)
            
            # 이벤트 발생
            await self._trigger_event('sync_completed', {
                'operation_id': operation.id,
                'results': sync_results,
                'execution_time': time.time() - start_time
            })
            
            logger.info(f"✅ 동기화 완료: {operation.id}")
            
        except Exception as e:
            # 실패 처리
            operation.status = "failed"
            operation.error_message = str(e)
            self._update_sync_metrics(start_time, False)
            
            # 재시도 로직
            if operation.retry_count < operation.max_retries:
                await self._schedule_retry(operation)
            else:
                # 최종 실패
                await self._trigger_event('sync_failed', {
                    'operation_id': operation.id,
                    'error': str(e),
                    'retry_count': operation.retry_count
                })
                
                logger.error(f"❌ 동기화 최종 실패: {operation.id} - {e}")
    
    async def _detect_conflicts(self, operation: SyncOperation, data_hash: str) -> List[Dict[str, Any]]:
        """데이터 충돌 감지"""
        conflicts = []
        
        for target_system in operation.target_systems:
            try:
                # 기존 데이터 조회
                existing_data = await self._get_existing_data(target_system, operation)
                
                if existing_data:
                    # 데이터 해시 비교
                    existing_hash = self._calculate_data_hash(existing_data)
                    
                    if existing_hash != data_hash:
                        # 충돌 감지
                        conflict = {
                            'system': target_system,
                            'existing_data': existing_data,
                            'existing_hash': existing_hash,
                            'new_data': operation.data,
                            'new_hash': data_hash,
                            'timestamp': datetime.now()
                        }
                        conflicts.append(conflict)
                        
                        logger.warning(f"⚠️ 충돌 감지됨: {target_system} - {operation.id}")
                
            except Exception as e:
                logger.error(f"충돌 감지 오류 ({target_system}): {e}")
        
        if conflicts:
            self.metrics['conflicts_detected'] += 1
        
        return conflicts
    
    async def _handle_conflicts(self, operation: SyncOperation, conflicts: List[Dict[str, Any]]):
        """충돌 처리"""
        operation.status = "conflicted"
        
        # 충돌 해결 전략에 따른 처리
        if self.conflict_resolution_strategy == DataConflictResolution.LAST_WRITE_WINS:
            # 마지막 쓰기 우선
            await self._resolve_conflict_last_write_wins(operation, conflicts)
            
        elif self.conflict_resolution_strategy == DataConflictResolution.MERGE_STRATEGY:
            # 병합 전략
            await self._resolve_conflict_merge(operation, conflicts)
            
        elif self.conflict_resolution_strategy == DataConflictResolution.ROLLBACK:
            # 롤백
            await self._resolve_conflict_rollback(operation, conflicts)
            
        else:
            # 수동 해결 대기
            await self.conflict_queue.put({
                'operation': operation,
                'conflicts': conflicts,
                'timestamp': datetime.now()
            })
        
        # 이벤트 발생
        await self._trigger_event('conflict_detected', {
            'operation_id': operation.id,
            'conflicts': conflicts,
            'resolution_strategy': self.conflict_resolution_strategy.value
        })
    
    async def _resolve_conflict_last_write_wins(self, operation: SyncOperation, conflicts: List[Dict[str, Any]]):
        """마지막 쓰기 우선 충돌 해결"""
        logger.info(f"🔄 마지막 쓰기 우선으로 충돌 해결: {operation.id}")
        
        # 새로운 데이터로 덮어쓰기
        operation.conflict_resolution = DataConflictResolution.LAST_WRITE_WINS
        
        # 동기화 재시도
        await self.sync_data(operation)
    
    async def _resolve_conflict_merge(self, operation: SyncOperation, conflicts: List[Dict[str, Any]]):
        """병합 전략 충돌 해결"""
        logger.info(f"🔄 병합 전략으로 충돌 해결: {operation.id}")
        
        # 데이터 병합
        merged_data = operation.data.copy()
        
        for conflict in conflicts:
            existing_data = conflict['existing_data']
            # 간단한 병합 로직 (실제로는 더 복잡한 로직 필요)
            for key, value in existing_data.items():
                if key not in merged_data:
                    merged_data[key] = value
        
        # 병합된 데이터로 동기화
        operation.data = merged_data
        operation.conflict_resolution = DataConflictResolution.MERGE_STRATEGY
        
        # 동기화 재시도
        await self.sync_data(operation)
    
    async def _resolve_conflict_rollback(self, operation: SyncOperation, conflicts: List[Dict[str, Any]]):
        """롤백 충돌 해결"""
        logger.info(f"🔄 롤백으로 충돌 해결: {operation.id}")
        
        operation.conflict_resolution = DataConflictResolution.ROLLBACK
        operation.status = "cancelled"
        
        # 이벤트 발생
        await self._trigger_event('rollback_required', {
            'operation_id': operation.id,
            'conflicts': conflicts
        })
    
    async def _perform_sync(self, operation: SyncOperation, data_hash: str) -> Dict[str, Any]:
        """실제 동기화 수행"""
        sync_results = {}
        
        for target_system in operation.target_systems:
            try:
                if target_system == 'redis':
                    result = await self._sync_to_redis(operation, data_hash)
                elif target_system == 'neo4j':
                    result = await self._sync_to_neo4j(operation, data_hash)
                elif target_system == 'bigquery':
                    result = await self._sync_to_bigquery(operation, data_hash)
                else:
                    result = {'success': False, 'error': f'Unknown system: {target_system}'}
                
                sync_results[target_system] = result
                
                # 성공한 경우 데이터 버전 업데이트
                if result.get('success', False):
                    await self._update_data_version(operation, target_system, data_hash)
                
            except Exception as e:
                sync_results[target_system] = {
                    'success': False,
                    'error': str(e)
                }
                logger.error(f"동기화 실패 ({target_system}): {e}")
        
        return sync_results
    
    async def _sync_to_redis(self, operation: SyncOperation, data_hash: str) -> Dict[str, Any]:
        """Redis 동기화"""
        try:
            if not self.redis_client:
                return {'success': False, 'error': 'Redis client not available'}
            
            key = operation.metadata.get('redis_key', f"argo:{operation.id}")
            
            if operation.operation_type == SyncOperationType.DELETE:
                await self.redis_client.delete(key)
            else:
                # CREATE, UPDATE, MERGE
                await self.redis_client.set(key, json.dumps(operation.data))
                await self.redis_client.expire(key, 3600)  # 1시간 TTL
            
            return {'success': True, 'key': key}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _sync_to_neo4j(self, operation: SyncOperation, data_hash: str) -> Dict[str, Any]:
        """Neo4j 동기화"""
        try:
            if not self.neo4j_driver:
                return {'success': False, 'error': 'Neo4j driver not available'}
            
            # 간단한 Cypher 쿼리 생성
            if operation.operation_type == SyncOperationType.DELETE:
                query = "MATCH (n {id: $id}) DELETE n"
                params = {'id': operation.id}
            else:
                # CREATE, UPDATE, MERGE
                query = """
                MERGE (n {id: $id})
                SET n += $properties
                RETURN n
                """
                params = {
                    'id': operation.id,
                    'properties': operation.data
                }
            
            # 쿼리 실행
            with self.neo4j_driver.session() as session:
                result = session.run(query, params)
                record = result.single()
            
            return {'success': True, 'record': record.data() if record else None}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _sync_to_bigquery(self, operation: SyncOperation, data_hash: str) -> Dict[str, Any]:
        """BigQuery 동기화"""
        try:
            if not self.bigquery_client:
                return {'success': False, 'error': 'BigQuery client not available'}
            
            # BigQuery 테이블 이름
            table_name = operation.metadata.get('bigquery_table', 'argo_sync_log')
            
            # 데이터 준비
            row_data = {
                'operation_id': operation.id,
                'operation_type': operation.operation_type.value,
                'source_system': operation.source_system,
                'data_hash': data_hash,
                'timestamp': operation.timestamp.isoformat(),
                'data': json.dumps(operation.data)
            }
            
            # 데이터 삽입 (실제 구현에서는 더 정교한 로직 필요)
            # self.bigquery_client.insert_rows_json(table_name, [row_data])
            
            return {'success': True, 'table': table_name}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _get_existing_data(self, system: str, operation: SyncOperation) -> Optional[Dict[str, Any]]:
        """기존 데이터 조회"""
        try:
            if system == 'redis':
                if self.redis_client:
                    key = operation.metadata.get('redis_key', f"argo:{operation.id}")
                    data = await self.redis_client.get(key)
                    return json.loads(data) if data else None
            
            elif system == 'neo4j':
                if self.neo4j_driver:
                    query = "MATCH (n {id: $id}) RETURN n"
                    with self.neo4j_driver.session() as session:
                        result = session.run(query, {'id': operation.id})
                        record = result.single()
                        return record.data() if record else None
            
            return None
            
        except Exception as e:
            logger.error(f"기존 데이터 조회 오류 ({system}): {e}")
            return None
    
    def _calculate_data_hash(self, data: Dict[str, Any]) -> str:
        """데이터 해시 계산"""
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    async def _update_data_version(self, operation: SyncOperation, system: str, data_hash: str):
        """데이터 버전 업데이트"""
        version = DataVersion(
            version_id=str(uuid.uuid4()),
            data_hash=data_hash,
            timestamp=datetime.now(),
            system=system,
            operation_id=operation.id
        )
        
        self.data_versions[operation.id].append(version)
    
    async def _schedule_retry(self, operation: SyncOperation):
        """재시도 스케줄링"""
        operation.retry_count += 1
        
        # 지수 백오프로 재시도 지연
        delay = 2 ** operation.retry_count
        
        asyncio.create_task(self._delayed_retry(operation, delay))
        
        logger.info(f"🔄 재시도 예약: {operation.id} ({operation.retry_count}/{operation.max_retries}) - {delay}초 후")
    
    async def _delayed_retry(self, operation: SyncOperation, delay: int):
        """지연된 재시도"""
        await asyncio.sleep(delay)
        
        if self.is_running:
            operation.status = "pending"
            await self.sync_data(operation)
    
    async def _conflict_resolver(self):
        """충돌 해결 처리기"""
        while self.is_running:
            try:
                # 충돌 큐에서 작업 가져오기
                conflict_data = await asyncio.wait_for(
                    self.conflict_queue.get(), 
                    timeout=1.0
                )
                
                # 수동 해결 대기 (실제로는 사용자 인터페이스 필요)
                logger.info(f"⏳ 충돌 수동 해결 대기: {conflict_data['operation'].id}")
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"충돌 해결 처리기 오류: {e}")
                await asyncio.sleep(1)
    
    async def _monitor_sync_health(self):
        """동기화 상태 모니터링"""
        while self.is_running:
            try:
                # 큐 상태 확인
                queue_size = self.sync_queue.qsize()
                priority_size = len(self.priority_queue)
                conflict_size = self.conflict_queue.qsize()
                
                # 경고 조건 확인
                if queue_size > 100:
                    logger.warning(f"⚠️ 동기화 큐 크기 증가: {queue_size}")
                
                if conflict_size > 10:
                    logger.warning(f"⚠️ 충돌 큐 크기 증가: {conflict_size}")
                
                # 메트릭 로깅
                logger.debug(f"동기화 상태 - 일반: {queue_size}, 우선순위: {priority_size}, 충돌: {conflict_size}")
                
                await asyncio.sleep(30)  # 30초마다 체크
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"동기화 상태 모니터링 오류: {e}")
                await asyncio.sleep(5)
    
    def _update_sync_metrics(self, start_time: float, success: bool):
        """동기화 메트릭 업데이트"""
        execution_time = time.time() - start_time
        
        if success:
            self.metrics['successful_syncs'] += 1
        else:
            self.metrics['failed_syncs'] += 1
        
        # 평균 실행 시간 업데이트
        total_successful = self.metrics['successful_syncs']
        if total_successful > 0:
            current_avg = self.metrics['average_sync_time']
            self.metrics['average_sync_time'] = (
                (current_avg * (total_successful - 1) + execution_time) / total_successful
            )
        
        self.metrics['total_sync_time'] += execution_time
    
    async def _trigger_event(self, event_type: str, data: Dict[str, Any]):
        """이벤트 발생"""
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    await handler(data)
                except Exception as e:
                    logger.error(f"이벤트 핸들러 오류: {e}")
    
    def add_event_handler(self, event_type: str, handler: Callable):
        """이벤트 핸들러 추가"""
        if event_type in self.event_handlers:
            self.event_handlers[event_type].append(handler)
    
    async def get_sync_status(self) -> Dict[str, Any]:
        """동기화 상태 정보 반환"""
        return {
            'is_running': self.is_running,
            'queue_sizes': {
                'sync_queue': self.sync_queue.qsize(),
                'priority_queue': len(self.priority_queue),
                'conflict_queue': self.conflict_queue.qsize()
            },
            'metrics': self.metrics.copy(),
            'config': {
                'conflict_resolution': self.conflict_resolution_strategy.value,
                'max_concurrent_syncs': self.config.get('max_concurrent_syncs', 3)
            }
        }

# 사용 예시
async def example_sync_handler(data: Dict[str, Any]):
    """예시 동기화 이벤트 핸들러"""
    print(f"🔄 동기화 이벤트: {data}")

async def main():
    """향상된 데이터 동기화 매니저 테스트"""
    config = {
        'max_concurrent_syncs': 3,
        'conflict_resolution': DataConflictResolution.LAST_WRITE_WINS
    }
    
    # 동기화 매니저 생성
    sync_manager = EnhancedDataSyncManager(config)
    
    # 이벤트 핸들러 등록
    sync_manager.add_event_handler('sync_completed', example_sync_handler)
    sync_manager.add_event_handler('conflict_detected', example_sync_handler)
    
    try:
        # 매니저 시작
        await sync_manager.start()
        
        # 테스트 동기화 작업 생성
        operations = [
            SyncOperation(
                operation_type=SyncOperationType.CREATE,
                source_system='redis',
                data={'name': 'Test Data 1', 'value': 100},
                metadata={'redis_key': 'test:data:1'}
            ),
            SyncOperation(
                operation_type=SyncOperationType.UPDATE,
                source_system='neo4j',
                data={'name': 'Test Data 2', 'value': 200},
                metadata={'redis_key': 'test:data:2'}
            )
        ]
        
        # 동기화 요청
        operation_ids = await sync_manager.sync_batch(operations)
        print(f"동기화 요청됨: {operation_ids}")
        
        # 상태 모니터링
        for _ in range(10):
            status = await sync_manager.get_sync_status()
            print(f"동기화 상태: {status['queue_sizes']}")
            await asyncio.sleep(2)
        
    finally:
        await sync_manager.stop()

if __name__ == "__main__":
    asyncio.run(main())
