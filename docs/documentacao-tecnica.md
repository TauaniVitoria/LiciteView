# LiciteView — Documentação Técnica

**Plataforma Inteligente de Avaliação de Oportunidades em Licitações Públicas**

Centro Universitário Sagrado Coração — Unisagrado · Curso de Ciências da Computação<br>
Disciplina: Tecnologias e Programação Integrada · Orientador: Prof. Victor Hugo Braguim Canto<br>
Autores: Guilherme Jardim, Jhuliani Cristina Santos, Tauani Vitória · Bauru, 2026

**Revisão de 05/10/2026.** Substitui a versão anterior (`documentacao-liciteview.pdf`, maio de 2026).

> **Estado descrito neste documento.** Esta revisão descreve o código do repositório após as correções de outubro de 2026, que ainda não foram publicadas: o ambiente de produção continua executando a versão anterior. O banco de dados de produção já recebeu as mudanças de estrutura (migrations até `006`). A seção 7 reproduz a infraestrutura de produção da versão anterior, que não foi alterada nem reverificada nesta revisão.

---

## Resumo

O LiciteView é uma plataforma web para avaliar oportunidades em licitações públicas brasileiras. O sistema busca editais no Portal Nacional de Contratações Públicas (PNCP), baixa o documento em PDF, processa-o em segundo plano com um pipeline de Recuperação Aumentada por Geração (RAG) e entrega três resultados: um resumo estruturado em cinco blocos, um chat em linguagem natural fundamentado no edital e uma análise de viabilidade financeira para um produto do fornecedor.

A solução é composta por um frontend em Angular, um backend em FastAPI com processamento assíncrono via Celery e serviços de nuvem para banco relacional (PostgreSQL), armazenamento vetorial (Qdrant) e fila de mensagens (Redis). A recuperação de trechos combina busca vetorial e busca por palavras, com reordenação. A análise de viabilidade compara o preço de venda do produto com o valor estimado do item no edital e estima custos de produção, impostos e frete pela tabela da ANTT.

**Palavras-chave:** licitações públicas; inteligência artificial; RAG; busca híbrida; FastAPI; Angular; Celery; PNCP; análise de viabilidade.

---

## 1. Introdução

### 1.1 Contexto

O mercado de compras públicas no Brasil movimenta centenas de bilhões de reais por ano. Segundo dados do PNCP, até o final de 2025 haviam sido registradas mais de 1,4 milhão de contratações, totalizando cerca de R$ 3 trilhões em valor estimado. Milhares de licitações são abertas diariamente em todo o território nacional.

### 1.2 Problema

Para participar de uma licitação, uma empresa precisa localizar licitações relevantes entre milhares de publicações diárias, ler editais que frequentemente passam de cem páginas, interpretar requisitos técnicos e jurídicos, estimar custos de produção, impostos e logística e avaliar se a operação é financeiramente viável. Esse processo é majoritariamente manual. Pequenas e médias empresas, que não têm equipes dedicadas, perdem oportunidades por falta de agilidade.

### 1.3 Objetivos

Desenvolver uma plataforma web que automatize as etapas mais custosas da análise de licitações, entregando:

- **Busca de editais** no PNCP com filtros por modalidade, UF, esfera, poder e status;
- **Resumo automático** do edital em cinco blocos temáticos gerado por IA;
- **Chat** com o edital em linguagem natural, fundamentado no documento original, com indicação da página;
- **Análise de viabilidade** financeira cruzando o item do edital com o produto e o preço do fornecedor;
- **Notificações** quando o processamento é concluído ou falha.

### 1.4 Público-alvo

Pequenas e médias empresas fornecedoras de produtos que participam ou desejam participar do mercado público, em especial vendedores responsáveis pela prospecção e analistas comerciais.

---

## 2. Arquitetura do Sistema

### 2.1 Visão geral

```text
                    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
                    │  Cohere API  │    │ Portal PNCP  │    │   Groq API   │
                    │   (rerank)   │    │ (API pública)│    │    (LLM)     │
                    └──────▲───────┘    └──────▲───────┘    └──────▲───────┘
                           │                   │                   │
┌──────────────┐  HTTPS  ┌─┴───────────────────┴───────────────────┴─┐      ┌──────────────┐
│   Frontend   ├────────►│              Backend API (FastAPI)         ├─────►│  PostgreSQL  │
│   Angular    │  JSON   └───────────────┬───────────────────────────┘      │ (relacional) │
└──────────────┘                         │ enfileira                         └──────▲───────┘
                                  ┌──────▼───────┐                                  │
                                  │    Redis     │                                  │
                                  │    (fila)    │                                  │
                                  └──────┬───────┘                                  │
                                         │ consome                                  │
                                  ┌──────▼───────┐    indexa e consulta      ┌──────┴───────┐
                                  │ Celery Worker├──────────────────────────►│    Qdrant    │
                                  └──────────────┘                           │  (vetorial)  │
                                                                             └──────────────┘
```

A arquitetura tem cinco camadas:

1. **Apresentação:** frontend Angular.
2. **Aplicação:** API FastAPI, que centraliza regras de negócio, autenticação e orquestração.
3. **Serviços assíncronos:** Celery com Redis, para o processamento dos editais em segundo plano.
4. **Pipeline de IA:** PyMuPDF, fastembed, Qdrant, Cohere Rerank e Groq.
5. **Dados:** PostgreSQL (em desenvolvimento local, SQLite) e Qdrant.

O worker usa o PNCP (download do edital), o Qdrant e a Groq. A API também usa o Qdrant, a Cohere e a Groq, porque o chat e a análise de viabilidade são respondidos na própria requisição.

### 2.2 Frontend

- Pesquisa de licitações com filtros;
- Tela do edital com três abas: Resumo, Viabilidade e Chat;
- Cadastro, edição e exclusão de produtos;
- Histórico dos editais abertos pelo usuário, com status do resumo e classificação de viabilidade;
- Notificações com contador no sino.

