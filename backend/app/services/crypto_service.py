from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import get_settings


class CryptoService:
    def __init__(self) -> None:
        settings = get_settings()
        self._fernet = Fernet(self._derive_key(settings.app_secret_key))

    @staticmethod
    def _derive_key(secret: str) -> bytes:
        digest = hashlib.sha256(secret.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    def encrypt(self, text: str) -> str:
        return self._fernet.encrypt(text.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
