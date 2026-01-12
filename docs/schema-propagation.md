# Schema Propagation System

> **Guide Document**: Specifications and key logic for building a high-performance
> schema propagation service. Adapt examples to your needs.

---

## Overview

### What is Schema Propagation?

**Schema Propagation** is a system designed to efficiently broadcast database schema changes 
across thousands of identical tenant databases in a multi-tenant SaaS architecture.

In BlinkHub's architecture, each company has its own isolated PostgreSQL database (`cmp_1`, 
`cmp_2`, ... `cmp_100000`). When the application evolves and requires schema changes (new 
tables, columns, indexes, constraints), these changes must be applied consistently to **every** 
tenant database.

### The Problem

The current approach using `migration_manager.py` has critical limitations:

1. **Sequential Processing**: Uses subprocess to run Alembic per database, one at a time
2. **Process Overhead**: Spawns a new Python process for each of 100,000 databases
3. **No Recovery**: If interrupted, must restart from the beginning
4. **No Visibility**: No real-time progress monitoring or error aggregation
5. **Time Prohibitive**: ~14 hours for 100k databases makes deployments impractical

### The Solution

This system replaces subprocess-based migrations with a high-performance async engine:

1. **Generate Once**: Extract raw SQL from Alembic migrations using Python API
2. **Propagate Concurrently**: Apply SQL to 50-200 databases simultaneously using `asyncpg`
3. **Track Progress**: Real-time SSE streaming, Prometheus metrics, and job persistence
4. **Ensure Idempotency**: Version tracking per database prevents duplicate applications
5. **Enable Recovery**: Resume from any point with automatic retry and error thresholds

### Key Goals

| Goal | Implementation |
|------|----------------|
| **Speed** | 100k databases in ~15 minutes (vs 14 hours) |
| **Reliability** | Automatic retry with exponential backoff |
| **Visibility** | Real-time progress via SSE + Prometheus metrics |
| **Safety** | Dry-run mode, error thresholds, rollback support |
| **Scalability** | Connection pooling via PgBouncer, distributed workers |
| **Testability** | Built-in benchmarking by DB count and schema type |

---

### Performance Comparison

| Metric | Current (Subprocess) | New (Async) |
|--------|---------------------|-------------|
| 100k DBs | ~14 hours | ~15 minutes |
| Memory | High (spawn process) | Low (shared) |
| Connections | 1 at a time | 50-200 concurrent |
| Error Recovery | Manual | Automatic retry |

---

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌─────────────────────────┐
│  SQLAlchemy  │────▶│   Alembic    │────▶│   SQL Script            │
│  Models      │     │  (Generate)  │     │  (ALTER TABLE...)       │
└──────────────┘     └──────────────┘     └───────────┬─────────────┘
                                                      │
                                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ASYNC PROPAGATOR ENGINE                          │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Worker Pool (asyncio.Semaphore - 50-200 concurrent)          │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
          │          │          │          │
          ▼          ▼          ▼          ▼
     ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐
     │ cmp_1  │ │ cmp_2  │ │ cmp_3  │ │ cmp_100000 │
     └────────┘ └────────┘ └────────┘ └────────────┘
```

---

## Tech Stack (Python 3.12+)

```text
# Core
asyncpg>=0.29.0              # Async PostgreSQL (10x faster than psycopg2)
alembic>=1.13.0              # SQL generation only
sqlalchemy>=2.0.0            # ORM for models
pydantic-settings>=2.0.0     # Type-safe config
python-decouple>=3.8         # Environment variable management

# API (FastAPI for native async + SSE)
fastapi>=0.115.0             # Native async, auto OpenAPI docs
uvicorn[standard]>=0.32.0    # ASGI server
sse-starlette>=2.0.0         # Server-Sent Events

# CLI & Observability
typer[all]>=0.12.0
rich>=13.0.0
structlog>=24.0.0
prometheus-client>=0.19.0
```

> **Why FastAPI over Flask?** Native async/await, built-in SSE support via Starlette,
> automatic OpenAPI documentation, and ~3x better throughput for async workloads.

### System Requirements (100k DBs)

| Component | Recommended |
|-----------|-------------|
| Python | 3.12+ |
| RAM | 8 GB |
| PostgreSQL | 15+ |
| PgBouncer | Required |

---

## Directory Structure

```
BlinkHub-BE/
├── schema_propagation/
│   ├── __init__.py
│   ├── generator.py      # Alembic → SQL extraction
│   ├── propagator.py     # Async broadcast engine
│   ├── simulator.py      # Test database creation
│   └── config.py         # Pydantic settings
├── routes/
│   └── schema_propagation.py  # API endpoints
└── sql_versions/
    └── YYYYMMDD_HHMMSS/
        ├── metadata.json
        ├── upgrade.sql
        └── downgrade.sql
