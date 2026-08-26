from __future__ import annotations

import fcntl
import json
import os
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, assert_never

from .bridge import ArtifactError, Bridge, BridgeError, BridgeErrorCode
from .install import ForeignWorkflowError, RuntimeTamperedError, _services_lock
from .install_artifacts import ArtifactTamperedError, OWNER, OWNER_BYTES, canonical, read_private, validate_manifest_release, validate_workflow_hashes, valid_prefix
from .install_paths import InstallPaths, InvalidPathError, revalidate_paths, sys_executable, sys_version
from .store import CaptureStore, StoreLockError, _Corrupt, canonical_record_bytes_from_mapping
from .url import CaptureModelError, parse_naver_url


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    status: str
    code: str


@dataclass(frozen=True, slots=True)
class DoctorResult:
    code: str
    ok: bool
    checks: tuple[DoctorCheck, ...]


def doctor(paths: InstallPaths, *, live: bool = False) -> DoctorResult:
    try:
        with _services_lock(paths.services, exclusive=False):
            revalidate_paths(paths)
            if paths.data_root.exists():
                entries = set(os.listdir(paths.data_root))
                if entries and ".commit.lock" not in entries:
                    raise StoreLockError(False)
                if ".commit.lock" in entries:
                    with _shared_store(paths) as store:
                        result = _evaluate(paths, store, live)
                        revalidate_paths(paths)
                        return result
            result = _evaluate(paths, None, live)
            if paths.data_root.exists() and ".commit.lock" in set(os.listdir(paths.data_root)):
                with _shared_store(paths) as store:
                    result = _evaluate(paths, store, live)
            revalidate_paths(paths)
            return result
    except InvalidPathError:
        return DoctorResult("INVALID_PATH", False, ())
    except (RuntimeTamperedError, ArtifactTamperedError, StoreLockError, _Corrupt, OSError):
        checks = (*_authority_failure(), *_lifecycle_checks("RUNTIME_TAMPERED", "RUNTIME_TAMPERED", None))
        if live:
            checks = (*checks, *_not_checked_live())
        return DoctorResult("NOT_READY", False, tuple(sorted(checks, key=lambda item: item.name.encode())))


def _evaluate(paths: InstallPaths, store: CaptureStore | None, live: bool) -> DoctorResult:
    authority = _authority_checks(paths, store)
    try:
        lifecycle, stable = _lifecycle(paths)
    except InvalidPathError:
        raise
    except ForeignWorkflowError:
        lifecycle = _lifecycle_checks("RUNTIME_MISSING", "FOREIGN_WORKFLOW", None)
        stable = None
    except (RuntimeTamperedError, ArtifactTamperedError, OSError):
        lifecycle = _lifecycle_checks("RUNTIME_TAMPERED", "RUNTIME_TAMPERED", None)
        stable = None
    checks = (*authority, *lifecycle, *(_live_checks(stable) if live else ()))
    ordered = tuple(sorted(checks, key=lambda item: item.name.encode()))
    ready = all(item.status == "PASS" for item in ordered)
    pending = any(item.status == "PENDING" for item in ordered)
    code = "READY" if ready else "LIVE_PREREQUISITE_MISSING" if pending and not any(
           item.status == "FAIL" for item in ordered) else "NOT_READY"
    return DoctorResult(code, ready, ordered)


def doctor_bytes(result: DoctorResult) -> bytes:
    return canonical({"schema": "mnemosyne.doctor/v1", "code": result.code, "ok": result.ok,
                      "checks": [{"name": item.name, "status": item.status, "code": item.code} for item in result.checks]})


@contextmanager
def _shared_store(paths: InstallPaths) -> Iterator[CaptureStore]:
    root_fd = os.open(paths.data_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    lock_fd = os.open(".commit.lock", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=root_fd)
    store = CaptureStore(paths.data_root)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_SH)
        store._validate_dir_fd(root_fd)
        store._validate_file_fd(lock_fd)
        store._root_fd = root_fd
        yield store
    finally:
        store._root_fd = None
        os.close(lock_fd)
        os.close(root_fd)


