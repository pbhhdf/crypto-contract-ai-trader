# Research Agent Boundary

This MVP borrows the safe parts of Anthropic financial-services and
TradingAgents without treating either project as a production crypto execution
engine.

## Interpretation

- Anthropic financial-services is used as a governance reference: agents create
  reviewable analysis artifacts and must not execute trades, bind risk, or make
  final approvals.
- TradingAgents is used as an organization and communication reference:
  analyst-style stages produce structured conclusions that can be audited.
- The hot execution path stays deterministic: `TradeIntent` must pass risk
  checks before OMS or exchange adapters see it.

## Current Implementation

The `/api/state` response includes a `research` object with:

- `protocol`: input treatment, exchange format, decision memory, and human
  review rules.
- `guardrails`: non-negotiable rules such as no secret access, no unsourced
  claims, and deterministic risk boundaries.
- `artifacts`: market research, sentiment/news gaps, structured intent, and
  risk-review records derived from the latest workflow events.

The UI renders this as `研究工件与治理边界` so the operator can see what the
research layer knows, what it does not know, and where execution authority stops.

The current artifact set intentionally maps the named reference concepts:

- Anthropic: user request / workflow trigger, Agent or Managed Agent,
  Skills/Commands, MCP Connectors, research artifacts, and human sign-off.
- Anthropic market-researcher guardrails: third-party material is untrusted
  data, not instructions; unsourced facts must remain explicit; critical
  artifacts need human review.
- Anthropic market-researcher skill shape: first define the research scope, then
  use sector-overview, competitive-analysis, comps-analysis, and
  idea-generation style skills as data extraction and synthesis steps.
- TradingAgents: analyst team, bull/bear debate, trader, risk or portfolio
  manager, simulated exchange, decision log, and checkpoint recovery.
- TradingAgents role map: fundamental analyst, sentiment analyst, news analyst,
  technical analyst, researcher, trader, and risk manager.
- Limitations: TradingAgents remains research-purpose infrastructure and is not
  a production crypto perpetual OMS/RMS.

## Future Agent Runtime Contract

If Claude Agent SDK, Anthropic Managed Agents, or LangGraph nodes are added:

- Each analyst must run with an isolated context and explicitly assigned tools.
- Each subagent must have its own context window, system prompt, and tool
  permissions.
- Tool calls that produce `TradeIntent`-like outputs must use a strict schema.
- Permission hooks must be able to deny secret access, exchange-order mutation,
  or untrusted external instructions through allow/deny rules and runtime
  callbacks.
- PreToolUse and PostToolUse hooks must be available before tools can affect
  state.
- Checkpoints must be recorded at node boundaries before any stateful action.
- File-write rollback should be available for research-side artifacts.
- OpenTelemetry or equivalent traces must connect research artifacts to risk
  checks, OMS decisions, and operator review.
- Prompt caching is allowed only as a cost/latency optimization; cached context
  must not hide unsourced inputs or stale evidence. The default cache assumption
  is a short-lived window such as 5 minutes.

TradingAgents-style debate may enrich research artifacts, but its research-only
status remains a hard boundary. It must not be treated as a production OMS/RMS or
as proof that a crypto perpetual strategy is ready for live funds.

## Safety Rule

Any future Anthropic, Claude, LangGraph, or TradingAgents integration must keep
the same boundary:

```text
ResearchArtifact -> TradeIntent -> RiskCheck -> OMS/Executor
```

Agents may enrich the first two steps. They must not bypass `RiskCheck`, mutate
orders directly, or receive exchange API secrets.
