import re
import uuid
from collections.abc import Callable

# Keep in sync with the frontend routes: top-level siblings of /app/:orgSlug
# and the static children of /app/:orgSlug that share the URL level with
# /app/:orgSlug/:fundSlug.
RESERVED_SLUGS = frozenset(
    {
        "app",
        "login",
        "profile",
        "onboarding",
        "settings",
        "superadmin",
        "invitations",
        "api",
        "funds",
        "investors",
        "calls",
        "distributions",
        "documents",
        "letters",
        "tasks",
        "notifications",
        "audit-log",
    }
)

_MAX_BASE_LENGTH = 80
_NON_SLUG_CHARS = re.compile(r"[^a-z0-9-]+")
_REPEATED_HYPHENS = re.compile(r"-{2,}")


def slugify(value: str) -> str:
    """Lowercase, ASCII-only, hyphenated slug derived from ``value``.

    Falls back to a short random token when the input has no slug-able
    characters (e.g. a name made entirely of emoji/symbols).
    """
    candidate = value.strip().lower().replace(" ", "-")
    candidate = _NON_SLUG_CHARS.sub("-", candidate)
    candidate = _REPEATED_HYPHENS.sub("-", candidate).strip("-")
    candidate = candidate[:_MAX_BASE_LENGTH].strip("-")
    if not candidate:
        candidate = f"org-{uuid.uuid4().hex[:8]}"
    return candidate


def generate_unique_slug(
    base: str,
    *,
    exists: Callable[[str], bool],
    reserved: frozenset[str] = RESERVED_SLUGS,
) -> str:
    """Slugify ``base`` and append a deterministic ``-2``, ``-3``, ... suffix
    until the candidate is free (per ``exists``) and not a reserved word.

    A reserved-word match is treated the same as a collision rather than
    raising, since organization/fund names like "App Capital" are plausible
    and shouldn't surface a confusing validation error at creation time.
    """
    root = slugify(base)
    candidate = root
    suffix = 2
    while exists(candidate) or candidate in reserved:
        candidate = f"{root}-{suffix}"
        suffix += 1
    return candidate
