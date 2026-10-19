"""Experimental MCP stdio adapter for public, deterministic AUN tools.

No private Core access, network listener, filesystem writes, accounts, or exchange.
Run with: python -m mcp.server (from repository root).
"""
import hashlib
import json
import math
import hmac
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Academia Singularidade — Verification Preview")

@mcp.tool()
def hash_text(document: str, algorithm: str = "sha256", expected: str | None = None) -> dict:
    """Hash bounded UTF-8 text with SHA-256 or SHA-512."""
    if len(document) > 4096:
        raise ValueError("Document too long")
    if algorithm not in ("sha256", "sha512"):
        raise ValueError("Unsupported algorithm")
    digest = hashlib.new(algorithm, document.encode("utf-8")).hexdigest()
    if expected is not None and (len(expected)>128 or any(c not in "0123456789abcdefABCDEF" for c in expected)):
        raise ValueError("Invalid expected digest")
    return {"algorithm": algorithm, "digest": digest, "matches": None if expected is None else hmac.compare_digest(digest, expected.lower())}

@mcp.tool()
def validate_json(document: str) -> dict:
    """Check bounded strict JSON syntax; reject duplicate keys and nonfinite numbers."""
    if len(document) > 4096:
        raise ValueError("Document too long")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError("Nonfinite JSON constant")
    def check(value, depth=0):
        if depth > 32:
            raise ValueError("JSON depth exceeded")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Nonfinite JSON number")
        if isinstance(value, dict):
            for child in value.values():
                check(child, depth + 1)
        if isinstance(value, list):
            for child in value:
                check(child, depth + 1)
    try:
        value = json.loads(document, object_pairs_hook=unique, parse_constant=reject_constant)
        check(value)
        return {"valid": True}
    except (ValueError, RecursionError):
        return {"valid": False, "error": "Invalid, duplicate-key, nonfinite, or over-depth JSON"}

if __name__ == "__main__":
    mcp.run(transport="stdio")
