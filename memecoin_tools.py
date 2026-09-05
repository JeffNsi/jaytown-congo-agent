"""
Memecoin Research Agent - Tools
================================
Free-stack tools for early-stage memecoin due diligence, built on the same
philosophy as congo_tools.py: no paid API keys required to get useful signal,
but every tool is explicit about what it can and cannot see.

Data sources:
- DexScreener public API   -> pairs, liquidity, volume, txns, socials (no key)
- DuckDuckGo (ddgs)        -> social/news chatter as a narrative proxy (no key)
- HF Inference (optional)  -> sentiment on chatter headlines (free tier)
- Birdeye (optional)       -> holder concentration / top holders, ONLY if
                               BIRDEYE_API_KEY is set. Without it, holder
                               distribution and whale/deployer analysis are
                               explicitly reported as unavailable rather than
                               guessed at.
- Telegram Bot API (optional) -> pushes a condensed digest to a chat/channel,
                               ONLY if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
                               are set. Free, no third-party cost.

IMPORTANT: DexScreener's "latest boosted" and "latest profiles" endpoints are
PAID promotion surfaces (projects pay to appear there). They are useful as a
*candidate discovery* source but must never be read as evidence of organic
community strength -- the tools below label them accordingly.
"""

import os
import json
import datetime as dt

import requests
from smolagents import tool

HF_TOKEN = os.environ.get("HF_TOKEN", "")
BIRDEYE_API_KEY = os.environ.get("BIRDEYE_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

DEXSCREENER_BASE = "https://api.dexscreener.com"
TELEGRAM_MAX_CHARS = 4000  # Telegram's hard limit is 4096; leave headroom


@tool
def discover_candidate_tokens(chain_id: str = "solana", limit: int = 10) -> str:
    """Discovers candidate memecoin tokens via DexScreener's public "boosted"
    and "latest profile" feeds. THESE ARE PAID PROMOTION SURFACES: a token
    appearing here means its team spent money to be listed, which is a
    marketing-spend signal, not evidence of organic community strength. Use
    this only to build a candidate list to then investigate with
    get_token_pairs and search_social_chatter -- never treat presence on
    this list itself as bullish.

    Args:
        chain_id: Chain to filter for (e.g. "solana", "ethereum", "base", "bsc").
        limit: Max candidates to return (default 10).

    Returns:
        JSON string: list of {chainId, tokenAddress, source, note} objects,
        where source is "boosted" or "profile" and note flags it as paid.
    """
    candidates = []
    endpoints = [
        (f"{DEXSCREENER_BASE}/token-boosts/latest/v1", "boosted"),
        (f"{DEXSCREENER_BASE}/token-profiles/latest/v1", "profile"),
    ]
    for url, source in endpoints:
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):
                data = data.get("items", data.get("data", []))
            for item in data:
                if item.get("chainId") != chain_id:
                    continue
                candidates.append({
                    "chainId": item.get("chainId"),
                    "tokenAddress": item.get("tokenAddress"),
                    "source": source,
                    "note": "PAID PROMOTION - not an organic-strength signal",
                })
        except Exception as e:
            candidates.append({"error": f"{source} fetch failed: {str(e)[:150]}"})

    # de-dupe by tokenAddress, cap to limit
    seen = set()
    deduped = []
    for c in candidates:
        addr = c.get("tokenAddress")
        if "error" in c or (addr and addr not in seen):
            if addr:
                seen.add(addr)
            deduped.append(c)
        if len(deduped) >= limit:
            break
    return json.dumps(deduped, ensure_ascii=False)


@tool
def search_pairs(query: str) -> str:
    """Searches DexScreener for trading pairs matching a token name, ticker,
    or contract address. Use this to locate the pair(s) for a token a human
    analyst named, rather than only relying on the paid discovery feeds.

    Args:
        query: Token name, ticker symbol, or contract address to search for.

    Returns:
        JSON string: list of matching pairs with chainId, pairAddress,
        baseToken symbol/name, liquidity, volume24h, priceChange24h.
    """
    try:
        resp = requests.get(f"{DEXSCREENER_BASE}/latest/dex/search",
                             params={"q": query}, timeout=20)
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
    except Exception as e:
        return json.dumps({"error": f"search failed: {str(e)[:150]}"})

    out = []
    for p in pairs[:25]:
        out.append({
            "chainId": p.get("chainId"),
            "dexId": p.get("dexId"),
            "pairAddress": p.get("pairAddress"),
            "baseToken": p.get("baseToken", {}).get("symbol"),
            "tokenAddress": p.get("baseToken", {}).get("address"),
            "priceUsd": p.get("priceUsd"),
            "liquidityUsd": (p.get("liquidity") or {}).get("usd"),
            "volume24h": (p.get("volume") or {}).get("h24"),
            "priceChange24h": (p.get("priceChange") or {}).get("h24"),
            "pairCreatedAt": p.get("pairCreatedAt"),
        })
    return json.dumps(out, ensure_ascii=False)


