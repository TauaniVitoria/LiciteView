from __future__ import annotations

import enum
from uuid import uuid4

from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime,
    Enum, ForeignKey, Integer, Numeric, String, Text, func
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ENUMS

class PerfilUsuario(str, enum.Enum):
    ADMIN      = "ADMIN"
    FORNECEDOR = "FORNECEDOR"


class CategoriaProduto(str, enum.Enum):
    MEDICAMENTO         = "MEDICAMENTO"
    MATERIAL_HOSPITALAR = "MATERIAL_HOSPITALAR"
    EQUIPAMENTO         = "EQUIPAMENTO"
    SERVICO             = "SERVICO"
    OUTRO               = "OUTRO"


class StatusProcessamento(str, enum.Enum):
    PENDENTE    = "PENDENTE"
    PROCESSANDO = "PROCESSANDO"
    PROCESSADO  = "PROCESSADO"
    ERRO        = "ERRO"


class EmbeddingStatus(str, enum.Enum):
    PENDENTE = "PENDENTE"
    GERADO   = "GERADO"
    ERRO     = "ERRO"


class StatusPergunta(str, enum.Enum):
    PENDENTE   = "PENDENTE"
    RESPONDIDA = "RESPONDIDA"
    ERRO       = "ERRO"


class ClassificacaoViabilidade(str, enum.Enum):
    VALE_A_PENA     = "VALE_A_PENA"
    ATENCAO         = "ATENCAO"
    NAO_RECOMENDADO = "NAO_RECOMENDADO"


class TipoProcesso(str, enum.Enum):
    INGESTAO_PDF        = "INGESTAO_PDF"
    SEGMENTACAO         = "SEGMENTACAO"
    EMBEDDING           = "EMBEDDING"
    RESUMO              = "RESUMO"
    EXTRACAO_VARIAVEIS  = "EXTRACAO_VARIAVEIS"
    ANALISE_VIABILIDADE = "ANALISE_VIABILIDADE"
    RESPOSTA_PERGUNTA   = "RESPOSTA_PERGUNTA"


class StatusExecucao(str, enum.Enum):
    PENDENTE   = "PENDENTE"
    EXECUTANDO = "EXECUTANDO"
    SUCESSO    = "SUCESSO"
    ERRO       = "ERRO"
    RETRY      = "RETRY"


# MODELS

class Usuario(Base):
    __tablename__ = "usuario"

    id            = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    nome          = Column(String(255), nullable=False)
    email         = Column(String(255), nullable=False, unique=True)
    senha_hash    = Column(String(255), nullable=False)
    razao_social  = Column(String(255), nullable=False)
    cnpj          = Column(String(18), nullable=False, unique=True)
    cep           = Column(String(9), nullable=False)
    cidade        = Column(String(255))
    uf            = Column(String(2))
    perfil        = Column(Enum(PerfilUsuario, name='perfil_usuario'), nullable=False, default=PerfilUsuario.FORNECEDOR)
    ativo         = Column(Boolean, nullable=False, default=True)
    criado_em     = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    atualizado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    produtos             = relationship("Produto",            back_populates="usuario")
    analises_viabilidade = relationship("AnaliseViabilidade", back_populates="usuario")
    perguntas            = relationship("PerguntaEdital",     back_populates="usuario")


class Produto(Base):
    __tablename__ = "produto"

    id            = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    usuario_id    = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False)
    nome          = Column(String(255), nullable=False)
    descricao     = Column(Text)
    categoria     = Column(Enum(CategoriaProduto, name='categoria_produto'), nullable=False, default=CategoriaProduto.OUTRO)
    ncm           = Column(String(10))
    preco_venda   = Column(Numeric(15, 4), nullable=False)
    custo_produto = Column(Numeric(15, 4), nullable=False)
    margem_minima = Column(Numeric(5, 4), nullable=False)
    peso_kg       = Column(Numeric(10, 4), nullable=False)
    ativo         = Column(Boolean, nullable=False, default=True)
    criado_em     = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    atualizado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    usuario              = relationship("Usuario", back_populates="produtos")
    analises_viabilidade = relationship("AnaliseViabilidade", back_populates="produto")


