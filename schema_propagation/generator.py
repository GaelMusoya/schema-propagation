import hashlib
import json
from datetime import datetime
from io import StringIO
from pathlib import Path
import importlib.util

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
import sqlalchemy as sa
from sqlalchemy.schema import CreateTable, CreateIndex, CreateColumn
from sqlalchemy.dialects import postgresql

from .config import get_settings


def generate_sql(description: str, target_revision: str = "head") -> dict:
    """Extract SQL from Alembic migrations using offline mode."""
    settings = get_settings()
    versions_dir = Path(settings.sql_versions_dir)
    versions_dir.mkdir(exist_ok=True)

    config = Config(settings.alembic_config_path)
    script = ScriptDirectory.from_config(config)
    head = script.get_current_head()

    # Capture SQL in offline mode
    upgrade_sql = StringIO()
    downgrade_sql = StringIO()

    config.output_buffer = upgrade_sql
    command.upgrade(config, target_revision, sql=True)

    config.output_buffer = downgrade_sql
    from_rev = head or target_revision
    command.downgrade(config, f"{from_rev}:base", sql=True)

    upgrade_content = upgrade_sql.getvalue()
    downgrade_content = downgrade_sql.getvalue()

    # Generate version metadata
    version_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    checksum = hashlib.sha256(upgrade_content.encode()).hexdigest()[:16]

    version_path = versions_dir / version_id
    version_path.mkdir(exist_ok=True)

    # Write files
    (version_path / "upgrade.sql").write_text(upgrade_content)
    (version_path / "downgrade.sql").write_text(downgrade_content)
    
    metadata = {
        "version_id": version_id,
        "revision_id": head,
        "checksum": checksum,
        "description": description,
        "created_at": datetime.now().isoformat()
    }
    (version_path / "metadata.json").write_text(json.dumps(metadata, indent=2))

    return {
        "success": True,
        "version_id": version_id,
        "checksum": checksum,
        "files": {
            "upgrade": str(version_path / "upgrade.sql"),
            "downgrade": str(version_path / "downgrade.sql")
        }
    }


def get_version(version_id: str) -> dict | None:
    """Get version metadata and SQL content."""
    settings = get_settings()
    version_path = Path(settings.sql_versions_dir) / version_id
    
    if not version_path.exists():
        return None
    
    metadata = json.loads((version_path / "metadata.json").read_text())
    metadata["upgrade_sql"] = (version_path / "upgrade.sql").read_text()
    return metadata


def list_versions() -> list[dict]:
    """List all generated SQL versions."""
    settings = get_settings()
    versions_dir = Path(settings.sql_versions_dir)
    
    if not versions_dir.exists():
        return []
    
    versions = []
    for path in sorted(versions_dir.iterdir(), reverse=True):
        if (path / "metadata.json").exists():
            versions.append(json.loads((path / "metadata.json").read_text()))
    return versions


def _load_previous_manifest(versions_dir: Path, specific_version: str | None = None) -> dict | None:
    """Load manifest from a previous models-generated version."""
    candidates = []
    if specific_version:
        candidates.append(versions_dir / specific_version)
    else:
        candidates.extend(sorted(versions_dir.iterdir(), reverse=True) if versions_dir.exists() else [])

    for candidate in candidates:
        meta_path = candidate / "metadata.json"
        if meta_path.exists():
            data = json.loads(meta_path.read_text())
            if data.get("revision_id") == "models" and "manifest" in data:
                return data["manifest"]
    return None


