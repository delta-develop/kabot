

# KABOT

Kabot is a data ingestion and search system that stores catalog records and their
embeddings in PostgreSQL with pgvector. It is built with FastAPI, SQLModel, and Docker.

## Features

- Upload and process CSV files via HTTP endpoint
- Store catalog records and embeddings atomically in PostgreSQL
- Chunked and asynchronous processing for performance
- Uses pgvector for semantic search

## Getting Started

### Requirements

- Docker and Docker Compose
- [uv](https://docs.astral.sh/uv/) — `brew install uv`
- Make

### Running the Project

```bash
cp .env.example .env    # only outside a Superset workspace; setup does it for you
make up
```

`make up` waits for Mongo, Redis and Postgres to report healthy before starting
`core-api`, which creates its own PostgreSQL schema on startup. There is no
separate initialization step.

The pgvector schema change requires a one-time reset before its first startup.
`docker compose down -v` deletes both named volumes, `pg_data` and `mongo_data`.
Both volumes are intentionally disposable for this reset; catalog data is regenerated
from the CSV files in `data/`, and existing Mongo memory data is intentionally discarded:

```bash
docker compose down -v --remove-orphans
make up
```

Services listen on the ports in `.env`. Inside a Superset workspace those come
from a reserved block, so several workspaces run side by side:

| Service | Variable | Default |
|---|---|---|
| core-api | `CORE_API_PORT` | 8000 |
| agent | `AGENT_PORT` | 8001 |
| memory | `MEMORY_PORT` | 8002 |
| postgres | `POSTGRES_PORT` | 5432 |
| mongo | `MONGO_PORT` | 27017 |
| redis | `REDIS_PORT` | 6379 |

To start a single service: `docker compose up -d --wait memory`.

> **Orphaned containers from before the compose project name was pinned:** if you
> ran this stack before `docker-compose.yml` started setting `name: kabot-${PORT_BASE:-8000}`,
> your old containers and volumes live under the previous implicit project name (the
> worktree's directory name), and `docker compose down -v` here will not remove them.
> No data is lost, but they linger. List and remove them with:
> `docker compose -p <old-name> down -v`.

### Tests

```bash
make test        # every service
make lint
make typecheck
```

`make typecheck` exits non-zero: it reports 3 known errors in inherited
`core-api` code, tracked as debt (see `AGENTS.md` §9).

`POST /upload?namespace=restaurant-supplies` accepts the catalog CSV and stores each
item together with its embedding in PostgreSQL.

![alt text](image.png)

Other available urls:

- `GET /search` performs semantic search in one catalog namespace.
  Example: `http://localhost:8000/search?namespace=restaurant-supplies&query=refresco`

- `POST /debug/migrate-memory` Enforces system to migrate WorkingMemory to Long-Term  emory. Example: `http://localhost:8000/debug/migrate-memory?user_id=5215578771322`

- `GET /author` Retrieve author data



### Useful Makefile Commands

- `make up` - Starts all services in the background
- `make down` - Stops and removes all containers
- `make build` - Builds the service images
- `make rebuild-app` - Rebuilds the `core-api` image and restarts all services
- `make logs` - Follows the logs of all Docker containers
- `make ps` - Lists running containers
- `make shell` - Opens a shell in the `core-api` container
- `make psql` - Opens a `psql` session against the `postgres` container
- `make test` - Runs the test suite for every service
- `make lint` - Checks formatting with black and isort
- `make format` - Applies black and isort formatting
- `make typecheck` - Runs mypy for every service
- `make coverage` - Runs `core-api` tests with coverage

### API Endpoint

- `POST /upload?namespace=restaurant-supplies` - Ingest a catalog CSV
- `GET /search?namespace=restaurant-supplies&query=...` - Search the catalog

## Notes

- Catalog ingestion uses batches of 10 records.
- Reingesting the same `(namespace, external_id)` updates the existing row.

---

Built with 💻 and lots of coffee ☕️ by Leonardo and ChatGPT.
(Si lo leí, si le di permiso de que lo pusiera ahí, sería irónico crear un sistema para trabajar con LLMs sin usar un LLM ¿no creen? atentamente y con mucho respeto, Leo)


## Conversation Memory Use Cases

Kabot incorporates a multi-layered memory system inspired by human cognition, enabling rich and context-aware interactions. These are the main use cases supported by the `CognitiveOrchestrator`:

### Initial Conversation Bootstrapping
When a user starts a new conversation, the system retrieves and loads:
- A summarized memory (semantic context)
- A structured factual memory (preferences, identity, traits)

These components are injected as non-conversational context to prime the LLM for coherent and personalized responses.

### Ongoing Interaction
As the user and assistant exchange messages, each turn is stored in working memory (Redis). This cache:
- Tracks recent turns for continuity
- Is kept separate from factual memory and summary memory to avoid mixing signal with noise

### Contextual Expansion on Demand
If the LLM cannot resolve a user's query due to insufficient context, the orchestrator:
- Retrieves the full episodic history from long-term memory (MongoDB)
- Augments the current prompt with this deep history for accurate reasoning

### Conversation Closure and Consolidation
When the conversation ends—either due to inactivity or an explicit farewell—the orchestrator:
- Persists the working memory into the episodic memory store (append-only)
- Summarizes the recent session and merges it with the prior summary
- Extracts any newly revealed facts and updates the factual memory accordingly

This layered approach ensures long-term retention, efficient recall, and low-token consumption during active sessions.



## 📚 Used prompts

```mermaid
graph TD
  P1[INTENTION_PROMPT] --> Detecta_intención
  P2[FILTER_EXTRACTION_PROMPT] --> Extrae_filtros_JSON
  P3[VEHICLE_SUMMARIZATION_PROMPT] --> Resume_autos
  P4[FINANCE_PROMPT] --> Estima_mensualidades
  P5[KAVAK_INFO_PROMPT] --> Responde_dudas_generales
  P6[EXIT_PROMPT] --> Cierre_conversación
```

## 🧠 Agent Memory

```mermaid
graph TD
  REDIS[Working Memory - Redis] --> CURRENT[Conversación actual]
  MONGO_FACT[Fact Memory - MongoDB] --> USER_DATA[Datos del usuario]
  MONGO_SUM[Summary Memory - MongoDB] --> SUMMARY[Resumen de conversaciones]
  MONGO_EPISODIC[Episodic Memory - MongoDB] --> HISTORY[Historial completo]
```
