from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit


_BLOG_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_POST_ID = re.compile(r"[0-9]{1,20}\Z")
_DIRECT_PATH = re.compile(r"/([A-Za-z0-9_-]{1,64})/([0-9]{1,20})/?\Z")
_URL_BYTES = 4096


class ModelErrorCode(StrEnum):
    UNSUPPORTED_HOST = "UNSUPPORTED_HOST"
    UNSUPPORTED_PAGE = "UNSUPPORTED_PAGE"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"


@dataclass(frozen=True, slots=True)
class CaptureModelError(Exception):
    code: ModelErrorCode
    field: str

    def __str__(self) -> str:
        return f"{self.code}: {self.field}"


@dataclass(frozen=True, slots=True)
class NaverIdentity:
    blog_id: str
    post_id: str
    canonical_url: str


def _fail(code: ModelErrorCode, field: str) -> CaptureModelError:
    return CaptureModelError(code=code, field=field)


def strict_utf8_bytes(value: str, field: str, code: ModelErrorCode) -> bytes:
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeEncodeError as error:
        raise _fail(code, field) from error
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise _fail(code, field)
    return encoded


def reject_controls(value: str, field: str, code: ModelErrorCode) -> None:
    for char in value:
        if unicodedata.category(char) == "Cc":
            raise _fail(code, field)


def reject_body_controls(value: str, field: str, code: ModelErrorCode) -> None:
    for char in value:
        if unicodedata.category(char) == "Cc" and char not in "\t\n\r":
            raise _fail(code, field)


def _canonical_post_id(raw: str, code: ModelErrorCode) -> str:
    if _POST_ID.fullmatch(raw) is None or int(raw) == 0:
        raise _fail(code, "post_id")
    return str(int(raw))


def _identity_query(raw_query: str, code: ModelErrorCode) -> tuple[list[str], list[str]]:
    blog_ids: list[str] = []
    post_ids: list[str] = []
    if not raw_query:
        return blog_ids, post_ids
    for item in raw_query.split("&"):
        name, separator, value = item.partition("=")
        if name == "blogId":
            blog_ids.append(value if separator else "")
        elif name == "logNo":
            post_ids.append(value if separator else "")
    for value in (*blog_ids, *post_ids):
        if "%" in value:
            raise _fail(code, "url_identity")
    return blog_ids, post_ids


def parse_naver_url(
    url: str,
    origin_code: ModelErrorCode = ModelErrorCode.UNSUPPORTED_HOST,
    identity_code: ModelErrorCode = ModelErrorCode.UNSUPPORTED_PAGE,
) -> NaverIdentity:
    if len(strict_utf8_bytes(url, "url", origin_code)) > _URL_BYTES:
        raise _fail(origin_code, "url")
    reject_controls(url, "url", origin_code)
    try:
        parsed = urlsplit(url)
    except ValueError as error:
        raise _fail(origin_code, "url") from error
    if not url.startswith("https://") or parsed.scheme != "https" or parsed.netloc != "blog.naver.com":
        raise _fail(origin_code, "url")

    blog_ids, post_ids = _identity_query(parsed.query, identity_code)
    direct = _DIRECT_PATH.fullmatch(parsed.path)
    if direct is not None:
        blog_id, raw_post_id = direct.groups()
        post_id = _canonical_post_id(raw_post_id, identity_code)
        if (blog_ids or post_ids) and (
            len(blog_ids) != 1
            or len(post_ids) != 1
            or blog_ids[0] != blog_id
            or _canonical_post_id(post_ids[0], identity_code) != post_id
        ):
            raise _fail(identity_code, "url_identity")
    elif parsed.path == "/PostView.naver":
        if len(blog_ids) != 1 or len(post_ids) != 1 or _BLOG_ID.fullmatch(blog_ids[0]) is None:
            raise _fail(identity_code, "url_identity")
        blog_id = blog_ids[0]
        post_id = _canonical_post_id(post_ids[0], identity_code)
    else:
        raise _fail(identity_code, "url_identity")
    return NaverIdentity(
        blog_id=blog_id,
        post_id=post_id,
        canonical_url=f"https://blog.naver.com/{blog_id}/{post_id}",
    )
