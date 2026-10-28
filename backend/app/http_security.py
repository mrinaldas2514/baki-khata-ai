"""HTTP hardening: security headers on every response, and a cap on request body size.

Both are plain ASGI middleware, added inside CORS (see app.main), so even a 413 carries the
CORS headers and the app can read it.
"""

import json
from collections.abc import Callable

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Pages that load scripts and styles (FastAPI's interactive docs, outside production only).
_DOCS_PATHS = ("/docs", "/redoc")

_BASE_HEADERS = [
    # Don't guess content types; don't let any site frame the API; send no referrer.
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), geolocation=(), microphone=()"),
]
# The API only serves JSON (and a CSV download): nothing may run or load from its responses.
_CSP = (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'")
_HSTS = (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
# Answers hold customers' names and money: no browser, proxy or service worker keeps them.
_NO_STORE = (b"cache-control", b"no-store")


class SecurityHeaders:
    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        docs = scope["path"].startswith(_DOCS_PATHS)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                extra = list(_BASE_HEADERS)
                if not docs:
                    extra.append(_CSP)
                if self.hsts:
                    extra.append(_HSTS)
                extra.append(_NO_STORE)
                headers += [(name, value) for name, value in extra if name not in present]
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _too_large_message(limit: int) -> str:
    return f"The request is too large (at most {limit // 1024} KB)."


class _TooLarge(HTTPException):
    """An HTTPException, so FastAPI passes it on as a 413 instead of "error parsing the body"."""

    def __init__(self, limit: int) -> None:
        super().__init__(status_code=413, detail=_too_large_message(limit))


class BodySizeLimit:
    """Answer 413 instead of reading a body bigger than `limit_for(path)` bytes.

    Checks Content-Length up front, and counts the bytes of bodies sent without it (chunked).
    In production put a limit in the proxy too (nginx `client_max_body_size`); this one is
    the last line.
    """

    def __init__(self, app: ASGIApp, *, limit_for: Callable[[str], int]) -> None:
        self.app = app
        self.limit_for = limit_for

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.limit_for(scope["path"])
        length = dict(scope["headers"]).get(b"content-length")
        if length is not None and (not length.isdigit() or int(length) > limit):
            await _send_413(send, limit)
            return

        received = 0
        started = False

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _TooLarge(limit)
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _TooLarge:
            if not started:
                await _send_413(send, limit)


async def _send_413(send: Send, limit: int) -> None:
    body = json.dumps({"detail": _too_large_message(limit)}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
