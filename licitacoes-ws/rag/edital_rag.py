import io
import json
import math
import os
import re
import time
from uuid import uuid4

import requests
from dotenv import load_dotenv
from groq import Groq
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams
from fastembed import TextEmbedding

from config import COHERE_API_KEY

_model = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
_groq = Groq()
_qdrant = QdrantClient(
    url=os.getenv("QDRANT_HOST"),
    api_key=os.getenv("QDRANT_API_KEY"),
)

VECTOR_SIZE = 384  # dimensão fixa do all-MiniLM-L6-v2
CHUNK_WORDS = 450
OVERLAP_WORDS = 75
LLM_MODEL = "llama-3.1-8b-instant"

# ── Coordenadas aproximadas das capitais brasileiras ─────────────────────────
_COORDS = {
    'AC': (-9.97, -67.81),  'AL': (-9.67, -35.74),  'AM': (-3.10, -60.03),
    'AP': (0.03, -51.07),   'BA': (-12.97, -38.50),  'CE': (-3.73, -38.52),
    'DF': (-15.78, -47.93), 'ES': (-20.32, -40.34),  'GO': (-16.68, -49.25),
    'MA': (-2.52, -44.30),  'MG': (-19.93, -43.94),  'MS': (-20.44, -54.64),
    'MT': (-15.60, -56.10), 'PA': (-1.46, -48.50),   'PB': (-7.12, -34.86),
    'PE': (-8.05, -34.88),  'PI': (-5.09, -42.80),   'PR': (-25.43, -49.27),
    'RJ': (-22.90, -43.17), 'RN': (-5.79, -35.21),   'RO': (-8.76, -63.90),
    'RR': (2.82, -60.67),   'RS': (-30.03, -51.23),  'SC': (-27.59, -48.55),
    'SE': (-10.91, -37.07), 'SP': (-23.55, -46.63),  'TO': (-10.25, -48.34),
}


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a)) * 1.3  # fator de tortuosidade rodovia


def distancia_entre_ufs(uf1: str, uf2: str) -> float:
    """Distância aproximada (km) entre capitais de dois estados."""
    if uf1 == uf2:
        return 50.0
    lat1, lon1 = _COORDS.get(uf1, (-15.78, -47.93))
    lat2, lon2 = _COORDS.get(uf2, (-15.78, -47.93))
    return round(_haversine(lat1, lon1, lat2, lon2), 1)


def uf_from_cep(cep: str) -> str | None:
    """Retorna a UF de um CEP via ViaCEP. Retorna None em caso de falha."""
    try:
        cep_clean = re.sub(r"\D", "", cep)
        if len(cep_clean) != 8:
            return None
        resp = requests.get(f"https://viacep.com.br/ws/{cep_clean}/json/", timeout=5)
        if resp.ok:
            return resp.json().get("uf")
    except Exception:
        pass
    return None


def coords_from_cep(cep: str) -> tuple[float, float] | None:
    """Retorna (latitude, longitude) para um CEP brasileiro usando APIs públicas gratuitas.

    Tenta BrasilAPI primeiro, com fallback para AwesomeAPI.
    """
    try:
        cep_clean = re.sub(r"\D", "", cep)
        if len(cep_clean) != 8:
            return None

        # Tenta BrasilAPI
        url = f"https://brasilapi.com.br/api/cep/v2/{cep_clean}"
        resp = requests.get(url, timeout=3)
        if resp.ok:
            data = resp.json()
            loc = data.get("location", {})
            coords = loc.get("coordinates", {})
            lat = coords.get("latitude")
            lng = coords.get("longitude")
            if lat is not None and lng is not None:
                return float(lat), float(lng)
    except Exception:
        pass

    try:
        # Tenta AwesomeAPI
        cep_clean = re.sub(r"\D", "", cep)
        url = f"https://cep.awesomeapi.com.br/json/{cep_clean}"
        resp = requests.get(url, timeout=3)
        if resp.ok:
            data = resp.json()
            lat = data.get("lat")
            lng = data.get("lng")
            if lat is not None and lng is not None:
                return float(lat), float(lng)
    except Exception:
        pass

    return None


