"""
고급 Neo4j 그래프 관리 시스템
ARGO Phase 2: 복잡한 시나리오, 다차원 검색, 실시간 업데이트 지원
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import uuid
from collections import defaultdict, deque
import hashlib
import numpy as np
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

logger = logging.getLogger(__name__)

class NodeType(Enum):
    """노드 타입 정의"""
    DOCUMENT = "Document"
    CONCEPT = "Concept"
    PERSON = "Person"
    ORGANIZATION = "Organization"
    LOCATION = "Location"
    EVENT = "Event"
    TECHNOLOGY = "Technology"
    DOMAIN = "Domain"
    EMBEDDING = "Embedding"
    METADATA = "Metadata"
    RELATIONSHIP = "Relationship"

class RelationshipType(Enum):
    """관계 타입 정의"""
    SIMILAR_TO = "SIMILAR_TO"
    CONTAINS = "CONTAINS"
    REFERENCES = "REFERENCES"
    AUTHORED_BY = "AUTHORED_BY"
    LOCATED_IN = "LOCATED_IN"
    OCCURRED_AT = "OCCURRED_AT"
    USES_TECHNOLOGY = "USES_TECHNOLOGY"
    BELONGS_TO_DOMAIN = "BELONGS_TO_DOMAIN"
    HAS_EMBEDDING = "HAS_EMBEDDING"
    DERIVED_FROM = "DERIVED_FROM"
    COLLABORATES_WITH = "COLLABORATES_WITH"
    INFLUENCES = "INFLUENCES"
    DEPENDS_ON = "DEPENDS_ON"
    SYNONYMOUS_WITH = "SYNONYMOUS_WITH"
    OPPOSITE_OF = "OPPOSITE_OF"

class QueryComplexity(Enum):
    """쿼리 복잡도 레벨"""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

@dataclass
class GraphNode:
    """그래프 노드 정보"""
    id: str
    labels: List[str]
    properties: Dict[str, Any]
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 1
    confidence_score: float = 1.0
    source_system: str = ""

@dataclass
class GraphRelationship:
    """그래프 관계 정보"""
    id: str
    source_node_id: str
    target_node_id: str
    relationship_type: str
    properties: Dict[str, Any]
    strength: float = 1.0
    confidence: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SearchFilter:
    """검색 필터 조건"""
    node_types: Optional[List[str]] = None
    relationship_types: Optional[List[str]] = None
    property_filters: Dict[str, Any] = field(default_factory=dict)
    embedding_similarity_threshold: float = 0.7
    confidence_threshold: float = 0.5
    date_range: Optional[Tuple[datetime, datetime]] = None
    strength_range: Optional[Tuple[float, float]] = None
    domain_filters: Optional[List[str]] = None
    source_system_filters: Optional[List[str]] = None

@dataclass
class SearchResult:
    """검색 결과"""
    nodes: List[GraphNode]
    relationships: List[GraphRelationship]
    paths: List[List[GraphNode]]
    relevance_score: float
    execution_time: float
    total_count: int
    metadata: Dict[str, Any]

class AdvancedNeo4jManager:
    """고급 Neo4j 그래프 관리 시스템"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.driver: Optional[GraphDatabase.Driver] = None
        self.connection_pool_size = config.get('connection_pool_size', 50)
        self.max_transaction_retries = config.get('max_transaction_retries', 3)
        self.query_timeout = config.get('query_timeout', 30)
        
        # 성능 메트릭
        self.performance_metrics = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'average_query_time': 0.0,
            'total_query_time': 0.0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        # 쿼리 캐시
        self.query_cache: Dict[str, Any] = {}
        self.cache_ttl = config.get('cache_ttl', 300)  # 5분
        
        # 인덱스 관리
        self.indexes_created = False
        
        logger.info("고급 Neo4j 매니저 초기화됨")
    
    async def connect(self) -> bool:
        """Neo4j 데이터베이스 연결"""
        try:
            uri = self.config['uri']
            username = self.config['username']
            password = self.config['password']
            
            self.driver = GraphDatabase.driver(
                uri,
                auth=(username, password),
                max_connection_pool_size=self.connection_pool_size,
                connection_timeout=10,
                connection_acquisition_timeout=10
            )
            
            # 연결 테스트
            with self.driver.session() as session:
                result = session.run("RETURN 1 as test")
                result.single()
            
            # 인덱스 생성
            await self._create_indexes()
            
            logger.info("✅ Neo4j 연결 성공")
            return True
            
        except Exception as e:
            logger.error(f"❌ Neo4j 연결 실패: {e}")
            return False
    
    async def disconnect(self):
        """연결 해제"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j 연결 해제됨")
    
    async def _create_indexes(self):
        """성능 향상을 위한 인덱스 생성"""
        if self.indexes_created:
            return
        
        index_queries = [
            # 노드 타입별 인덱스
            "CREATE INDEX node_labels IF NOT EXISTS FOR (n) ON (n.labels)",
            "CREATE INDEX node_created_at IF NOT EXISTS FOR (n) ON (n.created_at)",
            "CREATE INDEX node_updated_at IF NOT EXISTS FOR (n) ON (n.updated_at)",
            "CREATE INDEX node_confidence IF NOT EXISTS FOR (n) ON (n.confidence_score)",
            "CREATE INDEX node_source_system IF NOT EXISTS FOR (n) ON (n.source_system)",
            
            # 관계 타입별 인덱스
            "CREATE INDEX relationship_type IF NOT EXISTS FOR ()-[r]-() ON (r.type)",
            "CREATE INDEX relationship_strength IF NOT EXISTS FOR ()-[r]-() ON (r.strength)",
            "CREATE INDEX relationship_confidence IF NOT EXISTS FOR ()-[r]-() ON (r.confidence)",
            
            # 속성 기반 인덱스
            "CREATE INDEX node_name IF NOT EXISTS FOR (n) ON (n.name)",
            "CREATE INDEX node_category IF NOT EXISTS FOR (n) ON (n.category)",
            "CREATE INDEX node_domain IF NOT EXISTS FOR (n) ON (n.domain)",
            
            # 벡터 검색을 위한 인덱스
            "CREATE INDEX node_embedding IF NOT EXISTS FOR (n) ON (n.embedding) USING 'vector'"
        ]
        
        try:
            with self.driver.session() as session:
                for query in index_queries:
                    try:
                        session.run(query)
                        logger.debug(f"인덱스 생성: {query}")
                    except Exception as e:
                        logger.warning(f"인덱스 생성 실패: {query} - {e}")
            
            self.indexes_created = True
            logger.info("✅ Neo4j 인덱스 생성 완료")
            
        except Exception as e:
            logger.error(f"❌ 인덱스 생성 실패: {e}")
    
    async def create_node(self, node: GraphNode) -> str:
        """고급 노드 생성"""
        start_time = time.time()
        
        try:
            with self.driver.session() as session:
                # 노드 생성 쿼리
                query = """
                CREATE (n:Node {
                    id: $id,
                    labels: $labels,
                    properties: $properties,
                    embedding: $embedding,
                    metadata: $metadata,
                    created_at: $created_at,
                    updated_at: $updated_at,
                    version: $version,
                    confidence_score: $confidence_score,
                    source_system: $source_system
                })
                SET n += $properties
                RETURN n.id as node_id
                """
                
                params = {
                    'id': node.id,
                    'labels': node.labels,
                    'properties': node.properties,
                    'embedding': node.embedding,
                    'metadata': node.metadata,
                    'created_at': node.created_at.isoformat(),
                    'updated_at': node.updated_at.isoformat(),
                    'version': node.version,
                    'confidence_score': node.confidence_score,
                    'source_system': node.source_system
                }
                
                result = session.run(query, params)
                node_id = result.single()['node_id']
                
                # 라벨별 노드 생성
                for label in node.labels:
                    label_query = f"""
                    MATCH (n {{id: $node_id}})
                    SET n:{label}
                    RETURN n
                    """
                    session.run(label_query, {'node_id': node_id})
                
                self._update_metrics(start_time, True)
                logger.info(f"✅ 노드 생성 완료: {node_id}")
                return node_id
                
        except Exception as e:
            self._update_metrics(start_time, False)
            logger.error(f"❌ 노드 생성 실패: {e}")
            raise
    
    async def create_relationship(self, relationship: GraphRelationship) -> str:
        """고급 관계 생성"""
        start_time = time.time()
        
        try:
            with self.driver.session() as session:
                query = """
                MATCH (source {id: $source_id}), (target {id: $target_id})
                CREATE (source)-[r:RELATIONSHIP {
                    id: $id,
                    type: $type,
                    properties: $properties,
                    strength: $strength,
                    confidence: $confidence,
                    created_at: $created_at,
                    metadata: $metadata
                }]->(target)
                SET r += $properties
                RETURN r.id as relationship_id
                """
                
                params = {
                    'source_id': relationship.source_node_id,
                    'target_id': relationship.target_node_id,
                    'id': relationship.id,
                    'type': relationship.relationship_type,
                    'properties': relationship.properties,
                    'strength': relationship.strength,
                    'confidence': relationship.confidence,
                    'created_at': relationship.created_at.isoformat(),
                    'metadata': relationship.metadata
                }
                
                result = session.run(query, params)
                relationship_id = result.single()['relationship_id']
                
                self._update_metrics(start_time, True)
                logger.info(f"✅ 관계 생성 완료: {relationship_id}")
                return relationship_id
                
        except Exception as e:
            self._update_metrics(start_time, False)
            logger.error(f"❌ 관계 생성 실패: {e}")
            raise
    
    async def advanced_search(self, 
                            query_text: str,
                            filters: SearchFilter,
                            complexity: QueryComplexity = QueryComplexity.ADVANCED,
                            limit: int = 100) -> SearchResult:
        """고급 다차원 검색"""
        start_time = time.time()
        
        try:
            # 캐시된 쿼리 확인
            cache_key = self._generate_cache_key(query_text, filters, complexity, limit)
            if cache_key in self.query_cache:
                cached_result = self.query_cache[cache_key]
                if time.time() - cached_result['timestamp'] < self.cache_ttl:
                    self.performance_metrics['cache_hits'] += 1
                    return cached_result['result']
            
            self.performance_metrics['cache_misses'] += 1
            
            # 복잡도별 쿼리 생성
            if complexity == QueryComplexity.BASIC:
                cypher_query = self._build_basic_search_query(filters, limit)
            elif complexity == QueryComplexity.INTERMEDIATE:
                cypher_query = self._build_intermediate_search_query(filters, limit)
            elif complexity == QueryComplexity.ADVANCED:
                cypher_query = self._build_advanced_search_query(filters, limit)
            else:  # EXPERT
                cypher_query = self._build_expert_search_query(filters, limit)
            
            # 쿼리 실행
            with self.driver.session() as session:
                result = session.run(cypher_query, {
                    'query_text': query_text,
                    'similarity_threshold': filters.embedding_similarity_threshold,
                    'confidence_threshold': filters.confidence_threshold,
                    'limit': limit
                })
                
                # 결과 파싱
                nodes, relationships, paths = self._parse_search_results(result)
                
                # 관련성 점수 계산
                relevance_score = self._calculate_relevance_score(
                    query_text, nodes, relationships, paths
                )
                
                search_result = SearchResult(
                    nodes=nodes,
                    relationships=relationships,
                    paths=paths,
                    relevance_score=relevance_score,
                    execution_time=time.time() - start_time,
                    total_count=len(nodes),
                    metadata={'complexity': complexity.value, 'filters': filters}
                )
                
                # 캐시에 저장
                self.query_cache[cache_key] = {
                    'result': search_result,
                    'timestamp': time.time()
                }
                
                self._update_metrics(start_time, True)
                logger.info(f"✅ 고급 검색 완료: {len(nodes)}개 노드, {len(relationships)}개 관계")
                return search_result
                
        except Exception as e:
            self._update_metrics(start_time, False)
            logger.error(f"❌ 고급 검색 실패: {e}")
            raise
    
    def _build_basic_search_query(self, filters: SearchFilter, limit: int) -> str:
        """기본 검색 쿼리 생성"""
        query = """
        MATCH (n)
        WHERE 1=1
        """
        
        # 노드 타입 필터
        if filters.node_types:
            labels = ':'.join(filters.node_types)
            query += f" AND n:{labels}"
        
        # 속성 필터
        for key, value in filters.property_filters.items():
            if isinstance(value, str):
                query += f" AND n.{key} CONTAINS '{value}'"
            else:
                query += f" AND n.{key} = {value}"
        
        # 신뢰도 필터
        query += f" AND n.confidence_score >= {filters.confidence_threshold}"
        
        query += f" RETURN n LIMIT {limit}"
        return query
    
    def _build_intermediate_search_query(self, filters: SearchFilter, limit: int) -> str:
        """중급 검색 쿼리 생성"""
        query = """
        MATCH (n)-[r]-(m)
        WHERE 1=1
        """
        
        # 노드 타입 필터
        if filters.node_types:
            labels = ':'.join(filters.node_types)
            query += f" AND n:{labels}"
        
        # 관계 타입 필터
        if filters.relationship_types:
            rel_types = ':'.join(filters.relationship_types)
            query += f" AND r:{rel_types}"
        
        # 속성 필터
        for key, value in filters.property_filters.items():
            if isinstance(value, str):
                query += f" AND n.{key} CONTAINS '{value}'"
            else:
                query += f" AND n.{key} = {value}"
        
        # 신뢰도 및 강도 필터
        query += f" AND n.confidence_score >= {filters.confidence_threshold}"
        query += f" AND r.strength >= {filters.strength_range[0] if filters.strength_range else 0.0}"
        
        query += f" RETURN n, r, m LIMIT {limit}"
        return query
    
    def _build_advanced_search_query(self, filters: SearchFilter, limit: int) -> str:
        """고급 검색 쿼리 생성"""
        query = """
        MATCH path = (start)-[r*1..3]-(end)
        WHERE 1=1
        """
        
        # 노드 타입 필터
        if filters.node_types:
            labels = ':'.join(filters.node_types)
            query += f" AND start:{labels}"
        
        # 관계 타입 필터
        if filters.relationship_types:
            rel_types = ':'.join(filters.relationship_types)
            query += f" AND ALL(rel IN r WHERE rel:{rel_types})"
        
        # 속성 필터
        for key, value in filters.property_filters.items():
            if isinstance(value, str):
                query += f" AND start.{key} CONTAINS '{value}'"
            else:
                query += f" AND start.{key} = {value}"
        
        # 신뢰도 및 강도 필터
        query += f" AND start.confidence_score >= {filters.confidence_threshold}"
        query += f" AND ALL(rel IN r WHERE rel.strength >= {filters.strength_range[0] if filters.strength_range else 0.0})"
        
        # 경로 길이별 가중치 계산
        query += """
        WITH path, start, end, r,
             reduce(score = 1.0, rel IN r | score * rel.strength * rel.confidence) as path_score
        ORDER BY path_score DESC
        """
        
        query += f" RETURN path, path_score LIMIT {limit}"
        return query
    
    def _build_expert_search_query(self, filters: SearchFilter, limit: int) -> str:
        """전문가 수준 검색 쿼리 생성"""
        query = """
        MATCH path = (start)-[r*1..5]-(end)
        WHERE 1=1
        """
        
        # 노드 타입 필터
        if filters.node_types:
            labels = ':'.join(filters.node_types)
            query += f" AND start:{labels}"
        
        # 관계 타입 필터
        if filters.relationship_types:
            rel_types = ':'.join(filters.relationship_types)
            query += f" AND ALL(rel IN r WHERE rel:{rel_types})"
        
        # 속성 필터
        for key, value in filters.property_filters.items():
            if isinstance(value, str):
                query += f" AND start.{key} CONTAINS '{value}'"
            else:
                query += f" AND start.{key} = {value}"
        
        # 신뢰도 및 강도 필터
        query += f" AND start.confidence_score >= {filters.confidence_threshold}"
        query += f" AND ALL(rel IN r WHERE rel.strength >= {filters.strength_range[0] if filters.strength_range else 0.0})"
        
        # 도메인 필터
        if filters.domain_filters:
            domains = "', '".join(filters.domain_filters)
            query += f" AND start.domain IN ['{domains}']"
        
        # 소스 시스템 필터
        if filters.source_system_filters:
            sources = "', '".join(filters.source_system_filters)
            query += f" AND start.source_system IN ['{sources}']"
        
        # 날짜 범위 필터
        if filters.date_range:
            start_date, end_date = filters.date_range
            query += f" AND start.created_at >= '{start_date.isoformat()}'"
            query += f" AND start.created_at <= '{end_date.isoformat()}'"
        
        # 고급 경로 분석
        query += """
        WITH path, start, end, r,
             reduce(score = 1.0, rel IN r | score * rel.strength * rel.confidence) as path_score,
             length(path) as path_length,
             [node IN nodes(path) | node.confidence_score] as node_confidences,
             [rel IN r | rel.strength] as relationship_strengths
        WHERE path_score > 0.1
        WITH path, path_score, path_length, node_confidences, relationship_strengths,
             reduce(avg = 0.0, conf IN node_confidences | avg + conf) / size(node_confidences) as avg_node_confidence,
             reduce(avg = 0.0, strength IN relationship_strengths | avg + strength) / size(relationship_strengths) as avg_relationship_strength
        ORDER BY path_score DESC, avg_node_confidence DESC, avg_relationship_strength DESC
        """
        
        query += f" RETURN path, path_score, path_length, avg_node_confidence, avg_relationship_strength LIMIT {limit}"
        return query
    
    async def semantic_search(self, 
                            query_embedding: List[float],
                            filters: SearchFilter,
                            limit: int = 100) -> SearchResult:
        """의미론적 벡터 검색"""
        start_time = time.time()
        
        try:
            # 벡터 유사도 검색 쿼리
            query = """
            MATCH (n)
            WHERE n.embedding IS NOT NULL
            AND n.confidence_score >= $confidence_threshold
            """
            
            # 노드 타입 필터
            if filters.node_types:
                labels = ':'.join(filters.node_types)
                query += f" AND n:{labels}"
            
            # 벡터 유사도 계산 및 정렬
            query += """
            WITH n, gds.similarity.cosine(n.embedding, $query_embedding) as similarity
            WHERE similarity >= $similarity_threshold
            ORDER BY similarity DESC
            """
            
            query += f" RETURN n, similarity LIMIT {limit}"
            
            with self.driver.session() as session:
                result = session.run(query, {
                    'query_embedding': query_embedding,
                    'similarity_threshold': filters.embedding_similarity_threshold,
                    'confidence_threshold': filters.confidence_threshold
                })
                
                # 결과 파싱
                nodes = []
                for record in result:
                    node_data = record['n']
                    similarity = record['similarity']
                    
                    node = GraphNode(
                        id=node_data['id'],
                        labels=node_data.get('labels', []),
                        properties=node_data.get('properties', {}),
                        embedding=node_data.get('embedding'),
                        metadata={'similarity_score': similarity}
                    )
                    nodes.append(node)
                
                search_result = SearchResult(
                    nodes=nodes,
                    relationships=[],
                    paths=[],
                    relevance_score=np.mean([n.metadata.get('similarity_score', 0) for n in nodes]) if nodes else 0.0,
                    execution_time=time.time() - start_time,
                    total_count=len(nodes),
                    metadata={'search_type': 'semantic', 'filters': filters}
                )
                
                self._update_metrics(start_time, True)
                logger.info(f"✅ 의미론적 검색 완료: {len(nodes)}개 노드")
                return search_result
                
        except Exception as e:
            self._update_metrics(start_time, False)
            logger.error(f"❌ 의미론적 검색 실패: {e}")
            raise
    
    async def path_analysis(self, 
                           source_node_id: str,
                           target_node_id: str,
                           max_path_length: int = 5,
                           relationship_types: Optional[List[str]] = None) -> List[List[GraphNode]]:
        """경로 분석 및 추천"""
        start_time = time.time()
        
        try:
            query = """
            MATCH path = (start)-[r*1..$max_length]-(end)
            WHERE start.id = $source_id AND end.id = $target_id
            """
            
            if relationship_types:
                rel_types = ':'.join(relationship_types)
                query += f" AND ALL(rel IN r WHERE rel:{rel_types})"
            
            query += """
            WITH path, r,
                 reduce(score = 1.0, rel IN r | score * rel.strength * rel.confidence) as path_score,
                 length(path) as path_length
            ORDER BY path_score DESC, path_length ASC
            RETURN path, path_score, path_length
            LIMIT 10
            """
            
            with self.driver.session() as session:
                result = session.run(query, {
                    'source_id': source_node_id,
                    'target_id': target_node_id,
                    'max_length': max_path_length
                })
                
                paths = []
                for record in result:
                    path_data = record['path']
                    path_score = record['path_score']
                    path_length = record['path_length']
                    
                    path_nodes = []
                    for node_data in path_data.nodes:
                        node = GraphNode(
                            id=node_data['id'],
                            labels=node_data.get('labels', []),
                            properties=node_data.get('properties', {}),
                            metadata={'path_score': path_score, 'path_length': path_length}
                        )
                        path_nodes.append(node)
                    
                    paths.append(path_nodes)
                
                self._update_metrics(start_time, True)
                logger.info(f"✅ 경로 분석 완료: {len(paths)}개 경로")
                return paths
                
        except Exception as e:
            self._update_metrics(start_time, False)
            logger.error(f"❌ 경로 분석 실패: {e}")
            raise
    
    async def community_detection(self, 
                                min_community_size: int = 3,
                                relationship_types: Optional[List[str]] = None) -> List[List[str]]:
        """커뮤니티 탐지"""
        start_time = time.time()
        
        try:
            query = """
            CALL gds.louvain.stream({
                nodeProjection: 'Node',
                relationshipProjection: {
                    RELATIONSHIP: {
                        type: 'RELATIONSHIP',
                        properties: ['strength', 'confidence']
                    }
                },
                relationshipWeightProperty: 'strength'
            })
            YIELD nodeId, communityId
            WITH communityId, collect(nodeId) as community_nodes
            WHERE size(community_nodes) >= $min_size
            RETURN communityId, community_nodes
            ORDER BY size(community_nodes) DESC
            """
            
            with self.driver.session() as session:
                result = session.run(query, {'min_size': min_community_size})
                
                communities = []
                for record in result:
                    community_nodes = record['community_nodes']
                    communities.append(community_nodes)
                
                self._update_metrics(start_time, True)
                logger.info(f"✅ 커뮤니티 탐지 완료: {len(communities)}개 커뮤니티")
                return communities
                
        except Exception as e:
            self._update_metrics(start_time, False)
            logger.error(f"❌ 커뮤니티 탐지 실패: {e}")
            raise
    
    async def recommendation_engine(self, 
                                  node_id: str,
                                  recommendation_type: str = "collaborative",
                                  limit: int = 10) -> List[Dict[str, Any]]:
        """추천 엔진"""
        start_time = time.time()
        
        try:
            if recommendation_type == "collaborative":
                query = """
                MATCH (user)-[r1:RELATIONSHIP]-(item)
                MATCH (other)-[r2:RELATIONSHIP]-(item)
                WHERE user.id = $node_id AND other.id <> $node_id
                AND r1.strength > 0.7 AND r2.strength > 0.7
                WITH other, count(item) as common_items, avg(r2.strength) as avg_strength
                ORDER BY common_items DESC, avg_strength DESC
                LIMIT $limit
                RETURN other.id as recommended_node_id, other.properties as properties,
                       common_items, avg_strength as confidence
                """
            elif recommendation_type == "content_based":
                query = """
                MATCH (source)-[r:RELATIONSHIP]-(target)
                WHERE source.id = $node_id
                WITH target, r.strength * r.confidence as score
                ORDER BY score DESC
                LIMIT $limit
                RETURN target.id as recommended_node_id, target.properties as properties,
                       score as confidence
                """
            else:  # hybrid
                query = """
                MATCH (source)-[r:RELATIONSHIP]-(target)
                WHERE source.id = $node_id
                WITH target, r.strength * r.confidence as direct_score
                
                MATCH (source)-[r1:RELATIONSHIP]-(intermediate)-[r2:RELATIONSHIP]-(target)
                WHERE intermediate.id <> target.id
                WITH target, direct_score, avg(r1.strength * r1.confidence * r2.strength * r2.confidence) as indirect_score
                
                WITH target, direct_score, indirect_score,
                     (direct_score * 0.7 + indirect_score * 0.3) as hybrid_score
                ORDER BY hybrid_score DESC
                LIMIT $limit
                RETURN target.id as recommended_node_id, target.properties as properties,
                       hybrid_score as confidence
                """
            
            with self.driver.session() as session:
                result = session.run(query, {'node_id': node_id, 'limit': limit})
                
                recommendations = []
                for record in result:
                    recommendation = {
                        'node_id': record['recommended_node_id'],
                        'properties': record['properties'],
                        'confidence': record['confidence'],
                        'type': recommendation_type
                    }
                    recommendations.append(recommendation)
                
                self._update_metrics(start_time, True)
                logger.info(f"✅ 추천 엔진 완료: {len(recommendations)}개 추천")
                return recommendations
                
        except Exception as e:
            self._update_metrics(start_time, False)
            logger.error(f"❌ 추천 엔진 실패: {e}")
            raise
    
    def _parse_search_results(self, result) -> Tuple[List[GraphNode], List[GraphRelationship], List[List[GraphNode]]]:
        """검색 결과 파싱"""
        nodes = []
        relationships = []
        paths = []
        
        for record in result:
            # 노드 파싱
            if 'n' in record:
                node_data = record['n']
                node = GraphNode(
                    id=node_data['id'],
                    labels=node_data.get('labels', []),
                    properties=node_data.get('properties', {}),
                    embedding=node_data.get('embedding'),
                    metadata=node_data.get('metadata', {})
                )
                nodes.append(node)
            
            # 관계 파싱
            if 'r' in record:
                rel_data = record['r']
                relationship = GraphRelationship(
                    id=rel_data['id'],
                    source_node_id=rel_data.get('source_node_id', ''),
                    target_node_id=rel_data.get('target_node_id', ''),
                    relationship_type=rel_data.get('type', ''),
                    properties=rel_data.get('properties', {}),
                    strength=rel_data.get('strength', 1.0),
                    confidence=rel_data.get('confidence', 1.0)
                )
                relationships.append(relationship)
            
            # 경로 파싱
            if 'path' in record:
                path_data = record['path']
                path_nodes = []
                for node_data in path_data.nodes:
                    node = GraphNode(
                        id=node_data['id'],
                        labels=node_data.get('labels', []),
                        properties=node_data.get('properties', {}),
                        metadata=node_data.get('metadata', {})
                    )
                    path_nodes.append(node)
                paths.append(path_nodes)
        
        return nodes, relationships, paths
    
    def _calculate_relevance_score(self, 
                                  query_text: str,
                                  nodes: List[GraphNode],
                                  relationships: List[GraphRelationship],
                                  paths: List[List[GraphNode]]) -> float:
        """관련성 점수 계산"""
        if not nodes and not relationships and not paths:
            return 0.0
        
        scores = []
        
        # 노드 관련성 점수
        for node in nodes:
            node_score = 0.0
            
            # 속성 매칭 점수
            for key, value in node.properties.items():
                if isinstance(value, str) and query_text.lower() in value.lower():
                    node_score += 0.3
            
            # 신뢰도 점수
            node_score += node.confidence_score * 0.4
            
            # 메타데이터 점수
            if node.metadata:
                node_score += 0.1
            
            scores.append(node_score)
        
        # 관계 관련성 점수
        for rel in relationships:
            rel_score = rel.strength * rel.confidence * 0.5
            scores.append(rel_score)
        
        # 경로 관련성 점수
        for path in paths:
            path_score = len(path) * 0.1
            scores.append(path_score)
        
        return np.mean(scores) if scores else 0.0
    
    def _generate_cache_key(self, 
                           query_text: str,
                           filters: SearchFilter,
                           complexity: QueryComplexity,
                           limit: int) -> str:
        """캐시 키 생성"""
        key_data = {
            'query': query_text,
            'filters': filters.__dict__,
            'complexity': complexity.value,
            'limit': limit
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _update_metrics(self, start_time: float, success: bool):
        """성능 메트릭 업데이트"""
        execution_time = time.time() - start_time
        
        self.performance_metrics['total_queries'] += 1
        if success:
            self.performance_metrics['successful_queries'] += 1
        else:
            self.performance_metrics['failed_queries'] += 1
        
        # 평균 실행 시간 업데이트
        total_successful = self.performance_metrics['successful_queries']
        if total_successful > 0:
            current_avg = self.performance_metrics['average_query_time']
            self.performance_metrics['average_query_time'] = (
                (current_avg * (total_successful - 1) + execution_time) / total_successful
            )
        
        self.performance_metrics['total_query_time'] += execution_time
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 반환"""
        return self.performance_metrics.copy()
    
    async def clear_cache(self):
        """쿼리 캐시 정리"""
        self.query_cache.clear()
        logger.info("쿼리 캐시 정리됨")

# 사용 예시
async def main():
    """고급 Neo4j 매니저 테스트"""
    config = {
        'uri': 'neo4j://localhost:7687',
        'username': 'neo4j',
        'password': 'password',
        'connection_pool_size': 50,
        'max_transaction_retries': 3,
        'query_timeout': 30,
        'cache_ttl': 300
    }
    
    manager = AdvancedNeo4jManager(config)
    
    try:
        # 연결
        if await manager.connect():
            print("✅ Neo4j 연결 성공")
            
            # 성능 메트릭 확인
            metrics = await manager.get_performance_metrics()
            print(f"성능 메트릭: {metrics}")
            
    finally:
        await manager.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
