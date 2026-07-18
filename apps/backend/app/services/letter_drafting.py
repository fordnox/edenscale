"""AI letter drafting for the documents library.

``draft_letter`` sends a document's content to an LLM (via OpenRouter's
OpenAI-compatible chat-completions API) and returns a ``(subject, body)`` pair
suitable for a :class:`~app.models.communication` draft. The manager UI
surfaces this as the "Draft letter" row action; the work runs in the arq worker
(see ``app.worker.task_draft_letter``) because a multi-page PDF can take tens of
seconds to draft.

The feature is inert unless ``settings.OPENROUTER_API_KEY`` is set
(``settings.letter_drafting_enabled``); the endpoint gates on that before
anything reaches this module.
"""

import base64
import json
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Structured-output schema: the model must return exactly these two fields, so
# the worker can persist them without brittle text parsing.
_LETTER_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "body": {"type": "string"},
    },
    "required": ["subject", "body"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = (
    "You are an assistant to a private-fund manager. Draft a clear, professional "
    "letter to limited partners based on the attached document. Summarize what the "
    "document communicates and frame it as correspondence a fund manager would send "
    "to investors. Use plain prose in the body — paragraphs separated by blank "
    "lines, no markdown, no salutation placeholders like [Name]. Keep it concise "
    "and factual; do not invent figures or commitments that are not supported by "
    "the document. Return a concise subject line and the letter body."
)

# Text-like documents we inline directly; anything else that isn't a PDF is
# sent as a title-only prompt (the model drafts from the title alone).
_TEXT_MIME_PREFIXES = ("text/",)
_TEXT_MIME_TYPES = {"application/json", "application/xml"}
# Cap inlined text so a large plaintext file can't blow the context window.
_MAX_INLINE_TEXT_CHARS = 100_000

# How long to wait for the model — drafting a multi-page PDF is slow, and this
# runs in the worker (off the request path), so a generous timeout is fine.
_REQUEST_TIMEOUT_SECONDS = 180.0


def _build_user_content(
    *, file_bytes: bytes | None, mime_type: str | None, title: str
) -> tuple[list[dict], bool]:
    """Assemble the user message content array.

    Returns ``(content, is_pdf)`` — ``is_pdf`` tells the caller to attach the
    OpenRouter file-parser plugin. PDFs go in as a ``file`` content part; text
    files are decoded and inlined; everything else falls back to the title.
    """
    instruction = (
        f'Draft a letter to limited partners based on this document titled "{title}".'
    )
    mime = (mime_type or "").lower()

    if file_bytes and mime == "application/pdf":
        encoded = base64.standard_b64encode(file_bytes).decode("ascii")
        return (
            [
                {"type": "text", "text": instruction},
                {
                    "type": "file",
                    "file": {
                        "filename": f"{title}.pdf",
                        "file_data": f"data:application/pdf;base64,{encoded}",
                    },
                },
            ],
            True,
        )

    if file_bytes and (
        mime.startswith(_TEXT_MIME_PREFIXES) or mime in _TEXT_MIME_TYPES
    ):
        text = file_bytes.decode("utf-8", errors="ignore")[:_MAX_INLINE_TEXT_CHARS]
        return (
            [{"type": "text", "text": f"{instruction}\n\nDocument content:\n\n{text}"}],
            False,
        )

    # No usable bytes — draft from the title alone.
    return [{"type": "text", "text": instruction}], False


def draft_letter(
    *, file_bytes: bytes | None, mime_type: str | None, title: str
) -> tuple[str, str]:
    """Draft a letter from a document and return ``(subject, body)``.

    Raises if the model call fails or returns malformed output; the worker logs
    and drops the job in that case.
    """
    content, is_pdf = _build_user_content(
        file_bytes=file_bytes, mime_type=mime_type, title=title
    )
    payload: dict = {
        "model": settings.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "letter",
                "strict": True,
                "schema": _LETTER_SCHEMA,
            },
        },
        "max_tokens": 4000,
    }
    if is_pdf:
        # Claude-family models handle PDFs natively (billed as input tokens, no
        # OCR fee); the native engine passes the file straight through.
        payload["plugins"] = [{"id": "file-parser", "pdf": {"engine": "native"}}]

    response = httpx.post(
        f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            # OpenRouter app attribution (openrouter.ai/docs/app-attribution):
            # HTTP-Referer identifies the app in rankings; X-OpenRouter-Title
            # sets its display name.
            "HTTP-Referer": settings.app_domain_url,
            "X-OpenRouter-Title": "NewTaven",
        },
        json=payload,
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    message_content = response.json()["choices"][0]["message"]["content"]

    parsed = json.loads(message_content)
    subject = str(parsed["subject"]).strip()
    body = str(parsed["body"]).strip()
    if not subject or not body:
        raise ValueError("letter drafting returned an empty subject or body")
    return subject, body
