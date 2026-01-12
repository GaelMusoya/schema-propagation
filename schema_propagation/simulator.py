import asyncio
import asyncpg
from .config import get_settings


async def create_test_databases(
    count: int,
    prefix: str = "cmp_",
    start_id: int = 1,
    template_db: str | None = None
) -> list[str]:
    """Create test databases for benchmarking."""
    settings = get_settings()
    semaphore = asyncio.Semaphore(20)
    created = []

    async def create_one(db_name: str) -> str | None:
        async with semaphore:
            conn = await asyncpg.connect(settings.direct_dsn)
            try:
                if template_db:
                    await conn.execute(f'CREATE DATABASE "{db_name}" TEMPLATE "{template_db}"')
                else:
                    await conn.execute(f'CREATE DATABASE "{db_name}"')
                return db_name
            except asyncpg.DuplicateDatabaseError:
                return db_name  # Already exists
            except Exception:
                return None
            finally:
                await conn.close()

    names = [f"{prefix}{start_id + i}" for i in range(count)]
    results = await asyncio.gather(*[create_one(n) for n in names])
    return [r for r in results if r]


async def cleanup_test_databases(databases: list[str]) -> int:
    """Remove test databases."""
    settings = get_settings()
    semaphore = asyncio.Semaphore(20)
    removed = 0

    async def drop_one(db_name: str) -> bool:
        async with semaphore:
            conn = await asyncpg.connect(settings.direct_dsn)
            try:
                # Terminate connections
                await conn.execute(f"""
                    SELECT pg_terminate_backend(pid) 
                    FROM pg_stat_activity 
                    WHERE datname = '{db_name}' AND pid <> pg_backend_pid()
                """)
                await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
                return True
            except Exception:
                return False
            finally:
                await conn.close()

    results = await asyncio.gather(*[drop_one(db) for db in databases])
    return sum(results)
