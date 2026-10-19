"""Generate one random MCP preview agent credential in a private local terminal.

NEVER invoke this script in CI, issue comments, logs, public shells, or a
shared terminal. The raw key is displayed once; the Render config gets only
its SHA-256 digest. It does not create users in the public service.
"""
import hashlib
import json
import secrets
import sys

from auth import _AGENT_ID


def make_policy(agent_id, token):
    if not isinstance(agent_id, str) or not _AGENT_ID.fullmatch(agent_id):
        raise ValueError("Use a 2–64-character lowercase agent ID: a-z, 0-9, dot, underscore, hyphen")
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError("Use a cryptographically random credential of at least 32 characters")
    return {agent_id: {
        "sha256": hashlib.sha256(token.encode("ascii")).hexdigest(),
        "scopes": ["mcp:invoke"],
        "enabled": True,
    }}


def main():
    if len(sys.argv) != 2:
        print("Usage: python mcp/agent_keys.py lower-case-agent-id", file=sys.stderr)
        return 2
    if not sys.stdout.isatty():
        print("Refusing to print a credential into noninteractive logs or pipes.", file=sys.stderr)
        return 2
    agent_id = sys.argv[1]
    try:
        token = secrets.token_urlsafe(48)
        policy = make_policy(agent_id, token)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print("PRIVATE KEY (copy directly to authorized MCP client; shown only now):")
    print(token)
    print()
    print("RENDER HASH CONFIG ENTRY (add to AUN_MCP_AGENT_KEYS JSON):")
    print(json.dumps(policy, separators=(",", ":")))
    print()
    print("Revoke: set this agent's enabled field to false and redeploy.")
    print("Do not publish the token or a screenshot of this terminal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
