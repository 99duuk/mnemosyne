from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final

from .enums import WarningCode
from .url import (
    CaptureModelError,
    ModelErrorCode,
    NaverIdentity,
    parse_naver_url,
    reject_body_controls,
    reject_controls,
    strict_utf8_bytes,
)


PAYLOAD_SCHEMA: Final = "mnemosyne.safari-extract/v1"
_DATE_PATTERN = re.compile(
    r"^(?P<Y>[0-9]{4})[.] (?P<M>[0-9]{1,2})[.] (?P<D>[0-9]{1,2})[.]"
    r"(?: (?P<h>[0-9]{1,2}):(?P<m>[0-9]{2}))?$"
)
_PAYLOAD_FIELDS: Final = {
    "schema", "top_document_url", "content_document_url", "canonical_url", "title",
    "published_at_raw", "body", "editor_fingerprint", "component_counts", "warnings",
}
_COUNT_FIELDS: Final = {"images", "tables", "embeds", "media"}


@dataclass(frozen=True, slots=True)
class _TextLimits:
    raw_bytes: int
    scalars: int
    normalized_bytes: int


_TITLE_LIMITS: Final = _TextLimits(4096, 500, 4096)
_DATE_LIMITS: Final = _TextLimits(1024, 128, 1024)


@dataclass(frozen=True, slots=True)
class CapturePayload:
    identity: NaverIdentity
    observed_url: str
    title: str
    published_at: str | None
    published_at_raw: str
    body: str
    warnings: tuple[WarningCode, ...]

    @classmethod
    def from_json_bytes(cls, raw: bytes, observed_url: str) -> CapturePayload:
        observed_identity = parse_naver_url(observed_url)
        value = _decode_payload(raw)
        _require_fields(value, _PAYLOAD_FIELDS, "payload")
        if value["schema"] != PAYLOAD_SCHEMA or value["editor_fingerprint"] != "smarteditor_one":
            raise CaptureModelError(ModelErrorCode.INVALID_PAYLOAD, "schema")
        identity = _validate_payload_urls(value, observed_identity)
        title = _normalized_text_field(value["title"], "title", _TITLE_LIMITS)
        raw_date = _normalized_text_field(value["published_at_raw"], "published_at_raw", _DATE_LIMITS)
        body = _normalized_body_field(value["body"])
        warnings = list(_validate_components(value["component_counts"], value["warnings"]))
        published_at = _parse_date(raw_date)
        if published_at is None:
            warnings.append(WarningCode.PUBLISHED_AT_UNPARSED)
        return cls(identity, observed_url, title, published_at, raw_date, body, tuple(sorted(warnings)))


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def normalize_body(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    lines = [line.rstrip(" \t") for line in normalized.split("\n")]
    while lines and not lines[0].strip(" \t"):
        lines.pop(0)
    while lines and not lines[-1].strip(" \t"):
        lines.pop()
    return "\n".join(lines) + "\n"


class DuplicateKeyError(Exception):
    pass


def _decode_payload(raw: bytes):
    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=_unique_mapping)
    except (UnicodeDecodeError, json.JSONDecodeError, DuplicateKeyError) as error:
        raise CaptureModelError(ModelErrorCode.INVALID_PAYLOAD, "json") from error
    if type(value) is not dict:
        raise CaptureModelError(ModelErrorCode.INVALID_PAYLOAD, "json")
    _reject_nested_surrogates(value)
    return value


