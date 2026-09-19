"""
Shared-password gate for the public deployment: when DEMO_PASSWORD is set, every HTTP
request and WebSocket handshake must carry it as the HTTP Basic auth password (any
username). When it isn't set (local dev), everything is open.
"""

import base64
import hmac
import os


def _password_matches(authorization: str | None, password: str) -> bool:
    if not authorization or not authorization.lower().startswith("basic "):
        return False
    try:
        decoded = base64.b64decode(authorization[6:]).decode()
    except ValueError:
        return False
    supplied = decoded.partition(":")[2]
    return hmac.compare_digest(supplied.encode(), password.encode())


class BasicAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        password = os.getenv("DEMO_PASSWORD")
        if not password or scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        authorization = headers.get(b"authorization", b"").decode() or None
        if _password_matches(authorization, password):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [(b"www-authenticate", b'Basic realm="Dispatch Copilot"'), (b"content-length", b"0")],
            }
        )
        await send({"type": "http.response.body", "body": b""})
