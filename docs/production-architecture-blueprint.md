# Production Architecture Blueprint

The current MVP remains intentionally local-first, but it now exposes the target
production architecture as an explicit blueprint in `/api/state.architecture`.
This keeps the reference-project lessons visible without pretending the MVP is
already an institutional trading stack.

## Executive Summary

`/api/state.architecture.executive_summary` records the four top-level decisions
from the design report:

- Split research from execution first: Anthropic financial-services and
  TradingAgents are treated as research/governance references, while LLM output
  remains a candidate signal and deterministic code keeps risk, OMS,
  reconciliation, and settlement authority.
- Start small and closed-loop: one venue, one account or a few subaccounts,
  low-to-mid frequency strategies, sandbox first, small live only after replay
  and audit evidence. Binance Futures Testnet is first; Bybit testnet, OKX
  simulated trading, and Hyperliquid testnet remain later adapter references.
- Build a trading operations console, not a quote screen: the UI groups
  strategy configuration, backtests, sandbox/live status, alerts, review,
  permissions, and key-management evidence.
- Keep the standard stack visible without prematurely migrating the MVP:
  FastAPI, LangGraph or Anthropic Agent SDK, PostgreSQL/TimescaleDB,
  ClickHouse, NATS JetStream, Next.js, Lightweight Charts, ECharts, Monaco
  Editor, and xterm.js remain the standard-route target, while the current
  service stays on the safer stdlib Python + SQLite MVP path.

## Project Goals And Assumptions

`/api/state.architecture.project_goals_assumptions` records the default target
when budget, users, venues, strategy complexity, and compliance mode are still
unspecified:

- Serve 1 to 5 researchers/traders.
- Start with one exchange that has an official sandbox.
- Prefer low-to-mid frequency directional or event-driven strategies before
  multi-strategy portfolios.
- Convert LLM output into structured signals before deterministic risk and OMS.

The assumption matrix keeps the recommended defaults visible: small-team
internal use, single CEX, template strategies, standard-leaning MVP budget, and
internal-team compliance posture. It also records when those defaults stop
being enough: multi-user internal platforms need maker-checker, RBAC, approval,
and audit separation; external platform or SaaS use needs regulatory
classification around FATF VASP AML/CFT guidance, MiCA-style authorization and
disclosure, and derivative/CFD-like leverage controls where applicable.

The venue selection notes keep Binance U-margined futures as the first
implementation path, with Bybit V5, OKX simulated trading, and Hyperliquid
testnet captured as later adapter candidates.

## Anthropic Reference Project

`/api/state.architecture.anthropic_reference_project` records the interpretation
boundary for the Anthropic reference. In this project, Anthropic does not mean a
ready-made crypto perpetual trading terminal or production OMS/RMS. It means the
`anthropics/financial-services` reference templates plus Claude Agent SDK,
subagents, tool use, and MCP-style connector capabilities.

The UI now exposes the three reference layers:

- Agents for research, analysis, memos, notes, and reconciliation drafts.
- Skills / Commands for reusable research moves such as `sector-overview`,
  `competitive-analysis`, `comps-analysis`, and `idea-generation`.
- MCP Connectors for external data and workflow access, always behind
  permission and untrusted-input boundaries.

It also records the production boundary from the reference: agents produce
analysis artifacts that need professional review; they do not provide
investment advice, execute trades, bind risk, post accounting entries, or make
final approval decisions. The transferred design rule is that agents may
research, organize, and suggest, while deterministic services retain execution
and control authority.

The `market-researcher` section captures the guardrails used for external
materials: third-party reports, issuer material, news, social content, and web
pages are untrusted inputs; every number needs source evidence; missing figures
must be marked `[UNSOURCED]`; and critical artifacts must pause for analyst
review. The Agent SDK section records the future production capabilities:
subagent isolation, strict tool schemas, allow/deny permissions, hooks,
runtime callbacks, checkpointing, OpenTelemetry, and prompt caching.

## TradingAgents Reference Project

`/api/state.architecture.tradingagents_reference_project` records the
TradingAgents lessons as a research-company prototype, not as a crypto
perpetual live engine. The blueprint exposes the seven simulated-company roles:
fundamental analyst, sentiment analyst, news analyst, technical analyst,
researcher, trader, and risk manager. They are grouped under Analyst Team,
Researcher Team, Trader Agents, and Risk Management Team.

The recorded architecture path is:

1. Market/news/social/fundamental data
2. Analyst Team
3. Bull / Bear Research Debate
4. Trader
5. Risk Team / Portfolio Manager
6. Simulated Exchange / Decision Log / Checkpoint

