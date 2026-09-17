from __future__ import annotations

import hashlib
import json
import os
import plistlib
import stat
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Final

from .install_paths import InstallPaths, sys_executable


OWNER: Final = "github.com/99duuk/mnemosyne#mnemosyne-capture/v1"
OWNER_BYTES: Final = b'{"owner":"github.com/99duuk/mnemosyne#mnemosyne-capture/v1","schema":"mnemosyne.workflow-owner/v1"}\n'
RELEASE_PREFIX: Final = b"mnemosyne.runtime.release/v1\n"


@dataclass(frozen=True, slots=True)
class BuiltRelease:
    release_id: str
    files: tuple[tuple[str, bytes], ...]
    manifest: bytes
    document: bytes
    info: bytes


class ArtifactTamperedError(Exception):
    pass


def build_release(paths: InstallPaths) -> BuiltRelease:
    command = f"'{sys_executable()}' '{paths.data_root}/runtime/current/mnemosyne.pyz' --data-root '{paths.data_root}' capture"
    document = plistlib.dumps(workflow_plist(command), fmt=plistlib.FMT_XML, sort_keys=True)
    info = plistlib.dumps(info_plist(), fmt=plistlib.FMT_XML, sort_keys=True)
    pyz = _zipapp_bytes()
    source_root = Path(__file__).resolve().parents[1]
    extractor = (source_root / "extract-current-page.js").read_bytes()
    with tempfile.TemporaryDirectory(prefix="mnemosyne-osacompile-") as directory:
        compiled = Path(directory) / "capture.scpt"
        try:
            subprocess.run(["/usr/bin/osacompile", "-o", str(compiled), str(source_root / "macos/capture.applescript")],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except subprocess.SubprocessError as error:
            raise OSError from error
        capture = compiled.read_bytes()
    files = (("mnemosyne.pyz", pyz), ("extract-current-page.js", extractor), ("capture.scpt", capture))
    artifacts = {name: {"mode": "0600", "sha256": hashlib.sha256(content).hexdigest()} for name, content in files}
    unsigned = {"schema": "mnemosyne.runtime-manifest/v1", "owner": OWNER, "python_realpath": sys_executable(),
                "artifacts": artifacts, "workflow": {"document_sha256": hashlib.sha256(document).hexdigest(),
                "info_plist_sha256": hashlib.sha256(info).hexdigest(),
                "owner_marker_sha256": hashlib.sha256(OWNER_BYTES).hexdigest(), "path": str(paths.workflow)}}
    release_id = hashlib.sha256(RELEASE_PREFIX + canonical(unsigned)).hexdigest()
    return BuiltRelease(release_id, files, canonical({**unsigned, "release_id": release_id}), document, info)


def publish_release(runtime: Path, releases: Path, final: Path, built: BuiltRelease,
                    guard: Callable[[], None] = lambda: None) -> None:
    guard()
    stage = runtime / f".release-stage-{built.release_id}"
    owner = canonical({"owner": OWNER, "release_id": built.release_id, "schema": "mnemosyne.release-stage/v1"})
    _mkdir_or_validate(stage)
    guard()
    _resume_file(stage / "owner.json", owner)
    guard()
    bundle = stage / "release"
    _mkdir_or_validate(bundle)
    expected = dict((*built.files, ("manifest.json", built.manifest)))
    _validate_stage_entries(bundle, expected)
    for name, content in (*built.files, ("manifest.json", built.manifest)):
        guard()
        _resume_file(bundle / name, content)
    sync(bundle)
    guard()
    bundle.rename(final)
    sync(releases)
    (stage / "owner.json").unlink()
    sync(stage)
    stage.rmdir()
    sync(runtime)


def cleanup_published_release(runtime: Path, releases: Path, final: Path, built: BuiltRelease,
                              guard: Callable[[], None] = lambda: None) -> None:
    guard()
    validate_release(final, built)
    stage = runtime / f".release-stage-{built.release_id}"
    if not stage.exists():
        sync(releases)
        return
    _mkdir_or_validate(stage)
    entries = set(os.listdir(stage))
    if entries == {"owner.json"}:
        owner = canonical({"owner": OWNER, "release_id": built.release_id, "schema": "mnemosyne.release-stage/v1"})
        if read_private(stage / "owner.json") != owner:
            raise ArtifactTamperedError
        (stage / "owner.json").unlink()
        sync(stage)
    elif entries:
        raise ArtifactTamperedError
    sync(releases)
    stage.rmdir()
    sync(runtime)


def publish_workflow_stage(stage: Path, built: BuiltRelease,
                           guard: Callable[[], None] = lambda: None) -> None:
    guard()
    _mkdir_or_validate(stage)
    contents = stage / "Contents"
    resources = contents / "Resources"
    _mkdir_or_validate(contents)
    guard()
    _mkdir_or_validate(resources)
    _validate_stage_entries(contents, {"Info.plist": built.info}, {"Resources"})
    _validate_stage_entries(resources, {"document.wflow": built.document, "mnemosyne-owner.json": OWNER_BYTES})
    for path, content in ((resources / "document.wflow", built.document),
                          (contents / "Info.plist", built.info),
                          (resources / "mnemosyne-owner.json", OWNER_BYTES)):
        guard()
        _resume_file(path, content)
    sync(resources)
    sync(contents)
    sync(stage)


def validate_release(release: Path, built: BuiltRelease) -> None:
    if set(os.listdir(release)) != {"mnemosyne.pyz", "extract-current-page.js", "capture.scpt", "manifest.json"}:
        raise ArtifactTamperedError
    for name, content in (*built.files, ("manifest.json", built.manifest)):
        if read_private(release / name) != content:
            raise ArtifactTamperedError


def validate_manifest_release(release: Path, manifest: dict) -> None:
    status = release.stat(follow_symlinks=False)
    if (not stat.S_ISDIR(status.st_mode) or status.st_uid != os.getuid()
            or stat.S_IMODE(status.st_mode) != 0o700
            or set(os.listdir(release)) != {"mnemosyne.pyz", "extract-current-page.js", "capture.scpt", "manifest.json"}):
        raise ArtifactTamperedError
    if set(manifest) != {"schema", "owner", "python_realpath", "artifacts", "workflow", "release_id"}:
        raise ArtifactTamperedError
    unsigned = {name: value for name, value in manifest.items() if name != "release_id"}
    release_id = hashlib.sha256(RELEASE_PREFIX + canonical(unsigned)).hexdigest()
    if (manifest.get("schema") != "mnemosyne.runtime-manifest/v1" or manifest.get("owner") != OWNER
            or manifest.get("release_id") != release.name or release_id != release.name):
        raise ArtifactTamperedError
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {"mnemosyne.pyz", "extract-current-page.js", "capture.scpt"}:
        raise ArtifactTamperedError
    for name, descriptor in artifacts.items():
        if not isinstance(descriptor, dict) or descriptor.get("mode") != "0600":
            raise ArtifactTamperedError
        if hashlib.sha256(read_private(release / name)).hexdigest() != descriptor.get("sha256"):
            raise ArtifactTamperedError


def validate_workflow(workflow: Path, built: BuiltRelease) -> None:
    validate_workflow_hashes(workflow, {"document_sha256": hashlib.sha256(built.document).hexdigest(),
                                      "info_plist_sha256": hashlib.sha256(built.info).hexdigest(),
                                      "owner_marker_sha256": hashlib.sha256(OWNER_BYTES).hexdigest()})


def validate_legacy_workflow(workflow: Path, built: BuiltRelease) -> None:
    validate_legacy_workflow_hashes(workflow, {"document_sha256": hashlib.sha256(built.document).hexdigest(),
                                             "info_plist_sha256": hashlib.sha256(built.info).hexdigest(),
                                             "owner_marker_sha256": hashlib.sha256(OWNER_BYTES).hexdigest()})


def validate_workflow_hashes(workflow: Path, hashes: dict) -> None:
    if not workflow.exists():
        raise ArtifactTamperedError
    for directory, entries in ((workflow, {"Contents"}), (workflow / "Contents", {"Info.plist", "Resources"}),
                               (workflow / "Contents/Resources", {"document.wflow", "mnemosyne-owner.json"})):
        status = directory.stat(follow_symlinks=False)
        if (not stat.S_ISDIR(status.st_mode) or status.st_uid != os.getuid()
                or stat.S_IMODE(status.st_mode) != 0o700 or set(os.listdir(directory)) != entries):
            raise ArtifactTamperedError
    expected = {"Contents/Resources/document.wflow": "document_sha256", "Contents/Info.plist": "info_plist_sha256",
                "Contents/Resources/mnemosyne-owner.json": "owner_marker_sha256"}
    for relative, field in expected.items():
        if hashlib.sha256(read_private(workflow / relative)).hexdigest() != hashes.get(field):
            raise ArtifactTamperedError


def validate_legacy_workflow_hashes(workflow: Path, hashes: dict) -> None:
    if not workflow.exists():
        raise ArtifactTamperedError
    for directory, entries in ((workflow, {"Contents"}),
                               (workflow / "Contents", {"document.wflow", "Info.plist", "Resources"}),
                               (workflow / "Contents/Resources", {"mnemosyne-owner.json"})):
        status = directory.stat(follow_symlinks=False)
        if (not stat.S_ISDIR(status.st_mode) or status.st_uid != os.getuid()
                or stat.S_IMODE(status.st_mode) != 0o700 or set(os.listdir(directory)) != entries):
            raise ArtifactTamperedError
    expected = {"Contents/document.wflow": "document_sha256", "Contents/Info.plist": "info_plist_sha256",
                "Contents/Resources/mnemosyne-owner.json": "owner_marker_sha256"}
    for relative, field in expected.items():
        if hashlib.sha256(read_private(workflow / relative)).hexdigest() != hashes.get(field):
            raise ArtifactTamperedError


def workflow_plist(command: str) -> dict:
    return {"AMApplicationBuild": "523", "AMApplicationVersion": "2.10", "AMDocumentVersion": "2",
            "actions": [{"action": {"AMAccepts": {"Container": "List", "Optional": True,
            "Types": ["com.apple.Automator.nothing"]}, "AMActionVersion": "2.0.3", "AMApplication": ["Automator"],
            "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action", "ActionName": "Run Shell Script",
            "ActionParameters": {"COMMAND_STRING": command, "CheckedForUserDefaultShell": True,
            "inputMethod": 1, "shell": "/bin/zsh"}}}], "workflowMetaData": {
            "serviceApplicationBundleID": "com.google.Chrome", "serviceInputTypeIdentifier": "com.apple.Automator.nothing",
            "serviceOutputTypeIdentifier": "com.apple.Automator.nothing", "serviceProcessesInput": 0,
            "workflowTypeIdentifier": "com.apple.Automator.servicesMenu"}}


def info_plist() -> dict:
    return {"CFBundleDevelopmentRegion": "en_US", "CFBundleIdentifier": "com.99duuk.mnemosyne.capture",
            "CFBundleName": "Mnemosyne Capture", "CFBundleShortVersionString": "1.0",
            "NSServices": [{"NSMenuItem": {"default": "Mnemosyne Capture"}, "NSMessage": "runWorkflowAsService"}]}


def canonical(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def read_private(path: Path) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        status = os.fstat(stream.fileno())
        content = stream.read()
    if not stat.S_ISREG(status.st_mode) or status.st_uid != os.getuid() or status.st_nlink != 1 or stat.S_IMODE(status.st_mode) != 0o600:
        raise ArtifactTamperedError
    return content


def write_private(path: Path, content: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        os.fchmod(stream.fileno(), 0o600)
        stream.flush()
        os.fsync(stream.fileno())
    sync(path.parent)


def _resume_file(path: Path, content: bytes) -> None:
    writing = path.with_name(f"{path.name}.writing")
    if path.exists():
        if writing.exists():
            raise ArtifactTamperedError
        if read_private(path) != content:
            raise ArtifactTamperedError
        return
    if writing.exists():
        if not valid_prefix(content, read_private(writing)):
            raise ArtifactTamperedError
        descriptor = os.open(writing, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            os.fchmod(stream.fileno(), 0o600)
            stream.flush()
            os.fsync(stream.fileno())
    else:
        write_private(writing, content)
    os.replace(writing, path)
    sync(path.parent)


def _mkdir_or_validate(path: Path) -> None:
    try:
        path.mkdir(mode=0o700)
        sync(path.parent)
    except FileExistsError:
        status = path.stat(follow_symlinks=False)
        if (not stat.S_ISDIR(status.st_mode) or status.st_uid != os.getuid()
                or stat.S_IMODE(status.st_mode) != 0o700):
            raise ArtifactTamperedError


def _validate_stage_entries(directory: Path, expected: dict[str, bytes], extra: set[str] | None = None) -> None:
    allowed = set(expected) | {f"{name}.writing" for name in expected} | (extra or set())
    entries = set(os.listdir(directory))
    if not entries <= allowed or sum(name.endswith(".writing") for name in entries) > 1:
        raise ArtifactTamperedError
    for name, content in expected.items():
        final = directory / name
        writing = directory / f"{name}.writing"
        if final.exists() and writing.exists():
            raise ArtifactTamperedError
        if final.exists() and read_private(final) != content:
            raise ArtifactTamperedError
        if writing.exists() and not valid_prefix(content, read_private(writing)):
            raise ArtifactTamperedError


def valid_prefix(trusted: bytes, candidate: bytes) -> bool:
    return len(candidate) <= len(trusted) and trusted[:len(candidate)] == candidate


def sync(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _zipapp_bytes() -> bytes:
    package = Path(__file__).resolve().parent
    with tempfile.NamedTemporaryFile(prefix="mnemosyne-", suffix=".pyz") as stream:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            _zip_write(archive, "__main__.py", b"from mnemosyne_capture.cli import main\nraise SystemExit(main())\n")
            for source in sorted(package.glob("*.py"), key=lambda path: path.name.encode()):
                _zip_write(archive, f"mnemosyne_capture/{source.name}", source.read_bytes())
        stream.seek(0)
        return stream.read()


def _zip_write(archive: zipfile.ZipFile, name: str, content: bytes) -> None:
    info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
    info.external_attr = 0o600 << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, content)
