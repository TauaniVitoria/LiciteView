# LiciteView

Plataforma web para avaliar oportunidades em licitações públicas brasileiras. O sistema busca editais no PNCP, gera um resumo do edital por IA, responde perguntas sobre o documento e calcula se vale a pena participar com um produto do fornecedor.

Projeto da disciplina Tecnologias e Programação Integrada — Ciências da Computação, Unisagrado (Bauru, 2026).

## Componentes

| Pasta | O que é | Como rodar |
| --- | --- | --- |
| [`licitacoes-ws/`](licitacoes-ws/) | Backend: API FastAPI e worker Celery | [README do backend](licitacoes-ws/README.md) |
| [`liciteview-angular/`](liciteview-angular/) | Frontend: aplicação Angular 17 | [README do frontend](liciteview-angular/README.md) |

Para rodar localmente, siga primeiro o README do backend e depois o do frontend.

## Documentação

| Documento | Conteúdo |
| --- | --- |
| [`docs/documentacao-tecnica.md`](docs/documentacao-tecnica.md) | Documentação técnica atual: arquitetura, pipeline de IA, API, modelo de dados, manual do usuário e limitações |
| [`docs/documentacao-tecnica.pdf`](docs/documentacao-tecnica.pdf) | A mesma documentação, em PDF (23 páginas), gerada a partir do arquivo acima |
| [`CORRECOES.md`](CORRECOES.md) | Correções de outubro de 2026: o que foi feito, por quê e como foi verificado |
| [`RELATORIO-ANALISE.md`](RELATORIO-ANALISE.md) | Análise do sistema antes dessas correções |
| [`documentacao-liciteview.pdf`](documentacao-liciteview.pdf) | Versão anterior da documentação técnica (maio de 2026), mantida para referência |

## Serviços externos

O sistema depende de Redis (fila), Qdrant (banco vetorial), Groq (modelo de linguagem) e, opcionalmente, Cohere (reordenação da busca). Todos têm plano gratuito. O plano gratuito da Groq limita o uso diário e comporta poucas dezenas de processamentos e perguntas por dia.
