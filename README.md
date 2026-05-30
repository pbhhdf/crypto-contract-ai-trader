# Crypto Contract AI Trader

Local-first control room for an AI-assisted crypto perpetual futures workflow.

This first version is intentionally conservative:

- Local paper mode only.
- No real exchange keys are required.
- No real AI API is required yet.
- Binance USD-M Futures public market data is used by default.
- If the public endpoint is unavailable, the workflow falls back to synthetic data and records the reason.
- The AI decision layer is pluggable. It uses deterministic rules by default, and can call OpenAI Structured Outputs when configured.
- The research layer now exposes auditable research artifacts inspired by Anthropic financial-services boundaries and TradingAgents structured communication.
- The production architecture blueprint includes dedicated Anthropic and TradingAgents reference breakdowns plus a synthesis rule: use them for research/governance, not as the live execution engine.
- The blueprint also exposes the recommended four-plane architecture, the structured production graph, venue-specific adapter rule, and the research/ deterministic strategy-engine split.
- The key module definition table is preserved as an exact API/UI artifact before the expanded implementation matrix.
- The implementation-notes table is also preserved as an exact topic/basis/recommendation artifact before the expanded status table.
- The entity relationship blueprint preserves the exact Mermaid ER diagram source alongside the entity and relationship tables.
- The control-room information architecture preserves the exact workbench navigation tree before the navigation cards.
- The UI page component table is preserved as an exact page/components/design-focus artifact.
- The AI operator console adds a Chinese chat window plus audited workspace tools (`/list`, `/read`, `/write`, `/append`, `/replace`, `/patch`, `/restore`, `/shell`) and live-readiness commands (`/readiness`, `/go-live`, `/resolve-live-blockers`, `/final-live-ready`, `/server-readiness-run`, `/env-audit`, `/launch-plan`, `/handoff`, `/launch-kit`, `/env-pack`, `/live-postflight`, `/bundle`, `/server-audit`) without entering the trade execution path.
- Basic Auth now rate-limits failed login attempts before the high-permission operator console can be reached; server templates expose `AUTH_FAILURE_LIMIT`, `AUTH_FAILURE_WINDOW_SECONDS`, and `AUTH_LOCKOUT_SECONDS`.
- Binance testnet support now has two guarded modes: validation calls `/fapi/v1/order/test`, and opt-in placement uses real testnet `/fapi/v1/order` with OMS reconcile/cancel support.
- Binance live support is present as `live_guarded`, but it requires separate live keys, `ENABLE_BINANCE_LIVE=true`, `BINANCE_PLACE_LIVE_ORDERS=true`, and `LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_RISK`.
- Exchange recovery now runs at startup and on demand: it reconciles recent OMS orders, can sync Binance account snapshots, manages the Binance listenKey lifecycle, and runs a Binance private user-data WebSocket consumer when credentials are configured.
- Paper orders now create an auditable paper position ledger with margin, exposure, unrealized PnL, and manual close/realized PnL.
- Risk limits are visible and editable from the local dashboard, with emergency-stop rejection covered by a smoke test.
- The dashboard also exposes a confirmed panic stop: it sets emergency stop, disables scheduler/Testnet drill, disarms live trading, and attempts to cancel non-terminal Binance testnet/live OMS orders.
- Exchange-level emergency controls can cancel all open Binance orders by symbol and generate reduce-only flatten plans from the synced account snapshot; real flatten submission requires `FLATTEN_POSITIONS`.
- OMS reconciliation tracks client order IDs, venue status, reconciliation status, and last reconcile notes.
- The alert watchdog records critical/warning conditions for emergency stop, scheduler errors, OMS unknown states, stale recovery, and private stream health.
- Alert delivery can send opened/resolved alerts to Webhook, Telegram, and SMTP email channels and records every delivery attempt for audit.
- The Testnet drill panel can schedule repeated Binance Testnet validation/placement rehearsals, then run OMS recovery, alert checks, and private-stream health summaries for each auditable cycle.
- Real Testnet drill cycles now require order evidence before incrementing the go-live counter; dry-runs and completed workflows without accepted `/order/test` or cleaned-up placement orders do not count as real rehearsal cycles.
- Testnet drill cycle history, runner reports, and go-live evidence reports now expose `order_evidence` and `real_cycle_counted` so a server handoff can prove exactly which Binance Testnet cycle counted toward live readiness.
- The Go-live gate now blocks `live_guarded` order execution unless explicit live flags, risk limits, OMS reconciliation, alert health, recovery sync, live private stream, Testnet drill cycles, and backtest/walk-forward checks all pass.
- Stateful exchange execution now requires deterministic risk status `approved`; paper mode can still rehearse warning paths, but real Testnet placement and `live_guarded` do not submit orders on risk warnings.
- Even after the Go-live gate passes, live order execution requires a short-lived `ARM_LIVE_TRADING` authorization from the UI/API; the authorization expires automatically and has a per-arming entry-order budget.
- Binance orders are normalized against exchange `exchangeInfo` filters before signed submission, and live/testnet placement submits audited STOP_MARKET / TAKE_PROFIT_MARKET close-position protection orders.
- Paper mode sizes orders from the local ledger; Binance testnet/live modes size orders from the synced exchange account equity/free-margin snapshot and record that source in the audit trail.
- Critical events, OMS transitions, and AI operator messages are chained into a tamper-evident SQLite audit hash chain that is exposed in readiness and the dashboard.
- Server-side scheduling can run guarded paper workflows without a browser staying open.
- Every workflow step is written to SQLite for review and replay.
- The browser dashboard shows market data, agent outputs, risk checks, trade intent, account equity, open positions, orders, and raw audit events.

