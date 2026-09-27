
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from models import (
    CategoriaProduto,
    ClassificacaoViabilidade,
    PerfilUsuario,
    StatusPergunta,
    StatusProcessamento,
)


class UsuarioCreate(BaseModel):
    nome:         str      = Field(..., min_length=2, max_length=255)
    email:        EmailStr
    senha:        str      = Field(..., min_length=8)
    razao_social: str      = Field(..., min_length=2, max_length=255)
    cnpj:         str      = Field(..., pattern=r'^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$')
    cep:          str      = Field(..., pattern=r'^\d{5}-\d{3}$')
    cidade:       Optional[str] = None
    uf:           Optional[str] = Field(None, max_length=2)


class UsuarioUpdate(BaseModel):
    nome:         Optional[str] = Field(None, min_length=2, max_length=255)
    razao_social: Optional[str] = Field(None, min_length=2, max_length=255)
    cep:          Optional[str] = Field(None, pattern=r'^\d{5}-\d{3}$')
    cidade:       Optional[str] = None
    uf:           Optional[str] = Field(None, max_length=2)


class UsuarioResponse(BaseModel):
    id:           UUID
    nome:         str
    email:        str
    razao_social: str
    cnpj:         str
    cep:          str
    cidade:       Optional[str]
    uf:           Optional[str]
    perfil:       PerfilUsuario
    ativo:        bool
    criado_em:    datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"


