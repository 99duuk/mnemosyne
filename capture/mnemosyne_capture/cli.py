from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, assert_never

from .bridge import ArtifactError, Bridge, BridgeError, BridgeErrorCode
from .enums import CommandCode, CommandName, WarningCode
from .payload import CapturePayload
from .store import CaptureStore, StoreLockError, StoreResult
from .url import CaptureModelError, ModelErrorCode, parse_naver_url


_OWNER: Final = "github.com/99duuk/mnemosyne#mnemosyne-capture/v1"
_MANIFEST_SCHEMA: Final = "mnemosyne.runtime-manifest/v1"
_RELEASE_PREFIX: Final = b"mnemosyne.runtime.release/v1\n"
_HEX = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class InternalArtifactPairError(ValueError):
    def __str__(self) -> str:
        return "capture_script and extractor_script must be supplied together"


class RuntimeTamperedError(Exception):
    pass


def main(argv: Sequence[str] | None = None, *, capture_script: Path | None = None,
         extractor_script: Path | None = None) -> int:
    if (capture_script is None) != (extractor_script is None):
        raise InternalArtifactPairError
    parser = argparse.ArgumentParser(prog="mnemosyne_capture")
    parser.add_argument("--data-root", type=Path, default=Path.home() / "Library/Application Support/Mnemosyne")
    parser.add_argument("command", choices=(CommandName.CAPTURE.value, CommandName.EXPORT.value))
    arguments = parser.parse_args(argv)
    root = arguments.data_root
    command = CommandName(arguments.command)
    if not _valid_root(root):
        return _finish(_failure(command, CommandCode.INVALID_PATH))
    if sys.version_info[:2] != (3, 14):
        return _finish(_failure(command, CommandCode.PYTHON_VERSION_MISMATCH))
    store = CaptureStore(root)
    match command:
        case CommandName.EXPORT:
            return _finish(store.export())
        case CommandName.CAPTURE:
            if capture_script is not None and extractor_script is not None:
                try:
                    bridge = Bridge.bind(capture_script, extractor_script)
                except ArtifactError:
                    return _finish(_failure(command, CommandCode.RUNTIME_TAMPERED))
                return _capture_injected(store, bridge)
            return _capture_production(store)
        case unreachable:
            assert_never(unreachable)


def _capture_injected(store: CaptureStore, bridge: Bridge) -> int:
    prepared = _extract(bridge)
    match prepared:
        case StoreResult():
            return _finish(_notify(bridge, prepared))
        case CapturePayload():
            payload = prepared
        case unreachable:
            assert_never(unreachable)
    try:
        with store.locked(create=True):
            return _finish(_notify(bridge, store.capture(payload)))
    except StoreLockError as error:
        return _finish(_notify(bridge, _failure(CommandName.CAPTURE, CommandCode.WRITE_FAILED, error.changed)))


def _capture_production(store: CaptureStore) -> int:
    try:
        with store.locked(create=False):
            try:
                capture_script, extractor_script, capture_sha256, extractor_sha256 = _runtime_artifacts(store.root)
                bridge = Bridge.bind(
                    capture_script,
                    extractor_script,
                    expected_capture_sha256=capture_sha256,
                    expected_extractor_sha256=extractor_sha256,
                )
            except (ArtifactError, RuntimeTamperedError):
                return _finish(_failure(CommandName.CAPTURE, CommandCode.RUNTIME_TAMPERED))
            prepared = _extract(bridge)
            match prepared:
                case StoreResult():
                    result = prepared
                case CapturePayload():
                    result = store.capture(prepared)
                case unreachable:
                    assert_never(unreachable)
            return _finish(_notify(bridge, result))
    except StoreLockError:
        return _finish(_failure(CommandName.CAPTURE, CommandCode.RUNTIME_TAMPERED))


def _extract(bridge: Bridge):
    try:
        snapshot = bridge.snapshot()
        parse_naver_url(snapshot.url)
        return bridge.extract(snapshot.url).payload
    except BridgeError as error:
        return _failure(CommandName.CAPTURE, _bridge_code(error.code))
    except CaptureModelError as error:
        return _failure(CommandName.CAPTURE, _model_code(error.code))
    except ArtifactError:
        return _failure(CommandName.CAPTURE, CommandCode.RUNTIME_TAMPERED)


