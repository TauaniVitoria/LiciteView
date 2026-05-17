-- ============================================================
-- LiciteView — Schema PostgreSQL MVP (versão simplificada)
-- Portaria SUROC Nº 3, de 13/03/2026 (tabela ANTT vigente)
-- Simplificações aplicadas:
--   - vetor_chunk mesclado em chunk_edital
--   - resposta_pergunta mesclada em pergunta_edital
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- ── Enums ───────────────────────────────────────────────────

CREATE TYPE perfil_usuario AS ENUM ('ADMIN','FORNECEDOR');

CREATE TYPE categoria_produto AS ENUM (
    'MEDICAMENTO','MATERIAL_HOSPITALAR','EQUIPAMENTO','SERVICO','OUTRO'
);

CREATE TYPE status_processamento AS ENUM (
    'PENDENTE','PROCESSANDO','PROCESSADO','ERRO'
);

CREATE TYPE embedding_status AS ENUM ('PENDENTE','GERADO','ERRO');

CREATE TYPE status_pergunta AS ENUM ('PENDENTE','RESPONDIDA','ERRO');

CREATE TYPE classificacao_viabilidade AS ENUM (
    'VALE_A_PENA','ATENCAO','NAO_RECOMENDADO'
);

CREATE TYPE tipo_processo AS ENUM (
    'INGESTAO_PDF','SEGMENTACAO','EMBEDDING','RESUMO',
    'EXTRACAO_VARIAVEIS','ANALISE_VIABILIDADE','RESPOSTA_PERGUNTA'
);

CREATE TYPE status_execucao AS ENUM (
    'PENDENTE','EXECUTANDO','SUCESSO','ERRO','RETRY'
);

-- ============================================================
-- TABELAS
-- ============================================================

-- ── 1. Usuario ──────────────────────────────────────────────
-- Concentra autenticação e perfil comercial em uma entidade só
CREATE TABLE usuario (
    id            UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    nome          VARCHAR(255) NOT NULL,
    email         VARCHAR(255) NOT NULL,
    senha_hash    VARCHAR(255) NOT NULL,
    razao_social  VARCHAR(255) NOT NULL,
    cnpj          VARCHAR(18)  NOT NULL,
    cep           VARCHAR(9)   NOT NULL,
    cidade        VARCHAR(255),
    uf            CHAR(2),
    perfil        perfil_usuario NOT NULL DEFAULT 'FORNECEDOR',
    ativo         BOOLEAN      NOT NULL DEFAULT TRUE,
    criado_em     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_usuario_email UNIQUE (email),
    CONSTRAINT uq_usuario_cnpj  UNIQUE (cnpj),
    CONSTRAINT ck_usuario_cnpj  CHECK (cnpj ~ '^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$'),
    CONSTRAINT ck_usuario_cep   CHECK (cep ~ '^\d{5}-\d{3}$')
);

CREATE INDEX idx_usuario_email ON usuario (email);
CREATE INDEX idx_usuario_cnpj  ON usuario (cnpj);

-- ── 2. Produto ──────────────────────────────────────────────
-- Item ofertado pelo usuário com preço, custo e margem mínima
CREATE TABLE produto (
    id            UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id    UUID          NOT NULL,
    nome          VARCHAR(255)  NOT NULL,
    descricao     TEXT,
    categoria     categoria_produto NOT NULL DEFAULT 'OUTRO',
    ncm           VARCHAR(10),
    preco_venda   NUMERIC(15,4) NOT NULL,
    custo_produto NUMERIC(15,4) NOT NULL,
    margem_minima NUMERIC(5,4)  NOT NULL,  -- ex: 0.15 = 15%
    peso_kg       NUMERIC(10,4) NOT NULL,
    ativo         BOOLEAN       NOT NULL DEFAULT TRUE,
    criado_em     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_produto_usuario FOREIGN KEY (usuario_id)
        REFERENCES usuario (id) ON DELETE CASCADE,
    CONSTRAINT ck_produto_preco   CHECK (preco_venda > 0),
    CONSTRAINT ck_produto_custo   CHECK (custo_produto > 0),
    CONSTRAINT ck_produto_margem  CHECK (margem_minima >= 0 AND margem_minima <= 1),
    CONSTRAINT ck_produto_peso    CHECK (peso_kg > 0)
);

