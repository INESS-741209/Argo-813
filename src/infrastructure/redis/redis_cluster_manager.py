"""
Redis 클러스터 관리 시스템
ARGO Phase 2: 고가용성 Redis 클러스터 및 비동기 처리 시스템
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import redis.asyncio as redis
from redis.asyncio.cluster import RedisCluster
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff

logger = logging.getLogger(__name__)

@dataclass
class RedisNode:
    """Redis 노드 정보"""
    host: str
    port: int
    role: str  # 'master', 'slave', 'sentinel'
    status: str  # 'online', 'offline', 'failover'
    last_seen: datetime
    memory_usage: int
    connected_clients: int

@dataclass
class ClusterHealth:
    """클러스터 상태 정보"""
    total_nodes: int
    online_nodes: int
    offline_nodes: int
    master_nodes: int
    slave_nodes: int
    total_memory: int
    total_clients: int
    health_score: float  # 0.0 ~ 1.0

class RedisClusterManager:
    """Redis 클러스터 관리 및 모니터링"""
    
    def __init__(self, cluster_config: Dict[str, Any]):
        self.cluster_config = cluster_config
        self.cluster: Optional[RedisCluster] = None
        self.health_monitor_task: Optional[asyncio.Task] = None
        self.auto_failover_enabled = cluster_config.get('auto_failover', True)
        self.health_check_interval = cluster_config.get('health_check_interval', 30)
        
        # 클러스터 상태
        self.cluster_health = ClusterHealth(0, 0, 0, 0, 0, 0, 0, 0.0)
        self.node_status: Dict[str, RedisNode] = {}
        
        # 이벤트 핸들러
        self.event_handlers: Dict[str, List[Callable]] = {
            'node_failover': [],
            'cluster_resharding': [],
            'memory_warning': [],
            'connection_lost': []
        }
        
        # 성능 메트릭
        self.performance_metrics = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'average_response_time': 0.0,
            'peak_memory_usage': 0
        }
        
        logger.info("Redis 클러스터 매니저 초기화됨")
    
    async def connect(self) -> bool:
        """클러스터에 연결"""
        try:
            startup_nodes = self.cluster_config['startup_nodes']
            
            # 재시도 정책 설정
            retry = Retry(ExponentialBackoff(), 3)
            
            self.cluster = RedisCluster(
                startup_nodes=startup_nodes,
                decode_responses=True,
                retry=retry,
                health_check_interval=30,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # 연결 테스트
            await self.cluster.ping()
            logger.info("✅ Redis 클러스터 연결 성공")
            
            # 헬스 모니터링 시작
            await self.start_health_monitoring()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Redis 클러스터 연결 실패: {e}")
            return False
    
    async def disconnect(self):
        """클러스터 연결 해제"""
        if self.cluster:
            await self.cluster.close()
            logger.info("Redis 클러스터 연결 해제됨")
        
        if self.health_monitor_task:
            self.health_monitor_task.cancel()
    
    async def start_health_monitoring(self):
        """헬스 모니터링 시작"""
        async def monitor_health():
            while True:
                try:
                    await self.check_cluster_health()
                    await asyncio.sleep(self.health_check_interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"헬스 모니터링 오류: {e}")
                    await asyncio.sleep(5)
        
        self.health_monitor_task = asyncio.create_task(monitor_health())
        logger.info("헬스 모니터링 시작됨")
    
    async def check_cluster_health(self):
        """클러스터 상태 점검"""
        try:
            if not self.cluster:
                return
            
            # 클러스터 정보 조회
            cluster_info = await self.cluster.cluster_info()
            cluster_nodes = await self.cluster.cluster_nodes()
            
            # 노드별 상태 수집
            total_nodes = 0
            online_nodes = 0
            offline_nodes = 0
            master_nodes = 0
            slave_nodes = 0
            total_memory = 0
            total_clients = 0
            
            for node_info in cluster_nodes:
                node_id = node_info.get('id', str(uuid.uuid4()))
                host = node_info.get('host', 'localhost')
                port = node_info.get('port', 6379)
                role = node_info.get('role', 'unknown')
                status = node_info.get('status', 'unknown')
                
                # 노드 상태 업데이트
                if node_id not in self.node_status:
                    self.node_status[node_id] = RedisNode(
                        host=host, port=port, role=role, status=status,
                        last_seen=datetime.now(), memory_usage=0, connected_clients=0
                    )
                
                node = self.node_status[node_id]
                node.status = status
                node.last_seen = datetime.now()
                
                if status == 'online':
                    online_nodes += 1
                    if role == 'master':
                        master_nodes += 1
                    elif role == 'slave':
                        slave_nodes += 1
                    
                    # 메모리 및 클라이언트 정보 수집
                    try:
                        info = await self.cluster.info(node_id)
                        node.memory_usage = int(info.get('used_memory', 0))
                        node.connected_clients = int(info.get('connected_clients', 0))
                        total_memory += node.memory_usage
                        total_clients += node.connected_clients
                    except:
                        pass
                else:
                    offline_nodes += 1
                
                total_nodes += 1
            
            # 클러스터 헬스 점수 계산
            health_score = 0.0
            if total_nodes > 0:
                online_ratio = online_nodes / total_nodes
                master_slave_ratio = min(master_nodes, slave_nodes) / max(master_nodes, 1)
                health_score = (online_ratio * 0.6) + (master_slave_ratio * 0.4)
            
            # 헬스 상태 업데이트
            self.cluster_health = ClusterHealth(
                total_nodes=total_nodes,
                online_nodes=online_nodes,
                offline_nodes=offline_nodes,
                master_nodes=master_nodes,
                slave_nodes=slave_nodes,
                total_memory=total_memory,
                total_clients=total_clients,
                health_score=health_score
            )
            
            # 경고 조건 확인
            await self._check_warnings()
            
        except Exception as e:
            logger.error(f"클러스터 헬스 점검 실패: {e}")
    
    async def _check_warnings(self):
        """경고 조건 확인 및 이벤트 발생"""
        health = self.cluster_health
        
        # 메모리 사용량 경고
        if health.total_memory > 0:
            memory_usage_ratio = health.total_memory / (1024 * 1024 * 1024)  # GB
            if memory_usage_ratio > 0.8:  # 80% 이상
                await self._trigger_event('memory_warning', {
                    'usage_ratio': memory_usage_ratio,
                    'total_memory': health.total_memory
                })
        
        # 오프라인 노드 경고
        if health.offline_nodes > 0:
            await self._trigger_event('connection_lost', {
                'offline_nodes': health.offline_nodes,
                'total_nodes': health.total_nodes
            })
        
        # 헬스 점수 경고
        if health.health_score < 0.5:
            logger.warning(f"⚠️ 클러스터 헬스 점수 낮음: {health.health_score:.2f}")
    
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
    
    async def get_cluster_info(self) -> Dict[str, Any]:
        """클러스터 정보 반환"""
        return {
            'health': {
                'total_nodes': self.cluster_health.total_nodes,
                'online_nodes': self.cluster_health.online_nodes,
                'offline_nodes': self.cluster_health.offline_nodes,
                'master_nodes': self.cluster_health.master_nodes,
                'slave_nodes': self.cluster_health.slave_nodes,
                'health_score': self.cluster_health.health_score,
                'total_memory_mb': self.cluster_health.total_memory // (1024 * 1024),
                'total_clients': self.cluster_health.total_clients
            },
            'nodes': {
                node_id: {
                    'host': node.host,
                    'port': node.port,
                    'role': node.role,
                    'status': node.status,
                    'last_seen': node.last_seen.isoformat(),
                    'memory_mb': node.memory_usage // (1024 * 1024),
                    'clients': node.connected_clients
                }
                for node_id, node in self.node_status.items()
            },
            'performance': self.performance_metrics,
            'config': {
                'auto_failover': self.auto_failover_enabled,
                'health_check_interval': self.health_check_interval
            }
        }
    
    async def execute_command(self, command: str, *args, **kwargs) -> Any:
        """Redis 명령어 실행 (성능 메트릭 포함)"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            result = await self.cluster.execute_command(command, *args, **kwargs)
            
            # 성능 메트릭 업데이트
            execution_time = asyncio.get_event_loop().time() - start_time
            self.performance_metrics['total_operations'] += 1
            self.performance_metrics['successful_operations'] += 1
            
            # 평균 응답 시간 업데이트
            current_avg = self.performance_metrics['average_response_time']
            total_ops = self.performance_metrics['successful_operations']
            self.performance_metrics['average_response_time'] = (
                (current_avg * (total_ops - 1) + execution_time) / total_ops
            )
            
            return result
            
        except Exception as e:
            self.performance_metrics['total_operations'] += 1
            self.performance_metrics['failed_operations'] += 1
            logger.error(f"Redis 명령어 실행 실패: {command} - {e}")
            raise
    
    async def get_memory_usage(self) -> Dict[str, int]:
        """메모리 사용량 정보 반환"""
        try:
            memory_info = await self.cluster.memory_usage()
            return memory_info
        except Exception as e:
            logger.error(f"메모리 사용량 조회 실패: {e}")
            return {}
    
    async def flush_all(self) -> bool:
        """모든 데이터 삭제 (개발/테스트용)"""
        try:
            await self.cluster.flushall()
            logger.info("✅ 모든 Redis 데이터 삭제됨")
            return True
        except Exception as e:
            logger.error(f"❌ Redis 데이터 삭제 실패: {e}")
            return False

# 사용 예시
async def main():
    """Redis 클러스터 매니저 테스트"""
    cluster_config = {
        'startup_nodes': [
            {'host': 'localhost', 'port': 7000},
            {'host': 'localhost', 'port': 7001},
            {'host': 'localhost', 'port': 7002}
        ],
        'auto_failover': True,
        'health_check_interval': 30
    }
    
    manager = RedisClusterManager(cluster_config)
    
    try:
        # 클러스터 연결
        if await manager.connect():
            # 클러스터 정보 조회
            info = await manager.get_cluster_info()
            print("클러스터 정보:", json.dumps(info, indent=2, default=str))
            
            # 간단한 명령어 테스트
            await manager.execute_command('SET', 'test_key', 'test_value')
            value = await manager.execute_command('GET', 'test_key')
            print(f"테스트 값: {value}")
            
            # 10초 대기 (헬스 모니터링 관찰)
            await asyncio.sleep(10)
            
    finally:
        await manager.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