def _unique_mapping(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def _reject_nested_surrogates(value) -> None:
    if type(value) is str:
        strict_utf8_bytes(value, "payload", ModelErrorCode.INVALID_PAYLOAD)
    elif type(value) is list:
        for item in value:
            _reject_nested_surrogates(item)
    elif type(value) is dict:
        for key, item in value.items():
            strict_utf8_bytes(key, "payload", ModelErrorCode.INVALID_PAYLOAD)
            _reject_nested_surrogates(item)


def _require_fields(value, fields: set[str], field: str) -> None:
    if type(value) is not dict or set(value) != fields:
        raise CaptureModelError(ModelErrorCode.INVALID_PAYLOAD, field)


def _require_string(value, field: str) -> str:
    if type(value) is not str:
        raise CaptureModelError(ModelErrorCode.INVALID_PAYLOAD, field)
    return value


def _validate_payload_urls(value, observed: NaverIdentity) -> NaverIdentity:
    urls = (
        _require_string(value["top_document_url"], "top_document_url"),
        _require_string(value["content_document_url"], "content_document_url"),
    )
    canonical = value["canonical_url"]
    if canonical is not None:
        urls += (_require_string(canonical, "canonical_url"),)
    for url in urls:
        identity = parse_naver_url(url, ModelErrorCode.INVALID_PAYLOAD, ModelErrorCode.INVALID_PAYLOAD)
        if (identity.blog_id, identity.post_id) != (observed.blog_id, observed.post_id):
            raise CaptureModelError(ModelErrorCode.INVALID_PAYLOAD, "url_identity")
    return observed


def _normalized_text_field(value, field: str, limits: _TextLimits) -> str:
    raw = _require_string(value, field)
    reject_controls(raw, field, ModelErrorCode.INVALID_PAYLOAD)
    if len(strict_utf8_bytes(raw, field, ModelErrorCode.INVALID_PAYLOAD)) > limits.raw_bytes:
        raise CaptureModelError(ModelErrorCode.INVALID_PAYLOAD, field)
    normalized = normalize_text(raw)
    if not 1 <= len(normalized) <= limits.scalars or len(normalized.encode()) > limits.normalized_bytes:
        raise CaptureModelError(ModelErrorCode.INVALID_PAYLOAD, field)
    return normalized


def _normalized_body_field(value) -> str:
    raw = _require_string(value, "body")
    reject_body_controls(raw, "body", ModelErrorCode.INVALID_PAYLOAD)
    if len(strict_utf8_bytes(raw, "body", ModelErrorCode.INVALID_PAYLOAD)) > 10_485_760:
        raise CaptureModelError(ModelErrorCode.INVALID_PAYLOAD, "body")
    normalized = normalize_body(raw)
    size = len(normalized.encode())
    if not 1 <= size <= 10_485_760 or not any(not char.isspace() for char in normalized):
        raise CaptureModelError(ModelErrorCode.INVALID_PAYLOAD, "body")
    return normalized


def _validate_components(value, warnings_value) -> tuple[WarningCode, ...]:
    _require_fields(value, _COUNT_FIELDS, "component_counts")
    mapping = {
        "images": WarningCode.IMAGES_OMITTED, "tables": WarningCode.TABLES_OMITTED,
        "embeds": WarningCode.EMBEDS_OMITTED, "media": WarningCode.MEDIA_OMITTED,
    }
    expected = []
    for name, warning in mapping.items():
        count = value[name]
        if type(count) is not int or count < 0:
            raise CaptureModelError(ModelErrorCode.INVALID_PAYLOAD, "component_counts")
        if count > 0:
            expected.append(warning)
    if type(warnings_value) is not list or warnings_value != sorted(warning.value for warning in expected):
        raise CaptureModelError(ModelErrorCode.INVALID_PAYLOAD, "warnings")
    return tuple(sorted(expected))


def _parse_date(value: str) -> str | None:
    matched = _DATE_PATTERN.fullmatch(value)
    if matched is None:
        return None
    parts = {name: int(number) if number is not None else None for name, number in matched.groupdict().items()}
    try:
        parsed_date = date(parts["Y"], parts["M"], parts["D"])
        if parts["h"] is None:
            return parsed_date.isoformat()
        parsed = datetime(parts["Y"], parts["M"], parts["D"], parts["h"], parts["m"])
    except (TypeError, ValueError):
        return None
    return parsed.strftime("%Y-%m-%dT%H:%M:00+09:00")
