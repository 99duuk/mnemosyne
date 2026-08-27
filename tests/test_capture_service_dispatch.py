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
        # Given: a synthetic no-input workflow whose only effect is a private temporary sentinel.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-automator-") as directory:
            root = Path(directory)
            workflow = root / "Synthetic.workflow"
            sentinel = root / "dispatched"
            document = plistlib.dumps(workflow_plist(f"/usr/bin/touch '{sentinel}'"), fmt=plistlib.FMT_XML,
                                      sort_keys=True)
            built = BuiltRelease("synthetic", (), b"", document,
                                 plistlib.dumps(info_plist(), fmt=plistlib.FMT_XML, sort_keys=True))
            publish_workflow_stage(workflow, built)

            # When: macOS runs the published bundle through the native Automator surface.
            result = subprocess.run(["/usr/bin/automator", str(workflow)], capture_output=True, timeout=10)

            # Then: the workflow dispatches exactly once to its sentinel command.
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
            self.assertTrue(sentinel.is_file())

    def test_changed_default_install_updates_native_services_once(self) -> None:
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

            # Then: only the changed publication asks macOS to refresh Services.
            self.assertTrue(first.ok and second.ok)
            native.run.assert_called_once_with(["/System/Library/CoreServices/pbs", "-update"], check=True,
                                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


if __name__ == "__main__":
    unittest.main()
