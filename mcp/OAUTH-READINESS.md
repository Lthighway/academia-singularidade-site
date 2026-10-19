# OAuth readiness for public MCP agent access

**Design document only — OAuth is NOT enabled or advertised.** The existing
restricted bearer-key preview remains the only remote MCP authentication mode.

Reference: [MCP authorization specification 2025-11-25](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2025-11-25/basic/authorization.mdx).
The protocol draft may evolve; pin an SDK and revalidate before release.

## System roles

- **MCP resource server:** Academia Singularidade's `/mcp` endpoint.
- **Authorization server:** standards-compliant HTTPS OAuth 2.1 issuer, to be
  selected, configured and security reviewed before any public onboarding.
- **MCP client:** authorized third-party agent, with resource-owner consent
  when applicable. Existing operator and hash-only keys remain restricted
  previews and must not be misrepresented as OAuth access tokens.

## Resource server implementation gates

1. **Discovery:** only after a real issuer exists, expose OAuth Protected
   Resource Metadata (RFC 9728) for the canonical resource
   `https://academia-singularidade-aun.onrender.com/mcp`, with the actual
   `authorization_servers` URL, and return a matching
   `WWW-Authenticate: Bearer resource_metadata="..."` challenge.
   Never advertise a fictitious issuer.
2. **Authorization-server metadata:** verify the issuer discovery document via
   RFC 8414 (or OIDC discovery as specified), HTTPS certificate, stable issuer
   identifier, supported endpoints, and appropriate PKCE S256 support.
3. **Token audience:** validate `aud` (RFC 8707 resource indicator), `iss`,
   expiry/not-before and scopes for **this** MCP resource. Do not accept
   arbitrary provider access tokens or an ID token as an API credential.
4. **Cryptographic verification:** validate approved signing algorithms against
   the issuer's JWKS with bounded, cached key lookup and key rotation handling;
   never trust algorithms or remote key URLs supplied by an untrusted token.
5. **Scope control:** map specifically authorized MCP capabilities to scopes.
   Existing preview scope `mcp:invoke` is not per-tool isolation.
6. **Client identity and consent:** use standards-based client metadata or
   registration, with server-side policy, PKCE S256, redirect URI restrictions,
   resource-owner consent and revocation controls. Avoid implicit anonymous
   registration or storing third-party access tokens in source control.
7. **Responses:** use standard 401/403 bearer challenges, fail closed on
   malformed, expired or wrongly issued tokens; never echo credentials in logs
   or error messages.
8. **Abuse and operations:** global ingress rate limits, per-client quotas,
   capped request body/concurrency, TLS, monitoring, incident response,
   privacy and retention policies. Process-local limits alone are insufficient.

## Verification

Use a disposable authorization-server test issuer first, **not** the real
operator credential. CI must cover:

- PKCE / resource-indicator / discovery flow and authenticated MCP initialize,
  tools/list and tools/call over real HTTPS.
- Missing/wrong issuer, audience, signature, algorithm, scope, expiration,
  revocation, unauthorized Origin and malformed protocol version.
- Fail-closed behavior when JWKS discovery is unavailable, with bounded cache
  behavior and key-rotation tests.
- Compatibility with the specific SDK/protocol version deployed on Render.
- No private Academy Core imports, shell access or unrestricted network tools.

## Release decision

Do not create `/.well-known/oauth-protected-resource` or claim OAuth readiness
until the actual authorization server, cryptographic verification, discovery
and integration tests exist. No public client registration or external agent
claims until verified. Do not provision a paid authorization provider without
explicit operator approval.

The currently deployed /mcp uses an operator-controlled bearer credential and
an optional small hash-only agent registry, not standards-compliant OAuth.
