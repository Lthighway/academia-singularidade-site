"""End-to-end test for the single Render-ready REST+MCP ASGI process.

Enabling the MCP router must not break REST routes or bypass MCP auth.
Everything runs over an ephemeral loopback port with a disposable test token.
"""
import asyncio
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
from test_remote_integration import TOKEN, ROOT, exercise, free_port


async def main():
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update({
        "AUN_ENABLE_MCP": "1",
        "AUN_MCP_TOKEN": TOKEN,
        "AUN_MCP_HOSTS": f"127.0.0.1:{port}",
        "AUN_MCP_ORIGINS": "https://allowed.example",
    })

    with tempfile.TemporaryFile(mode="w+t") as log:
        process = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "app:app",
                "--app-dir", str(ROOT / "api"), "--host", "127.0.0.1",
                "--port", str(port), "--workers", "1",
            ],
            cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(80):
                if process.poll() is not None:
                    raise RuntimeError("Combined ASGI server exited during startup")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        break
                except OSError:
                    await asyncio.sleep(0.15)
            else:
                raise TimeoutError("Combined ASGI server did not start")

            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                health = await client.get(base + "/healthz")
                assert health.status_code == 200 and health.json()["status"] == "ok"
                catalog = await client.get(base + "/v1/tools")
                assert catalog.status_code == 200
                assert {x["name"] for x in catalog.json()["tools"]} == {"json", "hash"}
                manifest = await client.get(base + "/.well-known/agent-utility-network.json")
                assert manifest.status_code == 200
                assert manifest.json()["status"] == "public-preview"

            await exercise(base)
            print("One-process REST + authenticated MCP integration passed.")
        except BaseException:
            log.flush()
            log.seek(0)
            print("Combined ASGI server log (failure only):",
                  log.read()[-8000:], file=sys.stderr)
            raise
        finally:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    asyncio.run(main())