def generate_sql_from_models(
    path: str,
    base_symbol: str = "Base",
    description: str = "models import",
    prune_missing: bool = False,
    previous_version_id: str | None = None
) -> dict:
    """
    Dynamically load a SQLAlchemy model file and emit Postgres DDL as SQL.
    No database connection is required.
    If prune_missing is True, compare against the latest models manifest (or provided previous_version_id)
    and emit DROP statements for removed tables/columns.
    """
    settings = get_settings()
    versions_dir = Path(settings.sql_versions_dir)
    versions_dir.mkdir(exist_ok=True)

    module_path = Path(path)
    if not module_path.exists():
        raise FileNotFoundError(f"Model file not found: {module_path}")

    spec = importlib.util.spec_from_file_location("dynamic_models", module_path)
    if not spec or not spec.loader:
        raise ImportError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, base_symbol):
        raise ValueError(f"{base_symbol} not found in module {module_path}")
    base = getattr(module, base_symbol)
    metadata = getattr(base, "metadata", None)
    if metadata is None:
        raise ValueError("No metadata found on provided Base")
    if not metadata.tables:
        raise ValueError("Metadata has no tables to generate SQL for")

    dialect = postgresql.dialect()
    statements: list[str] = []
    alter_statements: list[str] = []
    drop_statements: list[str] = []
    enum_types: dict[str, sa.Enum] = {}
    format_table = dialect.identifier_preparer.format_table

    # Manifest for diffing and metadata
    manifest: dict[str, dict] = {"tables": {}}

    previous_manifest = _load_previous_manifest(versions_dir, previous_version_id) if prune_missing else None
    previous_tables = set(previous_manifest.get("tables", {})) if previous_manifest else set()

    for table in metadata.sorted_tables:
        # Collect enum types so we can create them before tables
        for col in table.columns:
            if isinstance(col.type, sa.Enum):
                name = col.type.name or f"{table.name}_{col.name}_enum"
                enum_types[name] = col.type
                col.type.name = name

        statements.append(str(CreateTable(table, if_not_exists=True).compile(dialect=dialect)).rstrip() + ";")

        table_ident = format_table(table)
        for col in table.columns:
            col_sql = str(CreateColumn(col).compile(dialect=dialect)).rstrip()
            alter_statements.append(f"ALTER TABLE {table_ident} ADD COLUMN IF NOT EXISTS {col_sql};")

        for idx in table.indexes:
            statements.append(str(CreateIndex(idx, if_not_exists=True).compile(dialect=dialect)).rstrip() + ";")

        manifest["tables"][table.name] = {
            "columns": [c.name for c in table.columns]
        }

    if previous_manifest:
        current_tables = set(manifest["tables"].keys())
        removed_tables = previous_tables - current_tables
        for tbl in sorted(removed_tables):
            drop_statements.append(f'DROP TABLE IF EXISTS "{tbl}" CASCADE;')

        for tbl in sorted(current_tables & previous_tables):
            old_cols = set(previous_manifest["tables"].get(tbl, {}).get("columns", []))
            new_cols = set(manifest["tables"].get(tbl, {}).get("columns", []))
            removed_cols = old_cols - new_cols
            for col in sorted(removed_cols):
                drop_statements.append(f'ALTER TABLE IF EXISTS "{tbl}" DROP COLUMN IF EXISTS "{col}" CASCADE;')

    enum_sql = []
    for name, enum in enum_types.items():
        labels = ", ".join(f"'{v}'" for v in enum.enums)
        enum_sql.append(f"CREATE TYPE {name} AS ENUM ({labels});")

    upgrade_parts = ["BEGIN;"]
    if enum_sql:
        upgrade_parts.extend(enum_sql)
    if drop_statements:
        upgrade_parts.extend(drop_statements)
    upgrade_parts.extend(statements)
    upgrade_parts.extend(alter_statements)
    upgrade_parts.append("COMMIT;")
    upgrade_content = "\n\n".join(upgrade_parts) + "\n"
    downgrade_content = "-- Downgrade not implemented for model-generated SQL\n"

    version_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    checksum = hashlib.sha256(upgrade_content.encode()).hexdigest()[:16]

    version_path = versions_dir / version_id
    version_path.mkdir(exist_ok=True)

    (version_path / "upgrade.sql").write_text(upgrade_content)
    (version_path / "downgrade.sql").write_text(downgrade_content)

    metadata_json = {
        "version_id": version_id,
        "revision_id": "models",
        "checksum": checksum,
        "description": description,
        "created_at": datetime.now().isoformat(),
        "manifest": manifest
    }
    (version_path / "metadata.json").write_text(json.dumps(metadata_json, indent=2))

    return {
        "success": True,
        "version_id": version_id,
        "checksum": checksum,
        "upgrade_sql": upgrade_content,
        "files": {
            "upgrade": str(version_path / "upgrade.sql"),
            "downgrade": str(version_path / "downgrade.sql")
        }
    }
