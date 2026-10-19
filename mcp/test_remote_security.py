"""Preflight security tests; no remote MCP deployment is performed."""
import asyncio
import hashlib
import json
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
    # Duplicate security-sensitive headers must be rejected consistently.
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        correct = "Bearer ci-only-long-example-token-never-deploy-123456"
        for repeated in [
            [("Authorization", correct), ("Authorization", "Bearer wrong")],
            [("Host", "testserver"), ("Host", "unexpected.example"), ("Authorization", correct)],
            [("Origin", "https://example.org"), ("Origin", "https://evil.example"), ("Authorization", correct)],
        ]:
            r = await client.post("/mcp", content=b"{}", headers=repeated)
            assert r.status_code == 400, (repeated, r.status_code)
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
            remote._actor_events.clear()
    # Distinct agents can be accepted, denied by scope, or revoked without
    # changing the operator token or exposing raw credentials in configuration.
    agent = "scoped-ci-agent-test-credential-never-deploy"
    policy = {"agent-ci": {
        "sha256": hashlib.sha256(agent.encode()).hexdigest(),
        "scopes": ["mcp:invoke"], "enabled": True,
    }}
    os.environ["AUN_MCP_AGENT_KEYS"] = json.dumps(policy)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=fake_app),
                                 base_url="http://testserver") as client:
        agent_headers = {"Authorization": "Bearer " + agent}
        assert (await client.post("/mcp", content=b"{}", headers=agent_headers)).status_code == 200
        old_actor_limit = remote.PER_AGENT_MINUTE_LIMIT
        try:
            remote._rate_events.clear()
            remote._actor_events.clear()
            remote.PER_AGENT_MINUTE_LIMIT = 2
            assert (await client.post("/mcp", content=b"{}", headers=agent_headers)).status_code == 200
            assert (await client.post("/mcp", content=b"{}", headers=agent_headers)).status_code == 200
            assert (await client.post("/mcp", content=b"{}", headers=agent_headers)).status_code == 429
        finally:
            remote.PER_AGENT_MINUTE_LIMIT = old_actor_limit
            remote._rate_events.clear()
            remote._actor_events.clear()
        policy["agent-ci"]["scopes"] = []
        os.environ["AUN_MCP_AGENT_KEYS"] = json.dumps(policy)
        assert (await client.post("/mcp", content=b"{}", headers=agent_headers)).status_code == 403
        policy["agent-ci"]["scopes"] = ["mcp:invoke"]
        policy["agent-ci"]["enabled"] = False
        os.environ["AUN_MCP_AGENT_KEYS"] = json.dumps(policy)
        assert (await client.post("/mcp", content=b"{}", headers=agent_headers)).status_code == 401
        os.environ["AUN_MCP_AGENT_KEYS"] = "{malformed-json"
        assert (await client.post("/mcp", content=b"{}", headers=agent_headers)).status_code == 503
    os.environ.pop("AUN_MCP_AGENT_KEYS", None)
    # Saturation is rejected before unbounded body processing or tool work.
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_tool(scope, receive, send):
        await receive()
        entered.set()
        await release.wait()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    original_sem = remote._inflight
    try:
        remote._inflight = asyncio.Semaphore(1)
        remote._rate_events.clear()
        remote._actor_events.clear()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=SecureMCP(slow_tool)),
            base_url="http://testserver", timeout=4
        ) as client:
            headers = {"Authorization": "Bearer ci-only-long-example-token-never-deploy-123456"}
            first = asyncio.create_task(client.post("/mcp", content=b"{}", headers=headers))
            await asyncio.wait_for(entered.wait(), timeout=2)
            busy = await client.post("/mcp", content=b"{}", headers=headers)
            assert busy.status_code == 429, busy.text
            release.set()
            assert (await first).status_code == 200
    finally:
        release.set()
        remote._inflight = original_sem
        remote._rate_events.clear()
        remote._actor_events.clear()

    print("MCP remote authentication, per-agent limits, revocation and concurrency tests passed.")


if __name__ == "__main__":
    asyncio.run(check())
