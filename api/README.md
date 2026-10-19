# AUN public preview API (standalone)

This is deliberately a **new, minimal public implementation**, not a copy of the private Academy Core or complete AUN backend. No authentication, accounts, signed exchange, database, MCP or A2A. Two bounded verification tools only. No request bodies intentionally persisted.

## Local run
```sh
python -m pip install -r api/requirements.txt
uvicorn app:app --app-dir api --host 127.0.0.1 --port 8000
```

## Render free tier
- Root directory: repository root
- Runtime: Python
- Build: `pip install -r api/requirements.txt`
- Start: `uvicorn app:app --app-dir api --host 0.0.0.0 --port $PORT --workers 1 --no-proxy-headers`
- Plan: Free; no payment required

This preview uses an in-process best-effort rate limit, not a global security gateway. Never expose secrets or personal data. Production requires independent tests, dependency pinning, proxy/rate policy and security review.
