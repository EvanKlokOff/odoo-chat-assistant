import asyncio
import logging
from src.config import settings
from src.interfaces.telegram.bot import start_bot, stop_bot
import warnings
from src import logging_config

warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core._api.deprecation")

logger = logging_config.setup_logging()


async def main():
    """Main entry point"""
    logger.info("Starting Chat Analyzer Bot...")

    try:
        # Start Telegram bot
        if settings.telegram_bot_token:
            logger.info("Initializing Telegram interface...")
            await start_bot()
        else:
            logger.warning("TELEGRAM_BOT_TOKEN not set, Telegram interface disabled")

    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await stop_bot()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())