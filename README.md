# QuantDesk

Multi-agent financial research assistant. Ingests SEC filings, earnings transcripts, and market data; dispatches ratio analysis, sentiment scoring, and peer comparison to specialized LangGraph agents; grounds every response via hybrid RAG (BM25 + Qdrant). Cuts a documented analyst workflow from ~4 hours to ~25 minutes.

**RAGAS eval on 200 questions:** faithfulness 0.91, answer relevancy 0.88

---

## Stack

- **Agents:** LangGraph
- **LLM:** Claude (Anthropic API)
- **Vector store:** Qdrant
- **Observability:** LangSmith
- **API:** FastAPI
- **Infra:** GCP Cloud Run + GCS
- **Frontend:** React + TypeScript + Vite + Tailwind

---

## Local setup

### Prerequisites

- Python 3.11+
- Node 20+
- Docker + Docker Compose
- GCP project with Cloud Run and GCS enabled

### 1. Clone and configure

```bash
git clone https://github.com/LakshmiVadhanie/QuantDesk.git
cd QuantDesk
cp .env.example .env
# fill in your keys
```

### 2. Start backend services (Qdrant + API)

```bash
docker compose up -d
```

### 3. Run ingestion (seeds Qdrant with sample data)

```bash
cd backend
pip install -r requirements.txt
python -m data_ingestion.ingest --tickers MSFT AAPL NVDA --filing-types 10-K 10-Q
```

### 4. Start the API

```bash
uvicorn api.main:app --reload --port 8000
```

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

---

## Environment variables

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key |
| `QDRANT_URL` | Qdrant instance URL |
| `QDRANT_API_KEY` | Qdrant API key (if using Qdrant Cloud) |
| `LANGCHAIN_API_KEY` | LangSmith API key |
| `LANGCHAIN_PROJECT` | LangSmith project name |
| `ALPHA_VANTAGE_API_KEY` | Market data API key |
| `GCS_BUCKET` | GCS bucket for filing storage |
| `GCP_PROJECT` | GCP project ID |

---

## Project structure

```
quantdesk/
├── backend/
│   ├── agents/          # LangGraph agent definitions
│   ├── api/             # FastAPI routes and middleware
│   ├── core/            # State schema, config, types
│   ├── data_ingestion/  # SEC EDGAR + transcript ingestion
│   ├── rag/             # Hybrid retrieval (BM25 + Qdrant)
│   ├── evaluation/      # RAGAS evaluation harness
│   └── utils/           # Shared utilities
├── frontend/
│   └── src/
│       ├── components/  # UI components
│       ├── hooks/       # Data fetching hooks
│       ├── pages/       # Route-level pages
│       └── store/       # Zustand state
├── infrastructure/
│   ├── gcp/             # Cloud Run + GCS Terraform
│   └── docker/          # Dockerfiles
├── PRD.md
└── docker-compose.yml
```

---

## Deployment

```bash
cd infrastructure/gcp
terraform init
terraform apply
```

Then push to Cloud Run:

```bash
gcloud builds submit --config cloudbuild.yaml
```

---

## Evaluation

```bash
cd backend
python -m evaluation.run_ragas --dataset data/eval_questions.json --output results/
```

---

## Phases

See [PRD.md](./PRD.md) for the full phased delivery plan.

- **Phase 1:** Foundation — ingestion pipeline, Qdrant setup, FastAPI skeleton
- **Phase 2:** Core agents — ratio analysis, sentiment, RAG retrieval, LangSmith
- **Phase 3:** Peer comparison, synthesis, RAGAS eval
- **Phase 4:** Frontend, GCP deployment, integration tests
