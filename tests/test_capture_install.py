from __future__ import annotations

import contextlib
import fcntl
import io
import json
import hashlib
import os
import plistlib
import stat
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from mnemosyne_capture.bridge import Bridge, BridgeError, BridgeErrorCode, SmokeResult, SnapshotResult
from mnemosyne_capture.cli import main
from mnemosyne_capture.payload import CapturePayload
from mnemosyne_capture.store import CaptureStore
from mnemosyne_capture.install_artifacts import (ArtifactTamperedError, OWNER, build_release,
                                                  canonical, publish_release, publish_workflow_stage, valid_prefix, _resume_file)
from mnemosyne_capture.doctor import _python_check
from mnemosyne_capture import doctor as doctor_module
from mnemosyne_capture.install import PathDriftError, _require_paths
from mnemosyne_capture.install_paths import bind_paths


OWNER_BYTES = b'{"owner":"github.com/99duuk/mnemosyne#mnemosyne-capture/v1","schema":"mnemosyne.workflow-owner/v1"}\n'


def invoke(argv: list[str]) -> tuple[int, dict[str, bool | str | None | list[str]]]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exit_code = main(argv)
    return exit_code, json.loads(output.getvalue())


def private_home(root: Path) -> Path:
    home = root / "home"
    services = home / "Library" / "Services"
    support = home / "Library" / "Application Support"
    services.mkdir(parents=True, mode=0o700)
    support.mkdir(mode=0o700)
    home.chmod(0o700)
    (home / "Library").chmod(0o700)
    return home


