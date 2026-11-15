import os
import re
from datetime import datetime, timezone
from uuid import UUID

import requests
from celery import Task
from dotenv import load_dotenv
from database import SessionLocal

from arquivos import ErroDefinitivo, TAMANHO_MAXIMO_BYTES, descrever_formato, extrair_pdf
from worker import celery_app

load_dotenv()
PNCP_API = "https://pncp.gov.br/api/pncp/v1"
MAX_ARQUIVOS_TENTADOS = 5

MSG_ENVIE_MANUALMENTE = "Envie o PDF do edital manualmente pelo botão \"Enviar PDF do Edital\"."


def _chave_compra(id_pncp: str | None, item_url: str | None) -> tuple[str, str, int] | None:
    """Extrai (cnpj, ano, sequencial) de item_url ("/compras/{cnpj}/{ano}/{seq}")
    ou de id_pncp ("{cnpj}-{tipo}-{seq}/{ano}")."""
    if item_url:
        m = re.search(r'/compras/(\d+)/(\d+)/(\d+)', item_url)
        if m:
            return m.group(1), m.group(2), int(m.group(3))
    if id_pncp:
        m = re.search(r'(\d{14})-\d+-0*(\d+)/(\d{4})', id_pncp)
        if m:
            return m.group(1), m.group(3), int(m.group(2))
    return None


def _listar_arquivos_pncp(id_pncp: str | None, item_url: str | None) -> list[dict]:
    """Lista os arquivos publicados no PNCP para a compra, como [{"url", "titulo"}].

    Ordem: primeiro os que têm cara de edital em PDF, depois os demais documentos de
    edital, depois o resto. Falha de rede levanta exceção (a tarefa tenta de novo);
    compra sem arquivos devolve lista vazia.
    """
    chave = _chave_compra(id_pncp, item_url)
    if not chave:
        return []
    cnpj, ano, seq = chave

    resp = requests.get(f"{PNCP_API}/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos", timeout=15)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    docs = resp.json()
    if not isinstance(docs, list):
        return []

    arquivos = []
    for doc in docs:
        url = doc.get("url") or doc.get("urlPublica")
        if not url:
            continue
        if url.startswith("/"):
            url = f"https://pncp.gov.br{url}"
        titulo = doc.get("titulo") or ""
        eh_edital = "edital" in (doc.get("tipoDocumentoNome") or "").lower() or "edital" in titulo.lower()
        eh_pdf_pelo_nome = titulo.lower().endswith(".pdf")
        arquivos.append({"url": url, "titulo": titulo, "ordem": (not eh_edital, not eh_pdf_pelo_nome)})

    arquivos.sort(key=lambda a: a["ordem"])
    return arquivos


def _baixar_pdf_pncp(edital) -> tuple[bytes, str]:
    """Baixa o edital em PDF do PNCP. Devolve (bytes do PDF, URL de onde veio).

    Tenta até MAX_ARQUIVOS_TENTADOS arquivos, porque o primeiro da lista nem sempre é
    PDF (órgãos publicam .doc, .docx, planilhas e .zip). Se nenhum servir, levanta
    ErroDefinitivo dizendo quais formatos foram encontrados.
    """
    arquivos = _listar_arquivos_pncp(edital.id_pncp, edital.url_origem)
    if edital.url_pdf and edital.url_pdf not in [a["url"] for a in arquivos]:
        arquivos.insert(0, {"url": edital.url_pdf, "titulo": ""})

    if not arquivos:
        raise ErroDefinitivo(f"O PNCP não disponibiliza arquivos para esta compra. {MSG_ENVIE_MANUALMENTE}")

    formatos: list[str] = []
    for arquivo in arquivos[:MAX_ARQUIVOS_TENTADOS]:
        resp = requests.get(arquivo["url"], timeout=60)
        resp.raise_for_status()
        if len(resp.content) > TAMANHO_MAXIMO_BYTES:
            formatos.append("arquivo acima de 50 MB")
            continue
        pdf = extrair_pdf(resp.content)
        if pdf:
            return pdf, arquivo["url"]
        formatos.append(descrever_formato(resp.content, arquivo["titulo"]))

    encontrados = ", ".join(sorted(set(formatos)))
    if len(arquivos) == 1:
        raise ErroDefinitivo(
            f"O arquivo publicado no PNCP não é um PDF ({encontrados}), e o sistema só lê PDF. {MSG_ENVIE_MANUALMENTE}"
        )
    raise ErroDefinitivo(
        f"Nenhum dos {min(len(arquivos), MAX_ARQUIVOS_TENTADOS)} arquivos verificados no PNCP é um PDF "
        f"(encontrados: {encontrados}). {MSG_ENVIE_MANUALMENTE}"
    )


