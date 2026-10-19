"""Standalone fail-closed credential-policy tests; no real secrets stored."""
import hashlib
import json

from auth import authorize, _load_registry


OWNER = "operator-test-credential-only-keep-out-of-production"
AGENT = "agent-test-credential-only-keep-out-of-production"


def sha(token):
    return hashlib.sha256(token.encode()).hexdigest()


def registry(enabled=True, scopes=None):
    return json.dumps({
        "agent-example": {
            "sha256": sha(AGENT),
            "scopes": ["mcp:invoke"] if scopes is None else scopes,
            "enabled": enabled,
        }
    })


def run():
    assert authorize("", {}) == (503, None)
    owner = {"AUN_MCP_TOKEN": OWNER}
    assert authorize("Bearer " + OWNER, owner) == (200, "operator")
    assert authorize("Bearer invalid", owner) == (401, None)
    assert authorize("Bearer " + AGENT, owner) == (401, None)

    agents = {"AUN_MCP_AGENT_KEYS": registry()}
    assert authorize("Bearer " + AGENT, agents) == (200, "agent-example")
    assert authorize("Bearer " + OWNER, agents) == (401, None)
    both = dict(agents, **owner)
    assert authorize("Bearer " + OWNER, both) == (200, "operator")
    assert authorize("Bearer " + AGENT, both) == (200, "agent-example")
    assert authorize("Bearer " + AGENT, {"AUN_MCP_AGENT_KEYS": registry(False)}) == (401, None)
    assert authorize("Bearer " + AGENT, {"AUN_MCP_AGENT_KEYS": registry(scopes=[])}) == (403, None)

    malformed = [
        "not json", '{"agent-example":{"sha256":"x"}}',
        '{"agent-example":1}',
        '{"agent-example":1,"agent-example":2}',
        '{"Agent Upper":{"sha256":"' + sha(AGENT) + '","scopes":["mcp:invoke"],"enabled":true}}',
        '{"agent-example":{"sha256":"' + sha(AGENT) + '","scopes":["admin"],"enabled":true}}',
        '{"agent-example":{"sha256":"' + sha(AGENT) + '","scopes":["mcp:invoke"],"enabled":"true"}}',
        '{"agent-example":{"sha256":"' + sha(AGENT) + '","scopes":["mcp:invoke","mcp:invoke"],"enabled":true}}',
    ]
    for value in malformed:
        assert authorize("Bearer " + OWNER, {
            "AUN_MCP_TOKEN": OWNER, "AUN_MCP_AGENT_KEYS": value
        }) == (503, None), value

    assert _load_registry("") == {}
    assert authorize("Bearer " + AGENT, {"AUN_MCP_AGENT_KEYS": registry()}) == (200, "agent-example")
    print("Scoped MCP credential, revocation, missing-scope and configuration tests passed.")


if __name__ == "__main__":
    run()
