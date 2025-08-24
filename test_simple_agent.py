#!/usr/bin/env python3
"""
간단한 테스트용 에이전트
AgentProcessManager 테스트를 위한 최소한의 구현
"""

import time
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """메인 함수"""
    logger.info("🚀 테스트 에이전트 시작됨")
    
    try:
        # 간단한 작업 시뮬레이션
        for i in range(10):
            logger.info(f"작업 진행 중... {i+1}/10")
            time.sleep(1)
        
        logger.info("✅ 테스트 에이전트 정상 완료")
        
    except KeyboardInterrupt:
        logger.info("⚠️ 테스트 에이전트 중단됨")
    except Exception as e:
        logger.error(f"❌ 테스트 에이전트 오류: {e}")
    
    logger.info("🔚 테스트 에이전트 종료")

if __name__ == "__main__":
    main()
