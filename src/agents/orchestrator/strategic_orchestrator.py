"""
Strategic Orchestrator Agent for ARGO Phase 2
The highest-level decision-making agent that acts as AI-Director's deputy
"""

import asyncio
import logging
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.base_agent import BaseAgent, AgentCapability
from shared.messaging.agent_protocol import AgentMessage, MessageType, Priority

logger = logging.getLogger(__name__)


@dataclass
class Goal:
    """Represents a high-level goal from the Director"""
    goal_id: str
    description: str
    success_criteria: List[str]
    constraints: Dict[str, Any]
    priority: Priority
    deadline: Optional[datetime] = None
    status: str = "pending"
    
    def to_dict(self) -> Dict:
        return {
            'goal_id': self.goal_id,
            'description': self.description,
            'success_criteria': self.success_criteria,
            'constraints': self.constraints,
            'priority': self.priority.value,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'status': self.status
        }


@dataclass
class ExecutionPlan:
    """Execution plan for achieving a goal"""
    plan_id: str
    goal_id: str
    steps: List[Dict[str, Any]]
    dependencies: Dict[str, List[str]]  # step_id -> [dependency_ids]
    resource_requirements: Dict[str, Any]
    estimated_duration: float  # in seconds
    approval_required: bool = False
    
    def get_next_steps(self, completed_steps: Set[str]) -> List[Dict[str, Any]]:
        """Get steps that can be executed next"""
        next_steps = []
        for step in self.steps:
            step_id = step['id']
            if step_id not in completed_steps:
                deps = self.dependencies.get(step_id, [])
                if all(dep in completed_steps for dep in deps):
                    next_steps.append(step)
        return next_steps


