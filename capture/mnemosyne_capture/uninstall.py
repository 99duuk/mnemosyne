from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

from .enums import CommandCode, CommandName
from .install import PathDriftError, _require_paths, _services_lock, _stable_release
from .install_artifacts import OWNER, ArtifactTamperedError, canonical, read_private, sync, validate_manifest_release, validate_workflow_hashes, _resume_file
from .install_paths import InstallPaths, InvalidPathError, sys_version
from .store import CaptureStore, StoreLockError, StoreResult


class UninstallTamperedError(Exception):
    pass


class UninstallMutationError(OSError):
    pass


def uninstall(paths: InstallPaths) -> StoreResult:
    command = CommandName.UNINSTALL
    if sys_version() != (3, 14):
        return StoreResult(command, CommandCode.PYTHON_VERSION_MISMATCH, False, False)
    try:
        with _services_lock(paths.services, exclusive=True):
            _require_paths(paths, False)
            if not paths.data_root.exists():
                if any(path.exists() or path.is_symlink() for path in
                       (paths.workflow, paths.workflow_stage, paths.workflow_tombstone)):
                    raise UninstallTamperedError
                return StoreResult(command, CommandCode.UNINSTALLED, True, False, path=str(paths.workflow))
            with CaptureStore(paths.data_root).locked(create=False):
                return _uninstall_locked(paths)
    except InvalidPathError:
        return StoreResult(command, CommandCode.INVALID_PATH, False, False)
    except PathDriftError as error:
        return StoreResult(command, CommandCode.WRITE_FAILED if error.changed else CommandCode.INVALID_PATH,
                           False, error.changed)
    except UninstallMutationError:
        return StoreResult(command, CommandCode.WRITE_FAILED, False, True)
    except (UninstallTamperedError, ArtifactTamperedError):
        return StoreResult(command, CommandCode.RUNTIME_TAMPERED, False, False)
    except StoreLockError:
        return StoreResult(command, CommandCode.RUNTIME_TAMPERED, False, False)
    except OSError:
        runtime = paths.data_root / "runtime"
        changed = any(path.exists() or path.is_symlink() for path in (
            runtime / ".uninstall-plan.json", runtime / ".uninstall-plan.json.writing",
            runtime / ".current.uninstalling", paths.workflow_tombstone))
        return StoreResult(command, CommandCode.WRITE_FAILED, False, changed)


def _uninstall_locked(paths: InstallPaths) -> StoreResult:
    runtime = paths.data_root / "runtime"
    final_plan = runtime / ".uninstall-plan.json"
    if final_plan.exists():
        return _resume(paths, _load_plan(final_plan))
    if ((runtime / ".current.installing").exists() or paths.workflow_stage.exists()
            or any(path.name.startswith(".release-stage-") for path in runtime.iterdir())):
        _check_install_residue(paths)
        return StoreResult(CommandName.UNINSTALL, CommandCode.INSTALL_IN_PROGRESS, False, False)
    writing = runtime / ".uninstall-plan.json.writing"
    stable = _stable_release(paths)
    if stable is None:
        sync(runtime)
        return StoreResult(CommandName.UNINSTALL, CommandCode.UNINSTALLED, True, False, path=str(paths.workflow))
    plan = _make_plan(paths, stable)
    _resume_file(final_plan, canonical(plan))
    return _resume(paths, plan)


def _make_plan(paths: InstallPaths, stable: tuple[Path, dict]) -> dict:
    release, manifest = stable
    runtime = paths.data_root / "runtime"
    releases = runtime / "releases"
    release_hashes: dict[str, str] = {}
    for candidate in sorted(releases.iterdir(), key=lambda path: path.name.encode()):
        status = candidate.stat(follow_symlinks=False)
        if not status.st_mode & 0o040000:
            raise UninstallTamperedError
        raw_manifest = read_private(candidate / "manifest.json")
        candidate_manifest = json.loads(raw_manifest)
        if not isinstance(candidate_manifest, dict):
            raise UninstallTamperedError
        validate_manifest_release(candidate, candidate_manifest)
        release_hashes[candidate.name] = hashlib.sha256(raw_manifest).hexdigest()
    return {"schema": "mnemosyne.uninstall/v1", "owner": OWNER, "workflow": manifest["workflow"],
            "current_target": f"releases/{release.name}", "releases": release_hashes}


def _load_plan(path: Path) -> dict:
    raw = read_private(path)
    plan = json.loads(raw)
    if not isinstance(plan, dict) or raw != canonical(plan):
        raise UninstallTamperedError
    return plan


