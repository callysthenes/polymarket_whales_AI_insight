# 🐋 Polymarket Whale Watcher & AI Analyst

A sophisticated Python bot that monitors [Polymarket](https://polymarket.com) for high-value "Whale" bets and uses AI (DeepSeek + Tavily) to provide market insights and betting recommendations.

## 🌟 Features

*   **🐋 Real-Time Whale Alerts**: Instantly detects and notifies you of bets over $10k (configurable).
*   **🤖 AI Market Analysis**: 
    *   Uses **DeepSeek** LLM to analyze market probability vs. real-world news.
    *   Uses **Tavily** for real-time web search to ground analysis in current events.
    *   Provides "Buy/Sell" recommendations and ROI calculations.
*   **📉 Smart Scheduling (Burst Mode)**:
    *   **Rapid Reports**: Analyzes the top 13 opportunities immediately upon starting (or daily reset).
    *   **Quota Management**: Stops AI analysis once the daily limit (13) is reached to save credits.
    *   **24/7 Whales**: Whale alerts are independent and run 24/7.
    *   **Diversity**: Prioritizes different topics (Politics, Crypto, Tech) to avoid repetition.
*   **💾 Robust Persistence**:
    *   Saves state to `bot_state.json`.
    *   Never misses a whale: Remembers past alerts even after restart.
    *   Deduplicates alerts to prevent spam.
*   **📡 Telegram Support**:
    *   Broadcasts to multiple chats (Private DM & Groups).
    *   Rich HTML formatting with "Bullish/Bearish" sentiment analysis.

## 🛠️ Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/callysthenes/polymarket_whales_AI_insight.git
    cd polymarket_whales_AI_insight
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment**:
    Create a `.env` file (see `.env.example`):
    ```bash
    TELEGRAM_BOT_TOKEN=your_bot_token
    TELEGRAM_CHAT_IDS=123456789,-987654321
    WHALE_THRESHOLD=10000
    DEEPSEEK_API_KEY=your_deepseek_key
    TAVILY_API_KEY=your_tavily_key
    ```
    
    > **Tip**: Use `python3 get_chat_id.py` to find your Telegram Chat IDs.

## 🚀 Usage

Run the bot:
```bash
python3 main.py
```

### Resetting Memory
If you want to re-scan recent history and trigger alerts for existing whales (e.g., after changing the threshold):
```bash
python3 reset_state.py
```

## ⚙️ Configuration (`config.py`)

You can tweak the scheduler settings in `config.py`:
- `MAX_AI_CALLS_PER_DAY`: Daily limit for AI analysis (Default: 13).
- `MIN_SECONDS_BETWEEN_AI_ALERTS`: Delay between AI insights to space them out.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

MIT
