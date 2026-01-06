import requests
import re
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmartFollower")

LEADERBOARD_URL = "https://polymarket.com/leaderboard"
POSITIONS_API = "https://data-api.polymarket.com/positions?user={}"

def get_top_traders():
    """
    Scrapes the Polymarket Leaderboard page to find top trader profiles.
    Returns a list of dicts: {'name': str, 'address': str}
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        }
        response = requests.get(LEADERBOARD_URL, headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to fetch leaderboard: {response.status_code}")
            return []
            
        html = response.text
        
        # Regex to find profiles: href="/profile/0x..." or similar
        # Pattern: <a href="/profile/(0x[a-fA-F0-9]+)" ... >(Name)</a>
        # This is rough scraping.
        
        # Let's find all addresses first
        # Format in HTML usually: href="/profile/0x123..."
        matches = re.findall(r'href="/profile/(0x[a-fA-F0-9]{40})"', html)
        
        # Deduplicate
        addresses = list(set(matches))
        logger.info(f"Found {len(addresses)} top traders on leaderboard.")
        
        traders = []
        for addr in addresses:
            traders.append({"address": addr, "name": f"Trader-{addr[:6]}"}) # Name is hard to extract reliably with simple regex without soup
            
        return traders
        
    except Exception as e:
        logger.error(f"Error scraping leaderboard: {e}")
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
    Orchestrator: Get top traders, check their positions, return improved candidates.
    """
    traders = get_top_traders()
    opportunities = []
    
    # Check the first 50 to avoid rate limits/spam
    # In production we might want to cache this list and only check new ones.
    for trader in traders[:10]:
        positions = get_active_positions(trader['address'])
        if not positions:
            continue
            
        # Strategy: Find their LARGEST conviction bet
        # "Filter for clean track" -> Ideally we'd check their PnL history.
        # Here we assume Leaderboard presence = Good.
        # We look for high conviction (large size).
        
        sorted_pos = sorted(positions, key=lambda x: x['value'], reverse=True)
        if sorted_pos:
            top_pick = sorted_pos[0]
            if top_pick['value'] > 1000: # Only significant bets
                opportunities.append({
                    'trader': trader['address'],
                    'position': top_pick
                })
                
    return opportunities

if __name__ == "__main__":
    # Test run
    opps = analyze_smart_money()
    for o in opps:
        print(f"Trader {o['trader'][:6]} is betting ${o['position']['value']:.0f} on {o['position']['outcome']} ({o['position']['market']})")
