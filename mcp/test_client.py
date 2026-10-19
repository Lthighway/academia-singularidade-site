"""Integration test: MCP client handshake, discovery and calls over stdio."""
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]

def tool_payload(result):
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        if "valid" in structured or "digest" in structured:
            return structured
        if isinstance(structured.get("result"), dict):
            return structured["result"]
    for block in getattr(result, "content", []):
        value = getattr(block, "text", None)
        if value:
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except (ValueError, TypeError):
                pass
    raise AssertionError(f"No parseable MCP tool result: {result!r}")


async def main():
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp" / "server.py")], cwd=str(ROOT))
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await asyncio.wait_for(session.initialize(), timeout=20)
            catalog = await asyncio.wait_for(session.list_tools(), timeout=20)
            names = {tool.name for tool in catalog.tools}
            assert {"hash_text", "validate_json"} <= names, names
            digest = await asyncio.wait_for(session.call_tool("hash_text", {"document":"abc"}), timeout=20)
            assert not digest.isError, digest
            assert tool_payload(digest)["digest"] == hashlib.sha256(b"abc").hexdigest(), digest
            valid = await asyncio.wait_for(session.call_tool("validate_json", {"document":'{"a":1}'}), timeout=20)
            assert not valid.isError and tool_payload(valid).get("valid") is True, valid
            invalid = await asyncio.wait_for(session.call_tool("validate_json", {"document":'{"a":1,"a":2}'}), timeout=20)
            assert not invalid.isError and tool_payload(invalid).get("valid") is False, invalid
            overflow = await asyncio.wait_for(session.call_tool("validate_json", {"document":"1e9999"}), timeout=20)
            assert not overflow.isError and tool_payload(overflow).get("valid") is False, overflow
            sha512 = await asyncio.wait_for(session.call_tool("hash_text", {"document": "abc", "algorithm": "sha512", "expected": hashlib.sha512(b"abc").hexdigest()}), timeout=20)
            assert not sha512.isError and tool_payload(sha512).get("matches") is True, sha512
            mismatch = await asyncio.wait_for(session.call_tool("hash_text", {"document": "abc", "expected": "0" * 64}), timeout=20)
            assert not mismatch.isError and tool_payload(mismatch).get("matches") is False, mismatch
            bad_algorithm = await asyncio.wait_for(session.call_tool("hash_text", {"document": "abc", "algorithm": "md5"}), timeout=20)
            assert bad_algorithm.isError, bad_algorithm
            too_large = await asyncio.wait_for(session.call_tool("validate_json", {"document": "x" * 4097}), timeout=20)
            assert too_large.isError, too_large
            print("MCP stdio handshake, discovery, positive and negative calls passed.")

if __name__ == "__main__":
    asyncio.run(main())
