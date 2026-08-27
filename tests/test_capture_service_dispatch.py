from __future__ import annotations

import plistlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mnemosyne_capture import install as install_module
from mnemosyne_capture.install import install
from mnemosyne_capture.install_artifacts import (BuiltRelease, info_plist, publish_workflow_stage,
                                                  workflow_plist)
from mnemosyne_capture.install_paths import bind_paths


def private_home(root: Path) -> Path:
    home = root / "home"
    (home / "Library/Services").mkdir(parents=True, mode=0o700)
    (home / "Library/Application Support").mkdir(mode=0o700)
    home.chmod(0o700)
    (home / "Library").chmod(0o700)
    return home


class CaptureServiceDispatchTests(unittest.TestCase):
    def test_published_workflow_dispatches_through_native_automator(self) -> None:
        # Given: Apple's installed workflow layout and a synthetic no-input sentinel workflow.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-automator-") as directory:
            root = Path(directory)
            workflow = root / "Synthetic.workflow"
            sentinel = root / "dispatched"
            platform_documents = sorted(Path("/System/Library/Services").glob(
                "*.workflow/Contents/Resources/document.wflow"))
            self.assertTrue(platform_documents)
            platform_layout = platform_documents[0].parts[-3:]
            document = plistlib.dumps(workflow_plist(f"/usr/bin/touch '{sentinel}'"), fmt=plistlib.FMT_XML,
                                      sort_keys=True)
            built = BuiltRelease("synthetic", (), b"", document,
                                 plistlib.dumps(info_plist(), fmt=plistlib.FMT_XML, sort_keys=True))
            publish_workflow_stage(workflow, built)

            # When: macOS runs the published bundle through the native Automator surface.
            result = subprocess.run(["/usr/bin/automator", str(workflow)], capture_output=True, timeout=10)

            # Then: publishing matches Apple's executable layout and dispatches to the sentinel.
            self.assertTrue(workflow.joinpath(*platform_layout).is_file())
            self.assertFalse((workflow / "Contents/document.wflow").exists())
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
            self.assertTrue(sentinel.is_file())

    def test_successful_default_installs_update_native_services(self) -> None:
        # Given: a synthetic home treated as the default home and a native Services updater spy.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            home = private_home(Path(directory))
            paths = bind_paths(home, None)
            with patch.object(Path, "home", return_value=home), patch.object(install_module, "subprocess") as native:
                native.DEVNULL = subprocess.DEVNULL
                native.PIPE = subprocess.PIPE

                # When: the default workflow is installed and then idempotently reinstalled.
                first = install(paths)
                second = install(paths)

            # Then: both successful installs refresh Services without changing install state twice.
            self.assertEqual((first.ok, first.changed, second.ok, second.changed), (True, True, True, False))
            self.assertEqual(native.run.call_count, 2)
            native.run.assert_called_with(["/System/Library/CoreServices/pbs", "-update"], check=True, timeout=10,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def test_services_update_timeout_maps_to_changed_write_failure(self) -> None:
        # Given: a changed default install whose bounded native Services update times out.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            home = private_home(Path(directory))
            paths = bind_paths(home, None)
            with patch.object(Path, "home", return_value=home), patch.object(install_module, "subprocess") as native:
                native.DEVNULL = subprocess.DEVNULL
                native.PIPE = subprocess.PIPE
                native.SubprocessError = subprocess.SubprocessError
                native.run.side_effect = subprocess.TimeoutExpired("pbs", 10)

                # When: the install reaches Services publication.
                result = install(paths)

            # Then: the existing write-failure boundary reports the committed mutation.
            self.assertEqual((result.code.value, result.ok, result.changed), ("WRITE_FAILED", False, True))

    def test_services_update_timeout_is_retried_by_exact_owned_install(self) -> None:
        # Given: a durable default installation whose first Services refresh times out.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            home = private_home(Path(directory))
            paths = bind_paths(home, None)
            with patch.object(Path, "home", return_value=home), patch.object(install_module, "subprocess") as native:
                native.DEVNULL = subprocess.DEVNULL
                native.PIPE = subprocess.PIPE
                native.SubprocessError = subprocess.SubprocessError
                native.run.side_effect = (subprocess.TimeoutExpired("pbs", 10), None,
                                          subprocess.TimeoutExpired("pbs", 10), None)

                # When: the exact-owned install is retried after the publication failure.
                failed = install(paths)
                recovered = install(paths)
                unchanged_failed = install(paths)
                unchanged_recovered = install(paths)

            # Then: the unchanged retry repeats PBS and succeeds without inventing a state mutation.
            self.assertEqual((failed.code.value, failed.ok, failed.changed), ("WRITE_FAILED", False, True))
            self.assertEqual((recovered.code.value, recovered.ok, recovered.changed), ("INSTALLED", True, False))
            self.assertEqual((unchanged_failed.code.value, unchanged_failed.ok, unchanged_failed.changed),
                             ("WRITE_FAILED", False, False))
            self.assertEqual((unchanged_recovered.code.value, unchanged_recovered.ok, unchanged_recovered.changed),
                             ("INSTALLED", True, False))
            self.assertEqual(native.run.call_count, 4)

    def test_install_repairs_owned_legacy_workflow_layout(self) -> None:
        # Given: a valid owned installation in the legacy root-document layout.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            home = private_home(Path(directory))
            paths = bind_paths(home, None)
            with patch("mnemosyne_capture.install_artifacts._zipapp_bytes", return_value=b"previous-runtime"):
                first = install(paths)
            resources = paths.workflow / "Contents/Resources"
            legacy = paths.workflow / "Contents/document.wflow"
            (resources / "document.wflow").rename(legacy)

            # When: the existing safe installer repairs the owned installation.
            repaired = install(paths)

            # Then: only the platform-canonical document location remains.
            self.assertTrue(first.ok)
            self.assertEqual((repaired.code.value, repaired.ok, repaired.changed), ("INSTALLED", True, True))
            self.assertTrue((resources / "document.wflow").is_file())
            self.assertFalse(legacy.exists())

    def test_install_refuses_tampered_legacy_workflow_layout(self) -> None:
        # Given: a legacy-shaped workflow whose document no longer matches its signed manifest.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-install-") as directory:
            home = private_home(Path(directory))
            paths = bind_paths(home, None)
            first = install(paths)
            canonical = paths.workflow / "Contents/Resources/document.wflow"
            legacy = paths.workflow / "Contents/document.wflow"
            canonical.rename(legacy)
            legacy.write_bytes(legacy.read_bytes() + b"tampered")

            # When: repair is attempted against the owned manifest.
            refused = install(paths)

            # Then: authentication fails without moving the untrusted document.
            self.assertTrue(first.ok)
            self.assertEqual((refused.code.value, refused.ok, refused.changed),
                             ("RUNTIME_TAMPERED", False, False))
            self.assertTrue(legacy.is_file())
            self.assertFalse(canonical.exists())


if __name__ == "__main__":
    unittest.main()
