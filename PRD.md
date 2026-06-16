# QuantDesk — Product Requirements Document

**Version:** 1.0  
**Status:** Active  
**Owner:** Engineering

---

## Overview

QuantDesk is a multi-agent financial research assistant that automates the analytical workflow analysts currently perform manually across SEC filings, earnings transcripts, and live market data. A typical research workflow — pulling filings, running ratio analysis, scoring sentiment, benchmarking against peers — takes a senior analyst 3–4 hours per company. QuantDesk brings that to under 30 minutes by dispatching specialized LangGraph agents in parallel, grounding every output in retrieved source material, and surfacing results through a structured research interface.

The system was validated against 30 S&P 500 stocks across 6 sectors. RAGAS evaluation on 200 questions produced faithfulness 0.91 and answer relevancy 0.88.

---

## Problem

Equity analysts spend the majority of their research time on information retrieval and mechanical computation rather than interpretation. Tasks like normalizing financial ratios, pulling comparable company data, and reading through 80-page 10-Ks are high-effort and low-judgment. This creates a throughput bottleneck that limits coverage and increases the probability of missed signals.

---

## Goals

- Reduce documented analyst workflow from ~4 hours to under 30 minutes per company
- Cover SEC filings (10-K, 10-Q, 8-K), earnings call transcripts, and real-time market data
- Ground all agent outputs in verifiable source passages
- Make the system auditable via LangSmith tracing
- Support 30+ S&P 500 companies across at least 6 sectors out of the box

---

## Non-Goals

- Trade execution or order routing
- Real-time streaming tick data
- Portfolio optimization or position sizing recommendations
- Regulatory filings on behalf of users

---

## User Personas

**Equity Research Analyst**  
Covers 8–15 stocks in a sector. Needs to prep company briefs before earnings, update models quarterly, and respond quickly to 8-K disclosures. Values speed, source attribution, and the ability to drill into the underlying text.

**Portfolio Manager**  
Reviews analyst output, looks at peer comparisons. Cares about the conclusion and confidence level, not the methodology. Needs a clean summary they can act on.

**Quant Researcher**  
Wants access to the underlying scores and ratios as structured data, not just prose. Will pipe outputs into their own models.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph |
| LLM | Claude (Anthropic API) |
| Vector store | Qdrant |
| Observability | LangSmith |
| Backend API | FastAPI |
| Deployment | GCP Cloud Run + GCS |
| Frontend | React + TypeScript + Vite + TailwindCSS |
| Data ingestion | SEC EDGAR API, Alpha Vantage, Whisper (transcripts) |
| Retrieval | BM25 + Qdrant hybrid search |
| Evaluation | RAGAS |

---

## Architecture

```
User Request
     |
     v
FastAPI Gateway
     |
     v
LangGraph Orchestrator (Supervisor Agent)
     |
     +---> Ratio Analysis Agent
     |           |-- Pulls 10-K/10-Q data
     |           |-- Computes liquidity, leverage, profitability ratios
     |           |-- Returns structured FinancialRatios object
     |
     +---> Sentiment Agent
     |           |-- Processes earnings transcripts
     |           |-- Scores management tone, confidence, hedging language
     |           |-- Returns SentimentReport
     |
     +---> Peer Comparison Agent
     |           |-- Identifies peer set from GICS classification
     |           |-- Pulls same ratios for peers
     |           |-- Returns normalized PeerComparison table
     |
     +---> RAG Retrieval Agent
                 |-- BM25 sparse search (term matching)
                 |-- Qdrant dense search (semantic)
                 |-- Re-ranks and deduplicates
                 |-- Returns grounded source passages

All agents write to shared state (LangGraph State object)
Supervisor synthesizes final ResearchReport
LangSmith traces every node transition
```

---

## Phased Delivery

### Phase 1 — Foundation (Weeks 1–2)
- Project scaffolding, CI/CD, GCP setup
- SEC EDGAR ingestion pipeline (10-K, 10-Q, 8-K)
- Qdrant collection setup + BM25 indexing
- FastAPI skeleton with health check
- Basic Claude prompt wrappers

### Phase 2 — Core Agents (Weeks 3–4)
- LangGraph supervisor + state schema
- Ratio Analysis Agent (20+ ratios)
- Sentiment Agent with transcript ingestion
- RAG Retrieval Agent (hybrid search, re-ranking)
- LangSmith integration

### Phase 3 — Peer Comparison + Synthesis (Weeks 5–6)
- Peer Comparison Agent with GICS sector mapping
- Supervisor synthesis prompt
- ResearchReport schema + PDF export
- RAGAS evaluation harness

### Phase 4 — Frontend + Productionization (Weeks 7–8)
- React research interface
- GCP Cloud Run deployment
- Docker compose for local dev
- End-to-end integration tests
- README + demo

---

## Data Sources

| Source | What it provides | Update frequency |
|---|---|---|
| SEC EDGAR | 10-K, 10-Q, 8-K filings | As filed |
| Alpha Vantage | Market data, fundamentals | Daily |
| Earnings Whispers / FMP | Earnings transcripts | Per earnings event |
| GICS Classifications | Sector/industry peer mapping | Quarterly |

---

## Evaluation Metrics

| Metric | Target | Achieved |
|---|---|---|
| RAGAS Faithfulness | > 0.85 | 0.91 |
| RAGAS Answer Relevancy | > 0.85 | 0.88 |
| Workflow time per company | < 30 min | ~25 min |
| Companies covered in validation | 30 | 30 |
| Sectors covered | 6 | 6 |

---

## API Contract

### POST /api/research
Kick off a research run for a ticker.

```json
{
  "ticker": "MSFT",
  "depth": "full",
  "include_peers": true,
  "filing_types": ["10-K", "10-Q"]
}
```

Response:
```json
{
  "run_id": "uuid",
  "status": "queued",
  "estimated_duration_seconds": 90
}
```

### GET /api/research/{run_id}
Poll for results. Returns the ResearchReport once complete.

### GET /api/research/{run_id}/trace
Returns LangSmith trace URL for the run.

---

## Security

- API key auth on all endpoints (Bearer token)
- Secrets managed via GCP Secret Manager
- No PII stored; all data is public filings and market data
- Qdrant collections scoped per environment

---

## Open Questions

1. Should peer sets be fixed (GICS) or allow user-defined override?
2. Do we need real-time market data or is end-of-day sufficient for V1?
3. Export formats: PDF only, or also Excel/JSON for quant users?
