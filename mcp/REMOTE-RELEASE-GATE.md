# Remote MCP release gate — AUN

**Current state: authenticated restricted preview deployed; not publicly onboardable.**
Endpoint: `https://academia-singularidade-aun.onrender.com/mcp`

The MCP route is disabled by default in source and enabled on Render only via
`AUN_ENABLE_MCP=1`. It uses a server-side bearer credential and explicit Host
allowlist. This is an operator-controlled staging credential, not an OAuth
server, public registration or a multi-tenant authorization service.

## Verified in GitHub Actions
- Independent MCP SDK stdio client handshake, tools/list, tools/call.
- Real loopback Streamable HTTP client with bearer auth, tools/list, tool calls.
- REST and MCP coexisting in one ASGI process (same route as Render).
- Missing/invalid or disabled token, insufficient scope, disallowed host/origin,
  streamed oversized body, document limits, per-agent throttling and
  concurrency-cap rejection.
- Public HTTPS REST smoke checks and the machine-readable manifest.
- Live `POST /mcp` without token gives `401 Unauthorized`.
- Render shows successful MCP session-manager startup with the REST API online.

The live private bearer handshake has **not** been independently tested by
an external third-party client. The source is not independently security
audited, and no external agent adoption is claimed.

## Controls and limitations
- Only bounded `hash_text` and `validate_json` are available through MCP.
  The Academy Core, signed needs exchange, databases and shell execution
  are not imported.
- Token is in Render environment variables, never Git.
- Origin/Host checks and body limits are enforced both at ASGI ingress and
  SDK transport levels; browser CORS is intentionally disabled.
- The rate circuit breaker, per-agent limit and concurrency semaphore are
  **per Python process**, not distributed or provider-level ingress limits.
  Current setup uses one worker.
- Optional SHA-256-configured agent keys now support distinct identities,
  a single invocation scope, operator-controlled revocation, and per-process
  per-agent throttling. They do **not** provide globally synchronized quotas,
  token self-service, consent, OAuth, audit-grade identities or billing.
- A published bearer URL is not a general invitation to connect; credentials
  are issued only by the operator.

## Conditions for public third-party onboarding
1. Standardized agent onboarding with auditable consent (prefer OAuth for
   arbitrary third-party clients), managed rotation and revocation, rather
   than only operator-edited environment JSON.
2. Infrastructure-level global rate limits, IP/tenant abuse protection and
   request concurrency limits.
3. External **live HTTPS** MCP client initialization and tool invocation,
   including invalid/missing credential and protocol downgrade cases.
4. Malformed JSON-RPC, timeout, cancellation and load tests.
5. Independent security review, incident response and retention policies.
6. Render quota/usage checks; free services share 750 monthly instance-hours
   across the workspace, and should not be treated as production infrastructure.
7. Truthful documentation and public MCP listing only after those checks.

## Rollback
Set `AUN_ENABLE_MCP=0` in the Render service environment (preserve other
variables). The API continues running REST; redeploy and verify
`/healthz`, `/v1/tools` and the discovery manifest. Never publish or echo
`AUN_MCP_TOKEN` in issue comments, workflow logs or documentation.
