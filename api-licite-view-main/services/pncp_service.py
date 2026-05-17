# pyrefly: ignore [missing-import]
import httpx
# pyrefly: ignore [missing-import]
from fastapi import HTTPException
# pyrefly: ignore [missing-import]
from loguru import logger
import urllib.parse
# pyrefly: ignore [missing-import]
from schemas import PncpBuscaFiltros

# URL base simulando a chamada do portal PNCP
# Observação: A URL do portal é https://pncp.gov.br/api/pncp/v1/contratacoes ou /api/pncp/v1/editais etc.
# Usaremos a API de compras do PNCP como exemplo (ajuste conforme a real rota do DevTools)
PNCP_BASE_URL = "https://pncp.gov.br/api/busca/v1/contratacoes"

async def buscar_editais_pncp(filtros: PncpBuscaFiltros) -> dict:
    """
    Serviço que atua como proxy para a API do PNCP.
    """
    # 1. Montar os query params com base nos filtros recebidos
    query_params = {
        "pagina": filtros.pagina,
        "tamanhoPagina": 10
    }
    
    if filtros.termoBusca:
        query_params["q"] = filtros.termoBusca
    
    if filtros.uf:
        query_params["uf"] = filtros.uf
        
    if filtros.modalidade:
        query_params["modalidade"] = filtros.modalidade
        
    if filtros.dataInicial:
        query_params["dataInicial"] = filtros.dataInicial.strftime("%Y%m%d")
        
    if filtros.dataFinal:
        query_params["dataFinal"] = filtros.dataFinal.strftime("%Y%m%d")

    if filtros.tipoInstrumento:
        query_params["tipoInstrumento"] = filtros.tipoInstrumento
    if filtros.orgao:
        query_params["orgao"] = filtros.orgao
    if filtros.unidade:
        query_params["unidade"] = filtros.unidade
    if filtros.municipio:
        query_params["municipio"] = filtros.municipio
    if filtros.esfera:
        query_params["esfera"] = filtros.esfera
    if filtros.poder:
        query_params["poder"] = filtros.poder
    if filtros.fonteOrcamentaria:
        query_params["fonteOrcamentaria"] = filtros.fonteOrcamentaria
    if filtros.tipoMargemPreferencia:
        query_params["tipoMargemPreferencia"] = filtros.tipoMargemPreferencia
    if filtros.exigenciaConteudoNacional:
        query_params["exigenciaConteudoNacional"] = filtros.exigenciaConteudoNacional
    if filtros.emendaParlamentar:
        query_params["emendaParlamentar"] = filtros.emendaParlamentar

    # 2. Configurar headers imitando navegador
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://pncp.gov.br/",
    }

    logger.info(f"Fazendo requisição para PNCP com query: {query_params}")

    # 3. Fazer requisição com timeout
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(
                PNCP_BASE_URL,
                params=query_params,
                headers=headers
            )
            response.raise_for_status() # Lança erro se HTTP falhar
            dados = response.json()
            
            # 4. Tratar e padronizar o retorno
            # O PNCP geralmente retorna "data" para a lista e "totalRegistros" etc.
            total_itens = dados.get("totalRegistros", 0)
            total_paginas = dados.get("totalPaginas", 1)
            items = dados.get("data", [])
            
            # Mapeamento do que o frontend espera (adaptável conforme necessário)
            return {
                "pagina": filtros.pagina,
                "totalPaginas": total_paginas,
                "totalItens": total_itens,
                "items": items
            }
            
        except httpx.ReadTimeout:
            logger.error("Timeout na requisição ao PNCP")
            raise HTTPException(status_code=504, detail="O portal PNCP demorou muito para responder. Tente novamente mais tarde.")
        except httpx.HTTPStatusError as exc:
            logger.error(f"Erro HTTP {exc.response.status_code} na API do PNCP: {exc.response.text}")
            raise HTTPException(status_code=exc.response.status_code, detail="Erro ao buscar dados do portal PNCP.")
        except Exception as exc:
            logger.exception("Erro desconhecido ao acessar o PNCP")
            raise HTTPException(status_code=500, detail="Erro interno de comunicação com o PNCP.")