class StrategicOrchestrator(BaseAgent):
    """
    Strategic Orchestrator - The master coordinator of the ARGO system
    Responsible for goal interpretation, strategic planning, and resource allocation
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Strategic Orchestrator"""
        super().__init__(
            agent_id="strategic_orchestrator",
            agent_type="orchestrator",
            config=config
        )
        
        # Goal management
        self.active_goals: Dict[str, Goal] = {}
        self.execution_plans: Dict[str, ExecutionPlan] = {}
        self.completed_steps: Dict[str, Set[str]] = {}  # goal_id -> completed step ids
        
        # Agent registry
        self.registered_agents: Dict[str, Dict[str, Any]] = {}
        self.agent_workloads: Dict[str, int] = {}  # agent_id -> current workload
        
        # Decision framework
        self.autonomous_decisions = [
            "technology_stack_selection",
            "implementation_methodology",
            "resource_allocation",
            "task_prioritization"
        ]
        
        self.requires_approval = [
            "budget_exceeding",  # > $100
            "external_service_integration",
            "production_deployment",
            "data_deletion_or_migration"
        ]
        
        logger.info("Strategic Orchestrator initialized")
    
    def _register_capabilities(self):
        """Register orchestrator capabilities"""
        self.capabilities = [
            AgentCapability(
                name="goal_interpretation",
                description="Interpret Director's intent into actionable goals",
                input_schema={"type": "object", "properties": {"intent": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"goal": {"type": "object"}}}
            ),
            AgentCapability(
                name="strategic_planning",
                description="Create multi-step execution plans",
                input_schema={"type": "object", "properties": {"goal": {"type": "object"}}},
                output_schema={"type": "object", "properties": {"plan": {"type": "object"}}}
            ),
            AgentCapability(
                name="resource_optimization",
                description="Optimize agent resource allocation",
                input_schema={"type": "object"},
                output_schema={"type": "object"}
            ),
            AgentCapability(
                name="conflict_resolution",
                description="Resolve conflicts between agents",
                input_schema={"type": "object"},
                output_schema={"type": "object"}
            ),
            AgentCapability(
                name="approval_requests",
                description="Identify and request Director approval when needed",
                input_schema={"type": "object"},
                output_schema={"type": "object"}
            )
        ]
    
    def _register_task_handlers(self):
        """Register task handlers"""
        self.task_handlers = {
            'interpret_goal': self._interpret_goal,
            'create_plan': self._create_execution_plan,
            'allocate_resources': self._allocate_resources,
            'resolve_conflict': self._resolve_conflict,
            'monitor_execution': self._monitor_execution
        }
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a task based on its type
        
        Args:
            task: Task to process
            
        Returns:
            Task result
        """
        task_type = task.get('type', 'unknown')
        handler = self.task_handlers.get(task_type)
        
        if handler:
            return await handler(task)
        else:
            # Default processing for Director requests
            return await self._process_director_request(task)
    
    async def _process_director_request(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a request from the Director"""
        request = task.get('parameters', {}).get('request', '')
        context = task.get('parameters', {}).get('context', {})
        
        logger.info(f"Processing Director request: {request[:100]}...")
        
        # Step 1: Interpret the goal
        goal = await self._interpret_goal({
            'parameters': {
                'intent': request,
                'context': context
            }
        })
        
        # Step 2: Create execution plan
        plan = await self._create_execution_plan({
            'parameters': {
                'goal': goal['goal']
            }
        })
        
        # Step 3: Check if approval is needed
        if plan['plan'].get('approval_required'):
            approval_request = await self._request_director_approval(plan['plan'])
            if not approval_request.get('approved'):
                return {
                    'status': 'awaiting_approval',
                    'plan': plan['plan'],
                    'message': 'Plan requires Director approval before execution'
                }
        
        # Step 4: Start execution
        execution_result = await self._execute_plan(plan['plan'])
        
        return {
            'status': 'executing',
            'goal': goal['goal'],
            'plan': plan['plan'],
            'execution': execution_result
        }
    
    async def _interpret_goal(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interpret Director's intent into a structured goal
        
        Example: "Optimize this app by 40%" becomes:
        - Goal: Application optimization
        - Success criteria: [40% performance improvement]
        - Constraints: {preserve_functionality: true}
        """
        intent = task.get('parameters', {}).get('intent', '')
        context = task.get('parameters', {}).get('context', {})
        
        # Create structured goal
        goal = Goal(
            goal_id=str(uuid.uuid4()),
            description=self._extract_goal_description(intent),
            success_criteria=self._extract_success_criteria(intent),
            constraints=self._extract_constraints(intent, context),
            priority=self._determine_priority(intent),
            deadline=self._extract_deadline(intent)
        )
        
        # Store goal
        self.active_goals[goal.goal_id] = goal
        
        # Store in context for learning
        session_id = context.get('session_id', 'default')
        self.context_fabric.store_event(session_id, {
            'type': 'goal',
            'content': goal.to_dict()
        })
        
        logger.info(f"Goal interpreted: {goal.goal_id} - {goal.description}")
        
        return {'goal': goal.to_dict()}
    
    async def _create_execution_plan(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a detailed execution plan for a goal
        
        Breaks down the goal into concrete steps that can be assigned to agents
        """
        goal_dict = task.get('parameters', {}).get('goal', {})
        goal_id = goal_dict.get('goal_id')
        
        # Decompose goal into steps
        steps = self._decompose_goal(goal_dict)
        
        # Identify dependencies
        dependencies = self._identify_dependencies(steps)
        
        # Estimate resource requirements
        resources = self._estimate_resources(steps)
        
        # Check if approval is needed
        approval_required = self._check_approval_requirements(steps, resources)
        
        # Create execution plan
        plan = ExecutionPlan(
            plan_id=str(uuid.uuid4()),
            goal_id=goal_id,
            steps=steps,
            dependencies=dependencies,
            resource_requirements=resources,
            estimated_duration=self._estimate_duration(steps),
            approval_required=approval_required
        )
        
        # Store plan
        self.execution_plans[goal_id] = plan
        self.completed_steps[goal_id] = set()
        
        logger.info(f"Execution plan created: {plan.plan_id} with {len(steps)} steps")
        
        return {'plan': {
            'plan_id': plan.plan_id,
            'goal_id': plan.goal_id,
            'steps': plan.steps,
            'dependencies': plan.dependencies,
            'resource_requirements': plan.resource_requirements,
            'estimated_duration': plan.estimated_duration,
            'approval_required': plan.approval_required
        }}
    
    async def _execute_plan(self, plan_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a plan by distributing tasks to agents"""
        goal_id = plan_dict.get('goal_id')
        plan = self.execution_plans.get(goal_id)
        
        if not plan:
            return {'error': 'Plan not found'}
        
        # Get next executable steps
        next_steps = plan.get_next_steps(self.completed_steps[goal_id])
        
        # Distribute steps to agents
        assignments = []
        for step in next_steps:
            agent_id = await self._select_best_agent(step)
            
            if agent_id:
                # Create task message
                task_message = AgentMessage(
                    sender_agent=self.agent_id,
                    recipient_agents=[agent_id],
                    message_type=MessageType.REQUEST,
                    priority=self._step_to_priority(step),
                    content={
                        'action': step.get('action'),
                        'parameters': step.get('parameters', {}),
                        'required_capabilities': step.get('required_capabilities', []),
                        'goal_id': goal_id,
                        'step_id': step.get('id')
                    }
                )
                
                # Send task to agent
                await self.send_message(task_message)
                
                assignments.append({
                    'step_id': step.get('id'),
                    'agent_id': agent_id,
                    'status': 'assigned'
                })
                
                # Update agent workload
                self.agent_workloads[agent_id] = self.agent_workloads.get(agent_id, 0) + 1
                
                logger.info(f"Step {step.get('id')} assigned to {agent_id}")
            else:
                logger.warning(f"No suitable agent found for step {step.get('id')}")
                assignments.append({
                    'step_id': step.get('id'),
                    'agent_id': None,
                    'status': 'unassigned'
                })
        
        return {
            'assignments': assignments,
            'total_steps': len(plan.steps),
            'completed_steps': len(self.completed_steps[goal_id]),
            'in_progress': len(assignments)
        }
    
    async def _select_best_agent(self, step: Dict[str, Any]) -> Optional[str]:
        """Select the best agent for a step"""
        required_capabilities = step.get('required_capabilities', [])
        
        # Update agent registry
        await self._update_agent_registry()
        
        best_agent = None
        best_score = -1
        
        for agent_id, agent_info in self.registered_agents.items():
            if agent_id == self.agent_id:
                continue
            
            # Calculate capability match score
            capabilities = agent_info.get('capabilities', [])
            score = self._calculate_capability_score(required_capabilities, capabilities)
            
            # Factor in current workload
            workload = self.agent_workloads.get(agent_id, 0)
            adjusted_score = score / (1 + workload * 0.1)  # Penalize busy agents
            
            if adjusted_score > best_score:
                best_score = adjusted_score
                best_agent = agent_id
        
        return best_agent
    
    async def _update_agent_registry(self):
        """Update the registry of available agents"""
        # Get all agent types
        agent_types = ['technical', 'creative', 'research', 'execution']
        
        for agent_type in agent_types:
            agent_ids = self.redis.smembers(f"agents:{agent_type}")
            
            for agent_id in agent_ids:
                agent_key = f"agent:{agent_id}"
                agent_data = self.redis.hgetall(agent_key)
                
                if agent_data:
                    # Parse capabilities
                    capabilities = json.loads(agent_data.get('capabilities', '[]'))
                    
                    self.registered_agents[agent_id] = {
                        'type': agent_type,
                        'capabilities': capabilities,
                        'status': agent_data.get('status', 'unknown')
                    }
    
    def _calculate_capability_score(self, required: List[str], available: List[Dict]) -> float:
        """Calculate how well capabilities match requirements"""
        if not required:
            return 1.0
        
        matches = 0
        for req in required:
            for cap in available:
                if req.lower() in cap.get('name', '').lower() or \
                   req.lower() in cap.get('description', '').lower():
                    matches += 1
                    break
        
        return matches / len(required)
    
    async def _request_director_approval(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Request Director approval for a plan"""
        approval_message = AgentMessage(
            sender_agent=self.agent_id,
            recipient_agents=["director_interface"],
            message_type=MessageType.PROPOSAL,
            priority=Priority.HIGH,
            requires_approval=True,
            content={
                'type': 'plan_approval',
                'plan': plan,
                'reason': self._get_approval_reason(plan),
                'options': self._generate_plan_options(plan)
            }
        )
        
        await self.send_message(approval_message)
        
        # In production, would wait for approval response
        # For now, return pending status
        return {
            'approved': False,
            'status': 'pending_approval',
            'message': 'Awaiting Director approval'
        }
    
    async def _allocate_resources(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Allocate resources optimally across agents"""
        # This would implement resource allocation logic
        return {'status': 'resources_allocated'}
    
    async def _resolve_conflict(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflicts between agents"""
        conflict = task.get('parameters', {}).get('conflict', {})
        
        # Conflict resolution strategies
        resolution_strategy = self._determine_resolution_strategy(conflict)
        
        if resolution_strategy == 'priority':
            # Resolve based on priority
            return self._resolve_by_priority(conflict)
        elif resolution_strategy == 'consensus':
            # Request consensus from agents
            return await self._resolve_by_consensus(conflict)
        elif resolution_strategy == 'director':
            # Escalate to Director
            return await self._escalate_to_director(conflict)
        else:
            # Default: first-come-first-served
            return self._resolve_by_order(conflict)
    
    async def _monitor_execution(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Monitor plan execution progress"""
        goal_id = task.get('parameters', {}).get('goal_id')
        
        if goal_id not in self.execution_plans:
            return {'error': 'Goal not found'}
        
        plan = self.execution_plans[goal_id]
        completed = len(self.completed_steps[goal_id])
        total = len(plan.steps)
        
        return {
            'goal_id': goal_id,
            'progress': completed / total if total > 0 else 0,
            'completed_steps': completed,
            'total_steps': total,
            'status': self.active_goals[goal_id].status if goal_id in self.active_goals else 'unknown'
        }
    
    # Helper methods
    
    def _extract_goal_description(self, intent: str) -> str:
        """Extract goal description from intent"""
        # Simplified extraction - in production would use NLP
        return intent[:100] if len(intent) > 100 else intent
    
    def _extract_success_criteria(self, intent: str) -> List[str]:
        """Extract success criteria from intent"""
        criteria = []
        
        # Look for percentage improvements
        import re
        percentages = re.findall(r'(\d+)%', intent)
        for pct in percentages:
            criteria.append(f"{pct}% improvement")
        
        # Look for specific keywords
        if 'optimize' in intent.lower():
            criteria.append('Performance optimization achieved')
        if 'fix' in intent.lower():
            criteria.append('Issues resolved')
        
        return criteria if criteria else ['Task completed successfully']
    
    def _extract_constraints(self, intent: str, context: Dict) -> Dict[str, Any]:
        """Extract constraints from intent and context"""
        constraints = {}
        
        # Time constraints
        if 'urgent' in intent.lower() or 'asap' in intent.lower():
            constraints['time_constraint'] = 'urgent'
        
        # Budget constraints
        if 'budget' in intent.lower() or 'cost' in intent.lower():
            constraints['budget_constraint'] = True
        
        # Quality constraints
        if 'quality' in intent.lower() or 'best' in intent.lower():
            constraints['quality_priority'] = 'high'
        
        return constraints
    
    def _determine_priority(self, intent: str) -> Priority:
        """Determine priority from intent"""
        intent_lower = intent.lower()
        
        if 'critical' in intent_lower or 'emergency' in intent_lower:
            return Priority.CRITICAL
        elif 'urgent' in intent_lower or 'asap' in intent_lower:
            return Priority.URGENT
        elif 'important' in intent_lower or 'priority' in intent_lower:
            return Priority.HIGH
        else:
            return Priority.NORMAL
    
    def _extract_deadline(self, intent: str) -> Optional[datetime]:
        """Extract deadline from intent"""
        # Simplified - in production would use date parsing
        return None
    
    def _decompose_goal(self, goal: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Decompose goal into executable steps"""
        steps = []
        description = goal.get('description', '')
        
        # Example decomposition for optimization goal
        if 'optimize' in description.lower():
            steps.extend([
                {
                    'id': 'analyze_performance',
                    'action': 'Analyze current performance metrics',
                    'required_capabilities': ['analysis', 'performance'],
                    'parameters': {'target': 'application'}
                },
                {
                    'id': 'identify_bottlenecks',
                    'action': 'Identify performance bottlenecks',
                    'required_capabilities': ['technical', 'analysis'],
                    'parameters': {}
                },
                {
                    'id': 'generate_solutions',
                    'action': 'Generate optimization solutions',
                    'required_capabilities': ['technical', 'optimization'],
                    'parameters': {}
                },
                {
                    'id': 'implement_optimizations',
                    'action': 'Implement optimization solutions',
                    'required_capabilities': ['execution', 'code_generation'],
                    'parameters': {}
                },
                {
                    'id': 'validate_results',
                    'action': 'Validate optimization results',
                    'required_capabilities': ['testing', 'validation'],
                    'parameters': {}
                }
            ])
        else:
            # Generic step
            steps.append({
                'id': 'execute_task',
                'action': description,
                'required_capabilities': [],
                'parameters': {}
            })
        
        return steps
    
    def _identify_dependencies(self, steps: List[Dict]) -> Dict[str, List[str]]:
        """Identify dependencies between steps"""
        dependencies = {}
        
        # Simple sequential dependencies for now
        for i, step in enumerate(steps):
            if i > 0:
                dependencies[step['id']] = [steps[i-1]['id']]
        
        return dependencies
    
    def _estimate_resources(self, steps: List[Dict]) -> Dict[str, Any]:
        """Estimate resource requirements"""
        return {
            'agents_required': len(set(step.get('required_capabilities', [])[0] 
                                     for step in steps if step.get('required_capabilities'))),
            'estimated_api_calls': len(steps) * 10,
            'estimated_cost': len(steps) * 0.5  # $0.50 per step estimate
        }
    
    def _estimate_duration(self, steps: List[Dict]) -> float:
        """Estimate total duration in seconds"""
        # Simple estimate: 5 minutes per step
        return len(steps) * 300
    
    def _check_approval_requirements(self, steps: List[Dict], resources: Dict) -> bool:
        """Check if approval is required"""
        # Check cost threshold
        if resources.get('estimated_cost', 0) > 100:
            return True
        
        # Check for sensitive operations
        for step in steps:
            action = step.get('action', '').lower()
            if any(keyword in action for keyword in ['deploy', 'delete', 'migrate', 'production']):
                return True
        
        return False
    
    def _step_to_priority(self, step: Dict) -> Priority:
        """Convert step to message priority"""
        # Could be more sophisticated based on step importance
        return Priority.NORMAL
    
    def _get_approval_reason(self, plan: Dict) -> str:
        """Get reason for approval requirement"""
        resources = plan.get('resource_requirements', {})
        
        if resources.get('estimated_cost', 0) > 100:
            return f"Estimated cost exceeds threshold: ${resources.get('estimated_cost', 0)}"
        
        return "Plan contains sensitive operations requiring approval"
    
    def _generate_plan_options(self, plan: Dict) -> List[Dict]:
        """Generate alternative plan options"""
        # Simplified - would generate actual alternatives
        return [
            {
                'id': 'option_a',
                'description': 'Execute as planned',
                'modifications': []
            },
            {
                'id': 'option_b',
                'description': 'Execute with reduced scope',
                'modifications': ['Skip non-critical steps']
            },
            {
                'id': 'option_c',
                'description': 'Defer execution',
                'modifications': ['Schedule for later']
            }
        ]
    
    def _determine_resolution_strategy(self, conflict: Dict) -> str:
        """Determine conflict resolution strategy"""
        conflict_type = conflict.get('type', '')
        
        if conflict_type == 'resource_contention':
            return 'priority'
        elif conflict_type == 'decision_conflict':
            return 'consensus'
        elif conflict_type == 'critical_error':
            return 'director'
        else:
            return 'order'
    
    def _resolve_by_priority(self, conflict: Dict) -> Dict[str, Any]:
        """Resolve conflict by priority"""
        return {
            'resolution': 'priority',
            'winner': conflict.get('higher_priority_agent'),
            'message': 'Resolved by priority'
        }
    
    async def _resolve_by_consensus(self, conflict: Dict) -> Dict[str, Any]:
        """Resolve conflict by consensus"""
        # Send consensus request to involved agents
        consensus_message = AgentMessage(
            sender_agent=self.agent_id,
            recipient_agents=conflict.get('involved_agents', []),
            message_type=MessageType.CONSENSUS,
            priority=Priority.HIGH,
            content={
                'conflict': conflict,
                'request': 'vote_on_resolution'
            }
        )
        
        await self.send_message(consensus_message)
        
        return {
            'resolution': 'consensus_requested',
            'status': 'pending',
            'message': 'Awaiting consensus from agents'
        }
    
    async def _escalate_to_director(self, conflict: Dict) -> Dict[str, Any]:
        """Escalate conflict to Director"""
        escalation_message = AgentMessage(
            sender_agent=self.agent_id,
            recipient_agents=["director_interface"],
            message_type=MessageType.ESCALATION,
            priority=Priority.URGENT,
            content={
                'type': 'conflict_escalation',
                'conflict': conflict,
                'attempted_resolutions': conflict.get('attempted_resolutions', [])
            }
        )
        
        await self.send_message(escalation_message)
        
        return {
            'resolution': 'escalated',
            'status': 'pending_director',
            'message': 'Escalated to Director for resolution'
        }
    
    def _resolve_by_order(self, conflict: Dict) -> Dict[str, Any]:
        """Resolve conflict by order (first-come-first-served)"""
        return {
            'resolution': 'order',
            'winner': conflict.get('first_agent'),
            'message': 'Resolved by order of request'
        }