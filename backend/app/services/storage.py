"""Object storage abstraction for document uploads.

Production deployments will plug in S3 / GCS / R2 by implementing
``StoragePort``. The shipped ``LocalDevStorage`` writes bytes to
``backend/dev_storage/`` and returns ``http://localhost:8000/dev-storage/{key}``
URLs so the upload-init / upload / record flow works end-to-end without an
external blob provider. ``get_storage()`` selects the implementation based on
``settings.STORAGE_BACKEND``.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from app.core.config import settings

_PRESIGN_TTL = timedelta(minutes=15)


class StoragePort(ABC):
    """Pluggable object storage contract used by the documents module."""

    @abstractmethod
    def presign_put(
        self, key: str, mime_type: str | None = None
    ) -> tuple[str, str, datetime]:
        """Return ``(upload_url, public_url, expires_at)`` for a PUT/POST upload.

        ``upload_url`` is what the client uploads bytes to. ``public_url`` is
        the canonical URL persisted in ``documents.file_url`` and used to
        generate later GETs.
        """

    @abstractmethod
    def presign_get(self, key: str) -> str:
        """Return a (possibly time-limited) URL the client can GET to read the file."""


def _key_from_url(url: str) -> str:
    marker = "/dev-storage/"
    idx = url.find(marker)
    if idx == -1:
        return url
    return url[idx + len(marker) :]


class LocalDevStorage(StoragePort):
    """Local-disk storage that mimics presigned uploads via the dev-storage route."""

    def __init__(self, base_dir: Path | None = None, base_url: str | None = None):
        self.base_dir = base_dir or Path(settings.APP_DATA_PATH) / "dev_storage"
        self.base_url = (base_url or "http://localhost:8000").rstrip("/")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _url_for(self, key: str) -> str:
        return f"{self.base_url}/dev-storage/{quote(key, safe='/')}"

    def presign_put(
        self, key: str, mime_type: str | None = None
    ) -> tuple[str, str, datetime]:
        url = self._url_for(key)
        expires_at = datetime.now(timezone.utc) + _PRESIGN_TTL
        return url, url, expires_at

    def presign_get(self, key: str) -> str:
        return self._url_for(key)

    def write(self, key: str, content: bytes) -> Path:
        path = self.base_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def read(self, key: str) -> bytes | None:
        path = self.base_dir / key
        if not path.exists() or not path.is_file():
            return None
        return path.read_bytes()


_storage_singleton: StoragePort | None = None


def get_storage() -> StoragePort:
    """Return the process-wide ``StoragePort`` based on ``settings.STORAGE_BACKEND``."""
    global _storage_singleton
    if _storage_singleton is not None:
        return _storage_singleton
    backend = (settings.STORAGE_BACKEND or "local").lower()
    if backend == "local":
        _storage_singleton = LocalDevStorage()
    else:
        raise ValueError(f"Unknown STORAGE_BACKEND: {settings.STORAGE_BACKEND}")
    return _storage_singleton


def reset_storage() -> None:
    """Drop the cached singleton; used by tests that point at a temp dir."""
    global _storage_singleton
    _storage_singleton = None


def key_from_file_url(file_url: str) -> str:
    """Extract the storage key from a stored ``file_url``."""
    return _key_from_url(file_url)
