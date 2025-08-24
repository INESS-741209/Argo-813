"""
비동기 메시지 큐 시스템
ARGO Phase 2: 고성능 비동기 처리 및 배치 처리 시스템
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
import heapq

logger = logging.getLogger(__name__)

class MessagePriority(Enum):
    """메시지 우선순위"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3

class MessageStatus(Enum):
    """메시지 상태"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    CANCELLED = "cancelled"

@dataclass
class Message:
    """메시지 객체"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    status: MessageStatus = MessageStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.scheduled_at is None:
            self.scheduled_at = self.created_at

@dataclass
class BatchConfig:
    """배치 처리 설정"""
    max_batch_size: int = 100
    max_wait_time: float = 5.0  # 초
    max_concurrent_batches: int = 5
    retry_delay: float = 1.0  # 초
    exponential_backoff: bool = True

class AsyncMessageQueue:
    """비동기 메시지 큐 시스템"""
    
    def __init__(self, batch_config: Optional[BatchConfig] = None):
        self.batch_config = batch_config or BatchConfig()
        
        # 메시지 큐 (우선순위별)
        self.message_queues: Dict[MessagePriority, deque] = {
            priority: deque() for priority in MessagePriority
        }
        
        # 스케줄된 메시지 (시간순 정렬)
        self.scheduled_messages: List[Message] = []
        
        # 배치 처리 큐
        self.batch_queue: asyncio.Queue = asyncio.Queue()
        self.active_batches: int = 0
        
        # 메시지 핸들러
        self.message_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.batch_handlers: Dict[str, Callable] = {}
        
        # 통계 및 모니터링
        self.stats = {
            'total_messages': 0,
            'processed_messages': 0,
            'failed_messages': 0,
            'total_processing_time': 0.0,
            'average_processing_time': 0.0,
            'queue_sizes': {priority.value: 0 for priority in MessagePriority}
        }
        
        # 실행 상태
        self.is_running = False
        self.processing_tasks: List[asyncio.Task] = []
        
        logger.info("비동기 메시지 큐 시스템 초기화됨")
    
    async def start(self):
        """메시지 큐 시스템 시작"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # 메시지 처리 태스크 시작
        self.processing_tasks.append(
            asyncio.create_task(self._message_processor())
        )
        
        # 스케줄된 메시지 처리 태스크 시작
        self.processing_tasks.append(
            asyncio.create_task(self._scheduled_message_processor())
        )
        
        # 배치 처리 태스크 시작
        for _ in range(self.batch_config.max_concurrent_batches):
            self.processing_tasks.append(
                asyncio.create_task(self._batch_processor())
            )
        
        logger.info("✅ 메시지 큐 시스템 시작됨")
    
    async def stop(self):
        """메시지 큐 시스템 중지"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # 모든 태스크 취소
        for task in self.processing_tasks:
            task.cancel()
        
        # 태스크 완료 대기
        await asyncio.gather(*self.processing_tasks, return_exceptions=True)
        self.processing_tasks.clear()
        
        logger.info("🛑 메시지 큐 시스템 중지됨")
    
    async def publish(self, topic: str, payload: Dict[str, Any], 
                     priority: MessagePriority = MessagePriority.NORMAL,
                     scheduled_at: Optional[datetime] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """메시지 발행"""
        message = Message(
            topic=topic,
            payload=payload,
            priority=priority,
            scheduled_at=scheduled_at,
            metadata=metadata or {}
        )
        
        if scheduled_at and scheduled_at > datetime.now():
            # 스케줄된 메시지
            heapq.heappush(self.scheduled_messages, (scheduled_at, message))
        else:
            # 즉시 처리할 메시지
            self.message_queues[priority].append(message)
            self.stats['queue_sizes'][priority.value] += 1
        
        self.stats['total_messages'] += 1
        
        logger.debug(f"📨 메시지 발행됨: {topic} (ID: {message.id}, 우선순위: {priority.name})")
        return message.id
    
    async def publish_batch(self, topic: str, messages: List[Dict[str, Any]],
                           priority: MessagePriority = MessagePriority.NORMAL) -> List[str]:
        """배치 메시지 발행"""
        message_ids = []
        
        for payload in messages:
            message_id = await self.publish(topic, payload, priority)
            message_ids.append(message_id)
        
        logger.info(f"📦 배치 메시지 발행됨: {topic} ({len(messages)}개)")
        return message_ids
    
    def subscribe(self, topic: str, handler: Callable, is_batch_handler: bool = False):
        """메시지 핸들러 구독"""
        if is_batch_handler:
            self.batch_handlers[topic] = handler
            logger.info(f"🔔 배치 핸들러 등록됨: {topic}")
        else:
            self.message_handlers[topic].append(handler)
            logger.info(f"🔔 메시지 핸들러 등록됨: {topic}")
    
    async def _message_processor(self):
        """메시지 처리 메인 루프"""
        while self.is_running:
            try:
                # 우선순위 순서로 메시지 처리
                for priority in reversed(list(MessagePriority)):
                    if self.message_queues[priority]:
                        message = self.message_queues[priority].popleft()
                        self.stats['queue_sizes'][priority.value] -= 1
                        
                        # 메시지 처리
                        await self._process_message(message)
                        
                        # 처리 완료 후 잠시 대기
                        await asyncio.sleep(0.001)
                
                # 처리할 메시지가 없으면 잠시 대기
                if not any(self.message_queues.values()):
                    await asyncio.sleep(0.1)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"메시지 처리 오류: {e}")
                await asyncio.sleep(1)
    
    async def _scheduled_message_processor(self):
        """스케줄된 메시지 처리"""
        while self.is_running:
            try:
                current_time = datetime.now()
                
                # 처리할 시간이 된 메시지들을 큐에 추가
                while (self.scheduled_messages and 
                       self.scheduled_messages[0][0] <= current_time):
                    _, message = heapq.heappop(self.scheduled_messages)
                    self.message_queues[message.priority].append(message)
                    self.stats['queue_sizes'][message.priority.value] += 1
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"스케줄된 메시지 처리 오류: {e}")
                await asyncio.sleep(1)
    
    async def _batch_processor(self):
        """배치 처리 메인 루프"""
        while self.is_running:
            try:
                # 배치 큐에서 메시지 수집
                batch_messages = []
                batch_start_time = time.time()
                
                # 최대 배치 크기 또는 최대 대기 시간까지 메시지 수집
                while (len(batch_messages) < self.batch_config.max_batch_size and
                       time.time() - batch_start_time < self.batch_config.max_wait_time):
                    try:
                        # 비동기로 메시지 가져오기
                        message = await asyncio.wait_for(
                            self.batch_queue.get(), 
                            timeout=0.1
                        )
                        batch_messages.append(message)
                    except asyncio.TimeoutError:
                        break
                
                if batch_messages:
                    # 배치 처리
                    await self._process_batch(batch_messages)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"배치 처리 오류: {e}")
                await asyncio.sleep(1)
    
    async def _process_message(self, message: Message):
        """개별 메시지 처리"""
        start_time = time.time()
        message.status = MessageStatus.PROCESSING
        
        try:
            # 메시지 핸들러 호출
            if message.topic in self.message_handlers:
                for handler in self.message_handlers[message.topic]:
                    try:
                        await handler(message)
                    except Exception as e:
                        logger.error(f"메시지 핸들러 오류: {e}")
                        message.error_message = str(e)
                        await self._handle_message_failure(message)
                        return
                
                # 성공 처리
                message.status = MessageStatus.COMPLETED
                message.processed_at = datetime.now()
                self.stats['processed_messages'] += 1
                
            else:
                # 핸들러가 없는 경우 배치 큐에 추가
                await self.batch_queue.put(message)
                return
            
        except Exception as e:
            logger.error(f"메시지 처리 실패: {e}")
            message.error_message = str(e)
            await self._handle_message_failure(message)
            return
        
        finally:
            # 처리 시간 통계 업데이트
            processing_time = time.time() - start_time
            self.stats['total_processing_time'] += processing_time
            self.stats['average_processing_time'] = (
                self.stats['total_processing_time'] / self.stats['processed_messages']
            )
    
    async def _process_batch(self, messages: List[Message]):
        """배치 메시지 처리"""
        if not messages:
            return
        
        topic = messages[0].topic
        if topic not in self.batch_handlers:
            logger.warning(f"배치 핸들러가 없음: {topic}")
            return
        
        batch_start_time = time.time()
        
        try:
            # 배치 핸들러 호출
            handler = self.batch_handlers[topic]
            await handler(messages)
            
            # 성공 처리
            for message in messages:
                message.status = MessageStatus.COMPLETED
                message.processed_at = datetime.now()
                self.stats['processed_messages'] += 1
            
            logger.info(f"✅ 배치 처리 완료: {topic} ({len(messages)}개)")
            
        except Exception as e:
            logger.error(f"배치 처리 실패: {topic} - {e}")
            
            # 실패한 메시지들 재시도 처리
            for message in messages:
                message.error_message = str(e)
                await self._handle_message_failure(message)
        
        finally:
            # 배치 처리 시간 통계
            batch_time = time.time() - batch_start_time
            logger.debug(f"배치 처리 시간: {topic} - {batch_time:.3f}초")
    
    async def _handle_message_failure(self, message: Message):
        """메시지 실패 처리"""
        if message.retry_count < message.max_retries:
            # 재시도
            message.retry_count += 1
            message.status = MessageStatus.RETRY
            
            # 지수 백오프로 재시도 지연
            if self.batch_config.exponential_backoff:
                delay = self.batch_config.retry_delay * (2 ** (message.retry_count - 1))
            else:
                delay = self.batch_config.retry_delay
            
            retry_time = datetime.now() + timedelta(seconds=delay)
            heapq.heappush(self.scheduled_messages, (retry_time, message))
            
            logger.info(f"🔄 메시지 재시도 예약: {message.id} ({message.retry_count}/{message.max_retries})")
            
        else:
            # 최대 재시도 횟수 초과
            message.status = MessageStatus.FAILED
            self.stats['failed_messages'] += 1
            
            logger.error(f"❌ 메시지 최종 실패: {message.id} - {message.error_message}")
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """큐 상태 정보 반환"""
        return {
            'is_running': self.is_running,
            'queue_sizes': {
                priority.name: len(queue) 
                for priority, queue in self.message_queues.items()
            },
            'scheduled_messages': len(self.scheduled_messages),
            'batch_queue_size': self.batch_queue.qsize(),
            'active_batches': self.active_batches,
            'stats': self.stats.copy(),
            'config': {
                'max_batch_size': self.batch_config.max_batch_size,
                'max_wait_time': self.batch_config.max_wait_time,
                'max_concurrent_batches': self.batch_config.max_concurrent_batches
            }
        }
    
    async def cancel_message(self, message_id: str) -> bool:
        """메시지 취소"""
        # 모든 큐에서 메시지 찾기
        for priority, queue in self.message_queues.items():
            for message in list(queue):
                if message.id == message_id:
                    queue.remove(message)
                    message.status = MessageStatus.CANCELLED
                    self.stats['queue_sizes'][priority.value] -= 1
                    logger.info(f"✅ 메시지 취소됨: {message_id}")
                    return True
        
        # 스케줄된 메시지에서 찾기
        for i, (scheduled_time, message) in enumerate(self.scheduled_messages):
            if message.id == message_id:
                self.scheduled_messages.pop(i)
                message.status = MessageStatus.CANCELLED
                logger.info(f"✅ 스케줄된 메시지 취소됨: {message_id}")
                return True
        
        return False
    
    async def clear_queue(self, topic: Optional[str] = None):
        """큐 비우기"""
        if topic:
            # 특정 토픽의 메시지만 제거
            for priority, queue in self.message_queues.items():
                queue[:] = [msg for msg in queue if msg.topic != topic]
                self.stats['queue_sizes'][priority.value] = len(queue)
            
            # 스케줄된 메시지에서도 제거
            self.scheduled_messages[:] = [
                (time, msg) for time, msg in self.scheduled_messages 
                if msg.topic != topic
            ]
            
            logger.info(f"✅ 토픽 큐 비움: {topic}")
        else:
            # 모든 큐 비우기
            for priority, queue in self.message_queues.items():
                queue.clear()
                self.stats['queue_sizes'][priority.value] = 0
            
            self.scheduled_messages.clear()
            logger.info("✅ 모든 큐 비움")