## Quick Start On This Machine

```powershell
cd /d E:\crypto-contract-ai-trader
py app\server.py
```

Open:

```text
http://127.0.0.1:8787
```

Click `Start Analysis` / `启动一次分析` to run the local paper workflow.

Run a local API smoke test:

```powershell
py scripts\check_public_data.py
```

Run the same test and close the newly opened paper position:

```powershell
$env:TRADER_CLOSE_POSITION="true"; py scripts\check_public_data.py
```

Run deployment preflight checks:

```powershell
py scripts\preflight.py
```

Run the server deployment profile check:

```powershell
py scripts\check_server_deploy_profile.py
```

Plan the server live-readiness runner:

```powershell
py scripts\check_server_live_readiness_runner.py
```

Audit the server environment profile without printing secrets:

```powershell
py scripts\live_env_profile.py --target live_guarded
py scripts\check_live_env_profile.py
py scripts\check_live_launch_plan.py
```

Run a historical K-line backtest smoke test:

```powershell
py scripts\check_backtest.py
```

Run a parameter comparison smoke test:

```powershell
py scripts\check_compare.py
```

Run walk-forward validation:

```powershell
py scripts\check_walkforward.py
```

The walk-forward job uses an expanding-window sample-out process over a
multi-signal candidate grid: SMA trend, SMA mean reversion, momentum, momentum
reversion, breakout, and breakout reversion. The Go-live gate still requires
the latest out-of-sample result to meet the configured fold count, total return,
positive-fold rate, and drawdown thresholds before `live_guarded` can arm.

Plan a multi-market strategy quality sweep without touching the running service:

```powershell
py scripts\check_strategy_quality_sweep.py
```

On the server, after paper/Testnet data paths are stable, run the real sweep to
evaluate multiple symbols and intervals against the current go-live
walk-forward thresholds:

```bash
python3 scripts/run_strategy_quality_sweep.py --symbols BTCUSDT,ETHUSDT,SOLUSDT --intervals 5m,15m,1h --bars 240
```

If a candidate passes and you want the dashboard/go-live gate to track that
selected symbol/interval, rerun with `--promote-best`; the report keeps the full
candidate set so the selection remains auditable.

Run a scheduler smoke test:

```powershell
py scripts\check_scheduler.py
```

Run a risk-control smoke test:

```powershell
py scripts\check_risk_controls.py
```

Run an OMS reconciliation smoke test:

```powershell
py scripts\check_oms.py
```

Run the exchange recovery smoke test:

```powershell
py scripts\check_exchange_recovery.py
```

Run the alert watchdog smoke test:

```powershell
py scripts\check_alert_watchdog.py
```

Run the external alert delivery smoke test:

```powershell
py scripts\check_alert_delivery.py
```

Run the Testnet drill control-plane smoke test without sending any Binance request:

```powershell
py scripts\check_testnet_drill.py
```

Run the local dry-run version of the continuous Testnet drill runner:

```powershell
py scripts\check_testnet_drill_runner.py
```

