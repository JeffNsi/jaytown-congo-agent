# JayTown Congo Intelligence Agent

One agent that sees everything — 24/7, 100% free.

Every hour it: fetches Congo-related market data (Ivanhoe, First Quantum, Glencore, copper ETFs, copper futures, USD/CDF) → searches the latest DRC / Kinshasa Stock Exchange / cobalt news → runs FinBERT sentiment on every headline → writes a markdown intelligence brief to `reports/latest.md`.

## Free stack

| Layer | Tool | Cost |
|---|---|---|
| Brain | smolagents + HF serverless inference | Free |
| Prices | yfinance (Yahoo Finance) | Free, no key |
| News | DuckDuckGo News (ddgs) | Free, no key |
| Sentiment | ProsusAI/finbert via HF Inference API | Free tier |
| 24/7 runner | GitHub Actions cron | Free (2000 min/mo) |

## Setup (5 minutes)

1. **Get a free HF token**: https://hf.co/settings/tokens → New token → "Read" + inference permission.
2. **Create a GitHub repo** and push these files.
3. **Add the secret**: repo → Settings → Secrets and variables → Actions → New repository secret → name `HF_TOKEN`, value = your token.
4. Done. The workflow runs every hour. Reports appear in `reports/`.

## Run locally

```bash
pip install -r requirements.txt
export HF_TOKEN=hf_xxx
python agent.py            # full agent (LLM reasons + writes analysis)
python agent.py --pipeline # deterministic mode, no LLM (rate-limit safe)
```

## Notes

- The agent auto-falls back to pipeline mode if the free inference tier is rate-limited, so you always get a report.
- Cobalt has no free real-time spot feed; copper futures (HG=F) + COPX act as the proxy. Cobalt news is still captured via the news layer.
- Add tickers in `congo_tools.py` → `WATCHLIST`. Add news topics in `NEWS_QUERIES`.
- Not investment advice — it's an information radar.

---

## Memecoin Research Agent

A second, independent agent (`memecoin_agent.py` / `memecoin_tools.py`) that hunts for **emerging** memecoins showing evidence of organic community formation, accelerating (not just high) growth, genuine engagement, healthy liquidity, reasonable holder distribution, and credible catalysts — as opposed to coins that are simply trending or artificially pumped.

It is built to be skeptical by construction: every report separates **FACTS** (directly observed), **SIGNALS** (derived heuristics), **ASSUMPTIONS**, and **SPECULATION**, and answers a fixed 20-question due-diligence framework per token (real vs. artificial community evidence, growth source, whale accumulation/distribution, supply concentration, deployer/insider links, bull/bear case, invalidation conditions, catalysts, failure modes, etc.). When a data source can't answer a question, the report says so explicitly instead of guessing.

### Free stack

| Layer | Tool | Cost |
|---|---|---|
| Brain | smolagents + HF serverless inference | Free |
| On-chain pairs/liquidity/volume/txns | DexScreener public API | Free, no key |
| Candidate discovery | DexScreener boosted/profile feeds | Free, no key — **paid promotion, not an organic signal** |
| Narrative/chatter | DuckDuckGo (ddgs) | Free, no key |
| Sentiment | Twitter-RoBERTa via HF Inference API | Free tier |
| Holder concentration / whale checks | Birdeye API | **Optional** — needs `BIRDEYE_API_KEY`; reported as unavailable without it |
| 24/7 runner | GitHub Actions cron | Free (2000 min/mo) |

### Run locally

```bash
pip install -r requirements.txt
export HF_TOKEN=hf_xxx                  # optional, enables LLM reasoning mode
export BIRDEYE_API_KEY=...              # optional, enables holder-distribution checks
python memecoin_agent.py                             # auto-discovery + full framework
python memecoin_agent.py --tokens=<addr1>,<addr2>     # analyze specific token addresses
python memecoin_agent.py --pipeline                   # deterministic mode, no LLM
```

### Honest limitations

- Without `BIRDEYE_API_KEY`, holder distribution, whale accumulation/distribution, and deployer/insider wallet links are **not available** — the report says so rather than assuming a healthy distribution.
- DexScreener's free discovery feeds (boosted tokens, new profiles) are paid-promotion surfaces. They are useful only as a starting candidate list, never as evidence of quality — the tools and prompts label them accordingly.
- Social chatter search measures indexed mentions, not follower counts, unique-author counts, or bot-vs-human split — it cannot on its own tell you whether growth is organic or whether the same accounts are posting repeatedly.
- Pipeline (no-LLM) mode applies fixed numeric thresholds instead of contextual judgment; treat it as a first-pass filter, not a verdict.
- Not investment advice — it's a research-triage tool, and every output should be read alongside its own stated data gaps.
