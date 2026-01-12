import hashlib
import json
from datetime import datetime
from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from .config import get_settings


def generate_sql(description: str, target_revision: str = "head") -> dict:
    """Extract SQL from Alembic migrations using offline mode."""
    settings = get_settings()
    versions_dir = Path(settings.sql_versions_dir)
    versions_dir.mkdir(exist_ok=True)

    config = Config(settings.alembic_config_path)
    script = ScriptDirectory.from_config(config)

    # Capture SQL in offline mode
    upgrade_sql = StringIO()
    downgrade_sql = StringIO()

    config.output_buffer = upgrade_sql
    command.upgrade(config, target_revision, sql=True)

    config.output_buffer = downgrade_sql
    command.downgrade(config, "-1", sql=True)

    upgrade_content = upgrade_sql.getvalue()
    downgrade_content = downgrade_sql.getvalue()

    # Generate version metadata
    version_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    checksum = hashlib.sha256(upgrade_content.encode()).hexdigest()[:16]

    head = script.get_current_head()
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