Run the Go-live gate smoke test:

```powershell
py scripts\check_go_live_gate.py
```

Run the panic-stop control-plane smoke test:

```powershell
py scripts\check_panic_stop.py
```

Run exchange-level emergency order/flatten parameter checks:

```powershell
py scripts\check_exchange_emergency.py
```

Run Binance exchange filter and protection-order parameter checks:

```powershell
py scripts\check_binance_filters.py
```

Run order sizing source checks:

```powershell
py scripts\check_order_sizing.py
```

Run the audit hash-chain check:

```powershell
py scripts\check_audit_chain.py
```

Run the research-artifact governance smoke test:

```powershell
py scripts\check_research_artifacts.py
```

Run the production architecture blueprint smoke test:

```powershell
py scripts\check_architecture_blueprint.py
```

Run a Binance Futures Testnet validation check after enabling testnet keys:

```powershell
$env:TRADER_CHECK_TESTNET="true"; py scripts\run_all_checks.py
```

Run a real Binance Futures Testnet placement/cancel check only after you have
enabled `BINANCE_PLACE_TESTNET_ORDERS=true`:

```powershell
$env:TRADER_CHECK_TESTNET_PLACE="true"; py scripts\run_all_checks.py
```

Run a UI Chinese copy check:

```powershell
py scripts\check_ui_chinese.py
```

Run all local deployment-readiness checks and write a JSON report under `reports/`:

```powershell
py scripts\run_all_checks.py
```

Export a go-live evidence package from the running service:

```powershell
py scripts\export_go_live_report.py
```

Write a combined server go-live audit package with health, readiness, gate,
final live checks, AI operator status, and the full evidence report:

```powershell
py scripts\server_go_live_audit.py
```

Export a deployment bundle that is safe to copy to the Ubuntu server. It includes
source, deploy scripts, docs, and examples, but intentionally excludes `.env`,
`data/`, `reports/`, databases, backups, and generated audit files:

```powershell
py scripts\export_server_bundle.py
```

The dashboard also exposes `导出部署包`, backed by `GET /api/server-bundle`,
which creates the same zip and downloads it through the authenticated UI.

Run the hard final live verifier on the server only after `live_guarded` is
configured. By default it requires the short live arming window to be active;
set `TRADER_FINAL_LIVE_REQUIRE_ARMED=false` for a pre-arm check:

```powershell
py scripts\check_final_live_ready.py
```

The same hard verifier is exposed in the dashboard by the `最终实盘检查` button
and by `GET /api/final-live-ready`. The endpoint is intentionally read-only and
returns every remaining blocker before `live_guarded` can place a real order.
The dashboard also has `导出服务器审计包`, backed by
`GET /api/server-go-live-audit`, which bundles health, readiness, gate state,
final live checks, AI operator status, and the go-live report.

Create a restorable runtime-state backup:

```powershell
py scripts\backup_state.py
```

Validate the restore path without touching the live database:

```powershell
py scripts\check_restore_state.py
```

## Current Scope

The app runs a complete paper-trading operating flow:

1. Market data snapshot
2. Market Analyst
3. Sentiment Analyst
4. News Analyst
5. Trader Agent
6. Deterministic Risk Engine
7. Paper Executor
8. Paper Position Ledger
9. Research Artifacts & Governance Boundary
10. Production Architecture Blueprint
11. Executive Summary Cards
12. Project Goals & Assumptions
13. Anthropic Reference Project Breakdown
14. TradingAgents Reference Project Breakdown
15. Reference Synthesis
16. Recommended Layered Architecture
17. Key Module Definition Table
18. Implementation Notes Table
19. Production Implementation Notes
20. Entity Relationship Blueprint
21. Mermaid ER Diagram Source
22. Control-room Information Architecture
23. Workbench Navigation Tree
24. UI Page Component Table
25. AI Operator Chat Console
26. Technical Stack & Implementation Roadmap
27. Risk Register & Acceptance Gates
28. Backtest Lab
29. Parameter Leaderboard
30. Walk-forward Validation
31. Guarded Binance Live Mode
32. Deployment Readiness
33. Exchange Recovery & Account Snapshot Sync
34. Alert Watchdog
35. Risk Center
36. OMS Reconciliation
37. Server-side Paper Scheduler
38. Binance Testnet Drill Control Plane
39. Tamper-evident audit hash chain
40. Go-live evidence report export
41. Runtime-state backup
42. Controlled runtime-state restore
43. Multi-market strategy quality sweep

