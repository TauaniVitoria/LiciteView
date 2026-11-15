# LiciteView — Correções aplicadas em 05/10/2026

Este documento registra as correções feitas após a análise descrita em [RELATORIO-ANALISE.md](RELATORIO-ANALISE.md). Os números de bug citados aqui são os da seção 1.1 daquele relatório.

As alterações estão na cópia de trabalho e **ainda não foram commitadas**.

O documento tem sete partes: o **lote 1** (correções dos bugs do relatório, seções 1 a 8), o **lote 2** (análise de viabilidade, seções 9 a 12), o **lote 3** (segurança e dados, seções 13 a 18) o **lote 4** (arquivos que não são PDF, editais com erro e criação do banco, seções 19 a 21) o **lote 5** (persistência na tela e edição de produto, seções 22 a 25) o **lote 6** (qualidade da busca, do resumo e da viabilidade, seções 26 a 32) e o **lote 7** (documentação do projeto, seção 33).

## Resumo do lote 1

| Bug | Problema | Situação |
| --- | --- | --- |
| 1 | Viabilidade retornava erro 500 quando a distância por CEP funcionava | Corrigido |
| 2 | Extração de quantidade e valor do item nunca funcionava | Corrigido |
| 3 | Frete saía R$ 0 sem aviso quando a tabela ANTT estava vazia | Corrigido |
| 6 | Link "Ver no PNCP" com o domínio duplicado | Corrigido |
| 8 | Todo edital era processado duas vezes | Corrigido |
| 9 | Tela presa em "Processando edital" | Corrigido |
| 10 | Blocos do resumo vazios por erro da Groq | Corrigido |
| 11 | Limite de uso da Groq atingido durante o resumo | Atenuado |

Também foi corrigido um problema que só apareceu depois de preencher a tabela ANTT (item 3.1 abaixo).

Os bugs 4, 5 e 7, que ficaram de fora deste lote, foram corrigidos no lote 4. Os itens de segurança foram tratados no lote 3 e a viabilidade no lote 2.

---

## 1. Viabilidade retornava erro 500 (bug 1)

**O que acontecia.** As variáveis `uf_origem` e `uf_destino` só eram definidas quando a distância por CEP falhava. Quando a distância por CEP funcionava, a montagem da justificativa usava variáveis inexistentes e a requisição quebrava.

**O que foi feito.** As duas UFs passaram a ser resolvidas sempre, antes do cálculo da distância. O bloco de fallback agora só calcula a distância entre UFs.

**Por quê.** As UFs têm dois usos: servir de fallback para a distância e aparecer no texto da justificativa. O segundo uso vale nos dois caminhos.

**Arquivo.** [licitacoes-ws/routes/cliente_routes.py](licitacoes-ws/routes/cliente_routes.py), função `_calcular_viabilidade`.

## 2. Extração do item do edital nunca funcionava (bug 2)

**O que acontecia.** O worker criava a coleção no Qdrant como `edital_<uuid com underscores>`, mas a viabilidade consultava `edital_<uuid com hífens>`. A coleção nunca era encontrada, e a quantidade e o valor unitário do item não eram extraídos.

**O que foi feito.** Foi criada a função `nome_colecao(edital_id)` em `edital_rag.py`. O worker, o chat e a viabilidade passaram a usá-la.

**Por quê.** O nome estava montado à mão em quatro lugares, e um deles divergiu. Com uma única função, a divergência não pode voltar.

**Arquivos.** [licitacoes-ws/rag/edital_rag.py](licitacoes-ws/rag/edital_rag.py), [licitacoes-ws/tasks.py](licitacoes-ws/tasks.py), [licitacoes-ws/routes/cliente_routes.py](licitacoes-ws/routes/cliente_routes.py).

**Efeito esperado.** A análise passa a tentar localizar o item do produto dentro do edital. Isso adiciona uma chamada à Groq por análise que antes falhava em silêncio.

## 3. Frete R$ 0 sem aviso (bug 3)

**O que acontecia.** Com a tabela ANTT vazia, a função de frete devolvia zero. A margem ficava inflada e o usuário não era avisado. No banco SQLite local, a tabela estava vazia e não havia como preenchê-la, porque o `script.sql` só funciona no PostgreSQL.

**O que foi feito.**

- Foi criado o script [licitacoes-ws/seed_antt.py](licitacoes-ws/seed_antt.py), que carrega as 24 linhas da tabela no banco configurado no `.env`. Ele lê os valores do próprio `script.sql` e não faz nada se a tabela já tiver dados.
- O script foi executado no banco local (`database.db`), que agora tem a tabela preenchida.
- Quando os coeficientes não existem, a análise agora responde com erro 503 e a mensagem "Tabela de frete ANTT não carregada no banco. Execute 'python seed_antt.py' no backend." A tela de viabilidade já exibe essa mensagem.
- O README do backend ganhou o passo `python seed_antt.py`.

**Por quê.** Um resultado "Vale a pena" calculado sem frete é pior do que nenhum resultado, porque parece confiável. Ler os valores do `script.sql` evita manter os coeficientes em dois lugares.

### 3.1 Coeficiente de carga perigosa podia ser usado no lugar do de carga geral

**O que acontecia.** A consulta buscava o tipo de carga com `ilike '%Carga Geral%'`, que também casa com "Perigosa (carga geral)". Como a consulta pegava a primeira linha encontrada, o frete podia sair com o coeficiente mais caro. Isso estava escondido enquanto a tabela estava vazia.

**O que foi feito.** A consulta passou a comparar o nome exato, `'Carga Geral'`.

## 4. Link "Ver no PNCP" duplicado (bug 6)

**O que acontecia.** O endereço saía como `https://pncp.gov.brhttps://pncp.gov.br/compras/...`.

**O que foi feito.** O link passou a usar `url_origem` diretamente, que já vem com o endereço completo.

**Arquivo.** [liciteview-angular/src/app/features/edital/edital.component.ts](liciteview-angular/src/app/features/edital/edital.component.ts).

## 5. Edital processado duas vezes (bug 8)

**O que acontecia.** A tela de pesquisa chamava `processar` ao clicar em um resultado, e a tela do edital chamava de novo ao abrir. O backend aceitava as duas chamadas, porque a segunda encontrava o edital em PROCESSANDO ainda sem registro de execução e concluía que a tarefa nunca tinha rodado. O resultado eram duas tarefas, duas notificações e o dobro de chamadas à Groq.

**O que foi feito.**

- **Frontend:** a chamada de `processar` foi removida da tela de pesquisa. A tela do edital continua responsável por ela.
- **Backend:** um edital em PROCESSANDO sem registro de execução só é reenfileirado se estiver parado há mais de 120 segundos (`JANELA_ENFILEIRAMENTO_S`).

**Por quê duas correções.** A do frontend remove a causa. A do backend protege contra qualquer outra chamada repetida, como duplo clique ou duas abas, e mantém a recuperação de editais realmente travados.

**Arquivos.** [liciteview-angular/src/app/features/pesquisa/pesquisa.component.ts](liciteview-angular/src/app/features/pesquisa/pesquisa.component.ts), [licitacoes-ws/routes/cliente_routes.py](licitacoes-ws/routes/cliente_routes.py).

**Mudança de comportamento.** Antes, o edital era criado no banco ao clicar no resultado da pesquisa. Agora ele é criado quando a tela do edital abre, uma fração de segundo depois. O histórico continua sendo alimentado.

## 6. Tela presa em "Processando edital" (bug 9)

**O que acontecia.** Durante um reprocessamento, o worker apagava o resumo sem mudar o status, que continuava PROCESSADO. A tela recebia "PROCESSADO, sem resumo", parava de consultar e nunca saía do estado de processamento.

**O que foi feito.**

- **Backend:** o worker volta o status para PROCESSANDO antes de apagar o resumo.
- **Frontend:** o polling só termina quando o status é ERRO ou quando é PROCESSADO **com resumo**.

**Por quê.** O status precisa descrever o estado real do edital. A mudança no frontend cobre o caso de a resposta chegar no intervalo entre o resumo ser apagado e regravado.

**Arquivos.** [licitacoes-ws/tasks.py](licitacoes-ws/tasks.py), [liciteview-angular/src/app/core/services/edital.service.ts](liciteview-angular/src/app/core/services/edital.service.ts).

## 7. Blocos do resumo vazios (bug 10)

**O que acontecia.** A Groq respondia `400 json_validate_failed` com geração vazia nos blocos Documentação, Requisitos técnicos e Riscos. O modelo `openai/gpt-oss-20b` raciocina antes de responder e, nesses blocos, não chegava a produzir o JSON. O código capturava o erro, gravava o bloco vazio e marcava o edital como processado.

**O que foi feito.**

