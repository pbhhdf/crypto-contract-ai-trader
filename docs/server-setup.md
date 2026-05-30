# Server Setup Plan

This deployment keeps the current Chinese MVP intact: paper trading, deterministic
risk, OMS reconciliation, backtests, scheduler, and Binance Futures Testnet
validation first. Live trading exists only as guarded `live_guarded` and remains
locked until the Go-live gate and short-lived arming both pass.

## Recommended Server

- Ubuntu Server 24.04 LTS
- amd64 / x86_64
- 4 vCPU
- 16 GB RAM
- 160 GB SSD

## Network Model

Use Tailscale first. The dashboard must not be exposed directly on a public
interface.

Two supported private access modes:

- Direct tailnet bind: set `TRADER_BIND_IP` to the server's Tailscale IPv4.
- Tailscale Serve / SSH tunnel: keep `TRADER_BIND_IP=127.0.0.1`.

Never use `TRADER_BIND_IP=0.0.0.0` for this MVP server profile.

## Host Preparation

From the workstation, create a clean deployment bundle before copying code to
the server:

```bash
python3 scripts/export_server_bundle.py
```

The zip is written under `reports/server-bundles/` and excludes `.env`, runtime
databases, backups, and generated reports. Copy that zip to the server, extract
it, then continue from the repository root on the server:

The dashboard button `导出部署包` calls `GET /api/server-bundle` and downloads
the same zip through the authenticated UI when the service is already running.

```bash
sudo bash deploy/setup-ubuntu-tailscale.sh
sudo bash deploy/setup-ubuntu-time-sync.sh
```

The script installs Docker Engine, Tailscale, and UFW, then allows SSH and port
`8787` only on `tailscale0`. It prints the Tailscale IPv4 address to place in
`.env`.

The time-sync script installs and starts `chrony`, adds an application-specific
Chrony config, runs a step correction, then verifies Binance `serverTime`
drift. Do not enable live mode until this command passes:

```bash
BINANCE_TIME_DRIFT_REQUIRE_PASS=true python3 scripts/check_binance_time_drift.py
```

## Environment

```bash
cp deploy/server.env.example .env
nano .env
```

Required server values:

```bash
APP_ENV=server
APP_HOST=0.0.0.0
APP_PORT=8787
APP_BASIC_AUTH_USER=<choose-user>
APP_BASIC_AUTH_PASSWORD=<choose-long-random-password>
TRADER_BIND_IP=<tailscale-ipv4>
AI_PROVIDER=rules
AI_OPERATOR_PROVIDER=rules
EXCHANGE_MODE=paper
ENABLE_BINANCE_TESTNET=false
BINANCE_PLACE_TESTNET_ORDERS=false
AI_OPERATOR_ALLOW_FILE_READ=true
AI_OPERATOR_ALLOW_FILE_WRITE=true
AI_OPERATOR_ALLOW_SHELL=true
AI_OPERATOR_APPLY_MODEL_FILE_ACTIONS=true
AI_OPERATOR_SNAPSHOT_WRITES=true
AI_OPERATOR_SNAPSHOT_DIR=data/ai_operator_snapshots
AI_OPERATOR_BACKUP_BEFORE_SHELL=true
AI_OPERATOR_SHELL_BACKUP_DIR=reports/ai_operator_backups
AI_OPERATOR_SHELL_BACKUP_TIMEOUT_SECONDS=45
MAX_ORDER_NOTIONAL_USDT=1000
EXCHANGE_ACCOUNT_SNAPSHOT_MAX_AGE_SECONDS=30
LIVE_ARMING_MAX_ORDERS=1
LIVE_ATTESTATION_MAX_AGE_DAYS=30
LIVE_PILOT_MAX_WALLET_USDT=5000
GO_LIVE_MIN_WALKFORWARD_FOLDS=2
GO_LIVE_MIN_WALKFORWARD_TOTAL_RETURN_PCT=0
GO_LIVE_MIN_WALKFORWARD_POSITIVE_FOLD_RATE_PCT=50
GO_LIVE_MAX_WALKFORWARD_DRAWDOWN_PCT=10
BINANCE_MAX_TIME_DRIFT_MS=1000
BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER=true
BINANCE_TARGET_MARGIN_TYPE=ISOLATED
BINANCE_SYNC_LEVERAGE_BEFORE_ORDER=true
BINANCE_REQUIRE_ONE_WAY_POSITION_MODE=true
```