The key transfer is structured communication. TradingAgents warns that long
natural-language agent chains can create a `telephone effect`, so the MVP keeps
research outputs in structured artifacts: reports, opinion summaries,
confidence, evidence references, and strategy parameter suggestions. These feed
`ResearchArtifact -> TradeIntent -> RiskCheck -> OMS/Executor`, where
deterministic services retain final control.

The runtime notes preserve the future LangGraph path:
`TradingAgentsGraph().propagate()`, multiple LLM providers, an always-on
decision log at `~/.tradingagents/memory/trading_memory.md`, and optional
checkpoint resume with per-ticker SQLite checkpoints. The limitation notes are
also explicit: TradingAgents is for research purposes, is sensitive to model,
temperature, timing, and data quality, and the paper's 11 LLM calls plus 20+
tool calls per prediction show why cost, throughput, and time consistency are
still production gaps.

## Reference Synthesis

`/api/state.architecture.reference_synthesis` keeps the two reference paths side
by side: Anthropic contributes skill reuse, MCP access, permissions, hooks, and
human review boundaries; TradingAgents contributes role division, structured
reports, debate-style research, and checkpoint recovery.

The implementation rule is deliberately strict: do not wrap either reference as
the trading engine. Use them as upper-layer research and governance frameworks,
while OMS, RMS, position settlement, exchange reconciliation, multi-user RBAC,
non-repudiable audit, and live failure recovery remain deterministic production
services.

## Recommended Layered Architecture

`/api/state.architecture.layered_architecture` now records the recommended
four-plane target architecture as first-class data:

- Research plane: may use Anthropic Agent SDK, LangGraph, and multi-agent
  research. It produces structured research artifacts, evidence references,
  confidence, debate conclusions, and candidate signals.
- Control plane: owns strategy versions, approvals, RBAC, configuration
  release, scheduling, and human review. It controls testnet/live switches but
  does not bypass risk or OMS.
- Execution plane: must be deterministic, replayable, and low-latency. It owns
  the deterministic strategy runtime, RMS, OMS, position ledger, settlement, and
  exchange adapters.
- Observability plane: owns logs, metrics, alerts, audit, replay evidence, and
  incident review.

The object also stores the production graph from the design report as Mermaid
text plus structured nodes and edges. The graph currently has 21 nodes and 28
edges covering Web UI / Mobile Readonly, API Gateway / BFF, SSO / RBAC /
Approval, Market Data Ingest, Normalizer / Sequencer, Event Bus, Agent Research
Service, Deterministic Strategy Runtime, Risk Engine, Order Management, Exchange
Adapters, Exchange REST / WS, Position & PnL Ledger, Funding / Fee / Settlement,
Backtest / Replay, Audit Log / Event Store, Metrics / Logs / Alerts,
PostgreSQL, TimescaleDB, ClickHouse, and Redis.

The venue-adapter rule is explicit: exchange APIs differ in signing,
idempotency fields, rate limits, order-book synchronization, simulated-trading
headers, and request-expiry semantics. The execution plane therefore needs
venue-specific adapters instead of relying on a single generic abstraction.

The strategy engine is split into two parts:

- Research strategy engine: reads news, social data, funding, order book data,
  and technical indicators, then generates candidate signals.
- Deterministic strategy runtime: accepts only structured input and outputs
  clear actions, positions, and conditions that risk and OMS can verify.

## Four Planes

- Research plane: Anthropic/TradingAgents-style research artifacts, structured
  reports, debate outputs, evidence gaps, and `TradeIntent` candidates.
- Control plane: Web UI, API/BFF, strategy versions, approvals, RBAC, scheduler,
  and configuration release controls.
- Execution plane: deterministic strategy runtime, RMS, OMS, venue-specific
  exchange adapters, position/PnL ledger, funding/fee settlement, sandbox/testnet
  execution, and recovery.
- Observability plane: audit log, event store, metrics, logs, alerts, replay,
  readiness reports, and incident evidence.

## Required Target Components

The blueprint explicitly tracks the target components from the architecture
report: Web UI / Mobile Readonly, API Gateway / BFF, SSO / RBAC / Approval,
Market Data Ingest, Normalizer / Sequencer, Event Bus, Agent Research Service,
Deterministic Strategy Runtime, Risk Engine, Order Management, Exchange
Adapters, Exchange REST / WS, Position & PnL Ledger, Funding / Fee / Settlement,
Backtest / Replay, Audit Log / Event Store, Metrics / Logs / Alerts,
PostgreSQL, TimescaleDB, ClickHouse, and Redis.