- As três chamadas à Groq que exigem JSON passaram a enviar `reasoning_effort="low"` (constante `LLM_REASONING_EFFORT`).
- A geração de cada bloco tenta até 3 vezes, com espera de 5 e 10 segundos entre as tentativas.
- Se as 3 tentativas falharem, o processamento falha com a mensagem "Falha ao gerar o bloco '...' do resumo". O edital vai para ERRO e o usuário pode tentar de novo, em vez de receber um resumo incompleto.

**Por quê.** O esforço de raciocínio baixo resolve a causa. A mudança no tratamento do erro garante que uma falha da IA seja visível.

**Arquivo.** [licitacoes-ws/rag/edital_rag.py](licitacoes-ws/rag/edital_rag.py).

**Observação.** O parâmetro `reasoning_effort` só é aceito por modelos com raciocínio. Se o modelo for trocado por um que não tenha, a constante deve ser removida das chamadas.

## 8. Limite de uso da Groq (bug 11) — atenuado

Não houve uma correção específica. Duas das mudanças acima reduzem o problema: o edital deixa de ser processado em dobro, e o raciocínio baixo consome menos tokens por chamada. No teste após as correções, os cinco blocos foram gerados sem nenhuma resposta 429. A pausa fixa de 1,2 segundo entre os blocos foi mantida, então o limite ainda pode ser atingido com editais maiores ou vários processamentos seguidos.

---

## Como o lote 1 foi verificado

| Verificação | Resultado |
| --- | --- |
| Duas chamadas seguidas de `processar` para o mesmo edital | Uma única tarefa enfileirada |
| Análise de viabilidade sem tabela ANTT | Erro 503 com a mensagem de orientação |
| Análise com distância por CEP (antes: erro 500) | Resposta 200; frete de R$ 1.991,03, igual ao esperado (436,39 + 3,8866 × 400 km) |
| Tabela com "Carga Geral" e "Perigosa (carga geral)" | O coeficiente usado foi o de Carga Geral |
| Nome da coleção consultada na viabilidade | Igual ao criado pelo worker |
| Análise com fallback por UF | Resposta 200, justificativa com as UFs corretas |
| Geração dos 5 blocos do resumo na Groq, sobre o edital real já indexado | Os 5 gerados em 14 segundos, sem erro 400 nem 429 |
| `seed_antt.py` executado duas vezes | 24 linhas na primeira; nada na segunda |
| Compilação do frontend (`ngc --noEmit`) | Sem erros |

Os testes do backend rodaram contra um banco SQLite descartável, com as chamadas de IA substituídas por valores fixos, exceto a geração dos blocos, que usou a Groq e o Qdrant reais.

Os testes automatizados do frontend (`.spec.ts`) não puderam ser executados, porque o projeto não tem executor de testes configurado.

### Teste do fluxo completo pela interface

Depois das correções, o fluxo foi percorrido no navegador (Edge controlado por script), contra o backend, o Redis, o Qdrant e a Groq reais. O edital `18291377000102-1-000191/2026` foi apagado do banco e do Qdrant antes, para ser processado do zero.

| Etapa | Resultado |
| --- | --- |
| Cadastro em duas etapas e login automático | Funcionou; redirecionou para a pesquisa |
| Cadastro de produto | Criado (HTTP 201) |
| Pesquisa por "ventilador" | 20 resultados |
| Abrir o edital | **Uma** chamada a `processar` (antes: duas) |
| Processamento | **Uma** execução registrada no banco, com sucesso |
| Tela do edital | O resumo apareceu sozinho em 26 segundos, sem sair da página (antes: ficava presa) |
| Respostas "PROCESSADO sem resumo" | Nenhuma |
| Resumo | Os cinco blocos vieram com conteúdo (antes: três vazios) |
| Notificações | **Uma** "Resumo pronto" (antes: duas) |
| Viabilidade | HTTP 200, com frete calculado pela tabela ANTT (R$ 631; antes: R$ 0) |
| Chat | Respondeu o prazo de entrega citando a cláusula do edital |
| Reabrir o edital pelo histórico | Resumo exibido direto, sem novo processamento |
| Erros HTTP ou no console do navegador | Nenhum |

A conta e o produto criados para o teste foram removidos do banco ao final. O edital ficou no banco, já processado com o resumo completo.

### Problemas que o teste mostrou e que não fazem parte destas correções

- **Destino do frete errado.** O edital é de Carmo do Cajuru/MG e o produto sai de Bauru/SP, mas o backend calculou o frete como SP→SP, 50 km. O resumo não trouxe a UF de entrega, o nome do órgão não contém a sigla, e nesse caso o código assume SP. A tela mostra "→ MG", porque usa a UF que veio do PNCP, e fica em desacordo com o cálculo. Corresponde à seção 2.4 e à sugestão "Substituir a detecção de UF por texto" do relatório.
- **A quantidade continua sendo estimada.** Com o bug 2 corrigido, a busca do item dentro do edital passou a rodar, mas não encontrou quantidade nem valor para o produto testado. A quantidade voltou a ser "valor informado ÷ preço do produto", e a margem continua refletindo o cadastro do produto. Corresponde à seção 2.5 e à sugestão "Avisar quando o produto não for encontrado no edital".
- **Painel de força da senha no cadastro.** Ele aparece em inglês ("Enter a password") e cobre a caixa "Li e concordo" enquanto o campo de senha está em foco.
- **Porta do frontend.** Quando a porta 4200 está ocupada, o Angular sobe em uma porta aleatória, que precisa ser incluída em `ALLOWED_ORIGINS` no `.env` a cada vez. Usar `npm start -- --port 4201` evita o problema.

## O que fazer depois de atualizar o código (lote 1)

1. **Reiniciar o backend**, se ele não estiver rodando com `--reload`.
2. **Em outros bancos** (PostgreSQL ou um SQLite novo), executar `python seed_antt.py` na pasta `licitacoes-ws`.
3. **Editais processados antes da correção** continuam com os blocos vazios gravados. No banco local, o edital `18291377000102-1-000191/2026` já foi apagado e reprocessado durante o teste pela interface. O sistema não reprocessa um edital que já está como PROCESSADO, e não há botão para isso na tela; é preciso alterar o status dele no banco para que seja processado de novo.

---

# Lote 2 — Análise de viabilidade (05/10/2026)

O teste pela interface do lote anterior mostrou que a viabilidade ainda produzia números enganosos: frete para o estado errado e "Vale a pena" para um produto que não estava no edital. Este lote trata disso. Ele implementa as sugestões 14, 21 e 24 do relatório e parte da 23.

## Erros encontrados neste lote

Além dos dois problemas já registrados no teste anterior (destino do frete e quantidade estimada), a revisão do código para este lote encontrou mais quatro:

| # | Erro | Consequência |
| --- | --- | --- |
| A | Quando o valor de referência era menor que o preço do produto, a quantidade estimada dava **zero** | Custo zero e margem de 100%, com classificação "Vale a pena" |
| B | Os valores devolvidos pela IA eram usados sem conversão | Um texto no lugar de um número (por exemplo `"1.500,00"`) quebrava a comparação e a análise falhava |
| C | Sem UF de entrega, o destino assumido era sempre **SP**, sem aviso | Frete calculado para o estado errado em qualquer edital de fora de SP cujo órgão não tivesse a sigla no nome |
| D | A análise antiga era devolvida sempre que a receita coincidia | Mudar o custo, o peso ou o CEP do produto e reanalisar com o mesmo valor devolvia o resultado antigo |

## 9. Destino do frete passa a usar a UF do PNCP (sugestão 24, erro C)

**O que acontecia.** O edital não guardava a UF do órgão comprador. A viabilidade tentava descobri-la pelo resumo da IA ou procurando siglas no nome do órgão e no objeto, com um padrão que casava palavras comuns como "SE". Sem resultado, assumia SP. No teste real, um edital de Carmo do Cajuru/MG teve o frete calculado como SP→SP, 50 km.

**O que foi feito.**

- O edital ganhou os campos `uf` e `municipio`. O frontend passou a enviá-los ao processar o edital, e o backend também os atualiza quando consulta a compra no PNCP. O histórico passou a devolver esses campos, que antes vinham vazios.
- A UF de entrega é resolvida pela função `_resolver_uf_destino`, nesta ordem: CEP de entrega extraído do edital; UF do órgão no PNCP; UF citada no resumo da IA; sigla escrita como "Cidade/UF" ou "- UF" no nome do órgão ou no objeto.
- O padrão antigo de busca por sigla foi substituído por um que só aceita a sigla em maiúsculas precedida de "/" ou "-".
- **Não há mais valor padrão.** Se nenhuma fonte der a UF, o frete é calculado para o mesmo estado de origem, a análise recebe um aviso e não pode ser classificada como "Vale a pena".

**Por quê.** A UF do órgão é um dado oficial que o PNCP já entrega; não fazia sentido adivinhá-la por texto. A UF do PNCP vem antes da UF do resumo porque a do resumo é gerada por IA e pode vir errada.

