import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator
from uuid import uuid4

import asyncpg
import structlog

from .config import get_settings

log = structlog.get_logger()

VERSION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_propagation_version (
    version_id VARCHAR(50) PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    checksum VARCHAR(32)
);
"""


class JobStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class DBStatus(str, Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class DBResult:
    database: str
    status: DBStatus
    error: str | None = None
    duration_ms: float = 0


@dataclass
class PropagationJob:
    job_id: str
    version_id: str
    status: JobStatus = JobStatus.PENDING
    total: int = 0
    completed: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    started_at: float = 0
    errors: list[dict] = field(default_factory=list)
    stop_requested: bool = False


# In-memory job store (use Redis for production distributed workers)
_jobs: dict[str, PropagationJob] = {}


def get_job(job_id: str) -> PropagationJob | None:
    return _jobs.get(job_id)


def create_job(version_id: str, total: int) -> PropagationJob:
    job = PropagationJob(
        job_id=f"prop_{uuid4().hex[:12]}",
        version_id=version_id,
        total=total,
        started_at=time.time()
    )
    _jobs[job.job_id] = job
    return job


async def list_tenant_databases(pattern: str = "cmp_%") -> list[str]:
    """List all tenant databases matching pattern."""
    settings = get_settings()
    conn = await asyncpg.connect(settings.direct_dsn)
    try:
        rows = await conn.fetch(
            "SELECT datname FROM pg_database WHERE datname LIKE $1 ORDER BY datname",
            pattern.replace("*", "%")
        )
        return [r["datname"] for r in rows]
    finally:
        await conn.close()


async def propagate(
    sql: str,
    version_id: str,
    checksum: str,
    databases: list[str],
    max_connections: int | None = None,
    dry_run: bool = False
) -> PropagationJob:
    """Propagate SQL to all databases concurrently."""
    settings = get_settings()
    max_conn = max_connections or settings.max_concurrent_connections
    semaphore = asyncio.Semaphore(max_conn)
    job = create_job(version_id, len(databases))
    job.status = JobStatus.IN_PROGRESS

    async def process_db(db: str) -> DBResult:
        start = time.perf_counter()
        async with semaphore:
            if job.stop_requested:
                return DBResult(db, DBStatus.SKIPPED)
            try:
                conn = await asyncpg.connect(settings.db_dsn(db))
                try:
                    # Ensure version table exists
                    await conn.execute(VERSION_TABLE_SQL)
                    
                    # Idempotency check
                    exists = await conn.fetchval(
                        "SELECT 1 FROM schema_propagation_version WHERE version_id = $1",
                        version_id
                    )
                    if exists:
                        return DBResult(db, DBStatus.SKIPPED, duration_ms=(time.perf_counter() - start) * 1000)

                    if dry_run:
                        return DBResult(db, DBStatus.SUCCESS, duration_ms=(time.perf_counter() - start) * 1000)

                    # Execute with retry
                    for attempt in range(settings.max_retries):
                        try:
                            async with conn.transaction():
                                await conn.execute(sql)
                                await conn.execute(
                                    "INSERT INTO schema_propagation_version (version_id, checksum) VALUES ($1, $2)",
                                    version_id, checksum
                                )
                            return DBResult(db, DBStatus.SUCCESS, duration_ms=(time.perf_counter() - start) * 1000)
                        except asyncpg.PostgresError as e:
                            if attempt == settings.max_retries - 1:
                                raise
                            await asyncio.sleep(1 * (2 ** attempt))
                finally:
                    await conn.close()
            except Exception as e:
                return DBResult(db, DBStatus.FAILED, str(e), (time.perf_counter() - start) * 1000)

    tasks = [asyncio.create_task(process_db(db)) for db in databases]
    
    for coro in asyncio.as_completed(tasks):
        result = await coro
        job.completed += 1
        
        if result.status == DBStatus.SUCCESS:
            job.successful += 1
        elif result.status == DBStatus.SKIPPED:
            job.skipped += 1
        else:
            job.failed += 1
            job.errors.append({"database": result.database, "error": result.error})
        
        # Error threshold circuit breaker
        if job.total > 0:
            error_pct = (job.failed / job.total) * 100
            if error_pct > settings.error_threshold_percent and job.completed > 10:
                job.stop_requested = True
                log.warning("error_threshold_exceeded", pct=error_pct)

    job.status = JobStatus.COMPLETED if not job.stop_requested else JobStatus.STOPPED
    if job.failed > 0 and job.successful == 0:
        job.status = JobStatus.FAILED
    
    return job


async def stream_job_progress(job_id: str) -> AsyncIterator[dict]:
    """Yield job progress updates for SSE streaming."""
    while True:
        job = get_job(job_id)
        if not job:
            yield {"error": "Job not found"}
            break
        
        elapsed = time.time() - job.started_at if job.started_at else 0
        rate = job.completed / elapsed if elapsed > 0 else 0
        remaining = job.total - job.completed
        eta = remaining / rate if rate > 0 else 0

        yield {
            "job_id": job.job_id,
            "status": job.status,
            "total": job.total,
            "completed": job.completed,
            "successful": job.successful,
            "failed": job.failed,
            "skipped": job.skipped,
            "rate": f"{rate:.1f} db/s",
            "eta_seconds": int(eta)
        }
        
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.STOPPED):
            break
        
        await asyncio.sleep(0.5)
