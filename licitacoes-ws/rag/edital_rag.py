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

from arquivos import ErroDefinitivo
from config import COHERE_API_KEY

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_model = TextEmbedding(EMBEDDING_MODEL)
_groq = Groq()
_qdrant = QdrantClient(
    url=os.getenv("QDRANT_HOST"),
    api_key=os.getenv("QDRANT_API_KEY"),
)

VECTOR_SIZE = 384  # dimensão fixa do all-MiniLM-L6-v2
# Trechos menores cabem em maior número no contexto do LLM e são representados por inteiro
# no vetor (o modelo lê ~256 tokens; com 450 palavras mais da metade do trecho ficava de fora).
CHUNK_WORDS = 200
OVERLAP_WORDS = 40

# Busca híbrida: candidatos da busca vetorial + candidatos da busca por palavras, reordenados.
# Medido no edital real (14 perguntas): só vetorial recuperava a resposta em 9; híbrida, em 14.
N_VETORIAL = 12
N_PALAVRAS = 12
# O contexto é limitado em palavras, não em número de trechos, para funcionar igual com as
# coleções antigas (trechos de 450 palavras) e as novas (200).
PALAVRAS_CHAT = 2250
PALAVRAS_RESUMO = 1000
LLM_MODEL = "openai/gpt-oss-20b"
# O gpt-oss raciocina antes de responder; com o esforço padrão ele às vezes gasta
# a resposta inteira raciocinando e a Groq devolve 400 json_validate_failed.
LLM_REASONING_EFFORT = "low"
TENTATIVAS_BLOCO = 3


def nome_colecao(edital_id) -> str:
    """Nome da coleção do edital no Qdrant (única fonte, usada por worker, chat e viabilidade)."""
    return f"edital_{str(edital_id).replace('-', '_')}"

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


def extrair_paginas(pdf_bytes: bytes) -> list[str]:
    """Extrai o texto do PDF, uma string por página (posição 0 = página 1).

    Usa PyMuPDF (fitz) — leve, sem torch/ML —, que detecta títulos pelo tamanho da fonte
    e gera texto hierárquico (# título, ## subtítulo). Fallback para pypdf em caso de erro.
    Páginas sem texto ficam como string vazia, para a numeração não se perder.
    """
    pdf_bytes = _desempacotar_pdf_de_zip(pdf_bytes)

    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        paginas: list[str] = []

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
            paginas.append("\n\n".join(paragrafos))

        doc.close()
        if any(p.strip() for p in paginas):
            return paginas
    except Exception:
        pass

    # Fallback para pypdf
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        return [p.extract_text() or "" for p in reader.pages]
    except Exception as exc:
        print(f"[PDF] Nenhuma biblioteca conseguiu ler o arquivo: {exc.__class__.__name__}: {exc}")
        raise ErroDefinitivo(
            "Não foi possível ler o PDF: o arquivo está corrompido ou protegido por senha. "
            "Envie outra cópia do edital em PDF."
        ) from exc


def extrair_texto_pdf(pdf_bytes: bytes) -> str:
    """Texto completo do PDF (todas as páginas com texto, separadas por linha em branco)."""
    return "\n\n".join(p for p in extrair_paginas(pdf_bytes) if p.strip())


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


def chunkar_paginas(paginas: list[str], tamanho: int = CHUNK_WORDS, overlap: int = OVERLAP_WORDS) -> list[dict]:
    """Divide o texto em trechos de `tamanho` palavras, guardando de que páginas cada um veio.

    Devolve [{"text", "pagina_inicial", "pagina_final"}], com páginas numeradas a partir de 1.
    """
    palavras: list[tuple[str, int]] = [
        (palavra, numero) for numero, texto in enumerate(paginas, start=1) for palavra in texto.split()
    ]
    passo = max(1, tamanho - overlap)
    trechos: list[dict] = []
    for i in range(0, len(palavras), passo):
        janela = palavras[i: i + tamanho]
        if not janela:
            break
        trechos.append({
            "text": " ".join(p for p, _ in janela),
            "pagina_inicial": janela[0][1],
            "pagina_final": janela[-1][1],
        })
        if i + tamanho >= len(palavras):
            break
    return trechos


