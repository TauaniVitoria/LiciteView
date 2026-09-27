from fastapi import Depends, HTTPException
from config import SECRET_KEY, ALGORITHM, oauth2_schema
from database import get_db
from models import Usuario, PerfilUsuario
from sqlalchemy.orm import Session
from jose import jwt, JWTError


def verificar_token(token: str = Depends(oauth2_schema), session: Session = Depends(get_db)):
    try:
        dic_info = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        id_usuario = dic_info.get("sub")
    except JWTError as erro:
        print(erro)
        raise HTTPException(status_code=401, detail="Acesso Negado, verifique a validade do token")
    usuario = session.query(Usuario).filter(Usuario.id == id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=401, detail="Acesso Inválido")
    return usuario


def verificar_admin(usuario: Usuario = Depends(verificar_token)):
    if usuario.perfil != PerfilUsuario.ADMIN:
        raise HTTPException(status_code=403, detail="Acesso negado. Apenas administradores podem acessar esta rota.")
    return usuario
