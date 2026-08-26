from __future__ import annotations

import hashlib
import json
import re
import struct
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from .enums import CaptureMethod, EditorFingerprint, Platform, RightsReviewStatus, WarningCode
from .payload import CapturePayload
from .url import CaptureModelError, ModelErrorCode


SCHEMA_VERSION: Final = "mnemosyne.capture/v1"
_REVISION_PREFIX: Final = b"mnemosyne.capture.revision/v1\n"
_CAPTURED_AT = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{6}[+]09:00\Z")


@dataclass(frozen=True, slots=True)
class CaptureContext:
    captured_at: str
    supersedes_revision_id: str | None = None


@dataclass(frozen=True, slots=True)
class SourceRecord:
    platform: Platform
    blog_id: str
    post_id: str
    observed_url: str
    canonical_url: str


@dataclass(frozen=True, slots=True)
class MarkdownRecord:
    path: str
    sha256: str
    bytes: int


@dataclass(frozen=True, slots=True)
class CaptureRecord:
    schema_version: str
    document_key: str
    revision_id: str
    supersedes_revision_id: str | None
    source: SourceRecord
    title: str
    published_at: str | None
    published_at_raw: str
    captured_at: str
    editor_fingerprint: EditorFingerprint
    capture_method: CaptureMethod
    rights_review_status: RightsReviewStatus
    warnings: tuple[WarningCode, ...]
    body_sha256: str
    markdown: MarkdownRecord


@dataclass(frozen=True, slots=True)
class Capture:
    draft: CapturePayload
    record: CaptureRecord


def revision_preimage(payload: CapturePayload) -> bytes:
    document_key = f"naver_blog:{payload.identity.blog_id}:{payload.identity.post_id}"
    discriminator = "P" if payload.published_at is not None else "R"
    date_value = payload.published_at if payload.published_at is not None else payload.published_at_raw
    fields = (document_key, payload.title, discriminator, date_value, payload.body)
    return _REVISION_PREFIX + b"".join(struct.pack(">Q", len(field.encode())) + field.encode() for field in fields)


def create_capture(payload: CapturePayload, context: CaptureContext) -> Capture:
    _validate_context(context)
    document_key = f"naver_blog:{payload.identity.blog_id}:{payload.identity.post_id}"
    revision_id = hashlib.sha256(revision_preimage(payload)).hexdigest()
    markdown = _markdown_bytes(payload, context, revision_id)
    record = CaptureRecord(
        schema_version=SCHEMA_VERSION,
        document_key=document_key,
        revision_id=revision_id,
        supersedes_revision_id=context.supersedes_revision_id,
        source=SourceRecord(Platform.NAVER_BLOG, payload.identity.blog_id, payload.identity.post_id, payload.observed_url, payload.identity.canonical_url),
        title=payload.title,
        published_at=payload.published_at,
        published_at_raw=payload.published_at_raw,
        captured_at=context.captured_at,
        editor_fingerprint=EditorFingerprint.SMARTEDITOR_ONE,
        capture_method=CaptureMethod.SAFARI_AUTOMATOR_CURRENT_TAB,
        rights_review_status=RightsReviewStatus.UNREVIEWED,
        warnings=payload.warnings,
        body_sha256=hashlib.sha256(payload.body.encode()).hexdigest(),
        markdown=MarkdownRecord("post.md", hashlib.sha256(markdown).hexdigest(), len(markdown)),
    )
    return Capture(payload, record)


def render_markdown(capture: Capture) -> bytes:
    return _markdown_bytes(
        capture.draft,
        CaptureContext(capture.record.captured_at, capture.record.supersedes_revision_id),
        capture.record.revision_id,
    )


def canonical_record_bytes(record: CaptureRecord) -> bytes:
    return (_canonical_json(_record_mapping(record)) + "\n").encode()


def render_jsonl_line(capture: Capture) -> bytes:
    value = _record_mapping(capture.record)
    value["body"] = capture.draft.body
    return (_canonical_json(value) + "\n").encode()


def _validate_context(context: CaptureContext) -> None:
    try:
        datetime.fromisoformat(context.captured_at)
    except ValueError as error:
        raise CaptureModelError(ModelErrorCode.INVALID_PAYLOAD, "captured_at") from error
    if _CAPTURED_AT.fullmatch(context.captured_at) is None:
        raise CaptureModelError(ModelErrorCode.INVALID_PAYLOAD, "captured_at")
    if context.supersedes_revision_id is not None and re.fullmatch(r"[0-9a-f]{64}", context.supersedes_revision_id) is None:
        raise CaptureModelError(ModelErrorCode.INVALID_PAYLOAD, "supersedes_revision_id")


def _json_scalar(value: str | None) -> str:
    return "null" if value is None else json.dumps(value, ensure_ascii=False)


def _markdown_bytes(payload: CapturePayload, context: CaptureContext, revision_id: str) -> bytes:
    document_key = f"naver_blog:{payload.identity.blog_id}:{payload.identity.post_id}"
    fields = (
        ("schema_version", SCHEMA_VERSION),
        ("document_key", document_key),
        ("revision_id", revision_id),
        ("title", payload.title),
        ("published_at", payload.published_at),
        ("published_at_raw", payload.published_at_raw),
        ("canonical_url", payload.identity.canonical_url),
        ("captured_at", context.captured_at),
        ("rights_review_status", "UNREVIEWED"),
    )
    frontmatter = "\n".join(f"{key}: {_json_scalar(value)}" for key, value in fields)
    return f"---\n{frontmatter}\n---\n\n{payload.body}".encode()


def _record_mapping(record: CaptureRecord):
    return {
        "schema_version": record.schema_version,
        "document_key": record.document_key,
        "revision_id": record.revision_id,
        "supersedes_revision_id": record.supersedes_revision_id,
        "source": {
            "platform": record.source.platform,
            "blog_id": record.source.blog_id,
            "post_id": record.source.post_id,
            "observed_url": record.source.observed_url,
            "canonical_url": record.source.canonical_url,
        },
        "title": record.title,
        "published_at": record.published_at,
        "published_at_raw": record.published_at_raw,
        "captured_at": record.captured_at,
        "editor_fingerprint": record.editor_fingerprint,
        "capture_method": record.capture_method,
        "rights_review_status": record.rights_review_status,
        "warnings": [warning.value for warning in record.warnings],
        "body_sha256": record.body_sha256,
        "markdown": {"path": record.markdown.path, "sha256": record.markdown.sha256, "bytes": record.markdown.bytes},
    }


def _canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