def _authority_checks(paths: InstallPaths, store: CaptureStore | None) -> tuple[DoctorCheck, DoctorCheck, DoctorCheck, DoctorCheck]:
    if store is None:
        return _authority_clean()
    bundles = store._scan()
    expected = b"".join(canonical_record_bytes_from_mapping({**item.record, "body": item.body})
                        for item in sorted(bundles, key=lambda item: (
                        item.record["document_key"], item.record["captured_at"], item.record["revision_id"])))
    export = paths.data_root / "posts.jsonl"
    actual = read_private(export) if export.exists() else None
    export_ok = actual == expected or not bundles and actual is None
    staging_clean = not store._stage_names()
    return (DoctorCheck("canonical", "PASS", "CANONICAL_OK"), DoctorCheck("data_modes", "PASS", "MODES_OK"),
            DoctorCheck("export", "PASS" if export_ok else "FAIL", "EXPORT_OK" if export_ok else "EXPORT_STALE"),
            DoctorCheck("staging", "PASS" if staging_clean else "FAIL", "STAGING_CLEAN" if staging_clean else "STALE_STAGING"))


def _authority_clean() -> tuple[DoctorCheck, DoctorCheck, DoctorCheck, DoctorCheck]:
    return (DoctorCheck("canonical", "PASS", "CANONICAL_OK"), DoctorCheck("data_modes", "PASS", "MODES_OK"),
            DoctorCheck("export", "PASS", "EXPORT_OK"), DoctorCheck("staging", "PASS", "STAGING_CLEAN"))


def _authority_failure() -> tuple[DoctorCheck, DoctorCheck, DoctorCheck, DoctorCheck]:
    return (DoctorCheck("canonical", "FAIL", "CORRUPT_CANONICAL"), DoctorCheck("data_modes", "FAIL", "MODES_INVALID"),
            DoctorCheck("export", "FAIL", "CORRUPT_CANONICAL"), DoctorCheck("staging", "FAIL", "STALE_STAGING"))


def _lifecycle_checks(runtime: str, workflow: str, python: DoctorCheck | None) -> tuple[DoctorCheck, DoctorCheck, DoctorCheck]:
    return (python or DoctorCheck("python", "FAIL", "PYTHON_EXPECTATION_UNAVAILABLE"),
            DoctorCheck("runtime", "FAIL", runtime), DoctorCheck("workflow", "FAIL", workflow))


def _lifecycle(paths: InstallPaths) -> tuple[tuple[DoctorCheck, DoctorCheck, DoctorCheck], tuple[Path, dict] | None]:
    runtime = paths.data_root / "runtime"
    plan = runtime / ".uninstall-plan.json"
    writing = runtime / ".uninstall-plan.json.writing"
    _validate_reserved_ownership(paths, uninstall_bound=plan.exists())
    _validate_runtime_namespace(runtime)
    witness = runtime / ".current.installing"
    stages = tuple(runtime.glob(".release-stage-*")) if runtime.exists() else ()
    if plan.exists() and writing.exists():
        raise RuntimeTamperedError
    if writing.exists():
        from .uninstall import _make_plan
        stable_for_plan = _runtime_release(paths)
        if stable_for_plan is None:
            raise RuntimeTamperedError
        validate_workflow_hashes(paths.workflow, stable_for_plan[1]["workflow"])
        expected = canonical(_make_plan(paths, stable_for_plan))
        if not valid_prefix(expected, read_private(writing)):
            raise RuntimeTamperedError
        return ((DoctorCheck("python", "FAIL", "PYTHON_EXPECTATION_UNAVAILABLE"),
                 DoctorCheck("runtime", "FAIL", "RUNTIME_INCOMPLETE"),
                 DoctorCheck("workflow", "PASS", "WORKFLOW_OK")), None)
    if plan.exists():
        from .uninstall import _load_plan, _validate_phase
        loaded = _load_plan(plan)
        _validate_phase(paths, loaded)
        workflow_code = "WORKFLOW_OK" if paths.workflow.exists() else "WORKFLOW_INCOMPLETE"
        workflow_status = "PASS" if workflow_code == "WORKFLOW_OK" else "FAIL"
        return ((DoctorCheck("python", "FAIL", "PYTHON_EXPECTATION_UNAVAILABLE"),
                 DoctorCheck("runtime", "FAIL", "RUNTIME_INCOMPLETE"),
                 DoctorCheck("workflow", workflow_status, workflow_code)), None)
    if witness.exists() or paths.workflow_stage.exists() or stages:
        _validate_install_residue(paths, stages)
        workflow_code = "WORKFLOW_OK" if paths.workflow.exists() else "WORKFLOW_INCOMPLETE"
        workflow_status = "PASS" if workflow_code == "WORKFLOW_OK" else "FAIL"
        return ((DoctorCheck("python", "FAIL", "PYTHON_EXPECTATION_UNAVAILABLE"),
                 DoctorCheck("runtime", "FAIL", "RUNTIME_INCOMPLETE"),
                 DoctorCheck("workflow", workflow_status, workflow_code)), None)
    stable = _runtime_release(paths)
    if stable is None:
        _validate_neutral_releases(runtime)
        workflow_code = "WORKFLOW_INCOMPLETE" if paths.workflow.exists() else "WORKFLOW_MISSING"
        return (_lifecycle_checks("RUNTIME_MISSING", workflow_code, None), None)
    workflow = stable[1]["workflow"]
    if not paths.workflow.exists():
        workflow_check = DoctorCheck("workflow", "FAIL", "WORKFLOW_MISSING")
    else:
        validate_workflow_hashes(paths.workflow, workflow)
        workflow_check = DoctorCheck("workflow", "PASS", "WORKFLOW_OK")
    return ((_python_check(stable[1]), DoctorCheck("runtime", "PASS", "RUNTIME_OK"), workflow_check), stable)


