"""Integration test: MCP client handshake, discovery and calls over stdio."""
import asyncio
import hashlib
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]

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
            assert hashlib.sha256(b"abc").hexdigest() in str(digest), digest
            valid = await asyncio.wait_for(session.call_tool("validate_json", {"document":'{"a":1}'}), timeout=20)
            assert not valid.isError and '"valid": true' in str(valid).lower().replace("'", '"'), valid
            invalid = await asyncio.wait_for(session.call_tool("validate_json", {"document":'{"a":1,"a":2}'}), timeout=20)
            assert not invalid.isError and '"valid": false' in str(invalid).lower().replace("'", '"'), invalid
            overflow = await asyncio.wait_for(session.call_tool("validate_json", {"document":"1e9999"}), timeout=20)
            assert not overflow.isError and '"valid": false' in str(overflow).lower().replace("'", '"'), overflow
            print("MCP stdio handshake, discovery, calls and validation passed.")

if __name__ == "__main__":
    asyncio.run(main())
