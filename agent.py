"""
JayTown Congo Intelligence Agent
================================
One agent that sees everything: prices, news, sentiment -> hourly brief.

100% free stack:
- smolagents CodeAgent + Hugging Face free serverless inference (the brain)
- yfinance (market data), DuckDuckGo news (headlines), FinBERT (sentiment)
- GitHub Actions cron = runs 24/7 without your laptop

Usage:
    export HF_TOKEN=hf_xxx        # free token from hf.co/settings/tokens
    python agent.py               # full agent run
    python agent.py --pipeline    # deterministic fallback (no LLM reasoning)
"""

import os
import sys
import json
import datetime as dt

from congo_tools import (
    get_market_data,
    get_congo_news,
    analyze_sentiment,
    save_report,
)

TASK = """
You are the JayTown Congo Intelligence Agent. Produce today's market brief.

Steps:
1. Call get_market_data() for the Congo watchlist quotes.
2. Call get_congo_news() for the latest headlines.
3. Pass the headlines JSON to analyze_sentiment() to get FinBERT sentiment.
4. Write a concise markdown report in English with these sections:
   ## Market Snapshot        (table: ticker, price, day %)
   ## News & Sentiment       (top 8 headlines with sentiment label)
   ## Signal of the Day      (2-4 sentences: what stands out, bullish/bearish tilt)
   ## Kinshasa Stock Exchange Watch (any KSE/IFC/eurobond news found, else say "no new developments")
5. Call save_report() with the full markdown, then give the file path as final answer.

Rules: be factual, never invent prices or headlines. If a tool errors, note it and continue.
"""


def run_agent() -> str:
    """Full agentic run: the LLM decides tool calls and writes the analysis."""
    from smolagents import CodeAgent, InferenceClientModel

    # Explicit model_id: smolagents' default (Qwen3-Next-80B-A3B-Thinking) is not
    # enabled on the free HF Inference router for most accounts. Llama-3.1-8B is.
    model = InferenceClientModel(model_id="meta-llama/Llama-3.1-8B-Instruct")
    agent = CodeAgent(
        tools=[get_market_data, get_congo_news, analyze_sentiment, save_report],
        model=model,
        max_steps=8,
    )
    return agent.run(TASK)


def run_pipeline() -> str:
    """Deterministic fallback: same data, no LLM. Guarantees a report even if
    the free inference tier is rate-limited."""
    market = json.loads(get_market_data())
    news = get_congo_news()
    sentiment = json.loads(analyze_sentiment(news))

    lines = ["## Market Snapshot", "", "| Ticker | Price | Day % |", "|---|---|---|"]
    for q in market:
        if q.get("price") is not None:
            lines.append(f"| {q['ticker']} | {q['price']} {q.get('currency','')} | {q.get('change_pct','–')} |")
    lines += ["", "## News & Sentiment", ""]
    if isinstance(sentiment, list):
        for s in sentiment[:12]:
            if "headline" in s:
                lines.append(f"- **[{s.get('sentiment','?').upper()}]** {s['headline']}")
    else:
        lines.append(f"- Sentiment unavailable: {sentiment.get('error','')}")
    lines += ["", "## Signal of the Day", "",
              "_Pipeline mode (no LLM analysis this run). Raw data above._"]

    path = save_report("\n".join(lines))
    return path


if __name__ == "__main__":
    started = dt.datetime.utcnow().isoformat()
    print(f"[{started}] JayTown Congo Agent starting...")

    if "--pipeline" in sys.argv:
        result = run_pipeline()
    else:
        try:
            result = run_agent()
        except Exception as e:
            print(f"Agent run failed ({e}); falling back to pipeline mode.")
            result = run_pipeline()

    print(f"Done. Result: {result}")