The market snapshot and backtest lab use Binance public futures data first. AI and testnet
execution are isolated adapters: the AI can only produce a `TradeIntent`, and
the deterministic risk engine must approve it before the executor boundary.
Live mode remains locked by default and requires the Go-live gate before it can
submit a real order. The Go-live gate treats local mode as development only:
real live orders require `APP_ENV=server` in addition to the live flags, Basic
Auth, private network access, external alerts, Testnet drills, and short-lived
arming.

## Optional Local Configuration

Create `.env` from `.env.example` when you want to override defaults:

```powershell
copy .env.example .env
```

Safe defaults:

- `AI_PROVIDER=rules`
- `EXCHANGE_MODE=paper`
- `ENABLE_BINANCE_TESTNET=false`
- Leave `APP_BASIC_AUTH_USER` / `APP_BASIC_AUTH_PASSWORD` empty for local-only work.
- Set `APP_BASIC_AUTH_USER` / `APP_BASIC_AUTH_PASSWORD` before exposing the UI on a server.

To test the AI adapter later, set `AI_PROVIDER=openai`, `OPENAI_API_KEY`, and
`AI_MODEL`. To test signed Binance futures connectivity without placing an
order, set `ENABLE_BINANCE_TESTNET=true`, add Binance testnet keys, and choose
`Binance Testnet 验证` in the UI. To place real Binance testnet orders, also set
`BINANCE_PLACE_TESTNET_ORDERS=true` and `EXCHANGE_MODE=binance_testnet_place_order`;
the UI will then show `Binance Testnet 真实下单`, and OMS can reconcile or cancel
submitted testnet orders by `clientOrderId`.

The Testnet drill panel is the rehearsal loop for server operation. It can keep
the system in validation mode, record each cycle in SQLite, trigger exchange
recovery, summarize alert state, and show private-stream health. Local smoke
tests use `dry_run=true` so the control chain is checked without any Binance
request; dry-run cycles are tracked separately and do not satisfy the live
go-live gate. Server drills require testnet keys before the real Testnet cycle
counter can advance.

On the server, after `ENABLE_BINANCE_TESTNET=true` and Testnet keys are set, run
the continuous validation runner to advance the real Testnet drill counter with
signed `/fapi/v1/order/test` requests and write an evidence report:

```bash
python3 scripts/run_testnet_drill_until_ready.py --mode binance_testnet_validate --target-cycles 24 --interval-seconds 60
```

For `binance_testnet_place_order`, the runner requires
`--allow-testnet-placement` because that mode can create real Testnet orders.

The exchange recovery panel can run OMS recovery, sync Binance account snapshots,
start/keepalive/close the Binance user-data `listenKey`, and show only a masked
listenKey fingerprint. The private WebSocket consumer stores `ORDER_TRADE_UPDATE`
and `ACCOUNT_UPDATE` events in SQLite, updates matching OMS orders by
`clientOrderId`, and records account/position snapshots for audit.

Live trading is a separate explicit mode. To make `live_guarded` appear, set
`ENABLE_BINANCE_LIVE=true`, `BINANCE_PLACE_LIVE_ORDERS=true`,
`BINANCE_LIVE_API_KEY`, `BINANCE_LIVE_API_SECRET`, and
`LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_RISK`. Use a Binance Futures key
with withdrawals disabled and IP whitelist enabled. Even after those flags are
set, the Go-live gate must pass and the dashboard must be temporarily armed with
`ARM_LIVE_TRADING` before a live order can be sent. `LIVE_ARMING_MAX_ORDERS`
defaults to `1`, so the first live pilot consumes the temporary authorization
after one entry order.
The short live arming window is intentionally process-local in spirit: on
server startup the app checks for any still-active persisted live arming window
and disarms it with reason `startup_disarm`, so a restart cannot inherit an
unspent live order authorization.
The Go-live gate also requires a fresh `LIVE_ATTESTATION_CONFIRMED` record from
the dashboard/API. That attestation covers the items Binance APIs cannot prove
for us: withdrawal permission disabled, live key IP whitelist, jurisdiction and
exchange terms, off-server backup/report copy, and intentionally limited pilot
capital.