**Arquivos.** [licitacoes-ws/models.py](licitacoes-ws/models.py), [licitacoes-ws/schemas.py](licitacoes-ws/schemas.py), [licitacoes-ws/routes/cliente_routes.py](licitacoes-ws/routes/cliente_routes.py), [licitacoes-ws/alembic/versions/003_add_edital_uf_municipio.py](licitacoes-ws/alembic/versions/003_add_edital_uf_municipio.py), [liciteview-angular/src/app/core/services/edital.service.ts](liciteview-angular/src/app/core/services/edital.service.ts), [liciteview-angular/src/app/features/edital/edital.component.ts](liciteview-angular/src/app/features/edital/edital.component.ts).

**Exige mudança no banco.** Ver "O que fazer depois de atualizar o código (lote 2)" abaixo.

## 10. Aviso quando o produto não é localizado no edital (sugestão 14, erros A e B)

**O que acontecia.** Sem quantidade extraída do edital, o sistema dividia o valor de referência pelo preço do produto e seguia o cálculo normalmente. A margem resultante era só a margem do cadastro do produto, mas aparecia como "Vale a pena", sem nenhum aviso.

**O que foi feito.**

- O cálculo passou a registrar de onde veio a quantidade: `ITEM_EDITAL` (item correspondente ao produto), `RESUMO_EDITAL` (quantidade geral do resumo) ou `ESTIMADA`.
- Quando a quantidade é estimada, a análise recebe o aviso "O produto não foi localizado no edital..." e **não pode ser classificada como "Vale a pena"**: o resultado é rebaixado para "Atenção". "Não recomendado" continua valendo quando há prejuízo.
- A quantidade estimada passou a ser no mínimo 1 (erro A).
- Os valores vindos da IA passam pela função `_numero`, que aceita números e textos como `"1.500,00"` e descarta o que não for número (erro B).

**Por quê.** A classificação é o que o usuário lê primeiro. Um resultado que não usa nenhuma informação do edital não deve ser apresentado como recomendação de participar.

**Limitação.** A classificação "Atenção" passou a ter dois significados: margem abaixo da mínima, ou resultado baseado em estimativa. O texto da justificativa e o aviso na tela dizem qual é o caso. Criar uma quarta classificação exigiria alterar o tipo enumerado no banco, e isso ficou fora deste lote.

**Arquivo.** [licitacoes-ws/routes/cliente_routes.py](licitacoes-ws/routes/cliente_routes.py), função `_calcular_viabilidade`.

## 11. Tela de viabilidade mostra só o que é calculado (sugestão 21)

**O que acontecia.** A tela exibia "Compatibilidade técnica 92%" fixo, "Capacidade vs demanda" e "Distância logística" variando só com a cor do resultado, uma barra de "Margem estimada" em escala inventada e um texto de "Análise contextual" fixo por cor. A justificativa calculada pelo backend não aparecia. O cartão de frete mostrava a UF vinda do PNCP, mesmo quando o cálculo tinha usado outra.

**O que foi feito.**

- O bloco "Critérios avaliados" foi removido.
- O cartão "Análise contextual" virou "Como o resultado foi calculado" e mostra a justificativa do backend, que agora traz quantidade considerada e sua origem, receita, custo de produção e impostos, frete, distância e rota.
- Os avisos do backend aparecem em destaque acima dos números.
- O cartão de custo operacional mostra a quantidade considerada. O de custo logístico mostra a rota e a distância realmente usadas no cálculo.
- O "Score de atratividade" só aparece quando não há avisos; caso contrário, a tela mostra "Resultado baseado em estimativas".
- A resposta da API de análise ganhou os campos `quantidade_considerada`, `quantidade_origem`, `uf_origem`, `uf_destino` e `avisos`. A justificativa passou a usar formato brasileiro de moeda e porcentagem.

**Por quê.** Indicadores fixos davam a impressão de uma análise técnica e de capacidade que o sistema não faz.

**Arquivos.** [liciteview-angular/src/app/features/edital/viabilidade-tab.component.ts](liciteview-angular/src/app/features/edital/viabilidade-tab.component.ts), [liciteview-angular/src/app/core/services/analise.service.ts](liciteview-angular/src/app/core/services/analise.service.ts), [liciteview-angular/src/app/core/models/analise.model.ts](liciteview-angular/src/app/core/models/analise.model.ts), [licitacoes-ws/schemas.py](licitacoes-ws/schemas.py).

## 12. Reanalisar atualiza a análise existente (parte da sugestão 23, erro D)

**O que acontecia.** Depois de fazer todo o cálculo, o backend procurava uma análise com a mesma receita e, se achasse, devolvia a antiga. Isso não economizava nada e podia devolver um resultado desatualizado.

**O que foi feito.** Existe agora uma análise por edital, produto e usuário. Reanalisar recalcula e atualiza esse registro, incluindo a data.

**Não foi feito.** A outra metade da sugestão 23, reaproveitar as variáveis já extraídas para não chamar a IA a cada análise, continua pendente.

## Como o lote 2 foi verificado

**Testes do backend**, num banco descartável e com as respostas da IA simuladas:

| Cenário | Resultado |
| --- | --- |
| `processar` com UF e município | Gravados no edital |
| Produto não localizado, edital de MG | "Atenção", 1 aviso, quantidade `ESTIMADA`, rota SP→MG |
| Mesmo edital com o item localizado (40 un.) | "Vale a pena", sem avisos, quantidade `ITEM_EDITAL` |
| Reanálise do mesmo par edital + produto | Um único registro no banco |
| Item localizado, UF de entrega desconhecida | "Atenção", aviso de UF, frete no estado de origem |
| Sigla só no nome do órgão ("- RN"), com a palavra "SE" no texto | Destino RN |
| CEP de entrega no resumo | Distância entre CEPs; UF obtida do CEP |
| IA devolve texto inválido e valor menor que o preço | Quantidade 1, sem erro (antes: quantidade 0 ou falha) |

**Teste pela interface**, com o sistema real e o mesmo edital de Carmo do Cajuru/MG:

| Item | Lote 1 | Lote 2 |
| --- | --- | --- |
| Rota do frete | SP→SP, 50 km | SP→MG, 636 km |
| Frete | R$ 631 | R$ 2.907 |
| Classificação | Vale a pena (27,9%) | Atenção (23,4%), com aviso de produto não localizado |
| Indicadores fixos na tela | Presentes | Removidos |
| Justificativa do backend na tela | Ausente | Presente |

Cadastro, pesquisa, resumo, chat e histórico continuaram funcionando, sem erros HTTP nem erros no console. O frontend compila sem erros. A conta de teste foi removida ao final.

## Pontos que continuam em aberto na viabilidade

- **A distância por UF é entre capitais.** Para Bauru/SP → Carmo do Cajuru/MG, o cálculo usa São Paulo → Belo Horizonte. A distância por CEP só é usada quando o resumo traz um CEP de entrega, o que é raro.
- **A busca do item não encontrou o produto testado.** Para "Armário de aço", a extração não devolveu quantidade nem valor. Não foi verificado se o edital lista esse item com quantidade no PDF processado ou em um anexo. A qualidade dessa busca depende do modelo de embeddings (seção 2.1 do relatório).
- **O valor por item extraído do edital continua sem uso**, porque a tela sempre envia o valor de referência (sugestão 22).
- **O imposto continua incidindo sobre o custo**, não sobre a receita (sugestão 22).
- **O aviso aparece duas vezes na tela**: no destaque e dentro do texto da justificativa.

## O que fazer depois de atualizar o código (lote 2)

O edital ganhou duas colunas, então **o banco precisa ser atualizado antes de subir o backend**. Sem isso, qualquer consulta a editais falha.

- **PostgreSQL:** `alembic upgrade head` (migration `003`).
- **SQLite já existente:** o Alembic não funciona nesse caso (bug 7 do relatório). Execute uma vez:

  ```sql
  ALTER TABLE edital ADD COLUMN uf VARCHAR(2);
  ALTER TABLE edital ADD COLUMN municipio VARCHAR(255);
  ```

**Situação em 05/10/2026:**

- **PostgreSQL do projeto (Neon):** a migration `003` já foi aplicada com `alembic upgrade head`. O banco estava na revisão `90d70d3e4eee` e passou para `003`. Foram criadas apenas as duas colunas, que aceitam valor vazio; os 5 editais e 5 usuários existentes não foram alterados. O backend antigo continua funcionando com o banco migrado, porque não usa essas colunas.
- **SQLite local desta máquina (`database.db`):** as colunas foram criadas à mão e o banco foi marcado como atualizado com `alembic stamp head`. A partir de agora, `alembic upgrade head` funciona nele para as próximas migrations.

