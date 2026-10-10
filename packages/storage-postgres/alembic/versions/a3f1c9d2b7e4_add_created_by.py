"""add created_by to journal_entries and postings

Revision ID: a3f1c9d2b7e4
Revises: 7e1b970f05a7
Create Date: 2026-10-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f1c9d2b7e4'
down_revision: Union[str, Sequence[str], None] = '7e1b970f05a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Both columns are nullable with no default, so PostgreSQL adds them as
    a metadata-only change: no table rewrite and no backfill. Existing
    rows stay null, which means "written before actor attribution".
    """
    op.add_column("journal_entries", sa.Column("created_by", sa.Text(), nullable=True))
    op.add_column("postings", sa.Column("created_by", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("postings", "created_by")
    op.drop_column("journal_entries", "created_by")