def _resume(paths: InstallPaths, plan: dict) -> StoreResult:
    runtime = paths.data_root / "runtime"
    if (set(plan) != {"schema", "owner", "workflow", "current_target", "releases"}
            or plan.get("schema") != "mnemosyne.uninstall/v1" or plan.get("owner") != OWNER):
        raise UninstallTamperedError
    workflow = plan.get("workflow")
    releases_value = plan.get("releases")
    if not isinstance(workflow, dict) or workflow.get("path") != str(paths.workflow):
        raise InvalidPathError
    if not isinstance(releases_value, dict):
        raise UninstallTamperedError
    if (runtime / ".uninstall-plan.json.writing").exists():
        raise UninstallTamperedError
    _validate_phase(paths, plan)
    _require_paths(paths, False)
    tombstone = paths.workflow_tombstone
    if paths.workflow.exists() and tombstone.exists():
        raise UninstallTamperedError
    if paths.workflow.exists():
        validate_workflow_hashes(paths.workflow, workflow)
        _rename_guarded(paths, paths.workflow, tombstone, False)
        sync(paths.services)
        _require_paths(paths, True)
    current = runtime / "current"
    current_tombstone = runtime / ".current.uninstalling"
    if current.is_symlink() and current_tombstone.is_symlink():
        raise UninstallTamperedError
    if current.is_symlink():
        if os.readlink(current) != plan.get("current_target"):
            raise UninstallTamperedError
        _rename_guarded(paths, current, current_tombstone, tombstone.exists())
        sync(runtime)
        _require_paths(paths, True)
    if current_tombstone.is_symlink():
        if os.readlink(current_tombstone) != plan.get("current_target"):
            raise UninstallTamperedError
        _unlink_guarded(paths, current_tombstone, True)
        sync(runtime)
        _require_paths(paths, True)
    releases = runtime / "releases"
    for release_id in sorted(releases_value, key=lambda value: value.encode()):
        if len(release_id) != 64 or any(character not in "0123456789abcdef" for character in release_id):
            raise UninstallTamperedError
        release = releases / release_id
        if release.exists():
            _validate_release_cursor(release, releases_value[release_id])
            for name in ("capture.scpt", "extract-current-page.js", "mnemosyne.pyz", "manifest.json"):
                target = release / name
                if target.exists():
                    _unlink_guarded(paths, target, True)
                    sync(release)
                    _require_paths(paths, True)
            _rmdir_guarded(paths, release, True)
            sync(releases)
            _require_paths(paths, True)
    if tombstone.exists():
        _validate_workflow_cursor(tombstone, workflow)
        for relative in ("Contents/Resources/document.wflow", "Contents/Resources/mnemosyne-owner.json",
                         "Contents/Info.plist"):
            target = tombstone / relative
            if target.exists():
                _unlink_guarded(paths, target, True)
                sync(target.parent)
                _require_paths(paths, True)
        for relative in ("Contents/Resources", "Contents"):
            target = tombstone / relative
            if target.exists():
                _rmdir_guarded(paths, target, True)
                sync(target.parent)
                _require_paths(paths, True)
        _rmdir_guarded(paths, tombstone, True)
        sync(paths.services)
        _require_paths(paths, True)
    _unlink_guarded(paths, runtime / ".uninstall-plan.json", True)
    try:
        sync(runtime)
    except OSError as error:
        raise UninstallMutationError from error
    _require_paths(paths, True)
    return StoreResult(CommandName.UNINSTALL, CommandCode.UNINSTALLED, True, True, path=str(paths.workflow))


def _validate_release_cursor(release: Path, expected_manifest_hash: str) -> None:
    entries = set(os.listdir(release))
    suffixes = ({"capture.scpt", "extract-current-page.js", "mnemosyne.pyz", "manifest.json"},
                {"extract-current-page.js", "mnemosyne.pyz", "manifest.json"},
                {"mnemosyne.pyz", "manifest.json"}, {"manifest.json"}, set())
    if entries not in suffixes:
        raise UninstallTamperedError
    if "manifest.json" not in entries:
        return
    raw = read_private(release / "manifest.json")
    if hashlib.sha256(raw).hexdigest() != expected_manifest_hash:
        raise UninstallTamperedError
    manifest = json.loads(raw)
    artifacts = manifest.get("artifacts") if isinstance(manifest, dict) else None
    if not isinstance(artifacts, dict) or manifest.get("release_id") != release.name:
        raise UninstallTamperedError
    for name in entries - {"manifest.json"}:
        descriptor = artifacts.get(name)
        if not isinstance(descriptor, dict) or hashlib.sha256(read_private(release / name)).hexdigest() != descriptor.get("sha256"):
            raise UninstallTamperedError