- **Tabela ANTT no Neon:** ao conferir o Neon, a tabela de frete estava **vazia também na produção**, ou seja, o bug 3 (frete R$ 0) acontecia lá em toda análise de viabilidade. O `seed_antt.py` foi executado contra o Neon e carregou as 24 linhas. A partir disso, as análises feitas na produção passam a incluir o frete, mesmo com o backend antigo.
- **Conferência de estrutura:** depois da migration, as tabelas e colunas do Neon foram comparadas com os modelos do código, e não há diferenças.

O desenvolvimento e os testes continuam no SQLite local (é o banco ativo no `.env` desta máquina), para não alterar dados do grupo. O Neon é mantido com a mesma estrutura e os mesmos dados de referência.

Quem tiver outro SQLite local, criado antes deste lote, precisa executar os dois `ALTER TABLE` acima e depois `alembic stamp head`.

Editais antigos recebem a UF na próxima vez em que forem abertos pela tela.

---

# Lote 3 — Segurança e dados (05/10/2026)

Este lote trata dos itens da seção 1.2 do relatório: editais sem dono, rotas sem login, limite de tentativas, vazamento de mensagens de erro, carga desnecessária do PDF e arquivos que não deveriam ir para o git ou para a imagem Docker. Implementa as sugestões 5, 16, 17, 18, 29 e 30.

## Erros encontrados neste lote

Além do que já estava no relatório, a implementação encontrou mais três:

| # | Erro | Consequência |
| --- | --- | --- |
| E | O `.dockerignore` começava com um caractere invisível (BOM) | A primeira regra, `venv/`, não era reconhecida pelo Docker |
| F | A rota do chat devolvia a mensagem da exceção ao cliente (`Erro ao processar pergunta: ...`) | Mesmo vazamento do tratador global de erros, por outro caminho |
| G | Em produção, atrás do Nginx, o limite de tentativas contaria todos os usuários como um só | O endereço visto pela API é o do proxy; um limite por IP bloquearia todo mundo junto |

## 13. Editais vinculados ao usuário (sugestão 16)

**O que acontecia.** O edital não tinha dono. O histórico listava os editais de todos os usuários, e qualquer usuário logado podia consultar o status, conversar, analisar ou enviar um PDF para qualquer edital, bastando ter o ID.

**O que foi feito.**

- Foi criada a tabela `usuario_edital` (migration `004`), que registra quais editais cada usuário abriu ou enviou.
- O vínculo é criado quando o usuário abre um edital pela busca (`processar`) ou envia um PDF.
- Histórico, status, chat, análise de viabilidade e upload para edital existente passaram a exigir esse vínculo. Sem ele, a resposta é 404, a mesma de um edital inexistente, para não revelar quais IDs existem.
- O histórico passou a ser ordenado pela data em que o usuário abriu o edital.
- Para os editais já existentes, o script [licitacoes-ws/vincular_editais_existentes.py](licitacoes-ws/vincular_editais_existentes.py) cria os vínculos a partir das notificações, análises e perguntas de cada usuário. Ele pode ser executado mais de uma vez.

**O que não mudou.** O processamento continua compartilhado: se um segundo usuário abrir um edital já processado, ele recebe o vínculo e vê o resumo na hora, sem novo processamento e sem novas chamadas à IA.

**Por quê uma tabela de vínculo, e não um dono por edital.** O mesmo edital do PNCP pode interessar a vários fornecedores. Com um dono único, cada um teria de reprocessar o mesmo documento.

**Arquivos.** [licitacoes-ws/models.py](licitacoes-ws/models.py), [licitacoes-ws/routes/cliente_routes.py](licitacoes-ws/routes/cliente_routes.py), [licitacoes-ws/alembic/versions/004_add_usuario_edital.py](licitacoes-ws/alembic/versions/004_add_usuario_edital.py).

**Limitações.**

- A notificação "Resumo pronto" vai só para quem disparou o processamento. Um segundo usuário que abra o edital enquanto ele ainda está sendo processado acompanha pela tela, mas não recebe notificação.
- O usuário com perfil ADMIN não tem acesso especial: vê apenas os próprios editais, como os demais.

## 14. Login obrigatório e rota de debug removida (sugestão 17)

**O que acontecia.** A busca de licitações, o status do edital e a rota `/cliente/debug/pncp-raw` respondiam sem login.

**O que foi feito.** A busca e o status passaram a exigir token. A rota de debug foi removida; o frontend não a usava. Todas as rotas de `/cliente` agora exigem login.

## 15. Limite de tentativas no login e no cadastro (sugestão 17, erro G)

**O que acontecia.** O limitador estava criado em `main.py`, mas nenhuma rota o usava. O login aceitava tentativas ilimitadas de senha.

**O que foi feito.**

- O limitador foi movido para o módulo [licitacoes-ws/rate_limit.py](licitacoes-ws/rate_limit.py), para que `main.py` e as rotas usem o mesmo objeto.
- Limites por IP: 20 tentativas de login por minuto e 10 cadastros por minuto. Acima disso, a resposta é 429.
- O IP é lido do cabeçalho `X-Forwarded-For` quando ele existe (erro G), e da conexão caso contrário.
- A tela de login mostra "Muitas tentativas de login. Aguarde um minuto e tente novamente." quando recebe 429.

**Limitações.**

- O `X-Forwarded-For` pode ser forjado por quem acessa a porta da API diretamente. O `docker-compose.yml` publica a porta 8000; em produção ela deveria ficar acessível só pelo Nginx. Isso não foi alterado neste lote.
- A contagem fica na memória do processo. Ela zera quando a API reinicia e não é compartilhada se houver mais de um processo.

## 16. Mensagens de erro interno não vão mais para o cliente (sugestão 30, erro F)

**O que acontecia.** O tratador global devolvia `Erro interno do servidor: <mensagem da exceção>`, e o chat fazia o mesmo. A mensagem de uma exceção pode conter nomes de tabelas, caminhos de arquivos e endereços de serviços.

**O que foi feito.** As duas respostas passaram a trazer um texto genérico. O detalhe continua sendo registrado no log do servidor. As mensagens de erro escritas de propósito para o usuário (por exemplo "Edital sem valor estimado...") não mudaram.

**Arquivos.** [licitacoes-ws/main.py](licitacoes-ws/main.py), [licitacoes-ws/routes/cliente_routes.py](licitacoes-ws/routes/cliente_routes.py).

**Também corrigido.** O chat respondia 500 quando o ID do edital não era um UUID válido; agora responde 400.

## 17. PDF não é mais carregado em toda consulta (sugestão 18)

**O que acontecia.** A coluna `pdf_conteudo` vinha junto em qualquer consulta de edital. O histórico trazia todos os PDFs para a memória, e o polling de status trazia o PDF inteiro a cada 8 segundos.

**O que foi feito.** A coluna foi marcada como de carregamento adiado (`deferred`). O arquivo só é lido do banco quando o código acessa o atributo, o que acontece apenas no worker.

**Arquivo.** [licitacoes-ws/models.py](licitacoes-ws/models.py).

## 18. Arquivos fora do git e da imagem Docker (sugestões 5 e 29, erro E)

- O `.gitignore` do backend passou a ignorar `*.db`. O `database.db` contém hashes de senha e arquivos de edital e estava a um `git add` de ser versionado.
- Foi criado um `.gitignore` na raiz do repositório para `.DS_Store` e `Thumbs.db`.
- O `.dockerignore` foi regravado sem o caractere invisível do início (erro E) e passou a excluir `.venv/` e `*.db`.
- O `Dockerfile` passou a remover também `.venv/` e `*.db` da imagem.

## Como o lote 3 foi verificado

**Testes do backend**, num banco descartável, com dois usuários (A e B):

| Cenário | Resultado |
| --- | --- |
| Sem token: busca, status, histórico | 401 nos três |
| Rota de debug | 404 (não existe mais) |
| A abre um edital | Histórico de A: 1 edital. Histórico de B: vazio |
| B tenta status, chat, análise e upload do edital de A | 404 nos quatro |
| A usa status e chat do próprio edital | 200 |
| B abre o mesmo edital pela busca | Recebe o vínculo, nenhuma tarefa nova, passa a ter acesso |
| Erro interno no chat (exceção com uma URL de banco na mensagem) | 500 com texto genérico; a URL não aparece |
| Chat com ID inválido | 400 |
| Consultas de status e histórico | Nenhuma seleciona `pdf_conteudo` |
| 24 logins errados seguidos | 429 a partir do limite de 20 por minuto |
| Login vindo de outro IP no mesmo minuto | Não é afetado pelo bloqueio do primeiro |

**Teste pela interface**, com o sistema real: cadastro, produto, busca, abertura do edital, resumo, viabilidade, chat e histórico funcionaram, sem erros HTTP nem no console. O histórico da conta de teste mostrou só o edital que ela abriu; antes, mostraria também o edital com erro de outro usuário. O frontend compila sem erros.

## Situação dos bancos após o lote 3