# ── Qdrant ────────────────────────────────────────────────────────────────────

def _recriar_colecao(collection_name: str):
    """Apaga a coleção, se existir, e cria de novo.

    Um reprocessamento que gerasse menos trechos que o anterior deixava os trechos
    antigos excedentes na coleção, misturados aos novos.
    """
    try:
        _qdrant.delete_collection(collection_name)
    except Exception:
        pass
    _qdrant.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    _cache_trechos.pop(collection_name, None)


def _indexar_trechos(collection_name: str, trechos: list[dict]):
    embeddings = list(_model.embed([t["text"] for t in trechos]))  # fastembed: batch eficiente
    points = [
        PointStruct(id=idx, vector=emb.tolist(), payload={**trecho, "ordem": idx})
        for idx, (trecho, emb) in enumerate(zip(trechos, embeddings))
    ]
    _qdrant.upsert(collection_name=collection_name, points=points, wait=True)


# Trechos de cada coleção, para a busca por palavras: {coleção: (instante, trechos)}.
_cache_trechos: dict[str, tuple[float, list[dict]]] = {}
CACHE_TRECHOS_TTL_S = 300


def _todos_trechos(collection_name: str) -> list[dict]:
    """Todos os trechos da coleção, em ordem. Um edital tem dezenas a poucas centenas."""
    em_cache = _cache_trechos.get(collection_name)
    if em_cache and time.time() - em_cache[0] < CACHE_TRECHOS_TTL_S:
        return em_cache[1]

    trechos: list[dict] = []
    offset = None
    while True:
        pontos, offset = _qdrant.scroll(
            collection_name=collection_name, limit=256, offset=offset,
            with_payload=True, with_vectors=False,
        )
        trechos.extend(p.payload for p in pontos)
        if offset is None:
            break
    trechos.sort(key=lambda t: t.get("ordem", 0))
    _cache_trechos[collection_name] = (time.time(), trechos)
    return trechos


_STOPWORDS = set(
    "a o e de da do das dos em no na nos nas um uma para por com que se os as ao aos e ser sao "
    "qual quais como onde quando quanto ou seu sua seus suas pelo pela este esta isso esse essa ha".split()
)


def _palavras_chave(texto: str) -> list[str]:
    import unicodedata
    sem_acento = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return [p for p in re.findall(r"[a-z0-9]+", sem_acento) if p not in _STOPWORDS and len(p) > 1]


def _ordenar_por_palavras(trechos: list[dict], query: str, n: int) -> list[int]:
    """Índices dos `n` trechos mais relevantes por correspondência de palavras (BM25).

    Complementa a busca vetorial: perguntas factuais ("qual o prazo de entrega?") costumam
    usar as mesmas palavras do edital, e o modelo de embeddings usado é fraco em português.
    """
    from collections import Counter

    termos = _palavras_chave(query)
    docs = [_palavras_chave(t.get("text", "")) for t in trechos]
    if not termos or not docs:
        return []
    total = len(docs)
    media = (sum(len(d) for d in docs) / total) or 1.0
    frequencia_doc = Counter(p for d in docs for p in set(d))
    k1, b = 1.5, 0.75

    pontuacoes: list[tuple[float, int]] = []
    for idx, doc in enumerate(docs):
        tf = Counter(doc)
        pontos = 0.0
        for termo in termos:
            if termo in tf:
                idf = math.log(1 + (total - frequencia_doc[termo] + 0.5) / (frequencia_doc[termo] + 0.5))
                pontos += idf * tf[termo] * (k1 + 1) / (tf[termo] + k1 * (1 - b + b * len(doc) / media))
        if pontos > 0:
            pontuacoes.append((pontos, idx))
    pontuacoes.sort(reverse=True)
    return [idx for _, idx in pontuacoes[:n]]


