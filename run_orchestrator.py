#!/usr/bin/env python3
"""
Run script for ARGO Strategic Orchestrator
Usage: python run_orchestrator.py
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from agents.orchestrator.strategic_orchestrator import StrategicOrchestrator
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/orchestrator.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """Main entry point"""
    
    # Load environment variables
    load_dotenv()
    
    # Check for required environment variables
    required_vars = ['REDIS_HOST']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.warning(f"Missing environment variables: {missing_vars}")
        logger.info("Please copy .env.template to .env and fill in the values")
        logger.info("Using default values for now...")
    
    # Load configuration
    import yaml
    config_path = Path(__file__).parent / "config" / "config.yaml"
    
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    else:
        logger.warning("Configuration file not found, using defaults")
        config = {
            'redis': {
                'host': os.getenv('REDIS_HOST', 'localhost'),
                'port': int(os.getenv('REDIS_PORT', 6379))
            }
        }
    
    # Create logs directory
    Path("logs").mkdir(exist_ok=True)
    
    # Initialize and start orchestrator
    logger.info("Starting Strategic Orchestrator...")
    
    try:
        orchestrator = StrategicOrchestrator(config)
        await orchestrator.start()
        
        logger.info("Strategic Orchestrator is running. Press Ctrl+C to stop.")
        
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)
            
            # Print statistics every 30 seconds
            if int(asyncio.get_event_loop().time()) % 30 == 0:
                stats = orchestrator.get_statistics()
                logger.info(f"Statistics: {stats}")
                
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await orchestrator.stop()
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())