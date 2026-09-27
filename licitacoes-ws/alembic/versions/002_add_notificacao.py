"""add tabela notificacao

Revision ID: 002
Revises: 001
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'notificacao',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('usuario_id', sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('usuario.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tipo', sa.String(50), nullable=False),
        sa.Column('titulo', sa.String(500), nullable=False),
        sa.Column('mensagem', sa.Text()),
        sa.Column('edital_id', sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('edital.id', ondelete='SET NULL'), nullable=True),
        sa.Column('referencia', sa.String(200)),
        sa.Column('lida', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('criada_em', sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_notificacao_usuario_id', 'notificacao', ['usuario_id'])


def downgrade() -> None:
    op.drop_index('ix_notificacao_usuario_id', 'notificacao')
    op.drop_table('notificacao')