def _notify(bridge: Bridge, result: StoreResult) -> StoreResult:
    match result.code:
        case CommandCode.CAPTURED | CommandCode.REVISED | CommandCode.DUPLICATE:
            body = f"{result.code.value} — saved"
        case CommandCode.CAPTURED_EXPORT_STALE:
            body = f"{result.code.value} — export required"
        case CommandCode.APPLE_EVENTS_DENIED | CommandCode.JAVASCRIPT_DISABLED:
            body = f"{result.code.value} — enable Safari JavaScript/Automation"
        case (CommandCode.NO_SAFARI_TAB | CommandCode.SAFARI_NOT_FRONTMOST | CommandCode.BRIDGE_TIMEOUT
              | CommandCode.SCRIPT_EXECUTION_BLOCKED | CommandCode.UNSUPPORTED_HOST | CommandCode.UNSUPPORTED_PAGE
              | CommandCode.TAB_CHANGED | CommandCode.INVALID_PAYLOAD | CommandCode.CORRUPT_CANONICAL | CommandCode.WRITE_FAILED):
            body = f"{result.code.value} — run doctor"
        case CommandCode.RUNTIME_TAMPERED:
            return result
        case unreachable:
            assert_never(unreachable)
    try:
        bridge.notify("Mnemosyne", body)
        return result
    except (ArtifactError, BridgeError):
        return StoreResult(result.command, result.code, result.ok, result.changed, result.document_key,
                           result.revision_id, result.path, tuple(sorted((*result.warnings, WarningCode.NOTIFICATION_FAILED))))


def _bridge_code(code: BridgeErrorCode) -> CommandCode:
    match code:
        case BridgeErrorCode.JAVASCRIPT_UNAVAILABLE:
            return CommandCode.JAVASCRIPT_DISABLED
        case BridgeErrorCode.NOTIFICATION_FAILED:
            raise AssertionError(code)
        case (BridgeErrorCode.NO_SAFARI_TAB | BridgeErrorCode.SAFARI_NOT_FRONTMOST | BridgeErrorCode.APPLE_EVENTS_DENIED
              | BridgeErrorCode.TAB_CHANGED | BridgeErrorCode.UNSUPPORTED_PAGE | BridgeErrorCode.BRIDGE_TIMEOUT
              | BridgeErrorCode.SCRIPT_EXECUTION_BLOCKED | BridgeErrorCode.INVALID_PAYLOAD):
            return CommandCode(code.value)
        case unreachable:
            assert_never(unreachable)


def _model_code(code: ModelErrorCode) -> CommandCode:
    match code:
        case ModelErrorCode.UNSUPPORTED_HOST:
            return CommandCode.UNSUPPORTED_HOST
        case ModelErrorCode.UNSUPPORTED_PAGE:
            return CommandCode.UNSUPPORTED_PAGE
        case ModelErrorCode.INVALID_PAYLOAD:
            return CommandCode.INVALID_PAYLOAD
        case unreachable:
            assert_never(unreachable)


