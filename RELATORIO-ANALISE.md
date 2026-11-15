# LiciteView — Relatório de análise do repositório

Data da análise: 05/10/2026
Escopo: backend (`licitacoes-ws/`), frontend (`liciteview-angular/`) e comparação com `documentacao-liciteview.pdf`.

> **Atualização:** os 11 bugs da seção 1.1 foram tratados em 05/10/2026: dez corrigidos e o bug 11 atenuado. Os bugs 4, 5 e 7 foram corrigidos junto com as sugestões 9 e 10. Em seguida foram implementadas as sugestões 14, 21 e 24 da seção 4 e parte da 23 (análise de viabilidade), as sugestões 5, 16, 17, 18, 29 e 30 (segurança e dados) a sugestão 26 (rotas de leitura para análise e chat), a edição de produto, e as sugestões 20 e 22 em parte (página no chat e fórmula da viabilidade). A sugestão 19 (trocar o modelo de embeddings) foi medida e não adotada: uma busca híbrida resolveu o problema sem trocar o modelo. A documentação do projeto foi reescrita em [docs/documentacao-tecnica.md](docs/documentacao-tecnica.md), o que cobre as diferenças listadas na seção 3. O que foi feito e por quê está em [CORRECOES.md](CORRECOES.md). Este relatório descreve o estado do sistema **antes** dessas correções.

## Resumo

A arquitetura do sistema faz sentido e o backend sobe normalmente. Os problemas se concentram em três pontos:

- a **análise de viabilidade** tem dois bugs que afetam o resultado e um que derruba a requisição;
- os **editais não têm dono**, então dados de um usuário aparecem para outros;
- a **qualidade da busca semântica** (resumo e chat) é limitada pelo modelo de embeddings escolhido.

Cada item abaixo indica se foi **confirmado por teste** ou **identificado por leitura do código**.

### Como foi verificado

- Leitura completa do backend, do frontend e da documentação.
- Backend instalado em um ambiente temporário com Python 3.10 no Windows e executado contra um banco SQLite descartável: `/health`, cadastro, login, produtos e análise de viabilidade.
- Inspeção do banco local `licitacoes-ws/database.db`.
- **Teste de uso real em 05/10/2026**: sistema completo rodando no Windows (Redis Cloud, Qdrant Cloud, Groq), com busca por "ventilador", processamento do edital `18291377000102-1-000191/2026` (Carmo do Cajuru/MG), chat e análise de viabilidade. Os itens 8 a 11 da seção 1.1 e as seções 2.5 e 2.6 vieram desse teste, com base nos logs do backend.
- Reprodução isolada das chamadas à Groq para os cinco blocos do resumo.

---

## 1. Problemas encontrados

### 1.1 Bugs que afetam o funcionamento

