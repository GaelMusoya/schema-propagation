# Schema Propagation

High-performance async system for broadcasting database schema changes across thousands of tenant databases.

## Problem

Applying schema migrations to 100k+ tenant databases sequentially takes ~14 hours. This system does it in ~15 minutes using async concurrency.

## Features

- **Concurrent execution** - 50-200 simultaneous connections via asyncpg
- **Idempotent** - Version tracking prevents duplicate applications
- **Resilient** - Automatic retry with exponential backoff
- **Observable** - Real-time SSE streaming + Prometheus metrics
- **Safe** - Dry-run mode, error threshold circuit breaker

## Quick Start

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your database credentials

# 2. Start services
docker-compose up -d

# 3. API available at http://localhost:8001
```

## Configuration (.env)

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_ENDPOINT` | PostgreSQL host | localhost |
| `DB_PORT` | PostgreSQL port | 5432 |
| `DB_USERNAME` | Database user | postgres |
| `DB_PASSWORD` | Database password | postgres |
| `APP_HOST_PORT` | Exposed API port | 8001 |
| `UVICORN_WORKERS` | Worker processes | 1 |
| `MAX_CONCURRENT_CONNECTIONS` | Parallel DB connections | 100 |
| `PGBOUNCER_DEFAULT_POOL_SIZE` | Connection pool size | 200 |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/schema/generate` | Generate SQL from Alembic |
| POST | `/schema/generate/models` | Generate SQL from a SQLAlchemy models file |
| GET | `/schema/versions` | List all versions |
| POST | `/schema/propagate` | Start propagation job |
| POST | `/schema/propagate/models` | Generate SQL from models and propagate in one step |
| GET | `/schema/propagate/{job_id}` | Get job status |
| GET | `/schema/propagate/{job_id}/stream` | SSE real-time updates |
| POST | `/schema/propagate/{job_id}/stop` | Stop propagation |
| GET | `/schema/databases` | List tenant databases |
| POST | `/schema/simulate/create` | Create test DBs |
| DELETE | `/schema/simulate/cleanup` | Remove test DBs |
| POST | `/schema/benchmark` | Run performance benchmark |
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |

## Usage Example

```bash
# Generate SQL from migrations
curl -X POST http://localhost:8001/schema/generate \
  -H "Content-Type: application/json" \
  -d '{"description": "Add user preferences"}'

# Start propagation (dry run first)
curl -X POST http://localhost:8001/schema/propagate \
  -H "Content-Type: application/json" \
  -d '{"version_id": "20260112_143000", "dry_run": true}'

# Execute propagation
curl -X POST http://localhost:8001/schema/propagate \
  -H "Content-Type: application/json" \
  -d '{"version_id": "20260112_143000", "max_connections": 100}'

# Monitor progress (response includes per-db latency and total elapsed_ms)
curl http://localhost:8001/schema/propagate/{job_id}
```

## Quick Test: Create 5 Tenant DBs and Propagate

**Windows PowerShell** (uses `curl.exe` to avoid the built‑in alias):

```powershell
# 1) Create 5 databases: cmp_1..cmp_5
curl.exe -X POST http://localhost:8001/schema/simulate/create `
  -H "Content-Type: application/json" `
  -d '{\"count\":5,\"prefix\":\"cmp_\",\"start_id\":1}'

# 2) Verify they exist
curl.exe http://localhost:8001/schema/databases?pattern=cmp_%

# 3) Generate SQL from migrations (note the version_id)
curl.exe -X POST http://localhost:8001/schema/generate `
  -H "Content-Type: application/json" `
  -d '{\"description\":\"test run\",\"target_revision\":\"head\"}'

# 4) Propagate to the 5 DBs (replace VERSION_ID)
curl.exe -X POST http://localhost:8001/schema/propagate `
  -H "Content-Type: application/json" `
  -d '{\"version_id\":\"VERSION_ID\",\"dry_run\":false,\"max_connections\":20}'

# 5) Check status (replace JOB_ID)
curl.exe http://localhost:8001/schema/propagate/JOB_ID
```

**Linux/macOS shells** (straight JSON, no escaping gymnastics):

```bash
curl -X POST http://localhost:8001/schema/simulate/create \
  -H "Content-Type: application/json" \
  -d '{"count":5,"prefix":"cmp_","start_id":1}'

curl http://localhost:8001/schema/databases?pattern=cmp_%

curl -X POST http://localhost:8001/schema/generate \
  -H "Content-Type: application/json" \
  -d '{"description":"test run","target_revision":"head"}'

curl -X POST http://localhost:8001/schema/propagate \
  -H "Content-Type: application/json" \
  -d '{"version_id":"VERSION_ID","dry_run":false,"max_connections":20}'

curl http://localhost:8001/schema/propagate/JOB_ID
```

Cleanup test databases:

```powershell
curl.exe -X DELETE http://localhost:8001/schema/simulate/cleanup?prefix=cmp_  # PowerShell
```
```bash
curl -X DELETE http://localhost:8001/schema/simulate/cleanup?prefix=cmp_      # Linux/macOS
```

### Model-driven propagation (optional pruning)
- `POST /schema/propagate/models` body supports: `path` (container path to models file), `base_symbol` (default `Base`), `database_pattern`, `max_connections`, `dry_run`, and `prune_missing` (default `false`). When `prune_missing` is true, the generated SQL will also drop tables/columns that were present in the previous models generation but are no longer defined.

### Common 422 Causes
- Wrong endpoint: `/schema/generate` requires `description`; `/schema/simulate/create` requires `count`. If the server complains about `description` but you sent `count`, the request likely hit `/schema/generate` or the JSON was malformed.
- PowerShell JSON quoting: prefer the `curl.exe ... -d '{\"key\":\"value\"}'` style above, or use `Invoke-RestMethod -Body (@{count=5;prefix='cmp_';start_id=1} | ConvertTo-Json)`.

## Project Structure

```
├── .env                    # Environment configuration
├── Dockerfile              # Container build
├── docker-compose.yml      # Service orchestration
├── docker/entrypoint.sh    # Runtime config (no rebuild needed)
├── schema_propagation/
│   ├── api.py              # FastAPI app + metrics
│   ├── config.py           # Pydantic settings
│   ├── generator.py        # Alembic SQL extraction
│   ├── propagator.py       # Async broadcast engine
│   ├── routes.py           # API endpoints
│   └── simulator.py        # Test DB creation
└── sql_versions/           # Generated SQL storage
```

## Performance

| Scale | Connections | Expected Rate |
|-------|-------------|---------------|
| 1k DBs | 50 | ~100 db/s |
| 10k DBs | 100 | ~200 db/s |
| 100k DBs | 200-300 | ~450 db/s |

PgBouncer is required for 10k+ databases.
