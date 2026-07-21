import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session
from app.models import User


def _load_or_create_secret() -> str:
    env_secret = os.getenv("SECRET_KEY")
    if env_secret:
        return env_secret

    secret_path = Path("data") / "secret.key"
    secret_path.parent.mkdir(exist_ok=True)

    if secret_path.exists():
        try:
            from cryptography.fernet import Fernet, InvalidToken
            enc_key_path = Path("data") / "encryption.key"
            if enc_key_path.exists():
                fernet = Fernet(enc_key_path.read_bytes())
                encrypted = secret_path.read_bytes()
                return fernet.decrypt(encrypted).decode()
        except Exception:
            pass
        return secret_path.read_text().strip()

    new_secret = secrets.token_hex(32)

    try:
        from cryptography.fernet import Fernet
        enc_key_path = Path("data") / "encryption.key"
        if enc_key_path.exists():
            fernet = Fernet(enc_key_path.read_bytes())
            secret_path.write_bytes(fernet.encrypt(new_secret.encode()))
        else:
            secret_path.write_text(new_secret)
    except Exception:
        secret_path.write_text(new_secret)

    return new_secret


SECRET_KEY = _load_or_create_secret()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(user_id: int) -> str:
    jti = secrets.token_hex(16)
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    iat_ts = int(now.timestamp())
    return jwt.encode(
        {"sub": str(user_id), "exp": expire, "jti": jti, "iat": iat_ts},
        SECRET_KEY, algorithm=ALGORITHM,
    )


def decode_token(token: str) -> tuple[int | None, str | None, int | None]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload.get("sub")), payload.get("jti"), payload.get("iat")
    except (JWTError, TypeError, ValueError):
        return None, None, None


async def _is_token_revoked(jti: str | None) -> bool:
    if not jti:
        return False
    from app.models import RevokedToken
    async with async_session() as db:
        result = await db.execute(
            select(RevokedToken).where(RevokedToken.jti == jti)
        )
        return result.scalar_one_or_none() is not None


async def _is_token_stale(user_id: int, iat_ts: int | None) -> bool:
    if not iat_ts:
        return False
    try:
        from app.models import User
        async with async_session() as db:
            user = await db.get(User, user_id)
            if user and user.password_changed_at:
                iat_dt = datetime.fromtimestamp(iat_ts, tz=timezone.utc)
                changed = user.password_changed_at
                if changed.tzinfo is None:
                    changed = changed.replace(tzinfo=timezone.utc)
                return iat_dt < changed
    except Exception:
        pass
    return False


async def get_current_user(request: Request) -> User | None:
    token = request.cookies.get("token")
    if not token:
        return None
    user_id, jti, iat = decode_token(token)
    if not user_id:
        return None
    if await _is_token_revoked(jti):
        return None
    if await _is_token_stale(user_id, iat):
        return None
    async with async_session() as db:
        user = await db.get(User, user_id)
        return user


async def require_auth(request: Request) -> User:
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user
