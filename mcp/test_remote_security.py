"""Preflight security tests; no remote MCP deployment is performed."""
import asyncio
import os
import httpx
from remote import app


async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        os.environ.pop("AUN_MCP_TOKEN", None)
        os.environ["AUN_MCP_HOSTS"] = "testserver"
        r = await client.post("/mcp", content=b"{}")
        assert r.status_code == 503, r.text
        os.environ["AUN_MCP_TOKEN"] = "test-only-not-a-secret"
        os.environ["AUN_MCP_ORIGINS"] = "https://example.org"
        r = await client.post("/mcp", content=b"{}")
        assert r.status_code == 401, r.text
        r = await client.post("/mcp", content=b"{}", headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 401, r.text
        r = await client.post("/mcp", content=b"{}", headers={"Authorization": "Bearer test-only-not-a-secret", "Origin": "https://evil.example"})
        assert r.status_code == 403, r.text
        r = await client.post("/mcp", content=b"{}", headers={"Authorization": "Bearer test-only-not-a-secret", "Host": "wrong.example"})
        assert r.status_code == 403, r.text
        r = await client.post("/mcp", content=b"x" * 9000, headers={"Authorization": "Bearer test-only-not-a-secret"})
        assert r.status_code == 413, r.text
    print("MCP remote preflight rejection tests passed.")


if __name__ == "__main__":
    asyncio.run(check())
