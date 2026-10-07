"""표준 라이브러리만 사용하는 Todo HTTP 서버.

계약: 인증 없음, JSON(UTF-8), 모든 출처에 CORS 허용(개발용), 기본 포트 8080.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .store import InvalidTitleError, TodoStore

DEFAULT_PORT = 8080
TODOS_PATH = "/api/todos"

# 유효한 title은 100자 이하이므로, 이보다 큰 본문은 읽지 않고 INVALID_TITLE로 거절한다.
MAX_BODY_BYTES = 1 * 1024 * 1024

INVALID_TITLE_MESSAGE = "제목은 1~100자로 입력해 주세요."


def _normalize_path(raw_path: str) -> str:
    """쿼리 문자열과 끝 슬래시를 제거한 경로."""
    path = urlsplit(raw_path).path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return path


def make_handler(store: TodoStore, *, quiet: bool = False) -> type[BaseHTTPRequestHandler]:
    """주어진 저장소를 사용하는 요청 핸들러 클래스를 만든다."""

    class TodoRequestHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "TodoAPI/1.0"

        # --- 응답 헬퍼 ---------------------------------------------------

        def _send_json(self, status: int, payload: object) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(body)

        def _send_error_json(self, status: int, code: str, message: str) -> None:
            self._send_json(status, {"code": code, "message": message})

        def _send_cors_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Max-Age", "86400")

        # --- 요청 본문 --------------------------------------------------

        def _body_length(self) -> int | None:
            """Content-Length. 읽을 수 없거나 너무 크면 None."""
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return None
            if length < 0 or length > MAX_BODY_BYTES:
                return None
            return length

        def _read_json_body(self) -> object:
            """본문을 JSON으로 파싱한다. 실패하면 InvalidTitleError."""
            length = self._body_length()
            if length is None:
                # 본문을 끝까지 읽지 않으므로 keep-alive를 유지할 수 없다.
                self.close_connection = True
                raise InvalidTitleError("unreadable request body")
            raw = self.rfile.read(length) if length else b""
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise InvalidTitleError("body is not valid JSON") from None

        def _drain_body(self) -> None:
            """응답 전에 남은 본문을 흘려보내 keep-alive 연결을 깨지 않게 한다."""
            length = self._body_length()
            if length is None:
                self.close_connection = True
                return
            if length:
                self.rfile.read(length)

        # --- 라우팅 -----------------------------------------------------

        def do_OPTIONS(self) -> None:  # noqa: N802 - http.server 규약
            # 204에는 본문이 없으므로 Content-Length를 보내지 않는다(RFC 7230).
            self.send_response(HTTPStatus.NO_CONTENT)
            self._send_cors_headers()
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802 - http.server 규약
            if _normalize_path(self.path) != TODOS_PATH:
                self._not_found()
                return
            self._send_json(HTTPStatus.OK, {"items": store.list()})

        def do_POST(self) -> None:  # noqa: N802 - http.server 규약
            if _normalize_path(self.path) != TODOS_PATH:
                self._not_found()
                return
            try:
                body = self._read_json_body()
                title = body.get("title") if isinstance(body, dict) else None
                todo = store.add(title)
            except InvalidTitleError:
                self._send_error_json(
                    HTTPStatus.BAD_REQUEST, "INVALID_TITLE", INVALID_TITLE_MESSAGE
                )
                return
            self._send_json(HTTPStatus.CREATED, todo)

        def do_PUT(self) -> None:  # noqa: N802 - http.server 규약
            self._method_not_allowed()

        def do_PATCH(self) -> None:  # noqa: N802 - http.server 규약
            self._method_not_allowed()

        def do_DELETE(self) -> None:  # noqa: N802 - http.server 규약
            self._method_not_allowed()

        # --- 그 외 -----------------------------------------------------

        def _not_found(self) -> None:
            self._drain_body()
            self._send_error_json(
                HTTPStatus.NOT_FOUND, "NOT_FOUND", "요청한 경로를 찾을 수 없습니다."
            )

        def _method_not_allowed(self) -> None:
            if _normalize_path(self.path) != TODOS_PATH:
                self._not_found()
                return
            self._drain_body()
            self._send_error_json(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "METHOD_NOT_ALLOWED",
                "허용되지 않은 메서드입니다.",
            )

        def log_message(self, fmt: str, *args: object) -> None:
            if not quiet:
                super().log_message(fmt, *args)

    return TodoRequestHandler


def create_server(
    port: int = DEFAULT_PORT,
    host: str = "0.0.0.0",
    store: TodoStore | None = None,
    *,
    quiet: bool = False,
) -> ThreadingHTTPServer:
    """요청을 처리할 준비가 된 서버를 만든다(아직 serve_forever는 호출하지 않는다)."""
    handler = make_handler(store if store is not None else TodoStore(), quiet=quiet)
    return ThreadingHTTPServer((host, port), handler)
