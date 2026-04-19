from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.entities import UserLLMKey
from app.services.crypto_service import CryptoService


@dataclass
class RuntimeLLMConfig:
    provider: str
    model_name: str
    api_key: str
    base_url: str | None = None


class LLMConfigService:
    def __init__(self, crypto: CryptoService) -> None:
        self.crypto = crypto

    def upsert_key(
        self,
        db: Session,
        *,
        user_id: str,
        label: str,
        provider: str,
        model_name: str,
        api_key: str,
        base_url: str | None,
        is_default: bool,
    ) -> UserLLMKey:
        existing = db.execute(
            select(UserLLMKey).where(UserLLMKey.user_id == user_id, UserLLMKey.label == label)
        ).scalar_one_or_none()

        if is_default:
            db.execute(update(UserLLMKey).where(UserLLMKey.user_id == user_id).values(is_default=False))

        encrypted = self.crypto.encrypt(api_key)
        if existing:
            existing.provider = provider
            existing.model_name = model_name
            existing.api_key_encrypted = encrypted
            existing.base_url = base_url
            existing.is_default = is_default
            db.flush()
            return existing

        row = UserLLMKey(
            user_id=user_id,
            label=label,
            provider=provider,
            model_name=model_name,
            api_key_encrypted=encrypted,
            base_url=base_url,
            is_default=is_default,
        )
        db.add(row)
        db.flush()
        return row

    def get_default_runtime_config(self, db: Session, user_id: str) -> RuntimeLLMConfig | None:
        row = db.execute(
            select(UserLLMKey).where(UserLLMKey.user_id == user_id).order_by(UserLLMKey.is_default.desc(), UserLLMKey.created_at.desc())
        ).scalars().first()
        if not row:
            return None

        try:
            api_key = self.crypto.decrypt(row.api_key_encrypted)
        except Exception:
            return None

        return RuntimeLLMConfig(
            provider=row.provider,
            model_name=row.model_name,
            api_key=api_key,
            base_url=row.base_url,
        )

    def list_keys(self, db: Session, user_id: str) -> list[UserLLMKey]:
        return db.execute(select(UserLLMKey).where(UserLLMKey.user_id == user_id).order_by(UserLLMKey.created_at.desc())).scalars().all()
