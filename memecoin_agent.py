"""
Memecoin Research Agent
========================
Finds emerging memecoin projects showing evidence of organic community
formation, accelerating growth, genuine engagement, healthy liquidity,
reasonable holder distribution, and credible catalysts -- as distinct from
tokens that are merely trending or artificially pumped.

This agent is deliberately skeptical by construction: the task prompt below
encodes a 20-question due-diligence framework and forbids treating any single
metric (volume, social mentions, wallet count) as proof of quality. Every
tool result is honest about what it can and cannot see, and the report
format forces FACTS / SIGNALS / ASSUMPTIONS / SPECULATION to stay separated.

100% free stack (one optional exception):
- smolagents CodeAgent + Hugging Face free serverless inference (the brain)
- DexScreener public API (pairs/liquidity/volume/txns/socials, no key)
- DuckDuckGo (ddgs) for narrative/chatter discovery (no key)
- Twitter-RoBERTa via HF Inference for sentiment (free tier)
- Birdeye API for holder concentration -- OPTIONAL, requires BIRDEYE_API_KEY.
  Without it, holder/whale/deployer analysis is reported as unavailable
  rather than guessed at.

Usage:
    export HF_TOKEN=hf_xxx                 # free token from hf.co/settings/tokens
    export BIRDEYE_API_KEY=...             # optional, enables holder-distribution checks
    python memecoin_agent.py                              # candidate discovery + full framework
    python memecoin_agent.py --tokens So111...,Es9vM...    # analyze specific token addresses
    python memecoin_agent.py --pipeline                    # deterministic fallback, no LLM
"""

import os
import sys
import json
import datetime as dt

from memecoin_tools import (
    discover_candidate_tokens,
    search_pairs,
    get_token_pairs,
    get_holder_distribution,
    search_social_chatter,
    analyze_sentiment,
    save_report,
)

FRAMEWORK_QUESTIONS = [
    "What evidence suggests this community is real?",
    "What evidence suggests the community may be artificial?",
    "Is engagement proportional to the size of the community?",
    "Is community growth accelerating?",
    "Where is the growth coming from?",
    "Are the same wallets/users repeatedly appearing?",
    "Is trading activity organic?",
    "Is liquidity sufficient?",
    "Are whales accumulating or distributing?",
    "Is supply concentrated?",
    "Are wallets connected to the deployer or insiders?",
    "What is the strongest bullish argument?",
    "What is the strongest bearish argument?",
    "What information would invalidate the bullish thesis?",
    "What important information is currently missing?",
    "What upcoming catalysts could increase attention?",
    "What could cause the community to disappear?",
    "Is the current momentum sustainable?",
    "Are we seeing genuine adoption or temporary speculation?",
    "If this token fails, what will most likely be the reason?",
]

TASK = """
You are a skeptical memecoin research analyst. You are NOT looking for coins
that are simply trending -- you are looking for EMERGING projects with
evidence of organic community formation, accelerating (not just high) growth,
genuine engagement, sustainable momentum, healthy liquidity, reasonable
holder distribution, interesting narrative potential, organic on-chain
activity, credible catalysts, and increasing attention from sophisticated
participants.

Hard rules, never violate them:
- Never rely on a single metric to reach a conclusion.
- Never equate social media mention volume with genuine community strength.
- Never treat high trading volume as automatically bullish (it can be wash
  trading, bot activity, or a pump-and-dump in progress).
- Never treat wallet activity as automatically "smart money" -- you have no
  reliable way to identify sophistication from a free-tier feed alone.
- Every claim must be labeled FACT (directly observed from a tool), SIGNAL
  (a derived/heuristic indicator, e.g. volume-to-liquidity ratio), ASSUMPTION
  (something taken as given but not verified), or SPECULATION (a forward-
  looking guess). Never blend these silently into plain prose.
- When a tool reports data as unavailable (e.g. holder distribution without
  a Birdeye key), say so explicitly in the report. Do not fill the gap with
  a guess.

Steps:
1. If specific token addresses were provided, use those as candidates.
   Otherwise call discover_candidate_tokens() to get a list -- but remember
   its results are PAID PROMOTION listings, a weak discovery signal only,
   never evidence of quality on their own. You may also use search_pairs()
   for named tokens.
2. For each candidate (investigate at most 5), call get_token_pairs() to get
   liquidity, volume, transaction counts, price action, pair age, and
   declared socials.
3. Call get_holder_distribution() for each candidate. If unavailable, note
   that explicitly -- do not skip mentioning it.
4. Call search_social_chatter() with the token's name/ticker, then pass the
   results to analyze_sentiment(). Treat this purely as a narrative/momentum
   proxy, not an engagement metric.
5. For EACH candidate token, write a report section with:
   ### <TICKER> (<chain>, <address>)
   **Facts** (bulleted, from tool outputs only, with numbers)
   **Signals** (derived heuristics: vol/liquidity ratio, buy/sell skew,
     FDV-to-mcap ratio, pair age, chatter trend, sentiment mix)
   **Assumptions** (explicitly labeled)
   **Data gaps** (what you could not verify, e.g. holder concentration,
     deployer wallet links, LP lock status, unique-author counts on socials)
   **Answers to the 20-question framework** -- answer each of the 20
     questions listed for you below in 1 sentence, writing "data unavailable"
     where the tools genuinely could not tell you, rather than guessing.
   **Verdict**: asymmetric-opportunity-candidate / needs-more-data / red-flags
     -- with the single strongest reason for that verdict.
6. Write an ## Executive Summary at the top ranking candidates by how well
   they match the "organic + accelerating + sustainable" thesis (not by
   volume or price change), explicitly naming which ones look like pumped/
   artificial activity instead.
7. Call save_report() with the full markdown, then give the file path as
   your final answer.

The 20-question framework (answer these per-token in step 5):
""" + "\n".join(f"{i+1}. {q}" for i, q in enumerate(FRAMEWORK_QUESTIONS)) + """

Rules: be factual, never invent prices, holder data, or headlines. If a tool
errors or reports unavailable data, note it and continue -- do not fabricate
a substitute number.
"""


