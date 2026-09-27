from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from dependencies import verificar_admin
from models import Usuario, Edital
from schemas import UsuarioResponse

admin_router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(verificar_admin)])