| # | Problema | Onde | Verificação |
| --- | --- | --- | --- |
| 1 | Viabilidade retorna erro 500 quando a distância por CEP funciona | [cliente_routes.py:623](licitacoes-ws/routes/cliente_routes.py#L623) | Confirmado por teste |
| 2 | Extração de quantidade e valor do item nunca funciona | [cliente_routes.py:546](licitacoes-ws/routes/cliente_routes.py#L546) | Confirmado por teste e em uso real |
| 3 | Frete sai R$ 0 sem aviso quando a tabela ANTT está vazia | [cliente_routes.py:479](licitacoes-ws/routes/cliente_routes.py#L479) | Confirmado por teste |
| 4 | Arquivo do PNCP que não é PDF quebra o processamento | [tasks.py:48](licitacoes-ws/tasks.py#L48) | Confirmado no banco local |
| 5 | Edital com erro é reprocessado em duplicidade | [edital.component.ts:198](liciteview-angular/src/app/features/edital/edital.component.ts#L198) | Causa provável |
| 6 | Link "Ver no PNCP" sai com o domínio duplicado | [edital.component.ts:60](liciteview-angular/src/app/features/edital/edital.component.ts#L60) | Leitura do código |
| 7 | `alembic upgrade head` falha em banco vazio | [001_add_produto_logistica.py](licitacoes-ws/alembic/versions/001_add_produto_logistica.py) | Confirmado por teste |
| 8 | Todo edital é processado duas vezes ao ser aberto pela pesquisa | [pesquisa.component.ts:274](liciteview-angular/src/app/features/pesquisa/pesquisa.component.ts#L274) | Confirmado em uso real |
| 9 | Tela fica presa em "Processando edital" mesmo após o término | [edital.component.ts:268](liciteview-angular/src/app/features/edital/edital.component.ts#L268) | Confirmado em uso real |
| 10 | Blocos do resumo ficam vazios por erro da Groq, e o edital é marcado como processado | [edital_rag.py:394](licitacoes-ws/rag/edital_rag.py#L394) | Confirmado e reproduzido |
| 11 | Limite de uso da Groq é atingido durante o resumo | [edital_rag.py:411](licitacoes-ws/rag/edital_rag.py#L411) | Confirmado em uso real |

**1. Erro 500 na viabilidade.** As variáveis `uf_origem` e `uf_destino` só são definidas dentro do bloco de fallback por UF (quando a distância por CEP falha). Quando a distância por CEP funciona, a montagem da justificativa usa variáveis que não existem e a requisição quebra com `UnboundLocalError`. Hoje isso quase não aparece porque o resumo raramente traz um CEP de entrega, mas é justamente o caminho mais preciso que está quebrado.

**2. Nome da coleção no Qdrant.** O worker cria a coleção como `edital_<uuid com underscores>` ([tasks.py:125](licitacoes-ws/tasks.py#L125)). A viabilidade consulta `edital_<uuid com hífens>`. A coleção não é encontrada, o erro é capturado e a função devolve vazio. Na prática, a quantidade e o valor unitário do item específico nunca são extraídos do edital. No uso real, o log do backend registrou o erro do Qdrant ``Collection `edital_8badf8de-1e7c-...` doesn't exist!``.

**3. Frete zerado.** A tabela `tabela_frete_antt` está vazia no SQLite local, e `_calcular_frete_antt` devolve `0.0` quando não encontra os coeficientes. No teste, a mesma análise deu **margem de 76% sem a tabela e 29% com ela**, com a mesma classificação "Vale a pena". O usuário não recebe nenhum aviso de que o frete não foi considerado.

**4. Arquivo que não é PDF.** O único edital no banco local falhou porque o PNCP entregou um documento `.doc` antigo. O código pega o primeiro arquivo listado sem verificar o tipo, tenta abrir como PDF e devolve a mensagem "Stream has ended unexpectedly", que não ajuda o usuário. Além disso, a tarefa é repetida 3 vezes mesmo sendo um erro que nunca vai se resolver sozinho.

**5. Reprocessamento em duplicidade.** O edital citado acima gerou 12 execuções e 4 notificações de erro. A causa provável: ao abrir a página do edital, o frontend chama `processar` automaticamente, e o backend reenfileira qualquer edital em status ERRO. Isso acontece enquanto as tentativas automáticas do Celery ainda estão rodando, gerando cadeias paralelas. Durante as tentativas, o status fica em ERRO, então a tela mostra falha mesmo com o processamento ainda em andamento.

**6. Link duplicado.** O mapeador já monta `url_origem` com `https://pncp.gov.br`, e o template concatena o domínio de novo. O resultado é `https://pncp.gov.brhttps://pncp.gov.br/compras/...`.

**7. Migrations.** A primeira migration faz `ALTER TABLE produto`, ou seja, pressupõe que as tabelas já existem. Não há migration inicial nem `create_all` no código. No PostgreSQL é preciso executar [script.sql](licitacoes-ws/script.sql) antes do Alembic; o README instrui apenas `alembic upgrade head`. No SQLite não há nenhum caminho documentado para criar o banco.

**8. Processamento em dobro.** Ao clicar em um resultado, a tela de pesquisa chama `processar` e navega para a tela do edital, que chama `processar` de novo. No backend, a segunda chamada encontra o edital em PROCESSANDO ainda sem registro de execução (o worker não começou) e conclui que a tarefa nunca rodou, enfileirando outra ([cliente_routes.py:146](licitacoes-ws/routes/cliente_routes.py#L146)). Resultado observado: duas tarefas para o mesmo edital (68 s e 72 s), duas notificações "Resumo pronto" e o dobro de chamadas à Groq.

**9. Tela presa em "Processando".** É consequência do item 8. A primeira tarefa termina e marca o edital como PROCESSADO. A segunda começa e apaga o resumo para refazê-lo, mas não volta o status para PROCESSANDO. A tela consulta o status nesse intervalo e recebe "PROCESSADO, sem resumo": o polling para ao ver PROCESSADO ([edital.service.ts:85](liciteview-angular/src/app/core/services/edital.service.ts#L85)), mas a tela só sai do estado de processamento se houver resumo. Ela nunca mais atualiza; o resumo só aparece ao sair e voltar à página.

**10. Blocos vazios no resumo.** No teste real, os blocos Documentação, Requisitos técnicos e Riscos vieram vazios nas duas execuções. A Groq respondeu `400 json_validate_failed` com geração vazia: o modelo `openai/gpt-oss-20b` raciocina antes de responder e, nesses blocos, não chegou a produzir o JSON. A função `_gerar_bloco` captura qualquer exceção e devolve o esquema vazio, então o edital é marcado como PROCESSADO e o usuário vê um resumo incompleto sem aviso. Na reprodução isolada, a falha se repetiu nos três blocos; com o parâmetro `reasoning_effort="low"`, os três vieram preenchidos em 2 a 6 segundos (um teste por bloco). O modelo anterior, `llama-3.1-8b-instant`, não é mais uma alternativa: a Groq responde `model_not_found`.

**11. Limite de uso da Groq.** O log registrou várias respostas `429 Too Many Requests` durante o resumo, com esperas de 3 a 12 segundos. A pausa fixa de 1,2 s entre blocos não é suficiente para o modelo atual, que consome mais tokens por causa do raciocínio. O processamento em dobro (item 8) agravou o problema.

### 1.2 Segurança e dados

| Problema | Onde |
| --- | --- |
| Editais não têm dono: o histórico lista os editais de todos os usuários | [cliente_routes.py:252](licitacoes-ws/routes/cliente_routes.py#L252) |
| Qualquer usuário logado pode enviar PDF para qualquer edital | [cliente_routes.py:358](licitacoes-ws/routes/cliente_routes.py#L358) |
| Rotas sem login: status do edital, busca de licitações e `/debug/pncp-raw` | [cliente_routes.py:23](licitacoes-ws/routes/cliente_routes.py#L23), [:52](licitacoes-ws/routes/cliente_routes.py#L52), [:177](licitacoes-ws/routes/cliente_routes.py#L177) |
| Rate limit criado, mas não aplicado em nenhuma rota (nem no login) | [main.py:20](licitacoes-ws/main.py#L20) |
| Erros internos são devolvidos ao cliente com a mensagem da exceção | [main.py:64](licitacoes-ws/main.py#L64) |
| `database.db` não está no `.gitignore` (contém hashes de senha e arquivos de edital) | [.gitignore](licitacoes-ws/.gitignore) |
| O PDF é carregado do banco em toda consulta de edital | [models.py:144](licitacoes-ws/models.py#L144) |

Sobre o último item: a coluna `pdf_conteudo` vem junto em qualquer `query(Edital)`. O histórico carrega todos os PDFs de todos os editais para a memória, e o polling de status (a cada 8 segundos) carrega o PDF inteiro a cada chamada. Com o banco na nuvem, isso consome banda e memória sem necessidade.

### 1.3 Ambiente e execução

- O `.venv` do repositório foi criado em um Mac (Python 3.14) e não funciona no Windows. Precisa ser recriado com Python 3.10.
- O `node_modules` do frontend contém apenas binários `darwin-arm64`. Precisa ser apagado e reinstalado.
- O `.dockerignore` e o `Dockerfile` excluem `venv/`, mas a pasta usada é `.venv/`. Em um build local, o ambiente virtual e o `database.db` seriam copiados para a imagem.
- O `.env.example` não lista `REDIS_URL`, `COHERE_API_KEY` nem `START_CELERY_WORKER`.
- O README do backend cita `rag/rag.py`, que não existe.
- Há um `package-lock.json` vazio e um `.DS_Store` na raiz do repositório.

### 1.4 Problemas menores

- **Polling sem fim visível.** Após 5 minutos o polling encerra em silêncio e a tela continua mostrando "Processando" ([edital.service.ts:86](liciteview-angular/src/app/core/services/edital.service.ts#L86)).
- **Cache de análise ineficaz.** A verificação de análise existente acontece depois de todas as chamadas ao LLM, então não economiza nada. Ela também devolve a análise antiga se o custo do produto mudar e a receita for a mesma ([cliente_routes.py:678](licitacoes-ws/routes/cliente_routes.py#L678)).
- **Variáveis extraídas não são reaproveitadas.** O LLM é chamado a cada análise, mesmo com as variáveis já gravadas em `variavel_viabilidade`. O campo `confianca` é fixo em 0,85.
- **Tipos vindos do LLM.** Se o modelo devolver a quantidade como texto, a comparação `qty <= 0` quebra.
- **`perguntar_edital` não valida o UUID.** Um ID inválido gera erro 500 em vez de 400 ([cliente_routes.py:414](licitacoes-ws/routes/cliente_routes.py#L414)).
- **Upload lê o arquivo inteiro antes de checar o tamanho** (limite de 50 MB).
- **Reprocessamento não limpa o Qdrant.** Se o novo processamento gerar menos trechos, os antigos permanecem na coleção.
- **Senhas acima de 72 bytes** fazem o cadastro falhar com erro 500 (limite do bcrypt).
- **Router de administração vazio** ([admin_routes.py](licitacoes-ws/routes/admin_routes.py)).

---

## 2. Avaliação da lógica

### 2.1 Busca semântica (resumo e chat)

O modelo `all-MiniLM-L6-v2` foi treinado em inglês e lê no máximo cerca de 256 tokens por texto. Os trechos têm 450 palavras, o que em português passa de 600 tokens. Consequências:

- mais da metade de cada trecho não entra no vetor, então o conteúdo do final do trecho é praticamente invisível para a busca;
- a qualidade da similaridade em português é inferior à de um modelo multilíngue.

O reranking da Cohere compensa parte disso no chat, mas só reordena o que a busca inicial já trouxe.

### 2.2 Fórmula de viabilidade

A fórmula implementada é a mesma da documentação. As ressalvas são de modelagem:

- **Imposto sobre o custo.** O cálculo usa `custo × (1 + imposto)`. No Brasil, a carga tributária incide sobre o preço de venda, o que tende a subestimar o imposto.
- **Preço de venda não entra na margem.** A receita é sempre o valor do edital. O preço do produto só é usado para estimar a quantidade quando ela não é encontrada.
- **Valor por item nunca é usado.** A tela preenche o campo "Valor estimado" com o valor global do edital e sempre o envia. Com isso, o ramo que calcularia a receita a partir do valor unitário do item nunca executa.
- **Estimativa de quantidade.** Sem quantidade extraída, o sistema divide o valor total do edital pelo preço do produto, o que pressupõe que o edital inteiro é daquele produto.
- **Frete.** Assume sempre caminhão de 2 eixos com 5 toneladas e carga geral, independentemente do produto.
- **O cálculo não verifica se o produto consta no edital.** Ver o caso real na seção 2.5.

### 2.3 Tela de viabilidade

A tela exibe indicadores que não são calculados:

- "Compatibilidade técnica" é sempre 92%;
- "Capacidade vs demanda" e "Distância logística" variam apenas conforme a cor do resultado (30/85 e 35/65);
- o texto de "Análise contextual" é fixo por cor;
- a justificativa calculada pelo backend não é exibida;
- o campo `capacidade_mensal` do produto não é usado em nenhum cálculo.

Isso passa ao usuário a impressão de uma análise mais ampla do que a que foi feita.

### 2.4 Detecção de UF

Quando não há UF de entrega, o sistema procura siglas de estado no nome do órgão e no objeto. O padrão casa palavras comuns em maiúsculas, como "SE", e pode apontar o estado errado. Quando nada é encontrado, o destino assumido é SP.

### 2.5 Caso real: "Vale a pena" para um produto que não está no edital

No teste de 05/10/2026, o produto "ventilador" (custo R$ 10, preço R$ 30, impostos 18%) foi analisado contra um edital que não contém ventiladores. O PDF de 44 páginas não tem nenhuma ocorrência da palavra, os 9 itens listados pelo PNCP para a compra também não, e o próprio chat do sistema respondeu que o edital não menciona ventilador. Mesmo assim, o resultado foi **margem de +61,1% e classificação "Vale a pena"**.

O motivo é que o cálculo ficou circular:

| Variável | De onde veio | Valor |
| --- | --- | --- |
| Receita | Digitada pelo usuário (o edital não tem valor estimado no PNCP) | cerca de R$ 1.000 |
| Quantidade | Receita dividida pelo preço do produto, porque nada foi extraído do edital (bug 2) | 33 unidades |
| Custo operacional | 33 × R$ 10 × 1,18 | R$ 389 |
| Frete | Tabela ANTT vazia (bug 3) | R$ 0 |

A margem resultante, (30 − 11,80) ÷ 30 ≈ 61%, é apenas a margem do cadastro do produto. Qualquer edital daria o mesmo número para esse produto. Quando a extração do item falha, a análise não usa nenhuma informação do edital e não avisa o usuário disso.

### 2.6 Busca de licitações

A busca por "ventilador" trouxe esse edital, que não tem ventilador. O backend apenas repassa a consulta à busca do PNCP, então a correspondência foi decidida pelo PNCP; o motivo não foi identificado. Um fator do lado do sistema é que o frontend pede os resultados ordenados por data ([licitacao.service.ts:71](liciteview-angular/src/app/core/services/licitacao.service.ts#L71)), não por relevância, o que coloca resultados recentes e pouco relacionados no topo.

---

## 3. Diferenças em relação à documentação

| Tema | Documentação | Código |
| --- | --- | --- |
| Modelo de linguagem | `llama-3.1-8b-instant` | `openai/gpt-oss-20b` (alteração ainda sem commit); o modelo da documentação não está mais disponível na Groq |
| Modelo de embeddings | Descrito como multilíngue | `all-MiniLM-L6-v2` é treinado em inglês |
| Tamanho dos trechos | 450/75 na seção 2.4 e 350/50 na seção 5.2 | 450 palavras com sobreposição de 75 |
| Busca do chat | Recupera 9 trechos, usa 3 | Recupera 15, usa 5 |
| Contexto máximo | 3.500 caracteres | 4.500 caracteres no resumo; sem limite no chat |
| Fonte da resposta | Trecho e número da página | Só o trecho; a página não é rastreada |
| Relação usuário–edital | Diagrama mostra Usuário 1:N Edital | `Edital` não tem `usuario_id` |
| Notificações | Uma ao concluir o processamento | Duas por edital, por causa do processamento em dobro |
| Histórico | Análises de viabilidade com data, produto e classificação | Lista de editais processados (de todos os usuários) |
| Histórico do chat | Perguntas salvas e consultáveis | São gravadas, mas não há rota para lê-las |
| Análise de viabilidade | Persistente | Some da tela ao recarregar a página (não há rota de leitura) |
| Justificativa | Exibida na tela | Calculada, mas não exibida |
| Testes | Jasmine cobrindo 5 serviços | Os arquivos `.spec.ts` existem, mas não há Karma nem script de teste |
| Rate limiting | slowapi listado como tecnologia | Configurado, mas não aplicado |
| Container da API | "Não executa operações de ML" | Chat e viabilidade carregam o modelo de embeddings no processo da API |
| Execução local | `alembic upgrade head` cria o banco | Falha em banco vazio |
| Variáveis de ambiente | Lista não inclui `REDIS_URL` nem `COHERE_API_KEY` | Ambas são lidas pelo código |
| Estrutura de pastas | Pasta `docs/` com 9 arquivos | Não existe no repositório |
| Edição de produto | Ícone de lápis para editar | O botão existe, mas não tem ação ([produtos-list.component.ts:44](liciteview-angular/src/app/features/produtos/produtos-list.component.ts#L44)); só há a rota `produtos/novo` |

---

## 4. Sugestões de melhoria

### Prioridade alta — correções pequenas com efeito imediato

1. **Definir `uf_origem` e `uf_destino` antes do cálculo de distância**, fora do bloco de fallback, para eliminar o erro 500 (bug 1).
2. **Centralizar o nome da coleção do Qdrant em uma única função** usada pelo worker, pelo chat e pela viabilidade (bug 2).
3. **Corrigir o link "Ver no PNCP"**, usando `url_origem` diretamente (bug 6).
4. **Popular a tabela ANTT no banco local** e fazer a análise falhar com mensagem clara, ou sinalizar "frete não calculado", quando os coeficientes não existirem (bug 3).
5. **Adicionar `database.db` e `.DS_Store` ao `.gitignore`.**
6. **Remover a chamada de `processar` da tela de pesquisa**, deixando apenas a da tela do edital (bug 8).
7. **Manter o polling enquanto o status for PROCESSADO sem resumo**, ou encerrar o estado de processamento e buscar o resumo em seguida (bug 9).
8. **Passar `reasoning_effort="low"` nas chamadas à Groq** que exigem JSON (bug 10).

### Prioridade alta — exigem um pouco mais de trabalho

9. **Validar o tipo do arquivo baixado do PNCP.** Preferir arquivos PDF na lista, checar os primeiros bytes (`%PDF`) e devolver uma mensagem como "O arquivo publicado não é PDF; envie o edital manualmente". Não repetir a tarefa para erros que não se resolvem sozinhos (bug 4).
10. **Não reprocessar automaticamente editais em ERRO.** Ao abrir a página, apenas consultar o status; reenfileirar só quando o usuário clicar em "Tentar novamente". Manter o status PROCESSANDO durante as tentativas automáticas (bug 5).
11. **Tornar o enfileiramento seguro contra chamadas repetidas.** Não reenfileirar um edital em PROCESSANDO só porque ainda não há registro de execução; reenfileirar apenas se ele estiver parado há alguns minutos. No worker, voltar o status para PROCESSANDO antes de apagar o resumo (bugs 8 e 9).
12. **Tratar falha na geração de um bloco como falha**: tentar de novo aquele bloco e, se persistir, mostrar um aviso de "bloco não gerado" em vez de gravar o bloco vazio (bug 10).
13. **Respeitar o limite da Groq**: aumentar a pausa entre blocos ou usar o tempo de espera informado na resposta 429 (bug 11).
14. **Avisar quando o produto não for encontrado no edital.** Se a extração do item não devolver quantidade nem valor, informar que o resultado é apenas a margem do cadastro, ou não classificar como "Vale a pena" (seção 2.5).
15. **Ordenar a busca por relevância** quando houver palavra-chave, mantendo a ordenação por data só para buscas sem termo (seção 2.6).
16. **Vincular editais ao usuário.** Criar uma tabela de associação usuário–edital (o processamento pode continuar compartilhado) e filtrar histórico, status, upload e chat por ela. Exigir login em todas as rotas de `/cliente`.
17. **Remover ou proteger `/debug/pncp-raw`** e aplicar o rate limit ao login e ao cadastro.
18. **Marcar `pdf_conteudo` como coluna de carregamento adiado** (`deferred`), para que só o worker a leia.

### Prioridade média — qualidade do resultado

19. **Trocar o modelo de embeddings por um multilíngue de mesma dimensão**, como `paraphrase-multilingual-MiniLM-L12-v2` (384 dimensões, disponível no fastembed), e reduzir os trechos para cerca de 150–200 palavras. Exige reprocessar os editais já indexados.
20. **Rastrear a página de cada trecho** na extração e gravá-la no Qdrant, para cumprir o que a documentação promete na resposta do chat.
21. **Mostrar na tela de viabilidade só o que é calculado**: exibir a justificativa do backend, a distância, a quantidade considerada e a origem de cada valor (extraído do edital, informado ou estimado). Remover os indicadores fixos.
22. **Revisar a fórmula**: aplicar o imposto sobre a receita, usar o valor unitário do item quando disponível e deixar o campo "Valor estimado" vazio por padrão, para que o valor do item possa ser usado.
23. **Reaproveitar as variáveis já extraídas** em vez de chamar o LLM a cada análise, e verificar o cache antes dos cálculos.
24. **Substituir a detecção de UF por texto** pelo campo `uf` que o PNCP já devolve na busca, gravando-o no edital.

### Prioridade média — manutenção

25. **Criar uma migration inicial** com todo o esquema (substituindo o `script.sql`), incluindo a carga da tabela ANTT, para que `alembic upgrade head` funcione em banco vazio, tanto em PostgreSQL quanto em SQLite.
26. **Adicionar rotas de leitura** para análises de viabilidade e para o histórico de perguntas, e usá-las no frontend ao carregar a página.
27. **Configurar o executor de testes do frontend** (Karma ou Jest) com um script `npm test`, e criar testes do backend para o cálculo de viabilidade, que hoje não tem nenhum.
28. **Atualizar a documentação e os READMEs** conforme a tabela da seção 3, e completar o `.env.example`.
29. **Corrigir `.dockerignore` e `Dockerfile`** para excluir `.venv/` e `*.db`.
30. **Não devolver a mensagem da exceção ao cliente** no tratador global de erros; registrar no log e responder com um texto genérico.
