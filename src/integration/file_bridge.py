"""
File-based Bridge for Layer 2 to communicate with Layer 1
Uses file system for message exchange (alternative to Redis)
"""

import json
import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class FileBridge:
    """
    File-based bridge for Layer 2 to Layer 1 communication
    Monitors directories for incoming messages and sends responses
    """
    
    def __init__(self, data_dir: str = "C:\\Argo-813\\data"):
        self.data_dir = Path(data_dir)
        self.layer1_to_layer2_dir = self.data_dir / "layer1_to_layer2"
        self.layer2_to_layer1_dir = self.data_dir / "layer2_to_layer1"
        
        # Ensure directories exist
        self.layer1_to_layer2_dir.mkdir(parents=True, exist_ok=True)
        self.layer2_to_layer1_dir.mkdir(parents=True, exist_ok=True)
        
        # Message processing state
        self.is_running = False
        self.processed_messages = set()
        self.message_handlers: Dict[str, callable] = {}
        
        logger.info(f"FileBridge initialized with data directory: {data_dir}")
    
    async def start(self):
        """Start the file bridge service"""
        if self.is_running:
            logger.info("FileBridge is already running")
            return
        
        logger.info("🚀 Starting File Bridge...")
        self.is_running = True
        
        # Start message monitoring
        asyncio.create_task(self._monitor_messages())
        
        logger.info("✅ File Bridge started successfully")
    
    async def stop(self):
        """Stop the file bridge service"""
        if not self.is_running:
            return
        
        logger.info("🛑 Stopping File Bridge...")
        self.is_running = False
        logger.info("✅ File Bridge stopped")
    
    def register_handler(self, event_type: str, handler: callable):
        """Register message handler for specific event type"""
        self.message_handlers[event_type] = handler
        logger.info(f"Registered handler for event: {event_type}")
    
    async def _monitor_messages(self):
        """Monitor for incoming messages from Layer 1"""
        while self.is_running:
            try:
                await self._check_for_messages()
                await asyncio.sleep(0.1)  # Check every 100ms
            except Exception as e:
                logger.error(f"Error in message monitoring: {e}")
                await asyncio.sleep(1)
    
    async def _check_for_messages(self):
        """Check for new messages from Layer 1"""
        try:
            # Get all JSON files in the incoming directory
            message_files = list(self.layer1_to_layer2_dir.glob("*.json"))
            
            for message_file in message_files:
                if message_file.name in self.processed_messages:
                    continue
                
                try:
                    # Read and process message
                    message = await self._read_message_file(message_file)
                    if message:
                        await self._process_message(message, message_file)
                        self.processed_messages.add(message_file.name)
                        
                except Exception as e:
                    logger.error(f"Error processing message file {message_file.name}: {e}")
                    
        except Exception as e:
            logger.error(f"Error checking for messages: {e}")
    
    async def _read_message_file(self, message_file: Path) -> Optional[Dict[str, Any]]:
        """Read message from file"""
        try:
            content = message_file.read_text(encoding='utf-8')
            if not content.strip():
                return None
            
            message = json.loads(content)
            return message
            
        except Exception as e:
            logger.error(f"Error reading message file {message_file.name}: {e}")
            return None
    
    async def _process_message(self, message: Dict[str, Any], message_file: Path):
        """Process incoming message"""
        event_type = message.get('event_type')
        message_id = message.get('id')
        
        logger.info(f"📥 Processing message: {event_type} (ID: {message_id})")
        
        if event_type in self.message_handlers:
            try:
                # Call registered handler
                result = await self.message_handlers[event_type](message['data'], message)
                
                # Send response back to Layer 1
                if result:
                    await self.send_response(message_id, event_type, result)
                    
            except Exception as e:
                logger.error(f"Error in message handler for {event_type}: {e}")
                
                # Send error response
                await self.send_response(message_id, f"{event_type}_error", {
                    "error": str(e),
                    "original_message": message
                })
        else:
            logger.warning(f"No handler registered for event type: {event_type}")
            
            # Send "no handler" response
            await self.send_response(message_id, f"{event_type}_no_handler", {
                "message": f"No handler registered for event type: {event_type}",
                "available_handlers": list(self.message_handlers.keys())
            })
    
    async def send_response(self, correlation_id: str, event_type: str, data: Any):
        """Send response back to Layer 1"""
        response = {
            "id": f"resp_{int(time.time() * 1000)}_{os.getpid()}",
            "timestamp": datetime.now().isoformat(),
            "source": "layer2",
            "target": "layer1",
            "event_type": event_type,
            "data": data,
            "correlation_id": correlation_id
        }
        
        try:
            response_file = self.layer2_to_layer1_dir / f"{response['id']}.json"
            response_file.write_text(json.dumps(response, indent=2, ensure_ascii=False), encoding='utf-8')
            
            logger.info(f"📤 Sent response to Layer 1: {event_type} (ID: {response['id']})")
            
        except Exception as e:
            logger.error(f"Failed to send response to Layer 1: {e}")
    
    async def send_message_to_layer1(self, event_type: str, data: Any):
        """Send proactive message to Layer 1"""
        message = {
            "id": f"msg_{int(time.time() * 1000)}_{os.getpid()}",
            "timestamp": datetime.now().isoformat(),
            "source": "layer2",
            "target": "layer1",
            "event_type": event_type,
            "data": data
        }
        
        try:
            message_file = self.layer2_to_layer1_dir / f"{message['id']}.json"
            message_file.write_text(json.dumps(message, indent=2, ensure_ascii=False), encoding='utf-8')
            
            logger.info(f"📤 Sent proactive message to Layer 1: {event_type} (ID: {message['id']})")
            return message['id']
            
        except Exception as e:
            logger.error(f"Failed to send proactive message to Layer 1: {e}")
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get bridge status"""
        return {
            "status": "active" if self.is_running else "stopped",
            "data_dir": str(self.data_dir),
            "layer1_to_layer2_dir": str(self.layer1_to_layer2_dir),
            "layer2_to_layer1_dir": str(self.layer2_to_layer1_dir),
            "processed_messages": len(self.processed_messages),
            "registered_handlers": list(self.message_handlers.keys()),
            "is_running": self.is_running
        }
    
    def clear_processed_messages(self):
        """Clear processed messages list (for testing)"""
        self.processed_messages.clear()
        logger.info("Processed messages list cleared")
    
    async def clear_message_files(self):
        """Clear all message files (for testing)"""
        try:
            # Clear Layer 1 → Layer 2 messages
            for message_file in self.layer1_to_layer2_dir.glob("*.json"):
                message_file.write_text("")
            
            # Clear Layer 2 → Layer 1 responses
            for response_file in self.layer2_to_layer1_dir.glob("*.json"):
                response_file.write_text("")
            
            logger.info("🧹 All message files cleared")
            
        except Exception as e:
            logger.error(f"Error clearing message files: {e}")


# Global file bridge instance
file_bridge = FileBridge()


async def get_file_bridge() -> FileBridge:
    """Get global file bridge instance"""
    return file_bridge