@tool
def get_token_pairs(token_address: str, chain_id: str = "solana") -> str:
    """Fetches full on-chain trading metrics for a specific token from
    DexScreener: liquidity, volume, buy/sell transaction counts across
    multiple windows, price changes, FDV vs market cap, pair age, and any
    declared social links. This is the primary FACTS source for liquidity
    health and trading-activity questions.

    Args:
        token_address: The token's contract address.
        chain_id: Chain the token lives on (default "solana").

    Returns:
        JSON string: list of pair objects with full metrics, plus derived
        fields (pair_age_hours, volume_to_liquidity_ratio, buy_sell_ratio_h24,
        fdv_to_mcap_ratio) computed for convenience. Fields DexScreener does
        not provide (holder count, holder concentration, LP lock status,
        deployer wallet) are NOT included here -- see get_holder_distribution.
    """
    try:
        resp = requests.get(
            f"{DEXSCREENER_BASE}/latest/dex/tokens/{token_address}", timeout=20)
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
    except Exception as e:
        return json.dumps({"error": f"lookup failed: {str(e)[:150]}"})

    pairs = [p for p in pairs if p.get("chainId") == chain_id] or pairs
    now_ms = dt.datetime.utcnow().timestamp() * 1000

    out = []
    for p in pairs:
        liquidity = (p.get("liquidity") or {}).get("usd")
        volume24h = (p.get("volume") or {}).get("h24")
        txns24h = (p.get("txns") or {}).get("h24", {})
        buys, sells = txns24h.get("buys"), txns24h.get("sells")
        fdv, mcap = p.get("fdv"), p.get("marketCap")
        created_at = p.get("pairCreatedAt")

        entry = {
            "chainId": p.get("chainId"),
            "dexId": p.get("dexId"),
            "pairAddress": p.get("pairAddress"),
            "baseToken": p.get("baseToken", {}).get("symbol"),
            "priceUsd": p.get("priceUsd"),
            "liquidityUsd": liquidity,
            "marketCap": mcap,
            "fdv": fdv,
            "volume": p.get("volume"),
            "priceChange": p.get("priceChange"),
            "txns": p.get("txns"),
            "pairCreatedAt": created_at,
            "socials": (p.get("info") or {}).get("socials"),
            "websites": (p.get("info") or {}).get("websites"),
        }
        if created_at:
            entry["pair_age_hours"] = round((now_ms - created_at) / 3_600_000, 1)
        if liquidity:
            entry["volume_to_liquidity_ratio_24h"] = (
                round(volume24h / liquidity, 2) if volume24h else None)
        if buys is not None and sells is not None and (buys + sells) > 0:
            entry["buy_sell_ratio_h24"] = round(buys / max(sells, 1), 2)
            entry["total_txns_24h"] = buys + sells
        if fdv and mcap:
            entry["fdv_to_mcap_ratio"] = round(fdv / mcap, 2)
        out.append(entry)
    return json.dumps(out, ensure_ascii=False)


