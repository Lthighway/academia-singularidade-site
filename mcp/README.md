# Experimental MCP stdio adapter

**Not a public MCP endpoint.** This adapter is a separate local process exposing only two deterministic tools. No Academy Core, exchange, database, credentials or network listener is imported.

## Run (Python 3.12)
```sh
python -m pip install -r mcp/requirements.txt
python -m mcp.server
```
The package name `mcp` conflicts with the third-party SDK namespace, so **do not use** the command above. Instead run:
```sh
python mcp/server.py
```
The stdio transport is intended for a local MCP client. Do not use the public HTTPS URL as an MCP endpoint; it currently serves HTTP/OpenAPI only.

## Release gates
- Run independent MCP client initialization, tools/list and tools/call tests.
- Verify malformed input, limits, concurrency, timeouts and cancellation.
- Review SDK versions and protocol negotiation.
- For remote MCP, design authenticated, globally rate-limited HTTPS ingress before deployment.
- Do not advertise MCP support until tested and deployed.
