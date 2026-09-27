"""add pdf content to edital

Revision ID: 90d70d3e4eee
Revises: 002
Create Date: 2026-05-22 19:41:57.216245

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '90d70d3e4eee'
down_revision: Union[str, Sequence[str], None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('edital', sa.Column('pdf_conteudo', sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('edital', 'pdf_conteudo')