### 2.3 Backend

- Autenticação por JWT, com limite de tentativas no login e no cadastro;
- Consulta de licitações na API do PNCP;
- Criação de tarefas assíncronas para processar editais;
- Controle de acesso por usuário aos editais;
- Chat e análise de viabilidade.

### 2.4 Fluxo de processamento do edital

1. O usuário abre a tela de um edital. O frontend envia `POST /cliente/editais/processar`.
2. O backend cria o edital, se ainda não existir, e **vincula o usuário a ele**.
3. Conforme o estado do edital:
   - **já processado:** o resumo é devolvido de imediato, sem novo processamento;
   - **em processamento:** nenhuma tarefa nova é criada;
   - **com erro:** o erro é exibido, e só há novo processamento se o usuário clicar em "Tentar novamente";
   - **novo:** uma tarefa é enfileirada no Redis.
4. O worker lista os arquivos da compra no PNCP e tenta até 5 deles, dando preferência aos que parecem ser o edital em PDF. Só é aceito conteúdo que seja de fato um PDF, ou um ZIP com um PDF dentro.
5. O PDF é gravado no banco, na coluna `pdf_conteudo`.
6. O texto é extraído por página com PyMuPDF (fallback: pypdf).
7. O texto é dividido em trechos de 200 palavras, com sobreposição de 40, e cada trecho registra as páginas de origem.
8. Os trechos são vetorizados e indexados em uma coleção do Qdrant, recriada a cada processamento.
9. Para cada um dos cinco blocos, os trechos mais relevantes são recuperados e enviados ao modelo de linguagem, que devolve um JSON.
10. O resumo é gravado, o edital passa a `PROCESSADO` e o usuário recebe uma notificação.

**Tratamento de falhas.** Falhas passageiras (rede, IA indisponível) são repetidas até 2 vezes, com 30 segundos de intervalo; o edital permanece `PROCESSANDO` entre as tentativas. Falhas definitivas (arquivo que não é PDF, PDF sem texto, PDF corrompido) não são repetidas. Em ambos os casos, o edital só passa a `ERRO`, com notificação, ao final. A mensagem exibida é escrita para o usuário e indica o que fazer.

A tela consulta o status a cada 8 segundos, por até 5 minutos.

### 2.5 Fluxo de consulta ao edital (chat)

1. A pergunta é convertida em vetor de 384 dimensões.
2. São reunidos candidatos de duas buscas: os 12 trechos mais próximos pela **busca vetorial** no Qdrant e os 12 mais relevantes pela **busca por palavras** (BM25), calculada em memória sobre os trechos do edital.
3. Os candidatos são reordenados pelo Cohere Rerank (`rerank-multilingual-v3.0`). Sem ele, vale a ordem intercalada das duas buscas.
4. Os trechos entram no contexto, em ordem, até o limite de 2.250 palavras.
5. O modelo de linguagem responde usando apenas esse contexto.
6. A resposta é devolvida com o início do trecho mais relevante e a página do edital de onde ele veio.

A seção 5.5 traz a medição que motivou a busca híbrida.

### 2.6 Fluxo de análise de viabilidade

A análise responde à pergunta: **vale a pena vender este produto, pelo preço do cadastro, neste edital?**

1. **Localização do item.** A busca híbrida recupera os trechos do edital relacionados ao produto, e o modelo de linguagem extrai a quantidade (*Q*) e o valor unitário estimado (*T*) do item correspondente.

2. **Quantidade.** Em ordem de prioridade: a informada pelo usuário; a do item encontrado; a quantidade geral citada no resumo; por fim, uma estimativa pelo valor total do edital dividido pelo preço do produto, com aviso. Sem nenhuma dessas fontes, a análise pede a quantidade ao usuário.

3. **Preço considerado.** Seja *P* o preço de venda do cadastro. O valor estimado do item é o máximo que o órgão aceita pagar:

   - se *P* ≤ *T*, usa-se *P*, e a análise informa quanto ele está abaixo do valor do edital;
   - se *P* > *T*, usa-se *T*, com aviso de que o preço do fornecedor está acima do máximo;
   - se *T* não for encontrado, usa-se *P*, com aviso.

   Se o produto não tiver preço cadastrado, ele é calculado pelo custo e pela margem mínima.

4. **Distância.** Se o resumo trouxer o CEP de entrega, a distância é calculada entre os CEPs de origem e de entrega pela fórmula de Haversine, com coordenadas obtidas na BrasilAPI (fallback: AwesomeAPI). Caso contrário, usa-se a distância entre as capitais das UFs de origem e de destino. Em ambos os casos aplica-se o fator de tortuosidade rodoviária de 1,3:

   *d*<sub>rodoviária</sub> = *d* × 1,3

   A UF de destino vem, em ordem: do CEP de entrega; da UF do órgão comprador informada pelo PNCP; da UF citada no resumo; de uma sigla escrita como "Cidade/UF" no nome do órgão. Não há valor padrão: se nenhuma fonte servir, a análise recebe um aviso.

5. **Frete.** Pela Tabela da ANTT (Portaria SUROC nº 3/2026), carga geral, veículo de 2 eixos, com capacidade considerada de 5 toneladas:

   *C*<sub>frete</sub> = *n*<sub>viagens</sub> × (*CC* + *CCD* × *d*<sub>rodoviária</sub>), com *n*<sub>viagens</sub> = ⌈peso total em toneladas ÷ 5⌉

   *CC* é o custo fixo de carga e descarga e *CCD* o custo de deslocamento por quilômetro. Se a tabela não estiver carregada no banco, a análise é recusada com uma mensagem de orientação, em vez de calcular com frete zero.

6. **Margem.** Com *C<sub>p</sub>* o custo unitário e *I* a carga tributária:

   Receita = *Q* × preço considerado<br>
   Custo operacional = *Q* × *C<sub>p</sub>* × (1 + *I*)<br>
   Custo total = Custo operacional + *C*<sub>frete</sub><br>
   *M* = (Receita − Custo total) ÷ Receita

   O valor gravado é limitado ao intervalo [−9,9999; 9,9999], por causa do tipo da coluna no banco.

