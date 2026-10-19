"""Standalone fail-closed credential-policy tests; no real secrets stored."""
import hashlib
import json
from datetime import datetime, timedelta, timezone

from auth import authorize, _load_registry
from agent_keys import make_policy


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

    generated = make_policy("agent-local", AGENT)
    assert generated["agent-local"]["sha256"] == sha(AGENT)
    assert authorize("Bearer " + AGENT, {
        "AUN_MCP_AGENT_KEYS": json.dumps(generated)
    }) == (200, "agent-local")
    for bad_id in ["A", "UPPER", "space name", ""]:
        try:
            make_policy(bad_id, AGENT)
            raise AssertionError("Invalid ID accepted")
        except ValueError:
            pass

    assert _load_registry("") == {}
    assert authorize("Bearer " + AGENT, {"AUN_MCP_AGENT_KEYS": registry()}) == (200, "agent-example")
    current = datetime.now(timezone.utc)
    issued = make_policy("agent-expiring", AGENT)
    expires = issued["agent-expiring"]["expires_at"]
    issued_date = datetime.strptime(expires, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert timedelta(days=29) < issued_date - current <= timedelta(days=31)
    assert authorize("Bearer " + AGENT, {
        "AUN_MCP_AGENT_KEYS": json.dumps(issued)
    }) == (200, "agent-expiring")

    expired = make_policy("agent-expiring", AGENT)
    expired["agent-expiring"]["expires_at"] = (current - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert authorize("Bearer " + AGENT, {
        "AUN_MCP_AGENT_KEYS": json.dumps(expired)
    }) == (401, None)

    for invalid_expiry in ["tomorrow", "2026-02-30T00:00:00Z", "2026-10-19T12:00:00+00:00", 123]:
        broken = make_policy("agent-expiring", AGENT)
        broken["agent-expiring"]["expires_at"] = invalid_expiry
        assert authorize("Bearer " + OWNER, {
            "AUN_MCP_TOKEN": OWNER,
            "AUN_MCP_AGENT_KEYS": json.dumps(broken),
        }) == (503, None), invalid_expiry

    for invalid_lifetime in [0, 91, True, "30"]:
        try:
            make_policy("agent-expiring", AGENT, days=invalid_lifetime)
            raise AssertionError("Invalid expiration lifetime accepted")
        except ValueError:
            pass

    print("Scoped MCP credential, expiry, revocation and fail-closed config tests passed.")


if __name__ == "__main__":
    run()