- **SQLite local:** migration `004` aplicada com `alembic upgrade head`. O script de vínculos criou 1 vínculo. O vínculo da conta da Jhuliani com o edital de Carmo do Cajuru foi recriado à mão, porque os registros que o originariam tinham sido apagados quando o edital foi removido para o teste do lote 1.
- **PostgreSQL do projeto (Neon):** migration `004` aplicada. O script de vínculos criou 6 vínculos, e os 5 editais existentes ficaram com pelo menos um usuário vinculado. A estrutura foi comparada de novo com os modelos e não há diferenças.

## O que fazer ao publicar o backend novo

1. **Rodar de novo `python vincular_editais_existentes.py` no Neon.** Editais processados pelo backend antigo entre hoje e a publicação não terão vínculo, e sumiriam do histórico de quem os abriu. O script cria os vínculos que faltarem.
2. **Fechar a porta 8000 para acesso externo**, deixando a API acessível só pelo Nginx, para que o limite de tentativas não possa ser contornado.
3. **Sessões abertas continuam valendo.** Nenhuma mudança deste lote invalida tokens já emitidos.

## Pontos de segurança que continuam em aberto

- **O token dura 24 horas e fica no `localStorage` do navegador.** Não há renovação nem revogação.
- **Não há verificação de e-mail no cadastro**, apesar de a tela mencionar a validação do e-mail corporativo.
- **A chave `SECRET_KEY` não tem valor padrão nem verificação.** Se faltar no `.env`, o login falha com erro interno.
- **O upload lê o arquivo inteiro para a memória antes de verificar o limite de 50 MB.**
- **O tipo do arquivo enviado é verificado só pela extensão** `.pdf`, não pelo conteúdo (relacionado ao bug 4).

---

# Lote 4 — Arquivos que não são PDF, editais com erro e criação do banco (05/10/2026)

Este lote trata dos três bugs do relatório que tinham ficado de fora: 4 (arquivo do PNCP que não é PDF), 5 (reprocessamento automático de edital com erro) e 7 (não havia como criar o banco do zero). Implementa as sugestões 9 e 10 e resolve a 25 por outro caminho.

## Erros encontrados neste lote

| # | Erro | Consequência |
| --- | --- | --- |
| H | O arquivo baixado era gravado no banco **antes** de ser verificado, e toda nova tentativa reaproveitava o que estava gravado | Depois de um download em formato errado, "Tentar novamente" nunca mais baixava nada: repetia o mesmo arquivo inválido para sempre |
| I | A mensagem de erro do worker ia para a tela e para a notificação como estava | Mensagens técnicas ("Stream has ended unexpectedly") e, em erros inesperados, possíveis detalhes internos |
| J | Um edital em PROCESSANDO com execução registrada nunca era reenfileirado | Se o worker morresse no meio de uma tarefa, o edital ficava preso em "Processando" para sempre |
| K | Durante a implementação: a primeira versão da função que reconhece PDF aceitava um ZIP sem compressão como se fosse PDF | Detectado pelo teste e corrigido antes de qualquer uso |

## 19. Arquivos do PNCP que não são PDF (bug 4, sugestão 9, erros H e I)

**O que acontecia.** O worker pegava o primeiro arquivo da lista do PNCP, gravava no banco e tentava abrir como PDF. Órgãos publicam editais em Word, planilha e ZIP; nesses casos o processamento falhava com "Stream has ended unexpectedly", repetia 3 vezes e deixava o arquivo inválido gravado.

**O que foi feito.**

- Novo módulo [licitacoes-ws/arquivos.py](licitacoes-ws/arquivos.py), sem dependências de IA, com três funções: reconhecer um PDF pelo conteúdo, extrair o PDF de dentro de um ZIP e descrever o formato de um arquivo em linguagem comum.
- O worker agora lista os arquivos da compra, coloca primeiro os que parecem ser o edital em PDF e tenta até 5 deles. Só grava no banco o que for realmente PDF.
- Se nenhum servir, o erro diz o que foi encontrado e o que fazer. Exemplo real: "O arquivo publicado no PNCP não é um PDF (documento Word antigo (.doc)), e o sistema só lê PDF. Envie o PDF do edital manualmente pelo botão 'Enviar PDF do Edital'."
- Foi criada a exceção `ErroDefinitivo` para falhas que não se resolvem tentando de novo: formato não suportado, compra sem arquivos, PDF corrompido ou protegido, PDF sem texto (digitalização). Nesses casos o worker não repete a tarefa.
- O conteúdo gravado no banco só é reaproveitado se for um PDF. Um arquivo inválido de uma tentativa antiga é descartado (erro H).
- O upload manual passou a conferir o conteúdo do arquivo, não só a extensão, e lê no máximo o limite de 50 MB mais um byte, em vez do arquivo inteiro.
- A mensagem mostrada ao usuário é escrita para ele. Erros previstos têm texto próprio; erros inesperados recebem um texto genérico, e o detalhe técnico fica no log do worker (erro I).

**Por quê.** A falha mais comum nesse fluxo não é um defeito do sistema, e sim um arquivo que ele não lê. O usuário precisa saber disso e saber o que fazer, e o sistema não deve gastar três tentativas com algo que não vai mudar.

**Arquivos.** [licitacoes-ws/arquivos.py](licitacoes-ws/arquivos.py), [licitacoes-ws/tasks.py](licitacoes-ws/tasks.py), [licitacoes-ws/rag/edital_rag.py](licitacoes-ws/rag/edital_rag.py), [licitacoes-ws/routes/cliente_routes.py](licitacoes-ws/routes/cliente_routes.py).

**Limitação.** O sistema continua lendo apenas PDF com texto. Editais publicados só em Word (`.doc`, `.docx`) ou digitalizados precisam ser convertidos e enviados manualmente.

## 20. Edital com erro não é mais reprocessado ao abrir a página (bug 5, sugestão 10, erro J)

**O que acontecia.** Abrir a página de um edital com erro disparava o processamento de novo, sem o usuário pedir. Além disso, o edital era marcado como ERRO já na primeira falha, com as novas tentativas automáticas ainda por rodar. A tela mostrava o erro e oferecia "Tentar novamente", o que gerava cadeias de processamento em paralelo. No banco local, um único edital tinha acumulado 12 execuções e 4 notificações.

**O que foi feito.**

- Abrir a página de um edital em ERRO apenas mostra o erro. O processamento só recomeça quando o usuário clica em "Tentar novamente", que envia o novo campo `reprocessar`.
- Entre as tentativas automáticas, o edital continua como PROCESSANDO. Ele só vai para ERRO, e só gera notificação, na última tentativa ou em um erro definitivo.
- Um edital em PROCESSANDO volta a poder ser reenfileirado depois de 15 minutos parado, para cobrir o caso de o worker ter morrido no meio da tarefa (erro J). Sem execução registrada, o prazo continua sendo de 2 minutos.
- A tela guarda o identificador do edital com erro, para que o upload manual vá para o mesmo edital, e não crie outro.

**Arquivos.** [licitacoes-ws/tasks.py](licitacoes-ws/tasks.py), [licitacoes-ws/routes/cliente_routes.py](licitacoes-ws/routes/cliente_routes.py), [licitacoes-ws/schemas.py](licitacoes-ws/schemas.py), [liciteview-angular/src/app/features/edital/edital.component.ts](liciteview-angular/src/app/features/edital/edital.component.ts), [liciteview-angular/src/app/core/services/edital.service.ts](liciteview-angular/src/app/core/services/edital.service.ts).

## 21. Criação do banco do zero (bug 7, alternativa à sugestão 25)

**O que acontecia.** `alembic upgrade head` falha em banco vazio, porque a primeira migration já altera uma tabela. No PostgreSQL era preciso rodar o `script.sql` antes; no SQLite não havia caminho nenhum.

**O que foi feito.** Novo script [licitacoes-ws/criar_banco.py](licitacoes-ws/criar_banco.py). Em um banco vazio, ele cria todas as tabelas a partir dos modelos, marca o banco como atualizado no Alembic e carrega a tabela ANTT. Funciona em SQLite e PostgreSQL. Se o banco já tiver tabelas do sistema, ele não altera nada e orienta a usar `alembic upgrade head`. O README do backend foi atualizado com os dois caminhos.

**Por quê não uma migration inicial, como a sugestão 25 propunha.** Uma migration inicial teria de reproduzir o esquema antigo, anterior às migrations que já existem, e os bancos em uso teriam de ser remarcados. O script resolve o problema prático sem mexer no histórico de migrations.

**Limitação.** O banco criado pelo script não tem os extras que só existem no `script.sql`: os gatilhos que atualizam `atualizado_em` no PostgreSQL e alguns índices. O código já atualiza esse campo por conta própria, então o funcionamento não muda.

## Como o lote 4 foi verificado

**Testes do backend**, executando a tarefa do worker de verdade, com download real do PNCP e a IA simulada:

| Cenário | Resultado |
| --- | --- |
| Compra real cujo único arquivo é um `.doc`, com o `.doc` antigo gravado no banco | ERRO com a mensagem nova; **1** execução (antes: 3); nenhuma chamada à IA; arquivo inválido descartado |
| Compra real com PDF (Carmo do Cajuru) | PROCESSADO; PDF de 900 KB baixado e gravado |
| IA falha ao gerar um bloco | 3 tentativas, **1** notificação só no fim, mensagem amigável |
| Erro inesperado com uma URL de banco na mensagem | Mensagem genérica na tela; a URL não aparece |
| Upload antigo cujo conteúdo não é PDF | Erro definitivo, 1 execução |
| Abrir edital em ERRO | Devolve ERRO, nenhuma tarefa; com `reprocessar`, enfileira |
| Upload de `.doc` renomeado para `.pdf` | 400 "O arquivo enviado não é um PDF válido." |
| Upload de PDF válido | Aceito |
| ZIP com e sem compressão, com o PDF em qualquer posição | PDF interno extraído nos quatro casos |
| `criar_banco.py` em banco vazio | 13 tabelas, banco marcado na revisão `004`, 24 linhas ANTT; segunda execução não altera nada |

**Teste pela interface**, com o sistema real e a compra `15023930000138-1-000118/2026`, a mesma que falhou em 01/10:

| Passo | Resultado |
| --- | --- |
| Abrir a página do edital que já tinha falhado | 1 chamada, resposta ERRO, sem polling: não reprocessou |
| Clicar em "Tentar novamente" | Reprocessou; em cerca de 10 segundos a tela mostrou a mensagem nova, explicando que o arquivo é um Word |
| Enviar um PDF pelo botão indicado na mensagem | Foi para o mesmo edital, e o resumo apareceu na tela |

Sem erros HTTP nem no console. O frontend compila sem erros. Ao final, o edital de teste foi devolvido ao estado de erro e a conta de teste foi removida.

## Situação dos bancos após o lote 4

Este lote não alterou a estrutura do banco. Não há migration nova, e o Neon não precisou de nenhuma ação.

---

# Lote 5 — Persistência na tela e edição de produto (05/10/2026)

A análise de viabilidade e a conversa do chat eram gravadas no banco, mas a tela não tinha como lê-las de volta: ao recarregar a página, as duas sumiam. Este lote implementa a sugestão 26 do relatório e fecha três diferenças em relação à documentação do projeto: histórico do chat consultável, análise persistente e edição de produto.

## Erros encontrados neste lote

| # | Erro | Consequência |
| --- | --- | --- |
| L | Os detalhes do cálculo acrescentados no lote 2 (quantidade, origem, rota, avisos) só existiam na resposta da API, não no banco | Mesmo com uma rota de leitura, a tela recarregada mostraria a análise sem o aviso de "produto não localizado" |
| M | O histórico não trazia nenhuma informação da análise de viabilidade | A documentação descreve o histórico como lista de análises com classificação; a tela só mostrava o status do resumo |

## 22. Análise de viabilidade continua na tela após recarregar (sugestão 26, erro L)

**O que foi feito.**

- A tabela `analise_viabilidade` ganhou cinco colunas (migration `005`): quantidade considerada, origem da quantidade, UF de origem, UF de destino e avisos. A análise passa a ser devolvida direto do banco, com todos os campos.
- Nova rota `GET /cliente/editais/{id}/analise`: devolve a análise mais recente do usuário para o edital, ou vazio se não houver. Só considera produtos ativos, porque a tela precisa do produto para exibir o resultado.
- A aba de viabilidade busca essa análise assim que o edital é identificado, e seleciona no campo de produto o que foi usado.

**Arquivos.** [licitacoes-ws/models.py](licitacoes-ws/models.py), [licitacoes-ws/schemas.py](licitacoes-ws/schemas.py), [licitacoes-ws/routes/cliente_routes.py](licitacoes-ws/routes/cliente_routes.py), [licitacoes-ws/alembic/versions/005_add_detalhes_analise.py](licitacoes-ws/alembic/versions/005_add_detalhes_analise.py), [liciteview-angular/src/app/core/services/analise.service.ts](liciteview-angular/src/app/core/services/analise.service.ts), [liciteview-angular/src/app/features/edital/viabilidade-tab.component.ts](liciteview-angular/src/app/features/edital/viabilidade-tab.component.ts).

**Limitação.** Análises feitas antes deste lote não têm os campos novos. Na tela, elas aparecem sem a quantidade e sem a rota no cartão de frete, até serem refeitas com "Reanalisar". No Neon não havia nenhuma análise gravada, então isso só afeta bancos locais.

## 23. Conversa do chat continua na tela após recarregar (sugestão 26)

**O que foi feito.** Nova rota `GET /cliente/editais/{id}/perguntas`, que devolve as perguntas já respondidas do usuário sobre o edital, em ordem. A aba de chat carrega esse histórico ao abrir e o exibe depois da saudação.

**Arquivos.** [licitacoes-ws/routes/cliente_routes.py](licitacoes-ws/routes/cliente_routes.py), [liciteview-angular/src/app/core/services/edital.service.ts](liciteview-angular/src/app/core/services/edital.service.ts), [liciteview-angular/src/app/features/edital/chat-tab.component.ts](liciteview-angular/src/app/features/edital/chat-tab.component.ts).

**Limitações.** São devolvidas no máximo 100 perguntas por edital. Perguntas que falharam não aparecem. O chat continua sem memória entre perguntas: cada uma é respondida isoladamente, sem considerar as anteriores.

## 24. Histórico mostra a classificação de viabilidade (erro M)

**O que foi feito.** A rota do histórico passou a devolver a classificação da análise mais recente do usuário em cada edital, e a tela ganhou a coluna "Viabilidade".

**Arquivos.** [licitacoes-ws/routes/cliente_routes.py](licitacoes-ws/routes/cliente_routes.py), [liciteview-angular/src/app/features/historico/historico.component.ts](liciteview-angular/src/app/features/historico/historico.component.ts), [liciteview-angular/src/app/core/models/licitacao.model.ts](liciteview-angular/src/app/core/models/licitacao.model.ts).

**O que continua diferente da documentação.** O histórico é uma lista de editais com a classificação mais recente, não uma lista de análises com data e produto.

## 25. Edição de produto

**O que acontecia.** O botão de lápis na lista de produtos existia, mas não tinha ação. Para corrigir um custo era preciso excluir o produto e cadastrar de novo, e isso desvinculava as análises já feitas.

**O que foi feito.** Nova rota de tela `produtos/:id/editar`, que usa o mesmo formulário do cadastro, preenchido com os dados do produto. O botão de lápis leva a ela, e salvar chama a rota de atualização que já existia no backend.

**Arquivos.** [liciteview-angular/src/app/app.routes.ts](liciteview-angular/src/app/app.routes.ts), [liciteview-angular/src/app/features/produtos/produto-form.component.ts](liciteview-angular/src/app/features/produtos/produto-form.component.ts), [liciteview-angular/src/app/features/produtos/produtos-list.component.ts](liciteview-angular/src/app/features/produtos/produtos-list.component.ts).

**Limitação.** O formulário não tem os campos categoria, NCM e capacidade mensal, que existem no banco. Editar um produto não altera as análises já feitas com ele; é preciso reanalisar.

## Como o lote 5 foi verificado

**Testes do backend**, num banco descartável:

| Cenário | Resultado |
| --- | --- |
| Edital sem análise e sem perguntas | Análise vazia; lista de perguntas vazia |
| Análise lida de volta | Igual à resposta original em todos os campos, incluindo avisos, quantidade e rota |
| Duas perguntas feitas | Devolvidas em ordem, com as respostas |
| Histórico | Traz a classificação da análise e a UF do edital |
| Outro usuário | 404 para a análise e para as perguntas; 401 sem login |
| Análise antiga, sem os campos novos | Lida sem erro, com avisos vazios |
| Editar produto | Dados atualizados |
| Produto excluído | A análise dele deixa de ser devolvida |

**Teste pela interface**, com o sistema real:

| Passo | Resultado |
| --- | --- |
| Analisar viabilidade, fazer uma pergunta e recarregar a página (F5) | A análise reaparece com a mesma justificativa, a rota, a quantidade e o aviso, sem nova chamada de análise |
| Aba de chat após o F5 | Mostra a pergunta e a resposta anteriores, sem nova chamada à IA |
| Histórico | A coluna "Viabilidade" mostra "Atenção" |
| Clicar no lápis de um produto | Abre "Editar produto" com o formulário preenchido |
| Alterar nome e custo e salvar | A lista mostra os dados novos, com uma única linha (não duplicou) |

Sem erros HTTP nem no console. O frontend compila sem erros. A conta de teste foi removida ao final.

## Situação dos bancos após o lote 5

