"""
BigQuery Data Warehouse Manager for ARGO Phase 2
Manages data warehouse operations and analytics
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
import pandas as pd
import hashlib

logger = logging.getLogger(__name__)


# BigQuery Schema Definitions
BIGQUERY_SCHEMAS = {
    "events": [
        bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("event_type", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("source", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("agent_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("session_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("content", "JSON", mode="NULLABLE"),
        bigquery.SchemaField("metadata", "JSON", mode="NULLABLE"),
    ],
    "agent_activities": [
        bigquery.SchemaField("activity_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("agent_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("activity_type", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("task_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("duration_ms", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("success", "BOOLEAN", mode="NULLABLE"),
        bigquery.SchemaField("details", "JSON", mode="NULLABLE"),
    ],
    "knowledge_base": [
        bigquery.SchemaField("knowledge_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("updated_at", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("type", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("content", "JSON", mode="REQUIRED"),
        bigquery.SchemaField("embeddings", "FLOAT64", mode="REPEATED"),
        bigquery.SchemaField("confidence", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("usage_count", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("metadata", "JSON", mode="NULLABLE"),
    ],
    "patterns": [
        bigquery.SchemaField("pattern_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("discovered_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("pattern_type", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("occurrences", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("success_rate", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("pattern_data", "JSON", mode="REQUIRED"),
        bigquery.SchemaField("confidence", "FLOAT64", mode="NULLABLE"),
    ],
    "metrics": [
        bigquery.SchemaField("metric_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("metric_type", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("metric_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("value", "FLOAT64", mode="REQUIRED"),
        bigquery.SchemaField("unit", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("dimensions", "JSON", mode="NULLABLE"),
    ],
    "audit_logs": [
        bigquery.SchemaField("log_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("action", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("actor", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("resource_type", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("resource_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("result", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("details", "JSON", mode="NULLABLE"),
    ]
}


@dataclass
class QueryResult:
    """Represents a BigQuery query result"""
    query: str
    rows: List[Dict[str, Any]]
    total_rows: int
    bytes_processed: int
    execution_time_ms: float
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert result to pandas DataFrame"""
        return pd.DataFrame(self.rows)


