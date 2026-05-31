from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

import run_all_checks as runner  # noqa: E402


def fake_step(name: str, args: list[str], timeout: int = 120) -> dict:
    calls.append(name)
    return {
        "name": name,
        "ok": True,
        "returncode": 0,
        "duration_seconds": 0,
        "command": args,
        "stdout": "",
        "stderr": "",
        "timed_out": False,
    }


def fake_server_step(name: str, args: list[str], timeout: int = 120) -> dict:
    calls.append(name)
    if name != "server_build_api":
        raise AssertionError(f"server-side check ran after build mismatch: {name}")
    return {
        "name": name,
        "ok": False,
        "returncode": 1,
        "duration_seconds": 0,
        "command": args,
        "stdout": "",
        "stderr": "running server build does not match workspace",
        "timed_out": False,
    }


def fail(message: str, details: object | None = None) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    if details is not None:
        print(json.dumps(details, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


calls: list[str] = []


def main() -> int:
    original = {
        "REPORT_DIR": runner.REPORT_DIR,
        "BASE_URL": runner.BASE_URL,
        "run_step": runner.run_step,
        "run_server_step": runner.run_server_step,
        "health_ok": runner.health_ok,
        "quiesce_background_work": runner.quiesce_background_work,
    }
    with tempfile.TemporaryDirectory(prefix="run-all-build-gate-") as tmp_dir:
        try:
            runner.REPORT_DIR = Path(tmp_dir)
            runner.BASE_URL = "http://127.0.0.1:8787"
            runner.run_step = fake_step
            runner.run_server_step = fake_server_step
            runner.health_ok = lambda: True
            runner.quiesce_background_work = lambda: (_ for _ in ()).throw(
                AssertionError("quiesce must not run before server_build_api passes")
            )
            rc = runner.main()
            if rc != 1:
                return fail("run_all_checks should fail on server build mismatch", {"returncode": rc, "calls": calls})
            if "server_build_api" not in calls:
                return fail("server_build_api was not called", calls)
            if "background_quiesce" in calls:
                return fail("background quiesce ran before build verification", calls)
            active = json.loads((Path(tmp_dir) / "local-readiness-active.json").read_text(encoding="utf-8"))
            if active.get("status") != "completed" or active.get("ok") is not False:
                return fail("build mismatch did not produce a completed failed active report", active)
            if "server_build_api" not in (active.get("failed_steps") or []):
                return fail("active report did not record server_build_api as failed", active)
        finally:
            runner.REPORT_DIR = original["REPORT_DIR"]
            runner.BASE_URL = original["BASE_URL"]
            runner.run_step = original["run_step"]
            runner.run_server_step = original["run_server_step"]
            runner.health_ok = original["health_ok"]
            runner.quiesce_background_work = original["quiesce_background_work"]
    print(json.dumps({"ok": True, "checked": "server_build_before_quiesce"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
