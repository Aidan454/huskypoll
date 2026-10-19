"""let event_log links clear when a course or user is deleted

Revision ID: 7d7350be1874
Revises: 2c3b479f4768
Create Date: 2026-10-07 16:30:56.392678

"""
from collections.abc import Sequence

from alembic import op

# The SQL is copied here (not imported) so this migration never changes
# when triggers.py is edited later.
# Old trigger blocked every UPDATE, which also blocked the database's own
# ON DELETE SET NULL clean-up - so courses and users could not be deleted.
OLD_TRIGGER = """CREATE TRIGGER trg_event_log_no_update
BEFORE UPDATE ON event_log
BEGIN
    SELECT RAISE(ABORT, 'event_log is append-only');
END"""

NEW_TRIGGER = """CREATE TRIGGER trg_event_log_no_update
BEFORE UPDATE ON event_log
WHEN NEW.id IS NOT OLD.id
  OR NEW.occurred_at IS NOT OLD.occurred_at
  OR NEW.event_type IS NOT OLD.event_type
  OR NEW.ip_address IS NOT OLD.ip_address
  OR NEW.details_json IS NOT OLD.details_json
  OR (NEW.user_id IS NOT OLD.user_id AND NEW.user_id IS NOT NULL)
  OR (NEW.course_id IS NOT OLD.course_id AND NEW.course_id IS NOT NULL)
  OR (NEW.poll_id IS NOT OLD.poll_id AND NEW.poll_id IS NOT NULL)
BEGIN
    SELECT RAISE(ABORT, 'event_log is append-only');
END"""

# revision identifiers, used by Alembic.
revision: str = '7d7350be1874'
down_revision: str | Sequence[str] | None = '2c3b479f4768'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_event_log_no_update")
    op.execute(NEW_TRIGGER)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_event_log_no_update")
    op.execute(OLD_TRIGGER)
