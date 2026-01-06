import time
import logging
from datetime import datetime
import polymarket_api
import notifier
import ai_analyst
import state_manager
from config import WHALE_THRESHOLD, MAX_AI_CALLS_PER_DAY, MIN_SECONDS_BETWEEN_AI_ALERTS

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("WhaleWatcher")

# In-memory queue for insight candidates: list of dicts
insight_candidates = []

def monitor_markets(state):
    try:
        logger.info("Starting checks...")
        
        # 1. Fetch expiring events
        categories = [
            "politics", "geopolitics", "finance", "crypto", 
            "elections", "tech", "culture", "world", "breaking"
        ]
        events = polymarket_api.fetch_expiring_events(hours_ahead=24, categories=categories)
        logger.info(f"Found {len(events)} relevant expiring events.")
        
        notified_trade_ids = set(state["trades"])
        
        for event in events:
            event_title = event.get('title', 'Unknown Event')
            event_slug = event.get('slug', '')
            
            # Simple Category detection (naively check if slug/title contains category keyword)
            # Better: Pass category from fetch_expiring_events if possible, or guess.
            # We'll try to guess from the event tags.
            event_category = "other"
            if 'tags' in event:
                for t in event['tags']:
                    tag_str = str(t).lower()
                    if 'label' in t: tag_str = t['label'].lower()
                    if tag_str in categories:
                        event_category = tag_str
                        break
            
            markets = event.get('markets', [])
            
            for market in markets:
                market_id = market.get('id')
                market_question = market.get('question', 'Unknown Market')
                
                # Fetch trades
                trades = polymarket_api.fetch_recent_trades(market_id)
                
                # --- INSIGHTS COLLECTION ---
                analysis = polymarket_api.analyze_market_activity(trades)
                if analysis:
                    score = analysis['total_volume'] + (abs(analysis['price_change']) * 10000)
                    
                    candidate = {
                        'score': score,
                        'event_title': event_title,
                        'event_slug': event_slug,
                        'event_category': event_category,
                        'market_question': market_question,
                        'analysis': analysis,
                        'timestamp': time.time()
                    }
                    insight_candidates.append(candidate)

                # --- WHALE CHECK (INSTANT) ---
                for trade in trades:
                    try:
                        price = float(trade.get('price', 0))
                        size = float(trade.get('size', 0))
                        trade_value = price * size
                        
                        if trade_value >= WHALE_THRESHOLD:
                            trade_id = trade.get('matchId') or trade.get('id') or f"{market_id}-{trade.get('timestamp')}-{size}"
                            
                            if trade_id in notified_trade_ids:
                                continue
                                
                            # New Whale Trade!
                            side = trade.get('side', 'Trade').upper()
                            outcome_token = "YES" # Default assumption for main market view; could be NO if specified in data
                            
                            # Determine sentiment
                            action_str = f"{side}ING {outcome_token}"
                            sentiment = "🐂 BULLISH" if side == "BUY" else "🐻 BEARISH"
                            
                            emoji = "🐋" # Default requested by user
                            if trade_value > 50000: emoji = "🐋🚨🐋"
                            
                            trade_prob = price * 100
                            
                            msg = (
                                f"{emoji} <b>WHALE ALERT!</b> {emoji}\n\n"
                                f"<b>Event:</b> {event_title}\n"
                                f"<b>Market:</b> {market_question}\n"
                                f"<b>Action:</b> {action_str} ({sentiment})\n"
                                f"<b>Amount:</b> ${trade_value:,.2f}\n"
                                f"<b>Price:</b> {price} ({trade_prob:.1f}% Odds)\n"
                                f"<b>Link:</b> <a href='https://polymarket.com/event/{event_slug}'>View Market</a>"
                            )
                            
                            if notifier.send_message(msg):
                                notified_trade_ids.add(trade_id)
                                logger.info(f"Whale Alert sent: {trade_value} on {event_title}")
                                
                    except Exception as e:
                        logger.error(f"Error processing trade: {e}")

        # Update State (Trades)
        state["trades"] = list(notified_trade_ids)
        
        # --- SCHEDULER: PROCESS INSIGHTS ---
        process_scheduler(state)
        
        # Save State
        state = state_manager.cleanup_state(state)
        state_manager.save_state(state)
        
    except Exception as e:
        logger.error(f"Error in monitor loop: {e}")

