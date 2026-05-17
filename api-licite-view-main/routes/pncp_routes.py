# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException
# pyrefly: ignore [missing-import]
from loguru import logger

# pyrefly: ignore [missing-import]
from services.pncp_service import buscar_editais_pncp
# pyrefly: ignore [missing-import]
from dependencies import verificar_token # Opcional: proteger a rota
# pyrefly: ignore [missing-import]
from models import Usuario

pncp_router = APIRouter(prefix="/pncp", tags=["PNCP Integration"])

# pyrefly: ignore [unknown-name]
@pncp_router.post("/buscar-editais", response_model=PncpBuscaResponse)
# pyrefly: ignore [unknown-name]
async def buscar_editais(filtros: PncpBuscaFiltros, usuario: Usuario = Depends(verificar_token)):
    """
    Endpoint que atua como proxy para buscar editais no Portal Nacional de Contratações Públicas (PNCP).
    Recebe os filtros do frontend Angular, formata, envia ao PNCP e devolve o JSON tratado.
    """
    logger.info(f"Usuário {usuario.id} iniciou busca no PNCP com os filtros: {filtros}")
    
    try:
        # Chama o serviço que faz o request HTTP assíncrono para o PNCP
        resultado = await buscar_editais_pncp(filtros)
        return resultado
        
    except HTTPException as http_exc:
        raise http_exc # Repassa os erros tratados do serviço (Timeout, StatusError)
    except Exception as e:
        logger.exception("Erro não tratado no endpoint /buscar-editais")
        raise HTTPException(status_code=500, detail="Erro interno do servidor ao processar busca.")
