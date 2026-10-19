"""Local API tests: bounded and deterministic."""
from fastapi.testclient import TestClient
from app import app
client=TestClient(app)
def test_health():
    r=client.get("/healthz")
    assert r.status_code==200 and r.json()["status"]=="ok"
def test_catalog():
    r=client.get("/v1/tools")
    assert r.status_code==200
    assert [x["name"] for x in r.json()["tools"]]==["hash","json"]
def test_hash():
    r=client.post("/v1/verify/hash",json={"document":"abc"})
    assert r.status_code==200
    assert r.json()["digest"]=="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
def test_json_valid():
    assert client.post("/v1/verify/json",json={"document":'{"a":1}'}).json()["valid"] is True
def test_json_duplicate_key():
    assert client.post("/v1/verify/json",json={"document":'{"a":1,"a":2}'}).json()["valid"] is False
def test_reject_unknown_fields():
    assert client.post("/v1/verify/hash",json={"document":"abc","unexpected":1}).status_code==422
def test_reject_large_payload():
    assert client.post("/v1/verify/json",json={"document":"x"*9000}).status_code==413
def test_reject_content_type():
    assert client.post("/v1/verify/json",content="hello",headers={"Content-Type":"text/plain"}).status_code==415

def test_json_overflow_rejected():
    assert client.post('/v1/verify/json',json={'document':'1e9999'}).json()['valid'] is False

def test_discovery_manifest_accurate():
    r = client.get("/.well-known/agent-utility-network.json")
    assert r.status_code == 200
    manifest = r.json()
    assert manifest["status"] == "public-preview"
    assert {item["name"] for item in manifest["tools"]} == {"hash", "json"}
    assert manifest["transports"] == {"rest": True, "mcp_remote": False, "a2a": False}
    assert manifest["limits"]["request_body_max_bytes"] == 8192