def _reordenar(query: str, textos: list[str]) -> list[int] | None:
    """Ordem dos textos por relevância segundo o Cohere Rerank; None se indisponível."""
    if not COHERE_API_KEY or not textos:
        return None
    try:
        resp = requests.post(
            "https://api.cohere.com/v1/rerank",
            json={"model": "rerank-multilingual-v3.0", "query": query, "documents": textos, "top_n": len(textos)},
            headers={"accept": "application/json", "content-type": "application/json",
                     "Authorization": f"Bearer {COHERE_API_KEY}"},
            timeout=8.0,
        )
        if resp.ok:
            ordem = [r.get("index") for r in resp.json().get("results", [])]
            ordem = [i for i in ordem if isinstance(i, int) and 0 <= i < len(textos)]
            if ordem:
                return ordem
        else:
            print(f"[Rerank] Cohere respondeu {resp.status_code}")
    except Exception as e:
        print(f"[Rerank] Erro na chamada do Cohere Rerank: {e}")
    return None


def buscar_trechos(collection_name: str, query: str, max_palavras: int = PALAVRAS_CHAT) -> list[dict]:
    """Trechos mais relevantes para a pergunta, até `max_palavras` de contexto.

    1. Candidatos: N_VETORIAL da busca vetorial + N_PALAVRAS da busca por palavras.
    2. Reordenação pelo Cohere Rerank; sem ele, vale a ordem intercalada (palavras primeiro).
    3. Corte pelo total de palavras (sempre devolve ao menos um trecho).
    """
    trechos = _todos_trechos(collection_name)
    if not trechos:
        return []

    query_vec = list(_model.embed([query]))[0].tolist()
    resultado = _qdrant.query_points(
        collection_name=collection_name, query=query_vec, limit=N_VETORIAL, with_payload=True,
    )
    por_vetor = [hit.payload.get("ordem") for hit in resultado.points]
    por_vetor = [i for i in por_vetor if isinstance(i, int) and i < len(trechos)]
    por_palavras = _ordenar_por_palavras(trechos, query, N_PALAVRAS)

    candidatos: list[int] = []
    for i in range(max(len(por_vetor), len(por_palavras))):
        for lista in (por_palavras, por_vetor):
            if i < len(lista) and lista[i] not in candidatos:
                candidatos.append(lista[i])

    ordem = _reordenar(query, [trechos[i]["text"] for i in candidatos])
    if ordem is not None:
        candidatos = [candidatos[i] for i in ordem]

    escolhidos: list[dict] = []
    total = 0
    for idx in candidatos:
        tamanho = len(trechos[idx]["text"].split())
        if escolhidos and total + tamanho > max_palavras:
            break
        escolhidos.append(trechos[idx])
        total += tamanho
    return escolhidos