If an entry order is accepted but Binance rejects one of the protective
stop-loss/take-profit orders, the OMS now triggers a protection-failure guard:
it disarms the live window, raises a critical audit alert, attempts to cancel
the entry order, and cancels any already-submitted child protection orders only
after the entry cancellation is confirmed. If entry cancellation is unknown or
fails, existing child protection orders are kept for safety and the parent order
stays `needs_reconcile`; the workflow fails closed instead of silently
continuing.
Before any real Testnet or guarded live entry order is submitted, the OMS also
calls `/fapi/v1/order/test` for the entry and both protective orders. A rejected
test payload blocks before the entry order reaches the book.
When a parent entry order is canceled after protective child orders exist, the
OMS cascades cancellation to those child orders and records the child cancel
attempts on the parent cancel result.

The AI operator window is separate from the trade-intent adapter. It can chat
with you and, when enabled, operate on files under `AI_OPERATOR_WORKSPACE_ROOT`.
The server example now uses the requested high-permission operator profile:
file read, file write, replace, shell, and model-proposed file actions can all
be enabled. Use `AI_OPERATOR_PROVIDER=codex` or `openai` with `OPENAI_API_KEY`
when you want model-generated actions; keep `rules` for offline direct commands.
File writes, appends, replacements, and restores create automatic pre-write
snapshots under `AI_OPERATOR_SNAPSHOT_DIR` when `AI_OPERATOR_SNAPSHOT_WRITES=true`;
the chat supports `/restore <snapshot_path> [target_path]` for recovery.
The chat also supports `/patch` with Codex-style `*** Begin Patch` blocks for
multi-file add/update/delete edits. Each touched file is snapshotted before the
patch operation and every operator message/action is included in the audit hash
chain.
The same chat window can now operate the live-readiness control plane directly:
`/readiness` summarizes deployment readiness, `/go-live` shows the current
go-live gate blockers, `/final-live-ready --prearm` runs the hard final verifier
without requiring the short arming window, `/server-readiness` shows the last
server runner state, `/server-readiness-run --testnet --cycles 24 --interval 60`
starts the unattended evidence runner, `/env-audit live_guarded` audits the
server environment profile with secret redaction, `/resolve-live-blockers`
translates current blockers into required server env vars, commands, and
evidence, `/launch-plan` returns the
current staged live launch plan, `/handoff` returns the live operator handoff
with exact commands, evidence paths, AI commands, and emergency controls,
`/live-pilot BTCUSDT` checks whether the first
guarded live run can be submitted, `/live-postflight BTCUSDT` reviews OMS,
alerts, audit chain, exchange snapshot, and disarming evidence after the first
run, `/panic-stop --confirm PANIC_STOP` executes
the same emergency stop chain from the chat window, `/live-pilot-run BTCUSDT --confirm
LAUNCH_LIVE_PILOT` submits exactly one live-pilot workflow only after every
final live gate is already passing, `/bundle` exports the deployment zip,
`/env-pack` exports stage-specific server `.env` templates, and `/server-audit`
summarizes the combined audit package. These commands still do
not enable live flags, arm live trading, or bypass deterministic risk/OMS gates.
When `AI_OPERATOR_PROVIDER=codex` or `openai` is used, the model-facing
structured action schema exposes the same control-plane actions, including
`panic_stop`, `live_pilot_run`, `live_pilot_postflight`, server readiness, launch-plan export, file
edits, patch/restore, and shell execution. The schema is strict and includes the
required confirmation fields, so model-generated actions go through the same
guarded execution path as direct slash commands.
Read and Shell responses are redacted before they reach the chat history,
dashboard, or audit chain: values assigned to keys such as `OPENAI_API_KEY`,
`BINANCE_API_SECRET`, `BINANCE_LIVE_API_SECRET`, passwords, tokens, webhook
URLs, and chat IDs are replaced with stable `[REDACTED:<name>:<fingerprint>]`
markers. The operator still executes the requested write or shell command with
the service user's permissions; only the returned transcript is masked.
When `/shell` is enabled, `AI_OPERATOR_BACKUP_BEFORE_SHELL=true` creates a
runtime-state backup under `AI_OPERATOR_SHELL_BACKUP_DIR` before the command is
executed. The hard final live verifier requires this pre-shell backup when
Shell access is enabled.
Use that only when the UI is protected by Tailscale, strong Basic Auth, backups,
and audit review; `/shell` runs commands as the service user and is intentionally
powerful.

