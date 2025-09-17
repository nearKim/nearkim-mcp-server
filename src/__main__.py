"""Main entry point for the Eisenhower MCP server."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from src.bootstrap.config import Config
from src.bootstrap.container import Container
from src.mcp.server import EisenhowerMCPServer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main server entry point."""
    try:
        config_path = Path("config.yaml")
        if config_path.exists():
            logger.info(f"Loading configuration from {config_path}")
            config = Config.from_yaml(config_path)
        else:
            logger.info("Loading configuration from environment variables")
            config = Config.from_env()
        
        logging.getLogger().setLevel(config.log_level)
        
        container = Container(config)
        await container.initialize()
        
        server = EisenhowerMCPServer(container)
        
        logger.info("Starting Eisenhower MCP server...")
        await server.run()
        
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as e:
        logger.error(f"Server failed: {e}", exc_info=e)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())