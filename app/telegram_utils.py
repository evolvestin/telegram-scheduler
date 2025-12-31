import asyncio
import logging
from telethon import TelegramClient, errors
from django.conf import settings

logger = logging.getLogger(__name__)

class TelethonWrapper:
    def __init__(self, session_path, api_id, api_hash):
        self.session_path = session_path
        self.api_id = api_id
        self.api_hash = api_hash
        self.client = None

    async def __aenter__(self):
        self.client = TelegramClient(self.session_path, self.api_id, self.api_hash)
        await self.client.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.disconnect()

    async def send_message(self, target, text, file=None):
        if not await self.client.is_user_authorized():
            raise Exception(f"Session {self.session_path} not authorized.")
        
        try:
            await self.client.send_message(target, text, file=file)
        except errors.FloodWaitError as e:
            logger.warning(f"FloodWaitError: Need to sleep {e.seconds} seconds")
            raise e 
        except Exception as e:
            logger.error(f"Failed to send to {target}: {e}")
            raise e

def run_sync(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()