def run_agent(token_addresses=None) -> str:
    """Full agentic run: the LLM applies the framework and writes the analysis."""
    from smolagents import CodeAgent, InferenceClientModel

    model = InferenceClientModel(model_id="meta-llama/Llama-3.1-8B-Instruct")
    agent = CodeAgent(
        tools=[
            discover_candidate_tokens, search_pairs, get_token_pairs,
            get_holder_distribution, search_social_chatter, analyze_sentiment,
            save_report,
        ],
        model=model,
        max_steps=20,
    )
    task = TASK
    if token_addresses:
        task += f"\n\nSpecific token addresses to investigate: {', '.join(token_addresses)}"
    return agent.run(task)


def run_pipeline(token_addresses=None, chain_id: str = "solana") -> str:
    """Deterministic fallback: same tools, no LLM reasoning. Applies fixed
    heuristic thresholds instead of judgment, and is explicit that this mode
    is a weaker substitute for the full agent's contextual reasoning."""
    candidates = []
    if token_addresses:
        candidates = [{"tokenAddress": a, "chainId": chain_id, "source": "user-specified"}
                      for a in token_addresses]
    else:
        try:
            candidates = json.loads(discover_candidate_tokens(chain_id=chain_id, limit=8))
        except Exception:
            candidates = []
        candidates = [c for c in candidates if c.get("tokenAddress")]

    sections = ["## Executive Summary", "",
                "_Pipeline mode: fixed heuristic thresholds, no LLM judgment. "
                "Candidate discovery (if used) came from DexScreener's PAID "
                "boosted/profile feeds -- presence there is a marketing-spend "
                "signal, not a quality signal._", ""]
    verdicts = []

    for cand in candidates[:5]:
        addr = cand["tokenAddress"]
        chain = cand.get("chainId", chain_id)
        try:
            pairs = json.loads(get_token_pairs(addr, chain_id=chain))
        except Exception as e:
            pairs = {"error": str(e)[:150]}

        pair = pairs[0] if isinstance(pairs, list) and pairs else None
        symbol = pair.get("baseToken", "?") if pair else "?"

        lines = [f"### {symbol} ({chain}, `{addr}`)", "",
                  f"_Discovery source: {cand.get('source', 'unspecified')}"
                  + (" -- PAID PROMOTION" if cand.get("source") in ("boosted", "profile") else "")
                  + "_", ""]

        if not pair:
            lines += ["**Facts**: no DexScreener pair data returned "
                       "(token may be too new, illiquid, or the address is wrong).",
                       "**Verdict**: needs-more-data -- no tradeable pair found.", ""]
            sections.extend(lines)
            verdicts.append((symbol, "needs-more-data"))
            continue

        liq = pair.get("liquidityUsd")
        vlr = pair.get("volume_to_liquidity_ratio_24h")
        bsr = pair.get("buy_sell_ratio_h24")
        age_h = pair.get("pair_age_hours")
        fdv_mcap = pair.get("fdv_to_mcap_ratio")
        socials = pair.get("socials") or []

        facts = [
            f"Liquidity: ${liq:,.0f}" if liq else "Liquidity: unavailable",
            f"24h volume: ${pair.get('volume', {}).get('h24', 0):,.0f}"
            if pair.get("volume") else "24h volume: unavailable",
            f"Pair age: {age_h} hours" if age_h is not None else "Pair age: unavailable",
            f"FDV/MarketCap ratio: {fdv_mcap}" if fdv_mcap else "FDV/MarketCap ratio: unavailable",
            f"Declared socials: {len(socials)} link(s)" if socials else "Declared socials: none listed",
        ]
        lines += ["**Facts**"] + [f"- {f}" for f in facts] + [""]

        signals = []
        if vlr is not None:
            if vlr > 5:
                signals.append(f"Volume/liquidity ratio {vlr}x in 24h -- "
                                "unusually high relative to pool depth; can "
                                "indicate wash trading or bot activity as "
                                "easily as genuine demand. Not automatically bullish.")
            else:
                signals.append(f"Volume/liquidity ratio {vlr}x -- within a normal range.")
        if bsr is not None:
            signals.append(f"Buy/sell ratio (24h): {bsr}x "
                            + ("(buy-skewed)" if bsr > 1.3 else "(sell-skewed)" if bsr < 0.77 else "(balanced)"))
        if liq is not None and liq < 10_000:
            signals.append("Liquidity under $10k -- high slippage/rug risk regardless of other metrics.")
        if age_h is not None and age_h < 24:
            signals.append("Pair is under 24h old -- too early for any growth-acceleration claim; treat as unknown-stage.")
        if fdv_mcap and fdv_mcap > 3:
            signals.append(f"FDV is {fdv_mcap}x market cap -- large uncirculated/locked supply overhang risk on unlock.")
        lines += ["**Signals**"] + [f"- {s}" for s in signals] + [""]

        holder = json.loads(get_holder_distribution(addr, chain_id=chain))
        if holder.get("available"):
            lines += ["**Facts (holders)**",
                       f"- Top 10 holders control {holder.get('top10_holder_pct')}% of supply.", ""]
        else:
            lines += ["**Data gaps**",
                       f"- Holder distribution unavailable: {holder.get('reason')}",
                       "- Deployer/insider wallet linkage: unavailable (no on-chain indexer configured).",
                       "- LP lock status: unavailable (not exposed by DexScreener's free API).",
                       "- Unique-author count / bot-vs-human split on social chatter: unavailable "
                       "(DuckDuckGo results give article mentions, not per-account engagement).", ""]

        chatter = json.loads(search_social_chatter(f"{symbol} memecoin", max_results=8))
        chatter_count = len([c for c in chatter if "error" not in c])
        lines += [f"**Narrative proxy**: {chatter_count} recent web/news mention(s) found "
                   "for the ticker+\"memecoin\" query. This measures indexed mentions, not "
                   "community size, growth rate, or authenticity.", ""]

        answers = []
        answers.append("1. Real-community evidence: " +
                        (f"{len(socials)} declared official social link(s) exist on-chain metadata."
                         if socials else "no declared social links found -- weak signal."))
        answers.append("2. Artificial-community evidence: " +
                        ("token was discovered via a PAID promotion feed, which is a spend signal, not organic pull."
                         if cand.get("source") in ("boosted", "profile") else "none specifically flagged by available tools."))
        for i in range(3, 21):
            answers.append(f"{i}. {FRAMEWORK_QUESTIONS[i-1]} -> data unavailable in pipeline mode "
                            "(requires holder/whale on-chain data and/or LLM contextual judgment).")
        lines += ["**Framework answers (heuristic-only, see note)**"] + [f"- {a}" for a in answers] + [""]

        verdict = "needs-more-data"
        reason = "insufficient free-tier data to confirm organic strength either way."
        if liq is not None and liq < 5_000:
            verdict, reason = "red-flags", "liquidity is too thin to consider tradeable at any real size."
        elif vlr is not None and vlr > 15:
            verdict, reason = "red-flags", f"volume/liquidity ratio of {vlr}x is extreme and consistent with wash trading."
        elif holder.get("available") and (holder.get("top10_holder_pct") or 0) > 50:
            verdict, reason = "red-flags", "top 10 wallets control over half of supply."
        elif liq and liq > 20_000 and age_h and age_h > 48 and (vlr is None or vlr < 5):
            verdict, reason = "asymmetric-opportunity-candidate", "adequate liquidity, sustained pair age, and no extreme volume/liquidity distortion -- warrants deeper (LLM-mode or manual) review."

        lines += [f"**Verdict**: {verdict} -- {reason}", ""]
        sections.extend(lines)
        verdicts.append((symbol, verdict))

    summary_lines = [f"- {sym}: {v}" for sym, v in verdicts] or ["- No candidates were analyzed."]
    sections[2:2] = summary_lines + [""]

    report = "\n".join(sections)
    path = save_report(report)
    return path


if __name__ == "__main__":
    started = dt.datetime.utcnow().isoformat()
    print(f"[{started}] Memecoin Research Agent starting...")

    args = sys.argv[1:]
    tokens = None
    for a in args:
        if a.startswith("--tokens="):
            tokens = [t.strip() for t in a.split("=", 1)[1].split(",") if t.strip()]

    if "--pipeline" in args:
        result = run_pipeline(token_addresses=tokens)
    else:
        try:
            result = run_agent(token_addresses=tokens)
        except Exception as e:
            print(f"Agent run failed ({e}); falling back to pipeline mode.")
            result = run_pipeline(token_addresses=tokens)

    print(f"Done. Result: {result}")
