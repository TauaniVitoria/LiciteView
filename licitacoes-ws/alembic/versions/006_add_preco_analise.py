"""add preco de proposta e valor unitario do edital a analise_viabilidade

Revision ID: 006
Revises: 005
Create Date: 2026-10-05

A análise passou a comparar o preço de venda do produto com o valor unitário
estimado do item no edital (o máximo aceito pelo órgão). As duas colunas guardam
os valores usados nessa comparação.
"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('analise_viabilidade', sa.Column('preco_proposta', sa.Numeric(15, 4), nullable=True))
    op.add_column('analise_viabilidade', sa.Column('valor_unitario_edital', sa.Numeric(15, 4), nullable=True))


def downgrade() -> None:
    op.drop_column('analise_viabilidade', 'valor_unitario_edital')
    op.drop_column('analise_viabilidade', 'preco_proposta')