```

---

## Core Components

### 1. Schema Generator

**Purpose**: Extract raw SQL from Alembic migrations using Python API (no subprocess).

**Technologies**:
- `alembic.config.Config` - Load configuration
- `alembic.script.ScriptDirectory` - Access migration scripts
- `alembic.runtime.migration.MigrationContext` - Capture SQL offline

**Key Logic**:

```python
# Use Alembic''s offline mode to capture SQL without executing
context = MigrationContext.configure(
    connection=connection,
    opts={"as_sql": True, "literal_binds": True}
)

# Iterate revisions and capture SQL
for rev in script_dir.iterate_revisions(target, current):
    ops = Operations(context)
    for op in rev.upgrade_ops.ops:
        op.invoke(ops)  # Writes SQL to buffer

# Output: sql_versions/{timestamp}/upgrade.sql
```

**Output Structure**:
```json
{
  "version_id": "20260112_143000",
  "revision_id": "abc123",
  "checksum": "sha256[:16]",
  "description": "Add user preferences"
}
```

---

### 2. High-Performance Propagator

**Purpose**: Broadcast SQL to thousands of databases concurrently.

**Technologies**:
- `asyncpg` - Async PostgreSQL driver
- `asyncio.Semaphore` - Connection limiting
- `asyncio.as_completed` - Process results as they finish

**Core Algorithm**:

```python
async def propagate(sql: str, version_id: str, databases: list[str]):
    semaphore = asyncio.Semaphore(max_connections)  # e.g., 100
    
    async def process_one(db: str) -> Result:
        async with semaphore:  # Limit concurrent connections
            conn = await asyncpg.connect(database=db)
            try:
                # Idempotency check
                if await is_version_applied(conn, version_id):
                    return Result(db, "skipped")
                
                # Execute with retry (exponential backoff)
                for attempt in range(max_retries):
                    try:
                        async with conn.transaction():
                            await conn.execute(sql)
                            await record_version(conn, version_id)
                        return Result(db, "success")
                    except PostgresError:
                        await asyncio.sleep(1 * 2**attempt)  # 1s, 2s, 4s...
                
                return Result(db, "failed")
            finally:
                await conn.close()
    
    # Process all databases concurrently
    tasks = [process_one(db) for db in databases]
    for coro in asyncio.as_completed(tasks):
        result = await coro
        # Update progress, check error threshold (stop if >10% fail)
```

**Key Features**:
- Semaphore-based connection limiting
- Exponential backoff retry (1s, 2s, 4s... max 30s)
- Version tracking table per database for idempotency
- Error threshold circuit breaker (stop if >10% fail)

**Version Tracking Table** (created in each tenant DB):
```sql
CREATE TABLE IF NOT EXISTS schema_propagation_version (
    version_id VARCHAR(50) PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    checksum VARCHAR(32)
);
```

---

### 3. Tenant Simulator

**Purpose**: Create test databases for load testing.

**Technologies**:
- `asyncpg` - Fast concurrent creation
- PostgreSQL `TEMPLATE` - Clone existing database

**Key Logic**:
```python
# Fast creation via PostgreSQL template
await conn.execute(f''CREATE DATABASE "{new_db}" TEMPLATE "{template_db}"'')

# Concurrent with semaphore limiting (max 20 parallel)
tasks = [create_single(i) for i in range(start_id, start_id + count)]
```

---

## API Endpoints

### Route Module: `routes/schema_propagation.py`

Using FastAPI for native async and SSE support:

```python
from fastapi import APIRouter, Depends, BackgroundTasks
from sse_starlette.sse import EventSourceResponse
from decouple import config

router = APIRouter(prefix="/schema", tags=["Schema Propagation"])

# Dependency for auth (adapt to existing JWT system)
async def require_schema_permission(token: str = Depends(oauth2_scheme)):
    # Validate JWT and check canManageSchemas permission
    pass

@router.post("/propagate")
async def start_propagation(
    request: PropagateRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(require_schema_permission)
):
    job_id = create_job(request)
    background_tasks.add_task(run_propagation, job_id)
    return {"job_id": job_id, "status": "started"}

