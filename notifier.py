import requests
import logging
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS

logger = logging.getLogger(__name__)

def send_message(message):
    """Sends a message to ALL configured Telegram chats."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set.")
        return False
    if not TELEGRAM_CHAT_IDS:
        logger.error("No TELEGRAM_CHAT_IDS set.")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    success_any = False
    
    for chat_id in TELEGRAM_CHAT_IDS:
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            success_any = True
        except Exception as e:
            logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
            
    return success_any