7. **Classificação.**

   - **Vale a pena:** *M* ≥ margem mínima do produto, com quantidade e valor do item vindos do edital ou do usuário;
   - **Atenção:** 0 ≤ *M* < margem mínima, **ou** o resultado depende de estimativa (produto não localizado, valor do item não encontrado, UF de entrega desconhecida);
   - **Não recomendado:** *M* < 0.

O resultado traz uma justificativa em texto com todos os valores usados e sua origem, além dos avisos. Há uma análise por edital, produto e usuário; reanalisar atualiza a existente.

---

## 3. Tecnologias Utilizadas

### 3.1 Frontend

| Tecnologia | Versão | Finalidade |
| --- | --- | --- |
| Angular | 17 | Framework SPA com componentes standalone e signals |
| TypeScript | 5.4 | Tipagem estática |
| PrimeNG | 17 | Biblioteca de componentes de interface |
| RxJS | 7.8 | Fluxos assíncronos |

### 3.2 Backend

| Tecnologia | Versão | Finalidade |
| --- | --- | --- |
| Python | 3.10 | Linguagem principal |
| FastAPI | 0.136 | Framework web |
| SQLAlchemy | 2.0 | ORM |
| Alembic | 1.18 | Migrations |
| Celery | 5.6 | Processamento assíncrono |
| Redis (cliente) | 7.4 | Fila de mensagens do Celery |
| Pydantic | 2.13 | Validação de dados |
| python-jose | 3.5 | Geração e validação de JWT |
| bcrypt | 5.0 | Hash de senhas |
| httpx / requests | 0.28 / 2.33 | Clientes HTTP |
| slowapi | 0.1.9 | Limite de requisições |

### 3.3 Inteligência artificial e RAG

| Tecnologia | Versão | Finalidade |
| --- | --- | --- |
| fastembed | 0.7 | Geração de embeddings com ONNX, sem PyTorch |
| all-MiniLM-L6-v2 | — | Modelo de embeddings, 384 dimensões |
| Qdrant Client | 1.17 | Banco vetorial |
| BM25 (implementação própria) | — | Busca por palavras sobre os trechos do edital |
| Cohere Rerank | `rerank-multilingual-v3.0` | Reordenação dos candidatos |
| Groq SDK | 1.2 | Cliente do modelo de linguagem `openai/gpt-oss-20b` |
| PyMuPDF | 1.24 | Extração de texto de PDFs |
| pypdf | 6.11 | Fallback de extração |

### 3.4 Infraestrutura

| Serviço | Plano | Uso |
| --- | --- | --- |
| Google Cloud Platform | e2-medium (2 vCPU, 4 GB) | Hospedagem da API e do worker |
| Render | Gratuito | Hospedagem do frontend |
| Neon PostgreSQL | Gratuito | Banco relacional |
| Qdrant Cloud | Gratuito | Banco vetorial |
| Redis Cloud | Gratuito | Fila do Celery |
| Groq API | Gratuito (200.000 tokens por dia) | Modelo de linguagem |
| Cohere API | Não verificado nesta revisão | Reordenação |
| DuckDNS / Let's Encrypt | Gratuito | DNS dinâmico e certificado TLS |

---

## 4. Modelagem de Dados

### 4.1 Entidades

Todas as entidades têm chave primária UUID.

| Entidade | Descrição |
| --- | --- |
| `usuario` | Fornecedor cadastrado: autenticação, razão social, CNPJ, CEP e UF |
| `produto` | Item ofertado pelo usuário: custo, preço de venda, margem mínima, impostos, peso e origem |
| `edital` | Documento da licitação obtido no PNCP: metadados, UF e município do órgão, PDF e status |
| `usuario_edital` | Vínculo entre usuário e edital; define o que cada usuário pode ver e consultar |
| `chunk_edital` | Trecho de texto do edital, com as páginas de origem |
| `resumo_edital` | Resumo em JSON com os cinco blocos |
| `variavel_viabilidade` | Variável extraída do resumo para uso nos cálculos |
| `analise_viabilidade` | Resultado da análise para um edital, produto e usuário |
| `pergunta_edital` | Pergunta feita no chat, com resposta, trecho e página de origem |
| `tabela_frete_antt` | Coeficientes de frete da ANTT por tipo de carga e número de eixos |
| `notificacao` | Aviso de conclusão ou erro de processamento |
| `execucao_processo` | Registro de cada tentativa de processamento |
| `secao_edital` | Reservada para a divisão do edital em seções; não utilizada |

### 4.2 Relacionamentos

- Um **usuário** tem muitos produtos, análises, perguntas e notificações.
- Usuários e **editais** se relacionam em muitos-para-muitos por `usuario_edital`. O processamento de um edital é compartilhado: se vários fornecedores abrirem o mesmo edital, ele é processado uma única vez.
- Um **edital** tem muitos trechos, resumos, variáveis, análises, perguntas e execuções.
- Uma **análise** pertence a um edital, um produto e um usuário.

### 4.3 Enumerações

| Enumeração | Valores |
| --- | --- |
| `StatusProcessamento` | PENDENTE, PROCESSANDO, PROCESSADO, ERRO |
| `ClassificacaoViabilidade` | VALE_A_PENA, ATENCAO, NAO_RECOMENDADO |
| `StatusPergunta` | PENDENTE, RESPONDIDA, ERRO |
| `PerfilUsuario` | ADMIN, FORNECEDOR |
| `EmbeddingStatus` | PENDENTE, GERADO, ERRO |
| `StatusExecucao` | PENDENTE, EXECUTANDO, SUCESSO, ERRO, RETRY |
| `TipoProcesso` | INGESTAO_PDF, SEGMENTACAO, EMBEDDING, RESUMO, EXTRACAO_VARIAVEIS, ANALISE_VIABILIDADE, RESPOSTA_PERGUNTA |

