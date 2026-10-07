"""F-01 Todo 목록 조회·추가 API 수용 기준 테스트."""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.server import create_server  # noqa: E402
from app.store import TodoStore  # noqa: E402

ISO_UTC_SECONDS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TodoApiTestCase(unittest.TestCase):
    """각 테스트마다 빈 저장소를 가진 서버를 임시 포트에 띄운다."""

    def setUp(self) -> None:
        self.store = TodoStore()
        self.server = create_server(port=0, host="127.0.0.1", store=self.store, quiet=True)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop_server)

    def _stop_server(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()

    # --- 요청 헬퍼 -------------------------------------------------------

    def _request(
        self, method: str, path: str, body: bytes | None = None
    ) -> tuple[int, dict, dict[str, str]]:
        req = urllib.request.Request(self.base_url + path, data=body, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                raw, status, headers = res.read(), res.status, dict(res.headers)
        except urllib.error.HTTPError as err:
            raw, status, headers = err.read(), err.code, dict(err.headers)
        payload = json.loads(raw.decode("utf-8")) if raw else {}
        return status, payload, headers

    def get_todos(self) -> tuple[int, dict]:
        status, payload, _ = self._request("GET", "/api/todos")
        return status, payload

    def post_todo(self, title: object) -> tuple[int, dict]:
        status, payload, _ = self._request(
            "POST", "/api/todos", json.dumps({"title": title}).encode("utf-8")
        )
        return status, payload

    def post_raw(self, body: bytes) -> tuple[int, dict]:
        status, payload, _ = self._request("POST", "/api/todos", body)
        return status, payload

    def assert_invalid_title(self, status: int, payload: dict) -> None:
        self.assertEqual(400, status)
        self.assertEqual("INVALID_TITLE", payload["code"])
        self.assertEqual("제목은 1~100자로 입력해 주세요.", payload["message"])

    # --- GET /api/todos --------------------------------------------------

    def test_get_returns_200_with_items(self) -> None:
        status, payload = self.get_todos()
        self.assertEqual(200, status)
        self.assertIn("items", payload)
        self.assertIsInstance(payload["items"], list)

    def test_get_returns_empty_list_when_no_todos(self) -> None:
        status, payload = self.get_todos()
        self.assertEqual(200, status)
        self.assertEqual([], payload["items"])

    def test_get_returns_items_ordered_by_id_ascending(self) -> None:
        for title in ("첫째", "둘째", "셋째"):
            self.assertEqual(201, self.post_todo(title)[0])

        _, payload = self.get_todos()
        self.assertEqual([1, 2, 3], [item["id"] for item in payload["items"]])
        self.assertEqual(["첫째", "둘째", "셋째"], [item["title"] for item in payload["items"]])

    # --- POST /api/todos -------------------------------------------------

    def test_post_valid_title_returns_201_with_created_todo(self) -> None:
        status, payload = self.post_todo("우유 사기")
        self.assertEqual(201, status)
        self.assertEqual(1, payload["id"])
        self.assertEqual("우유 사기", payload["title"])
        self.assertIs(False, payload["done"])
        self.assertRegex(payload["createdAt"], ISO_UTC_SECONDS)
        self.assertEqual({"id", "title", "done", "createdAt"}, set(payload))

    def test_created_todo_appears_in_subsequent_get(self) -> None:
        _, created = self.post_todo("빨래 하기")
        _, payload = self.get_todos()
        self.assertIn(created, payload["items"])

    def test_created_todo_is_not_done(self) -> None:
        _, created = self.post_todo("운동 하기")
        self.assertIs(False, created["done"])
        _, payload = self.get_todos()
        self.assertIs(False, payload["items"][0]["done"])

    def test_ids_increase_by_one_from_one(self) -> None:
        ids = [self.post_todo(f"할 일 {n}")[1]["id"] for n in range(1, 4)]
        self.assertEqual([1, 2, 3], ids)

    def test_post_trims_surrounding_whitespace(self) -> None:
        status, payload = self.post_todo("  우유 사기 \t\n")
        self.assertEqual(201, status)
        self.assertEqual("우유 사기", payload["title"])
        _, listed = self.get_todos()
        self.assertEqual("우유 사기", listed["items"][0]["title"])

    def test_post_accepts_boundary_lengths(self) -> None:
        self.assertEqual(201, self.post_todo("가")[0])
        self.assertEqual(201, self.post_todo("나" * 100)[0])

    # --- POST 검증 실패 ---------------------------------------------------

    def test_post_without_title_is_invalid(self) -> None:
        self.assert_invalid_title(*self.post_raw(b"{}"))

    def test_post_null_title_is_invalid(self) -> None:
        self.assert_invalid_title(*self.post_todo(None))

    def test_post_non_string_title_is_invalid(self) -> None:
        self.assert_invalid_title(*self.post_todo(123))
        self.assert_invalid_title(*self.post_todo(["우유 사기"]))

    def test_post_blank_title_is_invalid(self) -> None:
        self.assert_invalid_title(*self.post_todo(""))
        self.assert_invalid_title(*self.post_todo("   \t\n "))

    def test_post_title_over_100_chars_is_invalid(self) -> None:
        self.assert_invalid_title(*self.post_todo("가" * 101))

    def test_post_title_over_100_chars_after_trim_is_invalid(self) -> None:
        self.assert_invalid_title(*self.post_todo("  " + "가" * 101 + "  "))

    def test_post_malformed_json_is_invalid(self) -> None:
        self.assert_invalid_title(*self.post_raw(b'{"title": '))

    def test_post_empty_body_is_invalid(self) -> None:
        self.assert_invalid_title(*self.post_raw(b""))

    def test_post_non_object_json_is_invalid(self) -> None:
        self.assert_invalid_title(*self.post_raw(b'["우유 사기"]'))
        self.assert_invalid_title(*self.post_raw(b'"우유 사기"'))

    def test_failed_validation_adds_nothing_to_the_list(self) -> None:
        self.assert_invalid_title(*self.post_todo(""))
        self.assert_invalid_title(*self.post_todo("가" * 101))
        self.assert_invalid_title(*self.post_raw(b"nope"))

        _, payload = self.get_todos()
        self.assertEqual([], payload["items"])

    def test_id_sequence_is_unaffected_by_failed_validation(self) -> None:
        self.assert_invalid_title(*self.post_todo(""))
        status, payload = self.post_todo("우유 사기")
        self.assertEqual(201, status)
        self.assertEqual(1, payload["id"])

    # --- 공통 계약 --------------------------------------------------------

    def test_responses_are_json_utf8(self) -> None:
        _, _, headers = self._request("GET", "/api/todos")
        self.assertEqual("application/json; charset=utf-8", headers["Content-Type"])

    def test_cors_is_open_for_development(self) -> None:
        _, _, get_headers = self._request("GET", "/api/todos")
        self.assertEqual("*", get_headers["Access-Control-Allow-Origin"])

        status, _, options_headers = self._request("OPTIONS", "/api/todos")
        self.assertEqual(204, status)
        self.assertEqual("*", options_headers["Access-Control-Allow-Origin"])
        self.assertIn("POST", options_headers["Access-Control-Allow-Methods"])

    def test_unknown_path_returns_error_shape(self) -> None:
        status, payload, _ = self._request("GET", "/api/unknown")
        self.assertEqual(404, status)
        self.assertEqual({"code", "message"}, set(payload))

    def test_trailing_slash_and_query_are_accepted(self) -> None:
        self.assertEqual(200, self._request("GET", "/api/todos/")[0])
        self.assertEqual(200, self._request("GET", "/api/todos?foo=bar")[0])


if __name__ == "__main__":
    unittest.main()
