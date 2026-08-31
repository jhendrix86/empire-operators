"""ASGI middleware that rejects request bodies matching known-unsafe
patterns, using SafetyBoundaryOperator.

Pure ASGI (no Starlette version coupling). Buffers the body once, scans
it, and either 400s or replays the buffered body downstream unchanged.

Usage in a FastAPI app:

    from empire_operators.middleware import SafetyBoundaryMiddleware
    app.add_middleware(SafetyBoundaryMiddleware)

Scoping:
- Only POST / PUT / PATCH with a body are scanned.
- multipart/form-data (file uploads) is skipped.
- Bodies larger than `max_scan_bytes` (default 256 KiB) are passed through
  unscanned rather than buffered.
- `exempt_paths` (exact-match) are never scanned (default: none).
"""
import json
from typing import Iterable, Optional

from .operators import SafetyBoundaryOperator

_SCANNED_METHODS = {"POST", "PUT", "PATCH"}


class SafetyBoundaryMiddleware:
    def __init__(
        self,
        app,
        *,
        max_scan_bytes: int = 256 * 1024,
        exempt_paths: Optional[Iterable[str]] = None,
    ):
        self.app = app
        self.max_scan_bytes = max_scan_bytes
        self.exempt_paths = set(exempt_paths or ())
        self._operator = SafetyBoundaryOperator()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        ctype = headers.get("content-type", "")

        if (
            method not in _SCANNED_METHODS
            or path in self.exempt_paths
            or ctype.startswith("multipart/form-data")
        ):
            await self.app(scope, receive, send)
            return

        # Buffer the body.
        chunks = []
        total = 0
        too_big = False
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] != "http.request":
                # Unexpected (e.g. disconnect) - hand control back untouched.
                await self.app(scope, _single_message_receive(message, chunks), send)
                return
            body = message.get("body", b"")
            total += len(body)
            if total > self.max_scan_bytes:
                too_big = True
            chunks.append(body)
            more_body = message.get("more_body", False)

        raw = b"".join(chunks)

        if not too_big and raw:
            text = raw.decode("utf-8", errors="replace")
            state = self._operator.execute({"raw_input": text})
            if not state["flags"]["safety_ok"]:
                await _send_json(
                    send,
                    400,
                    {
                        "detail": "request body rejected by SafetyBoundaryOperator",
                        "patterns": state["unsafe_patterns_detected"],
                    },
                )
                return

        await self.app(scope, _replay_receive(raw), send)


def _replay_receive(raw: bytes):
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": raw, "more_body": False}
        return {"type": "http.disconnect"}

    return receive


def _single_message_receive(first, buffered_chunks):
    raw = b"".join(buffered_chunks)
    queue = [{"type": "http.request", "body": raw, "more_body": False}, first]
    idx = 0

    async def receive():
        nonlocal idx
        if idx < len(queue):
            msg = queue[idx]
            idx += 1
            return msg
        return {"type": "http.disconnect"}

    return receive


async def _send_json(send, status: int, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("latin-1")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
