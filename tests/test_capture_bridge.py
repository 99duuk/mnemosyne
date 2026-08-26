from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mnemosyne_capture.bridge import (
    ArtifactError,
    Bridge,
    BridgeError,
    BridgeErrorCode,
)


URL = "https://blog.naver.com/fixture_author/42"


def payload_bytes(**changes: str | None) -> bytes:
    value = {
        "schema": "mnemosyne.safari-extract/v1",
        "top_document_url": URL,
        "content_document_url": URL,
        "canonical_url": URL,
        "title": "Synthetic title",
        "published_at_raw": "2026. 8. 26.",
        "body": "Synthetic body\n",
        "editor_fingerprint": "smarteditor_one",
        "component_counts": {"images": 0, "tables": 0, "embeds": 0, "media": 0},
        "warnings": [],
    }
    value.update(changes)
    return json.dumps(value, separators=(",", ":")).encode()


def completed(stdout: bytes, returncode: int = 0, stderr: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(("/usr/bin/osascript",), returncode, stdout, stderr)


class BridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.capture_script = root / "capture.scpt"
        self.extractor_script = root / "extract-current-page.js"
        for path in (self.capture_script, self.extractor_script):
            path.write_bytes(b"fixed artifact")
            path.chmod(0o600)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def bridge(self) -> Bridge:
        return Bridge.bind(self.capture_script, self.extractor_script)

    def assert_bridge_error(self, code: BridgeErrorCode, action) -> None:
        with self.assertRaises(BridgeError) as caught:
            action()
        self.assertEqual(caught.exception.code, code)

    def test_snapshot_uses_exact_argv_timeout_and_envelope(self) -> None:
        with patch("mnemosyne_capture.bridge.subprocess.run", return_value=completed(b"MNEMOSYNE_BRIDGE_V1\nOK\n" + URL.encode() + b"\n")) as run:
            result = self.bridge().snapshot()

        self.assertEqual(result.url, URL)
        run.assert_called_once_with(
            ["/usr/bin/osascript", str(self.capture_script), "snapshot"],
            shell=False,
            timeout=10,
            capture_output=True,
        )

    def test_extract_parses_exact_envelope_and_payload(self) -> None:
        envelope = b"MNEMOSYNE_BRIDGE_V1\nOK\n" + URL.encode() + b"\n" + URL.encode() + b"\n" + payload_bytes() + b"\n"
        with patch("mnemosyne_capture.bridge.subprocess.run", return_value=completed(envelope)) as run:
            result = self.bridge().extract(URL)

        self.assertEqual(result.before_url, URL)
        self.assertEqual(result.after_url, URL)
        self.assertEqual(result.payload.identity.post_id, "42")
        run.assert_called_once_with(
            ["/usr/bin/osascript", str(self.capture_script), "extract", URL, str(self.extractor_script)],
            shell=False,
            timeout=10,
            capture_output=True,
        )

    def test_smoke_and_notify_accept_only_their_exact_success_envelopes(self) -> None:
        responses = [
            completed(b"MNEMOSYNE_BRIDGE_V1\nOK\nMNEMOSYNE_JS_OK\n"),
            completed(b"MNEMOSYNE_BRIDGE_V1\nOK\n"),
        ]
        with patch("mnemosyne_capture.bridge.subprocess.run", side_effect=responses) as run:
            self.assertEqual(self.bridge().smoke(URL).token, "MNEMOSYNE_JS_OK")
            self.bridge().notify("Mnemosyne", "CAPTURED — saved")

        self.assertEqual(run.call_args_list[0].args[0], ["/usr/bin/osascript", str(self.capture_script), "smoke", URL])
        self.assertEqual(
            run.call_args_list[1].args[0],
            ["/usr/bin/osascript", str(self.capture_script), "notify", "Mnemosyne", "CAPTURED — saved"],
        )

    def test_exact_mode_error_sets_reject_cross_mode_and_malformed_output(self) -> None:
        allowed = {
            "snapshot": ["NO_SAFARI_TAB", "SAFARI_NOT_FRONTMOST", "APPLE_EVENTS_DENIED"],
            "smoke": ["NO_SAFARI_TAB", "SAFARI_NOT_FRONTMOST", "APPLE_EVENTS_DENIED", "JAVASCRIPT_UNAVAILABLE", "TAB_CHANGED"],
            "extract": ["NO_SAFARI_TAB", "SAFARI_NOT_FRONTMOST", "APPLE_EVENTS_DENIED", "JAVASCRIPT_UNAVAILABLE", "TAB_CHANGED", "UNSUPPORTED_PAGE"],
        }
        for mode, codes in allowed.items():
            for code in codes:
                with self.subTest(mode=mode, code=code), patch(
                    "mnemosyne_capture.bridge.subprocess.run",
                    return_value=completed(f"MNEMOSYNE_BRIDGE_V1\nERROR\n{code}\n".encode()),
                ):
                    args = () if mode == "snapshot" else (URL,)
                    self.assert_bridge_error(BridgeErrorCode(code), lambda mode=mode, args=args: getattr(self.bridge(), mode)(*args))

        malformed = [
            completed(b"WRONG\nOK\n" + URL.encode() + b"\n"),
            completed(b"MNEMOSYNE_BRIDGE_V1\nERROR\nUNSUPPORTED_PAGE\n"),
            completed(b"MNEMOSYNE_BRIDGE_V1\nOK\n" + URL.encode()),
            completed(b"MNEMOSYNE_BRIDGE_V1\nOK\n" + URL.encode() + b"\nEXTRA\n"),
            completed(b"MNEMOSYNE_BRIDGE_V1\nOK\n\xff\n"),
            completed(b"MNEMOSYNE_BRIDGE_V1\nERROR\nNO_SAFARI_TAB\n", returncode=1),
        ]
        for response in malformed:
            with self.subTest(stdout=response.stdout), patch("mnemosyne_capture.bridge.subprocess.run", return_value=response):
                self.assert_bridge_error(BridgeErrorCode.SCRIPT_EXECUTION_BLOCKED, self.bridge().snapshot)

    def test_timeout_and_notify_failures_have_exact_codes(self) -> None:
        with patch("mnemosyne_capture.bridge.subprocess.run", side_effect=subprocess.TimeoutExpired("osascript", 10)):
            self.assert_bridge_error(BridgeErrorCode.BRIDGE_TIMEOUT, self.bridge().snapshot)
            self.assert_bridge_error(
                BridgeErrorCode.NOTIFICATION_FAILED,
                lambda: self.bridge().notify("Mnemosyne", "CAPTURED — saved"),
            )
        with patch("mnemosyne_capture.bridge.subprocess.run", return_value=completed(b"bad", returncode=1)):
            self.assert_bridge_error(
                BridgeErrorCode.NOTIFICATION_FAILED,
                lambda: self.bridge().notify("Mnemosyne", "CAPTURED — saved"),
            )

    def test_extract_outer_url_drift_and_caps_precede_payload_parsing(self) -> None:
        too_long = URL + "#" + "x" * 4097
        self.assert_bridge_error(BridgeErrorCode.TAB_CHANGED, lambda: self.bridge().extract(too_long))
        for before, after in ((URL + "?changed=1", URL), (URL, URL + "?changed=1"), (too_long, URL), (URL, too_long)):
            envelope = b"MNEMOSYNE_BRIDGE_V1\nOK\n" + before.encode() + b"\n" + after.encode() + b"\n{}\n"
            with self.subTest(before=before, after=after), patch("mnemosyne_capture.bridge.subprocess.run", return_value=completed(envelope)):
                self.assert_bridge_error(BridgeErrorCode.TAB_CHANGED, lambda: self.bridge().extract(URL))

    def test_payload_failures_are_invalid_payload_only_after_exact_outer_envelope(self) -> None:
        invalid_payloads = [b"{}", b"\xff", payload_bytes(canonical_url=URL + "#" + "x" * 4097)]
        for raw in invalid_payloads:
            envelope = b"MNEMOSYNE_BRIDGE_V1\nOK\n" + URL.encode() + b"\n" + URL.encode() + b"\n" + raw + b"\n"
            with self.subTest(raw=raw[:20]), patch("mnemosyne_capture.bridge.subprocess.run", return_value=completed(envelope)):
                self.assert_bridge_error(BridgeErrorCode.INVALID_PAYLOAD, lambda: self.bridge().extract(URL))

    def test_artifacts_must_be_absolute_private_current_uid_regular_single_link_files(self) -> None:
        relative = Path("capture.scpt")
        with self.assertRaises(ArtifactError):
            Bridge.bind(relative, self.extractor_script)
        self.capture_script.chmod(0o644)
        with self.assertRaises(ArtifactError):
            Bridge.bind(self.capture_script, self.extractor_script)
        self.capture_script.chmod(0o600)
        alias = Path(self.temp.name) / "alias.scpt"
        os.link(self.capture_script, alias)
        with self.assertRaises(ArtifactError):
            Bridge.bind(self.capture_script, self.extractor_script)

    def test_artifact_inode_hash_and_mode_are_revalidated_before_every_invocation(self) -> None:
        bridge = self.bridge()
        replacement = Path(self.temp.name) / "replacement.scpt"
        replacement.write_bytes(b"changed")
        replacement.chmod(0o600)
        os.replace(replacement, self.capture_script)
        with patch("mnemosyne_capture.bridge.subprocess.run") as run:
            with self.assertRaises(ArtifactError):
                bridge.snapshot()
        run.assert_not_called()

    def test_expected_hash_rejects_same_mode_replacement_at_bind(self) -> None:
        expected_capture = hashlib.sha256(self.capture_script.read_bytes()).hexdigest()
        expected_extractor = hashlib.sha256(self.extractor_script.read_bytes()).hexdigest()
        replacement = Path(self.temp.name) / "replacement.scpt"
        replacement.write_bytes(b"mode-valid replacement")
        replacement.chmod(0o600)
        os.replace(replacement, self.capture_script)

        with self.assertRaises(ArtifactError):
            Bridge.bind(
                self.capture_script,
                self.extractor_script,
                expected_capture_sha256=expected_capture,
                expected_extractor_sha256=expected_extractor,
            )

    def test_expected_hash_rejects_malformed_boundary_values(self) -> None:
        malformed = ("", "a" * 63, "a" * 65, "A" * 64, "g" * 64, 7)

        for value in malformed:
            with self.subTest(value=value), self.assertRaises(ArtifactError):
                Bridge.bind(
                    self.capture_script,
                    self.extractor_script,
                    expected_capture_sha256=value,
                )

        bridge = Bridge.bind(self.capture_script, self.extractor_script)
        self.extractor_script.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
        with patch("mnemosyne_capture.bridge.subprocess.run") as run:
            with self.assertRaises(ArtifactError):
                bridge.extract(URL)
        run.assert_not_called()

    def test_fixture_is_tracked_source_safe(self) -> None:
        fixture = Path("fixtures/naver/wrong-host.html")
        raw = fixture.read_bytes()
        text_value = raw.decode("utf-8", "strict")

        self.assertIn("MNEMOSYNE_SYNTHETIC_WRONG_HOST", text_value)
        for forbidden in ("naver.com", "blogId", "logNo", "cookie", "http://", "https://"):
            self.assertNotIn(forbidden, text_value)
        ignored = subprocess.run(
            ["/usr/bin/git", "check-ignore", "--quiet", str(fixture)],
            capture_output=True,
            check=False,
        )
        self.assertEqual(ignored.returncode, 1)
        self.assertTrue(fixture.is_file())

    def test_applescript_missing_current_tab_precheck_is_explicit(self) -> None:
        source = Path("capture/macos/capture.applescript").read_text(encoding="utf-8")
        selected = source.index("set selectedTab to «class cTab» of front window")
        missing = source.index('if selectedTab is missing value then return my bridgeError("NO_SAFARI_TAB")')
        url_read = source.index("set currentURL to «class pURL» of selectedTab")
        denial = source.index('if errorNumber is -1743 then return my bridgeError("APPLE_EVENTS_DENIED")')
        absent = source.index('if errorNumber is -1728 then return my bridgeError("NO_SAFARI_TAB")')

        self.assertLess(selected, missing)
        self.assertLess(missing, url_read)
        self.assertLess(denial, absent)

    def test_applescript_source_compiles_with_native_compiler(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mnemosyne-osacompile-") as directory:
            output = Path(directory) / "capture.scpt"

            result = subprocess.run(
                ["/usr/bin/osacompile", "-o", str(output), "capture/macos/capture.applescript"],
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
