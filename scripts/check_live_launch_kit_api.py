from __future__ import annotations

import base64
import io
import json
import os
import sys
import zipfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = os.getenv("TRADER_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
HTTP_TIMEOUT_SECONDS = float(os.getenv("TRADER_HTTP_TIMEOUT_SECONDS", "180"))
AUTH_USER = os.getenv("TRADER_AUTH_USER", os.getenv("APP_BASIC_AUTH_USER", ""))
AUTH_PASSWORD = os.getenv("TRADER_AUTH_PASSWORD", os.getenv("APP_BASIC_AUTH_PASSWORD", ""))


def request_kit() -> tuple[dict[str, str], bytes]:
    headers = {"Accept": "application/zip"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    request = Request(f"{BASE_URL}/api/live-launch-kit", headers=headers, method="GET")
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        response_headers = {key.lower(): value for key, value in response.headers.items()}
        return response_headers, response.read()


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    try:
        headers, body = request_kit()
        content_type = headers.get("content-type", "")
        disposition = headers.get("content-disposition", "")
        if "application/zip" not in content_type:
            return fail(f"unexpected content type: {content_type!r}")
        if "filename=" not in disposition:
            return fail("launch kit response is missing a download filename")
        if len(body) < 100_000:
            return fail(f"launch kit is unexpectedly small: {len(body)} bytes")
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            names = archive.namelist()
            if "LIVE_LAUNCH_KIT_MANIFEST.json" not in names:
                return fail("launch kit manifest is missing")
            if "README-LIVE-LAUNCH-KIT.md" not in names:
                return fail("launch kit README is missing")
            if not any(name.startswith("server-bundle/") and name.endswith(".zip") for name in names):
                return fail("launch kit does not include a server bundle")
            if not any(name.startswith("env-pack/") and name.endswith(".zip") for name in names):
                return fail("launch kit does not include a live environment template pack")
            manifest = json.loads(archive.read("LIVE_LAUNCH_KIT_MANIFEST.json").decode("utf-8"))
            manifest_files = manifest.get("files") or []
            if len(manifest_files) < 8:
                return fail("launch kit manifest has too few files")
        print(
            json.dumps(
                {
                    "ok": True,
                    "bytes": len(body),
                    "entry_count": len(names),
                    "manifest_files": len(manifest_files),
                    "content_type": content_type,
                    "content_disposition": disposition,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        return fail(f"could not validate live launch kit: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
