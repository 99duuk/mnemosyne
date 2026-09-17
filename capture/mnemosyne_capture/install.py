from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Final, Iterator

from .enums import CommandCode, CommandName
from .install_artifacts import (
    ArtifactTamperedError,
    BuiltRelease,
    build_release,
    canonical,
    cleanup_published_release,
    publish_release,
    publish_workflow_stage,
    read_private,
    sync,
    validate_manifest_release,
    validate_legacy_workflow_hashes,
    validate_release,
    validate_workflow,
    validate_workflow_hashes,
    valid_prefix,
    write_private,
)
from .install_paths import InstallPaths, InvalidPathError, bind_paths, private_directory, revalidate_paths, sys_version
from .store import CaptureStore, StoreLockError, StoreResult


DIR_MODE: Final = 0o700


class ForeignWorkflowError(Exception):
    pass


class RuntimeTamperedError(Exception):
    pass


class PathDriftError(Exception):
    def __init__(self, changed: bool) -> None:
        self.changed = changed


class InstallMutationError(OSError):
    pass


def install(paths: InstallPaths) -> StoreResult:
    command = CommandName.INSTALL
    if sys_version() != (3, 14):
        return StoreResult(command, CommandCode.PYTHON_VERSION_MISMATCH, False, False)
    try:
        built = build_release(paths)
        baseline = _install_signature(paths, built)
        coordination_existed = paths.data_root.exists() and (paths.data_root / ".commit.lock").exists()
        with _services_lock(paths.services, exclusive=True):
            revalidate_paths(paths)
            reserved = any(path.exists() or path.is_symlink() for path in
                           (paths.workflow, paths.workflow_stage, paths.workflow_tombstone))
            lock = paths.data_root / ".commit.lock"
            if reserved and (not paths.data_root.exists() or (not lock.exists() and not any(paths.data_root.iterdir()))):
                raise ForeignWorkflowError
            with CaptureStore(paths.data_root).locked(create=True):
                result = _install_locked(paths, built, coordination_changed=not coordination_existed)
        if result.ok and paths.home == Path.home():
            subprocess.run(["/System/Library/CoreServices/pbs", "-update"], check=True, timeout=10,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return result
    except InvalidPathError:
        return StoreResult(command, CommandCode.INVALID_PATH, False, False)
    except PathDriftError as error:
        return StoreResult(command, CommandCode.WRITE_FAILED if error.changed else CommandCode.INVALID_PATH,
                           False, error.changed)
    except InstallMutationError:
        return StoreResult(command, CommandCode.WRITE_FAILED, False, True)
    except ForeignWorkflowError:
        return StoreResult(command, CommandCode.FOREIGN_WORKFLOW, False, False)
    except (RuntimeTamperedError, ArtifactTamperedError):
        return StoreResult(command, CommandCode.RUNTIME_TAMPERED, False, False)
    except StoreLockError as error:
        return StoreResult(command, CommandCode.WRITE_FAILED, False, error.changed)
    except (OSError, subprocess.SubprocessError):
        return StoreResult(command, CommandCode.WRITE_FAILED, False,
                           'built' in locals() and _install_signature(paths, built) != baseline)


def _install_locked(paths: InstallPaths, built: BuiltRelease, *, coordination_changed: bool) -> StoreResult:
    _require_paths(paths, coordination_changed)
    runtime = paths.data_root / "runtime"
    _check_invocation_binding(paths, runtime)
    releases = runtime / "releases"
    _mkdir_private(runtime, lambda: _require_paths(paths, coordination_changed))
    _mkdir_private(releases, lambda: _require_paths(paths, runtime.exists()))
    final_plan = runtime / ".uninstall-plan.json"
    writing_plan = runtime / ".uninstall-plan.json.writing"
    if final_plan.exists() and writing_plan.exists():
        raise RuntimeTamperedError
    if writing_plan.exists():
        from .uninstall import _make_plan
        stable_for_plan = _stable_release(paths)
        if stable_for_plan is None or not valid_prefix(canonical(_make_plan(paths, stable_for_plan)), read_private(writing_plan)):
            raise RuntimeTamperedError
        return StoreResult(CommandName.INSTALL, CommandCode.UNINSTALL_IN_PROGRESS, False, False)
    if final_plan.exists():
        from .uninstall import _load_plan, _validate_phase
        _validate_phase(paths, _load_plan(final_plan))
        return StoreResult(CommandName.INSTALL, CommandCode.UNINSTALL_IN_PROGRESS, False, False)
    current = runtime / "current"
    witness = runtime / ".current.installing"
    final_release = releases / built.release_id
    target = f"releases/{built.release_id}"
    if current.is_symlink() and os.readlink(current) == target and final_release.exists() and not witness.exists():
        had_release_stage = (runtime / f".release-stage-{built.release_id}").exists()
        cleanup_published_release(runtime, releases, final_release, built, lambda: _require_paths(paths, had_release_stage))
        _require_paths(paths, had_release_stage)
        if paths.workflow_stage.exists() and not paths.workflow.exists():
            publish_workflow_stage(paths.workflow_stage, built, lambda: _require_paths(paths, True))
            paths.workflow_stage.rename(paths.workflow)
            sync(paths.services)
            _require_paths(paths, True)
            return StoreResult(CommandName.INSTALL, CommandCode.INSTALLED, True, True, path=str(paths.workflow))
        stable = _stable_release(paths, allow_legacy_workflow=True)
        if stable is None:
            raise RuntimeTamperedError
        layout_changed = _repair_legacy_workflow_layout(paths, stable[1]["workflow"])
        return StoreResult(CommandName.INSTALL, CommandCode.INSTALLED, True, had_release_stage or layout_changed,
                           path=str(paths.workflow))
    if witness.is_symlink() and os.readlink(witness) == target and final_release.exists():
        cleanup_published_release(runtime, releases, final_release, built, lambda: _require_paths(paths, False))
        _require_paths(paths, False)
        if paths.workflow.exists():
            _finish_workflow_update(paths, built, target)
            return StoreResult(CommandName.INSTALL, CommandCode.INSTALLED, True, True, path=str(paths.workflow))
        if paths.workflow_stage.exists():
            publish_workflow_stage(paths.workflow_stage, built, lambda: _require_paths(paths, True))
        else:
            publish_workflow_stage(paths.workflow_stage, built)
        os.replace(witness, current)
        sync(runtime)
        _require_paths(paths, True)
        paths.workflow_stage.rename(paths.workflow)
        sync(paths.services)
        _require_paths(paths, True)
        return StoreResult(CommandName.INSTALL, CommandCode.INSTALLED, True, True, path=str(paths.workflow))
    if current.is_symlink() and paths.workflow.exists() and not witness.exists():
        stable = _stable_release(paths, allow_legacy_workflow=True)
        if stable is None:
            raise RuntimeTamperedError
        layout_changed = _repair_legacy_workflow_layout(paths, stable[1]["workflow"])
        try:
            if final_release.exists():
                cleanup_published_release(runtime, releases, final_release, built,
                                          lambda: _require_paths(paths, layout_changed))
            else:
                publish_release(runtime, releases, final_release, built, lambda: _require_paths(paths, True))
            witness.symlink_to(target)
            sync(runtime)
            _require_paths(paths, True)
            _finish_workflow_update(paths, built, target)
        except (ArtifactTamperedError, OSError) as error:
            if layout_changed:
                raise InstallMutationError from error
            raise
        return StoreResult(CommandName.INSTALL, CommandCode.INSTALLED, True, True, path=str(paths.workflow))
    if current.exists() or current.is_symlink() or paths.workflow.exists():
        raise RuntimeTamperedError
    changed = False
    try:
        if final_release.exists():
            cleanup_published_release(runtime, releases, final_release, built, lambda: _require_paths(paths, changed))
        else:
            publish_release(runtime, releases, final_release, built, lambda: _require_paths(paths, True))
            changed = True
        witness.symlink_to(target)
        sync(runtime)
        changed = True
        _require_paths(paths, True)
        publish_workflow_stage(paths.workflow_stage, built, lambda: _require_paths(paths, True))
        _require_paths(paths, True)
        os.replace(witness, current)
        sync(runtime)
        _require_paths(paths, True)
        paths.workflow_stage.rename(paths.workflow)
        sync(paths.services)
        _require_paths(paths, True)
        return StoreResult(CommandName.INSTALL, CommandCode.INSTALLED, True, True, path=str(paths.workflow))
    except OSError:
        residue = (runtime / f".release-stage-{built.release_id}").exists() or witness.exists() \
                  or paths.workflow_stage.exists() or final_release.exists()
        return StoreResult(CommandName.INSTALL, CommandCode.WRITE_FAILED, False, changed or residue)


def _require_paths(paths: InstallPaths, changed: bool) -> None:
    try:
        revalidate_paths(paths)
    except (InvalidPathError, OSError) as error:
        raise PathDriftError(changed) from error


def _repair_legacy_workflow_layout(paths: InstallPaths, workflow: dict) -> bool:
    try:
        validate_workflow_hashes(paths.workflow, workflow)
        return False
    except ArtifactTamperedError:
        validate_legacy_workflow_hashes(paths.workflow, workflow)
    _require_paths(paths, False)
    source = paths.workflow / "Contents/document.wflow"
    target = paths.workflow / "Contents/Resources/document.wflow"
    source.rename(target)
    try:
        sync(target.parent)
        sync(source.parent)
        _require_paths(paths, True)
        validate_workflow_hashes(paths.workflow, workflow)
    except (ArtifactTamperedError, OSError) as error:
        raise InstallMutationError from error
    return True


def _finish_workflow_update(paths: InstallPaths, built: BuiltRelease, target: str) -> None:
    runtime = paths.data_root / "runtime"
    current = runtime / "current"
    witness = runtime / ".current.installing"
    if current.is_symlink():
        if os.readlink(current) != target:
            _stable_release(paths, allow_legacy_workflow=True, pending_document=built)
        else:
            validate_workflow(paths.workflow, built)
    elif current.exists() and not current.is_symlink():
        raise RuntimeTamperedError
    document = paths.workflow / "Contents/Resources/document.wflow"
    writing = document.with_name(f"{document.name}.writing")
    if read_private(document) != built.document:
        if writing.exists() and not valid_prefix(built.document, read_private(writing)):
            raise ArtifactTamperedError
        if not writing.exists():
            write_private(writing, built.document)
        os.replace(writing, document)
        sync(document.parent)
    elif writing.exists():
        raise ArtifactTamperedError
    validate_workflow(paths.workflow, built)
    os.replace(witness, current)
    sync(runtime)
    _require_paths(paths, True)


def _stable_release(paths: InstallPaths, *, allow_legacy_workflow: bool = False,
                    pending_document: BuiltRelease | None = None) -> tuple[Path, dict] | None:
    current = paths.data_root / "runtime/current"
    if not current.is_symlink():
        _reject_clean_reserved(paths)
        return None
    target = os.readlink(current)
    if not target.startswith("releases/") or "/" in target.removeprefix("releases/"):
        raise RuntimeTamperedError
    release = paths.data_root / "runtime" / target
    if not stat.S_ISDIR(release.stat(follow_symlinks=False).st_mode):
        raise RuntimeTamperedError
    raw = read_private(release / "manifest.json")
    try:
        manifest = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RuntimeTamperedError from error
    if not isinstance(manifest, dict) or raw != canonical(manifest):
        raise RuntimeTamperedError
    workflow = manifest.get("workflow")
    if not isinstance(workflow, dict) or workflow.get("path") != str(paths.workflow):
        raise InvalidPathError
    validate_manifest_release(release, manifest)
    try:
        validate_workflow_hashes(paths.workflow, workflow)
    except ArtifactTamperedError:
        if pending_document is not None:
            _validate_pending_workflow_document(paths, workflow, pending_document)
        elif not allow_legacy_workflow:
            raise
        else:
            validate_legacy_workflow_hashes(paths.workflow, workflow)
    return release, manifest


def _validate_pending_workflow_document(paths: InstallPaths, workflow: dict, built: BuiltRelease) -> None:
    resources = paths.workflow / "Contents/Resources"
    document = resources / "document.wflow"
    writing = resources / "document.wflow.writing"
    old_document = read_private(document)
    if old_document == built.document:
        if writing.exists():
            raise ArtifactTamperedError
        resource_entries = {"document.wflow", "mnemosyne-owner.json"}
    elif (hashlib.sha256(old_document).hexdigest() == workflow.get("document_sha256")
          and writing.exists() and valid_prefix(built.document, read_private(writing))):
        resource_entries = {"document.wflow", "document.wflow.writing", "mnemosyne-owner.json"}
    else:
        raise ArtifactTamperedError
    for directory, entries in ((paths.workflow, {"Contents"}),
                               (paths.workflow / "Contents", {"Info.plist", "Resources"}),
                               (resources, resource_entries)):
        status = directory.stat(follow_symlinks=False)
        if (not stat.S_ISDIR(status.st_mode) or status.st_uid != os.getuid()
                or stat.S_IMODE(status.st_mode) != 0o700 or set(os.listdir(directory)) != entries):
            raise ArtifactTamperedError
    for relative, field in (("Contents/Info.plist", "info_plist_sha256"),
                            ("Contents/Resources/mnemosyne-owner.json", "owner_marker_sha256")):
        if hashlib.sha256(read_private(paths.workflow / relative)).hexdigest() != workflow.get(field):
            raise ArtifactTamperedError


def _reject_clean_reserved(paths: InstallPaths) -> None:
    if paths.workflow_stage.exists() or paths.workflow_tombstone.exists():
        raise ForeignWorkflowError
    if paths.workflow.exists():
        status = paths.workflow.stat(follow_symlinks=False)
        if not stat.S_ISDIR(status.st_mode) or not (paths.workflow / "Contents/Resources/mnemosyne-owner.json").exists():
            raise ForeignWorkflowError


@contextmanager
def _services_lock(path: Path, *, exclusive: bool) -> Iterator[None]:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield
    finally:
        os.close(descriptor)


def _mkdir_private(path: Path, guard: Callable[[], None] = lambda: None) -> None:
    guard()
    try:
        path.mkdir(mode=DIR_MODE)
    except FileExistsError:
        private_directory(path)
        return
    try:
        sync(path.parent)
    except OSError as error:
        raise InstallMutationError from error


def _install_signature(paths: InstallPaths, built: BuiltRelease) -> tuple[bool, ...]:
    runtime = paths.data_root / "runtime"
    candidates = (runtime, runtime / "releases", runtime / "releases" / built.release_id,
                  runtime / f".release-stage-{built.release_id}", runtime / "current",
                  runtime / ".current.installing", paths.workflow, paths.workflow_stage,
                  paths.workflow_tombstone, runtime / ".uninstall-plan.json",
                  runtime / ".uninstall-plan.json.writing")
    return tuple(path.exists() or path.is_symlink() for path in candidates)


def _check_invocation_binding(paths: InstallPaths, runtime: Path) -> None:
    plan_path = runtime / ".uninstall-plan.json"
    if plan_path.exists():
        plan = json.loads(read_private(plan_path))
        workflow = plan.get("workflow") if isinstance(plan, dict) else None
        if not isinstance(workflow, dict) or workflow.get("path") != str(paths.workflow):
            raise InvalidPathError
        return
    for link in (runtime / ".current.installing", runtime / "current"):
        if link.is_symlink():
            target = os.readlink(link)
            if not target.startswith("releases/") or "/" in target.removeprefix("releases/"):
                raise RuntimeTamperedError
            manifest = json.loads(read_private(runtime / target / "manifest.json"))
            workflow = manifest.get("workflow") if isinstance(manifest, dict) else None
            if not isinstance(workflow, dict) or workflow.get("path") != str(paths.workflow):
                raise InvalidPathError
            return
