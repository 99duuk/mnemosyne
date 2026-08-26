from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
import struct
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Final, Iterator
from zoneinfo import ZoneInfo

from .enums import CommandCode, CommandName, WarningCode
from .model import CaptureContext, canonical_record_bytes, create_capture, render_jsonl_line, render_markdown, revision_preimage
from .payload import CapturePayload

# noqa: SIZE_OK — one locked persistence transaction with inseparable durability ordering.

_DIR_MODE: Final = 0o700
_FILE_MODE: Final = 0o600
_STAGE_PREFIX: Final = "mnemosyne-stage-"
_STAGE_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")
_BLOG_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_POST_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
_REVISION_ID = re.compile(r"[0-9a-f]{64}\Z")
_CAPTURED_AT = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{6}[+]09:00\Z")
_SEOUL: Final = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True, slots=True)
class StoreResult:
    command: CommandName
    code: CommandCode
    ok: bool
    changed: bool
    document_key: str | None = None
    revision_id: str | None = None
    path: str | None = None
    warnings: tuple[WarningCode, ...] = ()


@dataclass(frozen=True, slots=True)
class _Bundle:
    path: Path
    record: dict
    body: str


class _Corrupt(Exception):
    pass


class _WriteFailure(Exception):
    def __init__(self, changed: bool) -> None:
        super().__init__(changed)
        self.changed = changed


class _ExportFailure(Exception):
    def __init__(self, changed: bool) -> None:
        super().__init__(changed)
        self.changed = changed


