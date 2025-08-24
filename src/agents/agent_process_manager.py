#!/usr/bin/env python3
"""
Agent Process Manager for ARGO System
에이전트 실행 환경 안정화를 위한 프로세스 모니터링 및 자동 재시작 시스템
"""

import asyncio
import os
import psutil
import signal
import time
import logging
import json
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import redis
from pathlib import Path

logger = logging.getLogger(__name__)

class AgentStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    RESTARTING = "restarting"
    CRASHED = "crashed"
    STOPPING = "stopping"

@dataclass
class AgentProcess:
    name: str
    pid: Optional[int] = None
    status: AgentStatus = AgentStatus.STOPPED
    start_time: Optional[datetime] = None
    restart_count: int = 0
    max_restarts: int = 5
    memory_limit_mb: int = 512
    cpu_limit_percent: float = 80.0
    last_heartbeat: Optional[datetime] = None
    health_score: float = 100.0
    crash_reason: Optional[str] = None
    auto_restart: bool = True
    dependencies: List[str] = field(default_factory=list)

class AgentProcessManager:
    """
    ARGO 에이전트들의 프로세스 생명주기를 관리하는 매니저
    실제 데이터로 인한 시스템 파괴를 방지하기 위한 견고한 프로세스 관리
    """
    
    def __init__(self, redis_config: Dict = None):
        self.redis_config = redis_config or {
            'host': 'localhost',
            'port': 6379,
            'db': 0
        }
        
        # Redis 연결 (MockRedis 자동 전환 포함)
        self.redis_client = self._get_redis_client()
        
        # 에이전트 프로세스 관리
        self.agents: Dict[str, AgentProcess] = {}
        self.process_handles: Dict[str, asyncio.Task] = {}
        
        # 모니터링 설정
        self.monitoring_interval = 5  # 초
        self.heartbeat_timeout = 30   # 초
        self.memory_check_interval = 10  # 초
        self.cpu_check_interval = 5   # 초
        
        # 이벤트 핸들러
        self.event_handlers: Dict[str, List[Callable]] = {
            'agent_started': [],
            'agent_stopped': [],
            'agent_crashed': [],
            'agent_restarting': [],
            'memory_warning': [],
            'cpu_warning': [],
            'health_degraded': []
        }
        
        # 모니터링 태스크
        self.monitoring_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # 프로세스 시작 스크립트 매핑
        # 현재 작업 디렉토리 기준으로 절대 경로 설정
        import os
        base_dir = os.getcwd()
        self.agent_scripts = {
            'master_orchestrator': os.path.join(base_dir, 'src', 'agents', 'orchestrator', 'strategic_orchestrator.py'),
            'user_context_agent': os.path.join(base_dir, 'src', 'agents', 'specialist_agents.py'),
            'creative_agent': os.path.join(base_dir, 'src', 'agents', 'specialist_agents.py'),
            'technical_agent': os.path.join(base_dir, 'src', 'agents', 'specialist_agents.py'),
            'test_agent': os.path.join(base_dir, 'test_simple_agent.py')  # 간단한 테스트용 에이전트
        }
        
        logger.info("AgentProcessManager initialized")
    
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
    
    def register_agent(self, name: str, **kwargs) -> AgentProcess:
        """새로운 에이전트 등록"""
        if name in self.agents:
            logger.warning(f"에이전트가 이미 등록됨: {name}")
            return self.agents[name]
        
        agent = AgentProcess(name=name, **kwargs)
        self.agents[name] = agent
        
        # Redis에 에이전트 정보 저장
        self._save_agent_to_redis(agent)
        
        logger.info(f"에이전트 등록됨: {name}")
        return agent
    
    def _save_agent_to_redis(self, agent: AgentProcess):
        """에이전트 정보를 Redis에 저장"""
        try:
            agent_key = f"agent_process:{agent.name}"
            agent_data = {
                'name': agent.name,
                'status': agent.status.value,
                'pid': agent.pid or 0,
                'start_time': agent.start_time.isoformat() if agent.start_time else None,
                'restart_count': agent.restart_count,
                'max_restarts': agent.max_restarts,
                'memory_limit_mb': agent.memory_limit_mb,
                'cpu_limit_percent': agent.cpu_limit_percent,
                'last_heartbeat': agent.last_heartbeat.isoformat() if agent.last_heartbeat else None,
                'health_score': agent.health_score,
                'auto_restart': agent.auto_restart
            }
            
            # None 값 제거
            agent_data = {k: v for k, v in agent_data.items() if v is not None}
            
            self.redis_client.hset(agent_key, mapping=agent_data)
            self.redis_client.expire(agent_key, 3600)  # 1시간 TTL
            
        except Exception as e:
            logger.error(f"Redis 저장 실패: {e}")
    
    async def start_agent(self, name: str) -> bool:
        """에이전트 시작"""
        if name not in self.agents:
            logger.error(f"등록되지 않은 에이전트: {name}")
            return False
        
        agent = self.agents[name]
        
        if agent.status in [AgentStatus.STARTING, AgentStatus.RUNNING]:
            logger.warning(f"에이전트가 이미 실행 중: {name}")
            return True
        
        try:
            logger.info(f"에이전트 시작 중: {name}")
            agent.status = AgentStatus.STARTING
            
            # 의존성 체크
            if not await self._check_dependencies(agent):
                logger.error(f"의존성 체크 실패: {name}")
                agent.status = AgentStatus.CRASHED
                return False
            
            # 프로세스 시작
            if name in self.agent_scripts:
                script_path = self.agent_scripts[name]
                if await self._start_python_script(agent, script_path):
                    agent.status = AgentStatus.RUNNING
                    agent.start_time = datetime.utcnow()
                    agent.last_heartbeat = datetime.utcnow()
                    agent.health_score = 100.0
                    agent.crash_reason = None
                    
                    # Redis 업데이트
                    self._save_agent_to_redis(agent)
                    
                    # 모니터링 태스크 시작
                    if not self.monitoring_task or self.monitoring_task.done():
                        self.monitoring_task = asyncio.create_task(self._monitor_agents())
                    
                    self._emit_event('agent_started', {'agent_name': name})
                    logger.info(f"✅ 에이전트 시작 성공: {name}")
                    return True
                else:
                    agent.status = AgentStatus.CRASHED
                    return False
            else:
                logger.error(f"에이전트 스크립트를 찾을 수 없음: {name}")
                agent.status = AgentStatus.CRASHED
                return False
                
        except Exception as e:
            logger.error(f"에이전트 시작 실패: {name} - {e}")
            agent.status = AgentStatus.CRASHED
            agent.crash_reason = str(e)
            return False
    
    async def _check_dependencies(self, agent: AgentProcess) -> bool:
        """에이전트 의존성 체크"""
        if not agent.dependencies:
            return True
        
        for dep_name in agent.dependencies:
            if dep_name in self.agents:
                dep_agent = self.agents[dep_name]
                if dep_agent.status != AgentStatus.RUNNING:
                    logger.warning(f"의존성 에이전트가 실행되지 않음: {dep_name} -> {agent.name}")
                    return False
            else:
                logger.warning(f"의존성 에이전트가 등록되지 않음: {dep_name}")
                return False
        
        return True
    
    async def _start_python_script(self, agent: AgentProcess, script_path: str) -> bool:
        """Python 스크립트 실행"""
        try:
            # 스크립트 파일 존재 확인
            if not os.path.exists(script_path):
                logger.error(f"스크립트 파일을 찾을 수 없음: {script_path}")
                return False
            
            # Python 프로세스 시작
            process = await asyncio.create_subprocess_exec(
                'python', script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ.copy()
            )
            
            # 프로세스 핸들 저장
            self.process_handles[agent.name] = asyncio.create_task(
                self._monitor_process_output(agent.name, process)
            )
            
            # PID 저장
            agent.pid = process.pid
            
            # 프로세스 시작 대기
            await asyncio.sleep(2)
            
            # 프로세스 상태 확인
            if process.returncode is None:  # 아직 실행 중
                logger.info(f"Python 프로세스 시작됨: {agent.name} (PID: {agent.pid})")
                return True
            else:
                logger.error(f"Python 프로세스 시작 실패: {agent.name}")
                return False
                
        except Exception as e:
            logger.error(f"Python 스크립트 시작 실패: {e}")
            return False
    
    async def _monitor_process_output(self, agent_name: str, process: asyncio.subprocess.Process):
        """프로세스 출력 모니터링"""
        try:
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"에이전트 정상 종료: {agent_name}")
                await self._handle_agent_exit(agent_name, "normal_exit")
            else:
                logger.error(f"에이전트 비정상 종료: {agent_name} (코드: {process.returncode})")
                await self._handle_agent_exit(agent_name, f"exit_code_{process.returncode}")
                
        except Exception as e:
            logger.error(f"프로세스 모니터링 실패: {agent_name} - {e}")
            await self._handle_agent_exit(agent_name, f"monitoring_error: {e}")
    
    async def _handle_agent_exit(self, agent_name: str, reason: str):
        """에이전트 종료 처리"""
        if agent_name not in self.agents:
            return
        
        agent = self.agents[agent_name]
        agent.status = AgentStatus.CRASHED
        agent.crash_reason = reason
        agent.pid = None
        
        # 프로세스 핸들 정리
        if agent_name in self.process_handles:
            self.process_handles[agent_name].cancel()
            del self.process_handles[agent_name]
        
        # Redis 업데이트
        self._save_agent_to_redis(agent)
        
        # 자동 재시작 체크
        if agent.auto_restart and agent.restart_count < agent.max_restarts:
            logger.info(f"에이전트 자동 재시작 예정: {agent_name}")
            await self._schedule_restart(agent_name)
        else:
            logger.error(f"에이전트 재시작 한도 초과: {agent_name}")
            self._emit_event('agent_crashed', {
                'agent_name': agent_name,
                'reason': reason,
                'restart_count': agent.restart_count
            })
    
    async def _schedule_restart(self, agent_name: str):
        """에이전트 재시작 스케줄링"""
        if agent_name not in self.agents:
            return
        
        agent = self.agents[agent_name]
        agent.status = AgentStatus.RESTARTING
        agent.restart_count += 1
        
        # 지수 백오프로 재시작 지연
        delay = min(2 ** agent.restart_count, 60)  # 최대 60초
        
        logger.info(f"에이전트 재시작 스케줄: {agent_name} ({delay}초 후)")
        
        # 재시작 태스크 생성
        restart_task = asyncio.create_task(self._delayed_restart(agent_name, delay))
        self.process_handles[f"{agent_name}_restart"] = restart_task
    
    async def _delayed_restart(self, agent_name: str, delay: int):
        """지연된 재시작 실행"""
        try:
            await asyncio.sleep(delay)
            
            if agent_name in self.agents:
                agent = self.agents[agent_name]
                if agent.status == AgentStatus.RESTARTING:
                    logger.info(f"에이전트 재시작 실행: {agent_name}")
                    await self.start_agent(agent_name)
                    
        except asyncio.CancelledError:
            logger.info(f"재시작 태스크 취소됨: {agent_name}")
        except Exception as e:
            logger.error(f"재시작 실패: {agent_name} - {e}")
    
    async def stop_agent(self, name: str, force: bool = False) -> bool:
        """에이전트 중지"""
        if name not in self.agents:
            logger.error(f"등록되지 않은 에이전트: {name}")
            return False
        
        agent = self.agents[name]
        
        if agent.status == AgentStatus.STOPPED:
            logger.info(f"에이전트가 이미 중지됨: {name}")
            return True
        
        try:
            logger.info(f"에이전트 중지 중: {name}")
            agent.status = AgentStatus.STOPPING
            
            if agent.pid and force:
                # 강제 종료
                try:
                    os.kill(agent.pid, signal.SIGKILL)
                    logger.info(f"에이전트 강제 종료: {name} (PID: {agent.pid})")
                except ProcessLookupError:
                    logger.warning(f"프로세스가 이미 종료됨: {name}")
                except Exception as e:
                    logger.error(f"강제 종료 실패: {name} - {e}")
            
            # 프로세스 핸들 정리
            if name in self.process_handles:
                self.process_handles[name].cancel()
                del self.process_handles[name]
            
            # 상태 업데이트
            agent.status = AgentStatus.STOPPED
            agent.pid = None
            agent.last_heartbeat = None
            agent.health_score = 0.0
            
            # Redis 업데이트
            self._save_agent_to_redis(agent)
            
            self._emit_event('agent_stopped', {'agent_name': name})
            logger.info(f"✅ 에이전트 중지 완료: {name}")
            return True
            
        except Exception as e:
            logger.error(f"에이전트 중지 실패: {name} - {e}")
            return False
    
    async def restart_agent(self, name: str) -> bool:
        """에이전트 재시작"""
        if name not in self.agents:
            logger.error(f"등록되지 않은 에이전트: {name}")
            return False
        
        logger.info(f"에이전트 재시작 요청: {name}")
        
        # 먼저 중지
        if await self.stop_agent(name, force=True):
            # 잠시 대기 후 시작
            await asyncio.sleep(2)
            return await self.start_agent(name)
        
        return False
    
    async def _monitor_agents(self):
        """에이전트 모니터링 메인 루프"""
        logger.info("에이전트 모니터링 시작")
        
        while self.is_running:
            try:
                for agent_name, agent in self.agents.items():
                    if agent.status == AgentStatus.RUNNING:
                        await self._check_agent_health(agent)
                
                # 메모리 및 CPU 체크
                await self._check_system_resources()
                
                # 만료된 프로세스 정리
                await self._cleanup_expired_processes()
                
                await asyncio.sleep(self.monitoring_interval)
                
            except asyncio.CancelledError:
                logger.info("모니터링 태스크 취소됨")
                break
            except Exception as e:
                logger.error(f"모니터링 오류: {e}")
                await asyncio.sleep(self.monitoring_interval)
        
        logger.info("에이전트 모니터링 종료")
    
    async def _check_agent_health(self, agent: AgentProcess):
        """에이전트 상태 체크"""
        try:
            if not agent.pid:
                return
            
            # 프로세스 존재 확인
            try:
                process = psutil.Process(agent.pid)
                if not process.is_running():
                    logger.warning(f"프로세스가 실행되지 않음: {agent.name}")
                    await self._handle_agent_exit(agent.name, "process_not_running")
                    return
                
                # 메모리 사용량 체크
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                
                if memory_mb > agent.memory_limit_mb:
                    logger.warning(f"메모리 사용량 초과: {agent.name} ({memory_mb:.1f}MB > {agent.memory_limit_mb}MB)")
                    self._emit_event('memory_warning', {
                        'agent_name': agent.name,
                        'current_mb': memory_mb,
                        'limit_mb': agent.memory_limit_mb
                    })
                    
                    # 메모리 초과 시 자동 재시작
                    if agent.auto_restart:
                        logger.info(f"메모리 초과로 인한 자동 재시작: {agent.name}")
                        await self.restart_agent(agent.name)
                        return
                
                # CPU 사용량 체크
                cpu_percent = process.cpu_percent(interval=1)
                if cpu_percent > agent.cpu_limit_percent:
                    logger.warning(f"CPU 사용량 초과: {agent.name} ({cpu_percent:.1f}% > {agent.cpu_limit_percent}%)")
                    self._emit_event('cpu_warning', {
                        'agent_name': agent.name,
                        'current_percent': cpu_percent,
                        'limit_percent': agent.cpu_limit_percent
                    })
                
                # 헬스 스코어 업데이트
                agent.health_score = max(0, agent.health_score - 1)
                if agent.health_score < 50:
                    self._emit_event('health_degraded', {
                        'agent_name': agent.name,
                        'health_score': agent.health_score
                    })
                
                # Redis 업데이트
                self._save_agent_to_redis(agent)
                
            except psutil.NoSuchProcess:
                logger.warning(f"프로세스가 존재하지 않음: {agent.name}")
                await self._handle_agent_exit(agent.name, "process_not_found")
                
        except Exception as e:
            logger.error(f"에이전트 상태 체크 실패: {agent.name} - {e}")
    
    async def _check_system_resources(self):
        """시스템 리소스 체크"""
        try:
            # 전체 시스템 메모리
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                logger.warning(f"시스템 메모리 부족: {memory.percent:.1f}%")
                
                # 메모리 사용량이 높은 에이전트들 찾기
                for agent_name, agent in self.agents.items():
                    if agent.status == AgentStatus.RUNNING and agent.pid:
                        try:
                            process = psutil.Process(agent.pid)
                            memory_info = process.memory_info()
                            memory_mb = memory_info.rss / 1024 / 1024
                            
                            if memory_mb > 100:  # 100MB 이상 사용하는 에이전트
                                logger.warning(f"높은 메모리 사용 에이전트: {agent_name} ({memory_mb:.1f}MB)")
                        except:
                            pass
            
            # 전체 시스템 CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                logger.warning(f"시스템 CPU 부족: {cpu_percent:.1f}%")
                
        except Exception as e:
            logger.error(f"시스템 리소스 체크 실패: {e}")
    
    async def _cleanup_expired_processes(self):
        """만료된 프로세스 정리"""
        try:
            current_time = datetime.utcnow()
            
            for agent_name, agent in self.agents.items():
                if (agent.status == AgentStatus.RUNNING and 
                    agent.start_time and 
                    current_time - agent.start_time > timedelta(hours=24)):
                    
                    logger.info(f"24시간 실행된 에이전트 재시작: {agent_name}")
                    await self.restart_agent(agent_name)
                    
        except Exception as e:
            logger.error(f"만료된 프로세스 정리 실패: {e}")
    
    def get_agent_status(self, name: str) -> Optional[Dict]:
        """에이전트 상태 조회"""
        if name not in self.agents:
            return None
        
        agent = self.agents[name]
        return {
            'name': agent.name,
            'status': agent.status.value,
            'pid': agent.pid,
            'start_time': agent.start_time.isoformat() if agent.start_time else None,
            'restart_count': agent.restart_count,
            'health_score': agent.health_score,
            'memory_usage_mb': self._get_agent_memory_usage(agent),
            'cpu_usage_percent': self._get_agent_cpu_usage(agent),
            'crash_reason': agent.crash_reason
        }
    
    def _get_agent_memory_usage(self, agent: AgentProcess) -> Optional[float]:
        """에이전트 메모리 사용량 조회"""
        if not agent.pid:
            return None
        
        try:
            process = psutil.Process(agent.pid)
            memory_info = process.memory_info()
            return memory_info.rss / 1024 / 1024
        except:
            return None
    
    def _get_agent_cpu_usage(self, agent: AgentProcess) -> Optional[float]:
        """에이전트 CPU 사용량 조회"""
        if not agent.pid:
            return None
        
        try:
            process = psutil.Process(agent.pid)
            return process.cpu_percent(interval=1)
        except:
            return None
    
    def get_all_agents_status(self) -> Dict[str, Dict]:
        """모든 에이전트 상태 조회"""
        return {
            name: self.get_agent_status(name)
            for name in self.agents.keys()
        }
    
    async def start_all_agents(self) -> Dict[str, bool]:
        """모든 에이전트 시작"""
        results = {}
        
        for agent_name in self.agents.keys():
            results[agent_name] = await self.start_agent(agent_name)
            await asyncio.sleep(1)  # 순차적으로 시작
        
        return results
    
    async def stop_all_agents(self) -> Dict[str, bool]:
        """모든 에이전트 중지"""
        results = {}
        
        for agent_name in self.agents.keys():
            results[agent_name] = await self.stop_agent(agent_name, force=True)
        
        return results
    
    async def start(self):
        """프로세스 매니저 시작"""
        if self.is_running:
            logger.warning("프로세스 매니저가 이미 실행 중")
            return
        
        self.is_running = True
        
        # 기본 에이전트들 등록
        self._register_default_agents()
        
        # 모니터링 태스크 시작
        self.monitoring_task = asyncio.create_task(self._monitor_agents())
        
        logger.info("AgentProcessManager 시작됨")
    
    def _register_default_agents(self):
        """기본 에이전트들 등록"""
        # Master Orchestrator (의존성 없음)
        self.register_agent(
            'master_orchestrator',
            max_restarts=10,
            memory_limit_mb=1024,
            cpu_limit_percent=90.0,
            auto_restart=True
        )
        
        # User Context Agent (Master Orchestrator에 의존)
        self.register_agent(
            'user_context_agent',
            dependencies=['master_orchestrator'],
            max_restarts=5,
            memory_limit_mb=512,
            cpu_limit_percent=80.0,
            auto_restart=True
        )
        
        # Creative Agent (Master Orchestrator에 의존)
        self.register_agent(
            'creative_agent',
            dependencies=['master_orchestrator'],
            max_restarts=5,
            memory_limit_mb=512,
            cpu_limit_percent=80.0,
            auto_restart=True
        )
        
        # Technical Agent (Master Orchestrator에 의존)
        self.register_agent(
            'technical_agent',
            dependencies=['master_orchestrator'],
            max_restarts=5,
            memory_limit_mb=512,
            cpu_limit_percent=80.0,
            auto_restart=True
        )
        
        logger.info("기본 에이전트들 등록 완료")
    
    async def shutdown(self):
        """프로세스 매니저 종료"""
        if not self.is_running:
            return
        
        logger.info("AgentProcessManager 종료 중...")
        
        self.is_running = False
        
        # 모든 에이전트 중지
        await self.stop_all_agents()
        
        # 모니터링 태스크 취소
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        # 프로세스 핸들 정리
        for task in self.process_handles.values():
            if not task.done():
                task.cancel()
        
        logger.info("AgentProcessManager 종료 완료")

# 사용 예시
async def main():
    # 프로세스 매니저 초기화
    manager = AgentProcessManager()
    
    try:
        # 매니저 시작
        await manager.start()
        
        # 모든 에이전트 시작
        results = await manager.start_all_agents()
        print(f"에이전트 시작 결과: {results}")
        
        # 30초 동안 실행
        await asyncio.sleep(30)
        
        # 상태 조회
        status = manager.get_all_agents_status()
        print(f"에이전트 상태: {json.dumps(status, indent=2, default=str)}")
        
    finally:
        # 정상 종료
        await manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
