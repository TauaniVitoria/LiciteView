import io
import json
import os
import sys
import time
from uuid import uuid4

# Adiciona o diretório atual ao path para importar os módulos locais
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Erro: PyMuPDF (fitz) é necessário para executar a avaliação.")
    sys.exit(1)

from config import COHERE_API_KEY
from rag.edital_rag import processar_pdf, responder_pergunta, _groq, LLM_MODEL

# ── Texto do edital simulado para testes ─────────────────────────────────────
MOCK_EDITAL_TEXT = """
EDITAL DE PREGÃO ELETRÔNICO Nº 020/2026
ÓRGÃO: Secretaria Municipal de Educação de São Paulo
OBJETO: Aquisição de equipamentos de informática e mobiliário escolar.

CLÁUSULA 4 - DA ENTREGA E DO PRAZO
4.1. Os equipamentos de informática adjudicados deverão ser entregues no prazo máximo de 30 (trinta) dias corridos, contados a partir da data de recebimento da Nota de Empenho ou assinatura do contrato.
4.2. O local de entrega será no Almoxarifado Central da Secretaria de Educação, situado na Rua das Flores, nº 100, São Paulo/SP.

CLÁUSULA 7 - DAS EXIGÊNCIAS DE HABILITAÇÃO TÉCNICA
7.1. Para fins de qualificação técnica, as licitantes deverão apresentar Atestado de Capacidade Técnica, fornecido por pessoa jurídica de direito público ou privado, comprovando o fornecimento anterior de equipamentos de informática similares aos do objeto desta licitação.

CLÁUSULA 9 - DAS MULTAS E PENALIDADES
9.1. Em caso de atraso injustificado na entrega dos bens, sujeitar-se-á a adjudicatária à multa de mora de 0,5% (meio por cento) por dia de atraso, calculada sobre o valor total do item em atraso, até o limite máximo de 10% (dez por cento).
9.2. A aplicação de multa não impede a rescisão unilateral do contrato administrativo por descumprimento de obrigações.
"""

# ── Dataset de referência para avaliação (Perguntas e Respostas esperadas) ─────
DATASET_REFERENCIA = [
    {
        "pergunta": "Qual o prazo de entrega dos equipamentos?",
        "gabarito": "Até 30 dias corridos após a assinatura do contrato ou recebimento da Nota de Empenho."
    },
    {
        "pergunta": "Onde devem ser entregues as mercadorias?",
        "gabarito": "No Almoxarifado Central da Secretaria de Educação, na Rua das Flores, nº 100, São Paulo/SP."
    },
    {
        "pergunta": "É exigido atestado de capacidade técnica?",
        "gabarito": "Sim, é necessário atestado que comprove o fornecimento anterior de equipamentos de informática similares."
    },
    {
        "pergunta": "Quais as multas previstas para atraso na entrega?",
        "gabarito": "Multa de mora de 0,5% por dia de atraso, limitada ao limite máximo de 10% do valor em atraso."
    }
]


def gerar_pdf_simulado() -> bytes:
    """Cria um PDF em memória com o edital simulado utilizando PyMuPDF."""
    doc = fitz.open()
    page = doc.new_page()
    # Insere o texto em uma caixa de texto estruturada
    rect = fitz.Rect(50, 50, 550, 750)
    page.insert_textbox(rect, MOCK_EDITAL_TEXT, fontsize=11, fontname="helv")
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


def avaliar_llm_judge(pergunta: str, resposta: str, contexto: str, gabarito: str) -> dict:
    """Usa o LLM (Groq) como juiz para avaliar a qualidade da resposta do RAG."""
    prompt = f"""Você é um auditor independente de sistemas de IA especialista em processamento de editais.
Avalie a resposta gerada pelo sistema RAG de acordo com os critérios abaixo.

Contexto do Edital:
\"\"\"{contexto}\"\"\"

Pergunta do Usuário:
\"\"\"{pergunta}\"\"\"

Resposta do Sistema RAG:
\"\"\"{resposta}\"\"\"

Gabarito Esperado:
\"\"\"{gabarito}\"\"\"

Retorne um objeto JSON contendo exatamente as seguintes chaves de pontuação (números de 0.0 a 1.0) e justificativas textuais curtas:
{{
  "fidelidade_score": <se a resposta está fundamentada estritamente no contexto fornecido, sem inventar fatos extras>,
  "fidelidade_just": "<motivo>",
  "relevancia_score": <se a resposta aborda diretamente a pergunta formulada de forma útil>,
  "relevancia_just": "<motivo>",
  "precisao_contexto_score": <se os trechos do contexto fornecidos contêm as informações necessárias para responder à pergunta>,
  "precisao_contexto_just": "<motivo>"
}}"""

    try:
        resp = _groq.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "Você avalia respostas em formato JSON estruturado."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        return {
            "fidelidade_score": 0.0, "fidelidade_just": f"Erro na avaliação: {e}",
            "relevancia_score": 0.0, "relevancia_just": "",
            "precisao_contexto_score": 0.0, "precisao_contexto_just": ""
        }


