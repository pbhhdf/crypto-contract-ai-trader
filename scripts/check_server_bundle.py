from __future__ import annotations

import base64
import io
import json
import os
import sys
import zipfile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = os.getenv("TRADER_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
HTTP_TIMEOUT_SECONDS = float(os.getenv("TRADER_HTTP_TIMEOUT_SECONDS", "60"))
AUTH_USER = os.getenv("TRADER_AUTH_USER", "")
AUTH_PASSWORD = os.getenv("TRADER_AUTH_PASSWORD", "")


def request_bundle() -> tuple[dict[str, str], bytes]:
    headers = {"Accept": "application/zip"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    request = Request(f"{BASE_URL}/api/server-bundle", headers=headers, method="GET")
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        response_headers = {key.lower(): value for key, value in response.headers.items()}
        return response_headers, response.read()


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def unsafe_entry(name: str) -> bool:
    return (
        name == ".env"
        or name.startswith("data/")
        or name.startswith("reports/")
        or name.endswith(".db")
        or name.endswith(".sqlite")
        or name.endswith(".sqlite3")
        or name.endswith(".zip")
        or "__pycache__/" in name
    )


def main() -> int:
    try:
        headers, body = request_bundle()
        content_type = headers.get("content-type", "")
        disposition = headers.get("content-disposition", "")
        if "application/zip" not in content_type:
            return fail(f"unexpected content type: {content_type!r}")
        if "filename=" not in disposition:
            return fail("server bundle response is missing a download filename")
        if len(body) < 100_000:
            return fail(f"server bundle is unexpectedly small: {len(body)} bytes")

        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            names = archive.namelist()
            bad_entries = [name for name in names if unsafe_entry(name)]
            if bad_entries:
                return fail(f"bundle contains unsafe entries: {bad_entries[:10]!r}")
            if "SERVER_BUNDLE_MANIFEST.json" not in names:
                return fail("bundle manifest is missing")
            manifest: dict[str, Any] = json.loads(archive.read("SERVER_BUNDLE_MANIFEST.json").decode("utf-8"))
            manifest_files = manifest.get("files") or []
            if not manifest_files:
                return fail("bundle manifest does not list files")

        summary = {
            "ok": True,
            "bytes": len(body),
            "entry_count": len(names),
            "manifest_files": len(manifest_files),
            "content_type": content_type,
            "content_disposition": disposition,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        return fail(f"could not validate server bundle: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
