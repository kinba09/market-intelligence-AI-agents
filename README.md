# Market Intelligence AI (Free-First Complete Product)

A full product MVP for autonomous market intelligence:
- Landing page (`/`)
- Login/register (`/login`)
- Authenticated dashboard (`/app`)
- User BYOK LLM setup (Gemini free key or other provider keys)
- Daily autonomous source monitors
- Guardrailed hybrid RAG with citations
- LLMOps logs + workflow logs

## Key capabilities

- Ingestion: URL / RSS / report
- Enrichment: entities, events, sentiment, importance scoring
- Retrieval: OpenSearch BM25 + Qdrant vectors
- Agent workflow: query understanding -> retrieval -> validation -> synthesis
- Alerting: event-based scored alerts
- Automation: scheduler runs monitors daily (or every N hours)
- LLMOps: logs every LLM call + workflow runs

## System Design Architecture

### High-level architecture

```text
[External Sources: News/Company Sites/Jobs/Social/Reports]
                      |
                      v
          [Ingestion Layer: FastAPI endpoints]
               |                    |
               v                    v
      [MinIO Raw Artifacts]   [Normalize + Chunk]
                                     |
                                     +--> [AI Enrichment: entities/events/sentiment] --> [PostgreSQL]
                                     +--> [Embeddings] --> [Qdrant Vector Index]
                                     +--> [BM25 Indexing] --> [OpenSearch]

[OpenSearch] ----\
                  \
[Qdrant] -----------> [Hybrid Retrieval Service] -> [Agent Workflow]
                  /                                (understand -> retrieve -> validate -> synthesize)
[PostgreSQL] ----/                                          |
                                                            v
                                                  [RAG Answer + Citations] --> [Dashboard]

[AI Enrichment] -> [Alert Scoring] -> [PostgreSQL] -> [Dashboard]
[Scheduler] -> [Daily Source Monitors] -> [Ingestion Layer]
[LLMOps] -> [LLM Run Logs + Workflow Logs]
```

## Free-first approach

- No paid orchestration required.
- Scheduler uses `APScheduler` inside FastAPI.
- Users can bring free Gemini API Studio keys.
- Other LLM providers supported via LiteLLM-compatible provider+model settings.

## Guardrails implemented

- Input checks for prompt-injection patterns and length constraints.
- Grounded output validation (requires citations).
- Safe fallback answer when evidence is weak.

## LLMOps implemented

- `llm_run_logs` table + `logs/llm_runs.jsonl`
- `workflow_run_logs` table + `logs/workflow_runs.jsonl`
- Dashboard views for both log streams.

## Run with Docker Compose

### 1) Prepare env

```bash
cp .env.example .env
```

Set at least:

```env
APP_SECRET_KEY=your-long-random-secret
GEMINI_API_KEY=your-gemini-key-optional
```

### 2) Important: if you used older schema, reset volumes

```bash
docker compose down -v
```

### 3) Build and run

```bash
docker compose up --build
```

### 4) Open

- Landing: `http://localhost:8000/`
- Login: `http://localhost:8000/login`
- Dashboard: `http://localhost:8000/app`
- API docs: `http://localhost:8000/docs`

## Product usage flow

1. Register and login.
2. In dashboard, add your LLM key (provider/model/api key).
3. Add source monitors (`rss` or `url`) with frequency (default 24h).
4. Add watchlist companies.
5. Ingest manually once (optional bootstrap).
6. Ask RAG questions and review citations.
7. Check alerts and competitor summaries.
8. Review LLMOps logs for model latency/errors.

## Main API routes

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/llm-key`
- `GET /api/auth/llm-keys`
- `POST /api/automation/monitors`
- `GET /api/automation/monitors`
- `POST /api/automation/monitors/{id}/run`
- `GET /api/ops/llm-runs`
- `GET /api/ops/workflow-runs`
- `POST /api/ingest/url`
- `POST /api/ingest/rss`
- `POST /api/query/ask`
- `GET /api/events`
- `GET /api/alerts`
- `POST /api/reports/competitor-summary`

## Notes

- Data is user-scoped (multi-user safe at API layer).
- API keys are encrypted at rest using app secret-derived encryption.
- For local/dev with schema changes, rebuild from clean volumes.
