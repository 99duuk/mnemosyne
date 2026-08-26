from __future__ import annotations

import json
import unittest

from mnemosyne_capture import (
    CaptureContext,
    CaptureModelError,
    CapturePayload,
    ModelErrorCode,
    canonical_record_bytes,
    create_capture,
    normalize_body,
    normalize_text,
    parse_naver_url,
    render_jsonl_line,
    render_markdown,
    revision_preimage,
)

# noqa: SIZE_OK — this file is the plan's indivisible byte/boundary/URL contract matrix.


OBSERVED_URL = (
    "https://blog.naver.com/example_blog/00123?"
    "blogId=example_blog&logNo=123&utm=x#frag"
)
CAPTURED_AT = "2026-08-26T13:08:33.123456+09:00"
REVISION_ID = "854c52fd7b780d5dc1cc3352d6ce753058678325b149d5d009e2cfee4b66a101"


def payload_dict(**changes: str | None) -> dict:
    payload = {
        "schema": "mnemosyne.safari-extract/v1",
        "top_document_url": "https://blog.naver.com/PostView.naver?blogId=example_blog&logNo=123",
        "content_document_url": "https://blog.naver.com/example_blog/123/",
        "canonical_url": "https://blog.naver.com/example_blog/123",
        "title": "  Cafe\u0301\u2003 Notes  ",
        "published_at_raw": "2026. 8. 26. 9:05",
        "body": "\r\nFirst  \r\n\r\nCafe\u0301\t \r\n",
        "editor_fingerprint": "smarteditor_one",
        "component_counts": {"images": 1, "tables": 0, "embeds": 0, "media": 0},
        "warnings": ["IMAGES_OMITTED"],
    }
    payload.update(changes)
    return payload


def payload_bytes(**changes: str | None) -> bytes:
    return json.dumps(payload_dict(**changes), ensure_ascii=True, separators=(",", ":")).encode()


