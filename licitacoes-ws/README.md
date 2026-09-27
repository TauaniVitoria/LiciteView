# licitacoes-ws — Backend LicitiView

API REST em **FastAPI (Python)** para processamento de editais de licitação, análise de viabilidade financeira e RAG conversacional.

---

## Pré-requisitos

| Ferramenta | Versão mínima |
| --- | --- |
| Python | 3.10 |

Redis, PostgreSQL e Qdrant rodam na nuvem — as credenciais já estão no `.env`.

---

## Instalação

```bash
# 1. Entre na pasta do backend
cd licitacoes-ws

# 2. Crie e ative o ambiente virtual
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt
```

---

## Variáveis de Ambiente

```bash
cp .env.example .env
```

Edite o `.env`:

```env
# Banco de dados (PostgreSQL)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/licitiview

# JWT
SECRET_KEY=coloque-uma-string-longa-e-aleatoria-aqui
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Redis (broker do Celery)
REDIS_HOST=localhost:6379
REDIS_PASSWORD=

# Qdrant (banco vetorial para RAG)
QDRANT_HOST=http://localhost:6333
QDRANT_API_KEY=

# Groq (LLM para resumo e RAG)
GROQ_API_KEY=gsk_...

# CORS — URLs permitidas para chamar a API
ALLOWED_ORIGINS=http://localhost:4200

# Em desenvolvimento o worker Celery sobe junto com a API (padrão: true)
START_CELERY_WORKER=true
```

> Você precisa de uma chave da Groq para o processamento de editais funcionar.
> Crie uma gratuitamente em <https://console.groq.com>

---

## Criar o banco de dados

```bash
# Crie o banco no PostgreSQL
psql -U postgres -c "CREATE DATABASE licitiview;"

# Execute as migrações
alembic upgrade head
```

---

## Rodando o projeto

### Opção 1 — Tudo junto (recomendado para desenvolvimento)

Com `START_CELERY_WORKER=true` no `.env`, o worker Celery sobe automaticamente junto com a API:

```bash
uvicorn main:app --reload --port 8000
```

### Opção 2 — API e worker em terminais separados

**Terminal 1 — API:**

```bash
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Worker Celery** (processa os PDFs dos editais):

```bash
celery -A worker.celery_app worker --pool=solo --loglevel=info
```

### Opção 3 — Docker Compose

```bash
docker-compose up --build
```

---

A API estará disponível em <http://localhost:8000>

Documentação interativa (Swagger): <http://localhost:8000/docs>

---

## Estrutura do Projeto

```text
licitacoes-ws/
├── main.py             # Entrypoint FastAPI + lifespan Celery
├── config.py           # Configurações de auth e settings
├── database.py         # Sessão SQLAlchemy
├── models.py           # 12 modelos ORM (tabelas do banco)
├── schemas.py          # Schemas Pydantic (request/response)
├── tasks.py            # Tarefas assíncronas do Celery
├── worker.py           # Instância do Celery
├── dependencies.py     # Injeção de dependências FastAPI
├── routes/
│   ├── auth_routes.py      # Login, register, /auth/me
│   ├── cliente_routes.py   # Licitações, editais, análises, produtos
│   └── admin_routes.py     # Endpoints administrativos
├── rag/
│   ├── edital_rag.py   # Pipeline: PDF → chunks → embeddings → RAG → LLM
│   └── rag.py          # Utilitários de busca vetorial no Qdrant
├── alembic/            # Migrações do banco
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Solução de Problemas

**`pip install` falha em `psycopg2-binary`**
→ Linux: `sudo apt install libpq-dev python3-dev` antes de instalar.

**Erro de conexão com Redis**
→ Verifique se o Redis está rodando: `redis-cli ping` (deve retornar `PONG`).

**Tabelas não existem no banco**
→ Execute `alembic upgrade head` com o `.env` configurado corretamente.

**Worker não processa tarefas**
→ Confirme que `REDIS_HOST` está correto e que o worker foi iniciado. Verifique os logs no terminal do worker.