`APP_BASIC_AUTH_PASSWORD` must be at least 16 characters. Exchange API keys are
not needed for paper mode. The AI operator profile above is intentionally
powerful: it can edit files and run shell commands as the service user, so keep
the UI behind Tailscale and Basic Auth. Change `AI_OPERATOR_PROVIDER` to `codex`
or `openai` and set `OPENAI_API_KEY` only when you want model-generated file
actions; direct commands such as `/read`, `/replace`, and `/shell` work in
`rules` mode.
The same chat window also exposes go-live control commands: `/readiness`,
`/go-live`, `/final-live-ready --prearm`, `/server-readiness`,
`/server-readiness-run --testnet --cycles 24 --interval 60`,
`/env-audit live_guarded`, `/resolve-live-blockers`, `/launch-plan`, `/handoff`, `/launch-kit`,
`/env-pack`, `/live-pilot BTCUSDT`, `/live-postflight BTCUSDT`,
`/panic-stop --confirm PANIC_STOP`,
`/live-pilot-run BTCUSDT --confirm LAUNCH_LIVE_PILOT`, `/bundle`, and
`/server-audit`. They let the operator inspect blockers, run the emergency stop,
audit the live `.env` profile with secret redaction, produce a staged live launch plan, live operator handoff, and stage-specific env templates, run the
unattended readiness runner, translate current blockers into server env vars,
commands, and required evidence, check, submit, or postflight-review the first guarded live workflow,
and export evidence from the UI without bypassing the live gate, risk engine,
OMS, or short arming window.
Operator read and shell transcripts are secret-redacted before they reach the
browser or audit chain. `.env` assignments and JSON fields whose names contain
`SECRET`, `PASSWORD`, `TOKEN`, `API_KEY`, `WEBHOOK_URL`, or `CHAT_ID` are shown
as `[REDACTED:<name>:<fingerprint>]`, so Codex keeps high file/shell authority
without exposing Binance/OpenAI credentials in the UI.

Before starting Docker on the server, you can audit the `.env` profile without
printing secrets:

```bash
python3 scripts/live_env_profile.py --env-file .env --target mvp_server --strict
python3 scripts/live_env_profile.py --env-file .env --target live_guarded
```

The dashboard exposes the same check at `GET /api/live-env-profile` and in the
实盘准入门禁 panel. The output lists missing variable names and stable secret
fingerprints, never raw key or password values.

The dashboard button `导出上线计划` calls `GET /api/live-launch-plan` and
downloads the staged live launch plan as Markdown. The same data can be written
on the server with:

