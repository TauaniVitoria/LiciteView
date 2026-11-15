"""add uf e municipio ao edital

Revision ID: 003
Revises: 90d70d3e4eee
Create Date: 2026-10-05

Guarda no edital a UF e o município do órgão comprador (vindos do PNCP),
usados como destino do frete na análise de viabilidade.
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '90d70d3e4eee'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('edital', sa.Column('uf', sa.String(2), nullable=True))
    op.add_column('edital', sa.Column('municipio', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('edital', 'municipio')
    op.drop_column('edital', 'uf')
