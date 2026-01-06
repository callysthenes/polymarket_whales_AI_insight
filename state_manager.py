import json
import os
import logging
import time

logger = logging.getLogger(__name__)

STATE_FILE = "bot_state.json"

def load_state():
    """Loads notified trades and insights from disk."""
    if not os.path.exists(STATE_FILE):
        return {"trades": [], "insights": {}}
        
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            # Migration/Validation if needed
            if "trades" not in data: data["trades"] = []
            if "insights" not in data: data["insights"] = {}
            if "ai_usage" not in data: 
                data["ai_usage"] = {
                    "count": 0, 
                    "date": time.strftime("%Y-%m-%d"),
                    "last_sent_ts": 0,
                    "categories": {}
                }
            # Migration for existing ai_usage without categories
            if "categories" not in data["ai_usage"]:
                data["ai_usage"]["categories"] = {}
                
            return data
    except Exception as e:
        logger.error(f"Failed to load state: {e}")
        return {"trades": [], "insights": {}, "ai_usage": {"count": 0, "date": time.strftime("%Y-%m-%d"), "last_sent_ts": 0, "categories": {}}}

def save_state(state):
    """Saves state to disk."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")

def cleanup_state(state):
    """Removes old entries and resets daily counters."""
    # Reset daily counter if day changed
    today = time.strftime("%Y-%m-%d")
    if state["ai_usage"]["date"] != today:
        state["ai_usage"]["count"] = 0
        state["ai_usage"]["date"] = today
        state["ai_usage"]["categories"] = {}
        
    # Remove old trades (keep last 5000)
    if len(state["trades"]) > 5000:
        state["trades"] = state["trades"][-5000:]
        
    # Remove old insights (older than 24h)
    now = time.time()
    new_insights = {}
    for k, timestamp in state["insights"].items():
        if now - timestamp < 86400: # 24h
            new_insights[k] = timestamp
    state["insights"] = new_insights
    
    return state
