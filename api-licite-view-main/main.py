# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException
# pyrefly: ignore [missing-import]
# pyrefly: ignore [missing-import]
import httpx
from datetime import datetime
# pyrefly: ignore [missing-import]
from loguru import logger
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
import os
# pyrefly: ignore [missing-import]
from slowapi import Limiter, _rate_limit_exceeded_handler
# pyrefly: ignore [missing-import]
from slowapi.util import get_remote_address
# pyrefly: ignore [missing-import]
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:4200").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)



# pyrefly: ignore [missing-import]
from routes.auth_routes import auth_router
# pyrefly: ignore [missing-import]
from routes.admin_routes import admin_router
# pyrefly: ignore [missing-import]
from routes.cliente_routes import cliente_router
# pyrefly: ignore [missing-import]
from routes.pncp_routes import pncp_router

app.include_router(admin_router)
app.include_router(cliente_router)
app.include_router(auth_router)
app.include_router(pncp_router)

# pyrefly: ignore [missing-import]
from pydantic import BaseModel
from typing import Optional

class FiltrosFrontend(BaseModel):
    pagina: int = 1
    uf: Optional[str] = ""
    palavraChave: Optional[str] = ""
    modalidade: Optional[str] = ""
    dataInicial: Optional[str] = None
    dataFinal: Optional[str] = None
    tipoInstrumento: Optional[str] = None
    orgao: Optional[str] = None
    unidade: Optional[str] = None
    municipio: Optional[str] = None
    esfera: Optional[str] = None
    poder: Optional[str] = None
    fonteOrcamentaria: Optional[str] = None
    tipoMargemPreferencia: Optional[str] = None
    exigenciaConteudoNacional: Optional[str] = None
    emendaParlamentar: Optional[str] = None
    tipo: Optional[str] = None
    status: Optional[str] = None

@app.post("/buscar-editais")
async def buscar_editais_frontend(filtros: FiltrosFrontend):
    logger.info(f"Filtros recebidos do frontend: {filtros.model_dump()}")
    
    url = "https://pncp.gov.br/api/search/"
    
    params = {
        "tipos_documento": "edital",
        "ordenacao": "-data",
        "pagina": filtros.pagina,
        "tam_pagina": 10,
        "status": getattr(filtros, "status", None) or "recebendo_proposta"
    }
    
    if getattr(filtros, "uf", None):
        params["ufs"] = filtros.uf
        
    if getattr(filtros, "modalidade", None):
        params["modalidades"] = filtros.modalidade
        
    if getattr(filtros, "tipoInstrumento", None):
        params["tipos"] = filtros.tipoInstrumento
    elif getattr(filtros, "tipo", None):
        params["tipos"] = getattr(filtros, "tipo")
        
    if getattr(filtros, "palavraChave", None):
        params["q"] = filtros.palavraChave
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    logger.info(f"Consumindo PNCP: {url} com params {params}")
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            dados = response.json()
            
            pncp_items = dados.get("items", [])
            total_itens = dados.get("total", 0)
            
            parsed_items = []
            for item in pncp_items:
                titulo = item.get("title") or "Sem título"
                orgao = item.get("orgao_nome") or "Órgão não informado"
                modalidade = item.get("modalidade_licitacao_nome") or "Não informada"
                
                # Formatação de data
                data_abertura = item.get("data_publicacao_pncp")
                data_str = "Não informada"
                if data_abertura:
                    try:
                        data_obj = datetime.fromisoformat(data_abertura.replace("Z", "+00:00"))
                        data_str = data_obj.strftime("%d/%m/%Y")
                    except:
                        data_str = str(data_abertura)[:10]
                        
                valor = item.get("valor_global") or 0.0
                try:
                    valor_estimado = f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                except:
                    valor_estimado = "R$ 0,00"
                    
                uf_item = item.get("uf") or "BR"
                
                parsed_items.append({
                    "titulo": str(titulo),
                    "orgao": str(orgao),
                    "modalidade": str(modalidade),
                    "uf": str(uf_item),
                    "data": data_str,
                    "valorEstimado": valor_estimado,
                    "status": "Recebendo Proposta",
                    "statusClass": "aberta"
                })
                
            total_paginas = (total_itens // 10) + (1 if total_itens % 10 > 0 else 0)
            
            return {
                "pagina": filtros.pagina,
                "totalPaginas": total_paginas if total_paginas > 0 else 1,
                "totalItens": total_itens,
                "items": parsed_items
            }
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Erro no PNCP: {e.response.text}")
            raise HTTPException(status_code=502, detail="Erro ao comunicar com PNCP")
        except httpx.RequestError as e:
            logger.error(f"Erro de conexão com PNCP: {e}")
            raise HTTPException(status_code=504, detail="Timeout ao conectar no PNCP")