from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def fail(message: str, payload: Any | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def request_status(url: str, authorization: str | None = None) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    if authorization:
        headers["Authorization"] = authorization
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=5) as response:
            body = response.read().decode(response.headers.get_content_charset() or "utf-8")
            return {
                "status": response.status,
                "headers": dict(response.headers.items()),
                "body": body,
            }
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "status": exc.code,
            "headers": dict(exc.headers.items()),
            "body": body,
        }


def wait_for_health(base_url: str, process: subprocess.Popen[str], timeout_seconds: float = 25.0) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=2)
            return {
                "ok": False,
                "error": "server process exited before health became ready",
                "returncode": process.returncode,
                "stdout": stdout[-1000:],
                "stderr": stderr[-1000:],
            }
        try:
            health = request_status(f"{base_url}/api/health")
            if health["status"] == 200 and json.loads(health["body"]).get("ok") is True:
                return {"ok": True, "health": health}
        except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = f"{exc.__class__.__name__}: {exc}"
        time.sleep(0.25)
    return {"ok": False, "error": f"health timeout: {last_error}"}


def main() -> int:
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update(
        {
            "APP_HOST": "127.0.0.1",
            "APP_PORT": str(port),
            "APP_ENV": "server",
            "APP_BASIC_AUTH_USER": "admin",
            "APP_BASIC_AUTH_PASSWORD": "correct-long-password",
            "AUTH_FAILURE_LIMIT": "2",
            "AUTH_FAILURE_WINDOW_SECONDS": "300",
            "AUTH_LOCKOUT_SECONDS": "30",
            "AI_PROVIDER": "rules",
            "AI_OPERATOR_ALLOW_FILE_WRITE": "false",
            "AI_OPERATOR_ALLOW_SHELL": "false",
            "EXCHANGE_MODE": "paper",
            "ENABLE_BINANCE_TESTNET": "false",
            "BINANCE_PLACE_TESTNET_ORDERS": "false",
            "ENABLE_BINANCE_LIVE": "false",
            "BINANCE_PLACE_LIVE_ORDERS": "false",
            "MARKET_DATA_SOURCE": "synthetic",
            "HTTP_TIMEOUT_SECONDS": "2",
            "HTTP_RETRIES": "0",
        }
    )
    process = subprocess.Popen(
        [PYTHON, "-B", "app/server.py"],
        cwd=ROOT_DIR,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        ready = wait_for_health(base_url, process)
        if not ready.get("ok"):
            return fail("temporary server did not become healthy", ready)

        wrong = auth_header("admin", "wrong-password")
        correct = auth_header("admin", "correct-long-password")

        first = request_status(f"{base_url}/api/state", wrong)
        if first["status"] != 401:
            return fail("first failed HTTP auth attempt should return 401", first)

        second = request_status(f"{base_url}/api/state", wrong)
        if second["status"] != 429:
            return fail("second failed HTTP auth attempt should return 429 lockout", second)
        if not second["headers"].get("Retry-After"):
            return fail("HTTP lockout response must include Retry-After", second)

        correct_while_locked = request_status(f"{base_url}/api/state", correct)
        if correct_while_locked["status"] != 429:
            return fail("correct credentials must remain blocked during HTTP lockout", correct_while_locked)

        health_after_lockout = request_status(f"{base_url}/api/health")
        if health_after_lockout["status"] != 200:
            return fail("health endpoint should remain reachable without auth during lockout", health_after_lockout)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)

    print(
        json.dumps(
            {
                "ok": True,
                "base_url": base_url,
                "first_failure_status": 401,
                "lockout_status": 429,
                "retry_after_present": True,
                "correct_credentials_blocked_while_locked": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