CREATE INDEX idx_produto_usuario_id ON produto (usuario_id);
CREATE INDEX idx_produto_categoria  ON produto (categoria);
CREATE INDEX idx_produto_ativo      ON produto (ativo) WHERE ativo = TRUE;

-- ── 3. Edital ───────────────────────────────────────────────
-- Documento oficial da licitação obtido via PNCP
CREATE TABLE edital (
    id                   UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    id_pncp              VARCHAR(100)  NOT NULL,
    titulo               VARCHAR(500),
    orgao                VARCHAR(500)  NOT NULL,
    numero               VARCHAR(100),
    modalidade           VARCHAR(100),
    objeto               TEXT          NOT NULL,
    valor_estimado       NUMERIC(18,4),
    data_publicacao      DATE,
    data_abertura        DATE,
    url_origem           VARCHAR(1000),
    url_pdf              VARCHAR(1000),  -- caminho no Google Cloud Storage
    hash_documento       VARCHAR(64),    -- detecta se o PDF mudou
    status_processamento status_processamento NOT NULL DEFAULT 'PENDENTE',
    criado_em            TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    atualizado_em        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_edital_id_pncp UNIQUE (id_pncp)
);

CREATE INDEX idx_edital_id_pncp              ON edital (id_pncp);
CREATE INDEX idx_edital_status_processamento ON edital (status_processamento);
CREATE INDEX idx_edital_data_abertura        ON edital (data_abertura);
CREATE INDEX idx_edital_orgao  ON edital USING gin (to_tsvector('portuguese', orgao));
CREATE INDEX idx_edital_objeto ON edital USING gin (to_tsvector('portuguese', objeto));

-- ── 4. SecaoEdital ──────────────────────────────────────────
-- Seções extraídas pelo Docling antes do chunking
CREATE TABLE secao_edital (
    id             UUID     PRIMARY KEY DEFAULT uuid_generate_v4(),
    edital_id      UUID     NOT NULL,
    titulo         VARCHAR(500),
    ordem          INTEGER  NOT NULL,
    texto_bruto    TEXT     NOT NULL,
    chunk_tokens   INTEGER,
    pagina_inicial INTEGER,
    pagina_final   INTEGER,

    CONSTRAINT fk_secao_edital  FOREIGN KEY (edital_id)
        REFERENCES edital (id) ON DELETE CASCADE,
    CONSTRAINT ck_secao_paginas CHECK (
        pagina_final IS NULL OR pagina_final >= pagina_inicial
    )
);

CREATE INDEX idx_secao_edital_id ON secao_edital (edital_id);
CREATE INDEX idx_secao_ordem     ON secao_edital (edital_id, ordem);

-- ── 5. ChunkEdital ──────────────────────────────────────────
-- Fragmento semântico do edital
-- Inclui referência ao vetor no Qdrant (mesclado de vetor_chunk)
CREATE TABLE chunk_edital (
    id               UUID     PRIMARY KEY DEFAULT uuid_generate_v4(),
    edital_id        UUID     NOT NULL,
    secao_id         UUID,
    ordem            INTEGER  NOT NULL,
    texto            TEXT     NOT NULL,
    tokens           INTEGER  NOT NULL,
    pagina_inicial   INTEGER,
    pagina_final     INTEGER,
    hash_chunk       VARCHAR(64),
    -- status do embedding (controle do Celery)
    embedding_status embedding_status NOT NULL DEFAULT 'PENDENTE',
    -- referência ao vetor no Qdrant (antes era tabela separada)
    qdrant_point_id  VARCHAR(100),   -- ID do ponto no Qdrant
    embedding_model  VARCHAR(100),   -- modelo usado para gerar o vetor
    criado_em        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_chunk_edital FOREIGN KEY (edital_id)
        REFERENCES edital (id) ON DELETE CASCADE,
    CONSTRAINT fk_chunk_secao  FOREIGN KEY (secao_id)
        REFERENCES secao_edital (id) ON DELETE SET NULL,
    CONSTRAINT ck_chunk_tokens CHECK (tokens > 0)
);

CREATE INDEX idx_chunk_edital_id        ON chunk_edital (edital_id);
CREATE INDEX idx_chunk_secao_id         ON chunk_edital (secao_id);
CREATE INDEX idx_chunk_embedding_status ON chunk_edital (embedding_status);
CREATE INDEX idx_chunk_ordem            ON chunk_edital (edital_id, ordem);

