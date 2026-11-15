from typing import Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from arquivos import TAMANHO_MAXIMO_BYTES, eh_pdf
from database import get_db
from dependencies import verificar_token
from models import Produto, Usuario
from schemas import (
    AnaliseViabilidadeCreate, AnaliseViabilidadeResponse,
    EditalProcessarRequest, EditalStatusResponse,
    NotificacaoResponse,
    PerguntaCreate, PerguntaResponse, ProdutoCreate, ProdutoResponse, ProdutoUpdate,
)

cliente_router = APIRouter(prefix="/cliente", tags=["Cliente"])

PNCP_SEARCH_URL = "https://pncp.gov.br/api/search/"


def _vincular_edital(session, usuario, edital) -> None:
    """Registra que o usuário abriu/enviou o edital (idempotente)."""
    from models import UsuarioEdital

    ja_vinculado = session.query(UsuarioEdital).filter(
        UsuarioEdital.usuario_id == usuario.id,
        UsuarioEdital.edital_id == edital.id,
    ).first()
    if not ja_vinculado:
        session.add(UsuarioEdital(usuario_id=usuario.id, edital_id=edital.id))
        session.commit()


def _edital_do_usuario(session, edital_id, usuario):
    """Devolve o edital se ele estiver vinculado ao usuário.

    Responde 404 tanto para edital inexistente quanto para edital de outro usuário,
    para não revelar quais IDs existem.
    """
    from models import Edital, UsuarioEdital

    edital = (
        session.query(Edital)
        .join(UsuarioEdital, UsuarioEdital.edital_id == Edital.id)
        .filter(Edital.id == edital_id, UsuarioEdital.usuario_id == usuario.id)
        .first()
    )
    if not edital:
        raise HTTPException(status_code=404, detail="Edital não encontrado.")
    return edital


@cliente_router.get("/licitacoes/buscar")
async def buscar_licitacoes(
    q: Optional[str] = None,
    status: Optional[str] = "recebendo_proposta",
    ufs: Optional[str] = None,
    modalidades: Optional[str] = None,
    tipos: Optional[str] = None,
    esferas: Optional[str] = None,
    poderes: Optional[str] = None,
    pagina: int = 1,
    tam_pagina: int = 10,
    ordenacao: str = "-data",
    usuario: Usuario = Depends(verificar_token),
):
    params: dict = {
        "tipos_documento": "edital",
        "ordenacao": ordenacao,
        "pagina": pagina,
        "tam_pagina": tam_pagina,
    }

    if q:
        params["q"] = q
    if status:
        params["status"] = status
    if ufs:
        params["ufs"] = ufs
    if modalidades:
        params["modalidades"] = modalidades
    if tipos:
        params["tipos"] = tipos
    if esferas:
        params["esferas"] = esferas
    if poderes:
        params["poderes"] = poderes

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
            response = await client.get(PNCP_SEARCH_URL, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout ao consultar o PNCP.")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Erro ao consultar o PNCP.")
    except Exception:
        raise HTTPException(status_code=502, detail="Falha na comunicação com o PNCP.")


# Tempo que um edital pode ficar PROCESSANDO sem que uma nova chamada o reenfileire.
JANELA_SEM_EXECUCAO_S = 120    # a tarefa ainda não foi pega pelo worker
JANELA_COM_EXECUCAO_S = 900    # a tarefa começou; cobre o processamento e as novas tentativas


def _atualizado_ha_pouco(edital, janela_s: int) -> bool:
    """True se o edital mudou de estado há menos de `janela_s` segundos."""
    from datetime import datetime, timezone

    ref = edital.atualizado_em or edital.criado_em
    if ref is None:
        return False
    if ref.tzinfo is None:  # SQLite devolve datetime sem fuso (UTC)
        ref = ref.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ref).total_seconds() < janela_s