class BigQueryManager:
    """
    Manages BigQuery data warehouse operations
    Provides high-level interface for data storage and analytics
    """
    
    def __init__(self, project_id: str = None, dataset_id: str = None):
        """
        Initialize BigQuery client
        
        Args:
            project_id: GCP project ID (default from env)
            dataset_id: BigQuery dataset ID (default: argo_warehouse)
        """
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID", "argo-813")
        self.dataset_id = dataset_id or os.getenv("BQ_DATASET_ID", "argo_warehouse")
        
        # Initialize client
        self.client = bigquery.Client(project=self.project_id)
        
        # Initialize dataset and tables
        self._initialize_dataset()
        self._initialize_tables()
        
        logger.info(f"BigQuery manager initialized for {self.project_id}.{self.dataset_id}")
    
    def _initialize_dataset(self):
        """Create dataset if it doesn't exist"""
        dataset_ref = f"{self.project_id}.{self.dataset_id}"
        
        try:
            self.client.get_dataset(dataset_ref)
            logger.debug(f"Dataset {dataset_ref} already exists")
        except NotFound:
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = os.getenv("BQ_LOCATION", "US")
            dataset.description = "ARGO data warehouse for events, knowledge, and analytics"
            
            dataset = self.client.create_dataset(dataset, timeout=30)
            logger.info(f"Created dataset {dataset_ref}")
    
    def _initialize_tables(self):
        """Create tables if they don't exist"""
        for table_name, schema in BIGQUERY_SCHEMAS.items():
            table_ref = f"{self.project_id}.{self.dataset_id}.{table_name}"
            
            try:
                self.client.get_table(table_ref)
                logger.debug(f"Table {table_ref} already exists")
            except NotFound:
                table = bigquery.Table(table_ref, schema=schema)
                
                # Set partitioning for time-based tables
                if table_name in ["events", "agent_activities", "metrics", "audit_logs"]:
                    table.time_partitioning = bigquery.TimePartitioning(
                        type_=bigquery.TimePartitioningType.DAY,
                        field="timestamp"
                    )
                
                table = self.client.create_table(table)
                logger.info(f"Created table {table_ref}")
    
    # Insert Operations
    
    def insert_event(self, event_type: str, content: Dict[str, Any], 
                    source: str = None, agent_id: str = None, 
                    session_id: str = None) -> str:
        """Insert an event into the events table"""
        event_id = self._generate_id(f"{event_type}:{datetime.utcnow().isoformat()}")
        
        row = {
            "event_id": event_id,
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "source": source,
            "agent_id": agent_id,
            "session_id": session_id,
            "content": content,
            "metadata": {
                "inserted_at": datetime.utcnow().isoformat(),
                "version": "1.0"
            }
        }
        
        table_ref = f"{self.project_id}.{self.dataset_id}.events"
        errors = self.client.insert_rows_json(table_ref, [row])
        
        if errors:
            logger.error(f"Failed to insert event: {errors}")
            raise Exception(f"BigQuery insert failed: {errors}")
        
        logger.debug(f"Inserted event {event_id}")
        return event_id
    
    def insert_agent_activity(self, agent_id: str, activity_type: str, 
                             task_id: str = None, duration_ms: int = None,
                             success: bool = True, details: Dict = None) -> str:
        """Record agent activity"""
        activity_id = self._generate_id(f"{agent_id}:{activity_type}:{datetime.utcnow()}")
        
        row = {
            "activity_id": activity_id,
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": agent_id,
            "activity_type": activity_type,
            "task_id": task_id,
            "duration_ms": duration_ms,
            "success": success,
            "details": details or {}
        }
        
        table_ref = f"{self.project_id}.{self.dataset_id}.agent_activities"
        errors = self.client.insert_rows_json(table_ref, [row])
        
        if errors:
            logger.error(f"Failed to insert activity: {errors}")
            raise Exception(f"BigQuery insert failed: {errors}")
        
        return activity_id
    
    def insert_knowledge(self, knowledge_type: str, content: Dict,
                        embeddings: List[float] = None, confidence: float = 1.0) -> str:
        """Insert knowledge into knowledge base"""
        knowledge_id = self._generate_id(f"{knowledge_type}:{json.dumps(content, sort_keys=True)}")
        
        row = {
            "knowledge_id": knowledge_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "type": knowledge_type,
            "content": content,
            "embeddings": embeddings or [],
            "confidence": confidence,
            "usage_count": 0,
            "metadata": {
                "source": "agent_learning",
                "version": "1.0"
            }
        }
        
        table_ref = f"{self.project_id}.{self.dataset_id}.knowledge_base"
        errors = self.client.insert_rows_json(table_ref, [row])
        
        if errors:
            logger.error(f"Failed to insert knowledge: {errors}")
            raise Exception(f"BigQuery insert failed: {errors}")
        
        return knowledge_id
    
    def insert_pattern(self, pattern_type: str, pattern_data: Dict,
                       occurrences: int = 1, success_rate: float = None) -> str:
        """Insert discovered pattern"""
        pattern_id = self._generate_id(f"{pattern_type}:{json.dumps(pattern_data, sort_keys=True)}")
        
        row = {
            "pattern_id": pattern_id,
            "discovered_at": datetime.utcnow().isoformat(),
            "pattern_type": pattern_type,
            "occurrences": occurrences,
            "success_rate": success_rate,
            "pattern_data": pattern_data,
            "confidence": min(occurrences / 10.0, 1.0)  # Confidence based on occurrences
        }
        
        table_ref = f"{self.project_id}.{self.dataset_id}.patterns"
        errors = self.client.insert_rows_json(table_ref, [row])
        
        if errors:
            logger.error(f"Failed to insert pattern: {errors}")
            raise Exception(f"BigQuery insert failed: {errors}")
        
        return pattern_id
    
    def insert_metric(self, metric_type: str, metric_name: str, value: float,
                     unit: str = None, dimensions: Dict = None) -> str:
        """Insert metric data"""
        metric_id = self._generate_id(f"{metric_type}:{metric_name}:{datetime.utcnow()}")
        
        row = {
            "metric_id": metric_id,
            "timestamp": datetime.utcnow().isoformat(),
            "metric_type": metric_type,
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            "dimensions": dimensions or {}
        }
        
        table_ref = f"{self.project_id}.{self.dataset_id}.metrics"
        errors = self.client.insert_rows_json(table_ref, [row])
        
        if errors:
            logger.error(f"Failed to insert metric: {errors}")
            raise Exception(f"BigQuery insert failed: {errors}")
        
        return metric_id
    
    def insert_audit_log(self, action: str, actor: str, resource_type: str = None,
                        resource_id: str = None, result: str = "success",
                        details: Dict = None) -> str:
        """Insert audit log entry"""
        log_id = self._generate_id(f"{action}:{actor}:{datetime.utcnow()}")
        
        row = {
            "log_id": log_id,
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "actor": actor,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "result": result,
            "details": details or {}
        }
        
        table_ref = f"{self.project_id}.{self.dataset_id}.audit_logs"
        errors = self.client.insert_rows_json(table_ref, [row])
        
        if errors:
            logger.error(f"Failed to insert audit log: {errors}")
            raise Exception(f"BigQuery insert failed: {errors}")
        
        return log_id
    
    # Query Operations
    
    def query(self, sql: str, parameters: List[bigquery.ScalarQueryParameter] = None) -> QueryResult:
        """Execute a SQL query"""
        job_config = bigquery.QueryJobConfig()
        if parameters:
            job_config.query_parameters = parameters
        
        start_time = datetime.utcnow()
        query_job = self.client.query(sql, job_config=job_config)
        results = query_job.result()
        
        rows = [dict(row) for row in results]
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return QueryResult(
            query=sql,
            rows=rows,
            total_rows=results.total_rows,
            bytes_processed=query_job.total_bytes_processed,
            execution_time_ms=execution_time
        )
    
    def get_recent_events(self, hours: int = 24, event_type: str = None,
                         agent_id: str = None, limit: int = 100) -> List[Dict]:
        """Get recent events"""
        sql = f"""
        SELECT *
        FROM `{self.project_id}.{self.dataset_id}.events`
        WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours} HOUR)
        """
        
        if event_type:
            sql += f" AND event_type = '{event_type}'"
        if agent_id:
            sql += f" AND agent_id = '{agent_id}'"
        
        sql += f"""
        ORDER BY timestamp DESC
        LIMIT {limit}
        """
        
        result = self.query(sql)
        return result.rows
    
    def get_agent_performance(self, agent_id: str, days: int = 7) -> Dict[str, Any]:
        """Get agent performance metrics"""
        sql = f"""
        SELECT 
            agent_id,
            COUNT(*) as total_activities,
            COUNTIF(success = TRUE) as successful_activities,
            COUNTIF(success = FALSE) as failed_activities,
            AVG(duration_ms) as avg_duration_ms,
            MIN(timestamp) as first_activity,
            MAX(timestamp) as last_activity
        FROM `{self.project_id}.{self.dataset_id}.agent_activities`
        WHERE agent_id = '{agent_id}'
          AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        GROUP BY agent_id
        """
        
        result = self.query(sql)
        if result.rows:
            perf = result.rows[0]
            perf['success_rate'] = perf['successful_activities'] / perf['total_activities'] if perf['total_activities'] > 0 else 0
            return perf
        return {}
    
    def find_similar_knowledge(self, embeddings: List[float], limit: int = 5) -> List[Dict]:
        """Find similar knowledge using embeddings (simplified)"""
        # In production, use vector similarity functions
        sql = f"""
        SELECT *
        FROM `{self.project_id}.{self.dataset_id}.knowledge_base`
        WHERE ARRAY_LENGTH(embeddings) > 0
        ORDER BY usage_count DESC
        LIMIT {limit}
        """
        
        result = self.query(sql)
        return result.rows
    
    def get_patterns(self, pattern_type: str = None, min_confidence: float = 0.5) -> List[Dict]:
        """Get discovered patterns"""
        sql = f"""
        SELECT *
        FROM `{self.project_id}.{self.dataset_id}.patterns`
        WHERE confidence >= {min_confidence}
        """
        
        if pattern_type:
            sql += f" AND pattern_type = '{pattern_type}'"
        
        sql += " ORDER BY confidence DESC, occurrences DESC"
        
        result = self.query(sql)
        return result.rows
    
    def get_metrics_summary(self, metric_type: str, hours: int = 24) -> Dict[str, Any]:
        """Get metrics summary"""
        sql = f"""
        SELECT 
            metric_name,
            COUNT(*) as data_points,
            AVG(value) as avg_value,
            MIN(value) as min_value,
            MAX(value) as max_value,
            STDDEV(value) as std_dev
        FROM `{self.project_id}.{self.dataset_id}.metrics`
        WHERE metric_type = '{metric_type}'
          AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours} HOUR)
        GROUP BY metric_name
        """
        
        result = self.query(sql)
        return {row['metric_name']: row for row in result.rows}
    
    def get_audit_trail(self, actor: str = None, resource_id: str = None,
                        days: int = 7) -> List[Dict]:
        """Get audit trail"""
        sql = f"""
        SELECT *
        FROM `{self.project_id}.{self.dataset_id}.audit_logs`
        WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        """
        
        if actor:
            sql += f" AND actor = '{actor}'"
        if resource_id:
            sql += f" AND resource_id = '{resource_id}'"
        
        sql += " ORDER BY timestamp DESC"
        
        result = self.query(sql)
        return result.rows
    
    # Analytics Operations
    
    def analyze_event_patterns(self, days: int = 7) -> Dict[str, Any]:
        """Analyze event patterns"""
        sql = f"""
        WITH event_stats AS (
            SELECT 
                event_type,
                DATE(timestamp) as event_date,
                EXTRACT(HOUR FROM timestamp) as event_hour,
                COUNT(*) as event_count
            FROM `{self.project_id}.{self.dataset_id}.events`
            WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
            GROUP BY event_type, event_date, event_hour
        )
        SELECT 
            event_type,
            COUNT(DISTINCT event_date) as active_days,
            SUM(event_count) as total_events,
            AVG(event_count) as avg_events_per_hour,
            MAX(event_count) as peak_events
        FROM event_stats
        GROUP BY event_type
        ORDER BY total_events DESC
        """
        
        result = self.query(sql)
        return {"event_patterns": result.rows}
    
    def calculate_agent_collaboration_metrics(self) -> Dict[str, Any]:
        """Calculate agent collaboration metrics"""
        sql = f"""
        WITH agent_pairs AS (
            SELECT 
                a1.agent_id as agent1,
                a2.agent_id as agent2,
                COUNT(*) as interactions
            FROM `{self.project_id}.{self.dataset_id}.agent_activities` a1
            JOIN `{self.project_id}.{self.dataset_id}.agent_activities` a2
                ON a1.task_id = a2.task_id
                AND a1.agent_id < a2.agent_id
            WHERE a1.timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
            GROUP BY agent1, agent2
        )
        SELECT *
        FROM agent_pairs
        ORDER BY interactions DESC
        """
        
        result = self.query(sql)
        return {"collaborations": result.rows}
    
    def get_knowledge_usage_stats(self) -> Dict[str, Any]:
        """Get knowledge usage statistics"""
        sql = f"""
        SELECT 
            type as knowledge_type,
            COUNT(*) as total_items,
            AVG(usage_count) as avg_usage,
            MAX(usage_count) as max_usage,
            AVG(confidence) as avg_confidence
        FROM `{self.project_id}.{self.dataset_id}.knowledge_base`
        GROUP BY type
        ORDER BY total_items DESC
        """
        
        result = self.query(sql)
        return {"knowledge_stats": result.rows}
    
    # Maintenance Operations
    
    def cleanup_old_data(self, table_name: str, days: int) -> int:
        """Delete old data from a table"""
        if table_name not in BIGQUERY_SCHEMAS:
            raise ValueError(f"Invalid table name: {table_name}")
        
        sql = f"""
        DELETE FROM `{self.project_id}.{self.dataset_id}.{table_name}`
        WHERE timestamp < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        """
        
        query_job = self.client.query(sql)
        query_job.result()
        
        return query_job.num_dml_affected_rows
    
    def optimize_tables(self) -> Dict[str, Any]:
        """Get table optimization recommendations"""
        sql = f"""
        SELECT 
            table_name,
            row_count,
            ROUND(size_bytes / POW(10, 9), 2) as size_gb,
            TIMESTAMP_MILLIS(creation_time) as created_at,
            TIMESTAMP_MILLIS(last_modified_time) as last_modified
        FROM `{self.project_id}.{self.dataset_id}.__TABLES__`
        ORDER BY size_bytes DESC
        """
        
        result = self.query(sql)
        
        recommendations = []
        for table in result.rows:
            if table['size_gb'] > 1:
                recommendations.append({
                    "table": table['table_name'],
                    "recommendation": "Consider partitioning or clustering",
                    "size_gb": table['size_gb']
                })
        
        return {
            "tables": result.rows,
            "recommendations": recommendations
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get BigQuery statistics"""
        stats = {}
        
        for table_name in BIGQUERY_SCHEMAS.keys():
            sql = f"""
            SELECT COUNT(*) as row_count
            FROM `{self.project_id}.{self.dataset_id}.{table_name}`
            """
            
            try:
                result = self.query(sql)
                stats[table_name] = result.rows[0]['row_count'] if result.rows else 0
            except Exception as e:
                logger.error(f"Error getting stats for {table_name}: {e}")
                stats[table_name] = 0
        
        return stats
    
    def _generate_id(self, content: str) -> str:
        """Generate unique ID from content"""
        return hashlib.md5(content.encode()).hexdigest()