Each component is marked as implemented, partial, or gap. The MVP currently has
many partials and gaps by design.

## Hard Boundaries

- Agents may operate in research and control surfaces only.
- Agents must not enter the matching or exchange hot path.
- Venue adapters must remain venue-specific because signatures, idempotency,
  rate limits, order-book sequencing, simulation headers, and request expiry
  differ by exchange.
- Production work still needs OMS/RMS depth, settlement, exchange reconciliation,
  multi-user RBAC, non-repudiable audit, monitoring/alerts, and live-failure
  recovery.

## Module Matrix

`/api/state.architecture.module_definition_table` preserves the design report's
exact three-column key-module table: module, suggested responsibility, and
productionization point. It covers:

- Strategy engine
- Order management
- Risk controls
- Backtest
- Data ingestion
- Position and settlement
- Logs and audit
- Permission and multi-user management
- Monitoring and alerts
- Simulation and sandbox

The UI renders this exact table before the expanded module matrix, so the
original responsibility/productionization boundary stays visible and
machine-checkable.

The state endpoint and UI also expose `module_matrix`, an expanded version that
adds current MVP coverage and required next steps for each module. This matrix
is the bridge between the research/governance references and the engineering
work still required before any live deployment.

## Production Implementation Notes

`/api/state.architecture.implementation_note_table` preserves the exact
three-column implementation-notes table from the design report: topic,
documentation basis, and engineering recommendation. It covers:

- Key management, signing, and least privilege
- Retry and idempotency
- Latency and throughput
- Order slippage and fees
- Market-data quality
- Time consistency
- Backtest/live differences
- Failure recovery and rollback
- Compliance and risk rules
- Simulation and replay

The UI renders this exact table before the expanded status table so the
production caveats stay visible without being diluted by current MVP status.

The same state object also exposes `implementation_notes`. These expanded notes
add each topic's status, current MVP control, and required next step. This keeps
the dashboard honest: paper mode can be considered healthy while still showing
exactly which controls must exist before testnet placement or live trading is
considered.

## Entity Relationship Blueprint

`/api/state.architecture.entity_model` exposes the data chain that must become
replayable, explainable, and reconcilable. It tracks the entities from the
design report: `USER`, `ACCOUNT`, `API_KEY`, `AUDIT_LOG`,
`STRATEGY_DEPLOYMENT`, `ORDER`, `POSITION`, `RISK_RULE_BINDING`, `STRATEGY`,
`STRATEGY_VERSION`, `BACKTEST_RUN`, `SIGNAL_EVENT`, `FILL`,
`EXCHANGE_ORDER_REF`, `SETTLEMENT_EVENT`, `RISK_RULE`, `RISK_CHECK_RESULT`, and
`RESEARCH_ARTIFACT`.

The same object stores the exact Mermaid `erDiagram` from the design report so
the relationship graph is machine-checkable, not just implied by prose. The UI
renders the Mermaid source before the entity cards and relationship table.

