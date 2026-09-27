from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from sqlalchemy.orm import Session

from database import get_db
from dependencies import verificar_token
from config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY, hash_password, verify_password
from models import Usuario, PerfilUsuario
from schemas import LoginRequest, TokenResponse, UsuarioCreate, UsuarioResponse

auth_router = APIRouter(prefix="/auth", tags=["Autenticação"])


def _criar_token(usuario_id: str) -> str:
    expira = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": usuario_id, "exp": expira}, SECRET_KEY, algorithm=ALGORITHM)


@auth_router.post("/register", response_model=UsuarioResponse, status_code=201)
def registrar(dados: UsuarioCreate, session: Session = Depends(get_db)):
    if session.query(Usuario).filter(Usuario.email == dados.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
    if session.query(Usuario).filter(Usuario.cnpj == dados.cnpj).first():
        raise HTTPException(status_code=400, detail="CNPJ já cadastrado")

    usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_password(dados.senha),
        razao_social=dados.razao_social,
        cnpj=dados.cnpj,
        cep=dados.cep,
        cidade=dados.cidade,
        uf=dados.uf,
        perfil=PerfilUsuario.FORNECEDOR,
    )
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    return usuario


@auth_router.post("/login", response_model=TokenResponse)
def login(dados: LoginRequest, session: Session = Depends(get_db)):
    usuario = session.query(Usuario).filter(Usuario.email == dados.email).first()
    if not usuario or not verify_password(dados.senha, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Conta desativada")
    return {"access_token": _criar_token(str(usuario.id)), "token_type": "bearer"}


@auth_router.post("/login-form", response_model=TokenResponse)
def login_form(form: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_db)):
    usuario = session.query(Usuario).filter(Usuario.email == form.username).first()
    if not usuario or not verify_password(form.password, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Conta desativada")
    return {"access_token": _criar_token(str(usuario.id)), "token_type": "bearer"}


@auth_router.get("/me", response_model=UsuarioResponse)
def me(usuario: Usuario = Depends(verificar_token)):
    return usuario