A origem da quantidade usada em uma análise é gravada como texto: `INFORMADA`, `ITEM_EDITAL`, `RESUMO_EDITAL` ou `ESTIMADA`.

### 4.4 Migrations

| Revisão | Conteúdo |
| --- | --- |
| `001` | Campos logísticos e de impostos em `produto` |
| `002` | Tabela `notificacao` |
| `90d70d3e4eee` | Coluna `pdf_conteudo` em `edital` |
| `003` | Colunas `uf` e `municipio` em `edital` |
| `004` | Tabela `usuario_edital` |
| `005` | Detalhes do cálculo em `analise_viabilidade` (quantidade, origem, rota, avisos) |
| `006` | Preço considerado e valor unitário do edital em `analise_viabilidade` |

As migrations partem de um banco que já tem as tabelas iniciais. Para criar um banco do zero, usa-se o script `criar_banco.py` (seção 7.5).

---

## 5. Pipeline de Inteligência Artificial

### 5.1 Obtenção e validação do arquivo

Os órgãos publicam editais no PNCP em vários formatos: PDF, Word, planilhas e ZIP. O sistema lê apenas PDF com texto. O módulo `arquivos.py` reconhece um PDF pelo conteúdo, não pela extensão, extrai o PDF de dentro de um ZIP e descreve o formato encontrado para compor a mensagem de erro. A mesma verificação é aplicada ao upload manual, limitado a 50 MB.

### 5.2 Extração de texto

O PyMuPDF analisa os blocos de texto de cada página e identifica títulos pelo tamanho da fonte: acima de 14 pontos vira título (`#`), acima de 12 vira subtítulo (`##`). O texto é mantido separado por página. PDFs sem texto selecionável, como digitalizações, são recusados com mensagem específica, pois o sistema não faz reconhecimento óptico de caracteres.

### 5.3 Divisão em trechos

O texto é dividido em trechos de **200 palavras** com sobreposição de **40**, e cada trecho registra a página inicial e a final. Editais processados antes desta revisão têm trechos de 450 palavras e não registram a página; eles continuam funcionando sem reprocessamento.

### 5.4 Embeddings e indexação

Os trechos são vetorizados com `sentence-transformers/all-MiniLM-L6-v2` pela biblioteca fastembed, que usa ONNX Runtime em CPU. Os vetores, de 384 dimensões, são gravados no Qdrant em uma coleção por edital, `edital_{uuid com underscores}`, com similaridade de cosseno.

O modelo foi treinado em inglês e lê cerca de 256 tokens por texto. Por isso ele não é a única fonte de candidatos na busca.

### 5.5 Recuperação híbrida

Os candidatos vêm de duas buscas, 12 de cada:

- **vetorial**, por similaridade no Qdrant;
- **por palavras**, com o algoritmo BM25 sobre os trechos do edital, sem acentos e sem palavras muito comuns.

Os candidatos são reordenados pelo Cohere Rerank e entram no contexto até um limite de palavras: 2.250 no chat e 1.000 em cada bloco do resumo.

**Medição.** A decisão se baseou em 14 perguntas factuais sobre um edital real de 44 páginas, cada uma com a expressão que deveria constar no contexto recuperado:

| Configuração | Resposta presente no contexto |
| --- | --- |
| Somente vetorial (15 candidatos, reordena 5) | 9 de 14 |
| Híbrida (12 + 12), mesmo modelo de embeddings | 14 de 14 |
| Híbrida (12 + 12), modelo de embeddings multilíngue | 14 de 14 |

A troca do modelo de embeddings não alterou o resultado e exigiria reprocessar todos os editais, então não foi adotada. **Limitação da medição:** um único edital, com perguntas escritas por quem conhecia o texto, o que favorece a busca por palavras.

### 5.6 Geração do resumo em cinco blocos

| Bloco | Tema | Campos |
| --- | --- | --- |
| `bloco1_visao_geral` | Visão geral | objeto, órgão, modalidade, critério de julgamento, número do edital |
| `bloco2_prazos` | Prazos e execução | prazo de entrega, vigência do contrato, local de entrega, data de abertura |
| `bloco3_documentacao` | Documentação | documentos de habilitação, regularidade fiscal, qualificação técnica |
| `bloco4_requisitos_tecnicos` | Requisitos técnicos | resumo das especificações, certificações exigidas, exigência de amostra, outros requisitos |
| `bloco5_riscos` | Riscos e penalidades | multas, sanções, cláusulas críticas, pontos de atenção |

Para cada bloco, o prompt descreve cada campo, com o tipo esperado e o que deve conter. Cada bloco é tentado até 3 vezes. Se um bloco não puder ser gerado, o processamento falha, em vez de gravar um resumo incompleto. Entre os blocos há uma pausa de 1,2 segundo, por causa do limite de tokens por minuto do provedor.

### 5.7 Modelo de linguagem

- **Modelo:** `openai/gpt-oss-20b`, via Groq;
- **Temperatura:** 0;
- **Esforço de raciocínio:** baixo (`reasoning_effort="low"`). O modelo raciocina antes de responder; com o esforço padrão, ele por vezes consumia toda a saída raciocinando e devolvia a resposta vazia;
- **Formato:** `json_object` no resumo e nas extrações; texto corrido no chat;
- **Limite do plano gratuito:** 200.000 tokens por dia. Processar um edital consome da ordem de 10.000 a 15.000 tokens, e uma pergunta no chat, cerca de 4.000.

O modelo `llama-3.1-8b-instant`, usado na versão anterior, deixou de estar disponível na Groq.

---

## 6. Referência da API

A API segue o padrão REST e responde em JSON. Todas as rotas, exceto as de cadastro, login e `/health`, exigem o cabeçalho `Authorization: Bearer {token}`.

### 6.1 Autenticação

