# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

掌柜问数 (storekeeper-nl2sql) — a Chinese natural-language-to-SQL agent. A user asks a business question in Chinese, a LangGraph pipeline retrieves relevant schema/metric/value metadata, generates SQL, validates and (if needed) corrects it, executes it against a data warehouse, and streams progress back over SSE. The `pyproject.toml` package name is `data-agent`; older docs reference the project as `data-agent`.

## Commands

All commands run from the repository root (the directory containing `Makefile` and `pyproject.toml`). Python is wrapped with `uv run` — no manual venv activation needed.

**Middleware (MySQL / Elasticsearch+IK / Qdrant / TEI embedding):**
```sh
make middleware   # start all (first run pulls images + builds embedding model cache)
make down         # stop
make ps / make logs
make clean        # remove containers + dw/meta/qdrant/es data (embedding model cache preserved)
```
Ports: MySQL 3306, ES 9200, Qdrant 6333/6334, embedding (TEI) 8081.

**Embedding model is served offline from a local copy** — do NOT rely on HuggingFace downloads (network access to `huggingface.co` is blocked here). The compose `embedding` service uses `MODEL_ID: /models/bge-large-zh-v1.5` and mounts `docker/models/bge-large-zh-v1.5` (the full `bge-large-zh-v1.5` weights, ~1.2G `pytorch_model.bin`, sourced from `2.资料/2.docker compose/embedding/`). TEI's ONNX backend won't find `model.onnx` and automatically falls back to the candle backend loading the pytorch weights — this is expected. If you recreate the embedding container or move the repo, keep `docker/models/bge-large-zh-v1.5/` populated, otherwise startup hangs forever retrying HF downloads. Verify it's up: `curl -s localhost:8081/health` (200) and that `/embed` returns 1024-dim vectors.

**Build the meta knowledge base** (must run once after middleware is up, before querying — populates `meta` DB + Qdrant + ES from `backend/conf/meta_config.yaml`):
```sh
uv run python -m backend.app.scripts.build_meta_knowledge --conf backend/conf/meta_config.yaml
# --clean true  (or SYS_ISCLEAN_CONFIG=true in .env) wipes all meta knowledge first
```
Defaults for `--conf`/`--clean` come from `.env` (`META_KNOWLEDGE_CONFIG`, `SYS_ISCLEAN_CONFIG`). **Heads up:** `.env` ships with `SYS_ISCLEAN_CONFIG=true`, so *every* run of this script wipes the knowledge base (MySQL meta tables + Qdrant collections + ES index) before rebuilding. Fine for a fresh build; set it to `false` if you only want to append.

**Backend** — entry is `backend/main.py`, FastAPI on `0.0.0.0:8000`. Source uses absolute `backend.app.*` imports, so it **must** be started as a module from the root:
```sh
uv run python -m backend.main        # NOT `python backend/main.py` (import error)
```

**Frontend** — Vue 3 + Vite in `fronted/` (note the spelling: `fronted`, not `frontend`):
```sh
cd fronted && npm install && npm run dev   # http://127.0.0.1:5173
```
The backend CORS allowlist only permits `localhost:5173` / `127.0.0.1:5173`.

There is no test suite, linter, or build step for the backend. Most modules have a `if __name__ == '__main__':` smoke-test block (e.g. `backend/app/agent/graph.py`, `backend/app/agent/llm.py`, `backend/app/clients/mysql_client_manager.py`) — run them as `uv run python -m backend.app.<module>` to exercise a single component.

## Architecture

### Two MySQL databases
- **`meta`** — the *knowledge base*: `table_info`, `column_info`, `metric_info`, `column_metric`. Describes the warehouse schema and business metrics. Populated by `build_meta_knowledge`.
- **`dw`** — the actual *data warehouse* (star schema: `dim_*` + `fact_order`) that generated SQL runs against.

Each DB has its own client manager (`meta_mysql_client_manager`, `dw_mysql_client_manager`) and its own repository tree under `backend/app/repositories/mysql/{meta,dw}/`.

