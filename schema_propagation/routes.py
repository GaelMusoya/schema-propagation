import asyncio
import time
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .generator import generate_sql, get_version, list_versions
from .propagator import (
    get_job, list_tenant_databases, propagate, stream_job_progress, JobStatus
)
from .simulator import create_test_databases, cleanup_test_databases

router = APIRouter(prefix="/schema", tags=["Schema Propagation"])


class GenerateRequest(BaseModel):
    description: str
    target_revision: str = "head"


class PropagateRequest(BaseModel):
    version_id: str
    dry_run: bool = False
    max_connections: int = 100
    database_pattern: str = "cmp_%"


class SimulateRequest(BaseModel):
    count: int
    prefix: str = "cmp_"
    start_id: int = 1
    template_db: str | None = None


class BenchmarkRequest(BaseModel):
    database_counts: list[int] = [100, 500, 1000]
    schema_types: list[str] = ["add_column"]
    max_connections: int = 100


SAMPLE_SQL = {
    "add_column": "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS preferences JSONB;",
    "add_table": "CREATE TABLE IF NOT EXISTS user_settings (id SERIAL PRIMARY KEY, user_id INT, key VARCHAR(100), value TEXT);",
    "add_index": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email ON users(email);",
    "complex": """
        ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS metadata JSONB;
        CREATE TABLE IF NOT EXISTS audit_log (id SERIAL PRIMARY KEY, action VARCHAR(50), ts TIMESTAMPTZ DEFAULT NOW());
        CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
    """
}


# Background propagation task
async def run_propagation(job_id: str, sql: str, version_id: str, checksum: str, databases: list[str], max_connections: int, dry_run: bool):
    job = get_job(job_id)
    if job:
        await propagate(sql, version_id, checksum, databases, max_connections, dry_run)


@router.post("/generate")
async def generate(request: GenerateRequest):
    try:
        return generate_sql(request.description, request.target_revision)
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/versions")
async def versions():
    return list_versions()


@router.get("/versions/{version_id}")
async def version_detail(version_id: str):
    version = get_version(version_id)
    if not version:
        raise HTTPException(404, "Version not found")
    return version


@router.get("/databases")
async def databases(pattern: str = "cmp_%"):
    return await list_tenant_databases(pattern)


@router.post("/propagate")
async def start_propagation(request: PropagateRequest, background_tasks: BackgroundTasks):
    version = get_version(request.version_id)
    if not version:
        raise HTTPException(404, "Version not found")

    databases = await list_tenant_databases(request.database_pattern)
    if not databases:
        raise HTTPException(400, "No databases found matching pattern")

    from .propagator import create_job
    job = create_job(request.version_id, len(databases))

    background_tasks.add_task(
        run_propagation,
        job.job_id,
        version["upgrade_sql"],
        request.version_id,
        version["checksum"],
        databases,
        request.max_connections,
        request.dry_run
    )

    return {"job_id": job.job_id, "status": "started", "total_databases": len(databases)}


@router.get("/propagate/{job_id}")
async def get_propagation_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    
    elapsed = time.time() - job.started_at if job.started_at else 0
    rate = job.completed / elapsed if elapsed > 0 else 0
    remaining = job.total - job.completed
    eta = remaining / rate if rate > 0 else 0

    return {
        "job_id": job.job_id,
        "status": job.status,
        "progress": {
            "total": job.total,
            "completed": job.completed,
            "successful": job.successful,
            "failed": job.failed,
            "skipped": job.skipped
        },
        "rate": f"{rate:.1f} db/s",
        "eta_seconds": int(eta),
        "errors": job.errors[:10]  # Limit to 10
    }


@router.get("/propagate/{job_id}/stream")
async def stream_progress(job_id: str):
    if not get_job(job_id):
        raise HTTPException(404, "Job not found")
    
    async def generate():
        async for data in stream_job_progress(job_id):
            yield {"data": data}
    
    return EventSourceResponse(generate())


@router.post("/propagate/{job_id}/stop")
async def stop_propagation(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    job.stop_requested = True
    return {"status": "stop_requested"}


@router.post("/simulate/create")
async def simulate_create(request: SimulateRequest):
    dbs = await create_test_databases(request.count, request.prefix, request.start_id, request.template_db)
    return {"created": len(dbs), "databases": dbs[:20]}


@router.delete("/simulate/cleanup")
async def simulate_cleanup(prefix: str = "cmp_"):
    dbs = await list_tenant_databases(f"{prefix}%")
    removed = await cleanup_test_databases(dbs)
    return {"removed": removed}


@router.post("/benchmark")
async def run_benchmark(request: BenchmarkRequest):
    results = []
    benchmark_id = f"bench_{uuid4().hex[:8]}"

    for db_count in request.database_counts:
        test_dbs = await create_test_databases(db_count, prefix="bench_")

        for schema_type in request.schema_types:
            sql = SAMPLE_SQL.get(schema_type, SAMPLE_SQL["add_column"])
            version_id = f"bench_{uuid4().hex[:8]}"

            start = time.perf_counter()
            await propagate(sql, version_id, "benchtest", test_dbs, request.max_connections, dry_run=False)
            duration = time.perf_counter() - start

            results.append({
                "db_count": db_count,
                "schema_type": schema_type,
                "duration_sec": round(duration, 2),
                "rate": round(db_count / duration, 1) if duration > 0 else 0,
                "avg_ms_per_db": round((duration / db_count) * 1000, 2) if db_count > 0 else 0
            })

        await cleanup_test_databases(test_dbs)

    return {"benchmark_id": benchmark_id, "results": results}
