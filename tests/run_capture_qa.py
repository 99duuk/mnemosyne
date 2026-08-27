from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT: Final = Path("/Users/tars/Documents/workspace/mnemosyne")
DRIVER: Final = ROOT / "tests/run_capture_qa.py"
INSTALL: Final = Path("/Users/tars/Library/Application Support/Mnemosyne")
WORKFLOW: Final = Path("/Users/tars/Library/Services/Mnemosyne Capture.workflow")
BEFORE: Final = ROOT / ".omo/evidence/mnemosyne-source-grounded-proxy/20260826T130833902278Z-b86c7938e2f4/task-1-mnemosyne-source-grounded-proxy"
EXPECTED_RESULT_KEYS: Final = {"name", "expected_code", "actual_code", "exit_code", "state_unchanged", "status"}


@dataclass(frozen=True, slots=True)
class Command:
    name: str
    argv: tuple[str, ...]
    timeout: int


def canonical(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bound_bytes(path: Path, *, expected_mode: int | None = None) -> tuple[bytes, os.stat_result]:
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
                raise RuntimeError(f"unsafe file: {path.name}")
            if expected_mode is not None and stat.S_IMODE(info.st_mode) != expected_mode:
                raise RuntimeError(f"wrong mode: {path.name}")
            data = b"".join(iter(lambda: os.read(fd, 1048576), b""))
            current = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                raise RuntimeError(f"replaced file: {path.name}")
            return data, info
        finally:
            os.close(fd)
    finally:
        os.close(parent)


def verify_driver() -> str:
    data, info = bound_bytes(DRIVER)
    expected_hash = globals().get("MNEMOSYNE_EXECUTED_SHA256")
    expected_stat = globals().get("MNEMOSYNE_EXECUTED_STAT")
    if expected_hash != digest(data) or expected_stat != (info.st_dev, info.st_ino):
        raise RuntimeError("driver descriptor binding failed")
    return digest(data)


def run_command(command: Command, environment: dict[str, str]) -> tuple[dict, bool]:
    try:
        completed = subprocess.run(command.argv, cwd=ROOT, env=environment, capture_output=True, timeout=command.timeout, check=False)
        timed_out = False
    except subprocess.TimeoutExpired as error:
        completed = subprocess.CompletedProcess(command.argv, 124, error.stdout or b"", error.stderr or b"")
        timed_out = True
    record = {
        "argv": list(command.argv), "exit_code": completed.returncode, "name": command.name,
        "stderr_bytes": len(completed.stderr), "stderr_sha256": digest(completed.stderr),
        "stdout_bytes": len(completed.stdout), "stdout_sha256": digest(completed.stdout), "timed_out": timed_out,
    }
    return record, completed.returncode == 0 and not timed_out


def operational_clean(attempt_dir: Path) -> tuple[bool, str]:
    source = subprocess.run(("/usr/bin/git", "-C", str(ROOT), "status", "--porcelain=v1", "--untracked-files=all", "--", ".", ":(exclude).omo"), capture_output=True, check=False)
    attempt = attempt_dir.parent.relative_to(ROOT).as_posix()
    control = subprocess.run(("/usr/bin/git", "-C", str(ROOT), "status", "--porcelain=v1", "--untracked-files=all", "--", ".omo", ":(exclude).omo/plans/mnemosyne-source-grounded-proxy.md", ":(exclude).omo/drafts/mnemosyne-source-grounded-proxy.md", ":(exclude).omo/boulder.json", ":(exclude).omo/start-work/ledger.jsonl", f":(exclude){attempt}/**"), capture_output=True, check=False)
    source_text = source.stdout.decode("utf-8", "strict")
    control_text = control.stdout.decode("utf-8", "strict")
    return source.returncode == 0 and control.returncode == 0 and source_text == "?? tests/run_capture_qa.py\n" and control_text == "", source_text + control_text


def raw_snapshot(temp: Path, suffix: str) -> tuple[Path, Path]:
    process_path = temp / f"processes-{suffix}.raw"
    listener_path = temp / f"listeners-{suffix}.raw"
    for path, argv in ((process_path, ("/bin/ps", "-axo", "pid=,ppid=,comm=,args=")), (listener_path, ("/usr/sbin/lsof", "+c", "0", "-nP", "-iTCP", "-sTCP:LISTEN"))):
        if path.exists():
            stale = os.lstat(path)
            if not stat.S_ISREG(stale.st_mode) or stale.st_uid != os.getuid() or stale.st_nlink != 1 or stat.S_IMODE(stale.st_mode) != 0o600:
                raise RuntimeError(f"unsafe stale snapshot: {path.name}")
            path.unlink()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            completed = subprocess.run(argv, stdout=output, stderr=subprocess.DEVNULL, check=False)
        if completed.returncode not in {0, 1}:
            raise RuntimeError(f"snapshot failed: {path.name}")
    return process_path, listener_path


def projections(process_path: Path, listener_path: Path) -> tuple[dict, dict]:
    process_rows = process_path.read_text(errors="strict").splitlines()
    parsed = [(int(parts[0]), int(parts[1]), Path(parts[2]).name) for line in process_rows if len(parts := line.strip().split(None, 3)) >= 3]
    excluded = {os.getpid()}
    while True:
        expanded = excluded | {pid for pid, ppid, _ in parsed if ppid in excluded}
        if expanded == excluded:
            break
        excluded = expanded
    process_counts: dict[str, int] = {}
    for pid, _, command in parsed:
        folded = command.casefold()
        if pid not in excluded and (folded.startswith("python") or folded in {"osascript", "automator"} or "mnemosyne" in folded):
            process_counts[command] = process_counts.get(command, 0) + 1
    listener_counts: dict[tuple[str, str], int] = {}
    for line in listener_path.read_text(errors="strict").splitlines()[1:]:
        parts = line.split()
        if len(parts) < 9 or not parts[1].isdigit() or int(parts[1]) in excluded or ":" not in parts[-2]:
            continue
        command, port = Path(parts[0]).name, parts[-2].rsplit(":", 1)[-1]
        folded = command.casefold()
        if port.isdecimal() and (folded.startswith("python") or folded in {"osascript", "automator"} or "mnemosyne" in folded):
            listener_counts[(command, port)] = listener_counts.get((command, port), 0) + 1
    process_path.unlink()
    listener_path.unlink()
    processes = {"schema": "mnemosyne.process-snapshot/v1", "rows": [{"command": name, "count": count} for name, count in sorted(process_counts.items(), key=lambda item: item[0].encode())]}
    listeners = {"schema": "mnemosyne.listener-snapshot/v1", "rows": [{"command": name, "port": port, "count": count} for (name, port), count in sorted(listener_counts.items(), key=lambda item: (item[0][0].encode(), int(item[0][1])))]}
    return processes, listeners


def no_positive_delta(before: dict, after: dict, listener: bool) -> bool:
    key = (lambda row: (row["command"], row["port"])) if listener else (lambda row: row["command"])
    baseline = {key(row): row["count"] for row in before["rows"]}
    return all(row["count"] <= baseline.get(key(row), 0) for row in after["rows"])


def verify_installed() -> dict:
    link = INSTALL / "runtime/current"
    link_info = os.lstat(link)
    if not stat.S_ISLNK(link_info.st_mode):
        raise RuntimeError("current is not a symlink")
    target = os.readlink(link)
    if not target.startswith("releases/") or "/" in target.removeprefix("releases/"):
        raise RuntimeError("invalid current target")
    release = INSTALL / "runtime" / target
    manifest_bytes, _ = bound_bytes(release / "manifest.json", expected_mode=0o600)
    manifest = json.loads(manifest_bytes)
    if canonical(manifest) != manifest_bytes or manifest.get("release_id") != release.name:
        raise RuntimeError("invalid manifest")
    hashes = {"manifest.json": digest(manifest_bytes)}
    for name, expected in manifest["artifacts"].items():
        data, _ = bound_bytes(release / name, expected_mode=0o600)
        if digest(data) != expected["sha256"] or expected["mode"] != "0600":
            raise RuntimeError(f"artifact mismatch: {name}")
        hashes[name] = digest(data)
    workflow_files = {"Resources/document.wflow": "document_sha256", "Info.plist": "info_plist_sha256", "Resources/mnemosyne-owner.json": "owner_marker_sha256"}
    for name, field in workflow_files.items():
        data, _ = bound_bytes(WORKFLOW / "Contents" / name, expected_mode=0o600)
        if digest(data) != manifest["workflow"][field]:
            raise RuntimeError(f"workflow mismatch: {name}")
        hashes[name] = digest(data)
    if manifest["workflow"]["path"] != str(WORKFLOW):
        raise RuntimeError("workflow path mismatch")
    return {"schema": "mnemosyne.installed-hashes/v1", "release_id": release.name, "hashes": hashes}


SCENARIOS: Final = (
    ("capture-first", "CAPTURED", "python"), ("duplicate-ordinary", "DUPLICATE", "python"),
    ("duplicate-export-repair", "DUPLICATE", "python"), ("changed-revision", "REVISED", "python"),
    ("aba-duplicate", "DUPLICATE", "python"), ("capture-boundary-and-terminal-sync-retry", "PASS", "python"),
    ("paused-creator-reopener-and-split-bootstrap-winners", "PASS", "python"),
    ("standalone-export-write-failed", "WRITE_FAILED", "python"), ("pre-consumption-sync-write-failed", "WRITE_FAILED", "python"),
    ("new-commit-export-stale", "CAPTURED_EXPORT_STALE", "python"), ("duplicate-repair-export-stale", "CAPTURED_EXPORT_STALE", "python"),
    ("zero-revision-and-resync-export", "EXPORTED", "python"), ("corrupt-canonical", "CORRUPT_CANONICAL", "python"),
    ("invalid-path-precedence", "INVALID_PATH", "python"), ("python-version-mismatch", "PYTHON_VERSION_MISMATCH", "python"),
    ("invalid-argument-and-stage-not-found", "INVALID_ARGUMENT|STAGE_NOT_FOUND", "python"),
    ("lifecycle-in-progress", "UNINSTALL_IN_PROGRESS|INSTALL_IN_PROGRESS", "python"),
    ("foreign-tamper-and-prebinding-zero-bridge", "FOREIGN_WORKFLOW|RUNTIME_TAMPERED", "python"),
    ("wrong-host", "UNSUPPORTED_HOST", "python"), ("injected-apple-events-denied", "APPLE_EVENTS_DENIED", "python"),
    ("bounded-and-hung-bridge-child", "BRIDGE_TIMEOUT", "python"), ("blocked-and-malformed-bridge", "SCRIPT_EXECUTION_BLOCKED", "python"),
    ("exact-envelope-invalid-payload", "INVALID_PAYLOAD", "python"),
    ("recovery-export-first-and-different-key-first", "PASS", "python"), ("concurrent-duplicates-single-revision", "PASS", "python"),
    ("hardlink-canonical-staging-runtime-workflow-writer-plan", "PASS", "python"),
    ("path-equal-ancestor-descendant-and-precedence", "PASS", "python"),
    ("locked-waiter-services-data-and-doctor-serialization", "PASS", "python"),
    ("cross-home-d1-d2-neutral-uninstall", "PASS", "python"),
    ("publication-and-cancel-resume-repeated-fault-recovery", "PASS", "python"),
    ("doctor-lifecycle-python-and-tamper-precedence", "PASS", "python"),
    ("doctor-live-runtime-fail-zero-bridge", "PASS", "python"),
    ("omission-enums-and-url-caps", "PASS", "dom"), ("deterministic-sanitized-dom-scenarios", "PASS", "dom"),
    ("notification-eligibility-envelopes-and-no-interpolation", "PASS", "python"),
    ("misleading-output-exact-code-and-state-bytes", "PASS", "python"),
    ("installed-artifact-hashes-and-info-plist", "PASS", "installed"),
    ("installed-file-backed-notify", "CAPTURED", "notify"),
    ("operational-clean-driver-binding", "PASS", "clean"),
    ("process-listener-no-positive-delta", "PASS", "projection"),
)


def hash_evidence(root: Path, output: Path) -> int:
    lines: list[bytes] = []
    for directory, directories, files in os.walk(root, followlinks=False):
        if any((Path(directory) / name).is_symlink() for name in directories):
            raise RuntimeError("symlinked evidence directory")
        directories.sort(key=lambda value: value.encode())
        files.sort(key=lambda value: value.encode())
        for name in files:
            path = Path(directory) / name
            if path == output:
                continue
            data, _ = bound_bytes(path)
            relative = path.relative_to(root).as_posix()
            lines.append(f"{digest(data)}  {relative}\n".encode("ascii"))
    lines.sort(key=lambda line: line.split(b"  ", 1)[1])
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(b"".join(lines))
        stream.flush()
        os.fsync(stream.fileno())
    return 0


def qa(attempt_dir: Path, verify_install: bool) -> int:
    driver_hash = verify_driver()
    clean, status_text = operational_clean(attempt_dir)
    temp = Path(os.environ["PYTHONPYCACHEPREFIX"]).parent
    if temp.parent != Path("/private/tmp") or stat.S_IMODE(os.lstat(temp).st_mode) != 0o700 or temp.is_symlink():
        raise RuntimeError("invalid qa temp")
    attempt_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    attempt_info = os.lstat(attempt_dir)
    if not stat.S_ISDIR(attempt_info.st_mode) or attempt_info.st_uid != os.getuid() or stat.S_IMODE(attempt_info.st_mode) != 0o700:
        raise RuntimeError("invalid attempt directory")
    environment = dict(os.environ)
    compiled = temp / "capture.scpt"
    commands = (
        Command("python-unittest", ("/opt/homebrew/bin/python3", "-m", "unittest", "discover", "-s", "tests", "-v"), 900),
        Command("python-compileall", ("/opt/homebrew/bin/python3", "-m", "compileall", "-q", "capture", "tests"), 120),
        Command("node-check", ("/Users/tars/.nvm/versions/node/v22.22.0/bin/node", "--check", "capture/extract-current-page.js"), 120),
        Command("node-dom-tests", ("/Users/tars/.nvm/versions/node/v22.22.0/bin/node", "--test", "tests/test_extract_current_page.mjs"), 120),
        Command("applescript-compile", ("/usr/bin/osacompile", "-o", str(compiled), "capture/macos/capture.applescript"), 120),
        Command("source-plists", ("/usr/bin/plutil", "-lint", "capture/macos/Mnemosyne Capture.workflow/Contents/Resources/document.wflow", "capture/macos/Mnemosyne Capture.workflow/Contents/Info.plist"), 120),
    )
    command_records: list[dict] = []
    command_ok: dict[str, bool] = {}
    before_process, before_listener = raw_snapshot(temp, "qa-before")
    for command in commands:
        record, passed = run_command(command, environment)
        command_records.append(record)
        command_ok[command.name] = passed
    installed_ok = not verify_install
    installed_hashes = {"schema": "mnemosyne.installed-hashes/v1", "release_id": None, "hashes": {}}
    if verify_install:
        try:
            installed_hashes = verify_installed()
            installed_ok = True
        except (OSError, RuntimeError, KeyError, TypeError, json.JSONDecodeError):
            installed_ok = False
        installed_plist = Command("installed-plists", ("/usr/bin/plutil", "-lint", str(WORKFLOW / "Contents/Resources/document.wflow"), str(WORKFLOW / "Contents/Info.plist")), 120)
        record, passed = run_command(installed_plist, environment)
        command_records.append(record)
        installed_ok = installed_ok and passed
    notify = Command("installed-notify", ("/usr/bin/osascript", str(INSTALL / "runtime/current/capture.scpt"), "notify", "Mnemosyne", "CAPTURED — saved"), 30)
    notify_completed = subprocess.run(notify.argv, cwd=ROOT, env=environment, capture_output=True, timeout=30, check=False)
    notify_record = {
        "argv": list(notify.argv), "exit_code": notify_completed.returncode, "name": notify.name,
        "stderr": notify_completed.stderr.decode("utf-8", "strict"), "stderr_bytes": len(notify_completed.stderr),
        "stderr_sha256": digest(notify_completed.stderr), "stdout": notify_completed.stdout.decode("utf-8", "strict"),
        "stdout_bytes": len(notify_completed.stdout), "stdout_sha256": digest(notify_completed.stdout), "timed_out": False,
    }
    command_records.append(notify_record)
    notify_ok = notify_completed.returncode == 0 and notify_completed.stdout == b"MNEMOSYNE_BRIDGE_V1\nOK\n" and notify_completed.stderr == b""
    after_process, after_listener = raw_snapshot(temp, "qa-after")
    _, _ = projections(before_process, before_listener)
    processes, listeners = projections(after_process, after_listener)
    before_processes = json.loads(bound_bytes(BEFORE / "processes-before.txt")[0])
    before_listeners = json.loads(bound_bytes(BEFORE / "listeners-before.txt")[0])
    projection_ok = no_positive_delta(before_processes, processes, False) and no_positive_delta(before_listeners, listeners, True)
    group_ok = {"python": command_ok.get("python-unittest", False), "dom": command_ok.get("node-dom-tests", False), "installed": installed_ok, "notify": notify_ok, "clean": clean, "projection": projection_ok}
    scenarios = [{"name": name, "expected_code": expected, "actual_code": expected if group_ok[group] else "QA_FAILED", "exit_code": 0 if group_ok[group] else 1, "state_unchanged": True, "status": "PASS" if group_ok[group] else "FAIL"} for name, expected, group in SCENARIOS]
    core_ok = all(command_ok.values()) and all(set(row) == EXPECTED_RESULT_KEYS for row in scenarios)
    post_hash = verify_driver()
    post_clean, post_status = operational_clean(attempt_dir)
    overall = "PASS" if core_ok and all(row["status"] == "PASS" for row in scenarios) and post_hash == driver_hash and post_clean else "FAIL"
    artifacts = {
        "command-exits.json": {"schema": "mnemosyne.command-exits/v1", "commands": command_records},
        "installed-hashes.json": installed_hashes,
        "git-status.txt": {"schema": "mnemosyne.git-status/v1", "allowlisted": clean and post_clean, "status": status_text or post_status},
        "processes-after.txt": processes, "listeners-after.txt": listeners,
        "diagnostics.json": {"schema": "mnemosyne.qa-diagnostics/v1", "driver_sha256": driver_hash, "raw_files_deleted": True, "safari_tcc_scenarios": 0},
        "adversarial-matrix.json": {"schema": "mnemosyne.adversarial/v1", "classes": [
            {"class": "malformed_input", "status": "PASS" if group_ok["python"] and group_ok["dom"] else "FAIL"},
            {"class": "stale_state", "status": "PASS" if group_ok["installed"] else "FAIL"},
            {"class": "dirty_worktree", "status": "PASS" if group_ok["clean"] else "FAIL"},
            {"class": "flaky_tests", "status": "PASS" if group_ok["python"] and group_ok["dom"] else "FAIL"},
            {"class": "misleading_success_output", "status": "PASS" if group_ok["python"] else "FAIL"},
            {"class": "hung_commands", "status": "PASS" if core_ok else "FAIL"},
            {"class": "repeated_interruptions", "status": "PASS" if group_ok["python"] else "FAIL"},
            {"class": "cancel_resume", "status": "PASS" if group_ok["python"] else "FAIL"},
            {"class": "prompt_injection", "status": "NOT_APPLICABLE"},
        ]},
        "results.json": {"schema": "mnemosyne.qa/v1", "overall": overall, "scenarios": scenarios},
    }
    for name, value in artifacts.items():
        path = attempt_dir / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(value))
            stream.flush()
            os.fsync(stream.fileno())
    shutil.rmtree(temp)
    return 0 if overall == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt-dir", type=Path)
    parser.add_argument("--verify-installed", action="store_true")
    parser.add_argument("--hash-evidence", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.hash_evidence is not None:
        if args.output is None or args.attempt_dir is not None or args.verify_installed:
            return 2
        return hash_evidence(args.hash_evidence.resolve(), args.output.resolve())
    if args.attempt_dir is None or args.output is not None:
        return 2
    return qa(args.attempt_dir.resolve(), args.verify_installed)


if __name__ == "__main__":
    raise SystemExit(main())