class ProdutoCreate(BaseModel):
    nome:              str              = Field(..., min_length=2, max_length=255)
    descricao:         Optional[str]   = None
    categoria:         CategoriaProduto = CategoriaProduto.OUTRO
    ncm:               Optional[str]   = Field(None, max_length=10)
    preco_venda:       Optional[Decimal] = Field(None, ge=0)
    custo_produto:     Decimal         = Field(..., gt=0)
    margem_minima:     Decimal         = Field(..., ge=0, le=1,
                                            description="Percentual entre 0 e 1. Ex: 0.15 = 15%")
    peso_kg:           Optional[Decimal] = Field(None, gt=0)
    impostos:          Decimal         = Field(default=Decimal('0'), ge=0, le=100,
                                            description="Carga tributária em %. Ex: 18.5")
    cep:               Optional[str]   = Field(None, max_length=9)
    uf:                Optional[str]   = Field(None, max_length=2)
    capacidade_mensal: Optional[int]   = Field(None, ge=0)

    @field_validator("margem_minima")
    @classmethod
    def validar_margem(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 1:
            raise ValueError("margem_minima deve ser entre 0 e 1 (ex: 0.15 para 15%)")
        return v


class ProdutoUpdate(BaseModel):
    nome:              Optional[str]              = Field(None, min_length=2, max_length=255)
    descricao:         Optional[str]              = None
    categoria:         Optional[CategoriaProduto] = None
    ncm:               Optional[str]              = Field(None, max_length=10)
    preco_venda:       Optional[Decimal]          = Field(None, ge=0)
    custo_produto:     Optional[Decimal]          = Field(None, gt=0)
    margem_minima:     Optional[Decimal]          = Field(None, ge=0, le=1)
    peso_kg:           Optional[Decimal]          = Field(None, gt=0)
    impostos:          Optional[Decimal]          = Field(None, ge=0, le=100)
    cep:               Optional[str]              = Field(None, max_length=9)
    uf:                Optional[str]              = Field(None, max_length=2)
    capacidade_mensal: Optional[int]              = Field(None, ge=0)
    ativo:             Optional[bool]             = None


class ProdutoResponse(BaseModel):
    id:                UUID
    usuario_id:        UUID
    nome:              str
    descricao:         Optional[str]
    categoria:         CategoriaProduto
    ncm:               Optional[str]
    preco_venda:       Optional[Decimal]
    custo_produto:     Decimal
    margem_minima:     Decimal
    peso_kg:           Optional[Decimal]
    impostos:          Decimal
    cep:               Optional[str]
    uf:                Optional[str]
    capacidade_mensal: Optional[int]
    ativo:             bool
    criado_em:         datetime

    model_config = {"from_attributes": True}


class EditalListResponse(BaseModel):
    """Schema enxuto para listagem no radar de oportunidades."""
    id:                   UUID
    id_pncp:              str
    orgao:                str
    objeto:               str
    valor_estimado:       Optional[Decimal]
    data_abertura:        Optional[date]
    status_processamento: StatusProcessamento

    model_config = {"from_attributes": True}


class EditalResponse(BaseModel):
    """Schema completo para tela de detalhe da licitação."""
    id:                   UUID
    id_pncp:              str
    titulo:               Optional[str]
    orgao:                str
    numero:               Optional[str]
    modalidade:           Optional[str]
    objeto:               str
    valor_estimado:       Optional[Decimal]
    data_publicacao:      Optional[date]
    data_abertura:        Optional[date]
    url_origem:           Optional[str]
    status_processamento: StatusProcessamento
    criado_em:            datetime

    model_config = {"from_attributes": True}


class ResumoEditalResponse(BaseModel):
    id:           UUID
    edital_id:    UUID
    versao:       int
    json_resumo:  dict
    modelo_usado: Optional[str]
    ativo:        bool
    gerado_em:    datetime

    model_config = {"from_attributes": True}


class AnaliseViabilidadeCreate(BaseModel):
    edital_id:  UUID
    produto_id: UUID
    valor_referencia: Optional[Decimal] = None


class AnaliseViabilidadeResponse(BaseModel):
    id:                     UUID
    edital_id:              UUID
    produto_id:             UUID
    margem_minima_snapshot: Decimal
    preco_venda_snapshot:   Optional[Decimal]   # pode ser null quando não informado
    custo_produto_snapshot: Decimal
    distancia_km:           Optional[Decimal]
    custo_frete_estimado:   Optional[Decimal]
    custo_total_estimado:   Optional[Decimal]
    receita_estimada:       Optional[Decimal]
    margem_estimada:        Optional[Decimal]
    dentro_margem:          bool
    classificacao:          ClassificacaoViabilidade
    justificativa:          Optional[str]
    gerado_em:              datetime

    model_config = {"from_attributes": True}


class PerguntaCreate(BaseModel):
    pergunta: str = Field(..., min_length=5, max_length=2000)


class PerguntaResponse(BaseModel):
    id:            UUID
    edital_id:     UUID
    pergunta:      str
    status:        StatusPergunta
    criada_em:     datetime
    # campos preenchidos após processamento
    resposta:      Optional[str]
    confianca:     Optional[Decimal]
    trecho_fonte:  Optional[str]
    pagina_fonte:  Optional[int]
    respondida_em: Optional[datetime]

    model_config = {"from_attributes": True}


class EditalProcessarRequest(BaseModel):
    id_pncp:        str            = Field(..., max_length=100)
    titulo:         Optional[str]  = Field(None, max_length=500)
    orgao:          str            = Field(..., max_length=500)
    objeto:         str
    modalidade:     Optional[str]  = Field(None, max_length=100)
    valor_estimado: Optional[Decimal] = None
    url_origem:     Optional[str]  = Field(None, max_length=1000)
    url_pdf:        Optional[str]  = Field(None, max_length=1000)
    data_publicacao: Optional[date] = None
    data_abertura:   Optional[date] = None


class EditalStatusResponse(BaseModel):
    edital_id:     str
    id_pncp:       str
    status:        StatusProcessamento
    resumo:        Optional[dict] = None
    total_chunks:  int = 0
    erro_mensagem: Optional[str] = None
    url_pdf:       Optional[str] = None
    tempo_decorrido: Optional[int] = None


class NotificacaoResponse(BaseModel):
    id:         UUID
    tipo:       str
    titulo:     str
    mensagem:   Optional[str]
    edital_id:  Optional[UUID]
    referencia: Optional[str]
    lida:       bool
    criada_em:  datetime

    model_config = {"from_attributes": True}


class PaginatedEditais(BaseModel):
    total:  int
    page:   int
    size:   int
    items:  list[EditalListResponse]


class PaginatedPerguntas(BaseModel):
    total:  int
    page:   int
    size:   int
    items:  list[PerguntaResponse]