import os
import re
from datetime import datetime, timezone
from uuid import UUID

import requests
from celery import Task
from dotenv import load_dotenv
from database import SessionLocal

from worker import celery_app

load_dotenv()
PNCP_API = "https://pncp.gov.br/api/pncp/v1"


def _buscar_url_pdf_pncp(id_pncp: str, item_url: str | None) -> str | None:
    """Busca a URL do PDF do edital via API pública do PNCP.

    Tenta extrair cnpj/ano/seq de item_url ("/compras/{cnpj}/{ano}/{seq}")
    ou de id_pncp ("{cnpj}-{tipo}-{seq}/{ano}").
    """
    try:
        cnpj = ano = seq = None

        if item_url:
            m = re.match(r'/compras/(\d+)/(\d+)/(\d+)', item_url)
            if m:
                cnpj, ano, seq = m.group(1), m.group(2), m.group(3)

        if not cnpj and id_pncp:
            m = re.match(r'(\d+)-\d+-0*(\d+)/(\d+)', id_pncp)
            if m:
                cnpj, seq, ano = m.group(1), m.group(2), m.group(3)

        if not (cnpj and ano and seq):
            return None

        url = f"{PNCP_API}/orgaos/{cnpj}/compras/{ano}/{int(seq)}/arquivos"
        resp = requests.get(url, timeout=15)
        if not resp.ok:
            return None

        docs = resp.json()
        if not docs:
            return None

        # Prioriza documento do tipo Edital
        for doc in docs:
            tipo  = (doc.get("tipoDocumentoNome") or "").lower()
            titulo = (doc.get("titulo") or "").lower()
            if "edital" in tipo or "edital" in titulo:
                url = doc.get("url")
                if url:
                    return url

        # Fallback: primeiro documento com URL
        return docs[0].get("url") if docs else None

    except Exception:
        return None


@celery_app.task(bind=True, max_retries=2, name="processar_edital", default_retry_delay=30)
def processar_edital_task(self: Task, edital_id: str, usuario_id: str) -> dict:
    from models import (
        ChunkEdital, EmbeddingStatus, Edital, ExecucaoProcesso,
        Notificacao, ResumoEdital, StatusExecucao, StatusProcessamento, TipoProcesso,
    )
    from rag.edital_rag import processar_pdf

    with SessionLocal() as session:
        edital = session.query(Edital).filter(Edital.id == UUID(edital_id)).first()
        if not edital:
            return {"error": "Edital não encontrado"}

        execucao = ExecucaoProcesso(
            edital_id=edital.id,
            tipo_processo=TipoProcesso.INGESTAO_PDF,
            status=StatusExecucao.EXECUTANDO,
            tentativas=self.request.retries + 1,
            worker_id=self.request.id,
        )
        session.add(execucao)
        session.commit()
        execucao_id = execucao.id

        # Garante idempotência: remove chunks e resumos anteriores associados a este edital
        session.query(ChunkEdital).filter(ChunkEdital.edital_id == edital.id).delete()
        session.query(ResumoEdital).filter(ResumoEdital.edital_id == edital.id).delete()
        session.commit()

        try:
            pdf_bytes = edital.pdf_conteudo

            if not pdf_bytes:
                # Busca URL do PDF se não estiver preenchida
                if not edital.url_pdf:
                    edital.url_pdf = _buscar_url_pdf_pncp(edital.id_pncp, edital.url_origem)
                    session.commit()

                if not edital.url_pdf:
                    raise ValueError(
                        "PDF do edital não disponível no PNCP. "
                        "Faça o upload manual via /cliente/editais/upload-pdf."
                    )

                resp = requests.get(edital.url_pdf, timeout=60)
                resp.raise_for_status()
                pdf_bytes = resp.content
                
                # Salva o PDF no banco de dados para evitar novos downloads e garantir rastreabilidade
                edital.pdf_conteudo = pdf_bytes
                session.commit()

            collection_name = f"edital_{str(edital.id).replace('-', '_')}"
            resultado = processar_pdf(pdf_bytes, collection_name)

            chunks: list[str] = resultado["chunks"]
            resumo_json: dict = resultado["resumo"]

            for idx, txt in enumerate(chunks):
                session.add(ChunkEdital(
                    edital_id=edital.id,
                    ordem=idx,
                    texto=txt,
                    tokens=len(txt.split()),
                    embedding_status=EmbeddingStatus.GERADO,
                    qdrant_point_id=str(idx),
                    embedding_model="all-MiniLM-L6-v2",
                ))

            session.add(ResumoEdital(
                edital_id=edital.id,
                versao=1,
                json_resumo=resumo_json,
                modelo_usado="llama-3.1-8b-instant",
                versao_prompt="v1",
                ativo=True,
            ))

            edital.status_processamento = StatusProcessamento.PROCESSADO
            execucao.status = StatusExecucao.SUCESSO
            execucao.finalizado_em = datetime.now(timezone.utc)

            objeto_resumido = (edital.objeto or "")[:60]
            session.add(Notificacao(
                usuario_id=UUID(usuario_id),
                tipo="EDITAL_PROCESSADO",
                titulo=f"Resumo pronto: {objeto_resumido}",
                mensagem="O edital foi processado e o resumo de 5 blocos está disponível.",
                edital_id=edital.id,
                referencia=edital.id_pncp,
            ))

            session.commit()
            return {"edital_id": edital_id, "status": "PROCESSADO", "chunks": len(chunks)}

        except Exception as exc:
            session.rollback()
            # Como a sessão sofreu rollback, as instâncias de edital e execucao foram expiradas.
            # Recarregamos ambas do banco de dados para atualizar seus status de forma limpa.
            edital = session.query(Edital).filter(Edital.id == UUID(edital_id)).first()
            execucao = session.query(ExecucaoProcesso).filter(ExecucaoProcesso.id == execucao_id).first()

            if edital:
                edital.status_processamento = StatusProcessamento.ERRO
            if execucao:
                execucao.status = StatusExecucao.ERRO
                execucao.erro_mensagem = str(exc)
                execucao.finalizado_em = datetime.now(timezone.utc)

            # Notifica o usuário apenas se todas as tentativas de reprocessamento se esgotaram
            if self.request.retries >= self.max_retries and edital:
                session.add(Notificacao(
                    usuario_id=UUID(usuario_id),
                    tipo="EDITAL_ERRO",
                    titulo="Falha no processamento do edital",
                    mensagem=str(exc)[:300],
                    edital_id=edital.id,
                    referencia=edital.id_pncp,
                ))

            session.commit()
            raise self.retry(exc=exc)
