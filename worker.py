import asyncio
import logging
from quizbotafi import safe_run_bot, client   # ✅ import from quizbotafi

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    logging.info("🚀 Starting Telegram bot worker on Heroku...")
    asyncio.run(safe_run_bot())