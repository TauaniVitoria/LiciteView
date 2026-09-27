"""add produto logistica fields

Revision ID: 001
Revises:
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('produto', sa.Column('impostos', sa.Numeric(5, 2), server_default='0', nullable=False))
    op.add_column('produto', sa.Column('cep', sa.String(9), nullable=True))
    op.add_column('produto', sa.Column('uf', sa.String(2), nullable=True))
    op.add_column('produto', sa.Column('capacidade_mensal', sa.Integer(), nullable=True))
    # Tornar preco_venda e peso_kg opcionais (eram NOT NULL antes)
    op.alter_column('produto', 'preco_venda', nullable=True)
    op.alter_column('produto', 'peso_kg', nullable=True)


def downgrade() -> None:
    op.drop_column('produto', 'capacidade_mensal')
    op.drop_column('produto', 'uf')
    op.drop_column('produto', 'cep')
    op.drop_column('produto', 'impostos')
    op.alter_column('produto', 'preco_venda', nullable=False)
    op.alter_column('produto', 'peso_kg', nullable=False)
