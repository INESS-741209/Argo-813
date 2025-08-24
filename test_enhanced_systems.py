#!/usr/bin/env python3
"""
Enhanced Systems Integration Test for ARGO
새로 구현된 시스템들의 통합 테스트
"""

import asyncio
import logging
import json
import time
from datetime import datetime
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_data_sync_transaction_manager():
    """데이터 동기화 트랜잭션 매니저 테스트"""
    logger.info("🔄 Testing Data Sync Transaction Manager...")
    
    try:
        from src.infrastructure.sync.transaction_manager import (
            DataSyncTransactionManager, SyncOperation
        )
        
        # 설정
        redis_config = {'host': 'localhost', 'port': 6379, 'db': 0}
        neo4j_config = {
            'uri': 'bolt://localhost:7687',
            'username': 'neo4j',
            'password': 'password'
        }
        
        # 매니저 초기화
        manager = DataSyncTransactionManager(redis_config, neo4j_config)
        
        # 트랜잭션 시작
        transaction_id = "test_tx_001"
        success = await manager.begin_transaction(transaction_id)
        
        if not success:
            logger.error("❌ 트랜잭션 시작 실패")
            return False
        
        # 노드 생성 작업 추가
        operation = SyncOperation(
            id="test_op_001",
            operation_type="create",
            entity_type="node",
            entity_id="test_user_001",
            data={
                'labels': ['TestUser'],
                'properties': {
                    'name': 'Test User',
                    'email': 'test@example.com',
                    'created_at': datetime.utcnow().isoformat()
                }
            },
            timestamp=datetime.utcnow()
        )
        
        success = await manager.add_operation(transaction_id, operation)
        
        if not success:
            logger.error("❌ 작업 추가 실패")
            return False
        
        # 트랜잭션 커밋
        success = await manager.commit_transaction(transaction_id)
        
        if success:
            logger.info("✅ 데이터 동기화 트랜잭션 테스트 성공")
            return True
        else:
            logger.error("❌ 트랜잭션 커밋 실패")
            return False
            
    except Exception as e:
        logger.error(f"❌ 데이터 동기화 테스트 실패: {e}")
        return False
    finally:
        if 'manager' in locals():
            await manager.shutdown()

async def test_agent_process_manager():
    """에이전트 프로세스 매니저 테스트"""
    logger.info("🤖 Testing Agent Process Manager...")
    
    try:
        from src.agents.agent_process_manager import AgentProcessManager
        
        # 매니저 초기화
        manager = AgentProcessManager()
        
        # 매니저 시작
        await manager.start()
        
        # 에이전트 상태 확인
        status = manager.get_all_agents_status()
        logger.info(f"📊 초기 에이전트 상태: {len(status)}개 등록됨")
        
        # 모든 에이전트 시작
        results = await manager.start_all_agents()
        logger.info(f"🚀 에이전트 시작 결과: {results}")
        
        # 10초 대기
        await asyncio.sleep(10)
        
        # 상태 재확인
        status = manager.get_all_agents_status()
        logger.info(f"📊 실행 중인 에이전트: {sum(1 for s in status.values() if s and s.get('status') == 'running')}개")
        
        # 모든 에이전트 중지
        stop_results = await manager.stop_all_agents()
        logger.info(f"🛑 에이전트 중지 결과: {stop_results}")
        
        logger.info("✅ 에이전트 프로세스 매니저 테스트 성공")
        return True
        
    except Exception as e:
        logger.error(f"❌ 에이전트 프로세스 매니저 테스트 실패: {e}")
        return False
    finally:
        if 'manager' in locals():
            await manager.shutdown()

async def test_neo4j_langgraph_manager():
    """Neo4j LangGraph 매니저 테스트"""
    logger.info("🗃️ Testing Neo4j LangGraph Manager...")
    
    try:
        from src.infrastructure.graph.neo4j_langgraph_manager import (
            Neo4jLangGraphManager, GraphOperation, GraphOperationType
        )
        
        # 설정
        neo4j_config = {
            'uri': 'bolt://localhost:7687',
            'username': 'neo4j',
            'password': 'password'
        }
        
        redis_config = {'host': 'localhost', 'port': 6379, 'db': 0}
        
        # 매니저 초기화
        manager = Neo4jLangGraphManager(neo4j_config, redis_config)
        
        # 노드 생성 작업
        operation = GraphOperation(
            id="test_graph_op_001",
            operation_type=GraphOperationType.CREATE_NODE,
            target_type="node",
            labels=["TestNode"],
            properties={
                "name": "Test Graph Node",
                "description": "Test node for LangGraph integration",
                "test_data": "This is test data"
            }
        )
        
        # 작업 실행
        result = await manager.execute_graph_operation(operation)
        
        if result.get("success"):
            logger.info("✅ Neo4j LangGraph 작업 실행 성공")
            
            # 성능 메트릭 확인
            metrics = manager.get_performance_metrics()
            logger.info(f"📊 성능 메트릭: {len(metrics.get('performance_metrics', {}))}개 작업")
            
            return True
        else:
            logger.error(f"❌ Neo4j LangGraph 작업 실행 실패: {result.get('errors')}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Neo4j LangGraph 테스트 실패: {e}")
        return False
    finally:
        if 'manager' in locals():
            await manager.shutdown()

