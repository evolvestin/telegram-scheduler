import os
import requests
import logging

logger = logging.getLogger(__name__)

class TelegramSender:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_DEV_CHAT_ID')

    def send_dev_log(self, level, module, message):
        if not self.bot_token or not self.chat_id:
            return

        text = f"🚨 **{level}** in `{module}`\n\n{message}"
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        try:
            requests.post(url, json={
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }, timeout=5)
        except Exception as e:
            # Avoid infinite recursion in logging
            print(f"Failed to send log to Telegram: {e}")