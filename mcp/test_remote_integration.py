"""Real loopback MCP Streamable HTTP integration, no cloud deployment.

Starts the isolated ASGI app with a disposable test token, then exercises a
real SDK client handshake, tools/list and tools/call over an HTTP socket.
"""
import asyncio
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from test_client import tool_payload

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "ci-only-example-token-not-a-production-secret"
AGENT = "ci-agent-secret-only-for-loopback-tests-not-a-real-key"


def test_registry():
    return json.dumps({"agent-ci": {
        "sha256": hashlib.sha256(AGENT.encode()).hexdigest(),
        "scopes": ["mcp:invoke"], "enabled": True,
    }})


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def exercise(base, credential=TOKEN):
    async with httpx.AsyncClient(timeout=4, trust_env=False) as http:
        denied = await http.post(base + "/mcp", content=b"{}")
        assert denied.status_code == 401, denied.text
        forbidden = await http.post(
            base + "/mcp", content=b"{}", headers={
                "Authorization": "Bearer " + TOKEN,
                "Origin": "https://not-allowed.example",
            }
        )
        assert forbidden.status_code == 403, forbidden.text

    # The SDK client supplies MCP protocol headers and initializes the session.
    async with streamablehttp_client(
        base + "/mcp", headers={"Authorization": "Bearer " + credential}
    ) as (reader, writer, _):
        async with ClientSession(reader, writer) as session:
            await asyncio.wait_for(session.initialize(), timeout=15)
            catalog = await asyncio.wait_for(session.list_tools(), timeout=15)
            names = {tool.name for tool in catalog.tools}
            assert names == {"hash_text", "validate_json"}, names
            hashed = await asyncio.wait_for(
                session.call_tool("hash_text", {"document": "abc"}), timeout=15
            )
            assert not hashed.isError, hashed
            assert tool_payload(hashed)["digest"] == hashlib.sha256(b"abc").hexdigest()
            invalid = await asyncio.wait_for(
                session.call_tool("validate_json", {"document": "1e9999"}), timeout=15
            )
            assert not invalid.isError and tool_payload(invalid)["valid"] is False

    print("MCP authenticated Streamable HTTP handshake, discovery and calls passed.")


async def main():
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    environment = os.environ.copy()
    environment.update({
        "AUN_MCP_TOKEN": TOKEN,
        "AUN_MCP_AGENT_KEYS": test_registry(),
        "AUN_MCP_HOSTS": f"127.0.0.1:{port}",
        "AUN_MCP_ORIGINS": "https://allowed.example",
    })
    with tempfile.TemporaryFile(mode="w+t") as log:
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "remote:app",
                "--app-dir", str(ROOT / "mcp"), "--host", "127.0.0.1",
                "--port", str(port), "--workers", "1",
            ],
            cwd=str(ROOT),
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(80):
                if proc.poll() is not None:
                    raise RuntimeError("MCP server exited during startup")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        break
                except OSError:
                    await asyncio.sleep(0.15)
            else:
                raise TimeoutError("MCP server did not start")
            await exercise(base)
            await exercise(base, AGENT)
        except BaseException:
            log.flush()
            log.seek(0)
            print("MCP server log (failure only):", log.read()[-8000:], file=sys.stderr)
            raise
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


if __name__ == "__main__":
    asyncio.run(main())