@tool
def get_holder_distribution(token_address: str, chain_id: str = "solana") -> str:
    """Attempts to fetch holder count and top-holder concentration via the
    Birdeye API. REQUIRES the BIRDEYE_API_KEY environment variable -- this is
    the one paid-tier dependency in the toolkit, included because holder
    concentration and insider/deployer wallet checks are impossible to do
    honestly from free DEX aggregator data alone. If no key is configured,
    this returns an explicit "unavailable" result instead of guessing.

    Args:
        token_address: The token's contract address.
        chain_id: Chain the token lives on (default "solana").

    Returns:
        JSON string with holder_count, top10_holder_pct (share of supply held
        by the top 10 wallets) when available, or {"available": false,
        "reason": ...} when the API key is missing or the call fails.
    """
    if not BIRDEYE_API_KEY:
        return json.dumps({
            "available": False,
            "reason": "BIRDEYE_API_KEY not set. Holder distribution, whale "
                      "concentration, and deployer-wallet checks require a "
                      "paid on-chain indexer (Birdeye/Helius/Solscan Pro/Nansen). "
                      "Do not assume distribution is healthy in its absence.",
        })
    try:
        resp = requests.get(
            "https://public-api.birdeye.so/defi/v3/token/holder",
            params={"address": token_address, "offset": 0, "limit": 10},
            headers={"X-API-KEY": BIRDEYE_API_KEY, "x-chain": chain_id},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        items = data.get("items", [])
        total_pct = sum(h.get("percent", 0) for h in items[:10])
        return json.dumps({
            "available": True,
            "top10_holder_pct": round(total_pct, 2) if items else None,
            "sample_holders": items[:10],
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "available": False,
            "reason": f"Birdeye call failed: {str(e)[:150]}",
        })


@tool
def search_social_chatter(query: str, max_results: int = 15) -> str:
    """Searches DuckDuckGo (news + general web) for chatter about a token
    or project. This is a NARRATIVE and DISCOVERY proxy, not an engagement
    metric -- it returns article/post mentions with dates and sources, not
    follower counts, likes, retweets, or unique-author counts, and it cannot
    tell you whether the same accounts are posting repeatedly. Treat volume
    of hits as a weak, easily-gamed signal only.

    Args:
        query: Search string, typically "<TICKER> <token name> memecoin".
        max_results: Max results to return (default 15).

    Returns:
        JSON string: list of {title, source, date, url} mention objects.
    """
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS

    mentions = []
    try:
        with DDGS() as ddgs_client:
            for r in ddgs_client.news(query, max_results=max_results):
                mentions.append({
                    "title": r.get("title", ""),
                    "source": r.get("source", ""),
                    "date": r.get("date", ""),
                    "url": r.get("url", ""),
                })
    except Exception as e:
        mentions.append({"error": f"news search failed: {str(e)[:150]}"})
    return json.dumps(mentions, ensure_ascii=False)


@tool
def analyze_sentiment(texts_json: str) -> str:
    """Runs social-sentiment analysis (positive/negative/neutral) on a list of
    chatter headlines/snippets using a Twitter-tuned RoBERTa model via the
    free Hugging Face Inference API. More appropriate for meme-community
    slang than a financial-news sentiment model.

    Args:
        texts_json: JSON string with a list of objects containing a "title"
            field (the output of search_social_chatter), or a JSON list of
            plain strings.

    Returns:
        JSON string pairing each text with its sentiment label and score.
    """
    items = json.loads(texts_json)
    texts = []
    for it in items:
        if isinstance(it, str):
            texts.append(it)
        elif isinstance(it, dict) and it.get("title"):
            texts.append(it["title"])
    texts = texts[:30]

    if not texts:
        return json.dumps({"error": "no text to analyze"})

    url = ("https://router.huggingface.co/hf-inference/models/"
           "cardiffnlp/twitter-roberta-base-sentiment-latest")
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
                "text": text,
                "sentiment": best["label"],
                "score": round(best["score"], 3),
            })
        except Exception:
            out.append({"text": text, "sentiment": "unknown"})
    return json.dumps(out, ensure_ascii=False)


@tool
def save_report(markdown_report: str) -> str:
    """Saves the final memecoin research report as a timestamped markdown
    file in reports/, and updates reports/latest_memecoin.md. Call this
    exactly once at the end with the complete report.

    Args:
        markdown_report: The full report in markdown format.

    Returns:
        The path of the saved report file.
    """
    ts = dt.datetime.utcnow().strftime("%Y-%m-%d_%H%M")
    os.makedirs("reports", exist_ok=True)
    path = f"reports/memecoin_research_{ts}.md"
    header = f"# Memecoin Research Brief\n\n_Generated (UTC): {ts}_\n\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + markdown_report)
    with open("reports/latest_memecoin.md", "w", encoding="utf-8") as f:
        f.write(header + markdown_report)
    return path


@tool
def send_telegram_alert(digest_text: str) -> str:
    """Sends a condensed plain-text digest to a Telegram chat or channel via
    the Telegram Bot API. Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
    env vars (create a bot with @BotFather, add it to the target chat/channel,
    and use its chat ID). Plain text only -- do not include Markdown/HTML
    special characters expecting them to render, since ticker symbols and
    URLs in memecoin data reliably break Telegram's strict parse modes; this
    tool sends with no parse_mode for that reason. Messages over ~4000
    characters are split into multiple sends automatically.

    Args:
        digest_text: The plain-text summary to send (e.g. top candidates
            with verdicts and key numbers, plus a link to the full report).

    Returns:
        JSON string: {"sent": bool, "reason"/"chunks"/"results": ...}.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return json.dumps({
            "sent": False,
            "reason": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set -- "
                      "Telegram delivery is disabled, not failing silently.",
        })

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = [digest_text[i:i + TELEGRAM_MAX_CHARS]
              for i in range(0, len(digest_text), TELEGRAM_MAX_CHARS)] or [digest_text]

    results = []
    for chunk in chunks:
        try:
            resp = requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": chunk,
                "disable_web_page_preview": True,
            }, timeout=20)
            resp.raise_for_status()
            results.append({"ok": True})
        except Exception as e:
            results.append({"ok": False, "error": str(e)[:150]})

    return json.dumps({"sent": True, "chunks": len(chunks), "results": results},
                       ensure_ascii=False)
