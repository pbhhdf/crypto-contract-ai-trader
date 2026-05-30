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
HTTP_TIMEOUT_SECONDS = float(os.getenv("TRADER_HTTP_TIMEOUT_SECONDS", "120"))
AUTH_USER = os.getenv("TRADER_AUTH_USER", os.getenv("APP_BASIC_AUTH_USER", ""))
AUTH_PASSWORD = os.getenv("TRADER_AUTH_PASSWORD", os.getenv("APP_BASIC_AUTH_PASSWORD", ""))


def request_pack() -> tuple[dict[str, str], bytes]:
    headers = {"Accept": "application/zip"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    request = Request(f"{BASE_URL}/api/live-env-pack", headers=headers, method="GET")
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        response_headers = {key.lower(): value for key, value in response.headers.items()}
        return response_headers, response.read()


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    try:
        headers, body = request_pack()
        content_type = headers.get("content-type", "")
        disposition = headers.get("content-disposition", "")
        if "application/zip" not in content_type:
            return fail(f"unexpected content type: {content_type!r}")
        if "filename=" not in disposition:
            return fail("live env pack response is missing a download filename")
        if len(body) < 8_000:
            return fail(f"live env pack is unexpectedly small: {len(body)} bytes")
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            names = archive.namelist()
            for entry in (
                "LIVE_ENV_PACK_MANIFEST.json",
                "README-LIVE-ENV-PACK.md",
                "env/mvp_server.env",
                "env/testnet_validate.env",
                "env/testnet_place.env",
                "env/live_guarded.env",
            ):
                if entry not in names:
                    return fail(f"live env pack is missing {entry}")
            manifest = json.loads(archive.read("LIVE_ENV_PACK_MANIFEST.json").decode("utf-8"))
            if "live_guarded" not in (manifest.get("stages") or []):
                return fail("live env pack manifest does not include live_guarded")
        print(
            json.dumps(
                {
                    "ok": True,
                    "bytes": len(body),
                    "entry_count": len(names),
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
        return fail(f"could not validate live env pack: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
