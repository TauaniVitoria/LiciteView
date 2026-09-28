from typing import Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from dependencies import verificar_token
from models import Produto, Usuario
from schemas import (
    AnaliseViabilidadeCreate, AnaliseViabilidadeResponse,
    EditalProcessarRequest, EditalStatusResponse,
    NotificacaoResponse,
    PerguntaCreate, ProdutoCreate, ProdutoResponse, ProdutoUpdate,
)

cliente_router = APIRouter(prefix="/cliente", tags=["Cliente"])

PNCP_SEARCH_URL = "https://pncp.gov.br/api/search/"


@cliente_router.get("/debug/pncp-raw")
async def debug_pncp_raw(q: str = "computador"):
    """Retorna o primeiro item bruto do PNCP para inspecionar os campos reais."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                PNCP_SEARCH_URL,
                params={
                    "q": q,
                    "tipos_documento": "edital",
                    "pagina": 1,
                    "tam_pagina": 1,
                    "ordenacao": "-data",
                    "status": "recebendo_proposta",
                },
            )
            response.raise_for_status()
            data = response.json()
            items = data.get("data") or data.get("items") or []
            return {
                "keys_raiz": list(data.keys()),
                "total": data.get("totalRegistros") or data.get("total"),
                "keys_item": list(items[0].keys()) if items else [],
                "primeiro_item": items[0] if items else None,
            }
    except Exception as e:
        return {"erro": str(e)}


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


@cliente_router.post("/editais/processar", status_code=202)
def processar_edital(
    dados: EditalProcessarRequest,
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    from models import Edital, StatusProcessamento

    edital = session.query(Edital).filter(Edital.id_pncp == dados.id_pncp).first()

    if not edital:
        edital = Edital(
            id_pncp=dados.id_pncp,
            titulo=dados.titulo,
            orgao=dados.orgao,
            objeto=dados.objeto,
            modalidade=dados.modalidade,
            valor_estimado=dados.valor_estimado,
            url_origem=dados.url_origem,
            url_pdf=dados.url_pdf,
            data_publicacao=dados.data_publicacao,
            data_abertura=dados.data_abertura,
            status_processamento=StatusProcessamento.PENDENTE,
        )
        session.add(edital)
        session.commit()
        session.refresh(edital)

    if edital.status_processamento == StatusProcessamento.PROCESSADO:
        return {"edital_id": str(edital.id), "status": "PROCESSADO"}

    # PROCESSANDO sem execução registrada = worker não estava rodando → reenfileira
    if edital.status_processamento == StatusProcessamento.PROCESSANDO:
        from models import ExecucaoProcesso
        tem_execucao = session.query(ExecucaoProcesso).filter(
            ExecucaoProcesso.edital_id == edital.id
        ).first()
        if tem_execucao:
            return {"edital_id": str(edital.id), "status": "PROCESSANDO"}
        # Sem execução = task nunca rodou, reseta para reenfileirar
        edital.status_processamento = StatusProcessamento.PENDENTE
        session.commit()

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
def status_edital(edital_id: str, session: Session = Depends(get_db)):
    from models import (
        ChunkEdital, Edital, ExecucaoProcesso,
        ResumoEdital as ResumoEditalModel, StatusExecucao, StatusProcessamento,
    )

    try:
        uid = UUID(edital_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="edital_id inválido (deve ser UUID).")

    edital = session.query(Edital).filter(Edital.id == uid).first()
    if not edital:
        raise HTTPException(status_code=404, detail="Edital não encontrado.")

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
    """Retorna o histórico de todas as licitações/editais registrados no banco local."""
    from models import Edital
    
    # Busca todos os editais cadastrados, ordenando pelos mais recentes
    editais = session.query(Edital).order_by(Edital.criado_em.desc()).all()
    
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
            "municipio_nome": "",
            "uf": "",
            "modalidade_licitacao_nome": ed.modalidade or "",
            "situacao_nome": "Divulgada no PNCP",
            "data_publicacao_pncp": ed.data_publicacao.isoformat() if ed.data_publicacao else None,
            "data_inicio_vigencia": ed.data_abertura.isoformat() if ed.data_abertura else None,
            "data_fim_vigencia": None,
            "valor_global": float(ed.valor_estimado) if ed.valor_estimado is not None else None,
            "tipo_nome": "Edital",
            "cancelado": False,
            "status_processamento": ed.status_processamento.value if ed.status_processamento else None,
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

    if not (arquivo.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos.")

    pdf_bytes = arquivo.file.read()

    if len(pdf_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Arquivo muito grande. Máximo: 50 MB.")

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


@cliente_router.post("/editais/{edital_id}/perguntar")
def perguntar_edital(
    edital_id: str,
    body: PerguntaCreate,
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    from datetime import datetime, timezone
    from models import Edital, PerguntaEdital, StatusPergunta, StatusProcessamento

    edital = session.query(Edital).filter(Edital.id == UUID(edital_id)).first()
    if not edital:
        raise HTTPException(status_code=404, detail="Edital não encontrado.")

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
        from rag.edital_rag import responder_pergunta
        collection_name = f"edital_{edital_id.replace('-', '_')}"
        resultado = responder_pergunta(collection_name, body.pergunta)

        pergunta_db.resposta = resultado["resposta"]
        pergunta_db.trecho_fonte = resultado.get("trecho_fonte")
        pergunta_db.status = StatusPergunta.RESPONDIDA
        pergunta_db.respondida_em = datetime.now(timezone.utc)
        session.commit()

        return {
            "resposta": resultado["resposta"],
            "trecho_fonte": resultado.get("trecho_fonte"),
            "chunks_utilizados": resultado["chunks_utilizados"],
        }

    except Exception as exc:
        pergunta_db.status = StatusPergunta.ERRO
        session.commit()
        raise HTTPException(status_code=500, detail=f"Erro ao processar pergunta: {exc}")


# ── Viabilidade ───────────────────────────────────────────────────────────────

def _calcular_frete_antt(session, distancia_km: float, peso_total_kg: float) -> float:
    """Calcula o custo de frete usando a Tabela TACO da ANTT (Carga Geral, 2 eixos).

    Fórmula: custo_por_viagem = CC + CCD × distância_km
    Número de viagens = ceil(peso_total_ton / capacidade_caminhão)
    """
    import math
    from models import TabelaFreteANTT

    ccd = session.query(TabelaFreteANTT).filter(
        TabelaFreteANTT.tipo_carga_nome.ilike('%Carga Geral%'),
        TabelaFreteANTT.coeficiente == 'CCD',
        TabelaFreteANTT.ativo == True,
    ).first()
    cc = session.query(TabelaFreteANTT).filter(
        TabelaFreteANTT.tipo_carga_nome.ilike('%Carga Geral%'),
        TabelaFreteANTT.coeficiente == 'CC',
        TabelaFreteANTT.ativo == True,
    ).first()

    if not ccd or not cc or not ccd.eixos_2 or not cc.eixos_2:
        return 0.0

    capacidade_ton = 5.0  # caminhão 2 eixos ≈ 5 t de carga
    num_viagens = max(1, math.ceil((peso_total_kg / 1000) / capacidade_ton))
    custo_por_viagem = float(cc.eixos_2) + float(ccd.eixos_2) * distancia_km
    return custo_por_viagem * num_viagens


def _calcular_viabilidade(session, edital, produto, valor_referencia=None) -> dict:
    """Cálculo de viabilidade usando:

    1. LLM extrai quantidade, cep_entrega e prazo_dias do resumo do edital.
    2. ViaCEP converte CEPs em UFs.
    3. Distância aproximada entre capitais estaduais (fórmula de Haversine × 1,3).
    4. Tabela TACO da ANTT (Carga Geral, 2 eixos) para custo de frete real.
    5. Cálculo determinístico de margem, sem dependência do LLM para a decisão final.
    """
    from decimal import Decimal
    from models import ClassificacaoViabilidade, ResumoEdital as ResumoModel, VariavelViabilidade, Usuario
    from rag.edital_rag import extrair_variaveis_edital, distancia_entre_ufs, uf_from_cep, distancia_entre_ceps

    if valor_referencia is not None:
        valor = float(valor_referencia)
    else:
        valor = float(edital.valor_estimado or 0)
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

    quantidade   = variaveis.get("quantidade") or 0
    cep_entrega  = variaveis.get("cep_entrega")
    uf_entrega   = variaveis.get("uf_entrega")

    # 1.B. Extração de dados específicos do item correspondente ao produto no edital via RAG
    from rag.edital_rag import extrair_dados_item_edital
    dados_item = {}
    try:
        dados_item = extrair_dados_item_edital(
            collection_name=f"edital_{edital.id}",
            produto_nome=produto.nome,
            produto_descricao=produto.descricao or ""
        )
    except Exception as e:
        print(f"[Viabilidade] Erro ao extrair dados do item via RAG: {e}")

    qty_item = dados_item.get("quantidade")
    val_unit_item = dados_item.get("valor_unitario_estimado")

    # ── 2. Distância para frete ───────────────────────────────────────────
    usuario = session.query(Usuario).filter(Usuario.id == produto.usuario_id).first()
    cep_origem = produto.cep or (usuario.cep if usuario else None) or "01001-000"

    distancia = None
    if cep_origem and cep_entrega:
        distancia = distancia_entre_ceps(cep_origem, cep_entrega)

    if distancia is None:
        # Fallback para estados se não conseguirmos obter coordenadas dos CEPs
        uf_origem = produto.uf or (usuario.uf if usuario else "SP") or "SP"
        if cep_entrega and not uf_entrega:
            uf_entrega = uf_from_cep(cep_entrega)
        
        import re
        uf_match = None
        if edital.orgao:
            uf_match = re.search(
                r'\b(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)\b',
                edital.orgao.upper()
            )
        if not uf_match and edital.objeto:
            uf_match = re.search(
                r'\b(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)\b',
                edital.objeto.upper()
            )
        uf_destino = uf_entrega or (uf_match.group(1) if uf_match else "SP")
        distancia = distancia_entre_ufs(uf_origem, uf_destino)

    # ── 3. Quantidade e preço ─────────────────────────────────────────────
    if produto.preco_venda and float(produto.preco_venda) > 0:
        preco = float(produto.preco_venda)
    else:
        denominador = max(1 - marg_min - imp - 0.05, 0.05)
        preco = custo / denominador

    # Resolve quantidade: prioriza o item específico, depois o geral do resumo
    qty = qty_item or quantidade
    if not qty or qty <= 0:
        qty = int(valor / preco) if preco > 0 else 1
    quantidade = qty

    # Resolve receita estimada (valor):
    if valor_referencia is not None:
        valor = float(valor_referencia)
    else:
        if val_unit_item and val_unit_item > 0:
            valor = float(val_unit_item) * quantidade
        else:
            valor = float(edital.valor_estimado or 0)

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
        just = f"Prejuízo estimado de {abs(marg):.1%}. Custos (R$ {custo_total:,.0f}) superam a receita (R$ {valor:,.0f})."
    elif not dentro:
        classe = ClassificacaoViabilidade.ATENCAO
        just = (f"Margem estimada ({marg:.1%}) abaixo da mínima ({marg_min:.1%}). "
                f"Frete: R$ {custo_frete:,.0f} ({distancia:.0f} km, {uf_origem}→{uf_destino}).")
    else:
        classe = ClassificacaoViabilidade.VALE_A_PENA
        just = (f"Margem estimada ({marg:.1%}) acima da mínima ({marg_min:.1%}). "
                f"Frete: R$ {custo_frete:,.0f} ({distancia:.0f} km, {uf_origem}→{uf_destino}).")

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
    }


@cliente_router.post("/analise", response_model=AnaliseViabilidadeResponse)
def criar_analise(
    dados: AnaliseViabilidadeCreate,
    usuario: Usuario = Depends(verificar_token),
    session: Session = Depends(get_db),
):
    from models import AnaliseViabilidade, Edital, Produto

    edital = session.query(Edital).filter(Edital.id == dados.edital_id).first()
    if not edital:
        raise HTTPException(status_code=404, detail="Edital não encontrado.")

    produto = session.query(Produto).filter(
        Produto.id == dados.produto_id,
        Produto.usuario_id == usuario.id,
        Produto.ativo == True,
    ).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    # Executa o cálculo de viabilidade (passando valor_referencia que pode ser None)
    r = _calcular_viabilidade(session, edital, produto, valor_referencia=dados.valor_referencia)

    # Se a receita calculada ainda for zero ou menor, significa que nem o edital nem a IA conseguiram
    # estimar o valor total da receita/item, e o usuário não passou um valor_referencia.
    if r["receita"] <= 0:
        raise HTTPException(
            status_code=422,
            detail="Edital sem valor estimado — informe o valor do lote ou item para calcular a viabilidade."
        )

    # Verifica cache no banco usando a receita real calculada
    existente = session.query(AnaliseViabilidade).filter(
        AnaliseViabilidade.edital_id == dados.edital_id,
        AnaliseViabilidade.produto_id == dados.produto_id,
        AnaliseViabilidade.usuario_id == usuario.id,
        AnaliseViabilidade.receita_estimada == r["receita"],
    ).first()
    if existente:
        return existente

    analise = AnaliseViabilidade(
        edital_id=dados.edital_id,
        produto_id=dados.produto_id,
        usuario_id=usuario.id,
        margem_minima_snapshot=produto.margem_minima,
        preco_venda_snapshot=r["preco_venda_est"],
        custo_produto_snapshot=produto.custo_produto,
        distancia_km=r.get("distancia_km"),
        custo_frete_estimado=r["custo_frete"],
        custo_total_estimado=r["custo_total"],
        receita_estimada=r["receita"],
        margem_estimada=r["margem"],
        dentro_margem=r["dentro"],
        classificacao=r["classificacao"],
        justificativa=r["justificativa"],
        modelo_usado="deterministic-v1",
        versao_prompt="v1",
    )
    session.add(analise)
    session.commit()
    session.refresh(analise)
    return analise


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
                "municipio_nome": "",
                "uf": "",
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