| Método | Rota | Corpo | Resposta |
| --- | --- | --- | --- |
| POST | `/auth/register` | nome, email, senha, razao_social, cnpj, cep, cidade, uf | Usuário criado (201) |
| POST | `/auth/login` | email, senha | `access_token` |
| POST | `/auth/login-form` | formulário OAuth2 (usado pelo Swagger) | `access_token` |
| GET | `/auth/me` | — | Usuário autenticado |

Limites por IP: 20 tentativas de login e 10 cadastros por minuto; acima disso, a resposta é 429. O CNPJ deve ter o formato `00.000.000/0000-00` e o CEP, `00000-000`.

### 6.2 Licitações

| Método | Rota | Parâmetros | Resposta |
| --- | --- | --- | --- |
| GET | `/cliente/licitacoes/buscar` | q, status, ufs, modalidades, tipos, esferas, poderes, pagina, tam_pagina, ordenacao | Resultado da busca do PNCP |
| GET | `/cliente/licitacoes/{id_pncp}` | — | Dados da compra, consultados no PNCP |

### 6.3 Editais

| Método | Rota | Corpo | Resposta |
| --- | --- | --- | --- |
| POST | `/cliente/editais/processar` | id_pncp, orgao, objeto, titulo, modalidade, valor_estimado, url_origem, uf, municipio, reprocessar | `edital_id` e `status` (202) |
| GET | `/cliente/editais/{id}/status` | — | Status, resumo, total de trechos, mensagem de erro |
| GET | `/cliente/editais/historico` | — | Editais do usuário, com status e classificação de viabilidade |
| POST | `/cliente/editais/upload-pdf` | arquivo PDF | Cria um edital a partir do arquivo (202) |
| POST | `/cliente/editais/{id}/upload-pdf` | arquivo PDF | Envia o PDF de um edital existente (202) |
| POST | `/cliente/editais/{id}/perguntar` | pergunta | resposta, trecho_fonte, pagina_fonte, pagina_fonte_final |
| GET | `/cliente/editais/{id}/perguntas` | — | Perguntas respondidas do usuário sobre o edital |
| GET | `/cliente/editais/{id}/analise` | — | Análise mais recente do usuário para o edital, ou vazio |

O campo `reprocessar` só é enviado pelo botão "Tentar novamente". As rotas que recebem o `id` de um edital respondem 404 se o edital não estiver vinculado ao usuário.

### 6.4 Produtos

| Método | Rota | Resposta |
| --- | --- | --- |
| GET | `/cliente/produtos` | Produtos ativos do usuário |
| POST | `/cliente/produtos` | Produto criado (201) |
| PUT | `/cliente/produtos/{id}` | Produto atualizado |
| DELETE | `/cliente/produtos/{id}` | 204; a exclusão é lógica |

### 6.5 Análise de viabilidade

| Método | Rota | Corpo | Resposta |
| --- | --- | --- | --- |
| POST | `/cliente/analise` | edital_id, produto_id, quantidade (opcional) | Análise calculada |
| DELETE | `/cliente/analise/{edital_id}/{produto_id}` | — | 204 |

A resposta inclui classificação, margem, receita, custos, distância, quantidade considerada e sua origem, preço considerado, valor unitário do edital, UFs de origem e destino, avisos e justificativa.

### 6.6 Notificações e infraestrutura

| Método | Rota | Resposta |
| --- | --- | --- |
| GET | `/cliente/notificacoes` | Últimas 30 notificações |
| PATCH | `/cliente/notificacoes/{id}/lida` | 204 |
| PATCH | `/cliente/notificacoes/marcar-todas-lidas` | 204 |
| GET | `/health` | `{"status": "ok"}` |

---

## 7. Infraestrutura e Deploy

### 7.1 Arquitetura de containers

O sistema é implantado com dois containers Docker em uma VM do Google Cloud:

- **`api`:** servidor FastAPI, limitado a 700 MB de RAM e 0,5 vCPU;
- **`worker`:** worker Celery, limitado a 1.800 MB de RAM e 1,0 vCPU.

A separação isola falhas: se o worker travar em um processamento pesado, a API continua respondendo.

**Observação.** O chat e a análise de viabilidade carregam o modelo de embeddings no processo da API, na primeira chamada. A versão anterior deste documento afirmava que a API não executava operações de aprendizado de máquina. O consumo de memória da API com o modelo carregado não foi medido contra o limite de 700 MB.

### 7.2 Dockerfile

A imagem parte de `python:3.10-slim`, instala as dependências e pré-carrega o modelo de embeddings durante o build, para evitar o download na primeira execução. O `.dockerignore` e o `Dockerfile` excluem o ambiente virtual e os bancos SQLite locais.

### 7.3 Variáveis de ambiente

| Variável | Descrição |
| --- | --- |
| `DATABASE_URL` | Conexão com o banco. PostgreSQL em produção; sem ela, usa SQLite local |
| `SECRET_KEY` | Chave de assinatura do JWT |
| `ALGORITHM` | Algoritmo do JWT (HS256) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Validade do token |
| `REDIS_URL` | URL completa do Redis. **Tem prioridade** sobre as duas seguintes |
| `REDIS_HOST`, `REDIS_PASSWORD` | Alternativa: host:porta e senha |
| `QDRANT_HOST`, `QDRANT_API_KEY` | Endereço e chave do Qdrant |
| `GROQ_API_KEY` | Chave da Groq |
| `COHERE_API_KEY` | Chave da Cohere. Opcional: sem ela, não há reordenação |
| `ALLOWED_ORIGINS` | Origens aceitas pelo CORS, separadas por vírgula |
| `START_CELERY_WORKER` | `true` em desenvolvimento, para subir o worker junto com a API; `false` no Docker |

### 7.4 Nginx e TLS

O Nginx atua como proxy reverso na VM, com certificado do Let's Encrypt, redirecionamento de HTTP para HTTPS e timeout de 120 segundos.

