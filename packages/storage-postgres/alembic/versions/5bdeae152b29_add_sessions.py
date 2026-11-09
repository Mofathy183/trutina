"""add sessions

Revision ID: 5bdeae152b29
Revises: 4794a1756a02
Create Date: 2026-11-09 21:23:39.834653

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5bdeae152b29'
down_revision: Union[str, Sequence[str], None] = '4794a1756a02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('sessions',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('token_hash', sa.Text(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('client_kind', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('authenticated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('idle_expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('absolute_expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("client_kind IN ('api', 'cli')", name=op.f('ck_sessions_client_kind')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_sessions_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sessions')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_sessions_token_hash'))
    )
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_sessions_user_id', table_name='sessions')
    op.drop_table('sessions')