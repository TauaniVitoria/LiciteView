"""add tabela usuario_edital

Revision ID: 004
Revises: 003
Create Date: 2026-10-05

Liga cada usuário aos editais que ele abriu ou enviou. O processamento do edital
continua compartilhado; o que passa a ser individual é o acesso (histórico, status,
chat, viabilidade e upload).

Os vínculos dos editais já existentes são criados pelo script
vincular_editais_existentes.py, que pode ser executado mais de uma vez.
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'usuario_edital',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column('usuario_id', sa.Uuid(as_uuid=True),
                  sa.ForeignKey('usuario.id', ondelete='CASCADE'), nullable=False),
        sa.Column('edital_id', sa.Uuid(as_uuid=True),
                  sa.ForeignKey('edital.id', ondelete='CASCADE'), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('usuario_id', 'edital_id', name='uq_usuario_edital'),
    )
    op.create_index('ix_usuario_edital_usuario_id', 'usuario_edital', ['usuario_id'])


def downgrade() -> None:
    op.drop_index('ix_usuario_edital_usuario_id', 'usuario_edital')
    op.drop_table('usuario_edital')
