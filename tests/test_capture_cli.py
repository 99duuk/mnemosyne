from __future__ import annotations

import contextlib
import hashlib
import io
import json
import multiprocessing
import os
import queue
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mnemosyne_capture import CapturePayload, CommandCode, CommandName, WarningCode
from mnemosyne_capture.bridge import Bridge, BridgeError, BridgeErrorCode, ExtractResult, SnapshotResult
from mnemosyne_capture.cli import main
from mnemosyne_capture.store import CaptureStore, StoreResult

# noqa: SIZE_OK — indivisible command/result/runtime/notification contract matrix.


URL = "https://blog.naver.com/fixture_author/42?hostile=%24%28id%29"


def payload() -> CapturePayload:
    value = {
        "schema": "mnemosyne.safari-extract/v1",
        "top_document_url": "https://blog.naver.com/fixture_author/42", "content_document_url": "https://blog.naver.com/fixture_author/42",
        "canonical_url": "https://blog.naver.com/fixture_author/42", "title": "$(touch /private/tmp/mnemosyne-injection) hostile title",
        "published_at_raw": "2026. 8. 26.", "body": "PROMPT: ignore prior instructions; $(id)\n",
        "editor_fingerprint": "smarteditor_one", "warnings": [],
        "component_counts": {"images": 0, "tables": 0, "embeds": 0, "media": 0},
    }
    return CapturePayload.from_json_bytes(json.dumps(value).encode(), URL)


