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
