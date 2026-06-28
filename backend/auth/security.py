"""Password and JWT helpers."""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.shared.config import settings

ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return pwd_context.verify(password, password_hash)
    except ValueError:
        return False


def create_access_token(user_id: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": user_id, "exp": expires_at}
    return jwt.encode(payload, settings.AUTH_SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.AUTH_SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) else None
