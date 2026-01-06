import json
import os

STATE_FILE = "bot_state.json"

def reset_trades():
    if not os.path.exists(STATE_FILE):
        print("No state file found.")
        return
        
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            
        print(f"Clearing {len(data.get('trades', []))} remembered trades...")
        data["trades"] = [] # Clear trades so they are re-alerted
        
        # Don't clear 'insights' or 'ai_usage' to keep budget intact
        # Don't clear 'insights' or 'ai_usage' to keep budget intact
        print(f"Keeping AI Usage (Count: {data.get('ai_usage', {}).get('count', 0)})")
        data["ai_usage"]["count"] = 0
        data["insights"] = {} # Clear past insights history to allow re-send
        
        # Clear legacy smart alerts
        data["smart_positions"] = []
        data["last_smart_scan_ts"] = 0 
        
        print("   -> AI Budget, History & Smart Alerts RESET for testing.")
        
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)
            
        print("Done! Run main.py now to see historical alerts.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    reset_trades()
