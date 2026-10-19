"""Explicit opt-in ASGI routing for the existing AUN REST service and MCP.

AUN_ENABLE_MCP=1 is required. The default public REST deployment is unchanged.
A separate MCP session-manager lifespan is correctly started for mounted use.
"""
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette


def wrap_api_with_mcp(rest_api):
    mcp_dir = str(Path(__file__).resolve().parents[1] / "mcp")
    if mcp_dir not in sys.path:
        sys.path.insert(0, mcp_dir)

    # mcp/remote.py loads ONLY the two safe, standalone public MCP tools.
    from remote import app as mcp_http_app
    from server import mcp

    @asynccontextmanager
    async def lifespan(_app):
        async with mcp.session_manager.run():
            yield

    lifespan_app = Starlette(lifespan=lifespan)

    class CombinedASGI:
        async def __call__(self, scope, receive, send):
            if scope["type"] == "lifespan":
                await lifespan_app(scope, receive, send)
            elif scope["type"] == "http" and scope.get("path") == "/mcp":
                # Pass scope unchanged: the MCP SDK owns the exact /mcp route.
                await mcp_http_app(scope, receive, send)
            else:
                await rest_api(scope, receive, send)

    return CombinedASGI()
