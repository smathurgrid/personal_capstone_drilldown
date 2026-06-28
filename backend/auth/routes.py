"""Authentication API routes."""

from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.database import get_db
from backend.auth.dependencies import get_optional_current_user, require_current_user
from backend.auth.models import User
from backend.auth.schemas import (
    AuthResponse,
    LoginRequest,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    SessionResponse,
    UserRead,
)
from backend.auth.security import create_access_token, hash_password, verify_password
from backend.shared.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
MAX_AVATAR_BYTES = 3 * 1024 * 1024
ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _user_read(user: User) -> UserRead:
    return UserRead(id=user.id, email=user.email, name=user.name, avatar_url=user.avatar_url)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="lax",
        max_age=settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    email = payload.email.lower()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=email,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    _set_session_cookie(response, create_access_token(user.id))
    return AuthResponse(user=_user_read(user))


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(
        payload.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    _set_session_cookie(response, create_access_token(user.id))
    return AuthResponse(user=_user_read(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    response.delete_cookie(settings.AUTH_COOKIE_NAME, path="/")


@router.get("/me", response_model=AuthResponse)
async def me(user: User = Depends(require_current_user)):
    return AuthResponse(user=_user_read(user))


@router.get("/session", response_model=SessionResponse)
async def session(user: User | None = Depends(get_optional_current_user)):
    return SessionResponse(user=_user_read(user) if user else None)


@router.post("/profile", response_model=AuthResponse)
async def update_profile(
    payload: ProfileUpdateRequest,
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.name = payload.name.strip()
    await db.commit()
    await db.refresh(user)
    return AuthResponse(user=_user_read(user))


@router.post("/password", response_model=AuthResponse)
async def change_password(
    payload: PasswordChangeRequest,
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        )

    user.password_hash = hash_password(payload.new_password)
    await db.commit()
    await db.refresh(user)
    return AuthResponse(user=_user_read(user))


@router.post("/avatar", response_model=AuthResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Avatar must be a JPG, PNG, or WebP image",
        )

    contents = await file.read()
    if len(contents) > MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Avatar image must be 3 MB or smaller",
        )

    try:
        from io import BytesIO

        image = Image.open(BytesIO(contents))
        image.verify()
        image = Image.open(BytesIO(contents))
        image = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is not a valid image",
        ) from None

    image.thumbnail((512, 512))
    settings.PROFILE_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{user.id}-{uuid.uuid4().hex}.webp"
    destination = settings.PROFILE_UPLOADS_DIR / filename
    image.save(destination, format="WEBP", quality=88, method=6)

    if user.avatar_url:
        previous = Path(user.avatar_url).name
        previous_path = settings.PROFILE_UPLOADS_DIR / previous
        if previous_path.exists() and previous_path != destination:
            previous_path.unlink(missing_ok=True)

    user.avatar_url = f"/profile-uploads/{filename}"
    await db.commit()
    await db.refresh(user)
    return AuthResponse(user=_user_read(user))