def distancia_entre_ceps(cep1: str, cep2: str) -> float | None:
    """Calcula a distância rodoviária aproximada (km) entre dois CEPs usando coordenadas reais.

    Retorna None se não for possível obter as coordenadas de um dos CEPs.
    """
    c1 = coords_from_cep(cep1)
    if not c1:
        return None
    c2 = coords_from_cep(cep2)
    if not c2:
        return None
    return round(_haversine(c1[0], c1[1], c2[0], c2[1]), 1)


# ── PDF extraction ────────────────────────────────────────────────────────────

def _desempacotar_pdf_de_zip(pdf_bytes: bytes) -> bytes:
    """Se os bytes forem um ZIP, extrai o primeiro PDF encontrado dentro dele.

    O PNCP às vezes disponibiliza editais empacotados em ZIP contendo
    o PDF do edital + anexos. O magic bytes b'PK\\x03\\x04' identifica ZIPs.
    """
    import zipfile

    if not pdf_bytes[:4] == b"PK\x03\x04":
        return pdf_bytes

    with zipfile.ZipFile(io.BytesIO(pdf_bytes)) as z:
        pdfs = [n for n in z.namelist() if n.lower().endswith(".pdf")]
        if not pdfs:
            raise ValueError("Arquivo ZIP não contém PDF interno.")
        # Prioriza arquivo com 'edital' no nome
        alvo = next((n for n in pdfs if "edital" in n.lower()), pdfs[0])
        return z.read(alvo)


def extrair_texto_pdf(pdf_bytes: bytes) -> str:
    """Extrai texto do PDF usando PyMuPDF (fitz) — leve, sem torch/ML.

    PyMuPDF detecta estrutura de seções por tamanho de fonte e gera
    texto hierárquico (# título, ## subtítulo) adequado para chunking.
    Fallback para pypdf em caso de erro.
    """
    pdf_bytes = _desempacotar_pdf_de_zip(pdf_bytes)

    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        partes: list[str] = []

        for page in doc:
            blocos = page.get_text("dict").get("blocks", [])
            paragrafos: list[str] = []
            for bloco in blocos:
                if bloco.get("type") != 0:
                    continue
                # Concatena todas as linhas do bloco (parágrafo) para preservar contexto
                linhas_bloco: list[str] = []
                tamanho_max = 10.0
                for linha in bloco.get("lines", []):
                    spans = linha.get("spans", [])
                    texto = " ".join(s.get("text", "") for s in spans).strip()
                    if texto:
                        linhas_bloco.append(texto)
                        t = max((s.get("size", 10) for s in spans), default=10)
                        tamanho_max = max(tamanho_max, t)
                if not linhas_bloco:
                    continue
                texto_bloco = " ".join(linhas_bloco)
                # Detecta headings pelo tamanho de fonte do bloco
                if tamanho_max > 14:
                    paragrafos.append(f"# {texto_bloco}")
                elif tamanho_max > 12:
                    paragrafos.append(f"## {texto_bloco}")
                else:
                    paragrafos.append(texto_bloco)
            if paragrafos:
                partes.append("\n\n".join(paragrafos))

        doc.close()
        resultado = "\n\n".join(partes)
        if resultado.strip():
            return resultado
    except Exception:
        pass

    # Fallback para pypdf
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return "\n\n".join(p.extract_text() or "" for p in reader.pages)


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunkar_texto(texto: str, tamanho: int = CHUNK_WORDS, overlap: int = OVERLAP_WORDS) -> list[str]:
    palavras = texto.split()
    chunks, i = [], 0
    while i < len(palavras):
        chunk = " ".join(palavras[i: i + tamanho])
        if chunk.strip():
            chunks.append(chunk)
        passo = max(1, tamanho - overlap)
        i += passo
    return chunks


# ── Qdrant ────────────────────────────────────────────────────────────────────

def _criar_colecao(collection_name: str):
    try:
        _qdrant.get_collection(collection_name)
    except Exception:
        _qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def _indexar_chunks(collection_name: str, chunks: list[str]):
    embeddings = list(_model.embed(chunks))  # fastembed: batch eficiente
    points = [
        PointStruct(id=idx, vector=emb.tolist(), payload={"text": chunk, "ordem": idx})
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings))
    ]
    _qdrant.upsert(collection_name=collection_name, points=points, wait=True)


