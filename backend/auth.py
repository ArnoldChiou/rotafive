"""
auth.py — JWT Authentication helpers for RotaFive
Handles password hashing, token creation and current user dependency.
"""
import os
import bcrypt
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

# ─── Configuration ─────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "changeme-insecure-default-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# ─── Password Hashing (using bcrypt directly, not passlib) ────────────────────
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

# ─── JWT Token ─────────────────────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ─── Current User Dependency ───────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

async def get_current_user(token: str = Depends(oauth2_scheme), db_pool=None):
    """
    Dependency injected into protected endpoints.
    Decodes the JWT and returns the user dict from DB.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    if db_pool is None:
        raise credentials_exception

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, role FROM users WHERE id = $1", int(user_id)
        )
    if row is None:
        raise credentials_exception

    return dict(row)