**Atenção.** O limite de tentativas de login identifica o cliente pelo cabeçalho `X-Forwarded-For`, definido pelo Nginx. O `docker-compose.yml` publica a porta 8000 da API; ela deve ficar acessível apenas pelo Nginx, pois quem a acessa diretamente pode forjar esse cabeçalho.

### 7.5 Como executar localmente

```bash
# 1. Backend
cd licitacoes-ws
cp .env.example .env            # preencher com as credenciais
python -m venv .venv            # Python 3.10
.venv\Scripts\activate          # Windows; em Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# 2. Banco de dados
python criar_banco.py           # banco novo: cria as tabelas e carrega a tabela ANTT
alembic upgrade head            # banco existente: aplica mudanças de estrutura

# 3. Iniciar o backend (sobe o worker Celery junto)
uvicorn main:app --reload --port 8000

# 4. Frontend, em outro terminal
cd liciteview-angular
npm install
npm start
```

O ambiente virtual e a pasta `node_modules` dependem do sistema operacional e não devem ser copiados de uma máquina para outra. Se a porta 4200 estiver ocupada, use `npm start -- --port 4201` e inclua a nova origem em `ALLOWED_ORIGINS`.

### 7.6 Scripts de manutenção

| Script | Uso |
| --- | --- |
| `criar_banco.py` | Cria o banco do zero (SQLite ou PostgreSQL) e o registra no Alembic |
| `seed_antt.py` | Carrega a Tabela de Frete ANTT; não duplica se já houver dados |
| `vincular_editais_existentes.py` | Cria os vínculos usuário–edital de editais processados antes da tabela `usuario_edital`; pode ser repetido |
| `avaliar_rag.py` | Avaliação do chat com um edital simulado |

---

## 8. Testes

O frontend tem arquivos de teste unitário (`.spec.ts`) para cinco serviços, mas o projeto **não tem executor de testes configurado**: não há Karma, Jest nem script `npm test`. O backend não tem testes automatizados no repositório.

Na revisão de outubro de 2026, as correções foram verificadas de três formas, registradas em `CORRECOES.md`:

1. **Testes do backend em banco descartável**, executando as rotas e a tarefa do worker de verdade, com as chamadas de IA simuladas quando o objetivo era a lógica;
2. **Medições com os serviços reais** (Qdrant, Cohere e Groq), para a busca e a geração do resumo;
3. **Testes pela interface**, com um navegador controlado por script percorrendo os fluxos de cadastro, busca, processamento, resumo, viabilidade, chat, histórico e produtos.

Esses roteiros foram executados durante a revisão e não fazem parte do repositório. Configurar o executor de testes do frontend e criar uma suíte para o backend está no roadmap.

---

## 9. Decisões Técnicas

### 9.1 Embeddings locais com fastembed

O modelo `all-MiniLM-L6-v2` roda localmente, sem custo por token e sem depender de cotas externas. Com ONNX, ocupa cerca de 90 MB, contra cerca de 1,5 GB de uma instalação com PyTorch. A contrapartida é a qualidade limitada em português, compensada pela busca híbrida (9.7).

### 9.2 Chamadas diretas à Groq, sem LangChain

O pipeline é linear, e a camada de abstração do LangChain dificultaria a depuração.

### 9.3 PyMuPDF em vez de Docling

O Docling trazia o PyTorch como dependência, o que levava a imagem Docker a 6 GB e travava a VM de 4 GB durante o build.

### 9.4 PDFs no banco relacional

Os PDFs são gravados na coluna `pdf_conteudo`, o que evita novos downloads e mantém o documento disponível para reprocessamento. A coluna é carregada sob demanda: consultas comuns de edital não trazem o arquivo. A migração para armazenamento de objetos está no roadmap.

### 9.5 Processamento compartilhado, acesso individual

O mesmo edital do PNCP pode interessar a vários fornecedores. Por isso o edital é processado uma única vez, e o que é individual é o acesso, controlado pela tabela `usuario_edital`. Um dono único por edital obrigaria cada fornecedor a reprocessar o mesmo documento.

### 9.6 Frete por distância geodésica e tabela da ANTT

O cálculo usa APIs públicas de CEP e a fórmula de Haversine, sem depender de serviços pagos de rotas. Na falta do CEP de entrega, usa a distância entre capitais.

### 9.7 Busca híbrida em vez de trocar o modelo de embeddings

A medição da seção 5.5 mostrou que a busca vetorial sozinha deixava de recuperar a resposta em 5 de 14 perguntas, e que acrescentar a busca por palavras resolvia as 14. A troca por um modelo multilíngue foi testada e não trouxe ganho adicional. A busca por palavras não exigiu dependências novas nem reprocessamento.

### 9.8 Viabilidade baseada no preço do fornecedor

A versão anterior pedia que o usuário digitasse um valor estimado e o usava como receita. A análise passou a partir do preço de venda cadastrado, comparado ao valor estimado do item no edital, que é o que o fornecedor precisa saber.

### 9.9 Resultados que dependem de estimativa não são "Vale a pena"

Quando o produto não é encontrado no edital, a análise ainda calcula uma margem, mas ela reflete apenas o cadastro do produto. Nesses casos a classificação é limitada a "Atenção", com aviso.

### 9.10 Falhas visíveis em vez de resultados incompletos

Um bloco do resumo que não pôde ser gerado, um frete que não pôde ser calculado ou uma resposta vazia do chat são tratados como falha, com mensagem ao usuário. A versão anterior gravava o resultado incompleto como se fosse válido.

### 9.11 Limitação da margem no banco

A coluna `margem_estimada` é `NUMERIC(5, 4)`. Em cenários de prejuízo severo, o valor calculado excedia esse intervalo e causava erro. O valor gravado é limitado a ±9,9999.

---

## 10. Resultados

### 10.1 Funcionalidades