def _validate_reserved_ownership(paths: InstallPaths, *, uninstall_bound: bool) -> None:
    for workflow in (paths.workflow, paths.workflow_stage, paths.workflow_tombstone):
        if not workflow.exists():
            continue
        status = workflow.stat(follow_symlinks=False)
        if not stat.S_ISDIR(status.st_mode) or status.st_uid != os.getuid() or stat.S_IMODE(status.st_mode) != 0o700:
            raise ForeignWorkflowError
        marker = workflow / "Contents/Resources/mnemosyne-owner.json"
        if marker.exists():
            try:
                if read_private(marker) != OWNER_BYTES:
                    raise RuntimeTamperedError
            except ArtifactTamperedError as error:
                raise RuntimeTamperedError from error
        elif workflow == paths.workflow or (workflow == paths.workflow_tombstone and not uninstall_bound):
            raise ForeignWorkflowError


def _validate_runtime_namespace(runtime: Path) -> None:
    if not runtime.exists():
        return
    status = runtime.stat(follow_symlinks=False)
    if not stat.S_ISDIR(status.st_mode) or status.st_uid != os.getuid() or stat.S_IMODE(status.st_mode) != 0o700:
        raise RuntimeTamperedError
    allowed = {"releases", "current", ".current.installing", ".current.uninstalling",
               ".uninstall-plan.json", ".uninstall-plan.json.writing"}
    if any(name not in allowed and not name.startswith(".release-stage-") for name in os.listdir(runtime)):
        raise RuntimeTamperedError


def _validate_neutral_releases(runtime: Path) -> None:
    releases = runtime / "releases"
    if not releases.exists():
        return
    status = releases.stat(follow_symlinks=False)
    if not stat.S_ISDIR(status.st_mode) or stat.S_IMODE(status.st_mode) != 0o700:
        raise RuntimeTamperedError
    for release in releases.iterdir():
        raw = read_private(release / "manifest.json")
        manifest = json.loads(raw)
        if not isinstance(manifest, dict) or raw != canonical(manifest):
            raise RuntimeTamperedError
        validate_manifest_release(release, manifest)


