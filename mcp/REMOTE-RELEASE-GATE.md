# Remote MCP release gate — AUN

Status: **NOT RELEASED**. Passing local stdio MCP tests does not validate remote HTTP transport.

## Architecture
- Keep the existing FastAPI public preview and private Academy Core isolated.
- Expose only `hash_text` and `validate_json` through a separate, explicit MCP HTTP route after testing.
- Prefer the MCP SDK's supported Streamable HTTP transport. Do not invent a JSON-RPC transport implementation.
- Require an explicit opt-in deployment and a dedicated scoped credential for remote access; never store credentials in Git.
- Reject requests with invalid `Origin`; restrict `Host` to expected domains. Enforce TLS.
- Set request-size, execution-time, concurrency and global rate limits; a per-process dictionary is not a global rate limiter.
- Disable server-side arbitrary URLs, file paths, shell execution, subprocesses, agent-initiated writes, and access to private Academy modules.
- Return minimal error details and never log input documents, tokens, or sensitive headers.

## Mandatory validation before advertising remote MCP
1. SDK-version-pinned MCP client initialization, tools/list, tools/call over remote HTTPS.
2. Negative tests: missing/invalid credential, disallowed Origin, oversized body, unsupported protocol version and malformed JSON-RPC.
3. Confirm no filesystem/network side effects and no route to private Academy Core.
4. Observe traffic, errors and limits on Render free plan; check wake-up latency and capacity.
5. Publish accurate integration instructions only after independent remote client success.

**Current public URL is REST/OpenAPI only, not an MCP endpoint.**