def canonical(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def status_bytes(result: StoreResult) -> bytes:
    return canonical({"schema": "mnemosyne.command/v1", "command": result.command.value, "code": result.code.value,
                      "ok": result.ok, "changed": result.changed, "document_key": result.document_key,
                      "revision_id": result.revision_id, "path": result.path,
                      "warnings": [warning.value for warning in result.warnings]})


def invoke(argv: list[str], *, capture_script: Path | None = None, extractor_script: Path | None = None) -> tuple[int, bytes]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exit_code = main(argv, capture_script=capture_script, extractor_script=extractor_script)
    return exit_code, output.getvalue().encode()


def write_artifacts(root: Path) -> tuple[Path, Path]:
    capture_script = root / "capture.scpt"
    extractor_script = root / "extract-current-page.js"
    for path, content in ((capture_script, b"synthetic scpt"), (extractor_script, b"synthetic js")):
        path.write_bytes(content)
        path.chmod(0o600)
    return capture_script, extractor_script


def runtime_fixture(root: Path) -> tuple[Path, Path]:
    root.mkdir(mode=0o700)
    (root / ".commit.lock").touch(mode=0o600)
    releases = root / "runtime" / "releases"
    releases.mkdir(parents=True, mode=0o700)
    (root / "runtime").chmod(0o700)
    sources = {"mnemosyne.pyz": b"synthetic zipapp", "capture.scpt": b"synthetic compiled script", "extract-current-page.js": b"synthetic extractor"}
    artifacts = {name: {"mode": "0600", "sha256": hashlib.sha256(content).hexdigest()}
                 for name, content in sources.items()}
    unsigned = {
        "schema": "mnemosyne.runtime-manifest/v1", "owner": "github.com/99duuk/mnemosyne#mnemosyne-capture/v1",
        "python_realpath": os.path.realpath(sys.executable), "artifacts": artifacts,
        "workflow": {"document_sha256": "0" * 64, "info_plist_sha256": "1" * 64, "owner_marker_sha256": "2" * 64,
                     "path": str(root.parent / "Library/Services/Mnemosyne Capture.workflow")},
    }
    release_id = hashlib.sha256(b"mnemosyne.runtime.release/v1\n" + canonical(unsigned)).hexdigest()
    release = releases / release_id
    release.mkdir(mode=0o700)
    for name, content in sources.items():
        path = release / name
        path.write_bytes(content)
        path.chmod(0o600)
    (release / "manifest.json").write_bytes(canonical({**unsigned, "release_id": release_id}))
    (release / "manifest.json").chmod(0o600)
    (root / "runtime/current").symlink_to(f"releases/{release_id}")
    return release / "capture.scpt", release / "extract-current-page.js"


def replace_manifest(root: Path, update) -> None:
    current = (root / "runtime/current").resolve()
    manifest = json.loads((current / "manifest.json").read_bytes())
    update(manifest)
    manifest.pop("release_id", None)
    release_id = hashlib.sha256(b"mnemosyne.runtime.release/v1\n" + canonical(manifest)).hexdigest()
    (current / "manifest.json").write_bytes(canonical({**manifest, "release_id": release_id}))
    renamed = current.with_name(release_id)
    current.rename(renamed)
    (root / "runtime/current").unlink()
    (root / "runtime/current").symlink_to(f"releases/{release_id}")


def export_in_process(root: str, started, results) -> None:
    started.set()
    code, raw = invoke(["--data-root", root, "export"])
    results.put((code, raw))


class CaptureCliTests(unittest.TestCase):
    def test_invalid_path_and_python_version_precede_side_effects(self) -> None:
        # Given/When: an invalid path and a valid path under the wrong Python version are invoked.
        invalid = invoke(["--data-root", "relative", "export"])
        with tempfile.TemporaryDirectory(prefix="mnemosyne-cli-") as directory, patch("mnemosyne_capture.cli.sys.version_info", (3, 13)):
            root = Path(directory) / "data"
            mismatch = invoke(["--data-root", str(root), "export"])

        # Then: both return exact unchanged failures and create no root.
        self.assertEqual((invalid[0], json.loads(invalid[1])["code"]), (1, "INVALID_PATH"))
        self.assertEqual((mismatch[0], json.loads(mismatch[1])["code"], root.exists()), (1, "PYTHON_VERSION_MISMATCH", False))

    def test_internal_artifact_pair_is_both_or_neither(self) -> None:
        # Given: only one internal artifact path is supplied.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-cli-") as directory:
            capture_script, _ = write_artifacts(Path(directory))

            # When/Then: the typed entry rejects the impossible state without output.
            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(ValueError):
                main(["export"], capture_script=capture_script)
            self.assertEqual(output.getvalue(), "")

    def test_export_materializes_zero_revision_file_and_exact_status_bytes(self) -> None:
        # Given: a private absent synthetic data root.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-cli-") as directory:
            root = Path(directory) / "data"

            # When: the real CLI export command runs once.
            exit_code, raw = invoke(["--data-root", str(root), "export"])

            # Then: stdout, file bytes, and private modes are exact.
            expected = canonical({"schema": "mnemosyne.command/v1", "command": "export", "code": "EXPORTED", "ok": True,
                                  "changed": True, "document_key": None, "revision_id": None, "path": str(root / "posts.jsonl"), "warnings": []})
            self.assertEqual((exit_code, raw), (0, expected))
            self.assertEqual((root / "posts.jsonl").read_bytes(), b"")
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((root / "posts.jsonl").stat().st_mode), 0o600)

    def test_capture_commits_typed_payload_preserves_observed_url_and_notifies(self) -> None:
        # Given: trusted injected artifacts and a hostile but valid typed payload.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-cli-") as directory:
            base = Path(directory)
            root = base / "data"
            capture_script, extractor_script = write_artifacts(base)
            notifications: list[tuple[str, str]] = []

            # When: the real CLI/store path receives typed bridge results.
            with patch.object(Bridge, "snapshot", return_value=SnapshotResult(URL)), patch.object(Bridge, "extract", return_value=ExtractResult(URL, URL, payload())), patch.object(Bridge, "notify", side_effect=lambda title, body: notifications.append((title, body))):
                exit_code, raw = invoke(
                    ["--data-root", str(root), "capture"], capture_script=capture_script, extractor_script=extractor_script
                )

            # Then: one result line, one enum-only notification, and immutable authority exist.
            result = json.loads(raw)
            self.assertEqual((exit_code, result["code"], result["ok"], result["changed"]), (0, "CAPTURED", True, True))
            self.assertEqual(notifications, [("Mnemosyne", "CAPTURED — saved")])
            record = json.loads((Path(result["path"]) / "record.json").read_bytes())
            self.assertEqual(record["source"]["observed_url"], URL)
            self.assertNotIn("hostile", notifications[0][1])
            self.assertFalse(Path("/private/tmp/mnemosyne-injection").exists())

    def test_bridge_error_mapping_and_notification_failure_preserve_outcome(self) -> None:
        # Given: every typed pre-storage bridge failure.
        cases = {
            BridgeErrorCode.NO_SAFARI_TAB: (CommandCode.NO_SAFARI_TAB, "NO_SAFARI_TAB — run doctor"),
            BridgeErrorCode.SAFARI_NOT_FRONTMOST: (CommandCode.SAFARI_NOT_FRONTMOST, "SAFARI_NOT_FRONTMOST — run doctor"),
            BridgeErrorCode.APPLE_EVENTS_DENIED: (CommandCode.APPLE_EVENTS_DENIED, "APPLE_EVENTS_DENIED — enable Chrome JavaScript/Automation"),
            BridgeErrorCode.JAVASCRIPT_UNAVAILABLE: (CommandCode.JAVASCRIPT_DISABLED, "JAVASCRIPT_DISABLED — enable Chrome JavaScript/Automation"),
            BridgeErrorCode.TAB_CHANGED: (CommandCode.TAB_CHANGED, "TAB_CHANGED — run doctor"),
            BridgeErrorCode.UNSUPPORTED_PAGE: (CommandCode.UNSUPPORTED_PAGE, "UNSUPPORTED_PAGE — run doctor"),
            BridgeErrorCode.BRIDGE_TIMEOUT: (CommandCode.BRIDGE_TIMEOUT, "BRIDGE_TIMEOUT — run doctor"),
            BridgeErrorCode.SCRIPT_EXECUTION_BLOCKED: (CommandCode.SCRIPT_EXECUTION_BLOCKED, "SCRIPT_EXECUTION_BLOCKED — run doctor"),
            BridgeErrorCode.INVALID_PAYLOAD: (CommandCode.INVALID_PAYLOAD, "INVALID_PAYLOAD — run doctor"),
        }
        for bridge_code, (command_code, body) in cases.items():
            with self.subTest(code=bridge_code), tempfile.TemporaryDirectory(prefix="mnemosyne-cli-") as directory:
                base = Path(directory)
                root = base / "data"
                capture_script, extractor_script = write_artifacts(base)

                # When: the bridge raises and notification also fails.
                with patch.object(Bridge, "snapshot", side_effect=BridgeError(bridge_code)), patch.object(Bridge, "notify", side_effect=BridgeError(BridgeErrorCode.NOTIFICATION_FAILED)) as notify:
                    exit_code, raw = invoke(
                        ["--data-root", str(root), "capture"], capture_script=capture_script, extractor_script=extractor_script
                    )

                # Then: only the bridge mapping plus notification warning are visible.
                result = json.loads(raw)
                self.assertEqual((exit_code, result["code"], result["changed"]), (1, command_code.value, False))
                self.assertEqual(result["warnings"], [WarningCode.NOTIFICATION_FAILED.value])
                notify.assert_called_once()
                self.assertEqual(notify.call_args.args, ("Mnemosyne", body))
                self.assertFalse((root / "captures").exists())

    def test_store_results_map_exactly_and_only_eligible_capture_rows_notify(self) -> None:
        # Given: representative pre/post-commit typed store outcomes.
        rows = (
            (StoreResult(CommandName.CAPTURE, CommandCode.CAPTURED, True, True, "d1", "r1", "/p1"), 0, "CAPTURED — saved"),
            (StoreResult(CommandName.CAPTURE, CommandCode.REVISED, True, True, "d2", "r2", "/p2"), 0, "REVISED — saved"),
            (StoreResult(CommandName.CAPTURE, CommandCode.DUPLICATE, True, False, "d3", "r3", "/p3"), 0, "DUPLICATE — saved"),
            (StoreResult(CommandName.CAPTURE, CommandCode.DUPLICATE, True, True, "d4", "r4", "/p4"), 0, "DUPLICATE — saved"),
            (StoreResult(CommandName.CAPTURE, CommandCode.WRITE_FAILED, False, False), 1, "WRITE_FAILED — run doctor"),
            (StoreResult(CommandName.CAPTURE, CommandCode.WRITE_FAILED, False, True), 1, "WRITE_FAILED — run doctor"),
            (StoreResult(CommandName.CAPTURE, CommandCode.CORRUPT_CANONICAL, False, False), 1, "CORRUPT_CANONICAL — run doctor"),
            (StoreResult(CommandName.CAPTURE, CommandCode.CAPTURED_EXPORT_STALE, False, False, "d5", "r5", "/hostile/path", (WarningCode.EXPORT_WRITE_FAILED,)), 2, "CAPTURED_EXPORT_STALE — export required"),
            (StoreResult(CommandName.CAPTURE, CommandCode.CAPTURED_EXPORT_STALE, False, True, "d6", "r6", "/hostile/path", (WarningCode.CORRUPT_CANONICAL,)), 2, "CAPTURED_EXPORT_STALE — export required"),
        )
        for stored, expected_exit, body in rows:
            with self.subTest(code=stored.code, changed=stored.changed), tempfile.TemporaryDirectory(prefix="mnemosyne-cli-") as directory:
                base = Path(directory)
                capture_script, extractor_script = write_artifacts(base)

                # When: CLI receives the declared storage outcome.
                with patch.object(Bridge, "snapshot", return_value=SnapshotResult(URL)), patch.object(Bridge, "extract", return_value=ExtractResult(URL, URL, payload())), patch.object(CaptureStore, "capture", return_value=stored), patch.object(Bridge, "notify") as notify:
                    exit_code, raw = invoke(
                        ["--data-root", str(base / "data"), "capture"], capture_script=capture_script, extractor_script=extractor_script
                    )

                # Then: bytes preserve every field and notification is enum-derived.
                result = json.loads(raw)
                self.assertEqual((exit_code, result["code"], result["changed"]), (expected_exit, stored.code.value, stored.changed))
                self.assertEqual(result["warnings"], [warning.value for warning in stored.warnings])
                notify.assert_called_once_with("Mnemosyne", body)

    def test_export_store_outcomes_preserve_changed_and_never_notify(self) -> None:
        # Given: all standalone export result shapes consumed by the CLI.
        rows = (
            StoreResult(CommandName.EXPORT, CommandCode.EXPORTED, True, False, path="/synthetic/posts.jsonl"),
            StoreResult(CommandName.EXPORT, CommandCode.EXPORTED, True, True, path="/synthetic/posts.jsonl"),
            StoreResult(CommandName.EXPORT, CommandCode.WRITE_FAILED, False, False),
            StoreResult(CommandName.EXPORT, CommandCode.WRITE_FAILED, False, True),
            StoreResult(CommandName.EXPORT, CommandCode.CORRUPT_CANONICAL, False, False),
        )
        for stored in rows:
            with self.subTest(code=stored.code, changed=stored.changed), tempfile.TemporaryDirectory(prefix="mnemosyne-cli-") as directory:
                root = Path(directory) / "data"

                # When: export returns the typed store outcome.
                with patch.object(CaptureStore, "export", return_value=stored), patch.object(Bridge, "notify") as notify:
                    exit_code, raw = invoke(["--data-root", str(root), "export"])

                # Then: exit/result fields are exact and no notifier is reachable.
                result = json.loads(raw)
                self.assertEqual(exit_code, 0 if stored.ok else 1)
                self.assertEqual((result["code"], result["changed"], result["path"]), (stored.code.value, stored.changed, stored.path))
                notify.assert_not_called()

    def test_wrong_host_is_rejected_before_extract_with_enum_only_notification(self) -> None:
        # Given: trusted artifacts and a hostile non-NAVER snapshot URL.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-cli-") as directory:
            base = Path(directory)
            capture_script, extractor_script = write_artifacts(base)

            # When: capture applies the model origin gate.
            with patch.object(Bridge, "snapshot", return_value=SnapshotResult("https://evil.invalid/$(id)")), patch.object(Bridge, "extract") as extract, patch.object(Bridge, "notify") as notify:
                exit_code, raw = invoke(
                    ["--data-root", str(base / "data"), "capture"], capture_script=capture_script, extractor_script=extractor_script
                )

            # Then: extraction/storage never run and notification contains no hostile URL.
            self.assertEqual((exit_code, json.loads(raw)["code"]), (1, "UNSUPPORTED_HOST"))
            extract.assert_not_called()
            notify.assert_called_once_with("Mnemosyne", "UNSUPPORTED_HOST — run doctor")

    def test_invalid_injected_artifact_fails_before_bridge_and_root_creation(self) -> None:
        # Given: one trusted-looking path has the wrong mode.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-cli-") as directory:
            base = Path(directory)
            root = base / "data"
            capture_script, extractor_script = write_artifacts(base)
            extractor_script.chmod(0o644)

            # When: internal injection is bound.
            with patch.object(Bridge, "snapshot") as snapshot, patch.object(Bridge, "notify") as notify:
                exit_code, raw = invoke(
                    ["--data-root", str(root), "capture"], capture_script=capture_script, extractor_script=extractor_script
                )

            # Then: exact pre-binding tamper has no calls, warnings, or data root.
            self.assertEqual((exit_code, json.loads(raw)["code"], json.loads(raw)["warnings"]), (1, "RUNTIME_TAMPERED", []))
            snapshot.assert_not_called()
            notify.assert_not_called()
            self.assertFalse(root.exists())

    def test_invalid_production_runtime_binding_makes_zero_bridge_calls(self) -> None:
        # Given: valid production runtime followed by each artifact tamper class.
        for target in ("current", "manifest", "capture", "extractor"):
            with self.subTest(target=target), tempfile.TemporaryDirectory(prefix="mnemosyne-cli-") as directory:
                root = Path(directory) / "data"
                capture_script, extractor_script = runtime_fixture(root)
                if target == "current":
                    (root / "runtime/current").unlink()
                elif target == "manifest":
                    (capture_script.parent / "manifest.json").write_bytes(b"{}\n")
                elif target == "capture":
                    capture_script.write_bytes(b"tampered")
                else:
                    extractor_script.unlink()

                # When: production capture binds runtime under the existing lock.
                with patch.object(Bridge, "snapshot") as snapshot, patch.object(Bridge, "notify") as notify:
                    exit_code, raw = invoke(["--data-root", str(root), "capture"])

                # Then: fail closed before any bridge or notifier call.
                result = json.loads(raw)
                self.assertEqual((exit_code, result["code"], result["warnings"]), (1, "RUNTIME_TAMPERED", []))
                snapshot.assert_not_called()
                notify.assert_not_called()

    def test_production_runtime_swap_cannot_change_bound_artifacts(self) -> None:
        # Given: a validated release and a rogue release selected during bridge binding.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-cli-") as directory:
            root = Path(directory) / "data"
            capture_script, extractor_script = runtime_fixture(root)
            rogue = root / "runtime/releases" / ("f" * 64)
            rogue.mkdir(mode=0o700)
            rogue_capture, rogue_extractor = write_artifacts(rogue)
            rogue_capture.write_bytes(b"rogue capture")
            rogue_extractor.write_bytes(b"rogue extractor")
            real_bind = Bridge.bind
            bound_rogue: list[bool] = []

            def swap_then_bind(capture: Path, extractor: Path, **expected) -> Bridge:
                (root / "runtime/current").unlink()
                (root / "runtime/current").symlink_to(f"releases/{'f' * 64}")
                bound_rogue.append(capture.read_bytes().startswith(b"rogue"))
                return real_bind(capture, extractor, **expected)

            # When: current is swapped at the exact Bridge.bind boundary.
            with patch.object(Bridge, "bind", side_effect=swap_then_bind), patch.object(Bridge, "snapshot", return_value=SnapshotResult(URL)), patch.object(Bridge, "extract", return_value=ExtractResult(URL, URL, payload())), patch.object(Bridge, "notify"):
                exit_code, raw = invoke(["--data-root", str(root), "capture"])

            # Then: binding stays on the descriptor-validated immutable release.
            self.assertEqual((exit_code, json.loads(raw)["code"], bound_rogue), (0, "CAPTURED", [False]))
            self.assertEqual((capture_script.read_bytes(), extractor_script.read_bytes()), (b"synthetic compiled script", b"synthetic extractor"))

    def test_release_artifact_replacement_after_manifest_validation_fails_closed(self) -> None:
        # Given: a valid release whose capture artifact is replaced at Bridge.bind.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-cli-") as directory:
            root = Path(directory) / "data"
            capture_script, _ = runtime_fixture(root)
            real_bind = Bridge.bind
            bound_rogue: list[bool] = []

            def replace_then_bind(capture: Path, extractor: Path, **expected) -> Bridge:
                capture_script.write_bytes(b"rogue replacement")
                bridge = real_bind(capture, extractor, **expected)
                bound_rogue.append(True)
                return bridge

            # When: replacement occurs after manifest validation but before descriptor binding.
            with patch.object(Bridge, "bind", side_effect=replace_then_bind), patch.object(Bridge, "snapshot") as snapshot, patch.object(Bridge, "extract") as extract, patch.object(Bridge, "notify") as notify, patch.object(CaptureStore, "capture") as capture:
                exit_code, raw = invoke(["--data-root", str(root), "capture"])

            # Then: exact tamper bytes are returned before any bridge or storage mutation.
            expected = canonical({"schema": "mnemosyne.command/v1", "command": "capture", "code": "RUNTIME_TAMPERED", "ok": False,
                                  "changed": False, "document_key": None, "revision_id": None, "path": None, "warnings": []})
            self.assertEqual((exit_code, raw, bound_rogue), (1, expected, []))
            snapshot.assert_not_called()
            extract.assert_not_called()
            notify.assert_not_called()
            capture.assert_not_called()
            self.assertFalse((root / "captures").exists())

    def test_manifest_shape_and_scalar_types_fail_closed_at_trust_boundary(self) -> None:
        # Given: missing, extra, and wrong-type runtime manifest fields.
        rows = (
            lambda value: value.pop("owner"),
            lambda value: value.update({"extra": "hostile"}),
            lambda value: value["artifacts"]["capture.scpt"].update({"sha256": 7}),
        )
        for update in rows:
            with self.subTest(update=update), tempfile.TemporaryDirectory(prefix="mnemosyne-cli-") as directory:
                root = Path(directory) / "data"
                runtime_fixture(root)
                replace_manifest(root, update)

                # When: production capture parses the hostile manifest.
                with patch.object(Bridge, "snapshot") as snapshot, patch.object(Bridge, "notify") as notify:
                    exit_code, raw = invoke(["--data-root", str(root), "capture"])

                # Then: exact tamper result is visible without bridge or notification calls.
                result = json.loads(raw)
                self.assertEqual((exit_code, result["code"], result["warnings"]), (1, "RUNTIME_TAMPERED", []))
                snapshot.assert_not_called()
                notify.assert_not_called()

    def test_production_runtime_artifact_types_and_modes_fail_closed(self) -> None:
        # Given: every applicable wrong-mode, nonregular, and symlink runtime artifact.
        rows = (
            ("capture.scpt", "wrong_mode"), ("capture.scpt", "nonregular"), ("capture.scpt", "symlink"),
            ("extract-current-page.js", "wrong_mode"), ("extract-current-page.js", "nonregular"),
            ("extract-current-page.js", "symlink"), ("manifest.json", "wrong_mode"),
            ("manifest.json", "nonregular"), ("manifest.json", "symlink"),
            ("current", "nonregular"), ("current", "bad_target"),
        )
        expected = status_bytes(StoreResult(CommandName.CAPTURE, CommandCode.RUNTIME_TAMPERED, False, False))
        for target, mutation in rows:
            with self.subTest(target=target, mutation=mutation), tempfile.TemporaryDirectory(prefix="mnemosyne-cli-") as directory:
                root = Path(directory) / "data"
                capture_script, _ = runtime_fixture(root)
                path = root / "runtime/current" if target == "current" else capture_script.parent / target
                match mutation:
                    case "wrong_mode":
                        path.chmod(0o644)
                    case "nonregular":
                        path.unlink()
                        path.mkdir(mode=0o700)
                    case "symlink":
                        path.unlink()
                        path.symlink_to("mnemosyne.pyz")
                    case "bad_target":
                        path.unlink()
                        path.symlink_to(f"releases/{'f' * 64}")

                # When: production capture validates the runtime under its store lock.
                with patch.object(Bridge, "snapshot") as snapshot, patch.object(Bridge, "extract") as extract, patch.object(Bridge, "notify") as notify, patch.object(CaptureStore, "capture") as capture:
                    exit_code, raw = invoke(["--data-root", str(root), "capture"])

                # Then: exact tamper output precedes every bridge, notification, and storage mutation.
                self.assertEqual((exit_code, raw), (1, expected))
                snapshot.assert_not_called()
                extract.assert_not_called()
                notify.assert_not_called()
                capture.assert_not_called()
                self.assertFalse((root / "captures").exists())

    def test_locked_store_result_rows_emit_exact_canonical_bytes_and_exits(self) -> None:
        # Given: every typed capture/export result row consumed by the CLI.
        rows = (
            (StoreResult(CommandName.CAPTURE, CommandCode.CAPTURED, True, True, "d1", "r1", "/p1"), 0),
            (StoreResult(CommandName.CAPTURE, CommandCode.REVISED, True, True, "d2", "r2", "/p2"), 0),
            (StoreResult(CommandName.CAPTURE, CommandCode.DUPLICATE, True, False, "d3", "r3", "/p3"), 0),
            (StoreResult(CommandName.CAPTURE, CommandCode.DUPLICATE, True, True, "d4", "r4", "/p4"), 0),
            (StoreResult(CommandName.CAPTURE, CommandCode.WRITE_FAILED, False, False), 1),
            (StoreResult(CommandName.CAPTURE, CommandCode.WRITE_FAILED, False, True), 1),
            (StoreResult(CommandName.CAPTURE, CommandCode.CORRUPT_CANONICAL, False, False), 1),
            (StoreResult(CommandName.CAPTURE, CommandCode.CAPTURED_EXPORT_STALE, False, False, "d5", "r5", "/p5", (WarningCode.EXPORT_WRITE_FAILED,)), 2),
            (StoreResult(CommandName.CAPTURE, CommandCode.CAPTURED_EXPORT_STALE, False, True, "d6", "r6", "/p6", (WarningCode.CORRUPT_CANONICAL,)), 2),
            (StoreResult(CommandName.EXPORT, CommandCode.EXPORTED, True, False, path="/posts"), 0),
            (StoreResult(CommandName.EXPORT, CommandCode.EXPORTED, True, True, path="/posts"), 0),
            (StoreResult(CommandName.EXPORT, CommandCode.WRITE_FAILED, False, False), 1),
            (StoreResult(CommandName.EXPORT, CommandCode.WRITE_FAILED, False, True), 1),
            (StoreResult(CommandName.EXPORT, CommandCode.CORRUPT_CANONICAL, False, False), 1),
        )
        for stored, expected_exit in rows:
            with self.subTest(command=stored.command, code=stored.code, changed=stored.changed), tempfile.TemporaryDirectory(prefix="mnemosyne-cli-") as directory:
                base = Path(directory)

                # When: the CLI receives the typed result through its matching public store operation.
                match stored.command:
                    case CommandName.CAPTURE:
                        capture_script, extractor_script = write_artifacts(base)
                        with patch.object(Bridge, "snapshot", return_value=SnapshotResult(URL)), patch.object(Bridge, "extract", return_value=ExtractResult(URL, URL, payload())), patch.object(Bridge, "notify"), patch.object(CaptureStore, "capture", return_value=stored):
                            actual = invoke(["--data-root", str(base / "data"), "capture"], capture_script=capture_script, extractor_script=extractor_script)
                    case CommandName.EXPORT:
                        with patch.object(CaptureStore, "export", return_value=stored):
                            actual = invoke(["--data-root", str(base / "data"), "export"])

                # Then: exit and every canonical stdout byte equal the locked result contract.
                self.assertEqual(actual, (expected_exit, status_bytes(stored)))

    def test_production_lock_is_held_through_notification_and_result(self) -> None:
        # Given: a valid installed runtime and a second process ready to export.
        with tempfile.TemporaryDirectory(prefix="mnemosyne-cli-") as directory:
            root = Path(directory) / "data"
            runtime_fixture(root)
            context = multiprocessing.get_context("spawn")
            started = context.Event()
            results = context.Queue()
            process = context.Process(target=export_in_process, args=(str(root), started, results))

            def notify_while_locked(_title: str, _body: str) -> None:
                process.start()
                self.assertTrue(started.wait(timeout=5))
                with self.assertRaises(queue.Empty):
                    results.get(timeout=0.2)

            # When: production capture reaches its visible notification.
            with patch.object(Bridge, "snapshot", return_value=SnapshotResult(URL)), patch.object(Bridge, "extract", return_value=ExtractResult(URL, URL, payload())), patch.object(Bridge, "notify", side_effect=notify_while_locked):
                exit_code, raw = invoke(["--data-root", str(root), "capture"])
            process.join(timeout=5)

            # Then: the waiter starts only after capture releases the lock at final result.
            self.assertEqual((exit_code, json.loads(raw)["code"]), (0, "CAPTURED"))
            self.assertFalse(process.is_alive())
            self.assertEqual(process.exitcode, 0)
            waiter_exit, waiter_raw = results.get(timeout=1)
            self.assertEqual((waiter_exit, json.loads(waiter_raw)["code"]), (0, "EXPORTED"))


if __name__ == "__main__":
    unittest.main()