class Edital(Base):
    __tablename__ = "edital"

    id                   = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    id_pncp              = Column(String(100), nullable=False, unique=True)
    titulo               = Column(String(500))
    orgao                = Column(String(500), nullable=False)
    numero               = Column(String(100))
    modalidade           = Column(String(100))
    objeto               = Column(Text, nullable=False)
    valor_estimado       = Column(Numeric(18, 4))
    data_publicacao      = Column(Date)
    data_abertura        = Column(Date)
    url_origem           = Column(String(1000))
    url_pdf              = Column(String(1000))
    hash_documento       = Column(String(64))
    status_processamento = Column(Enum(StatusProcessamento, name='status_processamento'), nullable=False, default=StatusProcessamento.PENDENTE)
    criado_em            = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    atualizado_em        = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    secoes               = relationship("SecaoEdital",         back_populates="edital")
    chunks               = relationship("ChunkEdital",         back_populates="edital")
    resumos              = relationship("ResumoEdital",        back_populates="edital")
    variaveis            = relationship("VariavelViabilidade", back_populates="edital")
    analises_viabilidade = relationship("AnaliseViabilidade",  back_populates="edital")
    perguntas            = relationship("PerguntaEdital",      back_populates="edital")
    execucoes            = relationship("ExecucaoProcesso",    back_populates="edital")


class SecaoEdital(Base):
    __tablename__ = "secao_edital"

    id             = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    edital_id      = Column(PGUUID(as_uuid=True), ForeignKey("edital.id", ondelete="CASCADE"), nullable=False)
    titulo         = Column(String(500))
    ordem          = Column(Integer, nullable=False)
    texto_bruto    = Column(Text, nullable=False)
    chunk_tokens   = Column(Integer)
    pagina_inicial = Column(Integer)
    pagina_final   = Column(Integer)

    edital = relationship("Edital",      back_populates="secoes")
    chunks = relationship("ChunkEdital", back_populates="secao")


class ChunkEdital(Base):
    __tablename__ = "chunk_edital"

    id               = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    edital_id        = Column(PGUUID(as_uuid=True), ForeignKey("edital.id", ondelete="CASCADE"), nullable=False)
    secao_id         = Column(PGUUID(as_uuid=True), ForeignKey("secao_edital.id", ondelete="SET NULL"))
    ordem            = Column(Integer, nullable=False)
    texto            = Column(Text, nullable=False)
    tokens           = Column(Integer, nullable=False)
    pagina_inicial   = Column(Integer)
    pagina_final     = Column(Integer)
    hash_chunk       = Column(String(64))
    embedding_status = Column(Enum(EmbeddingStatus, name='embedding_status'), nullable=False, default=EmbeddingStatus.PENDENTE)
    qdrant_point_id  = Column(String(100))
    embedding_model  = Column(String(100))
    criado_em        = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    edital = relationship("Edital",      back_populates="chunks")
    secao  = relationship("SecaoEdital", back_populates="chunks")


class ResumoEdital(Base):
    __tablename__ = "resumo_edital"

    id            = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    edital_id     = Column(PGUUID(as_uuid=True), ForeignKey("edital.id", ondelete="CASCADE"), nullable=False)
    versao        = Column(Integer, nullable=False, default=1)
    json_resumo   = Column(JSONB, nullable=False)
    modelo_usado  = Column(String(100))
    versao_prompt = Column(String(50))
    ativo         = Column(Boolean, nullable=False, default=True)
    gerado_em     = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    edital = relationship("Edital", back_populates="resumos")


class VariavelViabilidade(Base):
    __tablename__ = "variavel_viabilidade"

    id             = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    edital_id      = Column(PGUUID(as_uuid=True), ForeignKey("edital.id", ondelete="CASCADE"), nullable=False)
    nome_variavel  = Column(String(100), nullable=False)
    valor_extraido = Column(Text, nullable=False)
    unidade        = Column(String(50))
    confianca      = Column(Numeric(4, 3))
    modelo_usado   = Column(String(100))
    gerado_em      = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    edital = relationship("Edital", back_populates="variaveis")


