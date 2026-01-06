import os

def load_env(filepath=".env"):
    """Simple .env loader since python-dotenv is missing"""
    if not os.path.exists(filepath):
        return
    
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

# Load env immediately on import
load_env()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Parse list of IDs
chat_ids_str = os.getenv("TELEGRAM_CHAT_IDS", "")
# Support legacy single ID env var if new one missing
if not chat_ids_str:
    chat_ids_str = os.getenv("TELEGRAM_CHAT_ID", "")
    
TELEGRAM_CHAT_IDS = [x.strip() for x in chat_ids_str.split(",") if x.strip()]

WHALE_THRESHOLD = float(os.getenv("WHALE_THRESHOLD", "10000"))
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Optimization Constraints
MAX_AI_CALLS_PER_DAY = 13 # 1000/month ~= 33/day
MIN_SECONDS_BETWEEN_AI_ALERTS = 30 # Burst Mode: Send insights rapidly until limit hit