def _ler_pdf_enviado(arquivo: UploadFile) -> bytes:
    """Lê o upload e garante que é um PDF de até 50 MB.

    Lê no máximo um byte além do limite, em vez do arquivo inteiro, e confere o
    conteúdo — a extensão .pdf sozinha não garante o formato.
    """
    if not (arquivo.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos.")
    conteudo = arquivo.file.read(TAMANHO_MAXIMO_BYTES + 1)
    if len(conteudo) > TAMANHO_MAXIMO_BYTES:
        raise HTTPException(status_code=400, detail="Arquivo muito grande. Máximo: 50 MB.")
    if not eh_pdf(conteudo):
        raise HTTPException(status_code=400, detail="O arquivo enviado não é um PDF válido.")
    return conteudo


@cliente_router.post("/editais/processar", status_code=202)
def processar_edital(
    dados: EditalProcessarRequest,
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    from models import Edital, StatusProcessamento

    edital = session.query(Edital).filter(Edital.id_pncp == dados.id_pncp).first()

    if not edital:
        titulo_safe = (dados.titulo[:500] if dados.titulo else None)
        orgao_safe = (dados.orgao[:500] if dados.orgao else "Órgão não informado")
        modalidade_safe = (dados.modalidade[:100] if dados.modalidade else None)
        url_origem_safe = (dados.url_origem[:1000] if dados.url_origem else None)
        url_pdf_safe = (dados.url_pdf[:1000] if dados.url_pdf else None)

        edital = Edital(
            id_pncp=dados.id_pncp[:100],
            titulo=titulo_safe,
            orgao=orgao_safe,
            objeto=dados.objeto or "Sem descrição fornecida",
            modalidade=modalidade_safe,
            valor_estimado=dados.valor_estimado,
            url_origem=url_origem_safe,
            url_pdf=url_pdf_safe,
            uf=_uf_valida(dados.uf),
            municipio=(dados.municipio[:255] if dados.municipio else None),
            data_publicacao=dados.data_publicacao,
            data_abertura=dados.data_abertura,
            status_processamento=StatusProcessamento.PENDENTE,
        )
        session.add(edital)
        session.commit()
        session.refresh(edital)
    else:
        # Atualiza URLs se vieram preenchidas agora
        if dados.url_origem and not edital.url_origem:
            edital.url_origem = dados.url_origem[:1000]
        if dados.url_pdf and not edital.url_pdf:
            edital.url_pdf = dados.url_pdf[:1000]
        if _uf_valida(dados.uf) and not edital.uf:
            edital.uf = _uf_valida(dados.uf)
        if dados.municipio and not edital.municipio:
            edital.municipio = dados.municipio[:255]
        session.commit()

    _vincular_edital(session, usuario, edital)

    if edital.status_processamento == StatusProcessamento.PROCESSADO:
        return {"edital_id": str(edital.id), "status": "PROCESSADO"}

    # PROCESSANDO sem execução registrada = worker não estava rodando → reenfileira
    if edital.status_processamento == StatusProcessamento.PROCESSANDO:
        from models import ExecucaoProcesso
        tem_execucao = session.query(ExecucaoProcesso).filter(
            ExecucaoProcesso.edital_id == edital.id
        ).first()
        janela = JANELA_COM_EXECUCAO_S if tem_execucao else JANELA_SEM_EXECUCAO_S
        if _atualizado_ha_pouco(edital, janela):
            return {"edital_id": str(edital.id), "status": "PROCESSANDO"}
        # Parado além da janela = a tarefa nunca rodou ou o worker morreu no meio; reenfileira
        edital.status_processamento = StatusProcessamento.PENDENTE
        session.commit()

    # Edital que falhou só é processado de novo a pedido do usuário ("Tentar novamente").
    # Abrir a página não pode reenfileirar: a causa costuma ser definitiva (arquivo que não é PDF).
    if edital.status_processamento == StatusProcessamento.ERRO and not dados.reprocessar:
        return {"edital_id": str(edital.id), "status": "ERRO"}

    edital.status_processamento = StatusProcessamento.PROCESSANDO
    session.commit()

    try:
        from tasks import processar_edital_task
        processar_edital_task.apply_async(
            args=[str(edital.id), str(usuario.id)],
            ignore_result=True,
        )
    except Exception as exc:
        edital.status_processamento = StatusProcessamento.PENDENTE
        session.commit()
        raise HTTPException(
            status_code=503,
            detail=f"Serviço de processamento indisponível. Verifique se o Redis está rodando. ({exc.__class__.__name__})",
        )

    return {"edital_id": str(edital.id), "status": "PROCESSANDO"}


@cliente_router.get("/editais/{edital_id}/status", response_model=EditalStatusResponse)
def status_edital(
    edital_id: str,
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    from models import (
        ChunkEdital, Edital, ExecucaoProcesso,
        ResumoEdital as ResumoEditalModel, StatusExecucao, StatusProcessamento,
    )

    try:
        uid = UUID(edital_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="edital_id inválido (deve ser UUID).")

    edital = _edital_do_usuario(session, uid, usuario)

    resultado: dict = {
        "edital_id": str(edital.id),
        "id_pncp": edital.id_pncp,
        "status": edital.status_processamento,
        "resumo": None,
        "total_chunks": 0,
        "erro_mensagem": None,
        "url_pdf": edital.url_pdf,
        "tempo_decorrido": None,
    }

    if edital.status_processamento == StatusProcessamento.PROCESSADO:
        resumo = (
            session.query(ResumoEditalModel)
            .filter(ResumoEditalModel.edital_id == edital.id, ResumoEditalModel.ativo == True)
            .order_by(ResumoEditalModel.versao.desc())
            .first()
        )
        if resumo:
            resultado["resumo"] = resumo.json_resumo
        resultado["total_chunks"] = (
            session.query(ChunkEdital).filter(ChunkEdital.edital_id == edital.id).count()
        )

    if edital.status_processamento == StatusProcessamento.PROCESSANDO:
        execucao = (
            session.query(ExecucaoProcesso)
            .filter(
                ExecucaoProcesso.edital_id == edital.id,
                ExecucaoProcesso.status == StatusExecucao.EXECUTANDO
            )
            .order_by(ExecucaoProcesso.iniciado_em.desc())
            .first()
        )
        if execucao and execucao.iniciado_em:
            from datetime import datetime, timezone
            iniciado = execucao.iniciado_em
            if iniciado.tzinfo is None:
                resultado["tempo_decorrido"] = int(
                    (datetime.now(timezone.utc).replace(tzinfo=None) - iniciado).total_seconds()
                )
            else:
                resultado["tempo_decorrido"] = int(
                    (datetime.now(timezone.utc) - iniciado).total_seconds()
                )

    if edital.status_processamento == StatusProcessamento.ERRO:
        ultimo = (
            session.query(ExecucaoProcesso)
            .filter(ExecucaoProcesso.edital_id == edital.id, ExecucaoProcesso.status == StatusExecucao.ERRO)
            .order_by(ExecucaoProcesso.iniciado_em.desc())
            .first()
        )
        if ultimo:
            resultado["erro_mensagem"] = ultimo.erro_mensagem

    return resultado


@cliente_router.get("/editais/historico")
def obter_historico_editais(
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    """Retorna os editais que o usuário abriu ou enviou, do mais recente para o mais antigo."""
    from models import Edital, UsuarioEdital

    editais = (
        session.query(Edital)
        .join(UsuarioEdital, UsuarioEdital.edital_id == Edital.id)
        .filter(UsuarioEdital.usuario_id == usuario.id)
        .order_by(UsuarioEdital.criado_em.desc())
        .all()
    )

    # Classificação da análise de viabilidade mais recente do usuário em cada edital
    from models import AnaliseViabilidade
    classificacoes: dict = {}
    for a in (
        session.query(AnaliseViabilidade)
        .filter(AnaliseViabilidade.usuario_id == usuario.id)
        .order_by(AnaliseViabilidade.gerado_em.asc())
        .all()
    ):
        classificacoes[a.edital_id] = a.classificacao.value

    resultado = []
    for ed in editais:
        cnpj = seq = ano = ""
        id_pncp = ed.id_pncp
        if "/" in id_pncp:
            try:
                base, ano_str = id_pncp.split("/", 1)
                parts = base.split("-")
                if len(parts) >= 3:
                    cnpj = parts[0].strip()
                    seq = parts[-1].strip()
                    seq = str(int(seq))
                    ano = ano_str.strip()
            except Exception:
                pass
                
        item_url = f"/compras/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else f"/compras/{id_pncp}"
        
        resultado.append({
            "id": ed.id_pncp,
            "numero_controle_pncp": ed.id_pncp,
            "title": ed.titulo or (f"Compra nº {seq}/{ano}" if (seq and ano) else f"Licitação {id_pncp}"),
            "description": ed.objeto or "Objeto não informado",
            "item_url": item_url,
            "orgao_nome": ed.orgao or "",
            "orgao_cnpj": cnpj,
            "unidade_nome": "",
            "esfera_id": "",
            "poder_id": "",
            "municipio_nome": ed.municipio or "",
            "uf": ed.uf or "",
            "modalidade_licitacao_nome": ed.modalidade or "",
            "situacao_nome": "Divulgada no PNCP",
            "data_publicacao_pncp": ed.data_publicacao.isoformat() if ed.data_publicacao else None,
            "data_inicio_vigencia": ed.data_abertura.isoformat() if ed.data_abertura else None,
            "data_fim_vigencia": None,
            "valor_global": float(ed.valor_estimado) if ed.valor_estimado is not None else None,
            "tipo_nome": "Edital",
            "cancelado": False,
            "status_processamento": ed.status_processamento.value if ed.status_processamento else None,
            "analise_classificacao": classificacoes.get(ed.id),
        })
        
    return resultado


@cliente_router.post("/editais/upload-pdf", status_code=202)
def upload_pdf(
    arquivo: UploadFile = File(...),
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    from uuid import uuid4
    from models import Edital, StatusProcessamento

    pdf_bytes = _ler_pdf_enviado(arquivo)

    nome_arquivo = arquivo.filename or "Upload Manual"
    id_pncp = f"UPLOAD-{str(uuid4())}"

    # Salva o edital como PROCESSANDO
    edital = Edital(
        id_pncp=id_pncp,
        titulo=f"Edital PDF: {nome_arquivo}",
        orgao="Upload Manual",
        objeto=f"Edital carregado manualmente pelo usuário: {nome_arquivo}",
        pdf_conteudo=pdf_bytes,
        status_processamento=StatusProcessamento.PROCESSANDO,
    )
    session.add(edital)
    session.commit()
    session.refresh(edital)
    _vincular_edital(session, usuario, edital)

    try:
        from tasks import processar_edital_task
        processar_edital_task.apply_async(
            args=[str(edital.id), str(usuario.id)],
            ignore_result=True,
        )
    except Exception as exc:
        edital.status_processamento = StatusProcessamento.PENDENTE
        session.commit()
        raise HTTPException(
            status_code=503,
            detail=f"Serviço de processamento indisponível. Verifique se o Redis está rodando. ({exc.__class__.__name__})",
        )

    return {"edital_id": str(edital.id), "status": "PROCESSANDO"}


@cliente_router.post("/editais/{edital_id}/upload-pdf", status_code=202)
def upload_pdf_para_edital(
    edital_id: str,
    arquivo: UploadFile = File(...),
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    from models import Edital, StatusProcessamento

    try:
        uid = UUID(edital_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="edital_id inválido.")

    edital = _edital_do_usuario(session, uid, usuario)

    pdf_bytes = _ler_pdf_enviado(arquivo)

    edital.pdf_conteudo = pdf_bytes
    edital.status_processamento = StatusProcessamento.PROCESSANDO
    session.commit()

    try:
        from tasks import processar_edital_task
        processar_edital_task.apply_async(
            args=[str(edital.id), str(usuario.id)],
            ignore_result=True,
        )
    except Exception as exc:
        edital.status_processamento = StatusProcessamento.PENDENTE
        session.commit()
        raise HTTPException(
            status_code=503,
            detail=f"Serviço de processamento indisponível ({exc.__class__.__name__}).",
        )

    return {"edital_id": str(edital.id), "status": "PROCESSANDO"}


@cliente_router.post("/editais/{edital_id}/perguntar")
def perguntar_edital(
    edital_id: str,
    body: PerguntaCreate,
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    from datetime import datetime, timezone
    from models import Edital, PerguntaEdital, StatusPergunta, StatusProcessamento

    try:
        uid = UUID(edital_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="edital_id inválido (deve ser UUID).")

    edital = _edital_do_usuario(session, uid, usuario)

    if edital.status_processamento != StatusProcessamento.PROCESSADO:
        raise HTTPException(
            status_code=400,
            detail="O chat só está disponível após o processamento completo do edital."
        )

    pergunta_db = PerguntaEdital(
        edital_id=edital.id,
        usuario_id=usuario.id,
        pergunta=body.pergunta,
        status=StatusPergunta.PENDENTE,
    )
    session.add(pergunta_db)
    session.commit()
    session.refresh(pergunta_db)

    try:
        from rag.edital_rag import nome_colecao, responder_pergunta
        collection_name = nome_colecao(edital.id)
        resultado = responder_pergunta(collection_name, body.pergunta)

        pergunta_db.resposta = resultado["resposta"]
        pergunta_db.trecho_fonte = resultado.get("trecho_fonte")
        pergunta_db.pagina_fonte = resultado.get("pagina_fonte")
        pergunta_db.status = StatusPergunta.RESPONDIDA
        pergunta_db.respondida_em = datetime.now(timezone.utc)
        session.commit()

        return {
            "resposta": resultado["resposta"],
            "trecho_fonte": resultado.get("trecho_fonte"),
            "pagina_fonte": resultado.get("pagina_fonte"),
            "pagina_fonte_final": resultado.get("pagina_fonte_final"),
            "chunks_utilizados": resultado["chunks_utilizados"],
        }

    except Exception as exc:
        pergunta_db.status = StatusPergunta.ERRO
        session.commit()
        print(f"[Chat] Erro ao responder pergunta: {exc.__class__.__name__}: {exc}")
        if exc.__class__.__name__ == "RateLimitError":
            # Cota do provedor de IA esgotada (por minuto ou por dia): não é defeito do sistema
            raise HTTPException(
                status_code=503,
                detail="O limite de uso da IA foi atingido. Aguarde alguns minutos e tente novamente.",
            )
        raise HTTPException(status_code=500, detail="Não foi possível responder agora. Tente novamente em instantes.")


# ── Viabilidade ───────────────────────────────────────────────────────────────

_UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}


def _uf_valida(valor) -> str | None:
    """Devolve a sigla em maiúsculas se for uma UF brasileira; caso contrário, None."""
    if not isinstance(valor, str):
        return None
    sigla = valor.strip().upper()
    return sigla if sigla in _UFS else None


def _numero(valor) -> float | None:
    """Converte o que o LLM devolveu (número ou texto como '1.500,00') em float; None se não der."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    try:
        txt = str(valor).strip().replace("R$", "").replace(" ", "")
        if "," in txt:
            txt = txt.replace(".", "").replace(",", ".")
        return float(txt)
    except ValueError:
        return None


def _brl(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(valor: float) -> str:
    return f"{valor * 100:.1f}%".replace(".", ",")


def _resolver_uf_destino(edital, cep_entrega, uf_resumo, uf_from_cep) -> str | None:
    """UF de entrega, da fonte mais confiável para a menos confiável.

    1. CEP de entrega extraído do edital; 2. UF do órgão comprador no PNCP;
    3. UF citada no resumo gerado pela IA; 4. sigla escrita como "Cidade/UF" ou "- UF"
    no nome do órgão ou no objeto. Não há valor padrão: sem fonte, devolve None.
    """
    import re

    if cep_entrega:
        uf = _uf_valida(uf_from_cep(cep_entrega))
        if uf:
            return uf
    if _uf_valida(edital.uf):
        return _uf_valida(edital.uf)
    if uf_resumo:
        return uf_resumo
    # Só aceita a sigla precedida de "/" ou "-": o padrão antigo casava palavras comuns ("SE", "PA").
    for texto in (edital.orgao, edital.objeto):
        for sigla in re.findall(r"[/\-–]\s*([A-Z]{2})\b", texto or ""):
            if _uf_valida(sigla):
                return _uf_valida(sigla)
    return None

def _calcular_frete_antt(session, distancia_km: float, peso_total_kg: float) -> float:
    """Calcula o custo de frete usando a Tabela TACO da ANTT (Carga Geral, 2 eixos).

    Fórmula: custo_por_viagem = CC + CCD × distância_km
    Número de viagens = ceil(peso_total_ton / capacidade_caminhão)
    """
    import math
    from models import TabelaFreteANTT

    ccd = session.query(TabelaFreteANTT).filter(
        TabelaFreteANTT.tipo_carga_nome == 'Carga Geral',  # ilike casava também "Perigosa (carga geral)"
        TabelaFreteANTT.coeficiente == 'CCD',
        TabelaFreteANTT.ativo == True,
    ).first()
    cc = session.query(TabelaFreteANTT).filter(
        TabelaFreteANTT.tipo_carga_nome == 'Carga Geral',  # ilike casava também "Perigosa (carga geral)"
        TabelaFreteANTT.coeficiente == 'CC',
        TabelaFreteANTT.ativo == True,
    ).first()

    if not ccd or not cc or not ccd.eixos_2 or not cc.eixos_2:
        # Sem os coeficientes o frete sairia R$ 0 e inflaria a margem sem aviso.
        raise HTTPException(
            status_code=503,
            detail="Tabela de frete ANTT não carregada no banco. Execute 'python seed_antt.py' no backend.",
        )

    capacidade_ton = 5.0  # caminhão 2 eixos ≈ 5 t de carga
    num_viagens = max(1, math.ceil((peso_total_kg / 1000) / capacidade_ton))
    custo_por_viagem = float(cc.eixos_2) + float(ccd.eixos_2) * distancia_km
    return custo_por_viagem * num_viagens


def _calcular_viabilidade(session, edital, produto, quantidade_informada=None, valor_referencia=None) -> dict:
    """Responde: vale a pena vender ESTE produto, pelo preço do cadastro, neste edital?

    A receita é quantidade × preço de proposta. O preço de proposta é o preço de venda do
    produto, limitado pelo valor unitário estimado do item no edital (o máximo aceito).

    1. LLM extrai quantidade, cep_entrega e prazo_dias do resumo do edital; a busca no
       edital localiza o item correspondente ao produto (quantidade e valor unitário).
    2. Distância entre os CEPs de origem e de entrega (Haversine × 1,3) quando ambos existem.
    3. Caso contrário, distância entre as capitais das UFs; a UF de entrega vem de
       _resolver_uf_destino (CEP do edital, UF do órgão no PNCP, resumo, texto).
    4. Tabela TACO da ANTT (Carga Geral, 2 eixos) para custo de frete real.
    5. Cálculo determinístico de margem, sem dependência do LLM para a decisão final.
    """
    from decimal import Decimal
    from models import ClassificacaoViabilidade, ResumoEdital as ResumoModel, VariavelViabilidade, Usuario
    from rag.edital_rag import extrair_variaveis_edital, distancia_entre_ufs, uf_from_cep, distancia_entre_ceps

    custo = float(produto.custo_produto)
    imp   = float(produto.impostos or 0) / 100
    marg_min = float(produto.margem_minima)
    peso_kg  = float(produto.peso_kg or 1.0)

    # ── 1. Extração de variáveis do resumo via LLM ────────────────────────
    variaveis: dict = {}
    resumo_db = (
        session.query(ResumoModel)
        .filter(ResumoModel.edital_id == edital.id, ResumoModel.ativo == True)
        .order_by(ResumoModel.versao.desc())
        .first()
    )
    if resumo_db:
        variaveis = extrair_variaveis_edital(resumo_db.json_resumo)
        # Persiste variáveis apenas na primeira análise deste edital
        ja_tem = session.query(VariavelViabilidade).filter(
            VariavelViabilidade.edital_id == edital.id
        ).first()
        if not ja_tem:
            from rag.edital_rag import LLM_MODEL as _LLM
            for nome, valor_raw in variaveis.items():
                if valor_raw is not None:
                    session.add(VariavelViabilidade(
                        edital_id=edital.id,
                        nome_variavel=nome,
                        valor_extraido=str(valor_raw),
                        confianca=0.85,
                        modelo_usado=f"groq/{_LLM}",
                    ))
            session.commit()

    quantidade_resumo = _numero(variaveis.get("quantidade"))
    cep_entrega       = variaveis.get("cep_entrega")
    uf_resumo         = _uf_valida(variaveis.get("uf_entrega"))

    # 1.B. Extração de dados específicos do item correspondente ao produto no edital via RAG
    from rag.edital_rag import extrair_dados_item_edital, nome_colecao
    dados_item = {}
    try:
        dados_item = extrair_dados_item_edital(
            collection_name=nome_colecao(edital.id),
            produto_nome=produto.nome,
            produto_descricao=produto.descricao or ""
        )
    except Exception as e:
        print(f"[Viabilidade] Erro ao extrair dados do item via RAG: {e}")

    qty_item      = _numero(dados_item.get("quantidade"))
    val_unit_item = _numero(dados_item.get("valor_unitario_estimado"))

    avisos: list[str] = []

    # ── 2. Distância para frete ───────────────────────────────────────────
    usuario = session.query(Usuario).filter(Usuario.id == produto.usuario_id).first()
    cep_origem = produto.cep or (usuario.cep if usuario else None) or "01001-000"
    uf_origem = _uf_valida(produto.uf) or _uf_valida(usuario.uf if usuario else None) or "SP"

    distancia = None
    if cep_origem and cep_entrega:
        distancia = distancia_entre_ceps(cep_origem, cep_entrega)

    uf_destino = _resolver_uf_destino(edital, cep_entrega, uf_resumo, uf_from_cep)
    if distancia is not None:
        base_distancia = "entre os CEPs de origem e de entrega"
        uf_destino = uf_destino or uf_origem
    else:
        base_distancia = "entre as capitais dos estados"
        if uf_destino is None:
            uf_destino = uf_origem
            avisos.append(
                "A UF de entrega não foi identificada; o frete foi calculado como se a entrega "
                "fosse no mesmo estado de origem do produto."
            )
        distancia = distancia_entre_ufs(uf_origem, uf_destino)

    # Avisos acumulados até aqui (UF de entrega desconhecida) já tornam o resultado uma estimativa
    depende_de_estimativa = bool(avisos)

    # ── 3. Preço do fornecedor ────────────────────────────────────────────
    if produto.preco_venda and float(produto.preco_venda) > 0:
        preco = float(produto.preco_venda)
        origem_preco = "preço de venda do seu cadastro"
    else:
        denominador = max(1 - marg_min - imp - 0.05, 0.05)
        preco = custo / denominador
        origem_preco = "calculado pelo custo e pela margem mínima, pois o produto não tem preço de venda cadastrado"

    # ── 3.1 Quantidade: a informada pelo usuário, depois a do item, depois a do resumo ──
    if quantidade_informada and quantidade_informada > 0:
        quantidade, quantidade_origem = int(quantidade_informada), "INFORMADA"
        texto_origem = "informada por você"
    elif qty_item and qty_item > 0:
        quantidade, quantidade_origem = int(qty_item), "ITEM_EDITAL"
        texto_origem = "encontrada no item do edital correspondente ao produto"
    elif quantidade_resumo and quantidade_resumo > 0:
        quantidade, quantidade_origem = int(quantidade_resumo), "RESUMO_EDITAL"
        texto_origem = "quantidade geral citada no resumo do edital"
    else:
        lote = float(valor_referencia) if valor_referencia is not None else float(edital.valor_estimado or 0)
        if lote <= 0 or preco <= 0:
            raise HTTPException(
                status_code=422,
                detail="Não encontrei este produto no edital, e o edital não informa o valor total. "
                       "Informe a quantidade que você pretende fornecer para calcular a viabilidade.",
            )
        quantidade = max(1, int(lote / preco))
        quantidade_origem = "ESTIMADA"
        texto_origem = "estimada: valor total do edital dividido pelo seu preço de venda"
        depende_de_estimativa = True
        avisos.append(
            "O produto não foi localizado no edital. A quantidade foi estimada dividindo o valor total "
            "do edital pelo seu preço de venda. Informe a quantidade para uma análise mais precisa."
        )

    # ── 3.2 Preço de proposta: o seu preço, limitado pelo valor estimado do item no edital ──
    teto = val_unit_item if (val_unit_item and val_unit_item > 0) else None
    if teto is None:
        preco_proposta = preco
        texto_preco = origem_preco
        if quantidade_origem != "ESTIMADA":   # o aviso de produto não localizado já cobre esse caso
            depende_de_estimativa = True
            avisos.append(
                "O valor estimado deste item não foi encontrado no edital. A análise usa o seu preço, "
                "sem saber se ele está dentro do máximo aceito pelo órgão."
            )
    elif preco <= teto:
        preco_proposta = preco
        texto_preco = f"{origem_preco}; {_pct((teto - preco) / teto)} abaixo do valor estimado do item no edital, {_brl(teto)}"
    else:
        preco_proposta = teto
        texto_preco = "valor estimado do item no edital, que é o máximo aceito"
        avisos.append(
            f"Seu preço ({_brl(preco)}) está acima do valor estimado do item no edital ({_brl(teto)}). "
            f"Propostas acima desse valor costumam ser desclassificadas, então a análise considera a venda por {_brl(teto)}."
        )

    valor = quantidade * preco_proposta

    # ── 4. Custos ─────────────────────────────────────────────────────────
    custo_op    = custo * (1 + imp) * quantidade
    peso_total  = peso_kg * quantidade
    custo_frete = _calcular_frete_antt(session, distancia, peso_total)
    custo_total = custo_op + custo_frete

    # ── 5. Margem e classificação ─────────────────────────────────────────
    marg  = (valor - custo_total) / valor if valor > 0 else -1.0
    dentro = marg >= marg_min

    if marg < 0:
        classe = ClassificacaoViabilidade.NAO_RECOMENDADO
        resultado = f"Prejuízo estimado de {_pct(abs(marg))}: os custos superam a receita."
    elif not dentro:
        classe = ClassificacaoViabilidade.ATENCAO
        resultado = f"Margem estimada de {_pct(marg)}, abaixo da mínima de {_pct(marg_min)}."
    else:
        classe = ClassificacaoViabilidade.VALE_A_PENA
        resultado = f"Margem estimada de {_pct(marg)}, acima da mínima de {_pct(marg_min)}."

    # Um resultado que depende de estimativa não pode ser apresentado como "Vale a pena".
    if depende_de_estimativa and classe == ClassificacaoViabilidade.VALE_A_PENA:
        classe = ClassificacaoViabilidade.ATENCAO
        resultado += " Classificada como Atenção porque o cálculo depende de estimativas."

    detalhes = (
        f"Preço considerado: {_brl(preco_proposta)} por unidade ({texto_preco}). "
        f"Quantidade: {quantidade} un. ({texto_origem}). "
        f"Receita: {_brl(valor)}. Produção + impostos: {_brl(custo_op)}. "
        f"Frete: {_brl(custo_frete)} ({distancia:.0f} km {base_distancia}, {uf_origem}→{uf_destino})."
    )
    just = " ".join([resultado, *[f"Atenção: {a}" for a in avisos], detalhes])

    # Garante que a margem calculada caiba no campo NUMERIC(5, 4) do PostgreSQL (-9.9999 a 9.9999)
    marg_decimal = Decimal(str(round(marg, 4)))
    marg_capped = max(Decimal("-9.9999"), min(Decimal("9.9999"), marg_decimal))

    return {
        "preco_venda_est": Decimal(str(round(preco, 4))),
        "custo_frete":     Decimal(str(round(custo_frete, 4))),
        "custo_total":     Decimal(str(round(custo_total, 4))),
        "receita":         Decimal(str(round(valor, 4))),
        "margem":          marg_capped,
        "dentro":          dentro,
        "classificacao":   classe,
        "justificativa":   just,
        "distancia_km":    Decimal(str(round(distancia, 1))),
        "quantidade":        quantidade,
        "quantidade_origem": quantidade_origem,
        "preco_proposta":        Decimal(str(round(preco_proposta, 4))),
        "valor_unitario_edital": Decimal(str(round(teto, 4))) if teto is not None else None,
        "uf_origem":         uf_origem,
        "uf_destino":        uf_destino,
        "avisos":            avisos,
    }


@cliente_router.post("/analise", response_model=AnaliseViabilidadeResponse)
def criar_analise(
    dados: AnaliseViabilidadeCreate,
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    from models import AnaliseViabilidade, Edital, Produto

    edital = _edital_do_usuario(session, dados.edital_id, usuario)

    produto = session.query(Produto).filter(
        Produto.id == dados.produto_id,
        Produto.usuario_id == usuario.id,
        Produto.ativo == True,
    ).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    # Executa o cálculo de viabilidade (passando valor_referencia que pode ser None)
    r = _calcular_viabilidade(
        session, edital, produto,
        quantidade_informada=dados.quantidade, valor_referencia=dados.valor_referencia,
    )

    # Se a receita calculada ainda for zero ou menor, significa que nem o edital nem a IA conseguiram
    # estimar o valor total da receita/item, e o usuário não passou um valor_referencia.
    if r["receita"] <= 0:
        raise HTTPException(
            status_code=422,
            detail="Edital sem valor estimado — informe o valor do lote ou item para calcular a viabilidade."
        )

    # Uma análise por edital + produto + usuário: reanalisar atualiza a existente.
    # (Antes, a análise antiga era devolvida sempre que a receita coincidia, mesmo com
    # custo ou frete diferentes.)
    from datetime import datetime, timezone

    analise = session.query(AnaliseViabilidade).filter(
        AnaliseViabilidade.edital_id == dados.edital_id,
        AnaliseViabilidade.produto_id == dados.produto_id,
        AnaliseViabilidade.usuario_id == usuario.id,
    ).first()
    if not analise:
        analise = AnaliseViabilidade(
            edital_id=dados.edital_id,
            produto_id=dados.produto_id,
            usuario_id=usuario.id,
        )
        session.add(analise)

    analise.margem_minima_snapshot = produto.margem_minima
    analise.preco_venda_snapshot   = r["preco_venda_est"]
    analise.custo_produto_snapshot = produto.custo_produto
    analise.distancia_km           = r["distancia_km"]
    analise.custo_frete_estimado   = r["custo_frete"]
    analise.custo_total_estimado   = r["custo_total"]
    analise.receita_estimada       = r["receita"]
    analise.margem_estimada        = r["margem"]
    analise.dentro_margem          = r["dentro"]
    analise.classificacao          = r["classificacao"]
    analise.justificativa          = r["justificativa"]
    analise.quantidade_considerada = r["quantidade"]
    analise.quantidade_origem      = r["quantidade_origem"]
    analise.preco_proposta         = r["preco_proposta"]
    analise.valor_unitario_edital  = r["valor_unitario_edital"]
    analise.uf_origem              = r["uf_origem"]
    analise.uf_destino             = r["uf_destino"]
    analise.avisos                 = r["avisos"]
    analise.modelo_usado           = "deterministic-v2"
    analise.versao_prompt          = "v1"
    analise.gerado_em              = datetime.now(timezone.utc)
    session.commit()
    session.refresh(analise)

    return analise


@cliente_router.get("/editais/{edital_id}/analise", response_model=Optional[AnaliseViabilidadeResponse])
def obter_analise(
    edital_id: UUID,
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    """Análise de viabilidade mais recente do usuário para o edital (null se não houver).

    Só considera produtos ativos: a tela precisa do produto para exibir o resultado.
    """
    from models import AnaliseViabilidade

    _edital_do_usuario(session, edital_id, usuario)
    return (
        session.query(AnaliseViabilidade)
        .join(Produto, Produto.id == AnaliseViabilidade.produto_id)
        .filter(
            AnaliseViabilidade.edital_id == edital_id,
            AnaliseViabilidade.usuario_id == usuario.id,
            Produto.ativo == True,
        )
        .order_by(AnaliseViabilidade.gerado_em.desc())
        .first()
    )


@cliente_router.get("/editais/{edital_id}/perguntas", response_model=list[PerguntaResponse])
def listar_perguntas(
    edital_id: UUID,
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    """Perguntas já respondidas que o usuário fez sobre o edital, da mais antiga para a mais nova."""
    from models import PerguntaEdital, StatusPergunta

    _edital_do_usuario(session, edital_id, usuario)
    return (
        session.query(PerguntaEdital)
        .filter(
            PerguntaEdital.edital_id == edital_id,
            PerguntaEdital.usuario_id == usuario.id,
            PerguntaEdital.status == StatusPergunta.RESPONDIDA,
        )
        .order_by(PerguntaEdital.criada_em.asc())
        .limit(100)
        .all()
    )


@cliente_router.delete("/analise/{edital_id}/{produto_id}", status_code=204)
def remover_analise(
    edital_id: UUID,
    produto_id: UUID,
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    from models import AnaliseViabilidade
    analise = session.query(AnaliseViabilidade).filter(
        AnaliseViabilidade.edital_id == edital_id,
        AnaliseViabilidade.produto_id == produto_id,
        AnaliseViabilidade.usuario_id == usuario.id,
    ).first()
    if analise:
        session.delete(analise)
        session.commit()


# ── Produtos ──────────────────────────────────────────────────────────────────

@cliente_router.get("/produtos", response_model=list[ProdutoResponse])
def listar_produtos(
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    return session.query(Produto).filter(
        Produto.usuario_id == usuario.id,
        Produto.ativo == True,
    ).order_by(Produto.criado_em.desc()).all()


@cliente_router.post("/produtos", response_model=ProdutoResponse, status_code=201)
def criar_produto(
    dados: ProdutoCreate,
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    produto = Produto(usuario_id=usuario.id, **dados.model_dump())
    session.add(produto)
    session.commit()
    session.refresh(produto)
    return produto


@cliente_router.put("/produtos/{produto_id}", response_model=ProdutoResponse)
def atualizar_produto(
    produto_id: UUID,
    dados: ProdutoUpdate,
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    produto = session.query(Produto).filter(
        Produto.id == produto_id,
        Produto.usuario_id == usuario.id,
    ).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(produto, campo, valor)

    session.commit()
    session.refresh(produto)
    return produto


@cliente_router.delete("/produtos/{produto_id}", status_code=204)
def remover_produto(
    produto_id: UUID,
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    produto = session.query(Produto).filter(
        Produto.id == produto_id,
        Produto.usuario_id == usuario.id,
    ).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    produto.ativo = False  # soft delete
    session.commit()


# ── Notificações ───────────────────────────────────────────────────────────────

@cliente_router.get("/notificacoes", response_model=list[NotificacaoResponse])
def listar_notificacoes(
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    from models import Notificacao
    return (
        session.query(Notificacao)
        .filter(Notificacao.usuario_id == usuario.id)
        .order_by(Notificacao.criada_em.desc())
        .limit(30)
        .all()
    )


@cliente_router.patch("/notificacoes/{notif_id}/lida", status_code=204)
def marcar_lida(
    notif_id: UUID,
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    from models import Notificacao
    n = session.query(Notificacao).filter(
        Notificacao.id == notif_id, Notificacao.usuario_id == usuario.id
    ).first()
    if n:
        n.lida = True
        session.commit()


@cliente_router.patch("/notificacoes/marcar-todas-lidas", status_code=204)
def marcar_todas_lidas(
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    from models import Notificacao
    session.query(Notificacao).filter(
        Notificacao.usuario_id == usuario.id, Notificacao.lida == False
    ).update({"lida": True})
    session.commit()


@cliente_router.get("/licitacoes/{id_pncp:path}")
async def obter_licitacao_pncp(
    id_pncp: str,
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    """Consulta detalhes de uma licitação específica diretamente na API pública do PNCP.

    Suporta F5/Refresh e cache-miss no frontend para carregar os dados reais.
    """
    cnpj = seq = ano = None
    if "/" in id_pncp:
        base, ano_str = id_pncp.split("/", 1)
        parts = base.split("-")
        if len(parts) >= 3:
            cnpj = parts[0].strip()
            seq = parts[-1].strip()
            try:
                seq = str(int(seq))
            except ValueError:
                pass
            ano = ano_str.strip()

    if not (cnpj and ano and seq):
        raise HTTPException(
            status_code=400,
            detail="Identificador PNCP inválido. Formato esperado: CNPJ-TIPO-SEQ/ANO"
        )

    # Nova URL de consulta de compra unitária no PNCP
    url = f"https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{seq}"
    data = None
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            if response.status_code == 404:
                data = None
            else:
                response.raise_for_status()
                data = response.json()
    except Exception:
        data = None

    if not data:
        # Tenta buscar no banco local como fallback (caso PNCP esteja fora do ar ou o item não exista mais)
        from models import Edital
        edital_local = session.query(Edital).filter(Edital.id_pncp == id_pncp).first()
        if edital_local:
            return {
                "id": edital_local.id_pncp,
                "numero_controle_pncp": edital_local.id_pncp,
                "title": edital_local.titulo or f"Compra nº {seq}/{ano}",
                "description": edital_local.objeto or "Objeto não informado",
                "item_url": f"/compras/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else f"/compras/{id_pncp}",
                "orgao_nome": edital_local.orgao or "",
                "orgao_cnpj": cnpj or "",
                "unidade_nome": "",
                "esfera_id": "",
                "poder_id": "",
                "municipio_nome": edital_local.municipio or "",
                "uf": edital_local.uf or "",
                "modalidade_licitacao_nome": edital_local.modalidade or "",
                "situacao_nome": "Divulgada no PNCP",
                "data_publicacao_pncp": edital_local.data_publicacao.isoformat() if edital_local.data_publicacao else None,
                "data_inicio_vigencia": edital_local.data_abertura.isoformat() if edital_local.data_abertura else None,
                "data_fim_vigencia": None,
                "valor_global": float(edital_local.valor_estimado) if edital_local.valor_estimado is not None else None,
                "tipo_nome": "Edital",
                "cancelado": False,
            }
        else:
            raise HTTPException(
                status_code=404,
                detail="Licitação não encontrada na API pública do PNCP e sem registro local no banco."
            )

    item_url = f"/compras/{cnpj}/{ano}/{seq}"
    objeto = data.get("objetoCompra") or ""

    # Sincroniza metadados se já existir um registro local de processamento (Edital)
    from models import Edital
    edital_local = session.query(Edital).filter(Edital.id_pncp == id_pncp).first()
    if edital_local:
        edital_local.titulo = f"Compra nº {data.get('numeroCompra')}/{data.get('anoCompra')}"
        edital_local.orgao = data.get("orgaoEntidade", {}).get("razaoSocial") or ""
        edital_local.objeto = objeto
        edital_local.modalidade = data.get("modalidadeNome")
        edital_local.valor_estimado = data.get("valorTotalEstimado")
        unidade = data.get("unidadeOrgao") or {}
        edital_local.uf = _uf_valida(unidade.get("ufSigla")) or edital_local.uf
        edital_local.municipio = (unidade.get("municipioNome") or edital_local.municipio or "")[:255] or None
        
        # Sincroniza datas
        from datetime import datetime
        pub_str = data.get("dataPublicacaoPncp")
        if pub_str:
            try:
                edital_local.data_publicacao = datetime.fromisoformat(pub_str).date()
            except Exception:
                pass
        ab_str = data.get("dataAberturaProposta")
        if ab_str:
            try:
                edital_local.data_abertura = datetime.fromisoformat(ab_str).date()
            except Exception:
                pass
                
        session.commit()

    mapped_item = {
        "id": data.get("numeroControlePNCP"),
        "numero_controle_pncp": data.get("numeroControlePNCP"),
        "title": f"Compra nº {data.get('numeroCompra')}/{data.get('anoCompra')}",
        "description": objeto,
        "item_url": item_url,
        "orgao_nome": data.get("orgaoEntidade", {}).get("razaoSocial"),
        "orgao_cnpj": cnpj,
        "unidade_nome": data.get("unidadeOrgao", {}).get("nomeUnidade"),
        "esfera_id": data.get("orgaoEntidade", {}).get("esferaId"),
        "poder_id": data.get("orgaoEntidade", {}).get("poderId"),
        "municipio_nome": data.get("unidadeOrgao", {}).get("municipioNome"),
        "uf": data.get("unidadeOrgao", {}).get("ufSigla"),
        "modalidade_licitacao_nome": data.get("modalidadeNome"),
        "situacao_nome": data.get("situacaoCompraNome"),
        "data_publicacao_pncp": data.get("dataPublicacaoPncp"),
        "data_inicio_vigencia": data.get("dataAberturaProposta"),
        "data_fim_vigencia": data.get("dataEncerramentoProposta"),
        "valor_global": data.get("valorTotalEstimado"),
        "tipo_nome": data.get("tipoInstrumentoConvocatorioNome"),
        "cancelado": "cancelado" in (data.get("situacaoCompraNome") or "").lower(),
    }

    return mapped_item
