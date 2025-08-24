"""
Neo4j Graph Database Manager for ARGO Phase 2
Manages knowledge graph with nodes and relationships
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from neo4j import GraphDatabase, Transaction
from neo4j.exceptions import Neo4jError
import hashlib

logger = logging.getLogger(__name__)


# Graph Schema Definitions
GRAPH_SCHEMA = {
    "nodes": {
        "Agent": {
            "properties": ["agent_id", "type", "status", "created_at", "capabilities"],
            "constraints": ["agent_id"]
        },
        "Goal": {
            "properties": ["goal_id", "description", "status", "priority", "created_at", "deadline"],
            "constraints": ["goal_id"]
        },
        "Task": {
            "properties": ["task_id", "type", "status", "created_at", "completed_at", "result"],
            "constraints": ["task_id"]
        },
        "Knowledge": {
            "properties": ["knowledge_id", "type", "content", "confidence", "created_at", "embeddings"],
            "constraints": ["knowledge_id"],
            "indexes": ["type", "created_at"]
        },
        "Context": {
            "properties": ["context_id", "session_id", "type", "timestamp", "content"],
            "constraints": ["context_id"],
            "indexes": ["session_id", "timestamp"]
        },
        "Pattern": {
            "properties": ["pattern_id", "type", "occurrences", "success_rate", "learned_at"],
            "constraints": ["pattern_id"],
            "indexes": ["type", "success_rate"]
        },
        "Resource": {
            "properties": ["resource_id", "type", "status", "owner", "locked_at"],
            "constraints": ["resource_id"]
        },
        "Director": {
            "properties": ["director_id", "preferences", "style", "created_at"],
            "constraints": ["director_id"]
        }
    },
    "relationships": {
        "ASSIGNED_TO": {
            "from": "Task",
            "to": "Agent",
            "properties": ["assigned_at", "priority"]
        },
        "CREATED_BY": {
            "from": ["Goal", "Task"],
            "to": "Director",
            "properties": ["created_at"]
        },
        "DECOMPOSED_INTO": {
            "from": "Goal",
            "to": "Task",
            "properties": ["step_order", "dependency"]
        },
        "DEPENDS_ON": {
            "from": "Task",
            "to": "Task",
            "properties": ["dependency_type"]
        },
        "LEARNED_FROM": {
            "from": "Pattern",
            "to": "Task",
            "properties": ["learning_score"]
        },
        "USES_KNOWLEDGE": {
            "from": ["Agent", "Task"],
            "to": "Knowledge",
            "properties": ["usage_count", "relevance_score"]
        },
        "IN_CONTEXT": {
            "from": ["Task", "Knowledge"],
            "to": "Context",
            "properties": ["relevance"]
        },
        "LOCKS": {
            "from": "Agent",
            "to": "Resource",
            "properties": ["locked_at", "ttl"]
        },
        "COLLABORATES_WITH": {
            "from": "Agent",
            "to": "Agent",
            "properties": ["collaboration_count", "success_rate"]
        },
        "SIMILAR_TO": {
            "from": "Knowledge",
            "to": "Knowledge",
            "properties": ["similarity_score"]
        }
    }
}


class Neo4jManager:
    """
    Manages Neo4j graph database operations
    Provides high-level interface for knowledge graph manipulation
    """
    
    def __init__(self, uri: str = None, username: str = None, password: str = None):
        """
        Initialize Neo4j connection
        
        Args:
            uri: Neo4j URI (default from env)
            username: Neo4j username (default from env)
            password: Neo4j password (default from env)
        """
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = username or os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            self.driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {self.uri}")
            
            # Initialize schema
            self._initialize_schema()
            
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
    
    def close(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def _initialize_schema(self):
        """Initialize graph schema with constraints and indexes"""
        with self.driver.session() as session:
            # Create constraints for each node type
            for node_type, config in GRAPH_SCHEMA["nodes"].items():
                for constraint_field in config.get("constraints", []):
                    try:
                        query = f"""
                        CREATE CONSTRAINT {node_type.lower()}_{constraint_field}_unique
                        IF NOT EXISTS
                        FOR (n:{node_type})
                        REQUIRE n.{constraint_field} IS UNIQUE
                        """
                        session.run(query)
                        logger.debug(f"Created constraint for {node_type}.{constraint_field}")
                    except Neo4jError as e:
                        if "already exists" not in str(e).lower():
                            logger.error(f"Error creating constraint: {e}")
                
                # Create indexes
                for index_field in config.get("indexes", []):
                    try:
                        query = f"""
                        CREATE INDEX {node_type.lower()}_{index_field}_index
                        IF NOT EXISTS
                        FOR (n:{node_type})
                        ON (n.{index_field})
                        """
                        session.run(query)
                        logger.debug(f"Created index for {node_type}.{index_field}")
                    except Neo4jError as e:
                        if "already exists" not in str(e).lower():
                            logger.error(f"Error creating index: {e}")
    
    # Node Operations
    
    def create_agent_node(self, agent_id: str, agent_type: str, capabilities: List[str]) -> Dict[str, Any]:
        """Create an Agent node"""
        query = """
        MERGE (a:Agent {agent_id: $agent_id})
        SET a.type = $type,
            a.status = 'active',
            a.created_at = datetime(),
            a.capabilities = $capabilities
        RETURN a
        """
        
        with self.driver.session() as session:
            result = session.run(query, 
                agent_id=agent_id,
                type=agent_type,
                capabilities=capabilities
            )
            record = result.single()
            return dict(record["a"]) if record else None
    
    def create_goal_node(self, goal_id: str, description: str, priority: str, 
                        director_id: str = "director_main") -> Dict[str, Any]:
        """Create a Goal node and link to Director"""
        query = """
        MERGE (d:Director {director_id: $director_id})
        ON CREATE SET d.created_at = datetime()
        
        CREATE (g:Goal {
            goal_id: $goal_id,
            description: $description,
            status: 'pending',
            priority: $priority,
            created_at: datetime()
        })
        
        CREATE (g)-[:CREATED_BY {created_at: datetime()}]->(d)
        
        RETURN g
        """
        
        with self.driver.session() as session:
            result = session.run(query,
                goal_id=goal_id,
                description=description,
                priority=priority,
                director_id=director_id
            )
            record = result.single()
            return dict(record["g"]) if record else None
    
    def create_task_node(self, task_id: str, task_type: str, goal_id: str = None) -> Dict[str, Any]:
        """Create a Task node and optionally link to Goal"""
        query = """
        CREATE (t:Task {
            task_id: $task_id,
            type: $type,
            status: 'pending',
            created_at: datetime()
        })
        
        WITH t
        OPTIONAL MATCH (g:Goal {goal_id: $goal_id})
        WHERE g IS NOT NULL
        CREATE (g)-[:DECOMPOSED_INTO {step_order: 0}]->(t)
        
        RETURN t
        """
        
        with self.driver.session() as session:
            result = session.run(query,
                task_id=task_id,
                type=task_type,
                goal_id=goal_id
            )
            record = result.single()
            return dict(record["t"]) if record else None
    
    def create_knowledge_node(self, knowledge_id: str, knowledge_type: str, 
                             content: Dict, embeddings: List[float] = None) -> Dict[str, Any]:
        """Create a Knowledge node with optional embeddings"""
        query = """
        CREATE (k:Knowledge {
            knowledge_id: $knowledge_id,
            type: $type,
            content: $content,
            confidence: $confidence,
            created_at: datetime(),
            embeddings: $embeddings
        })
        RETURN k
        """
        
        with self.driver.session() as session:
            result = session.run(query,
                knowledge_id=knowledge_id,
                type=knowledge_type,
                content=json.dumps(content),
                confidence=content.get("confidence", 1.0),
                embeddings=embeddings or []
            )
            record = result.single()
            return dict(record["k"]) if record else None
    
    def create_pattern_node(self, pattern_type: str, pattern_data: Dict) -> Dict[str, Any]:
        """Create a Pattern node from learned behavior"""
        pattern_id = hashlib.md5(
            f"{pattern_type}:{json.dumps(pattern_data, sort_keys=True)}".encode()
        ).hexdigest()[:16]
        
        query = """
        MERGE (p:Pattern {pattern_id: $pattern_id})
        ON CREATE SET 
            p.type = $type,
            p.occurrences = 1,
            p.success_rate = $success_rate,
            p.learned_at = datetime()
        ON MATCH SET
            p.occurrences = p.occurrences + 1,
            p.success_rate = (p.success_rate * p.occurrences + $success_rate) / (p.occurrences + 1)
        RETURN p
        """
        
        with self.driver.session() as session:
            result = session.run(query,
                pattern_id=pattern_id,
                type=pattern_type,
                success_rate=pattern_data.get("success_rate", 1.0)
            )
            record = result.single()
            return dict(record["p"]) if record else None
    
    # Relationship Operations
    
    def assign_task_to_agent(self, task_id: str, agent_id: str, priority: str = "normal") -> bool:
        """Create ASSIGNED_TO relationship between Task and Agent"""
        query = """
        MATCH (t:Task {task_id: $task_id})
        MATCH (a:Agent {agent_id: $agent_id})
        CREATE (t)-[:ASSIGNED_TO {
            assigned_at: datetime(),
            priority: $priority
        }]->(a)
        RETURN t, a
        """
        
        with self.driver.session() as session:
            result = session.run(query,
                task_id=task_id,
                agent_id=agent_id,
                priority=priority
            )
            return result.single() is not None
    
    def create_task_dependency(self, task_id: str, depends_on_id: str) -> bool:
        """Create DEPENDS_ON relationship between tasks"""
        query = """
        MATCH (t1:Task {task_id: $task_id})
        MATCH (t2:Task {task_id: $depends_on_id})
        CREATE (t1)-[:DEPENDS_ON {dependency_type: 'sequential'}]->(t2)
        RETURN t1, t2
        """
        
        with self.driver.session() as session:
            result = session.run(query,
                task_id=task_id,
                depends_on_id=depends_on_id
            )
            return result.single() is not None
    
    def link_knowledge_to_task(self, task_id: str, knowledge_id: str, relevance: float = 1.0) -> bool:
        """Create USES_KNOWLEDGE relationship"""
        query = """
        MATCH (t:Task {task_id: $task_id})
        MATCH (k:Knowledge {knowledge_id: $knowledge_id})
        MERGE (t)-[r:USES_KNOWLEDGE]->(k)
        SET r.usage_count = COALESCE(r.usage_count, 0) + 1,
            r.relevance_score = $relevance
        RETURN t, k
        """
        
        with self.driver.session() as session:
            result = session.run(query,
                task_id=task_id,
                knowledge_id=knowledge_id,
                relevance=relevance
            )
            return result.single() is not None
    
    def record_agent_collaboration(self, agent1_id: str, agent2_id: str, success: bool = True) -> bool:
        """Record collaboration between agents"""
        query = """
        MATCH (a1:Agent {agent_id: $agent1_id})
        MATCH (a2:Agent {agent_id: $agent2_id})
        MERGE (a1)-[c:COLLABORATES_WITH]-(a2)
        SET c.collaboration_count = COALESCE(c.collaboration_count, 0) + 1,
            c.success_count = COALESCE(c.success_count, 0) + CASE WHEN $success THEN 1 ELSE 0 END,
            c.success_rate = CASE 
                WHEN c.collaboration_count > 0 
                THEN c.success_count / c.collaboration_count 
                ELSE 0 
            END
        RETURN a1, a2, c
        """
        
        with self.driver.session() as session:
            result = session.run(query,
                agent1_id=agent1_id,
                agent2_id=agent2_id,
                success=success
            )
            return result.single() is not None
    
    # Query Operations
    
    def get_agent_workload(self, agent_id: str) -> Dict[str, Any]:
        """Get current workload for an agent"""
        query = """
        MATCH (a:Agent {agent_id: $agent_id})
        OPTIONAL MATCH (a)<-[:ASSIGNED_TO]-(t:Task)
        WHERE t.status IN ['pending', 'in_progress']
        WITH a, COUNT(t) as active_tasks, COLLECT(t.task_id) as task_ids
        RETURN {
            agent_id: a.agent_id,
            status: a.status,
            active_tasks: active_tasks,
            task_ids: task_ids
        } as workload
        """
        
        with self.driver.session() as session:
            result = session.run(query, agent_id=agent_id)
            record = result.single()
            return record["workload"] if record else None
    
    def get_task_dependencies(self, task_id: str) -> List[str]:
        """Get all tasks that must complete before this task"""
        query = """
        MATCH (t:Task {task_id: $task_id})-[:DEPENDS_ON]->(dep:Task)
        RETURN COLLECT(dep.task_id) as dependencies
        """
        
        with self.driver.session() as session:
            result = session.run(query, task_id=task_id)
            record = result.single()
            return record["dependencies"] if record else []
    
    def find_similar_knowledge(self, embeddings: List[float], limit: int = 5) -> List[Dict]:
        """Find similar knowledge nodes using embeddings"""
        # Note: This is a simplified version. In production, use vector similarity
        query = """
        MATCH (k:Knowledge)
        WHERE k.embeddings IS NOT NULL
        RETURN k
        LIMIT $limit
        """
        
        with self.driver.session() as session:
            result = session.run(query, limit=limit)
            return [dict(record["k"]) for record in result]
    
    def get_applicable_patterns(self, task_type: str, min_success_rate: float = 0.7) -> List[Dict]:
        """Get patterns applicable to a task type"""
        query = """
        MATCH (p:Pattern)
        WHERE p.type = $task_type 
          AND p.success_rate >= $min_success_rate
        RETURN p
        ORDER BY p.success_rate DESC, p.occurrences DESC
        LIMIT 5
        """
        
        with self.driver.session() as session:
            result = session.run(query,
                task_type=task_type,
                min_success_rate=min_success_rate
            )
            return [dict(record["p"]) for record in result]
    
    def get_collaboration_graph(self) -> Dict[str, Any]:
        """Get agent collaboration network"""
        query = """
        MATCH (a1:Agent)-[c:COLLABORATES_WITH]-(a2:Agent)
        RETURN a1.agent_id as agent1, 
               a2.agent_id as agent2, 
               c.collaboration_count as count,
               c.success_rate as success_rate
        """
        
        with self.driver.session() as session:
            result = session.run(query)
            collaborations = []
            for record in result:
                collaborations.append({
                    "agent1": record["agent1"],
                    "agent2": record["agent2"],
                    "count": record["count"],
                    "success_rate": record["success_rate"]
                })
            return {"collaborations": collaborations}
    
    def get_goal_progress(self, goal_id: str) -> Dict[str, Any]:
        """Get progress on a goal"""
        query = """
        MATCH (g:Goal {goal_id: $goal_id})
        OPTIONAL MATCH (g)-[:DECOMPOSED_INTO]->(t:Task)
        WITH g, 
             COUNT(t) as total_tasks,
             SUM(CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END) as completed_tasks,
             SUM(CASE WHEN t.status = 'failed' THEN 1 ELSE 0 END) as failed_tasks
        RETURN {
            goal_id: g.goal_id,
            description: g.description,
            status: g.status,
            total_tasks: total_tasks,
            completed_tasks: completed_tasks,
            failed_tasks: failed_tasks,
            progress: CASE 
                WHEN total_tasks > 0 
                THEN toFloat(completed_tasks) / total_tasks 
                ELSE 0 
            END
        } as progress
        """
        
        with self.driver.session() as session:
            result = session.run(query, goal_id=goal_id)
            record = result.single()
            return record["progress"] if record else None
    
    # Update Operations
    
    def update_task_status(self, task_id: str, status: str, result: Dict = None) -> bool:
        """Update task status and optionally add result"""
        query = """
        MATCH (t:Task {task_id: $task_id})
        SET t.status = $status,
            t.updated_at = datetime()
        """
        
        if status == "completed" and result:
            query += """,
            t.completed_at = datetime(),
            t.result = $result
            """
        
        query += " RETURN t"
        
        with self.driver.session() as session:
            params = {"task_id": task_id, "status": status}
            if result:
                params["result"] = json.dumps(result)
            
            result = session.run(query, **params)
            return result.single() is not None
    
    def update_agent_status(self, agent_id: str, status: str) -> bool:
        """Update agent status"""
        query = """
        MATCH (a:Agent {agent_id: $agent_id})
        SET a.status = $status,
            a.updated_at = datetime()
        RETURN a
        """
        
        with self.driver.session() as session:
            result = session.run(query,
                agent_id=agent_id,
                status=status
            )
            return result.single() is not None
    
    # Complex Queries
    
    def get_execution_path(self, goal_id: str) -> List[Dict]:
        """Get optimal execution path for a goal"""
        query = """
        MATCH path = (g:Goal {goal_id: $goal_id})-[:DECOMPOSED_INTO]->(t:Task)
        OPTIONAL MATCH (t)-[:DEPENDS_ON]->(dep:Task)
        WITH t, COLLECT(dep.task_id) as dependencies
        RETURN t.task_id as task_id,
               t.type as type,
               t.status as status,
               dependencies
        ORDER BY SIZE(dependencies)
        """
        
        with self.driver.session() as session:
            result = session.run(query, goal_id=goal_id)
            return [dict(record) for record in result]
    
    def find_expert_agent(self, required_capabilities: List[str]) -> Optional[str]:
        """Find best agent for given capabilities"""
        query = """
        MATCH (a:Agent)
        WHERE a.status = 'active'
          AND ALL(cap IN $required_capabilities WHERE cap IN a.capabilities)
        OPTIONAL MATCH (a)<-[:ASSIGNED_TO]-(t:Task)
        WHERE t.status IN ['pending', 'in_progress']
        WITH a, COUNT(t) as workload
        RETURN a.agent_id as agent_id
        ORDER BY workload ASC
        LIMIT 1
        """
        
        with self.driver.session() as session:
            result = session.run(query, required_capabilities=required_capabilities)
            record = result.single()
            return record["agent_id"] if record else None
    
    def get_knowledge_context(self, session_id: str, limit: int = 10) -> List[Dict]:
        """Get relevant knowledge for a session"""
        query = """
        MATCH (c:Context {session_id: $session_id})
        OPTIONAL MATCH (c)<-[:IN_CONTEXT]-(k:Knowledge)
        WITH k
        WHERE k IS NOT NULL
        RETURN k
        ORDER BY k.created_at DESC
        LIMIT $limit
        """
        
        with self.driver.session() as session:
            result = session.run(query,
                session_id=session_id,
                limit=limit
            )
            return [dict(record["k"]) for record in result]
    
    # Cleanup Operations
    
    def cleanup_old_contexts(self, days: int = 7) -> int:
        """Remove old context nodes"""
        query = """
        MATCH (c:Context)
        WHERE c.timestamp < datetime() - duration({days: $days})
        DETACH DELETE c
        RETURN COUNT(c) as deleted_count
        """
        
        with self.driver.session() as session:
            result = session.run(query, days=days)
            record = result.single()
            return record["deleted_count"] if record else 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics"""
        query = """
        MATCH (n)
        WITH labels(n)[0] as label, COUNT(n) as count
        RETURN label, count
        ORDER BY label
        """
        
        with self.driver.session() as session:
            result = session.run(query)
            stats = {"nodes": {}}
            for record in result:
                stats["nodes"][record["label"]] = record["count"]
            
            # Get relationship counts
            rel_query = """
            MATCH ()-[r]->()
            WITH type(r) as rel_type, COUNT(r) as count
            RETURN rel_type, count
            ORDER BY rel_type
            """
            
            result = session.run(rel_query)
            stats["relationships"] = {}
            for record in result:
                stats["relationships"][record["rel_type"]] = record["count"]
            
            return stats