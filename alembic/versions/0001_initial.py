"""Initial empty revision placeholder."""

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

# Revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add migration operations here.
    pass


def downgrade() -> None:
    # Revert migration operations here.
    pass
