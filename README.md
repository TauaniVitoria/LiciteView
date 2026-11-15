# LiciteView

Plataforma SaaS para busca, análise inteligente (RAG) e cálculo de viabilidade financeira em licitações públicas brasileiras, integrada à API oficial do **PNCP** (Portal Nacional de Contratações Públicas).

---

## Principais Funcionalidades

- **Busca no PNCP:** Consulta de editais por palavra-chave, modalidade, UF, esfera, poder e status.
- **Resumo Estruturado por IA:** Processamento automático do PDF do edital em 5 blocos (Visão Geral, Prazos e Execução, Documentação Exigida, Requisitos Técnicos e Riscos/Penalidades).
- **Análise de Viabilidade e Logística:** Cruzamento determinístico do edital com o catálogo de produtos do fornecedor, calculando margem líquida, tributos e frete via **Tabela ANTT**.
- **Chat com o Edital (RAG Híbrido):** Perguntas e respostas em linguagem natural sobre o documento com busca semântica + textual (Qdrant + BM25) e indicação da página de origem.
- **Histórico e Notificações:** Acompanhamento centralizado dos editais analisados e alertas de conclusão de processamento.

## Como Executar Localmente

### 1. Backend (`licitacoes-ws`)

```bash
cd licitacoes-ws
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Configure suas chaves (DATABASE_URL, REDIS_URL, QDRANT e GROQ_API_KEY)
alembic upgrade head
python seed_antt.py

# Iniciar API e Worker Celery
uvicorn main:app --reload
celery -A tasks.celery_app worker --loglevel=info --pool=solo
```

### 2. Frontend (`liciteview-angular`)

```bash
cd liciteview-angular
npm install
npm start
```

Acesse a aplicação em `http://localhost:4200` (API e Swagger em `http://localhost:8000/docs`).