def buscar_chunks(collection_name: str, query: str, max_palavras: int = PALAVRAS_CHAT) -> list[str]:
    return [t["text"] for t in buscar_trechos(collection_name, query, max_palavras)]


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
            reasoning_effort=LLM_REASONING_EFFORT,
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
        "campos": {
            "objeto": "o que está sendo comprado ou contratado, em uma frase",
            "orgao": "nome do órgão ou entidade compradora",
            "modalidade": "modalidade da licitação (ex.: Pregão Eletrônico)",
            "criterio_julgamento": "critério de julgamento (ex.: menor preço por item)",
            "numero_edital": "número do edital ou do processo",
        },
    },
    "bloco2_prazos": {
        "query": "prazo entrega vigência contrato local entrega data abertura proposta",
        "schema": {"prazo_entrega": None, "vigencia_contrato": None, "local_entrega": None, "data_abertura": None},
        "campos": {
            "prazo_entrega": "prazo para entrega dos bens ou execução do serviço",
            "vigencia_contrato": "prazo de vigência do contrato ou da ata",
            "local_entrega": "endereço ou local onde os bens devem ser entregues",
            "data_abertura": "data e hora de abertura da sessão ou das propostas",
        },
    },
    "bloco3_documentacao": {
        "query": "documentos habilitação regularidade fiscal certidão qualificação técnica econômica financeira",
        "schema": {"documentos_habilitacao": [], "regularidade_fiscal": [], "qualificacao_tecnica": []},
        "campos": {
            "documentos_habilitacao": "documentos exigidos para habilitação jurídica e econômico-financeira",
            "regularidade_fiscal": "certidões e provas de regularidade fiscal e trabalhista",
            "qualificacao_tecnica": "atestados, registros e comprovações de capacidade técnica",
        },
    },
    "bloco4_requisitos_tecnicos": {
        "query": "especificações técnicas produto certificação norma ABNT amostra requisito técnico",
        "schema": {"especificacoes_resumo": None, "certificacoes_exigidas": [], "exige_amostra": None, "outros_requisitos": []},
        "campos": {
            "especificacoes_resumo": "resumo dos itens e de suas especificações técnicas",
            "certificacoes_exigidas": "certificações, registros e normas exigidos dos produtos (INMETRO, ANVISA, ABNT)",
            "exige_amostra": "se o edital exige apresentação de amostra",
            "outros_requisitos": "outros requisitos técnicos, de garantia ou de entrega",
        },
    },
    "bloco5_riscos": {
        "query": "multa penalidade sanção rescisão cláusula garantia risco atenção",
        "schema": {"multas": [], "sancoes": [], "clausulas_criticas": [], "pontos_atencao": []},
        "campos": {
            "multas": "percentuais e hipóteses de multa",
            "sancoes": "outras sanções (advertência, impedimento de licitar, declaração de inidoneidade)",
            "clausulas_criticas": "cláusulas que podem gerar rescisão ou prejuízo ao fornecedor",
            "pontos_atencao": "exigências ou prazos que merecem atenção do fornecedor",
        },
    },
}


MAX_CONTEXT_CHARS = 7000  # folga para PALAVRAS_RESUMO palavras (~1.800 tokens por bloco)


def _instrucoes_campos(schema: dict, campos: dict | None) -> str:
    """Uma linha por campo, com o tipo esperado e o que ele deve conter."""
    linhas = []
    for nome, padrao in schema.items():
        if isinstance(padrao, list):
            tipo = "lista de frases curtas"
        elif nome == "exige_amostra":
            tipo = "true, false ou null"
        else:
            tipo = "texto curto, ou null se o trecho não informar"
        descricao = (campos or {}).get(nome, nome.replace("_", " "))
        linhas.append(f'- "{nome}" ({tipo}): {descricao}')
    return "\n".join(linhas)


def _gerar_bloco(collection_name: str, query: str, schema: dict, campos: dict | None = None) -> dict:
    chunks = buscar_chunks(collection_name, query, max_palavras=PALAVRAS_RESUMO)
    context = "\n\n---\n\n".join(chunks)
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS]
    # Os campos são descritos um a um. Mostrar só o molde vazio ({"multas": [], ...}) fazia o
    # modelo devolver o próprio molde, sem preencher nada, mesmo com a informação no trecho.
    prompt = (
        f"Trecho do edital:\n{context}\n\n"
        f"Extraia do trecho as informações abaixo e retorne SOMENTE um JSON com exatamente estes campos:\n"
        f"{_instrucoes_campos(schema, campos)}\n\n"
        f"Preencha cada campo com o que o trecho disser, citando números e prazos. "
        f"Use null ou lista vazia apenas quando o trecho realmente não tratar do assunto."
    )
    ultimo_erro: Exception | None = None
    for tentativa in range(1, TENTATIVAS_BLOCO + 1):
        try:
            resp = _groq.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_LICITACAO},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                reasoning_effort=LLM_REASONING_EFFORT,
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as exc:
            ultimo_erro = exc
            print(f"[Resumo] Tentativa {tentativa}/{TENTATIVAS_BLOCO} falhou: {exc.__class__.__name__}")
            if tentativa < TENTATIVAS_BLOCO:
                time.sleep(5 * tentativa)
    # Não grava bloco vazio como se fosse resumo válido: quem chama decide o que fazer.
    raise RuntimeError(f"a IA não respondeu após {TENTATIVAS_BLOCO} tentativas ({ultimo_erro.__class__.__name__})")


