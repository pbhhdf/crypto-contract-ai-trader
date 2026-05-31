from __future__ import annotations

import json
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from run_all_checks import write_json_atomic  # noqa: E402


def read_json_retry(path: Path) -> dict:
    last_error: Exception | None = None
    for attempt in range(8):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (PermissionError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(0.02 * (attempt + 1))
    if last_error is not None:
        raise last_error
    return {}


def write_many(path: Path, worker: int) -> None:
    for index in range(40):
        write_json_atomic(
            path,
            {
                "ok": True,
                "status": "running",
                "worker": worker,
                "index": index,
                "steps": [{"name": f"worker_{worker}_{index}", "ok": True}],
            },
        )
        payload = read_json_retry(path)
        if payload.get("ok") is not True:
            raise AssertionError(f"invalid payload after worker {worker}: {payload}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="local-readiness-atomic-") as tmp_dir:
        path = Path(tmp_dir) / "local-readiness-active.json"
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(write_many, path, worker) for worker in range(8)]
            for future in as_completed(futures):
                future.result()
        final_payload = read_json_retry(path)
        if final_payload.get("status") != "running":
            raise AssertionError(f"unexpected final payload: {final_payload}")
    print(json.dumps({"ok": True, "concurrent_writers": 8, "writes_per_worker": 40}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
