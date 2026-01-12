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
| GET | `/schema/versions` | List all versions |
| POST | `/schema/propagate` | Start propagation job |
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

# Monitor progress
curl http://localhost:8001/schema/propagate/{job_id}
```

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
