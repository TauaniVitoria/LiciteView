"""Cria o banco de dados do zero, em SQLite ou PostgreSQL.

As migrations do Alembic partem de um banco que já tem as tabelas (a primeira delas
é um ALTER TABLE), então `alembic upgrade head` falha em banco vazio. Este script
cobre esse caso:

  1. cria todas as tabelas a partir dos modelos (estrutura atual);
  2. marca o banco como atualizado no Alembic (`stamp head`), para que as próximas
     migrations funcionem normalmente;
  3. carrega a Tabela de Frete ANTT.

Só age em banco vazio. Se já existir alguma tabela do sistema, não altera nada e
orienta a usar `alembic upgrade head`.

Uso:  python criar_banco.py
"""
import os

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

import seed_antt
from database import engine
from models import Base


def main() -> None:
    existentes = set(inspect(engine).get_table_names())
    do_sistema = existentes & set(Base.metadata.tables)
    if do_sistema:
        raise SystemExit(
            f"O banco já tem {len(do_sistema)} tabelas do sistema. Nada foi alterado.\n"
            "Para atualizar um banco existente, use:  alembic upgrade head"
        )

    Base.metadata.create_all(engine)
    print(f"Tabelas criadas: {len(Base.metadata.tables)}")

    cfg = Config(os.path.join(os.path.dirname(os.path.abspath(__file__)), "alembic.ini"))
    command.stamp(cfg, "head")
    print("Banco marcado como atualizado no Alembic.")

    seed_antt.main()


if __name__ == "__main__":
    main()
