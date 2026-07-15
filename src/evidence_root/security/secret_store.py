"""API 키 저장소. Keyring 우선, 불가 시 Fernet 암호화 파일로 폴백한다.

로그/예외 메시지에 절대 키 값 자체를 포함하지 않는다.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Protocol

logger = logging.getLogger("evidence_root.security")

SERVICE_NAME = "EvidenceRoot"

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
SECRETS_FILE = DATA_DIR / "encrypted_secrets.json"
KEY_FILE = DATA_DIR / "local_secret.key"


class SecretStore(Protocol):
    def get(self, name: str) -> Optional[str]: ...
    def set(self, name: str, value: str) -> None: ...
    def delete(self, name: str) -> None: ...


def mask_key(value: Optional[str]) -> str:
    if not value:
        return "(저장된 값 없음)"
    if len(value) <= 6:
        return "•" * len(value)
    return f"{value[:4]}{'•' * 4}{value[-4:]}"


class KeyringSecretStore:
    """OS Keyring을 사용하는 저장소. 사용 불가 시 RuntimeError를 던져 폴백을 유도한다."""

    def __init__(self) -> None:
        import keyring  # noqa: F401 - 사용 가능 여부 확인용 import

        self._keyring = keyring
        # 실제로 동작하는지 왕복 확인
        probe_name = "__evidence_root_probe__"
        self._keyring.set_password(SERVICE_NAME, probe_name, "ok")
        if self._keyring.get_password(SERVICE_NAME, probe_name) != "ok":
            raise RuntimeError("keyring backend unavailable")
        self._keyring.delete_password(SERVICE_NAME, probe_name)

    def get(self, name: str) -> Optional[str]:
        try:
            return self._keyring.get_password(SERVICE_NAME, name)
        except Exception:
            logger.warning("keyring get 실패: name=%s", name)
            return None

    def set(self, name: str, value: str) -> None:
        self._keyring.set_password(SERVICE_NAME, name, value)

    def delete(self, name: str) -> None:
        try:
            self._keyring.delete_password(SERVICE_NAME, name)
        except Exception:
            pass


class FernetFileSecretStore:
    """Keyring을 쓸 수 없는 환경(서버/컨테이너)을 위한 로컬 암호화 파일 저장소."""

    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        from cryptography.fernet import Fernet

        self._Fernet = Fernet
        self._data_dir = data_dir
        self._secrets_file = data_dir / "encrypted_secrets.json"
        self._key_file = data_dir / "local_secret.key"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._fernet = self._Fernet(self._load_or_create_key())

    def _load_or_create_key(self) -> bytes:
        if self._key_file.exists():
            return self._key_file.read_bytes()
        key = self._Fernet.generate_key()
        self._key_file.write_bytes(key)
        return key

    def _load_all(self) -> dict[str, str]:
        if not self._secrets_file.exists():
            return {}
        try:
            raw = json.loads(self._secrets_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        result: dict[str, str] = {}
        for name, token in raw.items():
            try:
                result[name] = self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")
            except Exception:
                logger.warning("암호화된 값 복호화 실패: name=%s (손상되었거나 키가 변경됨)", name)
        return result

    def _save_all(self, values: dict[str, str]) -> None:
        encrypted = {
            name: self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")
            for name, value in values.items()
        }
        self._secrets_file.write_text(json.dumps(encrypted, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, name: str) -> Optional[str]:
        return self._load_all().get(name)

    def set(self, name: str, value: str) -> None:
        values = self._load_all()
        values[name] = value
        self._save_all(values)

    def delete(self, name: str) -> None:
        values = self._load_all()
        if name in values:
            del values[name]
            self._save_all(values)


_store_instance: Optional[SecretStore] = None


def get_secret_store() -> SecretStore:
    """프로세스 내 싱글턴 SecretStore. Keyring 우선, 실패 시 Fernet 파일로 폴백."""
    global _store_instance
    if _store_instance is not None:
        return _store_instance
    try:
        _store_instance = KeyringSecretStore()
        logger.info("SecretStore backend: keyring")
    except Exception:
        logger.info("keyring 사용 불가 → Fernet 파일 저장소로 폴백")
        _store_instance = FernetFileSecretStore()
    return _store_instance


def reset_secret_store() -> None:
    """테스트/키 변경 시 싱글턴을 초기화한다."""
    global _store_instance
    _store_instance = None