def process_scheduler(state):
    """Checks budget and interval, then sends best insight."""
    global insight_candidates
    
    ai_usage = state["ai_usage"]
    count = ai_usage["count"]
    last_sent = ai_usage["last_sent_ts"]
    cat_usage = ai_usage.get("categories", {})
    now = time.time()
    
    # Check Constraints
    if count >= MAX_AI_CALLS_PER_DAY:
        return # Budget exhausted
        
    if now - last_sent < MIN_SECONDS_BETWEEN_AI_ALERTS:
        return # Too soon
        
    if not insight_candidates:
        return
        
    # --- SCORING WITH DIVERSITY ---
    # We want to pick a candidate whose category has LOW usage.
    # New Score = Raw Score / (1 + CategoryUsageCount*10)
    
    scored_candidates = []
    for cand in insight_candidates:
        cat = cand.get('event_category', 'other')
        usage = cat_usage.get(cat, 0)
        
        # Diversity Penalty: Drastically reduce score if we already covered this topic today
        adjusted_score = cand['score'] / (1 + (usage * 50)) 
        
        scored_candidates.append((adjusted_score, cand))
    
    # Sort by Adjusted Score
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    
    # Pick Best
    best_score, best = scored_candidates[0]
    
    # Removing from queue happens via timestamp cleanup mainly, 
    # but we should remove this specific one to avoid sending it again?
    # Actually, state['insights'] handles dedup per event.
    
    last_event_ts = state["insights"].get(best['event_slug'], 0)
    if now - last_event_ts < 21600: 
        # Skip this one, try next best?
        # For simplicity, if best is blocked, we wait next loop. 
        # (Or we could iterate list, but lets keep it simple).
        return

    # --- EXECUTE AI ANALYSIS ---
    logger.info(f"SCHEDULER: Triggering AI Analysis for {best['event_title']} (Cat: {best['event_category']}, Score: {best_score:.0f})")
    
    try:
        market_question = best['market_question']
        analysis = best['analysis']
        
        ai_report = ai_analyst.analyze_opportunity(
            market_question=market_question,
            outcomes=["Outcome"], 
            current_prices=[str(analysis['end_price'])]
        )
        
        reasons_str = ", ".join(analysis['reasons'])
        ai_section = f"\n\n🤖 <b>AI Advisory:</b>\n{ai_report}" if ai_report else ""
        
        msg = (
            f"⚡ <b>Daily Market Insight</b> ⚡\n"
            f"<i>(Topic: {best['event_category'].upper()} | Budget: {count + 1}/{MAX_AI_CALLS_PER_DAY})</i>\n\n"
            f"<b>Event:</b> {best['event_title']}\n"
            f"<b>Market:</b> {market_question}\n"
            f"<b>Activity:</b> {reasons_str}\n"
            f"<b>Vol:</b> ${analysis['total_volume']:,.0f}\n"
            f"<b>Price:</b> {analysis['end_price']}\n"
            f"<b>Link:</b> <a href='https://polymarket.com/event/{best['event_slug']}'>View Market</a>"
            f"{ai_section}"
        )
        
        if notifier.send_message(msg):
            # Update State
            state["ai_usage"]["count"] += 1
            state["ai_usage"]["last_sent_ts"] = now
            state["insights"][best['event_slug']] = now
            
            # Increment Category Usage
            cat = best.get('event_category', 'other')
            state["ai_usage"]["categories"][cat] = cat_usage.get(cat, 0) + 1
            
            logger.info("Insight sent successfully.")
            
    except Exception as e:
        logger.error(f"Scheduler failed to send insight: {e}")

    # Cleanup old candidates
    insight_candidates = [c for c in insight_candidates if now - c['timestamp'] < 3600]

def main():
    logger.info("Polymarket Whale Watcher Started (Diversity Scheduler)")
    if not notifier.TELEGRAM_CHAT_IDS:
        logger.warning("Telegram Chat IDs not set!")
    
    state = state_manager.load_state()
    logger.info(f"Loaded state. AI Usage today: {state['ai_usage']['count']}/{MAX_AI_CALLS_PER_DAY}")
    
    while True:
        monitor_markets(state)
        logger.info("Sleeping for 60 seconds...")
        time.sleep(60)

if __name__ == "__main__":
    main()