def _runtime_artifacts(root: Path) -> tuple[Path, Path, str, str]:
    runtime = root / "runtime"
    releases = runtime / "releases"
    _private_directory(runtime)
    _private_directory(releases)
    current = runtime / "current"
    try:
        current_status = current.lstat()
        target = os.readlink(current)
    except OSError as error:
        raise RuntimeTamperedError from error
    if not stat.S_ISLNK(current_status.st_mode) or current_status.st_uid != os.getuid():
        raise RuntimeTamperedError
    matched = re.fullmatch(r"releases/([0-9a-f]{64})", target)
    if matched is None:
        raise RuntimeTamperedError
    release_id = matched.group(1)
    release = releases / release_id
    _private_directory(release)
    if set(os.listdir(release)) != {"mnemosyne.pyz", "capture.scpt", "extract-current-page.js", "manifest.json"}:
        raise RuntimeTamperedError
    raw_manifest = _private_file(release / "manifest.json")
    try:
        manifest = json.loads(raw_manifest.decode("utf-8", "strict"))
        canonical_manifest = _canonical(manifest)
    except (UnicodeDecodeError, ValueError) as error:
        raise RuntimeTamperedError from error
    if type(manifest) is not dict or raw_manifest != canonical_manifest:
        raise RuntimeTamperedError
    if set(manifest) != {"schema", "owner", "python_realpath", "artifacts", "workflow", "release_id"}:
        raise RuntimeTamperedError
    if (type(manifest["schema"]) is not str or type(manifest["owner"]) is not str
            or type(manifest["release_id"]) is not str or manifest["schema"] != _MANIFEST_SCHEMA
            or manifest["owner"] != _OWNER or manifest["release_id"] != release_id):
        raise RuntimeTamperedError
    unsigned = {key: value for key, value in manifest.items() if key != "release_id"}
    if hashlib.sha256(_RELEASE_PREFIX + _canonical(unsigned)).hexdigest() != release_id:
        raise RuntimeTamperedError
    artifacts = manifest["artifacts"]
    expected_names = {"mnemosyne.pyz", "capture.scpt", "extract-current-page.js"}
    if type(artifacts) is not dict or set(artifacts) != expected_names:
        raise RuntimeTamperedError
    for name in expected_names:
        descriptor = artifacts[name]
        if (type(descriptor) is not dict or set(descriptor) != {"mode", "sha256"}
                or type(descriptor["mode"]) is not str or descriptor["mode"] != "0600"
                or type(descriptor["sha256"]) is not str):
            raise RuntimeTamperedError
        content = _private_file(release / name)
        if _HEX.fullmatch(descriptor["sha256"]) is None or hashlib.sha256(content).hexdigest() != descriptor["sha256"]:
            raise RuntimeTamperedError
    workflow = manifest["workflow"]
    if type(workflow) is not dict or set(workflow) != {"document_sha256", "info_plist_sha256", "owner_marker_sha256", "path"}:
        raise RuntimeTamperedError
    workflow_hashes = ("document_sha256", "info_plist_sha256", "owner_marker_sha256")
    if any(type(workflow[name]) is not str or _HEX.fullmatch(workflow[name]) is None for name in workflow_hashes):
        raise RuntimeTamperedError
    if type(workflow["path"]) is not str or not Path(workflow["path"]).is_absolute() or _forbidden(workflow["path"]):
        raise RuntimeTamperedError
    python_realpath = manifest["python_realpath"]
    if (type(python_realpath) is not str or not Path(python_realpath).is_absolute()
            or python_realpath != os.path.realpath(sys.executable) or _forbidden(python_realpath)):
        raise RuntimeTamperedError
    _executable_file(Path(python_realpath))
    return (
        release / "capture.scpt",
        release / "extract-current-page.js",
        artifacts["capture.scpt"]["sha256"],
        artifacts["extract-current-page.js"]["sha256"],
    )


def _private_directory(path: Path) -> None:
    try:
        status = path.stat(follow_symlinks=False)
    except OSError as error:
        raise RuntimeTamperedError from error
    if not stat.S_ISDIR(status.st_mode) or status.st_uid != os.getuid() or stat.S_IMODE(status.st_mode) != 0o700:
        raise RuntimeTamperedError


def _private_file(path: Path) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            status = os.fstat(stream.fileno())
            content = stream.read()
    except OSError as error:
        raise RuntimeTamperedError from error
    if (
        not stat.S_ISREG(status.st_mode)
        or status.st_uid != os.getuid()
        or status.st_nlink != 1
        or stat.S_IMODE(status.st_mode) != 0o600
    ):
        raise RuntimeTamperedError
    return content


def _executable_file(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            status = os.fstat(stream.fileno())
    except OSError as error:
        raise RuntimeTamperedError from error
    if not stat.S_ISREG(status.st_mode) or status.st_uid != os.getuid() or status.st_nlink != 1 or status.st_mode & 0o111 == 0:
        raise RuntimeTamperedError


def _canonical(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _valid_root(root: Path) -> bool:
    return root.is_absolute() and root != Path("/") and not _forbidden(str(root))


def _forbidden(value: str) -> bool:
    return any(character in value for character in "\x00\r\n'")


def _failure(command: CommandName, code: CommandCode, changed: bool = False) -> StoreResult:
    return StoreResult(command, code, False, changed)


def _finish(result: StoreResult) -> int:
    value = {"schema": "mnemosyne.command/v1", "command": result.command.value, "code": result.code.value,
             "ok": result.ok, "changed": result.changed, "document_key": result.document_key,
             "revision_id": result.revision_id, "path": result.path,
             "warnings": sorted(warning.value for warning in result.warnings)}
    sys.stdout.write(_canonical(value).decode())
    return 2 if result.code is CommandCode.CAPTURED_EXPORT_STALE else 0 if result.ok else 1