def _validate_install_residue(paths: InstallPaths, stages: tuple[Path, ...]) -> None:
    runtime = paths.data_root / "runtime"
    witness = runtime / ".current.installing"
    if witness.exists():
        _release_from_link(paths, witness)
    if paths.workflow_stage.exists():
        target = _release_from_link(paths, witness if witness.exists() else runtime / "current")
        validate_workflow_hashes(paths.workflow_stage, target[1]["workflow"])
    for stage in stages:
        release_id = stage.name.removeprefix(".release-stage-")
        if len(release_id) != 64 or any(character not in "0123456789abcdef" for character in release_id):
            raise RuntimeTamperedError
        entries = set(os.listdir(stage))
        if entries not in (set(), {"owner.json"}):
            raise RuntimeTamperedError
        if entries:
            expected = canonical({"owner": OWNER, "release_id": release_id, "schema": "mnemosyne.release-stage/v1"})
            if read_private(stage / "owner.json") != expected:
                raise RuntimeTamperedError
        final = runtime / "releases" / release_id
        raw = read_private(final / "manifest.json")
        manifest = json.loads(raw)
        if not isinstance(manifest, dict):
            raise RuntimeTamperedError
        validate_manifest_release(final, manifest)


def _release_from_link(paths: InstallPaths, link: Path) -> tuple[Path, dict]:
    if not link.is_symlink():
        raise RuntimeTamperedError
    target = os.readlink(link)
    if not target.startswith("releases/") or "/" in target.removeprefix("releases/"):
        raise RuntimeTamperedError
    release = paths.data_root / "runtime" / target
    raw = read_private(release / "manifest.json")
    manifest = json.loads(raw)
    workflow = manifest.get("workflow") if isinstance(manifest, dict) else None
    if not isinstance(workflow, dict) or workflow.get("path") != str(paths.workflow):
        raise InvalidPathError
    validate_manifest_release(release, manifest)
    return release, manifest


def _runtime_release(paths: InstallPaths) -> tuple[Path, dict] | None:
    current = paths.data_root / "runtime/current"
    if not current.is_symlink():
        return None
    return _release_from_link(paths, current)


def _python_check(manifest: dict) -> DoctorCheck:
    expected = manifest.get("python_realpath")
    if not isinstance(expected, str) or not Path(expected).exists():
        return DoctorCheck("python", "FAIL", "PYTHON_MISSING")
    try:
        status = os.stat(expected, follow_symlinks=False)
    except OSError:
        return DoctorCheck("python", "FAIL", "PYTHON_CHANGED")
    if expected != sys_executable() or status.st_nlink != 1 or status.st_mode & 0o111 == 0:
        return DoctorCheck("python", "FAIL", "PYTHON_CHANGED")
    return DoctorCheck("python", "PASS" if sys_version() == (3, 14) else "FAIL",
                       "PYTHON_OK" if sys_version() == (3, 14) else "PYTHON_VERSION_MISMATCH")


def _live_checks(stable: tuple[Path, dict] | None) -> tuple[DoctorCheck, DoctorCheck, DoctorCheck]:
    if stable is None:
        return _not_checked_live()
    release, manifest = stable
    artifacts = manifest["artifacts"]
    try:
        bridge = Bridge.bind(release / "capture.scpt", release / "extract-current-page.js",
                             expected_capture_sha256=artifacts["capture.scpt"]["sha256"],
                             expected_extractor_sha256=artifacts["extract-current-page.js"]["sha256"])
        try:
            snapshot = bridge.snapshot()
        except BridgeError as error:
            return _snapshot_error(error.code)
        try:
            parse_naver_url(snapshot.url)
        except CaptureModelError:
            return (DoctorCheck("apple_events", "PASS", "APPLE_EVENTS_OK"),
                    DoctorCheck("javascript", "PENDING", "JAVASCRIPT_NOT_CHECKED"),
                    DoctorCheck("safari_tab", "PENDING", "UNSUPPORTED_HOST"))
        try:
            bridge.smoke(snapshot.url)
        except BridgeError as error:
            return _smoke_error(error.code)
        return (DoctorCheck("apple_events", "PASS", "APPLE_EVENTS_OK"),
                DoctorCheck("javascript", "PASS", "JAVASCRIPT_OK"), DoctorCheck("safari_tab", "PASS", "SAFARI_READY"))
    except ArtifactError:
        return (DoctorCheck("apple_events", "FAIL", "SCRIPT_EXECUTION_BLOCKED"),
                DoctorCheck("javascript", "PENDING", "JAVASCRIPT_NOT_CHECKED"),
                DoctorCheck("safari_tab", "PENDING", "SAFARI_TAB_NOT_CHECKED"))


