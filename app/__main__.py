"""`python -m app`으로 서버를 띄운다."""

from __future__ import annotations

import os
import sys

from .server import DEFAULT_PORT, create_server


def main() -> int:
    port = int(os.environ.get("PORT", DEFAULT_PORT))
    host = os.environ.get("HOST", "0.0.0.0")
    server = create_server(port=port, host=host)
    print(f"Todo API listening on http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("shutting down", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