```bash
python3 scripts/export_live_launch_plan.py
```
With `AI_OPERATOR_SNAPSHOT_WRITES=true`, every operator write, append, replace,
or restore first stores the previous file under `AI_OPERATOR_SNAPSHOT_DIR`; use
`/restore <snapshot_path> [target_path]` in the chat window to roll back a file.
Use `/patch` with a Codex-style `*** Begin Patch` block when a change should
touch multiple files in one audited action; each updated or deleted file gets a
pre-write snapshot before the patch is applied.
With `AI_OPERATOR_BACKUP_BEFORE_SHELL=true`, every operator `/shell` command
first creates a restorable runtime-state backup under
`AI_OPERATOR_SHELL_BACKUP_DIR`. The final live verifier requires this when
server Shell access is enabled.
Keep `MAX_ORDER_NOTIONAL_USDT` low during the first live pilot. It is an
absolute per-order notional cap layered on top of percentage sizing and leverage
limits.
`EXCHANGE_ACCOUNT_SNAPSHOT_MAX_AGE_SECONDS=30` requires Binance testnet/live
orders to be sized from a just-synced exchange account snapshot.
`LIVE_ARMING_MAX_ORDERS=1` makes each live arming a one-entry-order budget;
protection orders are submitted by the OMS as part of that entry workflow.
The app disarms any still-active persisted live arming window on startup with
reason `startup_disarm`, so a service restart cannot carry an unspent live
authorization into the new process.
If Binance accepts the entry but a protective stop-loss/take-profit submit
fails, the OMS protection-failure guard disarms the live window, records a
critical alert/audit event, and tries to cancel the entry order. Already
submitted child protection orders are canceled only when the entry cancellation
is confirmed; otherwise they remain in place and the parent stays
`needs_reconcile` for manual venue review.
Before the entry reaches the book in real Testnet or guarded live mode, the OMS
also sends `/fapi/v1/order/test` for the entry and both protective orders. Any
test rejection fails closed before a real entry order is submitted.
When a parent entry order is canceled after child protection orders exist, the
OMS cascades cancellation to those child orders and includes the child attempts
in the parent cancel evidence.
`LIVE_ATTESTATION_MAX_AGE_DAYS=30` makes the live gate require a fresh UI/API
attestation that withdrawal permission is disabled, the live key is IP
whitelisted to the server egress IP, jurisdiction and exchange terms are
acceptable, a fresh backup/go-live report is copied off-server, and the first
pilot capital cap is intentionally small.
`LIVE_PILOT_MAX_WALLET_USDT=5000` makes the go-live gate compare the latest
live account snapshot against the first-pilot wallet cap before live can be
armed.
The `GO_LIVE_MIN_WALKFORWARD_*` thresholds make the go-live gate check strategy
quality, not only that a walk-forward run exists. The default blocks live when
the latest result has fewer than two folds, negative total return, less than
50% positive folds, or more than 10% fold drawdown.
The current MVP walk-forward engine evaluates a multi-signal candidate grid
over each training window, including SMA trend, SMA mean reversion, momentum,
momentum reversion, breakout, and breakout reversion, then scores the selected
candidate only on the following out-of-sample test window.
Use the strategy quality sweep before live mode to avoid relying on a single
symbol/interval sample. It evaluates several market/timeframe candidates
against the same go-live thresholds and writes an audit report:

```bash
python3 scripts/run_strategy_quality_sweep.py --symbols BTCUSDT,ETHUSDT,SOLUSDT --intervals 5m,15m,1h --bars 240
```

Only when a candidate passes the configured thresholds should you promote it as
the current dashboard/go-live candidate:

```bash
python3 scripts/run_strategy_quality_sweep.py --symbols BTCUSDT,ETHUSDT,SOLUSDT --intervals 5m,15m,1h --bars 240 --promote-best
```

The report records every tested candidate and the threshold failures, so this is
a candidate-selection audit trail rather than a looser gate.
`BINANCE_MAX_TIME_DRIFT_MS=1000` makes the go-live gate compare local time with
Binance `serverTime`; signed live requests stay blocked when drift is too high.
`BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER=true` and
`BINANCE_TARGET_MARGIN_TYPE=ISOLATED` make the OMS set the Binance symbol to
isolated margin before any real testnet or live entry order.
`BINANCE_SYNC_LEVERAGE_BEFORE_ORDER=true` makes the OMS call Binance
`/fapi/v1/leverage` before any real testnet or live entry order, then records
the response in the order audit trail.
`BINANCE_REQUIRE_ONE_WAY_POSITION_MODE=true` makes the go-live gate require a
fresh Binance position-mode check proving the account is in One-way mode before
live can be armed.

For unattended operation, configure at least one external alert channel before
requesting live mode:

```bash
ALERT_WEBHOOK_ENABLED=true
ALERT_WEBHOOK_URL=<internal-webhook-url>
# or
ALERT_TELEGRAM_ENABLED=true
ALERT_TELEGRAM_BOT_TOKEN=<telegram-bot-token>
ALERT_TELEGRAM_CHAT_ID=<telegram-chat-id>
# or
ALERT_EMAIL_ENABLED=true
ALERT_EMAIL_SMTP_HOST=<smtp-host>
ALERT_EMAIL_FROM=<alerts-from-address>
ALERT_EMAIL_TO=<operator-address>
```

