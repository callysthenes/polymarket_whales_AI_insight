import requests
import re
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmartFollower")

LEADERBOARD_URL = "https://polymarket.com/leaderboard?window=month&category={}"
POSITIONS_API = "https://data-api.polymarket.com/positions?user={}"

def get_top_traders(category="politics"):
    """
    Scrapes the Polymarket Leaderboard page to find top trader profiles for a category.
    Returns a list of dicts: {'name': str, 'address': str}
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        }
        url = LEADERBOARD_URL.format(category)
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to fetch leaderboard for {category}: {response.status_code}")
            return []
            
        html = response.text
        
        # Regex to find profiles: href="/profile/0x..." or similar
        # Pattern: <a href="/profile/(0x[a-fA-F0-9]+)" ... >(Name)</a>
        matches = re.findall(r'href="/profile/(0x[a-fA-F0-9]{40})"', html)
        
        # Deduplicate but KEEP ORDER (Leaderboard rank matters!)
        # matches list in regex order which is usually page order (Rank 1, 2, 3...)
        seen = set()
        traders = []
        for addr in matches:
            if addr not in seen:
                traders.append({"address": addr, "name": f"Trader-{addr[:6]}"})
                seen.add(addr)
                
        logger.info(f"Found {len(traders)} top traders for {category}.")
        return traders
        
    except Exception as e:
        logger.error(f"Error scraping leaderboard for {category}: {e}")
        return []

def get_active_positions(user_address):
    """
    Fetches active positions for a user.
    """
    url = POSITIONS_API.format(user_address)
    try:
        r = requests.get(url)
        if r.status_code != 200:
            return []
            
        all_positions = r.json()
        active = []
        
        for pos in all_positions:
            try:
                size = float(pos.get('size', 0))
                if size < 10: # Filter dust
                    continue
                    
                # We want "active" positions that verify the "clean track"
                # But mostly we just want to see what they are holding NOW.
                
                market_slug = pos.get('slug', '')
                outcome = pos.get('outcome', '')
                
                active.append({
                    'market': pos.get('title'),
                    'slug': market_slug,
                    'outcome': outcome,
                    'size': size,
                    'value': float(pos.get('currentValue', 0)),
                    'price': float(pos.get('avgPrice', 0))
                })
            except:
                continue
                
        return active
        
    except Exception as e:
        logger.error(f"Error fetching positions for {user_address}: {e}")
        return []

def analyze_smart_money():
    """
    Orchestrator: Get top traders for key categories, check their positions.
    """
    categories = ["politics", "economics", "technology"] # User requested topics
    opportunities = []
    
    for cat in categories:
        traders = get_top_traders(cat)
        
        # "As soon as you see a user in the top 5 ... place a bet alert"
        # We process the top 5 for this category.
        for trader in traders[:5]:
            positions = get_active_positions(trader['address'])
            if not positions:
                continue
                
            # Strategy: Find their LARGEST conviction bet (or all significant ones?)
            # User said: "place a bet alert, otherwise show all present bets"
            # We'll show their TOP position as a proxy for "best bet".
            
            sorted_pos = sorted(positions, key=lambda x: x['value'], reverse=True)
            if sorted_pos:
                top_pick = sorted_pos[0]
                if top_pick['value'] > 1000: # Significant size
                    opportunities.append({
                        'trader': trader['address'],
                        'category': cat,
                        'position': top_pick
                    })
                
    return opportunities

if __name__ == "__main__":
    # Test run
    opps = analyze_smart_money()
    for o in opps:
        print(f"Trader {o['trader'][:6]} is betting ${o['position']['value']:.0f} on {o['position']['outcome']} ({o['position']['market']})")
