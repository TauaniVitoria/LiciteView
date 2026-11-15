"""add detalhes do calculo a analise_viabilidade

Revision ID: 005
Revises: 004
Create Date: 2026-10-05

Guarda na análise os detalhes que antes só existiam na resposta da API (quantidade
considerada e sua origem, rota do frete e avisos), para que a tela mostre o mesmo
resultado ao ser recarregada.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')


def upgrade() -> None:
    op.add_column('analise_viabilidade', sa.Column('quantidade_considerada', sa.Integer(), nullable=True))
    op.add_column('analise_viabilidade', sa.Column('quantidade_origem', sa.String(20), nullable=True))
    op.add_column('analise_viabilidade', sa.Column('uf_origem', sa.String(2), nullable=True))
    op.add_column('analise_viabilidade', sa.Column('uf_destino', sa.String(2), nullable=True))
    op.add_column('analise_viabilidade', sa.Column('avisos', _JSON, nullable=True))


def downgrade() -> None:
    for coluna in ('avisos', 'uf_destino', 'uf_origem', 'quantidade_origem', 'quantidade_considerada'):
        op.drop_column('analise_viabilidade', coluna)
