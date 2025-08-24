#!/usr/bin/env python3
"""
File-based Integration Test for ARGO Layer 1 and Layer 2
Tests the file-based communication bridge
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
import json

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from integration.file_bridge import get_file_bridge

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_file_bridge():
    """Test the file-based bridge functionality"""
    logger.info("🧪 Testing File-based Bridge...")
    
    bridge = await get_file_bridge()
    
    # Test 1: Register message handlers
    logger.info("📝 Registering message handlers...")
    
    async def handle_semantic_search(data, message):
        logger.info(f"🔍 Processing semantic search: {data['query']}")
        return {
            "query_id": message['id'],
            "analysis": {
                "relevance_score": 0.95,
                "key_concepts": ["AI", "neural", "networks"],
                "recommendations": [
                    "Focus on deep learning architectures",
                    "Consider transformer models",
                    "Implement attention mechanisms"
                ]
            }
        }
    
    async def handle_file_analysis(data, message):
        logger.info(f"📄 Processing file analysis: {data['file_path']}")
        return {
            "file_id": message['id'],
            "analysis": {
                "content_type": "code",
                "language": "typescript",
                "complexity_score": 0.7,
                "suggestions": [
                    "Consider breaking down large functions",
                    "Add more error handling",
                    "Improve documentation"
                ]
            }
        }
    
    bridge.register_handler("semantic_search", handle_semantic_search)
    bridge.register_handler("file_analysis", handle_file_analysis)
    
    logger.info("✅ Message handlers registered")
    
    # Test 2: Start bridge
    logger.info("🚀 Starting file bridge...")
    await bridge.start()
    
    # Test 3: Send test message to Layer 1
    logger.info("📤 Sending test message to Layer 1...")
    message_id = await bridge.send_message_to_layer1("system_status", {
        "status": "ready",
        "agents": ["orchestrator", "technical", "research", "creative"],
        "capabilities": ["goal_interpretation", "strategic_planning", "resource_optimization"]
    })
    logger.info(f"✅ Test message sent: {message_id}")
    
    # Test 4: Check bridge status
    status = bridge.get_status()
    logger.info(f"📊 Bridge Status: {status}")
    
    # Test 5: Wait for message processing
    logger.info("⏳ Waiting for message processing...")
    await asyncio.sleep(2)
    
    # Test 6: Stop bridge
    logger.info("🛑 Stopping file bridge...")
    await bridge.stop()
    
    logger.info("🎉 File-based bridge test completed!")


async def test_message_handling():
    """Test message handling with simulated Layer 1 messages"""
    logger.info("🧪 Testing Message Handling...")
    
    bridge = await get_file_bridge()
    
    # Register test handler
    async def test_handler(data, message):
        logger.info(f"🧠 Test handler called with: {data}")
        return {"processed": True, "result": f"Processed: {data['message']}"}
    
    bridge.register_handler("test_message", test_handler)
    
    # Start bridge
    await bridge.start()
    
    # Simulate Layer 1 message by creating a file
    test_message = {
        "id": "test_msg_001",
        "timestamp": "2025-08-24T01:50:00",
        "source": "layer1",
        "target": "layer2",
        "event_type": "test_message",
        "data": {"message": "Hello from Layer 1!"}
    }
    
    # Write test message to Layer 1 → Layer 2 directory
    message_file = bridge.layer1_to_layer2_dir / "test_msg_001.json"
    message_file.write_text(json.dumps(test_message, indent=2), encoding='utf-8')
    
    logger.info("📝 Test message file created")
    
    # Wait for processing
    await asyncio.sleep(1)
    
    # Check if response was created
    response_files = list(bridge.layer2_to_layer1_dir.glob("*.json"))
    if response_files:
        logger.info(f"✅ Response file created: {response_files[0].name}")
        
        # Read response
        response_content = response_files[0].read_text(encoding='utf-8')
        if response_content.strip():
            response = json.loads(response_content)
            logger.info(f"📥 Response content: {response['data']}")
        else:
            logger.warning("⚠️ Response file is empty")
    else:
        logger.warning("⚠️ No response file created")
    
    # Stop bridge
    await bridge.stop()
    
    logger.info("🎉 Message handling test completed!")


async def main():
    """Main test function"""
    logger.info("🚀 Starting File-based Integration Tests...")
    
    try:
        # Test 1: File Bridge
        await test_file_bridge()
        
        # Test 2: Message Handling
        await test_message_handling()
        
        logger.info("🎉 All file-based integration tests completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ File-based integration tests failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