- **SQLite local:** migration `005` aplicada com `alembic upgrade head`.
- **PostgreSQL do projeto (Neon):** migration `005` aplicada. São cinco colunas que aceitam valor vazio; o backend antigo não as usa e continua funcionando. A estrutura foi comparada com os modelos e não há diferenças.

---

# Lote 6 — Qualidade da busca, do resumo e da viabilidade (05/10/2026)

Este lote começou pela sugestão 19 do relatório (trocar o modelo de embeddings) e terminou em outro lugar, porque a medição mostrou que o problema principal não era o modelo. Implementa as sugestões 20 e 22 (em parte), avalia e descarta a 19, e redesenha a análise de viabilidade a partir de uma observação da usuária.

## Medição que orientou o lote

Foram escritas 14 perguntas factuais sobre o edital real de Carmo do Cajuru (44 páginas), cada uma com a expressão que precisa aparecer no trecho recuperado. Todas as respostas existem no texto.

**Só a busca, sem reordenação** (acertos entre os 5 primeiros trechos):

| Configuração | Busca vetorial | Busca por palavras |
| --- | --- | --- |
| Modelo atual, trechos de 450 palavras | 6 de 14 | 13 de 14 |
| Modelo atual, trechos de 200 | 4 de 14 | 12 de 14 |
| Modelo multilíngue, trechos de 200 | 6 de 14 | 12 de 14 |
| Modelo multilíngue, trechos de 120 | 8 de 14 | 11 de 14 |

**De ponta a ponta, com o reordenador Cohere real** (resposta presente no contexto final):

| Configuração | Resultado |
| --- | --- |
| Como estava: 15 candidatos vetoriais, reordena 5 | 9 de 14 |
| Híbrida: 12 vetoriais + 12 por palavras, modelo atual, trechos de 450 | 14 de 14 |
| Híbrida, modelo atual, trechos de 200 | 14 de 14 |
| Híbrida, modelo multilíngue, trechos de 200 | 14 de 14 |

**Conclusões.**

- O sistema deixava de recuperar a resposta em 5 das 14 perguntas, e nesses casos a resposta nem estava entre os candidatos enviados ao reordenador.
- Acrescentar a busca por palavras resolve as 14, inclusive nas coleções já existentes.
- Trocar o modelo de embeddings não mudou o resultado da busca híbrida. Ele seria mais pesado (220 MB contra 90 MB) e obrigaria a reprocessar todos os editais.

**Ressalva.** As perguntas foram escritas por quem tinha o texto do edital à vista, o que favorece a busca por palavras. Perguntas com vocabulário diferente do edital dependem mais da busca vetorial, que continua fazendo parte dos candidatos. A medição usou um único edital.

## Erros encontrados neste lote

| # | Erro | Consequência |
| --- | --- | --- |
| N | A busca só usava semelhança vetorial, com um modelo treinado em inglês | Em 5 de 14 perguntas factuais a resposta não chegava ao contexto do chat. A busca do item na viabilidade também falhava por isso |
| O | O contexto de cada bloco do resumo era cortado em 4.500 caracteres, com trechos de 450 palavras | Só cabia cerca de um trecho e meio dos quatro recuperados |
| P | O modelo de IA devolvia o bloco vazio mesmo com a informação no trecho | No edital de teste, o bloco de riscos veio vazio com 4 dos 5 trechos falando de multas. O prompt mostrava o molde vazio e o modelo o repetia |
| Q | O chat às vezes devolvia resposta vazia, que era gravada como respondida | O modelo gastava toda a saída raciocinando. Reproduzido: 1 de 2 chamadas idênticas veio vazia |
| R | Um reprocessamento com menos trechos deixava trechos antigos na coleção do Qdrant | Trechos de versões diferentes do texto misturados na busca |
| S | A tela de viabilidade pedia o "valor estimado do lote/item" e usava esse valor como receita | A análise não respondia à pergunta do usuário (vale a pena vender meu produto pelo meu preço?) e ignorava o preço do cadastro |
| T | Quando o limite diário da IA era atingido, o chat mostrava um erro genérico | O usuário não sabia que bastava esperar |

## 26. Busca híbrida (erro N; sugestão 19 avaliada e não adotada)

**O que foi feito.** A busca de trechos passou a juntar duas listas de candidatos: os 12 mais próximos pela busca vetorial e os 12 mais relevantes por correspondência de palavras (BM25, calculado em memória sobre os trechos do edital). Os candidatos são reordenados pelo Cohere Rerank. Se o Cohere estiver indisponível, vale a ordem intercalada, com a busca por palavras primeiro.

**Por quê.** Ver a medição acima. A busca por palavras não exige nenhuma dependência nova nem mudança no Qdrant: um edital tem de dezenas a poucas centenas de trechos, que são lidos da coleção e mantidos em memória por 5 minutos.

**O modelo de embeddings não foi trocado.** A sugestão 19 foi testada e não trouxe ganho mensurável na busca híbrida.

**Efeito nos editais já processados.** Nenhum reprocessamento é necessário. A coleção existente do edital de teste passou de 9 para 14 acertos em 14 só com a mudança no código.

**Arquivo.** [licitacoes-ws/rag/edital_rag.py](licitacoes-ws/rag/edital_rag.py), funções `buscar_trechos`, `_ordenar_por_palavras` e `_reordenar`.

## 27. Trechos menores e contexto medido em palavras (erro O)

**O que foi feito.**

- Novos editais são divididos em trechos de 200 palavras com sobreposição de 40 (antes: 450 e 75).
- O contexto enviado à IA passou a ser limitado em palavras, não em número de trechos: 2.250 no chat (o mesmo volume de antes) e 1.000 em cada bloco do resumo. Assim a busca funciona igual com as coleções antigas e com as novas.
- O limite de caracteres do contexto do resumo subiu de 4.500 para 7.000.

**Por quê.** Com trechos menores, cada bloco do resumo recebe cinco passagens distintas em vez de uma e meia, pelo mesmo custo.

## 28. Página do edital na resposta do chat (sugestão 20)

**O que foi feito.** A extração do PDF passou a guardar de que página veio cada palavra. Cada trecho registra a página inicial e a final, no Qdrant e na tabela `chunk_edital`. O chat devolve a página do trecho mais relevante, e a tela mostra "Página 24 do edital" ou "Páginas 24–25 do edital".

**Limitações.**

- Editais processados antes deste lote não têm a página; a tela continua mostrando "Trecho do edital" para eles.
- A página citada é a do trecho mais relevante, não necessariamente a de cada frase da resposta. Um trecho pode atravessar a quebra de página, por isso a tela cita o intervalo.
- No histórico do chat, só a página inicial é guardada; a tela mostra "A partir da página N".

## 29. Resumo: prompt que descreve cada campo (erro P)

**O que foi feito.** O prompt de cada bloco deixou de mostrar o molde vazio do JSON. Agora ele lista os campos um a um, com o tipo esperado e o que cada um deve conter, e pede lista vazia só quando o trecho não tratar do assunto.

**Resultado no edital de teste** (51 páginas), campos preenchidos por bloco:

| Bloco | Antes | Depois |
| --- | --- | --- |
| Visão geral | 5 de 5 | 5 de 5 |
| Prazos | 2 de 4 | 3 de 4 |
| Documentação | 2 de 3 | 3 de 3 |
| Requisitos técnicos | 3 de 4 | 3 de 4 |
| Riscos | 0 de 4 | 4 de 4 |

É uma execução de cada lado, então o ganho exato pode variar; o bloco de riscos vazio, porém, foi reproduzido duas vezes com o prompt antigo.

## 30. Chat: resposta vazia e limite da IA (erros Q e T)

- O chat passou a usar o mesmo esforço de raciocínio baixo das outras chamadas e tenta de novo, até 3 vezes, quando a resposta vem vazia. Se continuar vazia, a pergunta é registrada como erro, não como respondida.
- Quando o provedor de IA recusa por limite de uso, o chat mostra "O limite de uso da IA foi atingido. Aguarde alguns minutos e tente novamente." O processamento de edital mostra mensagem equivalente.

## 31. Coleção recriada a cada processamento (erro R)

A coleção do edital no Qdrant é apagada e criada de novo no início de cada processamento, em vez de ter os trechos sobrescritos.

## 32. Viabilidade redesenhada em torno do preço do produto (erro S; parte da sugestão 22)

**A pergunta que a análise responde agora:** vale a pena vender este produto, pelo preço do meu cadastro, neste edital?

**O que acontecia.** A tela pedia um "Valor estimado do lote/item" e o usava como receita. O preço de venda cadastrado no produto só servia para estimar a quantidade. Com a busca híbrida, o sistema passou a encontrar o item no edital (quantidade e valor unitário estimado), e o campo de valor deixou de fazer sentido.

**Como ficou o cálculo.**