-- ── 6. ResumoEdital ─────────────────────────────────────────
-- Resumo estruturado gerado pelo pipeline de IA (5 blocos temáticos)
CREATE TABLE resumo_edital (
    id            UUID     PRIMARY KEY DEFAULT uuid_generate_v4(),
    edital_id     UUID     NOT NULL,
    versao        INTEGER  NOT NULL DEFAULT 1,
    json_resumo   JSONB    NOT NULL,  -- objeto/prazos/documentos/requisitos/riscos
    modelo_usado  VARCHAR(100),
    versao_prompt VARCHAR(50),
    ativo         BOOLEAN  NOT NULL DEFAULT TRUE,
    gerado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_resumo_edital FOREIGN KEY (edital_id)
        REFERENCES edital (id) ON DELETE CASCADE
);

CREATE INDEX idx_resumo_edital_id ON resumo_edital (edital_id);
CREATE INDEX idx_resumo_ativo     ON resumo_edital (edital_id, ativo)
    WHERE ativo = TRUE;
CREATE INDEX idx_resumo_json      ON resumo_edital USING gin (json_resumo);

-- ── 7. VariavelViabilidade ──────────────────────────────────
-- Variáveis tipadas extraídas pelo LLM para alimentar o cálculo
CREATE TABLE variavel_viabilidade (
    id             UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    edital_id      UUID         NOT NULL,
    nome_variavel  VARCHAR(100) NOT NULL,  -- ex: prazo_dias, cep_entrega
    valor_extraido TEXT         NOT NULL,
    unidade        VARCHAR(50),
    confianca      NUMERIC(4,3),
    modelo_usado   VARCHAR(100),
    gerado_em      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_variavel_edital    FOREIGN KEY (edital_id)
        REFERENCES edital (id) ON DELETE CASCADE,
    CONSTRAINT ck_variavel_confianca CHECK (
        confianca IS NULL OR (confianca >= 0 AND confianca <= 1)
    )
);

CREATE INDEX idx_variavel_edital_id ON variavel_viabilidade (edital_id);

