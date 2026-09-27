import os
from dotenv import load_dotenv
from fastapi.security import OAuth2PasswordBearer
import bcrypt as _bcrypt

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database.db")
REDIS_URL = os.getenv("REDIS_URL")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")

# Esquema do OAuth2PasswordBearer para injeção de dependência de tokens
oauth2_schema = OAuth2PasswordBearer(tokenUrl="auth/login-form")


def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False
