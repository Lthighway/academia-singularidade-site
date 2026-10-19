"""Preflight security tests; no remote MCP deployment is performed."""
import asyncio
import os
import httpx
import remote
from remote import app, SecureMCP


async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        os.environ.pop("AUN_MCP_TOKEN", None)
        os.environ["AUN_MCP_HOSTS"] = "testserver"
        r = await client.post("/mcp", content=b"{}")
        assert r.status_code == 503, r.text
        os.environ["AUN_MCP_TOKEN"] = "short-token"
        assert (await client.post("/mcp", content=b"{}")).status_code == 503
        os.environ["AUN_MCP_TOKEN"] = "ci-only-long-example-token-never-deploy-123456"
        os.environ["AUN_MCP_ORIGINS"] = "https://example.org"
        r = await client.post("/mcp", content=b"{}")
        assert r.status_code == 401, r.text
        r = await client.post("/mcp", content=b"{}", headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 401, r.text
        r = await client.post("/mcp", content=b"{}", headers={"Authorization": "Bearer ci-only-long-example-token-never-deploy-123456", "Origin": "https://evil.example"})
        assert r.status_code == 403, r.text
        r = await client.post("/mcp", content=b"{}", headers={"Authorization": "Bearer ci-only-long-example-token-never-deploy-123456", "Host": "wrong.example"})
        assert r.status_code == 403, r.text
        r = await client.post("/mcp", content=b"x" * 9000, headers={"Authorization": "Bearer ci-only-long-example-token-never-deploy-123456"})
        assert r.status_code == 413, r.text
    # Exercise the guard's successful pass-through without MCP SDK sessions.
    async def fake_ok(scope, receive, send):
        message = await receive()
        assert message["type"] == "http.request"
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def streamed_body():
        yield b"x" * 5000
        yield b"y" * 5000

    fake_app = SecureMCP(fake_ok)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=fake_app),
                                 base_url="http://testserver") as client:
        headers = {"Authorization": "Bearer ci-only-long-example-token-never-deploy-123456"}
        r = await client.post("/mcp", content=b"{}", headers=headers)
        assert r.status_code == 200, r.text
        r = await client.post("/mcp", content=streamed_body(), headers=headers)
        assert r.status_code == 413, r.text
        old_limit = remote.PER_MINUTE_LIMIT
        try:
            remote._rate_events.clear()
            remote.PER_MINUTE_LIMIT = 2
            assert (await client.post("/mcp", content=b"{}", headers=headers)).status_code == 200
            assert (await client.post("/mcp", content=b"{}", headers=headers)).status_code == 200
            assert (await client.post("/mcp", content=b"{}", headers=headers)).status_code == 429
        finally:
            remote.PER_MINUTE_LIMIT = old_limit
            remote._rate_events.clear()
    print("MCP remote preflight authentication, limits and streaming tests passed.")


if __name__ == "__main__":
    asyncio.run(check())
