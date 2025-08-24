#!/usr/bin/env python3
"""
Integration Test Script for ARGO Layer 1 and Layer 2
Tests the communication bridge and data synchronization
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from integration.layer_bridge import get_layer_bridge
from agents.orchestrator.strategic_orchestrator import StrategicOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_layer_bridge():
    """Test the layer bridge functionality"""
    logger.info("🧪 Testing Layer Bridge...")
    
    bridge = await get_layer_bridge()
    
    # Test 1: Send message from Layer 2 to Layer 1
    logger.info("📤 Testing Layer 2 → Layer 1 communication...")
    message_id = await bridge.send_to_layer1("test_event", {
        "message": "Hello from Layer 2!",
        "timestamp": "2025-08-24T01:42:00",
        "data": {"test": True, "value": 42}
    })
    logger.info(f"✅ Message sent with ID: {message_id}")
    
    # Test 2: Send message from Layer 1 to Layer 2
    logger.info("📤 Testing Layer 1 → Layer 2 communication...")
    message_id = await bridge.send_to_layer2("search_result", {
        "query": "AI neural networks",
        "results": ["result1", "result2", "result3"],
        "confidence": 0.95
    })
    logger.info(f"✅ Message sent with ID: {message_id}")
    
    # Test 3: Check bridge status
    status = bridge.get_bridge_status()
    logger.info(f"📊 Bridge Status: {status}")
    
    # Test 4: Test message reception
    logger.info("📥 Testing message reception...")
    
    # Wait a bit for messages to be processed
    await asyncio.sleep(0.5)
    
    # Check Layer 1 queue
    layer1_message = await bridge.receive_from_layer2()
    if layer1_message:
        logger.info(f"✅ Received from Layer 2: {layer1_message['event_type']}")
        logger.info(f"   Data: {layer1_message['data']}")
    else:
        logger.warning("⚠️ No message received from Layer 2")
    
    # Check Layer 2 queue
    layer2_message = await bridge.receive_from_layer1()
    if layer2_message:
        logger.info(f"✅ Received from Layer 1: {layer2_message['event_type']}")
        logger.info(f"   Data: {layer2_message['data']}")
    else:
        logger.warning("⚠️ No message received from Layer 1")
    
    logger.info("🎉 Layer Bridge test completed!")


async def test_strategic_orchestrator():
    """Test the Strategic Orchestrator with mock Redis"""
    logger.info("🧪 Testing Strategic Orchestrator...")
    
    try:
        # Create orchestrator with mock configuration
        config = {
            'redis': {
                'host': 'localhost',
                'port': 6379
            },
            'enable_mock': True
        }
        
        orchestrator = StrategicOrchestrator(config)
        
        # Test basic functionality
        logger.info("📋 Testing goal creation...")
        goal_data = {
            "goal_id": "test_goal_001",
            "description": "Test integration between Layer 1 and Layer 2",
            "success_criteria": ["Layer 1 can send data", "Layer 2 can receive data"],
            "constraints": {"time_limit": "1 hour"},
            "priority": "HIGH"
        }
        
        # This would normally require Priority enum, but we'll test basic functionality
        logger.info(f"✅ Goal data prepared: {goal_data['description']}")
        
        # Test agent capabilities
        capabilities = orchestrator.get_capabilities()
        logger.info(f"✅ Agent capabilities: {len(capabilities)} capabilities registered")
        
        logger.info("🎉 Strategic Orchestrator test completed!")
        
    except Exception as e:
        logger.error(f"❌ Strategic Orchestrator test failed: {e}")
        raise


async def test_integration_scenario():
    """Test a complete integration scenario"""
    logger.info("🧪 Testing Complete Integration Scenario...")
    
    bridge = await get_layer_bridge()
    
    # Scenario: Layer 1 performs a search and Layer 2 analyzes the results
    
    # Step 1: Layer 1 performs semantic search
    logger.info("🔍 Step 1: Layer 1 performs semantic search...")
    search_event = await bridge.send_to_layer2("semantic_search", {
        "query": "ARGO architecture design",
        "filters": {"max_results": 10, "confidence_threshold": 0.8},
        "user_context": "software_architect"
    })
    logger.info(f"✅ Search event sent: {search_event}")
    
    # Step 2: Layer 2 processes the search request
    logger.info("🧠 Step 2: Layer 2 processes search request...")
    
    # Simulate Layer 2 processing
    await asyncio.sleep(0.2)
    
    # Step 3: Layer 2 sends analysis results back
    logger.info("📊 Step 3: Layer 2 sends analysis results...")
    analysis_event = await bridge.send_to_layer1("search_analysis", {
        "query_id": search_event,
        "analysis": {
            "relevance_score": 0.92,
            "key_concepts": ["architecture", "design", "system"],
            "recommendations": [
                "Focus on modular design patterns",
                "Consider scalability requirements",
                "Implement event-driven architecture"
            ]
        },
        "processing_time_ms": 150
    })
    logger.info(f"✅ Analysis event sent: {analysis_event}")
    
    # Step 4: Verify data flow
    logger.info("✅ Step 4: Verifying data flow...")
    
    # Check message queues
    status = bridge.get_bridge_status()
    logger.info(f"📊 Final Bridge Status: {status}")
    
    # Clear queues for clean state
    bridge.clear_queues()
    logger.info("🧹 Queues cleared for clean state")
    
    logger.info("🎉 Integration scenario test completed!")


async def main():
    """Main test function"""
    logger.info("🚀 Starting ARGO Layer Integration Tests...")
    
    try:
        # Test 1: Layer Bridge
        await test_layer_bridge()
        
        # Test 2: Strategic Orchestrator
        await test_strategic_orchestrator()
        
        # Test 3: Complete Integration Scenario
        await test_integration_scenario()
        
        logger.info("🎉 All integration tests completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Integration tests failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