def _mensagem_para_usuario(exc: Exception) -> str:
    """Texto que vai para a tela e para a notificação.

    Erros previstos já vêm com mensagem escrita para o usuário. Para os demais, a
    mensagem da exceção pode conter detalhes internos, então fica só no log.
    """
    if isinstance(exc, ErroDefinitivo):
        return str(exc)
    if isinstance(exc, RuntimeError) and str(exc).startswith("Falha ao gerar o bloco"):
        if "RateLimitError" in str(exc):
            return "O limite de uso da IA foi atingido. Aguarde alguns minutos e clique em \"Tentar novamente\"."
        return "A IA não conseguiu gerar o resumo deste edital agora. Tente novamente em alguns minutos."
    if isinstance(exc, requests.RequestException):
        return "Não foi possível baixar o edital do PNCP (o portal não respondeu). Tente novamente em alguns minutos."
    return "Falha inesperada ao processar o edital. Tente novamente; se o erro continuar, envie o PDF manualmente."


@celery_app.task(bind=True, max_retries=2, name="processar_edital", default_retry_delay=30)
def processar_edital_task(self: Task, edital_id: str, usuario_id: str) -> dict:
    from models import (
        ChunkEdital, EmbeddingStatus, Edital, ExecucaoProcesso,
        Notificacao, ResumoEdital, StatusExecucao, StatusProcessamento, TipoProcesso,
    )
    from rag import edital_rag
    from rag.edital_rag import nome_colecao, processar_pdf

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

        # O resumo é apagado logo abaixo: o status precisa refletir isso, senão a tela
        # lê "PROCESSADO sem resumo" durante um reprocessamento.
        edital.status_processamento = StatusProcessamento.PROCESSANDO

        # Garante idempotência: remove chunks e resumos anteriores associados a este edital
        session.query(ChunkEdital).filter(ChunkEdital.edital_id == edital.id).delete()
        session.query(ResumoEdital).filter(ResumoEdital.edital_id == edital.id).delete()
        session.commit()

        try:
            # Só reaproveita o que está no banco se for mesmo um PDF. Um download antigo
            # em outro formato ficava guardado e era reutilizado em toda nova tentativa.
            pdf_bytes = extrair_pdf(edital.pdf_conteudo)
            if edital.pdf_conteudo and not pdf_bytes:
                edital.pdf_conteudo = None
                session.commit()

            if not pdf_bytes:
                if (edital.id_pncp or "").startswith("UPLOAD-"):
                    raise ErroDefinitivo("O arquivo enviado não é um PDF válido. Envie novamente o edital em PDF.")
                pdf_bytes, url_pdf = _baixar_pdf_pncp(edital)
                # Salva o PDF no banco de dados para evitar novos downloads e garantir rastreabilidade
                edital.url_pdf = url_pdf
                edital.pdf_conteudo = pdf_bytes
                session.commit()

            collection_name = nome_colecao(edital.id)
            resultado = processar_pdf(pdf_bytes, collection_name)

            chunks: list[str] = resultado["chunks"]
            trechos: list[dict] = resultado.get("trechos") or [{"text": txt} for txt in chunks]
            resumo_json: dict = resultado["resumo"]
            modelo_embedding = getattr(edital_rag, "EMBEDDING_MODEL", "").split("/")[-1] or None

            for idx, trecho in enumerate(trechos):
                session.add(ChunkEdital(
                    edital_id=edital.id,
                    ordem=idx,
                    texto=trecho["text"],
                    tokens=len(trecho["text"].split()),
                    pagina_inicial=trecho.get("pagina_inicial"),
                    pagina_final=trecho.get("pagina_final"),
                    embedding_status=EmbeddingStatus.GERADO,
                    qdrant_point_id=str(idx),
                    embedding_model=modelo_embedding,
                ))

            session.add(ResumoEdital(
                edital_id=edital.id,
                versao=1,
                json_resumo=resumo_json,
                modelo_usado=getattr(edital_rag, "LLM_MODEL", None),
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
            print(f"[Worker] Falha ao processar edital {edital_id}: {exc.__class__.__name__}: {exc}")
            # Como a sessão sofreu rollback, as instâncias de edital e execucao foram expiradas.
            # Recarregamos ambas do banco de dados para atualizar seus status de forma limpa.
            edital = session.query(Edital).filter(Edital.id == UUID(edital_id)).first()
            execucao = session.query(ExecucaoProcesso).filter(ExecucaoProcesso.id == execucao_id).first()
            mensagem = _mensagem_para_usuario(exc)

            if execucao:
                execucao.status = StatusExecucao.ERRO
                execucao.erro_mensagem = mensagem
                execucao.finalizado_em = datetime.now(timezone.utc)

            # Erro definitivo não adianta repetir; os demais são repetidos até max_retries.
            ultima_tentativa = isinstance(exc, ErroDefinitivo) or self.request.retries >= self.max_retries

            if not ultima_tentativa:
                # O edital continua PROCESSANDO entre as tentativas: marcar ERRO aqui fazia a
                # tela mostrar falha (e oferecer "Tentar novamente") com a tarefa ainda viva.
                session.commit()
                raise self.retry(exc=exc)

            if edital:
                edital.status_processamento = StatusProcessamento.ERRO
                session.add(Notificacao(
                    usuario_id=UUID(usuario_id),
                    tipo="EDITAL_ERRO",
                    titulo="Falha no processamento do edital",
                    mensagem=mensagem[:300],
                    edital_id=edital.id,
                    referencia=edital.id_pncp,
                ))
            session.commit()
            return {"edital_id": edital_id, "status": "ERRO", "erro": mensagem}
