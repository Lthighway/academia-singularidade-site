# AUN MCP verification tools (experimental)

The MCP adapter exposes **only** `hash_text` and `validate_json`. It contains no
Academia Core modules, shared secrets, payment functions or persistent storage.

## Local stdio transport (tested by GitHub Actions)

From the repository root, using Python 3.12:

```sh
python -m pip install -r mcp/requirements.txt
python mcp/server.py
```

Client/stdio protocol regression: `python mcp/test_client.py`.

## Isolated Streamable HTTP staging (not publicly deployed)

`mcp/remote.py` wraps the official Python MCP SDK HTTP app with fail-closed
host, browser-Origin and constant-time bearer checks. The SDK independently
checks allowed hosts/origins. The service runs in stateless, JSON-response mode
for low-cost experiments, not public multi-tenant production.

Test on loopback only. Set environment variables in your shell **without
committing token values or posting them in logs**:

```sh
export AUN_MCP_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export AUN_MCP_HOSTS="127.0.0.1:8765"
export AUN_MCP_ORIGINS=""
python -m uvicorn remote:app --app-dir mcp --host 127.0.0.1 --port 8765 --workers 1
```

The MCP endpoint is `http://127.0.0.1:8765/mcp`, and requires a
`Bearer` token. This HTTP URL is strictly for loopback testing; production
credentials should only traverse HTTPS.

Automated preflight and actual HTTP client tests:

```sh
python mcp/test_remote_security.py
python mcp/test_remote_integration.py
```

The test harness creates a disposable loopback server and uses a **fixed
test-only credential**. That credential has no role in any deployment.

## Security / release limitations

- Local CI tests do not establish security, reliability or compatibility on a
  public Internet endpoint.
- The request rate circuit breaker is **per Python process**, not distributed.
  It cannot defend a multi-replica deployment by itself.
- The static bearer token is for controlled staging, **not OAuth**, key
  issuance, tenant authorization or broad third-party onboarding.
- Browser CORS is intentionally **not enabled** in staging.
- For a deployed HTTPS MCP route, configure exactly the expected
  `AUN_MCP_HOSTS`, allowed origins and a unique secret via Render environment
  variables, not the codebase.
- A remote rollout requires a verified live MCP client test, ingress-layer
  abuse limits, logs without payloads/credentials, cost limits and rollback.
- The current `https://academia-singularidade-aun.onrender.com` is the
  separate REST/OpenAPI preview. **It is not an MCP endpoint.**

See [REMOTE-RELEASE-GATE.md](REMOTE-RELEASE-GATE.md) for the full checklist.