## Deploy

```bash
bash deploy/deploy-server.sh
docker compose -f deploy/docker-compose.yml ps
```

`deploy/deploy-server.sh` is the preferred server entrypoint. It validates that
`.env` uses `APP_ENV=server`, strong Basic Auth, a private `TRADER_BIND_IP`,
shell backups for the high-permission AI operator, and locked live defaults.
It then starts Docker Compose, waits for `/api/health`, runs
`deploy/verify-server.sh`, exports `server-go-live-audit`, `live-launch-plan`,
`live-ops-handoff`, a fresh server bundle, the live environment template pack,
and the combined live launch kit, then creates a runtime backup. If live flags are already present, the script refuses to proceed unless
`TRADER_ALLOW_LIVE_DEPLOY=true` is set; in that case it also runs the pre-arm
final live verifier and still requires short live arming before any real order.

Open the UI through Tailscale:

```text
http://<tailscale-ipv4>:8787
```

Use the Basic Auth username and password from `.env`.

## Verification

Run:

```bash
bash deploy/verify-server.sh
```

Check that the deployment profile scripts and examples still preserve the
Tailscale-first, Basic Auth, backup, and live-lock invariants:

```bash
python3 scripts/check_server_deploy_profile.py
```

To let the server gather all available pre-live evidence unattended, run:

```bash
python3 scripts/run_server_live_readiness.py --run-testnet-drill --target-cycles 24 --interval-seconds 60
```

The runner validates the server profile, runs the full regression suite,
promotes the best passing multi-market strategy candidate, optionally advances
the real Binance Testnet drill counter, exports go-live/server-audit reports,
exports the staged live launch plan, live operator handoff, server bundle, live
environment pack, and combined live launch kit, creates a backup, and
finishes by printing the remaining final-live blockers.
It never arms live trading or bypasses the go-live gate.

From the authenticated dashboard, use `启动准入推进器` for the same unattended
server path. The UI calls `POST /api/server-live-readiness/run` and refreshes
`GET /api/server-live-readiness` so the status, report path, and remaining
blockers are visible without SSH. The `包含真实 Testnet` toggle should only be
enabled after Binance Futures Testnet keys are configured; live trading still
requires the separate go-live gate, human attestation, and short arming window.

Use `/env-pack` in the AI operator chat or `导出环境模板` in the dashboard to
download stage-specific `.env` templates. Use `/launch-kit` or `导出上线套件` to
download one zip containing the deployable server bundle, the latest
go-live/server-audit evidence, and the environment template pack. These packs
intentionally exclude filled `.env`, runtime databases, backups, and API secrets.

Then export evidence and back up state:

```bash
python3 scripts/export_server_bundle.py
python3 scripts/export_live_launch_kit.py
python3 scripts/export_go_live_report.py
python3 scripts/server_go_live_audit.py
bash deploy/backup-server.sh
python3 scripts/check_restore_state.py
```

`scripts/server_go_live_audit.py` writes `reports/server-go-live-audit-*.json`
and `.md`. It is non-strict by default so it can document blockers before live
is ready; set `TRADER_SERVER_AUDIT_STRICT=true` when the audit must fail unless
the armed final-live check is green.

When `live_guarded` is configured, use the hard final verifier immediately
before the first real order. It exits non-zero unless the server is in live
mode, every gate/checklist item passes, the manual attestation is fresh, the
Codex/operator console has file and shell control, and the short arming window
is active:

```bash
python3 scripts/check_final_live_ready.py
```

The dashboard exposes the same check with the `最终实盘检查` button, and the
read-only API form is `GET /api/final-live-ready`.
The `导出服务器审计包` button calls `GET /api/server-go-live-audit` and downloads
the same bundled health/readiness/gate/operator/go-live evidence from the UI.

