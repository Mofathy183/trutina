"""add login_attempts

Revision ID: 4794a1756a02
Revises: 41065b2e2190
Create Date: 2026-10-23 07:33:00.712141

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4794a1756a02'
down_revision: Union[str, Sequence[str], None] = '41065b2e2190'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('login_attempts',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('ip', sa.Text(), nullable=False),
    sa.Column('email_key', sa.Text(), nullable=False),
    sa.Column('attempted_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_login_attempts'))
    )
    op.create_index('ix_login_attempts_attempted_at', 'login_attempts', ['attempted_at'], unique=False)
    op.create_index('ix_login_attempts_ip_email_key_attempted_at', 'login_attempts', ['ip', 'email_key', 'attempted_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_login_attempts_ip_email_key_attempted_at', table_name='login_attempts')
    op.drop_index('ix_login_attempts_attempted_at', table_name='login_attempts')
    op.drop_table('login_attempts')