| Funcionalidade | Situação | Observação |
| --- | --- | --- |
| Autenticação (cadastro, login, JWT) | Implementada | Com limite de tentativas |
| Busca de licitações no PNCP | Implementada | Resultados ordenados por data |
| Cadastro, edição e exclusão de produtos | Implementada | |
| Processamento assíncrono | Implementada | Celery, Redis e polling |
| Download do edital no PNCP | Implementada | Somente PDF; outros formatos geram mensagem de orientação |
| Upload manual de PDF | Implementada | Oferecido quando o download automático falha |
| Resumo em cinco blocos | Implementada | |
| Chat sobre o edital | Implementada | Busca híbrida; cita a página |
| Histórico do chat | Implementada | Sem memória entre perguntas |
| Análise de viabilidade | Implementada | Baseada no preço do produto e no item do edital |
| Histórico de editais | Implementada | Por usuário, com classificação de viabilidade |
| Notificações | Implementada | Atualização a cada 30 segundos |
| Controle de acesso por usuário | Implementada | |
| Leitura de editais em Word ou digitalizados | Não implementada | |
| Testes automatizados | Não implementada | Ver seção 8 |

### 10.2 Medições

Medidas em ambiente de desenvolvimento (Windows, serviços de nuvem), em outubro de 2026:

| Métrica | Valor |
| --- | --- |
| Processamento de um edital de 44 páginas | 26 segundos (medido antes da redução do tamanho dos trechos) |
| Processamento de um edital de 51 páginas | 83 segundos, 167 trechos |
| Campos do resumo preenchidos (edital de 51 páginas) | 18 de 20 |
| Recuperação da resposta no chat (14 perguntas) | 14 de 14 |
| Resposta do chat | 2 a 4 segundos |
| Análise de viabilidade | cerca de 10 segundos |

Os tempos de processamento vêm de execuções únicas e variam com a carga do provedor de IA. As métricas de produção da versão anterior (tempo de build, tamanho da imagem, uso de memória dos containers) não foram refeitas.

---

## 11. Manual do Usuário

### 11.1 Cadastro e login

1. Na tela de login, clique em **Criar conta**.
2. Na primeira etapa, informe nome, e-mail e senha de pelo menos 8 caracteres, e aceite os termos.
3. Na segunda etapa, informe razão social, CNPJ, CEP, UF e município.
4. Clique em **Criar conta**. O sistema faz o login e abre a tela de pesquisa.

### 11.2 Busca de licitações

1. Digite um termo, por exemplo *armário de aço*.
2. Se quiser, abra os filtros: UF, status, modalidade, esfera, poder.
3. Clique em **Pesquisar**.
4. Clique em um resultado para abrir o edital.

A busca é feita pelo PNCP e os resultados vêm ordenados por data; nem todo resultado contém o termo no edital.

### 11.3 Processamento do edital

Ao abrir um edital pela primeira vez, o processamento começa automaticamente. A tela mostra as etapas e se atualiza sozinha; costuma levar de 30 segundos a 2 minutos. É possível navegar para outras telas: ao final, chega uma notificação.

**Se o processamento falhar**, a tela mostra o motivo. O caso mais comum é o órgão ter publicado o edital em um formato que não é PDF. Nesse caso, baixe o edital no PNCP, converta para PDF e use o botão **Enviar PDF do Edital**. O botão **Tentar novamente** repete o processamento automático.

### 11.4 Resumo

A aba **Resumo IA** mostra cinco blocos: visão geral, prazos e execução, documentação exigida, requisitos técnicos, e riscos e penalidades. O resumo é gerado por IA: confira no edital as informações que forem decisivas.

### 11.5 Análise de viabilidade

Antes, cadastre o produto em **Meus Produtos**, com custo e preço de venda.

1. Na aba **Viabilidade**, selecione o produto.
2. O campo **Quantidade** é opcional. Deixe em branco para usar a quantidade do edital.
3. Clique em **Analisar viabilidade**.

O resultado mostra:

- a **classificação**: Vale a pena, Atenção ou Não recomendado;
- **seu preço**, o **valor estimado no edital** e o **preço considerado**;
- a **margem estimada**, o **custo operacional** e o **custo logístico**, com a rota e a distância;
- os **avisos**, quando o resultado depende de alguma estimativa;
- **como o resultado foi calculado**, com todos os valores usados.

Se o sistema não encontrar o produto no edital, ele avisa e pede a quantidade. O botão **Reanalisar** refaz a análise, por exemplo depois de alterar o produto.

### 11.6 Chat

Na aba **Chat do edital**, digite a pergunta e pressione Enter. A resposta traz a página do edital de onde veio a informação. Exemplos:

- *Quais são os documentos exigidos para habilitação?*
- *Qual a multa por atraso na entrega?*
- *Qual a quantidade e o valor unitário do armário de aço?*

As perguntas anteriores ficam salvas e reaparecem ao reabrir o edital. Cada pergunta é respondida isoladamente, sem considerar as anteriores.

### 11.7 Produtos

Em **Meus Produtos**, use **Novo produto** para cadastrar, o ícone de lápis para editar e o de lixeira para excluir. Campos:

- **Nome** e **descrição**: use o nome como ele aparece nos editais, pois ele é usado para localizar o item;
- **Custo de produção** e **preço de venda esperado**;
- **Carga tributária** e **margem mínima aceitável**;
- **Peso por unidade**, **CEP** e **UF de origem**, usados no frete.

### 11.8 Notificações e histórico

O sino mostra os avisos de processamento concluído ou com erro; clicar em um aviso abre o edital. O **Histórico** lista os editais que você abriu, com o status do resumo e a classificação da última análise.

---

## 12. Limitações Conhecidas