@router.get("/propagate/{job_id}/stream")
async def stream_progress(job_id: str):
    async def event_generator():
        while not job_complete(job_id):
            yield {"data": get_progress(job_id)}
            await asyncio.sleep(0.5)
    return EventSourceResponse(event_generator())
```

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/schema/generate` | Generate SQL from Alembic |
| GET | `/schema/versions` | List all versions |
| GET | `/schema/versions/<id>` | Get version details |
| POST | `/schema/propagate` | Start propagation job |
| GET | `/schema/propagate/<job_id>` | Get job status |
| GET | `/schema/propagate/<job_id>/stream` | SSE real-time updates |
| POST | `/schema/propagate/<job_id>/stop` | Stop propagation |
| GET | `/schema/databases` | List tenant databases |
| POST | `/schema/simulate/create` | Create test DBs (dev) |
| DELETE | `/schema/simulate/cleanup` | Remove test DBs (dev) |

---

### Generate SQL

```
POST /schema/generate
Authorization: Bearer <token>
```

**Request**:
```json
{"description": "Add user preferences table", "target_revision": "head"}
```

**Response**:
```json
{
  "success": true,
  "version_id": "20260112_143000",
  "checksum": "a1b2c3d4e5f6g7h8",
  "files": {"upgrade": "sql_versions/.../upgrade.sql"}
}
```

---

### Start Propagation

```
POST /schema/propagate
```

**Request**:
```json
{
  "version_id": "20260112_143000",
  "dry_run": false,
  "max_connections": 100,
  "database_pattern": "cmp_%"
}
```

**Response**:
```json
{
  "job_id": "prop_abc123",
  "status": "in_progress",
  "total_databases": 100000
}
```

---

### Get Propagation Status

```
GET /schema/propagate/<job_id>
```

**Response**:
```json
{
  "job_id": "prop_abc123",
  "status": "in_progress",
  "progress": {
    "total": 100000,
    "completed": 45000,
    "successful": 44900,
    "failed": 100
  },
  "rate": "450.5 db/s",
  "eta_seconds": 122
}
```

---

## Docker Configuration

> **Assumption**: PostgreSQL database already exists externally.

### docker-compose.propagation.yml

```yaml
version: '3.8'

services:
  propagator:
    build:
      context: ..
      dockerfile: docker/Dockerfile.propagator
    ports:
      - "8001:8000"  # FastAPI on uvicorn
    environment:
      - DB_ENDPOINT=${DB_ENDPOINT}        # External PostgreSQL host
      - DB_PORT=${DB_PORT:-5432}
      - DB_USERNAME=${DB_USERNAME}
      - DB_PASSWORD=${DB_PASSWORD}
      - PGBOUNCER_HOST=pgbouncer
      - PGBOUNCER_PORT=6432
      - MAX_CONCURRENT_CONNECTIONS=200
    depends_on: [pgbouncer]
    networks: [propagation-net]

  pgbouncer:
    image: edoburu/pgbouncer:1.21.0
    environment:
      - DATABASE_URL=postgres://${DB_USERNAME}:${DB_PASSWORD}@${DB_ENDPOINT}:${DB_PORT}
      - POOL_MODE=transaction
      - MAX_CLIENT_CONN=10000
      - DEFAULT_POOL_SIZE=200
    networks: [propagation-net]

networks:
  propagation-net:
    driver: bridge
```

