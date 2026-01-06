import requests
import json
import logging
from config import DEEPSEEK_API_KEY, TAVILY_API_KEY

logger = logging.getLogger(__name__)

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions" # Standard Endpoint
TAVILY_URL = "https://api.tavily.com/search"

def search_tavily(query):
    """Searches the web for context using Tavily."""
    if not TAVILY_API_KEY:
        return None
        
    try:
        payload = {
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "basic",
            "include_answer": False,
            "max_results": 3
        }
        response = requests.post(TAVILY_URL, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Format results
        results = []
        for res in data.get("results", []):
            results.append(f"- {res.get('title')}: {res.get('content')}")
            
        return "\n".join(results)
    except Exception as e:
        logger.error(f"Tavily search failed: {e}")
        return None

def analyze_opportunity(market_question, outcomes, current_prices):
    """
    Uses DeepSeek to analyze the betting opportunity.
    market_question: str
    outcomes: list of outcome names (e.g. ["Yes", "No"])
    current_prices: list of prices corresponding to outcomes
    """
    if not DEEPSEEK_API_KEY:
        logger.error("DeepSeek API Key missing.")
        return None
        
    # 1. Get External Context
    search_context = search_tavily(market_question) or "No recent news found."
    
    # 2. Build Prompt
    prompt = f"""
    You are a professional prediction market analyst. 
    Analyze the likelihood of the following event expiring in 24 hours: "{market_question}".
    
    Current Market Prices:
    {', '.join([f'{o}: ${p}' for o, p in zip(outcomes, current_prices)])}
    
    Recent News Context:
    {search_context}
    
    Task:
    1. Analyze the news and current situation.
    2. Provide a recommendation on which outcome is most likely associated with the current price (is it undervalued?).
    3. Calculate potential profit for a $1000 bet if the user bets on your recommended outcome and wins (Price 1.00 at expiry).
       Profit Formula: (1000 / Price) * 1.00 - 1000.
    
    Output Format (HTML-supported for Telegram):
    <b>Analysis:</b> [Brief reasoning]
    <b>Recommendation:</b> [BUY YES/NO]
    <b>Risk:</b> [High/Medium/Low]
    <b>Potential Win:</b> $[Amount] (ROI: [Percent]%)
    """
    
    try:
        response = requests.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        content = result['choices'][0]['message']['content']
        return content
    except Exception as e:
        logger.error(f"DeepSeek analysis failed: {e}")
        return None
