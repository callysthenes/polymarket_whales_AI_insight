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
        
        # --- SMART MONEY SCAN (Every 10 mins approx) ---
        last_smart_scan = state.get("last_smart_scan_ts", 0)
        if time.time() - last_smart_scan > 600: # 10 minutes
            logger.info("Running Smart Money Scan...")
            try:
                import smart_follower
                opportunities = smart_follower.analyze_smart_money()
                notified_positions = set(state.get("smart_positions", []))
                
                for op in opportunities:
                    # Create unique ID for this position state
                    # address + slug + outcome + approx_size_tier
                    # We want to re-alert if they drastically increase size? 
                    # For now, unique id = trader + slug + outcome.
                    # Actually, if they hold it, we alert once.
                    pos_id = f"{op['trader']}-{op['position']['slug']}-{op['position']['outcome']}"
                    
                    if pos_id in notified_positions:
                        continue
                        
                    # Format Message
                    trader_short = op['trader'][:6]
                    val = op['position']['value']
                    outcome = op['position']['outcome']
                    mkt = op['position']['market']
                    
                    smart_msg = (
                        f"🧠 <b>SMART MONEY ALERT</b> 🧠\n"
                        f"<b>Leaderboard Trader:</b> {trader_short}...\n"
                        f"<b>Holding:</b> ${val:,.0f} on <b>{outcome}</b>\n"
                        f"<b>Market:</b> {mkt}\n"
                        f"<i>Replicate this position?</i>\n"
                        f"<b>Link:</b> <a href='https://polymarket.com/event/{op['position']['slug']}'>View Market</a>"
                    )
                    
                    if notifier.send_message(smart_msg):
                        notified_positions.add(pos_id)
                        logger.info(f"Smart Money Alert sent: {trader_short} on {mkt}")
                        
                state["smart_positions"] = list(notified_positions)
                state["last_smart_scan_ts"] = time.time()
                
            except Exception as e:
                logger.error(f"Smart Money Scan failed: {e}")
        
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
    
    # Burst Loop: Keep sending until budget hit or no candidates
    while True:
        count = ai_usage["count"]
        last_sent = ai_usage["last_sent_ts"]
        now = time.time()
        
        # Check Budget
        if count >= MAX_AI_CALLS_PER_DAY:
            logger.info("Daily AI Budget Reached.")
            return

        # Check Interval (Skipped if we haven't sent anything recently, OR if we are in Burst Mode)
        # If we just sent one (last_sent is roughly now), we normally wait.
        # But if MIN_SECONDS is small (<60), we assume Burst Mode and ignore wait relative to LAST send in this loop.
        # However, we must ensure we don't violate rate limits if we loop fast.
        if MIN_SECONDS_BETWEEN_AI_ALERTS >= 60:
             if now - last_sent < MIN_SECONDS_BETWEEN_AI_ALERTS:
                 return # Too soon for normal scheduler

        if not insight_candidates:
            return

        # --- SCORING ---
        cat_usage = ai_usage.get("categories", {})
        scored_candidates = []
        for cand in insight_candidates:
            cat = cand.get('event_category', 'other')
            usage = cat_usage.get(cat, 0)
            adjusted_score = cand['score'] / (1 + (usage * 50)) 
            scored_candidates.append((adjusted_score, cand))
        
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        # Pick Best
        best = None
        best_score = 0
        
        for score, cand in scored_candidates:
            last_event_ts = state["insights"].get(cand['event_slug'], 0)
            if now - last_event_ts < 21600: 
                continue
            best = cand
            best_score = score
            break
            
        if not best:
            return # No valid candidates

        # Remove chosen from candidates immediately so we don't pick it again in next iteration of while loop
        if best in insight_candidates:
            insight_candidates.remove(best)

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
                state["ai_usage"]["count"] += 1
                state["ai_usage"]["last_sent_ts"] = time.time()
                state["insights"][best['event_slug']] = time.time()
                
                cat = best.get('event_category', 'other')
                state["ai_usage"]["categories"][cat] = cat_usage.get(cat, 0) + 1
                
                logger.info("Insight sent successfully.")
                
            # Sleep slightly to avoid Telegram 429
            time.sleep(3)
                
        except Exception as e:
            logger.error(f"Scheduler failed to send insight: {e}")
            break # Break loop on error logic


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
