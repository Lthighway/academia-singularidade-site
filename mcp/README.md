# Academia Singularidade — MCP integration (restricted preview)

The public AUN preview exposes only two deterministic tools through MCP:
`hash_text` and `validate_json`. **No private Academy Core, persistence,
shell operations, arbitrary URL fetches, or third-party onboarding.**

## Local MCP stdio

Python 3.12, from the repository root:

```sh
python -m pip install -r mcp/requirements.txt
python mcp/server.py
```

## Protected remote Streamable HTTP

Staging endpoint: `https://academia-singularidade-aun.onrender.com/mcp`.

This endpoint is enabled in the existing Render Free service using
`AUN_ENABLE_MCP=1`, `AUN_MCP_HOSTS` and a server-side credential.
Anonymous callers receive 401. The separate REST API remains accessible
without MCP credentials. There is **no public agent enrollment**.

The server supports these operator-configured credential types:

- `AUN_MCP_TOKEN`: existing legacy operator bearer secret, minimum 32
  characters. Preserve it until an intentional rotation.
- `AUN_MCP_AGENT_KEYS`: optional JSON dictionary mapping 2–64-character
  agent IDs to SHA-256 credential digests, an `enabled` boolean, and
  `scopes: ["mcp:invoke"]`. The raw agent secret is never stored in JSON.

Example **shape only**, never a real digest or credential:

```json
{
  "agent-example": {
    "sha256": "replace-with-64-lowercase-hex-characters",
    "scopes": ["mcp:invoke"],
    "enabled": true
  }
}
```

### Local-only key issuance

On a **private interactive terminal** (not CI, not shared shell, not a chat),
run `python mcp/agent_keys.py agent-example`. The command refuses to print
credentials to redirected output. It displays a new random token **once** and
a matching hash-only registry entry. Deliver the raw token directly to the
authorized MCP client by an appropriate private channel. Add the hash-only
entry to `AUN_MCP_AGENT_KEYS` under the existing Render service environment,
preserving other agents and variables.

To revoke one agent, set `enabled` to `false` or remove its entry, deploy,
and confirm denial. Credential configuration is read on each request, but
Render changes take effect only after the service receives the configuration.
Revocation is **not instantaneous across an in-progress deployment**.
No agent credentials are issued automatically through HTTP.

### Local security/integration verification

```sh
python mcp/test_auth.py
python mcp/test_client.py
python mcp/test_remote_security.py
python mcp/test_remote_integration.py
python mcp/test_combined_integration.py
```

These run automatically in the public CI workflow. The HTTP integration uses
**disposable loopback credentials**; they are *never* production secrets.

## Safety and release limits

- The guard enforces allowed hosts, browser Origins, maximum body size,
  an eight-second read timeout, per-process throttling, per-agent throttling
  and up to eight concurrent active calls/reads. The SDK independently
  protects against forbidden hosts/origins.
- These limits are **not distributed** and are not a replacement for
  infrastructure-level IP controls and global quotas.
- `mcp:invoke` grants access to **both** public tools, not individually
  granular tool permissions. There is no OAuth flow, consent UI, key
  self-registration, billing or audited tenant isolation.
- Browser CORS is not enabled. Never send bearer tokens in URL query strings,
  logs, issue comments, screenshots or Git commits.
- The REST preview and MCP route have not passed an independent security audit
  or general public onboarding tests.
- Rollback: set `AUN_ENABLE_MCP=0` (do not unset other variables), deploy and
  verify REST health, catalog and the public discovery manifest.

See [REMOTE-RELEASE-GATE.md](REMOTE-RELEASE-GATE.md) for unresolved tasks.
