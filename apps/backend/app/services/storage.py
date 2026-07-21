"""Object storage abstraction for document uploads.

``get_storage()`` selects the implementation based on
``settings.STORAGE_BACKEND``:

* ``local`` (default) — ``LocalDevStorage`` writes bytes under
  ``APP_DATA_PATH/dev_storage`` and returns
  ``http://localhost:8000/dev-storage/{key}`` URLs so the upload-init /
  upload / record flow works end-to-end without an external blob provider.
* ``s3`` — ``S3Storage`` stores blobs in any S3-compatible bucket (R2,
  MinIO, AWS) using the ``S3_*`` settings. Uploads are proxied through the
  API (``PUT /documents/upload/{key}``) and written server-side, so the
  browser never talks to the bucket and no bucket CORS config is needed;
  downloads are presigned GETs consumed as plain link navigations, which
  CORS does not apply to either.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

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

    @abstractmethod
    def read(self, key: str) -> bytes | None:
        """Return the raw bytes stored under ``key``, or ``None`` if absent.

        Server-side read of the object (no client round-trip), used where the
        API itself needs the content — e.g. AI letter drafting. ``key`` comes
        out of a stored ``file_url`` via :func:`key_from_file_url`, so it is
        already prefixed; implementations must not prefix again."""

    @abstractmethod
    def write(self, key: str, content: bytes, mime_type: str | None = None) -> None:
        """Persist raw bytes under ``key`` (as returned inside upload URLs —
        already prefixed; implementations must not prefix again)."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove the object stored under ``key``. Missing objects are a
        no-op — deletes are best-effort cleanup after the DB row is gone."""


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

    def _resolve(self, key: str) -> Path:
        """Resolve ``key`` inside ``base_dir``, refusing any escape.

        ``pathlib`` does not normalize ``..``; without this check a key like
        ``../../etc/passwd`` reads outside the storage root.
        """
        root = self.base_dir.resolve()
        path = (root / key).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"Storage key escapes the storage root: {key!r}")
        return path

    def write(self, key: str, content: bytes, mime_type: str | None = None) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def read(self, key: str) -> bytes | None:
        path = self._resolve(key)
        if not path.exists() or not path.is_file():
            return None
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.is_file():
            path.unlink()


class S3Storage(StoragePort):
    """S3-compatible storage (R2 / MinIO / AWS).

    Uploads are proxied: ``presign_put`` hands the client an API-relative
    upload URL, and ``PUT /documents/upload/{key}`` calls :meth:`write` to
    push the bytes to the bucket server-side — no bucket CORS required.
    Reads stay presigned GETs (pure local crypto, no network round-trip, so
    the sync boto3 client is safe to call once per row when listing
    documents) consumed as link navigations.
    """

    def __init__(self):
        import boto3

        # Fail fast on partial config. Without this, boto3 silently falls
        # back to the ambient AWS credential chain (~/.aws, AWS_* env vars)
        # and the default AWS endpoint — i.e. it starts talking to the wrong
        # cloud and surfaces only as a confusing AccessDenied at upload time.
        missing = [
            name
            for name, value in (
                ("S3_ENDPOINT_URL", settings.S3_ENDPOINT_URL),
                ("S3_ACCESS_KEY_ID", settings.S3_ACCESS_KEY_ID),
                ("S3_SECRET_ACCESS_KEY", settings.S3_SECRET_ACCESS_KEY),
                ("S3_BUCKET_NAME", settings.S3_BUCKET_NAME),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                "STORAGE_BACKEND=s3 requires " + ", ".join(missing) + " to be set"
            )
        # A path on the endpoint (e.g. the per-bucket "S3 API" URL copied
        # from the R2 dashboard) makes R2 read that segment as the bucket
        # name and reject everything with AccessDenied. Host-only, always.
        endpoint_path = urlsplit(settings.S3_ENDPOINT_URL).path.strip("/")
        if endpoint_path:
            raise ValueError(
                "S3_ENDPOINT_URL must be host-only — remove the trailing "
                f"'/{endpoint_path}' (the bucket belongs in S3_BUCKET_NAME)"
            )

        self._client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
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
        # (prefixed) key, and write/presign_get — whose keys come back out of
        # upload URLs / file_urls — must never prefix again.
        #
        # The upload URL is API-relative: the client PUTs the bytes to the
        # authenticated /documents/upload/{key} proxy, which writes to the
        # bucket server-side. Expiry is advisory here — the proxy is governed
        # by bearer auth, not by a signature.
        full_key = _prefixed_key(key)
        upload_url = f"/documents/upload/{quote(full_key, safe='/')}"
        expires_at = datetime.now(timezone.utc) + _PRESIGN_TTL
        return upload_url, self._canonical_url(full_key), expires_at

    def presign_get(self, key: str) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=int(_PRESIGN_TTL.total_seconds()),
        )

    def read(self, key: str) -> bytes | None:
        from botocore.exceptions import ClientError

        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError:
            # Missing key (NoSuchKey) or any access error — treat as absent so
            # callers degrade rather than crash the worker.
            return None
        return response["Body"].read()

    def write(self, key: str, content: bytes, mime_type: str | None = None) -> None:
        extra: dict = {"ContentType": mime_type} if mime_type else {}
        self._client.put_object(Bucket=self._bucket, Key=key, Body=content, **extra)

    def delete(self, key: str) -> None:
        # S3 DeleteObject is idempotent — deleting a missing key succeeds.
        self._client.delete_object(Bucket=self._bucket, Key=key)


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