The relationship list preserves the report's chain, including `USER owns
ACCOUNT`, `SIGNAL_EVENT may_create ORDER`, `ORDER contains FILL`, `POSITION
updated_by FILL`, `ORDER checked_by RISK_CHECK_RESULT`, and both order/fill
records being written into `AUDIT_LOG`.

## Control-room Information Architecture

`/api/state.architecture.ui_information_architecture` exposes the target
operator console structure:

- Dashboard
- Strategy center
- Backtest and replay
- Trade execution
- Risk center
- Data and audit
- User and system

The same object stores the exact workbench navigation tree from the design
report under `navigation_tree`, with `工作台` as the root and the seven top-level
groups plus their children preserved as source text. The UI renders this tree
before the navigation cards so the intended IA remains visible.

The UI page matrix records the recommended components for dashboard, strategy
editor, backtest results, order book, position details, risk panel, user
settings, API-key management, and log/audit views. It also records the intended
tooling choices: Monaco Editor, Lightweight Charts, ECharts, and xterm.js.
`/api/state.architecture.ui_information_architecture.page_component_table`
preserves the exact page/components/design-focus rows from the design report,
and the UI renders its summary before the component matrix.

## Interaction Flow And Charts

The UI architecture also records the explicit release path:

1. Create strategy draft
2. Add research artifacts
3. Run backtest
4. Review return, risk, and fill distribution
5. Deploy to sandbox
6. Observe shadow run
7. Enter small live
8. Review logs, audit, and post-trade notes

This keeps the product flow centered on evidence, parameters, risk, and release
instead of hiding deployment behind a single button. The responsive guidance is
desktop-first with reduced mobile capability: mobile should focus on status,
alerts, emergency stop, and positions, while full strategy editing and API-key
management remain desktop workflows.

The chart guidance separates trading charts from analysis charts. Trading views
prioritize K-lines, volume, depth, latest trades, and position price lines.
Analysis views prioritize equity, drawdown, rolling Sharpe, win/loss
distribution, slippage, exposure stacks, and funding timelines.

The state also keeps the exact main loop labels from the design report:
strategy draft, research artifact and structured signal, backtest/replay,
approval/risk review, sandbox deployment, monitoring/reconciliation, small
live, and logs/audit/review. The UI renders these as a separate loop so the
operator can distinguish the product workflow from the broader implementation
status notes.

## Technical Implementation Plan

`/api/state.architecture.technical_implementation` exposes the recommended
standard stack and delivery route. It records:

- Technology stack layers from research-agent orchestration through
  exchange-unification prototypes.
- API priority: official exchange REST/WS docs and SDKs first, venue-specific
  adapters second, unified wrappers such as CCXT third.
- Six delivery phases from architecture definition through standardized
  expansion.
- MVP / standard / enterprise comparison across user scope, venues, strategy
  complexity, feature set, UI scope, technical shape, team, calendar time,
  budget, and use case.
- The recommended start: plan for the standard shape, but deliver the MVP in two
  phases while preserving idempotency, ledger, RBAC, and audit-schema decisions.
- The risk boundary: the hardest failure mode is not model quality but unclear
  boundaries between agent advice, orders, positions, and audit state.

## Risk, Test, And Acceptance Gates

The same state payload now exposes the report's operational risk register,
acceptance matrix, and go-live hard gates:

- Risk register: API-key leakage, duplicate orders, distorted market data, time
  drift, backtest illusion, model hallucination or injection, compliance
  misclassification, alert storms, failed operational recovery, and human
  misoperation.
- Acceptance matrix: market-data sync, order idempotency, cancel/replace races,
  pre-trade risk, position and settlement accounting, backtest/replay
  determinism, failure recovery, permission control, UI usability, and alert
  delivery.
- Small-live hard gates: multi-day sandbox/replay consistency, no duplicate
  opening on unknown order states, order-book break recovery, daily ledger
  reconciliation, critical-alert SLA delivery, and exercised RBAC/audit checks.

This keeps the UI honest: the console shows what is already implemented, what is
still a production gap, and which conditions must be satisfied before any move
from sandbox toward small live capital.

The current MVP has advanced beyond parameter-only Binance testnet validation:
`binance_testnet_place_order` can submit real Binance Futures testnet limit
orders when `BINANCE_PLACE_TESTNET_ORDERS=true`, then reconcile by
`origClientOrderId` and cancel submitted testnet orders through the OMS. Live
capital remains locked until private account streams, recovery drills, and
small-live gates are proven.

Startup recovery is now part of the MVP control plane. On process start and on
manual request, the service reconciles recent OMS orders, syncs Binance account
snapshots when testnet/live credentials are configured, and manages the Binance
user-data `listenKey` lifecycle with masked UI display. The private WebSocket
consumer now stores `ORDER_TRADE_UPDATE` and `ACCOUNT_UPDATE` payloads, updates
matching OMS orders by `clientOrderId`, and writes account/position snapshots
for recovery and audit.

The alert watchdog is also part of the MVP control plane. It persists alerts for
emergency stop, scheduler failures, OMS unknown states, stale exchange recovery,
and Binance private stream health, then exposes acknowledge/resolve actions in
the Chinese UI. Alerts can now be delivered to a generic signed Webhook, with
each delivery attempt recorded for audit.

The Binance Testnet drill control plane now ties the server-readiness pieces
together. Each drill cycle records its mode, symbol, run/order link, recovery
report, alert summary, and private-stream summary in SQLite. Local smoke tests
can run a `dry_run` cycle without touching Binance; server mode requires
testnet credentials before scheduled validation or placement rehearsals can be
enabled.

`live_guarded` is now also modeled as a separate live path. It reuses the same
OMS state machine and signed Binance USD-M Futures order/query/cancel endpoints,
but it remains invisible unless `ENABLE_BINANCE_LIVE=true`, separate live keys
are configured, `BINANCE_PLACE_LIVE_ORDERS=true`, and
`LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_RISK` is present.
