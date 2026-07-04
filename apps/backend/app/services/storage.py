"""Object storage abstraction for document uploads.

``get_storage()`` selects the implementation based on
``settings.STORAGE_BACKEND``:

* ``local`` (default) — ``LocalDevStorage`` writes bytes under
  ``APP_DATA_PATH/dev_storage`` and returns
  ``http://localhost:8000/dev-storage/{key}`` URLs so the upload-init /
  upload / record flow works end-to-end without an external blob provider.
* ``s3`` — ``S3Storage`` presigns direct-to-bucket PUT/GET URLs against any
  S3-compatible endpoint (R2, MinIO, AWS) using the ``S3_*`` settings. The
  bucket must allow CORS for PUT/GET from the app origins, since the browser
  uploads straight to the presigned URL.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, unquote

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


def _prefixed_key(key: str) -> str:
    """Prepend the configured ``S3_PREFIX`` subdirectory to a logical key."""
    prefix = settings.S3_PREFIX.strip("/")
    if prefix:
        return f"{prefix}/{key}"
    return key


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


class S3Storage(StoragePort):
    """S3-compatible storage (R2 / MinIO / AWS) via presigned URLs.

    Presigning is pure local crypto — no network round-trip — so the sync
    boto3 client is safe to call from request handlers (``presign_get`` runs
    once per row when listing documents).
    """

    def __init__(self):
        import boto3

        self._client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION,
        )
        self._bucket = settings.S3_BUCKET_NAME

    def _canonical_url(self, key: str) -> str:
        """The stable URL persisted in ``documents.file_url``.

        Prefer the public CDN base when configured; otherwise a path-style
        endpoint URL. Either way ``key_from_file_url`` can recover the key,
        and reads go through ``presign_get`` so private buckets still work.
        """
        encoded = quote(key, safe="/")
        public_base = settings.S3_PUBLIC_URL.rstrip("/")
        if public_base:
            return f"{public_base}/{encoded}"
        endpoint = settings.S3_ENDPOINT_URL.rstrip("/")
        return f"{endpoint}/{self._bucket}/{encoded}"

    def presign_put(
        self, key: str, mime_type: str | None = None
    ) -> tuple[str, str, datetime]:
        # The S3_PREFIX subdirectory is applied exactly once, here at
        # upload-init time. The canonical file_url therefore carries the full
        # (prefixed) key, and presign_get — whose keys come back out of
        # file_urls via key_from_file_url — must never prefix again.
        full_key = _prefixed_key(key)
        params: dict = {"Bucket": self._bucket, "Key": full_key}
        # Sign the content type only when known — a signed ContentType forces
        # the client to send exactly that header, while leaving it unsigned
        # lets the browser default (application/octet-stream) through.
        if mime_type:
            params["ContentType"] = mime_type
        upload_url = self._client.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=int(_PRESIGN_TTL.total_seconds()),
        )
        expires_at = datetime.now(timezone.utc) + _PRESIGN_TTL
        return upload_url, self._canonical_url(full_key), expires_at

    def presign_get(self, key: str) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=int(_PRESIGN_TTL.total_seconds()),
        )


_storage_singleton: StoragePort | None = None


def get_storage() -> StoragePort:
    """Return the process-wide ``StoragePort`` based on ``settings.STORAGE_BACKEND``."""
    global _storage_singleton
    if _storage_singleton is not None:
        return _storage_singleton
    backend = (settings.STORAGE_BACKEND or "local").lower()
    if backend == "local":
        _storage_singleton = LocalDevStorage()
    elif backend == "s3":
        _storage_singleton = S3Storage()
    else:
        raise ValueError(f"Unknown STORAGE_BACKEND: {settings.STORAGE_BACKEND}")
    return _storage_singleton


def reset_storage() -> None:
    """Drop the cached singleton; used by tests that point at a temp dir."""
    global _storage_singleton
    _storage_singleton = None


def key_from_file_url(file_url: str) -> str:
    """Extract the storage key from a stored ``file_url``.

    Handles every canonical form we have ever persisted: the local
    ``/dev-storage/{key}`` route, the S3 public base
    (``{S3_PUBLIC_URL}/{key}``), and the path-style endpoint form
    (``{S3_ENDPOINT_URL}/{bucket}/{key}``).
    """
    for base in (
        settings.S3_PUBLIC_URL.rstrip("/"),
        (
            f"{settings.S3_ENDPOINT_URL.rstrip('/')}/{settings.S3_BUCKET_NAME}"
            if settings.S3_ENDPOINT_URL
            else ""
        ),
    ):
        if base and file_url.startswith(f"{base}/"):
            return unquote(file_url[len(base) + 1 :])
    return _key_from_url(file_url)
