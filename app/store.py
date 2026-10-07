"""서버 메모리에 Todo를 보관하는 저장소. 프로세스를 재시작하면 초기화된다."""

from __future__ import annotations

import threading
from datetime import datetime, timezone

TITLE_MIN_LENGTH = 1
TITLE_MAX_LENGTH = 100


def _now_iso_utc() -> str:
    """ISO 8601 UTC 문자열(초 단위, 예: 2026-10-08T01:23:45Z)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class InvalidTitleError(ValueError):
    """title이 계약을 만족하지 않을 때 발생한다."""


def normalize_title(raw: object) -> str:
    """title 앞뒤 공백을 제거하고 길이를 검증한 값을 돌려준다."""
    if not isinstance(raw, str):
        raise InvalidTitleError("title must be a string")
    title = raw.strip()
    if not TITLE_MIN_LENGTH <= len(title) <= TITLE_MAX_LENGTH:
        raise InvalidTitleError("title length must be 1~100 after trimming")
    return title


class TodoStore:
    """id 오름차순(= 등록순)으로 Todo를 보관한다."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._todos: list[dict] = []
        self._next_id = 1

    def list(self) -> list[dict]:
        """등록순 Todo 목록의 복사본."""
        with self._lock:
            return [dict(todo) for todo in self._todos]

    def add(self, raw_title: object) -> dict:
        """검증을 통과하면 Todo를 추가하고 반환한다. 실패하면 아무것도 추가하지 않는다."""
        title = normalize_title(raw_title)
        with self._lock:
            todo = {
                "id": self._next_id,
                "title": title,
                "done": False,
                "createdAt": _now_iso_utc(),
            }
            self._next_id += 1
            self._todos.append(todo)
            return dict(todo)

    def clear(self) -> None:
        """테스트에서 상태를 비울 때 사용한다."""
        with self._lock:
            self._todos.clear()
            self._next_id = 1