-- ── 8. TabelaFreteANTT ──────────────────────────────────────
-- Portaria SUROC Nº 3, 13/03/2026
-- Fórmula: custo_frete = (distancia_km × CCD) + CC
CREATE TABLE tabela_frete_antt (
    id              UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    tabela_origem   CHAR(1)      NOT NULL,   -- 'A', 'B', 'C' ou 'D'
    tipo_carga_cod  INTEGER      NOT NULL,   -- 1 a 12
    tipo_carga_nome VARCHAR(100) NOT NULL,
    coeficiente     VARCHAR(20)  NOT NULL,   -- 'CCD' (R$/km) ou 'CC' (R$ fixo)
    unidade         VARCHAR(10)  NOT NULL,
    eixos_2         NUMERIC(10,4),
    eixos_3         NUMERIC(10,4),
    eixos_4         NUMERIC(10,4),
    eixos_5         NUMERIC(10,4),
    eixos_6         NUMERIC(10,4),
    eixos_7         NUMERIC(10,4),
    eixos_9         NUMERIC(10,4),
    versao_portaria VARCHAR(50)  NOT NULL DEFAULT 'SUROC-3-2026',
    data_vigencia   DATE         NOT NULL DEFAULT '2026-03-13',
    ativo           BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_frete_tabela_carga ON tabela_frete_antt
    (tabela_origem, tipo_carga_cod, coeficiente);
CREATE INDEX idx_frete_ativo ON tabela_frete_antt (ativo) WHERE ativo = TRUE;

-- ── 9. AnaliseViabilidade ───────────────────────────────────
-- Resultado do cálculo financeiro da licitação para o produto
CREATE TABLE analise_viabilidade (
    id                     UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    edital_id              UUID          NOT NULL,
    produto_id             UUID          NOT NULL,
    usuario_id             UUID          NOT NULL,
    -- snapshots no momento do cálculo (preserva histórico)
    margem_minima_snapshot NUMERIC(5,4)  NOT NULL,
    preco_venda_snapshot   NUMERIC(15,4) NOT NULL,
    custo_produto_snapshot NUMERIC(15,4) NOT NULL,
    -- cálculos
    distancia_km           NUMERIC(10,2),
    custo_frete_estimado   NUMERIC(15,4),
    custo_total_estimado   NUMERIC(15,4),
    receita_estimada       NUMERIC(15,4),
    margem_estimada        NUMERIC(5,4),
    -- resultado
    dentro_margem          BOOLEAN       NOT NULL,
    classificacao          classificacao_viabilidade NOT NULL,
    justificativa          TEXT,
    modelo_usado           VARCHAR(100),
    versao_prompt          VARCHAR(50),
    gerado_em              TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_analise_edital  FOREIGN KEY (edital_id)
        REFERENCES edital   (id) ON DELETE CASCADE,
    CONSTRAINT fk_analise_produto FOREIGN KEY (produto_id)
        REFERENCES produto  (id) ON DELETE CASCADE,
    CONSTRAINT fk_analise_usuario FOREIGN KEY (usuario_id)
        REFERENCES usuario  (id) ON DELETE CASCADE
);

CREATE INDEX idx_analise_edital_id     ON analise_viabilidade (edital_id);
CREATE INDEX idx_analise_produto_id    ON analise_viabilidade (produto_id);
CREATE INDEX idx_analise_usuario_id    ON analise_viabilidade (usuario_id);
CREATE INDEX idx_analise_classificacao ON analise_viabilidade (classificacao);

-- ── 10. PerguntaEdital ──────────────────────────────────────
-- Pergunta do usuário + resposta gerada pelo RAG
-- (mesclado de pergunta_edital + resposta_pergunta)
-- Campos de resposta ficam NULL até serem preenchidos pelo pipeline
CREATE TABLE pergunta_edital (
    id            UUID     PRIMARY KEY DEFAULT uuid_generate_v4(),
    edital_id     UUID     NOT NULL,
    usuario_id    UUID     NOT NULL,
    -- pergunta
    pergunta      TEXT     NOT NULL,
    status        status_pergunta NOT NULL DEFAULT 'PENDENTE',
    criada_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- resposta (NULL até ser processada)
    resposta      TEXT,
    confianca     NUMERIC(4,3),
    trecho_fonte  TEXT,        -- trecho do edital usado na resposta
    pagina_fonte  INTEGER,     -- página de origem no edital
    modelo_usado  VARCHAR(100),
    respondida_em TIMESTAMPTZ,

    CONSTRAINT fk_pergunta_edital  FOREIGN KEY (edital_id)
        REFERENCES edital   (id) ON DELETE CASCADE,
    CONSTRAINT fk_pergunta_usuario FOREIGN KEY (usuario_id)
        REFERENCES usuario  (id) ON DELETE CASCADE,
    CONSTRAINT ck_pergunta_confianca CHECK (
        confianca IS NULL OR (confianca >= 0 AND confianca <= 1)
    )
);

CREATE INDEX idx_pergunta_edital_id  ON pergunta_edital (edital_id);
CREATE INDEX idx_pergunta_usuario_id ON pergunta_edital (usuario_id);
CREATE INDEX idx_pergunta_status     ON pergunta_edital (status);

-- ── 11. ExecucaoProcesso ────────────────────────────────────
-- Auditoria de cada tarefa do Celery
CREATE TABLE execucao_processo (
    id                UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
    edital_id         UUID,
    pergunta_id       UUID,
    tipo_processo     tipo_processo   NOT NULL,
    status            status_execucao NOT NULL DEFAULT 'PENDENTE',
    tentativas        INTEGER NOT NULL DEFAULT 0,
    tempo_execucao_ms BIGINT,
    worker_id         VARCHAR(200),
    erro_mensagem     TEXT,
    iniciado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finalizado_em     TIMESTAMPTZ,

    CONSTRAINT fk_execucao_edital   FOREIGN KEY (edital_id)
        REFERENCES edital         (id) ON DELETE SET NULL,
    CONSTRAINT fk_execucao_pergunta FOREIGN KEY (pergunta_id)
        REFERENCES pergunta_edital (id) ON DELETE SET NULL
);

CREATE INDEX idx_execucao_edital_id   ON execucao_processo (edital_id);
CREATE INDEX idx_execucao_pergunta_id ON execucao_processo (pergunta_id);
CREATE INDEX idx_execucao_status      ON execucao_processo (status);
CREATE INDEX idx_execucao_tipo        ON execucao_processo (tipo_processo);

-- ============================================================
-- TRIGGERS — atualizado_em automático
-- ============================================================

CREATE OR REPLACE FUNCTION set_atualizado_em()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_usuario_atualizado_em
    BEFORE UPDATE ON usuario
    FOR EACH ROW EXECUTE FUNCTION set_atualizado_em();

CREATE TRIGGER trg_produto_atualizado_em
    BEFORE UPDATE ON produto
    FOR EACH ROW EXECUTE FUNCTION set_atualizado_em();

CREATE TRIGGER trg_edital_atualizado_em
    BEFORE UPDATE ON edital
    FOR EACH ROW EXECUTE FUNCTION set_atualizado_em();

-- ============================================================
-- DADOS — Tabela ANTT Portaria SUROC Nº 3 — 13/03/2026
-- Tabela A: Lotação com contratação da composição veicular
-- ============================================================

INSERT INTO tabela_frete_antt
    (tabela_origem, tipo_carga_cod, tipo_carga_nome, coeficiente, unidade,
     eixos_2, eixos_3, eixos_4, eixos_5, eixos_6, eixos_7, eixos_9)
VALUES
('A',  1, 'Granel sólido',                       'CCD', 'R$/km', 3.9173, 5.0127,  5.6728,  6.5381,  7.2108,  7.8555,  8.9995),
('A',  1, 'Granel sólido',                       'CC',  'R$',   444.84, 533.36,  576.59,  642.10,  656.76,  792.30,  877.83),
('A',  2, 'Granel líquido',                      'CCD', 'R$/km', 3.9888, 5.1050,  5.8219,  6.7002,  7.3780,  7.9892,  9.1532),
('A',  2, 'Granel líquido',                      'CC',  'R$',   455.84, 550.10,  600.27,  669.38,  685.45,  811.76,  902.80),
('A',  3, 'Frigorificada ou Aquecida',            'CCD', 'R$/km', 4.5986, 5.8762,  6.7046,  7.6837,  8.4688,  9.3596, 10.6295),
('A',  3, 'Frigorificada ou Aquecida',            'CC',  'R$',   502.29, 601.96,  663.16,  732.07,  745.94,  949.16, 1030.58),
('A',  4, 'Conteinerizada',                      'CCD', 'R$/km',   NULL,   NULL,  4.9864,  5.6031,  6.4765,  7.1476,  8.9193),
('A',  4, 'Conteinerizada',                      'CC',  'R$',     NULL,   NULL,  526.13,  557.42,  625.16,  639.38,  855.76),
('A',  5, 'Carga Geral',                         'CCD', 'R$/km', 3.8866, 4.9762,  5.6443,  6.5126,  7.1824,  7.8952,  8.9799),
('A',  5, 'Carga Geral',                         'CC',  'R$',   436.39, 523.33,  568.72,  635.08,  648.95,  803.22,  872.44),
('A',  6, 'Neogranel',                           'CCD', 'R$/km', 3.5108, 4.9748,  5.6706,  6.5126,  7.1824,  7.8952,  8.9799),
('A',  6, 'Neogranel',                           'CC',  'R$',   436.39, 522.93,  575.96,  635.08,  648.95,  803.22,  872.44),
('A',  7, 'Perigosa (granel sólido)',             'CCD', 'R$/km', 4.6610, 5.7660,  6.4616,  7.3269,  7.9996,  8.6619,  9.8137),
('A',  7, 'Perigosa (granel sólido)',             'CC',  'R$',   587.98, 679.12,  727.28,  792.80,  807.45,  947.84, 1035.49),
('A',  8, 'Perigosa (granel líquido)',            'CCD', 'R$/km', 4.7446, 5.8704,  6.5913,  7.4697,  8.1475,  8.7763,  9.9480),
('A',  8, 'Perigosa (granel líquido)',            'CC',  'R$',   610.96, 707.85,  762.95,  832.06,  848.13,  979.29, 1072.44),
('A',  9, 'Perigosa (frigorificada ou aquecida)', 'CCD', 'R$/km', 5.1859, 6.4760,  7.3202,  8.2992,  9.0843,  9.9980, 11.2780),
('A',  9, 'Perigosa (frigorificada ou aquecida)', 'CC',  'R$',   609.31, 712.41,  780.02,  848.93,  862.80, 1072.32, 1156.49),
('A', 10, 'Perigosa (conteinerizada)',            'CCD', 'R$/km',   NULL,   NULL,  5.3576,  6.0099,  6.8832,  7.5543,  9.3513),
('A', 10, 'Perigosa (conteinerizada)',            'CC',  'R$',     NULL,   NULL,  623.38,  659.60,  727.35,  741.56,  964.90),
('A', 11, 'Perigosa (carga geral)',               'CCD', 'R$/km', 4.2483, 5.3474,  6.0510,  6.9193,  7.5891,  8.3196,  9.4120),
('A', 11, 'Perigosa (carga geral)',               'CC',  'R$',   531.01, 620.58,  670.91,  737.27,  751.14,  910.26,  981.58),
('A', 12, 'Carga Granel Pressurizada',            'CCD', 'R$/km',   NULL,   NULL,    NULL,    NULL,  6.8646,  7.5789,  9.5030),
('A', 12, 'Carga Granel Pressurizada',            'CC',  'R$',     NULL,   NULL,    NULL,    NULL,  731.90,  757.99, 1016.29);

-- ============================================================
-- FUNÇÃO — calcular_frete_antt
-- Fórmula: (distancia_km × CCD) + CC
-- Padrão MVP: 4 eixos, Carga Geral (tipo 5), Tabela A
-- Exemplo: SELECT calcular_frete_antt(500);  → R$ 3.390,87
-- ============================================================

CREATE OR REPLACE FUNCTION calcular_frete_antt(
    p_distancia_km NUMERIC,
    p_peso_kg      NUMERIC  DEFAULT 0,
    p_eixos        INTEGER  DEFAULT 4,
    p_tipo_carga   INTEGER  DEFAULT 5,
    p_tabela       CHAR     DEFAULT 'A'
)
RETURNS NUMERIC AS $$
DECLARE
    v_ccd NUMERIC;
    v_cc  NUMERIC;
BEGIN
    SELECT CASE p_eixos
        WHEN 2 THEN eixos_2 WHEN 3 THEN eixos_3 WHEN 4 THEN eixos_4
        WHEN 5 THEN eixos_5 WHEN 6 THEN eixos_6 WHEN 7 THEN eixos_7
        WHEN 9 THEN eixos_9 END
    INTO v_ccd FROM tabela_frete_antt
    WHERE tabela_origem=p_tabela AND tipo_carga_cod=p_tipo_carga
      AND coeficiente='CCD' AND ativo=TRUE;

    SELECT CASE p_eixos
        WHEN 2 THEN eixos_2 WHEN 3 THEN eixos_3 WHEN 4 THEN eixos_4
        WHEN 5 THEN eixos_5 WHEN 6 THEN eixos_6 WHEN 7 THEN eixos_7
        WHEN 9 THEN eixos_9 END
    INTO v_cc FROM tabela_frete_antt
    WHERE tabela_origem=p_tabela AND tipo_carga_cod=p_tipo_carga
      AND coeficiente='CC' AND ativo=TRUE;

    IF v_ccd IS NULL OR v_cc IS NULL THEN
        RAISE EXCEPTION 'Combinação não encontrada: tabela=%, tipo_carga=%, eixos=%',
            p_tabela, p_tipo_carga, p_eixos;
    END IF;

    RETURN ROUND((p_distancia_km * v_ccd) + v_cc, 2);
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- RESUMO DAS TABELAS
-- ============================================================
-- 1.  usuario              — autenticação + perfil do fornecedor
-- 2.  produto              — produto com custo, preço e margem mínima
-- 3.  edital               — licitação obtida via PNCP
-- 4.  secao_edital         — seções extraídas pelo Docling
-- 5.  chunk_edital         — fragmentos semânticos + referência ao Qdrant
-- 6.  resumo_edital        — resumo estruturado em JSON (5 blocos)
-- 7.  variavel_viabilidade — variáveis tipadas extraídas pelo LLM
-- 8.  tabela_frete_antt    — tabela TACO vigente (SUROC-3-2026)
-- 9.  analise_viabilidade  — resultado do cálculo financeiro
-- 10. pergunta_edital      — pergunta + resposta do RAG (mescladas)
-- 11. execucao_processo    — auditoria das tarefas do Celery
-- ============================================================