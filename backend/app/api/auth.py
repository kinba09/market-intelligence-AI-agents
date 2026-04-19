from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.container import get_services
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.entities import User
from app.schemas.api import (
    LLMKeyOut,
    LLMKeyUpsertRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _mask_key(raw: str) -> str:
    if len(raw) <= 8:
        return "*" * len(raw)
    return f"{raw[:4]}...{raw[-4:]}"


@router.post("/register", response_model=UserOut)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> UserOut:
    existing = db.execute(select(User).where(User.email == req.email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=req.email, password_hash=hash_password(req.password), is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut(user_id=user.id, email=user.email)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.execute(select(User).where(User.email == req.email)).scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User inactive")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(user_id=current_user.id, email=current_user.email)


@router.post("/llm-key", response_model=LLMKeyOut)
def upsert_llm_key(
    req: LLMKeyUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LLMKeyOut:
    services = get_services()
    row = services.llm_config.upsert_key(
        db,
        user_id=current_user.id,
        label=req.label,
        provider=req.provider.lower().strip(),
        model_name=req.model_name.strip(),
        api_key=req.api_key.strip(),
        base_url=req.base_url.strip() if req.base_url else None,
        is_default=req.is_default,
    )
    db.commit()

    return LLMKeyOut(
        key_id=row.id,
        label=row.label,
        provider=row.provider,
        model_name=row.model_name,
        base_url=row.base_url,
        is_default=row.is_default,
        masked_api_key=_mask_key(req.api_key.strip()),
    )


@router.get("/llm-keys", response_model=list[LLMKeyOut])
def list_llm_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LLMKeyOut]:
    services = get_services()
    keys = services.llm_config.list_keys(db, current_user.id)

    out: list[LLMKeyOut] = []
    for k in keys:
        try:
            raw = services.crypto.decrypt(k.api_key_encrypted)
        except Exception:
            raw = "********"
        out.append(
            LLMKeyOut(
                key_id=k.id,
                label=k.label,
                provider=k.provider,
                model_name=k.model_name,
                base_url=k.base_url,
                is_default=k.is_default,
                masked_api_key=_mask_key(raw),
            )
        )
    return out
