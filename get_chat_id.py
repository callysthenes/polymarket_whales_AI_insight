import time
import requests
from config import TELEGRAM_BOT_TOKEN

TOKEN = TELEGRAM_BOT_TOKEN

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"timeout": 100, "offset": offset}
    response = requests.get(url, params=params)
    return response.json()

def main():
    print("To get your Chat ID:")
    print("1. Direct Message: Send any message to the bot.")
    print("2. Group Chat: Add the bot to the group, then send a message in the group (e.g., /start).")
    print("\nWaiting for messages... (Press Ctrl+C to stop)")
    
    offset = None
    seen_updates = set()
    
    while True:
        try:
            updates = get_updates(offset)
            if "result" in updates and updates["result"]:
                for update in updates["result"]:
                    update_id = update["update_id"]
                    if update_id in seen_updates:
                        continue
                    seen_updates.add(update_id)
                    
                    offset = update_id + 1
                    
                    if "message" in update:
                        chat = update["message"]["chat"]
                        chat_id = chat["id"]
                        chat_type = chat["type"] # private, group, supergroup
                        title = chat.get("title", "Private Chat")
                        user = update["message"].get("from", {}).get("username", "Unknown")
                        
                        print(f"\n📨 RECEIVED MESSAGE:")
                        print(f"   From: @{user}")
                        print(f"   Chat Type: {chat_type.upper()}")
                        print(f"   Chat Title: {title}")
                        print(f"   ID: {chat_id}")
                        print("-" * 30)
                        
                        if "group" in chat_type:
                            print(f"   >>> USE THIS ID FOR GROUPS: {chat_id} <<<")
                            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
            
        time.sleep(1)

if __name__ == "__main__":
    main()