# 사용 예시
async def example_message_handler(message: Message):
    """예시 메시지 핸들러"""
    print(f"📨 메시지 처리: {message.topic} - {message.payload}")
    await asyncio.sleep(0.1)  # 처리 시뮬레이션

async def example_batch_handler(messages: List[Message]):
    """예시 배치 핸들러"""
    print(f"📦 배치 처리: {len(messages)}개 메시지")
    for message in messages:
        print(f"  - {message.topic}: {message.payload}")
    await asyncio.sleep(0.5)  # 배치 처리 시뮬레이션

async def main():
    """메시지 큐 시스템 테스트"""
    # 배치 설정
    batch_config = BatchConfig(
        max_batch_size=10,
        max_wait_time=2.0,
        max_concurrent_batches=2
    )
    
    # 메시지 큐 생성
    queue = AsyncMessageQueue(batch_config)
    
    # 핸들러 등록
    queue.subscribe("test_topic", example_message_handler)
    queue.subscribe("batch_topic", example_batch_handler, is_batch_handler=True)
    
    try:
        # 시스템 시작
        await queue.start()
        
        # 메시지 발행
        for i in range(20):
            await queue.publish("test_topic", {"message": f"Test message {i}"})
            await asyncio.sleep(0.1)
        
        # 배치 메시지 발행
        batch_messages = [
            {"batch": f"Batch message {i}"} for i in range(15)
        ]
        await queue.publish_batch("batch_topic", batch_messages)
        
        # 상태 모니터링
        for _ in range(10):
            status = await queue.get_queue_status()
            print(f"큐 상태: {status['queue_sizes']}")
            await asyncio.sleep(1)
        
    finally:
        await queue.stop()

if __name__ == "__main__":
    asyncio.run(main())
