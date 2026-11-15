"""Limite de requisições por cliente (slowapi).

Fica em módulo próprio para que main.py e as rotas importem o mesmo objeto
sem importação circular.
"""
from slowapi import Limiter
from starlette.requests import Request


def ip_do_cliente(request: Request) -> str:
    """IP de quem fez a requisição.

    Em produção a API fica atrás do Nginx, então o endereço da conexão é sempre o do
    proxy; sem ler X-Forwarded-For, todos os usuários dividiriam o mesmo limite.
    O cabeçalho pode ser forjado por quem acessa a porta da API diretamente — por isso
    a porta 8000 não deve ficar exposta à internet (ver CORRECOES.md).
    """
    encaminhado = request.headers.get("x-forwarded-for")
    if encaminhado:
        return encaminhado.split(",")[0].strip()
    return request.client.host if request.client else "desconhecido"


limiter = Limiter(key_func=ip_do_cliente)

# Limites das rotas de autenticação (por IP)
LIMITE_LOGIN = "20/minute"
LIMITE_CADASTRO = "10/minute"