### Dockerfile.propagator

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libpq5 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY schema_propagation/ ./schema_propagation/
COPY routes/schema_propagation.py ./routes/
ENV PYTHONUNBUFFERED=1
# FastAPI with uvicorn
ENTRYPOINT ["uvicorn", "schema_propagation.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Performance Tuning

| Scale | Connections | PgBouncer | Expected Rate |
|-------|-------------|-----------|---------------|
| 1k | 50 | Optional | ~100 db/s |
| 10k | 100 | Recommended | ~200 db/s |
| 50k | 200 | Required | ~350 db/s |
| 100k | 300 | Required | ~450 db/s |

### PgBouncer Config (100k)

```ini
pool_mode = transaction
max_client_conn = 10000
default_pool_size = 200
reserve_pool_size = 100
```

---

## Performance Benchmarking

### Benchmark Endpoint

```
POST /schema/benchmark
```

**Request**:
```json
{
  "database_counts": [100, 500, 1000, 5000, 10000],
  "schema_types": ["add_column", "add_table", "add_index", "complex"],
  "max_connections": 100
}
```

**Response** (stored for analysis):
```json
{
  "benchmark_id": "bench_abc123",
  "results": [
    {"db_count": 100, "schema_type": "add_column", "duration_sec": 1.2, "rate": 83.3},
    {"db_count": 1000, "schema_type": "add_column", "duration_sec": 8.5, "rate": 117.6},
    {"db_count": 10000, "schema_type": "add_index", "duration_sec": 95.2, "rate": 105.0}
  ]
}
```

### Schema Type Definitions

| Type | SQL Complexity | Expected Impact |
|------|---------------|----------------|
| `add_column` | `ALTER TABLE ADD COLUMN` | Fast (~1ms/db) |
| `add_table` | `CREATE TABLE` with FKs | Medium (~5ms/db) |
| `add_index` | `CREATE INDEX` | Slow (~50ms/db, locks) |
| `complex` | Multiple operations | Variable |

### Benchmark Algorithm

```python
async def run_benchmark(config: BenchmarkConfig) -> BenchmarkResult:
    results = []
    
    for db_count in config.database_counts:
        # Create test databases (use simulator)
        test_dbs = await create_test_databases(db_count, prefix="bench_")
        
        for schema_type in config.schema_types:
            sql = get_sample_sql(schema_type)  # Pre-defined SQL samples
            
            start = time.perf_counter()
            await propagate(sql, f"bench_{uuid4()}", test_dbs, config.max_connections)
            duration = time.perf_counter() - start
            
            results.append({
                "db_count": db_count,
                "schema_type": schema_type,
                "duration_sec": round(duration, 2),
                "rate": round(db_count / duration, 1),
                "avg_ms_per_db": round((duration / db_count) * 1000, 2)
            })
        
        # Cleanup test databases
        await cleanup_test_databases(test_dbs)
    
    # Store results with timestamp for historical comparison
    await store_benchmark_result(results)
    return results
```

### Monitoring Dashboard Metrics

Expose via Prometheus `/metrics` endpoint:

```python
# Counters
schema_propagation_total = Counter(
    'schema_propagation_total', 
    'Total propagations',
    ['status', 'schema_type']
)

# Histograms (for rate analysis)
schema_propagation_duration = Histogram(
    'schema_propagation_duration_seconds',
    'Duration per database',
    ['schema_type'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

# Gauges
schema_propagation_rate = Gauge(
    'schema_propagation_rate_per_second',
    'Current propagation rate (db/s)'
)
```

### Performance Validation Query

```
GET /schema/benchmark/compare?baseline=bench_abc&current=bench_xyz
```

**Response**:
```json
{
  "comparison": {
    "1000_dbs_add_column": {
      "baseline_rate": 115.2,
      "current_rate": 118.5,
      "improvement": "+2.9%"
    },
    "10000_dbs_add_index": {
      "baseline_rate": 95.0,
      "current_rate": 102.3,
      "improvement": "+7.7%"
    }
  },
  "recommendation": "Performance stable. Safe to increase max_connections to 150."
}
```

---

## Advanced Strategies

### Distributed Workers (100k+ DBs)

Use Redis queue for work distribution across multiple workers:

```
Coordinator → Redis Queue → N Workers → Databases
```

Each worker: `LPOP propagation:v1:pending` (atomic pop)

### Sharding Strategy

```python
shard_id = int(db_name.split(''_'')[1]) % num_shards
# cmp_12345 → 12345 % 10 → shard 5
```

### Rolling Deployment

```python
for batch in chunks(databases, size=1000):
    await propagate(batch)
    if not health_check(): raise RollbackRequired()
    await asyncio.sleep(pause_seconds)
```

### Monitoring

**Prometheus Metrics**:
- `schema_propagation_total{status}` - Counter
- `schema_propagation_duration_seconds` - Histogram
- `schema_propagation_active_connections` - Gauge

---

## Quick Start

```bash
# 1. Generate SQL
POST /schema/generate {"description": "Add preferences"}

# 2. Dry run
POST /schema/propagate {"version_id": "...", "dry_run": true}

# 3. Execute
POST /schema/propagate {"version_id": "...", "max_connections": 100}

# 4. Monitor
GET /schema/propagate/{job_id}
```

---

## Summary

| Component | Tech | Purpose |
|-----------|------|---------|
| Generator | Alembic Python API | Extract SQL |
| Propagator | asyncpg + asyncio | Concurrent broadcast |
| Simulator | asyncpg + TEMPLATE | Test DB creation |
| API | FastAPI + uvicorn | Async REST + SSE |
| Config | python-decouple | Environment management |
| Pool | PgBouncer | Connection management |
| Benchmark | Custom endpoint | Performance validation |
| Metrics | Prometheus | Observability |