### Three retrieval stores
Schema/metric/value metadata is indexed three ways for recall:
- **Qdrant** (vectors) — column embeddings and metric embeddings (`column_qdrant_repository`, `metric_qdrant_repository`). Embeddings via a self-hosted TEI server (`BAAI/bge-large-zh-v1.5`, 1024-dim) wrapped by `HuggingFaceEndpointEmbeddings`.
- **Elasticsearch** (full-text, IK analyzer) — column *values* (`value_es_repository`). Only columns with `sync: true` in `meta_config.yaml` get their values indexed.

For each entity, multiple texts are embedded/indexed: the name, the description, and every alias — so recall matches any of them.

### The LangGraph agent (`backend/app/agent/`)
The pipeline is a compiled `StateGraph` in `graph.py`. Flow:
```
extract_keywords (jieba)
  ├─> recall_column ─┐
  ├─> recall_value  ─┼─> merge_retrieved_info ─┬─> filter_table ─┐
  └─> recall_metric ─┘                         └─> filter_metric ┴─> add_extra_context
  ─> generate_sql ─> validate_sql ──(error?)──> correct_sql ─┐
                              └──(ok)───────────> execute_sql ┴─> END
```
The fan-out (3 parallel recalls) and fan-in (`merge_retrieved_info`) are real concurrency. `validate_sql` branches via a conditional edge on `state["error"]`: `None` → `execute_sql`, otherwise → `correct_sql` → `execute_sql`.

Key conventions for nodes:
- **State** is a `TypedDict` (`DataAgentState` in `state.py`) — nodes return partial dicts that get merged.
- **Dependencies are injected via the graph `context`**, not imported. Every node has signature `async def node(state, runtime: Runtime[DataAgentContext])` and pulls repos/clients from `runtime.context[...]`. `DataAgentContext` (`agent/context.py`) is the typed bag of repositories + embedding client.
- **Progress is streamed** with `runtime.stream_writer({"type": "progress", "step": ..., "status": "running"|"success"|"error"})`. The graph is consumed with `stream_mode="custom"`, and `QueryService` forwards each chunk as an SSE `data:` line. When adding a node, emit running/success/error progress events to keep the UI in sync.
- The shared LLM is `backend/app/agent/llm.py` (`init_chat_model`, `model_provider="openai"`, temperature 0, pointed at the `llm` block in `app_config.yaml`). LLM-driven nodes load a prompt template from `backend/prompts/*.prompt` via `load_prompt(name)` and typically chain `prompt | llm | JsonOutputParser`.

### Request path
`POST /api/query` (`api/routers/query_router.py`) → FastAPI `Depends` chain in `api/dependencies.py` builds a `QueryService` with fresh per-request repositories → `QueryService.query` runs `graph.astream` and yields SSE. Long-lived clients (engines, ES/Qdrant/embedding) are initialized once in `core/lifespan.py` and torn down on shutdown; per-request DB sessions come from `*_client_manager.session_factory()`.

### Config & layering
- **Config** is YAML loaded into OmegaConf-structured dataclasses: `backend/conf/app_config.yaml` → `app_config.py` schema; `backend/conf/meta_config.yaml` → `meta_config.py` schema (via `conf/config_loader.py`). `app_config.yaml` holds DB creds, store hosts/ports, and **LLM api_key/base_url** — treat it as containing secrets.
- **`meta_config.yaml` is the source of truth** for what schema/metrics the agent knows about. To teach the agent a new table, column, metric, or alias, edit this file and re-run `build_meta_knowledge`. `role` values (`dim`/`fact`, `primary_key`/`foreign_key`/`dimension`/`measure`) and `sync` (value-indexing toggle) drive downstream behavior.
- Layering is `api → services → agent (nodes) → repositories → clients`. `entities/` are domain dataclasses (Qdrant/ES payloads); `models/` are SQLAlchemy ORM models for the `meta` DB; `repositories/mysql/meta/mappers/` convert between them.
- `PROJECT_ROOT` (`constants/project_constant.py`) is resolved by walking up to find `.env`, or from the `PROJECT_ROOT` env var (set by the Makefile for Docker).

### Initial warehouse/meta data
`scripts/mysql/init/*.sql` runs on first MySQL container start (`docker-entrypoint-initdb.d`): creates the `dw`/`meta` databases + `storekeeper` user, the `dw` star schema, sample data, and the `meta` schema. If the `storekeeper` user is missing after a prior run, `make clean && make middleware` re-runs these.