1. **Seu preço**: o preço de venda do cadastro. Se o produto não tiver preço, ele é calculado pelo custo e pela margem mínima.
2. **Quantidade**: a que o usuário informar; senão a do item encontrado no edital; senão a quantidade geral do resumo; em último caso, uma estimativa pelo valor total do edital, com aviso.
3. **Preço considerado**: o seu preço, limitado pelo valor unitário estimado do item no edital, que é o máximo aceito pelo órgão. Se o seu preço estiver acima, a análise usa o valor do edital e avisa.
4. **Receita** = quantidade × preço considerado. O restante (custo, impostos, frete, margem) não mudou.

**O que mudou na tela.**

- O campo "Valor estimado do lote/item" foi substituído por "Quantidade (opcional)".
- O resultado mostra uma faixa com seu preço, o valor estimado no edital e o preço considerado.
- Se o produto não for encontrado e o edital não tiver valor total, a tela pede a quantidade em vez de calcular com dados inventados.

**Classificação.** "Vale a pena" exige que a quantidade e o valor do item venham do edital ou do usuário. Sem o valor estimado do item, o resultado fica em "Atenção", porque não se sabe se o preço está dentro do máximo aceito.

**Mudança no banco.** A análise ganhou duas colunas (migration `006`): preço considerado e valor unitário do edital.

**Arquivos.** [licitacoes-ws/routes/cliente_routes.py](licitacoes-ws/routes/cliente_routes.py), [licitacoes-ws/schemas.py](licitacoes-ws/schemas.py), [licitacoes-ws/models.py](licitacoes-ws/models.py), [licitacoes-ws/alembic/versions/006_add_preco_analise.py](licitacoes-ws/alembic/versions/006_add_preco_analise.py), [liciteview-angular/src/app/features/edital/viabilidade-tab.component.ts](liciteview-angular/src/app/features/edital/viabilidade-tab.component.ts), [liciteview-angular/src/app/core/services/analise.service.ts](liciteview-angular/src/app/core/services/analise.service.ts).

**O que não foi feito da sugestão 22.** O imposto continua incidindo sobre o custo, não sobre a receita.

## Como o lote 6 foi verificado

**Busca implementada**, com o reordenador real:

| Cenário | Resultado |
| --- | --- |
| Coleção já existente (trechos de 450, sem reprocessar) | Resposta no contexto em 14 de 14 perguntas |
| Coleção nova (trechos de 200, com página) | 14 de 14; 122 trechos indexados em 9 segundos |
| Busca do item na viabilidade | "Armário de aço": 10 unidades a R$ 1.589,67. "Cadeira de alimentação": 20 a R$ 343,00. Os dois conferidos no PDF. "Ventilador": não encontrado, o que está correto |

**Cálculo de viabilidade**, num banco descartável:

| Cenário | Resultado |
| --- | --- |
| Preço do cadastro abaixo do valor do edital | Usa o seu preço e informa quanto está abaixo |
| Preço do cadastro acima do valor do edital | Usa o valor do edital e avisa |
| Usuário informa a quantidade | A quantidade informada prevalece |
| Produto sem preço de venda | Preço calculado pelo custo e pela margem mínima, com a explicação |
| Item encontrado sem valor estimado | "Atenção", com aviso |
| Produto não localizado, edital sem valor total | Erro 422 pedindo a quantidade |
| Produto não localizado, edital com valor total | Quantidade estimada, "Atenção", com aviso |

Os testes dos lotes anteriores foram repetidos após as mudanças, sem regressão.

**Teste pela interface**, com o sistema real:

| Passo | Resultado |
| --- | --- |
| Viabilidade no edital de Carmo do Cajuru, produto "Armário de aço" a R$ 1.500, sem informar nada | Encontrou o item (10 un., R$ 1.589,67), usou o preço do cadastro e explicou: 5,6% abaixo do valor do edital, margem de 9,8%, abaixo da mínima de 15% por causa do frete |
| Chat sobre o mesmo item | Respondeu a quantidade e o valor unitário corretos |
| Processar um edital novo de 51 páginas | Processado em 83 segundos, 167 trechos com página, resumo com 18 de 20 campos |
| Chat no edital novo | **Não concluído**: o limite diário da IA foi atingido durante o teste |

**O que ficou sem verificação na tela:** a citação com intervalo de páginas ("Páginas 24–25") e a mensagem de limite da IA. A citação de página única apareceu na tela em uma execução anterior; as páginas gravadas foram conferidas no banco (de 1 a 51 nos 167 trechos).

## Limite diário da IA

O plano gratuito da Groq permite 200.000 tokens por dia para o modelo em uso. Os testes de hoje consumiram essa cota. Processar um edital custa na ordem de 10.000 a 15.000 tokens, e cada pergunta do chat cerca de 4.000, então o plano gratuito comporta poucas dezenas de operações por dia. É uma restrição relevante para uma demonstração.

## Situação dos bancos após o lote 6

- **SQLite local:** migration `006` aplicada.
- **PostgreSQL do projeto (Neon):** migration `006` aplicada. São duas colunas que aceitam valor vazio.
- **Qdrant:** nenhuma coleção existente foi alterada. Editais antigos continuam com trechos de 450 palavras e sem página, e funcionam com a busca nova.

## O que continua em aberto

- **A medição de busca usou um único edital e perguntas escritas por quem conhecia o texto.** O script `avaliar_rag.py` do projeto poderia ser atualizado com esse conjunto e rodado em mais editais.
- **A busca vetorial continua fraca em português.** Ela pesa menos agora, mas um modelo multilíngue de recuperação seria o próximo passo se perguntas com vocabulário diferente do edital falharem.
- **A extração do item depende da IA.** Ela acertou nos três casos testados, mas pode errar em tabelas com layout diferente; a tela mostra os valores usados para o usuário conferir.
- **O imposto incide sobre o custo**, e o frete assume sempre caminhão de 2 eixos e distância entre capitais.

---

# Lote 7 — Documentação do projeto (05/10/2026)

## 33. Documentação técnica, READMEs e arquivo de exemplo de configuração

**O que acontecia.** A documentação técnica (PDF de maio de 2026) e os READMEs descreviam um sistema diferente do que o código fazia, como listado na seção 3 do relatório, e ficaram ainda mais distantes depois dos lotes 1 a 6. O fonte do PDF (um arquivo LaTeX citado na própria documentação) não está no repositório, então o PDF original não podia ser regerado.

**O que foi feito.**

- **Nova documentação técnica** em [docs/documentacao-tecnica.md](docs/documentacao-tecnica.md), com a mesma estrutura da anterior (introdução, arquitetura, tecnologias, modelo de dados, pipeline de IA, referência da API, infraestrutura, testes, decisões técnicas, resultados, manual do usuário, roadmap e referências), reescrita para o estado atual do código. Ganhou as seções "Limitações conhecidas" e "Histórico de revisões".
- **PDF** da nova documentação em [docs/documentacao-tecnica.pdf](docs/documentacao-tecnica.pdf), com 23 páginas, gerado a partir do Markdown.
- **README do backend** reescrito: serviços necessários, criação do banco, scripts de manutenção, estrutura atual e uma seção de solução de problemas com os erros que apareceram na prática.
- **README do frontend** atualizado: rotas, a questão da porta e do CORS, e a situação dos testes.
- **README na raiz** do repositório, que não existia, apontando para os componentes e os documentos.
- **`.env.example`** completo, com `REDIS_URL`, `COHERE_API_KEY`, `START_CELERY_WORKER` e a opção de SQLite, que faltavam.

O PDF original (`documentacao-liciteview.pdf`) foi mantido, sem alteração, como versão anterior.

**Cuidados na redação.**

- A documentação avisa, logo no início, que descreve o código do repositório, ainda não publicado em produção.
- A infraestrutura de produção (Google Cloud, Render, Nginx, DuckDNS) foi reproduzida da versão anterior e está marcada como não reverificada.
- As métricas de produção da versão anterior (tempo de build, tamanho da imagem, memória dos containers) não foram repetidas, porque não foram refeitas. As medições novas vêm de execuções únicas em ambiente de desenvolvimento, e isso está dito no texto.
- A seção de testes diz que não há suíte automatizada no repositório. A versão anterior descrevia uma cobertura de testes que não podia ser executada.
- O bloco "Acesso ao sistema" da versão anterior, que trazia um usuário e uma senha de produção, não foi reproduzido.

**Diferença de formato.** O PDF novo foi gerado a partir de Markdown, não de LaTeX. Ele não tem capa, sumário nem numeração de páginas, e o diagrama de arquitetura é em texto. Os diagramas de sequência e o diagrama entidade-relacionamento da versão anterior foram substituídos por listas e tabelas.

**Pendência.** Se o grupo tiver o arquivo LaTeX original, o conteúdo de `docs/documentacao-tecnica.md` pode ser levado para ele, para manter o padrão visual da versão anterior.
