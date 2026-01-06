import requests
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GAMMA_API_URL = "https://gamma-api.polymarket.com"
CLOB_API_URL = "https://clob.polymarket.com"

def fetch_expiring_events(hours_ahead=24, categories=None):
    """
    Fetches events expiring within the next `hours_ahead`.
    filtering by `categories` if provided (list of strings).
    """
    if categories is None:
        categories = []
        
    # Calculate time window
    now = datetime.utcnow()
    end_time = now + timedelta(hours=hours_ahead)
    
    # Categories mapping to handle user friendly names vs probable tags
    # We will search for these tags loosely
    normalized_categories = [c.lower() for c in categories]
    
    # Standard query params
    params = {
        "closed": "false",
        "limit": 100,
        "offset": 0,
        "order": "endDate",
        "ascending": "true"
    }
    
    relevant_events = []
    
    try:
        response = requests.get(f"{GAMMA_API_URL}/events", params=params)
        response.raise_for_status()
        events = response.json()
        
        # Depending on API structure, it might return a list or a dict with 'data'
        if isinstance(events, dict) and 'data' in events: # Just in case generic wrapper
            events = events['data']
            
        for event in events:
            # Check expiration
            if 'endDate' not in event:
                continue
            
            # Parse endDate (usually ISO)
            try:
                # API dates typically have 'Z' or offset.
                # using replace to handle naive vs aware if needed, but naive UTC is standard here.
                # Let's assume input is Z ending.
                expiry_str = event['endDate'].replace('Z', '+00:00')
                expiry_dt = datetime.fromisoformat(expiry_str)
                # Ensure UTC
                if expiry_dt.tzinfo is not None:
                    expiry_dt = expiry_dt.astimezone(datetime.utcnow().astimezone().tzinfo).replace(tzinfo=None) # straightforward convert to naive UTC or keep aware.
                    # Simpler: compare with aware now.
                    # Let's stick to comparing ISO strings if format matches, or robust parsing.
                
                # Re-do with robust compatible method
                # Gamma returns "2024-01-01T00:00:00Z"
                event_end = datetime.fromisoformat(event['endDate'].replace('Z', ''))
                
                if not (now < event_end <= end_time):
                    # If sorted by endDate, once we pass end_time, we can stop? 
                    # Yes, if strictly sorted.
                    if event_end > end_time:
                         # Since we sorted ascending, if this one is too far in future, stop.
                         # Wait, current params get *oldest* first?
                         # "ascending=true" on endDate means: closest dates first (e.g. tomorrow) vs (next year)?
                         # Yes. 2024 < 2025.
                         # But we also need to ensure we don't pick expired ones. closed=false should handle that.
                         break
                
                # Check Category
                # Event structure usually has 'tags' which is a list of objects or strings.
                # Let's log one to see structure if debugging, or assume standard.
                # Standard is usually a list of dicts: [{'label': 'Politics', ...}] or strings.
                # Let's assume verify logic below.
                
                # Logic: if categories provided, event must match AT LEAST ONE.
                if normalized_categories:
                    event_tags = []
                    # Check 'tags' (list of dicts or strings)
                    if 'tags' in event:
                         for t in event['tags']:
                             if isinstance(t, dict):
                                 event_tags.append(t.get('label', '').lower())
                                 event_tags.append(t.get('slug', '').lower())
                             else:
                                 event_tags.append(str(t).lower())
                    
                    found_match = False
                    for cat in normalized_categories:
                        # Exact match or substring match (e.g. "us politics" matches "politics")
                        for tag in event_tags:
                            if cat in tag or tag in cat:
                                found_match = True
                                break
                        if found_match:
                            break
                    if not found_match:
                        continue
                        
                relevant_events.append(event)
                
            except Exception as e:
                logger.error(f"Error parsing event {event.get('id')}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        
    return relevant_events

def analyze_market_activity(trades):
    """
    Analyzes a list of trades to generate insights.
    Returns a dict with metrics if significant activity is found, else None.
    """
    if not trades:
        return None
        
    total_volume = 0
    buy_volume = 0
    sell_volume = 0
    count = len(trades)
    
    # Simple price movement check
    # trade list is usually newest first? Need to verify. 
    # Let's assume passed in order or we sort.
    # Data API trades usually return newest first.
    
    sorted_trades = sorted(trades, key=lambda x: x.get('timestamp', 0))
    if not sorted_trades:
        return None
        
    start_price = float(sorted_trades[0].get('price', 0))
    end_price = float(sorted_trades[-1].get('price', 0))
    price_change = end_price - start_price
    
    for t in trades:
        try:
            p = float(t.get('price', 0))
            s = float(t.get('size', 0))
            val = p * s
            total_volume += val
            
            side = t.get('side', '').upper()
            if side == 'BUY':
                buy_volume += val
            elif side == 'SELL':
                sell_volume += val
        except:
            continue
            
    # Define "Interesting" criteria
    # e.g. High volume in short window, or large price swing
    
    is_interesting = False
    reasons = []
    
    if total_volume > 5000: # Arbitrary "decent activity" threshold for the fetched window
        is_interesting = True
        reasons.append(f"High Volume (${total_volume:,.0f})")
        
    if abs(price_change) > 0.05: # 5 cent move
        is_interesting = True
        direction = "📈 Raging Up" if price_change > 0 else "📉 Crashing Down"
        reasons.append(f"{direction} ({price_change:+.2f})")
        
    if not is_interesting:
        return None
        
    return {
        "total_volume": total_volume,
        "buy_volume": buy_volume,
        "sell_volume": sell_volume,
        "start_price": start_price,
        "end_price": end_price,
        "price_change": price_change,
        "trade_count": count,
        "reasons": reasons
    }

def fetch_recent_trades(market_id):
    """
    Fetch recent trades for a given market_id (asset_id or condition_id).
    Using CLOB API or Data API.
    GET /trades?market=...
    """
    # Try Data API first or CLOB. Data API is usually good for history.
    # Endpoint: https://data-api.polymarket.com/trades?market=TOKEN_ID
    # However market structure in Event has 'markets' list. Each market has 'clobTokenIds'.
    
    # We need to be careful with IDs. 
    # The 'market' in Gamma Event is just metadata. We need the 'clobTokenIds' or 'asset_id'.
    # For simplicity, we'll try to get trades by market ID if the API supports it, or iterate tokens (Yes/No tokens).
    
    trades = []
    # Implementation placeholder - need to see actual market structure to pick correct ID.
    # Assuming market_id passed is the clobTokenId (the asset ID for Yes or No).
    
    url = f"https://data-api.polymarket.com/trades?market={market_id}&limit=50"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            trades = r.json()
    except Exception as e:
        logger.error(f"Error fetching trades for {market_id}: {e}")
        
    return trades
