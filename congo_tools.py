"""
JayTown Congo Intelligence Agent - Tools
=========================================
All tools are 100% free:
- yfinance        -> stock/ETF/commodity prices (no API key)
- ddgs            -> DuckDuckGo news search (no API key)
- HF Inference    -> FinBERT sentiment (free HF token)
"""

import os
import json
import datetime as dt

import requests
from smolagents import tool

HF_TOKEN = os.environ.get("HF_TOKEN", "")

# Congo-related watchlist (all free via Yahoo Finance)
WATCHLIST = {
    "IVN.TO":  "Ivanhoe Mines (TSX) - Kamoa-Kakula copper, DRC",
    "FM.TO":   "First Quantum Minerals (TSX) - copper",
    "GLNCY":   "Glencore ADR - cobalt/copper trader, DRC assets",
    "ERG.IL":  "Eurasian Resources proxy (may be unavailable)",
    "COPX":    "Global X Copper Miners ETF",
    "XME":     "SPDR Metals & Mining ETF",
    "HG=F":    "Copper Futures (COMEX)",
    "CDF=X":   "USD/CDF (Congolese Franc)",
}

NEWS_QUERIES = [
    "Kinshasa Stock Exchange Congo",
    "DR Congo cobalt mining news",
    "Ivanhoe Mines Kamoa Kakula",
    "DRC eurobond IFC World Bank",
    "cobalt copper price AI demand",
]


@tool
def get_market_data() -> str:
    """Fetches latest prices for the Congo watchlist: Ivanhoe Mines, First Quantum,
    Glencore, copper miners ETFs, copper futures and USD/CDF exchange rate.
    Uses Yahoo Finance (free, no API key). Returns a JSON string with
    ticker, name, price, currency, day change percent.

    Returns:
        JSON string with a list of quote objects.
    """
    import yfinance as yf

    results = []
    for ticker, name in WATCHLIST.items():
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
            price = getattr(info, "last_price", None)
            prev = getattr(info, "previous_close", None)
            currency = getattr(info, "currency", "")
            change_pct = None
            if price and prev:
                change_pct = round((price - prev) / prev * 100, 2)
            results.append({
                "ticker": ticker,
                "name": name,
                "price": round(price, 4) if price else None,
                "currency": currency,
                "change_pct": change_pct,
            })
        except Exception as e:
            results.append({"ticker": ticker, "name": name, "error": str(e)[:120]})
    return json.dumps(results, ensure_ascii=False)


@tool
def get_congo_news(max_per_query: int = 4) -> str:
    """Searches DuckDuckGo News (free, no API key) for the latest headlines about
    the Kinshasa Stock Exchange, DRC mining, cobalt/copper and Congo macro news.

    Args:
        max_per_query: Max number of headlines per search query (default 4).

    Returns:
        JSON string with a list of {query, title, source, date, url} objects.
    """
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS

    headlines = []
    with DDGS() as ddgs_client:
        for q in NEWS_QUERIES:
            try:
                for r in ddgs_client.news(q, max_results=max_per_query):
                    headlines.append({
                        "query": q,
                        "title": r.get("title", ""),
                        "source": r.get("source", ""),
                        "date": r.get("date", ""),
                        "url": r.get("url", ""),
                    })
            except Exception as e:
                headlines.append({"query": q, "error": str(e)[:120]})
    return json.dumps(headlines, ensure_ascii=False)


@tool
def analyze_sentiment(headlines_json: str) -> str:
    """Runs FinBERT financial sentiment analysis (positive/negative/neutral) on a
    list of news headlines, using the free Hugging Face Inference API in one
    batched request.

    Args:
        headlines_json: JSON string with a list of objects that contain a "title"
            field (the output of get_congo_news), or a JSON list of plain strings.

    Returns:
        JSON string pairing each headline with its sentiment label and score.
    """
    items = json.loads(headlines_json)
    texts = []
    for it in items:
        if isinstance(it, str):
            texts.append(it)
        elif isinstance(it, dict) and it.get("title"):
            texts.append(it["title"])
    texts = texts[:30]  # stay well within free tier

    if not texts:
        return json.dumps({"error": "no headlines to analyze"})

    url = "https://router.huggingface.co/hf-inference/models/ProsusAI/finbert"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
    payload = {"inputs": texts, "parameters": {"top_k": 3, "function_to_apply": "softmax"}}

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        raw = resp.json()
    except Exception as e:
        return json.dumps({"error": f"HF inference failed: {str(e)[:200]}"})

    out = []
    for text, scores in zip(texts, raw):
        try:
            best = max(scores, key=lambda s: s["score"])
            out.append({
                "headline": text,
                "sentiment": best["label"],
                "score": round(best["score"], 3),
            })
        except Exception:
            out.append({"headline": text, "sentiment": "unknown"})
    return json.dumps(out, ensure_ascii=False)


@tool
def save_report(markdown_report: str) -> str:
    """Saves the final intelligence report as a timestamped markdown file in the
    reports/ folder, and updates reports/latest.md. Call this exactly once at the
    end with the complete report.

    Args:
        markdown_report: The full report in markdown format.

    Returns:
        The path of the saved report file.
    """
    ts = dt.datetime.utcnow().strftime("%Y-%m-%d_%H%M")
    os.makedirs("reports", exist_ok=True)
    path = f"reports/congo_brief_{ts}.md"
    header = f"# JayTown Congo Intelligence Brief\n\n_Generated (UTC): {ts}_\n\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + markdown_report)
    with open("reports/latest.md", "w", encoding="utf-8") as f:
        f.write(header + markdown_report)
    return path
