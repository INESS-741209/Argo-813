#!/usr/bin/env python3
"""
실제 Neo4j 매니저의 Cypher 쿼리 실행 테스트
"""

import asyncio
import logging
import json
import time
from datetime import datetime
from typing import Dict, Any, List

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CypherExecutionTester:
    """Cypher 쿼리 실행 테스터"""
    
    def __init__(self):
        self.test_results = {}
        self.performance_metrics = {}
        
    async def test_basic_cypher_operations(self):
        """기본 Cypher 작업 테스트"""
        logger.info("🧪 기본 Cypher 작업 테스트 시작...")
        
        try:
            from src.infrastructure.graph.neo4j_langgraph_manager import Neo4jLangGraphManager
            
            # Mock 설정으로 매니저 초기화
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
            
            manager = Neo4jLangGraphManager(neo4j_config, redis_config)
            
            # 1. 기본 노드 생성 테스트
            logger.info("📝 기본 노드 생성 테스트...")
            create_result = await manager.execute_cypher_query(
                "CREATE (n:TestNode {id: $id, name: $name, created_at: datetime()}) RETURN n",
                {"id": "test_001", "name": "Test Node 1"}
            )
            
            self.test_results["create_node"] = {
                "success": create_result.get("success", False),
                "records_count": create_result.get("count", 0),
                "execution_time": create_result.get("execution_time", 0)
            }
            
            # 2. 노드 조회 테스트
            logger.info("🔍 노드 조회 테스트...")
            query_result = await manager.execute_cypher_query(
                "MATCH (n:TestNode) RETURN n.id as id, n.name as name, n.created_at as created_at"
            )
            
            self.test_results["query_nodes"] = {
                "success": query_result.get("success", False),
                "records_count": query_result.get("count", 0),
                "execution_time": query_result.get("execution_time", 0)
            }
            
            # 3. 노드 업데이트 테스트
            logger.info("✏️ 노드 업데이트 테스트...")
            update_result = await manager.execute_cypher_query(
                "MATCH (n:TestNode {id: $id}) SET n.name = $new_name, n.updated_at = datetime() RETURN n",
                {"id": "test_001", "new_name": "Updated Test Node"}
            )
            
            self.test_results["update_node"] = {
                "success": update_result.get("success", False),
                "records_count": update_result.get("count", 0),
                "execution_time": update_result.get("execution_time", 0)
            }
            
            # 4. 관계 생성 테스트
            logger.info("🔗 관계 생성 테스트...")
            rel_result = await manager.execute_cypher_query(
                """
                MATCH (a:TestNode {id: $id1}), (b:TestNode {id: $id2})
                CREATE (a)-[r:RELATES_TO {type: 'test', created_at: datetime()}]->(b)
                RETURN r
                """,
                {"id1": "test_001", "id2": "test_002"}
            )
            
            self.test_results["create_relationship"] = {
                "success": rel_result.get("success", False),
                "records_count": rel_result.get("count", 0),
                "execution_time": rel_result.get("execution_time", 0)
            }
            
            # 5. 복잡한 쿼리 테스트
            logger.info("🧠 복잡한 쿼리 테스트...")
            complex_result = await manager.execute_cypher_query(
                """
                MATCH (n:TestNode)
                OPTIONAL MATCH (n)-[r:RELATES_TO]->(related)
                RETURN n.id as node_id, 
                       n.name as node_name,
                       collect(related.id) as related_ids,
                       count(r) as relationship_count
                ORDER BY relationship_count DESC
                """
            )
            
            self.test_results["complex_query"] = {
                "success": complex_result.get("success", False),
                "records_count": complex_result.get("count", 0),
                "execution_time": complex_result.get("execution_time", 0)
            }
            
            # 6. 정리 작업
            logger.info("🧹 테스트 데이터 정리...")
            cleanup_result = await manager.execute_cypher_query(
                "MATCH (n:TestNode) DETACH DELETE n"
            )
            
            self.test_results["cleanup"] = {
                "success": cleanup_result.get("success", False),
                "records_count": cleanup_result.get("count", 0),
                "execution_time": cleanup_result.get("execution_time", 0)
            }
            
            await manager.shutdown()
            
            logger.info("✅ 기본 Cypher 작업 테스트 완료")
            return self.test_results
            
        except Exception as e:
            logger.error(f"❌ 기본 Cypher 작업 테스트 실패: {e}")
            self.test_results["error"] = str(e)
            return self.test_results
    
    async def test_embedding_integration(self):
        """임베딩 통합 테스트"""
        logger.info("🧪 임베딩 통합 테스트 시작...")
        
        try:
            # Mock 임베딩 데이터 생성
            mock_embedding = [0.1] * 1536  # OpenAI 임베딩 차원
            
            # 임베딩 노드 생성 테스트
            from src.infrastructure.graph.neo4j_langgraph_manager import Neo4jLangGraphManager
            
            neo4j_config = {'uri': 'bolt://localhost:7687', 'username': 'neo4j', 'password': 'password'}
            redis_config = {'host': 'localhost', 'port': 6379, 'db': 0}
            
            manager = Neo4jLangGraphManager(neo4j_config, redis_config)
            
            # 1. 임베딩 노드 생성
            logger.info("📝 임베딩 노드 생성 테스트...")
            embedding_node_result = await manager.execute_cypher_query(
                """
                CREATE (e:EmbeddingNode {
                    id: $id,
                    source_text: $text,
                    embedding_vector: $vector,
                    model: $model,
                    created_at: datetime()
                }) RETURN e
                """,
                {
                    "id": "emb_001",
                    "text": "AI neural networks for natural language processing",
                    "vector": mock_embedding,
                    "model": "text-embedding-3-large"
                }
            )
            
            self.test_results["embedding_node_creation"] = {
                "success": embedding_node_result.get("success", False),
                "records_count": embedding_node_result.get("count", 0),
                "execution_time": embedding_node_result.get("execution_time", 0)
            }
            
            # 2. 임베딩 기반 유사도 검색 시뮬레이션
            logger.info("🔍 임베딩 기반 유사도 검색 시뮬레이션...")
            similarity_result = await manager.execute_cypher_query(
                """
                MATCH (e:EmbeddingNode)
                WHERE e.model = $model
                RETURN e.id as embedding_id,
                       e.source_text as text,
                       e.embedding_vector as vector,
                       e.created_at as created
                LIMIT 5
                """,
                {"model": "text-embedding-3-large"}
            )
            
            self.test_results["embedding_similarity_search"] = {
                "success": similarity_result.get("success", False),
                "records_count": similarity_result.get("count", 0),
                "execution_time": similarity_result.get("execution_time", 0)
            }
            
            # 3. 임베딩 메타데이터 쿼리
            logger.info("📊 임베딩 메타데이터 쿼리...")
            metadata_result = await manager.execute_cypher_query(
                """
                MATCH (e:EmbeddingNode)
                RETURN e.model as model,
                       count(e) as total_embeddings,
                       avg(size(e.embedding_vector)) as avg_dimension,
                       min(e.created_at) as oldest,
                       max(e.created_at) as newest
                """
            )
            
            self.test_results["embedding_metadata"] = {
                "success": metadata_result.get("success", False),
                "records_count": metadata_result.get("count", 0),
                "execution_time": metadata_result.get("execution_time", 0)
            }
            
            # 4. 정리
            cleanup_result = await manager.execute_cypher_query(
                "MATCH (e:EmbeddingNode) DETACH DELETE e"
            )
            
            await manager.shutdown()
            
            logger.info("✅ 임베딩 통합 테스트 완료")
            return self.test_results
            
        except Exception as e:
            logger.error(f"❌ 임베딩 통합 테스트 실패: {e}")
            self.test_results["embedding_error"] = str(e)
            return self.test_results
    
    async def test_performance_metrics(self):
        """성능 메트릭 테스트"""
        logger.info("📊 성능 메트릭 테스트 시작...")
        
        try:
            from src.infrastructure.graph.neo4j_langgraph_manager import Neo4jLangGraphManager
            
            neo4j_config = {'uri': 'bolt://localhost:7687', 'username': 'neo4j', 'password': 'password'}
            redis_config = {'host': 'localhost', 'port': 6379, 'db': 0}
            
            manager = Neo4jLangGraphManager(neo4j_config, redis_config)
            
            # 성능 메트릭 수집
            metrics = manager.get_performance_metrics()
            
            self.performance_metrics = {
                "operation_queue_size": metrics.get("operation_queue_size", 0),
                "failed_operations_count": metrics.get("failed_operations_count", 0),
                "performance_metrics": metrics.get("performance_metrics", {})
            }
            
            # 실패한 작업 정리
            cleaned_count = await manager.cleanup_failed_operations()
            self.performance_metrics["cleaned_operations"] = cleaned_count
            
            await manager.shutdown()
            
            logger.info("✅ 성능 메트릭 테스트 완료")
            return self.performance_metrics
            
        except Exception as e:
            logger.error(f"❌ 성능 메트릭 테스트 실패: {e}")
            self.performance_metrics["error"] = str(e)
            return self.performance_metrics
    
    async def generate_execution_report(self):
        """실행 테스트 보고서 생성"""
        logger.info("📊 실행 테스트 보고서 생성 시작...")
        
        # 모든 테스트 실행
        await self.test_basic_cypher_operations()
        await self.test_embedding_integration()
        await self.test_performance_metrics()
        
        # 성공률 계산
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results.values() 
                             if isinstance(result, dict) and result.get("success", False))
        
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
        
        # 평균 실행 시간 계산
        execution_times = []
        for result in self.test_results.values():
            if isinstance(result, dict) and "execution_time" in result:
                execution_times.append(result["execution_time"])
        
        avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
        
        # 보고서 생성
        report = {
            "test_timestamp": datetime.now().isoformat(),
            "test_summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate": f"{success_rate:.1f}%",
                "avg_execution_time": f"{avg_execution_time:.3f}초"
            },
            "detailed_results": self.test_results,
            "performance_metrics": self.performance_metrics,
            "recommendations": [
                "성공률이 80% 미만인 경우 MockNeo4j 구현 검토 필요",
                "실행 시간이 1초를 초과하는 쿼리는 최적화 고려",
                "실패한 작업이 많은 경우 에러 처리 로직 강화",
                "성능 메트릭을 지속적으로 모니터링하여 병목 지점 파악"
            ]
        }
        
        logger.info("✅ 실행 테스트 보고서 생성 완료")
        return report

