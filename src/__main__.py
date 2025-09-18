
from __future__ import annotations

import asyncio
import logging
import sys

from src.bootstrap.settings.settings import Settings
from src.bootstrap.container import Container
from src.mcp.server import EisenhowerMCPServer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    try:
        logger.info("Loading configuration from environment variables and .env file")
        settings = Settings.from_env()
        
        logging.getLogger().setLevel(settings.app.log_level)
        
        container = Container(settings)
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