# test-be

NOMOS 운영 테스트용 BE 레포

## 실행

런타임 의존성이 없다. Python 3.11+ 만 있으면 된다.

```bash
python -m app            # http://localhost:8080
PORT=3000 python -m app  # 포트 변경
```

Docker:

```bash
docker build -t test-be . && docker run -p 8080:8080 test-be
```

## 테스트

```bash
python -m unittest discover -s tests
```

## API (F-01)

인증 없음. JSON(UTF-8). 모든 출처에 CORS 허용(개발용). 저장소는 서버 메모리이므로
재시작하면 초기화된다.

Todo 객체: `{ id: number, title: string, done: boolean, createdAt: string }`
— `id`는 1부터 1씩 증가, `createdAt`은 ISO 8601 UTC(`2026-10-08T01:23:45Z`),
`done`은 항상 `false`로 생성된다.

### `GET /api/todos`

`200` · `{ "items": Todo[] }` — 등록순(id 오름차순), 페이지네이션 없음.
저장된 할 일이 없으면 `{ "items": [] }`.

### `POST /api/todos`

요청 `{ "title": string }`. 서버가 `title` 앞뒤 공백을 제거하고, 제거 후 1~100자인지 검증한다.

- `201` · 생성된 Todo
- `400` · `{ "code": "INVALID_TITLE", "message": "제목은 1~100자로 입력해 주세요." }`
  — title이 없음/문자열 아님/공백뿐/100자 초과, 또는 본문이 올바른 JSON이 아닌 경우.
  검증에 실패하면 목록에 아무것도 추가되지 않는다.

### 오류 응답

모든 오류는 `{ "code": string, "message": string }` 형태다. 명세에 없는 경로는 `404 NOT_FOUND`,
`/api/todos`에 허용되지 않은 메서드는 `405 METHOD_NOT_ALLOWED`를 같은 형태로 반환한다.