class CaptureStore:
    def __init__(self, root: Path, clock: Callable[[], datetime] | None = None) -> None:
        self.root = root.absolute()
        self._clock = clock or (lambda: datetime.now(_SEOUL))
        self._root_device: int | None = None
        self._root_fd: int | None = None

    def capture(self, payload: CapturePayload) -> StoreResult:
        try:
            with self._lock():
                bundles = self._scan()
                revision_id = hashlib.sha256(revision_preimage(payload)).hexdigest()
                existing = next((item for item in bundles if item.record["revision_id"] == revision_id), None)
                if existing is not None:
                    return self._duplicate(payload, existing, bundles)
                same_key = [item for item in bundles if item.record["document_key"] == self._document_key(payload)]
                captured_at = self._captured_at(bundles)
                latest = max(same_key, key=lambda item: (item.record["captured_at"], item.record["revision_id"]), default=None)
                capture = create_capture(payload, CaptureContext(captured_at, latest.record["revision_id"] if latest else None))
                bundle_path = self._commit(capture)
                try:
                    all_bundles = self._scan()
                    self._export_bytes(all_bundles)
                except (_Corrupt, _ExportFailure, OSError) as error:
                    warning = WarningCode.CORRUPT_CANONICAL if isinstance(error, _Corrupt) else WarningCode.EXPORT_WRITE_FAILED
                    return StoreResult(CommandName.CAPTURE, CommandCode.CAPTURED_EXPORT_STALE, False, True,
                                       capture.record.document_key, capture.record.revision_id, str(bundle_path),
                                       tuple(sorted((*capture.record.warnings, warning))))
                code = CommandCode.REVISED if same_key else CommandCode.CAPTURED
                return StoreResult(CommandName.CAPTURE, code, True, True, capture.record.document_key,
                                   capture.record.revision_id, str(bundle_path), capture.record.warnings)
        except _Corrupt:
            return self._failure(CommandName.CAPTURE, CommandCode.CORRUPT_CANONICAL)
        except _WriteFailure as error:
            return self._failure(CommandName.CAPTURE, CommandCode.WRITE_FAILED, error.changed)
        except OSError:
            return self._failure(CommandName.CAPTURE, CommandCode.WRITE_FAILED)

    def export(self) -> StoreResult:
        try:
            with self._lock():
                bundles = self._scan()
                changed = self._export_bytes(bundles)
                return StoreResult(CommandName.EXPORT, CommandCode.EXPORTED, True, changed, path=str(self.root / "posts.jsonl"))
        except _Corrupt:
            return self._failure(CommandName.EXPORT, CommandCode.CORRUPT_CANONICAL)
        except _ExportFailure as error:
            return self._failure(CommandName.EXPORT, CommandCode.WRITE_FAILED, error.changed)
        except _WriteFailure as error:
            return self._failure(CommandName.EXPORT, CommandCode.WRITE_FAILED, error.changed)
        except OSError:
            return self._failure(CommandName.EXPORT, CommandCode.WRITE_FAILED)

    def stale_stages(self) -> tuple[str, ...]:
        try:
            with self._lock():
                self._scan()
                return tuple(name.removeprefix(_STAGE_PREFIX) for name in self._stage_names())
        except (_Corrupt, _WriteFailure, OSError):
            return ()

    def discard_stage(self, stage_id: str) -> StoreResult:
        command = CommandName.DOCTOR_DISCARD_STAGE
        if _STAGE_ID.fullmatch(stage_id) is None:
            return self._failure(command, CommandCode.INVALID_ARGUMENT)
        changed = False
        stage = self.root / ".staging" / f"{_STAGE_PREFIX}{stage_id}"
        try:
            if self._empty_or_absent_root():
                return self._failure(command, CommandCode.STAGE_NOT_FOUND)
            with self._lock():
                self._scan()
                root_fd = self._require_root_fd()
                if not self._entry_exists_at(root_fd, ".staging"):
                    self._sync_dir_fd(root_fd, self.root)
                    return self._failure(command, CommandCode.STAGE_NOT_FOUND)
                staging_fd = self._open_dir_at(root_fd, ".staging")
                try:
                    stage_name = f"{_STAGE_PREFIX}{stage_id}"
                    if not self._entry_exists_at(staging_fd, stage_name):
                        self._sync_dir_fd(staging_fd, self.root / ".staging")
                        return self._failure(command, CommandCode.STAGE_NOT_FOUND)
                    stage_fd = self._open_dir_at(staging_fd, stage_name)
                    try:
                        self._validate_stage_at(stage_fd, stage_id)
                        entries = set(os.listdir(stage_fd))
                        if "bundle" in entries:
                            bundle_fd = self._open_dir_at(stage_fd, "bundle")
                            try:
                                members = set(os.listdir(bundle_fd))
                                for name in ("post.md", "record.json"):
                                    if name in members:
                                        self._unlink_file_at(bundle_fd, name)
                                        changed = True
                                        self._sync_dir_fd(bundle_fd, stage / "bundle")
                                self._require_same_entry(stage_fd, "bundle", bundle_fd)
                                self._validate_dir_fd(bundle_fd)
                                os.rmdir("bundle", dir_fd=stage_fd)
                            finally:
                                os.close(bundle_fd)
                            changed = True
                            self._sync_dir_fd(stage_fd, stage)
                        entries = set(os.listdir(stage_fd))
                        for name in ("owner.json", "owner.json.writing"):
                            if name in entries:
                                self._unlink_file_at(stage_fd, name)
                                changed = True
                                self._sync_dir_fd(stage_fd, stage)
                        if os.listdir(stage_fd):
                            raise _Corrupt
                        self._validate_dir_fd(stage_fd)
                        self._require_same_entry(staging_fd, stage_name, stage_fd)
                        os.rmdir(stage_name, dir_fd=staging_fd)
                    finally:
                        os.close(stage_fd)
                    changed = True
                    self._sync_dir_fd(staging_fd, self.root / ".staging")
                finally:
                    os.close(staging_fd)
                return StoreResult(command, CommandCode.STAGING_DISCARDED, True, True, path=str(stage))
        except _Corrupt:
            return self._failure(command, CommandCode.CORRUPT_CANONICAL)
        except (_WriteFailure, OSError):
            return self._failure(command, CommandCode.WRITE_FAILED, changed)

    def _duplicate(self, payload: CapturePayload, existing: _Bundle, bundles: list[_Bundle]) -> StoreResult:
        try:
            changed = self._export_bytes(bundles)
            return StoreResult(CommandName.CAPTURE, CommandCode.DUPLICATE, True, changed,
                               existing.record["document_key"], existing.record["revision_id"],
                               str(existing.path), payload.warnings)
        except (_Corrupt, _ExportFailure, OSError) as error:
            warning = WarningCode.CORRUPT_CANONICAL if isinstance(error, _Corrupt) else WarningCode.EXPORT_WRITE_FAILED
            changed = error.changed if isinstance(error, _ExportFailure) else True
            return StoreResult(CommandName.CAPTURE, CommandCode.CAPTURED_EXPORT_STALE, False, changed,
                               existing.record["document_key"], existing.record["revision_id"], str(existing.path),
                               tuple(sorted((*payload.warnings, warning))))

    @contextmanager
    def _lock(self) -> Iterator[None]:
        created_root = False
        created_lock = False
        parent = self.root.parent
        try:
            parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                if not self._entry_exists_at(parent_fd, self.root.name):
                    try:
                        os.mkdir(self.root.name, _DIR_MODE, dir_fd=parent_fd)
                        created_root = True
                        os.fsync(parent_fd)
                    except FileExistsError:
                        pass
                root_fd = os.open(self.root.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
                try:
                    self._validate_dir_fd(root_fd)
                    entries = set(os.listdir(root_fd))
                    if ".commit.lock" not in entries and entries:
                        raise _Corrupt
                    try:
                        lock_fd = os.open(".commit.lock", os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, _FILE_MODE, dir_fd=root_fd)
                        created_lock = True
                    except FileExistsError:
                        lock_fd = os.open(".commit.lock", os.O_RDWR | os.O_NOFOLLOW, dir_fd=root_fd)
                    try:
                        fcntl.flock(lock_fd, fcntl.LOCK_EX)
                        self._validate_dir_fd(root_fd)
                        self._validate_file_fd(lock_fd)
                        self._require_same_entry(parent_fd, self.root.name, root_fd)
                        self._require_same_entry(root_fd, ".commit.lock", lock_fd)
                        self._root_device = os.fstat(root_fd).st_dev
                        os.fsync(lock_fd)
                        os.fsync(root_fd)
                        os.fsync(parent_fd)
                        self._root_fd = root_fd
                        try:
                            yield
                        finally:
                            self._root_fd = None
                    finally:
                        os.close(lock_fd)
                finally:
                    os.close(root_fd)
            finally:
                os.close(parent_fd)
        except _Corrupt:
            raise
        except OSError as error:
            raise _WriteFailure(created_root or created_lock) from error

    def _scan(self) -> list[_Bundle]:
        root_fd = self._require_root_fd()
        allowed = {".commit.lock", "captures", ".staging", "posts.jsonl", ".posts.jsonl.writing", "runtime"}
        root_entries = set(os.listdir(root_fd))
        if not root_entries <= allowed:
            raise _Corrupt
        lock_fd = self._open_file_at(root_fd, ".commit.lock")
        os.close(lock_fd)
        for name in ("posts.jsonl", ".posts.jsonl.writing"):
            if name in root_entries:
                file_fd = self._open_file_at(root_fd, name)
                os.close(file_fd)
        self._validate_stages_at(root_fd)
        if "captures" not in root_entries:
            return []
        handles: list[tuple[int, int, str]] = []
        revision_parents: list[tuple[int, Path, str, str]] = []
        try:
            captures_fd = self._open_dir_at(root_fd, "captures")
            handles.append((captures_fd, root_fd, "captures"))
            for blog_name in sorted(os.listdir(captures_fd)):
                if _BLOG_ID.fullmatch(blog_name) is None:
                    raise _Corrupt
                blog_fd = self._open_dir_at(captures_fd, blog_name)
                handles.append((blog_fd, captures_fd, blog_name))
                for post_name in sorted(os.listdir(blog_fd)):
                    if _POST_ID.fullmatch(post_name) is None:
                        raise _Corrupt
                    post_fd = self._open_dir_at(blog_fd, post_name)
                    handles.append((post_fd, blog_fd, post_name))
                    entries = set(os.listdir(post_fd))
                    if not entries:
                        continue
                    if entries != {"revisions"}:
                        raise _Corrupt
                    revisions_fd = self._open_dir_at(post_fd, "revisions")
                    handles.append((revisions_fd, post_fd, "revisions"))
                    revision_parents.append((revisions_fd, self.root / "captures" / blog_name / post_name / "revisions", blog_name, post_name))
            for revisions_fd, revisions_path, _, _ in revision_parents:
                self._sync_dir_fd(revisions_fd, revisions_path)
            bundles: list[_Bundle] = []
            for revisions_fd, revisions_path, blog_name, post_name in revision_parents:
                for revision_name in sorted(os.listdir(revisions_fd)):
                    if _REVISION_ID.fullmatch(revision_name) is None:
                        raise _Corrupt
                    bundle_fd = self._open_dir_at(revisions_fd, revision_name)
                    handles.append((bundle_fd, revisions_fd, revision_name))
                    bundles.append(self._read_bundle_at(bundle_fd, revisions_path / revision_name, blog_name, post_name))
            for child_fd, parent_fd, name in handles:
                self._require_same_entry(parent_fd, name, child_fd)
            if set(os.listdir(root_fd)) != root_entries:
                raise _Corrupt
            self._validate_lineage(bundles)
            return bundles
        finally:
            for child_fd, _, _ in reversed(handles):
                os.close(child_fd)

    def _read_bundle_at(self, bundle_fd: int, path: Path, blog: str, post: str) -> _Bundle:
        if set(os.listdir(bundle_fd)) != {"post.md", "record.json"}:
            raise _Corrupt
        markdown = self._read_file_at(bundle_fd, "post.md")
        raw_record = self._read_file_at(bundle_fd, "record.json")
        try:
            record = json.loads(raw_record.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise _Corrupt from error
        fields = {"schema_version", "document_key", "revision_id", "supersedes_revision_id", "source", "title",
                  "published_at", "published_at_raw", "captured_at", "editor_fingerprint", "capture_method",
                  "rights_review_status", "warnings", "body_sha256", "markdown"}
        if type(record) is not dict or set(record) != fields or record["revision_id"] != path.name:
            raise _Corrupt
        if record["document_key"] != f"naver_blog:{blog}:{post}":
            raise _Corrupt
        source = record["source"]
        if type(source) is not dict or set(source) != {"platform", "blog_id", "post_id", "observed_url", "canonical_url"}:
            raise _Corrupt
        if (source["platform"], source["blog_id"], source["post_id"], source["canonical_url"]) != (
            "naver_blog", blog, post, f"https://blog.naver.com/{blog}/{post}"
        ):
            raise _Corrupt
        if type(source["observed_url"]) is not str:
            raise _Corrupt
        if record["schema_version"] != "mnemosyne.capture/v1" or record["editor_fingerprint"] != "smarteditor_one":
            raise _Corrupt
        if record["capture_method"] != "safari_automator_current_tab" or record["rights_review_status"] != "UNREVIEWED":
            raise _Corrupt
        if any(type(record[name]) is not str for name in ("document_key", "revision_id", "title", "published_at_raw", "captured_at", "body_sha256")):
            raise _Corrupt
        if record["published_at"] is not None and type(record["published_at"]) is not str:
            raise _Corrupt
        warning_values = {warning.value for warning in WarningCode if warning not in {WarningCode.CORRUPT_CANONICAL, WarningCode.EXPORT_WRITE_FAILED, WarningCode.NOTIFICATION_FAILED}}
        if (type(record["warnings"]) is not list or any(type(value) is not str or value not in warning_values for value in record["warnings"])
                or record["warnings"] != sorted(set(record["warnings"]))):
            raise _Corrupt
        if record["supersedes_revision_id"] is not None and (
            type(record["supersedes_revision_id"]) is not str or _REVISION_ID.fullmatch(record["supersedes_revision_id"]) is None
        ):
            raise _Corrupt
        if _CAPTURED_AT.fullmatch(record["captured_at"]) is None:
            raise _Corrupt
        try:
            datetime.fromisoformat(record["captured_at"])
        except (TypeError, ValueError) as error:
            raise _Corrupt from error
        if canonical_record_bytes_from_mapping(record) != raw_record:
            raise _Corrupt
        descriptor = record["markdown"]
        if type(descriptor) is not dict or descriptor != {"path": "post.md", "sha256": hashlib.sha256(markdown).hexdigest(), "bytes": len(markdown)}:
            raise _Corrupt
        marker = b"---\n\n"
        split = markdown.find(marker)
        if split < 0:
            raise _Corrupt
        body_bytes = markdown[split + len(marker):]
        try:
            body = body_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            raise _Corrupt from error
        if not body.endswith("\n") or hashlib.sha256(body_bytes).hexdigest() != record["body_sha256"]:
            raise _Corrupt
        header_fields = (
            ("schema_version", record["schema_version"]), ("document_key", record["document_key"]),
            ("revision_id", record["revision_id"]), ("title", record["title"]),
            ("published_at", record["published_at"]), ("published_at_raw", record["published_at_raw"]),
            ("canonical_url", source["canonical_url"]), ("captured_at", record["captured_at"]),
            ("rights_review_status", record["rights_review_status"]),
        )
        header = "---\n" + "\n".join(
            f"{key}: {'null' if value is None else json.dumps(value, ensure_ascii=False)}" for key, value in header_fields
        ) + "\n---\n\n"
        if markdown != header.encode() + body_bytes:
            raise _Corrupt
        date_discriminator = "P" if record["published_at"] is not None else "R"
        date_value = record["published_at"] if record["published_at"] is not None else record["published_at_raw"]
        revision_fields = (record["document_key"], record["title"], date_discriminator, date_value, body)
        revision_bytes = b"mnemosyne.capture.revision/v1\n" + b"".join(
            struct.pack(">Q", len(value.encode())) + value.encode() for value in revision_fields
        )
        if hashlib.sha256(revision_bytes).hexdigest() != record["revision_id"]:
            raise _Corrupt
        return _Bundle(path, record, body)

    def _validate_lineage(self, bundles: list[_Bundle]) -> None:
        keys = {bundle.record["document_key"] for bundle in bundles}
        for document_key in keys:
            history = sorted(
                (bundle for bundle in bundles if bundle.record["document_key"] == document_key),
                key=lambda bundle: (bundle.record["captured_at"], bundle.record["revision_id"]),
            )
            expected: str | None = None
            for bundle in history:
                if bundle.record["supersedes_revision_id"] != expected:
                    raise _Corrupt
                expected = bundle.record["revision_id"]

    def _commit(self, capture) -> Path:
        root_fd = self._require_root_fd()
        opened: list[int] = []
        created: list[tuple[int, str, int, Path]] = []
        stage_fd: int | None = None
        staging_fd: int | None = None
        stage_name: str | None = None
        renamed = False
        revisions_fd: int | None = None
        revision_id: str | None = None
        try:
            blog_name = capture.record.source.blog_id
            post_name = capture.record.source.post_id
            captures_fd = self._ensure_dir_at(root_fd, "captures", self.root / "captures", opened, created)
            blog_fd = self._ensure_dir_at(captures_fd, blog_name, self.root / "captures" / blog_name, opened, created)
            post_fd = self._ensure_dir_at(blog_fd, post_name, self.root / "captures" / blog_name / post_name, opened, created)
            target = self.root / "captures" / blog_name / post_name / "revisions"
            revisions_fd = self._ensure_dir_at(post_fd, "revisions", target, opened, created)
            staging_fd = self._ensure_dir_at(root_fd, ".staging", self.root / ".staging", opened, created)
            for descriptor, path in ((revisions_fd, target), (post_fd, target.parent), (blog_fd, target.parent.parent),
                                     (captures_fd, target.parent.parent.parent), (root_fd, self.root)):
                self._sync_dir_fd(descriptor, path)
            stage_id = str(uuid.uuid4())
            stage_name = f"{_STAGE_PREFIX}{stage_id}"
            os.mkdir(stage_name, _DIR_MODE, dir_fd=staging_fd)
            self._sync_dir_fd(staging_fd, self.root / ".staging")
            stage_fd = self._open_dir_at(staging_fd, stage_name)
            opened.append(stage_fd)
            owner = canonical_record_bytes_from_mapping({"schema": "mnemosyne.stage/v1", "stage_id": stage_id})
            self._write_file_at(stage_fd, "owner.json.writing", owner)
            self._replace_file_at(stage_fd, "owner.json.writing", "owner.json")
            self._sync_dir_fd(stage_fd, self.root / ".staging" / stage_name)
            os.mkdir("bundle", _DIR_MODE, dir_fd=stage_fd)
            self._sync_dir_fd(stage_fd, self.root / ".staging" / stage_name)
            bundle_fd = self._open_dir_at(stage_fd, "bundle")
            opened.append(bundle_fd)
            self._write_file_at(bundle_fd, "post.md", render_markdown(capture))
            self._write_file_at(bundle_fd, "record.json", canonical_record_bytes(capture.record))
            self._sync_dir_fd(bundle_fd, self.root / ".staging" / stage_name / "bundle")
            revision_id = capture.record.revision_id
            self._rename_bundle_at(stage_fd, bundle_fd, revisions_fd, revision_id)
            renamed = True
            self._sync_dir_fd(stage_fd, self.root / ".staging" / stage_name)
            self._sync_dir_fd(revisions_fd, target)
            self._unlink_file_at(stage_fd, "owner.json")
            self._sync_dir_fd(stage_fd, self.root / ".staging" / stage_name)
            self._validate_dir_fd(stage_fd)
            self._require_same_entry(staging_fd, stage_name, stage_fd)
            os.rmdir(stage_name, dir_fd=staging_fd)
            os.close(stage_fd)
            opened.remove(stage_fd)
            stage_fd = None
            self._sync_dir_fd(staging_fd, self.root / ".staging")
            return target / capture.record.revision_id
        except _Corrupt:
            raise
        except OSError as error:
            if not renamed and revisions_fd is not None and revision_id is not None:
                renamed = self._entry_exists_at(revisions_fd, revision_id)
            if renamed:
                raise _WriteFailure(True) from error
            cleaned = self._cleanup_stage_at(staging_fd, stage_fd, stage_name)
            if stage_fd is not None and stage_fd in opened:
                os.close(stage_fd)
                opened.remove(stage_fd)
                stage_fd = None
            for parent_fd, name, descriptor, path in reversed(created):
                try:
                    self._validate_dir_fd(descriptor)
                    self._require_same_entry(parent_fd, name, descriptor)
                    os.rmdir(name, dir_fd=parent_fd)
                    if descriptor in opened:
                        os.close(descriptor)
                        opened.remove(descriptor)
                    self._sync_dir_fd(parent_fd, path.parent)
                except (OSError, _Corrupt):
                    cleaned = False
                    break
            raise _WriteFailure(not cleaned) from error
        finally:
            for descriptor in reversed(opened):
                os.close(descriptor)

    def _cleanup_stage_at(self, staging_fd: int | None, stage_fd: int | None, stage_name: str | None) -> bool:
        if staging_fd is None or stage_fd is None or stage_name is None:
            return True
        try:
            self._validate_stage_at(stage_fd, stage_name.removeprefix(_STAGE_PREFIX))
            entries = set(os.listdir(stage_fd))
            if "bundle" in entries:
                bundle_fd = self._open_dir_at(stage_fd, "bundle")
                try:
                    members = set(os.listdir(bundle_fd))
                    if not members <= {"post.md", "record.json"}:
                        raise _Corrupt
                    for name in ("post.md", "record.json"):
                        if name in members:
                            self._unlink_file_at(bundle_fd, name)
                            self._sync_dir_fd(bundle_fd, self.root / ".staging" / stage_name / "bundle")
                    self._validate_dir_fd(bundle_fd)
                    self._require_same_entry(stage_fd, "bundle", bundle_fd)
                    os.rmdir("bundle", dir_fd=stage_fd)
                finally:
                    os.close(bundle_fd)
                self._sync_dir_fd(stage_fd, self.root / ".staging" / stage_name)
            for name in ("owner.json", "owner.json.writing"):
                if name in os.listdir(stage_fd):
                    self._unlink_file_at(stage_fd, name)
                    self._sync_dir_fd(stage_fd, self.root / ".staging" / stage_name)
            if os.listdir(stage_fd):
                raise _Corrupt
            self._validate_dir_fd(stage_fd)
            self._require_same_entry(staging_fd, stage_name, stage_fd)
            os.rmdir(stage_name, dir_fd=staging_fd)
            self._sync_dir_fd(staging_fd, self.root / ".staging")
            return True
        except (OSError, _Corrupt):
            return False

    def _ensure_dir_at(
        self,
        parent_fd: int,
        name: str,
        path: Path,
        opened: list[int],
        created: list[tuple[int, str, int, Path]],
    ) -> int:
        if not self._entry_exists_at(parent_fd, name):
            try:
                os.mkdir(name, _DIR_MODE, dir_fd=parent_fd)
            except FileExistsError:
                pass
            else:
                descriptor = self._open_dir_at(parent_fd, name)
                opened.append(descriptor)
                created.append((parent_fd, name, descriptor, path))
                self._sync_dir_fd(parent_fd, path.parent)
                return descriptor
        descriptor = self._open_dir_at(parent_fd, name)
        opened.append(descriptor)
        return descriptor

    def _rename_bundle_at(self, stage_fd: int, bundle_fd: int, revisions_fd: int, revision_id: str) -> None:
        if set(os.listdir(bundle_fd)) != {"post.md", "record.json"} or self._entry_exists_at(revisions_fd, revision_id):
            raise _Corrupt
        members = []
        try:
            owner_fd = self._open_file_at(stage_fd, "owner.json")
            members.append(("owner.json", owner_fd))
            for name in ("post.md", "record.json"):
                member_fd = self._open_file_at(bundle_fd, name)
                members.append((name, member_fd))
            self._require_same_entry(stage_fd, "bundle", bundle_fd)
            for name, member_fd in members:
                self._validate_file_fd(member_fd)
                self._require_same_entry(stage_fd if name == "owner.json" else bundle_fd, name, member_fd)
            os.rename("bundle", revision_id, src_dir_fd=stage_fd, dst_dir_fd=revisions_fd)
            self._require_same_entry(revisions_fd, revision_id, bundle_fd)
            for name, member_fd in members:
                self._validate_file_fd(member_fd)
                self._require_same_entry(stage_fd if name == "owner.json" else bundle_fd, name, member_fd)
        finally:
            for _, member_fd in members:
                os.close(member_fd)

    def _export_bytes(self, bundles: list[_Bundle]) -> bool:
        expected = b"".join(canonical_record_bytes_from_mapping({**item.record, "body": item.body})
                            for item in sorted(bundles, key=lambda item: (item.record["document_key"], item.record["captured_at"], item.record["revision_id"])))
        root_fd = self._require_root_fd()
        final_name = "posts.jsonl"
        temporary_name = ".posts.jsonl.writing"
        baseline = self._read_file_at(root_fd, final_name) if self._entry_exists_at(root_fd, final_name) else None
        if baseline == expected:
            if self._entry_exists_at(root_fd, temporary_name):
                self._unlink_file_at(root_fd, temporary_name)
                self._sync_dir_fd(root_fd, self.root)
            self._sync_dir_fd(root_fd, self.root)
            return False
        try:
            self._write_file_at(root_fd, temporary_name, expected, replace_existing=True)
            self._replace_file_at(root_fd, temporary_name, final_name)
            self._sync_dir_fd(root_fd, self.root)
            return True
        except _Corrupt:
            raise
        except OSError as error:
            restored = False
            try:
                if self._entry_exists_at(root_fd, temporary_name):
                    self._unlink_file_at(root_fd, temporary_name)
                self._sync_dir_fd(root_fd, self.root)
                current = self._read_file_at(root_fd, final_name) if self._entry_exists_at(root_fd, final_name) else None
                restored = current == baseline
            except (OSError, _Corrupt):
                restored = False
            raise _ExportFailure(not restored) from error

    def _stage_names(self) -> tuple[str, ...]:
        root_fd = self._require_root_fd()
        if ".staging" not in os.listdir(root_fd):
            return ()
        parent_fd = self._open_dir_at(root_fd, ".staging")
        try:
            names = tuple(sorted(os.listdir(parent_fd)))
            if any(not name.startswith(_STAGE_PREFIX) or _STAGE_ID.fullmatch(name.removeprefix(_STAGE_PREFIX)) is None for name in names):
                raise _Corrupt
            self._require_same_entry(root_fd, ".staging", parent_fd)
            return names
        finally:
            os.close(parent_fd)

    def _validate_stages_at(self, root_fd: int) -> None:
        if ".staging" not in os.listdir(root_fd):
            return
        staging_fd = self._open_dir_at(root_fd, ".staging")
        try:
            names = tuple(sorted(os.listdir(staging_fd)))
            for name in names:
                if not name.startswith(_STAGE_PREFIX) or _STAGE_ID.fullmatch(name.removeprefix(_STAGE_PREFIX)) is None:
                    raise _Corrupt
                stage_fd = self._open_dir_at(staging_fd, name)
                try:
                    self._validate_stage_at(stage_fd, name.removeprefix(_STAGE_PREFIX))
                    self._require_same_entry(staging_fd, name, stage_fd)
                finally:
                    os.close(stage_fd)
            self._require_same_entry(root_fd, ".staging", staging_fd)
        finally:
            os.close(staging_fd)

    def _validate_stage_at(self, stage_fd: int, stage_id: str) -> None:
        entries = set(os.listdir(stage_fd))
        owner = canonical_record_bytes_from_mapping({"schema": "mnemosyne.stage/v1", "stage_id": stage_id})
        if not entries:
            return
        if entries == {"owner.json.writing"}:
            if not owner.startswith(self._read_file_at(stage_fd, "owner.json.writing")):
                raise _Corrupt
            return
        if not entries <= {"owner.json", "bundle"} or "owner.json" not in entries:
            raise _Corrupt
        if self._read_file_at(stage_fd, "owner.json") != owner:
            raise _Corrupt
        if "bundle" in entries:
            bundle_fd = self._open_dir_at(stage_fd, "bundle")
            try:
                members = set(os.listdir(bundle_fd))
                if not members <= {"post.md", "record.json"}:
                    raise _Corrupt
                for member in members:
                    file_fd = self._open_file_at(bundle_fd, member)
                    os.close(file_fd)
                self._require_same_entry(stage_fd, "bundle", bundle_fd)
            finally:
                os.close(bundle_fd)

    def _require_root_fd(self) -> int:
        if self._root_fd is None:
            raise _Corrupt
        return self._root_fd

    def _open_dir_at(self, parent_fd: int, name: str) -> int:
        try:
            descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        except OSError as error:
            raise _Corrupt from error
        try:
            self._validate_dir_fd(descriptor)
            self._require_same_entry(parent_fd, name, descriptor)
            return descriptor
        except _Corrupt:
            os.close(descriptor)
            raise

    def _open_file_at(self, parent_fd: int, name: str, flags: int = os.O_RDONLY) -> int:
        try:
            descriptor = os.open(name, flags | os.O_NOFOLLOW, dir_fd=parent_fd)
        except OSError as error:
            raise _Corrupt from error
        try:
            self._validate_file_fd(descriptor)
            self._require_same_entry(parent_fd, name, descriptor)
            return descriptor
        except _Corrupt:
            os.close(descriptor)
            raise

    def _read_file_at(self, parent_fd: int, name: str) -> bytes:
        descriptor = self._open_file_at(parent_fd, name)
        try:
            chunks = []
            while chunk := os.read(descriptor, 1_048_576):
                chunks.append(chunk)
            self._validate_file_fd(descriptor)
            self._require_same_entry(parent_fd, name, descriptor)
            return b"".join(chunks)
        finally:
            os.close(descriptor)

    def _require_same_entry(self, parent_fd: int, name: str, descriptor: int) -> None:
        try:
            namespace_status = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except OSError as error:
            raise _Corrupt from error
        opened_status = os.fstat(descriptor)
        if (namespace_status.st_dev, namespace_status.st_ino) != (opened_status.st_dev, opened_status.st_ino):
            raise _Corrupt

    def _entry_exists_at(self, parent_fd: int, name: str) -> bool:
        try:
            os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return False
        except OSError as error:
            raise _Corrupt from error
        return True

    def _empty_or_absent_root(self) -> bool:
        parent_fd = os.open(self.root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if not self._entry_exists_at(parent_fd, self.root.name):
                return True
            root_fd = self._open_dir_at(parent_fd, self.root.name)
            try:
                return not os.listdir(root_fd)
            finally:
                os.close(root_fd)
        finally:
            os.close(parent_fd)

    def _write_file_at(self, parent_fd: int, name: str, data: bytes, replace_existing: bool = False) -> None:
        if replace_existing and self._entry_exists_at(parent_fd, name):
            descriptor = self._open_file_at(parent_fd, name, os.O_WRONLY)
            os.ftruncate(descriptor, 0)
        else:
            try:
                descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, _FILE_MODE, dir_fd=parent_fd)
            except FileExistsError as error:
                raise _Corrupt from error
        try:
            os.fchmod(descriptor, _FILE_MODE)
            view = memoryview(data)
            while view:
                view = view[os.write(descriptor, view):]
            os.fsync(descriptor)
            self._validate_file_fd(descriptor)
            self._require_same_entry(parent_fd, name, descriptor)
        finally:
            os.close(descriptor)

    def _unlink_file_at(self, parent_fd: int, name: str) -> None:
        descriptor = self._open_file_at(parent_fd, name)
        try:
            self._validate_file_fd(descriptor)
            self._require_same_entry(parent_fd, name, descriptor)
            os.unlink(name, dir_fd=parent_fd)
        finally:
            os.close(descriptor)

    def _replace_file_at(self, parent_fd: int, source: str, target: str) -> None:
        source_fd = self._open_file_at(parent_fd, source)
        target_fd: int | None = None
        try:
            if self._entry_exists_at(parent_fd, target):
                target_fd = self._open_file_at(parent_fd, target)
            self._validate_file_fd(source_fd)
            self._require_same_entry(parent_fd, source, source_fd)
            if target_fd is not None:
                self._validate_file_fd(target_fd)
                self._require_same_entry(parent_fd, target, target_fd)
            os.replace(source, target, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            self._validate_file_fd(source_fd)
            self._require_same_entry(parent_fd, target, source_fd)
        finally:
            if target_fd is not None:
                os.close(target_fd)
            os.close(source_fd)

    def _sync_dir_fd(self, descriptor: int, path: Path) -> None:
        self._validate_dir_fd(descriptor)
        os.fsync(descriptor)

    def _captured_at(self, bundles: list[_Bundle]) -> str:
        value = self._clock()
        value = value.replace(tzinfo=_SEOUL) if value.tzinfo is None else value.astimezone(_SEOUL)
        if bundles:
            greatest = max(datetime.fromisoformat(item.record["captured_at"]) for item in bundles)
            if value <= greatest:
                value = greatest + timedelta(microseconds=1)
        return value.isoformat(timespec="microseconds")

    def _validate_file_fd(self, fd: int) -> None:
        status = os.fstat(fd)
        if not stat.S_ISREG(status.st_mode) or stat.S_IMODE(status.st_mode) != _FILE_MODE or status.st_uid != os.getuid() or status.st_nlink != 1:
            raise _Corrupt
        if self._root_device is not None and status.st_dev != self._root_device:
            raise _Corrupt

    def _validate_dir_fd(self, fd: int) -> None:
        status = os.fstat(fd)
        if not stat.S_ISDIR(status.st_mode) or stat.S_IMODE(status.st_mode) != _DIR_MODE or status.st_uid != os.getuid():
            raise _Corrupt
        if self._root_device is not None and status.st_dev != self._root_device:
            raise _Corrupt

    @staticmethod
    def _document_key(payload: CapturePayload) -> str:
        return f"naver_blog:{payload.identity.blog_id}:{payload.identity.post_id}"

    @staticmethod
    def _failure(command: CommandName, code: CommandCode, changed: bool = False) -> StoreResult:
        return StoreResult(command, code, False, changed)


def canonical_record_bytes_from_mapping(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
