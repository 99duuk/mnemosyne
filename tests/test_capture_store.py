from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import stat
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from mnemosyne_capture import CapturePayload, CommandCode
from mnemosyne_capture.store import CaptureStore

# noqa: SIZE_OK — indivisible filesystem durability and adversarial contract matrix.


def payload(title: str = "Alpha", body: str = "Body A\n", blog_id: str = "example_blog", post_id: str = "123") -> CapturePayload:
    observed_url = f"https://blog.naver.com/{blog_id}/{post_id}"
    value = {
        "schema": "mnemosyne.safari-extract/v1",
        "top_document_url": observed_url,
        "content_document_url": observed_url,
        "canonical_url": observed_url,
        "title": title,
        "published_at_raw": "2026. 8. 26. 9:05",
        "body": body,
        "editor_fingerprint": "smarteditor_one",
        "component_counts": {"images": 0, "tables": 0, "embeds": 0, "media": 0},
        "warnings": [],
    }
    return CapturePayload.from_json_bytes(json.dumps(value).encode(), observed_url)


class Clock:
    def __init__(self, *values: datetime) -> None:
        self._values = iter(values)

    def __call__(self) -> datetime:
        return next(self._values)


def mode(path: Path) -> int:
    return stat.S_IMODE(path.lstat().st_mode)


def namespace(root: Path) -> tuple[tuple[str, str, bytes], ...]:
    rows = []
    if root.exists():
        for path in sorted(root.rglob("*")):
            kind = "d" if path.is_dir() else "l" if path.is_symlink() else "f"
            rows.append((path.relative_to(root).as_posix(), kind, path.read_bytes() if kind == "f" else b""))
    return tuple(rows)


def concurrent_capture(root: str, gate, queue) -> None:
    gate.wait(timeout=10)
    result = CaptureStore(Path(root)).capture(payload())
    queue.put((result.code.value, result.changed, result.revision_id))


def make_complete_stage(root: Path, stage_id: str) -> Path:
    stage = root / ".staging" / f"mnemosyne-stage-{stage_id}"
    stage.mkdir(parents=True, mode=0o700)
    (root / ".staging").chmod(0o700)
    owner = (f'{{"schema":"mnemosyne.stage/v1","stage_id":"{stage_id}"}}\n').encode()
    (stage / "owner.json").write_bytes(owner)
    (stage / "owner.json").chmod(0o600)
    bundle = stage / "bundle"
    bundle.mkdir(mode=0o700)
    for name in ("post.md", "record.json"):
        (bundle / name).write_bytes(name.encode())
        (bundle / name).chmod(0o600)
    return stage