async def main():
    """메인 실행 함수"""
    logger.info("🚀 Cypher 쿼리 실행 테스트 시작")
    
    tester = CypherExecutionTester()
    
    try:
        # 실행 테스트 실행
        report = await tester.generate_execution_report()
        
        # 결과 출력
        print("\n" + "="*80)
        print("🧪 CYPHER 쿼리 실행 테스트 결과")
        print("="*80)
        
        print(f"\n📊 테스트 요약:")
        print(f"   • 총 테스트: {report['test_summary']['total_tests']}개")
        print(f"   • 성공: {report['test_summary']['successful_tests']}개")
        print(f"   • 성공률: {report['test_summary']['success_rate']}")
        print(f"   • 평균 실행 시간: {report['test_summary']['avg_execution_time']}")
        
        print(f"\n🔍 상세 결과:")
        for test_name, result in report['detailed_results'].items():
            if isinstance(result, dict):
                status = "✅ 성공" if result.get("success", False) else "❌ 실패"
                print(f"   • {test_name}: {status}")
                if "execution_time" in result:
                    print(f"     실행 시간: {result['execution_time']:.3f}초")
            else:
                print(f"   • {test_name}: {result}")
        
        print(f"\n📈 성능 메트릭:")
        for metric_name, value in report['performance_metrics'].items():
            print(f"   • {metric_name}: {value}")
        
        print(f"\n🎯 권장사항:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"   {i}. {rec}")
        
        print(f"\n📅 테스트 완료 시간: {report['test_timestamp']}")
        print("="*80)
        
        # 상세 결과를 파일로 저장
        with open("cypher_execution_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info("📁 상세 보고서가 'cypher_execution_report.json'에 저장되었습니다")
        
    except Exception as e:
        logger.error(f"❌ 테스트 중 오류 발생: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
