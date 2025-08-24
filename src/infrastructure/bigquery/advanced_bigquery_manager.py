"""
고급 BigQuery 연동 시스템
ARGO Phase 2: 데이터 API, 복잡한 쿼리, 실시간 분석 지원
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
import pandas as pd
import numpy as np
from google.cloud import bigquery
from google.cloud.bigquery import SchemaField, Table, Dataset
from google.cloud.exceptions import NotFound, GoogleCloudError
import google.auth

logger = logging.getLogger(__name__)

class QueryType(Enum):
    """쿼리 타입 정의"""
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    CREATE_TABLE = "create_table"
    CREATE_DATASET = "create_dataset"
    DROP_TABLE = "drop_table"
    DROP_DATASET = "drop_dataset"
    ANALYTICS = "analytics"
    ML_PREDICTION = "ml_prediction"

class DataFormat(Enum):
    """데이터 포맷 정의"""
    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"
    AVRO = "avro"
    ORC = "orc"

@dataclass
class BigQueryTable:
    """BigQuery 테이블 정보"""
    table_id: str
    dataset_id: str
    project_id: str
    schema: List[SchemaField]
    description: str = ""
    labels: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    row_count: int = 0
    size_bytes: int = 0

@dataclass
class QueryResult:
    """쿼리 실행 결과"""
    query_id: str
    query_type: QueryType
    execution_time: float
    rows_affected: int
    data: Optional[List[Dict[str, Any]]] = None
    schema: Optional[List[SchemaField]] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AnalyticsQuery:
    """분석 쿼리 정의"""
    query_id: str
    name: str
    description: str
    sql_query: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    expected_columns: List[str] = field(default_factory=list)
    cache_ttl: int = 300  # 5분
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)

class AdvancedBigQueryManager:
    """고급 BigQuery 연동 시스템"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client: Optional[bigquery.Client] = None
        self.project_id = config.get('project_id')
        self.dataset_id = config.get('dataset_id', 'argo_analytics')
        self.location = config.get('location', 'US')
        
        # 성능 메트릭
        self.performance_metrics = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'average_query_time': 0.0,
            'total_query_time': 0.0,
            'total_data_processed': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        # 쿼리 캐시
        self.query_cache: Dict[str, Any] = {}
        self.cache_ttl = config.get('cache_ttl', 300)
        
        # 분석 쿼리 저장소
        self.analytics_queries: Dict[str, AnalyticsQuery] = {}
        
        # 스트리밍 설정
        self.streaming_enabled = config.get('streaming_enabled', True)
        self.streaming_buffer_size = config.get('streaming_buffer_size', 1000)
        self.streaming_buffer: List[Dict[str, Any]] = []
        
        logger.info("고급 BigQuery 매니저 초기화됨")
    
    async def connect(self) -> bool:
        """BigQuery 클라이언트 연결"""
        try:
            # 인증 설정
            if 'credentials_path' in self.config:
                self.client = bigquery.Client.from_service_account_json(
                    self.config['credentials_path'],
                    project=self.project_id
                )
            else:
                # 기본 인증 사용
                credentials, project = google.auth.default()
                self.client = bigquery.Client(credentials=credentials, project=project)
            
            # 프로젝트 확인
            project = self.client.project
            logger.info(f"✅ BigQuery 연결 성공: {project}")
            
            # 데이터셋 생성 확인
            await self._ensure_dataset_exists()
            
            # 기본 테이블 스키마 생성
            await self._create_default_tables()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ BigQuery 연결 실패: {e}")
            return False
    
    async def disconnect(self):
        """연결 해제"""
        if self.client:
            # 스트리밍 버퍼 플러시
            if self.streaming_buffer:
                await self._flush_streaming_buffer()
            
            self.client.close()
            logger.info("BigQuery 연결 해제됨")
    
    async def _ensure_dataset_exists(self):
        """데이터셋 존재 확인 및 생성"""
        try:
            dataset_ref = self.client.dataset(self.dataset_id)
            dataset = Dataset(dataset_ref)
            dataset.location = self.location
            
            try:
                self.client.get_dataset(dataset_ref)
                logger.info(f"데이터셋 존재 확인: {self.dataset_id}")
            except NotFound:
                dataset = self.client.create_dataset(dataset, timeout=30)
                logger.info(f"✅ 데이터셋 생성됨: {self.dataset_id}")
                
        except Exception as e:
            logger.error(f"데이터셋 확인/생성 실패: {e}")
            raise
    
    async def _create_default_tables(self):
        """기본 테이블 스키마 생성"""
        default_tables = {
            'argo_nodes': [
                SchemaField("node_id", "STRING", mode="REQUIRED"),
                SchemaField("node_type", "STRING", mode="REQUIRED"),
                SchemaField("properties", "JSON", mode="NULLABLE"),
                SchemaField("embedding", "FLOAT64", mode="REPEATED"),
                SchemaField("metadata", "JSON", mode="NULLABLE"),
                SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
                SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
                SchemaField("confidence_score", "FLOAT64", mode="REQUIRED"),
                SchemaField("source_system", "STRING", mode="REQUIRED")
            ],
            'argo_relationships': [
                SchemaField("relationship_id", "STRING", mode="REQUIRED"),
                SchemaField("source_node_id", "STRING", mode="REQUIRED"),
                SchemaField("target_node_id", "STRING", mode="REQUIRED"),
                SchemaField("relationship_type", "STRING", mode="REQUIRED"),
                SchemaField("properties", "JSON", mode="NULLABLE"),
                SchemaField("strength", "FLOAT64", mode="REQUIRED"),
                SchemaField("confidence", "FLOAT64", mode="REQUIRED"),
                SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
                SchemaField("metadata", "JSON", mode="NULLABLE")
            ],
            'argo_analytics': [
                SchemaField("query_id", "STRING", mode="REQUIRED"),
                SchemaField("query_name", "STRING", mode="REQUIRED"),
                SchemaField("execution_time", "FLOAT64", mode="REQUIRED"),
                SchemaField("rows_processed", "INT64", mode="REQUIRED"),
                SchemaField("result_data", "JSON", mode="NULLABLE"),
                SchemaField("executed_at", "TIMESTAMP", mode="REQUIRED"),
                SchemaField("user_id", "STRING", mode="NULLABLE"),
                SchemaField("session_id", "STRING", mode="NULLABLE")
            ],
            'argo_sync_log': [
                SchemaField("sync_id", "STRING", mode="REQUIRED"),
                SchemaField("source_system", "STRING", mode="REQUIRED"),
                SchemaField("target_system", "STRING", mode="REQUIRED"),
                SchemaField("operation_type", "STRING", mode="REQUIRED"),
                SchemaField("data_hash", "STRING", mode="REQUIRED"),
                SchemaField("status", "STRING", mode="REQUIRED"),
                SchemaField("execution_time", "FLOAT64", mode="REQUIRED"),
                SchemaField("error_message", "STRING", mode="NULLABLE"),
                SchemaField("created_at", "TIMESTAMP", mode="REQUIRED")
            ]
        }
        
        for table_name, schema in default_tables.items():
            await self._ensure_table_exists(table_name, schema)
    
    async def _ensure_table_exists(self, table_name: str, schema: List[SchemaField]):
        """테이블 존재 확인 및 생성"""
        try:
            table_id = f"{self.project_id}.{self.dataset_id}.{table_name}"
            table_ref = self.client.get_table(table_id)
            logger.debug(f"테이블 존재 확인: {table_name}")
            
        except NotFound:
            # 테이블 생성
            table = Table(table_id, schema=schema)
            table = self.client.create_table(table)
            logger.info(f"✅ 테이블 생성됨: {table_name}")
            
        except Exception as e:
            logger.error(f"테이블 확인/생성 실패: {table_name} - {e}")
    
    async def execute_query(self, 
                           sql_query: str,
                           query_type: QueryType = QueryType.SELECT,
                           parameters: Optional[Dict[str, Any]] = None,
                           use_cache: bool = True) -> QueryResult:
        """고급 쿼리 실행"""
        start_time = time.time()
        query_id = str(uuid.uuid4())
        
        try:
            # 캐시 확인
            if use_cache and query_type == QueryType.SELECT:
                cache_key = self._generate_cache_key(sql_query, parameters)
                if cache_key in self.query_cache:
                    cached_result = self.query_cache[cache_key]
                    if time.time() - cached_result['timestamp'] < self.cache_ttl:
                        self.performance_metrics['cache_hits'] += 1
                        return cached_result['result']
            
            self.performance_metrics['cache_misses'] += 1
            
            # 쿼리 실행
            if query_type == QueryType.SELECT:
                result = await self._execute_select_query(sql_query, parameters)
            elif query_type == QueryType.INSERT:
                result = await self._execute_insert_query(sql_query, parameters)
            elif query_type == QueryType.UPDATE:
                result = await self._execute_update_query(sql_query, parameters)
            elif query_type == QueryType.DELETE:
                result = await self._execute_delete_query(sql_query, parameters)
            elif query_type == QueryType.ANALYTICS:
                result = await self._execute_analytics_query(sql_query, parameters)
            else:
                raise ValueError(f"지원하지 않는 쿼리 타입: {query_type}")
            
            # 결과 생성
            query_result = QueryResult(
                query_id=query_id,
                query_type=query_type,
                execution_time=time.time() - start_time,
                rows_affected=result.get('rows_affected', 0),
                data=result.get('data'),
                schema=result.get('schema'),
                metadata={'sql_query': sql_query, 'parameters': parameters}
            )
            
            # 캐시에 저장 (SELECT 쿼리만)
            if use_cache and query_type == QueryType.SELECT:
                cache_key = self._generate_cache_key(sql_query, parameters)
                self.query_cache[cache_key] = {
                    'result': query_result,
                    'timestamp': time.time()
                }
            
            # 성능 메트릭 업데이트
            self._update_metrics(start_time, True, query_result.rows_affected)
            
            logger.info(f"✅ 쿼리 실행 완료: {query_type.value} - {query_result.rows_affected}행")
            return query_result
            
        except Exception as e:
            self._update_metrics(start_time, False, 0)
            logger.error(f"❌ 쿼리 실행 실패: {e}")
            
            return QueryResult(
                query_id=query_id,
                query_type=query_type,
                execution_time=time.time() - start_time,
                rows_affected=0,
                error_message=str(e),
                metadata={'sql_query': sql_query, 'parameters': parameters}
            )
    
    async def _execute_select_query(self, sql_query: str, parameters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """SELECT 쿼리 실행"""
        try:
            # 쿼리 실행
            query_job = self.client.query(sql_query, job_config=bigquery.QueryJobConfig(
                query_parameters=self._convert_parameters(parameters) if parameters else None
            ))
            
            # 결과 수집
            results = []
            for row in query_job:
                row_dict = dict(row.items())
                results.append(row_dict)
            
            return {
                'data': results,
                'schema': query_job.schema,
                'rows_affected': len(results)
            }
            
        except Exception as e:
            logger.error(f"SELECT 쿼리 실행 실패: {e}")
            raise
    
    async def _execute_insert_query(self, sql_query: str, parameters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """INSERT 쿼리 실행"""
        try:
            # 쿼리 실행
            query_job = self.client.query(sql_query, job_config=bigquery.QueryJobConfig(
                query_parameters=self._convert_parameters(parameters) if parameters else None
            ))
            
            # 완료 대기
            query_job.result()
            
            return {
                'rows_affected': query_job.num_dml_affected_rows or 0
            }
            
        except Exception as e:
            logger.error(f"INSERT 쿼리 실행 실패: {e}")
            raise
    
    async def _execute_update_query(self, sql_query: str, parameters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """UPDATE 쿼리 실행"""
        try:
            # 쿼리 실행
            query_job = self.client.query(sql_query, job_config=bigquery.QueryJobConfig(
                query_parameters=self._convert_parameters(parameters) if parameters else None
            ))
            
            # 완료 대기
            query_job.result()
            
            return {
                'rows_affected': query_job.num_dml_affected_rows or 0
            }
            
        except Exception as e:
            logger.error(f"UPDATE 쿼리 실행 실패: {e}")
            raise
    
    async def _execute_delete_query(self, sql_query: str, parameters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """DELETE 쿼리 실행"""
        try:
            # 쿼리 실행
            query_job = self.client.query(sql_query, job_config=bigquery.QueryJobConfig(
                query_parameters=self._convert_parameters(parameters) if parameters else None
            ))
            
            # 완료 대기
            query_job.result()
            
            return {
                'rows_affected': query_job.num_dml_affected_rows or 0
            }
            
        except Exception as e:
            logger.error(f"DELETE 쿼리 실행 실패: {e}")
            raise
    
    async def _execute_analytics_query(self, sql_query: str, parameters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """분석 쿼리 실행"""
        try:
            # 쿼리 실행
            query_job = self.client.query(sql_query, job_config=bigquery.QueryJobConfig(
                query_parameters=self._convert_parameters(parameters) if parameters else None,
                use_legacy_sql=False
            ))
            
            # 결과 수집
            results = []
            for row in query_job:
                row_dict = dict(row.items())
                results.append(row_dict)
            
            return {
                'data': results,
                'schema': query_job.schema,
                'rows_affected': len(results)
            }
            
        except Exception as e:
            logger.error(f"분석 쿼리 실행 실패: {e}")
            raise
    
    async def insert_data(self, 
                         table_name: str,
                         data: List[Dict[str, Any]],
                         batch_size: int = 1000) -> int:
        """데이터 삽입 (배치 처리)"""
        start_time = time.time()
        total_rows = 0
        
        try:
            table_id = f"{self.project_id}.{self.dataset_id}.{table_name}"
            
            # 배치별 처리
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                
                # 스트리밍 삽입
                if self.streaming_enabled:
                    errors = self.client.insert_rows_json(table_id, batch)
                    if errors:
                        logger.error(f"스트리밍 삽입 오류: {errors}")
                        raise Exception(f"스트리밍 삽입 실패: {errors}")
                else:
                    # 로드 작업 사용
                    job_config = bigquery.LoadJobConfig(
                        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                        autodetect=True
                    )
                    
                    # 임시 파일로 저장 후 로드
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
                        for row in batch:
                            f.write(json.dumps(row) + '\n')
                        temp_file = f.name
                    
                    with open(temp_file, 'rb') as f:
                        job = self.client.load_table_from_file(
                            f, table_id, job_config=job_config
                        )
                        job.result()
                    
                    # 임시 파일 삭제
                    import os
                    os.unlink(temp_file)
                
                total_rows += len(batch)
                logger.debug(f"배치 삽입 완료: {len(batch)}행")
            
            self._update_metrics(start_time, True, total_rows)
            logger.info(f"✅ 데이터 삽입 완료: {total_rows}행")
            return total_rows
            
        except Exception as e:
            self._update_metrics(start_time, False, 0)
            logger.error(f"❌ 데이터 삽입 실패: {e}")
            raise
    
    async def stream_data(self, 
                         table_name: str,
                         data: Dict[str, Any]) -> bool:
        """실시간 데이터 스트리밍"""
        try:
            # 스트리밍 버퍼에 추가
            self.streaming_buffer.append({
                'table_name': table_name,
                'data': data,
                'timestamp': datetime.now()
            })
            
            # 버퍼 크기 확인
            if len(self.streaming_buffer) >= self.streaming_buffer_size:
                await self._flush_streaming_buffer()
            
            return True
            
        except Exception as e:
            logger.error(f"스트리밍 데이터 추가 실패: {e}")
            return False
    
    async def _flush_streaming_buffer(self):
        """스트리밍 버퍼 플러시"""
        if not self.streaming_buffer:
            return
        
        try:
            # 테이블별로 그룹화
            table_groups = defaultdict(list)
            for item in self.streaming_buffer:
                table_name = item['table_name']
                table_groups[table_name].append(item['data'])
            
            # 각 테이블에 배치 삽입
            for table_name, data_batch in table_groups.items():
                await self.insert_data(table_name, data_batch)
            
            # 버퍼 클리어
            self.streaming_buffer.clear()
            logger.info("스트리밍 버퍼 플러시 완료")
            
        except Exception as e:
            logger.error(f"스트리밍 버퍼 플러시 실패: {e}")
    
    async def create_analytics_query(self, 
                                   name: str,
                                   description: str,
                                   sql_query: str,
                                   parameters: Optional[Dict[str, Any]] = None,
                                   expected_columns: Optional[List[str]] = None,
                                   cache_ttl: int = 300) -> str:
        """분석 쿼리 생성"""
        try:
            query_id = str(uuid.uuid4())
            
            analytics_query = AnalyticsQuery(
                query_id=query_id,
                name=name,
                description=description,
                sql_query=sql_query,
                parameters=parameters or {},
                expected_columns=expected_columns or [],
                cache_ttl=cache_ttl
            )
            
            self.analytics_queries[query_id] = analytics_query
            
            # BigQuery에 저장
            await self._save_analytics_query(analytics_query)
            
            logger.info(f"✅ 분석 쿼리 생성됨: {name} ({query_id})")
            return query_id
            
        except Exception as e:
            logger.error(f"❌ 분석 쿼리 생성 실패: {e}")
            raise
    
    async def execute_analytics_query(self, 
                                    query_id: str,
                                    parameters: Optional[Dict[str, Any]] = None) -> QueryResult:
        """저장된 분석 쿼리 실행"""
        try:
            if query_id not in self.analytics_queries:
                raise ValueError(f"분석 쿼리를 찾을 수 없음: {query_id}")
            
            analytics_query = self.analytics_queries[query_id]
            
            # 파라미터 병합
            merged_parameters = analytics_query.parameters.copy()
            if parameters:
                merged_parameters.update(parameters)
            
            # 쿼리 실행
            result = await self.execute_query(
                analytics_query.sql_query,
                QueryType.ANALYTICS,
                merged_parameters,
                use_cache=True
            )
            
            # 실행 로그 저장
            await self._log_analytics_execution(analytics_query, result, merged_parameters)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 분석 쿼리 실행 실패: {e}")
            raise
    
    async def get_table_info(self, table_name: str) -> Optional[BigQueryTable]:
        """테이블 정보 조회"""
        try:
            table_id = f"{self.project_id}.{self.dataset_id}.{table_name}"
            table = self.client.get_table(table_id)
            
            return BigQueryTable(
                table_id=table.table_id,
                dataset_id=table.dataset_id,
                project_id=table.project,
                schema=table.schema,
                description=table.description or "",
                labels=table.labels or {},
                created_at=table.created,
                updated_at=table.modified,
                row_count=table.num_rows or 0,
                size_bytes=table.num_bytes or 0
            )
            
        except NotFound:
            logger.warning(f"테이블을 찾을 수 없음: {table_name}")
            return None
        except Exception as e:
            logger.error(f"테이블 정보 조회 실패: {e}")
            return None
    
    async def export_data(self, 
                          table_name: str,
                          destination_uri: str,
                          format: DataFormat = DataFormat.CSV) -> bool:
        """데이터 내보내기"""
        try:
            table_id = f"{self.project_id}.{self.dataset_id}.{table_name}"
            
            # 내보내기 작업 설정
            job_config = bigquery.ExtractJobConfig()
            
            if format == DataFormat.CSV:
                job_config.destination_format = bigquery.DestinationFormat.CSV
            elif format == DataFormat.PARQUET:
                job_config.destination_format = bigquery.DestinationFormat.PARQUET
            elif format == DataFormat.AVRO:
                job_config.destination_format = bigquery.DestinationFormat.AVRO
            elif format == DataFormat.ORC:
                job_config.destination_format = bigquery.DestinationFormat.ORQUET
            
            # 내보내기 작업 실행
            extract_job = self.client.extract_table(
                table_id, destination_uri, job_config=job_config
            )
            extract_job.result()
            
            logger.info(f"✅ 데이터 내보내기 완료: {table_name} -> {destination_uri}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 데이터 내보내기 실패: {e}")
            return False
    
    def _convert_parameters(self, parameters: Optional[Dict[str, Any]]) -> List[bigquery.ScalarQueryParameter]:
        """파라미터를 BigQuery 형식으로 변환"""
        if not parameters:
            return []
        
        converted_params = []
        for key, value in parameters.items():
            if isinstance(value, str):
                param_type = 'STRING'
            elif isinstance(value, int):
                param_type = 'INT64'
            elif isinstance(value, float):
                param_type = 'FLOAT64'
            elif isinstance(value, bool):
                param_type = 'BOOL'
            elif isinstance(value, datetime):
                param_type = 'TIMESTAMP'
            else:
                param_type = 'STRING'
                value = str(value)
            
            converted_params.append(
                bigquery.ScalarQueryParameter(key, param_type, value)
            )
        
        return converted_params
    
    async def _save_analytics_query(self, analytics_query: AnalyticsQuery):
        """분석 쿼리를 BigQuery에 저장"""
        try:
            table_id = f"{self.project_id}.{self.dataset_id}.argo_analytics_queries"
            
            # 테이블이 없으면 생성
            try:
                self.client.get_table(table_id)
            except NotFound:
                schema = [
                    SchemaField("query_id", "STRING", mode="REQUIRED"),
                    SchemaField("name", "STRING", mode="REQUIRED"),
                    SchemaField("description", "STRING", mode="NULLABLE"),
                    SchemaField("sql_query", "STRING", mode="REQUIRED"),
                    SchemaField("parameters", "JSON", mode="NULLABLE"),
                    SchemaField("expected_columns", "STRING", mode="REPEATED"),
                    SchemaField("cache_ttl", "INT64", mode="REQUIRED"),
                    SchemaField("is_active", "BOOL", mode="REQUIRED"),
                    SchemaField("created_at", "TIMESTAMP", mode="REQUIRED")
                ]
                
                table = Table(table_id, schema=schema)
                self.client.create_table(table)
            
            # 쿼리 저장
            row_data = {
                'query_id': analytics_query.query_id,
                'name': analytics_query.name,
                'description': analytics_query.description,
                'sql_query': analytics_query.sql_query,
                'parameters': json.dumps(analytics_query.parameters),
                'expected_columns': analytics_query.expected_columns,
                'cache_ttl': analytics_query.cache_ttl,
                'is_active': analytics_query.is_active,
                'created_at': analytics_query.created_at.isoformat()
            }
            
            errors = self.client.insert_rows_json(table_id, [row_data])
            if errors:
                logger.error(f"분석 쿼리 저장 오류: {errors}")
            
        except Exception as e:
            logger.error(f"분석 쿼리 저장 실패: {e}")
    
    async def _log_analytics_execution(self, 
                                     analytics_query: AnalyticsQuery,
                                     result: QueryResult,
                                     parameters: Dict[str, Any]):
        """분석 쿼리 실행 로그 저장"""
        try:
            table_id = f"{self.project_id}.{self.dataset_id}.argo_analytics"
            
            row_data = {
                'query_id': analytics_query.query_id,
                'query_name': analytics_query.name,
                'execution_time': result.execution_time,
                'rows_processed': result.rows_affected,
                'result_data': json.dumps(result.data) if result.data else None,
                'executed_at': datetime.now().isoformat(),
                'user_id': 'system',
                'session_id': str(uuid.uuid4())
            }
            
            errors = self.client.insert_rows_json(table_id, [row_data])
            if errors:
                logger.error(f"분석 실행 로그 저장 오류: {errors}")
            
        except Exception as e:
            logger.error(f"분석 실행 로그 저장 실패: {e}")
    
    def _generate_cache_key(self, sql_query: str, parameters: Optional[Dict[str, Any]]) -> str:
        """캐시 키 생성"""
        key_data = {
            'sql': sql_query,
            'params': parameters or {}
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _update_metrics(self, start_time: float, success: bool, rows_affected: int):
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
        self.performance_metrics['total_data_processed'] += rows_affected
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 반환"""
        return self.performance_metrics.copy()
    
    async def clear_cache(self):
        """쿼리 캐시 정리"""
        self.query_cache.clear()
        logger.info("쿼리 캐시 정리됨")

# 사용 예시
async def main():
    """고급 BigQuery 매니저 테스트"""
    config = {
        'project_id': 'your-project-id',
        'dataset_id': 'argo_analytics',
        'location': 'US',
        'streaming_enabled': True,
        'streaming_buffer_size': 1000,
        'cache_ttl': 300
    }
    
    manager = AdvancedBigQueryManager(config)
    
    try:
        # 연결
        if await manager.connect():
            print("✅ BigQuery 연결 성공")
            
            # 성능 메트릭 확인
            metrics = await manager.get_performance_metrics()
            print(f"성능 메트릭: {metrics}")
            
    finally:
        await manager.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