def _snapshot_error(code: BridgeErrorCode) -> tuple[DoctorCheck, DoctorCheck, DoctorCheck]:
    match code:
        case BridgeErrorCode.APPLE_EVENTS_DENIED:
            return (DoctorCheck("apple_events", "PENDING", "APPLE_EVENTS_DENIED"),
                    DoctorCheck("javascript", "PENDING", "JAVASCRIPT_NOT_CHECKED"),
                    DoctorCheck("safari_tab", "PENDING", "SAFARI_TAB_NOT_CHECKED"))
        case BridgeErrorCode.NO_SAFARI_TAB | BridgeErrorCode.SAFARI_NOT_FRONTMOST:
            return (DoctorCheck("apple_events", "PASS", "APPLE_EVENTS_OK"),
                    DoctorCheck("javascript", "PENDING", "JAVASCRIPT_NOT_CHECKED"),
                    DoctorCheck("safari_tab", "PENDING", code.value))
        case BridgeErrorCode.BRIDGE_TIMEOUT:
            failure = "BRIDGE_TIMEOUT"
        case BridgeErrorCode.SCRIPT_EXECUTION_BLOCKED:
            failure = "SCRIPT_EXECUTION_BLOCKED"
        case (BridgeErrorCode.JAVASCRIPT_UNAVAILABLE | BridgeErrorCode.TAB_CHANGED | BridgeErrorCode.UNSUPPORTED_PAGE
              | BridgeErrorCode.INVALID_PAYLOAD | BridgeErrorCode.NOTIFICATION_FAILED):
            failure = "SCRIPT_EXECUTION_BLOCKED"
        case unreachable:
            assert_never(unreachable)
    return (DoctorCheck("apple_events", "FAIL", failure),
            DoctorCheck("javascript", "PENDING", "JAVASCRIPT_NOT_CHECKED"),
            DoctorCheck("safari_tab", "PENDING", "SAFARI_TAB_NOT_CHECKED"))


def _smoke_error(code: BridgeErrorCode) -> tuple[DoctorCheck, DoctorCheck, DoctorCheck]:
    if code is BridgeErrorCode.APPLE_EVENTS_DENIED:
        return _snapshot_error(code)
    if code in (BridgeErrorCode.NO_SAFARI_TAB, BridgeErrorCode.SAFARI_NOT_FRONTMOST):
        return _snapshot_error(code)
    if code is BridgeErrorCode.JAVASCRIPT_UNAVAILABLE:
        return (DoctorCheck("apple_events", "PASS", "APPLE_EVENTS_OK"),
                DoctorCheck("javascript", "PENDING", "JAVASCRIPT_DISABLED"),
                DoctorCheck("safari_tab", "PASS", "SAFARI_READY"))
    if code is BridgeErrorCode.TAB_CHANGED:
        return (DoctorCheck("apple_events", "PASS", "APPLE_EVENTS_OK"),
                DoctorCheck("javascript", "PENDING", "JAVASCRIPT_NOT_CHECKED"),
                DoctorCheck("safari_tab", "PENDING", "TAB_CHANGED"))
    failure = "BRIDGE_TIMEOUT" if code is BridgeErrorCode.BRIDGE_TIMEOUT else "SCRIPT_EXECUTION_BLOCKED"
    return (DoctorCheck("apple_events", "PASS", "APPLE_EVENTS_OK"),
            DoctorCheck("javascript", "FAIL", failure), DoctorCheck("safari_tab", "PASS", "SAFARI_READY"))


def _not_checked_live() -> tuple[DoctorCheck, DoctorCheck, DoctorCheck]:
    return (DoctorCheck("apple_events", "PENDING", "APPLE_EVENTS_NOT_CHECKED"),
            DoctorCheck("javascript", "PENDING", "JAVASCRIPT_NOT_CHECKED"),
            DoctorCheck("safari_tab", "PENDING", "SAFARI_TAB_NOT_CHECKED"))