class CaptureModelTests(unittest.TestCase):
    def assert_model_error(self, code: ModelErrorCode, action) -> None:
        with self.assertRaises(CaptureModelError) as caught:
            action()
        self.assertEqual(caught.exception.code, code)

    def test_revision_uses_five_exact_length_frames(self) -> None:
        capture = create_capture(
            CapturePayload.from_json_bytes(payload_bytes(), OBSERVED_URL),
            CaptureContext(captured_at=CAPTURED_AT),
        )

        self.assertEqual(capture.record.revision_id, REVISION_ID)
        self.assertEqual(
            revision_preimage(capture.draft).hex(),
            "6d6e656d6f73796e652e636170747572652e7265766973696f6e2f76310a"
            "000000000000001b6e617665725f626c6f673a6578616d706c655f626c6f673a313233"
            "000000000000000b436166c3a9204e6f746573"
            "000000000000000150"
            "0000000000000019323032362d30382d32365430393a30353a30302b30393a3030"
            "000000000000000d46697273740a0a436166c3a90a",
        )

    def test_unparseable_date_uses_exact_r_frame_golden(self) -> None:
        capture = create_capture(
            CapturePayload.from_json_bytes(payload_bytes(published_at_raw="2026-02-30"), OBSERVED_URL),
            CaptureContext(captured_at=CAPTURED_AT),
        )

        self.assertEqual(
            revision_preimage(capture.draft).hex(),
            "6d6e656d6f73796e652e636170747572652e7265766973696f6e2f76310a"
            "000000000000001b6e617665725f626c6f673a6578616d706c655f626c6f673a313233"
            "000000000000000b436166c3a9204e6f746573000000000000000152"
            "000000000000000a323032362d30322d3330000000000000000d46697273740a0a436166c3a90a",
        )
        self.assertEqual(capture.record.revision_id, "0256866a3b4d447f8bb8122efde87581cfa941223ba76093faca9bdf407ea791")
        self.assertEqual(tuple(capture.record.warnings), ("IMAGES_OMITTED", "PUBLISHED_AT_UNPARSED"))

    def test_normalization_and_date_contract(self) -> None:
        self.assertEqual(normalize_text(" \u2003Cafe\u0301\t notes \n"), "Café notes")
        self.assertEqual(normalize_body("\r\n a \t\r\n\r\n b\u00a0 \r\n \t\n"), " a\n\n b\u00a0\n")
        cases = [
            ("2026. 8. 26.", "2026-08-26", ()),
            ("2026. 8. 26. 9:05", "2026-08-26T09:05:00+09:00", ()),
            ("2026. 2. 30.", None, ("PUBLISHED_AT_UNPARSED",)),
            ("2026. 8. 26. 24:00", None, ("PUBLISHED_AT_UNPARSED",)),
            ("2026-08-26", None, ("PUBLISHED_AT_UNPARSED",)),
        ]
        for raw_date, published_at, warnings in cases:
            with self.subTest(raw_date=raw_date):
                data = payload_dict(published_at_raw=raw_date)
                data["component_counts"] = {"images": 0, "tables": 0, "embeds": 0, "media": 0}
                data["warnings"] = []
                capture = create_capture(
                    CapturePayload.from_json_bytes(json.dumps(data).encode(), OBSERVED_URL),
                    CaptureContext(captured_at=CAPTURED_AT),
                )
                self.assertEqual(capture.record.published_at, published_at)
                self.assertEqual(tuple(capture.record.warnings), warnings)

    def test_direct_and_postview_url_matrix(self) -> None:
        accepted = [
            ("https://blog.naver.com/a/1", "a", "1"),
            ("https://blog.naver.com/a/0001/", "a", "1"),
            ("https://blog.naver.com/a/1?x=y#fragment", "a", "1"),
            ("https://blog.naver.com/a/1?BlogId=ignored&LogNo=ignored", "a", "1"),
            ("https://blog.naver.com/a/0001?blogId=a&logNo=1", "a", "1"),
            ("https://blog.naver.com/a/1?x=y&blogId=a&logNo=0001#fragment", "a", "1"),
            ("https://blog.naver.com/PostView.naver?blogId=a&logNo=0001", "a", "1"),
            ("https://blog.naver.com/PostView.naver?x=y&blogId=a&logNo=1#z", "a", "1"),
        ]
        for url, blog_id, post_id in accepted:
            with self.subTest(url=url):
                identity = parse_naver_url(url)
                self.assertEqual((identity.blog_id, identity.post_id), (blog_id, post_id))
                self.assertEqual(identity.canonical_url, f"https://blog.naver.com/{blog_id}/{post_id}")

    def test_url_failures_preserve_origin_vs_identity_classification(self) -> None:
        origin_failures = [
            "not a url",
            "http://blog.naver.com/a/1",
            "HTTPS://blog.naver.com/a/1",
            "https://u@blog.naver.com/a/1",
            "https://blog.naver.com:443/a/1",
            "https://evil.example/a/1",
            "https://m.blog.naver.com/a/1",
        ]
        identity_failures = [
            "https://blog.naver.com/",
            "https://blog.naver.com/a/0",
            "https://blog.naver.com/a/1/extra",
            "https://blog.naver.com/%61/1",
            "https://blog.naver.com/a/%31",
            "https://blog.naver.com/a/1?blogId=a",
            "https://blog.naver.com/a/1?logNo=1",
            "https://blog.naver.com/a/1?blogId=a&blogId=a&logNo=1",
            "https://blog.naver.com/a/1?blogId=a&logNo=1&logNo=1",
            "https://blog.naver.com/a/1?blogId=b&logNo=1",
            "https://blog.naver.com/a/1?blogId=a&logNo=2",
            "https://blog.naver.com/a/1?blogId=%61&logNo=1",
            "https://blog.naver.com/a/1?blogId=a&logNo=%31",
            "https://blog.naver.com/PostView.naver",
            "https://blog.naver.com/PostView.naver?blogId=a",
            "https://blog.naver.com/PostView.naver?logNo=1",
            "https://blog.naver.com/PostView.naver?blogId=%61&logNo=1",
            "https://blog.naver.com/PostView.naver?blogId=a&logNo=%31",
            "https://blog.naver.com/PostView.naver?blogId=a&blogId=a&logNo=1",
            "https://blog.naver.com/PostView.naver?blogId=a&logNo=1&logNo=1",
            "https://blog.naver.com/PostView.naver/?blogId=a&logNo=1",
        ]
        for url in origin_failures:
            with self.subTest(url=url):
                self.assert_model_error(ModelErrorCode.UNSUPPORTED_HOST, lambda: parse_naver_url(url))
        for url in identity_failures:
            with self.subTest(url=url):
                self.assert_model_error(ModelErrorCode.UNSUPPORTED_PAGE, lambda: parse_naver_url(url))

    def test_payload_boundary_rejects_schema_size_controls_and_url_disagreement(self) -> None:
        base = payload_dict()
        for field in tuple(base):
            missing = base.copy()
            del missing[field]
            with self.subTest(missing=field):
                self.assert_model_error(
                    ModelErrorCode.INVALID_PAYLOAD,
                    lambda missing=missing: CapturePayload.from_json_bytes(json.dumps(missing).encode(), OBSERVED_URL),
                )
        wrong_types = {
            "schema": 1, "top_document_url": None, "content_document_url": 1,
            "canonical_url": 1, "title": 1, "published_at_raw": 1, "body": 1,
            "editor_fingerprint": 1, "component_counts": [], "warnings": "IMAGES_OMITTED",
        }
        for field, wrong in wrong_types.items():
            invalid = {**base, field: wrong}
            with self.subTest(wrong_type=field):
                self.assert_model_error(
                    ModelErrorCode.INVALID_PAYLOAD,
                    lambda invalid=invalid: CapturePayload.from_json_bytes(json.dumps(invalid).encode(), OBSERVED_URL),
                )
        invalid_payloads = [
            b"\xff",
            json.dumps({**payload_dict(), "extra": 1}).encode(),
            payload_bytes(schema="wrong"),
            payload_bytes(editor_fingerprint="legacy"),
            payload_bytes(title="a" * 4097),
            payload_bytes(title="a" * 501),
            payload_bytes(title="bad\x00title"),
            payload_bytes(published_at_raw="a" * 1025),
            payload_bytes(published_at_raw="a" * 129),
            payload_bytes(published_at_raw="bad\ntimestamp"),
            payload_bytes(body="a" * 10_485_761),
            payload_bytes(body="a" * 10_485_760),
            payload_bytes(body=" \t\r\n"),
            payload_bytes(body="bad\x01body"),
            payload_bytes(body="\ud800"),
            payload_bytes(top_document_url="https://blog.naver.com/other/123"),
            payload_bytes(content_document_url="https://m.blog.naver.com/example_blog/123"),
            payload_bytes(canonical_url="https://blog.naver.com/example_blog/124"),
            payload_bytes(canonical_url="https://blog.naver.com/" + "a" * 4097),
            payload_bytes(title="\ud800"),
            json.dumps({**payload_dict(), "warnings": []}).encode(),
            json.dumps({**payload_dict(), "component_counts": {"images": -1, "tables": 0, "embeds": 0, "media": 0}}).encode(),
            json.dumps({**payload_dict(), "component_counts": {"images": 1, "tables": 0, "embeds": 0}}).encode(),
            json.dumps({**payload_dict(), "component_counts": {"images": 1, "tables": 0, "embeds": 0, "media": 0, "extra": 0}}).encode(),
            json.dumps({**payload_dict(), "component_counts": {"images": "1", "tables": 0, "embeds": 0, "media": 0}}).encode(),
        ]
        for raw in invalid_payloads:
            with self.subTest(size=len(raw)):
                self.assert_model_error(
                    ModelErrorCode.INVALID_PAYLOAD,
                    lambda raw=raw: CapturePayload.from_json_bytes(raw, OBSERVED_URL),
                )
        self.assert_model_error(
            ModelErrorCode.UNSUPPORTED_HOST,
            lambda: CapturePayload.from_json_bytes(payload_bytes(), "https://m.blog.naver.com/a/1"),
        )
        self.assert_model_error(
            ModelErrorCode.UNSUPPORTED_HOST,
            lambda: CapturePayload.from_json_bytes(payload_bytes(), "https://blog.naver.com/" + "a" * 4097),
        )
        self.assertEqual(
            CapturePayload.from_json_bytes(payload_bytes(canonical_url=None), OBSERVED_URL).identity.post_id,
            "123",
        )

    def test_exact_raw_and_normalized_size_boundaries_are_accepted(self) -> None:
        title = ("a" * 499 + " ").ljust(4096)
        raw_date = "2026. 8. 26.".rjust(1024)
        body = "a" * 10_485_759 + "\n"
        observed = "https://blog.naver.com/a/1#" + "x" * (4096 - len("https://blog.naver.com/a/1#"))
        data = payload_dict(title=title, published_at_raw=raw_date, body=body)
        data["top_document_url"] = "https://blog.naver.com/a/1"
        data["content_document_url"] = "https://blog.naver.com/a/1"
        data["canonical_url"] = None

        parsed = CapturePayload.from_json_bytes(json.dumps(data).encode(), observed)

        self.assertEqual(len(observed.encode()), 4096)
        self.assertEqual(len(parsed.title), 499)
        self.assertEqual(parsed.published_at, "2026-08-26")
        self.assertEqual(len(parsed.body.encode()), 10_485_760)

        scalar_data = payload_dict(title="\U00010000" * 500, published_at_raw="\U00010000" * 128, body="x")
        scalar_parsed = CapturePayload.from_json_bytes(json.dumps(scalar_data).encode(), OBSERVED_URL)
        self.assertEqual((len(scalar_parsed.title), len(scalar_parsed.title.encode())), (500, 2000))
        self.assertEqual((len(scalar_parsed.published_at_raw), len(scalar_parsed.published_at_raw.encode())), (128, 512))

    def test_exact_markdown_record_and_inline_jsonl_bytes(self) -> None:
        capture = create_capture(
            CapturePayload.from_json_bytes(payload_bytes(), OBSERVED_URL),
            CaptureContext(captured_at=CAPTURED_AT),
        )
        markdown = (
            '---\nschema_version: "mnemosyne.capture/v1"\n'
            'document_key: "naver_blog:example_blog:123"\n'
            f'revision_id: "{REVISION_ID}"\n'
            'title: "Café Notes"\n'
            'published_at: "2026-08-26T09:05:00+09:00"\n'
            'published_at_raw: "2026. 8. 26. 9:05"\n'
            'canonical_url: "https://blog.naver.com/example_blog/123"\n'
            f'captured_at: "{CAPTURED_AT}"\n'
            'rights_review_status: "UNREVIEWED"\n---\n\nFirst\n\nCafé\n'
        ).encode()
        record_bytes = canonical_record_bytes(capture.record)
        expected_record = (
            '{"body_sha256":"9ddf582b0f7df4f1366116993e65a4d44814358fbf771bea79fd5efdf3f1ab2f",'
            '"capture_method":"safari_automator_current_tab","captured_at":"2026-08-26T13:08:33.123456+09:00",'
            '"document_key":"naver_blog:example_blog:123","editor_fingerprint":"smarteditor_one",'
            '"markdown":{"bytes":426,"path":"post.md","sha256":"e6be4ad38284b4cc65003584fdd1b66be725e5cd694ca4ff36e57b814d32d7e3"},'
            '"published_at":"2026-08-26T09:05:00+09:00","published_at_raw":"2026. 8. 26. 9:05",'
            f'"revision_id":"{REVISION_ID}","rights_review_status":"UNREVIEWED",'
            '"schema_version":"mnemosyne.capture/v1","source":{"blog_id":"example_blog",'
            '"canonical_url":"https://blog.naver.com/example_blog/123",'
            f'"observed_url":"{OBSERVED_URL}","platform":"naver_blog","post_id":"123"}},'
            '"supersedes_revision_id":null,"title":"Café Notes","warnings":["IMAGES_OMITTED"]}\n'
        ).encode()

        self.assertEqual(render_markdown(capture), markdown)
        self.assertEqual(len(markdown), 426)
        self.assertEqual(capture.record.markdown.sha256, "e6be4ad38284b4cc65003584fdd1b66be725e5cd694ca4ff36e57b814d32d7e3")
        self.assertEqual(record_bytes[-1:], b"\n")
        self.assertEqual(record_bytes, expected_record)
        self.assertEqual(json.loads(record_bytes)["source"]["observed_url"], OBSERVED_URL)
        jsonl = render_jsonl_line(capture)
        expected_jsonl = json.loads(expected_record)
        expected_jsonl["body"] = "First\n\nCafé\n"
        self.assertEqual(jsonl[-1:], b"\n")
        self.assertEqual(
            jsonl,
            (json.dumps(expected_jsonl, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n").encode(),
        )
        self.assertEqual(json.loads(jsonl)["body"], "First\n\nCafé\n")
        self.assertEqual(set(json.loads(jsonl)), set(json.loads(record_bytes)) | {"body"})

    def test_render_is_stable_and_observation_fields_do_not_change_revision(self) -> None:
        first = create_capture(
            CapturePayload.from_json_bytes(payload_bytes(), OBSERVED_URL),
            CaptureContext(captured_at=CAPTURED_AT),
        )
        second_url = "https://blog.naver.com/example_blog/123?x=second"
        second = create_capture(
            CapturePayload.from_json_bytes(payload_bytes(), second_url),
            CaptureContext(captured_at="2026-08-27T00:00:00.000000+09:00"),
        )

        self.assertEqual(render_markdown(first), render_markdown(first))
        self.assertEqual(canonical_record_bytes(first.record), canonical_record_bytes(first.record))
        self.assertEqual(first.record.revision_id, second.record.revision_id)
        self.assertNotEqual(canonical_record_bytes(first.record), canonical_record_bytes(second.record))


if __name__ == "__main__":
    unittest.main()