def rerank_chunks(query: str, chunks: list[str], top_n: int = 5) -> list[str]:
    """Reordena os chunks com base na relevância semântica usando Cohere Rerank.

    Faz fallback silencioso para os top_n chunks originais em caso de falha.
    """
    if not COHERE_API_KEY or not chunks:
        return chunks[:top_n]

    try:
        import requests
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Bearer {COHERE_API_KEY}"
        }
        payload = {
            "model": "rerank-multilingual-v3.0",
            "query": query,
            "documents": chunks,
            "top_n": top_n
        }
        resp = requests.post("https://api.cohere.com/v1/rerank", json=payload, headers=headers, timeout=4.0)
        if resp.ok:
            results = resp.json().get("results", [])
            reranked = []
            for r in results:
                idx = r.get("index")
                if idx is not None and idx < len(chunks):
                    reranked.append(chunks[idx])
            if reranked:
                return reranked
    except Exception as e:
        print(f"[Rerank] Erro na chamada do Cohere Rerank: {e}")

    return chunks[:top_n]


def buscar_chunks(collection_name: str, query: str, top_k: int = 5) -> list[str]:
    query_vec = list(_model.embed([query]))[0].tolist()
    # Se COHERE_API_KEY estiver configurado, buscamos mais candidatos para o reranking
    limit = top_k * 3 if COHERE_API_KEY else top_k
    results = _qdrant.query_points(collection_name=collection_name, query=query_vec, limit=limit, with_payload=True)
    chunks = [hit.payload["text"] for hit in results.points]

    if COHERE_API_KEY:
        return rerank_chunks(query, chunks, top_n=top_k)
    return chunks


# ── Extração de variáveis do edital via LLM ───────────────────────────────────

_SYSTEM_VARIAVEIS = (
    "Você é um especialista em licitações públicas. "
    "Extraia variáveis numéricas e estruturadas do resumo do edital. "
    "Retorne APENAS JSON válido, sem texto adicional."
)


def extrair_variaveis_edital(json_resumo: dict) -> dict:
    """Extrai variáveis tipadas do resumo gerado pelo pipeline RAG.

    Retorna dict com: quantidade, cep_entrega, prazo_dias, valor_unitario_estimado.
    Campos não encontrados têm valor null/None.
    """
    prompt = f"""Analise este resumo de edital e extraia as variáveis abaixo.

Resumo:
{json.dumps(json_resumo, ensure_ascii=False, indent=2)}

Retorne JSON com esta estrutura exata:
{{
  "quantidade": <número inteiro de unidades/itens solicitados ou null>,
  "cep_entrega": <CEP de entrega no formato NNNNN-NNN ou null>,
  "uf_entrega": <sigla do estado de entrega (ex: SP) ou null>,
  "prazo_dias": <prazo de entrega em dias corridos como inteiro ou null>,
  "valor_unitario_estimado": <valor estimado por unidade em R$ como decimal ou null>
}}"""

    try:
        resp = _groq.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_VARIAVEIS},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return {}


# ── RAG para resumo ────────────────────────────────────────────────────────────

_SYSTEM_LICITACAO = (
    "Você é um especialista em licitações públicas brasileiras. "
    "Analise o trecho do edital e extraia as informações solicitadas. "
    "Use apenas o contexto fornecido. Se não encontrar, use null."
)

_BLOCOS: dict[str, dict] = {
    "bloco1_visao_geral": {
        "query": "objeto da licitação órgão responsável modalidade critério julgamento número edital",
        "schema": {"objeto": None, "orgao": None, "modalidade": None, "criterio_julgamento": None, "numero_edital": None},
    },
    "bloco2_prazos": {
        "query": "prazo entrega vigência contrato local entrega data abertura proposta",
        "schema": {"prazo_entrega": None, "vigencia_contrato": None, "local_entrega": None, "data_abertura": None},
    },
    "bloco3_documentacao": {
        "query": "documentos habilitação regularidade fiscal certidão qualificação técnica econômica financeira",
        "schema": {"documentos_habilitacao": [], "regularidade_fiscal": [], "qualificacao_tecnica": []},
    },
    "bloco4_requisitos_tecnicos": {
        "query": "especificações técnicas produto certificação norma ABNT amostra requisito técnico",
        "schema": {"especificacoes_resumo": None, "certificacoes_exigidas": [], "exige_amostra": None, "outros_requisitos": []},
    },
    "bloco5_riscos": {
        "query": "multa penalidade sanção rescisão cláusula garantia risco atenção",
        "schema": {"multas": [], "sancoes": [], "clausulas_criticas": [], "pontos_atencao": []},
    },
}


