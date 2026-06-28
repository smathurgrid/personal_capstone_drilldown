"""Authentication dependencies for protected routes."""

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.database import get_db
from backend.auth.models import User
from backend.auth.security import decode_access_token
from backend.shared.config import settings


def _bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None
    return auth_header.split(" ", 1)[1].strip()


async def require_current_user(
    request: Request,
    session_cookie: str | None = Cookie(default=None, alias=settings.AUTH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = session_cookie or _bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )
    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )
    return user


async def get_optional_current_user(
    request: Request,
    session_cookie: str | None = Cookie(default=None, alias=settings.AUTH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    token = session_cookie or _bearer_token(request)
    if not token:
        return None
    user_id = decode_access_token(token)
    if not user_id:
        return None
    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    return result.scalar_one_or_none()


async def require_authenticated_api(
    request: Request,
    session_cookie: str | None = Cookie(default=None, alias=settings.AUTH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if request.url.path.endswith("/health"):
        return None
    return await require_current_user(request, session_cookie, db)
