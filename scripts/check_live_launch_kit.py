from __future__ import annotations

import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def fail(message: str, payload: object | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


def main() -> int:
    completed = subprocess.run(
        [sys.executable, "scripts/export_live_launch_kit.py"],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        timeout=240,
    )
    if completed.returncode != 0:
        return fail("export_live_launch_kit.py failed", {"stdout": completed.stdout, "stderr": completed.stderr})
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        return fail(f"launch kit exporter did not print JSON: {exc}", completed.stdout)
    kit_path = Path(str(payload.get("kit_path") or ""))
    if not kit_path.exists() or kit_path.stat().st_size < 100_000:
        return fail("launch kit zip is missing or unexpectedly small", payload)
    with zipfile.ZipFile(kit_path) as archive:
        names = archive.namelist()
        required = {
            "LIVE_LAUNCH_KIT_MANIFEST.json",
            "README-LIVE-LAUNCH-KIT.md",
        }
        missing = sorted(required - set(names))
        if missing:
            return fail("launch kit is missing required fixed entries", {"missing": missing, "names": names})
        if not any(name.startswith("server-bundle/") and name.endswith(".zip") for name in names):
            return fail("launch kit does not include the deployable server bundle", names)
        if not any(name.startswith("env-pack/") and name.endswith(".zip") for name in names):
            return fail("launch kit does not include the live environment template pack", names)
        for prefix in (
            "evidence/go-live-report-",
            "evidence/server-go-live-audit-",
            "evidence/live-launch-plan-",
            "evidence/live-ops-handoff-",
        ):
            if not any(name.startswith(prefix) for name in names):
                return fail(f"launch kit is missing {prefix}", names)
        manifest = json.loads(archive.read("LIVE_LAUNCH_KIT_MANIFEST.json").decode("utf-8"))
        if not manifest.get("files"):
            return fail("launch kit manifest does not list packaged files", manifest)
        text_payload = "\n".join(
            archive.read(name).decode("utf-8", errors="replace")
            for name in names
            if name.endswith((".json", ".md", ".txt"))
        )
        for forbidden in ("sk-proj-", "sk-test-", "live-secret-value", "testnet-secret-value"):
            if forbidden in text_payload:
                return fail(f"launch kit leaked forbidden marker {forbidden}", names)

    print(
        json.dumps(
            {
                "ok": True,
                "kit_path": str(kit_path),
                "entry_count": len(names),
                "bytes": kit_path.stat().st_size,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