For a pre-arm rehearsal that allows only the short-arming item to remain open:

```bash
TRADER_FINAL_LIVE_REQUIRE_ARMED=false python3 scripts/check_final_live_ready.py
```

This runs:

- `python3 scripts/preflight.py`
- `python3 scripts/check_binance_time_drift.py`
- `python3 scripts/check_ui_chinese.py`
- `python3 scripts/run_all_checks.py`

Readiness should be `pass` or a clearly explained `warn`. Any `fail` must be
fixed before enabling Binance Testnet validation.

## Backup And Restore

Create a backup before every risky server change:

```bash
bash deploy/backup-server.sh
```

Validate a backup archive without replacing the active database:

```bash
python3 scripts/restore_state.py --backup reports/backups/trader-state-backup-YYYYMMDDTHHMMSSZ.zip --dry-run
```

Restore only during a maintenance window. The wrapper stops Docker Compose,
restores `data/trader.db`, then starts the service again:

```bash
bash deploy/restore-server.sh reports/backups/trader-state-backup-YYYYMMDDTHHMMSSZ.zip
```

After restore, run:

```bash
python3 scripts/preflight.py
TRADER_BASE_URL=http://127.0.0.1:8787 python3 scripts/run_all_checks.py
```

## Binance Testnet Validation

Only after paper mode is stable:

```bash
nano .env
```

Set:

```bash
ENABLE_BINANCE_TESTNET=true
BINANCE_API_KEY=<binance-futures-testnet-key>
BINANCE_API_SECRET=<binance-futures-testnet-secret>
BINANCE_PLACE_TESTNET_ORDERS=false
```

Restart:

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

Verify:

```bash
TRADER_CHECK_TESTNET=true bash deploy/verify-server.sh
```

Then run the continuous Testnet drill runner until the real drill counter meets
the go-live requirement. In validation mode this sends signed Binance Futures
Testnet `/fapi/v1/order/test` requests and does not create real Testnet orders:

```bash
python3 scripts/run_testnet_drill_until_ready.py --mode binance_testnet_validate --target-cycles 24 --interval-seconds 60
```

The runner writes `reports/testnet-drill-runner-*.json` with each cycle, final
counter values, and the remaining go-live blockers. If you intentionally switch
to `binance_testnet_place_order`, add `--allow-testnet-placement`; that mode can
create and then reconcile/cancel real Testnet orders.

Expected result:

- UI offers `Binance 测试网验证`.
- The workflow calls Binance `/fapi/v1/order/test`.
- OMS shows `已验证，无真实订单`.
- No real testnet order is placed.

## Safety Gate

Do not add live mode until all are true:

1. The app is running with `APP_ENV=server`, strong Basic Auth, and a private
   `TRADER_BIND_IP` such as the Tailscale IPv4 address.
2. Paper mode has run long enough to inspect failure modes.
3. Real Binance Testnet validation or placement, not dry-run, has completed the required drill cycles.
4. OMS reconciliation, alert watchdog, exchange recovery, and audit hash chain pass.
5. Webhook, Telegram, or SMTP email alert delivery is configured.
6. Emergency stop blocks new orders.
7. Panic stop has been exercised from the UI/API; it must disable scheduler/Testnet drill, disarm live trading, and attempt OMS cancellation for non-terminal Binance orders.
8. Exchange-level emergency controls have been checked: cancel-all by symbol and flatten-plan generation must work; actual flatten submission must require `FLATTEN_POSITIONS`.
9. API keys have withdrawal disabled and IP whitelist enabled.
10. The server can reach Binance Futures/Testnet from its region.
11. Chrony/NTP is active and
    `BINANCE_TIME_DRIFT_REQUIRE_PASS=true python3 scripts/check_binance_time_drift.py`
    passes.
12. A fresh backup and `go-live-report-*.json` have been copied off the server.
13. The dashboard/API `实盘人工证据` attestation has been saved with
    `LIVE_ATTESTATION_CONFIRMED`.
14. Backup dry-run restore and restore smoke checks pass.