class CaptureInstallTests(unittest.TestCase):
    def test_install_reinstall_doctor_uninstall_real_cli(self) -> None:
        # Given: an explicit synthetic home with the required private Library directories.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            home = private_home(Path(directory))
            workflow = home / "Library/Services/Mnemosyne Capture.workflow"
            root = home / "Library/Application Support/Mnemosyne"

            # When: install, reinstall, static doctor, and uninstall run through the real CLI.
            installed = invoke(["--home", str(home), "install"])
            reinstalled = invoke(["--home", str(home), "install"])
            diagnosed = invoke(["--home", str(home), "doctor", "--json"])
            uninstalled = invoke(["--home", str(home), "uninstall"])

            # Then: lifecycle codes, idempotence, and cleanup are exact.
            self.assertEqual((installed[0], installed[1]["code"], installed[1]["changed"]), (0, "INSTALLED", True))
            self.assertEqual((reinstalled[0], reinstalled[1]["code"], reinstalled[1]["changed"]), (0, "INSTALLED", False))
            self.assertEqual((diagnosed[0], diagnosed[1]["code"]), (0, "READY"))
            self.assertEqual((uninstalled[0], uninstalled[1]["code"], uninstalled[1]["changed"]), (0, "UNINSTALLED", True))
            self.assertFalse(workflow.exists())
            self.assertFalse((root / "runtime/current").exists())

    def test_install_artifacts_have_exact_bytes_modes_and_binding(self) -> None:
        # Given: a private synthetic home and redirected data root.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home = private_home(base)
            data_root = base / "data"

            # When: install publishes one immutable release and workflow.
            exit_code, result = invoke(["--home", str(home), "--data-root", str(data_root), "install"])

            # Then: manifest binding, owner bytes, plist structure, and private modes are exact.
            self.assertEqual((exit_code, result["code"]), (0, "INSTALLED"))
            current = data_root / "runtime/current"
            self.assertTrue(current.is_symlink())
            release = current.resolve()
            manifest = json.loads((release / "manifest.json").read_bytes())
            installed_doctor = subprocess.run([os.sys.executable, str(release / "mnemosyne.pyz"), "--home", str(home),
                                               "--data-root", str(data_root), "doctor", "--json"], capture_output=True)
            workflow = home / "Library/Services/Mnemosyne Capture.workflow"
            self.assertEqual(manifest["workflow"]["path"], str(workflow))
            self.assertEqual((installed_doctor.returncode, json.loads(installed_doctor.stdout)["code"]), (0, "READY"),
                             installed_doctor.stdout.decode())
            self.assertEqual((workflow / "Contents/Resources/mnemosyne-owner.json").read_bytes(), OWNER_BYTES)
            document = plistlib.loads((workflow / "Contents/Resources/document.wflow").read_bytes())
            command = document["actions"][0]["action"]["ActionParameters"]["COMMAND_STRING"]
            self.assertEqual(command, f"'{os.path.realpath(os.sys.executable)}' '{data_root}/runtime/current/mnemosyne.pyz' --data-root '{data_root}' capture")
            info = plistlib.loads((workflow / "Contents/Info.plist").read_bytes())
            self.assertEqual(info["CFBundleIdentifier"], "com.99duuk.mnemosyne.capture")
            for path in (data_root, data_root / "runtime", data_root / "runtime/releases", release, workflow,
                         workflow / "Contents", workflow / "Contents/Resources"):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
            for path in (*release.iterdir(), workflow / "Contents/Resources/document.wflow", workflow / "Contents/Info.plist",
                         workflow / "Contents/Resources/mnemosyne-owner.json"):
                self.assertEqual((stat.S_IMODE(path.stat().st_mode), path.stat().st_nlink), (0o600, 1))

    def test_foreign_workflow_and_overlapping_root_fail_before_mutation(self) -> None:
        # Given: one home with a foreign reserved workflow and another with an overlapping data root.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home = private_home(base / "foreign")
            foreign = home / "Library/Services/Mnemosyne Capture.workflow"
            foreign.mkdir(mode=0o700)
            sentinel = foreign / "sentinel"
            sentinel.write_bytes(b"foreign")
            overlap_home = private_home(base / "overlap")
            overlap = overlap_home / "Library/Services/data"

            # When: both invalid installations are attempted.
            foreign_result = invoke(["--home", str(home), "install"])
            overlap_result = invoke(["--home", str(overlap_home), "--data-root", str(overlap), "install"])

            # Then: the precise refusal wins and neither target is mutated.
            self.assertEqual((foreign_result[0], foreign_result[1]["code"]), (1, "FOREIGN_WORKFLOW"))
            self.assertEqual(sentinel.read_bytes(), b"foreign")
            self.assertEqual((overlap_result[0], overlap_result[1]["code"]), (1, "INVALID_PATH"))
            self.assertFalse(overlap.exists())

    def test_source_and_installed_plists_are_exact_and_native_valid(self) -> None:
        # Given: the tracked default workflow and an explicit synthetic home.
        source = Path("capture/macos/Mnemosyne Capture.workflow/Contents")
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            home = private_home(Path(directory))

            # When: the workflow is installed and both source and installed plists are linted.
            invoke(["--home", str(home), "install"])
            installed = home / "Library/Services/Mnemosyne Capture.workflow/Contents"
            lint = subprocess.run(["/usr/bin/plutil", "-lint", str(source / "Resources/document.wflow"), str(source / "Info.plist"),
                                   str(installed / "Resources/document.wflow"), str(installed / "Info.plist")], capture_output=True)

            # Then: native parsing succeeds and Info.plist has exactly the locked plistlib bytes.
            self.assertEqual(lint.returncode, 0, lint.stderr.decode("utf-8", "replace"))
            expected_info = {"CFBundleDevelopmentRegion": "en_US", "CFBundleIdentifier": "com.99duuk.mnemosyne.capture",
                             "CFBundleName": "Mnemosyne Capture", "CFBundleShortVersionString": "1.0",
                             "NSServices": [{"NSMenuItem": {"default": "Mnemosyne Capture"}, "NSMessage": "runWorkflowAsService"}]}
            info_bytes = plistlib.dumps(expected_info, fmt=plistlib.FMT_XML, sort_keys=True)
            self.assertEqual((source / "Info.plist").read_bytes(), info_bytes)
            self.assertEqual((installed / "Info.plist").read_bytes(), info_bytes)
            manifest = json.loads(((home / "Library/Application Support/Mnemosyne/runtime/current").resolve() / "manifest.json").read_bytes())
            self.assertEqual(manifest["workflow"]["info_plist_sha256"], hashlib.sha256(info_bytes).hexdigest())

    def test_install_resumes_i1_and_i2_without_retargeting(self) -> None:
        # Given: separate stable installs transformed into exact I1 and I2 states.
        for phase in ("I1", "I2"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
                home = private_home(Path(directory))
                invoke(["--home", str(home), "install"])
                root = home / "Library/Application Support/Mnemosyne"
                runtime = root / "runtime"
                workflow = home / "Library/Services/Mnemosyne Capture.workflow"
                if phase == "I1":
                    (runtime / "current").rename(runtime / ".current.installing")
                else:
                    workflow.rename(workflow.with_name(".Mnemosyne Capture.workflow.installing"))

                # When: install resumes the declared transition.
                exit_code, result = invoke(["--home", str(home), "install"])

                # Then: only Stable remains and the target is unchanged.
                self.assertEqual((exit_code, result["code"], result["changed"]), (0, "INSTALLED", True))
                self.assertTrue((runtime / "current").is_symlink())
                self.assertFalse((runtime / ".current.installing").exists())
                self.assertTrue(workflow.is_dir())
                self.assertFalse(workflow.with_name(".Mnemosyne Capture.workflow.installing").exists())

    def test_cross_home_binding_and_hardlinked_manifest_fail_without_mutation(self) -> None:
        # Given: H1 owns a shared data root, H2 is distinct, and the manifest has an outside hardlink.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home1 = private_home(base / "one")
            home2 = private_home(base / "two")
            data_root = base / "data"
            invoke(["--home", str(home1), "--data-root", str(data_root), "install"])
            wrong = invoke(["--home", str(home2), "--data-root", str(data_root), "install"])
            release = (data_root / "runtime/current").resolve()
            manifest = release / "manifest.json"
            alias = base / "manifest-alias"
            os.link(manifest, alias)
            before = alias.read_bytes()

            # When: wrong-home install and same-home reinstall are attempted.
            tampered = invoke(["--home", str(home1), "--data-root", str(data_root), "install"])

            # Then: binding precedence and hardlink refusal are exact and neither alias changes.
            self.assertEqual((wrong[0], wrong[1]["code"], wrong[1]["changed"]), (1, "INVALID_PATH", False))
            self.assertEqual((tampered[0], tampered[1]["code"], tampered[1]["changed"]), (1, "RUNTIME_TAMPERED", False))
            self.assertEqual(alias.read_bytes(), before)

    def test_neutral_uninstall_preserves_unlisted_data(self) -> None:
        # Given: an installed root with an unrelated private capture sentinel.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            home = private_home(Path(directory))
            invoke(["--home", str(home), "install"])
            root = home / "Library/Application Support/Mnemosyne"
            sentinel = root / "captures/sentinel"
            sentinel.parent.mkdir(mode=0o700)
            sentinel.write_bytes(b"preserve")
            sentinel.chmod(0o600)

            # When: uninstall completes and is repeated on clean scaffolding.
            first = invoke(["--home", str(home), "uninstall"])
            second = invoke(["--home", str(home), "uninstall"])

            # Then: active ownership changes once, clean rerun does not, and captures survive.
            self.assertEqual((first[1]["code"], first[1]["changed"]), ("UNINSTALLED", True))
            self.assertEqual((second[1]["code"], second[1]["changed"]), ("UNINSTALLED", False))
            self.assertEqual(sentinel.read_bytes(), b"preserve")

    def test_doctor_scans_export_and_skips_live_bridge_without_runtime(self) -> None:
        # Given: one installed root with a stale zero-revision export and one clean uninstalled home.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            installed_home = private_home(base / "installed")
            clean_home = private_home(base / "clean")
            invoke(["--home", str(installed_home), "install"])
            export = installed_home / "Library/Application Support/Mnemosyne/posts.jsonl"
            export.write_bytes(b"stale")
            export.chmod(0o600)

            # When: static doctor scans bytes and live doctor sees no runtime.
            static = invoke(["--home", str(installed_home), "doctor", "--json"])
            with patch.object(Bridge, "snapshot") as snapshot:
                live = invoke(["--home", str(clean_home), "doctor", "--live"])

            # Then: stale export is a real failure and runtime dependency makes zero bridge calls.
            static_checks = {item["name"]: item for item in static[1]["checks"]}
            live_checks = {item["name"]: item for item in live[1]["checks"]}
            self.assertEqual((static[0], static[1]["code"], static_checks["export"]),
                             (1, "NOT_READY", {"name": "export", "status": "FAIL", "code": "EXPORT_STALE"}))
            self.assertEqual((live_checks["apple_events"]["code"], live_checks["javascript"]["code"],
                              live_checks["safari_tab"]["code"]),
                             ("APPLE_EVENTS_NOT_CHECKED", "JAVASCRIPT_NOT_CHECKED", "SAFARI_TAB_NOT_CHECKED"))
            snapshot.assert_not_called()

    def test_uninstall_resumes_after_release_cursor_fault(self) -> None:
        # Given: a stable install and a one-shot unlink fault at the first release artifact.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            home = private_home(Path(directory))
            invoke(["--home", str(home), "install"])
            original_unlink = Path.unlink
            faulted = False

            def fault_once(path: Path, missing_ok: bool = False) -> None:
                nonlocal faulted
                if path.name == "capture.scpt" and not faulted:
                    faulted = True
                    raise OSError
                original_unlink(path, missing_ok=missing_ok)

            # When: uninstall is interrupted after journal publication and then retried.
            with patch("mnemosyne_capture.uninstall.Path.unlink", new=fault_once):
                interrupted = invoke(["--home", str(home), "uninstall"])
            resumed = invoke(["--home", str(home), "uninstall"])

            # Then: the fault is changed WRITE_FAILED and the exact journal cursor reaches clean.
            runtime = home / "Library/Application Support/Mnemosyne/runtime"
            self.assertEqual((interrupted[0], interrupted[1]["code"], interrupted[1]["changed"]),
                             (1, "WRITE_FAILED", True))
            self.assertEqual((resumed[0], resumed[1]["code"], resumed[1]["changed"]), (0, "UNINSTALLED", True))
            self.assertFalse((runtime / ".uninstall-plan.json").exists())

    def test_static_doctor_is_read_only_when_directory_fsync_is_denied(self) -> None:
        # Given: a stable install and an environment that denies every directory fsync.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            home = private_home(Path(directory))
            invoke(["--home", str(home), "install"])

            # When: static doctor runs through its read-only shared-lock path.
            with patch("mnemosyne_capture.store.os.fsync", side_effect=OSError):
                diagnosed = invoke(["--home", str(home), "doctor", "--json"])

            # Then: it remains READY because diagnosis performs no mutation fsync.
            self.assertEqual((diagnosed[0], diagnosed[1]["code"]), (0, "READY"))

    def test_prefix_writer_matrix_accepts_every_owner_prefix_and_rejects_peers_hardlinks(self) -> None:
        # Given: trusted owner bytes and one private destination per exact prefix length.
        trusted = OWNER_BYTES
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            base.chmod(0o700)

            # When/Then: every possible prefix is resumed to the exact trusted final bytes.
            for length in range(len(trusted) + 1):
                target = base / f"owner-{length}.json"
                writing = target.with_name(f"{target.name}.writing")
                writing.write_bytes(trusted[:length])
                writing.chmod(0o600)
                _resume_file(target, trusted)
                self.assertEqual(target.read_bytes(), trusted)

            # When/Then: wrong prefixes, peer collisions, and hardlinked writers are immutable tamper.
            for shape in ("wrong", "peer", "hardlink"):
                with self.subTest(shape=shape):
                    target = base / f"{shape}.json"
                    writing = target.with_name(f"{target.name}.writing")
                    writing.write_bytes(b"wrong" if shape == "wrong" else trusted[:1])
                    writing.chmod(0o600)
                    if shape == "peer":
                        target.write_bytes(trusted)
                        target.chmod(0o600)
                    if shape == "hardlink":
                        os.link(writing, base / "writer-alias")
                    before = writing.read_bytes()
                    with self.assertRaises(ArtifactTamperedError):
                        _resume_file(target, trusted)
                    self.assertEqual(writing.read_bytes(), before)
                    (base / "writer-alias").unlink(missing_ok=True)

    def test_uninstall_a_to_f_fault_cursor_table_resumes_and_rejects_phase_gaps(self) -> None:
        # Given: independently installed homes and one injected fault at each A-F deletion class.
        fault_names = ("Mnemosyne Capture.workflow", "current", ".current.uninstalling", "capture.scpt",
                       "extract-current-page.js", "mnemosyne.pyz", "manifest.json", "document.wflow",
                       "Info.plist", "mnemosyne-owner.json", "Resources", "Contents",
                       ".Mnemosyne Capture.workflow.uninstalling", ".uninstall-plan.json")
        for name in fault_names:
            with self.subTest(boundary=name), tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
                home = private_home(Path(directory))
                invoke(["--home", str(home), "install"])
                original_rename = Path.rename
                original_unlink = Path.unlink
                original_rmdir = Path.rmdir
                faulted = False

                def maybe_fault(path: Path) -> None:
                    nonlocal faulted
                    if path.name == name and not faulted:
                        faulted = True
                        raise OSError

                def rename(path: Path, target: Path) -> Path:
                    maybe_fault(path)
                    return original_rename(path, target)

                def unlink(path: Path, missing_ok: bool = False) -> None:
                    maybe_fault(path)
                    original_unlink(path, missing_ok=missing_ok)

                def rmdir(path: Path) -> None:
                    maybe_fault(path)
                    original_rmdir(path)

                with patch("mnemosyne_capture.uninstall.Path.rename", new=rename), \
                     patch("mnemosyne_capture.uninstall.Path.unlink", new=unlink), \
                     patch("mnemosyne_capture.uninstall.Path.rmdir", new=rmdir):
                    interrupted = invoke(["--home", str(home), "uninstall"])
                resumed = invoke(["--home", str(home), "uninstall"])
                self.assertTrue(faulted, name)
                self.assertEqual((interrupted[1]["code"], interrupted[1]["changed"]), ("WRITE_FAILED", True))
                self.assertEqual((resumed[0], resumed[1]["code"], resumed[1]["changed"]),
                                 (0, "UNINSTALLED", True))

        # Given/When/Then: a durable plan plus writing peer and an unlisted release reject before deletion.
        for invalid in ("plan-plus-writing", "unlisted-release", "phase-gap"):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
                home = private_home(Path(directory))
                invoke(["--home", str(home), "install"])
                runtime = home / "Library/Application Support/Mnemosyne/runtime"
                with patch("mnemosyne_capture.uninstall.Path.rename", side_effect=OSError):
                    invoke(["--home", str(home), "uninstall"])
                plan = runtime / ".uninstall-plan.json"
                if invalid == "plan-plus-writing":
                    writing = runtime / ".uninstall-plan.json.writing"
                    writing.write_bytes(plan.read_bytes()[:1])
                    writing.chmod(0o600)
                elif invalid == "unlisted-release":
                    (runtime / "releases/unlisted").mkdir(mode=0o700)
                else:
                    (runtime / "current").unlink()
                before = plan.read_bytes()
                refused = invoke(["--home", str(home), "uninstall"])
                self.assertEqual((refused[1]["code"], refused[1]["changed"]), ("RUNTIME_TAMPERED", False))
                self.assertEqual(plan.read_bytes(), before)

    def test_path_overlap_hardlink_and_cross_root_refusal_table(self) -> None:
        # Given: private homes and aliases spanning Services, checkout, and owned artifacts.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home = private_home(base / "home")
            candidates = (home / "Library/Services", home / "Library", home / "Library/Services/child",
                          Path("/Users/tars/Documents/workspace/mnemosyne"),
                          Path("/Users/tars/Documents/workspace/mnemosyne/.omo/evidence"))
            for candidate in candidates:
                with self.subTest(candidate=str(candidate)):
                    result = invoke(["--home", str(home), "--data-root", str(candidate), "install"])
                    self.assertEqual((result[0], result[1]["code"], result[1]["changed"]),
                                     (1, "INVALID_PATH", False))

            data = base / "data"
            invoke(["--home", str(home), "--data-root", str(data), "install"])
            release = (data / "runtime/current").resolve()
            for name in ("capture.scpt", "extract-current-page.js", "mnemosyne.pyz", "manifest.json"):
                alias = base / f"alias-{name}"
                os.link(release / name, alias)
                refused = invoke(["--home", str(home), "--data-root", str(data), "install"])
                self.assertEqual((refused[1]["code"], refused[1]["changed"]), ("RUNTIME_TAMPERED", False))
                alias.unlink()

    def test_services_and_data_shared_locks_are_process_barriers(self) -> None:
        # Given: an exclusive Services lock held while a different-root installer starts.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home = private_home(base)
            data = base / "data"
            descriptor = os.open(home / "Library/Services", os.O_RDONLY | os.O_DIRECTORY)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            command = [os.sys.executable, "-m", "mnemosyne_capture", "--home", str(home),
                       "--data-root", str(data), "install"]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, env={**os.environ,
                                       "PYTHONPATH": "/Users/tars/Documents/workspace/mnemosyne/capture"})
            time.sleep(0.1)
            self.assertIsNone(process.poll())
            self.assertFalse(data.exists())
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
            stdout, _ = process.communicate(timeout=20)
            self.assertEqual((process.returncode, json.loads(stdout)["code"]), (0, "INSTALLED"))

            # Given/When/Then: a held data lock similarly blocks static doctor until release.
            lock = os.open(data / ".commit.lock", os.O_RDONLY)
            fcntl.flock(lock, fcntl.LOCK_EX)
            doctor_command = [*command[:-1], "doctor", "--json"]
            diagnosed = subprocess.Popen(doctor_command, stdout=subprocess.PIPE, env={**os.environ,
                                         "PYTHONPATH": "/Users/tars/Documents/workspace/mnemosyne/capture"})
            time.sleep(0.1)
            self.assertIsNone(diagnosed.poll())
            fcntl.flock(lock, fcntl.LOCK_UN)
            os.close(lock)
            stdout, _ = diagnosed.communicate(timeout=20)
            self.assertEqual((diagnosed.returncode, json.loads(stdout)["code"]), (0, "READY"))

    def test_static_doctor_lifecycle_and_python_precedence_tables(self) -> None:
        # Given: exact clean, Stable, missing-workflow, I1, I2, and uninstall phase states.
        states = ("clean", "stable", "missing-workflow", "I1", "I2", "uninstall-A", "uninstall-B")
        for state in states:
            with self.subTest(state=state), tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
                home = private_home(Path(directory))
                if state != "clean":
                    invoke(["--home", str(home), "install"])
                    runtime = home / "Library/Application Support/Mnemosyne/runtime"
                    workflow = home / "Library/Services/Mnemosyne Capture.workflow"
                    if state == "missing-workflow":
                        workflow.rename(workflow.with_name("saved"))
                    elif state == "I1":
                        (runtime / "current").rename(runtime / ".current.installing")
                        workflow.rename(workflow.with_name("saved"))
                    elif state == "I2":
                        workflow.rename(workflow.with_name(".Mnemosyne Capture.workflow.installing"))
                    elif state.startswith("uninstall"):
                        fault = "Mnemosyne Capture.workflow" if state == "uninstall-A" else "current"
                        original = Path.rename

                        def stop(path: Path, target: Path) -> Path:
                            if path.name == fault:
                                raise OSError
                            return original(path, target)

                        with patch("mnemosyne_capture.uninstall.Path.rename", new=stop):
                            invoke(["--home", str(home), "uninstall"])
                result = invoke(["--home", str(home), "doctor", "--json"])
                checks = {item["name"]: (item["status"], item["code"]) for item in result[1]["checks"]}
                expected = {
                    "clean": (("FAIL", "RUNTIME_MISSING"), ("FAIL", "WORKFLOW_MISSING")),
                    "stable": (("PASS", "RUNTIME_OK"), ("PASS", "WORKFLOW_OK")),
                    "missing-workflow": (("PASS", "RUNTIME_OK"), ("FAIL", "WORKFLOW_MISSING")),
                    "I1": (("FAIL", "RUNTIME_INCOMPLETE"), ("FAIL", "WORKFLOW_INCOMPLETE")),
                    "I2": (("FAIL", "RUNTIME_INCOMPLETE"), ("FAIL", "WORKFLOW_INCOMPLETE")),
                    "uninstall-A": (("FAIL", "RUNTIME_INCOMPLETE"), ("PASS", "WORKFLOW_OK")),
                    "uninstall-B": (("FAIL", "RUNTIME_INCOMPLETE"), ("FAIL", "WORKFLOW_INCOMPLETE")),
                }[state]
                self.assertEqual((checks["runtime"], checks["workflow"]), expected)

        # Given/When/Then: Python check precedence is unavailable, missing, changed, version mismatch, then pass.
        missing = _python_check({"python_realpath": "/private/tmp/mnemosyne-no-such-python"})
        with patch("mnemosyne_capture.doctor.sys_executable", return_value="/different"):
            changed = _python_check({"python_realpath": os.path.realpath(os.sys.executable)})
        with patch("mnemosyne_capture.doctor.sys_version", return_value=(3, 13)):
            mismatch = _python_check({"python_realpath": os.path.realpath(os.sys.executable)})
        passed = _python_check({"python_realpath": os.path.realpath(os.sys.executable)})
        self.assertEqual((missing.code, changed.code, mismatch.code, passed.code),
                         ("PYTHON_MISSING", "PYTHON_CHANGED", "PYTHON_VERSION_MISMATCH", "PYTHON_OK"))

    def test_parent_inode_drift_before_and_after_mutation_is_bounded(self) -> None:
        # Given: a bound private home whose Services inode is replaced before mutation.
        for changed in (False, True):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
                home = private_home(Path(directory))
                paths = bind_paths(home, None)
                services = home / "Library/Services"
                saved = home / "Library/Services.saved"
                services.rename(saved)
                services.mkdir(mode=0o700)
                sentinel = services / "replacement-sentinel"
                sentinel.write_bytes(b"replacement")

                # When/Then: witness revalidation reports the exact pre/post class and never touches replacement.
                with self.assertRaises(PathDriftError) as raised:
                    _require_paths(paths, changed)
                self.assertEqual(raised.exception.changed, changed)
                self.assertEqual(sentinel.read_bytes(), b"replacement")

    def test_install_sync_fault_boundary_table_is_recoverable(self) -> None:
        # Given: the number of actual install durability boundaries from a measured synthetic install.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            home = private_home(Path(directory))
            original_sync = __import__("mnemosyne_capture.install_artifacts", fromlist=["sync"]).sync
            calls = 0

            def count(path: Path) -> None:
                nonlocal calls
                calls += 1
                original_sync(path)

            with patch("mnemosyne_capture.install_artifacts.sync", new=count), \
                 patch("mnemosyne_capture.install.sync", new=count):
                invoke(["--home", str(home), "install"])

        # When/Then: each injected sync interruption yields a bounded failure and a reinstall reaches Stable.
        for boundary in range(1, calls + 1):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
                home = private_home(Path(directory))
                seen = 0

                def fault(path: Path) -> None:
                    nonlocal seen
                    seen += 1
                    if seen == boundary:
                        raise OSError
                    original_sync(path)

                with patch("mnemosyne_capture.install_artifacts.sync", new=fault), \
                     patch("mnemosyne_capture.install.sync", new=fault):
                    interrupted = invoke(["--home", str(home), "install"])
                resumed = invoke(["--home", str(home), "install"])
                self.assertEqual((interrupted[1]["code"], interrupted[1]["changed"]),
                                 ("WRITE_FAILED", True))
                self.assertEqual((resumed[0], resumed[1]["code"]), (0, "INSTALLED"))

    def test_release_and_workflow_writer_prefix_states_resume_end_to_end(self) -> None:
        # Given: one trusted built release and each release/workflow writer stopped at a strict prefix.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home = private_home(base)
            built = build_release(bind_paths(home, base / "binding-root"))
            release_files = (*built.files, ("manifest.json", built.manifest))
            for index, (name, content) in enumerate(release_files):
                with self.subTest(release_writer=name):
                    runtime = base / f"release-{index}" / "runtime"
                    releases = runtime / "releases"
                    releases.mkdir(parents=True, mode=0o700)
                    runtime.chmod(0o700)
                    stage = runtime / f".release-stage-{built.release_id}"
                    bundle = stage / "release"
                    bundle.mkdir(parents=True, mode=0o700)
                    stage.chmod(0o700)
                    owner = canonical({"owner": OWNER, "release_id": built.release_id,
                                       "schema": "mnemosyne.release-stage/v1"})
                    (stage / "owner.json").write_bytes(owner)
                    (stage / "owner.json").chmod(0o600)
                    for prior_name, prior_content in release_files[:index]:
                        (bundle / prior_name).write_bytes(prior_content)
                        (bundle / prior_name).chmod(0o600)
                    writing = bundle / f"{name}.writing"
                    writing.write_bytes(content[:len(content) // 2])
                    writing.chmod(0o600)
                    final = releases / built.release_id
                    publish_release(runtime, releases, final, built)
                    self.assertEqual((final / name).read_bytes(), content)

            workflow_files = (("Contents/Resources/document.wflow", built.document),
                              ("Contents/Info.plist", built.info),
                              ("Contents/Resources/mnemosyne-owner.json", OWNER_BYTES))
            for index, (relative, content) in enumerate(workflow_files):
                with self.subTest(workflow_writer=relative):
                    stage = base / f"workflow-{index}"
                    target = stage / relative
                    target.parent.mkdir(parents=True, mode=0o700)
                    stage.chmod(0o700)
                    (stage / "Contents").chmod(0o700)
                    if (stage / "Contents/Resources").exists():
                        (stage / "Contents/Resources").chmod(0o700)
                    writing = target.with_name(f"{target.name}.writing")
                    writing.write_bytes(content[:len(content) // 2])
                    writing.chmod(0o600)
                    publish_workflow_stage(stage, built)
                    self.assertEqual(target.read_bytes(), content)

    def test_install_recovery_uninstall_cross_root_and_hardlink_tables(self) -> None:
        # Given/When/Then: uninstall refuses each valid install transition until reinstall reaches Stable.
        for state in ("release-stage", "I1", "I2"):
            with self.subTest(state=state), tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
                home = private_home(Path(directory))
                invoke(["--home", str(home), "install"])
                root = home / "Library/Application Support/Mnemosyne"
                runtime = root / "runtime"
                workflow = home / "Library/Services/Mnemosyne Capture.workflow"
                if state == "release-stage":
                    release_id = (runtime / "current").resolve().name
                    stage = runtime / f".release-stage-{release_id}"
                    stage.mkdir(mode=0o700)
                elif state == "I1":
                    (runtime / "current").rename(runtime / ".current.installing")
                else:
                    workflow.rename(workflow.with_name(".Mnemosyne Capture.workflow.installing"))
                refused = invoke(["--home", str(home), "uninstall"])
                resumed = invoke(["--home", str(home), "install"])
                removed = invoke(["--home", str(home), "uninstall"])
                self.assertEqual((refused[1]["code"], refused[1]["changed"]),
                                 ("INSTALL_IN_PROGRESS", False))
                self.assertEqual((resumed[0], removed[0]), (0, 0))

        # Given: H owns D1 and its reserved workflow; D2 cannot claim or clean that home.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home = private_home(base)
            data1 = base / "data-one"
            data2 = base / "data-two"
            invoke(["--home", str(home), "--data-root", str(data1), "install"])
            install2 = invoke(["--home", str(home), "--data-root", str(data2), "install"])
            uninstall2 = invoke(["--home", str(home), "--data-root", str(data2), "uninstall"])
            self.assertEqual((install2[1]["code"], uninstall2[1]["code"]),
                             ("FOREIGN_WORKFLOW", "RUNTIME_TAMPERED"))
            self.assertFalse(data2.exists())

        # Given/When/Then: hardlinks across every workflow and plan class preserve both aliases on refusal.
        for relative in ("Contents/Resources/document.wflow", "Contents/Info.plist",
                         "Contents/Resources/mnemosyne-owner.json"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
                base = Path(directory)
                home = private_home(base)
                invoke(["--home", str(home), "install"])
                artifact = home / "Library/Services/Mnemosyne Capture.workflow" / relative
                alias = base / "workflow-alias"
                os.link(artifact, alias)
                before = alias.read_bytes()
                refused = invoke(["--home", str(home), "install"])
                self.assertEqual((refused[1]["code"], refused[1]["changed"]),
                                 ("RUNTIME_TAMPERED", False))
                self.assertEqual((artifact.read_bytes(), alias.read_bytes()), (before, before))

        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home = private_home(base)
            invoke(["--home", str(home), "install"])
            runtime = home / "Library/Application Support/Mnemosyne/runtime"
            writing = runtime / ".uninstall-plan.json.writing"
            writing.write_bytes(b"{")
            writing.chmod(0o600)
            alias = base / "plan-writer-alias"
            os.link(writing, alias)
            refused = invoke(["--home", str(home), "uninstall"])
            self.assertEqual((refused[1]["code"], refused[1]["changed"]),
                             ("RUNTIME_TAMPERED", False))
            self.assertEqual((writing.read_bytes(), alias.read_bytes()), (b"{", b"{"))

    def test_live_doctor_snapshot_and_smoke_dependency_matrix(self) -> None:
        # Given: a stable runtime and each permitted snapshot/smoke outcome.
        cases = (
            ("success", None, None, ("APPLE_EVENTS_OK", "JAVASCRIPT_OK", "SAFARI_READY"), 0),
            ("no-tab", BridgeErrorCode.NO_SAFARI_TAB, None,
             ("APPLE_EVENTS_OK", "JAVASCRIPT_NOT_CHECKED", "NO_SAFARI_TAB"), 2),
            ("frontmost", BridgeErrorCode.SAFARI_NOT_FRONTMOST, None,
             ("APPLE_EVENTS_OK", "JAVASCRIPT_NOT_CHECKED", "SAFARI_NOT_FRONTMOST"), 2),
            ("denied", BridgeErrorCode.APPLE_EVENTS_DENIED, None,
             ("APPLE_EVENTS_DENIED", "JAVASCRIPT_NOT_CHECKED", "SAFARI_TAB_NOT_CHECKED"), 2),
            ("snapshot-timeout", BridgeErrorCode.BRIDGE_TIMEOUT, None,
             ("BRIDGE_TIMEOUT", "JAVASCRIPT_NOT_CHECKED", "SAFARI_TAB_NOT_CHECKED"), 1),
            ("javascript", None, BridgeErrorCode.JAVASCRIPT_UNAVAILABLE,
             ("APPLE_EVENTS_OK", "JAVASCRIPT_DISABLED", "SAFARI_READY"), 2),
            ("tab-change", None, BridgeErrorCode.TAB_CHANGED,
             ("APPLE_EVENTS_OK", "JAVASCRIPT_NOT_CHECKED", "TAB_CHANGED"), 2),
            ("smoke-timeout", None, BridgeErrorCode.BRIDGE_TIMEOUT,
             ("APPLE_EVENTS_OK", "BRIDGE_TIMEOUT", "SAFARI_READY"), 1),
            ("smoke-blocked", None, BridgeErrorCode.SCRIPT_EXECUTION_BLOCKED,
             ("APPLE_EVENTS_OK", "SCRIPT_EXECUTION_BLOCKED", "SAFARI_READY"), 1),
        )
        for name, snapshot_error, smoke_error, expected, expected_exit in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
                home = private_home(Path(directory))
                invoke(["--home", str(home), "install"])
                snapshot_effect = (BridgeError(snapshot_error) if snapshot_error is not None
                                   else SnapshotResult("https://blog.naver.com/example/123"))
                smoke_effect = BridgeError(smoke_error) if smoke_error is not None else SmokeResult("MNEMOSYNE_JS_OK")
                with patch.object(Bridge, "snapshot", side_effect=(snapshot_effect if isinstance(snapshot_effect, Exception) else None),
                                  return_value=(None if isinstance(snapshot_effect, Exception) else snapshot_effect)), \
                     patch.object(Bridge, "smoke", side_effect=(smoke_effect if isinstance(smoke_effect, Exception) else None),
                                  return_value=(None if isinstance(smoke_effect, Exception) else smoke_effect)):
                    result = invoke(["--home", str(home), "doctor", "--live"])
                checks = {item["name"]: item["code"] for item in result[1]["checks"]}
                self.assertEqual((checks["apple_events"], checks["javascript"], checks["safari_tab"]), expected)
                self.assertEqual(result[0], expected_exit)

    def test_doctor_lock_appearance_and_lockless_nonempty_precedence(self) -> None:
        # Given: an empty root where a valid lock appears during the unlocked observation.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home = private_home(base)
            data = base / "data"
            data.mkdir(mode=0o700)
            paths = bind_paths(home, data)
            original = doctor_module._evaluate
            calls = 0

            def appear(bound, store, live):
                nonlocal calls
                calls += 1
                result = original(bound, store, live)
                if calls == 1:
                    lock = data / ".commit.lock"
                    lock.write_bytes(b"")
                    lock.chmod(0o600)
                return result

            # When/Then: doctor notices the lock and recomputes under the shared data lock.
            with patch("mnemosyne_capture.doctor._evaluate", new=appear):
                result = doctor_module.doctor(paths)
            self.assertEqual((calls, result.code), (2, "NOT_READY"))

        # Given/When/Then: nonempty lockless data fails closed without reading hostile child bytes.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home = private_home(base)
            data = base / "data"
            data.mkdir(mode=0o700)
            hostile = data / "hostile"
            hostile.symlink_to("/dev/null")
            result = invoke(["--home", str(home), "--data-root", str(data), "doctor", "--json"])
            self.assertEqual((result[0], result[1]["code"]), (1, "NOT_READY"))
            self.assertTrue(hostile.is_symlink())

    def test_uninstall_rejects_two_partial_releases_without_mutation(self) -> None:
        # Given: a durable phase-D plan with two separately valid releases both made partial.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home1 = private_home(base / "one")
            home2 = private_home(base / "two")
            data = base / "data"
            paths1 = bind_paths(home1, data)
            paths2 = bind_paths(home2, data)
            built1 = build_release(paths1)
            built2 = build_release(paths2)
            runtime = data / "runtime"
            releases = runtime / "releases"
            releases.mkdir(parents=True, mode=0o700)
            data.chmod(0o700)
            runtime.chmod(0o700)
            lock = data / ".commit.lock"
            lock.write_bytes(b"")
            lock.chmod(0o600)
            hashes = {}
            for built in (built1, built2):
                release = releases / built.release_id
                release.mkdir(mode=0o700)
                for name, content in (*built.files, ("manifest.json", built.manifest)):
                    (release / name).write_bytes(content)
                    (release / name).chmod(0o600)
                (release / "capture.scpt").unlink()
                hashes[built.release_id] = hashlib.sha256(built.manifest).hexdigest()
            tombstone = paths1.workflow_tombstone
            publish_workflow_stage(tombstone, built1)
            manifest = json.loads(built1.manifest)
            plan = {"schema": "mnemosyne.uninstall/v1", "owner": OWNER,
                    "workflow": manifest["workflow"], "current_target": f"releases/{built1.release_id}",
                    "releases": hashes}
            plan_path = runtime / ".uninstall-plan.json"
            plan_path.write_bytes(canonical(plan))
            plan_path.chmod(0o600)
            before = plan_path.read_bytes()

            # When/Then: uninstall rejects before deleting either cursor or the plan.
            refused = invoke(["--home", str(home1), "--data-root", str(data), "uninstall"])
            self.assertEqual((refused[1]["code"], refused[1]["changed"]),
                             ("RUNTIME_TAMPERED", False))
            self.assertEqual(plan_path.read_bytes(), before)
            self.assertTrue(all((releases / built.release_id / "extract-current-page.js").exists()
                                for built in (built1, built2)))

    def test_static_doctor_complete_lifecycle_cursor_table_and_precedence(self) -> None:
        # Given: every additional exact lifecycle row omitted by the initial gate submission.
        states = ("neutral", "release-cleanup", "I1-final", "I1-stage", "I2", "plan-writing",
                  "uninstall-C", "uninstall-D", "uninstall-E", "uninstall-F")
        for state in states:
            with self.subTest(state=state), tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
                home = private_home(Path(directory))
                invoke(["--home", str(home), "install"])
                runtime = home / "Library/Application Support/Mnemosyne/runtime"
                workflow = home / "Library/Services/Mnemosyne Capture.workflow"
                release_id = (runtime / "current").resolve().name
                if state == "neutral":
                    (runtime / "current").unlink()
                    workflow.rename(workflow.with_name("saved-neutral"))
                elif state == "release-cleanup":
                    stage = runtime / f".release-stage-{release_id}"
                    stage.mkdir(mode=0o700)
                elif state == "I1-final":
                    (runtime / "current").rename(runtime / ".current.installing")
                elif state == "I1-stage":
                    (runtime / "current").rename(runtime / ".current.installing")
                    workflow.rename(workflow.with_name(".Mnemosyne Capture.workflow.installing"))
                elif state == "I2":
                    workflow.rename(workflow.with_name(".Mnemosyne Capture.workflow.installing"))
                elif state == "plan-writing":
                    with patch("mnemosyne_capture.install_artifacts.os.replace", side_effect=OSError):
                        invoke(["--home", str(home), "uninstall"])
                else:
                    fault_name = {"uninstall-C": ".current.uninstalling", "uninstall-D": "capture.scpt",
                                  "uninstall-E": "document.wflow", "uninstall-F": ".uninstall-plan.json"}[state]
                    original_unlink = Path.unlink

                    def stop(path: Path, missing_ok: bool = False) -> None:
                        if path.name == fault_name:
                            raise OSError
                        original_unlink(path, missing_ok=missing_ok)

                    with patch("mnemosyne_capture.uninstall.Path.unlink", new=stop):
                        invoke(["--home", str(home), "uninstall"])
                result = invoke(["--home", str(home), "doctor", "--json"])
                checks = {item["name"]: (item["status"], item["code"]) for item in result[1]["checks"]}
                if state == "neutral":
                    expected = (("FAIL", "RUNTIME_MISSING"), ("FAIL", "WORKFLOW_MISSING"))
                elif state in ("release-cleanup", "I1-final"):
                    expected = (("FAIL", "RUNTIME_INCOMPLETE"), ("PASS", "WORKFLOW_OK"))
                elif state == "plan-writing":
                    expected = (("FAIL", "RUNTIME_INCOMPLETE"), ("PASS", "WORKFLOW_OK"))
                else:
                    expected = (("FAIL", "RUNTIME_INCOMPLETE"), ("FAIL", "WORKFLOW_INCOMPLETE"))
                self.assertEqual((checks["runtime"], checks["workflow"]), expected)
                self.assertEqual(checks["python"], ("FAIL", "PYTHON_EXPECTATION_UNAVAILABLE"))

        # Given/When/Then: unverified workflow wins FOREIGN while owned drift is runtime tamper.
        for owned in (False, True):
            with self.subTest(owned=owned), tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
                home = private_home(Path(directory))
                if owned:
                    invoke(["--home", str(home), "install"])
                    document = home / "Library/Services/Mnemosyne Capture.workflow/Contents/Resources/document.wflow"
                    document.write_bytes(b"drift")
                    document.chmod(0o600)
                else:
                    (home / "Library/Services/Mnemosyne Capture.workflow").mkdir(mode=0o700)
                result = invoke(["--home", str(home), "doctor", "--json"])
                checks = {item["name"]: item["code"] for item in result[1]["checks"]}
                self.assertEqual(checks["workflow"], "RUNTIME_TAMPERED" if owned else "FOREIGN_WORKFLOW")

    def test_every_trusted_writer_byte_prefix_and_invalid_file_shape_table(self) -> None:
        # Given: trusted bytes for every release, workflow, owner, and uninstall writer class.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home = private_home(base)
            data = base / "data"
            paths = bind_paths(home, data)
            built = build_release(paths)
            owner = canonical({"owner": OWNER, "release_id": built.release_id,
                               "schema": "mnemosyne.release-stage/v1"})
            invoke(["--home", str(home), "--data-root", str(data), "install"])
            runtime = data / "runtime"
            original_replace = os.replace

            def stop_plan(source, target, *args, **kwargs):
                if str(target).endswith(".uninstall-plan.json"):
                    raise OSError
                return original_replace(source, target, *args, **kwargs)

            with patch("mnemosyne_capture.install_artifacts.os.replace", new=stop_plan):
                invoke(["--home", str(home), "--data-root", str(data), "uninstall"])
            plan = (runtime / ".uninstall-plan.json.writing").read_bytes()
            classes = dict((*built.files, ("manifest.json", built.manifest),
                            ("release-owner.json", owner), ("document.wflow", built.document),
                            ("Info.plist", built.info), ("workflow-owner.json", OWNER_BYTES),
                            ("uninstall-plan.json", plan)))

            # When/Then: every byte boundary is accepted, while trailing/wrong bytes are rejected.
            for name, trusted in classes.items():
                with self.subTest(writer=name):
                    self.assertTrue(all(valid_prefix(trusted, trusted[:length])
                                        for length in range(len(trusted) + 1)))
                    self.assertFalse(valid_prefix(trusted, trusted + b"x"))
                    wrong = (b"x" + trusted[1:]) if trusted else b"x"
                    self.assertFalse(valid_prefix(trusted, wrong))

            # Given/When/Then: every invalid filesystem class is refused without changing the alias bytes.
            trusted = OWNER_BYTES
            for shape in ("mode", "owner", "directory", "symlink", "hardlink", "peer"):
                with self.subTest(shape=shape):
                    target = base / f"shape-{shape}"
                    writing = target.with_name(f"{target.name}.writing")
                    if shape == "directory":
                        writing.mkdir(mode=0o700)
                    elif shape == "symlink":
                        writing.symlink_to("/dev/null")
                    else:
                        writing.write_bytes(trusted[:1])
                        writing.chmod(0o644 if shape == "mode" else 0o600)
                    if shape == "hardlink":
                        os.link(writing, base / "shape-alias")
                    if shape == "peer":
                        target.write_bytes(trusted)
                        target.chmod(0o600)
                    owner_context = patch("mnemosyne_capture.install_artifacts.os.getuid",
                                          return_value=os.getuid() + 1) if shape == "owner" else contextlib.nullcontext()
                    with owner_context, self.assertRaises((ArtifactTamperedError, IsADirectoryError, OSError)):
                        _resume_file(target, trusted)
                    (base / "shape-alias").unlink(missing_ok=True)

    def test_bootstrap_changed_path_matrix_and_actual_inode_pause_points(self) -> None:
        # Given/When/Then: each root/lock bootstrap durability fault reports exact winner attribution.
        for boundary in range(1, 5):
            with self.subTest(bootstrap_sync=boundary), tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
                home = private_home(Path(directory))
                original_fsync = os.fsync
                calls = 0

                def fault(descriptor: int) -> None:
                    nonlocal calls
                    calls += 1
                    if calls == boundary:
                        raise OSError
                    original_fsync(descriptor)

                with patch("mnemosyne_capture.store.os.fsync", new=fault):
                    result = invoke(["--home", str(home), "install"])
                self.assertEqual((result[1]["code"], result[1]["changed"]), ("WRITE_FAILED", True))

        # Given: equality and both ancestor directions across every forbidden namespace.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home = private_home(base)
            services = home / "Library/Services"
            workflow = services / "Mnemosyne Capture.workflow"
            candidates = (services, services.parent, services / "child", workflow, workflow / "child",
                          services / ".Mnemosyne Capture.workflow.installing",
                          services / ".Mnemosyne Capture.workflow.uninstalling",
                          Path("/Users/tars/Documents/workspace/mnemosyne"),
                          Path("/Users/tars/Documents/workspace"),
                          Path("/Users/tars/Documents/workspace/mnemosyne/.omo/evidence"))
            before = tuple(sorted(str(path.relative_to(home)) for path in home.rglob("*")))
            for candidate in candidates:
                with self.subTest(path=str(candidate)):
                    result = invoke(["--home", str(home), "--data-root", str(candidate), "install"])
                    self.assertEqual((result[1]["code"], result[1]["changed"]), ("INVALID_PATH", False))
            after = tuple(sorted(str(path.relative_to(home)) for path in home.rglob("*")))
            self.assertEqual(after, before)

            other = private_home(base / "other")
            real = home / "Library/Application Support/real-parent"
            nested = real / "nested"
            nested.mkdir(parents=True, mode=0o700)
            real.chmod(0o700)
            alias = other / "Library/Application Support/cross-home"
            alias.symlink_to(real, target_is_directory=True)
            cross = invoke(["--home", str(other), "--data-root", str(alias / "nested/data"), "install"])
            self.assertEqual((cross[1]["code"], cross[1]["changed"]), ("INVALID_PATH", False))
            self.assertFalse((nested / "data").exists())
            for forbidden in ("'", "\r", "\n"):
                hostile = base / f"hostile{forbidden}root"
                result = invoke(["--home", str(home), "--data-root", str(hostile), "install"])
                self.assertEqual((result[1]["code"], result[1]["changed"]), ("INVALID_PATH", False))
                self.assertFalse(hostile.exists())

        # Given/When/Then: replacing the real parent at install and uninstall guarded boundaries never touches replacement.
        for command in ("install", "uninstall"):
            with self.subTest(command=command), tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
                home = private_home(Path(directory))
                if command == "uninstall":
                    invoke(["--home", str(home), "install"])
                support = home / "Library/Application Support"
                saved = home / "Library/Application Support.saved"
                replaced = False

                def replace_parent() -> None:
                    nonlocal replaced
                    if replaced:
                        return
                    replaced = True
                    support.rename(saved)
                    support.mkdir(mode=0o700)
                    sentinel = support / "replacement-sentinel"
                    sentinel.write_bytes(b"untouched")

                if command == "install":
                    original = __import__("mnemosyne_capture.install", fromlist=["_mkdir_private"])._mkdir_private

                    def pause(path: Path, guard=lambda: None) -> None:
                        if path.name == "runtime":
                            replace_parent()
                        original(path, guard)

                    context = patch("mnemosyne_capture.install._mkdir_private", new=pause)
                else:
                    original_unlink = __import__("mnemosyne_capture.uninstall", fromlist=["_unlink_guarded"])._unlink_guarded

                    def pause(paths, target: Path, changed: bool) -> None:
                        replace_parent()
                        original_unlink(paths, target, changed)

                    context = patch("mnemosyne_capture.uninstall._unlink_guarded", new=pause)
                with context:
                    result = invoke(["--home", str(home), command])
                self.assertEqual((result[1]["code"], result[1]["changed"]), ("WRITE_FAILED", True))
                self.assertEqual((support / "replacement-sentinel").read_bytes(), b"untouched")

    def test_complete_lifecycle_process_barrier_matrix(self) -> None:
        # Given: real competing CLI processes sharing Services or the data lock.
        environment = {**os.environ, "PYTHONPATH": "/Users/tars/Documents/workspace/mnemosyne/capture",
                       "PYTHONPYCACHEPREFIX": "/private/tmp/mnemosyne-qa.JXLDp7/pycache"}

        def command(home: Path, data: Path, action: str, *extra: str) -> list[str]:
            return [os.sys.executable, "-m", "mnemosyne_capture", "--home", str(home),
                    "--data-root", str(data), action, *extra]

        def synthetic_capture_command(home: Path, data: Path) -> list[str]:
            script = "\n".join((
                "import json", "import sys", "from pathlib import Path", "from unittest.mock import patch",
                "from mnemosyne_capture.bridge import Bridge, ExtractResult, SnapshotResult",
                "from mnemosyne_capture.cli import main", "from mnemosyne_capture.payload import CapturePayload",
                'url = "https://blog.naver.com/barrier_fixture/42"',
                'raw = json.dumps({"schema":"mnemosyne.safari-extract/v1","top_document_url":url,'
                '"content_document_url":url,"canonical_url":url,"title":"barrier fixture",'
                '"published_at_raw":"2026. 8. 27.","body":"synthetic no-Safari capture",'
                '"editor_fingerprint":"smarteditor_one","warnings":[],"component_counts":'
                '{"images":0,"tables":0,"embeds":0,"media":0}}).encode()',
                "payload = CapturePayload.from_json_bytes(raw, url)",
                'with patch.object(Bridge,"snapshot",return_value=SnapshotResult(url)), '
                'patch.object(Bridge,"extract",return_value=ExtractResult(url,url,payload)), '
                'patch.object(Bridge,"notify"):',
                '    raise SystemExit(main(["--home",sys.argv[1],"--data-root",sys.argv[2],"capture"],'
                ' capture_script=Path(sys.argv[3]),extractor_script=Path(sys.argv[4])))',
            ))
            release = (data / "runtime/current").resolve()
            return [os.sys.executable, "-c", script, str(home), str(data),
                    str(release / "capture.scpt"), str(release / "extract-current-page.js")]

        # When/Then: install↔install exposes one complete owner and one exact foreign refusal.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home = private_home(base)
            data1, data2 = base / "data1", base / "data2"
            services_fd = os.open(home / "Library/Services", os.O_RDONLY | os.O_DIRECTORY)
            fcntl.flock(services_fd, fcntl.LOCK_EX)
            processes = [subprocess.Popen(command(home, data, "install"), stdout=subprocess.PIPE, env=environment)
                         for data in (data1, data2)]
            time.sleep(0.1)
            self.assertTrue(all(process.poll() is None for process in processes))
            fcntl.flock(services_fd, fcntl.LOCK_UN)
            os.close(services_fd)
            results = [json.loads(process.communicate(timeout=20)[0])["code"] for process in processes]
            self.assertEqual(sorted(results), ["FOREIGN_WORKFLOW", "INSTALLED"])

        # When/Then: install↔uninstall yields only one of the two fully serialized outcomes.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home = private_home(base)
            data1, data2 = base / "data1", base / "data2"
            invoke(["--home", str(home), "--data-root", str(data1), "install"])
            services_fd = os.open(home / "Library/Services", os.O_RDONLY | os.O_DIRECTORY)
            fcntl.flock(services_fd, fcntl.LOCK_EX)
            removed = subprocess.Popen(command(home, data1, "uninstall"), stdout=subprocess.PIPE, env=environment)
            installed = subprocess.Popen(command(home, data2, "install"), stdout=subprocess.PIPE, env=environment)
            time.sleep(0.1)
            self.assertIsNone(removed.poll())
            self.assertIsNone(installed.poll())
            fcntl.flock(services_fd, fcntl.LOCK_UN)
            os.close(services_fd)
            removed_result = json.loads(removed.communicate(timeout=20)[0])
            installed_result = json.loads(installed.communicate(timeout=20)[0])
            self.assertEqual(removed_result["code"], "UNINSTALLED")
            self.assertIn(installed_result["code"], ("INSTALLED", "FOREIGN_WORKFLOW"))

        # When/Then: two uninstalls serialize to changed true followed by unchanged false.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home = private_home(base)
            data = base / "data"
            invoke(["--home", str(home), "--data-root", str(data), "install"])
            services_fd = os.open(home / "Library/Services", os.O_RDONLY | os.O_DIRECTORY)
            fcntl.flock(services_fd, fcntl.LOCK_EX)
            processes = [subprocess.Popen(command(home, data, "uninstall"), stdout=subprocess.PIPE, env=environment)
                         for _ in range(2)]
            time.sleep(0.1)
            self.assertTrue(all(process.poll() is None for process in processes))
            fcntl.flock(services_fd, fcntl.LOCK_UN)
            os.close(services_fd)
            results = [json.loads(process.communicate(timeout=20)[0]) for process in processes]
            self.assertEqual(sorted(result["changed"] for result in results), [False, True])
            self.assertTrue(all(result["code"] == "UNINSTALLED" for result in results))

        # When/Then: a shared-data export and lifecycle command wait on the same lock and both finish cleanly.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home = private_home(base)
            data = base / "data"
            invoke(["--home", str(home), "--data-root", str(data), "install"])
            lock_fd = os.open(data / ".commit.lock", os.O_RDONLY)
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            exported = subprocess.Popen(command(home, data, "export"), stdout=subprocess.PIPE, env=environment)
            removed = subprocess.Popen(command(home, data, "uninstall"), stdout=subprocess.PIPE, env=environment)
            time.sleep(0.1)
            self.assertIsNone(exported.poll())
            self.assertIsNone(removed.poll())
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
            outputs = [json.loads(process.communicate(timeout=20)[0]) for process in (exported, removed)]
            self.assertEqual({result["code"] for result in outputs}, {"EXPORTED", "UNINSTALLED"})

        # When/Then: capture and each lifecycle mutation serialize at the shared data boundary.
        for lifecycle in ("install", "uninstall"):
            with self.subTest(capture_lifecycle=lifecycle), tempfile.TemporaryDirectory(
                    prefix="mnemosyne-install-") as directory:
                base = Path(directory)
                home = private_home(base)
                data = base / "data"
                invoke(["--home", str(home), "--data-root", str(data), "install"])
                lock_fd = os.open(data / ".commit.lock", os.O_RDONLY)
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
                captured = subprocess.Popen(synthetic_capture_command(home, data), stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, env=environment)
                lifecycle_process = subprocess.Popen(command(home, data, lifecycle), stdout=subprocess.PIPE,
                                                     stderr=subprocess.PIPE, env=environment)
                time.sleep(0.1)
                self.assertIsNone(captured.poll())
                self.assertIsNone(lifecycle_process.poll())
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
                capture_stdout, capture_stderr = captured.communicate(timeout=20)
                lifecycle_stdout, lifecycle_stderr = lifecycle_process.communicate(timeout=20)
                self.assertEqual(capture_stderr, b"")
                self.assertEqual(lifecycle_stderr, b"")
                capture_result = json.loads(capture_stdout)
                lifecycle_result = json.loads(lifecycle_stdout)
                self.assertEqual((capture_result["code"], capture_result["changed"]), ("CAPTURED", True))
                expected = ("INSTALLED", False) if lifecycle == "install" else ("UNINSTALLED", True)
                self.assertEqual((lifecycle_result["code"], lifecycle_result["changed"]), expected)

        # When/Then: static and synthetic-live doctor retain both shared locks against every writer.
        for live in (False, True):
            for competitor in ("install", "uninstall", "capture", "export"):
                with self.subTest(doctor_live=live, competitor=competitor), tempfile.TemporaryDirectory(
                        prefix="mnemosyne-install-") as directory:
                    base = Path(directory)
                    home = private_home(base)
                    data = base / "data"
                    invoke(["--home", str(home), "--data-root", str(data), "install"])
                    entered = threading.Event()
                    release = threading.Event()
                    output: list[tuple[int, dict]] = []
                    if live:
                        def smoke(_bridge, _url):
                            entered.set()
                            self.assertTrue(release.wait(5))
                            return SmokeResult("MNEMOSYNE_JS_OK")
                        contexts = (patch.object(Bridge, "snapshot", return_value=SnapshotResult(
                                    "https://blog.naver.com/example/123")), patch.object(Bridge, "smoke", new=smoke))
                    else:
                        original_evaluate = doctor_module._evaluate
                        def evaluate(paths, store, requested_live):
                            entered.set()
                            self.assertTrue(release.wait(5))
                            return original_evaluate(paths, store, requested_live)
                        contexts = (patch("mnemosyne_capture.doctor._evaluate", new=evaluate), contextlib.nullcontext())
                    with contexts[0], contexts[1]:
                        thread = threading.Thread(target=lambda: output.append(invoke(
                            ["--home", str(home), "--data-root", str(data), "doctor",
                             "--live" if live else "--json"])))
                        thread.start()
                        self.assertTrue(entered.wait(5))
                        argv = (synthetic_capture_command(home, data) if competitor == "capture"
                                else command(home, data, competitor))
                        process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                   env=environment)
                        time.sleep(0.1)
                        self.assertIsNone(process.poll())
                        release.set()
                        thread.join(10)
                        competitor_stdout, competitor_stderr = process.communicate(timeout=20)
                    self.assertFalse(thread.is_alive())
                    self.assertEqual(competitor_stderr, b"")
                    result = json.loads(competitor_stdout)
                    expected = {"install": ("INSTALLED", False), "uninstall": ("UNINSTALLED", True),
                                "capture": ("CAPTURED", True), "export": ("EXPORTED", True)}[competitor]
                    self.assertEqual((output[0][0], output[0][1]["code"]), (0, "READY"))
                    self.assertEqual((result["code"], result["changed"]), expected)

    def test_remaining_uninstall_invalid_shapes_and_command_result_rows(self) -> None:
        # Given/When/Then: planless tombstone and owned workflow extras fail before mutation.
        for shape in ("planless-tombstone", "workflow-extra", "hardlinked-plan"):
            with self.subTest(shape=shape), tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
                base = Path(directory)
                home = private_home(base)
                invoke(["--home", str(home), "install"])
                runtime = home / "Library/Application Support/Mnemosyne/runtime"
                workflow = home / "Library/Services/Mnemosyne Capture.workflow"
                original_rename = Path.rename

                def stop_current(path: Path, target: Path) -> Path:
                    if path.name == "current":
                        raise OSError
                    return original_rename(path, target)

                with patch("mnemosyne_capture.uninstall.Path.rename", new=stop_current):
                    invoke(["--home", str(home), "uninstall"])
                plan = runtime / ".uninstall-plan.json"
                tombstone = workflow.with_name(".Mnemosyne Capture.workflow.uninstalling")
                if shape == "planless-tombstone":
                    plan.unlink()
                elif shape == "workflow-extra":
                    extra = tombstone / "Contents/extra"
                    extra.write_bytes(b"extra")
                    extra.chmod(0o600)
                else:
                    os.link(plan, base / "plan-alias")
                before = tuple(sorted(str(path.relative_to(base)) for path in base.rglob("*")))
                refused = invoke(["--home", str(home), "uninstall"])
                after = tuple(sorted(str(path.relative_to(base)) for path in base.rglob("*")))
                self.assertIn(refused[1]["code"], ("RUNTIME_TAMPERED", "FOREIGN_WORKFLOW"))
                self.assertFalse(refused[1]["changed"])
                self.assertEqual(after, before)

        # Given/When/Then: install/uninstall version rows and clean uninstall row are exact canonical objects.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            home = private_home(Path(directory))
            with patch("mnemosyne_capture.install.sys_version", return_value=(3, 13)):
                install_version = invoke(["--home", str(home), "install"])
            with patch("mnemosyne_capture.uninstall.sys_version", return_value=(3, 13)):
                uninstall_version = invoke(["--home", str(home), "uninstall"])
            clean = invoke(["--home", str(home), "uninstall"])
            self.assertEqual((install_version[1]["code"], uninstall_version[1]["code"], clean[1]["code"]),
                             ("PYTHON_VERSION_MISMATCH", "PYTHON_VERSION_MISMATCH", "UNINSTALLED"))
            for _, result in (install_version, uninstall_version, clean):
                self.assertEqual(set(result), {"schema", "command", "code", "ok", "changed",
                                               "document_key", "revision_id", "path", "warnings"})
                self.assertEqual(result["warnings"], [])

    def test_install_publication_faults_phase_f_clean_sync_and_same_root_loser(self) -> None:
        # Given/When/Then: each non-fsync publication interruption retains exact changed ownership and resumes.
        for boundary in ("release-rename", "witness-create", "current-replace", "workflow-rename"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
                home = private_home(Path(directory))
                original_rename = Path.rename
                original_symlink = Path.symlink_to
                original_replace = os.replace
                faulted = False

                def rename(path: Path, target: Path) -> Path:
                    nonlocal faulted
                    if not faulted and ((boundary == "release-rename" and path.name == "release") or
                                        (boundary == "workflow-rename" and path.name.endswith(".installing"))):
                        faulted = True
                        raise OSError
                    return original_rename(path, target)

                def symlink(path: Path, target, target_is_directory: bool = False) -> None:
                    nonlocal faulted
                    if boundary == "witness-create" and path.name == ".current.installing" and not faulted:
                        faulted = True
                        raise OSError
                    original_symlink(path, target, target_is_directory=target_is_directory)

                def replace(source, target, *args, **kwargs) -> None:
                    nonlocal faulted
                    if boundary == "current-replace" and str(source).endswith(".current.installing") and not faulted:
                        faulted = True
                        raise OSError
                    original_replace(source, target, *args, **kwargs)

                with patch("mnemosyne_capture.install_artifacts.Path.rename", new=rename), \
                     patch("mnemosyne_capture.install.Path.rename", new=rename), \
                     patch("mnemosyne_capture.install.Path.symlink_to", new=symlink), \
                     patch("mnemosyne_capture.install.os.replace", new=replace):
                    interrupted = invoke(["--home", str(home), "install"])
                resumed = invoke(["--home", str(home), "install"])
                self.assertTrue(faulted)
                self.assertEqual((interrupted[1]["code"], interrupted[1]["changed"]),
                                 ("WRITE_FAILED", True))
                self.assertEqual((resumed[0], resumed[1]["code"]), (0, "INSTALLED"))

        # Given/When/Then: phase-F sync is changed true; clean scaffold sync is changed false.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            home = private_home(Path(directory))
            invoke(["--home", str(home), "install"])
            original_unlink = Path.unlink

            def stop_plan(path: Path, missing_ok: bool = False) -> None:
                if path.name == ".uninstall-plan.json":
                    raise OSError
                original_unlink(path, missing_ok=missing_ok)

            with patch("mnemosyne_capture.uninstall.Path.unlink", new=stop_plan):
                invoke(["--home", str(home), "uninstall"])
            runtime = home / "Library/Application Support/Mnemosyne/runtime"
            original_sync = __import__("mnemosyne_capture.uninstall", fromlist=["sync"]).sync

            def fail_final(path: Path) -> None:
                if path == runtime and not (runtime / ".uninstall-plan.json").exists():
                    raise OSError
                original_sync(path)

            with patch("mnemosyne_capture.uninstall.sync", new=fail_final):
                phase_f = invoke(["--home", str(home), "uninstall"])
            with patch("mnemosyne_capture.uninstall.sync", side_effect=OSError):
                clean_fault = invoke(["--home", str(home), "uninstall"])
            clean = invoke(["--home", str(home), "uninstall"])
            self.assertEqual((phase_f[1]["code"], phase_f[1]["changed"]), ("WRITE_FAILED", True))
            self.assertEqual((clean_fault[1]["code"], clean_fault[1]["changed"]), ("WRITE_FAILED", False))
            self.assertEqual((clean[1]["code"], clean[1]["changed"]), ("UNINSTALLED", False))

        # Given/When/Then: simultaneous same-root installers attribute publication to one winner only.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home = private_home(base)
            data = base / "data"
            environment = {**os.environ, "PYTHONPATH": "/Users/tars/Documents/workspace/mnemosyne/capture",
                           "PYTHONPYCACHEPREFIX": "/private/tmp/mnemosyne-qa.JXLDp7/pycache"}
            argv = [os.sys.executable, "-m", "mnemosyne_capture", "--home", str(home),
                    "--data-root", str(data), "install"]
            processes = [subprocess.Popen(argv, stdout=subprocess.PIPE, env=environment) for _ in range(2)]
            results = [json.loads(process.communicate(timeout=20)[0]) for process in processes]
            self.assertEqual(sorted(result["changed"] for result in results), [False, True])
            self.assertTrue(all(result["code"] == "INSTALLED" for result in results))

    def test_verified_and_unverified_owner_writer_hardlink_namespaces(self) -> None:
        # Given/When/Then: unverified final and stage workflow hardlinks remain FOREIGN and untouched.
        for reserved_name in ("Mnemosyne Capture.workflow", ".Mnemosyne Capture.workflow.installing"):
            with self.subTest(reserved=reserved_name), tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
                base = Path(directory)
                home = private_home(base)
                reserved = home / "Library/Services" / reserved_name
                marker = reserved / "Contents/Resources/mnemosyne-owner.json"
                marker.parent.mkdir(parents=True, mode=0o700)
                reserved.chmod(0o700)
                (reserved / "Contents").chmod(0o700)
                marker.write_bytes(OWNER_BYTES)
                marker.chmod(0o600)
                alias = base / "unverified-alias"
                os.link(marker, alias)
                refused = invoke(["--home", str(home), "install"])
                self.assertEqual((refused[1]["code"], refused[1]["changed"]),
                                 ("FOREIGN_WORKFLOW", False))
                self.assertEqual((marker.read_bytes(), alias.read_bytes()), (OWNER_BYTES, OWNER_BYTES))

        # Given/When/Then: authenticated release-owner and workflow writers hardlinked elsewhere are runtime tamper.
        for writer in ("release-owner", "workflow-document"):
            with self.subTest(writer=writer), tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
                base = Path(directory)
                home = private_home(base)
                invoke(["--home", str(home), "install"])
                runtime = home / "Library/Application Support/Mnemosyne/runtime"
                workflow = home / "Library/Services/Mnemosyne Capture.workflow"
                release_id = (runtime / "current").resolve().name
                if writer == "release-owner":
                    stage = runtime / f".release-stage-{release_id}"
                    stage.mkdir(mode=0o700)
                    target = stage / "owner.json"
                    target.write_bytes(canonical({"owner": OWNER, "release_id": release_id,
                                                  "schema": "mnemosyne.release-stage/v1"}))
                    target.chmod(0o600)
                else:
                    (runtime / "current").rename(runtime / ".current.installing")
                    stage = workflow.with_name(".Mnemosyne Capture.workflow.installing")
                    workflow.rename(stage)
                    target = stage / "Contents/Resources/document.wflow"
                    content = target.read_bytes()
                    target.unlink()
                    target = target.with_name("document.wflow.writing")
                    target.write_bytes(content[:1])
                    target.chmod(0o600)
                alias = base / "verified-alias"
                os.link(target, alias)
                before = alias.read_bytes()
                refused = invoke(["--home", str(home), "install"])
                self.assertEqual((refused[1]["code"], refused[1]["changed"]),
                                 ("RUNTIME_TAMPERED", False))
                self.assertEqual((target.read_bytes(), alias.read_bytes()), (before, before))

    def test_neutral_release_exact_plan_and_nonzero_export_doctor_states(self) -> None:
        # Given/When/Then: neutral-only uninstall is unchanged and preserves the release byte-for-byte.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            base = Path(directory)
            home = private_home(base)
            invoke(["--home", str(home), "install"])
            runtime = home / "Library/Application Support/Mnemosyne/runtime"
            workflow = home / "Library/Services/Mnemosyne Capture.workflow"
            release = (runtime / "current").resolve()
            before = {path.name: path.read_bytes() for path in release.iterdir()}
            (runtime / "current").unlink()
            workflow.rename(workflow.with_name("neutral-sentinel"))
            result = invoke(["--home", str(home), "uninstall"])
            after = {path.name: path.read_bytes() for path in release.iterdir()}
            self.assertEqual((result[1]["code"], result[1]["changed"]), ("UNINSTALLED", False))
            self.assertEqual(after, before)

        # Given/When/Then: the durable uninstall plan has exact canonical keys, binding, and Info.plist hash.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            home = private_home(Path(directory))
            invoke(["--home", str(home), "install"])
            runtime = home / "Library/Application Support/Mnemosyne/runtime"
            original = Path.rename

            def stop(path: Path, target: Path) -> Path:
                if path.name == "Mnemosyne Capture.workflow":
                    raise OSError
                return original(path, target)

            with patch("mnemosyne_capture.uninstall.Path.rename", new=stop):
                invoke(["--home", str(home), "uninstall"])
            raw = (runtime / ".uninstall-plan.json").read_bytes()
            plan = json.loads(raw)
            self.assertEqual(raw, canonical(plan))
            self.assertEqual(set(plan), {"schema", "owner", "workflow", "current_target", "releases"})
            self.assertEqual(plan["workflow"]["path"], str(home / "Library/Services/Mnemosyne Capture.workflow"))
            self.assertEqual(len(plan["workflow"]["info_plist_sha256"]), 64)
            install_during = invoke(["--home", str(home), "install"])
            self.assertEqual((install_during[1]["code"], install_during[1]["changed"]),
                             ("UNINSTALL_IN_PROGRESS", False))

        # Given: one committed revision and exact, missing, then wrong-mode export states.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            home = private_home(Path(directory))
            invoke(["--home", str(home), "install"])
            root = home / "Library/Application Support/Mnemosyne"
            observed = "https://blog.naver.com/example/123"
            value = {"schema": "mnemosyne.safari-extract/v1", "top_document_url": observed,
                     "content_document_url": observed, "canonical_url": observed, "title": "Title",
                     "published_at_raw": "2026. 8. 26.", "body": "Body\n",
                     "editor_fingerprint": "smarteditor_one",
                     "component_counts": {"images": 0, "tables": 0, "embeds": 0, "media": 0}, "warnings": []}
            payload = CapturePayload.from_json_bytes(json.dumps(value).encode(), observed)
            store = CaptureStore(root)
            with store.locked(create=False):
                store.capture(payload)
            exact = invoke(["--home", str(home), "doctor", "--json"])
            export = root / "posts.jsonl"
            export.unlink()
            missing = invoke(["--home", str(home), "doctor", "--json"])
            with store.locked(create=False):
                store.export()
            export.chmod(0o644)
            corrupt = invoke(["--home", str(home), "doctor", "--json"])
            codes = [{item["name"]: item["code"] for item in result[1]["checks"]}["export"]
                     for result in (exact, missing, corrupt)]
            self.assertEqual(codes, ["EXPORT_OK", "EXPORT_STALE", "CORRUPT_CANONICAL"])

        # Given/When/Then: explicit bounded stage discard returns every Todo 6 discard result row.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            home = private_home(Path(directory))
            invoke(["--home", str(home), "install"])
            root = home / "Library/Application Support/Mnemosyne"
            stage_id = "12345678-1234-4234-8234-123456789abc"
            staging = root / ".staging"
            staging.mkdir(mode=0o700)
            stage = staging / f"mnemosyne-stage-{stage_id}"
            stage.mkdir(mode=0o700)
            discarded = invoke(["--home", str(home), "doctor", "--discard-stage", stage_id])
            missing = invoke(["--home", str(home), "doctor", "--discard-stage", stage_id])
            invalid = invoke(["--home", str(home), "doctor", "--discard-stage", stage_id.upper()])
            self.assertEqual([(row[1]["code"], row[1]["changed"]) for row in (discarded, missing, invalid)],
                             [("STAGING_DISCARDED", True), ("STAGE_NOT_FOUND", False),
                              ("INVALID_ARGUMENT", False)])


if __name__ == "__main__":
    unittest.main()
