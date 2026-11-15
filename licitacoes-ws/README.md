# licitacoes-ws — Backend LiciteView

API REST em **FastAPI (Python)** para processamento de editais de licitação, chat com o edital e análise de viabilidade financeira.

Documentação técnica completa: [`../docs/documentacao-tecnica.md`](../docs/documentacao-tecnica.md).

---

## Pré-requisitos

| Ferramenta | Versão |
| --- | --- |
| Python | 3.10 |

Além do Python, o backend usa quatro serviços externos. Todos têm plano gratuito:

| Serviço | Para quê | Obrigatório |
| --- | --- | --- |
| Redis | Fila do Celery | Sim |
| Qdrant | Banco vetorial | Sim |
| Groq | Modelo de linguagem | Sim |
| Cohere | Reordenação dos trechos na busca | Não |

O banco relacional pode ser PostgreSQL ou, em desenvolvimento, um arquivo SQLite local.

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

> O ambiente virtual depende do sistema operacional. Não copie a pasta `.venv` de outra
> máquina: apague-a e crie de novo.

---

## Variáveis de ambiente

```bash
cp .env.example .env
```

Preencha o `.env` com as suas credenciais. O `.env.example` traz todas as variáveis comentadas. Pontos que costumam causar erro:

- **`REDIS_URL` tem prioridade** sobre `REDIS_HOST` e `REDIS_PASSWORD`. Se as três estiverem definidas, só a primeira vale.
- **`ALLOWED_ORIGINS`** precisa conter o endereço exato do frontend, com a porta. Se o Angular subir em outra porta, o navegador recebe erro de CORS (`OPTIONS ... 400`).
- **`DATABASE_URL`** ausente faz o backend usar `sqlite:///./database.db`.
- Alterações no `.env` exigem reiniciar o backend. O `--reload` só observa arquivos `.py`.

---

## Criar o banco de dados

**Banco novo (vazio)** — SQLite ou PostgreSQL:

```bash
# PostgreSQL: crie o banco antes
psql -U postgres -c "CREATE DATABASE licitiview;"

# Cria as tabelas, registra o banco no Alembic e carrega a Tabela de Frete ANTT
python criar_banco.py
```

**Banco que já existe** — para aplicar mudanças de estrutura:

```bash
alembic upgrade head
```

> `alembic upgrade head` não funciona em banco vazio: as migrations partem de um banco
> que já tem as tabelas. Para banco vazio, use sempre o `criar_banco.py`.
>
> Se a Tabela de Frete ANTT estiver vazia em um banco existente, rode `python seed_antt.py`.
> Sem ela, a análise de viabilidade responde com erro.

---

## Rodando o projeto

### Opção 1 — Tudo junto (recomendado para desenvolvimento)

Com `START_CELERY_WORKER=true` (padrão), o worker Celery sobe junto com a API:

```bash
uvicorn main:app --reload --port 8000
```

### Opção 2 — API e worker em terminais separados

```bash
# Terminal 1 — API (com START_CELERY_WORKER=false no .env)
uvicorn main:app --reload --port 8000

# Terminal 2 — worker, que processa os editais
celery -A worker.celery_app worker --pool=solo --loglevel=info
```

### Opção 3 — Docker Compose

```bash
docker-compose up --build
```

A API fica em <http://localhost:8000> e a documentação interativa (Swagger) em <http://localhost:8000/docs>.

Na primeira vez que um edital é processado, o modelo de embeddings (cerca de 90 MB) é baixado.

---

## Scripts de manutenção

| Script | O que faz |
| --- | --- |
| `python criar_banco.py` | Cria o banco do zero e o registra no Alembic |
| `python seed_antt.py` | Carrega a Tabela de Frete ANTT; não duplica |
| `python vincular_editais_existentes.py` | Liga usuários a editais processados antes da tabela `usuario_edital`; pode ser repetido |
| `python avaliar_rag.py` | Avalia o chat com um edital simulado |

---

## Estrutura do projeto

```text
licitacoes-ws/
├── main.py             # Aplicação FastAPI, CORS, tratador de erros, worker em desenvolvimento
├── config.py           # Variáveis de ambiente e hash de senha
├── database.py         # Conexão e sessão SQLAlchemy
├── dependencies.py     # Autenticação das rotas
├── rate_limit.py       # Limite de requisições (login e cadastro)
├── models.py           # 13 modelos ORM (tabelas do banco)
├── schemas.py          # Schemas Pydantic (requisição e resposta)
├── arquivos.py         # Identifica o formato dos arquivos de edital (PDF, ZIP, Word...)
├── worker.py           # Instância do Celery
├── tasks.py            # Tarefa de processamento do edital
├── routes/
│   ├── auth_routes.py      # Cadastro, login, /auth/me
│   ├── cliente_routes.py   # Licitações, editais, chat, viabilidade, produtos, notificações
│   └── admin_routes.py     # Reservado (sem rotas)
├── rag/
│   └── edital_rag.py   # Extração do PDF, trechos, busca híbrida, resumo e chat
├── alembic/            # Migrations (001 a 006)
├── criar_banco.py, seed_antt.py, vincular_editais_existentes.py, avaliar_rag.py
├── script.sql          # Esquema inicial do PostgreSQL e dados da tabela ANTT
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Solução de problemas

**`OPTIONS /auth/register 400 Bad Request` no log, e o cadastro não funciona**
→ É CORS. O endereço do frontend, com a porta, não está em `ALLOWED_ORIGINS`. Corrija o `.env` e reinicie o backend.

**"Serviço de processamento indisponível" ao abrir um edital**
→ O backend não conseguiu falar com o Redis. Confira `REDIS_URL` (lembre que ela tem prioridade sobre `REDIS_HOST`).

**O edital fica em "Processando" e nada acontece**
→ O worker não está rodando ou não está conectado ao mesmo Redis da API. No modo "tudo junto", o log mostra `celery@... ready` logo após iniciar.

**"O arquivo publicado no PNCP não é um PDF"**
→ O órgão publicou o edital em outro formato. Converta para PDF e envie pelo botão "Enviar PDF do Edital".

**"O limite de uso da IA foi atingido"**
→ A cota da Groq acabou (por minuto ou por dia). Aguarde e tente de novo.

**"Tabela de frete ANTT não carregada no banco"**
→ Rode `python seed_antt.py`.

**`alembic upgrade head` falha com "no such table" ou "relation does not exist"**
→ O banco está vazio. Use `python criar_banco.py`.

**Erro com colunas inexistentes depois de atualizar o código**
→ O banco está atrás do código. Rode `alembic upgrade head`.

**`pip install` falha em `psycopg2-binary`**
→ Linux: `sudo apt install libpq-dev python3-dev` antes de instalar.
