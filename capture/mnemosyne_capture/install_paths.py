from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Final


REPOSITORY_ROOT: Final = Path("/Users/tars/Documents/workspace/mnemosyne")


@dataclass(frozen=True, slots=True)
class InstallPaths:
    home: Path
    data_root: Path
    services: Path
    workflow: Path
    workflow_stage: Path
    workflow_tombstone: Path
    bindings: tuple[tuple[Path, int, int], ...] = ()


class InvalidPathError(Exception):
    pass


def bind_paths(home: Path, data_root: Path | None) -> InstallPaths:
    selected_home = home.absolute()
    selected_root = (data_root if data_root is not None else selected_home / "Library/Application Support/Mnemosyne").absolute()
    services = selected_home / "Library/Services"
    workflow = services / "Mnemosyne Capture.workflow"
    paths = InstallPaths(selected_home, selected_root, services, workflow,
                         services / ".Mnemosyne Capture.workflow.installing",
                         services / ".Mnemosyne Capture.workflow.uninstalling")
    for value in (paths.home, paths.data_root, paths.services, paths.workflow,
                  paths.workflow_stage, paths.workflow_tombstone, Path(sys_executable())):
        if "'" in str(value) or any(character in str(value) for character in "\x00\r\n"):
            raise InvalidPathError
    for value in (paths.home, paths.services, paths.data_root, paths.data_root.parent):
        _reject_symlink_components(value)
    owned_directory(paths.home)
    for path in (paths.home / "Library", paths.services, paths.home / "Library/Application Support"):
        private_directory(path)
    private_directory(paths.data_root if paths.data_root.exists() else paths.data_root.parent)
    repository = REPOSITORY_ROOT
    forbidden = (paths.services, paths.workflow, paths.workflow_stage, paths.workflow_tombstone, repository)
    if paths.data_root == Path("/") or any(overlap(paths.data_root, value) for value in forbidden):
        raise InvalidPathError
    if any(overlap(paths.workflow, value) for value in (repository, paths.data_root)):
        raise InvalidPathError
    watched = (paths.home, paths.home / "Library", paths.services, paths.data_root.parent, paths.data_root)
    bindings = tuple((path, status.st_dev, status.st_ino) for path in watched if path.exists()
                     for status in (path.stat(follow_symlinks=False),))
    return InstallPaths(paths.home, paths.data_root, paths.services, paths.workflow,
                        paths.workflow_stage, paths.workflow_tombstone, bindings)


def private_directory(path: Path) -> None:
    status = path.stat(follow_symlinks=False)
    if not stat.S_ISDIR(status.st_mode) or status.st_uid != os.getuid() or stat.S_IMODE(status.st_mode) != 0o700:
        raise InvalidPathError


def owned_directory(path: Path) -> None:
    status = path.stat(follow_symlinks=False)
    if not stat.S_ISDIR(status.st_mode) or status.st_uid != os.getuid():
        raise InvalidPathError


def overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            status = current.stat(follow_symlinks=False)
        except FileNotFoundError:
            return
        if stat.S_ISLNK(status.st_mode):
            if current == Path("/var") and os.path.realpath(current) == "/private/var":
                continue
            raise InvalidPathError


def revalidate_paths(paths: InstallPaths) -> None:
    for path, device, inode in paths.bindings:
        status = path.stat(follow_symlinks=False)
        if (status.st_dev, status.st_ino) != (device, inode):
            raise InvalidPathError


def sys_executable() -> str:
    return os.path.realpath(os.sys.executable)


def sys_version() -> tuple[int, int]:
    return os.sys.version_info[:2]
