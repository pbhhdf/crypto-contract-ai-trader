from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(ROOT_DIR / ".env")

BASE_URL = os.getenv("TRADER_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
AUTH_USER = os.getenv("TRADER_AUTH_USER", os.getenv("APP_BASIC_AUTH_USER", ""))
AUTH_PASSWORD = os.getenv("TRADER_AUTH_PASSWORD", os.getenv("APP_BASIC_AUTH_PASSWORD", ""))
HTTP_TIMEOUT_SECONDS = float(os.getenv("TRADER_HTTP_TIMEOUT_SECONDS", "120"))


def headers() -> dict[str, str]:
    result = {"Accept": "application/json", "Content-Type": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        result["Authorization"] = f"Basic {token}"
    return result


def request_json(method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if method == "POST" else None
    request = Request(f"{BASE_URL}{path}", data=body, headers=headers(), method=method)
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def find_first_snapshot_path(value: object) -> str:
    if isinstance(value, dict):
        snapshot = value.get("snapshot")
        if isinstance(snapshot, dict) and snapshot.get("created") and snapshot.get("path"):
            return str(snapshot["path"])
        for item in value.values():
            found = find_first_snapshot_path(item)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = find_first_snapshot_path(item)
            if found:
                return found
    return ""


def main() -> int:
    payload = request_json("GET", "/api/ai-operator")
    status = payload.get("status") or {}
    if not isinstance(status, dict) or not status.get("enabled"):
        return fail("AI operator endpoint is not enabled")
    if "workspace_root" not in status:
        return fail("AI operator status missing workspace root")
    if "/shell <command>" not in (status.get("commands") or []):
        return fail("AI operator status is missing shell command metadata")
    if "/patch [path]\\n*** Begin Patch ..." not in (status.get("commands") or []):
        return fail("AI operator status is missing patch command metadata")
    for command in [
        "/readiness",
        "/go-live",
        "/final-live-ready [--prearm] [--skip-ai-operator]",
        "/live-pilot [symbol]",
        "/live-postflight [symbol] [--run-id RUN_ID]",
        "/resolve-live-blockers [symbol]",
        "/live-pilot-run [symbol] --confirm LAUNCH_LIVE_PILOT",
        "/live-arm --confirm ARM_LIVE_TRADING [--ttl-seconds N|--ttl-minutes N] [--reason text]",
        "/live-disarm [--reason text]",
        "/live-attest --confirm LIVE_ATTESTATION_CONFIRMED [--actor name] [--note text]",
        "/live-attestation-clear [--reason text]",
        "/panic-stop --confirm PANIC_STOP [--no-cancel] [--no-exchange-cancel] [--flatten --flatten-confirm FLATTEN_POSITIONS]",
        "/server-readiness",
        "/server-readiness-run [--real] [--testnet] [--mode binance_testnet_validate|binance_testnet_place_order] [--allow-testnet-placement] [--cycles N] [--interval seconds] [--timeout seconds] [--strict]",
        "/server-readiness-cancel [--reason text]",
        "/env-audit [mvp_server|testnet_validate|testnet_place|live_guarded]",
        "/launch-plan",
        "/handoff [symbol]",
        "/launch-kit",
        "/env-pack",
        "/bundle",
        "/server-audit",
    ]:
        if command not in (status.get("commands") or []):
            return fail(f"AI operator status is missing {command} command metadata")
    if status.get("allow_file_write") and status.get("allow_shell") and not status.get("apply_model_file_actions"):
        return fail("AI operator high-permission mode should auto-apply model file actions")
    if not status.get("redacts_secrets"):
        return fail("AI operator status should advertise secret redaction")

    list_result = request_json("POST", "/api/ai-operator/chat", {"message": "/list app/static"})
    list_history = list_result.get("history") or []
    if not list_history:
        return fail("AI operator did not record list command history")
    if "app/static/app.js" not in json.dumps(list_result, ensure_ascii=False):
        return fail("AI operator list command did not expose app/static/app.js")

    readiness_result = request_json("POST", "/api/ai-operator/chat", {"message": "/readiness"})
    if '"action": "readiness"' not in json.dumps(readiness_result, ensure_ascii=False):
        return fail("AI operator readiness command did not return readiness action")
    gate_result = request_json("POST", "/api/ai-operator/chat", {"message": "/go-live"})
    if '"action": "go_live_gate"' not in json.dumps(gate_result, ensure_ascii=False):
        return fail("AI operator go-live command did not return go_live_gate action")
    final_result = request_json("POST", "/api/ai-operator/chat", {"message": "/final-live-ready --prearm"})
    if '"action": "final_live_ready"' not in json.dumps(final_result, ensure_ascii=False):
        return fail("AI operator final-live-ready command did not return final_live_ready action")
    pilot_result = request_json("POST", "/api/ai-operator/chat", {"message": "/live-pilot BTCUSDT"})
    if '"action": "live_pilot"' not in json.dumps(pilot_result, ensure_ascii=False):
        return fail("AI operator live-pilot command did not return live_pilot action")
    postflight_result = request_json("POST", "/api/ai-operator/chat", {"message": "/live-postflight BTCUSDT"})
    if '"action": "live_pilot_postflight"' not in json.dumps(postflight_result, ensure_ascii=False):
        return fail("AI operator live-postflight command did not return live_pilot_postflight action")
    blockers_result = request_json("POST", "/api/ai-operator/chat", {"message": "/resolve-live-blockers BTCUSDT"})
    if '"action": "live_blocker_resolution"' not in json.dumps(blockers_result, ensure_ascii=False):
        return fail("AI operator resolve-live-blockers command did not return live_blocker_resolution action")
    live_arm_rejected = request_json(
        "POST",
        "/api/ai-operator/chat",
        {"message": "/live-arm --confirm WRONG --ttl-seconds 60 --reason ai_operator_smoke"},
    )
    serialized_live_arm_rejected = json.dumps(live_arm_rejected, ensure_ascii=False)
    if '"action": "error"' not in serialized_live_arm_rejected or "ARM_LIVE_TRADING" not in serialized_live_arm_rejected:
        return fail("AI operator live-arm rejected response did not require ARM_LIVE_TRADING")
    live_disarm_result = request_json(
        "POST",
        "/api/ai-operator/chat",
        {"message": "/live-disarm --reason ai_operator_smoke"},
    )
    if '"action": "live_disarm"' not in json.dumps(live_disarm_result, ensure_ascii=False):
        return fail("AI operator live-disarm command did not return live_disarm action")
    live_attest_rejected = request_json(
        "POST",
        "/api/ai-operator/chat",
        {"message": "/live-attest --confirm WRONG --actor smoke --note smoke"},
    )
    serialized_live_attest_rejected = json.dumps(live_attest_rejected, ensure_ascii=False)
    if '"action": "error"' not in serialized_live_attest_rejected or "LIVE_ATTESTATION_CONFIRMED" not in serialized_live_attest_rejected:
        return fail("AI operator live-attest rejected response did not require LIVE_ATTESTATION_CONFIRMED")
    live_attest_result = request_json(
        "POST",
        "/api/ai-operator/chat",
        {"message": "/live-attest --confirm LIVE_ATTESTATION_CONFIRMED --actor smoke --note ai_operator_smoke"},
    )
    if '"action": "live_attestation_save"' not in json.dumps(live_attest_result, ensure_ascii=False):
        return fail("AI operator live-attest command did not return live_attestation_save action")
    live_attest_clear = request_json(
        "POST",
        "/api/ai-operator/chat",
        {"message": "/live-attestation-clear --reason ai_operator_smoke_cleanup"},
    )
    if '"action": "live_attestation_clear"' not in json.dumps(live_attest_clear, ensure_ascii=False):
        return fail("AI operator live-attestation-clear command did not return live_attestation_clear action")
    panic_rejected = request_json("POST", "/api/ai-operator/chat", {"message": "/panic-stop --confirm WRONG"})
    serialized_panic_rejected = json.dumps(panic_rejected, ensure_ascii=False)
    if '"action": "error"' not in serialized_panic_rejected or "PANIC_STOP" not in serialized_panic_rejected:
        return fail("AI operator panic-stop rejected response did not require PANIC_STOP")
    panic_result = request_json(
        "POST",
        "/api/ai-operator/chat",
        {"message": "/panic-stop --confirm PANIC_STOP --reason ai_operator_smoke --no-cancel --no-exchange-cancel"},
    )
    serialized_panic = json.dumps(panic_result, ensure_ascii=False)
    if '"action": "panic_stop"' not in serialized_panic:
        return fail("AI operator panic-stop command did not return panic_stop action")
    reset_result = request_json("POST", "/api/reset-emergency-stop", {"reason": "check_ai_operator_cleanup"})
    if reset_result.get("emergency_stop"):
        return fail("AI operator panic-stop cleanup did not clear emergency stop")
    if (reset_result.get("alerts") or {}).get("summary", {}).get("critical"):
        return fail("AI operator panic-stop cleanup left critical alerts open")
    server_readiness_result = request_json("POST", "/api/ai-operator/chat", {"message": "/server-readiness"})
    if '"action": "server_live_readiness"' not in json.dumps(server_readiness_result, ensure_ascii=False):
        return fail("AI operator server-readiness command did not return server_live_readiness action")
    server_readiness_cancel_result = request_json(
        "POST",
        "/api/ai-operator/chat",
        {"message": "/server-readiness-cancel --reason ai_operator_smoke_idle"},
    )
    if '"action": "server_live_readiness_cancel"' not in json.dumps(server_readiness_cancel_result, ensure_ascii=False):
        return fail("AI operator server-readiness-cancel command did not return server_live_readiness_cancel action")
    env_audit_result = request_json("POST", "/api/ai-operator/chat", {"message": "/env-audit live_guarded"})
    serialized_env_audit = json.dumps(env_audit_result, ensure_ascii=False)
    if '"action": "live_env_profile"' not in serialized_env_audit:
        return fail("AI operator env-audit command did not return live_env_profile action")
    if "secret-value" in serialized_env_audit or "sk-test" in serialized_env_audit:
        return fail("AI operator env-audit leaked a secret-looking value")
    launch_plan_result = request_json("POST", "/api/ai-operator/chat", {"message": "/launch-plan"})
    serialized_launch_plan = json.dumps(launch_plan_result, ensure_ascii=False)
    if '"action": "live_launch_plan"' not in serialized_launch_plan:
        return fail("AI operator launch-plan command did not return live_launch_plan action")
    if "live-secret-value" in serialized_launch_plan or "sk-proj-" in serialized_launch_plan or "sk-test-" in serialized_launch_plan:
        return fail("AI operator launch-plan leaked a raw secret assignment")
    launch_kit_result = request_json("POST", "/api/ai-operator/chat", {"message": "/launch-kit"})
    serialized_launch_kit = json.dumps(launch_kit_result, ensure_ascii=False)
    if '"action": "live_launch_kit"' not in serialized_launch_kit:
        return fail("AI operator launch-kit command did not return live_launch_kit action")
    if "live-secret-value" in serialized_launch_kit or "sk-proj-" in serialized_launch_kit or "sk-test-" in serialized_launch_kit:
        return fail("AI operator launch-kit leaked a raw secret assignment")
    env_pack_result = request_json("POST", "/api/ai-operator/chat", {"message": "/env-pack"})
    serialized_env_pack = json.dumps(env_pack_result, ensure_ascii=False)
    if '"action": "live_env_pack"' not in serialized_env_pack:
        return fail("AI operator env-pack command did not return live_env_pack action")
    if "live-secret-value" in serialized_env_pack or "sk-proj-" in serialized_env_pack or "sk-test-" in serialized_env_pack:
        return fail("AI operator env-pack leaked a raw secret assignment")
    handoff_result = request_json("POST", "/api/ai-operator/chat", {"message": "/handoff BTCUSDT"})
    serialized_handoff = json.dumps(handoff_result, ensure_ascii=False)
    if '"action": "live_ops_handoff"' not in serialized_handoff:
        return fail("AI operator handoff command did not return live_ops_handoff action")
    for marker in ("LAUNCH_LIVE_PILOT", "PANIC_STOP", "run_guarded_live_pilot_once.py"):
        if marker not in serialized_handoff:
            return fail(f"AI operator handoff response missing {marker}")
    audit_result = request_json("POST", "/api/ai-operator/chat", {"message": "/server-audit"})
    if '"action": "server_audit"' not in json.dumps(audit_result, ensure_ascii=False):
        return fail("AI operator server-audit command did not return server_audit action")
    runner_result = request_json(
        "POST",
        "/api/ai-operator/chat",
        {
            "message": (
                "/server-readiness-run --testnet --mode binance_testnet_place_order "
                "--allow-testnet-placement --skip-full-checks --skip-strategy-sweep "
                "--cycles 2 --interval 1 --timeout 120"
            )
        },
    )
    serialized_runner = json.dumps(runner_result, ensure_ascii=False)
    if '"action": "server_live_readiness_run"' not in serialized_runner:
        return fail("AI operator server-readiness-run command did not start the runner")
    for expected_fragment in [
        '"testnet_mode": "binance_testnet_place_order"',
        '"allow_testnet_placement": true',
        '"skip_full_checks": true',
        '"skip_strategy_sweep": true',
    ]:
        if expected_fragment not in serialized_runner:
            return fail(f"AI operator server-readiness-run did not preserve option {expected_fragment}")
    deadline = time.time() + 45
    runner_status: dict[str, object] = {}
    while time.time() < deadline:
        runner_payload = request_json("GET", "/api/server-live-readiness")
        candidate = runner_payload.get("server_live_readiness") or {}
        if isinstance(candidate, dict):
            runner_status = candidate
            if not candidate.get("running") and candidate.get("status") in {"completed", "failed"}:
                break
        time.sleep(0.75)
    if runner_status.get("status") != "completed":
        return fail("AI operator server-readiness-run dry-run did not complete")

    redaction_checked = False
    secret_value = "sk-test-redaction-abcdefghijklmnopqrstuvwxyz123456"
    binance_secret = "fake-binance-secret-abcdefghijklmnopqrstuvwxyz0123456789"
    if status.get("allow_file_write") and status.get("allow_file_read"):
        secret_fixture = (
            f"OPENAI_API_KEY={secret_value}\n"
            f"BINANCE_API_SECRET={binance_secret}\n"
            "NORMAL_VALUE=visible\n"
        )
        secret_write = request_json(
            "POST",
            "/api/ai-operator/chat",
            {"message": f"/write data/ai_operator_secret_smoke.env\n{secret_fixture}"},
        )
        serialized_write = json.dumps(secret_write, ensure_ascii=False)
        if secret_value in serialized_write or binance_secret in serialized_write:
            return fail("AI operator write response leaked secret content")
        secret_read = request_json(
            "POST",
            "/api/ai-operator/chat",
            {"message": "/read data/ai_operator_secret_smoke.env"},
        )
        serialized_read = json.dumps(secret_read, ensure_ascii=False)
        if secret_value in serialized_read or binance_secret in serialized_read:
            return fail("AI operator read response leaked secret content")
        if "[REDACTED:OPENAI_API_KEY" not in serialized_read or "[REDACTED:BINANCE_API_SECRET" not in serialized_read:
            return fail("AI operator read response did not show redacted secret markers")
        redaction_checked = True

    write_checked = False
    if status.get("allow_file_write"):
        content = "AI operator smoke check\n"
        write_result = request_json(
            "POST",
            "/api/ai-operator/chat",
            {"message": f"/write data/ai_operator_smoke.txt\n{content}"},
        )
        if "ai_operator_smoke.txt" not in json.dumps(write_result, ensure_ascii=False):
            return fail("AI operator write command did not report target file")
        read_result = request_json(
            "POST",
            "/api/ai-operator/chat",
            {"message": "/read data/ai_operator_smoke.txt"},
        )
        if content.strip() not in json.dumps(read_result, ensure_ascii=False):
            return fail("AI operator read command did not return written content")
        replace_result = request_json(
            "POST",
            "/api/ai-operator/chat",
            {
                "message": (
                    "/replace data/ai_operator_smoke.txt\n"
                    "AI operator smoke check\n"
                    "---\n"
                    "AI operator replace check"
                )
            },
        )
        if "replace" not in json.dumps(replace_result, ensure_ascii=False):
            return fail("AI operator replace command did not report a replace action")
        replaced_read = request_json(
            "POST",
            "/api/ai-operator/chat",
            {"message": "/read data/ai_operator_smoke.txt"},
        )
        if "AI operator replace check" not in json.dumps(replaced_read, ensure_ascii=False):
            return fail("AI operator replace command did not update the file")
        if status.get("snapshot_writes"):
            snapshot_path = find_first_snapshot_path(replace_result)
            if not snapshot_path:
                return fail("AI operator replace command did not create a pre-write snapshot")
            restore_result = request_json(
                "POST",
                "/api/ai-operator/chat",
                {"message": f"/restore {snapshot_path} data/ai_operator_smoke.txt"},
            )
            if "restore_snapshot" not in json.dumps(restore_result, ensure_ascii=False):
                return fail("AI operator restore command did not report restore_snapshot")
            restored_read = request_json(
                "POST",
                "/api/ai-operator/chat",
                {"message": "/read data/ai_operator_smoke.txt"},
            )
            if content.strip() not in json.dumps(restored_read, ensure_ascii=False):
                return fail("AI operator restore command did not restore snapshot content")
        patch_result = request_json(
            "POST",
            "/api/ai-operator/chat",
            {
                "message": (
                    "/patch\n"
                    "*** Begin Patch\n"
                    "*** Update File: data/ai_operator_smoke.txt\n"
                    "@@\n"
                    "-AI operator smoke check\n"
                    "+AI operator patch check\n"
                    "*** End Patch"
                )
            },
        )
        if "patch_update" not in json.dumps(patch_result, ensure_ascii=False):
            return fail("AI operator patch command did not report a patch_update action")
        patched_read = request_json(
            "POST",
            "/api/ai-operator/chat",
            {"message": "/read data/ai_operator_smoke.txt"},
        )
        if "AI operator patch check" not in json.dumps(patched_read, ensure_ascii=False):
            return fail("AI operator patch command did not update the file")
        write_checked = True

    shell_checked = False
    if status.get("allow_shell"):
        secret_shell = request_json(
            "POST",
            "/api/ai-operator/chat",
            {"message": f"/shell python -c \"print('OPENAI_API_KEY={secret_value}')\""},
        )
        serialized_secret_shell = json.dumps(secret_shell, ensure_ascii=False)
        if secret_value in serialized_secret_shell:
            return fail("AI operator shell response leaked secret content")
        if "[REDACTED:OPENAI_API_KEY" not in serialized_secret_shell:
            return fail("AI operator shell response did not redact secret content")
        shell_result = request_json(
            "POST",
            "/api/ai-operator/chat",
            {"message": "/shell echo ai-operator-shell-smoke"},
        )
        serialized = json.dumps(shell_result, ensure_ascii=False)
        if "ai-operator-shell-smoke" not in serialized:
            return fail("AI operator shell command did not return expected output")
        if '"returncode": 0' not in serialized:
            return fail("AI operator shell command did not report returncode 0")
        if status.get("backup_before_shell"):
            if "pre_shell_backup" not in serialized:
                return fail("AI operator shell command did not report a pre-shell backup")
            if '"created": true' not in serialized:
                return fail("AI operator pre-shell backup was not created")
        shell_checked = True

    print(
        json.dumps(
            {
                "ok": True,
                "enabled": status.get("enabled"),
                "allow_file_read": status.get("allow_file_read"),
                "allow_file_write": status.get("allow_file_write"),
                "allow_shell": status.get("allow_shell"),
                "apply_model_file_actions": status.get("apply_model_file_actions"),
                "snapshot_writes": status.get("snapshot_writes"),
                "backup_before_shell": status.get("backup_before_shell"),
                "redaction_checked": redaction_checked,
                "write_checked": write_checked,
                "shell_checked": shell_checked,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
