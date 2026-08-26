from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from .payload import CapturePayload
from .url import CaptureModelError


_HEADER: Final = b"MNEMOSYNE_BRIDGE_V1"
_URL_BYTES: Final = 4096
_ALLOWED_ERRORS: Final = {
    "snapshot": frozenset({"NO_SAFARI_TAB", "SAFARI_NOT_FRONTMOST", "APPLE_EVENTS_DENIED"}),
    "smoke": frozenset(
        {"NO_SAFARI_TAB", "SAFARI_NOT_FRONTMOST", "APPLE_EVENTS_DENIED", "JAVASCRIPT_UNAVAILABLE", "TAB_CHANGED"},
    ),
    "extract": frozenset(
        {
            "NO_SAFARI_TAB", "SAFARI_NOT_FRONTMOST", "APPLE_EVENTS_DENIED",
            "JAVASCRIPT_UNAVAILABLE", "TAB_CHANGED", "UNSUPPORTED_PAGE",
        },
    ),
}


class BridgeErrorCode(StrEnum):
    NO_SAFARI_TAB = "NO_SAFARI_TAB"
    SAFARI_NOT_FRONTMOST = "SAFARI_NOT_FRONTMOST"
    APPLE_EVENTS_DENIED = "APPLE_EVENTS_DENIED"
    JAVASCRIPT_UNAVAILABLE = "JAVASCRIPT_UNAVAILABLE"
    TAB_CHANGED = "TAB_CHANGED"
    UNSUPPORTED_PAGE = "UNSUPPORTED_PAGE"
    BRIDGE_TIMEOUT = "BRIDGE_TIMEOUT"
    SCRIPT_EXECUTION_BLOCKED = "SCRIPT_EXECUTION_BLOCKED"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    NOTIFICATION_FAILED = "NOTIFICATION_FAILED"


@dataclass(frozen=True, slots=True)
class BridgeError(Exception):
    code: BridgeErrorCode

    def __str__(self) -> str:
        return self.code


@dataclass(frozen=True, slots=True)
class ArtifactError(Exception):
    path: Path

    def __str__(self) -> str:
        return "invalid bridge artifact"


@dataclass(frozen=True, slots=True)
class SnapshotResult:
    url: str


@dataclass(frozen=True, slots=True)
class SmokeResult:
    token: str


@dataclass(frozen=True, slots=True)
class ExtractResult:
    before_url: str
    after_url: str
    payload: CapturePayload


@dataclass(frozen=True, slots=True)
class _Artifact:
    path: Path
    device: int
    inode: int
    digest: bytes

    @classmethod
    def bind(cls, path: Path) -> _Artifact:
        if not path.is_absolute():
            raise ArtifactError(path)
        flags = os.O_RDONLY | os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags)
            with os.fdopen(descriptor, "rb") as artifact:
                status = os.fstat(artifact.fileno())
                content = artifact.read()
        except OSError as error:
            raise ArtifactError(path) from error
        if (
            not stat.S_ISREG(status.st_mode)
            or status.st_uid != os.getuid()
            or status.st_nlink != 1
            or stat.S_IMODE(status.st_mode) != 0o600
        ):
            raise ArtifactError(path)
        return cls(path, status.st_dev, status.st_ino, hashlib.sha256(content).digest())

    def revalidate(self) -> None:
        current = type(self).bind(self.path)
        if (current.device, current.inode, current.digest) != (self.device, self.inode, self.digest):
            raise ArtifactError(self.path)


@dataclass(frozen=True, slots=True)
class Bridge:
    capture_script: _Artifact
    extractor_script: _Artifact

    @classmethod
    def bind(cls, capture_script: Path, extractor_script: Path) -> Bridge:
        return cls(_Artifact.bind(capture_script), _Artifact.bind(extractor_script))

    def snapshot(self) -> SnapshotResult:
        lines = self._invoke("snapshot", ())
        if len(lines) != 3 or lines[:2] != [_HEADER, b"OK"]:
            self._blocked()
        return SnapshotResult(_decode(lines[2], BridgeErrorCode.SCRIPT_EXECUTION_BLOCKED))

    def smoke(self, expected_url: str) -> SmokeResult:
        _outer_url(expected_url)
        lines = self._invoke("smoke", (expected_url,))
        if lines != [_HEADER, b"OK", b"MNEMOSYNE_JS_OK"]:
            self._blocked()
        return SmokeResult("MNEMOSYNE_JS_OK")

    def extract(self, expected_url: str) -> ExtractResult:
        _outer_url(expected_url)
        lines = self._invoke("extract", (expected_url, str(self.extractor_script.path)))
        if len(lines) != 5 or lines[:2] != [_HEADER, b"OK"]:
            self._blocked()
        before = _outer_url(_decode(lines[2], BridgeErrorCode.TAB_CHANGED))
        after = _outer_url(_decode(lines[3], BridgeErrorCode.TAB_CHANGED))
        if before != expected_url or after != expected_url:
            raise BridgeError(BridgeErrorCode.TAB_CHANGED)
        try:
            payload = CapturePayload.from_json_bytes(lines[4], expected_url)
        except CaptureModelError as error:
            raise BridgeError(BridgeErrorCode.INVALID_PAYLOAD) from error
        return ExtractResult(before, after, payload)

    def notify(self, title: str, message: str) -> None:
        try:
            lines = self._invoke("notify", (title, message))
        except BridgeError as error:
            raise BridgeError(BridgeErrorCode.NOTIFICATION_FAILED) from error
        if lines != [_HEADER, b"OK"]:
            raise BridgeError(BridgeErrorCode.NOTIFICATION_FAILED)

    def _invoke(self, mode: str, arguments: tuple[str, ...]) -> list[bytes]:
        self.capture_script.revalidate()
        self.extractor_script.revalidate()
        argv = ["/usr/bin/osascript", str(self.capture_script.path), mode, *arguments]
        try:
            result = subprocess.run(argv, shell=False, timeout=10, capture_output=True)
        except subprocess.TimeoutExpired as error:
            code = BridgeErrorCode.NOTIFICATION_FAILED if mode == "notify" else BridgeErrorCode.BRIDGE_TIMEOUT
            raise BridgeError(code) from error
        except OSError as error:
            code = BridgeErrorCode.NOTIFICATION_FAILED if mode == "notify" else BridgeErrorCode.SCRIPT_EXECUTION_BLOCKED
            raise BridgeError(code) from error
        if result.returncode != 0 or not result.stdout.endswith(b"\n"):
            code = BridgeErrorCode.NOTIFICATION_FAILED if mode == "notify" else BridgeErrorCode.SCRIPT_EXECUTION_BLOCKED
            raise BridgeError(code)
        lines = result.stdout[:-1].split(b"\n")
        if mode != "notify" and lines[:2] == [_HEADER, b"ERROR"] and len(lines) == 3:
            try:
                raw_code = lines[2].decode("ascii", "strict")
            except UnicodeDecodeError:
                self._blocked()
            if raw_code in _ALLOWED_ERRORS[mode]:
                raise BridgeError(BridgeErrorCode(raw_code))
        return lines

    @staticmethod
    def _blocked() -> None:
        raise BridgeError(BridgeErrorCode.SCRIPT_EXECUTION_BLOCKED)


def _decode(value: bytes, code: BridgeErrorCode) -> str:
    try:
        return value.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise BridgeError(code) from error


def _outer_url(value: str) -> str:
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeEncodeError as error:
        raise BridgeError(BridgeErrorCode.TAB_CHANGED) from error
    if len(encoded) > _URL_BYTES:
        raise BridgeError(BridgeErrorCode.TAB_CHANGED)
    return value
