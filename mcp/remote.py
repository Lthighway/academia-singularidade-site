"""Isolated MCP Streamable HTTP staging service.

Never imports the private Academy Core. Not deployed by the REST preview service.
All allowed hosts, optional browser origins and bearer token must be configured.
"""
import asyncio
import time
from collections import deque
from threading import Lock
import hmac
import os

from mcp.server.transport_security import TransportSecuritySettings
from server import mcp

MAX_BODY = 8192
BODY_TIMEOUT_SECONDS = 8
# Process-local circuit breaker for a single-instance staging service.
# This is not a substitute for provider-level global rate limiting.
PER_MINUTE_LIMIT = 90
_rate_events = deque()
_rate_lock = Lock()


def configured_set(name):
    return {v.strip() for v in os.environ.get(name, "").split(",") if v.strip()}


# MCP SDK v1 performs DNS-rebinding and Origin checks independently.
# Reconfigure before the HTTP app/session manager is created.
_allowed_hosts = configured_set("AUN_MCP_HOSTS")
_allowed_origins = configured_set("AUN_MCP_ORIGINS")
mcp.settings.stateless_http = True
mcp.settings.json_response = True
mcp.settings.transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=sorted(_allowed_hosts),
    allowed_origins=sorted(_allowed_origins),
)
inner_app = mcp.streamable_http_app()


class SecureMCP:
    """Fail-closed ASGI guard, with an independent SDK transport-security layer."""

    def __init__(self, wrapped):
        self.wrapped = wrapped

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            # Preserve the inner app's lifespan for MCP's session manager.
            await self.wrapped(scope, receive, send)
            return

        async def reject(status):
            await send({"type": "http.response.start", "status": status,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"cache-control", b"no-store"),
                                    (b"x-content-type-options", b"nosniff")]})
            await send({"type": "http.response.body", "body": b'{"detail":"Request rejected"}'})

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        token = os.environ.get("AUN_MCP_TOKEN", "")
        hosts = {v.lower() for v in configured_set("AUN_MCP_HOSTS")}
        origins = configured_set("AUN_MCP_ORIGINS")
        host = headers.get(b"host", b"").decode("latin-1").lower()
        origin = headers.get(b"origin", b"").decode("latin-1")
        authorization = headers.get(b"authorization", b"").decode("latin-1")

        if len(token) < 32 or not hosts:
            await reject(503)
            return
        if host not in hosts or (origin and origin not in origins):
            await reject(403)
            return
        if not hmac.compare_digest(authorization, "Bearer " + token):
            await reject(401)
            return
        try:
            length_header = headers.get(b"content-length")
            length = int(length_header) if length_header is not None else 0
        except ValueError:
            await reject(400)
            return
        if length < 0 or length > MAX_BODY:
            await reject(413)
            return

        now = time.monotonic()
        with _rate_lock:
            while _rate_events and _rate_events[0] <= now - 60:
                _rate_events.popleft()
            throttled = len(_rate_events) >= PER_MINUTE_LIMIT
            if not throttled:
                _rate_events.append(now)
        if throttled:
            await reject(429)
            return

        chunks = []
        received = 0
        try:
            async with asyncio.timeout(BODY_TIMEOUT_SECONDS):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    if message["type"] != "http.request":
                        continue
                    chunk = message.get("body", b"")
                    received += len(chunk)
                    if received > MAX_BODY:
                        await reject(413)
                        return
                    chunks.append(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await reject(408)
            return

        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks),
                        "more_body": False}
            return await receive()

        await self.wrapped(scope, bounded_receive, send)


app = SecureMCP(inner_app)