class TabelaFreteANTT(Base):
    __tablename__ = "tabela_frete_antt"

    id              = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tabela_origem   = Column(String(1), nullable=False)
    tipo_carga_cod  = Column(Integer, nullable=False)
    tipo_carga_nome = Column(String(100), nullable=False)
    coeficiente     = Column(String(20), nullable=False)
    unidade         = Column(String(10), nullable=False)
    eixos_2         = Column(Numeric(10, 4))
    eixos_3         = Column(Numeric(10, 4))
    eixos_4         = Column(Numeric(10, 4))
    eixos_5         = Column(Numeric(10, 4))
    eixos_6         = Column(Numeric(10, 4))
    eixos_7         = Column(Numeric(10, 4))
    eixos_9         = Column(Numeric(10, 4))
    versao_portaria = Column(String(50), nullable=False, default="SUROC-3-2026")
    data_vigencia   = Column(Date, nullable=False, server_default='2026-03-13')
    ativo           = Column(Boolean, nullable=False, default=True)


class AnaliseViabilidade(Base):
    __tablename__ = "analise_viabilidade"

    id                     = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    edital_id              = Column(PGUUID(as_uuid=True), ForeignKey("edital.id", ondelete="CASCADE"), nullable=False)
    produto_id             = Column(PGUUID(as_uuid=True), ForeignKey("produto.id", ondelete="CASCADE"), nullable=False)
    usuario_id             = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False)
    margem_minima_snapshot = Column(Numeric(5, 4), nullable=False)
    preco_venda_snapshot   = Column(Numeric(15, 4), nullable=False)
    custo_produto_snapshot = Column(Numeric(15, 4), nullable=False)
    distancia_km           = Column(Numeric(10, 2))
    custo_frete_estimado   = Column(Numeric(15, 4))
    custo_total_estimado   = Column(Numeric(15, 4))
    receita_estimada       = Column(Numeric(15, 4))
    margem_estimada        = Column(Numeric(5, 4))
    dentro_margem          = Column(Boolean, nullable=False)
    classificacao          = Column(Enum(ClassificacaoViabilidade, name='classificacao_viabilidade'), nullable=False)
    justificativa          = Column(Text)
    modelo_usado           = Column(String(100))
    versao_prompt          = Column(String(50))
    gerado_em              = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    edital  = relationship("Edital",  back_populates="analises_viabilidade")
    produto = relationship("Produto", back_populates="analises_viabilidade")
    usuario = relationship("Usuario", back_populates="analises_viabilidade")


class PerguntaEdital(Base):
    __tablename__ = "pergunta_edital"

    id            = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    edital_id     = Column(PGUUID(as_uuid=True), ForeignKey("edital.id", ondelete="CASCADE"), nullable=False)
    usuario_id    = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False)
    pergunta      = Column(Text, nullable=False)
    status        = Column(Enum(StatusPergunta, name='status_pergunta'), nullable=False, default=StatusPergunta.PENDENTE)
    criada_em     = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resposta      = Column(Text)
    confianca     = Column(Numeric(4, 3))
    trecho_fonte  = Column(Text)
    pagina_fonte  = Column(Integer)
    modelo_usado  = Column(String(100))
    respondida_em = Column(DateTime(timezone=True))

    edital    = relationship("Edital",  back_populates="perguntas")
    usuario   = relationship("Usuario", back_populates="perguntas")
    execucoes = relationship("ExecucaoProcesso", back_populates="pergunta")


class ExecucaoProcesso(Base):
    __tablename__ = "execucao_processo"

    id                = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    edital_id         = Column(PGUUID(as_uuid=True), ForeignKey("edital.id", ondelete="SET NULL"))
    pergunta_id       = Column(PGUUID(as_uuid=True), ForeignKey("pergunta_edital.id", ondelete="SET NULL"))
    tipo_processo     = Column(Enum(TipoProcesso, name='tipo_processo'), nullable=False)
    status            = Column(Enum(StatusExecucao, name='status_execucao'), nullable=False, default=StatusExecucao.PENDENTE)
    tentativas        = Column(Integer, nullable=False, default=0)
    tempo_execucao_ms = Column(BigInteger)
    worker_id         = Column(String(200))
    erro_mensagem     = Column(Text)
    iniciado_em       = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finalizado_em     = Column(DateTime(timezone=True))

    edital   = relationship("Edital",         back_populates="execucoes")
    pergunta = relationship("PerguntaEdital", back_populates="execucoes")