MAX_CONTEXT_CHARS = 4500  # ~5500 tokens — dentro do limite do Groq free tier


def _gerar_bloco(collection_name: str, query: str, schema: dict) -> dict:
    chunks = buscar_chunks(collection_name, query, top_k=4)
    context = "\n\n---\n\n".join(chunks)
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS]
    prompt = (
        f"Trecho do edital:\n{context}\n\n"
        f"Extraia as informações e retorne SOMENTE um JSON com esta estrutura "
        f"(use null para campos não encontrados):\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )
    try:
        resp = _groq.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_LICITACAO},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return schema


def processar_pdf(pdf_bytes: bytes, collection_name: str) -> dict:
    """Processa PDF com collection_name explícito (usado pelo worker Celery)."""
    texto = extrair_texto_pdf(pdf_bytes)
    if not texto.strip():
        raise ValueError("Não foi possível extrair texto do PDF.")

    chunks = chunkar_texto(texto)
    _criar_colecao(collection_name)
    _indexar_chunks(collection_name, chunks)

    resumo: dict = {}
    for chave, cfg in _BLOCOS.items():
        resumo[chave] = _gerar_bloco(collection_name, cfg["query"], cfg["schema"])
        time.sleep(1.2)  # evita estourar o TPM do Groq free tier (413)

    return {"chunks": chunks, "resumo": resumo, "total_chunks": len(chunks)}


def processar_edital(pdf_bytes: bytes) -> dict:
    """Versão standalone com UUID gerado internamente (usado pelo upload manual)."""
    edital_id = str(uuid4())
    collection_name = f"edital_{edital_id.replace('-', '_')}"
    resultado = processar_pdf(pdf_bytes, collection_name)
    return {"edital_id": edital_id, "collection_name": collection_name, **resultado}


def responder_pergunta(collection_name: str, pergunta: str) -> dict:
    chunks = buscar_chunks(collection_name, pergunta, top_k=5)
    context = "\n\n---\n\n".join(chunks)
    resp = _groq.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": "Você é um especialista em licitações públicas. Use APENAS o contexto do edital para responder. Seja objetivo e cite o trecho relevante quando possível."},
            {"role": "user", "content": f"Contexto do edital:\n{context}\n\nPergunta: {pergunta}"},
        ],
        temperature=0,
    )
    trecho = chunks[0][:300].strip() if chunks else None
    return {"resposta": resp.choices[0].message.content, "chunks_utilizados": len(chunks), "trecho_fonte": trecho}


def extrair_dados_item_edital(collection_name: str, produto_nome: str, produto_descricao: str) -> dict:
    """Busca trechos do edital relacionados ao produto de interesse e extrai a
    quantidade e o valor unitário estimado desse item específico usando LLM.
    """
    query = f"quantidade valor unitário estimado lote item {produto_nome}"
    try:
        chunks = buscar_chunks(collection_name, query, top_k=4)
    except Exception as e:
        print(f"[Extração Item] Erro ao buscar chunks: {e}")
        return {}

    context = "\n\n---\n\n".join(chunks)
    
    prompt = f"""Você é um especialista em licitações públicas.
Analise os trechos do edital e identifique o item/lote que mais se assemelha ao produto abaixo:
Produto de interesse: {produto_nome}
Descrição: {produto_descricao}

Com base nisso, extraia a quantidade solicitada e o valor unitário estimado para esse item específico nos trechos fornecidos.

Trechos do edital:
{context}

Retorne APENAS um JSON válido nesta estrutura exata (se algum campo não for encontrado, retorne null):
{{
  "quantidade": <número inteiro da quantidade do item ou null>,
  "valor_unitario_estimado": <valor unitário estimado em R$ como número decimal/float ou null>
}}
"""
    try:
        resp = _groq.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "Você é um extrator de variáveis numéricas de licitações. Retorne exclusivamente JSON válido."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print(f"[Extração Item] Erro na chamada do Groq: {e}")
        return {}
