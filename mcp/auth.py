"""Fail-closed MCP staging credential verification.

Optional AUN_MCP_AGENT_KEYS registry stores only SHA-256 digests, not plaintext
agent secrets. This is *not* a substitute for OAuth or production identity.
No network, database, filesystem or Academy Core access.
"""
import hashlib
import hmac
import json
import os
import re

MAX_AGENTS = 64
MAX_REGISTRY_BYTES = 8192
TOKEN_MIN = 32
TOKEN_MAX = 256
_AGENT_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_SCOPES = frozenset({"mcp:invoke"})


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate agent configuration key")
        value[key] = item
    return value


def _load_registry(raw):
    if not raw:
        return {}
    if len(raw.encode("utf-8")) > MAX_REGISTRY_BYTES:
        raise ValueError("Agent registry too large")
    registry = json.loads(raw, object_pairs_hook=_unique_pairs)
    if not isinstance(registry, dict) or len(registry) > MAX_AGENTS:
        raise ValueError("Invalid agent registry")
    for agent_id, policy in registry.items():
        if not isinstance(agent_id, str) or not _AGENT_ID.fullmatch(agent_id):
            raise ValueError("Invalid agent identifier")
        if not isinstance(policy, dict) or set(policy) != {"sha256", "scopes", "enabled"}:
            raise ValueError("Invalid agent policy")
        if not isinstance(policy["sha256"], str) or not _DIGEST.fullmatch(policy["sha256"]):
            raise ValueError("Invalid digest")
        if type(policy["enabled"]) is not bool:
            raise ValueError("Invalid enabled state")
        scopes = policy["scopes"]
        if not isinstance(scopes, list) or len(scopes) > 4 or not all(
            isinstance(s, str) and s in _ALLOWED_SCOPES for s in scopes
        ):
            raise ValueError("Invalid agent scopes")
        if len(scopes) != len(set(scopes)):
            raise ValueError("Repeated agent scopes")
    return registry


def authorize(authorization, environment=None):
    """Return (HTTP status code, identity), never return the credential.

    (200, actor) is authorized to invoke the two public bounded MCP tools.
    (401, None) unknown/invalid key, (403, None) recognized but missing scope,
    (503, None) incomplete or malformed server-side authentication settings.
    """
    env = os.environ if environment is None else environment
    owner_token = env.get("AUN_MCP_TOKEN", "")
    try:
        registry = _load_registry(env.get("AUN_MCP_AGENT_KEYS", ""))
    except (ValueError, TypeError, UnicodeError):
        return 503, None
    has_owner = isinstance(owner_token, str) and len(owner_token) >= TOKEN_MIN
    if not has_owner and not registry:
        return 503, None
    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        return 401, None
    supplied = authorization[len("Bearer "):]
    if not TOKEN_MIN <= len(supplied) <= TOKEN_MAX or not supplied.isascii():
        return 401, None

    candidate = hashlib.sha256(supplied.encode("ascii")).hexdigest()
    owner_match = (
        has_owner and hmac.compare_digest(
            hashlib.sha256(owner_token.encode("utf-8")).hexdigest(), candidate
        )
    )
    matched_id = None
    matched_policy = None
    # Visit all entries to avoid early-return timing differences.
    for agent_id, policy in registry.items():
        if hmac.compare_digest(candidate, policy["sha256"]):
            matched_id, matched_policy = agent_id, policy
    if owner_match:
        return 200, "operator"
    if matched_policy is None or not matched_policy["enabled"]:
        return 401, None
    if "mcp:invoke" not in matched_policy["scopes"]:
        return 403, None
    return 200, matched_id
