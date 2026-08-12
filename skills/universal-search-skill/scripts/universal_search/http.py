from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class HTTPError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


def post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise HTTPError(
            f"HTTP {exc.code} from {url}",
            status=exc.code,
            body=raw,
        ) from exc
    except urllib.error.URLError as exc:
        raise HTTPError(f"Network error calling {url}: {exc.reason}") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPError(f"Invalid JSON response from {url}", body=raw[:2000]) from exc

    if not isinstance(parsed, dict):
        raise HTTPError(f"Unexpected JSON type from {url}: {type(parsed).__name__}")

    return parsed