def executar_avaliacao():
    print("=" * 70)
    print("INICIANDO PIPELINE DE AVALIAÇÃO RAG — LICITEVIEW")
    print(f"Status do Cohere Rerank: {'ATIVO' if COHERE_API_KEY else 'INATIVO'}")
    print("=" * 70)

    # 1. Gerar e processar PDF simulado
    print("\n1. Gerando PDF simulado do edital...")
    pdf_bytes = gerar_pdf_simulado()
    
    collection_name = f"eval_edital_{str(uuid4()).replace('-', '_')}"
    print(f"2. Indexando edital na coleção temporária '{collection_name}'...")
    resultado = processar_pdf(pdf_bytes, collection_name)
    print(f"✓ Chunks gerados e indexados: {resultado['total_chunks']}")

    avaliacoes = []
    
    # 2. Executar perguntas e avaliar respostas
    print("\n3. Executando perguntas do dataset de referência e avaliando...")
    for idx, item in enumerate(DATASET_REFERENCIA):
        pergunta = item["pergunta"]
        gabarito = item["gabarito"]
        
        print(f"\nPergunta {idx+1}: {pergunta}")
        
        # Chama a função de busca e resposta do RAG
        t_inicio = time.time()
        resp_rag = responder_pergunta(collection_name, pergunta)
        t_total = time.time() - t_inicio
        
        resposta = resp_rag["resposta"]
        trecho = resp_rag.get("trecho_fonte") or ""
        
        print(f"Resposta RAG ({t_total:.2f}s): {resposta}")
        
        # Avalia a qualidade com o LLM-as-a-judge
        notas = avaliar_llm_judge(pergunta, resposta, trecho, gabarito)
        avaliacoes.append(notas)
        
        print(f"  └ Fidelidade: {notas.get('fidelidade_score')} | {notas.get('fidelidade_just')}")
        print(f"  └ Relevância: {notas.get('relevancia_score')} | {notas.get('relevancia_just')}")
        print(f"  └ Precisão Contexto: {notas.get('precisao_contexto_score')} | {notas.get('precisao_contexto_just')}")
        
        time.sleep(1.0) # Respeita rate limit

    # 3. Consolidar resultados
    print("\n" + "=" * 70)
    print("MÉTRICAS CONSOLIDADAS DO PIPELINE RAG")
    print("=" * 70)
    
    avg_fidelidade = sum(a.get("fidelidade_score", 0) for a in avaliacoes) / len(avaliacoes)
    avg_relevancia = sum(a.get("relevancia_score", 0) for a in avaliacoes) / len(avaliacoes)
    avg_contexto = sum(a.get("precisao_contexto_score", 0) for a in avaliacoes) / len(avaliacoes)
    
    print(f"Fidelidade Média (Faithfulness): {avg_fidelidade:.2%}")
    print(f"Relevância Média (Answer Relevancy): {avg_relevancia:.2%}")
    print(f"Precisão de Contexto Média (Context Precision): {avg_contexto:.2%}")
    print("=" * 70)
    
    # 4. Limpar coleção temporária do Qdrant
    try:
        from rag.edital_rag import _qdrant
        _qdrant.delete_collection(collection_name)
        print("✓ Coleção de teste removida do Qdrant.")
    except Exception as e:
        print(f"Aviso: Não foi possível limpar a coleção temporária: {e}")


if __name__ == "__main__":
    executar_avaliacao()
