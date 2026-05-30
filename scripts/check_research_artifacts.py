from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
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
SYMBOL = os.getenv("TRADER_SYMBOL", "BTCUSDT")
HTTP_TIMEOUT_SECONDS = float(os.getenv("TRADER_HTTP_TIMEOUT_SECONDS", "20"))
RUN_TIMEOUT_SECONDS = float(os.getenv("TRADER_RUN_TIMEOUT_SECONDS", "60"))
AUTH_USER = os.getenv("TRADER_AUTH_USER", os.getenv("APP_BASIC_AUTH_USER", ""))
AUTH_PASSWORD = os.getenv("TRADER_AUTH_PASSWORD", os.getenv("APP_BASIC_AUTH_PASSWORD", ""))


def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    body = None
    headers = {"Accept": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def ensure_completed_run() -> dict[str, Any]:
    state = request_json("GET", "/api/state")
    latest = state.get("latest_run") or {}
    if latest.get("status") == "completed" and (state.get("research") or {}).get("status") == "ready":
        return state
    created = request_json("POST", "/api/runs", {"symbol": SYMBOL, "mode": "paper"})
    run_id = created.get("run_id") or (created.get("run") or {}).get("id")
    if not run_id:
        raise RuntimeError(f"run creation did not return id: {created!r}")
    deadline = time.time() + RUN_TIMEOUT_SECONDS
    while time.time() < deadline:
        state = request_json("GET", "/api/state")
        latest = state.get("latest_run") or {}
        if latest.get("id") == run_id and latest.get("status") in {"completed", "failed"}:
            return state
        time.sleep(1)
    raise TimeoutError(f"run {run_id} did not complete")


def main() -> int:
    try:
        state = ensure_completed_run()
        research = state.get("research") or {}
        if research.get("status") != "ready":
            return fail(f"research status is {research.get('status')!r}")

        protocol = research.get("protocol") or {}
        required_protocol = {"input_treatment", "exchange_format", "decision_memory", "human_review"}
        missing_protocol = sorted(required_protocol - set(protocol))
        if missing_protocol:
            return fail(f"missing research protocol keys: {missing_protocol}")

        guardrails = research.get("guardrails") or []
        if len(guardrails) < 4:
            return fail("research guardrails are incomplete")
        guardrail_text = " ".join(guardrails)
        for phrase in ["不执行交易", "没有来源", "结构化工件", "确定性风控"]:
            if phrase not in guardrail_text:
                return fail(f"missing guardrail phrase: {phrase}")

        artifacts = research.get("artifacts") or []
        required_ids = {
            "reference-architecture-map",
            "boundary",
            "market-research",
            "sentiment-news",
            "source-guardrails",
            "bull-bear-debate",
            "structured-intent",
            "risk-review",
            "decision-memory-checkpoint",
            "agent-runtime-plan",
            "research-limitations",
        }
        found_ids = {artifact.get("id") for artifact in artifacts}
        missing_ids = sorted(required_ids - found_ids)
        if missing_ids:
            return fail(f"missing research artifacts: {missing_ids}")

        structured = next(artifact for artifact in artifacts if artifact.get("id") == "structured-intent")
        if "TradeIntent" not in " ".join(structured.get("evidence") or []):
            return fail("structured-intent artifact does not prove TradeIntent structure")
        runtime = next(artifact for artifact in artifacts if artifact.get("id") == "agent-runtime-plan")
        runtime_text = " ".join([runtime.get("summary", ""), *runtime.get("gaps", [])])
        for phrase in ["独立上下文", "系统提示", "工具权限", "严格结构", "权限", "运行时回调", "钩子", "检查点", "遥测", "5 分钟", "提示词缓存"]:
            if phrase not in runtime_text:
                return fail(f"agent runtime contract is missing: {phrase}")
        architecture = next(artifact for artifact in artifacts if artifact.get("id") == "reference-architecture-map")
        architecture_text = " ".join([architecture.get("summary", ""), *architecture.get("evidence", [])])
        for phrase in ["Skills/Commands", "MCP", "人工签核", "分析师团队", "牛熊辩论", "模拟", "七类角色"]:
            if phrase not in architecture_text:
                return fail(f"reference architecture mapping is missing: {phrase}")
        source_guardrails = next(artifact for artifact in artifacts if artifact.get("id") == "source-guardrails")
        source_text = " ".join([source_guardrails.get("summary", ""), *source_guardrails.get("gaps", [])])
        for phrase in ["界定范围", "行业概览", "竞争分析", "可比分析", "想法生成", "第三方", "系统指令", "未接入", "UNSOURCED"]:
            if phrase not in source_text:
                return fail(f"source guardrail artifact is missing: {phrase}")
        debate = next(artifact for artifact in artifacts if artifact.get("id") == "bull-bear-debate")
        debate_text = debate.get("summary", "")
        for phrase in ["多头观点", "空头观点", "结构化工件"]:
            if phrase not in debate_text:
                return fail(f"bull/bear debate artifact is missing: {phrase}")
        memory = next(artifact for artifact in artifacts if artifact.get("id") == "decision-memory-checkpoint")
        memory_text = " ".join([memory.get("summary", ""), *memory.get("evidence", []), *memory.get("gaps", [])])
        for phrase in ["SQLite", "events", "order_transitions", "节点级"]:
            if phrase not in memory_text:
                return fail(f"decision memory/checkpoint artifact is missing: {phrase}")

        output = {
            "status": research.get("status"),
            "artifact_count": len(artifacts),
            "guardrail_count": len(guardrails),
            "latest_run_id": (state.get("latest_run") or {}).get("id"),
            "exchange_format": protocol.get("exchange_format"),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError, RuntimeError) as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
