"""Carrega a Tabela de Frete ANTT (Portaria SUROC nº 3/2026) no banco configurado no .env.

Os valores são lidos do INSERT do script.sql, para existir uma única fonte dos coeficientes.
Funciona em SQLite e PostgreSQL e não duplica: se a tabela já tiver linhas, não faz nada.

Uso:  python seed_antt.py
"""
import os
import re
from datetime import date
from decimal import Decimal

from database import SessionLocal
from models import TabelaFreteANTT

SCRIPT_SQL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "script.sql")
EIXOS = ("eixos_2", "eixos_3", "eixos_4", "eixos_5", "eixos_6", "eixos_7", "eixos_9")
LINHA = re.compile(r"^\('([A-D])',\s*(\d+),\s*'([^']+)',\s*'(CCD|CC)',\s*'([^']+)',\s*(.+?)\)[,;]\s*$")


def _ler_linhas() -> list[dict]:
    linhas = []
    with open(SCRIPT_SQL, encoding="utf-8") as f:
        for bruto in f:
            m = LINHA.match(bruto.strip())
            if not m:
                continue
            origem, cod, nome, coef, unidade, valores = m.groups()
            numeros = [v.strip() for v in valores.split(",")]
            if len(numeros) != len(EIXOS):
                raise ValueError(f"Linha inesperada no script.sql: {bruto.strip()}")
            linha = {
                "tabela_origem": origem,
                "tipo_carga_cod": int(cod),
                "tipo_carga_nome": nome,
                "coeficiente": coef,
                "unidade": unidade,
            }
            for eixo, v in zip(EIXOS, numeros):
                linha[eixo] = None if v.upper() == "NULL" else Decimal(v)
            linhas.append(linha)
    return linhas


def main() -> None:
    linhas = _ler_linhas()
    if not linhas:
        raise SystemExit("Nenhuma linha da tabela ANTT encontrada no script.sql.")

    with SessionLocal() as session:
        existentes = session.query(TabelaFreteANTT).count()
        if existentes:
            print(f"Tabela ANTT já possui {existentes} linhas — nada a fazer.")
            return
        for linha in linhas:
            session.add(TabelaFreteANTT(
                versao_portaria="SUROC-3-2026",
                data_vigencia=date(2026, 3, 13),
                ativo=True,
                **linha,
            ))
        session.commit()
        print(f"Tabela ANTT carregada: {len(linhas)} linhas.")


if __name__ == "__main__":
    main()