async def test_cypher_queries():
    """Cypher 쿼리 실행 테스트"""
    logger.info("🔍 Testing Cypher Queries...")
    
    try:
        from src.infrastructure.graph.neo4j_langgraph_manager import Neo4jLangGraphManager
        
        # 매니저 초기화
        neo4j_config = {
            'uri': 'bolt://localhost:7687',
            'username': 'neo4j',
            'password': 'password'
        }
        
        manager = Neo4jLangGraphManager(neo4j_config)
        
        # 테스트 쿼리들
        test_queries = [
            {
                "name": "노드 수 조회",
                "query": "MATCH (n) RETURN count(n) as node_count",
                "parameters": {}
            },
            {
                "name": "사용자 노드 조회",
                "query": "MATCH (u:User) RETURN u.name as name, u.email as email LIMIT 5",
                "parameters": {}
            },
            {
                "name": "태그 노드 조회",
                "query": "MATCH (t:Tag) RETURN t.name as tag_name, t.category as category",
                "parameters": {}
            },
            {
                "name": "프로젝트 노드 조회",
                "query": "MATCH (p:Project) RETURN p.name as project_name, p.description as description",
                "parameters": {}
            }
        ]
        
        success_count = 0
        
        for test_query in test_queries:
            try:
                logger.info(f"실행 중: {test_query['name']}")
                
                result = await manager.execute_cypher_query(
                    test_query['query'], 
                    test_query['parameters']
                )
                
                if result.get("success"):
                    logger.info(f"✅ {test_query['name']}: {result.get('count', 0)}개 결과")
                    success_count += 1
                else:
                    logger.error(f"❌ {test_query['name']}: {result.get('error')}")
                    
            except Exception as e:
                logger.error(f"❌ {test_query['name']} 실행 실패: {e}")
        
        logger.info(f"📊 Cypher 쿼리 테스트 결과: {success_count}/{len(test_queries)} 성공")
        return success_count == len(test_queries)
        
    except Exception as e:
        logger.error(f"❌ Cypher 쿼리 테스트 실패: {e}")
        return False
    finally:
        if 'manager' in locals():
            await manager.shutdown()

async def test_integrated_scenario():
    """통합 시나리오 테스트"""
    logger.info("🔄 Testing Integrated Scenario...")
    
    try:
        # 1. 데이터 동기화 테스트
        sync_success = await test_data_sync_transaction_manager()
        
        # 2. 에이전트 프로세스 관리 테스트
        agent_success = await test_agent_process_manager()
        
        # 3. Neo4j LangGraph 테스트
        graph_success = await test_neo4j_langgraph_manager()
        
        # 4. Cypher 쿼리 테스트
        query_success = await test_cypher_queries()
        
        # 전체 결과
        total_tests = 4
        successful_tests = sum([sync_success, agent_success, graph_success, query_success])
        
        logger.info("=" * 60)
        logger.info("📊 INTEGRATED SCENARIO TEST RESULTS")
        logger.info("=" * 60)
        logger.info(f"✅ Data Sync Transaction Manager: {'성공' if sync_success else '실패'}")
        logger.info(f"✅ Agent Process Manager: {'성공' if agent_success else '실패'}")
        logger.info(f"✅ Neo4j LangGraph Manager: {'성공' if graph_success else '실패'}")
        logger.info(f"✅ Cypher Queries: {'성공' if query_success else '실패'}")
        logger.info("=" * 60)
        logger.info(f"🎯 Overall Success Rate: {successful_tests}/{total_tests} ({successful_tests/total_tests*100:.1f}%)")
        
        if successful_tests == total_tests:
            logger.info("🎉 모든 시스템이 성공적으로 통합되었습니다!")
        else:
            logger.warning(f"⚠️ {total_tests - successful_tests}개 시스템에서 문제가 발생했습니다.")
        
        return successful_tests == total_tests
        
    except Exception as e:
        logger.error(f"❌ 통합 시나리오 테스트 실패: {e}")
        return False

async def main():
    """메인 테스트 실행"""
    logger.info("🚀 Starting Enhanced Systems Integration Tests...")
    
    try:
        # 개별 테스트 실행
        logger.info("\n" + "="*60)
        logger.info("🧪 INDIVIDUAL SYSTEM TESTS")
        logger.info("="*60)
        
        # 1. 데이터 동기화 테스트
        await test_data_sync_transaction_manager()
        
        # 2. 에이전트 프로세스 관리 테스트
        await test_agent_process_manager()
        
        # 3. Neo4j LangGraph 테스트
        await test_neo4j_langgraph_manager()
        
        # 4. Cypher 쿼리 테스트
        await test_cypher_queries()
        
        # 통합 시나리오 테스트
        logger.info("\n" + "="*60)
        logger.info("🔄 INTEGRATED SCENARIO TEST")
        logger.info("="*60)
        
        await test_integrated_scenario()
        
        logger.info("\n🎉 Enhanced Systems Integration Tests Completed!")
        
    except Exception as e:
        logger.error(f"❌ 테스트 실행 중 오류 발생: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