def _validate_phase(paths: InstallPaths, plan: dict) -> None:
    runtime = paths.data_root / "runtime"
    current = runtime / "current"
    current_tombstone = runtime / ".current.uninstalling"
    if current.is_symlink() and current_tombstone.is_symlink():
        raise UninstallTamperedError
    for link in (current, current_tombstone):
        if link.exists() and not link.is_symlink():
            raise UninstallTamperedError
        if link.is_symlink() and os.readlink(link) != plan["current_target"]:
            raise UninstallTamperedError
    if paths.workflow.exists() and paths.workflow_tombstone.exists():
        raise UninstallTamperedError
    workflow = plan["workflow"]
    if paths.workflow.exists():
        validate_workflow_hashes(paths.workflow, workflow)
    if paths.workflow_tombstone.exists():
        _validate_workflow_cursor(paths.workflow_tombstone, workflow)
    releases = runtime / "releases"
    listed = sorted(plan["releases"], key=lambda value: value.encode())
    if set(os.listdir(releases)) - set(listed):
        raise UninstallTamperedError
    states: list[str] = []
    for release_id in listed:
        release = releases / release_id
        if not release.exists():
            states.append("absent")
            continue
        entries = set(os.listdir(release))
        _validate_release_cursor(release, plan["releases"][release_id])
        states.append("complete" if len(entries) == 4 else "partial")
    if states.count("partial") > 1:
        raise UninstallTamperedError
    cursor = next((index for index, value in enumerate(states) if value != "absent"), len(states))
    if any(value != "complete" for value in states[cursor + (states[cursor:cursor + 1] == ["partial"]):]):
        raise UninstallTamperedError
    releases_absent = all(value == "absent" for value in states)
    source = paths.workflow.exists()
    tombstone = paths.workflow_tombstone.exists()
    if source and (not current.is_symlink() or current_tombstone.is_symlink() or not all(value == "complete" for value in states)):
        raise UninstallTamperedError
    if tombstone and current.is_symlink() and not all(value == "complete" for value in states):
        raise UninstallTamperedError
    if current_tombstone.is_symlink() and (not tombstone or current.is_symlink() or not all(value == "complete" for value in states)):
        raise UninstallTamperedError
    if not source and not tombstone and (current.is_symlink() or current_tombstone.is_symlink() or not releases_absent):
        raise UninstallTamperedError


def _validate_workflow_cursor(tombstone: Path, hashes: dict) -> None:
    allowed_shapes = ({"Contents"}, set())
    if set(os.listdir(tombstone)) not in allowed_shapes:
        raise UninstallTamperedError
    if not (tombstone / "Contents").exists():
        return
    contents = tombstone / "Contents"
    entries = set(os.listdir(contents))
    if entries not in ({"Info.plist", "Resources"}, {"Resources"}, set()):
        raise UninstallTamperedError
    resources = contents / "Resources"
    if resources.exists() and set(os.listdir(resources)) not in (
            {"document.wflow", "mnemosyne-owner.json"}, {"mnemosyne-owner.json"}, set()):
        raise UninstallTamperedError
    present = {relative for relative in ("Contents/Resources/document.wflow", "Contents/Info.plist",
               "Contents/Resources/mnemosyne-owner.json") if (tombstone / relative).exists()}
    expected = {"Contents/Resources/document.wflow": "document_sha256", "Contents/Info.plist": "info_plist_sha256",
                "Contents/Resources/mnemosyne-owner.json": "owner_marker_sha256"}
    for relative in present:
        if hashlib.sha256(read_private(tombstone / relative)).hexdigest() != hashes.get(expected[relative]):
            raise UninstallTamperedError


def _check_install_residue(paths: InstallPaths) -> None:
    runtime = paths.data_root / "runtime"
    witness = runtime / ".current.installing"
    if witness.exists() and not witness.is_symlink():
        raise UninstallTamperedError
    if witness.is_symlink():
        target = os.readlink(witness)
        if not target.startswith("releases/") or "/" in target.removeprefix("releases/"):
            raise UninstallTamperedError
        raw = read_private(runtime / target / "manifest.json")
        manifest = json.loads(raw)
        workflow = manifest.get("workflow") if isinstance(manifest, dict) else None
        if not isinstance(workflow, dict) or workflow.get("path") != str(paths.workflow):
            raise InvalidPathError
        validate_manifest_release(runtime / target, manifest)
    for stage in runtime.iterdir():
        if not stage.name.startswith(".release-stage-"):
            continue
        status = stage.stat(follow_symlinks=False)
        if not stat.S_ISDIR(status.st_mode) or stat.S_IMODE(status.st_mode) != 0o700:
            raise UninstallTamperedError
        entries = set(os.listdir(stage))
        if not entries <= {"owner.json", "owner.json.writing", "release"}:
            raise UninstallTamperedError
        for owner in (stage / "owner.json", stage / "owner.json.writing"):
            if owner.exists():
                read_private(owner)


def _rename_guarded(paths: InstallPaths, source: Path, target: Path, changed: bool) -> None:
    _require_paths(paths, changed)
    source.rename(target)


def _unlink_guarded(paths: InstallPaths, target: Path, changed: bool) -> None:
    _require_paths(paths, changed)
    target.unlink()


def _rmdir_guarded(paths: InstallPaths, target: Path, changed: bool) -> None:
    _require_paths(paths, changed)
    target.rmdir()
