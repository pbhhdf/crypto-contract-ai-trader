from __future__ import annotations

import base64
import asyncio
import importlib.util
import json
import hashlib
import hmac
import os
import random
import re
import smtplib
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
from email.message import EmailMessage
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

try:
    from app.live_env_profile import build_live_env_profile
    from app.live_launch_plan import build_live_launch_plan
    from app.live_ops_handoff import build_live_ops_handoff
except ModuleNotFoundError:  # Running as python app/server.py.
    from live_env_profile import build_live_env_profile
    from live_launch_plan import build_live_launch_plan
    from live_ops_handoff import build_live_ops_handoff


ROOT_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT_DIR / "app" / "static"
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "trader.db"


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


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}


def env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


HOST = os.getenv("APP_HOST", "127.0.0.1")
PORT = int(os.getenv("APP_PORT", "8787"))
APP_ENV = os.getenv("APP_ENV", "local").lower().strip()
MARKET_DATA_SOURCE = os.getenv("MARKET_DATA_SOURCE", "binance_public").lower()
BINANCE_FAPI_BASE = os.getenv("BINANCE_FAPI_BASE", "https://fapi.binance.com")
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "8"))
HTTP_RETRIES = int(os.getenv("HTTP_RETRIES", "2"))
AI_PROVIDER = os.getenv("AI_PROVIDER", "rules").lower().strip()
AI_MODEL = os.getenv("AI_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini")).strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
EXCHANGE_PROVIDER = os.getenv("EXCHANGE_PROVIDER", "binance").lower().strip()
EXCHANGE_MODE = os.getenv("EXCHANGE_MODE", "paper").lower().strip()
ENABLE_BINANCE_TESTNET = os.getenv("ENABLE_BINANCE_TESTNET", "false").lower() == "true"
BINANCE_TESTNET_FAPI_BASE = os.getenv(
    "BINANCE_TESTNET_FAPI_BASE",
    "https://testnet.binancefuture.com",
).rstrip("/")
BINANCE_TESTNET_WS_BASE = os.getenv(
    "BINANCE_TESTNET_WS_BASE",
    "wss://stream.binancefuture.com",
).rstrip("/")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "").strip()
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "").strip()
BINANCE_PLACE_TESTNET_ORDERS = os.getenv("BINANCE_PLACE_TESTNET_ORDERS", "false").lower() == "true"
BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER = env_bool("BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER", True)
BINANCE_TARGET_MARGIN_TYPE = os.getenv("BINANCE_TARGET_MARGIN_TYPE", "ISOLATED").upper().strip()
BINANCE_SYNC_LEVERAGE_BEFORE_ORDER = env_bool("BINANCE_SYNC_LEVERAGE_BEFORE_ORDER", True)
BINANCE_REQUIRE_ONE_WAY_POSITION_MODE = env_bool("BINANCE_REQUIRE_ONE_WAY_POSITION_MODE", True)
ENABLE_BINANCE_LIVE = env_bool("ENABLE_BINANCE_LIVE", False)
BINANCE_LIVE_FAPI_BASE = os.getenv("BINANCE_LIVE_FAPI_BASE", BINANCE_FAPI_BASE).rstrip("/")
BINANCE_LIVE_WS_BASE = os.getenv("BINANCE_LIVE_WS_BASE", "wss://fstream.binance.com/private").rstrip("/")
BINANCE_LIVE_API_KEY = os.getenv("BINANCE_LIVE_API_KEY", "").strip()
BINANCE_LIVE_API_SECRET = os.getenv("BINANCE_LIVE_API_SECRET", "").strip()
BINANCE_PLACE_LIVE_ORDERS = env_bool("BINANCE_PLACE_LIVE_ORDERS", False)
LIVE_TRADING_CONFIRMATION = os.getenv("LIVE_TRADING_CONFIRMATION", "").strip()
GO_LIVE_MIN_TESTNET_DRILL_CYCLES = env_int("GO_LIVE_MIN_TESTNET_DRILL_CYCLES", 24, 1, 100000)
GO_LIVE_REQUIRE_ALERT_WEBHOOK = env_bool("GO_LIVE_REQUIRE_ALERT_WEBHOOK", APP_ENV == "server")
GO_LIVE_REQUIRE_PRIVATE_STREAM = env_bool("GO_LIVE_REQUIRE_PRIVATE_STREAM", True)
GO_LIVE_MIN_WALKFORWARD_FOLDS = env_int("GO_LIVE_MIN_WALKFORWARD_FOLDS", 2, 1, 100)
GO_LIVE_MIN_WALKFORWARD_TOTAL_RETURN_PCT = env_float(
    "GO_LIVE_MIN_WALKFORWARD_TOTAL_RETURN_PCT",
    0.0,
    -100.0,
    100000.0,
)
GO_LIVE_MIN_WALKFORWARD_POSITIVE_FOLD_RATE_PCT = env_float(
    "GO_LIVE_MIN_WALKFORWARD_POSITIVE_FOLD_RATE_PCT",
    50.0,
    0.0,
    100.0,
)
GO_LIVE_MAX_WALKFORWARD_DRAWDOWN_PCT = env_float(
    "GO_LIVE_MAX_WALKFORWARD_DRAWDOWN_PCT",
    10.0,
    0.0,
    100.0,
)
LIVE_ARMING_MAX_SECONDS = env_int("LIVE_ARMING_MAX_SECONDS", 900, 60, 86400)
LIVE_ARMING_MAX_ORDERS = env_int("LIVE_ARMING_MAX_ORDERS", 1, 1, 1000)
LIVE_ATTESTATION_MAX_AGE_DAYS = env_int("LIVE_ATTESTATION_MAX_AGE_DAYS", 30, 1, 365)
LIVE_PILOT_MAX_WALLET_USDT = env_float("LIVE_PILOT_MAX_WALLET_USDT", 5000.0, 0.0, 1_000_000_000.0)
BINANCE_ENFORCE_EXCHANGE_FILTERS = env_bool("BINANCE_ENFORCE_EXCHANGE_FILTERS", True)
BINANCE_MAX_TIME_DRIFT_MS = env_int("BINANCE_MAX_TIME_DRIFT_MS", 1000, 50, 60_000)
PRIVATE_STREAM_STALE_SECONDS = env_int("PRIVATE_STREAM_STALE_SECONDS", 86400, 300, 604800)
EXCHANGE_RECOVERY_STALE_SECONDS = env_int("EXCHANGE_RECOVERY_STALE_SECONDS", 3600, 300, 86400)
EXCHANGE_ACCOUNT_SNAPSHOT_MAX_AGE_SECONDS = env_int("EXCHANGE_ACCOUNT_SNAPSHOT_MAX_AGE_SECONDS", 30, 1, 3600)
EXECUTION_MARKET_SNAPSHOT_MAX_AGE_SECONDS = env_int("EXECUTION_MARKET_SNAPSHOT_MAX_AGE_SECONDS", 60, 1, 3600)
ALERT_WEBHOOK_ENABLED = env_bool("ALERT_WEBHOOK_ENABLED", False)
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "").strip()
ALERT_WEBHOOK_SECRET = os.getenv("ALERT_WEBHOOK_SECRET", "").strip()
ALERT_WEBHOOK_MIN_SEVERITY = os.getenv("ALERT_WEBHOOK_MIN_SEVERITY", "warning").lower().strip()
ALERT_WEBHOOK_NOTIFY_RESOLVED = env_bool("ALERT_WEBHOOK_NOTIFY_RESOLVED", True)
ALERT_WEBHOOK_TIMEOUT_SECONDS = float(os.getenv("ALERT_WEBHOOK_TIMEOUT_SECONDS", "5"))
ALERT_TELEGRAM_ENABLED = env_bool("ALERT_TELEGRAM_ENABLED", False)
ALERT_TELEGRAM_BOT_TOKEN = os.getenv("ALERT_TELEGRAM_BOT_TOKEN", "").strip()
ALERT_TELEGRAM_CHAT_ID = os.getenv("ALERT_TELEGRAM_CHAT_ID", "").strip()
ALERT_TELEGRAM_API_BASE = os.getenv("ALERT_TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/")
ALERT_EMAIL_ENABLED = env_bool("ALERT_EMAIL_ENABLED", False)
ALERT_EMAIL_SMTP_HOST = os.getenv("ALERT_EMAIL_SMTP_HOST", "").strip()
ALERT_EMAIL_SMTP_PORT = env_int("ALERT_EMAIL_SMTP_PORT", 587, 1, 65535)
ALERT_EMAIL_SMTP_USERNAME = os.getenv("ALERT_EMAIL_SMTP_USERNAME", "").strip()
ALERT_EMAIL_SMTP_PASSWORD = os.getenv("ALERT_EMAIL_SMTP_PASSWORD", "").strip()
ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM", "").strip()
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "").strip()
ALERT_EMAIL_USE_TLS = env_bool("ALERT_EMAIL_USE_TLS", False)
ALERT_EMAIL_STARTTLS = env_bool("ALERT_EMAIL_STARTTLS", True)
MAX_LEVERAGE = float(os.getenv("MAX_LEVERAGE", "3"))
MAX_POSITION_PCT = float(os.getenv("MAX_POSITION_PCT", "0.05"))
MAX_ORDER_NOTIONAL_USDT = float(os.getenv("MAX_ORDER_NOTIONAL_USDT", "1000"))
MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "0.03"))
MAX_CONSECUTIVE_LOSSES = int(float(os.getenv("MAX_CONSECUTIVE_LOSSES", "3")))
MAX_OPEN_POSITIONS = int(float(os.getenv("MAX_OPEN_POSITIONS", "8")))
ALLOWED_SYMBOLS = os.getenv("ALLOWED_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT")
ACCOUNT_EQUITY_USDT = float(os.getenv("ACCOUNT_EQUITY_USDT", "10000"))
APP_BASIC_AUTH_USER = os.getenv("APP_BASIC_AUTH_USER", "").strip()
APP_BASIC_AUTH_PASSWORD = os.getenv("APP_BASIC_AUTH_PASSWORD", "").strip()
AUTH_ENABLED = bool(APP_BASIC_AUTH_USER and APP_BASIC_AUTH_PASSWORD)
TRADER_BIND_IP = os.getenv("TRADER_BIND_IP", "127.0.0.1").strip()
AI_OPERATOR_ENABLED = env_bool("AI_OPERATOR_ENABLED", True)
AI_OPERATOR_PROVIDER = os.getenv("AI_OPERATOR_PROVIDER", AI_PROVIDER).lower().strip()
AI_OPERATOR_MODEL = os.getenv("AI_OPERATOR_MODEL", AI_MODEL).strip()
AI_OPERATOR_ALLOW_FILE_READ = env_bool("AI_OPERATOR_ALLOW_FILE_READ", True)
AI_OPERATOR_ALLOW_FILE_WRITE = env_bool("AI_OPERATOR_ALLOW_FILE_WRITE", APP_ENV == "local")
AI_OPERATOR_ALLOW_SHELL = env_bool("AI_OPERATOR_ALLOW_SHELL", APP_ENV == "local")
AI_OPERATOR_APPLY_MODEL_FILE_ACTIONS = env_bool(
    "AI_OPERATOR_APPLY_MODEL_FILE_ACTIONS",
    AI_OPERATOR_ALLOW_FILE_WRITE and AI_OPERATOR_ALLOW_SHELL,
)
AI_OPERATOR_MAX_READ_BYTES = env_int("AI_OPERATOR_MAX_READ_BYTES", 80_000, 1_024, 2_000_000)
AI_OPERATOR_MAX_WRITE_BYTES = env_int("AI_OPERATOR_MAX_WRITE_BYTES", 200_000, 1_024, 5_000_000)
AI_OPERATOR_MAX_SHELL_OUTPUT_BYTES = env_int("AI_OPERATOR_MAX_SHELL_OUTPUT_BYTES", 120_000, 1_024, 2_000_000)
AI_OPERATOR_SHELL_TIMEOUT_SECONDS = env_int("AI_OPERATOR_SHELL_TIMEOUT_SECONDS", 30, 1, 600)
AI_OPERATOR_SNAPSHOT_WRITES = env_bool("AI_OPERATOR_SNAPSHOT_WRITES", True)
AI_OPERATOR_MAX_SNAPSHOT_BYTES = env_int("AI_OPERATOR_MAX_SNAPSHOT_BYTES", 5_000_000, 1_024, 50_000_000)
AI_OPERATOR_BACKUP_BEFORE_SHELL = env_bool("AI_OPERATOR_BACKUP_BEFORE_SHELL", True)
AI_OPERATOR_SHELL_BACKUP_TIMEOUT_SECONDS = env_int("AI_OPERATOR_SHELL_BACKUP_TIMEOUT_SECONDS", 45, 5, 600)
_AI_OPERATOR_WORKSPACE_RAW = Path(os.getenv("AI_OPERATOR_WORKSPACE_ROOT", str(ROOT_DIR))).expanduser()
AI_OPERATOR_WORKSPACE_ROOT = (
    _AI_OPERATOR_WORKSPACE_RAW
    if _AI_OPERATOR_WORKSPACE_RAW.is_absolute()
    else ROOT_DIR / _AI_OPERATOR_WORKSPACE_RAW
).resolve()
_AI_OPERATOR_SNAPSHOT_DIR_RAW = Path(os.getenv("AI_OPERATOR_SNAPSHOT_DIR", "data/ai_operator_snapshots")).expanduser()
AI_OPERATOR_SNAPSHOT_DIR = (
    _AI_OPERATOR_SNAPSHOT_DIR_RAW
    if _AI_OPERATOR_SNAPSHOT_DIR_RAW.is_absolute()
    else ROOT_DIR / _AI_OPERATOR_SNAPSHOT_DIR_RAW
).resolve()
_AI_OPERATOR_SHELL_BACKUP_DIR_RAW = Path(
    os.getenv("AI_OPERATOR_SHELL_BACKUP_DIR", "reports/ai_operator_backups")
).expanduser()
AI_OPERATOR_SHELL_BACKUP_DIR = (
    _AI_OPERATOR_SHELL_BACKUP_DIR_RAW
    if _AI_OPERATOR_SHELL_BACKUP_DIR_RAW.is_absolute()
    else ROOT_DIR / _AI_OPERATOR_SHELL_BACKUP_DIR_RAW
).resolve()
AI_OPERATOR_SENSITIVE_KEY_RE = re.compile(
    r"(SECRET|PASSWORD|TOKEN|API[_-]?KEY|PRIVATE[_-]?KEY|WEBHOOK[_-]?URL|CHAT[_-]?ID)",
    re.IGNORECASE,
)
AI_OPERATOR_ENV_ASSIGNMENT_RE = re.compile(
    r"(?m)^(\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*)(.*)$"
)
AI_OPERATOR_JSON_SECRET_RE = re.compile(
    r'("([^"]*(?:secret|password|token|api[_-]?key|private[_-]?key|webhook[_-]?url|chat[_-]?id)[^"]*)"\s*:\s*)"([^"]*)"',
    re.IGNORECASE,
)
_SERVER_BUNDLE_OUTPUT_DIR_RAW = Path(os.getenv("SERVER_BUNDLE_OUTPUT_DIR", "reports/server-bundles")).expanduser()
SERVER_BUNDLE_OUTPUT_DIR = (
    _SERVER_BUNDLE_OUTPUT_DIR_RAW
    if _SERVER_BUNDLE_OUTPUT_DIR_RAW.is_absolute()
    else ROOT_DIR / _SERVER_BUNDLE_OUTPUT_DIR_RAW
).resolve()
_LIVE_LAUNCH_KIT_OUTPUT_DIR_RAW = Path(os.getenv("LIVE_LAUNCH_KIT_OUTPUT_DIR", "reports/live-launch-kits")).expanduser()
LIVE_LAUNCH_KIT_OUTPUT_DIR = (
    _LIVE_LAUNCH_KIT_OUTPUT_DIR_RAW
    if _LIVE_LAUNCH_KIT_OUTPUT_DIR_RAW.is_absolute()
    else ROOT_DIR / _LIVE_LAUNCH_KIT_OUTPUT_DIR_RAW
).resolve()
_LIVE_ENV_PACK_OUTPUT_DIR_RAW = Path(os.getenv("LIVE_ENV_PACK_OUTPUT_DIR", "reports/live-env-packs")).expanduser()
LIVE_ENV_PACK_OUTPUT_DIR = (
    _LIVE_ENV_PACK_OUTPUT_DIR_RAW
    if _LIVE_ENV_PACK_OUTPUT_DIR_RAW.is_absolute()
    else ROOT_DIR / _LIVE_ENV_PACK_OUTPUT_DIR_RAW
).resolve()

DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_LOCK = threading.Lock()
RUN_LOCK = threading.Lock()
ACTIVE_RUNS: set[str] = set()
STATEFUL_EXCHANGE_ORDER_MODES = {"binance_testnet_place_order", "live_guarded"}
SCHEDULER_STOP = threading.Event()
TESTNET_DRILL_STOP = threading.Event()
USER_STREAM_LOCK = threading.Lock()
USER_STREAM_STOP = threading.Event()
USER_STREAM_THREAD: threading.Thread | None = None
SERVER_LIVE_READINESS_LOCK = threading.Lock()
SERVER_LIVE_READINESS_THREAD: threading.Thread | None = None
BINANCE_SYMBOL_RULES_CACHE: dict[tuple[str, str], dict[str, Any]] = {}
BINANCE_SYMBOL_RULES_LOCK = threading.Lock()

RECONCILED_ORDER_STATUSES = {
    "paper_filled",
    "testnet_validated",
    "testnet_submitted",
    "testnet_filled",
    "testnet_canceled",
    "testnet_protection_submitted",
    "testnet_protection_canceled",
    "live_submitted",
    "live_protection_submitted",
    "live_protection_canceled",
    "closed",
}
NEEDS_RECONCILE_STATUSES = {
    "prepared",
    "submitted",
    "testnet_submitted",
    "testnet_protection_submitted",
    "live_submitted",
    "live_protection_submitted",
    "pending_reconcile",
    "unknown",
}
CANCELABLE_BINANCE_ORDER_STATUSES = {
    "testnet_submitted",
    "testnet_protection_submitted",
    "live_submitted",
    "live_protection_submitted",
    "pending_reconcile",
}
LIVE_ATTESTATION_REQUIREMENTS = [
    {
        "id": "withdrawal_disabled",
        "label": "Binance live API key 已关闭提现权限",
        "detail": "该项无法由交易 API 自动确认，必须在 Binance API 管理页人工核验。",
    },
    {
        "id": "ip_whitelisted",
        "label": "Binance live API key 已绑定服务器公网出口 IP",
        "detail": "首阶段只允许服务器出口 IP 调用交易权限 key，避免密钥泄露后被异地滥用。",
    },
    {
        "id": "jurisdiction_ok",
        "label": "所在地区与交易所条款允许当前合约交易用途",
        "detail": "该项属于运营与合规前置条件，系统只记录确认，不替代法律意见。",
    },
    {
        "id": "offserver_backup_copied",
        "label": "最新备份与 go-live 报告已复制到服务器外部",
        "detail": "进入实盘前必须有离线/异机证据，避免服务器损坏时无法恢复与复盘。",
    },
    {
        "id": "pilot_capital_limit_ok",
        "label": "小额试运行资金与单笔名义上限已人工确认",
        "detail": "实盘首阶段只能用受限资金和受限单笔额度验证链路，不用于放大风险。",
    },
]


class ProtectionFailureGuarded(RuntimeError):
    """Raised after a submitted entry order has been put into protection-failure guard handling."""



def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def seconds_from_now(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec="seconds")


def seconds_since(value: str | None) -> float | None:
    parsed = parse_iso_datetime(value)
    if not parsed:
        return None
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds())


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_order_columns(conn: sqlite3.Connection) -> None:
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(orders)").fetchall()
    }
    columns = {
        "client_order_id": "TEXT",
        "venue_order_id": "TEXT",
        "venue_status": "TEXT",
        "reconcile_status": "TEXT NOT NULL DEFAULT 'unchecked'",
        "reconcile_note": "TEXT NOT NULL DEFAULT ''",
        "last_reconciled_at": "TEXT",
        "updated_at": "TEXT",
        "parent_order_id": "TEXT",
        "protection_kind": "TEXT",
    }
    for name, ddl in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE orders ADD COLUMN {name} {ddl}")
    conn.execute("UPDATE orders SET client_order_id = id WHERE client_order_id IS NULL OR client_order_id = ''")
    conn.execute("UPDATE orders SET updated_at = created_at WHERE updated_at IS NULL OR updated_at = ''")
    conn.execute("UPDATE orders SET venue_status = UPPER(status) WHERE venue_status IS NULL OR venue_status = ''")


def init_db() -> None:
    with DB_LOCK, connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                decision TEXT,
                final_action TEXT,
                risk_status TEXT
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                ts TEXT NOT NULL,
                kind TEXT NOT NULL,
                actor TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                payload TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL,
                quantity REAL NOT NULL,
                leverage REAL NOT NULL,
                entry_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS order_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                ts TEXT NOT NULL,
                from_status TEXT,
                to_status TEXT NOT NULL,
                reason TEXT NOT NULL,
                payload TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS positions (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                order_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                leverage REAL NOT NULL,
                entry_price REAL NOT NULL,
                mark_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                status TEXT NOT NULL,
                opened_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                closed_at TEXT,
                exit_price REAL,
                realized_pnl REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS backtest_runs (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                interval TEXT NOT NULL,
                bars INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                params TEXT NOT NULL DEFAULT '{}',
                metrics TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS backtest_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                opened_at TEXT NOT NULL,
                closed_at TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                quantity REAL NOT NULL,
                leverage REAL NOT NULL,
                pnl_usdt REAL NOT NULL,
                return_pct REAL NOT NULL,
                reason TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ai_operator_messages (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL,
                actions TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS exchange_account_snapshots (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                mode TEXT NOT NULL,
                account TEXT NOT NULL DEFAULT '{}',
                positions TEXT NOT NULL DEFAULT '[]',
                summary TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS exchange_stream_events (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                mode TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_time INTEGER,
                transaction_time INTEGER,
                symbol TEXT,
                client_order_id TEXT,
                venue_order_id TEXT,
                payload TEXT NOT NULL DEFAULT '{}',
                processed TEXT NOT NULL DEFAULT 'false',
                note TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                key TEXT NOT NULL UNIQUE,
                ts TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                payload TEXT NOT NULL DEFAULT '{}',
                acknowledged_at TEXT,
                resolved_at TEXT
            );

            CREATE TABLE IF NOT EXISTS alert_deliveries (
                id TEXT PRIMARY KEY,
                alert_id TEXT NOT NULL,
                ts TEXT NOT NULL,
                channel TEXT NOT NULL,
                transition TEXT NOT NULL,
                status TEXT NOT NULL,
                target TEXT NOT NULL,
                status_code INTEGER,
                error TEXT NOT NULL DEFAULT '',
                payload TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS testnet_drill_cycles (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                completed_at TEXT,
                mode TEXT NOT NULL,
                symbol TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL,
                run_id TEXT,
                order_id TEXT,
                recovery_report TEXT NOT NULL DEFAULT '{}',
                alert_summary TEXT NOT NULL DEFAULT '{}',
                stream_summary TEXT NOT NULL DEFAULT '{}',
                note TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS audit_chain (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                stream TEXT NOT NULL,
                ref_id TEXT NOT NULL,
                action TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                row_hash TEXT NOT NULL,
                payload TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_audit_chain_stream_ref
                ON audit_chain(stream, ref_id);
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES('emergency_stop', 'false')"
        )
        defaults = {
            "scheduler_enabled": "false",
            "scheduler_symbol": "BTCUSDT",
            "scheduler_mode": "paper",
            "scheduler_interval_seconds": "900",
            "scheduler_last_run_at": "",
            "scheduler_next_run_at": "",
            "scheduler_last_run_id": "",
            "scheduler_last_error": "",
            "risk_max_leverage": str(MAX_LEVERAGE),
            "risk_max_position_pct": str(MAX_POSITION_PCT),
            "risk_max_order_notional_usdt": str(MAX_ORDER_NOTIONAL_USDT),
            "risk_max_daily_loss_pct": str(MAX_DAILY_LOSS_PCT),
            "risk_max_open_positions": str(MAX_OPEN_POSITIONS),
            "risk_max_consecutive_losses": str(MAX_CONSECUTIVE_LOSSES),
            "risk_allowed_symbols": ALLOWED_SYMBOLS,
            "exchange_recovery_last_at": "",
            "exchange_recovery_last_report": "{}",
            "binance_user_stream_mode": "",
            "binance_user_stream_listen_key": "",
            "binance_user_stream_status": "stopped",
            "binance_user_stream_started_at": "",
            "binance_user_stream_keepalive_at": "",
            "binance_user_stream_expires_at": "",
            "binance_user_stream_last_error": "",
            "binance_user_stream_connected": "false",
            "binance_user_stream_consumer_started_at": "",
            "binance_user_stream_last_event_at": "",
            "binance_user_stream_last_event_type": "",
            "binance_user_stream_event_count": "0",
            "testnet_drill_enabled": "false",
            "testnet_drill_symbol": "BTCUSDT",
            "testnet_drill_mode": "binance_testnet_validate",
            "testnet_drill_interval_seconds": "1800",
            "testnet_drill_target_cycles": "24",
            "testnet_drill_completed_cycles": "0",
            "testnet_drill_real_completed_cycles": "0",
            "testnet_drill_last_real_cycle_at": "",
            "testnet_drill_last_real_cycle_id": "",
            "testnet_drill_started_at": "",
            "testnet_drill_last_cycle_at": "",
            "testnet_drill_next_cycle_at": "",
            "testnet_drill_last_cycle_id": "",
            "testnet_drill_last_error": "",
            "server_live_readiness_status": "idle",
            "server_live_readiness_run_id": "",
            "server_live_readiness_started_at": "",
            "server_live_readiness_completed_at": "",
            "server_live_readiness_last_error": "",
            "server_live_readiness_last_summary": "{}",
            "server_live_readiness_last_report_path": "",
            "server_live_readiness_last_options": "{}",
            "live_armed_at": "",
            "live_armed_until": "",
            "live_armed_by": "",
            "live_armed_reason": "",
            "live_armed_order_count": "0",
            "live_armed_order_ids": "[]",
            "live_disarmed_at": "",
            "live_disarm_reason": "",
            "live_startup_disarm_last_at": "",
            "live_startup_disarm_last_report": "{}",
            "live_attestation": "{}",
        }
        conn.executemany(
            "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
            list(defaults.items()),
        )
        ensure_order_columns(conn)
        conn.commit()


def get_setting(key: str, default: str = "") -> str:
    with DB_LOCK, connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with DB_LOCK, connect() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()


def raise_alert(
    key: str,
    severity: str,
    source: str,
    title: str,
    body: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = utc_now()
    clean_severity = severity if severity in {"critical", "warning", "info"} else "warning"
    should_deliver = False
    with DB_LOCK, connect() as conn:
        existing = conn.execute("SELECT * FROM alerts WHERE key = ?", (key,)).fetchone()
        if existing:
            current_status = existing["status"]
            status = "open" if current_status == "resolved" else current_status
            acknowledged_at = None if current_status == "resolved" else existing["acknowledged_at"]
            should_deliver = current_status == "resolved"
            conn.execute(
                """
                UPDATE alerts
                SET updated_at = ?,
                    severity = ?,
                    status = ?,
                    source = ?,
                    title = ?,
                    body = ?,
                    payload = ?,
                    acknowledged_at = ?,
                    resolved_at = NULL
                WHERE key = ?
                """,
                (
                    now,
                    clean_severity,
                    status,
                    source,
                    title,
                    body,
                    json.dumps(payload or {}, ensure_ascii=False),
                    acknowledged_at,
                    key,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO alerts(id, key, ts, updated_at, severity, status, source, title, body, payload)
                VALUES(?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)
                """,
                (
                    f"ALT-{str(uuid.uuid4())[:10].upper()}",
                    key,
                    now,
                    now,
                    clean_severity,
                    source,
                    title,
                    body,
                    json.dumps(payload or {}, ensure_ascii=False),
                ),
            )
            should_deliver = True
        conn.commit()
        row = conn.execute("SELECT * FROM alerts WHERE key = ?", (key,)).fetchone()
    alert = alert_from_row(row)
    if should_deliver:
        deliver_alert(alert, "opened")
    return alert


def resolve_alert(key: str, note: str = "") -> dict[str, Any] | None:
    now = utc_now()
    should_deliver = False
    with DB_LOCK, connect() as conn:
        row = conn.execute("SELECT * FROM alerts WHERE key = ?", (key,)).fetchone()
        if not row:
            return None
        if row["status"] != "resolved":
            should_deliver = True
            body = f"{row['body']} | 已恢复：{note}" if note else row["body"]
            conn.execute(
                """
                UPDATE alerts
                SET status = 'resolved',
                    updated_at = ?,
                    resolved_at = ?,
                    body = ?
                WHERE key = ?
                """,
                (now, now, body, key),
            )
            conn.commit()
        row = conn.execute("SELECT * FROM alerts WHERE key = ?", (key,)).fetchone()
    alert = alert_from_row(row)
    if alert and should_deliver and ALERT_WEBHOOK_NOTIFY_RESOLVED:
        deliver_alert(alert, "resolved")
    return alert


def acknowledge_alert(alert_id: str) -> dict[str, Any]:
    now = utc_now()
    with DB_LOCK, connect() as conn:
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        if not row:
            raise ValueError(f"Alert {alert_id} was not found")
        if row["status"] == "open":
            conn.execute(
                """
                UPDATE alerts
                SET status = 'acknowledged',
                    updated_at = ?,
                    acknowledged_at = ?
                WHERE id = ?
                """,
                (now, now, alert_id),
            )
            conn.commit()
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
    return alert_from_row(row)


def resolve_alert_by_id(alert_id: str) -> dict[str, Any]:
    with DB_LOCK, connect() as conn:
        row = conn.execute("SELECT key FROM alerts WHERE id = ?", (alert_id,)).fetchone()
    if not row:
        raise ValueError(f"Alert {alert_id} was not found")
    resolved = resolve_alert(row["key"], "手动解决")
    if not resolved:
        raise ValueError(f"Alert {alert_id} was not found")
    return resolved


def alert_from_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if not row:
        return {}
    item = dict(row)
    item["payload"] = json.loads(item.get("payload") or "{}")
    return item


def alert_severity_rank(severity: str | None) -> int:
    return {"info": 0, "warning": 1, "critical": 2}.get(str(severity or "").lower(), 1)


def alert_delivery_target() -> str:
    if not ALERT_WEBHOOK_URL:
        return ""
    if "://" not in ALERT_WEBHOOK_URL:
        return mask_secret(ALERT_WEBHOOK_URL)
    scheme, rest = ALERT_WEBHOOK_URL.split("://", 1)
    host = rest.split("/", 1)[0]
    return f"{scheme}://{host}/..."


def alert_email_recipients() -> list[str]:
    return [item.strip() for item in ALERT_EMAIL_TO.replace(";", ",").split(",") if item.strip()]


def alert_delivery_channels() -> list[dict[str, Any]]:
    telegram_target = f"telegram:{mask_secret(ALERT_TELEGRAM_CHAT_ID)}" if ALERT_TELEGRAM_CHAT_ID else ""
    email_recipients = alert_email_recipients()
    email_target = f"email:{len(email_recipients)} recipient(s)" if email_recipients else ""
    return [
        {
            "channel": "webhook",
            "enabled": ALERT_WEBHOOK_ENABLED,
            "configured": bool(ALERT_WEBHOOK_URL),
            "target": alert_delivery_target(),
        },
        {
            "channel": "telegram",
            "enabled": ALERT_TELEGRAM_ENABLED,
            "configured": bool(ALERT_TELEGRAM_BOT_TOKEN and ALERT_TELEGRAM_CHAT_ID),
            "target": telegram_target,
        },
        {
            "channel": "email",
            "enabled": ALERT_EMAIL_ENABLED,
            "configured": bool(ALERT_EMAIL_SMTP_HOST and ALERT_EMAIL_FROM and email_recipients),
            "target": email_target,
        },
    ]


def alert_delivery_config() -> dict[str, Any]:
    channels = alert_delivery_channels()
    any_ready = any(channel["enabled"] and channel["configured"] for channel in channels)
    return {
        "webhook_enabled": ALERT_WEBHOOK_ENABLED,
        "webhook_configured": bool(ALERT_WEBHOOK_URL),
        "webhook_target": alert_delivery_target(),
        "telegram_enabled": ALERT_TELEGRAM_ENABLED,
        "telegram_configured": bool(ALERT_TELEGRAM_BOT_TOKEN and ALERT_TELEGRAM_CHAT_ID),
        "telegram_target": next((item["target"] for item in channels if item["channel"] == "telegram"), ""),
        "email_enabled": ALERT_EMAIL_ENABLED,
        "email_configured": bool(ALERT_EMAIL_SMTP_HOST and ALERT_EMAIL_FROM and alert_email_recipients()),
        "email_target": next((item["target"] for item in channels if item["channel"] == "email"), ""),
        "channels": channels,
        "any_channel_ready": any_ready,
        "min_severity": ALERT_WEBHOOK_MIN_SEVERITY,
        "notify_resolved": ALERT_WEBHOOK_NOTIFY_RESOLVED,
        "timeout_seconds": ALERT_WEBHOOK_TIMEOUT_SECONDS,
        "secret_configured": bool(ALERT_WEBHOOK_SECRET),
    }


def should_send_alert_delivery(alert: dict[str, Any], transition: str, channel: dict[str, Any]) -> bool:
    if transition == "test":
        return bool(channel.get("enabled") and channel.get("configured"))
    if not (channel.get("enabled") and channel.get("configured")):
        return False
    if transition == "resolved" and not ALERT_WEBHOOK_NOTIFY_RESOLVED:
        return False
    return alert_severity_rank(alert.get("severity")) >= alert_severity_rank(ALERT_WEBHOOK_MIN_SEVERITY)


def record_alert_delivery(
    alert: dict[str, Any],
    transition: str,
    status: str,
    target: str,
    payload: dict[str, Any],
    status_code: int | None = None,
    error: str = "",
    channel: str = "webhook",
) -> dict[str, Any]:
    delivery = {
        "id": f"ADL-{str(uuid.uuid4())[:10].upper()}",
        "alert_id": alert.get("id") or "test",
        "ts": utc_now(),
        "channel": channel,
        "transition": transition,
        "status": status,
        "target": target,
        "status_code": status_code,
        "error": error,
        "payload": payload,
    }
    with DB_LOCK, connect() as conn:
        conn.execute(
            """
            INSERT INTO alert_deliveries(
                id, alert_id, ts, channel, transition, status, target,
                status_code, error, payload
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                delivery["id"],
                delivery["alert_id"],
                delivery["ts"],
                delivery["channel"],
                delivery["transition"],
                delivery["status"],
                delivery["target"],
                delivery["status_code"],
                delivery["error"],
                json.dumps(delivery["payload"], ensure_ascii=False),
            ),
        )
        conn.commit()
    return delivery


def alert_delivery_payload(alert: dict[str, Any], transition: str) -> dict[str, Any]:
    return {
        "app": "crypto-contract-ai-trader",
        "environment": APP_ENV,
        "transition": transition,
        "sent_at": utc_now(),
        "alert": {
            "id": alert.get("id"),
            "key": alert.get("key"),
            "severity": alert.get("severity"),
            "status": alert.get("status"),
            "source": alert.get("source"),
            "title": alert.get("title"),
            "body": alert.get("body"),
            "ts": alert.get("ts"),
            "updated_at": alert.get("updated_at"),
            "payload": alert.get("payload") or {},
        },
    }


def deliver_webhook_alert(alert: dict[str, Any], transition: str, payload: dict[str, Any], target: str) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "crypto-contract-ai-trader-alerts/0.1",
    }
    if ALERT_WEBHOOK_SECRET:
        signature = hmac.new(ALERT_WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
        headers["X-Trader-Alert-Signature"] = f"sha256={signature}"
    request = Request(ALERT_WEBHOOK_URL, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=ALERT_WEBHOOK_TIMEOUT_SECONDS) as response:
            response.read()
            status_code = response.status
        return record_alert_delivery(alert, transition, "sent", target, payload, status_code=status_code, channel="webhook")
    except HTTPError as exc:
        return record_alert_delivery(
            alert,
            transition,
            "failed",
            target,
            payload,
            status_code=exc.code,
            error=exc.read().decode("utf-8", errors="replace")[:500],
            channel="webhook",
        )
    except Exception as exc:
        return record_alert_delivery(
            alert,
            transition,
            "failed",
            target,
            payload,
            error=f"{exc.__class__.__name__}: {exc}",
            channel="webhook",
        )


def alert_plain_text(alert: dict[str, Any], transition: str) -> str:
    return "\n".join(
        [
            f"[{APP_ENV}] {transition.upper()} {str(alert.get('severity') or '').upper()}",
            str(alert.get("title") or ""),
            str(alert.get("body") or ""),
            f"source={alert.get('source') or '-'} key={alert.get('key') or '-'} id={alert.get('id') or '-'}",
            f"updated_at={alert.get('updated_at') or alert.get('ts') or utc_now()}",
        ]
    ).strip()


def deliver_telegram_alert(alert: dict[str, Any], transition: str, payload: dict[str, Any], target: str) -> dict[str, Any]:
    body = json.dumps(
        {
            "chat_id": ALERT_TELEGRAM_CHAT_ID,
            "text": alert_plain_text(alert, transition),
            "disable_web_page_preview": True,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        f"{ALERT_TELEGRAM_API_BASE}/bot{ALERT_TELEGRAM_BOT_TOKEN}/sendMessage",
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "crypto-contract-ai-trader-alerts/0.1",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=ALERT_WEBHOOK_TIMEOUT_SECONDS) as response:
            response.read()
            status_code = response.status
        return record_alert_delivery(alert, transition, "sent", target, payload, status_code=status_code, channel="telegram")
    except HTTPError as exc:
        return record_alert_delivery(
            alert,
            transition,
            "failed",
            target,
            payload,
            status_code=exc.code,
            error=exc.read().decode("utf-8", errors="replace")[:500],
            channel="telegram",
        )
    except Exception as exc:
        return record_alert_delivery(
            alert,
            transition,
            "failed",
            target,
            payload,
            error=f"{exc.__class__.__name__}: {exc}",
            channel="telegram",
        )


def deliver_email_alert(alert: dict[str, Any], transition: str, payload: dict[str, Any], target: str) -> dict[str, Any]:
    message = EmailMessage()
    severity = str(alert.get("severity") or "warning").upper()
    message["Subject"] = f"[{APP_ENV}] {severity} {transition}: {alert.get('title') or 'Trader alert'}"
    message["From"] = ALERT_EMAIL_FROM
    message["To"] = ", ".join(alert_email_recipients())
    message.set_content(alert_plain_text(alert, transition) + "\n\n" + json.dumps(payload, ensure_ascii=False, indent=2))
    try:
        smtp_cls = smtplib.SMTP_SSL if ALERT_EMAIL_USE_TLS else smtplib.SMTP
        with smtp_cls(ALERT_EMAIL_SMTP_HOST, ALERT_EMAIL_SMTP_PORT, timeout=ALERT_WEBHOOK_TIMEOUT_SECONDS) as smtp:
            if ALERT_EMAIL_STARTTLS and not ALERT_EMAIL_USE_TLS:
                smtp.starttls()
            if ALERT_EMAIL_SMTP_USERNAME or ALERT_EMAIL_SMTP_PASSWORD:
                smtp.login(ALERT_EMAIL_SMTP_USERNAME, ALERT_EMAIL_SMTP_PASSWORD)
            smtp.send_message(message)
        return record_alert_delivery(alert, transition, "sent", target, payload, status_code=250, channel="email")
    except Exception as exc:
        return record_alert_delivery(
            alert,
            transition,
            "failed",
            target,
            payload,
            error=f"{exc.__class__.__name__}: {exc}",
            channel="email",
        )


def deliver_alert_channel(alert: dict[str, Any], transition: str, payload: dict[str, Any], channel: dict[str, Any]) -> dict[str, Any]:
    name = str(channel.get("channel") or "")
    target = str(channel.get("target") or "")
    if not should_send_alert_delivery(alert, transition, channel):
        return record_alert_delivery(
            alert,
            transition,
            "skipped",
            target,
            payload,
            error=f"{name or 'channel'} is disabled or not configured.",
            channel=name or "unknown",
        )
    if name == "webhook":
        return deliver_webhook_alert(alert, transition, payload, target)
    if name == "telegram":
        return deliver_telegram_alert(alert, transition, payload, target)
    if name == "email":
        return deliver_email_alert(alert, transition, payload, target)
    return record_alert_delivery(alert, transition, "skipped", target, payload, error="Unknown alert channel.", channel=name or "unknown")


def deliver_alert(alert: dict[str, Any], transition: str) -> dict[str, Any] | None:
    payload = alert_delivery_payload(alert, transition)
    channels = alert_delivery_channels()
    if transition != "test" and not any(should_send_alert_delivery(alert, transition, channel) for channel in channels):
        return None
    deliveries = [
        deliver_alert_channel(alert, transition, payload, channel)
        for channel in channels
        if transition == "test" or should_send_alert_delivery(alert, transition, channel)
    ]
    if not deliveries:
        return None
    if len(deliveries) == 1:
        return deliveries[0]
    sent_count = sum(1 for item in deliveries if item.get("status") == "sent")
    return {
        "id": f"ADL-MULTI-{str(uuid.uuid4())[:8].upper()}",
        "alert_id": alert.get("id") or "test",
        "ts": utc_now(),
        "channel": "multi",
        "transition": transition,
        "status": "sent" if sent_count else "failed",
        "target": ", ".join(item.get("target") or item.get("channel") or "-" for item in deliveries),
        "status_code": None,
        "error": "" if sent_count else "No alert channel delivered successfully.",
        "payload": payload,
        "deliveries": deliveries,
    }


def send_test_alert_delivery() -> dict[str, Any]:
    alert = {
        "id": "test",
        "key": "alert.delivery_test",
        "severity": "info",
        "status": "open",
        "source": "Alert Delivery",
        "title": "告警通知测试",
        "body": "这是一条来自加密合约交易系统的外部告警通道测试通知。",
        "ts": utc_now(),
        "updated_at": utc_now(),
        "payload": {"test": True},
    }
    delivery = deliver_alert(alert, "test")
    return {
        "config": alert_delivery_config(),
        "delivery": delivery,
        "deliveries": (delivery or {}).get("deliveries") if isinstance(delivery, dict) and delivery.get("deliveries") else ([delivery] if delivery else []),
    }


def delivery_from_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if not row:
        return {}
    item = dict(row)
    item["payload"] = json.loads(item.get("payload") or "{}")
    return item


def get_alert_deliveries(limit: int = 50) -> list[dict[str, Any]]:
    with DB_LOCK, connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alert_deliveries ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [delivery_from_row(row) for row in rows]


def get_alerts(limit: int = 50, include_resolved: bool = False) -> list[dict[str, Any]]:
    query = "SELECT * FROM alerts"
    params: list[Any] = []
    if not include_resolved:
        query += " WHERE status != 'resolved'"
    query += " ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, updated_at DESC LIMIT ?"
    params.append(limit)
    with DB_LOCK, connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [alert_from_row(row) for row in rows]


def alert_summary(alerts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = alerts if alerts is not None else get_alerts(limit=100, include_resolved=False)
    active = [alert for alert in rows if alert.get("status") != "resolved"]
    return {
        "active": len(active),
        "critical": sum(1 for alert in active if alert.get("severity") == "critical"),
        "warning": sum(1 for alert in active if alert.get("severity") == "warning"),
        "info": sum(1 for alert in active if alert.get("severity") == "info"),
        "acknowledged": sum(1 for alert in active if alert.get("status") == "acknowledged"),
        "latest": active[0] if active else None,
        "updated_at": utc_now(),
    }


def alert_state_snapshot(limit: int = 50) -> dict[str, Any]:
    alerts = get_alerts(limit=limit, include_resolved=False)
    return {
        "alerts": alerts,
        "summary": alert_summary(alerts),
        "delivery": alert_delivery_config(),
        "deliveries": get_alert_deliveries(limit=10),
        "watchdog": "snapshot",
    }


def run_watchdog_checks() -> dict[str, Any]:
    risk = risk_config()
    if risk["emergency_stop"]:
        raise_alert(
            "risk.emergency_stop",
            "critical",
            "Risk Engine",
            "紧急停止已开启",
            "所有新订单都会被风控拒绝，需要人工确认后再解除。",
            {"risk": risk},
        )
    else:
        resolve_alert("risk.emergency_stop", "紧急停止已关闭")

    sched = scheduler_status()
    if sched.get("last_error"):
        raise_alert(
            "scheduler.last_error",
            "warning",
            "Scheduler",
            "自动调度最近失败",
            str(sched["last_error"]),
            {"scheduler": sched},
        )
    else:
        resolve_alert("scheduler.last_error", "调度错误已清除")

    oms = oms_summary()
    if oms["unknown_venue_status"] > 0:
        raise_alert(
            "oms.unknown_status",
            "critical",
            "OMS",
            "存在未知交易所状态订单",
            f"未知状态订单 {oms['unknown_venue_status']} 个，必须先对账再继续下单。",
            {"oms": oms},
        )
    else:
        resolve_alert("oms.unknown_status", "未知状态已清零")
    if oms["needs_reconcile"] > 0:
        raise_alert(
            "oms.needs_reconcile",
            "warning",
            "OMS",
            "存在待对账订单",
            f"待对账订单 {oms['needs_reconcile']} 个，建议立即执行恢复对账。",
            {"oms": oms},
        )
    else:
        resolve_alert("oms.needs_reconcile", "待对账订单已清零")

    recovery_age = seconds_since(get_setting("exchange_recovery_last_at", ""))
    if recovery_age is None or recovery_age > EXCHANGE_RECOVERY_STALE_SECONDS:
        raise_alert(
            "exchange.recovery_stale",
            "warning",
            "Exchange Recovery",
            "交易所恢复同步过旧",
            "恢复同步尚未执行或已经超过阈值，请运行恢复对账。",
            {
                "last_at": get_setting("exchange_recovery_last_at", ""),
                "threshold_seconds": EXCHANGE_RECOVERY_STALE_SECONDS,
                "age_seconds": recovery_age,
            },
        )
    else:
        resolve_alert("exchange.recovery_stale", "恢复同步在阈值内")

    stream = binance_user_stream_status()
    stream_has_key = bool(stream.get("listen_key_present"))
    if stream_has_key and not stream.get("dependency_ready"):
        raise_alert(
            "stream.dependency_missing",
            "critical",
            "Private User Stream",
            "私有流依赖缺失",
            "Python websockets 依赖不可用，无法消费 Binance 私有回报流。",
            {"stream": stream},
        )
    else:
        resolve_alert("stream.dependency_missing", "私有流依赖可用或未启用")

    stream_status = str(stream.get("status") or "")
    if stream_has_key and (
        not stream.get("consumer_running")
        or stream_status in {"error", "expired"}
    ):
        raise_alert(
            "stream.consumer_down",
            "critical",
            "Private User Stream",
            "私有回报流消费线程异常",
            "listenKey 存在但消费线程未运行或状态异常，订单/仓位回报可能延迟。",
            {"stream": stream},
        )
    else:
        resolve_alert("stream.consumer_down", "私有流消费线程正常或未启用")

    last_event_age = seconds_since(str(stream.get("last_event_at") or ""))
    if stream_has_key and stream.get("consumer_running") and last_event_age is not None and last_event_age > PRIVATE_STREAM_STALE_SECONDS:
        raise_alert(
            "stream.events_stale",
            "warning",
            "Private User Stream",
            "私有回报流事件过旧",
            "私有流长时间没有事件，若账户有活动请检查连接和 Binance 状态。",
            {
                "stream": stream,
                "threshold_seconds": PRIVATE_STREAM_STALE_SECONDS,
                "age_seconds": last_event_age,
            },
        )
    else:
        resolve_alert("stream.events_stale", "私有流事件新鲜或未启用")

    active_alerts = get_alerts(limit=100, include_resolved=False)
    return {
        "summary": alert_summary(active_alerts),
        "alerts": active_alerts,
        "delivery": alert_delivery_config(),
        "deliveries": get_alert_deliveries(limit=20),
    }


def dict_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def append_audit_record(
    conn: sqlite3.Connection,
    stream: str,
    ref_id: str,
    action: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = utc_now()
    previous_row = conn.execute(
        "SELECT row_hash FROM audit_chain ORDER BY id DESC LIMIT 1"
    ).fetchone()
    previous_hash = previous_row["row_hash"] if previous_row else "GENESIS"
    clean_payload = payload or {}
    hash_input = {
        "ts": now,
        "stream": stream,
        "ref_id": ref_id,
        "action": action,
        "previous_hash": previous_hash,
        "payload": clean_payload,
    }
    row_hash = hashlib.sha256(canonical_json(hash_input).encode("utf-8")).hexdigest()
    conn.execute(
        """
        INSERT INTO audit_chain(ts, stream, ref_id, action, previous_hash, row_hash, payload)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now,
            stream,
            ref_id,
            action,
            previous_hash,
            row_hash,
            canonical_json(clean_payload),
        ),
    )
    return {
        "ts": now,
        "stream": stream,
        "ref_id": ref_id,
        "action": action,
        "previous_hash": previous_hash,
        "row_hash": row_hash,
    }


def audit_chain_status(limit: int = 10) -> dict[str, Any]:
    with DB_LOCK, connect() as conn:
        rows = conn.execute("SELECT * FROM audit_chain ORDER BY id ASC").fetchall()
        recent_rows = conn.execute(
            "SELECT * FROM audit_chain ORDER BY id DESC LIMIT ?",
            (max(1, min(100, limit)),),
        ).fetchall()
    previous_hash = "GENESIS"
    broken_records: list[dict[str, Any]] = []
    stream_counts: dict[str, int] = {}
    last_hash = "GENESIS"
    last_ts = ""
    for row in rows:
        item = dict(row)
        payload = json.loads(item.get("payload") or "{}")
        expected_hash = hashlib.sha256(
            canonical_json(
                {
                    "ts": item["ts"],
                    "stream": item["stream"],
                    "ref_id": item["ref_id"],
                    "action": item["action"],
                    "previous_hash": item["previous_hash"],
                    "payload": payload,
                }
            ).encode("utf-8")
        ).hexdigest()
        stream_counts[item["stream"]] = stream_counts.get(item["stream"], 0) + 1
        if item["previous_hash"] != previous_hash or item["row_hash"] != expected_hash:
            broken_records.append(
                {
                    "id": item["id"],
                    "stream": item["stream"],
                    "ref_id": item["ref_id"],
                    "expected_previous_hash": previous_hash,
                    "actual_previous_hash": item["previous_hash"],
                    "expected_row_hash": expected_hash,
                    "actual_row_hash": item["row_hash"],
                }
            )
        previous_hash = item["row_hash"]
        last_hash = item["row_hash"]
        last_ts = item["ts"]
    recent: list[dict[str, Any]] = []
    for row in reversed(recent_rows):
        item = dict(row)
        item["payload"] = json.loads(item.get("payload") or "{}")
        recent.append(item)
    return {
        "status": "pass" if not broken_records else "fail",
        "total_records": len(rows),
        "broken_records": broken_records,
        "broken_count": len(broken_records),
        "last_hash": last_hash,
        "last_ts": last_ts,
        "stream_counts": stream_counts,
        "recent": recent,
    }


def audit_chain_snapshot(limit: int = 8) -> dict[str, Any]:
    row_limit = max(1, min(100, limit))
    with DB_LOCK, connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS count FROM audit_chain").fetchone()["count"]
        last = conn.execute(
            "SELECT ts, row_hash FROM audit_chain ORDER BY id DESC LIMIT 1"
        ).fetchone()
        recent_rows = conn.execute(
            """
            SELECT ts, stream, ref_id, action, previous_hash, row_hash
            FROM audit_chain
            ORDER BY id DESC
            LIMIT ?
            """,
            (row_limit,),
        ).fetchall()
    recent = [dict(row) for row in reversed(recent_rows)]
    return {
        "status": "pass" if total else "warn",
        "snapshot": True,
        "total_records": total,
        "broken_records": [],
        "broken_count": 0,
        "last_hash": (dict(last).get("row_hash") if last else "GENESIS"),
        "last_ts": (dict(last).get("ts") if last else ""),
        "stream_counts": {},
        "recent": recent,
    }


def insert_event(
    run_id: str,
    kind: str,
    actor: str,
    title: str,
    body: str,
    payload: dict[str, Any] | None = None,
) -> None:
    now = utc_now()
    clean_payload = payload or {}
    with DB_LOCK, connect() as conn:
        conn.execute(
            """
            INSERT INTO events(run_id, ts, kind, actor, title, body, payload)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, now, kind, actor, title, body, json.dumps(clean_payload, ensure_ascii=False)),
        )
        append_audit_record(
            conn,
            "event",
            run_id,
            kind,
            {
                "run_id": run_id,
                "kind": kind,
                "actor": actor,
                "title": title,
                "body": body,
                "payload": clean_payload,
            },
        )
        conn.execute("UPDATE runs SET updated_at = ? WHERE id = ?", (now, run_id))
        conn.commit()


def update_run(run_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = utc_now()
    names = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [run_id]
    with DB_LOCK, connect() as conn:
        conn.execute(f"UPDATE runs SET {names} WHERE id = ?", values)
        conn.commit()


def create_run(symbol: str, mode: str) -> dict[str, Any]:
    run_id = str(uuid.uuid4())[:8]
    now = utc_now()
    with DB_LOCK, connect() as conn:
        conn.execute(
            """
            INSERT INTO runs(id, symbol, mode, status, created_at, updated_at)
            VALUES(?, ?, ?, 'queued', ?, ?)
            """,
            (run_id, symbol.upper().strip(), mode, now, now),
        )
        conn.commit()
    return get_run(run_id) or {}


def launch_run(symbol: str, mode: str) -> dict[str, Any]:
    if mode == "live_guarded":
        assert_go_live_gate_allows_live_order()
    with RUN_LOCK:
        if ACTIVE_RUNS:
            raise RuntimeError("A run is already active.")
        run = create_run(symbol, mode)
        ACTIVE_RUNS.add(run["id"])
        thread = threading.Thread(target=run_workflow, args=(run["id"],), daemon=True)
        thread.start()
    return run


def get_run(run_id: str) -> dict[str, Any] | None:
    with DB_LOCK, connect() as conn:
        return dict_row(conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone())


def get_latest_run() -> dict[str, Any] | None:
    with DB_LOCK, connect() as conn:
        return dict_row(
            conn.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT 1").fetchone()
        )


def get_events(run_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    query = "SELECT * FROM events"
    params: list[Any] = []
    if run_id:
        query += " WHERE run_id = ?"
        params.append(run_id)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with DB_LOCK, connect() as conn:
        rows = conn.execute(query, params).fetchall()
    events = []
    for row in reversed(rows):
        item = dict(row)
        item["payload"] = json.loads(item.get("payload") or "{}")
        events.append(item)
    return events


def insert_ai_operator_message(
    role: str,
    content: str,
    status: str = "ok",
    actions: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_content = ai_operator_redact_sensitive_text(content)
    safe_actions = ai_operator_redact_sensitive_obj(actions or [])
    safe_metadata = ai_operator_redact_sensitive_obj(metadata or {})
    message = {
        "id": str(uuid.uuid4())[:12],
        "ts": utc_now(),
        "role": role,
        "content": safe_content,
        "status": status,
        "actions": safe_actions,
        "metadata": safe_metadata,
    }
    with DB_LOCK, connect() as conn:
        conn.execute(
            """
            INSERT INTO ai_operator_messages(id, ts, role, content, status, actions, metadata)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message["id"],
                message["ts"],
                message["role"],
                message["content"],
                message["status"],
                json.dumps(message["actions"], ensure_ascii=False),
                json.dumps(message["metadata"], ensure_ascii=False),
            ),
        )
        append_audit_record(
            conn,
            "ai_operator",
            message["id"],
            f"message_{role}",
            {
                "role": message["role"],
                "status": message["status"],
                "content_sha256": hashlib.sha256(message["content"].encode("utf-8")).hexdigest(),
                "actions": message["actions"],
                "metadata": message["metadata"],
            },
        )
        conn.commit()
    return message


def get_ai_operator_messages(limit: int = 40) -> list[dict[str, Any]]:
    with DB_LOCK, connect() as conn:
        rows = conn.execute(
            "SELECT * FROM ai_operator_messages ORDER BY ts DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    messages: list[dict[str, Any]] = []
    for row in reversed(rows):
        item = dict(row)
        item["actions"] = json.loads(item.get("actions") or "[]")
        item["metadata"] = json.loads(item.get("metadata") or "{}")
        messages.append(item)
    return messages


def ai_operator_safe_path(path_value: Any) -> Path:
    raw = str(path_value or ".").strip().replace("\\", "/")
    if not raw:
        raw = "."
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = AI_OPERATOR_WORKSPACE_ROOT / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(AI_OPERATOR_WORKSPACE_ROOT)
    except ValueError as exc:
        raise ValueError("AI 操作员只能访问配置的工作区目录。") from exc
    return resolved


def ai_operator_relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(AI_OPERATOR_WORKSPACE_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def ai_operator_file_digest(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ai_operator_secret_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:10]


def ai_operator_redaction_token(name: str, value: str) -> str:
    label = re.sub(r"[^A-Za-z0-9_:-]+", "_", name or "secret")[:48] or "secret"
    return f"[REDACTED:{label}:{ai_operator_secret_fingerprint(value)}]"


def ai_operator_known_secret_values() -> dict[str, str]:
    names = {
        "APP_BASIC_AUTH_PASSWORD",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "BINANCE_API_KEY",
        "BINANCE_API_SECRET",
        "BINANCE_LIVE_API_KEY",
        "BINANCE_LIVE_API_SECRET",
        "ALERT_WEBHOOK_URL",
        "ALERT_WEBHOOK_SECRET",
        "ALERT_TELEGRAM_BOT_TOKEN",
        "ALERT_TELEGRAM_CHAT_ID",
        "ALERT_EMAIL_SMTP_PASSWORD",
        "OKX_API_KEY",
        "OKX_API_SECRET",
    }
    result: dict[str, str] = {}
    for name in names:
        value = os.getenv(name, "").strip()
        if value and len(value) >= 4 and not value.startswith("<"):
            result[name] = value
    return result


def ai_operator_redact_sensitive_text(text: Any) -> str:
    raw = str(text if text is not None else "")
    redacted = raw

    def replace_assignment(match: re.Match[str]) -> str:
        prefix, key, value = match.group(1), match.group(2), match.group(3)
        clean_value = value.strip().strip('"').strip("'")
        if not clean_value or clean_value.startswith("<"):
            return match.group(0)
        if AI_OPERATOR_SENSITIVE_KEY_RE.search(key):
            quote = '"' if value.strip().startswith('"') and value.strip().endswith('"') else ""
            token = ai_operator_redaction_token(key, clean_value)
            return f"{prefix}{quote}{token}{quote}"
        return match.group(0)

    redacted = AI_OPERATOR_ENV_ASSIGNMENT_RE.sub(replace_assignment, redacted)

    def replace_json_secret(match: re.Match[str]) -> str:
        prefix, key, value = match.group(1), match.group(2), match.group(3)
        if not value:
            return match.group(0)
        return f'{prefix}"{ai_operator_redaction_token(key, value)}"'

    redacted = AI_OPERATOR_JSON_SECRET_RE.sub(replace_json_secret, redacted)

    for name, value in sorted(ai_operator_known_secret_values().items(), key=lambda item: len(item[1]), reverse=True):
        if value:
            redacted = redacted.replace(value, ai_operator_redaction_token(name, value))

    redacted = re.sub(r"\bsk-[A-Za-z0-9_-]{16,}\b", lambda m: ai_operator_redaction_token("OPENAI_API_KEY", m.group(0)), redacted)
    redacted = re.sub(
        r"\b(xox[baprs]-[A-Za-z0-9-]{16,})\b",
        lambda m: ai_operator_redaction_token("TOKEN", m.group(1)),
        redacted,
    )
    return redacted


def ai_operator_redact_sensitive_obj(value: Any) -> Any:
    if isinstance(value, str):
        return ai_operator_redact_sensitive_text(value)
    if isinstance(value, list):
        return [ai_operator_redact_sensitive_obj(item) for item in value]
    if isinstance(value, tuple):
        return [ai_operator_redact_sensitive_obj(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): ai_operator_redact_sensitive_obj(item)
            for key, item in value.items()
        }
    return value


def ai_operator_snapshot_slug(value: str) -> str:
    cleaned = []
    for char in value:
        if char.isalnum() or char in {".", "-", "_"}:
            cleaned.append(char)
        else:
            cleaned.append("_")
    slug = "".join(cleaned).strip("._")
    return (slug or "workspace_file")[:120]


def ai_operator_create_file_snapshot(path: Path, reason: str) -> dict[str, Any]:
    if not AI_OPERATOR_SNAPSHOT_WRITES:
        return {"enabled": False, "created": False, "reason": "AI_OPERATOR_SNAPSHOT_WRITES=false"}
    target = path.resolve()
    if not target.exists() or not target.is_file():
        return {"enabled": True, "created": False, "reason": "target_missing_before_write"}
    size = target.stat().st_size
    if size > AI_OPERATOR_MAX_SNAPSHOT_BYTES:
        raise ValueError(
            f"写入前快照超过 AI_OPERATOR_MAX_SNAPSHOT_BYTES 限制：{size} bytes"
        )
    AI_OPERATOR_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_id = f"AIOP-SNAP-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    target_rel = ai_operator_relative_path(target)
    snapshot_name = f"{snapshot_id}__{ai_operator_snapshot_slug(target_rel)}"
    snapshot_path = AI_OPERATOR_SNAPSHOT_DIR / snapshot_name
    metadata_path = AI_OPERATOR_SNAPSHOT_DIR / f"{snapshot_name}.json"
    content = target.read_bytes()
    snapshot_path.write_bytes(content)
    metadata = {
        "id": snapshot_id,
        "created_at": utc_now(),
        "reason": reason,
        "target_path": target_rel,
        "snapshot_path": ai_operator_relative_path(snapshot_path),
        "size_bytes": size,
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "enabled": True,
        "created": True,
        "id": snapshot_id,
        "path": ai_operator_relative_path(snapshot_path),
        "metadata_path": ai_operator_relative_path(metadata_path),
        "target_path": target_rel,
        "size_bytes": size,
        "sha256": metadata["sha256"],
    }


def ai_operator_restore_snapshot(snapshot_path_value: Any, target_path_value: Any = None) -> dict[str, Any]:
    if not AI_OPERATOR_ALLOW_FILE_WRITE:
        raise ValueError("AI 操作员文件写入权限未启用。")
    snapshot_path = ai_operator_safe_path(snapshot_path_value)
    if not snapshot_path.exists() or not snapshot_path.is_file():
        raise ValueError(f"快照文件不存在：{ai_operator_relative_path(snapshot_path)}")
    try:
        snapshot_path.relative_to(AI_OPERATOR_SNAPSHOT_DIR)
    except ValueError as exc:
        raise ValueError("只能恢复 AI 操作员快照目录中的文件。") from exc
    metadata_path = snapshot_path.with_name(f"{snapshot_path.name}.json")
    metadata: dict[str, Any] = {}
    if metadata_path.exists():
        try:
            parsed = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata = parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            metadata = {}
    restore_target = target_path_value or metadata.get("target_path")
    if not restore_target:
        raise ValueError("恢复快照需要 target_path，或快照旁边必须存在元数据文件。")
    target_path = ai_operator_safe_path(restore_target)
    before_snapshot = ai_operator_create_file_snapshot(target_path, "restore_snapshot_before_overwrite")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    content = snapshot_path.read_bytes()
    target_path.write_bytes(content)
    return {
        "action": "restore_snapshot",
        "snapshot_path": ai_operator_relative_path(snapshot_path),
        "metadata_path": ai_operator_relative_path(metadata_path) if metadata_path.exists() else "",
        "path": ai_operator_relative_path(target_path),
        "bytes": len(content),
        "restored_sha256": hashlib.sha256(content).hexdigest(),
        "before_restore_snapshot": before_snapshot,
        "after_sha256": ai_operator_file_digest(target_path),
    }


def ai_operator_list_files(path_value: Any = ".", limit: int = 80) -> dict[str, Any]:
    if not AI_OPERATOR_ALLOW_FILE_READ:
        raise ValueError("AI 操作员文件读取权限未启用。")
    path = ai_operator_safe_path(path_value)
    if not path.exists():
        raise ValueError(f"路径不存在：{ai_operator_relative_path(path)}")
    entries: list[dict[str, Any]] = []
    if path.is_file():
        entries.append(
            {
                "path": ai_operator_relative_path(path),
                "type": "file",
                "size_bytes": path.stat().st_size,
            }
        )
    else:
        for child in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            if len(entries) >= limit:
                break
            entries.append(
                {
                    "path": ai_operator_relative_path(child),
                    "type": "dir" if child.is_dir() else "file",
                    "size_bytes": child.stat().st_size if child.is_file() else None,
                }
            )
    return {"action": "list", "path": ai_operator_relative_path(path), "entries": entries}


def ai_operator_read_file(path_value: Any) -> dict[str, Any]:
    if not AI_OPERATOR_ALLOW_FILE_READ:
        raise ValueError("AI 操作员文件读取权限未启用。")
    path = ai_operator_safe_path(path_value)
    if not path.exists() or not path.is_file():
        raise ValueError(f"文件不存在：{ai_operator_relative_path(path)}")
    size = path.stat().st_size
    if size > AI_OPERATOR_MAX_READ_BYTES:
        raise ValueError(f"文件超过 AI_OPERATOR_MAX_READ_BYTES 限制：{size} bytes")
    content = path.read_text(encoding="utf-8", errors="replace")
    safe_content = ai_operator_redact_sensitive_text(content)
    return {
        "action": "read",
        "path": ai_operator_relative_path(path),
        "size_bytes": size,
        "sha256": ai_operator_file_digest(path),
        "content": safe_content,
        "redacted": safe_content != content,
    }


def ai_operator_write_file(path_value: Any, content: Any, append: bool = False) -> dict[str, Any]:
    if not AI_OPERATOR_ALLOW_FILE_WRITE:
        raise ValueError("AI 操作员文件写入权限未启用。")
    path = ai_operator_safe_path(path_value)
    text = str(content if content is not None else "")
    encoded = text.encode("utf-8")
    if len(encoded) > AI_OPERATOR_MAX_WRITE_BYTES:
        raise ValueError(f"写入内容超过 AI_OPERATOR_MAX_WRITE_BYTES 限制：{len(encoded)} bytes")
    before_sha = ai_operator_file_digest(path)
    snapshot = ai_operator_create_file_snapshot(path, "append" if append else "write")
    path.parent.mkdir(parents=True, exist_ok=True)
    if append:
        with path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(text)
    else:
        path.write_text(text, encoding="utf-8", newline="")
    return {
        "action": "append" if append else "write",
        "path": ai_operator_relative_path(path),
        "bytes": len(encoded),
        "before_sha256": before_sha,
        "after_sha256": ai_operator_file_digest(path),
        "snapshot": snapshot,
    }


def ai_operator_replace_in_file(path_value: Any, old_text: Any, new_text: Any) -> dict[str, Any]:
    if not AI_OPERATOR_ALLOW_FILE_WRITE:
        raise ValueError("AI 操作员文件写入权限未启用。")
    path = ai_operator_safe_path(path_value)
    if not path.exists() or not path.is_file():
        raise ValueError(f"文件不存在：{ai_operator_relative_path(path)}")
    text = path.read_text(encoding="utf-8", errors="replace")
    old = str(old_text if old_text is not None else "")
    new = str(new_text if new_text is not None else "")
    if not old:
        raise ValueError("replace 动作必须提供 old_text。")
    if old not in text:
        raise ValueError("replace 动作未找到 old_text。")
    updated = text.replace(old, new, 1)
    return ai_operator_write_file(path, updated, append=False) | {
        "action": "replace",
        "replacements": 1,
    }


def ai_operator_find_sequence(lines: list[str], sequence: list[str], start: int) -> int:
    if not sequence:
        return start
    max_start = len(lines) - len(sequence)
    for index in range(max(0, start), max_start + 1):
        if lines[index : index + len(sequence)] == sequence:
            return index
    return -1


def ai_operator_apply_hunk(path: Path, hunk_lines: list[str], cursor: int) -> tuple[list[str], int]:
    original_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    old_sequence: list[str] = []
    new_sequence: list[str] = []
    for raw_line in hunk_lines:
        if not raw_line:
            raise ValueError("patch hunk contains an empty control line")
        prefix = raw_line[0]
        value = raw_line[1:]
        if prefix == " ":
            old_sequence.append(value)
            new_sequence.append(value)
        elif prefix == "-":
            old_sequence.append(value)
        elif prefix == "+":
            new_sequence.append(value)
        elif prefix == "\\":
            continue
        else:
            raise ValueError(f"unsupported patch hunk line: {raw_line!r}")
    match_index = ai_operator_find_sequence(original_lines, old_sequence, cursor)
    if match_index < 0:
        raise ValueError(f"patch hunk did not match {ai_operator_relative_path(path)}")
    updated = (
        original_lines[:match_index]
        + new_sequence
        + original_lines[match_index + len(old_sequence) :]
    )
    return updated, match_index + len(new_sequence)


def ai_operator_apply_update_patch(path_value: Any, hunk_lines: list[str]) -> dict[str, Any]:
    if not AI_OPERATOR_ALLOW_FILE_WRITE:
        raise ValueError("AI operator file write permission is disabled.")
    path = ai_operator_safe_path(path_value)
    if not path.exists() or not path.is_file():
        raise ValueError(f"file does not exist: {ai_operator_relative_path(path)}")
    cursor = 0
    current_hunk: list[str] = []
    updated_lines: list[str] | None = None
    original_text = path.read_text(encoding="utf-8", errors="replace")

    # Work on a temporary in-memory file image by writing each applied hunk back
    # into the line list, then snapshot/write once at the end.
    working_lines = original_text.splitlines()
    for raw_line in hunk_lines + ["@@"]:
        if raw_line.startswith("@@"):
            if current_hunk:
                old_sequence: list[str] = []
                new_sequence: list[str] = []
                for hunk_line in current_hunk:
                    prefix = hunk_line[0]
                    value = hunk_line[1:]
                    if prefix == " ":
                        old_sequence.append(value)
                        new_sequence.append(value)
                    elif prefix == "-":
                        old_sequence.append(value)
                    elif prefix == "+":
                        new_sequence.append(value)
                    elif prefix == "\\":
                        continue
                    else:
                        raise ValueError(f"unsupported patch hunk line: {hunk_line!r}")
                match_index = ai_operator_find_sequence(working_lines, old_sequence, cursor)
                if match_index < 0:
                    raise ValueError(f"patch hunk did not match {ai_operator_relative_path(path)}")
                working_lines = (
                    working_lines[:match_index]
                    + new_sequence
                    + working_lines[match_index + len(old_sequence) :]
                )
                cursor = match_index + len(new_sequence)
                current_hunk = []
            continue
        if raw_line[:1] in {" ", "-", "+", "\\"}:
            current_hunk.append(raw_line)
        elif raw_line:
            raise ValueError(f"unsupported patch line: {raw_line!r}")
    updated_lines = working_lines
    updated_text = "\n".join(updated_lines)
    if original_text.endswith("\n"):
        updated_text += "\n"
    result = ai_operator_write_file(path, updated_text, append=False)
    result["action"] = "patch_update"
    return result


def ai_operator_apply_begin_patch(patch_content: str) -> dict[str, Any]:
    if not AI_OPERATOR_ALLOW_FILE_WRITE:
        raise ValueError("AI operator file write permission is disabled.")
    lines = patch_content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines or lines[0].strip() != "*** Begin Patch":
        raise ValueError("patch must start with *** Begin Patch")
    operations: list[dict[str, Any]] = []
    index = 1
    while index < len(lines):
        line = lines[index]
        if line.strip() == "*** End Patch":
            break
        if line.startswith("*** Add File: "):
            target = line.removeprefix("*** Add File: ").strip()
            index += 1
            content_lines: list[str] = []
            while index < len(lines) and not lines[index].startswith("*** "):
                if not lines[index].startswith("+"):
                    raise ValueError("add-file patch lines must start with +")
                content_lines.append(lines[index][1:])
                index += 1
            path = ai_operator_safe_path(target)
            if path.exists():
                raise ValueError(f"add-file target already exists: {ai_operator_relative_path(path)}")
            operations.append(ai_operator_write_file(path, "\n".join(content_lines) + "\n", append=False))
            operations[-1]["action"] = "patch_add"
            continue
        if line.startswith("*** Delete File: "):
            target = line.removeprefix("*** Delete File: ").strip()
            path = ai_operator_safe_path(target)
            if not path.exists() or not path.is_file():
                raise ValueError(f"delete-file target does not exist: {ai_operator_relative_path(path)}")
            snapshot = ai_operator_create_file_snapshot(path, "patch_delete")
            before_sha = ai_operator_file_digest(path)
            path.unlink()
            operations.append(
                {
                    "action": "patch_delete",
                    "path": ai_operator_relative_path(path),
                    "before_sha256": before_sha,
                    "snapshot": snapshot,
                }
            )
            index += 1
            continue
        if line.startswith("*** Update File: "):
            target = line.removeprefix("*** Update File: ").strip()
            index += 1
            hunk_lines: list[str] = []
            while index < len(lines) and not lines[index].startswith("*** "):
                hunk_lines.append(lines[index])
                index += 1
            operations.append(ai_operator_apply_update_patch(target, hunk_lines))
            continue
        if not line.strip():
            index += 1
            continue
        raise ValueError(f"unsupported patch directive: {line!r}")
    else:
        raise ValueError("patch must end with *** End Patch")
    return {"action": "patch", "operations": operations, "operation_count": len(operations)}


def ai_operator_apply_patch_action(path_value: Any, content_value: Any) -> dict[str, Any]:
    patch_content = str(content_value if content_value is not None else "")
    if not patch_content.strip():
        raise ValueError("patch action requires content")
    if patch_content.lstrip().startswith("*** Begin Patch"):
        return ai_operator_apply_begin_patch(patch_content.strip())
    path = str(path_value or "").strip()
    if not path:
        raise ValueError("non-Begin-Patch patch action requires a path")
    return ai_operator_apply_update_patch(path, patch_content.splitlines())


def ai_operator_truncate_output(text: str | bytes | None) -> tuple[str, bool]:
    if text is None:
        return "", False
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    text = ai_operator_redact_sensitive_text(str(text))
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= AI_OPERATOR_MAX_SHELL_OUTPUT_BYTES:
        return text, False
    clipped = encoded[:AI_OPERATOR_MAX_SHELL_OUTPUT_BYTES].decode("utf-8", errors="replace")
    return clipped + "\n...[truncated by AI_OPERATOR_MAX_SHELL_OUTPUT_BYTES]", True


def ai_operator_create_runtime_backup(reason: str = "before_shell") -> dict[str, Any]:
    if not AI_OPERATOR_BACKUP_BEFORE_SHELL:
        return {"enabled": False, "created": False, "reason": "AI_OPERATOR_BACKUP_BEFORE_SHELL=false"}
    script_path = ROOT_DIR / "scripts" / "backup_state.py"
    if not script_path.exists():
        raise ValueError("AI 操作员 Shell 前备份脚本不存在。")
    AI_OPERATOR_SHELL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(script_path),
        "--output-dir",
        str(AI_OPERATOR_SHELL_BACKUP_DIR),
        "--include-env-example",
    ]
    completed = subprocess.run(
        command,
        cwd=str(ROOT_DIR),
        text=True,
        capture_output=True,
        timeout=AI_OPERATOR_SHELL_BACKUP_TIMEOUT_SECONDS,
    )
    stdout, stdout_truncated = ai_operator_truncate_output(completed.stdout)
    stderr, stderr_truncated = ai_operator_truncate_output(completed.stderr)
    payload: dict[str, Any] = {
        "enabled": True,
        "created": completed.returncode == 0,
        "reason": reason,
        "command": ai_operator_redact_sensitive_text(" ".join(command)),
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
    }
    try:
        summary = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        summary = {}
    if summary:
        payload["summary"] = summary
        if summary.get("backup_path"):
            payload["backup_path"] = summary["backup_path"]
            try:
                payload["relative_backup_path"] = ai_operator_relative_path(Path(str(summary["backup_path"])))
            except ValueError:
                payload["relative_backup_path"] = str(summary["backup_path"])
        if summary.get("sha256"):
            payload["sha256"] = summary["sha256"]
    if completed.returncode != 0:
        raise ValueError(f"AI 操作员 Shell 前备份失败：{stderr or stdout or completed.returncode}")
    return payload


def ai_operator_run_shell(
    command_value: Any,
    cwd_value: Any = ".",
    timeout_value: Any = None,
) -> dict[str, Any]:
    if not AI_OPERATOR_ALLOW_SHELL:
        raise ValueError("AI 操作员 Shell 权限未启用。")
    command = str(command_value if command_value is not None else "").strip()
    if not command:
        raise ValueError("shell 动作必须提供 command。")
    cwd = ai_operator_safe_path(cwd_value or ".")
    if cwd.exists() and cwd.is_file():
        cwd = cwd.parent
    if not cwd.exists() or not cwd.is_dir():
        raise ValueError(f"Shell 工作目录不存在：{ai_operator_relative_path(cwd)}")
    try:
        timeout_seconds = int(float(timeout_value or AI_OPERATOR_SHELL_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        timeout_seconds = AI_OPERATOR_SHELL_TIMEOUT_SECONDS
    timeout_seconds = max(1, min(600, timeout_seconds))
    backup = ai_operator_create_runtime_backup("before_shell")
    started = time.time()
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        stdout, stdout_truncated = ai_operator_truncate_output(completed.stdout)
        stderr, stderr_truncated = ai_operator_truncate_output(completed.stderr)
        return {
            "action": "shell",
            "command": ai_operator_redact_sensitive_text(command),
            "cwd": ai_operator_relative_path(cwd),
            "pre_shell_backup": backup,
            "returncode": completed.returncode,
            "duration_seconds": round(time.time() - started, 3),
            "timed_out": False,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }
    except subprocess.TimeoutExpired as exc:
        stdout, stdout_truncated = ai_operator_truncate_output(exc.stdout)
        stderr, stderr_truncated = ai_operator_truncate_output(exc.stderr)
        return {
            "action": "shell",
            "command": ai_operator_redact_sensitive_text(command),
            "cwd": ai_operator_relative_path(cwd),
            "pre_shell_backup": backup,
            "returncode": None,
            "duration_seconds": round(time.time() - started, 3),
            "timed_out": True,
            "timeout_seconds": timeout_seconds,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }


def ai_operator_compact_gate(gate: dict[str, Any]) -> dict[str, Any]:
    blockers = gate.get("blocking_gates") or []
    return {
        "action": "go_live_gate",
        "status": gate.get("status"),
        "ready_to_enable_live": gate.get("ready_to_enable_live"),
        "ready_to_arm_live": gate.get("ready_to_arm_live"),
        "ready_for_live_order": gate.get("ready_for_live_order"),
        "blocking_count": len(blockers),
        "blocking_gates": [
            {
                "id": item.get("id"),
                "label": item.get("label"),
                "status": item.get("status"),
                "detail": item.get("detail"),
                "blocks_live_order": item.get("blocks_live_order"),
            }
            for item in blockers
        ],
    }


def ai_operator_latest_report_path(pattern: str) -> str:
    report_dir = ROOT_DIR / "reports"
    matches = list(report_dir.glob(pattern)) if report_dir.exists() else []
    if not matches:
        return ""
    return ai_operator_relative_path(max(matches, key=lambda item: item.stat().st_mtime))


def ai_operator_system_action(action: dict[str, Any]) -> dict[str, Any]:
    action_type = str(action.get("type") or action.get("action") or "").lower().strip()
    if action_type == "readiness":
        readiness = deployment_readiness()
        return {
            "action": "readiness",
            "overall": readiness.get("overall"),
            "checks": readiness.get("checks"),
            "warnings": readiness.get("warnings") or [],
            "errors": readiness.get("errors") or [],
        }
    if action_type == "go_live_gate":
        return ai_operator_compact_gate(go_live_gate_status())
    if action_type == "go_live_report":
        report = go_live_report()
        gate = report.get("go_live_gate") or {}
        return {
            "action": "go_live_report",
            "generated_at": report.get("generated_at"),
            "app_env": report.get("app_env"),
            "exchange_mode": report.get("exchange_mode"),
            "gate": ai_operator_compact_gate(gate),
            "latest_report_json": ai_operator_latest_report_path("go-live-report-*.json"),
            "latest_report_md": ai_operator_latest_report_path("go-live-report-*.md"),
        }
    if action_type == "final_live_ready":
        require_armed = coerce_bool(action.get("require_armed", True))
        require_ai_operator = coerce_bool(action.get("require_ai_operator", True))
        result = final_live_readiness(require_armed=require_armed, require_ai_operator=require_ai_operator)
        return {
            "action": "final_live_ready",
            "ok": result.get("ok"),
            "status": result.get("status"),
            "require_armed": result.get("require_armed"),
            "require_ai_operator": result.get("require_ai_operator"),
            "ready_for_live_order": result.get("ready_for_live_order"),
            "blocking_gates": result.get("blocking_gates") or [],
            "failures": result.get("failures") or [],
        }
    if action_type == "live_pilot":
        symbol = str(action.get("symbol") or "BTCUSDT").upper().strip()
        status = live_pilot_status(symbol)
        return {
            "action": "live_pilot",
            "status": status.get("status"),
            "symbol": status.get("symbol"),
            "can_launch": status.get("can_launch"),
            "confirmation_phrase": status.get("confirmation_phrase"),
            "next_action": status.get("next_action"),
            "failures": status.get("failures") or [],
            "prearm_ready": status.get("prearm_ready"),
            "armed_ready": status.get("armed_ready"),
        }
    if action_type == "live_pilot_postflight":
        symbol = str(action.get("symbol") or "BTCUSDT").upper().strip()
        status = live_pilot_postflight_status(symbol, str(action.get("run_id") or ""))
        return {
            "action": "live_pilot_postflight",
            "status": status.get("status"),
            "ok": status.get("ok"),
            "symbol": status.get("symbol"),
            "run_id": status.get("run_id"),
            "checks": status.get("checks") or [],
            "next_actions": status.get("next_actions") or [],
            "oms": status.get("oms"),
            "alerts": status.get("alerts"),
            "audit_chain": status.get("audit_chain"),
        }
    if action_type == "live_blocker_resolution":
        symbol = str(action.get("symbol") or "BTCUSDT").upper().strip()
        status = live_blocker_resolution_status(symbol)
        return {
            "action": "live_blocker_resolution",
            "status": status.get("status"),
            "ok": status.get("ok"),
            "symbol": status.get("symbol"),
            "blocking_gates": status.get("blocking_gates") or [],
            "next_action": status.get("next_action"),
            "steps": status.get("steps") or [],
            "ai_commands": status.get("ai_commands") or [],
            "safety_note": status.get("safety_note"),
        }
    if action_type == "live_pilot_run":
        result = execute_live_pilot_order(
            {
                "symbol": action.get("symbol") or "BTCUSDT",
                "confirmation": action.get("confirmation") or "",
            }
        )
        return {
            "action": "live_pilot_run",
            "status": result.get("status"),
            "run": result.get("run"),
            "live_pilot": result.get("live_pilot"),
        }
    if action_type == "live_arm":
        arming = arm_live_trading(
            {
                "confirmation": action.get("confirmation") or "",
                "ttl_seconds": action.get("ttl_seconds"),
                "ttl_minutes": action.get("ttl_minutes"),
                "actor": action.get("actor") or "ai_operator",
                "reason": action.get("reason") or "ai_operator_live_arm",
            }
        )
        return {"action": "live_arm", "live_arming": arming, "go_live_gate": ai_operator_compact_gate(go_live_gate_status())}
    if action_type == "live_disarm":
        arming = disarm_live_trading(str(action.get("reason") or "ai_operator_live_disarm"))
        return {"action": "live_disarm", "live_arming": arming, "go_live_gate": ai_operator_compact_gate(go_live_gate_status())}
    if action_type == "live_attestation_save":
        accepted_all = coerce_bool(action.get("accepted_all", False))
        accepted = (
            {item["id"]: True for item in LIVE_ATTESTATION_REQUIREMENTS}
            if accepted_all
            else {}
        )
        attestation = save_live_attestation(
            {
                "confirmation": action.get("confirmation") or "",
                "actor": action.get("actor") or "ai_operator",
                "note": action.get("note") or "ai_operator_live_attestation",
                "accepted": accepted,
            }
        )
        return {"action": "live_attestation_save", "live_attestation": attestation, "go_live_gate": ai_operator_compact_gate(go_live_gate_status())}
    if action_type == "live_attestation_clear":
        attestation = clear_live_attestation(str(action.get("reason") or "ai_operator_live_attestation_clear"))
        return {"action": "live_attestation_clear", "live_attestation": attestation, "go_live_gate": ai_operator_compact_gate(go_live_gate_status())}
    if action_type == "panic_stop":
        report = emergency_panic_stop(
            {
                "confirmation": action.get("confirmation") or "",
                "reason": action.get("reason") or "ai_operator_panic_stop",
                "cancel_orders": coerce_bool(action.get("cancel_orders", True)),
                "cancel_exchange_open_orders": coerce_bool(action.get("cancel_exchange_open_orders", True)),
                "flatten_positions": coerce_bool(action.get("flatten_positions", False)),
                "flatten_confirmation": action.get("flatten_confirmation") or "",
                "reconcile": coerce_bool(action.get("reconcile", True)),
            }
        )
        return {
            "action": "panic_stop",
            "status": report.get("status"),
            "reason": report.get("reason"),
            "emergency_stop": report.get("emergency_stop"),
            "cancel_attempt_count": len(report.get("cancel_attempts") or []),
            "cancel_failed_count": len(report.get("cancel_failed") or []),
            "exchange_cancel_attempt_count": len(report.get("exchange_cancel_attempts") or []),
            "exchange_cancel_failed_count": len(report.get("exchange_cancel_failed") or []),
            "flatten_attempt_count": len(report.get("flatten_attempts") or []),
            "flatten_failed_count": len(report.get("flatten_failed") or []),
            "live_arming": report.get("live_arming"),
            "oms": report.get("oms"),
            "alerts": report.get("alerts"),
            "created_at": report.get("created_at"),
        }
    if action_type == "server_live_readiness":
        return {"action": "server_live_readiness", **server_live_readiness_status()}
    if action_type == "live_env_profile":
        target = str(action.get("target") or "live_guarded").strip() or "live_guarded"
        return {"action": "live_env_profile", "profile": live_env_profile_status(target)}
    if action_type == "live_launch_plan":
        plan = live_launch_plan_status()
        return {
            "action": "live_launch_plan",
            "status": plan.get("status"),
            "generated_at": plan.get("generated_at"),
            "current_summary": plan.get("current_summary"),
            "blocker_count": len(plan.get("blockers") or []),
            "blockers": (plan.get("blockers") or [])[:12],
            "next_actions": plan.get("next_actions") or [],
            "evidence_paths": plan.get("evidence_paths") or {},
        }
    if action_type == "live_ops_handoff":
        symbols = normalize_symbols(str(action.get("symbol") or "BTCUSDT"))
        symbol = symbols[0] if symbols else "BTCUSDT"
        handoff = live_ops_handoff_status(symbol)
        return {
            "action": "live_ops_handoff",
            "status": handoff.get("status"),
            "symbol": handoff.get("symbol"),
            "ready_for_live_order": handoff.get("ready_for_live_order"),
            "blocker_count": len(handoff.get("blockers") or []),
            "blockers": (handoff.get("blockers") or [])[:12],
            "evidence_paths": handoff.get("evidence_paths") or {},
            "command_groups": handoff.get("command_groups") or [],
            "ai_commands": handoff.get("ai_commands") or [],
            "safety_note": handoff.get("safety_note"),
        }
    if action_type == "server_live_readiness_run":
        options = {
            "dry_run": coerce_bool(action.get("dry_run", True)),
            "run_testnet_drill": coerce_bool(action.get("run_testnet_drill", False)),
            "allow_testnet_placement": coerce_bool(action.get("allow_testnet_placement", False)),
            "skip_full_checks": coerce_bool(action.get("skip_full_checks", False)),
            "skip_strategy_sweep": coerce_bool(action.get("skip_strategy_sweep", False)),
            "strict": coerce_bool(action.get("strict", False)),
            "testnet_mode": action.get("testnet_mode") or "binance_testnet_validate",
            "target_cycles": int(safe_float(action.get("target_cycles"), 2)),
            "interval_seconds": int(safe_float(action.get("interval_seconds"), 1)),
            "timeout_seconds": int(safe_float(action.get("timeout_seconds"), 120)),
        }
        if not options["dry_run"]:
            options["target_cycles"] = max(1, options["target_cycles"])
            options["interval_seconds"] = max(1, options["interval_seconds"])
            options["timeout_seconds"] = max(300, options["timeout_seconds"])
        status = start_server_live_readiness(options)
        return {"action": "server_live_readiness_run", "options": options, "status": status}
    if action_type == "server_bundle":
        bundle = create_server_bundle()
        return {
            "action": "server_bundle",
            "bundle_path": bundle.get("bundle_path"),
            "download_name": bundle.get("download_name"),
            "sha256": bundle.get("sha256"),
            "size_bytes": bundle.get("size_bytes"),
        }
    if action_type == "live_launch_kit":
        kit = create_live_launch_kit()
        return {
            "action": "live_launch_kit",
            "kit_path": kit.get("kit_path"),
            "download_name": kit.get("download_name"),
            "sha256": kit.get("sha256"),
            "bytes": kit.get("bytes"),
            "file_count": kit.get("file_count"),
            "server_bundle": kit.get("server_bundle"),
            "excluded": kit.get("excluded"),
        }
    if action_type == "live_env_pack":
        pack = create_live_env_pack()
        return {
            "action": "live_env_pack",
            "pack_path": pack.get("pack_path"),
            "download_name": pack.get("download_name"),
            "sha256": pack.get("sha256"),
            "bytes": pack.get("bytes"),
            "file_count": pack.get("file_count"),
            "stages": pack.get("stages"),
            "excluded": pack.get("excluded"),
        }
    if action_type == "server_audit":
        readiness = deployment_readiness()
        gate = go_live_gate_status()
        operator = ai_operator_status()
        server_runner = server_live_readiness_status()
        env_profile = live_env_profile_status()
        return {
            "action": "server_audit",
            "ok": True,
            "generated_at": utc_now(),
            "readiness": readiness.get("overall"),
            "go_live_gate": ai_operator_compact_gate(gate),
            "ai_operator_ready": operator.get("ready"),
            "server_live_readiness": {
                "status": server_runner.get("status"),
                "running": server_runner.get("running"),
                "last_report_path": server_runner.get("last_report_path"),
                "last_error": server_runner.get("last_error"),
            },
            "live_env_profile": {
                "status": env_profile.get("status"),
                "target": env_profile.get("target"),
                "missing_required_vars": env_profile.get("missing_required_vars"),
            },
            "latest_go_live_report": ai_operator_latest_report_path("go-live-report-*.json"),
            "latest_server_go_live_audit": ai_operator_latest_report_path("server-go-live-audit-*.json"),
            "latest_server_bundle": ai_operator_latest_report_path("server-bundles/*.zip"),
            "latest_live_env_pack": ai_operator_latest_report_path("live-env-packs/*.zip"),
            "latest_live_launch_kit": ai_operator_latest_report_path("live-launch-kits/*.zip"),
        }
    raise ValueError(f"不支持的系统动作：{action_type or '-'}")


def apply_ai_operator_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for action in actions:
        action_type = str(action.get("type") or action.get("action") or "").lower().strip()
        if action_type in {
            "readiness",
            "go_live_gate",
            "go_live_report",
            "final_live_ready",
            "live_pilot",
            "live_pilot_postflight",
            "live_blocker_resolution",
            "live_pilot_run",
            "live_arm",
            "live_disarm",
            "live_attestation_save",
            "live_attestation_clear",
            "panic_stop",
            "server_live_readiness",
            "live_env_profile",
            "live_launch_plan",
            "live_ops_handoff",
            "live_launch_kit",
            "live_env_pack",
            "server_live_readiness_run",
            "server_bundle",
            "server_audit",
        }:
            results.append(ai_operator_system_action(action))
            continue
        if action_type == "shell":
            results.append(
                ai_operator_run_shell(
                    action.get("command") or action.get("content"),
                    action.get("cwd") or action.get("path") or ".",
                    action.get("timeout_seconds"),
                )
            )
            continue
        if action_type == "list":
            results.append(ai_operator_list_files(action.get("path") or ".", limit=80))
        elif action_type == "read":
            results.append(ai_operator_read_file(action.get("path")))
        elif action_type == "write":
            results.append(ai_operator_write_file(action.get("path"), action.get("content"), append=False))
        elif action_type == "append":
            results.append(ai_operator_write_file(action.get("path"), action.get("content"), append=True))
        elif action_type == "replace":
            results.append(
                ai_operator_replace_in_file(
                    action.get("path"),
                    action.get("old_text"),
                    action.get("new_text"),
                )
            )
        elif action_type == "patch":
            results.append(ai_operator_apply_patch_action(action.get("path"), action.get("content")))
        elif action_type in {"restore", "restore_snapshot"}:
            results.append(
                ai_operator_restore_snapshot(
                    action.get("snapshot_path") or action.get("path"),
                    action.get("target_path"),
                )
            )
        else:
            raise ValueError(f"不支持的 AI 操作员动作：{action_type or '-'}")
    return results


def parse_ai_operator_direct_actions(message: str) -> list[dict[str, Any]] | None:
    text = message.strip()
    if not text:
        return None
    if text.startswith("{"):
        payload = json.loads(text)
        actions = payload.get("actions") if isinstance(payload, dict) else None
        if isinstance(actions, list):
            return actions
    if text.startswith("/list"):
        return [{"type": "list", "path": text.removeprefix("/list").strip() or "."}]
    if text.startswith("/readiness"):
        return [{"type": "readiness"}]
    if text.startswith("/go-live-report"):
        return [{"type": "go_live_report"}]
    if text.startswith("/go-live") or text.startswith("/gate"):
        return [{"type": "go_live_gate"}]
    if text.startswith("/final-live-ready"):
        parts = text.removeprefix("/final-live-ready").strip().split()
        return [
            {
                "type": "final_live_ready",
                "require_armed": "--prearm" not in parts,
                "require_ai_operator": "--skip-ai-operator" not in parts,
            }
        ]
    if text.startswith("/live-pilot-run"):
        parts = text.removeprefix("/live-pilot-run").strip().split()
        symbol = parts[0] if parts else "BTCUSDT"
        confirmation = ""
        for index, part in enumerate(parts):
            if part in {"--confirm", "--confirmation"} and index + 1 < len(parts):
                confirmation = parts[index + 1]
        return [{"type": "live_pilot_run", "symbol": symbol, "confirmation": confirmation}]
    if text.startswith("/live-postflight") or text.startswith("/live-pilot-postflight"):
        command = "/live-postflight" if text.startswith("/live-postflight") else "/live-pilot-postflight"
        parts = text.removeprefix(command).strip().split()
        options: dict[str, Any] = {"type": "live_pilot_postflight", "symbol": parts[0] if parts else "BTCUSDT"}
        for index, part in enumerate(parts):
            if part == "--run-id" and index + 1 < len(parts):
                options["run_id"] = parts[index + 1]
        return [options]
    if text.startswith("/resolve-live-blockers") or text.startswith("/live-blockers"):
        command = "/resolve-live-blockers" if text.startswith("/resolve-live-blockers") else "/live-blockers"
        parts = text.removeprefix(command).strip().split()
        return [{"type": "live_blocker_resolution", "symbol": parts[0] if parts else "BTCUSDT"}]
    if text.startswith("/live-pilot"):
        parts = text.removeprefix("/live-pilot").strip().split()
        return [{"type": "live_pilot", "symbol": parts[0] if parts else "BTCUSDT"}]
    if text.startswith("/live-arm"):
        parts = text.removeprefix("/live-arm").strip().split()
        options: dict[str, Any] = {
            "type": "live_arm",
            "confirmation": "",
            "actor": "ai_operator",
            "reason": "ai_operator_live_arm",
        }
        for index, part in enumerate(parts):
            if part in {"--confirm", "--confirmation"} and index + 1 < len(parts):
                options["confirmation"] = parts[index + 1]
            elif part == "--actor" and index + 1 < len(parts):
                options["actor"] = parts[index + 1]
            elif part in {"--reason", "--note"} and index + 1 < len(parts):
                options["reason"] = parts[index + 1]
            elif part in {"--ttl", "--ttl-seconds"} and index + 1 < len(parts):
                options["ttl_seconds"] = parts[index + 1]
            elif part == "--ttl-minutes" and index + 1 < len(parts):
                options["ttl_minutes"] = parts[index + 1]
        return [options]
    if text.startswith("/live-disarm"):
        parts = text.removeprefix("/live-disarm").strip().split()
        options = {"type": "live_disarm", "reason": "ai_operator_live_disarm"}
        for index, part in enumerate(parts):
            if part in {"--reason", "--note"} and index + 1 < len(parts):
                options["reason"] = parts[index + 1]
        return [options]
    if text.startswith("/live-attestation-clear") or text.startswith("/clear-live-attestation"):
        command = "/live-attestation-clear" if text.startswith("/live-attestation-clear") else "/clear-live-attestation"
        parts = text.removeprefix(command).strip().split()
        options = {"type": "live_attestation_clear", "reason": "ai_operator_live_attestation_clear"}
        for index, part in enumerate(parts):
            if part in {"--reason", "--note"} and index + 1 < len(parts):
                options["reason"] = parts[index + 1]
        return [options]
    if text.startswith("/live-attest"):
        parts = text.removeprefix("/live-attest").strip().split()
        options = {
            "type": "live_attestation_save",
            "confirmation": "",
            "actor": "ai_operator",
            "note": "ai_operator_live_attestation",
            "accepted_all": True,
        }
        for index, part in enumerate(parts):
            if part in {"--confirm", "--confirmation"} and index + 1 < len(parts):
                options["confirmation"] = parts[index + 1]
            elif part == "--actor" and index + 1 < len(parts):
                options["actor"] = parts[index + 1]
            elif part in {"--note", "--reason"} and index + 1 < len(parts):
                options["note"] = parts[index + 1]
            elif part == "--not-accepted-all":
                options["accepted_all"] = False
        return [options]
    if text.startswith("/panic-stop") or text.startswith("/panic"):
        command = "/panic-stop" if text.startswith("/panic-stop") else "/panic"
        parts = text.removeprefix(command).strip().split()
        options: dict[str, Any] = {
            "type": "panic_stop",
            "confirmation": "",
            "reason": "ai_operator_panic_stop",
            "cancel_orders": "--no-cancel" not in parts,
            "cancel_exchange_open_orders": "--no-exchange-cancel" not in parts,
            "flatten_positions": "--flatten" in parts,
            "flatten_confirmation": "",
            "reconcile": "--no-reconcile" not in parts,
        }
        for index, part in enumerate(parts):
            if part in {"--confirm", "--confirmation"} and index + 1 < len(parts):
                options["confirmation"] = parts[index + 1]
            elif part == "--reason" and index + 1 < len(parts):
                options["reason"] = parts[index + 1]
            elif part in {"--flatten-confirm", "--flatten-confirmation"} and index + 1 < len(parts):
                options["flatten_confirmation"] = parts[index + 1]
        return [options]
    if text.startswith("/server-readiness-run"):
        parts = text.removeprefix("/server-readiness-run").strip().split()
        options: dict[str, Any] = {
            "type": "server_live_readiness_run",
            "dry_run": "--real" not in parts,
            "run_testnet_drill": "--testnet" in parts,
            "allow_testnet_placement": "--allow-testnet-placement" in parts,
            "skip_full_checks": "--skip-full-checks" in parts,
            "skip_strategy_sweep": "--skip-strategy-sweep" in parts,
            "strict": "--strict" in parts,
        }
        for index, part in enumerate(parts):
            if part in {"--cycles", "--target-cycles"} and index + 1 < len(parts):
                options["target_cycles"] = parts[index + 1]
            elif part in {"--interval", "--interval-seconds"} and index + 1 < len(parts):
                options["interval_seconds"] = parts[index + 1]
            elif part in {"--timeout", "--timeout-seconds"} and index + 1 < len(parts):
                options["timeout_seconds"] = parts[index + 1]
            elif part in {"--mode", "--testnet-mode"} and index + 1 < len(parts):
                options["testnet_mode"] = parts[index + 1]
        return [options]
    if text.startswith("/server-readiness"):
        return [{"type": "server_live_readiness"}]
    if text.startswith("/env-audit") or text.startswith("/live-env"):
        parts = text.split()
        target = parts[1] if len(parts) > 1 else "live_guarded"
        return [{"type": "live_env_profile", "target": target}]
    if text.startswith("/launch-plan") or text.startswith("/live-plan"):
        return [{"type": "live_launch_plan"}]
    if text.startswith("/handoff") or text.startswith("/live-handoff"):
        parts = text.split()
        return [{"type": "live_ops_handoff", "symbol": parts[1] if len(parts) > 1 else "BTCUSDT"}]
    if text.startswith("/launch-kit") or text.startswith("/live-kit"):
        return [{"type": "live_launch_kit"}]
    if text.startswith("/env-pack") or text.startswith("/live-env-pack"):
        return [{"type": "live_env_pack"}]
    if text.startswith("/bundle"):
        return [{"type": "server_bundle"}]
    if text.startswith("/server-audit"):
        return [{"type": "server_audit"}]
    if text.startswith("/read"):
        return [{"type": "read", "path": text.removeprefix("/read").strip()}]
    if text.startswith("/write"):
        first_line, _, content = text.partition("\n")
        return [{"type": "write", "path": first_line.removeprefix("/write").strip(), "content": content}]
    if text.startswith("/append"):
        first_line, _, content = text.partition("\n")
        return [{"type": "append", "path": first_line.removeprefix("/append").strip(), "content": content}]
    if text.startswith("/replace"):
        first_line, _, content = text.partition("\n")
        old_text, separator, new_text = content.partition("\n---\n")
        if not separator:
            raise ValueError("/replace 用法：/replace <path>\\n<old_text>\\n---\\n<new_text>")
        return [
            {
                "type": "replace",
                "path": first_line.removeprefix("/replace").strip(),
                "old_text": old_text,
                "new_text": new_text,
            }
        ]
    if text.startswith("/patch"):
        first_line, _, content = text.partition("\n")
        path = first_line.removeprefix("/patch").strip()
        if not content.strip() and path.startswith("*** Begin Patch"):
            content = path
            path = ""
        if not content.strip():
            raise ValueError("/patch usage: /patch [path]\\n*** Begin Patch ... or unified hunk lines")
        return [{"type": "patch", "path": path, "content": content}]
    if text.startswith("/restore"):
        parts = text.removeprefix("/restore").strip().split()
        if not parts:
            raise ValueError("/restore 用法：/restore <snapshot_path> [target_path]")
        return [
            {
                "type": "restore_snapshot",
                "snapshot_path": parts[0],
                "target_path": parts[1] if len(parts) > 1 else "",
            }
        ]
    if text.startswith("/shell"):
        first_line, _, content = text.partition("\n")
        command = content.strip() or first_line.removeprefix("/shell").strip()
        return [{"type": "shell", "command": command, "cwd": ".", "timeout_seconds": AI_OPERATOR_SHELL_TIMEOUT_SECONDS}]
    if text.startswith("/run"):
        first_line, _, content = text.partition("\n")
        command = content.strip() or first_line.removeprefix("/run").strip()
        return [{"type": "shell", "command": command, "cwd": ".", "timeout_seconds": AI_OPERATOR_SHELL_TIMEOUT_SECONDS}]
    if text.startswith("/help"):
        return []
    if text.startswith("/state"):
        return [{"type": "read", "path": "README.md"}]
    return None


def ai_operator_status() -> dict[str, Any]:
    model_provider = AI_OPERATOR_PROVIDER in {"openai", "codex"}
    key_ready = bool(OPENAI_API_KEY) if model_provider else AI_OPERATOR_PROVIDER == "rules"
    return {
        "enabled": AI_OPERATOR_ENABLED,
        "provider": AI_OPERATOR_PROVIDER,
        "model": AI_OPERATOR_MODEL if AI_OPERATOR_PROVIDER != "rules" else "local_operator_rules",
        "ready": AI_OPERATOR_ENABLED and (AI_OPERATOR_PROVIDER == "rules" or key_ready),
        "key_present": bool(OPENAI_API_KEY) if model_provider else False,
        "model_provider": "openai_responses" if model_provider else "local_rules",
        "workspace_root": str(AI_OPERATOR_WORKSPACE_ROOT),
        "allow_file_read": AI_OPERATOR_ALLOW_FILE_READ,
        "allow_file_write": AI_OPERATOR_ALLOW_FILE_WRITE,
        "allow_shell": AI_OPERATOR_ALLOW_SHELL,
        "apply_model_file_actions": AI_OPERATOR_APPLY_MODEL_FILE_ACTIONS,
        "max_read_bytes": AI_OPERATOR_MAX_READ_BYTES,
        "max_write_bytes": AI_OPERATOR_MAX_WRITE_BYTES,
        "snapshot_writes": AI_OPERATOR_SNAPSHOT_WRITES,
        "redacts_secrets": True,
        "snapshot_dir": str(AI_OPERATOR_SNAPSHOT_DIR),
        "max_snapshot_bytes": AI_OPERATOR_MAX_SNAPSHOT_BYTES,
        "backup_before_shell": AI_OPERATOR_BACKUP_BEFORE_SHELL,
        "shell_backup_dir": str(AI_OPERATOR_SHELL_BACKUP_DIR),
        "shell_backup_timeout_seconds": AI_OPERATOR_SHELL_BACKUP_TIMEOUT_SECONDS,
        "max_shell_output_bytes": AI_OPERATOR_MAX_SHELL_OUTPUT_BYTES,
        "shell_timeout_seconds": AI_OPERATOR_SHELL_TIMEOUT_SECONDS,
        "commands": [
            "/list <path>",
            "/readiness",
            "/go-live",
            "/go-live-report",
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
            "/env-audit [mvp_server|testnet_validate|testnet_place|live_guarded]",
            "/launch-plan",
            "/handoff [symbol]",
            "/launch-kit",
            "/env-pack",
            "/bundle",
            "/server-audit",
            "/read <path>",
            "/write <path>\\n<content>",
            "/append <path>\\n<content>",
            "/replace <path>\\n<old_text>\\n---\\n<new_text>",
            "/patch [path]\\n*** Begin Patch ...",
            "/restore <snapshot_path> [target_path]",
            "/shell <command>",
        ],
        "shell_boundary": "Shell 命令具有当前服务进程权限；只应在私有网络、强认证和审计开启时启用。",
        "boundary": "AI 操作员可协助改工作区文件；交易执行仍必须经过确定性风控、OMS 和显式模式开关；前端与审计会脱敏 API key、secret、token 和密码。",
    }


def compact_operator_context() -> dict[str, Any]:
    latest = get_latest_run()
    env_profile = live_env_profile_status()
    return {
        "system": {
            "environment": APP_ENV,
            "exchange_mode": EXCHANGE_MODE,
            "enabled_modes": enabled_modes(),
            "emergency_stop": get_setting("emergency_stop", "false") == "true",
        },
        "latest_run": latest,
        "risk": risk_config(),
        "oms": oms_summary(get_orders(limit=25)),
        "ai_operator": ai_operator_status(),
        "live_env_profile": {
            key: env_profile.get(key)
            for key in ("status", "target", "missing_required_vars", "next_actions")
        },
    }


AI_OPERATOR_ACTION_TYPES = [
    "readiness",
    "go_live_gate",
    "go_live_report",
    "final_live_ready",
    "live_pilot",
    "live_pilot_postflight",
    "live_blocker_resolution",
    "live_pilot_run",
    "live_arm",
    "live_disarm",
    "live_attestation_save",
    "live_attestation_clear",
    "panic_stop",
    "server_live_readiness",
    "live_env_profile",
    "live_launch_plan",
    "live_ops_handoff",
    "live_launch_kit",
    "live_env_pack",
    "server_live_readiness_run",
    "server_bundle",
    "server_audit",
    "list",
    "read",
    "write",
    "append",
    "replace",
    "patch",
    "restore_snapshot",
    "shell",
]


def ai_operator_response_schema() -> dict[str, Any]:
    action_properties: dict[str, Any] = {
        "type": {"type": "string", "enum": AI_OPERATOR_ACTION_TYPES},
        "path": {"type": "string"},
        "snapshot_path": {"type": "string"},
        "target_path": {"type": "string"},
        "content": {"type": "string"},
        "old_text": {"type": "string"},
        "new_text": {"type": "string"},
        "command": {"type": "string"},
        "cwd": {"type": "string"},
        "timeout_seconds": {"type": "number"},
        "symbol": {"type": "string"},
        "run_id": {"type": "string"},
        "target": {"type": "string"},
        "testnet_mode": {"type": "string"},
        "actor": {"type": "string"},
        "note": {"type": "string"},
        "confirmation": {"type": "string"},
        "reason": {"type": "string"},
        "ttl_seconds": {"type": "number"},
        "ttl_minutes": {"type": "number"},
        "accepted_all": {"type": "boolean"},
        "cancel_orders": {"type": "boolean"},
        "cancel_exchange_open_orders": {"type": "boolean"},
        "flatten_positions": {"type": "boolean"},
        "flatten_confirmation": {"type": "string"},
        "reconcile": {"type": "boolean"},
        "require_armed": {"type": "boolean"},
        "require_ai_operator": {"type": "boolean"},
        "dry_run": {"type": "boolean"},
        "run_testnet_drill": {"type": "boolean"},
        "allow_testnet_placement": {"type": "boolean"},
        "skip_full_checks": {"type": "boolean"},
        "skip_strategy_sweep": {"type": "boolean"},
        "strict": {"type": "boolean"},
        "target_cycles": {"type": "number"},
        "interval_seconds": {"type": "number"},
        "rationale": {"type": "string"},
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "reply": {"type": "string"},
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": action_properties,
                    "required": list(action_properties.keys()),
                },
            },
        },
        "required": ["reply", "actions"],
    }


def call_openai_operator(message: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    history_text = "\n".join(
        f"{item['role']}: {item['content'][:1200]}"
        for item in history[-8:]
    )
    payload = {
        "model": AI_OPERATOR_MODEL,
        "input": [
            {
                "role": "system",
                "content": (
                    "你是这个加密合约交易系统的 AI 操作员。你可以帮助用户理解系统、规划实盘前缺口，"
                    "并在允许时通过文件动作修改工作区文件。不要索要或输出 API secret。"
                    "不要绕过风控或 OMS 直接下单。文件动作只能使用 JSON 中的 actions 字段表达。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "current_context": compact_operator_context(),
                        "recent_history": history_text,
                        "user_message": message,
                        "available_actions": AI_OPERATOR_ACTION_TYPES,
                        "model_actions_auto_apply": AI_OPERATOR_APPLY_MODEL_FILE_ACTIONS,
                        "action_defaults": {
                            "unused_string": "",
                            "unused_number": 0,
                            "unused_boolean": False,
                            "live_env_profile_targets": ["mvp_server", "testnet_validate", "testnet_place", "live_guarded"],
                            "testnet_modes": ["binance_testnet_validate", "binance_testnet_place_order"],
                            "live_arm_requires_confirmation": "ARM_LIVE_TRADING",
                            "live_attestation_requires_confirmation": "LIVE_ATTESTATION_CONFIRMED",
                            "panic_stop_requires_confirmation": "PANIC_STOP",
                            "live_pilot_run_requires_confirmation": "LAUNCH_LIVE_PILOT",
                            "flatten_requires_confirmation": "FLATTEN_POSITIONS",
                        },
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "ai_operator_response",
                "strict": True,
                "schema": ai_operator_response_schema(),
            }
        },
        "temperature": 0.2,
        "store": False,
    }
    response = http_post_json(
        f"{OPENAI_BASE_URL}/responses",
        payload,
        {"Authorization": f"Bearer {OPENAI_API_KEY}"},
    )
    return json.loads(extract_openai_output_text(response))


def build_rule_operator_reply(message: str) -> dict[str, Any]:
    return {
        "reply": (
            "我现在以本地规则操作员模式运行。你可以直接输入 /readiness、/go-live、/final-live-ready、"
            "/server-readiness、/server-readiness-run、/env-audit、/launch-plan、/bundle、/server-audit 查看和推进实盘准入；也可以输入 "
            "/list、/read、/write、/append、/replace、/patch、/restore 或 /shell，让我查看、修改当前工作区文件并执行命令。"
            "配置 AI_OPERATOR_PROVIDER=codex 或 openai，并设置 OPENAI_API_KEY 后，我可以用模型对话生成结构化文件动作。"
            "交易实盘仍必须通过 Testnet、私有账户流、真实订单对账、强制风控和上线门禁。"
        ),
        "actions": [],
    }


def handle_ai_operator_chat(message: str) -> dict[str, Any]:
    if not AI_OPERATOR_ENABLED:
        raise ValueError("AI 操作员未启用。")
    clean_message = str(message or "").strip()
    if not clean_message:
        raise ValueError("消息不能为空。")
    user_message = insert_ai_operator_message("user", clean_message)
    action_results: list[dict[str, Any]] = []
    status = "ok"
    try:
        direct_actions = parse_ai_operator_direct_actions(clean_message)
        if direct_actions is not None:
            if direct_actions:
                action_results = ai_operator_redact_sensitive_obj(apply_ai_operator_actions(direct_actions))
                reply = "已执行文件动作：\n" + json.dumps(action_results, ensure_ascii=False, indent=2)
            else:
                reply = build_rule_operator_reply(clean_message)["reply"]
        elif AI_OPERATOR_PROVIDER in {"openai", "codex"} and OPENAI_API_KEY:
            model_result = call_openai_operator(clean_message, get_ai_operator_messages(limit=16))
            proposed_actions = model_result.get("actions") or []
            if proposed_actions and AI_OPERATOR_APPLY_MODEL_FILE_ACTIONS:
                action_results = ai_operator_redact_sensitive_obj(apply_ai_operator_actions(proposed_actions))
                reply = model_result.get("reply", "") + "\n\n已自动执行模型文件动作。"
            elif proposed_actions:
                action_results = ai_operator_redact_sensitive_obj([{"action": "proposed_only", "items": proposed_actions}])
                reply = model_result.get("reply", "") + "\n\n模型提出了文件动作，但当前未启用自动执行。"
            else:
                reply = model_result.get("reply", "已收到。")
        else:
            reply = build_rule_operator_reply(clean_message)["reply"]
    except Exception as exc:
        status = "error"
        safe_error = ai_operator_redact_sensitive_text(str(exc))
        reply = f"AI 操作员执行失败：{exc.__class__.__name__}: {safe_error}"
        action_results = [{"action": "error", "error_type": exc.__class__.__name__, "error": safe_error}]
    reply = ai_operator_redact_sensitive_text(reply)
    action_results = ai_operator_redact_sensitive_obj(action_results)
    assistant_message = insert_ai_operator_message(
        "assistant",
        reply,
        status=status,
        actions=action_results,
        metadata={"responding_to": user_message["id"]},
    )
    insert_event(
        "ai-operator",
        "system" if status == "ok" else "error",
        "AI Operator",
        "AI 操作员对话已记录",
        reply[:800],
        {"message_id": assistant_message["id"], "actions": action_results, "status": ai_operator_status()},
    )
    return {
        "message": assistant_message,
        "history": get_ai_operator_messages(limit=40),
        "status": ai_operator_status(),
    }


def latest_event_payload(events: list[dict[str, Any]], actor: str) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("actor") == actor:
            payload = event.get("payload")
            return payload if isinstance(payload, dict) else None
    return None


def research_artifacts_for_run(events: list[dict[str, Any]], latest_run: dict[str, Any] | None) -> dict[str, Any]:
    market = latest_event_payload(events, "Market Data") or {}
    market_score = latest_event_payload(events, "Market Analyst") or {}
    sentiment = latest_event_payload(events, "Sentiment Analyst") or {}
    news = latest_event_payload(events, "News Analyst") or {}
    intent = latest_event_payload(events, "Trader Agent") or {}
    risk = latest_event_payload(events, "Risk Engine") or {}
    has_run = bool(latest_run and events)
    score = float(market_score.get("score") or 0)
    bull_case = (
        "多头观点：价格动量、资金费率、持仓量或多空比中存在可交易线索。"
        if score >= 0
        else "多头观点：当前信号偏弱，只能作为反弹候选，不能直接升级为订单。"
    )
    bear_case = (
        "空头观点：综合评分偏弱或证据不足，需优先防止过度交易。"
        if score < 0.8
        else "空头观点：即使评分偏强，也必须检查资金费率、清算压力和止损距离。"
    )

    artifacts = [
        {
            "id": "reference-architecture-map",
            "role": "参考架构映射",
            "status": "active",
            "reference": "Anthropic + TradingAgents",
            "summary": "Anthropic 路径映射为用户请求、Agent/Managed Agent、Skills/Commands、MCP Connectors、研究工件、人工签核；TradingAgents 路径映射为市场数据、分析师团队、牛熊辩论、交易代理、风控/组合经理、模拟交易与检查点。",
            "evidence": ["研究工件是交接格式", "人工签核保留为上线门槛", "模拟/纸交易先于真实交易", "七类角色映射：基本面、情绪、新闻、技术、研究员、交易员、风控经理"],
            "gaps": ["Managed Agent 部署", "MCP 外部数据连接器", "独立组合经理审批流"],
        },
        {
            "id": "boundary",
            "role": "研究/执行边界",
            "status": "active",
            "reference": "Anthropic 金融服务模板",
            "summary": "代理只产出研究工件和结构化交易意图；确定性风控、OMS 和执行器才允许处理订单边界。",
            "evidence": ["AI 不接收交易所密钥", "TradeIntent 先经过风险检查", "实盘模式未启用"],
            "gaps": [],
        },
        {
            "id": "market-research",
            "role": "市场研究工件",
            "status": "ready" if market else "waiting",
            "reference": "TradingAgents Analyst Team",
            "summary": (
                f"使用 {source_label(market.get('data_source'))}、资金费率、持仓量、多空比和盘口深度形成评分 "
                f"{market_score.get('score', '-')}。"
                if market
                else "等待最新行情快照。"
            ),
            "evidence": [
                f"交易对={market.get('symbol', '-')}",
                f"标记价格={market.get('mark_price', '-')}",
                f"资金费率={market.get('funding_rate_pct', '-')}%",
                f"多空比={market.get('long_short_ratio', '-')}",
            ],
            "gaps": ["未接入基本面数据"] if market else ["尚无运行事件"],
        },
        {
            "id": "sentiment-news",
            "role": "情绪与事件工件",
            "status": "partial" if has_run else "waiting",
            "reference": "Anthropic market-researcher guardrails",
            "summary": (
                "已使用交易所多空比作为情绪代理；实时新闻、社媒和研报连接器仍未启用，不能声称已核验外部事件。"
                if has_run
                else "等待工作流生成情绪与事件记录。"
            ),
            "evidence": [
                f"情绪定位={sentiment.get('sentiment_bias', '-')}",
                f"实时新闻启用={source_label(str(news.get('live_news_enabled', False)))}",
            ],
            "gaps": ["实时新闻", "社媒情绪", "第三方研报来源"],
        },
        {
            "id": "source-guardrails",
            "role": "来源与提示注入护栏",
            "status": "active",
            "reference": "Anthropic market-researcher",
            "summary": "研究先界定范围，再进入行业概览、竞争分析、可比分析和想法生成类技能；第三方报告、新闻、网页和发行方材料只作为待提取数据，不允许成为系统指令；无法取得来源的数据必须显式标为未接入、未验证或 UNSOURCED，关键研究工件需要人工复核。",
            "evidence": ["实时新闻缺口已记录", "无来源数据不参与下单", "外部文本不进入执行层"],
            "gaps": ["来源引用字段", "UNSOURCED 标记流", "行业概览/竞争分析/可比分析/想法生成技能", "新闻/研报连接器"],
        },
        {
            "id": "bull-bear-debate",
            "role": "牛熊研究辩论",
            "status": "ready" if market else "waiting",
            "reference": "TradingAgents Bull/Bear Research Debate",
            "summary": f"{bull_case} {bear_case} 当前结论必须以结构化工件交给交易代理，不能依赖长对话历史。",
            "evidence": [f"综合评分={market_score.get('score', '-')}", f"清算压力={source_label(market.get('liquidation_pressure'))}", f"资金费率={market.get('funding_rate_pct', '-')}%"],
            "gaps": ["独立牛方代理", "独立熊方代理", "辩论轮次成本统计"],
        },
        {
            "id": "structured-intent",
            "role": "结构化通信工件",
            "status": "ready" if intent else "waiting",
            "reference": "TradingAgents structured communication",
            "summary": (
                f"交易代理输出 {zh_side(intent.get('side'))}，置信度 {intent.get('confidence', '-')}，"
                f"来源 {source_label(intent.get('provider'))} / {source_label(intent.get('model'))}。"
                if intent
                else "等待 TradeIntent。"
            ),
            "evidence": ["结构=TradeIntent", f"周期={intent.get('time_horizon', '-')}", f"止损={intent.get('stop_loss', '-')}"],
            "gaps": [],
        },
        {
            "id": "risk-review",
            "role": "风控复核工件",
            "status": risk.get("status", "waiting"),
            "reference": "Portfolio Manager / Risk Team",
            "summary": (
                f"确定性风控结果为 {zh_status(risk.get('status'))}；任何订单动作前都必须通过该复核。"
                if risk
                else "等待风控输出。"
            ),
            "evidence": [f"检查项数量={len(risk.get('checks', []))}" if risk else "检查项数量=0"],
            "gaps": [],
        },
        {
            "id": "decision-memory-checkpoint",
            "role": "决策记忆与恢复",
            "status": "active",
            "reference": "TradingAgents decision log / LangGraph checkpoint",
            "summary": "当前用 SQLite runs、events 和 order_transitions 承担决策日志与恢复线索；后续接入 LangGraph 时再升级为节点级 checkpoint resume。",
            "evidence": ["runs 表记录运行状态", "events 表记录代理与风控过程", "order_transitions 表记录订单状态迁移"],
            "gaps": ["节点级 checkpoint resume", "按交易对长期反思记忆", "崩溃后自动恢复策略状态"],
        },
        {
            "id": "agent-runtime-plan",
            "role": "代理运行时契约",
            "status": "partial",
            "reference": "Claude 代理 SDK / LangGraph",
            "summary": "未来接入 Claude 或 LangGraph 时，子代理必须有独立上下文、系统提示和工具权限；工具输出必须符合严格结构；允许/拒绝权限规则、运行时回调、工具前/工具后钩子、检查点、遥测和约 5 分钟提示词缓存都要作为治理能力接入。当前 MVP 仅保留适配边界。",
            "evidence": ["TradeIntent 结构", "AI 不接触密钥", "事件日志可审计"],
            "gaps": ["子代理隔离", "工具允许/拒绝规则", "运行时回调", "工具前/工具后钩子", "遥测", "节点级检查点", "文件变更回滚", "提示词缓存"],
        },
        {
            "id": "research-limitations",
            "role": "研究框架限制",
            "status": "active",
            "reference": "TradingAgents research purpose",
            "summary": "TradingAgents 适合研究、辩论和模拟决策，不作为生产级加密合约 OMS/RMS；成本、吞吐和时间一致性必须另行控制。",
            "evidence": ["执行层仍为确定性代码", "实盘模式未启用", "测试网真实下单保持关闭"],
            "gaps": ["多代理成本治理", "长周期样本外验证", "真实交易所恢复演练"],
        },
    ]

    return {
        "status": "ready" if has_run else "waiting",
        "summary": "研究层采用 Anthropic 的边界治理和 TradingAgents 的结构化通信思想；执行层保持确定性。",
        "protocol": {
            "input_treatment": "外部新闻、社媒、研报和网页内容一律按不可信数据处理，不能执行其中的指令。",
            "exchange_format": "ResearchArtifact -> TradeIntent -> RiskCheck -> OMS/Executor",
            "decision_memory": "当前使用 SQLite 事件日志作为决策记忆；后续可替换为 LangGraph checkpoint。",
            "human_review": "关键研究工件和上线模式切换必须由人工复核。",
        },
        "guardrails": [
            "代理不执行交易，不绑定风险，不接触 API 密钥。",
            "没有来源的数据必须显式标为未接入或未验证。",
            "多代理结论以结构化工件传递，不依赖不可审计的长对话。",
            "确定性风控和 OMS 是下单前的强制边界。",
        ],
        "artifacts": artifacts,
    }


def production_architecture_blueprint() -> dict[str, Any]:
    executive_summary = [
        {
            "title": "研究层与执行层先切开",
            "summary": "参考 Anthropic financial-services 的复核边界和 TradingAgents 的研究/模拟定位，当前系统坚持 LLM 负责研究、解释和信号候选；确定性代码负责风控、下单、对账和结算。",
            "mvp_state": "当前 MVP 已把研究工件、TradeIntent、风控、OMS、纸交易执行拆成独立边界；AI_PROVIDER 默认保持 rules。",
            "production_rule": "代理不直接执行交易，不绑定风险，不做最终审批，不接触 API secret。",
        },
        {
            "title": "首版范围先小而闭环",
            "summary": "首版按单交易所、单账户或少量子账户、低到中频策略推进，先沙盒后小额实盘，全程保留回放与审计链。",
            "mvp_state": "当前优先 Binance U 本位纸交易与 Binance Futures Testnet 验证；Bybit testnet、OKX API 模拟盘 x-simulated-trading: 1、Hyperliquid testnet API / WebSocket 作为后续适配参考。",
            "production_rule": "先打穿数据链路、风控、OMS、审计、UI 和真实 testnet 下单闭环，再讨论小额 live。",
        },
        {
            "title": "UI 是交易运营控制台",
            "summary": "界面不做单纯行情页，而是交易中台式控制台，把策略配置、回测、沙盒、实盘、告警、复盘、权限和密钥管理放到同一个工作台。",
            "mvp_state": "当前中文 UI 已展示行情、研究工件、风控、OMS、持仓、回测、调度、readiness、生产架构蓝图和验收门槛。",
            "production_rule": "桌面端承载完整运营工作流，移动端后续只保留状态、告警、紧急停机和仓位查看等低风险操作。",
        },
        {
            "title": "标准技术路线暂不前置重构",
            "summary": "标准版建议 Python + FastAPI、LangGraph 或 Anthropic Agent SDK、PostgreSQL + TimescaleDB、ClickHouse、NATS JetStream、Next.js、Lightweight Charts、ECharts、Monaco Editor、xterm.js。",
            "mvp_state": "当前阶段不迁移 FastAPI/Next/PostgreSQL/NATS，先稳定现有 stdlib Python 服务、SQLite、中文静态 UI、纸交易和 testnet 验证模式。",
            "production_rule": "若强调仿真/实盘一致性再评估 NautilusTrader；若强调参数扫描则继续增强 vectorbt/事件回放能力。",
        },
    ]
    project_goals_assumptions = {
        "title": "项目目标与假设",
        "default_target": "首阶段默认服务 1 到 5 名研究员/交易员，优先支持 1 家官方支持沙盒的合约交易所，先做低到中频方向性或事件驱动策略，再逐步扩展到多策略组合；LLM 输出必须先转成结构化信号，再进入确定性风控与下单链路。",
        "reasoning": "这些默认值用于在预算、合规、交易所范围和用户规模未指定时收窄风险；它们是本文设计建议，不是官方要求。",
        "assumption_defaults": [
            {
                "item": "目标用户规模",
                "current_status": "未指定",
                "options": "个人自营；小团队内用；多团队/多租户",
                "fit": "从个人工具到机构级平台差异极大，尤其体现在 RBAC、审计、子账户、审批流。",
                "recommended_default": "小团队内用",
            },
            {
                "item": "支持的交易所",
                "current_status": "未指定",
                "options": "单一 CEX；多 CEX；CEX + DEX/链上永续",
                "fit": "单一交易所最容易先把撮合语义、速率限制和回报事件跑顺。",
                "recommended_default": "单一 CEX",
            },
            {
                "item": "策略复杂度",
                "current_status": "未指定",
                "options": "模板策略；多策略组合；做市/高频/统计套利",
                "fit": "高频或做市会立刻把延迟、撮合、库存风控推到核心问题。",
                "recommended_default": "模板策略",
            },
            {
                "item": "预算",
                "current_status": "未指定",
                "options": "MVP；标准；企业级",
                "fit": "预算会直接影响是否做多活、KMS/HSM、专职 QA/DevOps、合规咨询。",
                "recommended_default": "标准偏 MVP",
            },
            {
                "item": "合规要求",
                "current_status": "未指定",
                "options": "个人自营；团队内部工具；对外服务/SaaS",
                "fit": "一旦对外提供服务，监管、KYC/AML、适当性与衍生品限制都要前置考虑。",
                "recommended_default": "团队内部工具",
            },
        ],
        "compliance_tiers": [
            {
                "tier": "个人或团队内部自营工具",
                "focus": "交易所条款、API 密钥安全、审计留痕与风险阈值。",
                "default_action": "当前 MVP 只按内部工具处理，保持 Basic Auth、服务端密钥、风控阈值和审计记录。",
            },
            {
                "tier": "多名用户使用的内部平台",
                "focus": "maker-checker、权限隔离、审批与留痕。",
                "default_action": "进入多用户前必须补 RBAC、审批流、子账户隔离和不可抵赖审计。",
            },
            {
                "tier": "对外平台化或 SaaS 服务",
                "focus": "FATF 的 VASP AML/CFT 指引、MiCA 授权与披露要求，以及类 CFD 杠杆限制、风险提示、强平和负余额保护。",
                "default_action": "首阶段不按 SaaS 设计；一旦对外服务，先做监管分类和合规咨询，再改架构。",
            },
        ],
        "exchange_selection": [
            {
                "venue": "Binance U 本位",
                "phase": "首选起步",
                "why": "Futures testnet 可用于验证，公共行情和本地订单簿同步规则清晰。",
                "engineering_notes": "当前 MVP 已接 Binance 公共行情、/fapi/v1/order/test 验证模式，以及显式开关保护下的真实 testnet 下单/查单/撤单。",
            },
            {
                "venue": "Bybit V5",
                "phase": "第二批 CEX 候选",
                "why": "orderLinkId、速率限制头和 testnet 路径说明较细。",
                "engineering_notes": "适合在 Binance 闭环稳定后验证 venue-specific adapter、幂等字段和限频器抽象。",
            },
            {
                "venue": "OKX",
                "phase": "第二批 CEX 候选",
                "why": "提供 API 模拟盘，要求 x-simulated-trading: 1，并提供 clOrdId、expTime、深度序列与校验机制。",
                "engineering_notes": "适合验证模拟环境 header、请求过期时间、checksum 和 prevSeqId/seqId 处理。",
            },
            {
                "venue": "Hyperliquid",
                "phase": "第二阶段链上永续候选",
                "why": "支持 testnet API 与 testnet WebSocket，更适合覆盖链上永续。",
                "engineering_notes": "加入前必须单独设计 API wallet、nonce、链上签名模型和账户隔离。",
            },
        ],
    }
    anthropic_reference_project = {
        "title": "Anthropic 参考项目拆解",
        "interpretation_premise": "这里的 Anthropic 参考项目不是一个面向加密合约自动交易的官方开源引擎；在本系统里，它指 anthropics/financial-services 官方金融服务代理模板 + Claude Agent SDK、subagents、tool use 与 MCP 能力栈。",
        "not_a_trading_terminal": "它不是现成的加密合约交易终端，也不是生产级 OMS/RMS；它更适合作为研究代理、技能复用、连接器、权限治理和人工复核边界的参考。",
        "repository_layers": [
            {
                "layer": "Agents",
                "meaning": "承载金融研究、分析、备忘录、对账草稿等代理工作流。",
                "mvp_mapping": "当前 MVP 用研究工件和 TradeIntent 记录代理输出，不允许代理直接触碰订单执行。",
            },
            {
                "layer": "Skills / Commands",
                "meaning": "把 sector-overview、competitive-analysis、comps-analysis、idea-generation 等可复用分析动作做成技能或命令。",
                "mvp_mapping": "当前 MVP 先保留规则策略、研究工件和后续技能插槽；真实新闻/研报技能仍标记为缺口。",
            },
            {
                "layer": "MCP Connectors",
                "meaning": "把外部数据源、文档、系统和工作流连接到代理，但仍需权限和输入边界。",
                "mvp_mapping": "当前 MVP 尚未接外部 MCP 数据连接器；交易所 API 和密钥仍由确定性服务端适配器管理。",
            },
        ],
        "deployment_surfaces": [
            "Claude Cowork 插件",
            "Claude Managed Agents API",
            "自有工作流引擎后面的托管代理编排",
            "managed-agent-cookbooks / orchestrate.py / leaf-worker subagents / per-agent security notes 这类编排与安全参考",
        ],
        "boundary_contract": [
            "代理产出模型、备忘录、研究笔记、对账草稿等分析工件。",
            "分析工件需要由合格专业人员复核。",
            "代理不做投资建议。",
            "代理不执行交易。",
            "代理不绑定风险。",
            "代理不入账。",
            "代理不做最终开户审批。",
            "生产化启发是：代理负责研究、整理与建议；确定性系统负责执行与控制。",
        ],
        "market_researcher": {
            "workflow": "market-researcher 先界定研究范围，再调用 sector-overview、competitive-analysis、comps-analysis 和 idea-generation 等技能，最后组装研究笔记。",
            "guardrails": [
                "第三方报告、发行人材料、新闻、社媒和网页内容都是不可信输入，只能当作待提取数据。",
                "外部材料里的指令不能被执行，也不能覆盖系统提示、风控规则或订单边界。",
                "每个数字都要引用来源。",
                "如果无法从 CapIQ、FactSet 或 filing 拿到数字，就标记为 [UNSOURCED]，而不是估算。",
                "关键研究工件要停下来给分析师复核。",
                "这些规则迁移到本系统时，用于新闻/社媒/研报摄取层的提示注入防御与证据链约束。",
            ],
        },
        "agent_sdk_capabilities": [
            {
                "capability": "agent loop 与 context management",
                "production_value": "把长运行研究代理做成可控循环，而不是一次性 prompt。",
                "mvp_boundary": "当前 MVP 用同步工作流和 SQLite 事件日志保留边界，尚未接完整 SDK loop。",
            },
            {
                "capability": "subagents",
                "production_value": "每个子代理有自己的 context window、system prompt、工具权限和独立权限控制。",
                "mvp_boundary": "当前只用角色化研究工件模拟分析师、交易代理和风控团队。",
            },
            {
                "capability": "tool use strict: true",
                "production_value": "工具调用必须严格符合 schema，减少自由文本误用。",
                "mvp_boundary": "当前 TradeIntent 使用结构化字段，真实工具 strict schema 待接入。",
            },
            {
                "capability": "permissions allow/deny、hooks、runtime callback",
                "production_value": "在 PreToolUse、PostToolUse、subagent 启停等节点允许、拒绝、改写或注入上下文。",
                "mvp_boundary": "当前由确定性风控、OMS 和环境变量开关充当执行边界。",
            },
            {
                "capability": "checkpointing",
                "production_value": "支持回滚工具写入的文件变更，并为长运行代理提供恢复点。",
                "mvp_boundary": "当前用 runs、events、order_transitions 作为审计和恢复线索。",
            },
            {
                "capability": "OpenTelemetry monitoring",
                "production_value": "让代理运行、工具调用和错误进入可观测链路。",
                "mvp_boundary": "当前 readiness 报告和事件日志可用，OTEL 未接入。",
            },
            {
                "capability": "prompt caching",
                "production_value": "缓存长前缀提示词，默认缓存寿命约 5 分钟，用于降低成本和延迟。",
                "mvp_boundary": "当前 AI_PROVIDER 默认 rules，无 LLM 成本路径；接入 LLM 后再加成本治理。",
            },
        ],
    }
    tradingagents_reference_project = {
        "title": "TradingAgents 参考项目拆解",
        "core_positioning": "TradingAgents 把多代理交易研究组织成模拟交易公司，适合做研究-辩论-决策-风控审批链路的原型验证，但不是生产级加密合约 OMS/RMS。",
        "simulated_company_roles": [
            {
                "role": "基本面分析师",
                "team": "Analyst Team",
                "responsibility": "整理基本面、资金面和长期叙事证据，形成结构化研究输入。",
            },
            {
                "role": "情绪分析师",
                "team": "Analyst Team",
                "responsibility": "分析市场情绪、仓位拥挤度和社媒倾向，输出可审计的情绪摘要。",
            },
            {
                "role": "新闻分析师",
                "team": "Analyst Team",
                "responsibility": "处理新闻、公告和事件驱动信息，并标记来源、时效和证据缺口。",
            },
            {
                "role": "技术分析师",
                "team": "Analyst Team",
                "responsibility": "分析价格、成交量、波动率和技术指标，给出结构化技术面结论。",
            },
            {
                "role": "研究员",
                "team": "Researcher Team",
                "responsibility": "组织 Bull / Bear Research Debate，把多方观点压缩成可比较的论证记录。",
            },
            {
                "role": "交易员",
                "team": "Trader Agents",
                "responsibility": "把研究结论转成交易候选和策略参数建议，但不绕过确定性风控。",
            },
            {
                "role": "风控经理",
                "team": "Risk Management Team",
                "responsibility": "复核风险、回撤、敞口和执行边界，并进入 Portfolio Manager 审批。",
            },
        ],
        "architecture_flow": [
            "市场/新闻/社媒/基本面数据",
            "Analyst Team",
            "Bull / Bear Research Debate",
            "Trader",
            "Risk Team / Portfolio Manager",
            "Simulated Exchange / Decision Log / Checkpoint",
        ],
        "portfolio_manager_approval": "README 补上 Portfolio Manager 审批流程：如果 Portfolio Manager 批准，订单才会被发送到 simulated exchange 并执行；本 MVP 映射为风控通过后也只进入纸交易或 test order 验证，不进入真实 live mode。",
        "structured_communication": {
            "why_it_matters": "TradingAgents 最值得借鉴的不是多代理数量，而是通信形式：过度依赖自然语言长对话容易产生 telephone effect，导致结论在转述中失真。",
            "protocol": "structured communication protocol",
            "preferred_outputs": [
                "结构化研究报告",
                "意见摘要",
                "置信度",
                "证据引用",
                "策略参数建议",
            ],
            "avoid": "不要把不可审计的自由文本长对话当作交易依据。",
            "mvp_mapping": "当前 MVP 使用 ResearchArtifact -> TradeIntent -> RiskCheck -> OMS/Executor，把研究层输出先压成结构化信号，再交给确定性风控和 OMS。",
        },
        "implementation_runtime": {
            "framework": "LangGraph",
            "graph_call": "TradingAgentsGraph().propagate()",
            "llm_provider_support": "支持多家 LLM provider，用于研究代理而不是下单热路径。",
            "decision_log": "decision log 总是开启，会把已完成的决策写入 ~/.tradingagents/memory/trading_memory.md，并在后续同 ticker 分析里注入反思。",
            "checkpoint_resume": "可选 checkpoint resume 由 LangGraph 在每个节点后保存状态；crash 后从 last successful node 恢复；每个 ticker 的 checkpoint 存在 SQLite 数据库。",
            "mvp_mapping": "当前 MVP 用 SQLite 的 runs、events、orders、order_transitions 和 backtests 保存决策记忆与恢复线索；后续接 LangGraph 时可迁移为节点级 checkpoint。",
        },
        "limitations": [
            {
                "limitation": "research purposes",
                "impact": "README 明确是 research purposes，模型输出不构成投资建议，也不能直接替代人工复核。",
            },
            {
                "limitation": "模型、温度、时段和数据质量敏感",
                "impact": "同一策略在不同 model、temperature、运行时间和数据质量下可能产生不同结论。",
            },
            {
                "limitation": "成本与吞吐",
                "impact": "论文报告每次预测约 11 次 LLM 调用 + 20 多次工具调用，因此只做了 3 个月回测；这说明 cost/throughput/time consistency 离生产化仍有距离。",
            },
            {
                "limitation": "生产缺口",
                "impact": "可以借组织形态和结构化产出，但不能把它直接当作加密合约实盘引擎或 live crypto perpetual engine。",
            },
        ],
        "borrow_do_not_copy": "借 TradingAgents 的组织形态、结构化报告、辩论式研究和节点级恢复，不直接套成生产交易引擎。",
    }
    reference_synthesis = {
        "title": "两类参考综合吸收点",
        "architecture_paths": [
            {
                "reference": "TradingAgents 参考架构",
                "steps": [
                    "市场/新闻/社媒/基本面数据",
                    "Analyst Team",
                    "Bull / Bear Research Debate",
                    "Trader",
                    "Risk Team / Portfolio Manager",
                    "Simulated Exchange / Decision Log / Checkpoint",
                ],
            },
            {
                "reference": "Anthropic 参考架构",
                "steps": [
                    "用户请求 / 工作流触发",
                    "Agent Plugin / Managed Agent",
                    "Skills / Commands",
                    "MCP Connectors",
                    "研究工件",
                    "人工签核",
                ],
            },
        ],
        "absorb_points": [
            {
                "source": "Anthropic",
                "point": "吸收技能复用、MCP 接入、权限与 hook、人工审核边界。",
            },
            {
                "source": "TradingAgents",
                "point": "吸收角色分工、结构化报告、辩论式研究和 checkpoint 恢复。",
            },
            {
                "source": "共同事实",
                "point": "代理系统更适合放在研究层和控制层，不适合直接进入撮合热路径。",
            },
            {
                "source": "生产缺口",
                "point": "两者都没有替你完成生产必需的 OMS、RMS、持仓结算、交易所对账、多用户 RBAC、审计不可抵赖、真仓故障恢复。",
            },
        ],
        "implementation_rule": "不能简单套壳；Anthropic 与 TradingAgents 只能作为上层研究与治理框架来吸收，生产交易能力必须由确定性执行层补齐。",
    }
    principles = [
        "吸收 Anthropic 的技能复用、MCP 接入、权限与钩子、人工审核边界。",
        "吸收 TradingAgents 的角色分工、结构化报告、辩论式研究和检查点恢复。",
        "代理系统只进入研究层和控制层，不进入撮合热路径。",
        "生产能力必须由确定性 OMS、RMS、持仓结算、交易所对账、RBAC、审计和故障恢复补齐。",
    ]
    planes = [
        {
            "id": "research",
            "name": "研究平面",
            "status": "partial",
            "responsibility": "生成结构化研究工件、证据缺口、辩论结论和 TradeIntent 候选。",
            "implemented": ["研究工件", "牛熊辩论摘要", "TradeIntent 结构", "AI/规则适配边界"],
            "gaps": ["真实新闻/社媒/研报连接器", "MCP 数据连接器", "Claude/LangGraph 子代理运行时", "多代理成本治理"],
        },
        {
            "id": "control",
            "name": "控制平面",
            "status": "partial",
            "responsibility": "管理策略版本、审批、RBAC、配置发布、调度和人工复核。",
            "implemented": ["中文 Web 控制台", "Basic Auth", "风控配置", "纸交易调度", "部署 readiness"],
            "gaps": ["SSO", "多用户 RBAC", "maker-checker 审批", "策略版本库", "发布审批流"],
        },
        {
            "id": "execution",
            "name": "执行平面",
            "status": "partial",
            "responsibility": "用确定性代码完成风控、OMS、交易所适配、持仓账本、结算和恢复。",
            "implemented": ["确定性风控", "纸交易执行", "OMS 对账", "持仓与 PnL 账本", "Binance 测试网参数验证"],
            "gaps": ["真实测试网下单", "venue-specific adapter 扩展", "订单簿 WS 同步", "撤改单状态机", "资金费/手续费结算", "真仓故障恢复"],
        },
        {
            "id": "observability",
            "name": "观测平面",
            "status": "partial",
            "responsibility": "提供日志、指标、告警、审计链、回放和生产运行报告。",
            "implemented": ["SQLite 事件日志", "订单状态迁移", "完整自检报告", "回测/参数/滚动验证"],
            "gaps": ["OpenTelemetry", "Prometheus/告警", "ClickHouse 审计查询", "事件总线重放", "事故恢复演练"],
        },
    ]
    components = [
        ("Web UI / Mobile Readonly", "Web UI / 移动只读", "control", "partial", "已有中文 Web 控制台；移动端只读事故视图未实现。"),
        ("API Gateway / BFF", "API 网关 / BFF", "control", "partial", "当前为单进程 HTTP API；未拆独立网关。"),
        ("SSO / RBAC / Approval", "SSO / RBAC / 审批", "control", "gap", "当前只有 Basic Auth；多用户角色和审批流未实现。"),
        ("Market Data Ingest", "行情采集", "research", "partial", "已有 Binance REST 快照；WS 增量和历史补数未实现。"),
        ("Normalizer / Sequencer", "标准化 / 序列器", "execution", "gap", "尚未实现订单簿序列校验和跨交易所标准化。"),
        ("Event Bus", "事件总线", "observability", "gap", "当前使用 SQLite 事件表；未接 NATS/JetStream。"),
        ("Agent Research Service", "代理研究服务", "research", "partial", "已有研究工件聚合；真实多代理运行时未接入。"),
        ("Deterministic Strategy Runtime", "确定性策略运行时", "execution", "partial", "已有规则策略与回测；生产事件驱动运行时未拆分。"),
        ("Risk Engine", "风险引擎 / RMS", "execution", "partial", "已有下单前风控；持仓中、日终和账户级熔断仍需增强。"),
        ("Order Management", "订单管理 / OMS", "execution", "partial", "已有订单 ID、状态和对账；撤改单、未知状态恢复和私有 WS 回报未实现。"),
        ("Exchange Adapters", "交易所适配器", "execution", "partial", "已有 Binance 公共行情和 test order；多交易所 venue-specific adapter 未实现，不同交易所签名、幂等字段、速率限制、模拟盘 header、请求失效时间必须分开处理。"),
        ("Exchange REST / WS", "交易所 REST / WS", "execution", "partial", "REST 已接入；私有流、订单簿 WS、序列校验和本地簿恢复未接入。"),
        ("Position & PnL Ledger", "持仓与 PnL 账本", "execution", "partial", "已有纸交易持仓和未实现/已实现 PnL；生产结算仍需补齐。"),
        ("Funding / Fee / Settlement", "资金费 / 手续费 / 结算", "execution", "gap", "尚未入账资金费、手续费、转账和清算事件。"),
        ("Backtest / Replay", "回测 / 回放", "research", "partial", "已有回测、参数比较、滚动验证；事件重放和盘口回放未实现。"),
        ("Audit Log / Event Store", "审计日志 / 事件存储", "observability", "partial", "已有 append-style 事件表；不可抵赖审计和归档未实现。"),
        ("Metrics / Logs / Alerts", "指标 / 日志 / 告警", "observability", "gap", "尚未接 Prometheus、Alertmanager 或通知渠道。"),
        ("PostgreSQL", "PostgreSQL", "control", "gap", "当前使用 SQLite；标准版需迁移 OLTP 数据。"),
        ("TimescaleDB", "TimescaleDB", "observability", "gap", "时序行情和账户指标尚未拆到时序库。"),
        ("ClickHouse", "ClickHouse", "observability", "gap", "大规模审计查询和归因分析尚未接入。"),
        ("Redis", "Redis", "control", "gap", "缓存、会话、轻量锁和速率限制尚未接入。"),
    ]
    module_definition_table = {
        "title": "关键模块定义",
        "summary": "这张表是面向本项目的模块定义，职责与生产化要点紧贴参考项目和交易所文档。",
        "rows": [
            {
                "module": "策略引擎",
                "responsibility": "维护策略 DSL、参数集、版本、因子与代理信号组合",
                "production_note": "研究层异步，执行层确定性；策略版本必须可回放",
            },
            {
                "module": "订单管理",
                "responsibility": "下单、改单、撤单、批量操作、生命周期状态机",
                "production_note": "统一内部状态，不同交易所各自映射",
            },
            {
                "module": "风控",
                "responsibility": "杠杆、名义敞口、方向偏置、单策略回撤、账户级熔断",
                "production_note": "强制前置；高风险策略需审批",
            },
            {
                "module": "回测",
                "responsibility": "快速参数扫描、事件驱动回放、策略比较",
                "production_note": "费率、滑点、资金费和成交约束要贴合交易所",
            },
            {
                "module": "数据采集",
                "responsibility": "K 线、盘口、成交、资金费、账户事件、新闻与社媒",
                "production_note": "要区分快照、增量、私有流和历史补数",
            },
            {
                "module": "持仓与结算",
                "responsibility": "仓位、均价、未实现/已实现盈亏、手续费、funding",
                "production_note": "账本式而不是“临时算一下”",
            },
            {
                "module": "日志与审计",
                "responsibility": "订单级、代理级、配置级、用户级日志",
                "production_note": "append-only；支持 correlation ID",
            },
            {
                "module": "权限与多用户管理",
                "responsibility": "登录、角色、审批、子账户与 API key 隔离",
                "production_note": "live 开关与密钥查看必须最小权限",
            },
            {
                "module": "监控告警",
                "responsibility": "延迟、错误率、序列缺口、收益/回撤、心跳",
                "production_note": "告警要能去重、分组和静默",
            },
            {
                "module": "模拟交易/沙盒",
                "responsibility": "测试网、模拟盘、影子订单、历史回放",
                "production_note": "沙盒与实盘共用同一套数据模型与订单模型",
            },
        ],
    }
    module_matrix = [
        {
            "module": "策略引擎",
            "responsibility": "维护策略 DSL、参数集、版本、因子与代理信号组合；拆成研究型策略引擎和确定性策略运行时。",
            "production_note": "研究层异步，执行层确定性；策略版本必须可回放。",
            "current": "研究工件 + 规则 TradeIntent + 回测实验室。",
            "required_next": "策略版本库、参数集、发布审批、事件驱动运行时和版本化回放入口。",
        },
        {
            "module": "订单管理",
            "responsibility": "下单、改单、撤单、批量操作、生命周期状态机；负责 order id 生成、交易所映射、重试和回报归并。",
            "production_note": "统一内部状态，不同交易所各自映射。",
            "current": "纸交易订单、client_order_id、venue_status、reconcile_status 和 order_transitions。",
            "required_next": "撤改单、批量操作、未知状态 reconcile、私有 WS 回报、幂等重试。",
        },
        {
            "module": "风控",
            "responsibility": "杠杆、名义敞口、方向偏置、单策略回撤、账户级熔断。",
            "production_note": "强制前置；高风险策略需审批；至少覆盖下单前、持仓中、日终后三层。",
            "current": "杠杆、仓位、日亏损、持仓数量、连续亏损、允许交易对和紧急停止。",
            "required_next": "名义敞口、方向偏置、单策略回撤、账户级熔断、审批阈值。",
        },
        {
            "module": "回测",
            "responsibility": "快速参数扫描、事件驱动回放、策略比较。",
            "production_note": "费率、滑点、资金费和成交约束要贴合交易所。",
            "current": "K 线回测、参数比较、滚动验证。",
            "required_next": "盘口回放、事件流回放、资金费/手续费/滑点/部分成交模型。",
        },
        {
            "module": "数据采集",
            "responsibility": "K 线、盘口、成交、资金费、账户事件、新闻与社媒。",
            "production_note": "要区分快照、增量、私有流和历史补数；REST 启动快照必须与 WebSocket 增量同步在一起。",
            "current": "Binance REST 公共行情、K 线、资金费和公开快照。",
            "required_next": "订单簿同步、成交流、序列校验、私有账户事件、历史补数、新闻/社媒连接器。",
        },
        {
            "module": "持仓与结算",
            "responsibility": "仓位、均价、未实现/已实现盈亏、手续费、funding。",
            "production_note": "账本式而不是“临时算一下”；必须跟踪 realized / unrealized PnL、手续费、资金费、转账和清算事件。",
            "current": "纸交易持仓、保证金、未实现/已实现 PnL。",
            "required_next": "手续费、资金费、转账、清算事件入账，以及交易所对账。",
        },
        {
            "module": "日志与审计",
            "responsibility": "订单级、代理级、配置级、用户级日志。",
            "production_note": "append-only；支持 correlation ID；能追溯每次配置、每笔订单、每个代理建议。",
            "current": "SQLite events、orders、order_transitions 和自检报告。",
            "required_next": "correlation ID、不可抵赖归档、配置变更审计、用户操作审计和导出能力。",
        },
        {
            "module": "权限与多用户管理",
            "responsibility": "登录、角色、审批、子账户与 API key 隔离。",
            "production_note": "live 开关与密钥查看必须最小权限；支持 maker-checker、只读研究员、交易员、风控、管理员等角色。",
            "current": "Basic Auth；服务端读取 API secret，前端不展示 secret。",
            "required_next": "SSO、RBAC、maker-checker、子账户、密钥权限隔离和 live 开关双人审批。",
        },
        {
            "module": "监控告警",
            "responsibility": "延迟、错误率、序列缺口、收益/回撤、心跳。",
            "production_note": "告警要能去重、分组和静默；覆盖数据陈旧、延迟、下单失败、风险超限、收益回撤。",
            "current": "部署 readiness、自检报告、运行状态和前端状态页。",
            "required_next": "Prometheus/OpenTelemetry、Alertmanager、告警去重分组静默、心跳和收益/回撤告警。",
        },
        {
            "module": "模拟交易/沙盒",
            "responsibility": "测试网、模拟盘、影子订单、历史回放。",
            "production_note": "沙盒与实盘共用同一套数据模型与订单模型；支持影子运行、回放、回归和环境隔离。",
            "current": "纸交易 + Binance /fapi/v1/order/test 验证 + 显式开关保护的真实 testnet 下单/查单/撤单；live mode 仍锁定。",
            "required_next": "私有账户流、影子订单、历史事件回放、发布前回归门槛和环境隔离报告。",
        },
    ]
    layered_architecture = {
        "title": "推荐的分层架构",
        "summary": "综合参考项目和交易所 API 约束，目标系统采用研究平面、控制平面、执行平面、观测平面四平面；研究层允许 Anthropic Agent SDK / LangGraph / 多代理，执行层必须保持确定性、可重放、低延迟。",
        "source_note": "这张生产级架构不是任何单一官方项目原样提供的图，而是基于参考项目边界和交易所 API 约束综合出的目标架构。",
        "planes": [
            {
                "name": "研究平面",
                "allowed": "允许使用 Anthropic Agent SDK / LangGraph / 多代理。",
                "responsibility": "生成结构化研究工件、候选信号、证据引用、辩论结论和策略参数建议。",
                "execution_boundary": "只输出结构化候选，不直接下单、不绑定风险、不接触 API secret。",
            },
            {
                "name": "控制平面",
                "allowed": "负责策略版本、审批、RBAC、配置发布、调度和人工复核。",
                "responsibility": "把策略草稿、回测、沙盒、发布审批、权限和配置变更放进同一控制链。",
                "execution_boundary": "控制 live/testnet 开关和发布流程，但不绕过风控与 OMS。",
            },
            {
                "name": "执行平面",
                "allowed": "必须尽量确定性、可重放、低延迟。",
                "responsibility": "运行确定性策略、RMS、OMS、持仓账本、结算和交易所适配器。",
                "execution_boundary": "所有订单都经确定性风控、幂等订单状态机和 venue-specific adapter。",
            },
            {
                "name": "观测平面",
                "allowed": "负责日志、指标、告警与审计。",
                "responsibility": "提供运行证据、事件回放、审计查询、指标监控、告警和事故复盘。",
                "execution_boundary": "记录和告警不改变交易决策，只提供可验证证据链。",
            },
        ],
        "venue_adapter_rule": {
            "summary": "交易所层不能只依赖统一抽象；执行平面必须做成 venue-specific adapter。",
            "api_differences": ["签名", "幂等字段", "速率限制", "订单簿同步", "模拟盘 header", "请求失效时间"],
            "production_requirement": "每个交易所适配器独立处理签名、client order id/orderLinkId/clOrdId、限频器、本地订单簿序列、模拟环境 header 和请求过期语义。",
        },
        "architecture_graph": {
            "mermaid": """flowchart LR
    UI[Web UI / Mobile Readonly]
    API[API Gateway / BFF]
    AUTH[SSO / RBAC / Approval]

    MD[Market Data Ingest]
    NORM[Normalizer / Sequencer]
    BUS[(Event Bus)]
    RESEARCH[Agent Research Service]
    STRAT[Deterministic Strategy Runtime]
    RISK[Risk Engine]
    OMS[Order Management]
    ADAPTER[Exchange Adapters]
    EX[(Exchange REST / WS)]

    POS[Position & PnL Ledger]
    SETTLE[Funding / Fee / Settlement]
    BT[Backtest / Replay]
    AUDIT[Audit Log / Event Store]
    OBS[Metrics / Logs / Alerts]

    DB[(PostgreSQL)]
    TS[(TimescaleDB)]
    OLAP[(ClickHouse)]
    CACHE[(Redis)]

    UI --> API --> AUTH
    API --> RESEARCH
    API --> BT
    API --> OMS
    API --> POS

    MD --> NORM --> BUS
    BUS --> RESEARCH
    BUS --> STRAT
    RESEARCH --> STRAT
    STRAT --> RISK --> OMS --> ADAPTER --> EX

    EX --> OMS
    EX --> POS
    OMS --> AUDIT
    POS --> SETTLE --> DB
    POS --> TS
    AUDIT --> OLAP
    BT --> OLAP
    API --> DB
    API --> CACHE
    BUS --> OBS
    OMS --> OBS
    POS --> OBS""",
            "nodes": [
                {"id": "UI", "label": "Web UI / Mobile Readonly", "plane": "control"},
                {"id": "API", "label": "API Gateway / BFF", "plane": "control"},
                {"id": "AUTH", "label": "SSO / RBAC / Approval", "plane": "control"},
                {"id": "MD", "label": "Market Data Ingest", "plane": "research"},
                {"id": "NORM", "label": "Normalizer / Sequencer", "plane": "execution"},
                {"id": "BUS", "label": "Event Bus", "plane": "observability"},
                {"id": "RESEARCH", "label": "Agent Research Service", "plane": "research"},
                {"id": "STRAT", "label": "Deterministic Strategy Runtime", "plane": "execution"},
                {"id": "RISK", "label": "Risk Engine", "plane": "execution"},
                {"id": "OMS", "label": "Order Management", "plane": "execution"},
                {"id": "ADAPTER", "label": "Exchange Adapters", "plane": "execution"},
                {"id": "EX", "label": "Exchange REST / WS", "plane": "execution"},
                {"id": "POS", "label": "Position & PnL Ledger", "plane": "execution"},
                {"id": "SETTLE", "label": "Funding / Fee / Settlement", "plane": "execution"},
                {"id": "BT", "label": "Backtest / Replay", "plane": "research"},
                {"id": "AUDIT", "label": "Audit Log / Event Store", "plane": "observability"},
                {"id": "OBS", "label": "Metrics / Logs / Alerts", "plane": "observability"},
                {"id": "DB", "label": "PostgreSQL", "plane": "control"},
                {"id": "TS", "label": "TimescaleDB", "plane": "observability"},
                {"id": "OLAP", "label": "ClickHouse", "plane": "observability"},
                {"id": "CACHE", "label": "Redis", "plane": "control"},
            ],
            "edges": [
                {"from": "UI", "to": "API"},
                {"from": "API", "to": "AUTH"},
                {"from": "API", "to": "RESEARCH"},
                {"from": "API", "to": "BT"},
                {"from": "API", "to": "OMS"},
                {"from": "API", "to": "POS"},
                {"from": "MD", "to": "NORM"},
                {"from": "NORM", "to": "BUS"},
                {"from": "BUS", "to": "RESEARCH"},
                {"from": "BUS", "to": "STRAT"},
                {"from": "RESEARCH", "to": "STRAT"},
                {"from": "STRAT", "to": "RISK"},
                {"from": "RISK", "to": "OMS"},
                {"from": "OMS", "to": "ADAPTER"},
                {"from": "ADAPTER", "to": "EX"},
                {"from": "EX", "to": "OMS"},
                {"from": "EX", "to": "POS"},
                {"from": "OMS", "to": "AUDIT"},
                {"from": "POS", "to": "SETTLE"},
                {"from": "SETTLE", "to": "DB"},
                {"from": "POS", "to": "TS"},
                {"from": "AUDIT", "to": "OLAP"},
                {"from": "BT", "to": "OLAP"},
                {"from": "API", "to": "DB"},
                {"from": "API", "to": "CACHE"},
                {"from": "BUS", "to": "OBS"},
                {"from": "OMS", "to": "OBS"},
                {"from": "POS", "to": "OBS"},
            ],
        },
        "strategy_engine_split": [
            {
                "part": "研究型策略引擎",
                "plane": "研究平面",
                "responsibility": "从新闻、社媒、funding、盘口与技术指标中生成候选信号。",
                "output": "输出结构化研究报告、证据引用、置信度和 TradeIntent 候选。",
            },
            {
                "part": "确定性策略运行时",
                "plane": "执行平面",
                "responsibility": "只接收结构化输入，输出明确的动作、仓位和条件。",
                "output": "输出可被风控验证的 order intent、仓位调整或 no-op。",
            },
        ],
        "module_definitions": [
            {
                "module": item["module"],
                "responsibility": item["responsibility"],
                "production_note": item["production_note"],
            }
            for item in module_definition_table["rows"]
        ],
        "integration_statement": "这样的模块划分吸收 Anthropic 的治理思路，也吸收 TradingAgents 的研究组织方式；但交易执行、风控、对账和结算仍由确定性代码负责。",
    }
    implementation_note_table = {
        "title": "自动交易系统实现注意事项",
        "summary": "这张表保留生产系统容易出问题的主题、文档依据和工程建议，作为进入 testnet 或 live 前的基础检查清单。",
        "rows": [
            {
                "topic": "密钥管理、签名、最小权限",
                "basis": "Binance 的 TRADE/USER_DATA 端点要求签名并支持 HMAC/RSA；Bybit 支持 HMAC 或 RSA，且 recv_window 用于防重放；OKX 明确建议 API key 绑定 IP，且有 trade/withdraw 权限但未绑 IP 的 key 会在 14 天不活跃后过期；Hyperliquid 官方建议尽量使用现成 SDK 处理签名，并区分 user address 与 API wallet。",
                "recommendation": "密钥只放服务端；用 KMS/HSM 或至少密文存储；读权限 key 与交易权限 key 分离；按交易所/账户/环境隔离 signer service；前端绝不接触 secret。",
            },
            {
                "topic": "重试与幂等",
                "basis": "Binance 在部分 503 场景明确说“API 是否成功执行未知，不应当直接当作失败”；同时提供 newClientOrderId。Bybit 提供 orderLinkId；OKX 提供 clOrdId，都作为用户自定义订单标识。",
                "recommendation": "所有下单都先生成内部订单号与 venue client order id；出现 unknown 状态时进入 PENDING_RECON，先查单 / 等私有 WS 回报，再决定是否重发。",
            },
            {
                "topic": "延迟与吞吐",
                "basis": "Bybit 的 API 限流是“rolling time window per second per UID”，同时返回 X-Bapi-Limit-* 头；Binance 会在 429 后进一步触发 418 IP ban；OKX 则按用户、产品或 instrument family 限频。",
                "recommendation": "把速率限制器做成 per-venue、per-account、per-endpoint；行情优先走 WebSocket，控制面再用 REST。",
            },
            {
                "topic": "订单滑点与费率",
                "basis": "Bybit 明确写出市价单会被交易引擎转换成带滑点保护的 IOC 限价单，超出范围即不成交；OKX 在期货/永续的市价单上使用 Price Limit Mechanism。",
                "recommendation": "回测和模拟必须建“可成交性模型”，不能把所有市价单都按理想价格成交；实盘下单应支持 IOC/FOK/PostOnly 和限价回退。",
            },
            {
                "topic": "市场数据质量",
                "basis": "Binance 维护本地订单簿要求 snapshot + diff depth + lastUpdateId/U/u/pu 串联；Bybit 用 snapshot/delta；OKX 用 snapshot/update + checksum + prevSeqId/seqId。",
                "recommendation": "做 canonical order-book engine；发现序列缺口、校验和不符或 prevSeqId 断裂时，立即重建本地簿，并在恢复前降级或暂停依赖盘口的策略。",
            },
            {
                "topic": "时序一致性",
                "basis": "Bybit 强调本地时间必须 NTP 同步，且 timestamp 必须落在指定时间窗；OKX 提供 expTime；Hyperliquid 提供 expiresAfter。",
                "recommendation": "所有机器强制 NTP；请求统一带过期时间；把“超时未处理”的订单从业务语义上区别于“失败订单”。",
            },
            {
                "topic": "回测与实盘差异",
                "basis": "TradingAgents 论文由于每次预测需要大量 LLM/工具调用，只做了 3 个月回测；README 也明确是 research purpose，且下单只到 simulated exchange。",
                "recommendation": "不要把研究框架里的回测表现直接外推到加密永续实盘；必须加入真实盘口、资金费、部分成交、撤改单失败、延迟与限频。",
            },
            {
                "topic": "故障恢复与回滚",
                "basis": "TradingAgents 使用 LangGraph checkpoint resume；Anthropic SDK 提供 hooks 与 file checkpointing；OTEL 也可接入遥测。",
                "recommendation": "策略运行态、订单态、持仓态、代理态分别做 checkpoint；恢复时先账户对账，再恢复策略。",
            },
            {
                "topic": "合规与风控规则",
                "basis": "FATF 对 VASP 的 AML/CFT 风险基础方法有明确指导；ESMA 的 MiCA 页面与 CFD 干预措施说明了授权、披露、杠杆限制、风险提示、margin close-out 和负余额保护等要求。",
                "recommendation": "即便是内部工具，也应内建白名单市场、最大杠杆、单账户日亏损上限、人工审批阈值和敏感区域禁用。",
            },
            {
                "topic": "模拟与回放能力",
                "basis": "Binance/Bybit/OKX/Hyperliquid 都提供 testnet、模拟盘或 testnet API/WS。",
                "recommendation": "把 replay 和 sandbox 作为一等公民；策略发布前先过 replay，再过 sandbox，再进入小额 live。",
            },
        ],
    }
    implementation_notes = [
        {
            "topic": "密钥管理、签名、最小权限",
            "status": "partial",
            "basis": "Binance TRADE/USER_DATA 端点要求签名并支持 HMAC/RSA；Bybit 使用 recv_window 防重放；OKX 建议 API key 绑定 IP；Hyperliquid 区分 user address 与 API wallet。",
            "recommendation": "密钥只放服务端，secret 永不下发前端；读权限 key 与交易权限 key 分离；按交易所、账户、环境隔离 signer service；生产阶段使用 KMS/HSM 或至少密文存储。",
            "current_control": "当前 MVP 默认 paper；Binance testnet 支持 /fapi/v1/order/test 参数验证，并可在 BINANCE_PLACE_TESTNET_ORDERS=true 时由服务端提交真实测试网订单；前端不接触 API secret。",
            "required_next": "服务器部署时强制 Basic Auth + Tailscale；启用测试网前绑定出口 IP，并补密钥轮换和吊销记录。",
        },
        {
            "topic": "重试与幂等",
            "status": "partial",
            "basis": "Binance 503 可能代表状态未知，且支持 newClientOrderId；Bybit 提供 orderLinkId；OKX 提供 clOrdId。",
            "recommendation": "所有订单先生成内部订单号和 venue client order id；unknown 状态进入 PENDING_RECON，先查单或等待私有 WS 回报，再决定是否重发。",
            "current_control": "当前 OMS 已保存 client_order_id、venue_status、reconcile_status 和订单状态迁移。",
            "required_next": "实现 unknown 状态恢复、查单优先重试、撤改单竞争条件处理和幂等回放测试。",
        },
        {
            "topic": "延迟与吞吐",
            "status": "gap",
            "basis": "Bybit 按 UID rolling time window 限频并返回 X-Bapi-Limit-*；Binance 429 后可能触发 418 IP ban；OKX 按用户、产品或 instrument family 限频。",
            "recommendation": "把速率限制器做成 per-venue、per-account、per-endpoint；行情优先 WebSocket，控制面再用 REST。",
            "current_control": "当前只有同步 HTTP 重试和超时配置，适合 MVP 纸交易。",
            "required_next": "增加 venue 级限频器、请求预算、退避策略和限频审计事件。",
        },
        {
            "topic": "订单滑点与费率",
            "status": "partial",
            "basis": "Bybit 市价单可能转换成带滑点保护的 IOC 限价单；OKX 期货/永续存在 Price Limit Mechanism。",
            "recommendation": "回测和模拟必须有可成交性模型，不能把所有市价单按理想价格成交；实盘下单应支持 IOC、FOK、PostOnly 和限价回退。",
            "current_control": "当前回测已有手续费与简单滑点模型，但没有盘口可成交性和部分成交模型。",
            "required_next": "接入盘口回放、部分成交、撤改单失败、资金费和交易所价格保护规则。",
        },
        {
            "topic": "市场数据质量",
            "status": "gap",
            "basis": "Binance 本地订单簿需要 snapshot + diff depth + lastUpdateId/U/u/pu 串联；Bybit 使用 snapshot/delta；OKX 使用 snapshot/update + checksum + prevSeqId/seqId。",
            "recommendation": "实现 canonical order-book engine；发现序列缺口、checksum 不符或 prevSeqId 断裂时立即重建本地簿，并在恢复前暂停依赖盘口的策略。",
            "current_control": "当前使用 Binance REST 快照和 K 线，不维护本地订单簿。",
            "required_next": "增加 WS 增量、序列校验、本地簿重建、数据陈旧告警和策略降级开关。",
        },
        {
            "topic": "时序一致性",
            "status": "gap",
            "basis": "Bybit 要求 timestamp 落在 recv_window；OKX 提供 expTime；Hyperliquid 提供 expiresAfter。",
            "recommendation": "所有服务器强制 NTP；请求统一带过期时间；把超时未处理订单从业务语义上区别于失败订单。",
            "current_control": "当前记录 UTC 事件时间，并有 HTTP timeout。",
            "required_next": "部署脚本加入 NTP/chrony 检查，订单请求增加过期时间和超时状态机。",
        },
        {
            "topic": "回测与实盘差异",
            "status": "partial",
            "basis": "TradingAgents 每次预测消耗大量 LLM/工具调用，README 也将下单放在 simulated exchange 和 research purpose 边界内。",
            "recommendation": "不要把研究框架回测表现直接外推到加密永续实盘；必须加入真实盘口、资金费、部分成交、撤改单失败、延迟与限频。",
            "current_control": "当前已有 K 线回测、参数比较、滚动验证和 paper workflow。",
            "required_next": "建立事件驱动 replay，统一策略版本输入，让 sandbox/live 共用同一套成交约束模型。",
        },
        {
            "topic": "故障恢复与回滚",
            "status": "partial",
            "basis": "TradingAgents 使用 LangGraph checkpoint resume；Anthropic SDK 提供 hooks、checkpointing 和 OpenTelemetry。",
            "recommendation": "策略运行态、订单态、持仓态、代理态分别 checkpoint；恢复时先账户对账，再恢复策略。",
            "current_control": "当前 SQLite 保存 runs、events、orders、positions 和 order_transitions。",
            "required_next": "增加启动恢复流程、私有 WS 断线恢复、真仓对账门禁和事故演练脚本。",
        },
        {
            "topic": "合规与风控规则",
            "status": "partial",
            "basis": "FATF 对 VASP 有 AML/CFT 风险基础方法；MiCA 与 CFD 监管语境强调授权、披露、杠杆限制、margin close-out 和负余额保护。",
            "recommendation": "即便是内部工具，也应内建白名单市场、最大杠杆、单账户日亏损上限、人工审批阈值和敏感区域禁用。",
            "current_control": "当前已有允许交易对、最大杠杆、单笔仓位、日亏损、持仓数、连续亏损和紧急停止。",
            "required_next": "补审批流、账户级熔断、区域/交易所禁用策略和合规审计导出。",
        },
        {
            "topic": "模拟与回放能力",
            "status": "partial",
            "basis": "Binance、Bybit、OKX、Hyperliquid 都提供 testnet、模拟盘或 testnet API/WS。",
            "recommendation": "把 replay 和 sandbox 作为一等公民；策略发布前先过 replay，再过 sandbox，再进入小额 live。",
            "current_control": "当前支持 paper、Binance test order 验证、真实 testnet 下单/查单/撤单、回测、参数比较和滚动验证；真实 live mode 仍锁定。",
            "required_next": "实现私有账户流、影子订单、历史事件回放、发布前回归门槛和环境隔离报告。",
        },
    ]
    entity_model = {
        "title": "关键数据流与实体关系",
        "summary": "关键数据流必须让策略、订单、成交、仓位、风控规则与审计日志形成一条可回放、可解释、可核账的链。",
        "focus": "重点不是数据库画得多漂亮，而是让策略、订单、成交、仓位、风控规则与审计日志成为一条可回放、可解释、可核账的链。",
        "mermaid": """erDiagram
    USER ||--o{ ACCOUNT : owns
    USER ||--o{ API_KEY : manages
    USER ||--o{ AUDIT_LOG : triggers

    ACCOUNT ||--o{ STRATEGY_DEPLOYMENT : runs
    ACCOUNT ||--o{ ORDER : places
    ACCOUNT ||--o{ POSITION : holds
    ACCOUNT ||--o{ RISK_RULE_BINDING : uses

    STRATEGY ||--o{ STRATEGY_VERSION : has
    STRATEGY_VERSION ||--o{ BACKTEST_RUN : tested_by
    STRATEGY_VERSION ||--o{ SIGNAL_EVENT : emits
    STRATEGY_DEPLOYMENT }o--|| STRATEGY_VERSION : deploys

    SIGNAL_EVENT ||--o{ ORDER : may_create
    ORDER ||--o{ FILL : contains
    ORDER }o--|| EXCHANGE_ORDER_REF : maps_to
    POSITION ||--o{ FILL : updated_by
    POSITION ||--o{ SETTLEMENT_EVENT : settled_by

    RISK_RULE ||--o{ RISK_RULE_BINDING : applied_to
    ORDER ||--o{ RISK_CHECK_RESULT : checked_by
    SIGNAL_EVENT ||--o{ RESEARCH_ARTIFACT : explained_by
    ORDER ||--o{ AUDIT_LOG : recorded_in
    FILL ||--o{ AUDIT_LOG : recorded_in""",
        "entities": [
            {"name": "USER", "label": "用户", "current": "Basic Auth 用户占位；多用户尚未实现。"},
            {"name": "ACCOUNT", "label": "账户", "current": "当前以单纸交易账户和账户权益快照表示。"},
            {"name": "API_KEY", "label": "API 密钥", "current": "服务端环境变量读取；前端不展示 secret。"},
            {"name": "AUDIT_LOG", "label": "审计日志", "current": "SQLite events 与自检报告。"},
            {"name": "STRATEGY_DEPLOYMENT", "label": "策略部署", "current": "纸交易调度配置，尚未版本化部署。"},
            {"name": "ORDER", "label": "订单", "current": "orders 表记录纸交易和测试网验证订单。"},
            {"name": "POSITION", "label": "持仓", "current": "positions 表记录纸交易仓位和 PnL。"},
            {"name": "RISK_RULE_BINDING", "label": "风控规则绑定", "current": "settings 中的风险阈值和允许交易对。"},
            {"name": "STRATEGY", "label": "策略", "current": "内置规则策略和回测参数。"},
            {"name": "STRATEGY_VERSION", "label": "策略版本", "current": "回测参数快照；正式版本库尚未实现。"},
            {"name": "BACKTEST_RUN", "label": "回测运行", "current": "backtest_runs、compare 和 walk-forward 结果。"},
            {"name": "SIGNAL_EVENT", "label": "信号事件", "current": "研究工件与 TradeIntent 事件。"},
            {"name": "FILL", "label": "成交", "current": "纸交易成交通过订单与持仓变化表示；独立 fills 表待补。"},
            {"name": "EXCHANGE_ORDER_REF", "label": "交易所订单映射", "current": "client_order_id、venue_order_id、venue_status。"},
            {"name": "SETTLEMENT_EVENT", "label": "结算事件", "current": "资金费、手续费、转账和清算事件待补。"},
            {"name": "RISK_RULE", "label": "风控规则", "current": "杠杆、仓位、日亏损、持仓数、连续亏损、白名单。"},
            {"name": "RISK_CHECK_RESULT", "label": "风控检查结果", "current": "每次运行的风险检查事件和拒绝/通过状态。"},
            {"name": "RESEARCH_ARTIFACT", "label": "研究工件", "current": "Anthropic/TradingAgents 风格结构化研究工件。"},
        ],
        "relationships": [
            ("USER", "owns", "ACCOUNT", "用户拥有交易账户或子账户。"),
            ("USER", "manages", "API_KEY", "用户管理 API key，但 secret 只留在服务端。"),
            ("USER", "triggers", "AUDIT_LOG", "用户操作必须写入审计日志。"),
            ("ACCOUNT", "runs", "STRATEGY_DEPLOYMENT", "账户运行策略部署实例。"),
            ("ACCOUNT", "places", "ORDER", "账户通过 OMS 发出订单。"),
            ("ACCOUNT", "holds", "POSITION", "账户持有仓位和保证金。"),
            ("ACCOUNT", "uses", "RISK_RULE_BINDING", "账户绑定风险规则。"),
            ("STRATEGY", "has", "STRATEGY_VERSION", "策略拥有可回放版本。"),
            ("STRATEGY_VERSION", "tested_by", "BACKTEST_RUN", "策略版本被回测和滚动验证检验。"),
            ("STRATEGY_VERSION", "emits", "SIGNAL_EVENT", "策略版本输出结构化信号。"),
            ("STRATEGY_DEPLOYMENT", "deploys", "STRATEGY_VERSION", "部署实例引用具体策略版本。"),
            ("SIGNAL_EVENT", "may_create", "ORDER", "信号经过风控后才可能创建订单。"),
            ("ORDER", "contains", "FILL", "订单包含一个或多个成交。"),
            ("ORDER", "maps_to", "EXCHANGE_ORDER_REF", "内部订单映射交易所订单引用。"),
            ("POSITION", "updated_by", "FILL", "成交更新仓位数量、均价和 PnL。"),
            ("POSITION", "settled_by", "SETTLEMENT_EVENT", "资金费、手续费和清算事件结算仓位。"),
            ("RISK_RULE", "applied_to", "RISK_RULE_BINDING", "风控规则应用到账户或策略。"),
            ("ORDER", "checked_by", "RISK_CHECK_RESULT", "订单必须通过前置风控检查。"),
            ("SIGNAL_EVENT", "explained_by", "RESEARCH_ARTIFACT", "信号必须能回溯到研究工件和证据。"),
            ("ORDER", "recorded_in", "AUDIT_LOG", "订单状态迁移写入审计链。"),
            ("FILL", "recorded_in", "AUDIT_LOG", "成交和结算写入审计链。"),
        ],
    }
    ui_page_component_table = {
        "title": "主要页面与组件",
        "summary": "这张表保留控制台页面、必备组件和设计重点，作为前端信息架构的精确验收表。",
        "rows": [
            {
                "page": "仪表盘",
                "components": "账户净值卡、PnL、回撤、保证金率、策略状态、告警流",
                "design_focus": "首屏只放“需要动作”的信息，不堆技术细节",
            },
            {
                "page": "策略编辑器",
                "components": "Monaco 编辑器、参数表单、版本 diff、研究工件侧栏、发布按钮",
                "design_focus": "把“研究解释”和“策略配置”并排展示，便于审阅",
            },
            {
                "page": "回测结果",
                "components": "权益曲线、回撤曲线、月度热力图、成交统计、参数对比表",
                "design_focus": "强调可比性与可复现性，而不是单次好看结果",
            },
            {
                "page": "订单簿",
                "components": "DOM 表、盘口深度、最新成交、下单面板、撤改单面板",
                "design_focus": "尽量桌面端三栏布局，减少视线跳转",
            },
            {
                "page": "持仓详情",
                "components": "K 线、均价线、资金费时间线、成交流水、风险敞口图",
                "design_focus": "不只显示仓位数量，要显示“为什么还在持有”",
            },
            {
                "page": "风控面板",
                "components": "规则列表、命中次数、日损阈值、账户/策略熔断开关",
                "design_focus": "要支持只读审查和带审批的修改",
            },
            {
                "page": "用户设置",
                "components": "偏好、通知渠道、默认工作区、语言和时区",
                "design_focus": "时区和数字格式要一致，避免交易误读",
            },
            {
                "page": "API 密钥管理",
                "components": "指纹、权限、IP 白名单、环境隔离、最后使用时间",
                "design_focus": "绝不展示 secret 明文；支持轮换和失效",
            },
            {
                "page": "日志/审计视图",
                "components": "时间线、过滤器、关联 ID、对象快照、xterm 辅助面板",
                "design_focus": "审计视图要偏“证据链”，日志视图要偏“排障链”",
            },
        ],
    }
    ui_information_architecture = {
        "title": "控制台信息架构",
        "summary": "UI 不做单纯行情页或聊天页，而是面向交易运营和风控协作的控制台。",
        "root": "工作台",
        "navigation_tree": """工作台
├─ 仪表盘
├─ 策略中心
│  ├─ 策略列表
│  ├─ 策略编辑器
│  ├─ 参数集与版本
│  ├─ 发布审批
│  └─ 研究工件与信号预览
├─ 回测与回放
│  ├─ 任务列表
│  ├─ 结果对比
│  ├─ 交易明细
│  └─ 事件回放
├─ 交易执行
│  ├─ 订单簿
│  ├─ 当前委托
│  ├─ 成交流水
│  └─ 仓位详情
├─ 风控中心
│  ├─ 规则配置
│  ├─ 账户风险
│  ├─ 告警事件
│  └─ 熔断与人工干预
├─ 数据与审计
│  ├─ 行情健康
│  ├─ 日志检索
│  ├─ 审计视图
│  └─ 指标看板
└─ 用户与系统
   ├─ 用户设置
   ├─ API 密钥管理
   ├─ 角色与权限
   └─ 系统配置""",
        "navigation": [
            {"name": "仪表盘", "children": []},
            {"name": "策略中心", "children": ["策略列表", "策略编辑器", "参数集与版本", "发布审批", "研究工件与信号预览"]},
            {"name": "回测与回放", "children": ["任务列表", "结果对比", "交易明细", "事件回放"]},
            {"name": "交易执行", "children": ["订单簿", "当前委托", "成交流水", "仓位详情"]},
            {"name": "风控中心", "children": ["规则配置", "账户风险", "告警事件", "熔断与人工干预"]},
            {"name": "数据与审计", "children": ["行情健康", "日志检索", "审计视图", "指标看板"]},
            {"name": "用户与系统", "children": ["用户设置", "API 密钥管理", "角色与权限", "系统配置"]},
        ],
        "page_component_table": ui_page_component_table,
        "page_components": ui_page_component_table["rows"],
        "component_tooling": [
            "Monaco Editor 用于策略 DSL、JSON 配置和版本 diff。",
            "Lightweight Charts 用于 K 线、十字光标、缩放和金融图表联动。",
            "ECharts 用于回撤、热力图、风险敞口和大数据可视化。",
            "xterm.js 用于日志 tail、运维辅助和回放诊断。",
        ],
        "interaction_flow": {
            "summary": "策略从草稿到真仓必须是显式工作流，把证据—参数—风险—发布串起来，而不是只让用户改参数。",
            "steps": [
                {"name": "创建策略草稿", "current": "当前以规则策略和参数表单占位。"},
                {"name": "补充研究工件", "current": "已有研究工件与结构化信号预览。"},
                {"name": "跑回测", "current": "已有 K 线回测、参数比较和滚动验证。"},
                {"name": "复核收益/风险/成交分布", "current": "已有收益、回撤、胜率、交易明细和风险检查；成交分布待增强。"},
                {"name": "发布到 sandbox", "current": "当前支持 paper 和 Binance test order 验证，真实 sandbox 发布待实现。"},
                {"name": "观察影子运行", "current": "调度和纸交易可作为影子运行基础，影子订单待实现。"},
                {"name": "进入 live", "current": "live mode 仍锁定，只保留未来小额 Live 门槛。"},
                {"name": "日志 / 审计 / 复盘", "current": "已有 events、orders、positions 和自检报告。"},
            ],
            "main_loop": [
                {"name": "策略草稿", "purpose": "从策略想法、参数集和版本草稿开始。"},
                {"name": "研究工件与结构化信号", "purpose": "把 Anthropic/TradingAgents 风格研究结论沉淀为可审阅工件和 TradeIntent 候选。"},
                {"name": "回测 / 回放", "purpose": "用回测、参数比较、滚动验证和未来事件回放验证策略。"},
                {"name": "审批 / 风控复核", "purpose": "让收益、风险、成交分布和风控阈值在发布前被显式复核。"},
                {"name": "Sandbox 部署", "purpose": "先进入 paper、测试网或模拟盘环境，禁止直接跳到 live。"},
                {"name": "监控与对账", "purpose": "持续观察订单、仓位、PnL、告警、OMS 对账和数据健康。"},
                {"name": "小额 Live", "purpose": "只有在沙盒和对账门槛通过后，才进入小额真仓验证。"},
                {"name": "日志 / 审计 / 复盘", "purpose": "把决策、订单、成交、风险和事故处理写入审计链并回到下一轮草稿。"},
            ],
        },
        "responsive_guidance": {
            "principle": "桌面优先、移动端降能力。",
            "desktop": "桌面端采用 12 栏栅格，让订单簿、图表、委托/持仓三栏并列，减少交易员视线跳转。",
            "mobile": "移动端保留看状态、确认告警、紧急停机、查看仓位等低风险操作，不做完整策略编辑、API key 管理或高风险发布。",
            "incident": "移动端最有价值的是事故处理能力：告警确认、紧急停机、仓位查看应当 3 步内可达。",
        },
        "chart_guidance": {
            "summary": "图表建议分成交易图和分析图；交易图服务执行判断，分析图服务回测、风险和归因。",
            "trading_charts": ["K 线", "成交量", "盘口深度", "最新成交", "持仓均价/止盈止损线"],
            "analysis_charts": ["权益曲线", "回撤曲线", "rolling Sharpe", "胜率/盈亏比分布", "滑点散点图", "账户/策略敞口堆叠图", "资金费时间线"],
            "tool_mapping": [
                "Lightweight Charts 优先承载专业金融 K 线、十字光标、缩放与同步联动。",
                "ECharts 优先承载回撤、热力图、多图矩阵、风险敞口和大数据可视化。",
            ],
        },
    }
    technical_implementation = {
        "summary": "技术路线继续坚持研究代理与执行交易分离；当前 MVP 仍先稳定本地纸交易、Binance 测试网验证和中文控制台，再评估标准版重构。",
        "principles": [
            "研究代理层可使用 LangGraph 或 Anthropic Agent SDK；执行热路径必须保持确定性。",
            "API 与控制面标准版建议 FastAPI，前端标准版建议 Next.js App Router。",
            "数据层按 PostgreSQL、TimescaleDB、ClickHouse 分层，消息层优先 NATS JetStream，告警使用 Prometheus + Alertmanager。",
            "策略研究不押单一工具：vectorbt 做快速扫描，事件回放做精细验证，NautilusTrader 可作为标准/企业级一致性引擎候选。",
            "第三方 API 优先级为官方交易所 REST/WS 文档与官方 SDK 第一，自研 venue-specific adapter 第二，统一封装库第三。",
        ],
        "api_priority": [
            "官方交易所 REST/WS 文档与官方 SDK 第一优先。",
            "自研 venue-specific adapter 第二优先，用于处理签名、时序、clientOrderId/orderLinkId/clOrdId、订单簿同步、模拟环境和过期时间差异。",
            "CCXT 等统一封装库适合原型和补数据，关键下单热路径仍应直连官方 API。",
        ],
        "stack_layers": [
            {"layer": "研究代理编排", "recommendation": "LangGraph / Anthropic Agent SDK", "preferred": "是", "note": "负责研究、解释、结构化信号、审批辅助。"},
            {"layer": "API / 控制面", "recommendation": "FastAPI", "preferred": "是", "note": "Python 生态下启动最快，便于和研究层集成。"},
            {"layer": "执行引擎", "recommendation": "自研确定性运行时；标准/企业级可引入 NautilusTrader", "preferred": "是", "note": "不建议把 LLM 放进热路径。"},
            {"layer": "前端框架", "recommendation": "Next.js", "preferred": "是", "note": "适合控制台式 Web 应用。"},
            {"layer": "金融图表", "recommendation": "Lightweight Charts", "preferred": "是", "note": "K 线与专业金融交互。"},
            {"layer": "通用可视化", "recommendation": "ECharts", "preferred": "是", "note": "风险、统计、热力图、多图种。"},
            {"layer": "策略编辑器", "recommendation": "Monaco Editor", "preferred": "是", "note": "代码/DSL/JSON 编辑和 diff。"},
            {"layer": "日志终端", "recommendation": "xterm.js", "preferred": "可选", "note": "在线 tail、运维辅助、回放诊断。"},
            {"layer": "OLTP 数据库", "recommendation": "PostgreSQL", "preferred": "是", "note": "订单、仓位、用户、审批。"},
            {"layer": "时序数据库", "recommendation": "TimescaleDB", "preferred": "是", "note": "K 线、指标、策略运行时序。"},
            {"layer": "分析数据库", "recommendation": "ClickHouse", "preferred": "标准起", "note": "审计查询、归因分析、海量报表。"},
            {"layer": "消息总线", "recommendation": "NATS JetStream", "preferred": "是", "note": "事件流、持久化、重放。"},
            {"layer": "监控与告警", "recommendation": "OTEL + Prometheus + Alertmanager", "preferred": "是", "note": "指标、日志、告警、路由静默。"},
            {"layer": "回测工具", "recommendation": "vectorbt / 自研事件回放", "preferred": "是", "note": "快速实验 + 精细回放双轨。"},
            {"layer": "参考型 bot/运维借鉴", "recommendation": "Freqtrade", "preferred": "可选", "note": "参考其 WebUI、策略组织与资金管理。"},
            {"layer": "多交易所统一层", "recommendation": "CCXT", "preferred": "原型期", "note": "原型和补数据可用，热路径仍应直连官方 API。"},
        ],
        "roadmap": [
            {"stage": "架构定型", "goal": "明确领域模型、事件模型与发布流程", "deliverables": "领域模型、订单状态机、风控规则、环境隔离方案、UI IA 图", "team": "2–3 人", "timeline": "2–3 周"},
            {"stage": "单交易所闭环", "goal": "打通一条从行情到沙盒下单再到对账的链路", "deliverables": "市场数据采集、OMS、RMS、仓位账本、审计日志、sandbox adapter", "team": "4–6 人", "timeline": "4–6 周"},
            {"stage": "回测与回放", "goal": "建立可重复验证的策略实验体系", "deliverables": "向量化回测、事件回放、费率/滑点/funding 模型、结果报告", "team": "4–6 人", "timeline": "3–5 周"},
            {"stage": "控制台与告警", "goal": "让系统可运营、可排障、可审批", "deliverables": "仪表盘、策略编辑器、回测页面、风控面板、日志/审计视图、告警链路", "team": "5–7 人", "timeline": "4–6 周"},
            {"stage": "小额实盘", "goal": "在真仓验证幂等、延迟、风控与恢复", "deliverables": "live adapter、影子运行、事故手册、回滚手册、上线检查单", "team": "5–8 人", "timeline": "4–8 周"},
            {"stage": "标准化扩展", "goal": "支持多策略、多账户、多交易所和多角色", "deliverables": "子账户、多租户隔离、审批流、密钥轮换、HA/DR、更多策略模板", "team": "7–12 人", "timeline": "2–6 个月"},
        ],
        "scale_comparison": [
            {"dimension": "目标用户", "mvp": "个人或 1 个小团队", "standard": "1–3 个团队，含研究/交易/风控分工", "enterprise": "多团队、多角色、潜在多租户"},
            {"dimension": "交易所范围", "mvp": "1 家官方支持沙盒的 CEX", "standard": "2–3 家 CEX，部分子账户", "enterprise": "多 CEX + 可选 DEX/链上永续"},
            {"dimension": "策略范围", "mvp": "1–3 个模板策略", "standard": "多策略组合，支持代理研究层", "enterprise": "多策略、多账户、多审批流"},
            {"dimension": "关键功能", "mvp": "行情、回测、sandbox、OMS、RMS、持仓、日志", "standard": "加入 replay、审批流、子账户、告警、研究工件", "enterprise": "多活、HA/DR、细粒度 RBAC、合规留痕、成本治理"},
            {"dimension": "UI 范围", "mvp": "仪表盘、策略编辑器、回测结果、持仓与订单", "standard": "增加风控中心、审计视图、用户设置、密钥管理", "enterprise": "再增加多工作区、审批列表、运营看板、报表中心"},
            {"dimension": "技术形态", "mvp": "Python + FastAPI + Next.js + PostgreSQL/TimescaleDB", "standard": "再加 ClickHouse、NATS、OTEL、更多 venue adapters", "enterprise": "再加 KMS/HSM、跨区部署、蓝绿/金丝雀发布、DR 演练"},
            {"dimension": "交付团队", "mvp": "4–6 人", "standard": "7–10 人", "enterprise": "12–18 人"},
            {"dimension": "日历时间", "mvp": "10–14 周", "standard": "5–7 个月", "enterprise": "9–15 个月"},
            {"dimension": "粗略预算", "mvp": "60–120 万", "standard": "180–350 万", "enterprise": "500–1200 万以上"},
            {"dimension": "适用场景", "mvp": "先证明系统闭环", "standard": "小团队稳定使用并真仓迭代", "enterprise": "机构级内控、审计、分权与扩张"},
        ],
        "recommended_start": "功能上按标准版规划，交付上按 MVP 分两期做；订单幂等、统一账本、RBAC、审计 schema 需要在 MVP 阶段打底，多活、跨区、全量多租户暂不前置。",
        "risk_boundary": "最大的风险不是模型不够聪明，而是系统边界不清；代理建议、订单状态、仓位状态和审计状态必须在同一事件链上，否则重试、回放、对账和事故处理会失控。",
        "testing_principle": "测试必须覆盖正常路径 + 异常路径 + 恢复路径；未知状态、盘口断链和恢复对账是上线前真正的生死线。",
        "risk_register": [
            {
                "risk": "API 密钥泄露",
                "typical_manifestation": "前端泄露、日志泄露、弱权限 key 被滥用。",
                "mitigation": "服务端签名、最小权限、IP 白名单、密钥轮换、审计告警。",
            },
            {
                "risk": "重复下单",
                "typical_manifestation": "网络抖动后盲目重试，形成双开仓。",
                "mitigation": "内部订单号 + venue client order id + reconcile before retry。",
            },
            {
                "risk": "行情失真",
                "typical_manifestation": "订单簿序列断裂、checksum 错误、旧快照污染。",
                "mitigation": "快照/增量重建、checksum/校验和校验、断链暂停策略。",
            },
            {
                "risk": "时间漂移",
                "typical_manifestation": "签名失败、请求超窗、旧请求误执行。",
                "mitigation": "全节点 NTP、统一 recvWindow/expTime/expiresAfter 策略。",
            },
            {
                "risk": "回测幻觉",
                "typical_manifestation": "回测收益高，实盘成交差、滑点爆炸。",
                "mitigation": "引入盘口回放、局部成交、撤改单失败、funding 与费率模型。",
            },
            {
                "risk": "模型幻觉或被注入",
                "typical_manifestation": "代理读到恶意文档后输出危险指令。",
                "mitigation": "把第三方内容当数据而非指令；结构化输出；严格工具 schema。",
            },
            {
                "risk": "合规误踩",
                "typical_manifestation": "对外服务触发许可、披露、反洗钱义务。",
                "mitigation": "上线前按运营模式做监管分类，默认内用工具化。",
            },
            {
                "risk": "告警风暴",
                "typical_manifestation": "一个故障触发成百上千条告警。",
                "mitigation": "分组、去重、静默、升级路由。",
            },
            {
                "risk": "运维恢复失败",
                "typical_manifestation": "crash 后仓位在交易所与本地不一致。",
                "mitigation": "恢复先对账后恢复策略，账本为权威源。",
            },
            {
                "risk": "人为误操作",
                "typical_manifestation": "错账户、错环境、错杠杆、错参数发布。",
                "mitigation": "强环境标识、审批、双人发布、live 开关二次确认。",
            },
        ],
        "acceptance_matrix": [
            {
                "category": "行情同步",
                "key_cases": "REST 快照 + WS 增量正常拼接；序列缺口重建；checksum 不一致重建。",
                "minimum_acceptance": "缺口在检测后 2 秒内完成重建；重建期间相关策略暂停。",
            },
            {
                "category": "下单幂等",
                "key_cases": "同一订单重复提交、网络超时、未知状态回包。",
                "minimum_acceptance": "同一内部订单最多在交易所生成 1 个有效挂单；未知状态必须先 reconcile。",
            },
            {
                "category": "撤改单",
                "key_cases": "撤单成功、撤单已成交、改单与成交竞争条件。",
                "minimum_acceptance": "结果与交易所最终状态一致，本地状态不允许“幽灵挂单”。",
            },
            {
                "category": "风控前置",
                "key_cases": "超杠杆、超名义、超日损、黑名单 symbol。",
                "minimum_acceptance": "命中规则时绝不发单，并留审计记录。",
            },
            {
                "category": "持仓与结算",
                "key_cases": "部分成交、反向成交、资金费结算、手续费入账。",
                "minimum_acceptance": "任何时点仓位、均价、已实现/未实现盈亏可复算。",
            },
            {
                "category": "回测与回放",
                "key_cases": "同一输入重复回放、配置变更后对比。",
                "minimum_acceptance": "确定性运行时在同一事件流上结果一致；版本差异可解释。",
            },
            {
                "category": "故障恢复",
                "key_cases": "进程崩溃、私有 WS 中断、交易所短时不可用。",
                "minimum_acceptance": "恢复后先对账再恢复；不允许带未核实仓位继续交易。",
            },
            {
                "category": "权限控制",
                "key_cases": "只读用户访问 live 操作、跨角色审批、密钥查看权限。",
                "minimum_acceptance": "非授权角色无法执行 live 发布/查看 secret；所有越权请求有审计。",
            },
            {
                "category": "UI 可用性",
                "key_cases": "高风险操作确认、错误提示、移动端紧急停机。",
                "minimum_acceptance": "live 风险操作至少二次确认；事故操作在移动端 3 步内可达。",
            },
            {
                "category": "告警链路",
                "key_cases": "数据陈旧、风控命中、下单拒绝、服务心跳丢失。",
                "minimum_acceptance": "告警 1 分钟内到达，支持分组去重与静默恢复。",
            },
        ],
        "go_live_gates": [
            "连续多日的沙盒与回放结果一致性达标。",
            "未知状态订单不出现重复开仓。",
            "盘口断链可自动恢复。",
            "持仓与账本可每日对平。",
            "关键告警可在 SLA 内到达。",
            "RBAC 与审计经演练验证通过。",
        ],
    }
    return {
        "summary": "目标架构采用研究、控制、执行、观测四平面；当前 MVP 已覆盖纸交易闭环，但生产数据库、RBAC、告警、事件总线、多交易所适配和真仓恢复仍是显式缺口。",
        "executive_summary": executive_summary,
        "project_goals_assumptions": project_goals_assumptions,
        "anthropic_reference_project": anthropic_reference_project,
        "tradingagents_reference_project": tradingagents_reference_project,
        "reference_synthesis": reference_synthesis,
        "layered_architecture": layered_architecture,
        "principles": principles,
        "planes": planes,
        "components": [
            {
                "name": name,
                "label": label,
                "plane": plane,
                "status": status,
                "detail": detail,
            }
            for name, label, plane, status, detail in components
        ],
        "module_definition_table": module_definition_table,
        "module_matrix": module_matrix,
        "implementation_note_table": implementation_note_table,
        "implementation_notes": implementation_notes,
        "entity_model": {
            "title": entity_model["title"],
            "summary": entity_model["summary"],
            "focus": entity_model["focus"],
            "mermaid": entity_model["mermaid"],
            "entities": entity_model["entities"],
            "relationships": [
                {"from": source, "relation": relation, "to": target, "detail": detail}
                for source, relation, target, detail in entity_model["relationships"]
            ],
        },
        "ui_information_architecture": ui_information_architecture,
        "technical_implementation": technical_implementation,
    }


def get_orders(limit: int = 50) -> list[dict[str, Any]]:
    with DB_LOCK, connect() as conn:
        rows = conn.execute(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def get_order(order_id: str) -> dict[str, Any] | None:
    with DB_LOCK, connect() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    return dict_row(row)


def get_order_by_client_order_id(client_order_id: str) -> dict[str, Any] | None:
    with DB_LOCK, connect() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE client_order_id = ? ORDER BY created_at DESC LIMIT 1",
            (client_order_id,),
        ).fetchone()
    return dict_row(row)


def get_child_protection_orders(parent_order_id: str) -> list[dict[str, Any]]:
    with DB_LOCK, connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM orders
            WHERE parent_order_id = ?
              AND protection_kind IS NOT NULL
              AND protection_kind != ''
            ORDER BY created_at ASC
            """,
            (parent_order_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def insert_order_transition(
    order_id: str,
    from_status: str | None,
    to_status: str,
    reason: str,
    payload: dict[str, Any] | None = None,
) -> None:
    now = utc_now()
    clean_payload = payload or {}
    with DB_LOCK, connect() as conn:
        conn.execute(
            """
            INSERT INTO order_transitions(order_id, ts, from_status, to_status, reason, payload)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                now,
                from_status,
                to_status,
                reason,
                json.dumps(clean_payload, ensure_ascii=False),
            ),
        )
        append_audit_record(
            conn,
            "order_transition",
            order_id,
            reason,
            {
                "order_id": order_id,
                "from_status": from_status,
                "to_status": to_status,
                "reason": reason,
                "payload": clean_payload,
            },
        )
        conn.commit()


def update_order_state(
    order_id: str,
    status: str | None = None,
    venue_order_id: str | None = None,
    venue_status: str | None = None,
    reconcile_status: str | None = None,
    reconcile_note: str | None = None,
    reason: str = "state_update",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    order = get_order(order_id)
    if not order:
        raise ValueError(f"Order {order_id} was not found")
    new_status = status or order["status"]
    now = utc_now()
    with DB_LOCK, connect() as conn:
        conn.execute(
            """
            UPDATE orders
            SET status = ?,
                venue_order_id = COALESCE(?, venue_order_id),
                venue_status = COALESCE(?, venue_status),
                reconcile_status = COALESCE(?, reconcile_status),
                reconcile_note = COALESCE(?, reconcile_note),
                last_reconciled_at = CASE WHEN ? IS NOT NULL THEN ? ELSE last_reconciled_at END,
                updated_at = ?
            WHERE id = ?
            """,
            (
                new_status,
                venue_order_id,
                venue_status,
                reconcile_status,
                reconcile_note,
                reconcile_status,
                now,
                now,
                order_id,
            ),
        )
        conn.commit()
    if new_status != order["status"] or reconcile_status or venue_status:
        insert_order_transition(
            order_id,
            order["status"],
            new_status,
            reason,
            payload or {
                "venue_status": venue_status,
                "venue_order_id": venue_order_id,
                "reconcile_status": reconcile_status,
                "reconcile_note": reconcile_note,
            },
        )
    return get_order(order_id) or {}


def reconcile_order(order_id: str) -> dict[str, Any]:
    order = get_order(order_id)
    if not order:
        raise ValueError(f"Order {order_id} was not found")
    positions = get_positions(status=None, limit=500)
    linked_position = next((position for position in positions if position.get("order_id") == order_id), None)
    if order["status"] == "paper_filled":
        note = (
            f"Paper fill matched position {linked_position['id']}."
            if linked_position
            else "Paper fill has no linked position; manual review required."
        )
        return update_order_state(
            order_id,
            venue_status="PAPER_FILLED",
            reconcile_status="reconciled" if linked_position else "needs_review",
            reconcile_note=note,
            reason="paper_reconcile",
        )
    if order["status"] == "testnet_validated":
        return update_order_state(
            order_id,
            venue_status="ORDER_TEST_ACCEPTED",
            reconcile_status="validated_no_live_order",
            reconcile_note="Binance /fapi/v1/order/test accepted the payload; no venue order exists.",
            reason="testnet_validate_reconcile",
        )
    if order["status"] in {
        "testnet_submitted",
        "testnet_protection_submitted",
        "live_submitted",
        "live_protection_submitted",
        "pending_reconcile",
    }:
        order_mode = (
            "live_guarded"
            if str(order.get("id", "")).startswith("LIVE") or str(order.get("status", "")).startswith("live_")
            else "binance_testnet_place_order"
        )
        live_order = order_mode == "live_guarded"
        if live_order:
            venue_ready = ENABLE_BINANCE_LIVE and BINANCE_LIVE_API_KEY and BINANCE_LIVE_API_SECRET
            missing_note = "Binance live keys are not configured; cannot query venue order."
        else:
            venue_ready = ENABLE_BINANCE_TESTNET and BINANCE_API_KEY and BINANCE_API_SECRET
            missing_note = "Binance testnet keys are not configured; cannot query venue order."
        if not venue_ready:
            return update_order_state(
                order_id,
                venue_status=order.get("venue_status") or "UNKNOWN",
                reconcile_status="needs_reconcile",
                reconcile_note=missing_note,
                reason="binance_reconcile_missing_keys",
            )
        try:
            response = signed_binance_request_for_mode(
                "GET",
                "/fapi/v1/order",
                {
                    "symbol": order["symbol"],
                    "origClientOrderId": order["client_order_id"],
                },
                order_mode,
            )
            venue_status = str(response.get("status") or "UNKNOWN").upper()
            venue_order_id = str(response.get("orderId") or order.get("venue_order_id") or "")
            terminal = venue_status in {"FILLED", "CANCELED", "EXPIRED", "REJECTED"}
            prefix = "live" if live_order else "testnet"
            new_status = {
                "FILLED": f"{prefix}_filled",
                "CANCELED": f"{prefix}_canceled",
                "EXPIRED": f"{prefix}_canceled",
                "REJECTED": f"{prefix}_canceled",
            }.get(venue_status, f"{prefix}_submitted")
            return update_order_state(
                order_id,
                status=new_status,
                venue_order_id=venue_order_id or None,
                venue_status=venue_status,
                reconcile_status="reconciled" if terminal else "needs_reconcile",
                reconcile_note=(
                    f"Binance {'live' if live_order else 'testnet'} order status={venue_status}; "
                    f"orderId={venue_order_id or '-'}; executedQty={response.get('executedQty', '-')}; "
                    f"avgPrice={response.get('avgPrice', '-')}."
                ),
                reason="binance_order_reconcile",
                payload={"response": response},
            )
        except Exception as exc:
            return update_order_state(
                order_id,
                venue_status=order.get("venue_status") or "UNKNOWN",
                reconcile_status="needs_reconcile",
                reconcile_note=f"Binance {'live' if live_order else 'testnet'} reconcile failed: {exc.__class__.__name__}: {exc}",
                reason="binance_order_reconcile_failed",
            )
    if order["status"] in NEEDS_RECONCILE_STATUSES:
        return update_order_state(
            order_id,
            venue_status=order.get("venue_status") or "UNKNOWN",
            reconcile_status="needs_reconcile",
            reconcile_note="Order is not terminal. Query venue/private stream before retrying.",
            reason="needs_reconcile",
        )
    if order["status"] == "paper_submitted":
        return update_order_state(
            order_id,
            venue_status="LEGACY_PAPER_SUBMITTED",
            reconcile_status="reviewed",
            reconcile_note="Legacy local paper order from before the position ledger; no venue retry is pending.",
            reason="legacy_paper_review",
        )
    reconcile_status = order.get("reconcile_status") or ""
    return update_order_state(
        order_id,
        venue_status=order.get("venue_status") or order["status"].upper(),
        reconcile_status="reviewed" if reconcile_status in {"", "unchecked"} else reconcile_status,
        reconcile_note=order.get("reconcile_note") or "No action required for current status.",
        reason="generic_reconcile",
    )


def reconcile_recent_orders(limit: int = 100) -> dict[str, Any]:
    reconciled: list[dict[str, Any]] = []
    for order in get_orders(limit=limit):
        reconciled.append(reconcile_order(order["id"]))
    return {"orders": reconciled, "summary": oms_summary(reconciled)}


def binance_order_mode_for_order(order: dict[str, Any]) -> str:
    if str(order.get("id", "")).startswith("LIVE") or str(order.get("status", "")).startswith("live_"):
        return "live_guarded"
    return "binance_testnet_place_order"


def cancel_testnet_order(order_id: str) -> dict[str, Any]:
    order = get_order(order_id)
    if not order:
        raise ValueError(f"Order {order_id} was not found")
    if order["status"] not in CANCELABLE_BINANCE_ORDER_STATUSES:
        raise ValueError("Only submitted Binance orders can be canceled by this endpoint.")
    order_mode = binance_order_mode_for_order(order)
    if order_mode == "live_guarded":
        if not (ENABLE_BINANCE_LIVE and BINANCE_LIVE_API_KEY and BINANCE_LIVE_API_SECRET):
            raise ValueError("Binance live keys are required before canceling a live order.")
        prefix = "live"
    else:
        if not (ENABLE_BINANCE_TESTNET and BINANCE_API_KEY and BINANCE_API_SECRET):
            raise ValueError("Binance testnet keys are required before canceling a testnet order.")
        prefix = "testnet"
    response = signed_binance_request_for_mode(
        "DELETE",
        "/fapi/v1/order",
        {
            "symbol": order["symbol"],
            "origClientOrderId": order["client_order_id"],
        },
        order_mode,
    )
    venue_status = str(response.get("status") or "CANCELED").upper()
    venue_order_id = str(response.get("orderId") or order.get("venue_order_id") or "")
    updated = update_order_state(
        order_id,
        status=(
            f"{prefix}_protection_canceled"
            if "protection" in str(order.get("status", "")) and venue_status in {"CANCELED", "EXPIRED"}
            else f"{prefix}_canceled"
            if venue_status in {"CANCELED", "EXPIRED"}
            else order["status"]
        ),
        venue_order_id=venue_order_id or None,
        venue_status=venue_status,
        reconcile_status="reconciled" if venue_status in {"CANCELED", "EXPIRED", "FILLED"} else "needs_reconcile",
        reconcile_note=(
            f"Binance {'live' if prefix == 'live' else 'testnet'} cancel response status={venue_status}; "
            f"orderId={venue_order_id or '-'}."
        ),
        reason="binance_order_cancel",
        payload={"response": response},
    )
    child_attempts: list[dict[str, Any]] = []
    if not order.get("parent_order_id") and venue_status in {"CANCELED", "EXPIRED"}:
        for child in get_child_protection_orders(order_id):
            attempt = {
                "order_id": child.get("id"),
                "kind": child.get("protection_kind"),
                "previous_status": child.get("status"),
            }
            if child.get("status") not in CANCELABLE_BINANCE_ORDER_STATUSES:
                attempt.update({"status": "skipped", "reason": "child_order_not_cancelable"})
            else:
                try:
                    canceled_child = cancel_testnet_order(str(child["id"]))
                    attempt.update(
                        {
                            "status": "canceled",
                            "new_status": canceled_child.get("status"),
                            "venue_status": canceled_child.get("venue_status"),
                            "reconcile_status": canceled_child.get("reconcile_status"),
                        }
                    )
                except Exception as child_exc:  # noqa: BLE001 - parent cancel should still return with child evidence.
                    attempt.update(
                        {
                            "status": "failed",
                            "error_type": child_exc.__class__.__name__,
                            "error": str(child_exc),
                        }
                    )
            child_attempts.append(attempt)
        if child_attempts:
            updated["child_protection_cancel_attempts"] = child_attempts
            insert_order_transition(
                order_id,
                updated.get("status"),
                updated.get("status", order.get("status")),
                "binance_child_protection_cancel_after_parent_cancel",
                {"attempts": child_attempts},
            )
            failed_children = [item for item in child_attempts if item.get("status") == "failed"]
            if failed_children:
                raise_alert(
                    f"protection.cancel_after_parent_failed.{order_id}",
                    "critical",
                    "OMS",
                    f"Binance {prefix} child protection cancel failed",
                    (
                        f"Parent order {order_id} was canceled, but {len(failed_children)} child protection "
                        "order(s) could not be canceled automatically. Manual venue review is required."
                    ),
                    {"parent_order": updated, "attempts": child_attempts},
                )
    return updated


def cancel_open_binance_orders(limit: int = 200) -> list[dict[str, Any]]:
    placeholders = ", ".join("?" for _ in CANCELABLE_BINANCE_ORDER_STATUSES)
    with DB_LOCK, connect() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM orders
            WHERE status IN ({placeholders})
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [*CANCELABLE_BINANCE_ORDER_STATUSES, limit],
        ).fetchall()
    attempts: list[dict[str, Any]] = []
    for row in rows:
        order = dict(row)
        attempt = {
            "order_id": order.get("id"),
            "client_order_id": order.get("client_order_id"),
            "symbol": order.get("symbol"),
            "previous_status": order.get("status"),
            "mode": binance_order_mode_for_order(order),
        }
        try:
            canceled = cancel_testnet_order(order["id"])
            attempt.update(
                {
                    "status": "canceled",
                    "new_status": canceled.get("status"),
                    "venue_status": canceled.get("venue_status"),
                    "reconcile_status": canceled.get("reconcile_status"),
                }
            )
        except Exception as exc:
            attempt.update(
                {
                    "status": "failed",
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                }
            )
            try:
                update_order_state(
                    order["id"],
                    venue_status=order.get("venue_status") or "UNKNOWN",
                    reconcile_status="needs_reconcile",
                    reconcile_note=f"Emergency cancel failed: {exc.__class__.__name__}: {exc}",
                    reason="emergency_cancel_failed",
                    payload={"panic_cancel_attempt": attempt},
                )
            except Exception:
                pass
        attempts.append(attempt)
    return attempts


def binance_emergency_modes() -> list[str]:
    modes: list[str] = []
    if ENABLE_BINANCE_TESTNET and BINANCE_API_KEY and BINANCE_API_SECRET:
        modes.append("binance_testnet_place_order")
    if ENABLE_BINANCE_LIVE and BINANCE_LIVE_API_KEY and BINANCE_LIVE_API_SECRET:
        modes.append("live_guarded")
    return modes


def binance_emergency_symbols(
    mode: str,
    snapshot: dict[str, Any] | None = None,
    explicit_symbols: list[str] | None = None,
) -> list[str]:
    symbols = set()
    for symbol in explicit_symbols or []:
        clean = "".join(ch for ch in str(symbol).upper() if ch.isalnum())
        if clean:
            symbols.add(clean)
    for symbol in risk_config().get("allowed_symbols") or []:
        clean = "".join(ch for ch in str(symbol).upper() if ch.isalnum())
        if clean:
            symbols.add(clean)
    for position in (snapshot or {}).get("positions") or []:
        clean = "".join(ch for ch in str(position.get("symbol") or "").upper() if ch.isalnum())
        if clean:
            symbols.add(clean)
    mode_prefix = "live_" if mode == "live_guarded" else "testnet_"
    for order in get_orders(limit=200):
        if order.get("status") in CANCELABLE_BINANCE_ORDER_STATUSES or str(order.get("status") or "").startswith(mode_prefix):
            clean = "".join(ch for ch in str(order.get("symbol") or "").upper() if ch.isalnum())
            if clean:
                symbols.add(clean)
    return sorted(symbols)


def cancel_all_open_exchange_orders(
    modes: list[str] | None = None,
    explicit_symbols: list[str] | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for mode in modes or binance_emergency_modes():
        try:
            normalized = ensure_binance_account_mode(mode)
        except Exception as exc:
            results.append(
                {
                    "mode": mode,
                    "status": "skipped",
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                }
            )
            continue
        snapshot: dict[str, Any] | None = None
        try:
            snapshot = sync_exchange_account_snapshot(normalized)
        except Exception as exc:
            results.append(
                {
                    "mode": normalized,
                    "action": "account_snapshot",
                    "status": "failed",
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                }
            )
        symbols = binance_emergency_symbols(normalized, snapshot=snapshot, explicit_symbols=explicit_symbols)
        for symbol in symbols:
            item = {"mode": normalized, "symbol": symbol, "action": "cancel_all_open_orders"}
            try:
                response = signed_binance_request_for_mode(
                    "DELETE",
                    "/fapi/v1/allOpenOrders",
                    {"symbol": symbol},
                    normalized,
                )
                item.update({"status": "sent", "response": response})
            except Exception as exc:
                item.update(
                    {
                        "status": "failed",
                        "error_type": exc.__class__.__name__,
                        "error": str(exc),
                    }
                )
            results.append(item)
    return results


def binance_flatten_position_params(position: dict[str, Any], mode: str) -> tuple[dict[str, Any], dict[str, Any]]:
    symbol = "".join(ch for ch in str(position.get("symbol") or "").upper() if ch.isalnum())
    if not symbol:
        raise ValueError("Position is missing symbol.")
    amount = Decimal(str(position.get("positionAmt") or position.get("pa") or "0"))
    if amount == 0:
        raise ValueError(f"Position {symbol} has zero quantity.")
    rules = binance_symbol_rules(symbol, mode)
    step_size = Decimal(str(rules["step_size"]))
    quantity = decimal_floor_to_step(abs(amount), step_size)
    min_qty = Decimal(str(rules["min_qty"]))
    if quantity <= 0 or (min_qty > 0 and quantity < min_qty):
        raise ValueError(f"Flatten quantity {decimal_text(quantity)} is below Binance minQty {rules['min_qty']} for {symbol}.")
    position_side = str(position.get("positionSide") or "BOTH").upper()
    side = "SELL" if amount > 0 else "BUY"
    client_order_id = f"FLAT-{symbol[:12]}-{str(uuid.uuid4())[:8].upper()}"
    params = {
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "quantity": decimal_text(quantity),
        "newClientOrderId": client_order_id,
        "newOrderRespType": "RESULT",
    }
    if position_side and position_side != "BOTH":
        params["positionSide"] = position_side
    else:
        params["reduceOnly"] = "true"
    evidence = {
        "symbol": symbol,
        "mode": mode,
        "position_amt": decimal_text(amount),
        "position_side": position_side,
        "side": side,
        "quantity": params["quantity"],
        "reduce_only": params.get("reduceOnly") == "true",
        "client_order_id": client_order_id,
        "rules": rules,
    }
    return params, evidence


def binance_flatten_positions(
    mode: str,
    dry_run: bool = True,
    confirmation: str = "",
) -> dict[str, Any]:
    normalized = ensure_binance_account_mode(mode)
    if not dry_run and confirmation != "FLATTEN_POSITIONS":
        raise ValueError("Live/Testnet flatten requires confirmation=FLATTEN_POSITIONS.")
    snapshot = sync_exchange_account_snapshot(normalized)
    plan: list[dict[str, Any]] = []
    submissions: list[dict[str, Any]] = []
    for position in snapshot.get("positions") or []:
        try:
            params, evidence = binance_flatten_position_params(position, normalized)
            item = {"status": "planned", "params": params, "evidence": evidence}
            plan.append(item)
            if not dry_run:
                response = signed_binance_request_for_mode("POST", "/fapi/v1/order", params, normalized)
                submissions.append({"status": "submitted", "params": params, "response": response})
        except Exception as exc:
            plan.append(
                {
                    "status": "failed",
                    "symbol": position.get("symbol"),
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                }
            )
    result = {
        "mode": normalized,
        "dry_run": dry_run,
        "snapshot_id": snapshot.get("id"),
        "snapshot_ts": snapshot.get("ts"),
        "position_count": len(snapshot.get("positions") or []),
        "planned_count": sum(1 for item in plan if item.get("status") == "planned"),
        "failed_count": sum(1 for item in plan if item.get("status") == "failed"),
        "submitted_count": len(submissions),
        "plan": plan,
        "submissions": submissions,
        "created_at": utc_now(),
    }
    set_setting("exchange_emergency_plan_last_at", result["created_at"])
    set_setting(
        "exchange_emergency_plan_last_report",
        json.dumps(
            {
                "mode": normalized,
                "dry_run": dry_run,
                "position_count": result["position_count"],
                "planned_count": result["planned_count"],
                "failed_count": result["failed_count"],
                "submitted_count": result["submitted_count"],
                "created_at": result["created_at"],
            },
            ensure_ascii=False,
        ),
    )
    insert_event(
        "system",
        "system",
        "Exchange Emergency",
        "交易所平仓预案已生成" if dry_run else "交易所应急平仓已提交",
        (
            f"{mode_label(normalized)} 持仓 {result['position_count']} 个，"
            f"可平仓 {result['planned_count']} 个，失败 {result['failed_count']} 个。"
        ),
        result,
    )
    return result


def emergency_panic_stop(settings: dict[str, Any]) -> dict[str, Any]:
    confirmation = str(settings.get("confirmation") or "").strip()
    if confirmation != "PANIC_STOP":
        raise ValueError("Panic stop requires confirmation=PANIC_STOP.")
    reason = str(settings.get("reason") or "manual_panic_stop").strip()[:200]
    cancel_orders = coerce_bool(settings.get("cancel_orders", True))
    cancel_exchange_orders = coerce_bool(settings.get("cancel_exchange_open_orders", True))
    flatten_positions = coerce_bool(settings.get("flatten_positions", False))
    reconcile_after = coerce_bool(settings.get("reconcile", True))
    set_setting("emergency_stop", "true")
    set_setting("scheduler_enabled", "false")
    set_setting("testnet_drill_enabled", "false")
    arming = disarm_live_trading(f"panic_stop: {reason}")
    cancel_attempts = cancel_open_binance_orders() if cancel_orders else []
    exchange_cancel_attempts = cancel_all_open_exchange_orders() if cancel_exchange_orders else []
    flatten_attempts: list[dict[str, Any]] = []
    if flatten_positions:
        for mode in binance_emergency_modes():
            try:
                flatten_attempts.append(
                    binance_flatten_positions(
                        mode,
                        dry_run=False,
                        confirmation=str(settings.get("flatten_confirmation") or ""),
                    )
                )
            except Exception as exc:
                flatten_attempts.append(
                    {
                        "mode": mode,
                        "status": "failed",
                        "error_type": exc.__class__.__name__,
                        "error": str(exc),
                    }
                )
    reconcile_result: dict[str, Any] = {"skipped": not reconcile_after}
    if reconcile_after:
        try:
            reconcile_result = reconcile_recent_orders(limit=100)
        except Exception as exc:
            reconcile_result = {
                "error_type": exc.__class__.__name__,
                "error": str(exc),
                "summary": oms_summary(),
            }
    alerts = run_watchdog_checks()
    report = {
        "status": "panic_stop_active",
        "reason": reason,
        "emergency_stop": True,
        "scheduler_enabled": False,
        "testnet_drill_enabled": False,
        "live_arming": arming,
        "cancel_orders": cancel_orders,
        "cancel_attempts": cancel_attempts,
        "cancel_exchange_open_orders": cancel_exchange_orders,
        "exchange_cancel_attempts": exchange_cancel_attempts,
        "exchange_cancel_failed": [item for item in exchange_cancel_attempts if item.get("status") == "failed"],
        "flatten_positions": flatten_positions,
        "flatten_attempts": flatten_attempts,
        "flatten_failed": [item for item in flatten_attempts if item.get("status") == "failed" or item.get("failed_count", 0) > 0],
        "cancel_failed": [item for item in cancel_attempts if item.get("status") == "failed"],
        "oms": (reconcile_result.get("summary") if isinstance(reconcile_result, dict) else None) or oms_summary(),
        "alerts": alerts.get("summary", {}),
        "created_at": utc_now(),
    }
    set_setting("panic_stop_last_at", report["created_at"])
    set_setting(
        "panic_stop_last_report",
        json.dumps(
            {
                "reason": reason,
                "cancel_attempt_count": len(cancel_attempts),
                "cancel_failed_count": len(report["cancel_failed"]),
                "exchange_cancel_attempt_count": len(exchange_cancel_attempts),
                "exchange_cancel_failed_count": len(report["exchange_cancel_failed"]),
                "flatten_attempt_count": len(flatten_attempts),
                "flatten_failed_count": len(report["flatten_failed"]),
                "oms": report["oms"],
                "created_at": report["created_at"],
            },
            ensure_ascii=False,
        ),
    )
    insert_event(
        "system",
        "system",
        "Emergency Stop",
        "事故停机已执行",
        (
            "系统已开启紧急停止、关闭调度与测试网演练、解除实盘武装，"
            "并按配置尝试撤销未终态 Binance 订单。"
        ),
        report,
    )
    raise_alert(
        "panic_stop.active",
        "critical",
        "Risk Center",
        "事故停机已执行",
        f"事故停机原因：{reason}。系统已拒绝新订单；请完成对账后再手动解除停止。",
        report,
    )
    return report


def reset_emergency_stop(reason: str = "manual_reset") -> dict[str, Any]:
    clean_reason = str(reason or "manual_reset").strip()[:200]
    set_setting("emergency_stop", "false")
    resolved_alerts = [
        alert
        for alert in [
            resolve_alert("risk.emergency_stop", clean_reason),
            resolve_alert("panic_stop.active", clean_reason),
        ]
        if alert
    ]
    report = {
        "emergency_stop": False,
        "reason": clean_reason,
        "resolved_alerts": resolved_alerts,
        "resolved_alert_count": len(resolved_alerts),
        "updated_at": utc_now(),
    }
    insert_event(
        "system",
        "system",
        "Emergency Stop",
        "Emergency stop reset",
        f"Emergency stop was reset; reason={clean_reason}.",
        report,
    )
    return report


def oms_summary(orders: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = orders if orders is not None else get_orders(limit=100)
    total = len(rows)
    reconciled = sum(
        1
        for order in rows
        if order.get("reconcile_status") in {"reconciled", "validated_no_live_order", "reviewed"}
    )
    needs = sum(
        1
        for order in rows
        if order.get("reconcile_status") in {"unchecked", "needs_reconcile", "needs_review"}
    )
    unknown = sum(1 for order in rows if (order.get("venue_status") or "").upper() == "UNKNOWN")
    latest = rows[0] if rows else None
    return {
        "total_orders": total,
        "reconciled_orders": reconciled,
        "needs_reconcile": needs,
        "unknown_venue_status": unknown,
        "latest_order_id": (latest or {}).get("id"),
        "latest_order_status": (latest or {}).get("status"),
        "updated_at": utc_now(),
    }


def create_backtest_run(symbol: str, interval: str, bars: int, params: dict[str, Any]) -> dict[str, Any]:
    run_id = f"BT-{str(uuid.uuid4())[:8].upper()}"
    now = utc_now()
    with DB_LOCK, connect() as conn:
        conn.execute(
            """
            INSERT INTO backtest_runs(id, symbol, interval, bars, status, created_at, params)
            VALUES(?, ?, ?, ?, 'running', ?, ?)
            """,
            (
                run_id,
                symbol.upper().strip(),
                interval,
                bars,
                now,
                json.dumps(params),
            ),
        )
        conn.commit()
    return get_backtest_run(run_id) or {}


def get_backtest_run(run_id: str) -> dict[str, Any] | None:
    with DB_LOCK, connect() as conn:
        row = conn.execute("SELECT * FROM backtest_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["params"] = json.loads(item.get("params") or "{}")
    item["metrics"] = json.loads(item.get("metrics") or "{}")
    return item


def update_backtest_run(run_id: str, status: str, metrics: dict[str, Any]) -> None:
    with DB_LOCK, connect() as conn:
        conn.execute(
            """
            UPDATE backtest_runs
            SET status = ?, completed_at = ?, metrics = ?
            WHERE id = ?
            """,
            (status, utc_now(), json.dumps(metrics), run_id),
        )
        conn.commit()


def get_backtests(limit: int = 10) -> list[dict[str, Any]]:
    with DB_LOCK, connect() as conn:
        rows = conn.execute(
            "SELECT * FROM backtest_runs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["params"] = json.loads(item.get("params") or "{}")
        item["metrics"] = json.loads(item.get("metrics") or "{}")
        items.append(item)
    return items


def insert_backtest_trades(backtest_id: str, trades: list[dict[str, Any]]) -> None:
    if not trades:
        return
    with DB_LOCK, connect() as conn:
        conn.executemany(
            """
            INSERT INTO backtest_trades(
                backtest_id, symbol, side, opened_at, closed_at,
                entry_price, exit_price, quantity, leverage,
                pnl_usdt, return_pct, reason
            )
            VALUES(
                :backtest_id, :symbol, :side, :opened_at, :closed_at,
                :entry_price, :exit_price, :quantity, :leverage,
                :pnl_usdt, :return_pct, :reason
            )
            """,
            [{**trade, "backtest_id": backtest_id} for trade in trades],
        )
        conn.commit()


def get_backtest_trades(backtest_id: str | None, limit: int = 100) -> list[dict[str, Any]]:
    if not backtest_id:
        return []
    with DB_LOCK, connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM backtest_trades
            WHERE backtest_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (backtest_id, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def get_positions(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    query = "SELECT * FROM positions"
    params: list[Any] = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY opened_at DESC LIMIT ?"
    params.append(limit)
    with DB_LOCK, connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_position(position_id: str) -> dict[str, Any] | None:
    with DB_LOCK, connect() as conn:
        row = conn.execute("SELECT * FROM positions WHERE id = ?", (position_id,)).fetchone()
    return dict_row(row)


def latest_market_marks(limit: int = 200) -> dict[str, dict[str, Any]]:
    query = """
        SELECT payload FROM events
        WHERE actor = 'Market Data'
        ORDER BY id DESC
        LIMIT ?
    """
    marks: dict[str, dict[str, Any]] = {}
    with DB_LOCK, connect() as conn:
        rows = conn.execute(query, (limit,)).fetchall()
    for row in rows:
        payload = json.loads(row["payload"] or "{}")
        symbol = payload.get("symbol")
        if symbol and symbol not in marks:
            marks[symbol] = payload
    return marks


def mark_position(position: dict[str, Any], market: dict[str, Any] | None) -> dict[str, Any]:
    mark_price = float((market or {}).get("mark_price") or position["mark_price"] or position["entry_price"])
    quantity = float(position["quantity"])
    entry_price = float(position["entry_price"])
    leverage = float(position["leverage"] or 1)
    side = position["side"]
    unrealized_pnl = (
        (mark_price - entry_price) * quantity
        if side == "BUY"
        else (entry_price - mark_price) * quantity
    )
    entry_notional = entry_price * quantity
    mark_notional = mark_price * quantity
    used_margin = entry_notional / leverage if leverage else entry_notional
    roe_pct = (unrealized_pnl / used_margin) * 100 if used_margin else 0.0
    enriched = {
        **position,
        "mark_price": round(mark_price, 2),
        "entry_notional_usdt": round(entry_notional, 2),
        "mark_notional_usdt": round(mark_notional, 2),
        "used_margin_usdt": round(used_margin, 2),
        "unrealized_pnl_usdt": round(unrealized_pnl, 2),
        "roe_pct": round(roe_pct, 2),
        "mark_source": (market or {}).get("data_source", "entry_price"),
        "mark_timestamp": (market or {}).get("timestamp"),
    }
    return enriched


def enrich_closed_position(position: dict[str, Any]) -> dict[str, Any]:
    quantity = float(position["quantity"])
    entry_price = float(position["entry_price"])
    leverage = float(position["leverage"] or 1)
    entry_notional = entry_price * quantity
    used_margin = entry_notional / leverage if leverage else entry_notional
    realized_pnl = float(position.get("realized_pnl") or 0)
    roe_pct = (realized_pnl / used_margin) * 100 if used_margin else 0.0
    return {
        **position,
        "mark_price": round(float(position.get("exit_price") or position["mark_price"]), 2),
        "entry_notional_usdt": round(entry_notional, 2),
        "mark_notional_usdt": 0,
        "used_margin_usdt": 0,
        "unrealized_pnl_usdt": 0,
        "realized_pnl_usdt": round(realized_pnl, 2),
        "roe_pct": round(roe_pct, 2),
        "mark_source": "closed_position",
        "mark_timestamp": position.get("closed_at"),
    }


def paper_account_state() -> dict[str, Any]:
    open_positions = get_positions(status="open", limit=200)
    marks = latest_market_marks()
    marked_positions = [
        mark_position(position, marks.get(position["symbol"]))
        for position in open_positions
    ]
    recent_positions = get_positions(status=None, limit=50)
    display_positions = [
        mark_position(position, marks.get(position["symbol"]))
        if position["status"] == "open"
        else enrich_closed_position(position)
        for position in recent_positions
    ]
    with DB_LOCK, connect() as conn:
        realized = conn.execute(
            "SELECT COALESCE(SUM(realized_pnl), 0) AS realized FROM positions WHERE status = 'closed'"
        ).fetchone()["realized"]
    unrealized = sum(position["unrealized_pnl_usdt"] for position in marked_positions)
    used_margin = sum(position["used_margin_usdt"] for position in marked_positions)
    exposure = sum(position["mark_notional_usdt"] for position in marked_positions)
    equity = ACCOUNT_EQUITY_USDT + realized + unrealized
    account = {
        "base_equity_usdt": round(ACCOUNT_EQUITY_USDT, 2),
        "equity_usdt": round(equity, 2),
        "realized_pnl_usdt": round(realized, 2),
        "unrealized_pnl_usdt": round(unrealized, 2),
        "used_margin_usdt": round(used_margin, 2),
        "free_margin_usdt": round(equity - used_margin, 2),
        "gross_exposure_usdt": round(exposure, 2),
        "open_position_count": len(marked_positions),
        "margin_usage_pct": round((used_margin / equity) * 100, 2) if equity else 0.0,
    }
    return {"account": account, "positions": display_positions}


def pct_change(old: float, new: float) -> float:
    if old == 0:
        return 0.0
    return ((new - old) / old) * 100


def http_get_json(path: str, params: dict[str, Any] | None = None) -> Any:
    query = f"?{urlencode(params)}" if params else ""
    url = f"{BINANCE_FAPI_BASE}{path}{query}"
    request = Request(url, headers={"User-Agent": "crypto-contract-ai-trader/0.1"})
    for attempt in range(HTTP_RETRIES + 1):
        try:
            with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return json.loads(response.read().decode(charset))
        except HTTPError as exc:
            retryable = exc.code in {418, 429, 500, 502, 503, 504}
            if not retryable or attempt >= HTTP_RETRIES:
                raise
            time.sleep(0.6 * (attempt + 1))
    raise RuntimeError("unreachable")


def http_get_json_base(base_url: str, path: str, params: dict[str, Any] | None = None) -> Any:
    query = f"?{urlencode(params)}" if params else ""
    url = f"{base_url.rstrip('/')}{path}{query}"
    request = Request(url, headers={"User-Agent": "crypto-contract-ai-trader/0.1"})
    for attempt in range(HTTP_RETRIES + 1):
        try:
            with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return json.loads(response.read().decode(charset))
        except HTTPError as exc:
            retryable = exc.code in {418, 429, 500, 502, 503, 504}
            if not retryable or attempt >= HTTP_RETRIES:
                raise
            time.sleep(0.6 * (attempt + 1))
    raise RuntimeError("unreachable")


def http_post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> Any:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "crypto-contract-ai-trader/0.1",
            **headers,
        },
        method="POST",
    )
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset))


def enabled_modes() -> list[str]:
    modes = ["paper"]
    if ENABLE_BINANCE_TESTNET and BINANCE_API_KEY and BINANCE_API_SECRET:
        modes.append("binance_testnet_validate")
        if BINANCE_PLACE_TESTNET_ORDERS:
            modes.append("binance_testnet_place_order")
    if (
        ENABLE_BINANCE_LIVE
        and BINANCE_LIVE_API_KEY
        and BINANCE_LIVE_API_SECRET
        and BINANCE_PLACE_LIVE_ORDERS
        and LIVE_TRADING_CONFIRMATION == "I_UNDERSTAND_LIVE_RISK"
    ):
        modes.append("live_guarded")
    return modes


def mode_label(mode: str) -> str:
    labels = {
        "paper": "本地纸交易",
        "binance_testnet_validate": "Binance 测试网验证",
        "binance_testnet_place_order": "Binance 测试网真实下单",
        "live_guarded": "Binance 实盘保护模式",
    }
    return labels.get(mode, mode)


def source_label(value: str | None) -> str:
    labels = {
        "local": "本地",
        "server": "服务器",
        "paper": "本地纸交易",
        "binance_public": "Binance 公共行情",
        "synthetic": "本地合成行情",
        "rules": "本地规则",
        "deterministic_rules_v1": "确定性规则 v1",
        "low": "低",
        "medium": "中",
        "high": "高",
        "False": "否",
        "True": "是",
        "false": "否",
        "true": "是",
        "active": "已启动",
        "stopped": "已停止",
        "error": "异常",
        "connecting": "连接中",
        "reconnecting": "重连中",
        "expired": "已过期",
    }
    return labels.get(str(value), str(value or "-"))


def reason_label(value: str | None) -> str:
    labels = {
        "manual_run_now": "手动立即运行",
        "manual_scheduler_run": "手动调度运行",
        "interval": "定时运行",
    }
    return labels.get(str(value), str(value or "-"))


def zh_status(status: str | None) -> str:
    labels = {
        "approved": "通过",
        "warning": "警告",
        "rejected": "拒绝",
        "completed": "已完成",
        "failed": "失败",
        "prepared": "已准备",
        "paper_submitted": "纸交易已提交",
        "paper_filled": "纸交易已成交",
        "pending_reconcile": "待对账",
        "testnet_validated": "测试网已验证",
        "testnet_submitted": "测试网已提交",
        "testnet_protection_submitted": "测试网保护单已提交",
        "testnet_protection_canceled": "测试网保护单已取消",
        "testnet_filled": "测试网已成交",
        "testnet_canceled": "测试网已取消",
        "live_submitted": "实盘已提交",
        "live_protection_submitted": "实盘保护单已提交",
        "live_protection_canceled": "实盘保护单已取消",
        "live_filled": "实盘已成交",
        "live_canceled": "实盘已取消",
    }
    return labels.get(status or "", status or "-")


def zh_side(side: str | None) -> str:
    labels = {"BUY": "买入", "SELL": "卖出", "HOLD": "观望"}
    return labels.get(side or "", side or "-")


def ai_status() -> dict[str, Any]:
    configured = AI_PROVIDER != "rules"
    ready = AI_PROVIDER == "rules" or (AI_PROVIDER == "openai" and bool(OPENAI_API_KEY))
    if AI_PROVIDER not in {"rules", "openai"}:
        ready = False
    return {
        "provider": AI_PROVIDER,
        "model": AI_MODEL if AI_PROVIDER != "rules" else "deterministic_rules_v1",
        "configured": configured,
        "ready": ready,
        "key_present": bool(OPENAI_API_KEY) if AI_PROVIDER == "openai" else False,
        "fallback": None if ready else "AI 提供方未就绪；将使用确定性规则。",
    }


def exchange_status() -> dict[str, Any]:
    testnet_key_ready = bool(BINANCE_API_KEY and BINANCE_API_SECRET)
    live_key_ready = bool(BINANCE_LIVE_API_KEY and BINANCE_LIVE_API_SECRET)
    live_confirmation_ready = LIVE_TRADING_CONFIRMATION == "I_UNDERSTAND_LIVE_RISK"
    return {
        "provider": EXCHANGE_PROVIDER,
        "mode": EXCHANGE_MODE,
        "enabled_modes": enabled_modes(),
        "testnet_enabled": ENABLE_BINANCE_TESTNET,
        "testnet_key_ready": testnet_key_ready,
        "testnet_places_real_orders": BINANCE_PLACE_TESTNET_ORDERS,
        "sync_margin_type_before_order": BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER,
        "target_margin_type": BINANCE_TARGET_MARGIN_TYPE,
        "sync_leverage_before_order": BINANCE_SYNC_LEVERAGE_BEFORE_ORDER,
        "require_one_way_position_mode": BINANCE_REQUIRE_ONE_WAY_POSITION_MODE,
        "max_time_drift_ms": BINANCE_MAX_TIME_DRIFT_MS,
        "testnet_base_url": BINANCE_TESTNET_FAPI_BASE,
        "testnet_ws_base": BINANCE_TESTNET_WS_BASE,
        "live_enabled": ENABLE_BINANCE_LIVE,
        "live_key_ready": live_key_ready,
        "live_places_real_orders": BINANCE_PLACE_LIVE_ORDERS,
        "live_confirmation_ready": live_confirmation_ready,
        "live_base_url": BINANCE_LIVE_FAPI_BASE,
        "live_ws_base": BINANCE_LIVE_WS_BASE,
    }


def binance_time_base_for_mode(mode: str = "live_guarded") -> str:
    normalized = str(mode or "").lower().strip()
    if normalized == "binance_testnet_validate" or normalized == "binance_testnet_place_order":
        return BINANCE_TESTNET_FAPI_BASE
    if normalized == "live_guarded":
        return BINANCE_LIVE_FAPI_BASE
    return BINANCE_FAPI_BASE.rstrip("/")


def binance_time_drift_status(mode: str = "live_guarded") -> dict[str, Any]:
    normalized = str(mode or "live_guarded").lower().strip()
    base_url = binance_time_base_for_mode(normalized)
    started_ms = int(time.time() * 1000)
    payload = http_get_json_base(base_url, "/fapi/v1/time")
    completed_ms = int(time.time() * 1000)
    server_time_ms = int(payload.get("serverTime"))
    local_midpoint_ms = int((started_ms + completed_ms) / 2)
    drift_ms = local_midpoint_ms - server_time_ms
    abs_drift_ms = abs(drift_ms)
    roundtrip_ms = completed_ms - started_ms
    return {
        "status": "pass" if abs_drift_ms <= BINANCE_MAX_TIME_DRIFT_MS else "fail",
        "mode": normalized,
        "base_url": base_url,
        "server_time_ms": server_time_ms,
        "local_midpoint_ms": local_midpoint_ms,
        "drift_ms": drift_ms,
        "abs_drift_ms": abs_drift_ms,
        "roundtrip_ms": roundtrip_ms,
        "max_drift_ms": BINANCE_MAX_TIME_DRIFT_MS,
        "checked_at": utc_now(),
    }


def safe_binance_time_drift_status(mode: str = "live_guarded") -> dict[str, Any]:
    try:
        return binance_time_drift_status(mode)
    except Exception as exc:
        return {
            "status": "fail",
            "mode": str(mode or "live_guarded").lower().strip(),
            "error_type": exc.__class__.__name__,
            "error": str(exc),
            "max_drift_ms": BINANCE_MAX_TIME_DRIFT_MS,
            "checked_at": utc_now(),
        }


def live_arming_status() -> dict[str, Any]:
    armed_until_raw = get_setting("live_armed_until", "")
    armed_until = parse_iso_datetime(armed_until_raw)
    now = datetime.now(timezone.utc)
    try:
        order_count = int(float(get_setting("live_armed_order_count", "0") or "0"))
    except ValueError:
        order_count = 0
    remaining_orders = max(0, LIVE_ARMING_MAX_ORDERS - order_count)
    time_active = bool(armed_until and armed_until > now)
    armed = bool(time_active and remaining_orders > 0)
    remaining_seconds = int((armed_until - now).total_seconds()) if armed_until and armed_until > now else 0
    try:
        order_ids = json.loads(get_setting("live_armed_order_ids", "[]") or "[]")
    except json.JSONDecodeError:
        order_ids = []
    return {
        "armed": armed,
        "time_active": time_active,
        "armed_at": get_setting("live_armed_at", ""),
        "armed_until": armed_until_raw,
        "armed_by": get_setting("live_armed_by", ""),
        "reason": get_setting("live_armed_reason", ""),
        "remaining_seconds": remaining_seconds,
        "max_seconds": LIVE_ARMING_MAX_SECONDS,
        "order_count": order_count,
        "max_orders": LIVE_ARMING_MAX_ORDERS,
        "remaining_orders": remaining_orders,
        "order_ids": order_ids if isinstance(order_ids, list) else [],
        "disarmed_at": get_setting("live_disarmed_at", ""),
        "disarm_reason": get_setting("live_disarm_reason", ""),
        "confirmation_phrase": "ARM_LIVE_TRADING",
    }


def consume_live_arming_order(order_id: str) -> dict[str, Any]:
    status = live_arming_status()
    if not status["armed"]:
        raise ValueError("Live arming is not active or its order budget is exhausted.")
    order_ids = [str(item) for item in status.get("order_ids") or []]
    order_ids.append(str(order_id))
    set_setting("live_armed_order_count", str(status["order_count"] + 1))
    set_setting("live_armed_order_ids", json.dumps(order_ids[-100:], ensure_ascii=False))
    consumed = live_arming_status()
    insert_event(
        "system",
        "system",
        "Live Arming",
        "实盘授权额度已消耗",
        (
            f"实盘订单 {order_id} 已消耗本次武装额度；"
            f"剩余额度 {consumed['remaining_orders']}/{consumed['max_orders']}。"
        ),
        {"order_id": order_id, "arming": consumed},
    )
    return consumed


def live_attestation_status() -> dict[str, Any]:
    raw_payload = get_setting("live_attestation", "{}") or "{}"
    try:
        parsed = json.loads(raw_payload)
        payload = parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        payload = {}
    accepted = payload.get("accepted") if isinstance(payload.get("accepted"), dict) else {}
    required_ids = [item["id"] for item in LIVE_ATTESTATION_REQUIREMENTS]
    missing_ids = [requirement_id for requirement_id in required_ids if accepted.get(requirement_id) is not True]
    attested_at = str(payload.get("attested_at") or "")
    age_seconds = seconds_since(attested_at)
    max_age_seconds = LIVE_ATTESTATION_MAX_AGE_DAYS * 24 * 60 * 60
    fresh = age_seconds is not None and age_seconds <= max_age_seconds
    expired = bool(attested_at) and not fresh
    status = "pass" if not missing_ids and fresh else "fail"
    requirements = [
        {
            **item,
            "accepted": accepted.get(item["id"]) is True,
            "missing": item["id"] in missing_ids,
        }
        for item in LIVE_ATTESTATION_REQUIREMENTS
    ]
    return {
        "status": status,
        "requirements": requirements,
        "accepted": {key: accepted.get(key) is True for key in required_ids},
        "missing_ids": missing_ids,
        "attested_at": attested_at,
        "age_seconds": age_seconds,
        "max_age_seconds": max_age_seconds,
        "max_age_days": LIVE_ATTESTATION_MAX_AGE_DAYS,
        "expired": expired,
        "actor": str(payload.get("actor") or ""),
        "note": str(payload.get("note") or ""),
        "raw_payload": payload,
    }


def save_live_attestation(settings: dict[str, Any]) -> dict[str, Any]:
    confirmation = str(settings.get("confirmation") or "").strip()
    if confirmation != "LIVE_ATTESTATION_CONFIRMED":
        raise ValueError("Live attestation requires confirmation=LIVE_ATTESTATION_CONFIRMED.")
    accepted = settings.get("accepted")
    if not isinstance(accepted, dict):
        raise ValueError("Live attestation requires an accepted map.")
    required_ids = [item["id"] for item in LIVE_ATTESTATION_REQUIREMENTS]
    missing_ids = [requirement_id for requirement_id in required_ids if accepted.get(requirement_id) is not True]
    if missing_ids:
        raise ValueError(f"Live attestation is missing required evidence: {', '.join(missing_ids)}.")
    actor = str(settings.get("actor") or "dashboard").strip()[:80]
    note = str(settings.get("note") or "").strip()[:500]
    payload = {
        "attested_at": utc_now(),
        "actor": actor,
        "note": note,
        "accepted": {requirement_id: True for requirement_id in required_ids},
        "max_age_days": LIVE_ATTESTATION_MAX_AGE_DAYS,
    }
    set_setting("live_attestation", json.dumps(payload, ensure_ascii=False, sort_keys=True))
    status = live_attestation_status()
    insert_event(
        "system",
        "risk",
        "Live Attestation",
        "实盘人工证据已确认",
        f"{actor} 已确认 live API key、IP 白名单、合规、备份和小额试运行证据；有效期 {LIVE_ATTESTATION_MAX_AGE_DAYS} 天。",
        status,
    )
    return status


def clear_live_attestation(reason: str = "manual_clear") -> dict[str, Any]:
    clean_reason = str(reason or "manual_clear").strip()[:200]
    set_setting("live_attestation", "{}")
    status = live_attestation_status()
    insert_event(
        "system",
        "risk",
        "Live Attestation",
        "实盘人工证据已清除",
        f"实盘人工证据已清除；原因：{clean_reason}。",
        {"reason": clean_reason, "attestation": status},
    )
    return status


def go_live_gate_status() -> dict[str, Any]:
    exchange = exchange_status()
    live_mode_enabled = "live_guarded" in exchange["enabled_modes"]
    live_requested = bool(
        ENABLE_BINANCE_LIVE
        or BINANCE_PLACE_LIVE_ORDERS
        or EXCHANGE_MODE == "live_guarded"
        or BINANCE_LIVE_API_KEY
        or BINANCE_LIVE_API_SECRET
    )
    gates: list[dict[str, Any]] = []

    def add_gate(
        gate_id: str,
        label: str,
        status: str,
        detail: str,
        evidence: dict[str, Any] | None = None,
        required_for_live: bool = True,
    ) -> None:
        clean_status = status if status in {"pass", "warn", "fail"} else "warn"
        gates.append(
            {
                "id": gate_id,
                "label": label,
                "status": clean_status,
                "detail": detail,
                "evidence": evidence or {},
                "required_for_live": required_for_live,
                "blocks_live_order": required_for_live and clean_status != "pass",
            }
        )

    add_gate(
        "live_flags",
        "实盘显式开关",
        "pass" if live_mode_enabled else ("fail" if live_requested else "warn"),
        (
            "live_guarded 已启用；所有实盘 key、真实下单开关和确认短语均已配置。"
            if live_mode_enabled
            else "实盘仍处于锁定状态；需要 ENABLE_BINANCE_LIVE、BINANCE_PLACE_LIVE_ORDERS、live key 和确认短语同时满足。"
        ),
        {
            "live_enabled": ENABLE_BINANCE_LIVE,
            "live_key_ready": exchange["live_key_ready"],
            "live_places_real_orders": BINANCE_PLACE_LIVE_ORDERS,
            "live_confirmation_ready": exchange["live_confirmation_ready"],
            "exchange_mode": EXCHANGE_MODE,
        },
    )

    bind_is_public = TRADER_BIND_IP in {"0.0.0.0", "::", ""}
    deployment_profile_ok = APP_ENV == "server"
    server_auth_ok = APP_ENV != "server" or AUTH_ENABLED
    private_network_ok = APP_ENV != "server" or not bind_is_public
    add_gate(
        "deployment_profile",
        "服务器部署档案",
        "pass" if deployment_profile_ok else ("fail" if live_requested else "warn"),
        (
            "当前运行于服务器档案；可以继续检查认证、私有网络和实盘准入项。"
            if deployment_profile_ok
            else "真实实盘只允许在 APP_ENV=server 的服务器部署档案下启用；本地模式只能用于纸交易、回测和演练。"
        ),
        {"app_env": APP_ENV, "required_app_env": "server"},
    )
    add_gate(
        "server_auth",
        "服务器认证",
        "pass" if server_auth_ok else "fail",
        "服务器模式已配置 Basic Auth。" if AUTH_ENABLED else "服务器模式必须配置 APP_BASIC_AUTH_USER 和强密码。",
        {"app_env": APP_ENV, "auth_enabled": AUTH_ENABLED},
    )
    add_gate(
        "private_network",
        "私有网络访问",
        "pass" if private_network_ok else "fail",
        "交易控制台未直接绑定公网地址。" if private_network_ok else "服务器上不能把 8787 直接绑定到 0.0.0.0 公网。",
        {"app_env": APP_ENV, "trader_bind_ip": TRADER_BIND_IP},
    )
    attestation = live_attestation_status()
    attestation_required = live_requested or live_mode_enabled
    attestation_passed = attestation.get("status") == "pass"
    add_gate(
        "live_attestation",
        "实盘人工证据",
        "pass" if attestation_passed else ("fail" if attestation_required else "warn"),
        (
            f"{attestation.get('actor') or 'operator'} 已在 {attestation.get('attested_at')} 确认外部证据；"
            f"有效期 {attestation.get('max_age_days')} 天。"
            if attestation_passed
            else "实盘前必须一次性确认：live API key 关闭提现、绑定服务器出口 IP、合规可用、离线备份已复制、小额试运行额度已确认。"
        ),
        {"attestation": attestation},
        required_for_live=attestation_required,
    )
    time_check_mode = "live_guarded" if live_requested or live_mode_enabled else "paper"
    time_drift = (
        safe_binance_time_drift_status(time_check_mode)
        if live_requested or live_mode_enabled
        else {
            "status": "pass",
            "mode": time_check_mode,
            "skipped": True,
            "reason": "live_not_requested",
            "max_drift_ms": BINANCE_MAX_TIME_DRIFT_MS,
            "checked_at": utc_now(),
        }
    )
    time_drift_ok = time_drift.get("status") == "pass"
    add_gate(
        "binance_time_drift",
        "Binance 时间漂移",
        "pass" if time_drift_ok else ("fail" if live_requested or live_mode_enabled else "warn"),
        (
            f"本机与 Binance serverTime 漂移 {time_drift.get('abs_drift_ms')}ms，往返 {time_drift.get('roundtrip_ms')}ms，低于阈值 {BINANCE_MAX_TIME_DRIFT_MS}ms。"
            if time_drift_ok and not time_drift.get("skipped")
            else "实盘未请求；启用 live 前会强制检查本机时间与 Binance serverTime 漂移。"
            if time_drift.get("skipped")
            else "无法确认本机时间与 Binance serverTime 的漂移在阈值内；签名请求可能因 timestamp 超窗失败。"
        ),
        {"time_drift": time_drift},
        required_for_live=live_requested or live_mode_enabled,
    )

    risk = risk_config()
    risk_failures: list[str] = []
    if risk["emergency_stop"]:
        risk_failures.append("紧急停止仍然开启")
    if risk["max_leverage"] > 3:
        risk_failures.append("最大杠杆超过 3x")
    if risk["max_position_pct"] > 0.05:
        risk_failures.append("单笔仓位超过 5%")
    if risk["max_order_notional_usdt"] <= 0:
        risk_failures.append("单笔名义金额未设置绝对上限")
    if risk["max_daily_loss_pct"] > 0.03:
        risk_failures.append("日亏损阈值超过 3%")
    if not risk["allowed_symbols"]:
        risk_failures.append("交易白名单为空")
    add_gate(
        "risk_controls",
        "风控阈值",
        "fail" if risk_failures else "pass",
        "；".join(risk_failures) if risk_failures else "杠杆、仓位、日亏损、交易对白名单和紧急停止均满足实盘前置要求。",
        {"risk": risk},
    )
    margin_type_valid = BINANCE_TARGET_MARGIN_TYPE in {"ISOLATED", "CROSSED"}
    margin_type_ready = BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER and margin_type_valid
    add_gate(
        "exchange_margin_type_sync",
        "Binance 保证金模式同步",
        "pass" if margin_type_ready else ("fail" if live_requested else "warn"),
        (
            f"真实 Testnet/实盘下单前会先调用 /fapi/v1/marginType 同步为 {BINANCE_TARGET_MARGIN_TYPE}，并把响应写入订单审计。"
            if margin_type_ready
            else "真实 Testnet/实盘下单前未启用或未正确配置保证金模式同步；实盘前必须开启。"
        ),
        {
            "sync_enabled": BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER,
            "endpoint": "/fapi/v1/marginType",
            "target_margin_type": BINANCE_TARGET_MARGIN_TYPE,
            "valid_margin_type": margin_type_valid,
        },
    )
    add_gate(
        "exchange_leverage_sync",
        "Binance 杠杆同步",
        "pass" if BINANCE_SYNC_LEVERAGE_BEFORE_ORDER else ("fail" if live_requested else "warn"),
        (
            "真实 Testnet/实盘下单前会先调用 /fapi/v1/leverage 同步交易对杠杆，并把响应写入订单审计。"
            if BINANCE_SYNC_LEVERAGE_BEFORE_ORDER
            else "真实 Testnet/实盘下单前未启用交易所杠杆同步；实盘前必须开启。"
        ),
        {
            "sync_enabled": BINANCE_SYNC_LEVERAGE_BEFORE_ORDER,
            "endpoint": "/fapi/v1/leverage",
            "max_leverage": risk["max_leverage"],
        },
    )
    recovery_for_position_mode = exchange_recovery_status()
    position_modes = (recovery_for_position_mode.get("last_report") or {}).get("position_modes") or []
    live_position_mode = next((item for item in position_modes if item.get("mode") == "live_guarded"), None)
    any_one_way_mode = next((item for item in position_modes if item.get("position_mode") == "ONE_WAY"), None)
    position_mode_required = live_requested or live_mode_enabled
    position_mode_evidence = live_position_mode if position_mode_required else (live_position_mode or any_one_way_mode)
    one_way_verified = bool(position_mode_evidence and position_mode_evidence.get("position_mode") == "ONE_WAY")
    one_way_ready = BINANCE_REQUIRE_ONE_WAY_POSITION_MODE and one_way_verified
    add_gate(
        "exchange_position_mode",
        "Binance 持仓模式",
        "pass" if one_way_ready else ("fail" if position_mode_required else "warn"),
        (
            "Binance 持仓模式已验证为 One-way；订单使用 BOTH 单向持仓语义。"
            if one_way_ready
            else "实盘前必须通过交易所恢复同步验证 Binance 持仓模式为 One-way，避免 Hedge Mode 下订单被拒。"
        ),
        {
            "required_one_way": BINANCE_REQUIRE_ONE_WAY_POSITION_MODE,
            "required": position_mode_required,
            "position_mode": (position_mode_evidence or {}).get("position_mode"),
            "mode": (position_mode_evidence or {}).get("mode"),
            "synced_at": (position_mode_evidence or {}).get("synced_at"),
            "available_modes": position_modes,
        },
        required_for_live=position_mode_required,
    )

    panic_last_at = get_setting("panic_stop_last_at", "")
    panic_age = seconds_since(panic_last_at)
    panic_recent = panic_age is not None and panic_age <= 7 * 24 * 60 * 60
    add_gate(
        "panic_stop_drill",
        "事故停机演练",
        "pass" if panic_recent else ("fail" if live_requested else "warn"),
        (
            f"最近一次事故停机演练在 {panic_last_at}，已验证紧急停止、解除武装、停调度和撤单流程。"
            if panic_recent
            else "实盘前必须从 UI/API 跑一次 PANIC_STOP 事故停机演练，并确认系统可恢复。"
        ),
        {
            "last_at": panic_last_at,
            "age_seconds": panic_age,
            "max_age_seconds": 7 * 24 * 60 * 60,
        },
    )

    exchange_emergency_last_at = get_setting("exchange_emergency_plan_last_at", "")
    exchange_emergency_age = seconds_since(exchange_emergency_last_at)
    exchange_emergency_recent = exchange_emergency_age is not None and exchange_emergency_age <= 7 * 24 * 60 * 60
    add_gate(
        "exchange_emergency_controls",
        "交易所应急撤单/平仓预案",
        "pass" if exchange_emergency_recent else ("fail" if live_requested else "warn"),
        (
            f"最近一次交易所级应急预案在 {exchange_emergency_last_at}，已验证全局撤单入口和平仓参数生成。"
            if exchange_emergency_recent
            else "实盘前必须验证交易所全局撤单和平仓预案；真实平仓提交必须要求 FLATTEN_POSITIONS。"
        ),
        {
            "last_at": exchange_emergency_last_at,
            "age_seconds": exchange_emergency_age,
            "max_age_seconds": 7 * 24 * 60 * 60,
        },
    )

    restore_last_at = get_setting("restore_state_drill_last_at", "")
    restore_age = seconds_since(restore_last_at)
    restore_recent = restore_age is not None and restore_age <= 7 * 24 * 60 * 60
    add_gate(
        "backup_restore_drill",
        "备份恢复演练",
        "pass" if restore_recent else ("fail" if live_requested else "warn"),
        (
            f"最近一次备份恢复演练在 {restore_last_at}，已验证备份包、SQLite integrity 和临时库恢复。"
            if restore_recent
            else "实盘前必须通过备份 dry-run 与临时库恢复检查，确认事故后可恢复 data/trader.db。"
        ),
        {
            "last_at": restore_last_at,
            "age_seconds": restore_age,
            "max_age_seconds": 7 * 24 * 60 * 60,
            "last_backup": get_setting("restore_state_drill_last_backup", ""),
        },
    )

    oms = oms_summary()
    oms_ok = oms["needs_reconcile"] == 0 and oms["unknown_venue_status"] == 0
    add_gate(
        "oms_reconciled",
        "OMS 对账",
        "pass" if oms_ok else "fail",
        "近期订单无待对账或未知交易所状态。" if oms_ok else "存在待对账或 UNKNOWN 订单，必须先 reconcile。",
        {"oms": oms},
    )

    audit = audit_chain_status(limit=5)
    audit_ok = audit["status"] == "pass" and audit["total_records"] > 0
    add_gate(
        "audit_chain",
        "审计哈希链",
        "pass" if audit_ok else "fail",
        (
            f"审计链完整；记录数={audit['total_records']}，最后哈希={audit['last_hash'][:12]}..."
            if audit_ok
            else "审计链为空或存在断裂，不能进入实盘。"
        ),
        {
            "total_records": audit["total_records"],
            "broken_count": audit["broken_count"],
            "last_hash": audit["last_hash"],
            "stream_counts": audit["stream_counts"],
        },
    )

    alert_state = run_watchdog_checks()
    alert_summary_state = alert_state["summary"]
    if alert_summary_state["critical"]:
        alert_status = "fail"
        alert_detail = "存在严重告警，禁止进入实盘。"
    elif alert_summary_state["warning"]:
        alert_status = "warn"
        alert_detail = "存在警告告警，进入实盘前需要处理或确认。"
    else:
        alert_status = "pass"
        alert_detail = "当前没有活跃告警。"
    add_gate(
        "alert_watchdog",
        "告警看门狗",
        alert_status,
        alert_detail,
        {"summary": alert_summary_state},
    )

    delivery = alert_delivery_config()
    delivery_ready = bool(delivery.get("any_channel_ready"))
    delivery_required = GO_LIVE_REQUIRE_ALERT_WEBHOOK or live_requested or live_mode_enabled
    add_gate(
        "alert_delivery",
        "告警通知链路",
        "pass" if delivery_ready else ("fail" if delivery_required else "warn"),
        "外部告警通道已启用并配置。" if delivery_ready else "实盘前建议启用 Webhook、Telegram 或 Email，避免只依赖浏览器页面。",
        {"delivery": delivery, "required": delivery_required},
        required_for_live=delivery_required,
    )

    recovery = exchange_recovery_status()
    recovery_age = seconds_since(recovery.get("last_at"))
    recovery_errors = (recovery.get("last_report") or {}).get("errors") or []
    recovery_ok = bool(recovery.get("last_at")) and not recovery_errors and (
        recovery_age is not None and recovery_age <= EXCHANGE_RECOVERY_STALE_SECONDS
    )
    if recovery_ok:
        recovery_status = "pass"
        recovery_detail = "交易所恢复同步在新鲜度阈值内，且没有错误。"
    elif recovery_errors:
        recovery_status = "fail"
        recovery_detail = "最近一次交易所恢复同步存在错误。"
    else:
        recovery_status = "fail" if live_requested else "warn"
        recovery_detail = "尚未完成近期交易所恢复同步，实盘前必须先对账。"
    add_gate(
        "exchange_recovery",
        "交易所恢复同步",
        recovery_status,
        recovery_detail,
        {
            "last_at": recovery.get("last_at"),
            "age_seconds": recovery_age,
            "threshold_seconds": EXCHANGE_RECOVERY_STALE_SECONDS,
            "errors": recovery_errors,
        },
    )

    live_snapshot = latest_exchange_account_snapshot("live_guarded")
    live_snapshot_summary = (live_snapshot or {}).get("summary") or {}
    live_wallet_balance = safe_float(live_snapshot_summary.get("wallet_balance_usdt"), 0.0)
    pilot_cap_required = live_requested or live_mode_enabled
    if LIVE_PILOT_MAX_WALLET_USDT <= 0:
        pilot_cap_status = "fail" if pilot_cap_required else "warn"
        pilot_cap_detail = "LIVE_PILOT_MAX_WALLET_USDT 必须大于 0，首轮实盘需要明确的钱包资金上限。"
    elif not live_snapshot:
        pilot_cap_status = "fail" if pilot_cap_required else "warn"
        pilot_cap_detail = "尚无 live 账户快照；实盘前需要先运行交易所恢复同步来读取钱包余额。"
    elif live_wallet_balance <= LIVE_PILOT_MAX_WALLET_USDT:
        pilot_cap_status = "pass"
        pilot_cap_detail = (
            f"最近 live 钱包余额 {live_wallet_balance:.2f} USDT，"
            f"未超过首轮试运行上限 {LIVE_PILOT_MAX_WALLET_USDT:.2f} USDT。"
        )
    else:
        pilot_cap_status = "fail"
        pilot_cap_detail = (
            f"最近 live 钱包余额 {live_wallet_balance:.2f} USDT，"
            f"超过首轮试运行上限 {LIVE_PILOT_MAX_WALLET_USDT:.2f} USDT；请降低账户资金或调低实盘范围。"
        )
    add_gate(
        "live_pilot_capital",
        "首轮实盘资金上限",
        pilot_cap_status,
        pilot_cap_detail,
        {
            "max_wallet_usdt": LIVE_PILOT_MAX_WALLET_USDT,
            "wallet_balance_usdt": live_wallet_balance if live_snapshot else None,
            "snapshot_id": (live_snapshot or {}).get("id"),
            "snapshot_ts": (live_snapshot or {}).get("ts"),
            "required": pilot_cap_required,
        },
        required_for_live=pilot_cap_required,
    )

    stream = recovery.get("user_stream") or binance_user_stream_status()
    stream_required = GO_LIVE_REQUIRE_PRIVATE_STREAM and (live_requested or live_mode_enabled)
    stream_ok = (
        stream.get("dependency_ready")
        and stream.get("listen_key_present")
        and stream.get("consumer_running")
        and stream.get("status") == "active"
        and stream.get("mode") == "live_guarded"
    )
    add_gate(
        "private_user_stream",
        "私有回报流",
        "pass" if stream_ok else ("fail" if stream_required else "warn"),
        "Binance live user-data stream 已运行。" if stream_ok else "实盘前需要 live listenKey 和私有回报流消费线程运行。",
        {"stream": stream, "required": stream_required},
        required_for_live=stream_required,
    )

    drill = testnet_drill_status()
    drill_ok = drill["real_completed_cycles"] >= GO_LIVE_MIN_TESTNET_DRILL_CYCLES and not drill["last_error"]
    add_gate(
        "testnet_drill_cycles",
        "Testnet 连续演练",
        "pass" if drill_ok else ("fail" if live_requested else "warn"),
        (
            f"真实 Testnet 演练 {drill['real_completed_cycles']}/{GO_LIVE_MIN_TESTNET_DRILL_CYCLES}；"
            f"控制面 dry-run {drill['dry_run_completed_cycles']} 次。"
            if not drill_ok
            else "Testnet 演练次数和最近错误状态满足实盘门槛。"
        ),
        {
            "completed_cycles": drill["completed_cycles"],
            "real_completed_cycles": drill["real_completed_cycles"],
            "dry_run_completed_cycles": drill["dry_run_completed_cycles"],
            "required_cycles": GO_LIVE_MIN_TESTNET_DRILL_CYCLES,
            "last_error": drill["last_error"],
            "target_cycles": drill["target_cycles"],
            "last_real_cycle_at": drill["last_real_cycle_at"],
            "last_real_cycle_id": drill["last_real_cycle_id"],
        },
    )

    latest_backtests = get_backtests(limit=1)
    walkforward = get_latest_walkforward()
    backtest_ok = bool(latest_backtests and latest_backtests[0].get("status") == "completed")
    walkforward_fold_count = int(safe_float((walkforward or {}).get("fold_count"), 0))
    walkforward_return = safe_float((walkforward or {}).get("total_return_pct"), -999999.0)
    walkforward_positive_rate = safe_float((walkforward or {}).get("positive_fold_rate_pct"), 0.0)
    walkforward_drawdown = safe_float((walkforward or {}).get("max_fold_drawdown_pct"), 999999.0)
    walkforward_failures: list[str] = []
    if not walkforward:
        walkforward_failures.append("缺少滚动验证结果")
    if walkforward_fold_count < GO_LIVE_MIN_WALKFORWARD_FOLDS:
        walkforward_failures.append(
            f"滚动验证折数 {walkforward_fold_count}/{GO_LIVE_MIN_WALKFORWARD_FOLDS} 未达标"
        )
    if walkforward_return < GO_LIVE_MIN_WALKFORWARD_TOTAL_RETURN_PCT:
        walkforward_failures.append(
            f"滚动验证总收益 {walkforward_return:.2f}% 低于 {GO_LIVE_MIN_WALKFORWARD_TOTAL_RETURN_PCT:.2f}%"
        )
    if walkforward_positive_rate < GO_LIVE_MIN_WALKFORWARD_POSITIVE_FOLD_RATE_PCT:
        walkforward_failures.append(
            f"正收益折数占比 {walkforward_positive_rate:.2f}% 低于 {GO_LIVE_MIN_WALKFORWARD_POSITIVE_FOLD_RATE_PCT:.2f}%"
        )
    if walkforward_drawdown > GO_LIVE_MAX_WALKFORWARD_DRAWDOWN_PCT:
        walkforward_failures.append(
            f"最大折内回撤 {walkforward_drawdown:.2f}% 高于 {GO_LIVE_MAX_WALKFORWARD_DRAWDOWN_PCT:.2f}%"
        )
    walkforward_ok = not walkforward_failures
    strategy_ok = backtest_ok and walkforward_ok
    add_gate(
        "backtest_walkforward",
        "回测与滚动验证",
        "pass" if strategy_ok else ("fail" if live_requested else "warn"),
        (
            "最近回测与滚动验证质量满足实盘前置阈值。"
            if strategy_ok
            else "实盘前必须有完成的回测，并且最新滚动验证收益、正收益折数和回撤满足阈值。"
        ),
        {
            "latest_backtest_id": latest_backtests[0]["id"] if latest_backtests else "",
            "latest_backtest_status": latest_backtests[0].get("status") if latest_backtests else "",
            "walkforward_id": (walkforward or {}).get("id", ""),
            "walkforward_folds": walkforward_fold_count,
            "walkforward_total_return_pct": None if not walkforward else walkforward_return,
            "walkforward_positive_fold_rate_pct": None if not walkforward else walkforward_positive_rate,
            "walkforward_max_fold_drawdown_pct": None if not walkforward else walkforward_drawdown,
            "thresholds": {
                "min_folds": GO_LIVE_MIN_WALKFORWARD_FOLDS,
                "min_total_return_pct": GO_LIVE_MIN_WALKFORWARD_TOTAL_RETURN_PCT,
                "min_positive_fold_rate_pct": GO_LIVE_MIN_WALKFORWARD_POSITIVE_FOLD_RATE_PCT,
                "max_fold_drawdown_pct": GO_LIVE_MAX_WALKFORWARD_DRAWDOWN_PCT,
            },
            "failures": walkforward_failures,
        },
    )

    arming = live_arming_status()
    arming_required = live_requested or live_mode_enabled
    add_gate(
        "live_arming",
        "短时实盘授权",
        "pass" if arming["armed"] else ("fail" if live_mode_enabled else "warn"),
        (
            f"实盘已武装，剩余 {arming['remaining_seconds']} 秒，"
            f"入口订单额度 {arming['remaining_orders']}/{arming['max_orders']}。"
            if arming["armed"]
            else "实盘未武装或本次武装额度已用尽；所有准入项通过后，需要在控制台输入 ARM_LIVE_TRADING 进行短时授权。"
        ),
        {"arming": arming, "required": arming_required},
        required_for_live=arming_required,
    )

    blocking_gates = [gate for gate in gates if gate["blocks_live_order"]]
    prerequisite_blockers = [gate for gate in blocking_gates if gate["id"] not in {"live_flags", "live_arming"}]
    arming_blockers = [gate for gate in blocking_gates if gate["id"] != "live_arming"]
    ready_to_enable_live = not prerequisite_blockers
    ready_to_arm_live = live_mode_enabled and not arming_blockers
    ready_for_live_order = live_mode_enabled and not blocking_gates
    if ready_for_live_order:
        status = "ready"
    elif live_requested:
        status = "blocked"
    else:
        status = "locked"
    return {
        "status": status,
        "ready_to_enable_live": ready_to_enable_live,
        "ready_to_arm_live": ready_to_arm_live,
        "ready_for_live_order": ready_for_live_order,
        "live_requested": live_requested,
        "live_mode_enabled": live_mode_enabled,
        "live_arming": arming,
        "min_testnet_drill_cycles": GO_LIVE_MIN_TESTNET_DRILL_CYCLES,
        "walkforward_thresholds": {
            "min_folds": GO_LIVE_MIN_WALKFORWARD_FOLDS,
            "min_total_return_pct": GO_LIVE_MIN_WALKFORWARD_TOTAL_RETURN_PCT,
            "min_positive_fold_rate_pct": GO_LIVE_MIN_WALKFORWARD_POSITIVE_FOLD_RATE_PCT,
            "max_fold_drawdown_pct": GO_LIVE_MAX_WALKFORWARD_DRAWDOWN_PCT,
        },
        "require_alert_webhook": GO_LIVE_REQUIRE_ALERT_WEBHOOK,
        "require_private_stream": GO_LIVE_REQUIRE_PRIVATE_STREAM,
        "updated_at": utc_now(),
        "gates": gates,
        "blocking_gates": blocking_gates,
    }


def assert_go_live_gate_allows_live_order() -> dict[str, Any]:
    gate = go_live_gate_status()
    if gate["ready_for_live_order"]:
        return gate
    labels = ", ".join(item["label"] for item in gate["blocking_gates"][:6]) or "unknown gate"
    raise ValueError(f"Go-live gate blocks live order: {labels}")


def arm_live_trading(settings: dict[str, Any]) -> dict[str, Any]:
    confirmation = str(settings.get("confirmation") or "").strip()
    if confirmation != "ARM_LIVE_TRADING":
        raise ValueError("Live arming requires confirmation=ARM_LIVE_TRADING.")
    gate = go_live_gate_status()
    blockers = [item for item in gate["blocking_gates"] if item["id"] != "live_arming"]
    if blockers:
        labels = ", ".join(item["label"] for item in blockers[:6])
        raise ValueError(f"Live arming is blocked by: {labels}")
    ttl_seconds = settings.get("ttl_seconds")
    if ttl_seconds is None and settings.get("ttl_minutes") is not None:
        ttl_seconds = float(settings["ttl_minutes"]) * 60
    if ttl_seconds is None:
        ttl_seconds = min(600, LIVE_ARMING_MAX_SECONDS)
    ttl_seconds = max(60, min(LIVE_ARMING_MAX_SECONDS, int(float(ttl_seconds))))
    actor = str(settings.get("actor") or "dashboard").strip()[:80]
    reason = str(settings.get("reason") or "manual_live_arming").strip()[:200]
    armed_at = utc_now()
    armed_until = seconds_from_now(ttl_seconds)
    set_setting("live_armed_at", armed_at)
    set_setting("live_armed_until", armed_until)
    set_setting("live_armed_by", actor)
    set_setting("live_armed_reason", reason)
    set_setting("live_armed_order_count", "0")
    set_setting("live_armed_order_ids", "[]")
    set_setting("live_disarmed_at", "")
    set_setting("live_disarm_reason", "")
    status = live_arming_status()
    insert_event(
        "system",
        "system",
        "Live Arming",
        "实盘短时授权已开启",
        f"实盘已由 {actor} 授权至 {armed_until}；本次最多 {LIVE_ARMING_MAX_ORDERS} 笔入口订单；原因：{reason}。",
        {"arming": status},
    )
    return status


def disarm_live_trading(reason: str = "manual_disarm") -> dict[str, Any]:
    now = utc_now()
    clean_reason = str(reason or "manual_disarm").strip()[:200]
    set_setting("live_armed_until", now)
    set_setting("live_disarmed_at", now)
    set_setting("live_disarm_reason", clean_reason)
    status = live_arming_status()
    insert_event(
        "system",
        "system",
        "Live Arming",
        "实盘短时授权已解除",
        f"实盘授权已解除；原因：{clean_reason}。",
        {"arming": status},
    )
    return status


def disarm_live_arming_on_startup() -> dict[str, Any]:
    before = live_arming_status()
    report: dict[str, Any] = {
        "action": "noop",
        "reason": "startup",
        "checked_at": utc_now(),
        "previous": before,
        "live_arming": before,
    }
    if before.get("time_active") or before.get("armed"):
        after = disarm_live_trading("startup_disarm")
        report.update(
            {
                "action": "disarmed",
                "reason": "startup_disarm",
                "live_arming": after,
                "disarmed_at": after.get("disarmed_at"),
            }
        )
    set_setting("live_startup_disarm_last_at", report["checked_at"])
    set_setting("live_startup_disarm_last_report", json.dumps(report, ensure_ascii=False))
    return report


def scheduler_status() -> dict[str, Any]:
    interval_seconds = int(float(get_setting("scheduler_interval_seconds", "900") or "900"))
    return {
        "enabled": get_setting("scheduler_enabled", "false") == "true",
        "symbol": get_setting("scheduler_symbol", "BTCUSDT"),
        "mode": get_setting("scheduler_mode", "paper"),
        "interval_seconds": interval_seconds,
        "interval_minutes": round(interval_seconds / 60, 2),
        "last_run_at": get_setting("scheduler_last_run_at", ""),
        "next_run_at": get_setting("scheduler_next_run_at", ""),
        "last_run_id": get_setting("scheduler_last_run_id", ""),
        "last_error": get_setting("scheduler_last_error", ""),
        "active_runs": sorted(ACTIVE_RUNS),
    }


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return bool(value)


def coerce_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def coerce_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def normalize_symbols(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_symbols = value
    else:
        raw_symbols = str(value or "").replace(";", ",").split(",")
    symbols: list[str] = []
    for raw_symbol in raw_symbols:
        symbol = str(raw_symbol).upper().strip()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols or ["BTCUSDT"]


def risk_config() -> dict[str, Any]:
    allowed_symbols = normalize_symbols(get_setting("risk_allowed_symbols", ALLOWED_SYMBOLS))
    return {
        "max_leverage": coerce_float(
            get_setting("risk_max_leverage", str(MAX_LEVERAGE)),
            MAX_LEVERAGE,
            1,
            125,
        ),
        "max_position_pct": coerce_float(
            get_setting("risk_max_position_pct", str(MAX_POSITION_PCT)),
            MAX_POSITION_PCT,
            0.001,
            1,
        ),
        "max_order_notional_usdt": coerce_float(
            get_setting("risk_max_order_notional_usdt", str(MAX_ORDER_NOTIONAL_USDT)),
            MAX_ORDER_NOTIONAL_USDT,
            0,
            100_000_000,
        ),
        "max_daily_loss_pct": coerce_float(
            get_setting("risk_max_daily_loss_pct", str(MAX_DAILY_LOSS_PCT)),
            MAX_DAILY_LOSS_PCT,
            0,
            1,
        ),
        "max_open_positions": coerce_int(
            get_setting("risk_max_open_positions", str(MAX_OPEN_POSITIONS)),
            MAX_OPEN_POSITIONS,
            0,
            200,
        ),
        "max_consecutive_losses": coerce_int(
            get_setting("risk_max_consecutive_losses", str(MAX_CONSECUTIVE_LOSSES)),
            MAX_CONSECUTIVE_LOSSES,
            0,
            100,
        ),
        "allowed_symbols": allowed_symbols,
        "emergency_stop": get_setting("emergency_stop", "false") == "true",
        "daily_realized_pnl_usdt": round(today_realized_pnl(), 2),
        "consecutive_losses": current_consecutive_losses(),
    }


def configure_risk(settings: dict[str, Any]) -> dict[str, Any]:
    current = risk_config()
    config = {
        "max_leverage": coerce_float(
            settings.get("max_leverage", current["max_leverage"]),
            current["max_leverage"],
            1,
            125,
        ),
        "max_position_pct": coerce_float(
            settings.get("max_position_pct", current["max_position_pct"]),
            current["max_position_pct"],
            0.001,
            1,
        ),
        "max_order_notional_usdt": coerce_float(
            settings.get("max_order_notional_usdt", current["max_order_notional_usdt"]),
            current["max_order_notional_usdt"],
            0,
            100_000_000,
        ),
        "max_daily_loss_pct": coerce_float(
            settings.get("max_daily_loss_pct", current["max_daily_loss_pct"]),
            current["max_daily_loss_pct"],
            0,
            1,
        ),
        "max_open_positions": coerce_int(
            settings.get("max_open_positions", current["max_open_positions"]),
            current["max_open_positions"],
            0,
            200,
        ),
        "max_consecutive_losses": coerce_int(
            settings.get("max_consecutive_losses", current["max_consecutive_losses"]),
            current["max_consecutive_losses"],
            0,
            100,
        ),
        "allowed_symbols": normalize_symbols(settings.get("allowed_symbols", current["allowed_symbols"])),
    }
    set_setting("risk_max_leverage", str(config["max_leverage"]))
    set_setting("risk_max_position_pct", str(config["max_position_pct"]))
    set_setting("risk_max_order_notional_usdt", str(config["max_order_notional_usdt"]))
    set_setting("risk_max_daily_loss_pct", str(config["max_daily_loss_pct"]))
    set_setting("risk_max_open_positions", str(config["max_open_positions"]))
    set_setting("risk_max_consecutive_losses", str(config["max_consecutive_losses"]))
    set_setting("risk_allowed_symbols", ",".join(config["allowed_symbols"]))
    return risk_config()


def configure_scheduler(settings: dict[str, Any]) -> dict[str, Any]:
    current = scheduler_status()
    enabled = settings.get("enabled", current["enabled"])
    enabled_bool = coerce_bool(enabled)
    symbol = str(settings.get("symbol") or current["symbol"]).upper().strip()
    mode = str(settings.get("mode") or current["mode"]).lower().strip()
    interval_seconds = settings.get("interval_seconds")
    if interval_seconds is None and settings.get("interval_minutes") is not None:
        interval_seconds = float(settings["interval_minutes"]) * 60
    if interval_seconds is None:
        interval_seconds = current["interval_seconds"]
    interval_seconds = max(60, min(86_400, int(float(interval_seconds))))

    if mode not in enabled_modes():
        raise ValueError(f"Mode {mode} is not enabled.")
    if enabled_bool and mode == "live_guarded":
        assert_go_live_gate_allows_live_order()
    if not symbol:
        raise ValueError("Scheduler symbol is required.")

    set_setting("scheduler_enabled", "true" if enabled_bool else "false")
    set_setting("scheduler_symbol", symbol)
    set_setting("scheduler_mode", mode)
    set_setting("scheduler_interval_seconds", str(interval_seconds))
    schedule_changed = (
        symbol != current["symbol"]
        or mode != current["mode"]
        or interval_seconds != current["interval_seconds"]
    )
    if enabled_bool and (not current.get("enabled") or schedule_changed):
        set_setting("scheduler_next_run_at", seconds_from_now(interval_seconds))
    if not enabled_bool:
        set_setting("scheduler_next_run_at", "")
    set_setting("scheduler_last_error", "")
    return scheduler_status()


def trigger_scheduler_run(reason: str = "manual_scheduler_run") -> dict[str, Any]:
    status = scheduler_status()
    run = launch_run(status["symbol"], status["mode"])
    now = utc_now()
    set_setting("scheduler_last_run_at", now)
    set_setting("scheduler_last_run_id", run["id"])
    set_setting("scheduler_next_run_at", seconds_from_now(status["interval_seconds"]))
    set_setting("scheduler_last_error", "")
    insert_event(
        run["id"],
        "system",
        "Scheduler",
        "调度运行已排队",
        f"调度器已触发 {run['symbol']}，模式为 {mode_label(run['mode'])}（原因：{reason_label(reason)}）。",
        {"reason": reason, "scheduler": scheduler_status()},
    )
    return run


def scheduler_loop() -> None:
    while not SCHEDULER_STOP.is_set():
        try:
            status = scheduler_status()
            if status["enabled"]:
                next_at = parse_iso_datetime(status["next_run_at"])
                if not next_at:
                    set_setting("scheduler_next_run_at", seconds_from_now(status["interval_seconds"]))
                elif datetime.now(timezone.utc) >= next_at:
                    if ACTIVE_RUNS:
                        set_setting("scheduler_next_run_at", seconds_from_now(30))
                    else:
                        trigger_scheduler_run(reason="interval")
            SCHEDULER_STOP.wait(5)
        except Exception as exc:
            set_setting("scheduler_last_error", f"{exc.__class__.__name__}: {exc}")
            set_setting("scheduler_next_run_at", seconds_from_now(60))
            SCHEDULER_STOP.wait(5)


def testnet_drill_modes() -> list[str]:
    modes = ["binance_testnet_validate"]
    if BINANCE_PLACE_TESTNET_ORDERS:
        modes.append("binance_testnet_place_order")
    return modes


def create_testnet_drill_cycle(symbol: str, mode: str, reason: str) -> dict[str, Any]:
    cycle_id = f"TND-{str(uuid.uuid4())[:10].upper()}"
    now = utc_now()
    with DB_LOCK, connect() as conn:
        conn.execute(
            """
            INSERT INTO testnet_drill_cycles(
                id, ts, mode, symbol, reason, status,
                recovery_report, alert_summary, stream_summary, note
            )
            VALUES(?, ?, ?, ?, ?, 'running', '{}', '{}', '{}', '')
            """,
            (cycle_id, now, mode, symbol.upper().strip(), reason),
        )
        conn.commit()
    return get_testnet_drill_cycle(cycle_id) or {}


def update_testnet_drill_cycle(cycle_id: str, **fields: Any) -> dict[str, Any]:
    allowed = {
        "completed_at",
        "status",
        "run_id",
        "order_id",
        "recovery_report",
        "alert_summary",
        "stream_summary",
        "note",
    }
    updates: dict[str, Any] = {}
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key in {"recovery_report", "alert_summary", "stream_summary"} and not isinstance(value, str):
            updates[key] = json.dumps(value or {}, ensure_ascii=False)
        else:
            updates[key] = value
    if updates:
        names = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values()) + [cycle_id]
        with DB_LOCK, connect() as conn:
            conn.execute(f"UPDATE testnet_drill_cycles SET {names} WHERE id = ?", values)
            conn.commit()
    return get_testnet_drill_cycle(cycle_id) or {}


def parse_testnet_drill_cycle(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if not row:
        return None
    item = dict(row)
    for key in ("recovery_report", "alert_summary", "stream_summary"):
        try:
            item[key] = json.loads(item.get(key) or "{}")
        except json.JSONDecodeError:
            item[key] = {"raw": item.get(key)}
    return item


def get_testnet_drill_cycle(cycle_id: str) -> dict[str, Any] | None:
    with DB_LOCK, connect() as conn:
        row = conn.execute("SELECT * FROM testnet_drill_cycles WHERE id = ?", (cycle_id,)).fetchone()
    return parse_testnet_drill_cycle(row)


def get_testnet_drill_cycles(limit: int = 20) -> list[dict[str, Any]]:
    with DB_LOCK, connect() as conn:
        rows = conn.execute(
            "SELECT * FROM testnet_drill_cycles ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [item for item in (parse_testnet_drill_cycle(row) for row in rows) if item]


def wait_for_run_completion(run_id: str, timeout_seconds: int = 240) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        run = get_run(run_id)
        if run and run.get("status") in {"completed", "failed"}:
            return run
        time.sleep(1)
    run = get_run(run_id) or {"id": run_id, "status": "unknown"}
    raise TimeoutError(f"Run {run_id} did not finish within {timeout_seconds} seconds; last status={run.get('status')}.")


def latest_order_for_run(run_id: str) -> dict[str, Any] | None:
    with DB_LOCK, connect() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE run_id = ? ORDER BY created_at DESC LIMIT 1",
            (run_id,),
        ).fetchone()
    return dict_row(row)


def cancel_open_testnet_orders_for_run(run_id: str) -> list[dict[str, Any]]:
    canceled: list[dict[str, Any]] = []
    with DB_LOCK, connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM orders
            WHERE run_id = ?
              AND status IN ('testnet_submitted', 'testnet_protection_submitted', 'pending_reconcile')
            ORDER BY created_at DESC
            """,
            (run_id,),
        ).fetchall()
    for row in rows:
        canceled.append(cancel_testnet_order(dict(row)["id"]))
    return canceled


def testnet_drill_status() -> dict[str, Any]:
    completed = int(float(get_setting("testnet_drill_completed_cycles", "0") or 0))
    real_completed = int(float(get_setting("testnet_drill_real_completed_cycles", "0") or 0))
    target = max(1, int(float(get_setting("testnet_drill_target_cycles", "24") or 24)))
    interval_seconds = max(60, int(float(get_setting("testnet_drill_interval_seconds", "1800") or 1800)))
    cycles = get_testnet_drill_cycles(limit=20)
    enabled = get_setting("testnet_drill_enabled", "false") == "true"
    next_at = get_setting("testnet_drill_next_cycle_at", "")
    active_cycle = next((cycle for cycle in cycles if cycle.get("status") == "running"), None)
    return {
        "enabled": enabled,
        "symbol": get_setting("testnet_drill_symbol", "BTCUSDT"),
        "mode": get_setting("testnet_drill_mode", "binance_testnet_validate"),
        "available_modes": testnet_drill_modes(),
        "active_run_modes": enabled_modes(),
        "interval_seconds": interval_seconds,
        "interval_minutes": max(1, round(interval_seconds / 60)),
        "target_cycles": target,
        "completed_cycles": completed,
        "real_completed_cycles": real_completed,
        "dry_run_completed_cycles": max(0, completed - real_completed),
        "remaining_cycles": max(0, target - completed),
        "remaining_real_cycles": max(0, target - real_completed),
        "started_at": get_setting("testnet_drill_started_at", ""),
        "last_cycle_at": get_setting("testnet_drill_last_cycle_at", ""),
        "last_real_cycle_at": get_setting("testnet_drill_last_real_cycle_at", ""),
        "last_real_cycle_id": get_setting("testnet_drill_last_real_cycle_id", ""),
        "next_cycle_at": next_at,
        "last_cycle_id": get_setting("testnet_drill_last_cycle_id", ""),
        "last_error": get_setting("testnet_drill_last_error", ""),
        "running": bool(active_cycle),
        "active_cycle": active_cycle,
        "cycles": cycles,
    }


def compact_testnet_drill_cycle(cycle: dict[str, Any] | None) -> dict[str, Any] | None:
    if not cycle:
        return None
    return {
        key: cycle.get(key)
        for key in (
            "id",
            "ts",
            "completed_at",
            "mode",
            "symbol",
            "reason",
            "status",
            "run_id",
            "order_id",
            "note",
            "alert_summary",
            "stream_summary",
        )
    }


def compact_testnet_drill_status(drill: dict[str, Any] | None = None, limit: int = 8) -> dict[str, Any]:
    source = drill if drill is not None else testnet_drill_status()
    compact = {
        key: source.get(key)
        for key in (
            "enabled",
            "symbol",
            "mode",
            "available_modes",
            "active_run_modes",
            "interval_seconds",
            "interval_minutes",
            "target_cycles",
            "completed_cycles",
            "real_completed_cycles",
            "dry_run_completed_cycles",
            "remaining_cycles",
            "remaining_real_cycles",
            "started_at",
            "last_cycle_at",
            "last_real_cycle_at",
            "last_real_cycle_id",
            "next_cycle_at",
            "last_cycle_id",
            "last_error",
            "running",
        )
    }
    compact["active_cycle"] = compact_testnet_drill_cycle(source.get("active_cycle"))
    compact["cycles"] = [
        item
        for item in (
            compact_testnet_drill_cycle(cycle)
            for cycle in (source.get("cycles") or [])[:limit]
        )
        if item
    ]
    return compact


def configure_testnet_drill(settings: dict[str, Any]) -> dict[str, Any]:
    enabled_bool = coerce_bool(settings.get("enabled", False))
    symbol = str(settings.get("symbol") or "BTCUSDT").upper().strip()
    mode = str(settings.get("mode") or "binance_testnet_validate").lower().strip()
    interval_minutes = int(float(settings.get("interval_minutes") or 30))
    target_cycles = int(float(settings.get("target_cycles") or 24))
    if symbol not in risk_config()["allowed_symbols"]:
        raise ValueError(f"Symbol {symbol} is not in the risk whitelist.")
    if mode not in testnet_drill_modes():
        raise ValueError(f"Testnet drill mode {mode} is not available.")
    if enabled_bool and mode not in enabled_modes():
        raise ValueError("Binance Testnet drill requires ENABLE_BINANCE_TESTNET=true and testnet API keys for the selected mode.")
    interval_seconds = max(60, min(86_400, interval_minutes * 60))
    target_cycles = max(1, min(10_000, target_cycles))
    set_setting("testnet_drill_enabled", "true" if enabled_bool else "false")
    set_setting("testnet_drill_symbol", symbol)
    set_setting("testnet_drill_mode", mode)
    set_setting("testnet_drill_interval_seconds", str(interval_seconds))
    set_setting("testnet_drill_target_cycles", str(target_cycles))
    if enabled_bool and not get_setting("testnet_drill_started_at", ""):
        set_setting("testnet_drill_started_at", utc_now())
    if enabled_bool:
        set_setting("testnet_drill_next_cycle_at", seconds_from_now(interval_seconds))
    else:
        set_setting("testnet_drill_next_cycle_at", "")
    set_setting("testnet_drill_last_error", "")
    return testnet_drill_status()


def execute_testnet_drill_cycle(reason: str = "manual", dry_run: bool = False) -> dict[str, Any]:
    status = testnet_drill_status()
    cycle = create_testnet_drill_cycle(status["symbol"], status["mode"], reason)
    cycle_id = cycle["id"]
    run: dict[str, Any] | None = None
    order: dict[str, Any] | None = None
    note = ""
    try:
        if dry_run:
            note = "local dry_run validated the drill control chain without sending a Binance request."
        else:
            if status["mode"] not in enabled_modes():
                raise ValueError("Selected Binance Testnet drill mode is not enabled. Check ENABLE_BINANCE_TESTNET, API keys, and order-placement flag.")
            run = launch_run(status["symbol"], status["mode"])
            run = wait_for_run_completion(run["id"], timeout_seconds=300)
            order = latest_order_for_run(run["id"])
            if status["mode"] == "binance_testnet_place_order":
                canceled = cancel_open_testnet_orders_for_run(run["id"])
                if canceled:
                    order = canceled[0]
                    note = f"submitted testnet orders were canceled after drill: {', '.join(item['id'] for item in canceled)}."
            if run.get("status") != "completed":
                raise RuntimeError(f"Drill run ended with status={run.get('status')}.")
        recovery_report = recover_exchange_state(trigger=f"testnet_drill:{cycle_id}")
        resolve_alert("testnet_drill.last_error", "Testnet drill cycle reached recovery checks.")
        alert_state = run_watchdog_checks()
        stream_summary = exchange_stream_event_summary()
        alert_counts = alert_state["summary"]
        completed_status = "failed" if alert_counts.get("critical", 0) else "completed"
        completed_at = utc_now()
        completed_cycles = int(float(get_setting("testnet_drill_completed_cycles", "0") or 0)) + 1
        real_completed_cycles = int(float(get_setting("testnet_drill_real_completed_cycles", "0") or 0))
        if not dry_run and completed_status == "completed":
            real_completed_cycles += 1
            set_setting("testnet_drill_real_completed_cycles", str(real_completed_cycles))
            set_setting("testnet_drill_last_real_cycle_at", completed_at)
            set_setting("testnet_drill_last_real_cycle_id", cycle_id)
        interval_seconds = status["interval_seconds"]
        set_setting("testnet_drill_completed_cycles", str(completed_cycles))
        set_setting("testnet_drill_last_cycle_at", completed_at)
        set_setting("testnet_drill_last_cycle_id", cycle_id)
        set_setting("testnet_drill_next_cycle_at", seconds_from_now(interval_seconds))
        set_setting("testnet_drill_last_error", "" if completed_status == "completed" else "Critical alert exists after drill.")
        if completed_status == "completed":
            resolve_alert("testnet_drill.last_error", "Testnet drill cycle completed.")
        update = update_testnet_drill_cycle(
            cycle_id,
            completed_at=completed_at,
            status=completed_status,
            run_id=(run or {}).get("id"),
            order_id=(order or {}).get("id"),
            recovery_report=recovery_report,
            alert_summary=alert_counts,
            stream_summary=stream_summary,
            note=note or "drill completed; no live mode was enabled.",
        )
        if completed_cycles >= status["target_cycles"]:
            set_setting("testnet_drill_enabled", "false")
            set_setting("testnet_drill_next_cycle_at", "")
        insert_event(
            "system",
            "system",
            "Testnet Drill",
            "Binance Testnet drill cycle completed",
            f"Cycle {cycle_id} finished with status {completed_status}; mode={mode_label(status['mode'])}.",
            {"cycle": update, "run": run, "order": order},
        )
        return update
    except Exception as exc:
        message = f"{exc.__class__.__name__}: {exc}"
        set_setting("testnet_drill_last_error", message)
        failed = update_testnet_drill_cycle(
            cycle_id,
            completed_at=utc_now(),
            status="failed",
            run_id=(run or {}).get("id"),
            order_id=(order or {}).get("id"),
            alert_summary=alert_summary(get_alerts(limit=100, include_resolved=False)),
            stream_summary=exchange_stream_event_summary(),
            note=message,
        )
        raise_alert(
            "testnet_drill.last_error",
            "critical",
            "Testnet Drill",
            "Binance Testnet drill failed",
            message,
            {"cycle": failed, "reason": reason, "dry_run": dry_run},
        )
        raise


def testnet_drill_loop() -> None:
    while not TESTNET_DRILL_STOP.is_set():
        try:
            status = testnet_drill_status()
            if status["enabled"]:
                if status["completed_cycles"] >= status["target_cycles"]:
                    set_setting("testnet_drill_enabled", "false")
                    set_setting("testnet_drill_next_cycle_at", "")
                else:
                    next_at = parse_iso_datetime(status["next_cycle_at"])
                    if not next_at:
                        set_setting("testnet_drill_next_cycle_at", seconds_from_now(status["interval_seconds"]))
                    elif datetime.now(timezone.utc) >= next_at:
                        if ACTIVE_RUNS:
                            set_setting("testnet_drill_next_cycle_at", seconds_from_now(30))
                        else:
                            execute_testnet_drill_cycle(reason="interval")
            TESTNET_DRILL_STOP.wait(5)
        except Exception:
            set_setting("testnet_drill_next_cycle_at", seconds_from_now(60))
            TESTNET_DRILL_STOP.wait(5)


def order_book_imbalance(depth: dict[str, Any]) -> dict[str, float]:
    bid_qty = sum(float(level[1]) for level in depth.get("bids", []))
    ask_qty = sum(float(level[1]) for level in depth.get("asks", []))
    total = bid_qty + ask_qty
    imbalance = ((bid_qty - ask_qty) / total) if total else 0.0
    return {
        "depth_bid_qty": round(bid_qty, 6),
        "depth_ask_qty": round(ask_qty, 6),
        "depth_imbalance": round(imbalance, 4),
    }


def infer_liquidation_pressure(
    volatility_pct: float,
    open_interest_change_pct: float,
    funding_rate_pct: float,
    depth_imbalance: float,
) -> str:
    pressure_score = 0
    if volatility_pct >= 3.5:
        pressure_score += 1
    if abs(open_interest_change_pct) >= 1.0:
        pressure_score += 1
    if abs(funding_rate_pct) >= 0.02:
        pressure_score += 1
    if abs(depth_imbalance) >= 0.25:
        pressure_score += 1
    if pressure_score >= 3:
        return "high"
    if pressure_score >= 1:
        return "medium"
    return "low"


def build_binance_public_snapshot(symbol: str) -> dict[str, Any]:
    clean_symbol = "".join(ch for ch in symbol.upper() if ch.isalnum())
    if not clean_symbol:
        raise ValueError("symbol is empty")

    premium = http_get_json("/fapi/v1/premiumIndex", {"symbol": clean_symbol})
    ticker = http_get_json("/fapi/v1/ticker/24hr", {"symbol": clean_symbol})
    depth = http_get_json("/fapi/v1/depth", {"symbol": clean_symbol, "limit": 20})
    open_interest = http_get_json(
        "/futures/data/openInterestHist",
        {"symbol": clean_symbol, "period": "5m", "limit": 2},
    )
    long_short = http_get_json(
        "/futures/data/globalLongShortAccountRatio",
        {"symbol": clean_symbol, "period": "5m", "limit": 1},
    )

    mark_price = float(premium["markPrice"])
    index_price = float(premium["indexPrice"])
    weighted_avg = float(ticker["weightedAvgPrice"])
    high_price = float(ticker["highPrice"])
    low_price = float(ticker["lowPrice"])
    volatility_pct = ((high_price - low_price) / weighted_avg) * 100 if weighted_avg else 0.0

    oi_change_pct = 0.0
    oi_value = None
    if len(open_interest) >= 2:
        old_oi = float(open_interest[-2]["sumOpenInterest"])
        new_oi = float(open_interest[-1]["sumOpenInterest"])
        oi_change_pct = pct_change(old_oi, new_oi)
        oi_value = float(open_interest[-1]["sumOpenInterestValue"])

    long_short_ratio = 1.0
    if long_short:
        long_short_ratio = float(long_short[-1]["longShortRatio"])

    depth_stats = order_book_imbalance(depth)
    funding_rate_pct = float(premium["lastFundingRate"]) * 100
    liquidation_pressure = infer_liquidation_pressure(
        volatility_pct,
        oi_change_pct,
        funding_rate_pct,
        depth_stats["depth_imbalance"],
    )

    return {
        "symbol": clean_symbol,
        "data_source": "binance_public",
        "fallback": False,
        "mark_price": round(mark_price, 2),
        "index_price": round(index_price, 2),
        "change_24h_pct": round(float(ticker["priceChangePercent"]), 2),
        "realized_volatility_pct": round(volatility_pct, 2),
        "funding_rate_pct": round(funding_rate_pct, 4),
        "open_interest_change_pct": round(oi_change_pct, 4),
        "open_interest_value_usdt": round(oi_value, 2) if oi_value is not None else None,
        "long_short_ratio": round(long_short_ratio, 4),
        "depth_imbalance": depth_stats["depth_imbalance"],
        "depth_bid_qty": depth_stats["depth_bid_qty"],
        "depth_ask_qty": depth_stats["depth_ask_qty"],
        "quote_volume_usdt": round(float(ticker["quoteVolume"]), 2),
        "liquidation_pressure": liquidation_pressure,
        "timestamp": utc_now(),
    }


def build_synthetic_market_snapshot(symbol: str, source_error: str | None = None) -> dict[str, Any]:
    seed = int(time.time() // 60) + sum(ord(c) for c in symbol)
    rng = random.Random(seed)
    base_price = 68000 if symbol.startswith("BTC") else 3600 if symbol.startswith("ETH") else 1.0
    drift = rng.uniform(-0.018, 0.022)
    volatility = rng.uniform(0.012, 0.046)
    price = base_price * (1 + drift)
    funding = rng.uniform(-0.00018, 0.00034)
    open_interest_change = rng.uniform(-0.035, 0.048)
    long_short_ratio = rng.uniform(0.78, 1.42)
    depth_imbalance = rng.uniform(-0.26, 0.32)
    liquidation_pressure = rng.choice(["low", "medium", "medium", "high"])
    snapshot = {
        "symbol": symbol,
        "data_source": "synthetic",
        "fallback": bool(source_error),
        "source_error": source_error,
        "mark_price": round(price, 2),
        "index_price": round(price * rng.uniform(0.9992, 1.0008), 2),
        "change_24h_pct": round(drift * 100, 2),
        "realized_volatility_pct": round(volatility * 100, 2),
        "funding_rate_pct": round(funding * 100, 4),
        "open_interest_change_pct": round(open_interest_change * 100, 2),
        "open_interest_value_usdt": None,
        "long_short_ratio": round(long_short_ratio, 2),
        "depth_imbalance": round(depth_imbalance, 2),
        "depth_bid_qty": None,
        "depth_ask_qty": None,
        "quote_volume_usdt": None,
        "liquidation_pressure": liquidation_pressure,
        "timestamp": utc_now(),
    }
    return snapshot


def build_market_snapshot(symbol: str) -> dict[str, Any]:
    if MARKET_DATA_SOURCE == "synthetic":
        return build_synthetic_market_snapshot(symbol)
    try:
        return build_binance_public_snapshot(symbol)
    except Exception as exc:
        return build_synthetic_market_snapshot(
            symbol,
            source_error=f"{exc.__class__.__name__}: {exc}",
        )


def fetch_klines(symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
    if MARKET_DATA_SOURCE == "synthetic":
        return build_synthetic_klines(symbol, interval, limit)
    clean_symbol = "".join(ch for ch in symbol.upper() if ch.isalnum())
    try:
        raw = http_get_json(
            "/fapi/v1/klines",
            {"symbol": clean_symbol, "interval": interval, "limit": limit},
        )
    except Exception:
        return build_synthetic_klines(clean_symbol, interval, limit)
    candles = []
    for item in raw:
        candles.append(
            {
                "open_time": int(item[0]),
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5]),
                "close_time": int(item[6]),
                "quote_volume": float(item[7]),
                "trade_count": int(item[8]),
            }
        )
    return candles


def interval_to_ms(interval: str) -> int:
    unit = interval[-1:].lower()
    try:
        value = int(interval[:-1])
    except ValueError:
        value = 15
    if unit == "m":
        return value * 60_000
    if unit == "h":
        return value * 60 * 60_000
    if unit == "d":
        return value * 24 * 60 * 60_000
    return 15 * 60_000


def build_synthetic_klines(symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
    clean_symbol = "".join(ch for ch in symbol.upper() if ch.isalnum())
    rng = random.Random(sum(ord(c) for c in f"{clean_symbol}:{interval}:{limit}"))
    base_price = 68000 if clean_symbol.startswith("BTC") else 3600 if clean_symbol.startswith("ETH") else 140
    interval_ms = interval_to_ms(interval)
    now_ms = int(time.time() * 1000)
    first_open = now_ms - limit * interval_ms
    price = base_price * (1 + rng.uniform(-0.02, 0.02))
    candles: list[dict[str, Any]] = []
    for index in range(limit):
        open_time = first_open + index * interval_ms
        drift = 0.00005 * (1 if index % 17 < 9 else -1)
        shock = rng.uniform(-0.003, 0.003)
        close = max(0.01, price * (1 + drift + shock))
        high = max(price, close) * (1 + rng.uniform(0.0002, 0.0025))
        low = min(price, close) * (1 - rng.uniform(0.0002, 0.0025))
        volume = rng.uniform(120, 900)
        quote_volume = volume * ((price + close) / 2)
        candles.append(
            {
                "open_time": open_time,
                "open": round(price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
                "volume": round(volume, 4),
                "close_time": open_time + interval_ms - 1,
                "quote_volume": round(quote_volume, 2),
                "trade_count": int(rng.uniform(300, 1800)),
            }
        )
        price = close
    return candles


def ms_to_iso(ts: int) -> str:
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat(timespec="seconds")


def average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


DEFAULT_BACKTEST_PARAMS: dict[str, Any] = {
    "signal_type": "sma_trend",
    "fast_ma": 8,
    "slow_ma": 21,
    "lookback": 48,
    "threshold": 0.0007,
    "stop_pct": 0.012,
    "take_pct": 0.02,
    "position_pct": 0.03,
    "leverage": 2.0,
    "max_hold_bars": 18,
}


def normalize_backtest_params(params: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = {**DEFAULT_BACKTEST_PARAMS, **(params or {})}
    signal_type = str(merged.get("signal_type") or "sma_trend").lower().strip()
    allowed_signal_types = {
        "sma_trend",
        "sma_reversion",
        "momentum",
        "momentum_reversion",
        "breakout",
        "breakout_reversion",
    }
    if signal_type not in allowed_signal_types:
        signal_type = "sma_trend"
    fast_ma = max(3, min(30, int(merged["fast_ma"])))
    slow_ma = max(fast_ma + 2, min(80, int(merged["slow_ma"])))
    return {
        "signal_type": signal_type,
        "fast_ma": fast_ma,
        "slow_ma": slow_ma,
        "lookback": max(4, min(120, int(merged.get("lookback", 48)))),
        "threshold": max(0.0001, min(0.003, float(merged["threshold"]))),
        "stop_pct": max(0.004, min(0.04, float(merged["stop_pct"]))),
        "take_pct": max(0.006, min(0.08, float(merged["take_pct"]))),
        "position_pct": max(0.005, min(MAX_POSITION_PCT, float(merged["position_pct"]))),
        "leverage": max(1.0, min(MAX_LEVERAGE, float(merged["leverage"]))),
        "max_hold_bars": max(4, min(80, int(merged["max_hold_bars"]))),
    }


def backtest_signal(candles: list[dict[str, Any]], index: int, params: dict[str, Any]) -> str:
    closes = [candle["close"] for candle in candles]
    signal_type = str(params.get("signal_type") or "sma_trend")
    threshold = float(params["threshold"])
    fast_ma = int(params["fast_ma"])
    slow_ma = int(params["slow_ma"])
    lookback = int(params.get("lookback") or slow_ma)

    if signal_type in {"sma_trend", "sma_reversion"}:
        fast = average(closes[index - fast_ma : index])
        slow = average(closes[index - slow_ma : index])
        if not slow:
            return "HOLD"
        spread = (fast - slow) / slow
        if signal_type == "sma_trend":
            if spread > threshold:
                return "BUY"
            if spread < -threshold:
                return "SELL"
        else:
            if spread > threshold:
                return "SELL"
            if spread < -threshold:
                return "BUY"
        return "HOLD"

    if index < lookback:
        return "HOLD"

    if signal_type in {"momentum", "momentum_reversion"}:
        anchor = closes[index - lookback]
        if not anchor:
            return "HOLD"
        move = (closes[index - 1] - anchor) / anchor
        if signal_type == "momentum":
            if move > threshold:
                return "BUY"
            if move < -threshold:
                return "SELL"
        else:
            if move > threshold:
                return "SELL"
            if move < -threshold:
                return "BUY"
        return "HOLD"

    if signal_type in {"breakout", "breakout_reversion"}:
        high = max(candle["high"] for candle in candles[index - lookback : index])
        low = min(candle["low"] for candle in candles[index - lookback : index])
        close = closes[index - 1]
        if signal_type == "breakout":
            if close > high * (1 + threshold):
                return "BUY"
            if close < low * (1 - threshold):
                return "SELL"
        else:
            if close > high * (1 + threshold):
                return "SELL"
            if close < low * (1 - threshold):
                return "BUY"
    return "HOLD"


def max_drawdown_pct(equity_curve: list[float]) -> float:
    peak = equity_curve[0] if equity_curve else ACCOUNT_EQUITY_USDT
    max_drawdown = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
    return round(max_drawdown * 100, 2)


def run_strategy_backtest(
    symbol: str,
    interval: str,
    bars: int,
    params: dict[str, Any] | None = None,
    candles: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    bars = max(80, min(1000, int(bars)))
    interval = interval if interval in {"5m", "15m", "1h", "4h"} else "15m"
    params = normalize_backtest_params(params)
    candles = candles or fetch_klines(symbol, interval, bars)
    if len(candles) < 60:
        raise ValueError("Not enough candles for backtest")

    equity = ACCOUNT_EQUITY_USDT
    equity_curve = [equity]
    trades: list[dict[str, Any]] = []
    position: dict[str, Any] | None = None
    fee_rate = 0.0004
    stop_pct = float(params["stop_pct"])
    take_pct = float(params["take_pct"])
    max_hold_bars = int(params["max_hold_bars"])

    warmup_bars = max(int(params["slow_ma"]), int(params.get("lookback") or 0), 4)
    for index in range(warmup_bars, len(candles)):
        candle = candles[index]
        signal = backtest_signal(candles, index, params)

        if position:
            side = position["side"]
            entry = position["entry_price"]
            stop = entry * (1 - stop_pct) if side == "BUY" else entry * (1 + stop_pct)
            take = entry * (1 + take_pct) if side == "BUY" else entry * (1 - take_pct)
            exit_price = None
            reason = ""

            if side == "BUY" and candle["low"] <= stop:
                exit_price = stop
                reason = "stop_loss"
            elif side == "BUY" and candle["high"] >= take:
                exit_price = take
                reason = "take_profit"
            elif side == "SELL" and candle["high"] >= stop:
                exit_price = stop
                reason = "stop_loss"
            elif side == "SELL" and candle["low"] <= take:
                exit_price = take
                reason = "take_profit"
            elif index - position["entry_index"] >= max_hold_bars:
                exit_price = candle["close"]
                reason = "max_hold"
            elif (side == "BUY" and signal == "SELL") or (side == "SELL" and signal == "BUY"):
                exit_price = candle["close"]
                reason = "opposite_signal"

            if exit_price is not None:
                quantity = position["quantity"]
                gross_pnl = (
                    (exit_price - entry) * quantity
                    if side == "BUY"
                    else (entry - exit_price) * quantity
                )
                fees = (entry * quantity + exit_price * quantity) * fee_rate
                pnl = gross_pnl - fees
                equity += pnl
                entry_margin = (entry * quantity) / position["leverage"]
                trades.append(
                    {
                        "symbol": position["symbol"],
                        "side": side,
                        "opened_at": ms_to_iso(position["opened_at"]),
                        "closed_at": ms_to_iso(candle["close_time"]),
                        "entry_price": round(entry, 2),
                        "exit_price": round(exit_price, 2),
                        "quantity": round(quantity, 6),
                        "leverage": position["leverage"],
                        "pnl_usdt": round(pnl, 2),
                        "return_pct": round((pnl / entry_margin) * 100, 2) if entry_margin else 0.0,
                        "reason": reason,
                    }
                )
                position = None
                equity_curve.append(equity)
                continue

        if not position and signal in {"BUY", "SELL"}:
            entry_price = candle["close"]
            leverage = float(params["leverage"])
            notional = equity * float(params["position_pct"]) * leverage
            position = {
                "symbol": symbol.upper(),
                "side": signal,
                "entry_price": entry_price,
                "quantity": notional / entry_price,
                "leverage": leverage,
                "opened_at": candle["close_time"],
                "entry_index": index,
            }

    if position:
        candle = candles[-1]
        entry = position["entry_price"]
        exit_price = candle["close"]
        quantity = position["quantity"]
        pnl = (
            (exit_price - entry) * quantity
            if position["side"] == "BUY"
            else (entry - exit_price) * quantity
        )
        fees = (entry * quantity + exit_price * quantity) * fee_rate
        pnl -= fees
        equity += pnl
        entry_margin = (entry * quantity) / position["leverage"]
        trades.append(
            {
                "symbol": position["symbol"],
                "side": position["side"],
                "opened_at": ms_to_iso(position["opened_at"]),
                "closed_at": ms_to_iso(candle["close_time"]),
                "entry_price": round(entry, 2),
                "exit_price": round(exit_price, 2),
                "quantity": round(quantity, 6),
                "leverage": position["leverage"],
                "pnl_usdt": round(pnl, 2),
                "return_pct": round((pnl / entry_margin) * 100, 2) if entry_margin else 0.0,
                "reason": "end_of_sample",
            }
        )
        equity_curve.append(equity)

    wins = [trade for trade in trades if trade["pnl_usdt"] > 0]
    losses = [trade for trade in trades if trade["pnl_usdt"] < 0]
    gross_profit = sum(trade["pnl_usdt"] for trade in wins)
    gross_loss = abs(sum(trade["pnl_usdt"] for trade in losses))
    metrics = {
        "symbol": symbol.upper(),
        "interval": interval,
        "bars": len(candles),
        "data_source": "binance_klines",
        "initial_equity_usdt": round(ACCOUNT_EQUITY_USDT, 2),
        "final_equity_usdt": round(equity, 2),
        "net_pnl_usdt": round(equity - ACCOUNT_EQUITY_USDT, 2),
        "total_return_pct": round(((equity - ACCOUNT_EQUITY_USDT) / ACCOUNT_EQUITY_USDT) * 100, 2),
        "max_drawdown_pct": max_drawdown_pct(equity_curve),
        "trade_count": len(trades),
        "win_rate_pct": round((len(wins) / len(trades)) * 100, 2) if trades else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else None,
        "fee_rate_pct": fee_rate * 100,
        "strategy": (
            f"{params['signal_type']}_{params['fast_ma']}_{params['slow_ma']}_stop_take_v2"
            if str(params["signal_type"]).startswith("sma_")
            else f"{params['signal_type']}_{params['lookback']}_stop_take_v2"
        ),
        "params": {
            **params,
            "stop_pct": round(params["stop_pct"] * 100, 3),
            "take_pct": round(params["take_pct"] * 100, 3),
            "position_pct": round(params["position_pct"] * 100, 3),
            "threshold_pct": round(params["threshold"] * 100, 4),
        },
    }
    return {"metrics": metrics, "trades": trades}


def execute_backtest(symbol: str, interval: str, bars: int) -> dict[str, Any]:
    params = normalize_backtest_params()
    display_params = {
        **params,
        "stop_pct": round(params["stop_pct"] * 100, 3),
        "take_pct": round(params["take_pct"] * 100, 3),
        "position_pct": round(params["position_pct"] * 100, 3),
        "threshold_pct": round(params["threshold"] * 100, 4),
    }
    backtest = create_backtest_run(symbol, interval, bars, display_params)
    try:
        result = run_strategy_backtest(symbol, interval, bars, params=params)
        insert_backtest_trades(backtest["id"], result["trades"])
        update_backtest_run(backtest["id"], "completed", result["metrics"])
        return {
            "backtest": get_backtest_run(backtest["id"]),
            "trades": get_backtest_trades(backtest["id"], limit=200),
        }
    except Exception as exc:
        metrics = {"error": str(exc), "error_type": exc.__class__.__name__}
        update_backtest_run(backtest["id"], "failed", metrics)
        raise


def backtest_rank_score(metrics: dict[str, Any]) -> float:
    return round(
        float(metrics["total_return_pct"])
        - float(metrics["max_drawdown_pct"]) * 0.4
        + float(metrics["win_rate_pct"]) * 0.015,
        4,
    )


def comparison_param_grid() -> list[dict[str, Any]]:
    pairs = [(6, 18), (8, 21), (10, 30), (12, 36)]
    exits = [(0.008, 0.014), (0.012, 0.02), (0.016, 0.028)]
    thresholds = [0.0005, 0.0009]
    grid = []
    for signal_type in ["sma_trend", "sma_reversion"]:
        for fast_ma, slow_ma in pairs:
            for stop_pct, take_pct in exits:
                for threshold in thresholds:
                    grid.append(
                        normalize_backtest_params(
                            {
                                "signal_type": signal_type,
                                "fast_ma": fast_ma,
                                "slow_ma": slow_ma,
                                "lookback": slow_ma,
                                "stop_pct": stop_pct,
                                "take_pct": take_pct,
                                "threshold": threshold,
                                "position_pct": 0.03,
                                "leverage": 2.0,
                                "max_hold_bars": 18,
                            }
                        )
                    )
    for signal_type in ["momentum", "momentum_reversion", "breakout", "breakout_reversion"]:
        for lookback in [24, 36, 48, 60]:
            for stop_pct, take_pct in exits:
                for threshold in [0.0005, 0.0015, 0.0025]:
                    for max_hold_bars in [18, 48]:
                        grid.append(
                            normalize_backtest_params(
                                {
                                    "signal_type": signal_type,
                                    "lookback": lookback,
                                    "fast_ma": 8,
                                    "slow_ma": max(21, min(80, lookback)),
                                    "stop_pct": stop_pct,
                                    "take_pct": take_pct,
                                    "threshold": threshold,
                                    "position_pct": 0.03,
                                    "leverage": 2.0,
                                    "max_hold_bars": max_hold_bars,
                                }
                            )
                        )
    return grid


def get_latest_backtest_comparison() -> dict[str, Any] | None:
    raw = get_setting("latest_backtest_comparison", "")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def execute_backtest_comparison(symbol: str, interval: str, bars: int) -> dict[str, Any]:
    bars = max(100, min(1000, int(bars)))
    interval = interval if interval in {"5m", "15m", "1h", "4h"} else "15m"
    candles = fetch_klines(symbol, interval, bars)
    results = []
    for params in comparison_param_grid():
        result = run_strategy_backtest(
            symbol,
            interval,
            bars,
            params=params,
            candles=candles,
        )
        metrics = result["metrics"]
        results.append(
            {
                "rank_score": backtest_rank_score(metrics),
                "metrics": metrics,
                "params": metrics["params"],
            }
        )
    results.sort(
        key=lambda item: (
            item["rank_score"],
            item["metrics"]["total_return_pct"],
            -item["metrics"]["max_drawdown_pct"],
            item["metrics"]["trade_count"],
        ),
        reverse=True,
    )
    comparison = {
        "id": f"CMP-{str(uuid.uuid4())[:8].upper()}",
        "symbol": symbol.upper(),
        "interval": interval,
        "bars": len(candles),
        "created_at": utc_now(),
        "strategy_family": "multi_signal_stop_take_grid",
        "tested_count": len(results),
        "results": results[:12],
    }
    set_setting("latest_backtest_comparison", json.dumps(comparison))
    return comparison


def get_latest_walkforward() -> dict[str, Any] | None:
    raw = get_setting("latest_walkforward", "")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def lightweight_go_live_gate_status() -> dict[str, Any]:
    live_requested = bool(
        ENABLE_BINANCE_LIVE
        or BINANCE_PLACE_LIVE_ORDERS
        or EXCHANGE_MODE == "live_guarded"
        or BINANCE_LIVE_API_KEY
        or BINANCE_LIVE_API_SECRET
    )
    live_mode_enabled = EXCHANGE_MODE == "live_guarded"
    arming = live_arming_status()
    blocking_gates = []
    if live_requested or live_mode_enabled:
        blocking_gates.append(
            {
                "id": "full_gate_pending",
                "label": "完整实盘门禁需要刷新",
                "status": "warn",
                "detail": "首页使用轻量摘要；真实下单仍会调用完整 go-live gate。",
                "required_for_live": True,
                "blocks_live_order": True,
            }
        )
    return {
        "status": "blocked" if live_requested else "locked",
        "ready_to_enable_live": False,
        "ready_to_arm_live": False,
        "ready_for_live_order": False,
        "live_requested": live_requested,
        "live_mode_enabled": live_mode_enabled,
        "live_arming": arming,
        "min_testnet_drill_cycles": GO_LIVE_MIN_TESTNET_DRILL_CYCLES,
        "walkforward_thresholds": {
            "min_folds": GO_LIVE_MIN_WALKFORWARD_FOLDS,
            "min_total_return_pct": GO_LIVE_MIN_WALKFORWARD_TOTAL_RETURN_PCT,
            "min_positive_fold_rate_pct": GO_LIVE_MIN_WALKFORWARD_POSITIVE_FOLD_RATE_PCT,
            "max_fold_drawdown_pct": GO_LIVE_MAX_WALKFORWARD_DRAWDOWN_PCT,
        },
        "require_alert_webhook": GO_LIVE_REQUIRE_ALERT_WEBHOOK,
        "require_private_stream": GO_LIVE_REQUIRE_PRIVATE_STREAM,
        "updated_at": utc_now(),
        "summary_only": True,
        "gates": blocking_gates,
        "blocking_gates": blocking_gates,
    }


def lightweight_deployment_readiness() -> dict[str, Any]:
    latest = get_latest_run()
    account_state = paper_account_state()["account"]
    drill = compact_testnet_drill_status(limit=1)
    risk = risk_config()
    oms = oms_summary()
    operator = ai_operator_status()
    items: list[dict[str, str]] = []

    def add(name: str, status: str, detail: str) -> None:
        items.append({"name": name, "status": status, "detail": detail})

    add(
        "Runtime",
        "pass" if APP_ENV in {"local", "server"} else "warn",
        f"环境={source_label(APP_ENV)}；监听={HOST}:{PORT}。",
    )
    add(
        "Execution boundary",
        "pass" if EXCHANGE_MODE in enabled_modes() else "fail",
        f"当前模式={mode_label(EXCHANGE_MODE)}；已启用模式={', '.join(mode_label(mode) for mode in enabled_modes())}。",
    )
    add(
        "Paper workflow",
        "pass" if latest and latest.get("status") == "completed" else "warn",
        f"最近运行状态：{zh_status((latest or {}).get('status', 'none'))}。",
    )
    add(
        "Paper ledger",
        "pass" if account_state.get("realized_pnl_usdt") is not None else "warn",
        f"权益={account_state.get('equity_usdt')} USDT；当前持仓 {account_state.get('open_position_count')}。",
    )
    add(
        "Testnet drill",
        "warn" if drill.get("last_error") else "pass",
        (
            f"real={drill.get('real_completed_cycles')}/{drill.get('target_cycles')}; "
            f"dry_run={drill.get('dry_run_completed_cycles')}; "
            f"last_error={drill.get('last_error') or '-'}."
        ),
    )
    add(
        "Risk controls",
        "pass" if not risk["emergency_stop"] else "warn",
        f"最大杠杆 {risk['max_leverage']}x；单笔仓位 {risk['max_position_pct']:.1%}；日亏损 {risk['max_daily_loss_pct']:.1%}。",
    )
    add(
        "OMS reconciliation",
        "pass" if oms["needs_reconcile"] == 0 and oms["unknown_venue_status"] == 0 else "warn",
        f"订单={oms['total_orders']}；待对账={oms['needs_reconcile']}；未知状态={oms['unknown_venue_status']}。",
    )
    add(
        "Exchange recovery",
        "pass",
        "首页使用轻量摘要；完整交易所恢复同步在 readiness/go-live gate 中异步验证。",
    )
    add(
        "Audit hash chain",
        "pass",
        "首页使用轻量摘要；完整哈希链在 readiness/go-live gate 中异步验证。",
    )
    add(
        "Alert watchdog",
        "pass",
        "首页读取当前告警快照；完整看门狗规则由 /api/alerts/check 和 readiness 异步验证。",
    )
    add(
        "Go-live gate",
        "pass" if not (ENABLE_BINANCE_LIVE or BINANCE_PLACE_LIVE_ORDERS or EXCHANGE_MODE == "live_guarded") else "warn",
        "首页显示轻量摘要；真实下单和门禁按钮仍使用完整 go-live gate。",
    )
    add(
        "AI operator console",
        "pass" if operator["enabled"] else "warn",
        (
            f"启用={source_label(str(operator['enabled']))}；"
            f"文件写入={source_label(str(operator['allow_file_write']))}；"
            f"Shell={source_label(str(operator['allow_shell']))}。"
        ),
    )
    add(
        "Live trading lock",
        "pass" if not BINANCE_PLACE_LIVE_ORDERS and EXCHANGE_MODE != "live_guarded" else "warn",
        f"实盘真实下单={source_label(str(BINANCE_PLACE_LIVE_ORDERS))}；当前模式={mode_label(EXCHANGE_MODE)}。",
    )
    add(
        "Binance live guard",
        "pass" if not BINANCE_PLACE_LIVE_ORDERS and EXCHANGE_MODE != "live_guarded" else "warn",
        "live_guarded 默认锁定；真实下单仍要求完整门禁、人工证据和短时武装。",
    )
    if any(item["status"] == "fail" for item in items):
        overall = "fail"
    elif any(item["status"] == "warn" for item in items):
        overall = "warn"
    else:
        overall = "pass"
    return {
        "overall": overall,
        "updated_at": utc_now(),
        "summary_only": True,
        "items": items,
    }


def best_params_for_candles(symbol: str, interval: str, candles: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = []
    for params in comparison_param_grid():
        result = run_strategy_backtest(
            symbol,
            interval,
            len(candles),
            params=params,
            candles=candles,
        )
        metrics = result["metrics"]
        candidates.append(
            {
                "rank_score": backtest_rank_score(metrics),
                "metrics": metrics,
                "params": params,
                "display_params": metrics["params"],
            }
        )
    candidates.sort(
        key=lambda item: (
            item["rank_score"],
            item["metrics"]["total_return_pct"],
            -item["metrics"]["max_drawdown_pct"],
            item["metrics"]["trade_count"],
        ),
        reverse=True,
    )
    return candidates[0]


def execute_walkforward(symbol: str, interval: str, bars: int) -> dict[str, Any]:
    bars = max(160, min(1000, int(bars)))
    interval = interval if interval in {"5m", "15m", "1h", "4h"} else "15m"
    candles = fetch_klines(symbol, interval, bars)
    if len(candles) < 160:
        raise ValueError("Walk-forward needs at least 160 candles")

    test_bars = 60 if len(candles) < 360 else 80
    min_train_target = 100 if len(candles) < 220 else 120 if len(candles) < 360 else 180
    min_train = max(100, min(min_train_target, len(candles) - test_bars))
    fold_count = max(1, min(4, (len(candles) - min_train) // test_bars))
    initial_train = len(candles) - fold_count * test_bars

    folds = []
    aggregate_net = 0.0
    aggregate_trades = 0
    aggregate_wins = 0
    aggregate_losses = 0
    max_fold_drawdown = 0.0

    for fold_index in range(fold_count):
        train_end = initial_train + fold_index * test_bars
        test_end = train_end + test_bars
        train_candles = candles[:train_end]
        test_candles = candles[train_end:test_end]
        if len(test_candles) < 60:
            continue

        best = best_params_for_candles(symbol, interval, train_candles)
        test_result = run_strategy_backtest(
            symbol,
            interval,
            len(test_candles),
            params=best["params"],
            candles=test_candles,
        )
        train_metrics = best["metrics"]
        test_metrics = test_result["metrics"]
        aggregate_net += float(test_metrics["net_pnl_usdt"])
        aggregate_trades += int(test_metrics["trade_count"])
        aggregate_wins += sum(1 for trade in test_result["trades"] if trade["pnl_usdt"] > 0)
        aggregate_losses += sum(1 for trade in test_result["trades"] if trade["pnl_usdt"] < 0)
        max_fold_drawdown = max(max_fold_drawdown, float(test_metrics["max_drawdown_pct"]))
        folds.append(
            {
                "fold": fold_index + 1,
                "train_start": ms_to_iso(train_candles[0]["open_time"]),
                "train_end": ms_to_iso(train_candles[-1]["close_time"]),
                "test_start": ms_to_iso(test_candles[0]["open_time"]),
                "test_end": ms_to_iso(test_candles[-1]["close_time"]),
                "rank_score": best["rank_score"],
                "selected_params": best["display_params"],
                "train_metrics": {
                    "total_return_pct": train_metrics["total_return_pct"],
                    "max_drawdown_pct": train_metrics["max_drawdown_pct"],
                    "trade_count": train_metrics["trade_count"],
                    "win_rate_pct": train_metrics["win_rate_pct"],
                },
                "test_metrics": {
                    "total_return_pct": test_metrics["total_return_pct"],
                    "net_pnl_usdt": test_metrics["net_pnl_usdt"],
                    "max_drawdown_pct": test_metrics["max_drawdown_pct"],
                    "trade_count": test_metrics["trade_count"],
                    "win_rate_pct": test_metrics["win_rate_pct"],
                },
            }
        )

    positive_folds = sum(1 for fold in folds if fold["test_metrics"]["total_return_pct"] > 0)
    win_rate = (
        (aggregate_wins / (aggregate_wins + aggregate_losses)) * 100
        if (aggregate_wins + aggregate_losses)
        else 0.0
    )
    summary = {
        "id": f"WF-{str(uuid.uuid4())[:8].upper()}",
        "symbol": symbol.upper(),
        "interval": interval,
        "bars": len(candles),
        "created_at": utc_now(),
        "fold_count": len(folds),
        "train_mode": "expanding_window_grid_search",
        "tested_params_per_fold": len(comparison_param_grid()),
        "net_pnl_usdt": round(aggregate_net, 2),
        "total_return_pct": round((aggregate_net / ACCOUNT_EQUITY_USDT) * 100, 2),
        "max_fold_drawdown_pct": round(max_fold_drawdown, 2),
        "positive_fold_rate_pct": round((positive_folds / len(folds)) * 100, 2) if folds else 0.0,
        "test_trade_count": aggregate_trades,
        "test_win_rate_pct": round(win_rate, 2),
        "folds": folds,
    }
    set_setting("latest_walkforward", json.dumps(summary))
    return summary


def deployment_readiness() -> dict[str, Any]:
    latest = get_latest_run()
    latest_backtests = get_backtests(limit=1)
    comparison = get_latest_backtest_comparison()
    walkforward = get_latest_walkforward()
    account_state = paper_account_state()["account"]

    items: list[dict[str, str]] = []

    def add(name: str, status: str, detail: str) -> None:
        items.append({"name": name, "status": status, "detail": detail})

    add(
        "Runtime",
        "pass" if APP_ENV in {"local", "server"} else "warn",
        f"环境={source_label(APP_ENV)}，监听地址={HOST}，端口={PORT}。",
    )
    add(
        "Market data",
        "pass" if MARKET_DATA_SOURCE in {"binance_public", "synthetic"} else "fail",
        f"当前行情源：{source_label(MARKET_DATA_SOURCE)}。",
    )
    add(
        "AI adapter",
        "pass" if ai_status()["ready"] else "warn",
        f"当前决策适配器：{source_label(ai_status()['provider'])} / {source_label(ai_status()['model'])}。",
    )
    add(
        "Research boundary",
        "pass",
        "研究代理只输出研究工件和 TradeIntent；订单动作必须经过确定性风控与 OMS。",
    )
    add(
        "Architecture blueprint",
        "pass",
        "已显式建模研究、控制、执行、观测四平面，并标出生产缺口。",
    )
    add(
        "Execution boundary",
        "pass" if EXCHANGE_MODE in enabled_modes() else "fail",
        f"当前模式={mode_label(EXCHANGE_MODE)}；已启用模式={', '.join(mode_label(mode) for mode in enabled_modes())}。",
    )
    add(
        "Paper workflow",
        "pass" if latest and latest.get("status") == "completed" else "warn",
        f"最近一次运行状态：{zh_status((latest or {}).get('status', 'none'))}。",
    )
    add(
        "Paper ledger",
        "pass" if account_state.get("realized_pnl_usdt") is not None else "warn",
        f"权益={account_state.get('equity_usdt')} USDT，当前持仓={account_state.get('open_position_count')}。",
    )
    sched = scheduler_status()
    add(
        "Scheduled paper runs",
        "pass" if (APP_ENV != "server" or sched["enabled"]) else "warn",
        f"启用={source_label(str(sched['enabled']))}，交易对={sched['symbol']}，间隔={sched['interval_minutes']} 分钟。",
    )
    drill = testnet_drill_status()
    drill_status = "pass"
    if drill["last_error"]:
        drill_status = "warn"
    elif APP_ENV == "server" and drill["completed_cycles"] < 1:
        drill_status = "warn"
    add(
        "Testnet drill",
        drill_status,
        (
            f"enabled={source_label(str(drill['enabled']))}; mode={mode_label(drill['mode'])}; "
            f"real={drill['real_completed_cycles']}/{drill['target_cycles']}; "
            f"dry_run={drill['dry_run_completed_cycles']}; total={drill['completed_cycles']}; "
            f"last_error={drill['last_error'] or '-'}."
        ),
    )
    risk = risk_config()
    add(
        "Risk controls",
        "pass" if not risk["emergency_stop"] else "warn",
        (
            f"最大杠杆={risk['max_leverage']}x，单笔仓位={risk['max_position_pct']:.1%}，"
            f"日亏损={risk['max_daily_loss_pct']:.1%}，交易对={', '.join(risk['allowed_symbols'])}。"
        ),
    )
    oms = oms_summary()
    add(
        "OMS reconciliation",
        "pass" if oms["needs_reconcile"] == 0 and oms["unknown_venue_status"] == 0 else "warn",
        (
            f"订单={oms['total_orders']}，已对账={oms['reconciled_orders']}，"
            f"待对账={oms['needs_reconcile']}，未知状态={oms['unknown_venue_status']}。"
        ),
    )
    audit = audit_chain_status(limit=5)
    add(
        "Audit hash chain",
        "pass" if audit["status"] == "pass" and audit["total_records"] > 0 else "fail",
        (
            f"记录={audit['total_records']}，断裂={audit['broken_count']}，最后哈希={audit['last_hash'][:12]}..."
            if audit["total_records"]
            else "审计链尚无记录。"
        ),
    )
    recovery = exchange_recovery_status()
    recovery_report = recovery.get("last_report") or {}
    recovery_errors = recovery_report.get("errors") or []
    add(
        "Exchange recovery",
        "pass" if recovery.get("last_at") and not recovery_errors else "warn",
        (
            f"最近同步={recovery.get('last_at') or '尚未执行'}，"
            f"账户快照={len(recovery.get('snapshots') or [])}，"
            f"私有流={source_label((recovery.get('user_stream') or {}).get('status'))}。"
        ),
    )
    user_stream = recovery.get("user_stream") or {}
    stream_has_key = bool(user_stream.get("listen_key_present"))
    stream_ok = user_stream.get("dependency_ready") and (
        not stream_has_key or user_stream.get("consumer_running")
    )
    add(
        "Private user stream",
        "pass" if stream_ok else "warn",
        (
            f"WebSocket 依赖={source_label(str(user_stream.get('dependency_ready')))}，"
            f"listenKey={source_label(str(stream_has_key))}，"
            f"消费线程={source_label(str(user_stream.get('consumer_running')))}，"
            f"最近事件={user_stream.get('last_event_type') or '-'}。"
        ),
    )
    alert_state = run_watchdog_checks()
    alerts = alert_state["summary"]
    add(
        "Alert watchdog",
        "fail" if alerts["critical"] else ("warn" if alerts["warning"] else "pass"),
        (
            f"活跃告警={alerts['active']}，严重={alerts['critical']}，"
            f"警告={alerts['warning']}，已确认={alerts['acknowledged']}。"
        ),
    )
    delivery = alert_delivery_config()
    delivery_ready = bool(delivery.get("any_channel_ready"))
    add(
        "Alert delivery",
        "pass" if delivery_ready or APP_ENV != "server" else "warn",
        (
            f"可用通道={', '.join(item['channel'] for item in delivery['channels'] if item['enabled'] and item['configured']) or '无'}，"
            f"最低级别={delivery['min_severity']}。"
        ),
    )
    add(
        "Backtest",
        "pass" if latest_backtests and latest_backtests[0].get("status") == "completed" else "warn",
        f"最近回测：{(latest_backtests[0]['id'] if latest_backtests else 'none')}。",
    )
    add(
        "Parameter comparison",
        "pass" if comparison and comparison.get("tested_count", 0) >= 12 else "warn",
        f"最近参数比较：{(comparison or {}).get('id', 'none')}。",
    )
    add(
        "Walk-forward",
        "pass" if walkforward and walkforward.get("fold_count", 0) >= 1 else "warn",
        f"最近滚动验证：{(walkforward or {}).get('id', 'none')}。",
    )
    walkforward_fold_count = int(safe_float((walkforward or {}).get("fold_count"), 0))
    walkforward_return = safe_float((walkforward or {}).get("total_return_pct"), -999999.0)
    walkforward_positive_rate = safe_float((walkforward or {}).get("positive_fold_rate_pct"), 0.0)
    walkforward_drawdown = safe_float((walkforward or {}).get("max_fold_drawdown_pct"), 999999.0)
    walkforward_quality_ok = bool(
        walkforward
        and walkforward_fold_count >= GO_LIVE_MIN_WALKFORWARD_FOLDS
        and walkforward_return >= GO_LIVE_MIN_WALKFORWARD_TOTAL_RETURN_PCT
        and walkforward_positive_rate >= GO_LIVE_MIN_WALKFORWARD_POSITIVE_FOLD_RATE_PCT
        and walkforward_drawdown <= GO_LIVE_MAX_WALKFORWARD_DRAWDOWN_PCT
    )
    add(
        "Walk-forward quality",
        "pass" if walkforward_quality_ok else "warn",
        (
            f"折数={walkforward_fold_count}/{GO_LIVE_MIN_WALKFORWARD_FOLDS}，"
            f"总收益={walkforward_return:.2f}%/{GO_LIVE_MIN_WALKFORWARD_TOTAL_RETURN_PCT:.2f}%，"
            f"正收益折数={walkforward_positive_rate:.2f}%/{GO_LIVE_MIN_WALKFORWARD_POSITIVE_FOLD_RATE_PCT:.2f}%，"
            f"最大回撤={walkforward_drawdown:.2f}%/{GO_LIVE_MAX_WALKFORWARD_DRAWDOWN_PCT:.2f}%。"
        ),
    )
    add(
        "Server auth",
        "pass" if (APP_ENV != "server" or AUTH_ENABLED) else "fail",
        "已配置基础认证。" if AUTH_ENABLED else "本地模式可不启用认证；服务器模式必须配置基础认证。",
    )
    bind_is_public = TRADER_BIND_IP in {"0.0.0.0", "::", ""}
    add(
        "Private network access",
        "pass" if APP_ENV != "server" or not bind_is_public else "fail",
        (
            f"Docker 主机绑定地址={TRADER_BIND_IP or '未设置'}；"
            "服务器阶段应绑定 127.0.0.1/Tailscale IP，并通过 Tailscale 私有网络访问。"
        ),
    )
    testnet_key_ready = bool(BINANCE_API_KEY and BINANCE_API_SECRET)
    if ENABLE_BINANCE_TESTNET and not testnet_key_ready:
        testnet_status = "fail"
    elif BINANCE_PLACE_TESTNET_ORDERS:
        testnet_status = "warn"
    else:
        testnet_status = "pass"
    add(
        "Binance testnet guard",
        testnet_status,
        (
            f"测试网验证={source_label(str(ENABLE_BINANCE_TESTNET))}，"
            f"密钥就绪={source_label(str(testnet_key_ready))}，"
            f"真实测试网下单={source_label(str(BINANCE_PLACE_TESTNET_ORDERS))}。"
        ),
    )
    live_requested_for_readiness = bool(
        ENABLE_BINANCE_LIVE
        or BINANCE_PLACE_LIVE_ORDERS
        or EXCHANGE_MODE == "live_guarded"
        or BINANCE_LIVE_API_KEY
        or BINANCE_LIVE_API_SECRET
    )
    time_drift = (
        safe_binance_time_drift_status("live_guarded")
        if live_requested_for_readiness
        else {
            "status": "pass",
            "mode": "paper",
            "skipped": True,
            "reason": "live_not_requested",
            "max_drift_ms": BINANCE_MAX_TIME_DRIFT_MS,
            "checked_at": utc_now(),
        }
    )
    time_drift_ok = time_drift.get("status") == "pass"
    add(
        "Binance time drift",
        "pass" if time_drift_ok else ("warn" if live_requested_for_readiness else "pass"),
        (
            f"本机与 Binance serverTime 漂移 {time_drift.get('abs_drift_ms')}ms，阈值 {BINANCE_MAX_TIME_DRIFT_MS}ms。"
            if time_drift_ok and not time_drift.get("skipped")
            else "实盘未请求；启用 live 前会强制检查本机时间与 Binance serverTime 漂移。"
        ),
    )
    margin_type_valid = BINANCE_TARGET_MARGIN_TYPE in {"ISOLATED", "CROSSED"}
    add(
        "Binance margin type sync",
        "pass" if BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER and margin_type_valid else "warn",
        (
            f"真实 Testnet/实盘下单前会先同步保证金模式为 {BINANCE_TARGET_MARGIN_TYPE}。"
            if BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER and margin_type_valid
            else "未启用或未正确配置交易所保证金模式同步；实盘前必须开启。"
        ),
    )
    add(
        "Binance leverage sync",
        "pass" if BINANCE_SYNC_LEVERAGE_BEFORE_ORDER else "warn",
        (
            "真实 Testnet/实盘下单前会先同步交易对杠杆。"
            if BINANCE_SYNC_LEVERAGE_BEFORE_ORDER
            else "未启用交易所杠杆同步；实盘前必须开启。"
        ),
    )
    position_modes = (exchange_recovery_status().get("last_report") or {}).get("position_modes") or []
    live_position_mode = next((item for item in position_modes if item.get("mode") == "live_guarded"), None)
    any_position_mode = live_position_mode or next((item for item in position_modes if item.get("position_mode")), None)
    add(
        "Binance position mode",
        (
            "pass"
            if any_position_mode and any_position_mode.get("position_mode") == "ONE_WAY"
            else ("warn" if live_requested_for_readiness else "pass")
        ),
        (
            f"最近同步的持仓模式={any_position_mode.get('position_mode')}，模式来源={mode_label(any_position_mode.get('mode'))}。"
            if any_position_mode
            else "实盘未请求；持仓模式将在配置 live key 后由交易所恢复同步验证为 One-way。"
        ),
    )
    attestation = live_attestation_status()
    add(
        "Live attestation",
        (
            "pass"
            if attestation["status"] == "pass"
            else ("fail" if live_requested_for_readiness else "warn")
        ),
        (
            f"人工证据已由 {attestation['actor'] or 'operator'} 在 {attestation['attested_at']} 确认，"
            f"有效期 {attestation['max_age_days']} 天。"
            if attestation["status"] == "pass"
            else "实盘未请求时可保持未确认；启用 live 前必须确认 live key 权限、IP 白名单、合规、外部备份和小额试运行额度。"
        ),
    )
    live_snapshot = latest_exchange_account_snapshot("live_guarded")
    live_wallet_balance = safe_float(((live_snapshot or {}).get("summary") or {}).get("wallet_balance_usdt"), 0.0)
    if LIVE_PILOT_MAX_WALLET_USDT <= 0:
        pilot_status = "fail" if live_requested_for_readiness else "warn"
        pilot_detail = "首轮实盘资金上限未配置；LIVE_PILOT_MAX_WALLET_USDT 必须大于 0。"
    elif live_snapshot and live_wallet_balance <= LIVE_PILOT_MAX_WALLET_USDT:
        pilot_status = "pass"
        pilot_detail = (
            f"live 钱包余额={live_wallet_balance:.2f} USDT，"
            f"首轮上限={LIVE_PILOT_MAX_WALLET_USDT:.2f} USDT。"
        )
    elif live_requested_for_readiness:
        pilot_status = "fail"
        pilot_detail = (
            "实盘已请求但没有新鲜 live 账户快照，或钱包余额超过首轮试运行资金上限。"
        )
    else:
        pilot_status = "pass"
        pilot_detail = (
            f"实盘未请求；启用 live 后会要求 live 钱包余额不超过 {LIVE_PILOT_MAX_WALLET_USDT:.2f} USDT。"
        )
    add("Live pilot capital", pilot_status, pilot_detail)
    live_key_ready = bool(BINANCE_LIVE_API_KEY and BINANCE_LIVE_API_SECRET)
    live_confirmation_ready = LIVE_TRADING_CONFIRMATION == "I_UNDERSTAND_LIVE_RISK"
    if EXCHANGE_MODE == "live_guarded" and not (
        ENABLE_BINANCE_LIVE and live_key_ready and BINANCE_PLACE_LIVE_ORDERS and live_confirmation_ready
    ):
        live_status = "fail"
    elif BINANCE_PLACE_LIVE_ORDERS or ENABLE_BINANCE_LIVE:
        live_status = "warn"
    else:
        live_status = "pass"
    add(
        "Binance live guard",
        live_status,
        (
            f"实盘启用={source_label(str(ENABLE_BINANCE_LIVE))}，"
            f"实盘密钥={source_label(str(live_key_ready))}，"
            f"实盘真实下单={source_label(str(BINANCE_PLACE_LIVE_ORDERS))}，"
            f"确认短语={source_label(str(live_confirmation_ready))}。"
        ),
    )
    go_live_gate = go_live_gate_status()
    if go_live_gate["ready_for_live_order"]:
        go_live_readiness_status = "pass"
        go_live_detail = "实盘准入门禁已全部通过，live_guarded 可执行真实订单。"
    elif go_live_gate["live_requested"]:
        go_live_readiness_status = "fail"
        go_live_detail = (
            f"实盘已被请求但仍有 {len(go_live_gate['blocking_gates'])} 个阻塞门禁："
            + "、".join(item["label"] for item in go_live_gate["blocking_gates"][:5])
        )
    else:
        go_live_readiness_status = "pass"
        go_live_detail = (
            f"实盘锁定中；准入前置通过={source_label(str(go_live_gate['ready_to_enable_live']))}，"
            f"阻塞项={len(go_live_gate['blocking_gates'])}。"
        )
    add("Go-live gate", go_live_readiness_status, go_live_detail)
    operator = ai_operator_status()
    operator_status = "pass" if operator["enabled"] else "warn"
    if APP_ENV == "server" and (operator["allow_file_write"] or operator["allow_shell"]) and not AUTH_ENABLED:
        operator_status = "fail"
    add(
        "AI operator console",
        operator_status,
        (
            f"启用={source_label(str(operator['enabled']))}，提供方={source_label(operator['provider'])}，"
            f"文件读取={source_label(str(operator['allow_file_read']))}，"
            f"文件写入={source_label(str(operator['allow_file_write']))}，"
            f"模型动作自动执行={source_label(str(operator['apply_model_file_actions']))}。"
        ),
    )
    add(
        "Live trading lock",
        "pass" if not BINANCE_PLACE_LIVE_ORDERS and EXCHANGE_MODE != "live_guarded" else "warn",
        f"实盘真实下单={source_label(str(BINANCE_PLACE_LIVE_ORDERS))}；当前模式={mode_label(EXCHANGE_MODE)}。",
    )

    if any(item["status"] == "fail" for item in items):
        overall = "fail"
    elif any(item["status"] == "warn" for item in items):
        overall = "warn"
    else:
        overall = "pass"

    return {
        "overall": overall,
        "updated_at": utc_now(),
        "items": items,
    }


TRADE_INTENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "side": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
        "confidence": {"type": "number"},
        "entry_price": {"type": "number"},
        "stop_loss": {"type": "number"},
        "take_profit": {"type": "number"},
        "leverage": {"type": "number"},
        "position_pct": {"type": "number"},
        "time_horizon": {"type": "string"},
        "rationale": {"type": "string"},
    },
    "required": [
        "side",
        "confidence",
        "entry_price",
        "stop_loss",
        "take_profit",
        "leverage",
        "position_pct",
        "time_horizon",
        "rationale",
    ],
}


def score_market(snapshot: dict[str, Any]) -> float:
    score = 0.0
    score += snapshot["change_24h_pct"] * 0.9
    score += snapshot["open_interest_change_pct"] * 0.7
    score += (snapshot["long_short_ratio"] - 1) * 4.0
    score += snapshot["depth_imbalance"] * 3.0
    if snapshot["funding_rate_pct"] > 0.02:
        score -= 1.4
    if snapshot["funding_rate_pct"] < -0.01:
        score += 0.6
    if snapshot["liquidation_pressure"] == "high":
        score -= 1.2
    return round(score, 2)


def build_rule_trade_intent(snapshot: dict[str, Any], fallback_reason: str | None = None) -> dict[str, Any]:
    score = score_market(snapshot)
    side = "BUY" if score >= 0.8 else "SELL" if score <= -0.8 else "HOLD"
    price = snapshot["mark_price"]
    volatility = snapshot["realized_volatility_pct"] / 100
    stop_distance = max(0.012, min(0.035, volatility * 0.72))
    take_distance = stop_distance * 1.65
    leverage = 2.0 if snapshot["liquidation_pressure"] != "high" else 1.0

    if side == "BUY":
        stop_loss = price * (1 - stop_distance)
        take_profit = price * (1 + take_distance)
    elif side == "SELL":
        stop_loss = price * (1 + stop_distance)
        take_profit = price * (1 - take_distance)
    else:
        stop_loss = price
        take_profit = price

    return {
        "symbol": snapshot["symbol"],
        "side": side,
        "score": score,
        "confidence": round(min(0.82, 0.48 + abs(score) / 12), 2),
        "entry_price": round(price, 2),
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "leverage": leverage,
        "position_pct": 0.03 if side != "HOLD" else 0,
        "time_horizon": "30-90 minutes",
        "provider": "rules",
        "model": "deterministic_rules_v1",
        "ai_enabled": False,
        "fallback_reason": fallback_reason,
        "rationale": (
            "动量、资金费率、持仓量与盘口不平衡共同形成"
            f" {score} 的综合评分。在真实交易所数据和回测链路充分验证前，"
            "建议仓位保持小规模。"
        ),
    }


def decision_prompt(snapshot: dict[str, Any]) -> str:
    context = {
        "task": "Produce one crypto perpetual futures TradeIntent. You propose only; deterministic risk code decides execution.",
        "hard_rules": [
            "Return HOLD when the evidence is weak or contradictory.",
            f"Never request leverage above {MAX_LEVERAGE}x.",
            f"Never request position_pct above {MAX_POSITION_PCT}.",
            "Directional BUY must have stop_loss below entry_price and take_profit above entry_price.",
            "Directional SELL must have stop_loss above entry_price and take_profit below entry_price.",
            "Do not invent live news or social signals not present in the supplied context.",
        ],
        "market_snapshot": snapshot,
        "derived_market_score": score_market(snapshot),
        "available_news": "No live news connector is enabled in this local build.",
    }
    return json.dumps(context, ensure_ascii=False, indent=2)


def extract_openai_output_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return content["text"]
    raise ValueError("OpenAI response did not contain output_text")


def call_openai_trade_intent(snapshot: dict[str, Any]) -> dict[str, Any]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    payload = {
        "model": AI_MODEL,
        "input": [
            {
                "role": "system",
                "content": (
                    "You are a crypto futures trading analyst. Output only the requested JSON shape. "
                    "You never execute orders, never ask for secrets, and never override risk controls."
                ),
            },
            {"role": "user", "content": decision_prompt(snapshot)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "trade_intent",
                "strict": True,
                "schema": TRADE_INTENT_SCHEMA,
            }
        },
        "temperature": 0.2,
        "store": False,
    }
    response = http_post_json(
        f"{OPENAI_BASE_URL}/responses",
        payload,
        {"Authorization": f"Bearer {OPENAI_API_KEY}"},
    )
    parsed = json.loads(extract_openai_output_text(response))
    parsed["provider"] = "openai"
    parsed["model"] = AI_MODEL
    parsed["ai_enabled"] = True
    parsed["fallback_reason"] = None
    return parsed


def validate_trade_intent(intent: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    side = str(intent.get("side", "HOLD")).upper()
    if side not in {"BUY", "SELL", "HOLD"}:
        raise ValueError(f"Unsupported side: {side}")

    entry = float(intent.get("entry_price") or snapshot["mark_price"])
    stop = float(intent.get("stop_loss") or entry)
    target = float(intent.get("take_profit") or entry)
    leverage = float(intent.get("leverage") or 1)
    position_pct = float(intent.get("position_pct") or 0)
    confidence = float(intent.get("confidence") or 0)

    if leverage < 1 or leverage > MAX_LEVERAGE:
        raise ValueError(f"Leverage {leverage} is outside 1-{MAX_LEVERAGE}")
    if position_pct < 0 or position_pct > MAX_POSITION_PCT:
        raise ValueError(f"Position {position_pct} exceeds max {MAX_POSITION_PCT}")

    if side == "BUY" and not (stop < entry < target):
        raise ValueError("BUY intent must satisfy stop_loss < entry_price < take_profit")
    if side == "SELL" and not (target < entry < stop):
        raise ValueError("SELL intent must satisfy take_profit < entry_price < stop_loss")
    if side == "HOLD":
        stop = entry
        target = entry
        position_pct = 0.0
        leverage = 1.0

    return {
        "symbol": snapshot["symbol"],
        "side": side,
        "score": score_market(snapshot),
        "confidence": round(max(0.0, min(confidence, 1.0)), 2),
        "entry_price": round(entry, 2),
        "stop_loss": round(stop, 2),
        "take_profit": round(target, 2),
        "leverage": round(leverage, 2),
        "position_pct": round(position_pct, 4),
        "time_horizon": str(intent.get("time_horizon") or "30-90 minutes")[:80],
        "provider": intent.get("provider", AI_PROVIDER),
        "model": intent.get("model", AI_MODEL),
        "ai_enabled": bool(intent.get("ai_enabled")),
        "fallback_reason": intent.get("fallback_reason"),
        "prompt_summary": "基于行情、持仓、资金费率、盘口深度和明确的新闻缺口上下文生成结构化交易意图。",
        "rationale": str(intent.get("rationale") or "未提供理由。")[:800],
    }


def build_trade_intent(snapshot: dict[str, Any]) -> dict[str, Any]:
    if AI_PROVIDER == "rules":
        return validate_trade_intent(build_rule_trade_intent(snapshot), snapshot)
    if AI_PROVIDER == "openai":
        try:
            return validate_trade_intent(call_openai_trade_intent(snapshot), snapshot)
        except Exception as exc:
            return validate_trade_intent(
                build_rule_trade_intent(
                    snapshot,
                    fallback_reason=f"OpenAI 决策适配器不可用：{exc.__class__.__name__}: {exc}",
                ),
                snapshot,
            )
    return validate_trade_intent(
        build_rule_trade_intent(
            snapshot,
            fallback_reason=f"不支持的 AI_PROVIDER={AI_PROVIDER}；已使用确定性规则。",
        ),
        snapshot,
    )


def today_realized_pnl() -> float:
    day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    with DB_LOCK, connect() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(realized_pnl), 0) AS realized
            FROM positions
            WHERE status = 'closed' AND closed_at >= ?
            """,
            (day_start.isoformat(timespec="seconds"),),
        ).fetchone()
    return float(row["realized"] or 0)


def current_consecutive_losses() -> int:
    with DB_LOCK, connect() as conn:
        rows = conn.execute(
            """
            SELECT realized_pnl
            FROM positions
            WHERE status = 'closed'
            ORDER BY closed_at DESC
            LIMIT 100
            """
        ).fetchall()
    losses = 0
    for row in rows:
        if float(row["realized_pnl"] or 0) < 0:
            losses += 1
        else:
            break
    return losses


def account_state_for_mode(mode: str) -> dict[str, Any]:
    normalized = str(mode or "paper").lower().strip()
    if normalized == "paper":
        account = paper_account_state()["account"]
        return {
            **account,
            "source": "paper",
            "snapshot_id": "",
            "synced_at": account.get("updated_at", utc_now()),
            "snapshot_age_seconds": 0,
        }
    exchange_snapshot = sync_exchange_account_snapshot(normalized)
    summary = exchange_snapshot["summary"]
    equity = safe_float(summary.get("margin_balance_usdt"), safe_float(summary.get("wallet_balance_usdt"), 0.0))
    free_margin = safe_float(summary.get("available_balance_usdt"), 0.0)
    snapshot_age = seconds_since(exchange_snapshot["ts"])
    return {
        "source": normalized,
        "snapshot_id": exchange_snapshot["id"],
        "synced_at": exchange_snapshot["ts"],
        "snapshot_age_seconds": round(snapshot_age or 0, 3),
        "base_equity_usdt": round(equity, 2),
        "equity_usdt": round(equity, 2),
        "free_margin_usdt": round(free_margin, 2),
        "wallet_balance_usdt": round(safe_float(summary.get("wallet_balance_usdt"), 0.0), 2),
        "unrealized_pnl_usdt": round(safe_float(summary.get("unrealized_pnl_usdt"), 0.0), 2),
        "open_position_count": int(summary.get("open_position_count") or 0),
        "daily_realized_pnl_usdt": round(today_realized_pnl(), 2),
    }


def execution_account_freshness(mode: str, account_state: dict[str, Any] | None) -> dict[str, Any]:
    normalized = str(mode or "paper").lower().strip()
    account = account_state or {}
    if normalized == "paper":
        return {
            "status": "pass",
            "mode": normalized,
            "detail": "本地纸交易使用本地账本，不要求交易所账户快照。",
            "max_age_seconds": EXCHANGE_ACCOUNT_SNAPSHOT_MAX_AGE_SECONDS,
        }
    source = str(account.get("source") or "").lower().strip()
    snapshot_id = str(account.get("snapshot_id") or "").strip()
    synced_at = str(account.get("synced_at") or "").strip()
    age = seconds_since(synced_at)
    failures: list[str] = []
    if source != normalized:
        failures.append(f"资金快照来源 {source or '-'} 与执行模式 {normalized} 不一致")
    if not snapshot_id:
        failures.append("缺少交易所账户快照 ID")
    if age is None:
        failures.append("交易所账户快照时间无效")
    elif age > EXCHANGE_ACCOUNT_SNAPSHOT_MAX_AGE_SECONDS:
        failures.append(
            f"交易所账户快照已过期 {age:.1f}s，超过 {EXCHANGE_ACCOUNT_SNAPSHOT_MAX_AGE_SECONDS}s"
        )
    equity = safe_float(account.get("equity_usdt"), 0.0)
    free_margin = safe_float(account.get("free_margin_usdt"), -1.0)
    if equity <= 0:
        failures.append("交易所账户权益必须大于 0")
    if free_margin < 0:
        failures.append("交易所可用保证金不能为负数")
    return {
        "status": "fail" if failures else "pass",
        "mode": normalized,
        "source": source,
        "snapshot_id": snapshot_id,
        "synced_at": synced_at,
        "age_seconds": None if age is None else round(age, 3),
        "max_age_seconds": EXCHANGE_ACCOUNT_SNAPSHOT_MAX_AGE_SECONDS,
        "equity_usdt": round(equity, 2),
        "free_margin_usdt": round(free_margin, 2),
        "detail": "；".join(failures) if failures else "交易所账户快照新鲜且来源匹配，可用于本次执行 sizing。",
    }


def assert_fresh_execution_account_state(mode: str, account_state: dict[str, Any] | None) -> dict[str, Any]:
    freshness = execution_account_freshness(mode, account_state)
    if freshness["status"] != "pass":
        raise ValueError(f"Execution account snapshot is not fresh: {freshness['detail']}")
    return freshness


def execution_market_freshness(mode: str, snapshot: dict[str, Any] | None) -> dict[str, Any]:
    normalized = str(mode or "paper").lower().strip()
    market = snapshot or {}
    source = str(market.get("data_source") or "").lower().strip()
    fallback = bool(market.get("fallback"))
    source_error = str(market.get("source_error") or "").strip()
    timestamp = str(market.get("timestamp") or "").strip()
    age = seconds_since(timestamp)
    mark_price = safe_float(market.get("mark_price"), 0.0)
    detail = "纸交易或验证模式不提交真实状态订单；行情可用于研究和 payload 校验。"
    if normalized not in STATEFUL_EXCHANGE_ORDER_MODES:
        return {
            "status": "pass",
            "mode": normalized,
            "source": source or "-",
            "fallback": fallback,
            "source_error": source_error,
            "timestamp": timestamp,
            "age_seconds": None if age is None else round(age, 3),
            "max_age_seconds": EXECUTION_MARKET_SNAPSHOT_MAX_AGE_SECONDS,
            "mark_price": round(mark_price, 8),
            "detail": detail,
        }

    failures: list[str] = []
    if source != "binance_public":
        failures.append(f"真实下单要求 Binance 公共行情，当前来源为 {source_label(source or '-')}")
    if fallback:
        failures.append("行情发生 fallback，禁止用回退数据提交真实订单")
    if source_error:
        failures.append(f"行情源错误仍未清除：{source_error}")
    if age is None:
        failures.append("行情快照时间无效")
    elif age > EXECUTION_MARKET_SNAPSHOT_MAX_AGE_SECONDS:
        failures.append(
            f"行情快照已过期 {age:.1f}s，超过 {EXECUTION_MARKET_SNAPSHOT_MAX_AGE_SECONDS}s"
        )
    if mark_price <= 0:
        failures.append("行情标记价格必须大于 0")
    return {
        "status": "fail" if failures else "pass",
        "mode": normalized,
        "source": source or "-",
        "fallback": fallback,
        "source_error": source_error,
        "timestamp": timestamp,
        "age_seconds": None if age is None else round(age, 3),
        "max_age_seconds": EXECUTION_MARKET_SNAPSHOT_MAX_AGE_SECONDS,
        "mark_price": round(mark_price, 8),
        "detail": "；".join(failures) if failures else "真实下单行情快照新鲜、来源真实，未使用 fallback。",
    }


def assert_fresh_execution_market_snapshot(mode: str, snapshot: dict[str, Any] | None) -> dict[str, Any]:
    freshness = execution_market_freshness(mode, snapshot)
    if freshness["status"] != "pass":
        raise ValueError(f"Execution market snapshot is not fresh: {freshness['detail']}")
    return freshness


def stateful_order_mode_for_order(order: dict[str, Any]) -> str:
    status = str(order.get("status") or "").lower().strip()
    order_id = str(order.get("id") or "").upper().strip()
    client_order_id = str(order.get("client_order_id") or "").upper().strip()
    if status.startswith("live_") or order_id.startswith("LIVE") or client_order_id.startswith("LIVE"):
        return "live_guarded"
    if status.startswith("testnet_") or order_id.startswith("TESTLIVE") or client_order_id.startswith("TESTLIVE"):
        return "binance_testnet_place_order"
    if status == "pending_reconcile":
        return "stateful_unknown"
    return ""


def stateful_order_conflict_reason(order: dict[str, Any], mode: str, symbol: str) -> str:
    normalized_mode = str(mode or "").lower().strip()
    if normalized_mode not in STATEFUL_EXCHANGE_ORDER_MODES:
        return ""
    if str(order.get("symbol") or "").upper().strip() != str(symbol or "").upper().strip():
        return ""
    order_mode = stateful_order_mode_for_order(order)
    if order_mode not in {normalized_mode, "stateful_unknown"}:
        return ""
    status = str(order.get("status") or "").lower().strip()
    reconcile_status = str(order.get("reconcile_status") or "").lower().strip()
    venue_status = str(order.get("venue_status") or "").upper().strip()
    terminal_venue_statuses = {"FILLED", "CANCELED", "EXPIRED", "REJECTED"}
    if status == "pending_reconcile" or venue_status == "UNKNOWN":
        return "订单处于未知或待对账状态，必须先 reconcile 后才能重试"
    if status in CANCELABLE_BINANCE_ORDER_STATUSES and venue_status not in terminal_venue_statuses:
        return "交易所订单可能仍然打开，必须先确认、撤单或成交终态"
    if reconcile_status in {"unchecked", "needs_reconcile", "needs_review"} and status in NEEDS_RECONCILE_STATUSES:
        return "本地 OMS 仍要求复核该订单"
    return ""


def stateful_order_conflicts(mode: str, symbol: str, limit: int = 500) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for order in get_orders(limit=limit):
        reason = stateful_order_conflict_reason(order, mode, symbol)
        if reason:
            conflicts.append(
                {
                    "id": order.get("id"),
                    "client_order_id": order.get("client_order_id"),
                    "symbol": order.get("symbol"),
                    "status": order.get("status"),
                    "venue_status": order.get("venue_status"),
                    "reconcile_status": order.get("reconcile_status"),
                    "updated_at": order.get("updated_at"),
                    "mode": stateful_order_mode_for_order(order),
                    "reason": reason,
                }
            )
    return conflicts


def assert_no_stateful_order_conflicts(mode: str, symbol: str) -> list[dict[str, Any]]:
    conflicts = stateful_order_conflicts(mode, symbol)
    if conflicts:
        sample = ", ".join(str(item.get("id") or item.get("client_order_id")) for item in conflicts[:5])
        raise ValueError(
            f"Stateful order conflict blocks new {mode_label(mode)} order for {symbol}: "
            f"{len(conflicts)} existing order(s) require reconcile or terminal venue state first: {sample}"
        )
    return conflicts


def risk_check(intent: dict[str, Any], snapshot: dict[str, Any], mode: str = "paper") -> dict[str, Any]:
    config = risk_config()
    account_state = account_state_for_mode(mode)
    account_freshness = execution_account_freshness(mode, account_state)
    market_freshness = execution_market_freshness(mode, snapshot)
    order_conflicts = [] if intent["side"] == "HOLD" else stateful_order_conflicts(mode, intent["symbol"])
    equity_base = float(account_state.get("equity_usdt") or ACCOUNT_EQUITY_USDT)
    daily_realized = today_realized_pnl()
    daily_loss_limit = equity_base * config["max_daily_loss_pct"]
    consecutive_losses = current_consecutive_losses()
    required_margin = equity_base * intent["position_pct"]
    requested_notional = equity_base * intent["position_pct"] * intent["leverage"]
    open_positions = int(account_state.get("open_position_count") or 0)
    checks = [
        {
            "name": "Account source",
            "status": "pass",
            "detail": (
                f"资金口径={mode_label(account_state.get('source'))}；"
                f"权益={account_state.get('equity_usdt')} USDT；"
                f"快照={account_state.get('snapshot_id') or '本地账本'}。"
            ),
        },
        {
            "name": "Account snapshot freshness",
            "status": account_freshness["status"],
            "detail": account_freshness["detail"],
        },
        {
            "name": "Market snapshot freshness",
            "status": market_freshness["status"],
            "detail": market_freshness["detail"],
        },
        {
            "name": "Mode lock",
            "status": "pass",
            "detail": f"已启用运行模式：{', '.join(mode_label(mode) for mode in enabled_modes())}。",
        },
        {
            "name": "Stateful order conflict",
            "status": "fail" if order_conflicts else "pass",
            "detail": (
                f"同交易对存在 {len(order_conflicts)} 个未完成或待对账真实订单，必须先执行 OMS 对账/撤单。"
                if order_conflicts
                else "同交易对没有阻塞新真实订单的未对账/未知状态订单。"
            ),
        },
        {
            "name": "Allowed symbol",
            "status": "pass" if intent["symbol"] in config["allowed_symbols"] else "fail",
            "detail": f"{intent['symbol']} 必须在允许交易对列表内：{', '.join(config['allowed_symbols'])}。",
        },
        {
            "name": "Emergency stop",
            "status": "fail" if config["emergency_stop"] else "pass",
            "detail": "紧急停止开启时禁止产生新订单。",
        },
        {
            "name": "Max leverage",
            "status": "pass" if intent["leverage"] <= config["max_leverage"] else "fail",
            "detail": f"请求杠杆 {intent['leverage']}x，配置上限 {config['max_leverage']}x。",
        },
        {
            "name": "Max position",
            "status": "pass" if intent["position_pct"] <= config["max_position_pct"] else "fail",
            "detail": f"请求仓位 {intent['position_pct']:.1%}，配置上限 {config['max_position_pct']:.1%}。",
        },
        {
            "name": "Max order notional",
            "status": (
                "pass"
                if intent["side"] == "HOLD"
                or config["max_order_notional_usdt"] == 0
                or requested_notional <= config["max_order_notional_usdt"]
                else "fail"
            ),
            "detail": (
                f"请求名义金额 {requested_notional:.2f} USDT，"
                f"单笔上限 {config['max_order_notional_usdt']:.2f} USDT（0 表示不限制）。"
            ),
        },
        {
            "name": "Open position cap",
            "status": (
                "pass"
                if intent["side"] == "HOLD"
                or config["max_open_positions"] == 0
                or open_positions < config["max_open_positions"]
                else "fail"
            ),
            "detail": f"当前持仓 {open_positions}，配置上限 {config['max_open_positions']}（0 表示不限制）。",
        },
        {
            "name": "Free margin",
            "status": (
                "pass"
                if intent["side"] == "HOLD"
                or required_margin <= float(account_state.get("free_margin_usdt") or 0)
                else "fail"
            ),
            "detail": f"所需保证金 {required_margin:.2f} USDT，可用保证金 {account_state.get('free_margin_usdt')} USDT。",
        },
        {
            "name": "Daily loss limit",
            "status": "pass" if daily_realized >= -daily_loss_limit else "fail",
            "detail": f"今日已实现 PnL {daily_realized:.2f} USDT，亏损上限 {daily_loss_limit:.2f} USDT。",
        },
        {
            "name": "Consecutive losses",
            "status": (
                "pass"
                if config["max_consecutive_losses"] == 0
                or consecutive_losses < config["max_consecutive_losses"]
                else "fail"
            ),
            "detail": f"当前连续亏损 {consecutive_losses}，配置上限 {config['max_consecutive_losses']}（0 表示不限制）。",
        },
        {
            "name": "Stop-loss required",
            "status": "pass" if intent["side"] == "HOLD" or intent["stop_loss"] > 0 else "fail",
            "detail": "所有方向性订单都必须带止损。",
        },
        {
            "name": "Liquidation pressure",
            "status": "pass" if snapshot["liquidation_pressure"] != "high" else "warn",
            "detail": f"当前清算压力：{source_label(snapshot['liquidation_pressure'])}。",
        },
    ]
    failed = any(check["status"] == "fail" for check in checks)
    warned = any(check["status"] == "warn" for check in checks)
    return {
        "status": "rejected" if failed else "warning" if warned else "approved",
        "checks": checks,
        "config": config,
        "account": account_state,
        "market": snapshot,
        "market_freshness": market_freshness,
        "order_conflicts": order_conflicts,
    }


def signed_binance_request(
    method: str,
    path: str,
    params: dict[str, Any],
    base_url: str = BINANCE_TESTNET_FAPI_BASE,
    api_key: str | None = None,
    api_secret: str | None = None,
) -> Any:
    key = api_key if api_key is not None else BINANCE_API_KEY
    secret = api_secret if api_secret is not None else BINANCE_API_SECRET
    if not key or not secret:
        raise RuntimeError("Binance API key/secret are not configured")
    signed_params = {
        **params,
        "recvWindow": 5000,
        "timestamp": int(time.time() * 1000),
    }
    query = urlencode(signed_params)
    signature = hmac.new(
        secret.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    url = f"{base_url}{path}?{query}&signature={signature}"
    request = Request(
        url,
        data=b"" if method.upper() in {"POST", "DELETE", "PUT"} else None,
        headers={
            "X-MBX-APIKEY": key,
            "User-Agent": "crypto-contract-ai-trader/0.1",
        },
        method=method.upper(),
    )
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        raw = response.read().decode(response.headers.get_content_charset() or "utf-8")
        return json.loads(raw) if raw.strip() else {}


def format_binance_decimal(value: float, decimals: int = 6) -> str:
    formatted = f"{float(value):.{decimals}f}".rstrip("0").rstrip(".")
    return formatted or "0"


def decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    formatted = format(value.normalize(), "f")
    return formatted.rstrip("0").rstrip(".") if "." in formatted else formatted


def decimal_floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return value
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def binance_public_base_for_mode(mode: str) -> str:
    return BINANCE_LIVE_FAPI_BASE if mode == "live_guarded" else BINANCE_TESTNET_FAPI_BASE


def binance_symbol_rules(symbol: str, mode: str) -> dict[str, Any]:
    clean_symbol = "".join(ch for ch in str(symbol).upper() if ch.isalnum())
    cache_key = (mode, clean_symbol)
    with BINANCE_SYMBOL_RULES_LOCK:
        cached = BINANCE_SYMBOL_RULES_CACHE.get(cache_key)
        if cached and seconds_since(cached.get("fetched_at")) is not None and seconds_since(cached.get("fetched_at")) < 3600:
            return cached
    payload = http_get_json_base(binance_public_base_for_mode(mode), "/fapi/v1/exchangeInfo", {"symbol": clean_symbol})
    symbols = payload.get("symbols") or []
    symbol_info = next((item for item in symbols if item.get("symbol") == clean_symbol), None)
    if not symbol_info:
        raise ValueError(f"Binance exchangeInfo did not return rules for {clean_symbol}.")
    filters = {item.get("filterType"): item for item in symbol_info.get("filters", [])}
    price_filter = filters.get("PRICE_FILTER") or {}
    lot_filter = filters.get("LOT_SIZE") or {}
    min_notional_filter = filters.get("MIN_NOTIONAL") or {}
    rules = {
        "symbol": clean_symbol,
        "mode": mode,
        "fetched_at": utc_now(),
        "price_precision": symbol_info.get("pricePrecision"),
        "quantity_precision": symbol_info.get("quantityPrecision"),
        "tick_size": price_filter.get("tickSize") or "0.01",
        "min_price": price_filter.get("minPrice") or "0",
        "max_price": price_filter.get("maxPrice") or "0",
        "step_size": lot_filter.get("stepSize") or "0.001",
        "min_qty": lot_filter.get("minQty") or "0",
        "max_qty": lot_filter.get("maxQty") or "0",
        "min_notional": min_notional_filter.get("notional") or min_notional_filter.get("minNotional") or "0",
    }
    with BINANCE_SYMBOL_RULES_LOCK:
        BINANCE_SYMBOL_RULES_CACHE[cache_key] = rules
    return rules


def normalize_binance_order_params(order: dict[str, Any], mode: str) -> tuple[dict[str, Any], dict[str, Any]]:
    rules = binance_symbol_rules(order["symbol"], mode)
    price = Decimal(str(order["entry_price"]))
    quantity = Decimal(str(order["quantity"]))
    tick_size = Decimal(str(rules["tick_size"]))
    step_size = Decimal(str(rules["step_size"]))
    price = decimal_floor_to_step(price, tick_size)
    quantity = decimal_floor_to_step(quantity, step_size)
    min_price = Decimal(str(rules["min_price"]))
    max_price = Decimal(str(rules["max_price"]))
    min_qty = Decimal(str(rules["min_qty"]))
    max_qty = Decimal(str(rules["max_qty"]))
    min_notional = Decimal(str(rules["min_notional"]))
    notional = price * quantity
    failures: list[str] = []
    if price <= 0:
        failures.append("price is zero after tickSize normalization")
    if quantity <= 0:
        failures.append("quantity is zero after stepSize normalization")
    if min_price > 0 and price < min_price:
        failures.append(f"price {decimal_text(price)} is below minPrice {rules['min_price']}")
    if max_price > 0 and price > max_price:
        failures.append(f"price {decimal_text(price)} is above maxPrice {rules['max_price']}")
    if min_qty > 0 and quantity < min_qty:
        failures.append(f"quantity {decimal_text(quantity)} is below minQty {rules['min_qty']}")
    if max_qty > 0 and quantity > max_qty:
        failures.append(f"quantity {decimal_text(quantity)} is above maxQty {rules['max_qty']}")
    if min_notional > 0 and notional < min_notional:
        failures.append(f"notional {decimal_text(notional)} is below minNotional {rules['min_notional']}")
    if failures:
        raise ValueError("Binance order filter check failed: " + "; ".join(failures))
    normalized = {
        "symbol": order["symbol"],
        "side": order["side"],
        "type": "LIMIT",
        "timeInForce": "GTC",
        "quantity": decimal_text(quantity),
        "price": decimal_text(price),
        "newClientOrderId": order["client_order_id"],
        "newOrderRespType": "RESULT",
    }
    evidence = {
        "rules": rules,
        "original_quantity": order["quantity"],
        "original_price": order["entry_price"],
        "normalized_quantity": normalized["quantity"],
        "normalized_price": normalized["price"],
        "notional_usdt": decimal_text(notional),
    }
    return normalized, evidence


def binance_order_params(order: dict[str, Any], mode: str = "binance_testnet_validate") -> dict[str, Any]:
    if BINANCE_ENFORCE_EXCHANGE_FILTERS or mode == "live_guarded":
        params, evidence = normalize_binance_order_params(order, mode)
        order["binance_filter_evidence"] = evidence
        return params
    return {
        "symbol": order["symbol"],
        "side": order["side"],
        "type": "LIMIT",
        "timeInForce": "GTC",
        "quantity": format_binance_decimal(order["quantity"], 6),
        "price": format_binance_decimal(order["entry_price"], 2),
        "newClientOrderId": order["client_order_id"],
        "newOrderRespType": "RESULT",
    }


def binance_http_error_payload(exc: HTTPError) -> dict[str, Any]:
    raw = exc.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {"raw": raw}
    payload.setdefault("http_status", exc.code)
    return payload


def target_binance_margin_type() -> str:
    target = BINANCE_TARGET_MARGIN_TYPE.upper().strip()
    if target not in {"ISOLATED", "CROSSED"}:
        raise ValueError("BINANCE_TARGET_MARGIN_TYPE must be ISOLATED or CROSSED.")
    return target


def ensure_binance_margin_type(order: dict[str, Any], mode: str) -> dict[str, Any]:
    normalized_mode = str(mode or "").lower().strip()
    symbol = "".join(ch for ch in str(order.get("symbol", "")).upper() if ch.isalnum())
    target_margin = target_binance_margin_type()
    evidence: dict[str, Any] = {
        "enabled": BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER,
        "mode": normalized_mode,
        "symbol": symbol,
        "target_margin_type": target_margin,
    }
    if normalized_mode not in {"binance_testnet_place_order", "live_guarded"}:
        return {**evidence, "status": "skipped", "reason": "mode_does_not_place_stateful_orders"}
    if not BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER:
        return {**evidence, "status": "skipped", "reason": "BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER=false"}
    if not symbol:
        raise ValueError("Cannot sync Binance margin type without a symbol.")
    params = {"symbol": symbol, "marginType": target_margin}
    try:
        response = signed_binance_request_for_mode("POST", "/fapi/v1/marginType", params, normalized_mode)
    except HTTPError as exc:
        payload = binance_http_error_payload(exc)
        if int(payload.get("code") or 0) == -4046:
            return {
                **evidence,
                "status": "already_set",
                "endpoint": "/fapi/v1/marginType",
                "params": params,
                "response": payload,
                "synced_at": utc_now(),
            }
        raise ValueError(f"Binance margin type sync failed: HTTP {exc.code}: {payload}") from exc
    return {
        **evidence,
        "status": "synced",
        "endpoint": "/fapi/v1/marginType",
        "params": params,
        "response": response,
        "synced_at": utc_now(),
    }


def binance_leverage_for_order(order: dict[str, Any]) -> int:
    try:
        raw_leverage = Decimal(str(order.get("leverage", 1)))
    except Exception:
        raw_leverage = Decimal("1")
    normalized = int(raw_leverage.to_integral_value(rounding=ROUND_DOWN))
    return max(1, min(125, normalized))


def ensure_binance_leverage(order: dict[str, Any], mode: str) -> dict[str, Any]:
    normalized_mode = str(mode or "").lower().strip()
    symbol = "".join(ch for ch in str(order.get("symbol", "")).upper() if ch.isalnum())
    leverage = binance_leverage_for_order(order)
    evidence: dict[str, Any] = {
        "enabled": BINANCE_SYNC_LEVERAGE_BEFORE_ORDER,
        "mode": normalized_mode,
        "symbol": symbol,
        "requested_leverage": order.get("leverage"),
        "synced_leverage": leverage,
        "rounding": "floor_to_integer",
    }
    if normalized_mode not in {"binance_testnet_place_order", "live_guarded"}:
        return {**evidence, "status": "skipped", "reason": "mode_does_not_place_stateful_orders"}
    if not BINANCE_SYNC_LEVERAGE_BEFORE_ORDER:
        return {**evidence, "status": "skipped", "reason": "BINANCE_SYNC_LEVERAGE_BEFORE_ORDER=false"}
    if not symbol:
        raise ValueError("Cannot sync Binance leverage without a symbol.")
    params = {"symbol": symbol, "leverage": leverage}
    response = signed_binance_request_for_mode("POST", "/fapi/v1/leverage", params, normalized_mode)
    return {
        **evidence,
        "status": "synced",
        "endpoint": "/fapi/v1/leverage",
        "params": params,
        "response": response,
        "synced_at": utc_now(),
    }


def opposite_order_side(side: str) -> str:
    return "SELL" if str(side).upper() == "BUY" else "BUY"


def normalize_binance_stop_price(symbol: str, stop_price: float, mode: str) -> tuple[str, dict[str, Any]]:
    rules = binance_symbol_rules(symbol, mode)
    tick_size = Decimal(str(rules["tick_size"]))
    normalized = decimal_floor_to_step(Decimal(str(stop_price)), tick_size)
    min_price = Decimal(str(rules["min_price"]))
    max_price = Decimal(str(rules["max_price"]))
    failures: list[str] = []
    if normalized <= 0:
        failures.append("stopPrice is zero after tickSize normalization")
    if min_price > 0 and normalized < min_price:
        failures.append(f"stopPrice {decimal_text(normalized)} is below minPrice {rules['min_price']}")
    if max_price > 0 and normalized > max_price:
        failures.append(f"stopPrice {decimal_text(normalized)} is above maxPrice {rules['max_price']}")
    if failures:
        raise ValueError("Binance protection filter check failed: " + "; ".join(failures))
    return decimal_text(normalized), {
        "rules": rules,
        "original_stop_price": stop_price,
        "normalized_stop_price": decimal_text(normalized),
    }


def binance_protection_order_params(
    order: dict[str, Any],
    protection_kind: str,
    mode: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    clean_kind = "stop_loss" if protection_kind == "stop_loss" else "take_profit"
    stop_price = order["stop_loss"] if clean_kind == "stop_loss" else order["take_profit"]
    normalized_stop, evidence = normalize_binance_stop_price(order["symbol"], float(stop_price), mode)
    client_order_id = f"{order['client_order_id']}-{'SL' if clean_kind == 'stop_loss' else 'TP'}"
    order_type = "STOP_MARKET" if clean_kind == "stop_loss" else "TAKE_PROFIT_MARKET"
    params = {
        "symbol": order["symbol"],
        "side": opposite_order_side(order["side"]),
        "type": order_type,
        "stopPrice": normalized_stop,
        "closePosition": "true",
        "workingType": "MARK_PRICE",
        "priceProtect": "true",
        "newClientOrderId": client_order_id,
        "newOrderRespType": "RESULT",
    }
    evidence = {
        **evidence,
        "parent_order_id": order["id"],
        "parent_client_order_id": order["client_order_id"],
        "protection_kind": clean_kind,
        "order_type": order_type,
        "side": params["side"],
        "close_position": True,
    }
    return params, evidence


def protection_order_record(
    parent_order: dict[str, Any],
    params: dict[str, Any],
    evidence: dict[str, Any],
    mode: str,
    response: dict[str, Any],
) -> dict[str, Any]:
    prefix = "LIVE" if mode == "live_guarded" else "TESTLIVE"
    protection_kind = evidence["protection_kind"]
    venue_status = str(response.get("status") or "NEW").upper()
    now = utc_now()
    return {
        "id": str(params["newClientOrderId"]),
        "run_id": parent_order["run_id"],
        "symbol": parent_order["symbol"],
        "side": params["side"],
        "order_type": params["type"],
        "quantity": parent_order["quantity"],
        "leverage": parent_order["leverage"],
        "entry_price": float(params["stopPrice"]),
        "stop_loss": parent_order["stop_loss"],
        "take_profit": parent_order["take_profit"],
        "status": f"{'live' if prefix == 'LIVE' else 'testnet'}_protection_submitted",
        "client_order_id": params["newClientOrderId"],
        "venue_order_id": str(response.get("orderId") or ""),
        "venue_status": venue_status,
        "reconcile_status": "needs_reconcile",
        "reconcile_note": (
            f"Protective {protection_kind} {params['type']} submitted; "
            f"status={venue_status}; orderId={response.get('orderId') or '-'}."
        ),
        "last_reconciled_at": None,
        "created_at": now,
        "updated_at": now,
        "parent_order_id": parent_order["id"],
        "protection_kind": protection_kind,
        "exchange_response": response,
        "binance_filter_evidence": evidence,
    }


def validate_binance_protection_orders(
    order: dict[str, Any],
    mode: str,
    record_transition: bool = True,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for kind in ("stop_loss", "take_profit"):
        params, evidence = binance_protection_order_params(order, kind, mode)
        response = signed_binance_request_for_mode("POST", "/fapi/v1/order/test", params, mode)
        results.append({"kind": kind, "params": params, "response": response, "evidence": evidence})
    if record_transition:
        insert_order_transition(
            order["id"],
            order.get("status"),
            order.get("status", "prepared"),
            "binance_protection_test_validated",
            {"protections": results},
        )
    return results


def validate_binance_order_bundle(
    order: dict[str, Any],
    entry_params: dict[str, Any],
    mode: str,
    record_transition: bool = False,
) -> dict[str, Any]:
    entry_response = signed_binance_request_for_mode("POST", "/fapi/v1/order/test", entry_params, mode)
    protection_validation = validate_binance_protection_orders(order, mode, record_transition=record_transition)
    return {
        "mode": mode,
        "entry": {"params": entry_params, "response": entry_response},
        "protections": protection_validation,
    }


def submit_binance_protection_orders(parent_order: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    submitted: list[dict[str, Any]] = []
    for kind in ("stop_loss", "take_profit"):
        params, evidence = binance_protection_order_params(parent_order, kind, mode)
        response = signed_binance_request_for_mode("POST", "/fapi/v1/order", params, mode)
        protection = protection_order_record(parent_order, params, evidence, mode, response)
        persist_order(protection)
        submitted.append(protection)
    insert_order_transition(
        parent_order["id"],
        parent_order.get("status"),
        parent_order.get("status", "submitted"),
        "binance_protection_orders_submitted",
        {"protection_order_ids": [item["id"] for item in submitted]},
    )
    return submitted


def handle_binance_protection_submit_failure(
    parent_order: dict[str, Any],
    exc: Exception,
    mode: str,
) -> dict[str, Any]:
    order_id = str(parent_order.get("id") or "")
    live_order = mode == "live_guarded" or order_id.startswith("LIVE")
    mode_label_text = "live" if live_order else "testnet"
    error_summary = f"{exc.__class__.__name__}: {exc}"
    guard: dict[str, Any] = {
        "status": "triggered",
        "mode": mode,
        "order_id": order_id,
        "error_type": exc.__class__.__name__,
        "error": str(exc),
        "entry_cancel": {"attempted": False, "status": "not_started"},
        "protection_cancel_attempts": [],
        "live_disarm": {"attempted": False, "status": "not_applicable"},
        "reconcile_status": "needs_reconcile",
    }

    raise_alert(
        f"protection.submit_failed.{order_id}",
        "critical",
        "OMS",
        f"Binance {mode_label_text} protection order submit failed",
        (
            f"Parent order {order_id} was submitted, but protective orders failed. "
            "The guard is disarming live trading, attempting safe cancellation, and requiring reconciliation. "
            f"Error: {error_summary}"
        ),
        {"order": parent_order, "error": str(exc), "mode": mode, "guard": guard},
    )

    if get_order(order_id):
        update_order_state(
            order_id,
            reconcile_status="needs_reconcile",
            reconcile_note=f"Entry submitted but protection orders failed: {error_summary}",
            reason="binance_protection_submit_failed",
            payload={"error": str(exc), "mode": mode},
        )

    if live_order:
        guard["live_disarm"]["attempted"] = True
        try:
            guard["live_disarm"] = {
                "attempted": True,
                "status": "disarmed",
                "arming": disarm_live_trading(f"protection_submit_failed:{order_id}"),
            }
        except Exception as disarm_exc:  # noqa: BLE001 - preserve the original protection failure path.
            guard["live_disarm"] = {
                "attempted": True,
                "status": "failed",
                "error_type": disarm_exc.__class__.__name__,
                "error": str(disarm_exc),
            }

    if order_id and get_order(order_id):
        guard["entry_cancel"]["attempted"] = True
        try:
            canceled = cancel_testnet_order(order_id)
            venue_status = str(canceled.get("venue_status") or "").upper()
            entry_canceled = venue_status in {"CANCELED", "EXPIRED"} or str(canceled.get("status") or "").endswith("_canceled")
            guard["entry_cancel"] = {
                "attempted": True,
                "status": "canceled" if entry_canceled else "requires_reconcile",
                "order_status": canceled.get("status"),
                "venue_status": venue_status,
                "reconcile_status": canceled.get("reconcile_status"),
            }
        except Exception as cancel_exc:  # noqa: BLE001 - cancellation failure is evidence, not a replacement error.
            entry_canceled = False
            guard["entry_cancel"] = {
                "attempted": True,
                "status": "failed",
                "error_type": cancel_exc.__class__.__name__,
                "error": str(cancel_exc),
            }
    else:
        entry_canceled = False
        guard["entry_cancel"] = {
            "attempted": False,
            "status": "skipped",
            "reason": "parent_order_not_persisted",
        }

    child_orders = get_child_protection_orders(order_id) if order_id else []
    if child_orders and not entry_canceled:
        guard["protection_cancel_attempts"] = [
            {
                "order_id": child.get("id"),
                "status": "kept_for_safety",
                "reason": "entry_order_was_not_confirmed_canceled",
            }
            for child in child_orders
        ]
    elif child_orders:
        for child in child_orders:
            attempt = {
                "order_id": child.get("id"),
                "kind": child.get("protection_kind"),
                "previous_status": child.get("status"),
            }
            try:
                canceled_child = cancel_testnet_order(str(child["id"]))
                attempt.update(
                    {
                        "status": "canceled",
                        "new_status": canceled_child.get("status"),
                        "venue_status": canceled_child.get("venue_status"),
                        "reconcile_status": canceled_child.get("reconcile_status"),
                    }
                )
            except Exception as child_exc:  # noqa: BLE001 - keep moving through all known child orders.
                attempt.update(
                    {
                        "status": "failed",
                        "error_type": child_exc.__class__.__name__,
                        "error": str(child_exc),
                    }
                )
            guard["protection_cancel_attempts"].append(attempt)

    protection_cancels_ok = all(
        item.get("status") in {"canceled", "kept_for_safety", "skipped"}
        for item in guard["protection_cancel_attempts"]
    )
    if entry_canceled and protection_cancels_ok:
        guard["status"] = "entry_canceled"
        guard["reconcile_status"] = "reconciled"
    else:
        guard["status"] = "needs_manual_reconcile"

    if get_order(order_id):
        final_order = update_order_state(
            order_id,
            reconcile_status=guard["reconcile_status"],
            reconcile_note=(
                "Protection order submission failed; live guard attempted mitigation. "
                f"guard_status={guard['status']}; error={error_summary}"
            ),
            reason="binance_protection_failure_guard",
            payload=guard,
        )
    else:
        final_order = parent_order

    insert_event(
        parent_order.get("run_id") or "system",
        "risk",
        "Protection Failure Guard",
        f"Binance {mode_label_text} protection failure guard triggered",
        (
            f"Order {order_id} protection submission failed. "
            f"Guard status={guard['status']}; entry_cancel={guard['entry_cancel'].get('status')}."
        ),
        {"guard": guard, "order": final_order},
    )
    return {"guard": guard, "order": final_order}


def binance_credentials_for_mode(mode: str) -> dict[str, str]:
    if mode == "live_guarded":
        return {
            "base_url": BINANCE_LIVE_FAPI_BASE,
            "api_key": BINANCE_LIVE_API_KEY,
            "api_secret": BINANCE_LIVE_API_SECRET,
        }
    return {
        "base_url": BINANCE_TESTNET_FAPI_BASE,
        "api_key": BINANCE_API_KEY,
        "api_secret": BINANCE_API_SECRET,
    }


def signed_binance_request_for_mode(method: str, path: str, params: dict[str, Any], mode: str) -> Any:
    creds = binance_credentials_for_mode(mode)
    return signed_binance_request(
        method,
        path,
        params,
        base_url=creds["base_url"],
        api_key=creds["api_key"],
        api_secret=creds["api_secret"],
    )


def mask_secret(value: str | None) -> str:
    raw = str(value or "")
    if not raw:
        return ""
    if len(raw) <= 10:
        return f"{raw[:2]}***{raw[-2:]}"
    return f"{raw[:5]}...{raw[-5:]}"


def binance_ws_base_for_mode(mode: str) -> str:
    return BINANCE_LIVE_WS_BASE if mode == "live_guarded" else BINANCE_TESTNET_WS_BASE


def user_stream_dependency_ready() -> bool:
    return importlib.util.find_spec("websockets") is not None


def build_binance_user_stream_url(mode: str, listen_key: str) -> str:
    base = binance_ws_base_for_mode(mode).rstrip("/")
    return f"{base}/ws/{listen_key}"


def current_user_stream_thread_alive() -> bool:
    with USER_STREAM_LOCK:
        return bool(USER_STREAM_THREAD and USER_STREAM_THREAD.is_alive())


def ensure_binance_account_mode(mode: str) -> str:
    normalized = str(mode or "").lower().strip()
    if normalized not in {"binance_testnet_validate", "binance_testnet_place_order", "live_guarded"}:
        raise ValueError("Unsupported Binance account mode.")
    if normalized == "live_guarded":
        if not (ENABLE_BINANCE_LIVE and BINANCE_LIVE_API_KEY and BINANCE_LIVE_API_SECRET):
            raise ValueError("Binance live account sync requires ENABLE_BINANCE_LIVE=true and live API keys.")
    elif not (ENABLE_BINANCE_TESTNET and BINANCE_API_KEY and BINANCE_API_SECRET):
        raise ValueError("Binance testnet account sync requires ENABLE_BINANCE_TESTNET=true and testnet API keys.")
    return normalized


def binance_key_request_for_mode(method: str, path: str, params: dict[str, Any], mode: str) -> Any:
    normalized = ensure_binance_account_mode(mode)
    creds = binance_credentials_for_mode(normalized)
    query = urlencode(params)
    url = f"{creds['base_url']}{path}" + (f"?{query}" if query else "")
    request = Request(
        url,
        data=b"" if method.upper() in {"POST", "PUT", "DELETE"} else None,
        headers={
            "X-MBX-APIKEY": creds["api_key"],
            "User-Agent": "crypto-contract-ai-trader/0.1",
        },
        method=method.upper(),
    )
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        raw = response.read().decode(response.headers.get_content_charset() or "utf-8")
        return json.loads(raw) if raw.strip() else {}


def binance_user_stream_status() -> dict[str, Any]:
    mode = get_setting("binance_user_stream_mode", "")
    listen_key = get_setting("binance_user_stream_listen_key", "")
    return {
        "mode": mode,
        "mode_label": mode_label(mode) if mode else "-",
        "status": get_setting("binance_user_stream_status", "stopped"),
        "listen_key_present": bool(listen_key),
        "listen_key_fingerprint": mask_secret(listen_key),
        "started_at": get_setting("binance_user_stream_started_at", ""),
        "keepalive_at": get_setting("binance_user_stream_keepalive_at", ""),
        "expires_at": get_setting("binance_user_stream_expires_at", ""),
        "last_error": get_setting("binance_user_stream_last_error", ""),
        "websocket_base": binance_ws_base_for_mode(mode) if mode else "",
        "websocket_connected": get_setting("binance_user_stream_connected", "false") == "true",
        "consumer_running": current_user_stream_thread_alive(),
        "dependency_ready": user_stream_dependency_ready(),
        "consumer_started_at": get_setting("binance_user_stream_consumer_started_at", ""),
        "last_event_at": get_setting("binance_user_stream_last_event_at", ""),
        "last_event_type": get_setting("binance_user_stream_last_event_type", ""),
        "event_count": int(float(get_setting("binance_user_stream_event_count", "0") or "0")),
        "note": "已接入 Binance user data WebSocket 消费线程；事件会写入审计表并驱动 OMS 状态更新。",
    }


def start_binance_user_stream(mode: str) -> dict[str, Any]:
    normalized = ensure_binance_account_mode(mode)
    try:
        response = binance_key_request_for_mode("POST", "/fapi/v1/listenKey", {}, normalized)
        listen_key = str(response.get("listenKey") or "").strip()
        if not listen_key:
            raise RuntimeError("Binance did not return a listenKey.")
        now = utc_now()
        set_setting("binance_user_stream_mode", normalized)
        set_setting("binance_user_stream_listen_key", listen_key)
        set_setting("binance_user_stream_status", "active")
        set_setting("binance_user_stream_started_at", now)
        set_setting("binance_user_stream_keepalive_at", now)
        set_setting("binance_user_stream_expires_at", seconds_from_now(55 * 60))
        set_setting("binance_user_stream_last_error", "")
        set_setting("binance_user_stream_connected", "false")
        start_binance_user_stream_consumer()
    except Exception as exc:
        set_setting("binance_user_stream_status", "error")
        set_setting("binance_user_stream_last_error", f"{exc.__class__.__name__}: {exc}")
        raise
    return binance_user_stream_status()


def keepalive_binance_user_stream() -> dict[str, Any]:
    mode = get_setting("binance_user_stream_mode", "")
    listen_key = get_setting("binance_user_stream_listen_key", "")
    if not mode or not listen_key:
        raise ValueError("No active Binance user stream listenKey is stored.")
    try:
        binance_key_request_for_mode("PUT", "/fapi/v1/listenKey", {"listenKey": listen_key}, mode)
        set_setting("binance_user_stream_status", "active")
        set_setting("binance_user_stream_keepalive_at", utc_now())
        set_setting("binance_user_stream_expires_at", seconds_from_now(55 * 60))
        set_setting("binance_user_stream_last_error", "")
        if not current_user_stream_thread_alive():
            start_binance_user_stream_consumer()
    except Exception as exc:
        set_setting("binance_user_stream_status", "error")
        set_setting("binance_user_stream_last_error", f"{exc.__class__.__name__}: {exc}")
        raise
    return binance_user_stream_status()


def close_binance_user_stream() -> dict[str, Any]:
    mode = get_setting("binance_user_stream_mode", "")
    listen_key = get_setting("binance_user_stream_listen_key", "")
    if mode and listen_key:
        try:
            binance_key_request_for_mode("DELETE", "/fapi/v1/listenKey", {"listenKey": listen_key}, mode)
        except Exception as exc:
            set_setting("binance_user_stream_last_error", f"{exc.__class__.__name__}: {exc}")
            raise
    set_setting("binance_user_stream_mode", "")
    set_setting("binance_user_stream_listen_key", "")
    set_setting("binance_user_stream_status", "stopped")
    set_setting("binance_user_stream_connected", "false")
    set_setting("binance_user_stream_started_at", "")
    set_setting("binance_user_stream_keepalive_at", "")
    set_setting("binance_user_stream_expires_at", "")
    stop_binance_user_stream_consumer()
    return binance_user_stream_status()


def save_exchange_stream_event(
    mode: str,
    payload: dict[str, Any],
    processed: bool,
    note: str = "",
) -> dict[str, Any]:
    event_type = str(payload.get("e") or "UNKNOWN")
    order_payload = payload.get("o") if isinstance(payload.get("o"), dict) else {}
    event = {
        "id": f"XEVT-{str(uuid.uuid4())[:12].upper()}",
        "ts": utc_now(),
        "mode": mode,
        "event_type": event_type,
        "event_time": payload.get("E"),
        "transaction_time": payload.get("T"),
        "symbol": order_payload.get("s") or payload.get("s"),
        "client_order_id": order_payload.get("c") or payload.get("c"),
        "venue_order_id": str(order_payload.get("i") or payload.get("i") or ""),
        "payload": payload,
        "processed": "true" if processed else "false",
        "note": note,
    }
    with DB_LOCK, connect() as conn:
        conn.execute(
            """
            INSERT INTO exchange_stream_events(
                id, ts, mode, event_type, event_time, transaction_time, symbol,
                client_order_id, venue_order_id, payload, processed, note
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["id"],
                event["ts"],
                event["mode"],
                event["event_type"],
                event["event_time"],
                event["transaction_time"],
                event["symbol"],
                event["client_order_id"],
                event["venue_order_id"],
                json.dumps(event["payload"]),
                event["processed"],
                event["note"],
            ),
        )
        conn.commit()
    set_setting("binance_user_stream_last_event_at", event["ts"])
    set_setting("binance_user_stream_last_event_type", event_type)
    current_count = int(float(get_setting("binance_user_stream_event_count", "0") or "0"))
    set_setting("binance_user_stream_event_count", str(current_count + 1))
    return event


def get_exchange_stream_events(limit: int = 25) -> list[dict[str, Any]]:
    with DB_LOCK, connect() as conn:
        rows = conn.execute(
            "SELECT * FROM exchange_stream_events ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
    events: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["payload"] = json.loads(item.get("payload") or "{}")
        item["processed"] = item.get("processed") == "true"
        events.append(item)
    return events


def exchange_stream_event_summary() -> dict[str, Any]:
    events = get_exchange_stream_events(limit=100)
    counts: dict[str, int] = {}
    for event in events:
        counts[event["event_type"]] = counts.get(event["event_type"], 0) + 1
    latest = events[0] if events else {}
    return {
        "recent_count": len(events),
        "counts": counts,
        "latest_event_type": latest.get("event_type", ""),
        "latest_event_at": latest.get("ts", ""),
    }


def status_from_private_order_event(mode: str, venue_status: str) -> str:
    prefix = "live" if mode == "live_guarded" else "testnet"
    status = str(venue_status or "UNKNOWN").upper()
    return {
        "FILLED": f"{prefix}_filled",
        "CANCELED": f"{prefix}_canceled",
        "EXPIRED": f"{prefix}_canceled",
        "EXPIRED_IN_MATCH": f"{prefix}_canceled",
        "REJECTED": f"{prefix}_canceled",
    }.get(status, f"{prefix}_submitted")


def handle_private_order_update(mode: str, event: dict[str, Any]) -> tuple[bool, str]:
    order_update = event.get("o") if isinstance(event.get("o"), dict) else {}
    client_order_id = str(order_update.get("c") or "").strip()
    if not client_order_id:
        return False, "ORDER_TRADE_UPDATE did not include client order id."
    local_order = get_order_by_client_order_id(client_order_id)
    if not local_order:
        return False, f"No local order matched clientOrderId={client_order_id}."
    venue_status = str(order_update.get("X") or "UNKNOWN").upper()
    venue_order_id = str(order_update.get("i") or local_order.get("venue_order_id") or "")
    terminal = venue_status in {"FILLED", "CANCELED", "EXPIRED", "EXPIRED_IN_MATCH", "REJECTED"}
    updated = update_order_state(
        local_order["id"],
        status=status_from_private_order_event(mode, venue_status),
        venue_order_id=venue_order_id or None,
        venue_status=venue_status,
        reconcile_status="reconciled" if terminal else "needs_reconcile",
        reconcile_note=(
            f"Binance private stream ORDER_TRADE_UPDATE: execution={order_update.get('x', '-')}; "
            f"status={venue_status}; filled={order_update.get('z', '-')}; "
            f"avgPrice={order_update.get('ap', '-')}; realizedPnl={order_update.get('rp', '-')}."
        ),
        reason="binance_private_order_update",
        payload={"event": event},
    )
    return True, f"Updated local order {updated['id']} from private stream."


def handle_private_account_update(mode: str, event: dict[str, Any]) -> tuple[bool, str]:
    account_update = event.get("a") if isinstance(event.get("a"), dict) else {}
    balances = account_update.get("B") or []
    positions = account_update.get("P") or []
    summary = {
        "asset": "USDT",
        "wallet_balance_usdt": 0.0,
        "available_balance_usdt": 0.0,
        "unrealized_pnl_usdt": sum(safe_float(position.get("up"), 0.0) for position in positions),
        "open_position_count": sum(1 for position in positions if abs(safe_float(position.get("pa"), 0.0)) > 0),
        "reason": account_update.get("m") or "",
        "synced_at": utc_now(),
    }
    for balance in balances:
        if balance.get("a") == "USDT":
            summary["wallet_balance_usdt"] = safe_float(balance.get("wb"), 0.0)
            summary["available_balance_usdt"] = safe_float(balance.get("cw"), 0.0)
    snapshot = {
        "id": f"EXSTR-{str(uuid.uuid4())[:10].upper()}",
        "ts": utc_now(),
        "mode": mode,
        "account": account_update,
        "positions": positions,
        "summary": summary,
    }
    with DB_LOCK, connect() as conn:
        conn.execute(
            """
            INSERT INTO exchange_account_snapshots(id, ts, mode, account, positions, summary)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot["id"],
                snapshot["ts"],
                snapshot["mode"],
                json.dumps(snapshot["account"]),
                json.dumps(snapshot["positions"]),
                json.dumps(snapshot["summary"]),
            ),
        )
        conn.commit()
    return True, f"Saved ACCOUNT_UPDATE snapshot {snapshot['id']}."


def handle_binance_user_stream_event(mode: str, event: dict[str, Any]) -> dict[str, Any]:
    event_type = str(event.get("e") or "UNKNOWN")
    processed = False
    note = "Stored event without state mutation."
    if event_type == "ORDER_TRADE_UPDATE":
        processed, note = handle_private_order_update(mode, event)
    elif event_type == "ACCOUNT_UPDATE":
        processed, note = handle_private_account_update(mode, event)
    elif event_type == "listenKeyExpired":
        set_setting("binance_user_stream_status", "expired")
        set_setting("binance_user_stream_connected", "false")
        note = "listenKey expired; recreate the user stream before relying on private events."
    return save_exchange_stream_event(mode, event, processed=processed, note=note)


async def binance_user_stream_consumer_loop(mode: str, listen_key: str) -> None:
    import websockets

    url = build_binance_user_stream_url(mode, listen_key)
    backoff_seconds = 1.0
    while not USER_STREAM_STOP.is_set():
        try:
            set_setting("binance_user_stream_status", "connecting")
            set_setting("binance_user_stream_connected", "false")
            async with websockets.connect(url, ping_interval=20, ping_timeout=20, close_timeout=5) as websocket:
                set_setting("binance_user_stream_status", "active")
                set_setting("binance_user_stream_connected", "true")
                set_setting("binance_user_stream_last_error", "")
                backoff_seconds = 1.0
                while not USER_STREAM_STOP.is_set():
                    try:
                        raw_message = await asyncio.wait_for(websocket.recv(), timeout=5)
                    except asyncio.TimeoutError:
                        continue
                    event = json.loads(raw_message)
                    if isinstance(event, dict):
                        handle_binance_user_stream_event(mode, event)
        except Exception as exc:
            set_setting("binance_user_stream_connected", "false")
            if USER_STREAM_STOP.is_set():
                break
            set_setting("binance_user_stream_status", "reconnecting")
            set_setting("binance_user_stream_last_error", f"{exc.__class__.__name__}: {exc}")
            await asyncio.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, 30)
    set_setting("binance_user_stream_connected", "false")
    if get_setting("binance_user_stream_status", "") != "stopped":
        set_setting("binance_user_stream_status", "stopped")


def run_binance_user_stream_consumer(mode: str, listen_key: str) -> None:
    try:
        asyncio.run(binance_user_stream_consumer_loop(mode, listen_key))
    except Exception as exc:
        set_setting("binance_user_stream_connected", "false")
        set_setting("binance_user_stream_status", "error")
        set_setting("binance_user_stream_last_error", f"{exc.__class__.__name__}: {exc}")


def start_binance_user_stream_consumer() -> dict[str, Any]:
    global USER_STREAM_THREAD
    mode = get_setting("binance_user_stream_mode", "")
    listen_key = get_setting("binance_user_stream_listen_key", "")
    if not mode or not listen_key:
        raise ValueError("No Binance user stream listenKey is available.")
    if not user_stream_dependency_ready():
        set_setting("binance_user_stream_connected", "false")
        set_setting("binance_user_stream_last_error", "Python dependency `websockets` is not installed.")
        return binance_user_stream_status()
    with USER_STREAM_LOCK:
        if USER_STREAM_THREAD and USER_STREAM_THREAD.is_alive():
            return binance_user_stream_status()
        USER_STREAM_STOP.clear()
        USER_STREAM_THREAD = threading.Thread(
            target=run_binance_user_stream_consumer,
            args=(mode, listen_key),
            daemon=True,
        )
        USER_STREAM_THREAD.start()
    set_setting("binance_user_stream_consumer_started_at", utc_now())
    return binance_user_stream_status()


def stop_binance_user_stream_consumer() -> None:
    USER_STREAM_STOP.set()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def summarize_binance_account(payload: dict[str, Any]) -> dict[str, Any]:
    positions = payload.get("positions") or []
    nonzero_positions = [
        item
        for item in positions
        if abs(safe_float(item.get("positionAmt"), 0.0)) > 0
    ]
    return {
        "asset": "USDT",
        "wallet_balance_usdt": float(payload.get("totalWalletBalance") or 0),
        "margin_balance_usdt": float(payload.get("totalMarginBalance") or 0),
        "available_balance_usdt": float(payload.get("availableBalance") or 0),
        "unrealized_pnl_usdt": float(payload.get("totalUnrealizedProfit") or 0),
        "maint_margin_usdt": float(payload.get("totalMaintMargin") or 0),
        "open_position_count": len(nonzero_positions),
        "synced_at": utc_now(),
    }


def save_exchange_account_snapshot(mode: str, payload: dict[str, Any]) -> dict[str, Any]:
    summary = summarize_binance_account(payload)
    nonzero_positions = [
        item
        for item in payload.get("positions", [])
        if abs(safe_float(item.get("positionAmt"), 0.0)) > 0
    ]
    snapshot = {
        "id": f"EXSNAP-{str(uuid.uuid4())[:10].upper()}",
        "ts": utc_now(),
        "mode": mode,
        "account": payload,
        "positions": nonzero_positions,
        "summary": summary,
    }
    with DB_LOCK, connect() as conn:
        conn.execute(
            """
            INSERT INTO exchange_account_snapshots(id, ts, mode, account, positions, summary)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot["id"],
                snapshot["ts"],
                snapshot["mode"],
                json.dumps(snapshot["account"]),
                json.dumps(snapshot["positions"]),
                json.dumps(snapshot["summary"]),
            ),
        )
        conn.commit()
    return snapshot


def fetch_binance_account_snapshot(mode: str) -> dict[str, Any]:
    normalized = ensure_binance_account_mode(mode)
    try:
        return signed_binance_request_for_mode("GET", "/fapi/v3/account", {}, normalized)
    except Exception:
        return signed_binance_request_for_mode("GET", "/fapi/v2/account", {}, normalized)


def coerce_binance_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def fetch_binance_position_mode(mode: str) -> dict[str, Any]:
    normalized = ensure_binance_account_mode(mode)
    payload = signed_binance_request_for_mode("GET", "/fapi/v1/positionSide/dual", {}, normalized)
    dual_side = coerce_binance_bool(payload.get("dualSidePosition"))
    return {
        "mode": normalized,
        "dual_side_position": dual_side,
        "position_mode": "HEDGE" if dual_side else "ONE_WAY",
        "raw": payload,
        "synced_at": utc_now(),
    }


def sync_exchange_account_snapshot(mode: str) -> dict[str, Any]:
    normalized = ensure_binance_account_mode(mode)
    payload = fetch_binance_account_snapshot(normalized)
    snapshot = save_exchange_account_snapshot(normalized, payload)
    return {
        "id": snapshot["id"],
        "ts": snapshot["ts"],
        "mode": snapshot["mode"],
        "summary": snapshot["summary"],
        "positions": snapshot["positions"],
    }


def get_exchange_account_snapshots(limit: int = 5) -> list[dict[str, Any]]:
    with DB_LOCK, connect() as conn:
        rows = conn.execute(
            "SELECT * FROM exchange_account_snapshots ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
    snapshots: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["account"] = json.loads(item.get("account") or "{}")
        item["positions"] = json.loads(item.get("positions") or "[]")
        item["summary"] = json.loads(item.get("summary") or "{}")
        snapshots.append(item)
    return snapshots


def latest_exchange_account_snapshot(mode: str, limit: int = 20) -> dict[str, Any] | None:
    normalized = str(mode or "").lower().strip()
    for snapshot in get_exchange_account_snapshots(limit=limit):
        if snapshot.get("mode") == normalized:
            return snapshot
    return None


def binance_recovery_modes() -> list[str]:
    modes: list[str] = []
    if ENABLE_BINANCE_TESTNET and BINANCE_API_KEY and BINANCE_API_SECRET:
        modes.append("binance_testnet_place_order" if BINANCE_PLACE_TESTNET_ORDERS else "binance_testnet_validate")
    if ENABLE_BINANCE_LIVE and BINANCE_LIVE_API_KEY and BINANCE_LIVE_API_SECRET:
        modes.append("live_guarded")
    return modes


def recover_exchange_state(trigger: str = "manual") -> dict[str, Any]:
    started_at = utc_now()
    report: dict[str, Any] = {
        "trigger": trigger,
        "started_at": started_at,
        "completed_at": "",
        "orders": {},
        "account_snapshots": [],
        "position_modes": [],
        "user_stream": binance_user_stream_status(),
        "warnings": [],
        "errors": [],
    }
    try:
        report["orders"] = reconcile_recent_orders(limit=100)
    except Exception as exc:
        report["errors"].append(f"OMS reconcile failed: {exc.__class__.__name__}: {exc}")

    for mode in binance_recovery_modes():
        try:
            report["account_snapshots"].append(sync_exchange_account_snapshot(mode))
        except Exception as exc:
            report["warnings"].append(
                f"{mode_label(mode)} account snapshot failed: {exc.__class__.__name__}: {exc}"
            )
        try:
            report["position_modes"].append(fetch_binance_position_mode(mode))
        except Exception as exc:
            report["warnings"].append(
                f"{mode_label(mode)} position mode check failed: {exc.__class__.__name__}: {exc}"
            )

    if get_setting("binance_user_stream_listen_key", ""):
        try:
            report["user_stream"] = keepalive_binance_user_stream()
            if not current_user_stream_thread_alive():
                report["user_stream"] = start_binance_user_stream_consumer()
        except Exception as exc:
            report["warnings"].append(f"Binance user stream keepalive failed: {exc.__class__.__name__}: {exc}")
            report["user_stream"] = binance_user_stream_status()

    report["completed_at"] = utc_now()
    set_setting("exchange_recovery_last_at", report["completed_at"])
    set_setting("exchange_recovery_last_report", json.dumps(report, ensure_ascii=False))
    return report


def exchange_recovery_status() -> dict[str, Any]:
    raw_report = get_setting("exchange_recovery_last_report", "{}")
    try:
        last_report = json.loads(raw_report or "{}")
    except json.JSONDecodeError:
        last_report = {"error": raw_report}
    return {
        "last_at": get_setting("exchange_recovery_last_at", ""),
        "last_report": last_report,
        "snapshots": get_exchange_account_snapshots(limit=5),
        "user_stream": binance_user_stream_status(),
        "stream_events": get_exchange_stream_events(limit=20),
        "stream_summary": exchange_stream_event_summary(),
    }


def compact_exchange_recovery_status(recovery: dict[str, Any] | None = None) -> dict[str, Any]:
    source = recovery if recovery is not None else exchange_recovery_status()
    report = source.get("last_report") or {}
    orders = report.get("orders") if isinstance(report, dict) else {}
    if isinstance(orders, dict):
        compact_orders = {
            key: value
            for key, value in orders.items()
            if key != "orders"
        }
    else:
        compact_orders = {}
    compact_report = {
        "trigger": report.get("trigger") if isinstance(report, dict) else None,
        "started_at": report.get("started_at") if isinstance(report, dict) else None,
        "completed_at": report.get("completed_at") if isinstance(report, dict) else None,
        "orders": compact_orders,
        "warnings": (report.get("warnings") or [])[:8] if isinstance(report, dict) else [],
        "errors": (report.get("errors") or [])[:8] if isinstance(report, dict) else [],
        "position_modes": (report.get("position_modes") or [])[:8] if isinstance(report, dict) else [],
    }
    stream_events = source.get("stream_events")
    if isinstance(stream_events, dict):
        events = stream_events.get("events") or []
    else:
        events = stream_events or []
    compact_events = [
        {
            key: event.get(key)
            for key in ("id", "ts", "event_type", "processed", "error")
        }
        for event in events[:5]
        if isinstance(event, dict)
    ]
    return {
        "last_at": source.get("last_at"),
        "last_report": compact_report,
        "snapshots": [
            {
                key: snapshot.get(key)
                for key in ("id", "ts", "mode", "summary")
            }
            for snapshot in (source.get("snapshots") or [])[:3]
            if isinstance(snapshot, dict)
        ],
        "user_stream": source.get("user_stream"),
        "stream_events": compact_events,
        "stream_summary": source.get("stream_summary"),
    }


def prepare_order_payload(
    run_id: str,
    intent: dict[str, Any],
    prefix: str,
    equity_usdt: float | None = None,
    account_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    order_id = f"{prefix}-{str(uuid.uuid4())[:8].upper()}"
    now = utc_now()
    sizing_equity = float(equity_usdt if equity_usdt is not None else ACCOUNT_EQUITY_USDT)
    quantity = round(
        (sizing_equity * intent["position_pct"] * intent["leverage"])
        / intent["entry_price"],
        6,
    )
    order = {
        "id": order_id,
        "run_id": run_id,
        "symbol": intent["symbol"],
        "side": intent["side"],
        "order_type": "LIMIT",
        "quantity": quantity,
        "leverage": intent["leverage"],
        "entry_price": intent["entry_price"],
        "stop_loss": intent["stop_loss"],
        "take_profit": intent["take_profit"],
        "status": "prepared",
        "client_order_id": order_id,
        "venue_order_id": None,
        "venue_status": "PREPARED",
        "reconcile_status": "unchecked",
        "reconcile_note": "",
        "last_reconciled_at": None,
        "created_at": now,
        "updated_at": now,
        "parent_order_id": None,
        "protection_kind": None,
        "sizing": {
            "equity_usdt": round(sizing_equity, 2),
            "position_pct": intent["position_pct"],
            "leverage": intent["leverage"],
            "notional_usdt": round(sizing_equity * intent["position_pct"] * intent["leverage"], 2),
            "account_source": (account_state or {}).get("source", "configured_local"),
            "account_snapshot_id": (account_state or {}).get("snapshot_id", ""),
            "free_margin_usdt": (account_state or {}).get("free_margin_usdt"),
        },
    }
    return order


def persist_order(order: dict[str, Any]) -> dict[str, Any]:
    order.setdefault("parent_order_id", None)
    order.setdefault("protection_kind", None)
    with DB_LOCK, connect() as conn:
        conn.execute(
            """
            INSERT INTO orders(
                id, run_id, symbol, side, order_type, quantity, leverage,
                entry_price, stop_loss, take_profit, status, created_at,
                client_order_id, venue_order_id, venue_status, reconcile_status,
                reconcile_note, last_reconciled_at, updated_at, parent_order_id,
                protection_kind
            )
            VALUES(
                :id, :run_id, :symbol, :side, :order_type, :quantity, :leverage,
                :entry_price, :stop_loss, :take_profit, :status, :created_at,
                :client_order_id, :venue_order_id, :venue_status, :reconcile_status,
                :reconcile_note, :last_reconciled_at, :updated_at, :parent_order_id,
                :protection_kind
            )
            """,
            order,
        )
        conn.commit()
    insert_order_transition(
        order["id"],
        None,
        order["status"],
        "order_created",
        {
            "client_order_id": order.get("client_order_id"),
            "venue_status": order.get("venue_status"),
            "reconcile_status": order.get("reconcile_status"),
            "binance_filter_evidence": order.get("binance_filter_evidence"),
            "margin_type_sync": order.get("margin_type_sync"),
            "leverage_sync": order.get("leverage_sync"),
            "sizing": order.get("sizing"),
            "parent_order_id": order.get("parent_order_id"),
            "protection_kind": order.get("protection_kind"),
            "pre_submit_validation": order.get("pre_submit_validation"),
            "market_freshness": order.get("market_freshness"),
            "order_conflict_check": order.get("order_conflict_check"),
        },
    )
    return order


def open_paper_position(run_id: str, order: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    position = {
        "id": f"POS-{str(uuid.uuid4())[:8].upper()}",
        "run_id": run_id,
        "order_id": order["id"],
        "symbol": order["symbol"],
        "side": order["side"],
        "quantity": order["quantity"],
        "leverage": order["leverage"],
        "entry_price": order["entry_price"],
        "mark_price": order["entry_price"],
        "stop_loss": order["stop_loss"],
        "take_profit": order["take_profit"],
        "status": "open",
        "opened_at": now,
        "updated_at": now,
        "closed_at": None,
        "exit_price": None,
        "realized_pnl": 0,
    }
    with DB_LOCK, connect() as conn:
        conn.execute(
            """
            INSERT INTO positions(
                id, run_id, order_id, symbol, side, quantity, leverage,
                entry_price, mark_price, stop_loss, take_profit, status,
                opened_at, updated_at, closed_at, exit_price, realized_pnl
            )
            VALUES(
                :id, :run_id, :order_id, :symbol, :side, :quantity, :leverage,
                :entry_price, :mark_price, :stop_loss, :take_profit, :status,
                :opened_at, :updated_at, :closed_at, :exit_price, :realized_pnl
            )
            """,
            position,
        )
        conn.commit()
    return position


def close_paper_position(position_id: str, reason: str = "manual_close") -> dict[str, Any]:
    position = get_position(position_id)
    if not position:
        raise ValueError(f"Position {position_id} was not found")
    if position["status"] != "open":
        raise ValueError(f"Position {position_id} is already {position['status']}")

    marks = latest_market_marks()
    marked = mark_position(position, marks.get(position["symbol"]))
    now = utc_now()
    realized_pnl = float(marked["unrealized_pnl_usdt"])
    with DB_LOCK, connect() as conn:
        conn.execute(
            """
            UPDATE positions
            SET status = 'closed',
                mark_price = ?,
                updated_at = ?,
                closed_at = ?,
                exit_price = ?,
                realized_pnl = ?
            WHERE id = ?
            """,
            (
                marked["mark_price"],
                now,
                now,
                marked["mark_price"],
                realized_pnl,
                position_id,
            ),
        )
        conn.commit()
    closed = {
        **marked,
        "status": "closed",
        "updated_at": now,
        "closed_at": now,
        "exit_price": marked["mark_price"],
        "realized_pnl": round(realized_pnl, 2),
        "close_reason": reason,
    }
    return closed


def execute_order(run_id: str, intent: dict[str, Any], risk: dict[str, Any], mode: str) -> dict[str, Any] | None:
    if intent["side"] == "HOLD" or risk["status"] == "rejected":
        return None
    order_conflict_check = assert_no_stateful_order_conflicts(mode, intent["symbol"])
    order_account_state = risk.get("account") or account_state_for_mode(mode)
    account_freshness = assert_fresh_execution_account_state(mode, order_account_state)
    market_freshness = assert_fresh_execution_market_snapshot(mode, risk.get("market"))
    order_equity = float(order_account_state.get("equity_usdt") or ACCOUNT_EQUITY_USDT)

    if mode == "paper":
        order = prepare_order_payload(run_id, intent, "PAPER", order_equity, order_account_state)
        order["account_freshness"] = account_freshness
        order["market_freshness"] = market_freshness
        order["order_conflict_check"] = order_conflict_check
        order["status"] = "paper_filled"
        order["venue_status"] = "PAPER_FILLED"
        persist_order(order)
        order["position"] = open_paper_position(run_id, order)
        reconciled = reconcile_order(order["id"])
        order.update(reconciled)
        return order

    if mode == "binance_testnet_validate":
        order = prepare_order_payload(run_id, intent, "TEST", order_equity, order_account_state)
        order["account_freshness"] = account_freshness
        order["market_freshness"] = market_freshness
        order["order_conflict_check"] = order_conflict_check
        params = binance_order_params(order, mode)
        validation = validate_binance_order_bundle(order, params, mode)
        order["status"] = "testnet_validated"
        order["venue_status"] = "ORDER_TEST_ACCEPTED"
        order["exchange_response"] = validation
        persist_order(order)
        reconciled = reconcile_order(order["id"])
        reconciled["exchange_response"] = order["exchange_response"]
        return reconciled

    if mode == "binance_testnet_place_order":
        if not BINANCE_PLACE_TESTNET_ORDERS:
            raise ValueError("BINANCE_PLACE_TESTNET_ORDERS must be true before placing real testnet orders.")
        order = prepare_order_payload(run_id, intent, "TESTLIVE", order_equity, order_account_state)
        order["account_freshness"] = account_freshness
        order["market_freshness"] = market_freshness
        order["order_conflict_check"] = order_conflict_check
        params = binance_order_params(order, mode)
        order["margin_type_sync"] = ensure_binance_margin_type(order, mode)
        order["leverage_sync"] = ensure_binance_leverage(order, mode)
        order["pre_submit_validation"] = validate_binance_order_bundle(order, params, mode)
        try:
            response = signed_binance_request("POST", "/fapi/v1/order", params)
            venue_status = str(response.get("status") or "NEW").upper()
            order["status"] = "testnet_submitted"
            order["venue_order_id"] = str(response.get("orderId") or "")
            order["venue_status"] = venue_status
            order["reconcile_status"] = "needs_reconcile"
            order["reconcile_note"] = (
                f"Binance testnet order submitted; status={venue_status}; "
                f"orderId={order['venue_order_id'] or '-'}."
            )
            order["exchange_response"] = response
            persist_order(order)
            try:
                protection_orders = submit_binance_protection_orders(order, mode)
            except Exception as exc:
                handle_binance_protection_submit_failure(order, exc, mode)
                raise ProtectionFailureGuarded(f"Binance testnet protection guard handled {order['id']}") from exc
                raise_alert(
                    f"protection.submit_failed.{order['id']}",
                    "critical",
                    "OMS",
                    "测试网保护单提交失败",
                    f"父订单 {order['id']} 已提交，但止损/止盈保护单提交失败：{exc.__class__.__name__}: {exc}",
                    {"order": order, "error": str(exc), "mode": mode},
                )
                update_order_state(
                    order["id"],
                    reconcile_status="needs_reconcile",
                    reconcile_note=f"Entry submitted but protection orders failed: {exc.__class__.__name__}: {exc}",
                    reason="binance_protection_submit_failed",
                    payload={"error": str(exc)},
                )
                raise
            reconciled = reconcile_order(order["id"])
            reconciled["exchange_response"] = response
            reconciled["pre_submit_validation"] = order.get("pre_submit_validation")
            reconciled["protection_orders"] = protection_orders
            return reconciled
        except ProtectionFailureGuarded:
            raise
        except Exception as exc:
            order["status"] = "pending_reconcile"
            order["venue_status"] = "UNKNOWN"
            order["reconcile_status"] = "needs_reconcile"
            order["reconcile_note"] = (
                "Binance testnet order submit returned unknown state; "
                f"reconcile by clientOrderId before any retry. {exc.__class__.__name__}: {exc}"
            )
            if get_order(order["id"]):
                update_order_state(
                    order["id"],
                    status="pending_reconcile",
                    venue_status="UNKNOWN",
                    reconcile_status="needs_reconcile",
                    reconcile_note=order["reconcile_note"],
                    reason="binance_testnet_submit_exception",
                    payload={"error": str(exc)},
                )
            else:
                persist_order(order)
            return reconcile_order(order["id"])

    if mode == "live_guarded":
        if not (
            ENABLE_BINANCE_LIVE
            and BINANCE_LIVE_API_KEY
            and BINANCE_LIVE_API_SECRET
            and BINANCE_PLACE_LIVE_ORDERS
            and LIVE_TRADING_CONFIRMATION == "I_UNDERSTAND_LIVE_RISK"
        ):
            raise ValueError("Live guarded mode requires explicit live enablement, live keys, live order flag, and confirmation text.")
        go_live_gate = assert_go_live_gate_allows_live_order()
        order = prepare_order_payload(run_id, intent, "LIVE", order_equity, order_account_state)
        order["account_freshness"] = account_freshness
        order["market_freshness"] = market_freshness
        order["order_conflict_check"] = order_conflict_check
        order["go_live_gate"] = go_live_gate
        params = binance_order_params(order, mode)
        order["margin_type_sync"] = ensure_binance_margin_type(order, mode)
        order["leverage_sync"] = ensure_binance_leverage(order, mode)
        order["pre_submit_validation"] = validate_binance_order_bundle(order, params, mode)
        try:
            order["live_arming_after_consume"] = consume_live_arming_order(order["id"])
            response = signed_binance_request_for_mode("POST", "/fapi/v1/order", params, "live_guarded")
            venue_status = str(response.get("status") or "NEW").upper()
            order["status"] = "live_submitted"
            order["venue_order_id"] = str(response.get("orderId") or "")
            order["venue_status"] = venue_status
            order["reconcile_status"] = "needs_reconcile"
            order["reconcile_note"] = (
                f"Binance live order submitted; status={venue_status}; "
                f"orderId={order['venue_order_id'] or '-'}."
            )
            order["exchange_response"] = response
            persist_order(order)
            try:
                protection_orders = submit_binance_protection_orders(order, mode)
            except Exception as exc:
                handle_binance_protection_submit_failure(order, exc, mode)
                raise ProtectionFailureGuarded(f"Binance live protection guard handled {order['id']}") from exc
                raise_alert(
                    f"protection.submit_failed.{order['id']}",
                    "critical",
                    "OMS",
                    "实盘保护单提交失败",
                    f"父订单 {order['id']} 已提交，但止损/止盈保护单提交失败：{exc.__class__.__name__}: {exc}",
                    {"order": order, "error": str(exc), "mode": mode},
                )
                update_order_state(
                    order["id"],
                    reconcile_status="needs_reconcile",
                    reconcile_note=f"Entry submitted but protection orders failed: {exc.__class__.__name__}: {exc}",
                    reason="binance_protection_submit_failed",
                    payload={"error": str(exc)},
                )
                raise
            reconciled = reconcile_order(order["id"])
            reconciled["exchange_response"] = response
            reconciled["pre_submit_validation"] = order.get("pre_submit_validation")
            reconciled["protection_orders"] = protection_orders
            return reconciled
        except ProtectionFailureGuarded:
            raise
        except Exception as exc:
            order["status"] = "pending_reconcile"
            order["venue_status"] = "UNKNOWN"
            order["reconcile_status"] = "needs_reconcile"
            order["reconcile_note"] = (
                "Binance live order submit returned unknown state; "
                f"reconcile by clientOrderId before any retry. {exc.__class__.__name__}: {exc}"
            )
            if get_order(order["id"]):
                update_order_state(
                    order["id"],
                    status="pending_reconcile",
                    venue_status="UNKNOWN",
                    reconcile_status="needs_reconcile",
                    reconcile_note=order["reconcile_note"],
                    reason="binance_live_submit_exception",
                    payload={"error": str(exc)},
                )
            else:
                persist_order(order)
            return reconcile_order(order["id"])

    raise ValueError(f"Unsupported execution mode: {mode}")


def sleep_step(seconds: float = 1.0) -> None:
    time.sleep(seconds)


def run_workflow(run_id: str) -> None:
    with RUN_LOCK:
        ACTIVE_RUNS.add(run_id)
    run = get_run(run_id)
    if not run:
        return
    symbol = run["symbol"]
    mode = run["mode"]
    try:
        update_run(run_id, status="running")
        insert_event(
            run_id,
            "system",
            "Orchestrator",
            "运行已启动",
            f"开始为 {symbol} 执行 {mode_label(mode)} 工作流。",
            {"mode": mode, "environment": "local", "ai": ai_status(), "exchange": exchange_status()},
        )
        sleep_step()

        snapshot = build_market_snapshot(symbol)
        source_note = (
            f"，来源为 {source_label(snapshot['data_source'])}"
            if not snapshot.get("fallback")
            else f"，在 {snapshot.get('source_error')} 后回退到本地合成数据"
        )
        insert_event(
            run_id,
            "data",
            "Market Data",
            "行情快照已采集",
            "已采集标记价格、指数价格、资金费率、持仓量、多空比和盘口深度不平衡"
            f"{source_note}。",
            snapshot,
        )
        sleep_step()

        score = score_market(snapshot)
        insert_event(
            run_id,
            "agent",
            "Market Analyst",
            "技术面读取完成",
            (
                f"基于 {source_label(snapshot['data_source'])} 数据得到综合评分 {score}。"
                f"价格 24h 变化 {snapshot['change_24h_pct']}%，"
                f"持仓量变化 {snapshot['open_interest_change_pct']}%，"
                f"盘口深度不平衡 {snapshot['depth_imbalance']}。"
            ),
            {"score": score},
        )
        sleep_step()

        sentiment_bias = "偏多" if snapshot["long_short_ratio"] > 1.08 else "偏空" if snapshot["long_short_ratio"] < 0.92 else "中性"
        insert_event(
            run_id,
            "agent",
            "Sentiment Analyst",
            "持仓与情绪已汇总",
            (
                f"多空比为 {snapshot['long_short_ratio']}，当前定位解读为 {sentiment_bias}。"
                "当 Binance 公共数据可用时会纳入交易所持仓数据；社媒数据仍属于后续计划。"
            ),
            {"sentiment_bias": sentiment_bias},
        )
        sleep_step()

        insert_event(
            run_id,
            "agent",
            "News Analyst",
            "宏观与事件过滤已应用",
            (
                "当前尚未启用实时新闻连接器。工作流会明确记录这个缺口，避免后续 AI 运行声称已经检查了无来源新闻。"
            ),
            {"live_news_enabled": False},
        )
        sleep_step()

        intent = build_trade_intent(snapshot)
        insert_event(
            run_id,
            "agent",
            "AI Decision Adapter",
            "交易意图适配完成",
            (
                f"决策提供方：{source_label(intent['provider'])} / {source_label(intent['model'])}。"
                f"{'回退原因：' + intent['fallback_reason'] if intent.get('fallback_reason') else '结构化交易意图已通过。'}"
            ),
            {
                "provider": intent["provider"],
                "model": intent["model"],
                "ai_enabled": intent["ai_enabled"],
                "fallback_reason": intent.get("fallback_reason"),
                "schema": "TradeIntent",
                "prompt_summary": intent.get("prompt_summary"),
            },
        )
        sleep_step()

        update_run(run_id, decision=intent["rationale"], final_action=intent["side"])
        insert_event(
            run_id,
            "agent",
            "Trader Agent",
            "交易意图已生成",
            (
                f"建议动作：{zh_side(intent['side'])} {intent['symbol']}，入场 {intent['entry_price']}，"
                f"杠杆 {intent['leverage']}x，止损 {intent['stop_loss']}，目标 {intent['take_profit']}。"
            ),
            intent,
        )
        sleep_step()

        risk = risk_check(intent, snapshot, mode)
        update_run(run_id, risk_status=risk["status"])
        insert_event(
            run_id,
            "risk",
            "Risk Engine",
            f"风控结果：{zh_status(risk['status'])}",
            "确定性风控规则已在任何订单动作前复核 AI 风格交易意图。",
            risk,
        )
        sleep_step()

        order = execute_order(run_id, intent, risk, mode)
        if order:
            actor = {
                "paper": "Paper Executor",
                "binance_testnet_validate": "Binance Testnet Validator",
                "binance_testnet_place_order": "Binance Testnet Executor",
                "live_guarded": "Binance Live Executor",
            }.get(mode, "Order Executor")
            insert_event(
                run_id,
                "order",
                actor,
                "订单边界已完成",
                (
                    f"已创建 {zh_side(order['side'])} {zh_status(order['status'])} 订单记录 {order['id']}，"
                    f"数量 {order['quantity']} {order['symbol']}"
                    f"{'，并打开持仓 ' + order['position']['id'] if order.get('position') else ''}。"
                ),
                order,
            )
            if order.get("position"):
                account_state = paper_account_state()
                insert_event(
                    run_id,
                    "account",
                    "Paper Position Ledger",
                    "持仓与账户已标记",
                    (
                        f"已打开 {zh_side(order['position']['side'])} 持仓 {order['position']['id']}，"
                        f"纸交易权益标记为 {account_state['account']['equity_usdt']} USDT。"
                    ),
                    {
                        "position": order["position"],
                        "account": account_state["account"],
                    },
                )
        else:
            insert_event(
                run_id,
                "order",
                "Order Executor",
                "未提交订单",
                "由于动作是观望或风控拒绝，本次工作流未产生订单。",
                {"action": intent["side"], "risk_status": risk["status"]},
            )
        update_run(run_id, status="completed")
        insert_event(
            run_id,
            "system",
            "Orchestrator",
            "运行已完成",
            "所有本地工作流步骤已完成，并写入审计日志。",
            {"status": "completed"},
        )
    except Exception as exc:
        update_run(run_id, status="failed")
        insert_event(
            run_id,
            "error",
            "Orchestrator",
            "运行失败",
            str(exc),
            {"error_type": exc.__class__.__name__},
        )
    finally:
        with RUN_LOCK:
            ACTIVE_RUNS.discard(run_id)


def final_live_readiness(require_armed: bool = True, require_ai_operator: bool = True) -> dict[str, Any]:
    report = go_live_report()
    verdict = report.get("verdict") or {}
    gate = report.get("go_live_gate") or {}
    attestation = report.get("live_attestation") or {}
    operator = report.get("ai_operator") or {}
    checklist = report.get("checklist") or []
    failures: list[str] = []

    if report.get("app_env") != "server":
        failures.append("APP_ENV must be server.")
    if report.get("exchange_mode") != "live_guarded":
        failures.append("EXCHANGE_MODE must be live_guarded.")
    if not gate.get("live_mode_enabled"):
        failures.append("go-live gate does not show live_guarded as enabled.")
    if verdict.get("ready_to_enable_live") is not True:
        failures.append("go-live prerequisites are not complete enough to enable live mode.")
    if verdict.get("ready_to_arm_live") is not True:
        failures.append("go-live gate is not ready to arm live trading.")
    if require_armed and verdict.get("ready_for_live_order") is not True:
        failures.append("final live readiness requires a currently armed live window.")
    if not require_armed and gate.get("blocking_gates"):
        non_arming_blockers = [
            item.get("id") or item.get("label")
            for item in gate.get("blocking_gates", [])
            if item.get("id") != "live_arming"
        ]
        if non_arming_blockers:
            failures.append(f"non-arming blockers remain: {', '.join(non_arming_blockers)}.")
    if verdict.get("blocking_gate_ids") and require_armed:
        failures.append(f"blocking gates remain: {', '.join(verdict.get('blocking_gate_ids') or [])}.")
    if attestation.get("status") != "pass":
        failures.append("live attestation is missing, incomplete, or expired.")

    failed_checklist = [
        item.get("id") or item.get("label")
        for item in checklist
        if item.get("status") != "pass"
        and (require_armed or item.get("id") != "short_live_arming")
    ]
    if failed_checklist:
        failures.append(f"go-live checklist is not all pass: {', '.join(failed_checklist)}.")

    if require_ai_operator:
        if not operator.get("enabled"):
            failures.append("AI/Codex operator console is not enabled.")
        if not operator.get("ready"):
            failures.append("AI/Codex operator is not ready; configure its provider and API key or use rules mode.")
        if not operator.get("allow_file_read"):
            failures.append("AI/Codex operator cannot read workspace files.")
        if not operator.get("allow_file_write"):
            failures.append("AI/Codex operator cannot write workspace files.")
        if not operator.get("allow_shell"):
            failures.append("AI/Codex operator cannot run shell commands.")
        if operator.get("allow_shell") and not operator.get("backup_before_shell"):
            failures.append("AI/Codex operator Shell backup is disabled; enable AI_OPERATOR_BACKUP_BEFORE_SHELL.")
        if not operator.get("apply_model_file_actions"):
            failures.append("AI/Codex operator is not set to auto-apply model file actions.")

    arming = gate.get("live_arming") or {}
    return {
        "ok": not failures,
        "status": "pass" if not failures else "fail",
        "generated_at": report.get("generated_at"),
        "require_armed": require_armed,
        "require_ai_operator": require_ai_operator,
        "app_env": report.get("app_env"),
        "exchange_mode": report.get("exchange_mode"),
        "ready_to_enable_live": verdict.get("ready_to_enable_live"),
        "ready_to_arm_live": verdict.get("ready_to_arm_live"),
        "ready_for_live_order": verdict.get("ready_for_live_order"),
        "blocking_gates": verdict.get("blocking_gate_ids") or [],
        "failures": failures,
        "live_arming": {
            "armed": arming.get("armed"),
            "remaining_seconds": arming.get("remaining_seconds"),
            "remaining_orders": arming.get("remaining_orders"),
            "max_orders": arming.get("max_orders"),
        },
        "live_attestation": {
            "status": attestation.get("status"),
            "attested_at": attestation.get("attested_at"),
            "missing_ids": attestation.get("missing_ids") or [],
        },
        "ai_operator": operator,
        "report": report,
    }


LIVE_PILOT_CONFIRMATION = "LAUNCH_LIVE_PILOT"


def live_pilot_status(symbol: str = "BTCUSDT") -> dict[str, Any]:
    symbol = (symbol or "BTCUSDT").upper().strip()
    risk = risk_config()
    symbol_allowed = symbol in (risk.get("allowed_symbols") or [])
    prearm = final_live_readiness(require_armed=False)
    armed = final_live_readiness(require_armed=True)
    active_runs = sorted(ACTIVE_RUNS)
    failures: list[str] = []
    if not symbol_allowed:
        failures.append(f"Symbol {symbol} is not in the risk whitelist.")
    if active_runs:
        failures.append(f"Active run exists: {', '.join(active_runs)}.")
    failures.extend(armed.get("failures") or [])
    can_launch = symbol_allowed and not active_runs and bool(armed.get("ok"))
    if can_launch:
        status = "ready"
        next_action = "POST /api/live-pilot/run with confirmation=LAUNCH_LIVE_PILOT to submit one live_guarded pilot run."
    elif prearm.get("ok") and not armed.get("ok"):
        status = "needs_arming"
        next_action = "Arm live trading with ARM_LIVE_TRADING, then re-run the final live pilot check."
    else:
        status = "blocked"
        next_action = "Resolve the listed final-live blockers before attempting a live pilot run."
    return {
        "status": status,
        "symbol": symbol,
        "can_launch": can_launch,
        "confirmation_phrase": LIVE_PILOT_CONFIRMATION,
        "active_runs": active_runs,
        "symbol_allowed": symbol_allowed,
        "next_action": next_action,
        "failures": failures,
        "prearm_ready": {
            "ok": prearm.get("ok"),
            "status": prearm.get("status"),
            "failures": prearm.get("failures") or [],
            "blocking_gates": prearm.get("blocking_gates") or [],
            "ready_to_arm_live": prearm.get("ready_to_arm_live"),
        },
        "armed_ready": {
            "ok": armed.get("ok"),
            "status": armed.get("status"),
            "failures": armed.get("failures") or [],
            "blocking_gates": armed.get("blocking_gates") or [],
            "ready_for_live_order": armed.get("ready_for_live_order"),
            "live_arming": armed.get("live_arming") or {},
        },
        "safety_contract": [
            "This endpoint never changes environment flags or enables live mode.",
            "A real Binance order can only be launched after final_live_readiness(require_armed=true) passes.",
            "The existing live_guarded OMS/RMS path still performs go-live gate checks immediately before order submission.",
            "The request must include confirmation=LAUNCH_LIVE_PILOT; otherwise it is rejected.",
        ],
        "updated_at": utc_now(),
    }


def execute_live_pilot_order(settings: dict[str, Any]) -> dict[str, Any]:
    confirmation = str(settings.get("confirmation") or "").strip()
    if confirmation != LIVE_PILOT_CONFIRMATION:
        raise ValueError(f"Live pilot requires confirmation={LIVE_PILOT_CONFIRMATION}.")
    symbol = str(settings.get("symbol") or "BTCUSDT").upper().strip()
    status = live_pilot_status(symbol)
    if not status["can_launch"]:
        failures = status.get("failures") or ["live pilot is not ready"]
        raise ValueError("Live pilot is blocked: " + "; ".join(str(item) for item in failures[:8]))
    run = launch_run(symbol, "live_guarded")
    insert_event(
        run["id"],
        "system",
        "Live Pilot",
        "实盘首单执行器已提交 live_guarded 工作流",
        (
            f"已为 {symbol} 提交一次 live_guarded 首单工作流；真实下单仍由 OMS/RMS、"
            "go-live gate 和短时武装额度在执行路径内再次校验。"
        ),
        {
            "symbol": symbol,
            "run_id": run["id"],
            "live_pilot": {
                "status_before_launch": status["status"],
                "confirmation": "[REDACTED:LIVE_PILOT_CONFIRMATION]",
            },
        },
    )
    return {
        "status": "launched",
        "run": run,
        "live_pilot": live_pilot_status(symbol),
    }


def live_pilot_postflight_status(symbol: str = "BTCUSDT", run_id: str = "") -> dict[str, Any]:
    symbol = (symbol or "BTCUSDT").upper().strip()
    selected_run = get_run(run_id) if run_id else get_latest_run()
    run_orders = [
        order
        for order in get_orders(limit=200)
        if selected_run and order.get("run_id") == selected_run.get("id")
    ]
    live_orders = [
        order
        for order in run_orders
        if order.get("mode") == "live_guarded" or str(order.get("id") or "").startswith("LIVE")
    ]
    oms = oms_summary(get_orders(limit=200))
    audit = audit_chain_status(limit=8)
    audit_ok = audit.get("status") == "pass" and int(audit.get("total_records") or 0) > 0
    alerts = run_watchdog_checks()
    recovery = exchange_recovery_status()
    live_snapshot = latest_exchange_account_snapshot("live_guarded")
    live_pilot = live_pilot_status(symbol)
    final_prearm = final_live_readiness(require_armed=False)
    selected_mode = str((selected_run or {}).get("mode") or "")
    selected_status = str((selected_run or {}).get("status") or "")

    checks = [
        {
            "id": "selected_live_run",
            "label": "实盘首单运行记录",
            "status": "pass" if selected_run and selected_mode == "live_guarded" else "warn",
            "detail": (
                f"运行 {selected_run.get('id')} 是 live_guarded。"
                if selected_run and selected_mode == "live_guarded"
                else "尚未选择或尚未产生 live_guarded 首单运行记录。"
            ),
        },
        {
            "id": "run_terminal",
            "label": "首单工作流终态",
            "status": "pass" if selected_status == "completed" else "fail" if selected_status == "failed" else "warn",
            "detail": f"当前运行状态={selected_status or '-'}。",
        },
        {
            "id": "live_order_evidence",
            "label": "实盘订单证据",
            "status": "pass" if live_orders else "warn",
            "detail": f"该运行关联 live_guarded 订单 {len(live_orders)} 个。",
        },
        {
            "id": "oms_postflight_reconciled",
            "label": "OMS 后验对账",
            "status": "pass" if oms.get("needs_reconcile") == 0 and oms.get("unknown_venue_status") == 0 else "fail",
            "detail": f"待对账={oms.get('needs_reconcile')}，未知交易所状态={oms.get('unknown_venue_status')}。",
        },
        {
            "id": "alerts_postflight",
            "label": "告警后验状态",
            "status": "pass" if (alerts.get("summary") or {}).get("critical", 0) == 0 else "fail",
            "detail": (
                f"活跃告警={(alerts.get('summary') or {}).get('active', 0)}，"
                f"严重={(alerts.get('summary') or {}).get('critical', 0)}，"
                f"警告={(alerts.get('summary') or {}).get('warning', 0)}。"
            ),
        },
        {
            "id": "audit_chain_postflight",
            "label": "审计链后验状态",
            "status": "pass" if audit_ok else "fail",
            "detail": f"审计记录={audit.get('total_records')}，断链={audit.get('broken_count')}。",
        },
        {
            "id": "live_arming_disarmed",
            "label": "短时武装已释放",
            "status": "pass" if not (live_pilot.get("armed_ready") or {}).get("live_arming", {}).get("armed") else "warn",
            "detail": "当前没有活跃 live arming。" if not (live_pilot.get("armed_ready") or {}).get("live_arming", {}).get("armed") else "live arming 仍处于活跃窗口，请确认是否应立即解除。",
        },
        {
            "id": "exchange_snapshot_postflight",
            "label": "交易所账户快照",
            "status": "pass" if live_snapshot else "warn",
            "detail": f"最近 live_guarded 快照时间={(live_snapshot or {}).get('ts') or '-'}。",
        },
        {
            "id": "final_prearm_after_pilot",
            "label": "后验准入仍可解释",
            "status": "pass" if final_prearm.get("ok") else "warn",
            "detail": "非武装 final-live 检查通过。" if final_prearm.get("ok") else f"仍有 {len(final_prearm.get('failures') or [])} 个非武装阻塞项。",
        },
    ]
    failed = [item for item in checks if item["status"] == "fail"]
    warned = [item for item in checks if item["status"] == "warn"]
    status = "fail" if failed else "warn" if warned else "pass"
    return {
        "status": status,
        "ok": not failed,
        "symbol": symbol,
        "run_id": (selected_run or {}).get("id") or "",
        "run": selected_run,
        "checks": checks,
        "failed_checks": failed,
        "warnings": warned,
        "orders": live_orders[:10],
        "oms": oms,
        "alerts": alerts.get("summary") or {},
        "audit_chain": {
            "ok": audit_ok,
            "status": audit.get("status"),
            "total_records": audit.get("total_records"),
            "broken_count": audit.get("broken_count"),
            "last_hash": audit.get("last_hash"),
        },
        "exchange_recovery": {
            "last_at": recovery.get("last_at"),
            "user_stream": recovery.get("user_stream"),
            "live_snapshot": live_snapshot,
        },
        "live_pilot": live_pilot,
        "final_live_ready_prearm": {
            "ok": final_prearm.get("ok"),
            "status": final_prearm.get("status"),
            "failures": final_prearm.get("failures") or [],
            "blocking_gates": final_prearm.get("blocking_gates") or [],
        },
        "next_actions": [
            item["detail"] for item in failed[:5]
        ]
        or [
            item["detail"] for item in warned[:5]
        ]
        or ["实盘首单后验检查通过；继续按小额、短时、单笔预算扩大。"],
        "updated_at": utc_now(),
    }


def server_go_live_audit() -> dict[str, Any]:
    return {
        "ok": True,
        "generated_at": utc_now(),
        "base_url": f"http://{HOST}:{PORT}",
        "health": {"ok": True, "time": utc_now(), "auth_enabled": AUTH_ENABLED},
        "readiness": deployment_readiness(),
        "go_live_gate": go_live_gate_status(),
        "live_env_profile": live_env_profile_status(),
        "final_live_ready_prearm": final_live_readiness(require_armed=False),
        "final_live_ready_armed": final_live_readiness(require_armed=True),
        "live_blocker_resolution": live_blocker_resolution_status(),
        "ai_operator": {
            "status": ai_operator_status(),
            "history": get_ai_operator_messages(limit=20),
        },
        "go_live_report": go_live_report(),
    }


def create_server_bundle() -> dict[str, Any]:
    command = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "export_server_bundle.py"),
        "--output-dir",
        str(SERVER_BUNDLE_OUTPUT_DIR),
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "server bundle export failed").strip())
    try:
        result = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"server bundle export returned invalid JSON: {exc}") from exc
    bundle_path = Path(str(result.get("bundle_path") or "")).resolve()
    if not bundle_path.exists() or not bundle_path.is_file():
        raise RuntimeError("server bundle export did not create a zip file")
    try:
        bundle_path.relative_to(ROOT_DIR)
    except ValueError as exc:
        raise RuntimeError("server bundle path escaped the project root") from exc
    result["download_name"] = bundle_path.name
    return result


def create_live_launch_kit() -> dict[str, Any]:
    command = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "export_live_launch_kit.py"),
        "--output-dir",
        str(LIVE_LAUNCH_KIT_OUTPUT_DIR),
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        timeout=360,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "live launch kit export failed").strip())
    try:
        result = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"live launch kit export returned invalid JSON: {exc}") from exc
    kit_path = Path(str(result.get("kit_path") or "")).resolve()
    if not kit_path.exists() or not kit_path.is_file():
        raise RuntimeError("live launch kit export did not create a zip file")
    try:
        kit_path.relative_to(ROOT_DIR)
    except ValueError as exc:
        raise RuntimeError("live launch kit path escaped the project root") from exc
    result["download_name"] = kit_path.name
    return result


def create_live_env_pack() -> dict[str, Any]:
    command = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "export_live_env_pack.py"),
        "--output-dir",
        str(LIVE_ENV_PACK_OUTPUT_DIR),
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "live env pack export failed").strip())
    try:
        result = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"live env pack export returned invalid JSON: {exc}") from exc
    pack_path = Path(str(result.get("pack_path") or "")).resolve()
    if not pack_path.exists() or not pack_path.is_file():
        raise RuntimeError("live env pack export did not create a zip file")
    try:
        pack_path.relative_to(ROOT_DIR)
    except ValueError as exc:
        raise RuntimeError("live env pack path escaped the project root") from exc
    result["download_name"] = pack_path.name
    return result


def live_env_profile_runtime_env() -> dict[str, str]:
    env = {key: str(value) for key, value in os.environ.items()}
    env.update(
        {
            "APP_ENV": APP_ENV,
            "APP_HOST": HOST,
            "APP_PORT": str(PORT),
            "APP_BASIC_AUTH_USER": APP_BASIC_AUTH_USER,
            "APP_BASIC_AUTH_PASSWORD": APP_BASIC_AUTH_PASSWORD,
            "TRADER_BIND_IP": TRADER_BIND_IP,
            "AI_PROVIDER": AI_PROVIDER,
            "AI_OPERATOR_ENABLED": str(AI_OPERATOR_ENABLED).lower(),
            "AI_OPERATOR_PROVIDER": AI_OPERATOR_PROVIDER,
            "AI_OPERATOR_ALLOW_FILE_WRITE": str(AI_OPERATOR_ALLOW_FILE_WRITE).lower(),
            "AI_OPERATOR_ALLOW_SHELL": str(AI_OPERATOR_ALLOW_SHELL).lower(),
            "AI_OPERATOR_APPLY_MODEL_FILE_ACTIONS": str(AI_OPERATOR_APPLY_MODEL_FILE_ACTIONS).lower(),
            "AI_OPERATOR_SNAPSHOT_WRITES": str(AI_OPERATOR_SNAPSHOT_WRITES).lower(),
            "AI_OPERATOR_BACKUP_BEFORE_SHELL": str(AI_OPERATOR_BACKUP_BEFORE_SHELL).lower(),
            "EXCHANGE_MODE": EXCHANGE_MODE,
            "ENABLE_BINANCE_TESTNET": str(ENABLE_BINANCE_TESTNET).lower(),
            "BINANCE_API_KEY": BINANCE_API_KEY,
            "BINANCE_API_SECRET": BINANCE_API_SECRET,
            "BINANCE_PLACE_TESTNET_ORDERS": str(BINANCE_PLACE_TESTNET_ORDERS).lower(),
            "ENABLE_BINANCE_LIVE": str(ENABLE_BINANCE_LIVE).lower(),
            "BINANCE_LIVE_API_KEY": BINANCE_LIVE_API_KEY,
            "BINANCE_LIVE_API_SECRET": BINANCE_LIVE_API_SECRET,
            "BINANCE_PLACE_LIVE_ORDERS": str(BINANCE_PLACE_LIVE_ORDERS).lower(),
            "LIVE_TRADING_CONFIRMATION": LIVE_TRADING_CONFIRMATION,
            "MAX_ORDER_NOTIONAL_USDT": str(MAX_ORDER_NOTIONAL_USDT),
            "LIVE_PILOT_MAX_WALLET_USDT": str(LIVE_PILOT_MAX_WALLET_USDT),
            "GO_LIVE_MIN_TESTNET_DRILL_CYCLES": str(GO_LIVE_MIN_TESTNET_DRILL_CYCLES),
            "GO_LIVE_MIN_WALKFORWARD_FOLDS": str(GO_LIVE_MIN_WALKFORWARD_FOLDS),
            "GO_LIVE_MIN_WALKFORWARD_POSITIVE_FOLD_RATE_PCT": str(GO_LIVE_MIN_WALKFORWARD_POSITIVE_FOLD_RATE_PCT),
            "GO_LIVE_MAX_WALKFORWARD_DRAWDOWN_PCT": str(GO_LIVE_MAX_WALKFORWARD_DRAWDOWN_PCT),
            "BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER": str(BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER).lower(),
            "BINANCE_TARGET_MARGIN_TYPE": BINANCE_TARGET_MARGIN_TYPE,
            "BINANCE_SYNC_LEVERAGE_BEFORE_ORDER": str(BINANCE_SYNC_LEVERAGE_BEFORE_ORDER).lower(),
            "BINANCE_REQUIRE_ONE_WAY_POSITION_MODE": str(BINANCE_REQUIRE_ONE_WAY_POSITION_MODE).lower(),
            "BINANCE_MAX_TIME_DRIFT_MS": str(BINANCE_MAX_TIME_DRIFT_MS),
            "ALERT_WEBHOOK_ENABLED": str(ALERT_WEBHOOK_ENABLED).lower(),
            "ALERT_WEBHOOK_URL": ALERT_WEBHOOK_URL,
            "ALERT_WEBHOOK_SECRET": ALERT_WEBHOOK_SECRET,
            "ALERT_TELEGRAM_ENABLED": str(ALERT_TELEGRAM_ENABLED).lower(),
            "ALERT_TELEGRAM_BOT_TOKEN": ALERT_TELEGRAM_BOT_TOKEN,
            "ALERT_TELEGRAM_CHAT_ID": ALERT_TELEGRAM_CHAT_ID,
            "ALERT_EMAIL_ENABLED": str(ALERT_EMAIL_ENABLED).lower(),
            "ALERT_EMAIL_SMTP_HOST": ALERT_EMAIL_SMTP_HOST,
            "ALERT_EMAIL_SMTP_PASSWORD": ALERT_EMAIL_SMTP_PASSWORD,
            "ALERT_EMAIL_FROM": ALERT_EMAIL_FROM,
            "ALERT_EMAIL_TO": ALERT_EMAIL_TO,
        }
    )
    return env


def live_env_profile_status(target: str = "live_guarded") -> dict[str, Any]:
    return build_live_env_profile(live_env_profile_runtime_env(), target=target, source="server_runtime")


def live_blocker_resolution_status(symbol: str = "BTCUSDT") -> dict[str, Any]:
    symbol = (symbol or "BTCUSDT").upper().strip()
    readiness = deployment_readiness()
    gate = go_live_gate_status()
    final_prearm = final_live_readiness(require_armed=False)
    final_armed = final_live_readiness(require_armed=True)
    env_profile = live_env_profile_status("live_guarded")
    drill = testnet_drill_status()
    server_runner = server_live_readiness_status()
    blocking_items = gate.get("blocking_gates") or []
    blocking_ids = [str(item.get("id") or "") for item in blocking_items]
    blocking_by_id = {str(item.get("id") or ""): item for item in blocking_items}

    def template(gate_id: str) -> dict[str, Any]:
        item = blocking_by_id.get(gate_id, {})
        base = {
            "id": gate_id,
            "label": item.get("label") or gate_id,
            "status": item.get("status") or "pending",
            "detail": item.get("detail") or "",
            "env_vars": [],
            "commands": [],
            "proof": [],
            "safety": "不会绕过 go-live gate、确认短语、短时武装、确定性风控或 OMS。",
        }
        if gate_id == "deployment_profile":
            base.update(
                {
                    "env_vars": [
                        "APP_ENV=server",
                        "APP_HOST=0.0.0.0",
                        "TRADER_BIND_IP=<tailscale-ipv4>",
                        "APP_BASIC_AUTH_USER=<choose-user>",
                        "APP_BASIC_AUTH_PASSWORD=<long-random-password>",
                    ],
                    "commands": [
                        "bash deploy/setup-ubuntu-tailscale.sh",
                        "bash deploy/setup-ubuntu-time-sync.sh",
                        "cp deploy/server.env.example .env",
                        "python3 scripts/live_env_profile.py --env-file .env --target mvp_server --strict",
                        "bash deploy/deploy-server.sh",
                    ],
                    "proof": [
                        "python3 scripts/preflight.py 显示 server_deployment_profile_ready=true。",
                        "UI 只能通过 Tailscale 地址和 Basic Auth 访问。",
                    ],
                }
            )
        elif gate_id == "live_flags":
            base.update(
                {
                    "env_vars": [
                        "EXCHANGE_MODE=live_guarded",
                        "ENABLE_BINANCE_LIVE=true",
                        "BINANCE_PLACE_LIVE_ORDERS=true",
                        "BINANCE_LIVE_API_KEY=<binance-live-key-without-withdrawal>",
                        "BINANCE_LIVE_API_SECRET=<binance-live-secret>",
                        "LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_RISK",
                    ],
                    "commands": [
                        "python3 scripts/live_env_profile.py --env-file .env --target live_guarded --strict",
                        "TRADER_ALLOW_LIVE_DEPLOY=true bash deploy/deploy-server.sh",
                        "TRADER_FINAL_LIVE_REQUIRE_ARMED=false python3 scripts/check_final_live_ready.py",
                    ],
                    "proof": [
                        "Binance live API key 已关闭提现并绑定服务器出口 IP。",
                        "final live pre-arm 只剩短时武装或无非武装阻塞。",
                    ],
                }
            )
        elif gate_id == "testnet_drill_cycles":
            base.update(
                {
                    "env_vars": [
                        "ENABLE_BINANCE_TESTNET=true",
                        "BINANCE_API_KEY=<binance-futures-testnet-key>",
                        "BINANCE_API_SECRET=<binance-futures-testnet-secret>",
                        "EXCHANGE_MODE=binance_testnet_validate",
                        "BINANCE_PLACE_TESTNET_ORDERS=false",
                    ],
                    "commands": [
                        "python3 scripts/live_env_profile.py --env-file .env --target testnet_validate --strict",
                        "python3 scripts/run_testnet_drill_until_ready.py --mode binance_testnet_validate --target-cycles 24 --interval-seconds 60",
                        "TRADER_CHECK_TESTNET=true python3 scripts/run_all_checks.py",
                    ],
                    "proof": [
                        f"真实 Testnet 验证周期达到 {GO_LIVE_MIN_TESTNET_DRILL_CYCLES} 次。",
                        "无真实 Testnet 挂单；验证模式只调用 /fapi/v1/order/test。",
                    ],
                }
            )
        elif gate_id == "server_auth":
            base.update(
                {
                    "env_vars": ["APP_BASIC_AUTH_USER=<choose-user>", "APP_BASIC_AUTH_PASSWORD=<long-random-password>"],
                    "commands": ["python3 scripts/preflight.py", "bash deploy/deploy-server.sh"],
                    "proof": ["未认证请求不能访问控制台；认证后可以访问中文 UI。"],
                }
            )
        elif gate_id == "private_network":
            base.update(
                {
                    "env_vars": ["TRADER_BIND_IP=<tailscale-ipv4>"],
                    "commands": ["bash deploy/setup-ubuntu-tailscale.sh", "sudo ufw allow OpenSSH", "sudo ufw enable"],
                    "proof": ["公网不开放 8787；只通过 Tailscale IP 访问。"],
                }
            )
        elif gate_id == "live_attestation":
            base.update(
                {
                    "commands": [
                        "/live-attest --confirm LIVE_ATTESTATION_CONFIRMED --actor operator --note <evidence-id>",
                        "python3 scripts/check_live_attestation.py",
                    ],
                    "proof": [
                        "提现权限关闭。",
                        "live key 绑定服务器公网出口 IP。",
                        "离线备份已复制到服务器外部。",
                        "小额首单资金上限已确认。",
                    ],
                }
            )
        elif gate_id == "alert_delivery":
            base.update(
                {
                    "env_vars": [
                        "ALERT_WEBHOOK_URL=<https-webhook-url>",
                        "或 ALERT_TELEGRAM_BOT_TOKEN / ALERT_TELEGRAM_CHAT_ID",
                        "或 ALERT_EMAIL_SMTP_HOST / ALERT_EMAIL_TO",
                    ],
                    "commands": ["python3 scripts/check_alert_delivery.py"],
                    "proof": ["外部告警测试成功，且 readiness 不再只依赖浏览器页面。"],
                }
            )
        elif gate_id == "private_user_stream":
            base.update(
                {
                    "commands": [
                        "python3 scripts/check_private_stream_mapping.py",
                        "python3 scripts/check_exchange_recovery.py",
                    ],
                    "proof": ["live listenKey 存在，私有回报流 consumer_running=true。"],
                }
            )
        elif gate_id == "exchange_recovery":
            base.update(
                {
                    "commands": ["POST /api/exchange-recovery", "python3 scripts/check_exchange_recovery.py"],
                    "proof": ["账户快照新鲜，订单状态已和交易所对齐。"],
                }
            )
        elif gate_id == "backtest_walkforward":
            base.update(
                {
                    "commands": [
                        "python3 scripts/run_strategy_quality_sweep.py --symbols BTCUSDT,ETHUSDT,SOLUSDT --intervals 5m,15m,1h --bars 240 --promote-best",
                        "python3 scripts/check_walkforward_quality_gate.py",
                    ],
                    "proof": ["最新 walk-forward 达到收益、正收益折数和回撤阈值。"],
                }
            )
        elif gate_id == "live_arming":
            base.update(
                {
                    "commands": [
                        "/live-arm --confirm ARM_LIVE_TRADING --ttl-minutes 10",
                        f"/live-pilot-run {symbol} --confirm LAUNCH_LIVE_PILOT",
                        f"/live-postflight {symbol}",
                    ],
                    "proof": ["短时武装仍在有效期内，且剩余入口订单额度大于 0。"],
                    "safety": "短时武装只在所有非武装门禁通过后使用；每次武装默认单笔入口订单预算。",
                }
            )
        else:
            base.update(
                {
                    "commands": [
                        "python3 scripts/run_all_checks.py",
                        "python3 scripts/server_go_live_audit.py",
                        "python3 scripts/check_go_live_gate.py",
                    ],
                    "proof": ["对应检查项状态变为 pass，并写入审计链。"],
                }
            )
        return base

    ordered_ids = [
        "deployment_profile",
        "server_auth",
        "private_network",
        "testnet_drill_cycles",
        "backtest_walkforward",
        "live_attestation",
        "alert_delivery",
        "exchange_recovery",
        "private_user_stream",
        "live_flags",
        "live_arming",
    ]
    step_ids = [gate_id for gate_id in ordered_ids if gate_id in blocking_ids]
    step_ids.extend(gate_id for gate_id in blocking_ids if gate_id not in step_ids)
    steps = [template(gate_id) for gate_id in step_ids]
    if not steps and gate.get("ready_for_live_order"):
        status = "ready_for_live_order"
        next_action = f"可以提交受控首单：/live-pilot-run {symbol} --confirm LAUNCH_LIVE_PILOT。"
    elif not steps and gate.get("ready_to_arm_live"):
        status = "ready_to_arm"
        next_action = "所有非武装门禁通过；下一步输入 ARM_LIVE_TRADING 短时武装。"
    elif gate.get("ready_to_enable_live") and not gate.get("live_mode_enabled"):
        status = "ready_to_enable_live"
        next_action = "前置门禁已过；下一步在服务器 .env 启用 live_guarded 显式 flags。"
    else:
        status = "blocked"
        next_action = steps[0]["detail"] if steps else "继续运行准入推进器收集证据。"

    return {
        "ok": status in {"ready_to_enable_live", "ready_to_arm", "ready_for_live_order"},
        "status": status,
        "symbol": symbol,
        "generated_at": utc_now(),
        "app_env": APP_ENV,
        "exchange_mode": EXCHANGE_MODE,
        "blocking_gates": blocking_ids,
        "next_action": next_action,
        "steps": steps,
        "readiness": {
            "overall": readiness.get("overall"),
            "server_deployment_profile_ready": APP_ENV == "server" and AUTH_ENABLED and TRADER_BIND_IP not in {"0.0.0.0", "::", ""},
        },
        "testnet_drill": {
            "real_completed_cycles": drill.get("real_completed_cycles"),
            "target_cycles": drill.get("target_cycles"),
            "last_error": drill.get("last_error"),
            "mode": drill.get("mode"),
        },
        "final_live_ready_prearm": {
            "ok": final_prearm.get("ok"),
            "failures": final_prearm.get("failures") or [],
            "blocking_gates": final_prearm.get("blocking_gates") or [],
        },
        "final_live_ready_armed": {
            "ok": final_armed.get("ok"),
            "failures": final_armed.get("failures") or [],
            "blocking_gates": final_armed.get("blocking_gates") or [],
        },
        "live_env_profile": {
            "status": env_profile.get("status"),
            "target": env_profile.get("target"),
            "failed_checks": env_profile.get("failed_checks") or [],
        },
        "server_live_readiness": {
            "status": server_runner.get("status"),
            "running": server_runner.get("running"),
            "last_report_path": server_runner.get("last_report_path"),
            "last_error": server_runner.get("last_error"),
        },
        "ai_commands": [
            "/resolve-live-blockers",
            "/server-readiness-run --testnet --cycles 24 --interval 60",
            "/env-pack",
            "/launch-kit",
            f"/live-pilot {symbol}",
            f"/live-postflight {symbol}",
        ],
        "safety_note": "该路线只解释和编排剩余门禁，不会写入 secret、不会启用 live、不会短时武装、不会下单。",
    }


def live_launch_plan_status() -> dict[str, Any]:
    gate = go_live_gate_status()
    evidence = {
        "app_env": APP_ENV,
        "exchange_mode": EXCHANGE_MODE,
        "readiness": deployment_readiness(),
        "live_env_profile": live_env_profile_status(),
        "go_live_gate": gate,
        "final_live_ready_prearm": {
            "ok": gate.get("ready_to_arm_live"),
            "failures": [],
        },
        "final_live_ready_armed": {
            "ok": gate.get("ready_for_live_order"),
            "failures": [] if gate.get("ready_for_live_order") else ["final live verifier and ARM_LIVE_TRADING are still required."],
        },
        "go_live_report": {
            "verdict": {
                "status": gate.get("status"),
                "ready_for_live_order": gate.get("ready_for_live_order"),
                "blocking_gate_ids": [
                    item.get("id") for item in (gate.get("blocking_gates") or [])
                ],
            }
        },
        "server_live_readiness": server_live_readiness_status(),
        "ai_operator": ai_operator_status(),
        "paths": {
            "latest_go_live_report": ai_operator_latest_report_path("go-live-report-*.json"),
            "latest_go_live_report_md": ai_operator_latest_report_path("go-live-report-*.md"),
            "latest_server_go_live_audit": ai_operator_latest_report_path("server-go-live-audit-*.json"),
            "latest_server_go_live_audit_md": ai_operator_latest_report_path("server-go-live-audit-*.md"),
            "latest_server_bundle": ai_operator_latest_report_path("server-bundles/*.zip"),
            "latest_local_readiness": ai_operator_latest_report_path("local-readiness-*.json"),
        },
    }
    return build_live_launch_plan(evidence)


def live_ops_handoff_status(symbol: str = "BTCUSDT") -> dict[str, Any]:
    normalized_symbols = normalize_symbols(symbol)
    symbol = normalized_symbols[0] if normalized_symbols else "BTCUSDT"
    gate = go_live_gate_status()
    plan = live_launch_plan_status()
    evidence = {
        "generated_at": utc_now(),
        "symbol": symbol,
        "app_env": APP_ENV,
        "exchange_mode": EXCHANGE_MODE,
        "go_live_gate": gate,
        "final_live_ready_prearm": final_live_readiness(require_armed=False),
        "final_live_ready_armed": final_live_readiness(require_armed=True),
        "live_pilot": live_pilot_status(symbol),
        "live_launch_plan": plan,
        "server_live_readiness": server_live_readiness_status(),
        "ai_operator": ai_operator_status(),
        "paths": {
            "latest_go_live_report": ai_operator_latest_report_path("go-live-report-*.json"),
            "latest_go_live_report_md": ai_operator_latest_report_path("go-live-report-*.md"),
            "latest_server_go_live_audit": ai_operator_latest_report_path("server-go-live-audit-*.json"),
            "latest_server_go_live_audit_md": ai_operator_latest_report_path("server-go-live-audit-*.md"),
            "latest_live_launch_plan": ai_operator_latest_report_path("live-launch-plan-*.json"),
            "latest_live_launch_plan_md": ai_operator_latest_report_path("live-launch-plan-*.md"),
            "latest_server_bundle": ai_operator_latest_report_path("server-bundles/*.zip"),
            "latest_local_readiness": ai_operator_latest_report_path("local-readiness-*.json"),
        },
    }
    return build_live_ops_handoff(evidence)


def server_live_readiness_status() -> dict[str, Any]:
    global SERVER_LIVE_READINESS_THREAD
    with SERVER_LIVE_READINESS_LOCK:
        running = SERVER_LIVE_READINESS_THREAD is not None and SERVER_LIVE_READINESS_THREAD.is_alive()
    status = get_setting("server_live_readiness_status", "idle")
    if running:
        status = "running"
    try:
        summary = json.loads(get_setting("server_live_readiness_last_summary", "{}") or "{}")
    except json.JSONDecodeError:
        summary = {}
    try:
        options = json.loads(get_setting("server_live_readiness_last_options", "{}") or "{}")
    except json.JSONDecodeError:
        options = {}
    return {
        "status": status,
        "running": running,
        "run_id": get_setting("server_live_readiness_run_id", ""),
        "started_at": get_setting("server_live_readiness_started_at", ""),
        "completed_at": get_setting("server_live_readiness_completed_at", ""),
        "last_error": get_setting("server_live_readiness_last_error", ""),
        "last_report_path": get_setting("server_live_readiness_last_report_path", ""),
        "last_summary": summary,
        "last_options": options,
    }


def server_live_readiness_command(options: dict[str, Any]) -> list[str]:
    command = [sys.executable, str(ROOT_DIR / "scripts" / "run_server_live_readiness.py")]
    if coerce_bool(options.get("dry_run", False)):
        command.append("--dry-run")
    if coerce_bool(options.get("run_testnet_drill", False)):
        command.append("--run-testnet-drill")
    if coerce_bool(options.get("skip_full_checks", False)):
        command.append("--skip-full-checks")
    if coerce_bool(options.get("skip_strategy_sweep", False)):
        command.append("--skip-strategy-sweep")
    if coerce_bool(options.get("allow_testnet_placement", False)):
        command.append("--allow-testnet-placement")
    if coerce_bool(options.get("strict", False)):
        command.append("--strict")
    mode = str(options.get("testnet_mode") or "binance_testnet_validate").strip()
    if mode:
        command.extend(["--testnet-mode", mode])
    target_cycles = int(safe_float(options.get("target_cycles"), GO_LIVE_MIN_TESTNET_DRILL_CYCLES))
    interval_seconds = float(safe_float(options.get("interval_seconds"), 60.0))
    command.extend(["--target-cycles", str(max(1, target_cycles))])
    command.extend(["--interval-seconds", str(max(0.0, interval_seconds))])
    return command


def run_server_live_readiness_background(run_id: str, options: dict[str, Any]) -> None:
    global SERVER_LIVE_READINESS_THREAD
    command = server_live_readiness_command(options)
    timeout_seconds = int(safe_float(options.get("timeout_seconds"), 1800.0))
    timeout_seconds = max(60, min(86400, timeout_seconds))
    set_setting("server_live_readiness_status", "running")
    set_setting("server_live_readiness_run_id", run_id)
    set_setting("server_live_readiness_started_at", utc_now())
    set_setting("server_live_readiness_completed_at", "")
    set_setting("server_live_readiness_last_error", "")
    set_setting("server_live_readiness_last_options", json.dumps(options, ensure_ascii=False))
    insert_event(
        run_id,
        "system",
        "Server Live Readiness",
        "服务器准入推进器已启动",
        "系统正在收集部署、策略、Testnet、审计、备份和最终实盘准入证据。",
        {"command": command, "options": options},
    )
    started = time.time()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT_DIR,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        stdout, stdout_truncated = ai_operator_truncate_output(completed.stdout)
        stderr, stderr_truncated = ai_operator_truncate_output(completed.stderr)
        try:
            summary = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError:
            summary = {}
        report_path = str(summary.get("report_path") or "")
        status = "completed" if completed.returncode == 0 else "failed"
        error = "" if completed.returncode == 0 else (stderr or stdout or f"returncode={completed.returncode}")
        payload = {
            "run_id": run_id,
            "status": status,
            "command": command,
            "returncode": completed.returncode,
            "duration_seconds": round(time.time() - started, 2),
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "summary": summary,
            "report_path": report_path,
        }
        set_setting("server_live_readiness_status", status)
        set_setting("server_live_readiness_completed_at", utc_now())
        set_setting("server_live_readiness_last_error", error)
        set_setting("server_live_readiness_last_summary", json.dumps(summary, ensure_ascii=False))
        set_setting("server_live_readiness_last_report_path", report_path)
        insert_event(
            run_id,
            "system" if completed.returncode == 0 else "error",
            "Server Live Readiness",
            "服务器准入推进器已完成" if completed.returncode == 0 else "服务器准入推进器失败",
            f"状态={status}，最终实盘就绪={summary.get('final_live_ready')}，阻塞项={summary.get('blocking_gates')}",
            payload,
        )
    except subprocess.TimeoutExpired as exc:
        stdout, stdout_truncated = ai_operator_truncate_output(exc.stdout)
        stderr, stderr_truncated = ai_operator_truncate_output(exc.stderr)
        error = f"Timed out after {timeout_seconds}s"
        summary = {
            "ok": False,
            "final_live_ready": False,
            "blocking_gates": [],
            "error": error,
        }
        set_setting("server_live_readiness_status", "failed")
        set_setting("server_live_readiness_completed_at", utc_now())
        set_setting("server_live_readiness_last_error", error)
        set_setting("server_live_readiness_last_summary", json.dumps(summary, ensure_ascii=False))
        insert_event(
            run_id,
            "error",
            "Server Live Readiness",
            "服务器准入推进器超时",
            error,
            {
                "run_id": run_id,
                "command": command,
                "stdout": stdout,
                "stderr": stderr,
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated,
            },
        )
    finally:
        with SERVER_LIVE_READINESS_LOCK:
            SERVER_LIVE_READINESS_THREAD = None


def start_server_live_readiness(options: dict[str, Any]) -> dict[str, Any]:
    global SERVER_LIVE_READINESS_THREAD
    with SERVER_LIVE_READINESS_LOCK:
        if SERVER_LIVE_READINESS_THREAD is not None and SERVER_LIVE_READINESS_THREAD.is_alive():
            raise RuntimeError("Server live-readiness runner is already active.")
        run_id = f"SLR-{uuid.uuid4().hex[:8].upper()}"
        thread = threading.Thread(
            target=run_server_live_readiness_background,
            args=(run_id, dict(options)),
            daemon=True,
        )
        SERVER_LIVE_READINESS_THREAD = thread
        thread.start()
    time.sleep(0.05)
    return server_live_readiness_status()


def go_live_report() -> dict[str, Any]:
    gate = go_live_gate_status()
    readiness = deployment_readiness()
    audit = audit_chain_status(limit=12)
    orders = get_orders(limit=100)
    backtests = get_backtests(limit=5)
    latest_backtest = backtests[0] if backtests else None
    walkforward = get_latest_walkforward()
    comparison = get_latest_backtest_comparison()
    recovery = exchange_recovery_status()
    alerts = run_watchdog_checks()
    drill = testnet_drill_status()
    operator = ai_operator_status()
    exchange = exchange_status()
    live_blockers = gate.get("blocking_gates") or []
    recovery_report = recovery.get("last_report") or {}
    raw_stream_events = recovery.get("stream_events")
    if isinstance(raw_stream_events, dict):
        stream_event_summary = {
            key: value for key, value in raw_stream_events.items() if key != "events"
        }
    else:
        stream_event_summary = {"event_count": len(raw_stream_events or [])}
    compact_recovery = {
        "last_at": recovery.get("last_at"),
        "orders": (recovery_report.get("orders") or {}) if isinstance(recovery_report.get("orders"), dict) else {},
        "errors": recovery_report.get("errors") or [],
        "trigger": recovery_report.get("trigger"),
        "started_at": recovery_report.get("started_at"),
        "completed_at": recovery_report.get("completed_at"),
        "snapshot_count": len(recovery.get("snapshots") or []),
        "position_modes": recovery_report.get("position_modes") or [],
        "stream_event_summary": stream_event_summary,
        "user_stream": recovery.get("user_stream"),
    }
    if "orders" in compact_recovery and "orders" in compact_recovery["orders"]:
        compact_recovery["orders"] = {
            key: value
            for key, value in compact_recovery["orders"].items()
            if key != "orders"
        }
    compact_comparison = None
    if comparison:
        compact_comparison = {
            key: comparison.get(key)
            for key in ("id", "symbol", "interval", "bars", "created_at", "strategy_family", "tested_count")
        }
        results = comparison.get("results") or []
        if results:
            compact_comparison["top_result"] = results[0]
    compact_walkforward = None
    if walkforward:
        compact_walkforward = {
            key: walkforward.get(key)
            for key in (
                "id",
                "symbol",
                "interval",
                "bars",
                "created_at",
                "fold_count",
                "tested_params_per_fold",
                "net_pnl_usdt",
                "total_return_pct",
                "max_fold_drawdown_pct",
                "positive_fold_rate_pct",
                "test_trade_count",
                "test_win_rate_pct",
            )
        }
        compact_walkforward["folds"] = (walkforward.get("folds") or [])[:3]
    compact_drill = {
        key: drill.get(key)
        for key in (
            "enabled",
            "symbol",
            "mode",
            "interval_seconds",
            "target_cycles",
            "completed_cycles",
            "real_completed_cycles",
            "dry_run_completed_cycles",
            "remaining_real_cycles",
            "started_at",
            "last_cycle_at",
            "last_real_cycle_at",
            "last_real_cycle_id",
            "next_cycle_at",
            "last_cycle_id",
            "last_error",
            "running",
            "available_modes",
            "active_run_modes",
        )
    }
    compact_drill["cycles"] = [
        {
            key: cycle.get(key)
            for key in (
                "id",
                "ts",
                "completed_at",
                "mode",
                "symbol",
                "reason",
                "status",
                "run_id",
                "order_id",
                "note",
            )
        }
        for cycle in (drill.get("cycles") or [])[:8]
    ]
    compact_alerts = {
        "summary": alerts["summary"],
        "delivery": alerts["delivery"],
        "recent_deliveries": [
            {
                key: item.get(key)
                for key in ("id", "alert_id", "ts", "channel", "transition", "status", "target", "status_code", "error")
            }
            for item in alerts["deliveries"][:10]
        ],
    }
    checklist = [
        {
            "id": "deployment_profile",
            "label": "真实实盘必须运行在 APP_ENV=server 的服务器部署档案",
            "status": next((item["status"] for item in gate["gates"] if item["id"] == "deployment_profile"), "fail"),
        },
        {
            "id": "server_private_access",
            "label": "服务器必须通过 Tailscale/私有地址访问",
            "status": next((item["status"] for item in gate["gates"] if item["id"] == "private_network"), "fail"),
        },
        {
            "id": "basic_auth",
            "label": "服务器 Basic Auth 必须启用",
            "status": next((item["status"] for item in gate["gates"] if item["id"] == "server_auth"), "fail"),
        },
        {
            "id": "live_flags",
            "label": "实盘 key、下单开关和确认短语必须全部显式配置",
            "status": next((item["status"] for item in gate["gates"] if item["id"] == "live_flags"), "fail"),
        },
        {
            "id": "live_attestation",
            "label": "live API key 外部权限、IP 白名单、合规、备份和小额试运行证据必须确认",
            "status": next((item["status"] for item in gate["gates"] if item["id"] == "live_attestation"), "fail"),
        },
        {
            "id": "live_pilot_capital",
            "label": "首轮实盘 live 钱包余额必须低于小额试运行上限",
            "status": next((item["status"] for item in gate["gates"] if item["id"] == "live_pilot_capital"), "fail"),
        },
        {
            "id": "exchange_leverage_sync",
            "label": "真实 Testnet/实盘下单前必须同步 Binance 交易对杠杆",
            "status": next((item["status"] for item in gate["gates"] if item["id"] == "exchange_leverage_sync"), "fail"),
        },
        {
            "id": "exchange_margin_type_sync",
            "label": "真实 Testnet/实盘下单前必须同步 Binance 保证金模式",
            "status": next((item["status"] for item in gate["gates"] if item["id"] == "exchange_margin_type_sync"), "fail"),
        },
        {
            "id": "exchange_position_mode",
            "label": "实盘前必须验证 Binance 持仓模式为 One-way",
            "status": next((item["status"] for item in gate["gates"] if item["id"] == "exchange_position_mode"), "fail"),
        },
        {
            "id": "binance_time_drift",
            "label": "实盘前本机时间与 Binance serverTime 漂移必须在阈值内",
            "status": next((item["status"] for item in gate["gates"] if item["id"] == "binance_time_drift"), "fail"),
        },
        {
            "id": "risk_oms_audit",
            "label": "风控、OMS 对账、审计哈希链必须通过",
            "status": "pass"
            if all(
                next((item["status"] for item in gate["gates"] if item["id"] == gate_id), "fail") == "pass"
                for gate_id in ("risk_controls", "oms_reconciled", "audit_chain")
            )
            else "fail",
        },
        {
            "id": "panic_stop_drill",
            "label": "事故停机演练必须在最近 7 天内通过",
            "status": next((item["status"] for item in gate["gates"] if item["id"] == "panic_stop_drill"), "fail"),
        },
        {
            "id": "exchange_emergency_controls",
            "label": "交易所全局撤单和平仓预案必须通过",
            "status": next((item["status"] for item in gate["gates"] if item["id"] == "exchange_emergency_controls"), "fail"),
        },
        {
            "id": "backup_restore_drill",
            "label": "备份 dry-run 与临时库恢复必须在最近 7 天内通过",
            "status": next((item["status"] for item in gate["gates"] if item["id"] == "backup_restore_drill"), "fail"),
        },
        {
            "id": "alerts_recovery_stream",
            "label": "告警、恢复同步、私有回报流必须满足实盘要求",
            "status": "pass"
            if all(
                not item.get("blocks_live_order")
                for item in gate["gates"]
                if item["id"] in {"alert_watchdog", "alert_delivery", "exchange_recovery", "private_user_stream"}
            )
            else "fail",
        },
        {
            "id": "testnet_drill",
            "label": "Testnet 连续演练次数必须达标",
            "status": next((item["status"] for item in gate["gates"] if item["id"] == "testnet_drill_cycles"), "fail"),
        },
        {
            "id": "backtest_walkforward",
            "label": "回测、参数比较和滚动验证必须可追溯",
            "status": next((item["status"] for item in gate["gates"] if item["id"] == "backtest_walkforward"), "fail"),
        },
        {
            "id": "short_live_arming",
            "label": "每次实盘下单前必须短时武装",
            "status": next((item["status"] for item in gate["gates"] if item["id"] == "live_arming"), "fail"),
        },
    ]
    return {
        "generated_at": utc_now(),
        "app_env": APP_ENV,
        "exchange_mode": EXCHANGE_MODE,
        "verdict": {
            "ready_to_enable_live": gate["ready_to_enable_live"],
            "ready_to_arm_live": gate["ready_to_arm_live"],
            "ready_for_live_order": gate["ready_for_live_order"],
            "status": gate["status"],
            "blocking_gate_ids": [item.get("id") for item in live_blockers],
            "blocking_gate_labels": [item.get("label") for item in live_blockers],
        },
        "checklist": checklist,
        "go_live_gate": gate,
        "readiness": readiness,
        "risk": risk_config(),
        "oms": oms_summary(orders),
        "exchange": exchange,
        "exchange_recovery": compact_recovery,
        "alerts": compact_alerts,
        "testnet_drill": compact_drill,
        "audit_chain": audit,
        "live_attestation": live_attestation_status(),
        "latest_backtest": latest_backtest,
        "latest_comparison": compact_comparison,
        "latest_walkforward": compact_walkforward,
        "ai_operator": {
            "enabled": operator["enabled"],
            "ready": operator["ready"],
            "provider": operator["provider"],
            "allow_file_read": operator["allow_file_read"],
            "allow_file_write": operator["allow_file_write"],
            "allow_shell": operator["allow_shell"],
            "apply_model_file_actions": operator["apply_model_file_actions"],
            "backup_before_shell": operator["backup_before_shell"],
            "shell_backup_dir": operator["shell_backup_dir"],
            "workspace_root": operator["workspace_root"],
        },
        "required_manual_evidence": [
            "Binance live API key must have withdrawal disabled and should be IP-whitelisted to the server egress IP.",
            "Run the server behind Tailscale/private network plus strong Basic Auth.",
            "Keep a fresh data backup before enabling live_guarded.",
            "Confirm jurisdiction and exchange terms permit your intended futures trading.",
            "Confirm pilot live capital and per-order notional limits before short live arming.",
        ],
    }


def latest_state(
    include_architecture: bool = False,
    include_profile: bool = False,
    include_checks: bool = False,
) -> dict[str, Any]:
    profile: list[dict[str, Any]] = []

    def measure(name: str, fn: Callable[[], Any]) -> Any:
        if not include_profile:
            return fn()
        started = time.perf_counter()
        result = fn()
        profile.append({"name": name, "seconds": round(time.perf_counter() - started, 4)})
        return result

    alert_state = measure(
        "run_watchdog_checks" if include_checks else "alert_state_snapshot",
        run_watchdog_checks if include_checks else alert_state_snapshot,
    )
    latest = measure("get_latest_run", get_latest_run)
    run_id = latest["id"] if latest else None
    paper_state = measure("paper_account_state", paper_account_state)
    backtests = measure("get_backtests", lambda: get_backtests(limit=10))
    latest_backtest_id = backtests[0]["id"] if backtests else None
    orders = measure("get_orders", lambda: get_orders(limit=25))
    events = measure("get_events", lambda: get_events(run_id=run_id, limit=200) if run_id else [])
    testnet_drill = measure("testnet_drill", lambda: compact_testnet_drill_status(limit=6))
    exchange_recovery = measure("exchange_recovery", compact_exchange_recovery_status)
    readiness = measure(
        "deployment_readiness" if include_checks else "lightweight_deployment_readiness",
        deployment_readiness if include_checks else lightweight_deployment_readiness,
    )
    go_live_gate = measure(
        "go_live_gate_status" if include_checks else "lightweight_go_live_gate_status",
        go_live_gate_status if include_checks else lightweight_go_live_gate_status,
    )
    state = {
        "system": {
            "name": "Crypto Contract AI Trader",
            "environment": APP_ENV,
            "mode": EXCHANGE_MODE,
            "auth_enabled": AUTH_ENABLED,
            "emergency_stop": get_setting("emergency_stop", "false") == "true",
            "panic_stop_last_at": get_setting("panic_stop_last_at", ""),
            "active_runs": sorted(ACTIVE_RUNS),
            "updated_at": utc_now(),
        },
        "config": {
            "enabled_modes": enabled_modes(),
            "planned_modes": ["okx_demo", "live_guarded"],
            "market_data_source": MARKET_DATA_SOURCE,
            "ai": ai_status(),
            "ai_operator": ai_operator_status(),
            "exchange": exchange_status(),
            "account_equity_usdt": ACCOUNT_EQUITY_USDT,
            "max_leverage": MAX_LEVERAGE,
            "max_position_pct": MAX_POSITION_PCT,
            "risk": risk_config(),
            "project_root": str(ROOT_DIR),
        },
        "latest_run": latest,
        "events": events,
        "research": measure("research_artifacts", lambda: research_artifacts_for_run(events, latest)),
        "orders": orders,
        "oms": oms_summary(orders),
        "account": paper_state["account"],
        "positions": paper_state["positions"],
        "scheduler": measure("scheduler_status", scheduler_status),
        "testnet_drill": testnet_drill,
        "server_live_readiness": measure("server_live_readiness_status", server_live_readiness_status),
        "live_env_profile": measure("live_env_profile_status", live_env_profile_status),
        "go_live_gate": go_live_gate,
        "live_arming": go_live_gate.get("live_arming") or measure("live_arming_status", live_arming_status),
        "live_attestation": measure("live_attestation_status", live_attestation_status),
        "risk": risk_config(),
        "alerts": alert_state,
        "audit_chain": audit_chain_status(limit=8) if include_checks else audit_chain_snapshot(limit=6),
        "exchange_recovery": exchange_recovery,
        "backtests": backtests,
        "backtest_trades": measure("get_backtest_trades", lambda: get_backtest_trades(latest_backtest_id, limit=200)),
        "backtest_comparison": measure("get_latest_backtest_comparison", get_latest_backtest_comparison),
        "walkforward": measure("get_latest_walkforward", get_latest_walkforward),
        "ai_operator": {
            "status": measure("ai_operator_status", ai_operator_status),
            "history": measure("get_ai_operator_messages", lambda: get_ai_operator_messages(limit=20)),
        },
        "readiness": readiness,
    }
    if include_architecture:
        state["architecture"] = measure("production_architecture_blueprint", production_architecture_blueprint)
    if include_profile:
        state["_profile"] = profile
    return state


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{utc_now()}] {self.address_string()} {format % args}")

    def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file_download(self, path: Path, content_type: str, download_name: str) -> None:
        body = path.read_bytes()
        safe_name = "".join(ch for ch in download_name if ch.isalnum() or ch in {".", "-", "_"})
        if not safe_name:
            safe_name = path.name
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def is_authorized(self) -> bool:
        if not AUTH_ENABLED:
            return True
        header = self.headers.get("Authorization", "")
        expected_raw = f"{APP_BASIC_AUTH_USER}:{APP_BASIC_AUTH_PASSWORD}".encode("utf-8")
        expected = "Basic " + base64.b64encode(expected_raw).decode("ascii")
        return hmac.compare_digest(header, expected)

    def require_auth(self) -> bool:
        if self.is_authorized():
            return True
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Basic realm="Crypto Contract AI Trader"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        return False

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_json({"ok": True, "time": utc_now(), "auth_enabled": AUTH_ENABLED})
            return
        if not self.require_auth():
            return
        if parsed.path == "/api/state":
            params = parse_qs(parsed.query)
            include_architecture = params.get("include_architecture", ["false"])[0].lower() in {"1", "true", "yes"}
            include_profile = params.get("profile", ["false"])[0].lower() in {"1", "true", "yes"}
            include_checks = params.get("include_checks", ["false"])[0].lower() in {"1", "true", "yes"}
            self.send_json(
                latest_state(
                    include_architecture=include_architecture,
                    include_profile=include_profile,
                    include_checks=include_checks,
                )
            )
            return
        if parsed.path == "/api/architecture":
            self.send_json({"architecture": production_architecture_blueprint(), "generated_at": utc_now()})
            return
        if parsed.path == "/api/readiness":
            self.send_json(deployment_readiness())
            return
        if parsed.path == "/api/risk":
            self.send_json({"risk": risk_config(), "account": paper_account_state()["account"]})
            return
        if parsed.path == "/api/oms":
            orders = get_orders(limit=100)
            self.send_json({"oms": oms_summary(orders), "orders": orders})
            return
        if parsed.path == "/api/alerts":
            params = parse_qs(parsed.query)
            limit = min(100, int(params.get("limit", ["50"])[0]))
            include_resolved = params.get("include_resolved", ["false"])[0].lower() == "true"
            alerts = get_alerts(limit=limit, include_resolved=include_resolved)
            self.send_json(
                {
                    "alerts": alerts,
                    "summary": alert_summary(alerts),
                    "delivery": alert_delivery_config(),
                    "deliveries": get_alert_deliveries(limit=20),
                }
            )
            return
        if parsed.path == "/api/alerts/deliveries":
            params = parse_qs(parsed.query)
            limit = min(100, int(params.get("limit", ["50"])[0]))
            self.send_json({"deliveries": get_alert_deliveries(limit=limit), "delivery": alert_delivery_config()})
            return
        if parsed.path == "/api/audit-chain":
            params = parse_qs(parsed.query)
            limit = min(100, int(params.get("limit", ["25"])[0]))
            self.send_json({"audit_chain": audit_chain_status(limit=limit)})
            return
        if parsed.path == "/api/exchange/recovery":
            params = parse_qs(parsed.query)
            include_detail = params.get("detail", ["false"])[0].lower() in {"1", "true", "yes"}
            recovery = exchange_recovery_status()
            self.send_json({"exchange_recovery": recovery if include_detail else compact_exchange_recovery_status(recovery)})
            return
        if parsed.path == "/api/user-stream/events":
            params = parse_qs(parsed.query)
            limit = min(100, int(params.get("limit", ["25"])[0]))
            self.send_json(
                {
                    "events": get_exchange_stream_events(limit=limit),
                    "summary": exchange_stream_event_summary(),
                    "user_stream": binance_user_stream_status(),
                }
            )
            return
        if parsed.path == "/api/scheduler":
            self.send_json({"scheduler": scheduler_status()})
            return
        if parsed.path == "/api/testnet-drill":
            params = parse_qs(parsed.query)
            include_detail = params.get("detail", ["false"])[0].lower() in {"1", "true", "yes"}
            drill = testnet_drill_status()
            self.send_json({"testnet_drill": drill if include_detail else compact_testnet_drill_status(drill)})
            return
        if parsed.path == "/api/server-live-readiness":
            self.send_json({"server_live_readiness": server_live_readiness_status()})
            return
        if parsed.path == "/api/live-env-profile":
            params = parse_qs(parsed.query)
            target = params.get("target", ["live_guarded"])[0]
            self.send_json({"live_env_profile": live_env_profile_status(target)})
            return
        if parsed.path == "/api/live-launch-plan":
            self.send_json({"live_launch_plan": live_launch_plan_status()})
            return
        if parsed.path == "/api/live-ops-handoff":
            params = parse_qs(parsed.query)
            symbol = params.get("symbol", ["BTCUSDT"])[0]
            self.send_json({"live_ops_handoff": live_ops_handoff_status(symbol)})
            return
        if parsed.path == "/api/go-live-gate":
            self.send_json({"go_live_gate": go_live_gate_status()})
            return
        if parsed.path == "/api/go-live-report":
            self.send_json({"go_live_report": go_live_report()})
            return
        if parsed.path == "/api/final-live-ready":
            params = parse_qs(parsed.query)
            require_armed = params.get("require_armed", ["true"])[0].lower() == "true"
            require_ai_operator = params.get("require_ai_operator", ["true"])[0].lower() == "true"
            self.send_json(
                {
                    "final_live_ready": final_live_readiness(
                        require_armed=require_armed,
                        require_ai_operator=require_ai_operator,
                    )
                }
            )
            return
        if parsed.path == "/api/live-pilot":
            params = parse_qs(parsed.query)
            symbol = params.get("symbol", ["BTCUSDT"])[0]
            self.send_json({"live_pilot": live_pilot_status(symbol)})
            return
        if parsed.path == "/api/live-pilot-postflight":
            params = parse_qs(parsed.query)
            symbol = params.get("symbol", ["BTCUSDT"])[0]
            run_id = params.get("run_id", [""])[0]
            self.send_json({"live_pilot_postflight": live_pilot_postflight_status(symbol, run_id)})
            return
        if parsed.path == "/api/live-blocker-resolution":
            params = parse_qs(parsed.query)
            symbol = params.get("symbol", ["BTCUSDT"])[0]
            self.send_json({"live_blocker_resolution": live_blocker_resolution_status(symbol)})
            return
        if parsed.path == "/api/server-go-live-audit":
            self.send_json({"server_go_live_audit": server_go_live_audit()})
            return
        if parsed.path == "/api/server-bundle":
            try:
                bundle = create_server_bundle()
                self.send_file_download(
                    Path(bundle["bundle_path"]),
                    "application/zip",
                    str(bundle.get("download_name") or "crypto-contract-ai-trader-server-bundle.zip"),
                )
            except Exception as exc:
                self.send_json({"error": str(exc), "error_type": exc.__class__.__name__}, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/live-launch-kit":
            try:
                kit = create_live_launch_kit()
                self.send_file_download(
                    Path(kit["kit_path"]),
                    "application/zip",
                    str(kit.get("download_name") or "crypto-contract-ai-trader-live-launch-kit.zip"),
                )
            except Exception as exc:
                self.send_json({"error": str(exc), "error_type": exc.__class__.__name__}, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/live-env-pack":
            try:
                pack = create_live_env_pack()
                self.send_file_download(
                    Path(pack["pack_path"]),
                    "application/zip",
                    str(pack.get("download_name") or "crypto-contract-ai-trader-live-env-pack.zip"),
                )
            except Exception as exc:
                self.send_json({"error": str(exc), "error_type": exc.__class__.__name__}, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/live-arming":
            self.send_json({"live_arming": live_arming_status(), "go_live_gate": go_live_gate_status()})
            return
        if parsed.path == "/api/live-attestation":
            self.send_json({"live_attestation": live_attestation_status(), "go_live_gate": go_live_gate_status()})
            return
        if parsed.path == "/api/ai-operator":
            self.send_json(
                {
                    "status": ai_operator_status(),
                    "history": get_ai_operator_messages(limit=40),
                }
            )
            return
        if parsed.path == "/api/runs":
            params = parse_qs(parsed.query)
            limit = min(100, int(params.get("limit", ["25"])[0]))
            with DB_LOCK, connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
            self.send_json({"runs": [dict(row) for row in rows]})
            return
        if parsed.path == "/api/backtests":
            params = parse_qs(parsed.query)
            limit = min(50, int(params.get("limit", ["10"])[0]))
            backtests = get_backtests(limit=limit)
            latest_backtest_id = backtests[0]["id"] if backtests else None
            self.send_json(
                {
                    "backtests": backtests,
                    "trades": get_backtest_trades(latest_backtest_id, limit=200),
                }
            )
            return
        if parsed.path == "/api/backtests/compare":
            self.send_json({"comparison": get_latest_backtest_comparison()})
            return
        if parsed.path == "/api/backtests/walkforward":
            self.send_json({"walkforward": get_latest_walkforward()})
            return
        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if not self.require_auth():
            return
        if parsed.path == "/api/runs":
            body = self.read_json()
            symbol = str(body.get("symbol") or "BTCUSDT").upper().strip()
            mode = str(body.get("mode") or "paper").lower().strip()
            if mode not in enabled_modes():
                self.send_json(
                    {
                        "error": f"Mode {mode} is not enabled in this local build.",
                        "enabled_modes": enabled_modes(),
                    },
                    HTTPStatus.BAD_REQUEST,
                )
                return
            try:
                run = launch_run(symbol, mode)
            except ValueError as exc:
                self.send_json(
                    {"error": str(exc), "go_live_gate": go_live_gate_status() if mode == "live_guarded" else None},
                    HTTPStatus.BAD_REQUEST,
                )
                return
            except RuntimeError as exc:
                status_code = HTTPStatus.CONFLICT if "active" in str(exc).lower() else HTTPStatus.BAD_REQUEST
                self.send_json(
                    {"error": str(exc), "active_runs": sorted(ACTIVE_RUNS)},
                    status_code,
                )
                return
            self.send_json({"run": run}, HTTPStatus.CREATED)
            return
        if parsed.path == "/api/scheduler":
            body = self.read_json()
            try:
                status = configure_scheduler(body)
                self.send_json({"scheduler": status})
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/scheduler/run-now":
            try:
                run = trigger_scheduler_run(reason="manual_run_now")
                self.send_json({"run": run, "scheduler": scheduler_status()}, HTTPStatus.CREATED)
            except ValueError as exc:
                self.send_json({"error": str(exc), "scheduler": scheduler_status()}, HTTPStatus.BAD_REQUEST)
            except RuntimeError:
                self.send_json(
                    {"error": "A run is already active.", "active_runs": sorted(ACTIVE_RUNS)},
                    HTTPStatus.CONFLICT,
                )
            return
        if parsed.path == "/api/testnet-drill":
            body = self.read_json()
            try:
                status = configure_testnet_drill(body)
                self.send_json({"testnet_drill": compact_testnet_drill_status(status)})
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/testnet-drill/run-now":
            body = self.read_json()
            try:
                cycle = execute_testnet_drill_cycle(
                    reason="manual_run_now",
                    dry_run=coerce_bool(body.get("dry_run", False)),
                )
                self.send_json({"cycle": cycle, "testnet_drill": compact_testnet_drill_status()}, HTTPStatus.CREATED)
            except RuntimeError:
                self.send_json(
                    {"error": "A run is already active.", "active_runs": sorted(ACTIVE_RUNS)},
                    HTTPStatus.CONFLICT,
                )
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self.send_json(
                    {"error": str(exc), "error_type": exc.__class__.__name__},
                    HTTPStatus.BAD_REQUEST,
                )
            return
        if parsed.path == "/api/server-live-readiness/run":
            body = self.read_json()
            try:
                status = start_server_live_readiness(body)
                self.send_json({"server_live_readiness": status}, HTTPStatus.CREATED)
            except RuntimeError as exc:
                self.send_json(
                    {"error": str(exc), "server_live_readiness": server_live_readiness_status()},
                    HTTPStatus.CONFLICT,
                )
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/go-live-gate/check":
            gate = go_live_gate_status()
            insert_event(
                "system",
                "system",
                "Go-live Gate",
                "实盘准入门禁已检查",
                (
                    f"状态={gate['status']}，阻塞项={len(gate['blocking_gates'])}，"
                    f"可启用实盘={gate['ready_to_enable_live']}，可真实下单={gate['ready_for_live_order']}。"
                ),
                gate,
            )
            self.send_json({"go_live_gate": gate}, HTTPStatus.CREATED)
            return
        if parsed.path == "/api/live-pilot/run":
            body = self.read_json()
            try:
                result = execute_live_pilot_order(body)
                self.send_json(result, HTTPStatus.CREATED)
            except RuntimeError:
                self.send_json(
                    {"error": "A run is already active.", "active_runs": sorted(ACTIVE_RUNS)},
                    HTTPStatus.CONFLICT,
                )
            except ValueError as exc:
                self.send_json({"error": str(exc), "live_pilot": live_pilot_status(body.get("symbol", "BTCUSDT"))}, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/live-arming/arm":
            body = self.read_json()
            try:
                arming = arm_live_trading(body)
                self.send_json(
                    {"live_arming": arming, "go_live_gate": go_live_gate_status()},
                    HTTPStatus.CREATED,
                )
            except ValueError as exc:
                self.send_json({"error": str(exc), "go_live_gate": go_live_gate_status()}, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/live-arming/disarm":
            body = self.read_json()
            arming = disarm_live_trading(str(body.get("reason") or "manual_disarm"))
            self.send_json({"live_arming": arming, "go_live_gate": go_live_gate_status()})
            return
        if parsed.path == "/api/live-attestation":
            body = self.read_json()
            try:
                attestation = save_live_attestation(body)
                self.send_json(
                    {"live_attestation": attestation, "go_live_gate": go_live_gate_status()},
                    HTTPStatus.CREATED,
                )
            except ValueError as exc:
                self.send_json(
                    {"error": str(exc), "live_attestation": live_attestation_status(), "go_live_gate": go_live_gate_status()},
                    HTTPStatus.BAD_REQUEST,
                )
            return
        if parsed.path == "/api/live-attestation/clear":
            body = self.read_json()
            attestation = clear_live_attestation(str(body.get("reason") or "manual_clear"))
            self.send_json({"live_attestation": attestation, "go_live_gate": go_live_gate_status()})
            return
        if parsed.path == "/api/ai-operator/chat":
            body = self.read_json()
            try:
                result = handle_ai_operator_chat(str(body.get("message") or ""))
                self.send_json(result, HTTPStatus.CREATED)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/risk":
            body = self.read_json()
            status = configure_risk(body)
            insert_event(
                "system",
                "system",
                "Risk Center",
                "风控设置已更新",
                "风控限制已通过控制台或 smoke test 更新。",
                status,
            )
            self.send_json({"risk": status})
            return
        if parsed.path == "/api/oms/reconcile":
            summary = reconcile_recent_orders(limit=100)
            insert_event(
                "system",
                "system",
                "OMS",
                "订单对账已完成",
                "最近订单已基于本地纸交易或测试网验证状态完成对账。",
                summary["summary"],
            )
            self.send_json(summary)
            return
        if parsed.path == "/api/alerts/check":
            self.send_json(run_watchdog_checks())
            return
        if parsed.path == "/api/alerts/test-delivery":
            self.send_json(send_test_alert_delivery(), HTTPStatus.CREATED)
            return
        if parsed.path.startswith("/api/alerts/") and parsed.path.endswith("/ack"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) != 4:
                self.send_json({"error": "Invalid alert acknowledge path."}, HTTPStatus.BAD_REQUEST)
                return
            try:
                alert = acknowledge_alert(parts[2])
                self.send_json({"alert": alert, "alerts": run_watchdog_checks()})
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path.startswith("/api/alerts/") and parsed.path.endswith("/resolve"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) != 4:
                self.send_json({"error": "Invalid alert resolve path."}, HTTPStatus.BAD_REQUEST)
                return
            try:
                alert = resolve_alert_by_id(parts[2])
                self.send_json({"alert": alert, "alerts": run_watchdog_checks()})
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/exchange/recover":
            report = recover_exchange_state(trigger="manual")
            insert_event(
                "system",
                "system",
                "Exchange Recovery",
                "交易所恢复同步已执行",
                "系统已完成订单对账、可用账户快照同步和私有流保活检查。",
                report,
            )
            self.send_json({"exchange_recovery": exchange_recovery_status(), "report": report})
            return
        if parsed.path == "/api/exchange/account-sync":
            body = self.read_json()
            mode = str(body.get("mode") or "binance_testnet_validate").lower().strip()
            try:
                snapshot = sync_exchange_account_snapshot(mode)
                self.send_json({"snapshot": snapshot, "exchange_recovery": exchange_recovery_status()})
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self.send_json(
                    {"error": str(exc), "error_type": exc.__class__.__name__},
                    HTTPStatus.BAD_REQUEST,
                )
            return
        if parsed.path == "/api/exchange/flatten-positions":
            body = self.read_json()
            mode = str(body.get("mode") or "binance_testnet_place_order").lower().strip()
            dry_run = coerce_bool(body.get("dry_run", True))
            try:
                result = binance_flatten_positions(
                    mode,
                    dry_run=dry_run,
                    confirmation=str(body.get("confirmation") or ""),
                )
                self.send_json({"flatten": result, "exchange_recovery": exchange_recovery_status()}, HTTPStatus.CREATED)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self.send_json(
                    {"error": str(exc), "error_type": exc.__class__.__name__},
                    HTTPStatus.BAD_REQUEST,
                )
            return
        if parsed.path == "/api/user-stream/start":
            body = self.read_json()
            mode = str(body.get("mode") or "binance_testnet_validate").lower().strip()
            try:
                status = start_binance_user_stream(mode)
                self.send_json({"user_stream": status, "exchange_recovery": exchange_recovery_status()})
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self.send_json(
                    {"error": str(exc), "error_type": exc.__class__.__name__},
                    HTTPStatus.BAD_REQUEST,
                )
            return
        if parsed.path == "/api/user-stream/keepalive":
            try:
                status = keepalive_binance_user_stream()
                self.send_json({"user_stream": status, "exchange_recovery": exchange_recovery_status()})
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self.send_json(
                    {"error": str(exc), "error_type": exc.__class__.__name__},
                    HTTPStatus.BAD_REQUEST,
                )
            return
        if parsed.path == "/api/user-stream/close":
            try:
                status = close_binance_user_stream()
                self.send_json({"user_stream": status, "exchange_recovery": exchange_recovery_status()})
            except Exception as exc:
                self.send_json(
                    {"error": str(exc), "error_type": exc.__class__.__name__},
                    HTTPStatus.BAD_REQUEST,
                )
            return
        if parsed.path.startswith("/api/orders/") and parsed.path.endswith("/reconcile"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) != 4:
                self.send_json({"error": "Invalid order reconcile path."}, HTTPStatus.BAD_REQUEST)
                return
            try:
                order = reconcile_order(parts[2])
                self.send_json({"order": order})
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path.startswith("/api/orders/") and parsed.path.endswith("/cancel"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) != 4:
                self.send_json({"error": "Invalid order cancel path."}, HTTPStatus.BAD_REQUEST)
                return
            try:
                order = cancel_testnet_order(parts[2])
                insert_event(
                    order["run_id"],
                    "order",
                    "OMS",
                    "Binance 订单已撤单",
                    f"订单 {order['id']} 已请求 Binance 撤单，交易所状态为 {order.get('venue_status') or '-'}。",
                    {"order": order},
                )
                self.send_json({"order": order})
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self.send_json(
                    {"error": str(exc), "error_type": exc.__class__.__name__},
                    HTTPStatus.BAD_REQUEST,
                )
            return
        if parsed.path == "/api/backtests":
            body = self.read_json()
            symbol = str(body.get("symbol") or "BTCUSDT").upper().strip()
            interval = str(body.get("interval") or "15m").lower().strip()
            bars = int(body.get("bars") or 240)
            try:
                result = execute_backtest(symbol, interval, bars)
                self.send_json(result, HTTPStatus.CREATED)
            except Exception as exc:
                self.send_json(
                    {"error": str(exc), "error_type": exc.__class__.__name__},
                    HTTPStatus.BAD_REQUEST,
                )
            return
        if parsed.path == "/api/backtests/compare":
            body = self.read_json()
            symbol = str(body.get("symbol") or "BTCUSDT").upper().strip()
            interval = str(body.get("interval") or "15m").lower().strip()
            bars = int(body.get("bars") or 240)
            try:
                comparison = execute_backtest_comparison(symbol, interval, bars)
                self.send_json({"comparison": comparison}, HTTPStatus.CREATED)
            except Exception as exc:
                self.send_json(
                    {"error": str(exc), "error_type": exc.__class__.__name__},
                    HTTPStatus.BAD_REQUEST,
                )
            return
        if parsed.path == "/api/backtests/walkforward":
            body = self.read_json()
            symbol = str(body.get("symbol") or "BTCUSDT").upper().strip()
            interval = str(body.get("interval") or "15m").lower().strip()
            bars = int(body.get("bars") or 240)
            try:
                walkforward = execute_walkforward(symbol, interval, bars)
                self.send_json({"walkforward": walkforward}, HTTPStatus.CREATED)
            except Exception as exc:
                self.send_json(
                    {"error": str(exc), "error_type": exc.__class__.__name__},
                    HTTPStatus.BAD_REQUEST,
                )
            return
        if parsed.path == "/api/emergency-stop":
            set_setting("emergency_stop", "true")
            self.send_json({"emergency_stop": True})
            return
        if parsed.path == "/api/panic-stop":
            body = self.read_json()
            try:
                report = emergency_panic_stop(body)
                self.send_json(
                    {
                        "panic_stop": report,
                        "risk": risk_config(),
                        "live_arming": live_arming_status(),
                        "go_live_gate": go_live_gate_status(),
                    },
                    HTTPStatus.CREATED,
                )
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/reset-emergency-stop":
            body = self.read_json()
            report = reset_emergency_stop(str(body.get("reason") or "manual_reset"))
            self.send_json({"emergency_stop": False, "reset": report, "alerts": run_watchdog_checks()})
            return
        if parsed.path.startswith("/api/positions/") and parsed.path.endswith("/close"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) != 4:
                self.send_json({"error": "Invalid position close path."}, HTTPStatus.BAD_REQUEST)
                return
            position_id = parts[2]
            body = self.read_json()
            reason = str(body.get("reason") or "manual_close")[:80]
            try:
                closed = close_paper_position(position_id, reason=reason)
                account_state = paper_account_state()
                insert_event(
                    closed["run_id"],
                    "account",
                    "Paper Position Ledger",
                    "持仓已关闭",
                    (
                        f"已按 {closed['exit_price']} 关闭持仓 {closed['id']}，"
                        f"已实现 PnL 为 {closed['realized_pnl']} USDT。"
                    ),
                    {"position": closed, "account": account_state["account"]},
                )
                self.send_json(
                    {
                        "position": closed,
                        "account": account_state["account"],
                    }
                )
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)


def main() -> None:
    init_db()
    try:
        disarm_live_arming_on_startup()
    except Exception as exc:
        report = {
            "action": "failed",
            "reason": "startup_disarm_failed",
            "checked_at": utc_now(),
            "error_type": exc.__class__.__name__,
            "error": str(exc),
        }
        set_setting("live_startup_disarm_last_at", report["checked_at"])
        set_setting("live_startup_disarm_last_report", json.dumps(report, ensure_ascii=False))
    try:
        recover_exchange_state(trigger="startup")
    except Exception as exc:
        report = {
            "trigger": "startup",
            "completed_at": utc_now(),
            "errors": [f"{exc.__class__.__name__}: {exc}"],
            "warnings": [],
        }
        set_setting("exchange_recovery_last_at", report["completed_at"])
        set_setting("exchange_recovery_last_report", json.dumps(report, ensure_ascii=False))
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()
    testnet_drill_thread = threading.Thread(target=testnet_drill_loop, daemon=True)
    testnet_drill_thread.start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Crypto Contract AI Trader local dashboard: http://{HOST}:{PORT}")
    print(f"Project root: {ROOT_DIR}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
