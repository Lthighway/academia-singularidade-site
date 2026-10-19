"""Public, stateless AUN preview: no private Core, accounts, or storage."""
import hashlib
import hmac
import json
import math
import os
import time
from collections import deque
from threading import Lock
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="Academia Singularidade — Public Verification Preview", version="0.1.0")
MAX_BODY = 8192
_lock = Lock()
_requests = {}
class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
class HashInput(StrictModel):
    document: str = Field(max_length=4096)
    algorithm: str = Field(default="sha256", pattern="^(sha256|sha512)$")
    expected: str | None = Field(default=None, max_length=128, pattern="^[0-9a-fA-F]+$")
class JsonInput(StrictModel):
    document: str = Field(max_length=4096)
def parse_json(raw):
    def unique(pairs):
        d = {}
        for k,v in pairs:
            if k in d:
                raise ValueError("Duplicate JSON key")
            d[k] = v
        return d
    def reject(x):
        raise ValueError("Nonfinite JSON value")
    obj = json.loads(raw, object_pairs_hook=unique, parse_constant=reject)
    def walk(v, depth=0):
        if depth > 32:
            raise ValueError("JSON depth exceeded")
        if isinstance(v, dict):
            for x in v.values(): walk(x, depth+1)
        elif isinstance(v, list):
            for x in v: walk(x, depth+1)
        elif isinstance(v, float) and not math.isfinite(v):
            raise ValueError("Nonfinite JSON number")
    walk(obj)
    return obj
@app.middleware("http")
async def guard(request: Request, call_next):
    if request.method not in ("GET", "POST", "HEAD", "OPTIONS"):
        return JSONResponse({"detail":"Method not allowed"},status_code=405)
    if request.method == "POST":
        if request.headers.get("content-type","").split(";")[0].strip().lower() != "application/json":
            return JSONResponse({"detail":"Content-Type must be application/json"},status_code=415)
        try:
            length = int(request.headers.get("content-length","0"))
        except ValueError:
            return JSONResponse({"detail":"Invalid Content-Length"},status_code=400)
        if length > MAX_BODY:
            return JSONResponse({"detail":"Body too large"},status_code=413)
        try:
            import asyncio
            body = await asyncio.wait_for(request.body(),timeout=5)
        except (TimeoutError, ValueError):
            return JSONResponse({"detail":"Body read failed"},status_code=408)
        if len(body)>MAX_BODY:
            return JSONResponse({"detail":"Body too large"},status_code=413)
    # Best-effort in-process limit; NOT a production/global abuse control.
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _lock:
        if len(_requests)>2000:
            _requests.clear()
        q = _requests.setdefault(ip,deque())
        while q and q[0]<now-60:q.popleft()
        if len(q)>=60:
            return JSONResponse({"detail":"Rate limit exceeded"},status_code=429)
        q.append(now)
    response=await call_next(request)
    response.headers["Cache-Control"]="no-store"
    response.headers["X-Content-Type-Options"]="nosniff"
    return response
def mcp_preview_enabled():
    """Report MCP only when the router and a valid auth configuration exist."""
    if os.environ.get("AUN_ENABLE_MCP") != "1":
        return False
    if not os.environ.get("AUN_MCP_HOSTS", "").strip():
        return False
    try:
        # combined.py loads the isolated MCP directory when enabled.
        from auth import authorize
        # Empty authorization must yield 401 for a correctly configured
        # protected endpoint, regardless of operator versus agent-only keys.
        return authorize("")[0] == 401
    except (ImportError, ValueError, TypeError):
        return False


@app.get("/")
def root():
    return {"service":"Academia Singularidade AUN public preview","status":"online","health":"/healthz","tools":"/v1/tools","docs":"/docs","mcp":mcp_preview_enabled(),"a2a":False}

@app.get("/healthz")
def health():
    return {"status":"ok","service":"aun-public-preview"}
@app.get("/v1/tools")
def tools():
    return {"status":"preview","public":True,"tools":[
        {"name":"hash","path":"/v1/verify/hash"},
        {"name":"json","path":"/v1/verify/json"}],
        "mcp":mcp_preview_enabled(),"a2a":False}
@app.get("/.well-known/agent-utility-network.json")
def discovery_manifest():
    """Machine-readable public capabilities, without private-network claims."""
    return {
        "network": "academia-singularidade-aun",
        "schema_version": "0.1",
        "status": "public-preview",
        "base_url": "https://academia-singularidade-aun.onrender.com",
        "documentation_url": "https://lthighway.github.io/academia-singularidade-site/docs.html",
        "openapi_url": "https://academia-singularidade-aun.onrender.com/openapi.json",
        "mcp_url": "https://academia-singularidade-aun.onrender.com/mcp" if mcp_preview_enabled() else None,
        "tools": [
            {"name": "hash", "method": "POST", "path": "/v1/verify/hash"},
            {"name": "json", "method": "POST", "path": "/v1/verify/json"},
        ],
        "transports": {"rest": True, "mcp_remote": mcp_preview_enabled(), "a2a": False},
        "authentication": {"rest": "none", "mcp_remote": "restricted-bearer-preview" if mcp_preview_enabled() else "unavailable"},
        "limits": {
            "document_max_characters": 4096,
            "request_body_max_bytes": MAX_BODY,
            "rate_limit": "best-effort-per-process",
        },
    }


@app.post("/v1/verify/hash")
def hash_text(payload:HashInput):
    digest=hashlib.new(payload.algorithm,payload.document.encode("utf-8")).hexdigest()
    return {"algorithm":payload.algorithm,"digest":digest,
        "matches":None if payload.expected is None else hmac.compare_digest(digest,payload.expected.lower())}
@app.post("/v1/verify/json")
def json_check(payload:JsonInput):
    try:
        parse_json(payload.document)
        return {"valid":True}
    except (ValueError,RecursionError):
        return {"valid":False,"error":"Invalid, duplicate-key, nonfinite, or over-depth JSON"}

# Deliberately disabled unless explicitly enabled in the deployment environment.
# The REST FastAPI routes above remain the default application.
if os.environ.get("AUN_ENABLE_MCP") == "1":
    from combined import wrap_api_with_mcp
    app = wrap_api_with_mcp(app)
