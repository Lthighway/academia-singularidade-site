"""Isolated experimental MCP Streamable HTTP ASGI application.

NOT deployed. Requires AUN_MCP_TOKEN and explicit allowed Origin/Host settings.
Launch only in a controlled staging environment after CI passes.
"""
import hmac
import os
from server import mcp

MAX_BODY = 8192
inner_app = mcp.streamable_http_app()


class SecureMCP:
    def __init__(self, wrapped):
        self.wrapped = wrapped

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.wrapped(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        token = os.environ.get("AUN_MCP_TOKEN", "")
        hosts = {h.strip().lower() for h in os.environ.get("AUN_MCP_HOSTS", "").split(",") if h.strip()}
        origins = {o.strip() for o in os.environ.get("AUN_MCP_ORIGINS", "").split(",") if o.strip()}
        host = headers.get(b"host", b"").decode("latin-1").lower()
        origin = headers.get(b"origin", b"").decode("latin-1")
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        try:
            declared_length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared_length = -1

        status = None
        if not token or not hosts:
            status = 503
        elif host not in hosts or (origin and origin not in origins):
            status = 403
        elif not hmac.compare_digest(authorization, "Bearer " + token):
            status = 401
        elif declared_length < 0 or declared_length > MAX_BODY:
            status = 413

        if status is not None:
            await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"application/json"), (b"cache-control", b"no-store")]})
            await send({"type": "http.response.body", "body": b'{"detail":"Request rejected"}'})
            return

        received = 0
        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_BODY:
                    raise ValueError("MCP request body limit exceeded")
            return message

        await self.wrapped(scope, limited_receive, send)


app = SecureMCP(inner_app)