## Ubuntu Server MVP Deployment

Use Ubuntu Server 24.04 LTS on an amd64 host with 4 vCPU, 16 GB RAM, and 160 GB SSD.
The first server profile is Tailscale-first: do not publish the trading UI directly
to the public internet.

```bash
python3 scripts/export_server_bundle.py
sudo bash deploy/setup-ubuntu-tailscale.sh
cp deploy/server.env.example .env
# Fill APP_BASIC_AUTH_PASSWORD and TRADER_BIND_IP with the Tailscale IPv4 printed by the setup script.
bash deploy/deploy-server.sh
```

Server safety defaults:

- `APP_ENV=server`
- `AI_PROVIDER=rules`
- `EXCHANGE_MODE=paper`
- `ENABLE_BINANCE_TESTNET=false` until testnet keys are ready.
- `BINANCE_PLACE_TESTNET_ORDERS=false` until you intentionally test real Binance testnet order placement.
- `ENABLE_BINANCE_LIVE=false` and `BINANCE_PLACE_LIVE_ORDERS=false` until you intentionally enter guarded live mode.
- `TRADER_BIND_IP` must be `127.0.0.1` or a Tailscale IPv4 address, never `0.0.0.0`.
- `GO_LIVE_REQUIRE_ALERT_WEBHOOK=true` keeps live mode blocked until Webhook,
  Telegram, or SMTP email alert delivery is configured.
- `MAX_ORDER_NOTIONAL_USDT=1000` adds an absolute per-order notional cap on top
  of percentage sizing and leverage limits; keep it low for first live pilots.
- `MIN_PROTECTION_REWARD_RISK_RATIO=1.0` rejects directional orders whose
  stop-loss / take-profit geometry offers less reward distance than risk
  distance before OMS validation or Binance protection orders are built.
- `EXCHANGE_ACCOUNT_SNAPSHOT_MAX_AGE_SECONDS=30` forces Binance testnet/live
  orders to use a fresh account snapshot for sizing and margin checks.
- `LIVE_ATTESTATION_MAX_AGE_DAYS=30` expires the manual live evidence record;
  use the dashboard "实盘人工证据" panel before enabling guarded live mode.
- `LIVE_PILOT_MAX_WALLET_USDT=5000` blocks guarded live mode when the latest
  live account snapshot shows more wallet balance than the first-pilot cap.
- `GO_LIVE_MIN_WALKFORWARD_FOLDS=2`,
  `GO_LIVE_MIN_WALKFORWARD_TOTAL_RETURN_PCT=0`,
  `GO_LIVE_MIN_WALKFORWARD_POSITIVE_FOLD_RATE_PCT=50`, and
  `GO_LIVE_MAX_WALKFORWARD_DRAWDOWN_PCT=10` keep live mode blocked when the
  latest multi-signal walk-forward result is too thin, negative, one-sided, or
  too deep in drawdown.
- `BINANCE_MAX_TIME_DRIFT_MS=1000` blocks live readiness when local time drifts
  too far from Binance `serverTime`.
  On Ubuntu, run `sudo bash deploy/setup-ubuntu-time-sync.sh` to install Chrony
  and verify the drift gate before live mode.
- `BINANCE_SYNC_MARGIN_TYPE_BEFORE_ORDER=true` with
  `BINANCE_TARGET_MARGIN_TYPE=ISOLATED` sets the symbol to isolated margin
  before any real testnet or live entry order.
- `BINANCE_SYNC_LEVERAGE_BEFORE_ORDER=true` calls Binance `/fapi/v1/leverage`
  before any real testnet or live entry order, and records the exchange response
  in the order audit trail.
- `BINANCE_REQUIRE_ONE_WAY_POSITION_MODE=true` requires exchange recovery to
  verify Binance One-way position mode before live can be armed.
- `AI_OPERATOR_ALLOW_FILE_WRITE=true`, `AI_OPERATOR_ALLOW_SHELL=true`, and `AI_OPERATOR_APPLY_MODEL_FILE_ACTIONS=true` grant the browser operator broad workspace control; keep them behind private access and audit.
- `AI_OPERATOR_SNAPSHOT_WRITES=true` keeps automatic pre-write file snapshots so operator edits can be restored with `/restore`.
- `AI_OPERATOR_BACKUP_BEFORE_SHELL=true` creates a runtime-state backup before
  every operator `/shell` command; keep this on when Shell access is enabled on
  the server.