- **Somente PDF com texto.** Editais em Word ou digitalizados precisam ser convertidos e enviados manualmente.
- **Limite diário da IA.** O plano gratuito da Groq comporta poucas dezenas de processamentos e perguntas por dia. Atingido o limite, o sistema informa e pede para aguardar.
- **Frete aproximado.** Sem o CEP de entrega, a distância é entre capitais. O cálculo assume sempre carga geral em veículo de 2 eixos.
- **Imposto sobre o custo.** A carga tributária é aplicada sobre o custo de produção, não sobre a receita.
- **Extração por IA.** A quantidade e o valor do item são extraídos por modelo de linguagem e podem estar errados em tabelas com layout incomum. A tela mostra os valores usados, para conferência.
- **Qualidade da busca vetorial em português.** O modelo de embeddings é treinado em inglês; perguntas com vocabulário muito diferente do edital podem ter resultado pior.
- **Editais antigos sem página.** Editais processados antes desta revisão não informam a página no chat.
- **Sessão.** O token dura 24 horas na configuração usada (`ACCESS_TOKEN_EXPIRE_MINUTES=1440`) e não pode ser revogado. Não há verificação de e-mail no cadastro.

---

## 13. Próximos Passos

1. **Testes automatizados:** configurar o executor de testes do frontend e criar a suíte do backend, começando pelo cálculo de viabilidade.
2. **Avaliação contínua da busca:** incorporar o conjunto de perguntas ao `avaliar_rag.py`, ampliá-lo para mais editais e executá-lo em CI.
3. **Outros formatos:** leitura de editais em `.docx` e reconhecimento óptico de documentos digitalizados.
4. **Embeddings multilíngues de recuperação**, se a avaliação com mais editais mostrar falhas da busca híbrida.
5. **Frete porta a porta:** integrar um serviço de rotas e considerar o tipo de carga do produto.
6. **Fórmula tributária:** aplicar os impostos sobre a receita.
7. **Armazenamento de PDFs** em serviço de objetos.
8. **Alertas proativos:** monitorar o PNCP e avisar sobre novas licitações compatíveis com os produtos cadastrados.
9. **Análise com vários produtos** em uma mesma licitação.
10. **Sessão e cadastro:** renovação e revogação de token, e verificação de e-mail.

---

## 14. Referências

1. BRASIL. Portal Nacional de Contratações Públicas (PNCP). Disponível em: https://www.pncp.gov.br.
2. BRASIL. Lei nº 14.133, de 1º de abril de 2021 — Nova Lei de Licitações e Contratos Administrativos.
3. ANTT. Tabela de Custos Operacionais (TACO) — Portaria SUROC nº 3/2026. Agência Nacional de Transportes Terrestres, 2026.
4. LEWIS, Patrick et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *Advances in Neural Information Processing Systems*, v. 33, 2020.
5. ROBERTSON, Stephen; ZARAGOZA, Hugo. The Probabilistic Relevance Framework: BM25 and Beyond. *Foundations and Trends in Information Retrieval*, v. 3, n. 4, 2009.
6. ES, Shahul et al. RAGAS: Automated Evaluation of Retrieval Augmented Generation. arXiv:2309.15217, 2023.
7. FASTAPI. Documentação oficial. Disponível em: https://fastapi.tiangolo.com.
8. ANGULAR. Documentação oficial. Disponível em: https://angular.io.
9. QDRANT. Vector Search Engine. Disponível em: https://qdrant.tech.
10. FASTEMBED. Documentação. Disponível em: https://qdrant.github.io/fastembed.
11. GROQ. API documentation. Disponível em: https://console.groq.com/docs.
12. COHERE. Rerank. Disponível em: https://docs.cohere.com.
13. CELERY. Distributed Task Queue. Disponível em: https://docs.celeryq.dev.
14. PYMUPDF. Documentation. Disponível em: https://pymupdf.readthedocs.io.

---

## Apêndice A — Estrutura de diretórios

```text
licitacoes-ws/                       # repositório
├── README.md
├── RELATORIO-ANALISE.md             # análise do sistema antes das correções de outubro de 2026
├── CORRECOES.md                     # o que foi corrigido, por quê e como foi verificado
├── documentacao-liciteview.pdf      # versão anterior desta documentação
├── docs/
│   ├── documentacao-tecnica.md      # este documento
│   └── documentacao-tecnica.pdf     # o mesmo conteúdo, em PDF
├── licitacoes-ws/                   # backend FastAPI
│   ├── main.py                      # aplicação, CORS, tratador de erros, worker em desenvolvimento
│   ├── config.py                    # variáveis de ambiente e hash de senha
│   ├── database.py                  # conexão e sessão
│   ├── dependencies.py              # autenticação das rotas
│   ├── rate_limit.py                # limite de requisições
│   ├── models.py                    # modelos SQLAlchemy
│   ├── schemas.py                   # schemas Pydantic
│   ├── arquivos.py                  # identificação de formato dos arquivos de edital
│   ├── worker.py                    # instância do Celery
│   ├── tasks.py                     # tarefa de processamento do edital
│   ├── rag/edital_rag.py            # extração, trechos, busca híbrida, resumo, chat
│   ├── routes/                      # auth_routes, cliente_routes, admin_routes
│   ├── alembic/versions/            # migrations 001 a 006
│   ├── criar_banco.py               # criação do banco do zero
│   ├── seed_antt.py                 # carga da tabela ANTT
│   ├── vincular_editais_existentes.py
│   ├── avaliar_rag.py
│   ├── script.sql                   # esquema inicial do PostgreSQL e dados da tabela ANTT
│   ├── Dockerfile, docker-compose.yml, requirements.txt, .env.example
└── liciteview-angular/              # frontend Angular
    └── src/app/
        ├── core/                    # models, services, interceptors
        ├── features/                # auth, pesquisa, edital, produtos, historico
        └── layout/                  # estrutura da aplicação e notificações
```

## Apêndice B — Histórico de revisões

| Data | Mudanças |
| --- | --- |
| Maio de 2026 | Primeira versão |
| 05/10/2026 | Revisão completa após a análise e as correções de outubro. Mudanças de comportamento: busca híbrida; trechos de 200 palavras com página; novo modelo de linguagem; análise de viabilidade baseada no preço do produto; controle de acesso por usuário; validação do formato dos arquivos; persistência da análise e do chat na tela; edição de produto. Detalhes em `CORRECOES.md` |
