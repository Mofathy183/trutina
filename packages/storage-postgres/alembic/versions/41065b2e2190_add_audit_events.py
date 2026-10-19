"""add audit_events

Revision ID: 41065b2e2190
Revises: 373da73ec0bb
Create Date: 2026-10-19 21:00:07.216842

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '41065b2e2190'
down_revision: Union[str, Sequence[str], None] = '373da73ec0bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('audit_events',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('entity', sa.Text(), nullable=False),
    sa.Column('entity_key', sa.Text(), nullable=False),
    sa.Column('action', sa.Text(), nullable=False),
    sa.Column('actor', sa.Text(), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("action IN ('create', 'update', 'delete')", name=op.f('ck_audit_events_action')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_events'))
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('audit_events')