Before changing live flags, export evidence and back up state:

```bash
python3 scripts/export_server_bundle.py
python3 scripts/export_live_env_pack.py
python3 scripts/export_live_launch_kit.py
python3 scripts/export_go_live_report.py
bash deploy/backup-server.sh
```

`deploy/deploy-server.sh` is the server-side safe deploy entrypoint. It refuses
to continue unless `.env` is a server profile with strong Basic Auth, a private
`TRADER_BIND_IP`, high-permission AI operator backups, and locked live defaults.
It also runs `scripts/live_env_profile.py` so the same secret-redacted
environment profile shown in the UI is checked before Docker starts. It then
starts Docker Compose, waits for `/api/health`, runs
`deploy/verify-server.sh`, exports a server go-live audit plus
`live-launch-plan-*.md`, `live-ops-handoff-*.md`, exports a fresh server bundle,
packages the live environment templates, packages the combined
`live-launch-kit-*.zip`, and creates a backup.
If live flags are present, set `TRADER_ALLOW_LIVE_DEPLOY=true`; the script will
run the pre-arm final live verifier and still leave live orders blocked until
short live arming succeeds.

After deployment and before enabling live flags, the server can run all
available evidence gathering unattended:

```bash
python3 scripts/run_server_live_readiness.py --run-testnet-drill --target-cycles 24 --interval-seconds 60
```

That runner validates the deployment profile, executes the full check suite,
promotes the best passing strategy-quality candidate, optionally advances the
real Binance Testnet drill counter, exports the go-live/server-audit reports,
exports the staged live launch plan, live operator handoff, server bundle, live
environment pack, and combined live launch kit, creates a backup, and
prints the remaining final-live blockers. It does not
arm live trading or bypass the go-live gate.

The dashboard exposes the same path with `启动准入推进器`. It calls
`POST /api/server-live-readiness/run`, shows status from
`GET /api/server-live-readiness`, records the generated report path, and keeps
live trading locked behind the same go-live gate and short-lived arming flow.
Leave `包含真实 Testnet` off for local/server dry operations; enable it only
after Binance Futures Testnet keys are configured and validation requests are
expected.

Use `/env-pack` in the AI operator chat or the `导出环境模板` dashboard button to
produce stage-specific `.env` templates for `mvp_server`, `testnet_validate`,
`testnet_place`, and `live_guarded`. Use `/launch-kit` in the AI operator chat
or the `导出上线套件` dashboard button to produce one zip containing the
deployable server bundle plus the latest go-live report, server audit, live
launch plan, live operator handoff, and environment template pack. Both packs
intentionally exclude filled `.env`, runtime databases, backups, and API secrets.

Validate a backup before a maintenance restore:

```bash
python3 scripts/restore_state.py --backup reports/backups/trader-state-backup-YYYYMMDDTHHMMSSZ.zip --dry-run
```

Restore on the server through the wrapper, which stops the service, replaces
`data/trader.db`, and starts the service again:

```bash
bash deploy/restore-server.sh reports/backups/trader-state-backup-YYYYMMDDTHHMMSSZ.zip
```

## Next Milestones

1. Add Anthropic/local Ollama adapters.
2. Replace analyst stages with TradingAgents/LangGraph nodes.
3. Add richer historical performance reports and scheduler history controls.
4. Run multi-day Binance Testnet drill cycles with private stream reconciliation.
5. Only after long testnet validation and private stream recovery, enable small-size guarded live runs.

## Safety Rules

- AI never receives exchange API secrets.
- AI outputs only a `TradeIntent`.
- Deterministic risk code approves or rejects every intent.
- Live mode must keep withdrawal disabled, IP whitelist enabled, and leverage capped.
- Emergency stop must block all new orders.
- Panic stop must be rehearsed before live mode; it disables scheduler/Testnet drill, disarms live trading, and attempts OMS cancellation for non-terminal Binance orders.
- Exchange-level cancel-all and flatten-plan checks must pass before live mode; flatten execution must require `FLATTEN_POSITIONS`.
- Restore drills must pass before live mode; `restore_state.py` validates the backup archive and SQLite integrity before replacing the runtime database.