def processar_pdf(pdf_bytes: bytes, collection_name: str) -> dict:
    """Processa PDF com collection_name explícito (usado pelo worker Celery)."""
    paginas = extrair_paginas(pdf_bytes)
    if not any(p.strip() for p in paginas):
        raise ErroDefinitivo(
            "O PDF não contém texto selecionável (provavelmente é uma digitalização). "
            "O sistema ainda não lê documentos escaneados."
        )

    trechos = chunkar_paginas(paginas)
    chunks = [t["text"] for t in trechos]
    _recriar_colecao(collection_name)
    _indexar_trechos(collection_name, trechos)

    resumo: dict = {}
    for chave, cfg in _BLOCOS.items():
        try:
            resumo[chave] = _gerar_bloco(collection_name, cfg["query"], cfg["schema"], cfg.get("campos"))
        except RuntimeError as exc:
            raise RuntimeError(f"Falha ao gerar o bloco '{chave}' do resumo: {exc}") from exc
        time.sleep(1.2)  # evita estourar o TPM do Groq free tier (413)

    return {"chunks": chunks, "trechos": trechos, "resumo": resumo, "total_chunks": len(chunks)}


def processar_edital(pdf_bytes: bytes) -> dict:
    """Versão standalone com UUID gerado internamente (usado pelo upload manual)."""
    edital_id = str(uuid4())
    collection_name = nome_colecao(edital_id)
    resultado = processar_pdf(pdf_bytes, collection_name)
    return {"edital_id": edital_id, "collection_name": collection_name, **resultado}


def responder_pergunta(collection_name: str, pergunta: str) -> dict:
    trechos = buscar_trechos(collection_name, pergunta, max_palavras=PALAVRAS_CHAT)
    chunks = [t["text"] for t in trechos]
    context = "\n\n---\n\n".join(chunks)
    # Sem limitar o raciocínio, o modelo às vezes gasta toda a saída "pensando" e devolve
    # a resposta vazia (finish_reason=length). Resposta vazia não pode ser gravada como válida.
    texto = ""
    for _ in range(TENTATIVAS_BLOCO):
        resp = _groq.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "Você é um especialista em licitações públicas. Use APENAS o contexto do edital para responder. Seja objetivo e cite o trecho relevante quando possível."},
                {"role": "user", "content": f"Contexto do edital:\n{context}\n\nPergunta: {pergunta}"},
            ],
            temperature=0,
            reasoning_effort=LLM_REASONING_EFFORT,
        )
        texto = (resp.choices[0].message.content or "").strip()
        if texto:
            break
        time.sleep(2)
    if not texto:
        raise RuntimeError("a IA devolveu resposta vazia")

    trecho = chunks[0][:300].strip() if chunks else None
    # Página do trecho mais relevante; None em coleções indexadas antes de a página ser guardada
    pagina = trechos[0].get("pagina_inicial") if trechos else None
    pagina_final = trechos[0].get("pagina_final") if trechos else None
    return {
        "resposta": texto,
        "chunks_utilizados": len(chunks),
        "trecho_fonte": trecho,
        "pagina_fonte": pagina,
        # Um trecho pode atravessar a quebra de página; a tela cita o intervalo
        "pagina_fonte_final": pagina_final,
    }


def extrair_dados_item_edital(collection_name: str, produto_nome: str, produto_descricao: str) -> dict:
    """Busca trechos do edital relacionados ao produto de interesse e extrai a
    quantidade e o valor unitário estimado desse item específico usando LLM.
    """
    query = f"quantidade valor unitário estimado lote item {produto_nome}"
    try:
        chunks = buscar_chunks(collection_name, query, max_palavras=PALAVRAS_RESUMO)
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
            reasoning_effort=LLM_REASONING_EFFORT,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print(f"[Extração Item] Erro na chamada do Groq: {e}")
        return {}
