from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    db_endpoint: str = "localhost"
    db_port: int = 5432
    db_username: str = "postgres"
    db_password: str = "postgres"
    db_name: str = "postgres"
    pgbouncer_host: str = "pgbouncer"
    pgbouncer_port: int = 6432
    max_concurrent_connections: int = 100
    error_threshold_percent: float = 10.0
    max_retries: int = 3
    alembic_config_path: str = "alembic.ini"
    sql_versions_dir: str = "sql_versions"

    @property
    def direct_dsn(self) -> str:
        return f"postgresql://{self.db_username}:{self.db_password}@{self.db_endpoint}:{self.db_port}/{self.db_name}"

    @property
    def pgbouncer_dsn(self) -> str:
        return f"postgresql://{self.db_username}:{self.db_password}@{self.pgbouncer_host}:{self.pgbouncer_port}/{self.db_name}"

    def db_dsn(self, database: str, use_pgbouncer: bool = True) -> str:
        host = self.pgbouncer_host if use_pgbouncer else self.db_endpoint
        port = self.pgbouncer_port if use_pgbouncer else self.db_port
        return f"postgresql://{self.db_username}:{self.db_password}@{host}:{port}/{database}"

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()
