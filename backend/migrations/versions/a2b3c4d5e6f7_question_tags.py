"""Add question tags without modifying existing poll content."""
import sqlalchemy as sa
from alembic import op

revision = "a2b3c4d5e6f7"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("questions", sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"))


def downgrade():
    with op.batch_alter_table("questions") as batch:
        batch.drop_column("tags")