class CaptureStoreTests(unittest.TestCase):
    def test_capture_duplicate_revision_and_aba_are_immutable_and_monotonic(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
            root = Path(directory) / "data"
            instant = datetime.fromisoformat("2026-08-26T13:00:00+09:00")
            store = CaptureStore(root, Clock(instant, instant, instant))

            first = store.capture(payload())
            duplicate = store.capture(payload())
            revised = store.capture(payload("Beta", "Body B\n"))
            aba = store.capture(payload())

            self.assertEqual(
                [result.code for result in (first, duplicate, revised, aba)],
                [CommandCode.CAPTURED, CommandCode.DUPLICATE, CommandCode.REVISED, CommandCode.DUPLICATE],
            )
            self.assertEqual([result.changed for result in (first, duplicate, revised, aba)], [True, False, True, False])
            self.assertEqual(first.revision_id, duplicate.revision_id)
            self.assertEqual(first.revision_id, aba.revision_id)
            revisions = root / "captures/example_blog/123/revisions"
            self.assertEqual({path.name for path in revisions.iterdir()}, {first.revision_id, revised.revision_id})
            first_record = json.loads((Path(first.path) / "record.json").read_bytes())
            revised_record = json.loads((Path(revised.path) / "record.json").read_bytes())
            self.assertEqual(first_record["supersedes_revision_id"], None)
            self.assertEqual(revised_record["supersedes_revision_id"], first.revision_id)
            self.assertLess(first_record["captured_at"], revised_record["captured_at"])
            export_before = (root / "posts.jsonl").read_bytes()
            exported = store.export()
            self.assertFalse(exported.changed)
            self.assertEqual((root / "posts.jsonl").read_bytes(), export_before)
            lines = [json.loads(line) for line in export_before.splitlines()]
            self.assertEqual(len(lines), 2)
            for line in lines:
                self.assertEqual(hashlib.sha256(line["body"].encode()).hexdigest(), line["body_sha256"])

    def test_private_layout_and_fresh_store_duplicate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
            root = Path(directory) / "data"
            first = CaptureStore(root).capture(payload())
            reopened = CaptureStore(root).capture(payload())

            self.assertEqual(reopened.code, CommandCode.DUPLICATE)
            self.assertFalse(reopened.changed)
            self.assertEqual(mode(root), 0o700)
            self.assertEqual(mode(root / ".commit.lock"), 0o600)
            self.assertEqual(mode(root / "posts.jsonl"), 0o600)
            bundle = Path(first.path)
            self.assertEqual(set(path.name for path in bundle.iterdir()), {"post.md", "record.json"})
            self.assertEqual(mode(bundle), 0o700)
            self.assertEqual({mode(path) for path in bundle.iterdir()}, {0o600})

    def test_two_process_root_and_lock_race_commits_once(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
            root = Path(directory) / "data"
            context = multiprocessing.get_context("fork")
            gate = context.Barrier(2)
            queue = context.Queue()
            processes = [context.Process(target=concurrent_capture, args=(str(root), gate, queue)) for _ in range(2)]

            for process in processes:
                process.start()
            for process in processes:
                process.join(timeout=10)
                self.assertFalse(process.is_alive())
                self.assertEqual(process.exitcode, 0)
            results = [queue.get(timeout=2) for _ in processes]

            self.assertEqual(sorted(code for code, _, _ in results), ["CAPTURED", "DUPLICATE"])
            self.assertEqual(sorted(changed for _, changed, _ in results), [False, True])
            self.assertEqual(len({revision for _, _, revision in results}), 1)
            revisions = root / "captures/example_blog/123/revisions"
            self.assertEqual(len(tuple(revisions.iterdir())), 1)

    def test_reopener_can_acquire_lock_created_by_paused_creator(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
            root = Path(directory) / "data"
            root.mkdir(mode=0o700)
            lock = root / ".commit.lock"
            descriptor = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                result = CaptureStore(root).capture(payload())
            finally:
                os.close(descriptor)

            self.assertEqual(result.code, CommandCode.CAPTURED)
            self.assertEqual(mode(lock), 0o600)
            self.assertEqual(CaptureStore(root).capture(payload()).code, CommandCode.DUPLICATE)

    def test_root_and_lock_namespace_swaps_after_flock_are_rejected(self) -> None:
        for target in ("root", "lock"):
            with self.subTest(target=target), tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
                parent = Path(directory)
                root = parent / "data"
                root.mkdir(mode=0o700)
                (root / ".commit.lock").touch(mode=0o600)
                real_flock = __import__("fcntl").flock
                swapped = False

                def swap_after_flock(descriptor: int, operation: int) -> None:
                    nonlocal swapped
                    real_flock(descriptor, operation)
                    if swapped:
                        return
                    if target == "lock":
                        (root / ".commit.lock").rename(parent / "moved-lock")
                        (root / ".commit.lock").touch(mode=0o600)
                    else:
                        root.rename(parent / "moved-root")
                        root.mkdir(mode=0o700)
                        (root / ".commit.lock").touch(mode=0o600)
                    swapped = True

                with mock.patch("mnemosyne_capture.store.fcntl.flock", side_effect=swap_after_flock):
                    result = CaptureStore(root).capture(payload())

                self.assertTrue(swapped)
                self.assertEqual((result.code, result.changed), (CommandCode.CORRUPT_CANONICAL, False))
                self.assertFalse((root / "captures").exists())

    def test_valid_empty_prefix_is_ignored_and_reused_but_wrong_prefix_is_refused(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
            root = Path(directory) / "data"
            root.mkdir(mode=0o700)
            (root / ".commit.lock").touch(mode=0o600)
            empty = root / "captures/other/7/revisions"
            empty.mkdir(parents=True, mode=0o700)
            for path in (root / "captures", root / "captures/other", root / "captures/other/7"):
                path.chmod(0o700)

            result = CaptureStore(root).capture(payload())

            self.assertEqual(result.code, CommandCode.CAPTURED)
            self.assertTrue(empty.is_dir())
            (root / "captures/bad.name").mkdir(mode=0o700)
            before = namespace(root)
            corrupt = CaptureStore(root).export()
            self.assertEqual(corrupt.code, CommandCode.CORRUPT_CANONICAL)
            self.assertFalse(corrupt.changed)
            self.assertEqual(namespace(root), before)

    def test_symlink_mode_extra_and_hardlinks_fail_without_mutation(self) -> None:
        cases = ("extra", "mode", "symlink", "record-hardlink", "post-hardlink", "export-hardlink", "lock-hardlink")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
                root = Path(directory) / "data"
                first = CaptureStore(root).capture(payload())
                alias = Path(directory) / "alias"
                if case == "extra":
                    (root / "unexpected").write_bytes(b"x")
                elif case == "mode":
                    (Path(first.path) / "record.json").chmod(0o644)
                elif case == "symlink":
                    (root / "captures/example_blog/123/revisions/link").symlink_to(Path(first.path))
                elif case in {"record-hardlink", "post-hardlink"}:
                    os.link(Path(first.path) / ("record.json" if case == "record-hardlink" else "post.md"), alias)
                elif case == "export-hardlink":
                    os.link(root / "posts.jsonl", alias)
                else:
                    os.link(root / ".commit.lock", alias)
                before = namespace(root)
                alias_before = alias.read_bytes() if alias.exists() else None

                result = CaptureStore(root).export()

                self.assertEqual(result.code, CommandCode.CORRUPT_CANONICAL)
                self.assertFalse(result.changed)
                self.assertEqual(namespace(root), before)
                if alias_before is not None:
                    self.assertEqual(alias.read_bytes(), alias_before)

    def test_zero_revision_export_and_deterministic_repair(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
            root = Path(directory) / "data"
            first = CaptureStore(root).export()
            second = CaptureStore(root).export()
            self.assertEqual((first.code, first.changed), (CommandCode.EXPORTED, True))
            self.assertEqual((second.code, second.changed), (CommandCode.EXPORTED, False))
            self.assertEqual((root / "posts.jsonl").read_bytes(), b"")
            (root / "posts.jsonl").write_bytes(b"stale\n")
            repaired = CaptureStore(root).export()
            self.assertTrue(repaired.changed)
            self.assertEqual((root / "posts.jsonl").read_bytes(), b"")

    def test_replace_failure_preserves_old_export_and_reports_unchanged_when_cleaned(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
            root = Path(directory) / "data"
            store = CaptureStore(root)
            store.capture(payload())
            old = (root / "posts.jsonl").read_bytes()
            (root / "posts.jsonl").write_bytes(b"old authoritative\n")
            real_replace = os.replace

            def fault(source, target, *args, **kwargs):
                if target == "posts.jsonl" or str(target).endswith("posts.jsonl"):
                    raise OSError("replace fault")
                return real_replace(source, target, *args, **kwargs)

            with mock.patch("mnemosyne_capture.store.os.replace", side_effect=fault):
                result = store.export()

            self.assertEqual(result.code, CommandCode.WRITE_FAILED)
            self.assertFalse(result.changed)
            self.assertEqual((root / "posts.jsonl").read_bytes(), b"old authoritative\n")
            repaired = store.export()
            self.assertTrue(repaired.changed)
            self.assertEqual((root / "posts.jsonl").read_bytes(), old)

    def test_stale_stage_prefix_report_discard_and_absent_retry(self) -> None:
        exemplar_id = "12345678-1234-4234-8234-123456789abc"
        exemplar = (f'{{"schema":"mnemosyne.stage/v1","stage_id":"{exemplar_id}"}}\n').encode()
        prefixes = (*range(len(exemplar) + 1), None)
        for prefix in prefixes:
            with self.subTest(prefix=prefix), tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
                root = Path(directory) / "data"
                CaptureStore(root).export()
                stage_id = "12345678-1234-4234-8234-123456789abc"
                stage = root / ".staging" / f"mnemosyne-stage-{stage_id}"
                stage.mkdir(parents=True, mode=0o700)
                (root / ".staging").chmod(0o700)
                owner = (f'{{"schema":"mnemosyne.stage/v1","stage_id":"{stage_id}"}}\n').encode()
                if prefix is None:
                    (stage / "owner.json").write_bytes(owner)
                    (stage / "owner.json").chmod(0o600)
                    bundle = stage / "bundle"
                    bundle.mkdir(mode=0o700)
                    (bundle / "post.md").write_bytes(b"partial")
                    (bundle / "post.md").chmod(0o600)
                else:
                    (stage / "owner.json.writing").write_bytes(owner[:prefix])
                    (stage / "owner.json.writing").chmod(0o600)

                self.assertEqual(CaptureStore(root).stale_stages(), (stage_id,))
                discarded = CaptureStore(root).discard_stage(stage_id)
                absent = CaptureStore(root).discard_stage(stage_id)

                self.assertEqual((discarded.code, discarded.changed), (CommandCode.STAGING_DISCARDED, True))
                self.assertEqual((absent.code, absent.changed), (CommandCode.STAGE_NOT_FOUND, False))
                self.assertFalse(stage.exists())

    def test_stale_stage_tamper_and_hardlink_are_never_discarded(self) -> None:
        for case in ("trailing", "peer", "hardlink", "owner-hardlink", "post-hardlink", "record-hardlink"):
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
                root = Path(directory) / "data"
                CaptureStore(root).export()
                stage_id = "12345678-1234-4234-8234-123456789abc"
                stage = root / ".staging" / f"mnemosyne-stage-{stage_id}"
                stage.mkdir(parents=True, mode=0o700)
                (root / ".staging").chmod(0o700)
                owner = (f'{{"schema":"mnemosyne.stage/v1","stage_id":"{stage_id}"}}\n').encode()
                writing = stage / "owner.json.writing"
                writing.write_bytes(owner + (b"x" if case == "trailing" else b""))
                writing.chmod(0o600)
                alias = Path(directory) / "alias"
                if case == "peer":
                    (stage / "owner.json").write_bytes(owner)
                    (stage / "owner.json").chmod(0o600)
                elif case == "hardlink":
                    os.link(writing, alias)
                elif case in {"owner-hardlink", "post-hardlink", "record-hardlink"}:
                    writing.replace(stage / "owner.json")
                    bundle = stage / "bundle"
                    bundle.mkdir(mode=0o700)
                    member = bundle / ("post.md" if case == "post-hardlink" else "record.json")
                    member.write_bytes(b"partial")
                    member.chmod(0o600)
                    os.link(stage / "owner.json" if case == "owner-hardlink" else member, alias)
                before = namespace(root)

                result = CaptureStore(root).discard_stage(stage_id)

                self.assertEqual(result.code, CommandCode.CORRUPT_CANONICAL)
                self.assertFalse(result.changed)
                self.assertEqual(namespace(root), before)
                if case in {"hardlink", "owner-hardlink", "post-hardlink", "record-hardlink"}:
                    self.assertTrue(alias.exists())

    def test_preconsumption_parent_sync_failure_reads_no_bundle_and_changes_nothing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
            root = Path(directory) / "data"
            CaptureStore(root).capture(payload())
            before = namespace(root)
            store = CaptureStore(root)
            real_sync = store._sync_dir_fd

            def fault(descriptor: int, path: Path) -> None:
                if path.name == "revisions":
                    raise OSError("preconsumption sync fault")
                real_sync(descriptor, path)

            with mock.patch.object(store, "_sync_dir_fd", side_effect=fault):
                result = store.export()

            self.assertEqual((result.code, result.changed), (CommandCode.WRITE_FAILED, False))
            self.assertIsNone(result.document_key)
            self.assertEqual(namespace(root), before)

    def test_forged_supersedes_lineage_is_corrupt_canonical(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
            root = Path(directory) / "data"
            store = CaptureStore(root)
            first = store.capture(payload())
            revised = store.capture(payload("Beta", "Body B\n"))
            record_path = Path(revised.path) / "record.json"
            record = json.loads(record_path.read_bytes())
            self.assertEqual(record["supersedes_revision_id"], first.revision_id)
            record["supersedes_revision_id"] = "0" * 64
            record_path.write_bytes((json.dumps(record, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n").encode())

            result = store.export()

            self.assertEqual((result.code, result.changed), (CommandCode.CORRUPT_CANONICAL, False))

    def test_swapped_captures_symlink_cannot_redirect_authority_reads(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
            parent = Path(directory)
            victim = parent / "victim"
            foreign = parent / "foreign"
            CaptureStore(victim).capture(payload("Victim", "victim body\n"))
            CaptureStore(foreign).capture(payload("Foreign", "foreign body\n"))
            export_before = (victim / "posts.jsonl").read_bytes()
            moved = parent / "victim-captures-original"
            real_open = os.open
            swapped = False
            victim_status = victim.stat()

            def swap_after_open(path, flags, mode_bits=0o777, *, dir_fd=None):
                nonlocal swapped
                descriptor = real_open(path, flags, mode_bits, dir_fd=dir_fd)
                relative_capture = (
                    path == "captures" and dir_fd is not None
                    and (os.fstat(dir_fd).st_dev, os.fstat(dir_fd).st_ino) == (victim_status.st_dev, victim_status.st_ino)
                )
                if not swapped and (Path(path) == victim / "captures" or relative_capture):
                    os.rename(victim / "captures", moved)
                    (victim / "captures").symlink_to(foreign / "captures")
                    swapped = True
                return descriptor

            with mock.patch("mnemosyne_capture.store.os.open", side_effect=swap_after_open):
                result = CaptureStore(victim).export()

            self.assertTrue(swapped)
            self.assertEqual((result.code, result.changed), (CommandCode.CORRUPT_CANONICAL, False))
            self.assertEqual((victim / "posts.jsonl").read_bytes(), export_before)

    def test_capture_refuses_hardlinked_stage_writers_before_publication(self) -> None:
        for target_name in ("owner.json.writing", "post.md", "record.json"):
            with self.subTest(target_name=target_name), tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
                root = Path(directory) / "data"
                alias = Path(directory) / "outside-alias"
                real_fsync = os.fsync
                linked = False

                def link_after_file_sync(descriptor: int) -> None:
                    nonlocal linked
                    real_fsync(descriptor)
                    if linked or not (root / ".staging").exists():
                        return
                    matches = tuple((root / ".staging").glob(f"*/**/{target_name}"))
                    if matches:
                        os.link(matches[0], alias)
                        linked = True

                with mock.patch("mnemosyne_capture.store.os.fsync", side_effect=link_after_file_sync):
                    result = CaptureStore(root).capture(payload())

                self.assertTrue(linked)
                self.assertEqual((result.code, result.changed), (CommandCode.CORRUPT_CANONICAL, False))
                self.assertTrue(alias.exists())
                self.assertEqual(alias.read_bytes(), tuple((root / ".staging").glob(f"*/**/{target_name}"))[0].read_bytes())
                revisions = root / "captures/example_blog/123/revisions"
                self.assertEqual(tuple(revisions.iterdir()) if revisions.exists() else (), ())

    def test_capture_refuses_hardlinked_final_stage_owner_before_publication(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
            root = Path(directory) / "data"
            alias = Path(directory) / "outside-alias"
            store = CaptureStore(root)
            real_replace = store._replace_file_at

            def link_final_owner(parent_fd: int, source: str, target: str) -> None:
                real_replace(parent_fd, source, target)
                if target == "owner.json":
                    stages = tuple((root / ".staging").iterdir())
                    os.link(stages[0] / target, alias)

            with mock.patch.object(store, "_replace_file_at", side_effect=link_final_owner):
                result = store.capture(payload())

            self.assertEqual((result.code, result.changed), (CommandCode.CORRUPT_CANONICAL, False))
            owner = tuple((root / ".staging").glob("*/owner.json"))[0]
            self.assertEqual(alias.read_bytes(), owner.read_bytes())
            revisions = root / "captures/example_blog/123/revisions"
            self.assertEqual(tuple(revisions.iterdir()) if revisions.exists() else (), ())

    def test_export_rechecks_existing_target_hardlink_immediately_before_replace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
            root = Path(directory) / "data"
            CaptureStore(root).capture(payload())
            (root / "posts.jsonl").write_bytes(b"old\n")
            alias = Path(directory) / "outside-alias"
            store = CaptureStore(root)
            real_validate = store._validate_file_fd
            linked = False

            def inject(descriptor: int) -> None:
                nonlocal linked
                status = os.fstat(descriptor)
                writing = root / ".posts.jsonl.writing"
                if not linked and writing.exists() and (status.st_dev, status.st_ino) == (writing.stat().st_dev, writing.stat().st_ino):
                    os.link(root / "posts.jsonl", alias)
                    linked = True
                real_validate(descriptor)

            with mock.patch.object(store, "_validate_file_fd", side_effect=inject):
                result = store.export()

            self.assertTrue(linked)
            self.assertEqual((result.code, result.changed), (CommandCode.CORRUPT_CANONICAL, False))
            self.assertEqual(alias.read_bytes(), b"old\n")
            self.assertEqual((root / "posts.jsonl").read_bytes(), b"old\n")

    def test_duplicate_repair_failure_keeps_identity_and_old_export(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
            root = Path(directory) / "data"
            first = CaptureStore(root).capture(payload())
            (root / "posts.jsonl").write_bytes(b"old\n")
            old = (root / "posts.jsonl").read_bytes()

            with mock.patch("mnemosyne_capture.store.os.replace", side_effect=OSError("replace fault")):
                result = CaptureStore(root).capture(payload())

            self.assertEqual((result.code, result.changed), (CommandCode.CAPTURED_EXPORT_STALE, False))
            self.assertEqual((result.document_key, result.revision_id, result.path),
                             (first.document_key, first.revision_id, first.path))
            self.assertEqual(result.warnings, ("EXPORT_WRITE_FAILED",))
            self.assertEqual((root / "posts.jsonl").read_bytes(), old)

    def test_export_parent_sync_failure_exposes_complete_repair_and_retry_is_stable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
            root = Path(directory) / "data"
            CaptureStore(root).capture(payload())
            (root / "posts.jsonl").write_bytes(b"stale\n")
            store = CaptureStore(root)
            real_sync = store._sync_dir_fd
            faulted = False

            def fault(descriptor: int, path: Path) -> None:
                nonlocal faulted
                if path == root and not faulted:
                    faulted = True
                    raise OSError("export parent sync fault")
                real_sync(descriptor, path)

            with mock.patch.object(store, "_sync_dir_fd", side_effect=fault):
                failed = store.export()

            replacement = (root / "posts.jsonl").read_bytes()
            self.assertEqual((failed.code, failed.changed), (CommandCode.WRITE_FAILED, True))
            self.assertNotEqual(replacement, b"stale\n")
            repaired = CaptureStore(root).export()
            self.assertEqual((repaired.code, repaired.changed), (CommandCode.EXPORTED, False))
            self.assertEqual((root / "posts.jsonl").read_bytes(), replacement)

    def test_discard_failure_changed_tracks_first_and_terminal_boundaries(self) -> None:
        for terminal in (False, True):
            with self.subTest(terminal=terminal), tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
                root = Path(directory) / "data"
                CaptureStore(root).export()
                stage_id = "12345678-1234-4234-8234-123456789abc"
                stage = root / ".staging" / f"mnemosyne-stage-{stage_id}"
                stage.mkdir(parents=True, mode=0o700)
                (root / ".staging").chmod(0o700)
                owner = (f'{{"schema":"mnemosyne.stage/v1","stage_id":"{stage_id}"}}\n').encode()
                (stage / "owner.json").write_bytes(owner)
                (stage / "owner.json").chmod(0o600)
                store = CaptureStore(root)
                if terminal:
                    real_sync = store._sync_dir_fd

                    def sync_fault(descriptor: int, path: Path) -> None:
                        if path == root / ".staging" and not stage.exists():
                            raise OSError("terminal sync fault")
                        real_sync(descriptor, path)

                    patcher = mock.patch.object(store, "_sync_dir_fd", side_effect=sync_fault)
                else:
                    patcher = mock.patch.object(store, "_unlink_file_at", side_effect=OSError("first unlink fault"))
                with patcher:
                    result = store.discard_stage(stage_id)

                self.assertEqual((result.code, result.changed), (CommandCode.WRITE_FAILED, terminal))
                self.assertEqual(stage.exists(), not terminal)

    def test_commit_parent_sync_failure_is_changed_and_recoverable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
            root = Path(directory) / "data"
            store = CaptureStore(root)
            real_sync = store._sync_dir_fd
            renamed = False
            real_rename = store._rename_bundle_at

            def track_rename(*args) -> None:
                nonlocal renamed
                real_rename(*args)
                renamed = True

            def fault(descriptor: int, path: Path) -> None:
                if path.name == "revisions" and renamed:
                    raise OSError("parent sync fault")
                real_sync(descriptor, path)

            with mock.patch.object(store, "_rename_bundle_at", side_effect=track_rename):
                with mock.patch.object(store, "_sync_dir_fd", side_effect=fault):
                    failed = store.capture(payload())

            self.assertEqual((failed.code, failed.changed), (CommandCode.WRITE_FAILED, True))
            self.assertIsNone(failed.document_key)
            self.assertIsNone(failed.path)
            self.assertFalse((root / "posts.jsonl").exists())
            recovered = CaptureStore(root).capture(payload())
            self.assertEqual(recovered.code, CommandCode.DUPLICATE)
            self.assertTrue(recovered.changed)

    def test_bootstrap_fault_attribution_distinguishes_creator_and_reopener(self) -> None:
        cases = (("root-create", False, False), ("lock-create", True, False),
                 ("creator-flock", True, False), ("reopener-flock", True, True))
        for case, precreate_root, precreate_lock in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
                root = Path(directory) / "data"
                if precreate_root:
                    root.mkdir(mode=0o700)
                if precreate_lock:
                    (root / ".commit.lock").touch(mode=0o600)
                if case == "root-create":
                    patcher = mock.patch("mnemosyne_capture.store.os.mkdir", side_effect=OSError("root create"))
                elif case == "lock-create":
                    real_open = os.open

                    def open_fault(name, flags, *args, **kwargs):
                        if name == ".commit.lock" and flags & os.O_EXCL:
                            raise OSError("lock create")
                        return real_open(name, flags, *args, **kwargs)

                    patcher = mock.patch("mnemosyne_capture.store.os.open", side_effect=open_fault)
                else:
                    patcher = mock.patch("mnemosyne_capture.store.fcntl.flock", side_effect=OSError("flock"))
                with patcher:
                    result = CaptureStore(root).capture(payload())

                self.assertEqual(result.code, CommandCode.WRITE_FAILED)
                self.assertEqual(result.changed, case == "creator-flock")

    def test_bootstrap_sync_fault_attribution_tracks_only_published_boundaries(self) -> None:
        cases = (("lock", False, True), ("lock", True, False), ("root", False, True),
                 ("root", True, False), ("parent", False, True), ("parent", True, False))
        for target, preexisting_lock, expected_changed in cases:
            with self.subTest(target=target, preexisting_lock=preexisting_lock), tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
                root = Path(directory) / "data"
                root.mkdir(mode=0o700)
                if preexisting_lock:
                    (root / ".commit.lock").touch(mode=0o600)
                real_fsync = os.fsync
                faulted = False

                def fault(descriptor: int) -> None:
                    nonlocal faulted
                    status = os.fstat(descriptor)
                    lock = root / ".commit.lock"
                    matches = target == "lock" and stat.S_ISREG(status.st_mode)
                    matches |= target == "root" and (status.st_dev, status.st_ino) == (root.stat().st_dev, root.stat().st_ino)
                    matches |= target == "parent" and (status.st_dev, status.st_ino) == (root.parent.stat().st_dev, root.parent.stat().st_ino)
                    if matches and not faulted:
                        faulted = True
                        raise OSError("bootstrap sync")
                    real_fsync(descriptor)

                with mock.patch("mnemosyne_capture.store.os.fsync", side_effect=fault):
                    result = CaptureStore(root).capture(payload())

                self.assertTrue(faulted)
                self.assertEqual((result.code, result.changed), (CommandCode.WRITE_FAILED, expected_changed))

    def test_created_ancestor_sync_fault_is_cleaned_without_claiming_change(self) -> None:
        expected_parent = {
            "captures": "data", "example_blog": "captures", "123": "example_blog", "revisions": "123",
        }
        for created_name, parent_name in expected_parent.items():
            with self.subTest(created_name=created_name), tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
                root = Path(directory) / "data"
                root.mkdir(mode=0o700)
                (root / ".commit.lock").touch(mode=0o600)
                store = CaptureStore(root)
                real_sync = store._sync_dir_fd
                faulted = False

                def fault(descriptor: int, path: Path) -> None:
                    nonlocal faulted
                    if not faulted and path.name == parent_name:
                        faulted = True
                        raise OSError("ancestor parent sync")
                    real_sync(descriptor, path)

                with mock.patch.object(store, "_sync_dir_fd", side_effect=fault):
                    result = store.capture(payload())

                self.assertTrue(faulted)
                self.assertEqual((result.code, result.changed), (CommandCode.WRITE_FAILED, False))
                self.assertEqual(set(root.iterdir()), {root / ".commit.lock"})

    def test_post_rename_fault_preserves_bundle_owner_and_old_export(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
            root = Path(directory) / "data"
            CaptureStore(root).export()
            old_export = (root / "posts.jsonl").read_bytes()
            store = CaptureStore(root)
            real_rename = store._rename_bundle_at

            def fault(*args) -> None:
                real_rename(*args)
                raise OSError("after rename")

            with mock.patch.object(store, "_rename_bundle_at", side_effect=fault):
                result = store.capture(payload())

            self.assertEqual((result.code, result.changed), (CommandCode.WRITE_FAILED, True))
            self.assertIsNone(result.document_key)
            self.assertIsNone(result.path)
            self.assertEqual((root / "posts.jsonl").read_bytes(), old_export)
            revisions = tuple((root / "captures/example_blog/123/revisions").iterdir())
            self.assertEqual(len(revisions), 1)
            stages = tuple((root / ".staging").iterdir())
            self.assertEqual(len(stages), 1)
            self.assertEqual(set(path.name for path in stages[0].iterdir()), {"owner.json"})

    def test_discard_fault_matrix_preserves_revalidatable_suffix_and_changed(self) -> None:
        boundaries = (
            ("unlink", "post.md", False), ("sync", "bundle", True), ("unlink", "record.json", True),
            ("rmdir", "bundle", True), ("sync", "stage", True), ("unlink", "owner.json", True),
            ("rmdir", "stage", True), ("sync", ".staging", True),
        )
        stage_id = "12345678-1234-4234-8234-123456789abc"
        for operation, target, changed in boundaries:
            with self.subTest(operation=operation, target=target), tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
                root = Path(directory) / "data"
                CaptureStore(root).export()
                stage = make_complete_stage(root, stage_id)
                store = CaptureStore(root)
                faulted = False
                if operation == "unlink":
                    real_unlink = store._unlink_file_at

                    def unlink_fault(parent_fd: int, name: str) -> None:
                        nonlocal faulted
                        if not faulted and name == target:
                            faulted = True
                            raise OSError("unlink")
                        real_unlink(parent_fd, name)

                    patcher = mock.patch.object(store, "_unlink_file_at", side_effect=unlink_fault)
                elif operation == "rmdir":
                    real_rmdir = os.rmdir

                    def rmdir_fault(name, *args, **kwargs):
                        nonlocal faulted
                        matches = name == "bundle" if target == "bundle" else str(name).endswith(stage.name)
                        if not faulted and matches:
                            faulted = True
                            raise OSError("rmdir")
                        return real_rmdir(name, *args, **kwargs)

                    patcher = mock.patch("mnemosyne_capture.store.os.rmdir", side_effect=rmdir_fault)
                else:
                    real_sync = store._sync_dir_fd

                    def sync_fault(descriptor: int, path: Path) -> None:
                        nonlocal faulted
                        matches = path.name == "bundle" if target == "bundle" else path == stage if target == "stage" else path == root / ".staging" and not stage.exists()
                        if not faulted and matches:
                            faulted = True
                            raise OSError("sync")
                        real_sync(descriptor, path)

                    patcher = mock.patch.object(store, "_sync_dir_fd", side_effect=sync_fault)
                with patcher:
                    result = store.discard_stage(stage_id)

                self.assertTrue(faulted)
                self.assertEqual((result.code, result.changed), (CommandCode.WRITE_FAILED, changed))
                expected = CommandCode.STAGING_DISCARDED if stage.exists() else CommandCode.STAGE_NOT_FOUND
                retry = CaptureStore(root).discard_stage(stage_id)
                self.assertEqual(retry.code, expected)

    def test_stage_owner_and_bundle_prepublication_faults_leave_no_revision(self) -> None:
        cases = ("owner-create", "owner-write", "owner-fchmod", "owner-fsync", "owner-close",
                 "owner-replace", "owner-stage-sync", "post-write", "record-write", "bundle-sync", "rename")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
                root = Path(directory) / "data"
                store = CaptureStore(root)
                if case == "owner-create":
                    real_open = os.open

                    def open_fault(name, flags, *args, **kwargs):
                        if name == "owner.json.writing" and flags & os.O_EXCL:
                            raise OSError("owner create")
                        return real_open(name, flags, *args, **kwargs)

                    patcher = mock.patch("mnemosyne_capture.store.os.open", side_effect=open_fault)
                elif case == "owner-write":
                    patcher = mock.patch("mnemosyne_capture.store.os.write", side_effect=OSError("owner write"))
                elif case == "owner-fchmod":
                    real_fchmod = os.fchmod

                    def fchmod_fault(descriptor: int, bits: int) -> None:
                        if (root / ".staging").exists():
                            raise OSError("owner fchmod")
                        real_fchmod(descriptor, bits)

                    patcher = mock.patch("mnemosyne_capture.store.os.fchmod", side_effect=fchmod_fault)
                elif case == "owner-fsync":
                    real_fsync = os.fsync

                    def fsync_fault(descriptor: int) -> None:
                        if (root / ".staging").exists() and stat.S_ISREG(os.fstat(descriptor).st_mode):
                            raise OSError("owner fsync")
                        real_fsync(descriptor)

                    patcher = mock.patch("mnemosyne_capture.store.os.fsync", side_effect=fsync_fault)
                elif case == "owner-close":
                    real_open = os.open
                    real_close = os.close
                    owner_descriptor = None
                    close_faulted = False

                    def track_open(name, flags, *args, **kwargs):
                        nonlocal owner_descriptor
                        descriptor = real_open(name, flags, *args, **kwargs)
                        if name == "owner.json.writing":
                            owner_descriptor = descriptor
                        return descriptor

                    def close_fault(descriptor: int) -> None:
                        nonlocal owner_descriptor, close_faulted
                        real_close(descriptor)
                        if descriptor == owner_descriptor and not close_faulted:
                            close_faulted = True
                            owner_descriptor = None
                            raise OSError("owner close")

                    patcher = mock.patch("mnemosyne_capture.store.os.open", side_effect=track_open)
                    close_patcher = mock.patch("mnemosyne_capture.store.os.close", side_effect=close_fault)
                elif case == "owner-replace":
                    real_replace = os.replace

                    def replace_fault(source, target, *args, **kwargs):
                        if source == "owner.json.writing":
                            raise OSError("owner replace")
                        return real_replace(source, target, *args, **kwargs)

                    patcher = mock.patch("mnemosyne_capture.store.os.replace", side_effect=replace_fault)
                elif case in {"owner-stage-sync", "bundle-sync"}:
                    real_sync = store._sync_dir_fd
                    sync_faulted = False

                    def sync_fault(descriptor: int, path: Path) -> None:
                        nonlocal sync_faulted
                        is_stage = path.parent.name == ".staging" and path.name.startswith("mnemosyne-stage-")
                        if not sync_faulted and case == "owner-stage-sync" and is_stage and (path / "owner.json").exists() and not (path / "bundle").exists():
                            sync_faulted = True
                            raise OSError("owner stage sync")
                        if not sync_faulted and case == "bundle-sync" and path.name == "bundle":
                            sync_faulted = True
                            raise OSError("bundle sync")
                        real_sync(descriptor, path)

                    patcher = mock.patch.object(store, "_sync_dir_fd", side_effect=sync_fault)
                elif case in {"post-write", "record-write"}:
                    real_write = store._write_file_at
                    selected = case.removesuffix("-write") + ".md" if case == "post-write" else "record.json"

                    def write_fault(parent_fd: int, name: str, data: bytes, replace_existing: bool = False) -> None:
                        if name == selected:
                            raise OSError("bundle write")
                        real_write(parent_fd, name, data, replace_existing)

                    patcher = mock.patch.object(store, "_write_file_at", side_effect=write_fault)
                else:
                    patcher = mock.patch("mnemosyne_capture.store.os.rename", side_effect=OSError("rename"))
                with patcher:
                    if case == "owner-close":
                        with close_patcher:
                            result = store.capture(payload())
                    else:
                        result = store.capture(payload())

                self.assertEqual((result.code, result.changed), (CommandCode.WRITE_FAILED, False))
                revisions = root / "captures/example_blog/123/revisions"
                self.assertEqual(tuple(revisions.iterdir()) if revisions.exists() else (), ())

    def test_absent_stage_retry_syncs_selected_existing_parent(self) -> None:
        stage_id = "12345678-1234-4234-8234-123456789abc"
        for existing_staging in (False, True):
            with self.subTest(existing_staging=existing_staging), tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
                root = Path(directory) / "data"
                CaptureStore(root).export()
                if existing_staging:
                    (root / ".staging").mkdir(mode=0o700)
                store = CaptureStore(root)
                real_sync = store._sync_dir_fd
                selected = root / ".staging" if existing_staging else root
                faulted = False

                def fault(descriptor: int, path: Path) -> None:
                    nonlocal faulted
                    if path == selected and not faulted:
                        faulted = True
                        raise OSError("absence sync")
                    real_sync(descriptor, path)

                before = namespace(root)
                with mock.patch.object(store, "_sync_dir_fd", side_effect=fault):
                    result = store.discard_stage(stage_id)

                self.assertTrue(faulted)
                self.assertEqual((result.code, result.changed), (CommandCode.WRITE_FAILED, False))
                self.assertEqual(namespace(root), before)

    def test_prefix_owner_unlink_fault_is_unchanged_and_retryable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
            root = Path(directory) / "data"
            CaptureStore(root).export()
            stage_id = "12345678-1234-4234-8234-123456789abc"
            stage = root / ".staging" / f"mnemosyne-stage-{stage_id}"
            stage.mkdir(parents=True, mode=0o700)
            (root / ".staging").chmod(0o700)
            owner = (f'{{"schema":"mnemosyne.stage/v1","stage_id":"{stage_id}"}}\n').encode()
            (stage / "owner.json.writing").write_bytes(owner)
            (stage / "owner.json.writing").chmod(0o600)
            before = namespace(root)
            store = CaptureStore(root)

            with mock.patch.object(store, "_unlink_file_at", side_effect=OSError("owner writing unlink")):
                failed = store.discard_stage(stage_id)

            self.assertEqual((failed.code, failed.changed), (CommandCode.WRITE_FAILED, False))
            self.assertEqual(namespace(root), before)
            self.assertEqual(CaptureStore(root).discard_stage(stage_id).code, CommandCode.STAGING_DISCARDED)

    def test_post_rename_recovery_export_first_and_different_key_first(self) -> None:
        for recovery in ("export", "different-key"):
            with self.subTest(recovery=recovery), tempfile.TemporaryDirectory(prefix="mnemosyne-store-") as directory:
                root = Path(directory) / "data"
                CaptureStore(root).export()
                store = CaptureStore(root)
                real_rename = store._rename_bundle_at

                def rename_fault(*args) -> None:
                    real_rename(*args)
                    raise OSError("after rename")

                with mock.patch.object(store, "_rename_bundle_at", side_effect=rename_fault):
                    failed = store.capture(payload())
                self.assertEqual((failed.code, failed.changed), (CommandCode.WRITE_FAILED, True))
                syncs = []
                recovery_store = CaptureStore(root)
                real_sync = recovery_store._sync_dir_fd

                def record_sync(descriptor: int, path: Path) -> None:
                    if path.name == "revisions":
                        syncs.append(path)
                    real_sync(descriptor, path)

                with mock.patch.object(recovery_store, "_sync_dir_fd", side_effect=record_sync):
                    if recovery == "export":
                        result = recovery_store.export()
                        self.assertEqual(result.code, CommandCode.EXPORTED)
                    else:
                        result = recovery_store.capture(payload("Other", "Other body\n", "other_blog", "456"))
                        self.assertEqual(result.code, CommandCode.CAPTURED)
                self.assertIn(root / "captures/example_blog/123/revisions", syncs)
                rows = [json.loads(line) for line in (root / "posts.jsonl").read_bytes().splitlines()]
                self.assertEqual(len(rows), 1 if recovery == "export" else 2)
                stages = tuple((root / ".staging").iterdir())
                self.assertEqual(len(stages), 1)
                self.assertEqual(set(path.name for path in stages[0].iterdir()), {"owner.json"})


if __name__ == "__main__":
    unittest.main()
