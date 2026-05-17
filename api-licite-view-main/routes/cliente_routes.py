from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from dependencies import verificar_token


cliente_router = APIRouter(prefix="/cliente", tags=["Cliente"])

