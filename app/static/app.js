const stateUrl = "/api/state";
const architectureUrl = "/api/architecture";
const readinessUrl = "/api/readiness";
const goLiveGateUrl = "/api/go-live-gate";

const els = {
  systemStatus: document.querySelector("#system-status"),
  runStatus: document.querySelector("#run-status"),
  finalAction: document.querySelector("#final-action"),
  riskStatus: document.querySelector("#risk-status"),
  environment: document.querySelector("#environment"),
  runId: document.querySelector("#run-id"),
  timeline: document.querySelector("#timeline"),
  marketSnapshot: document.querySelector("#market-snapshot"),
  researchStatus: document.querySelector("#research-status"),
  researchSummary: document.querySelector("#research-summary"),
  researchProtocol: document.querySelector("#research-protocol"),
  researchArtifacts: document.querySelector("#research-artifacts"),
  researchGuardrails: document.querySelector("#research-guardrails"),
  architectureStatus: document.querySelector("#architecture-status"),
  architectureSummary: document.querySelector("#architecture-summary"),
  executiveSummary: document.querySelector("#executive-summary"),
  projectDefaultTarget: document.querySelector("#project-default-target"),
  projectAssumptionReasoning: document.querySelector("#project-assumption-reasoning"),
  assumptionDefaults: document.querySelector("#assumption-defaults"),
  complianceTiers: document.querySelector("#compliance-tiers"),
  exchangeSelection: document.querySelector("#exchange-selection"),
  anthropicReferencePremise: document.querySelector("#anthropic-reference-premise"),
  anthropicReferenceLayers: document.querySelector("#anthropic-reference-layers"),
  anthropicReferenceBoundaries: document.querySelector("#anthropic-reference-boundaries"),
  marketResearcherGuardrails: document.querySelector("#market-researcher-guardrails"),
  agentSdkCapabilities: document.querySelector("#agent-sdk-capabilities"),
  tradingagentsPositioning: document.querySelector("#tradingagents-positioning"),
  tradingagentsRoles: document.querySelector("#tradingagents-roles"),
  tradingagentsFlow: document.querySelector("#tradingagents-flow"),
  tradingagentsCommunication: document.querySelector("#tradingagents-communication"),
  tradingagentsRuntime: document.querySelector("#tradingagents-runtime"),
  tradingagentsLimitations: document.querySelector("#tradingagents-limitations"),
  referenceArchitecturePaths: document.querySelector("#reference-architecture-paths"),
  referenceAbsorbPoints: document.querySelector("#reference-absorb-points"),
  referenceImplementationRule: document.querySelector("#reference-implementation-rule"),
  layeredArchitectureSummary: document.querySelector("#layered-architecture-summary"),
  layeredArchitecturePlanes: document.querySelector("#layered-architecture-planes"),
  venueAdapterRule: document.querySelector("#venue-adapter-rule"),
  strategyEngineSplit: document.querySelector("#strategy-engine-split"),
  architectureGraphNodes: document.querySelector("#architecture-graph-nodes"),
  architectureGraphEdges: document.querySelector("#architecture-graph-edges"),
  architecturePrinciples: document.querySelector("#architecture-principles"),
  architecturePlanes: document.querySelector("#architecture-planes"),
  architectureComponents: document.querySelector("#architecture-components"),
  moduleDefinitionSummary: document.querySelector("#module-definition-summary"),
  moduleDefinitionTable: document.querySelector("#module-definition-table"),
  moduleMatrix: document.querySelector("#module-matrix"),
  implementationNoteSummary: document.querySelector("#implementation-note-summary"),
  implementationNoteTable: document.querySelector("#implementation-note-table"),
  implementationNotes: document.querySelector("#implementation-notes"),
  entitySummary: document.querySelector("#entity-summary"),
  entityFocus: document.querySelector("#entity-focus"),
  entityMermaid: document.querySelector("#entity-mermaid"),
  entityList: document.querySelector("#entity-list"),
  entityRelationships: document.querySelector("#entity-relationships"),
  uiIaSummary: document.querySelector("#ui-ia-summary"),
  uiIaRoot: document.querySelector("#ui-ia-root"),
  uiNavigationTree: document.querySelector("#ui-navigation-tree"),
  uiNavigation: document.querySelector("#ui-navigation"),
  uiPageComponentSummary: document.querySelector("#ui-page-component-summary"),
  uiPageComponents: document.querySelector("#ui-page-components"),
  uiTooling: document.querySelector("#ui-tooling"),
  interactionFlowSummary: document.querySelector("#interaction-flow-summary"),
  interactionFlowSteps: document.querySelector("#interaction-flow-steps"),
  mainLoopSteps: document.querySelector("#main-loop-steps"),
  responsiveGuidance: document.querySelector("#responsive-guidance"),
  chartGuidance: document.querySelector("#chart-guidance"),
  technicalSummary: document.querySelector("#technical-summary"),
  technicalPrinciples: document.querySelector("#technical-principles"),
  technicalStack: document.querySelector("#technical-stack"),
  apiPriority: document.querySelector("#api-priority"),
  implementationRoadmap: document.querySelector("#implementation-roadmap"),
  scaleComparison: document.querySelector("#scale-comparison"),
  recommendedStart: document.querySelector("#recommended-start"),
  riskBoundary: document.querySelector("#risk-boundary"),
  testingPrinciple: document.querySelector("#testing-principle"),
  riskRegister: document.querySelector("#risk-register"),
  acceptanceMatrix: document.querySelector("#acceptance-matrix"),
  goLiveGates: document.querySelector("#go-live-gates"),
  tradeIntent: document.querySelector("#trade-intent"),
  riskChecks: document.querySelector("#risk-checks"),
  orders: document.querySelector("#orders"),
  rawLog: document.querySelector("#raw-log"),
  startRun: document.querySelector("#start-run"),
  stop: document.querySelector("#stop"),
  panicStop: document.querySelector("#panic-stop"),
  resetStop: document.querySelector("#reset-stop"),
  symbol: document.querySelector("#symbol"),
  mode: document.querySelector("#mode"),
  aiProvider: document.querySelector("#ai-provider"),
  aiModel: document.querySelector("#ai-model"),
  aiReady: document.querySelector("#ai-ready"),
  aiFallback: document.querySelector("#ai-fallback"),
  overviewLiveStatus: document.querySelector("#overview-live-status"),
  overviewLiveDetail: document.querySelector("#overview-live-detail"),
  overviewReadinessStatus: document.querySelector("#overview-readiness-status"),
  overviewReadinessDetail: document.querySelector("#overview-readiness-detail"),
  overviewAlertStatus: document.querySelector("#overview-alert-status"),
  overviewAlertDetail: document.querySelector("#overview-alert-detail"),
  overviewOmsStatus: document.querySelector("#overview-oms-status"),
  overviewOmsDetail: document.querySelector("#overview-oms-detail"),
  overviewTestnetStatus: document.querySelector("#overview-testnet-status"),
  overviewTestnetDetail: document.querySelector("#overview-testnet-detail"),
  overviewAuditStatus: document.querySelector("#overview-audit-status"),
  overviewAuditDetail: document.querySelector("#overview-audit-detail"),
  deskPostureCard: document.querySelector("#desk-posture-card"),
  deskModePill: document.querySelector("#desk-mode-pill"),
  deskHeadline: document.querySelector("#desk-headline"),
  deskSubtitle: document.querySelector("#desk-subtitle"),
  deskRunChip: document.querySelector("#desk-run-chip"),
  deskRiskChip: document.querySelector("#desk-risk-chip"),
  deskAccountChip: document.querySelector("#desk-account-chip"),
  deskBlockerCount: document.querySelector("#desk-blocker-count"),
  deskBlockerList: document.querySelector("#desk-blocker-list"),
  aiOperatorStatus: document.querySelector("#ai-operator-status"),
  aiOperatorBoundary: document.querySelector("#ai-operator-boundary"),
  aiOperatorMessages: document.querySelector("#ai-operator-messages"),
  aiOperatorInput: document.querySelector("#ai-operator-input"),
  sendAiOperator: document.querySelector("#send-ai-operator"),
  aiOperatorPermissions: document.querySelector("#ai-operator-permissions"),
  marketSource: document.querySelector("#market-source"),
  enabledModes: document.querySelector("#enabled-modes"),
  exchangeMode: document.querySelector("#exchange-mode"),
  testnetStatus: document.querySelector("#testnet-status"),
  readinessOverall: document.querySelector("#readiness-overall"),
  readinessList: document.querySelector("#readiness-list"),
  auditChainStatus: document.querySelector("#audit-chain-status"),
  auditChainTotal: document.querySelector("#audit-chain-total"),
  auditChainBroken: document.querySelector("#audit-chain-broken"),
  auditChainHash: document.querySelector("#audit-chain-hash"),
  auditChainRecent: document.querySelector("#audit-chain-recent"),
  localReadinessStatus: document.querySelector("#local-readiness-status"),
  localReadinessCurrent: document.querySelector("#local-readiness-current"),
  localReadinessCount: document.querySelector("#local-readiness-count"),
  localReadinessFailed: document.querySelector("#local-readiness-failed"),
  localReadinessPath: document.querySelector("#local-readiness-path"),
  localReadinessSteps: document.querySelector("#local-readiness-steps"),
  alertStatus: document.querySelector("#alert-status"),
  alertSummary: document.querySelector("#alert-summary"),
  alertList: document.querySelector("#alert-list"),
  runAlertCheck: document.querySelector("#run-alert-check"),
  testAlertDelivery: document.querySelector("#test-alert-delivery"),
  alertDeliveryStatus: document.querySelector("#alert-delivery-status"),
  alertDeliveries: document.querySelector("#alert-deliveries"),
  exchangeRecoveryStatus: document.querySelector("#exchange-recovery-status"),
  exchangeSyncMode: document.querySelector("#exchange-sync-mode"),
  runExchangeRecovery: document.querySelector("#run-exchange-recovery"),
  syncExchangeAccount: document.querySelector("#sync-exchange-account"),
  planFlattenPositions: document.querySelector("#plan-flatten-positions"),
  startUserStream: document.querySelector("#start-user-stream"),
  keepaliveUserStream: document.querySelector("#keepalive-user-stream"),
  closeUserStream: document.querySelector("#close-user-stream"),
  exchangeRecoveryFacts: document.querySelector("#exchange-recovery-facts"),
  exchangeSnapshots: document.querySelector("#exchange-snapshots"),
  schedulerStatus: document.querySelector("#scheduler-status"),
  schedulerEnabled: document.querySelector("#scheduler-enabled"),
  schedulerSymbol: document.querySelector("#scheduler-symbol"),
  schedulerInterval: document.querySelector("#scheduler-interval"),
  saveScheduler: document.querySelector("#save-scheduler"),
  runSchedulerNow: document.querySelector("#run-scheduler-now"),
  schedulerLast: document.querySelector("#scheduler-last"),
  schedulerNext: document.querySelector("#scheduler-next"),
  schedulerError: document.querySelector("#scheduler-error"),
  testnetDrillStatus: document.querySelector("#testnet-drill-status"),
  testnetDrillEnabled: document.querySelector("#testnet-drill-enabled"),
  testnetDrillSymbol: document.querySelector("#testnet-drill-symbol"),
  testnetDrillMode: document.querySelector("#testnet-drill-mode"),
  testnetDrillInterval: document.querySelector("#testnet-drill-interval"),
  testnetDrillTarget: document.querySelector("#testnet-drill-target"),
  saveTestnetDrill: document.querySelector("#save-testnet-drill"),
  runTestnetDrillNow: document.querySelector("#run-testnet-drill-now"),
  testnetDrillProgress: document.querySelector("#testnet-drill-progress"),
  testnetDrillLast: document.querySelector("#testnet-drill-last"),
  testnetDrillNext: document.querySelector("#testnet-drill-next"),
  testnetDrillError: document.querySelector("#testnet-drill-error"),
  testnetDrillCycles: document.querySelector("#testnet-drill-cycles"),
  liveGateStatus: document.querySelector("#live-gate-status"),
  liveGateSummary: document.querySelector("#live-gate-summary"),
  liveGateFacts: document.querySelector("#live-gate-facts"),
  liveGateList: document.querySelector("#live-gate-list"),
  checkLiveGate: document.querySelector("#check-live-gate"),
  exportGoLiveReport: document.querySelector("#export-go-live-report"),
  exportLiveLaunchPlan: document.querySelector("#export-live-launch-plan"),
  exportLiveOpsHandoff: document.querySelector("#export-live-ops-handoff"),
  exportLiveLaunchKit: document.querySelector("#export-live-launch-kit"),
  exportLiveEnvPack: document.querySelector("#export-live-env-pack"),
  exportServerBundle: document.querySelector("#export-server-bundle"),
  exportServerGoLiveAudit: document.querySelector("#export-server-go-live-audit"),
  checkFinalLiveReady: document.querySelector("#check-final-live-ready"),
  runServerLiveReadiness: document.querySelector("#run-server-live-readiness"),
  cancelServerLiveReadiness: document.querySelector("#cancel-server-live-readiness"),
  serverLiveReadinessTestnet: document.querySelector("#server-live-readiness-testnet"),
  serverLiveReadinessStatus: document.querySelector("#server-live-readiness-status"),
  serverLiveReadinessStarted: document.querySelector("#server-live-readiness-started"),
  serverLiveReadinessReport: document.querySelector("#server-live-readiness-report"),
  serverLiveReadinessBlockers: document.querySelector("#server-live-readiness-blockers"),
  serverLiveReadinessEvidence: document.querySelector("#server-live-readiness-evidence"),
  checkLiveEnvProfile: document.querySelector("#check-live-env-profile"),
  liveEnvProfileStatus: document.querySelector("#live-env-profile-status"),
  liveEnvProfileTarget: document.querySelector("#live-env-profile-target"),
  liveEnvProfileMissing: document.querySelector("#live-env-profile-missing"),
  liveEnvProfileNext: document.querySelector("#live-env-profile-next"),
  liveEnvProfileList: document.querySelector("#live-env-profile-list"),
  finalLiveReady: document.querySelector("#final-live-ready"),
  liveArmConfirmation: document.querySelector("#live-arm-confirmation"),
  liveArmTtl: document.querySelector("#live-arm-ttl"),
  liveArmReason: document.querySelector("#live-arm-reason"),
  armLiveGate: document.querySelector("#arm-live-gate"),
  disarmLiveGate: document.querySelector("#disarm-live-gate"),
  livePilotConfirmation: document.querySelector("#live-pilot-confirmation"),
  checkLivePilot: document.querySelector("#check-live-pilot"),
  runLivePilot: document.querySelector("#run-live-pilot"),
  checkLivePostflight: document.querySelector("#check-live-postflight"),
  resolveLiveBlockers: document.querySelector("#resolve-live-blockers"),
  livePilotStatus: document.querySelector("#live-pilot-status"),
  livePilotSummary: document.querySelector("#live-pilot-summary"),
  livePilotList: document.querySelector("#live-pilot-list"),
  livePostflightStatus: document.querySelector("#live-postflight-status"),
  livePostflightSummary: document.querySelector("#live-postflight-summary"),
  livePostflightList: document.querySelector("#live-postflight-list"),
  liveBlockerStatus: document.querySelector("#live-blocker-status"),
  liveBlockerSummary: document.querySelector("#live-blocker-summary"),
  liveBlockerList: document.querySelector("#live-blocker-list"),
  liveNextActionStatus: document.querySelector("#live-next-action-status"),
  liveNextActionSummary: document.querySelector("#live-next-action-summary"),
  liveNextActionList: document.querySelector("#live-next-action-list"),
  liveAttestationStatus: document.querySelector("#live-attestation-status"),
  attestWithdrawalDisabled: document.querySelector("#attest-withdrawal-disabled"),
  attestIpWhitelisted: document.querySelector("#attest-ip-whitelisted"),
  attestJurisdictionOk: document.querySelector("#attest-jurisdiction-ok"),
  attestOffserverBackupCopied: document.querySelector("#attest-offserver-backup-copied"),
  attestPilotCapitalLimitOk: document.querySelector("#attest-pilot-capital-limit-ok"),
  liveAttestationActor: document.querySelector("#live-attestation-actor"),
  liveAttestationConfirmation: document.querySelector("#live-attestation-confirmation"),
  liveAttestationNote: document.querySelector("#live-attestation-note"),
  saveLiveAttestation: document.querySelector("#save-live-attestation"),
  clearLiveAttestation: document.querySelector("#clear-live-attestation"),
  liveAttestationList: document.querySelector("#live-attestation-list"),
  riskCenterStatus: document.querySelector("#risk-center-status"),
  riskMaxLeverage: document.querySelector("#risk-max-leverage"),
  riskMaxPosition: document.querySelector("#risk-max-position"),
  riskMaxNotional: document.querySelector("#risk-max-notional"),
  riskDailyLoss: document.querySelector("#risk-daily-loss"),
  riskMaxOpen: document.querySelector("#risk-max-open"),
  riskLossStreak: document.querySelector("#risk-loss-streak"),
  riskSymbols: document.querySelector("#risk-symbols"),
  saveRisk: document.querySelector("#save-risk"),
  riskStop: document.querySelector("#risk-stop"),
  riskPanicStop: document.querySelector("#risk-panic-stop"),
  riskReset: document.querySelector("#risk-reset"),
  riskEmergency: document.querySelector("#risk-emergency"),
  riskOpenPositions: document.querySelector("#risk-open-positions"),
  riskDailyPnl: document.querySelector("#risk-daily-pnl"),
  accountEquity: document.querySelector("#account-equity"),
  freeMargin: document.querySelector("#free-margin"),
  unrealizedPnl: document.querySelector("#unrealized-pnl"),
  grossExposure: document.querySelector("#gross-exposure"),
  positionSummary: document.querySelector("#position-summary"),
  positions: document.querySelector("#positions"),
  reconcileOrders: document.querySelector("#reconcile-orders"),
  omsTotal: document.querySelector("#oms-total"),
  omsReconciled: document.querySelector("#oms-reconciled"),
  omsNeeds: document.querySelector("#oms-needs"),
  omsUnknown: document.querySelector("#oms-unknown"),
  backtestSymbol: document.querySelector("#backtest-symbol"),
  backtestInterval: document.querySelector("#backtest-interval"),
  backtestBars: document.querySelector("#backtest-bars"),
  runBacktest: document.querySelector("#run-backtest"),
  runCompare: document.querySelector("#run-compare"),
  backtestId: document.querySelector("#backtest-id"),
  backtestReturn: document.querySelector("#backtest-return"),
  backtestWinRate: document.querySelector("#backtest-win-rate"),
  backtestDrawdown: document.querySelector("#backtest-drawdown"),
  backtestTradesCount: document.querySelector("#backtest-trades-count"),
  backtestTrades: document.querySelector("#backtest-trades"),
  compareId: document.querySelector("#compare-id"),
  compareResults: document.querySelector("#compare-results"),
  runWalkforward: document.querySelector("#run-walkforward"),
  walkforwardId: document.querySelector("#walkforward-id"),
  walkforwardReturn: document.querySelector("#walkforward-return"),
  walkforwardPositive: document.querySelector("#walkforward-positive"),
  walkforwardDrawdown: document.querySelector("#walkforward-drawdown"),
  walkforwardTrades: document.querySelector("#walkforward-trades"),
  walkforwardFolds: document.querySelector("#walkforward-folds"),
};

let schedulerDirty = false;
let testnetDrillDirty = false;
let riskDirty = false;
let liveAttestationDirty = false;
let architectureLoaded = false;
let architectureLoading = false;
let readinessLoading = false;
let readinessLoadedAt = 0;
let goLiveGateLoading = false;
let goLiveGateLoadedAt = 0;
let lastFullGoLiveGate = null;
const activeViewStorageKey = "cryptoTrader.activeView";

const viewMeta = {
  overview: {
    kicker: "实时总览",
    title: "今日处置台",
    summary: "门禁、阻塞、资金、系统边界同屏。",
    focus: "先看阻塞项，再处理快捷动作",
  },
  ai: {
    kicker: "人机协作",
    title: "AI 操作员",
    summary: "对话生成检查、交接、部署包和受控建议。",
    focus: "AI 可辅助操作，交易边界仍由风控和 OMS 决定",
  },
  live: {
    kicker: "上线门禁",
    title: "实盘准入",
    summary: "处理实盘锁、授权、首单、上线包和终检。",
    focus: "默认锁定，未满足门禁不会触发真实订单",
  },
  trading: {
    kicker: "执行观察",
    title: "交易工作台",
    summary: "运行、行情、意图、风控、持仓和订单同屏。",
    focus: "适合盯盘、复盘和纸交易验证",
  },
  risk: {
    kicker: "确定性控制",
    title: "风控中心",
    summary: "配置杠杆、名义金额、日亏损和停机动作。",
    focus: "所有交易意图必须先过这里",
  },
  backtest: {
    kicker: "策略实验",
    title: "回测实验室",
    summary: "单次回测、参数比较和样本外验证。",
    focus: "先看回撤和样本外，再看收益",
  },
  ops: {
    kicker: "服务运维",
    title: "调度与恢复",
    summary: "管理调度、Testnet、交易所同步和告警。",
    focus: "服务器运行时优先看这里",
  },
  evidence: {
    kicker: "证据链",
    title: "检查与审计",
    summary: "查看就绪、审计哈希链和原始事件流。",
    focus: "用于排障、交接和上线复核",
  },
  research: {
    kicker: "系统蓝图",
    title: "架构与研究",
    summary: "研究工件、治理边界、实体关系和验收门槛。",
    focus: "长内容已收进本地滚动面板",
  },
};

const viewGroups = {
  overview: [".action-board", ".overview-grid", ".account-grid", ".system-grid"],
  ai: [".ai-operator-panel"],
  live: [".live-gate-panel"],
  trading: [".metrics-grid", ".workflow-workspace", ".intent-workspace", ".positions-panel", ".orders-panel"],
  risk: [".risk-panel"],
  backtest: [".backtest-panel"],
  ops: [".scheduler-panel", ".testnet-drill-panel", ".exchange-recovery-panel", ".alert-panel"],
  evidence: [".readiness-panel", ".local-readiness-panel", ".audit-chain-panel", ".raw-log-panel"],
  research: [".research-panel", ".architecture-panel"],
};

function initializeViewSwitcher() {
  const tabs = Array.from(document.querySelectorAll(".view-tab"));
  const switcher = document.querySelector(".view-switcher");
  const stage = document.createElement("section");
  stage.className = "view-stage";
  const context = document.createElement("section");
  context.className = "view-context";
  context.innerHTML = `
    <div class="view-context-copy">
      <span id="view-kicker">实时总览</span>
      <strong id="view-title">今日处置台</strong>
      <small id="view-summary">门禁、阻塞、资金、系统边界同屏。</small>
    </div>
    <div class="view-context-focus">
      <span>当前焦点</span>
      <b id="view-focus">先看阻塞项，再处理快捷动作</b>
    </div>
  `;
  const sections = new Set();
  Object.entries(viewGroups).forEach(([view, selectors]) => {
    selectors.forEach((selector) => {
      document.querySelectorAll(selector).forEach((section) => {
        section.dataset.view = view;
        section.classList.add("view-section");
        sections.add(section);
      });
    });
  });
  if (switcher) {
    switcher.insertAdjacentElement("afterend", stage);
    stage.appendChild(context);
    sections.forEach((section) => stage.appendChild(section));
  }
  const contextEls = {
    kicker: context.querySelector("#view-kicker"),
    title: context.querySelector("#view-title"),
    summary: context.querySelector("#view-summary"),
    focus: context.querySelector("#view-focus"),
  };
  function storedView() {
    try {
      return window.localStorage.getItem(activeViewStorageKey);
    } catch (error) {
      return "";
    }
  }
  function rememberView(view) {
    try {
      window.localStorage.setItem(activeViewStorageKey, view);
    } catch (error) {
      // 浏览器隐私模式可能禁止 localStorage，忽略即可。
    }
  }
  function activate(view, persist = true) {
    const nextView = viewGroups[view] ? view : "overview";
    const meta = viewMeta[nextView] || viewMeta.overview;
    document.body.dataset.activeView = nextView;
    context.dataset.activeView = nextView;
    contextEls.kicker.textContent = meta.kicker;
    contextEls.title.textContent = meta.title;
    contextEls.summary.textContent = meta.summary;
    contextEls.focus.textContent = meta.focus;
    tabs.forEach((tab) => {
      const active = tab.dataset.viewTarget === nextView;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    sections.forEach((section) => {
      section.hidden = section.dataset.view !== nextView;
    });
    if (persist) {
      rememberView(nextView);
      if (window.location.hash !== `#${nextView}`) {
        window.history.replaceState(null, "", `#${nextView}`);
      }
    }
  }
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => activate(tab.dataset.viewTarget || "overview"));
  });
  const initialView = window.location.hash.replace("#", "") || storedView() || "overview";
  activate(initialView, false);
  window.addEventListener("hashchange", () => {
    activate(window.location.hash.replace("#", "") || "overview", false);
  });
}

function initializeDeskActions() {
  document.querySelectorAll("[data-jump-view]").forEach((button) => {
    button.addEventListener("click", () => {
      const view = button.dataset.jumpView || "overview";
      const tab = document.querySelector(`.view-tab[data-view-target="${view}"]`);
      tab?.click();
      window.setTimeout(() => {
        const targetId = button.dataset.focusId;
        const target = targetId ? document.getElementById(targetId) : null;
        if (!target) return;
        target.scrollIntoView({ block: "center", behavior: "smooth" });
        target.focus({ preventScroll: true });
        target.classList.add("focus-pulse");
        window.setTimeout(() => target.classList.remove("focus-pulse"), 1100);
      }, 80);
    });
  });
}

function fmt(value) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") {
    return Number.isInteger(value)
      ? value
      : value.toLocaleString(undefined, { maximumFractionDigits: 6 });
  }
  return String(value);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeJson(value) {
  return JSON.stringify(value, (_key, item) => (item === null ? "-" : item), 2);
}

function chatText(value) {
  return String(value ?? "").replaceAll("null", "-");
}

function shortTime(ts) {
  if (!ts) return "-";
  const date = new Date(ts);
  return Number.isNaN(date.getTime()) ? ts : date.toLocaleTimeString();
}

function statusText(status) {
  const map = {
    queued: "排队中",
    running: "运行中",
    completed: "已完成",
    failed: "失败",
    approved: "通过",
    warning: "警告",
    rejected: "拒绝",
    active: "生效中",
    ready: "已生成",
    partial: "部分生成",
    waiting: "等待中",
    pass: "通过",
    warn: "警告",
    fail: "失败",
  };
  return map[status] || status || "-";
}

function kindText(kind) {
  const map = {
    system: "系统",
    data: "数据",
    agent: "代理",
    risk: "风控",
    order: "订单",
    account: "账户",
    error: "错误",
  };
  return map[kind] || kind || "-";
}

function sideText(side) {
  const map = {
    BUY: "买入",
    SELL: "卖出",
    HOLD: "观望",
  };
  return map[side] || side || "-";
}

function boolText(value) {
  return value ? "是" : "否";
}

function sourceText(source) {
  const map = {
    binance_public: "Binance 公共行情",
    synthetic: "本地合成行情",
    rules: "本地规则",
    openai: "OpenAI",
    codex: "Codex",
    deterministic_rules_v1: "确定性规则 v1",
    paper: "本地纸交易",
    local: "本地",
    completed: "已完成",
    false: "否",
    true: "是",
    low: "低",
    medium: "中",
    high: "高",
  };
  return map[source] || source || "-";
}

function modelText(model) {
  return sourceText(model);
}

function timeHorizonText(value) {
  return localizedText(value)
    .replace("30-90 minutes", "30-90 分钟")
    .replace("30-90 minute", "30-90 分钟");
}

function localizedText(value) {
  if (value === undefined || value === null || value === "") return "-";
  return String(value)
    .replaceAll("Legacy local paper order from before the position ledger; no venue retry is pending.", "历史本地纸交易订单早于持仓账本，当前无需交易所重试。")
    .replaceAll("Paper fill matched position", "纸交易成交已匹配持仓")
    .replaceAll("Paper fill has no linked position; manual review required.", "纸交易成交未关联持仓，需要人工复核。")
    .replaceAll("Anthropic financial-services boundaries", "Anthropic 金融服务边界")
    .replaceAll("Anthropic market-researcher guardrails", "Anthropic 市场研究护栏")
    .replaceAll("Anthropic market-researcher", "Anthropic 市场研究代理")
    .replaceAll("Anthropic + TradingAgents", "Anthropic + TradingAgents")
    .replaceAll("TradingAgents Analyst Team", "TradingAgents 分析师团队")
    .replaceAll("TradingAgents Bull/Bear Research Debate", "TradingAgents 牛熊研究辩论")
    .replaceAll("TradingAgents structured communication", "TradingAgents 结构化通信")
    .replaceAll("TradingAgents decision log / LangGraph checkpoint", "TradingAgents 决策日志 / LangGraph 检查点")
    .replaceAll("TradingAgents research purpose", "TradingAgents 研究用途边界")
    .replaceAll("Portfolio Manager / Risk Team", "组合经理 / 风控团队")
    .replaceAll("Claude Agent SDK / LangGraph", "Claude 代理 SDK / LangGraph")
    .replaceAll("ResearchArtifact -> TradeIntent -> RiskCheck -> OMS/Executor", "研究工件 -> TradeIntent -> 风控检查 -> OMS/执行器")
    .replaceAll("LangGraph checkpoint", "LangGraph 检查点")
    .replaceAll("subagent", "子代理")
    .replaceAll("allow/deny", "允许/拒绝")
    .replaceAll("OpenTelemetry", "遥测")
    .replaceAll("prompt caching", "提示词缓存")
    .replaceAll("hook", "钩子")
    .replaceAll("manual_run_now", "手动立即运行")
    .replaceAll("binance_public", "Binance 公共行情")
    .replaceAll("deterministic_rules_v1", "确定性规则 v1")
    .replaceAll("rules", "本地规则")
    .replaceAll("30-90 minutes", "30-90 分钟")
    .replaceAll("mode is paper", "模式为本地纸交易")
    .replaceAll("mode=paper", "模式=本地纸交易")
    .replace(/\bmode为 paper\b/g, "模式为本地纸交易")
    .replace(/\bpaper\b/g, "本地纸交易")
    .replace(/\blocal\b/g, "本地")
    .replace(/\blow\b/g, "低")
    .replace(/\bmedium\b/g, "中")
    .replace(/\bhigh\b/g, "高");
}

function orderStatusText(status) {
  const map = {
    prepared: "已准备",
    paper_submitted: "历史纸交易已提交",
    paper_filled: "纸交易已成交",
    testnet_validated: "测试网已验证",
    testnet_submitted: "测试网已提交",
    testnet_protection_submitted: "测试网保护单已提交",
    testnet_protection_canceled: "测试网保护单已取消",
    testnet_filled: "测试网已成交",
    testnet_canceled: "测试网已取消",
    live_submitted: "实盘已提交",
    live_protection_submitted: "实盘保护单已提交",
    live_protection_canceled: "实盘保护单已取消",
    live_filled: "实盘已成交",
    live_canceled: "实盘已取消",
    submitted: "已提交",
    pending_reconcile: "待对账",
    unknown: "未知",
    open: "持仓中",
    closed: "已关闭",
  };
  return map[status] || status || "-";
}

function reconcileText(status) {
  const map = {
    unchecked: "未检查",
    reconciled: "已对账",
    validated_no_live_order: "已验证，无真实订单",
    reviewed: "已复核",
    needs_reconcile: "需要对账",
    needs_review: "需要复核",
  };
  return map[status] || status || "-";
}

function venueStatusText(status) {
  const map = {
    PAPER_FILLED: "纸交易已成交",
    ORDER_TEST_ACCEPTED: "测试网参数已验证",
    NEW: "测试网挂单中",
    PARTIALLY_FILLED: "测试网部分成交",
    FILLED: "测试网已成交",
    CANCELED: "测试网已取消",
    EXPIRED: "测试网已过期",
    REJECTED: "测试网已拒绝",
    LEGACY_PAPER_SUBMITTED: "历史纸交易已复核",
    UNKNOWN: "未知",
  };
  return map[status] || status || "-";
}

function reasonText(reason) {
  const map = {
    stop_loss: "止损",
    take_profit: "止盈",
    max_hold: "达到最大持有周期",
    opposite_signal: "反向信号",
    end_of_sample: "样本结束",
    manual_close_from_dashboard: "控制台手动平仓",
    smoke_test_close: "自检平仓",
    manual_run_now: "手动立即运行",
    interval: "定时运行",
  };
  return map[reason] || reason || "-";
}

function modeText(mode) {
  const map = {
    paper: "本地纸交易",
    binance_testnet_validate: "Binance Testnet 验证",
    binance_testnet_place_order: "Binance Testnet 真实下单",
    live_guarded: "实盘保护模式",
  };
  return map[mode] || mode || "-";
}

function readinessName(name) {
  const map = {
    Runtime: "运行环境",
    "Market data": "行情数据",
    "AI adapter": "AI 适配器",
    "Research boundary": "研究边界",
    "Architecture blueprint": "架构蓝图",
    "Execution boundary": "执行边界",
    "Paper workflow": "纸交易流程",
    "Paper ledger": "纸交易账本",
    "Scheduled paper runs": "纸交易调度",
    "Testnet drill": "Testnet 演练",
    "Risk controls": "风控规则",
    "OMS reconciliation": "订单对账",
    "Audit hash chain": "审计哈希链",
    "Exchange recovery": "交易所恢复同步",
    "Private user stream": "私有回报流",
    "Alert watchdog": "告警看门狗",
    "Alert delivery": "告警通知",
    Backtest: "回测",
    "Parameter comparison": "参数比较",
    "Walk-forward": "滚动验证",
    "Server auth": "服务器认证",
    "Private network access": "私有网络访问",
    "Binance testnet guard": "Binance 测试网防护",
    "Binance time drift": "Binance 时间漂移",
    "Binance margin type sync": "Binance 保证金模式同步",
    "Binance leverage sync": "Binance 杠杆同步",
    "Binance position mode": "Binance 持仓模式",
    "Binance live guard": "Binance 实盘防护",
    "Go-live gate": "实盘准入门禁",
    "AI operator console": "AI 操作员窗口",
    "Live trading lock": "实盘锁",
  };
  return map[name] || name;
}

function readinessDetail(detail) {
  if (!detail) return "-";
  return String(detail)
    .replace("Configured source is binance_public.", "行情源为 Binance 公共行情。")
    .replace("Configured source is synthetic.", "行情源为本地合成行情。")
    .replace("Latest run status: completed.", "最近一次运行已完成。")
    .replace("Latest run status: failed.", "最近一次运行失败。")
    .replace("Latest run status: none.", "暂无运行记录。")
    .replace("Basic Auth is configured.", "已配置基础认证。")
    .replace(
      "Local mode can run without auth; server mode must set Basic Auth.",
      "本地模式可不启用认证；服务器模式必须配置基础认证。",
    )
    .replace("live mode is not enabled", "实盘模式未启用")
    .replace("Mode=paper", "模式=本地纸交易")
    .replace("enabled=paper", "已启用=本地纸交易")
    .replace("Orders=", "订单数=")
    .replace("reconciled=", "已对账=")
    .replace("needs_reconcile=", "待对账=")
    .replace("unknown=", "未知=")
    .replace("Enabled=", "启用=")
    .replace("symbol=", "交易对=")
    .replace("interval=", "间隔=")
    .replace("Max leverage=", "最大杠杆=")
    .replace("max position=", "单笔仓位=")
    .replace("daily loss=", "日亏损=")
    .replace("symbols=", "交易对=")
    .replace("open positions=", "当前持仓=")
    .replace("Equity=", "权益=");
}

function actorText(actor) {
  const map = {
    "Market Data": "行情数据",
    "Market Analyst": "市场分析师",
    "Sentiment Analyst": "情绪分析师",
    "News Analyst": "新闻分析师",
    "AI Decision Adapter": "AI 决策适配器",
    "Trader Agent": "交易代理",
    "Risk Engine": "风控引擎",
    "Paper Executor": "纸交易执行器",
    "Binance Testnet Validator": "Binance 测试网验证器",
    "Paper Position Ledger": "纸交易持仓账本",
    "Order Executor": "订单执行器",
    Orchestrator: "编排器",
    Scheduler: "自动调度器",
    "Risk Center": "风控中心",
    OMS: "订单管理",
  };
  return map[actor] || actor;
}

function riskCheckName(name) {
  const map = {
    "Account source": "资金口径",
    "Account snapshot freshness": "账户快照新鲜度",
    "Mode lock": "模式锁",
    "Allowed symbol": "允许交易对",
    "Emergency stop": "紧急停止",
    "Max leverage": "最大杠杆",
    "Max position": "单笔仓位",
    "Max order notional": "单笔名义金额",
    "Open position cap": "持仓数量上限",
    "Free margin": "可用保证金",
    "Daily loss limit": "日亏损限制",
    "Consecutive losses": "连续亏损",
    "Stop-loss required": "止损要求",
    "Liquidation pressure": "清算压力",
  };
  return map[name] || name;
}

function latestPayloadByActor(events, actor) {
  return [...events].reverse().find((event) => event.actor === actor)?.payload || null;
}

function renderModeOptions(config) {
  const modes = config.enabled_modes || ["paper"];
  const selected = modes.includes(els.mode.value) ? els.mode.value : modes[0];
  els.mode.innerHTML = modes
    .map((mode) => `<option value="${mode}">${modeText(mode)}</option>`)
    .join("");
  els.mode.value = selected;
}

function renderConfig(data) {
  const config = data.config || {};
  const ai = config.ai || {};
  const exchange = config.exchange || {};
  renderModeOptions(config);
  els.aiProvider.textContent = sourceText(ai.provider || "rules");
  els.aiModel.textContent = modelText(ai.model);
  els.aiReady.textContent = ai.ready ? "可用" : "回退";
  els.aiFallback.textContent = ai.fallback || "结构化交易意图";
  els.marketSource.textContent = sourceText(config.market_data_source);
  els.enabledModes.textContent = `已启用：${(config.enabled_modes || []).map(modeText).join("、")}`;
  els.exchangeMode.textContent = modeText(exchange.mode || data.system?.mode);
  els.testnetStatus.textContent = exchange.testnet_enabled
    ? `测试网${exchange.testnet_key_ready ? "密钥已配置" : "未配置密钥"} / 测试网下单${exchange.testnet_places_real_orders ? "开" : "关"} / 保证金${exchange.target_margin_type || "-"}${exchange.sync_margin_type_before_order ? "同步开" : "同步关"} / 杠杆同步${exchange.sync_leverage_before_order ? "开" : "关"} / One-way${exchange.require_one_way_position_mode ? "必需" : "未要求"} / 实盘${exchange.live_places_real_orders ? "开" : "关"}`
    : `测试网未启用 / 保证金${exchange.target_margin_type || "-"}${exchange.sync_margin_type_before_order ? "同步开" : "同步关"} / 杠杆同步${exchange.sync_leverage_before_order ? "开" : "关"} / One-way${exchange.require_one_way_position_mode ? "必需" : "未要求"} / 实盘${exchange.live_places_real_orders ? "开" : "关"}`;
}

function deskBlockerText(value) {
  const map = {
    live_flags: "实盘开关未进入 live_guarded，真实订单仍被锁定",
    deployment_profile: "服务器部署剖面未通过，先完成 server 环境与 Basic Auth",
    testnet_drill_cycles: "真实 Testnet 演练证据不足，还不能进入实盘",
    live_attestation: "人工实盘证据未确认：提现关闭、IP 白名单、外部备份",
    live_pilot_capital: "首单资金上限或小额试运行约束未确认",
    exchange_position_mode: "交易所持仓模式未确认 One-way",
    short_live_arming: "实盘短时武装窗口未开启或已过期",
    emergency_stop: "紧急停止中，自动交易和调度均应保持暂停",
    alert_critical: "存在严重告警，先处理告警再推进交易",
    oms_reconcile: "OMS 仍有未知或待复核订单，需要先对账",
    readiness_fail: "部署就绪检查存在失败项",
    readiness_warn: "部署就绪检查存在警告项",
  };
  return map[value] || localizedText(value);
}

function uniqueList(items) {
  const seen = new Set();
  return items.filter((item) => {
    const key = String(item || "");
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function collectDeskBlockers(data) {
  const blockers = [];
  const gate = data.go_live_gate || {};
  const readiness = data.readiness || {};
  const readinessItems = readiness.items || [];
  const alerts = data.alerts?.summary || {};
  const oms = data.oms || {};
  if (data.system?.emergency_stop) blockers.push("emergency_stop");
  if (alerts.critical) blockers.push("alert_critical");
  blockers.push(...(gate.blocking_gates || []));
  if (Number(oms.needs_review_orders || 0) || Number(oms.unknown_venue_status_orders || 0)) {
    blockers.push("oms_reconcile");
  }
  const failCount = readinessItems.filter((item) => item.status === "fail").length;
  const warnCount = readinessItems.filter((item) => item.status === "warn").length;
  if (failCount) blockers.push("readiness_fail");
  if (warnCount && !failCount) blockers.push("readiness_warn");
  return uniqueList(blockers);
}

function renderDesk(data) {
  if (!els.deskHeadline) return;
  const run = data.latest_run;
  const gate = data.go_live_gate || {};
  const risk = data.risk || {};
  const account = data.account || {};
  const alerts = data.alerts?.summary || {};
  const blockers = collectDeskBlockers(data);
  const mode = data.system?.mode || "paper";
  let posture = "ok";
  let modeLabel = modeText(mode);
  let headline = "系统在线，可以继续纸交易或演练";
  let subtitle = "首屏只保留处置摘要；细节放在左侧标签页里按需查看。";

  if (data.system?.emergency_stop || risk.emergency_stop) {
    posture = "danger";
    modeLabel = "已停机";
    headline = "紧急停止中，先确认风险与未结订单";
    subtitle = "所有自动调度应保持暂停；需要解除时先查看风控页和 OMS 对账。";
  } else if (Number(alerts.critical || 0)) {
    posture = "danger";
    modeLabel = "有严重告警";
    headline = "存在严重告警，先处理告警再交易";
    subtitle = `当前严重告警 ${fmt(alerts.critical)} 条，建议进入运维页确认通知和恢复记录。`;
  } else if (gate.ready_for_live_order) {
    posture = "active";
    modeLabel = "可进入首单";
    headline = "实盘前置条件已通过，仍需短时武装";
    subtitle = "真实订单只允许在短时武装窗口内提交，并继续受风控和 OMS 约束。";
  } else if (blockers.length) {
    posture = "warn";
    modeLabel = "实盘锁定";
    headline = "当前适合纸交易、回测和 Testnet 演练";
    subtitle = `还有 ${fmt(blockers.length)} 个上线阻塞项，先处理最上方的阻塞项即可。`;
  } else if (run?.status === "running" || run?.status === "queued") {
    posture = "active";
    modeLabel = "分析中";
    headline = "策略分析正在运行";
    subtitle = "交易意图、风控结论和 OMS 事件会在交易页同步刷新。";
  }

  els.deskPostureCard?.setAttribute("data-status", posture);
  els.deskModePill.textContent = modeLabel;
  els.deskHeadline.textContent = headline;
  els.deskSubtitle.textContent = subtitle;
  els.deskRunChip.textContent = `运行：${run ? statusText(run.status) : "未启动"}`;
  els.deskRiskChip.textContent = `风控：${risk.emergency_stop ? "紧急停止" : statusText(run?.risk_status)}`;
  els.deskAccountChip.textContent = `权益：${money(account.equity_usdt)}`;
  els.deskBlockerCount.textContent = fmt(blockers.length);
  els.deskBlockerList.innerHTML = blockers.length
    ? blockers.slice(0, 5).map((item) => `<li>${escapeHtml(deskBlockerText(item))}</li>`).join("")
    : `<li>暂无阻塞项；继续观察告警、OMS 与 Testnet 演练。</li>`;
}

function renderReadiness(readiness) {
  if (!readiness) {
    els.readinessOverall.textContent = "-";
    els.readinessList.innerHTML = "";
    if (els.overviewReadinessStatus) {
      els.overviewReadinessStatus.textContent = "-";
      els.overviewReadinessDetail.textContent = "尚未读取就绪检查";
    }
    return;
  }
  const overallMap = {
    pass: "已就绪",
    warn: "本地可用，服务器需复核",
    fail: "需要处理",
  };
  els.readinessOverall.textContent = overallMap[readiness.overall] || readiness.overall || "-";
  if (els.overviewReadinessStatus) {
    const items = readiness.items || [];
    const failCount = items.filter((item) => item.status === "fail").length;
    const warnCount = items.filter((item) => item.status === "warn").length;
    els.overviewReadinessStatus.textContent = overallMap[readiness.overall] || readiness.overall || "-";
    els.overviewReadinessDetail.textContent = `${fmt(items.length)} 项 / 失败 ${fmt(failCount)} / 警告 ${fmt(warnCount)}`;
  }
  const badgeClass = {
    pass: "pass",
    warn: "warn",
    fail: "fail",
  };
  els.readinessList.innerHTML = (readiness.items || [])
    .map(
      (item) => `
        <div class="readiness-item">
          <strong>${readinessName(item.name)}<span class="badge ${badgeClass[item.status] || "warn"}">${statusText(item.status)}</span></strong>
          <span class="event-body">${readinessDetail(item.detail)}</span>
        </div>
      `,
    )
    .join("");
}

function localReadinessStatusText(report) {
  if (!report || report.exists === false) return "尚未生成";
  if (report.status === "running") return "运行中";
  if (report.status === "completed" && report.ok === true) return "已完成";
  if (report.status === "completed" && report.ok === false) return "有失败项";
  if (report.status === "error") return "读取失败";
  return report.status || "未知";
}

function localReadinessStepStatusText(status) {
  const map = {
    starting: "启动中",
    running: "运行中",
    done: "已完成",
    completed: "已完成",
  };
  return map[status] || status || "";
}

function renderLocalReadiness(report) {
  if (!els.localReadinessStatus) return;
  if (!report || report.exists === false) {
    els.localReadinessStatus.textContent = "尚未生成";
    els.localReadinessCurrent.textContent = "-";
    els.localReadinessCount.textContent = "0";
    els.localReadinessFailed.textContent = "-";
    els.localReadinessPath.textContent = "运行全量检查脚本后会生成验收进度报告";
    els.localReadinessSteps.innerHTML = `<article class="guidance-card"><strong>暂无验收报告</strong><p>全量检查运行时，这里会显示当前步骤和最近完成项。</p></article>`;
    return;
  }
  const current = report.current_step || {};
  const currentName = current.name || (report.status === "completed" ? "完成" : "-");
  const currentStatus = current.status ? ` / ${localReadinessStepStatusText(current.status)}` : "";
  const failedCount = Number(report.failed_step_count || 0);
  const timedOut = report.timed_out_steps || [];
  const lastSteps = report.last_steps || [];
  els.localReadinessStatus.textContent = localReadinessStatusText(report);
  els.localReadinessCurrent.textContent = `${currentName}${currentStatus}`;
  els.localReadinessCount.textContent = fmt(report.completed_step_count || lastSteps.length || 0);
  els.localReadinessFailed.textContent = `${fmt(failedCount)} / 超时 ${fmt(timedOut.length)}`;
  els.localReadinessPath.textContent = report.report_path
    ? `报告：${report.report_path}`
    : "尚未找到可读取的验收报告";
  els.localReadinessSteps.innerHTML = lastSteps.length
    ? lastSteps.map((step) => {
        const badge = step.ok ? "pass" : step.timed_out ? "fail" : "warn";
        const duration = step.duration_seconds === undefined || step.duration_seconds === null ? "-" : `${step.duration_seconds}s`;
        const note = step.note ? `<p>${escapeHtml(step.note)}</p>` : "";
        return `
          <article class="guidance-card">
            <strong>${escapeHtml(step.name || "-")}<span class="badge ${badge}">${step.ok ? "通过" : step.timed_out ? "超时" : "失败"}</span></strong>
            <span>耗时 ${escapeHtml(duration)} / 退出码 ${escapeHtml(String(step.returncode ?? "-"))}</span>
            ${note}
          </article>
        `;
      }).join("")
    : `<article class="guidance-card"><strong>等待步骤完成</strong><p>检查启动后会逐项写入进度报告。</p></article>`;
}

function renderAuditChain(audit) {
  if (!audit) {
    els.auditChainStatus.textContent = "-";
    els.auditChainTotal.textContent = "-";
    els.auditChainBroken.textContent = "-";
    els.auditChainHash.textContent = "-";
    els.auditChainRecent.innerHTML = "";
    if (els.overviewAuditStatus) {
      els.overviewAuditStatus.textContent = "-";
      els.overviewAuditDetail.textContent = "尚未读取审计链";
    }
    return;
  }
  const ok = audit.status === "pass" && Number(audit.total_records || 0) > 0;
  els.auditChainStatus.textContent = ok ? "完整" : "需要检查";
  els.auditChainTotal.textContent = fmt(audit.total_records || 0);
  els.auditChainBroken.textContent = fmt(audit.broken_count || 0);
  els.auditChainHash.textContent = audit.last_hash && audit.last_hash !== "GENESIS"
    ? `${audit.last_hash.slice(0, 18)}...`
    : "-";
  if (els.overviewAuditStatus) {
    els.overviewAuditStatus.textContent = ok ? "完整" : "需要检查";
    els.overviewAuditDetail.textContent = `记录 ${fmt(audit.total_records || 0)} / 断裂 ${fmt(audit.broken_count || 0)}`;
  }
  const recent = audit.recent || [];
  els.auditChainRecent.innerHTML = recent.length
    ? recent.slice(-6).map((item) => `
        <article class="guidance-card">
          <strong>${escapeHtml(item.stream)} / ${escapeHtml(item.action)}</strong>
          <span>${escapeHtml(shortTime(item.ts))} / ${escapeHtml(item.ref_id)}</span>
          <p>${escapeHtml((item.row_hash || "").slice(0, 32))}...</p>
        </article>
      `).join("")
    : `<article class="guidance-card"><strong>暂无审计记录</strong><p>关键事件写入后会自动形成哈希链。</p></article>`;
}

function alertSeverityText(severity) {
  const map = {
    critical: "严重",
    warning: "警告",
    info: "提示",
  };
  return map[severity] || severity || "-";
}

function alertStatusText(status) {
  const map = {
    open: "待处理",
    acknowledged: "已确认",
    resolved: "已解决",
  };
  return map[status] || status || "-";
}

function deliveryChannelText(channel) {
  const map = {
    webhook: "外部通知",
    telegram: "Telegram",
    email: "Email",
    multi: "多通道",
  };
  return map[channel] || channel || "-";
}

function deliveryTransitionText(transition) {
  const map = {
    opened: "告警打开",
    resolved: "告警解决",
    test: "测试发送",
  };
  return map[transition] || transition || "-";
}

function deliveryStatusText(status) {
  const map = {
    sent: "已发送",
    failed: "失败",
    skipped: "跳过",
  };
  return map[status] || status || "-";
}

function renderAlerts(alertState) {
  const summary = alertState?.summary || {};
  const alerts = alertState?.alerts || [];
  const delivery = alertState?.delivery || {};
  const deliveries = alertState?.deliveries || [];
  if (!summary.active) {
    els.alertStatus.textContent = "正常";
    els.alertSummary.textContent = "没有活跃告警";
  } else {
    els.alertStatus.textContent = summary.critical ? "需要处理" : "需要关注";
    els.alertSummary.textContent = `活跃 ${fmt(summary.active)} / 严重 ${fmt(summary.critical)} / 警告 ${fmt(summary.warning)} / 已确认 ${fmt(summary.acknowledged)}`;
  }
  if (els.overviewAlertStatus) {
    els.overviewAlertStatus.textContent = summary.active
      ? summary.critical
        ? "需要处理"
        : "需要关注"
      : "正常";
    els.overviewAlertDetail.textContent = summary.active
      ? `活跃 ${fmt(summary.active)} / 严重 ${fmt(summary.critical)} / 警告 ${fmt(summary.warning)}`
      : "暂无活跃告警";
  }
  const minSeverity = alertSeverityText(delivery.min_severity || "warning");
  const readyChannels = (delivery.channels || [])
    .filter((item) => item.enabled && item.configured)
    .map((item) => deliveryChannelText(item.channel));
  els.alertDeliveryStatus.textContent = readyChannels.length
    ? `外部通知已启用 / ${readyChannels.join("、")} / 最低级别 ${minSeverity}`
    : `外部通知未启用 / 最低级别 ${minSeverity}`;
  els.alertDeliveries.innerHTML = deliveries.length
    ? deliveries.slice(0, 5).map((item) => `
      <article>
        <strong>${deliveryChannelText(item.channel)} / ${deliveryTransitionText(item.transition)} / ${deliveryStatusText(item.status)}</strong>
        <span>${shortTime(item.ts)} / ${item.target || "-"}</span>
      </article>
    `).join("")
    : `<article><strong>暂无通知投递记录</strong><span>配置 Webhook、Telegram 或 Email 后，告警打开和解决都会记录投递结果。</span></article>`;
  if (!alerts.length) {
    els.alertList.innerHTML = `<div class="empty">暂无活跃告警</div>`;
    return;
  }
  els.alertList.innerHTML = alerts
    .map((alert) => `
      <article class="alert-card ${alert.severity}" data-alert-id="${alert.id}">
        <div>
          <strong>${escapeHtml(alert.title)}</strong>
          <span>${alertSeverityText(alert.severity)} / ${alertStatusText(alert.status)} / ${shortTime(alert.updated_at)}</span>
          <p>${escapeHtml(alert.body)}</p>
        </div>
        <div class="alert-card-actions">
          <button class="compact ack-alert" data-alert-id="${alert.id}" ${alert.status !== "open" ? "disabled" : ""}>确认</button>
          <button class="compact resolve-alert" data-alert-id="${alert.id}">解决</button>
        </div>
      </article>
    `)
    .join("");
}

function userStreamText(stream) {
  const status = stream?.status || "stopped";
  const statusMap = {
    active: "已启动",
    stopped: "已停止",
    error: "异常",
    connecting: "连接中",
    reconnecting: "重连中",
    expired: "已过期",
  };
  const key = stream?.listen_key_present ? ` / 指纹 ${stream.listen_key_fingerprint}` : "";
  const socket = stream?.websocket_connected ? " / WebSocket 已连接" : "";
  const consumer = stream?.consumer_running ? " / 消费线程运行中" : "";
  return `${statusMap[status] || status}${socket}${consumer}${key}`;
}

function renderExchangeRecovery(recovery) {
  if (!recovery) {
    els.exchangeRecoveryStatus.textContent = "等待同步";
    els.exchangeRecoveryFacts.innerHTML = "";
    els.exchangeSnapshots.innerHTML = "";
    return;
  }
  const report = recovery.last_report || {};
  const orders = report.orders?.summary || {};
  const stream = recovery.user_stream || {};
  const streamSummary = recovery.stream_summary || {};
  const streamEvents = recovery.stream_events || [];
  const openOrderReports = report.open_orders || [];
  const openOrderCount = openOrderReports.reduce(
    (total, item) => total + Number(item.open_order_count || 0),
    0,
  );
  const exchangePositionCount = (recovery.snapshots || []).reduce(
    (total, snapshot) => total + Number(snapshot.summary?.open_position_count || 0),
    0,
  );
  const warnings = report.warnings || [];
  const errors = report.errors || [];
  els.exchangeRecoveryStatus.textContent = errors.length
    ? "需要处理"
    : recovery.last_at
      ? "已同步"
      : "等待同步";
  els.exchangeRecoveryFacts.innerHTML = `
    <article>
      <span>最近同步</span>
      <strong>${recovery.last_at ? shortTime(recovery.last_at) : "-"}</strong>
    </article>
    <article>
      <span>订单对账</span>
      <strong>${fmt(orders.reconciled_orders || 0)} / ${fmt(orders.total_orders || 0)}</strong>
    </article>
    <article>
      <span>待核查订单</span>
      <strong>${fmt(orders.needs_reconcile || 0)}</strong>
    </article>
    <article>
      <span>私有流状态</span>
      <strong>${userStreamText(stream)}</strong>
    </article>
    <article>
      <span>账户快照</span>
      <strong>${fmt((recovery.snapshots || []).length)}</strong>
    </article>
    <article>
      <span>交易所挂单</span>
      <strong>${fmt(openOrderCount)}</strong>
    </article>
    <article>
      <span>交易所持仓</span>
      <strong>${fmt(exchangePositionCount)}</strong>
    </article>
    <article>
      <span>私有事件</span>
      <strong>${fmt(stream.event_count || streamSummary.recent_count || 0)} / ${stream.last_event_type || streamSummary.latest_event_type || "-"}</strong>
    </article>
    <article>
      <span>告警</span>
      <strong>${fmt(warnings.length)} 警告 / ${fmt(errors.length)} 错误</strong>
    </article>
  `;
  const snapshots = recovery.snapshots || [];
  const openOrderCard = openOrderReports.length
    ? `
      <article>
        <strong>交易所挂单快照</strong>
        <span>${openOrderReports.map((item) => `${modeText(item.mode)} ${fmt(item.open_order_count || 0)} 个 / ${shortTime(item.synced_at)}`).join("；")}</span>
      </article>
    `
    : "";
  const eventCard = streamEvents.length
    ? `
      <article>
        <strong>最近私有事件</strong>
        <span>${streamEvents.slice(0, 3).map((event) => `${event.event_type} / ${shortTime(event.ts)} / ${event.processed ? "已处理" : "已记录"}`).join("；")}</span>
      </article>
    `
    : "";
  if (!snapshots.length) {
    els.exchangeSnapshots.innerHTML = `<article><strong>暂无交易所账户快照</strong><span>配置 Testnet 或实盘只读/交易 API key 后，可在这里同步账户余额与持仓摘要。</span></article>${openOrderCard}${eventCard}`;
    return;
  }
  els.exchangeSnapshots.innerHTML = snapshots
    .map((snapshot) => {
      const summary = snapshot.summary || {};
      return `
        <article>
          <strong>${modeText(snapshot.mode)} / ${shortTime(snapshot.ts)}</strong>
          <span>钱包 ${fmt(summary.wallet_balance_usdt)} USDT，可用 ${fmt(summary.available_balance_usdt)} USDT，未实现 PnL ${fmt(summary.unrealized_pnl_usdt)} USDT，持仓 ${fmt(summary.open_position_count)}。</span>
        </article>
      `;
    })
    .join("") + openOrderCard + eventCard;
}

function renderAiOperator(operator) {
  const status = operator?.status || operator || {};
  const history = operator?.history || [];
  if (!status.enabled) {
    els.aiOperatorStatus.textContent = "未启用";
    els.aiOperatorBoundary.textContent = "设置 AI_OPERATOR_ENABLED=true 后可以使用操作员聊天窗口。";
    els.aiOperatorPermissions.textContent = "文件权限未启用";
  } else {
    els.aiOperatorStatus.textContent = status.ready ? "已就绪" : "等待模型配置";
    els.aiOperatorBoundary.textContent = localizedText(status.boundary);
    if (status.shell_boundary) {
      els.aiOperatorBoundary.textContent += ` ${status.shell_boundary}`;
    }
    els.aiOperatorPermissions.textContent = [
      `读取：${status.allow_file_read ? "开" : "关"}`,
      `写入：${status.allow_file_write ? "开" : "关"}`,
      `快照：${status.snapshot_writes ? "开" : "关"}`,
      `Shell前备份：${status.backup_before_shell ? "开" : "关"}`,
      `自动执行：${status.apply_model_file_actions ? "开" : "关"}`,
    ].join(" / ");
    els.aiOperatorPermissions.textContent += ` / Shell：${status.allow_shell ? "开" : "关"}`;
  }
  if (!history.length) {
    els.aiOperatorMessages.innerHTML = `
      <div class="ai-message assistant">
        <strong>AI 操作员</strong>
        <p>我可以帮你检查系统、读取工作区文件，并在权限打开时写入文件、应用补丁或运行 Shell。右侧快捷命令会先填入输入框，你也可以直接描述任务。</p>
      </div>
    `;
    return;
  }
  els.aiOperatorMessages.innerHTML = history
    .map((message) => {
      const role = message.role === "user" ? "你" : "AI 操作员";
      const actionText = (message.actions || []).length
        ? `<pre>${escapeHtml(safeJson(message.actions))}</pre>`
        : "";
      return `
        <div class="ai-message ${message.role === "user" ? "user" : "assistant"}">
          <strong>${role}<span>${shortTime(message.ts)}</span></strong>
          <p>${escapeHtml(chatText(message.content))}</p>
          ${actionText}
        </div>
      `;
    })
    .join("");
  els.aiOperatorMessages.scrollTop = els.aiOperatorMessages.scrollHeight;
}

function renderScheduler(scheduler) {
  if (!scheduler) {
    els.schedulerStatus.textContent = "已暂停";
    els.schedulerLast.textContent = "-";
    els.schedulerNext.textContent = "-";
    els.schedulerError.textContent = "-";
    return;
  }
  const activeCount = (scheduler.active_runs || []).length;
  els.schedulerStatus.textContent = activeCount
    ? `运行中 ${activeCount}`
    : scheduler.enabled
      ? "已启用"
      : "已暂停";
  if (!schedulerDirty) {
    els.schedulerEnabled.checked = Boolean(scheduler.enabled);
    els.schedulerSymbol.value = scheduler.symbol || "BTCUSDT";
    els.schedulerInterval.value = Math.max(1, Math.round((scheduler.interval_seconds || 900) / 60));
  }
  els.schedulerLast.textContent = scheduler.last_run_id
    ? `${shortTime(scheduler.last_run_at)} / ${scheduler.last_run_id}`
    : "-";
  els.schedulerNext.textContent = scheduler.enabled ? shortTime(scheduler.next_run_at) : "-";
  els.schedulerError.textContent = scheduler.last_error || "-";
  els.runSchedulerNow.disabled = activeCount > 0;
}

function renderTestnetDrill(drill) {
  if (!drill) {
    els.testnetDrillStatus.textContent = "已暂停";
    els.testnetDrillProgress.textContent = "-";
    els.testnetDrillLast.textContent = "-";
    els.testnetDrillNext.textContent = "-";
    els.testnetDrillError.textContent = "-";
    els.testnetDrillCycles.innerHTML = "";
    if (els.overviewTestnetStatus) {
      els.overviewTestnetStatus.textContent = "已暂停";
      els.overviewTestnetDetail.textContent = "尚未配置演练";
    }
    return;
  }
  const availableModes = drill.available_modes || ["binance_testnet_validate"];
  const activeModes = drill.active_run_modes || [];
  Array.from(els.testnetDrillMode.options).forEach((option) => {
    option.disabled = !availableModes.includes(option.value);
  });
  els.testnetDrillStatus.textContent = drill.running
    ? "演练运行中"
    : drill.enabled
      ? "已启用"
      : "已暂停";
  if (els.overviewTestnetStatus) {
    els.overviewTestnetStatus.textContent = els.testnetDrillStatus.textContent;
    els.overviewTestnetDetail.textContent =
      `真实 ${fmt(drill.real_completed_cycles || 0)}/${fmt(drill.target_cycles)} / dry-run ${fmt(drill.dry_run_completed_cycles || 0)}`;
  }
  if (!testnetDrillDirty) {
    els.testnetDrillEnabled.checked = Boolean(drill.enabled);
    els.testnetDrillSymbol.value = drill.symbol || "BTCUSDT";
    els.testnetDrillMode.value = availableModes.includes(drill.mode) ? drill.mode : availableModes[0];
    els.testnetDrillInterval.value = Math.max(1, Math.round((drill.interval_seconds || 1800) / 60));
    els.testnetDrillTarget.value = drill.target_cycles || 24;
  }
  els.testnetDrillProgress.textContent = `真实 ${fmt(drill.real_completed_cycles || 0)}/${fmt(drill.target_cycles)} / dry-run ${fmt(drill.dry_run_completed_cycles || 0)}`;
  els.testnetDrillLast.textContent = drill.last_cycle_id
    ? `${shortTime(drill.last_cycle_at)} / ${drill.last_cycle_id}`
    : "-";
  els.testnetDrillNext.textContent = drill.enabled ? shortTime(drill.next_cycle_at) : "-";
  els.testnetDrillError.textContent = drill.last_error || "-";
  const canRunNow = !drill.running && activeModes.includes(drill.mode);
  els.runTestnetDrillNow.disabled = !canRunNow;
  els.testnetDrillCycles.innerHTML = (drill.cycles || [])
    .slice(0, 6)
    .map((cycle) => {
      const alerts = cycle.alert_summary || {};
      const stream = cycle.stream_summary || {};
      return `
        <article>
          <strong>${escapeHtml(cycle.id)}<span class="badge ${cycle.status === "completed" ? "pass" : cycle.status === "running" ? "warn" : "fail"}">${statusText(cycle.status)}</span></strong>
          <p>${modeText(cycle.mode)} / ${escapeHtml(cycle.symbol)} / ${reasonText(cycle.reason)}</p>
          <span>${shortTime(cycle.ts)} → ${shortTime(cycle.completed_at)}</span>
          <span>订单 ${escapeHtml(cycle.order_id || "-")} / 告警 ${fmt(alerts.active || 0)} / 私有流 ${escapeHtml(stream.latest_event_type || "-")}</span>
          <small>${escapeHtml(cycle.note || "-")}</small>
        </article>
      `;
    })
    .join("");
}

function renderLiveAttestation(attestation) {
  if (!attestation) {
    els.liveAttestationStatus.textContent = "未确认";
    els.liveAttestationList.innerHTML = "";
    return;
  }
  const statusLabel = {
    pass: "已确认",
    warn: "待确认",
    fail: "未通过",
  };
  els.liveAttestationStatus.textContent = statusLabel[attestation.status] || attestation.status || "未确认";
  const accepted = attestation.accepted || {};
  const checkboxMap = {
    withdrawal_disabled: els.attestWithdrawalDisabled,
    ip_whitelisted: els.attestIpWhitelisted,
    jurisdiction_ok: els.attestJurisdictionOk,
    offserver_backup_copied: els.attestOffserverBackupCopied,
    pilot_capital_limit_ok: els.attestPilotCapitalLimitOk,
  };
  if (!liveAttestationDirty) {
    Object.entries(checkboxMap).forEach(([key, checkbox]) => {
      if (checkbox) checkbox.checked = accepted[key] === true;
    });
    if (attestation.note) {
      els.liveAttestationNote.value = attestation.note;
    }
    if (attestation.actor) {
      els.liveAttestationActor.value = attestation.actor;
    }
  }
  const ageDays = attestation.age_seconds == null ? "-" : fmt(Number(attestation.age_seconds) / 86400);
  const maxAgeDays = fmt(attestation.max_age_days || 0);
  els.liveAttestationList.innerHTML = `
    <article>
      <strong>证据状态<span class="badge ${attestation.status === "pass" ? "pass" : "warn"}">${statusText(attestation.status)}</span></strong>
      <p>确认时间 ${escapeHtml(shortTime(attestation.attested_at))}；确认人 ${escapeHtml(attestation.actor || "-")}；年龄 ${ageDays}/${maxAgeDays} 天。</p>
      <span>${attestation.expired ? "已过期" : "有效期内或尚未确认"} / 缺失 ${fmt((attestation.missing_ids || []).length)} 项</span>
    </article>
    ${(attestation.requirements || [])
      .map((item) => `
        <article>
          <strong>${escapeHtml(item.label)}<span class="badge ${item.accepted ? "pass" : "warn"}">${item.accepted ? "已确认" : "待确认"}</span></strong>
          <p>${escapeHtml(item.detail || "-")}</p>
        </article>
      `)
      .join("")}
  `;
}

function liveQuickCommandForGate(id) {
  const map = {
    deployment_profile: "python3 scripts/live_env_profile.py --env-file .env --target mvp_server --strict",
    live_flags: "python3 scripts/live_env_profile.py --env-file .env --target live_guarded --strict",
    testnet_drill_cycles: "python3 scripts/run_testnet_drill_until_ready.py --mode binance_testnet_validate --target-cycles 24 --interval-seconds 60",
    live_attestation: "/live-attest --confirm LIVE_ATTESTATION_CONFIRMED",
    alert_delivery: "python3 scripts/check_alert_delivery.py",
    private_user_stream: "python3 scripts/check_private_stream_mapping.py",
    exchange_position_mode: "python3 scripts/check_binance_position_mode.py",
    exchange_open_orders: "python3 scripts/check_exchange_open_order_gate.py",
    exchange_open_positions: "python3 scripts/check_exchange_position_gate.py",
    live_pilot_capital: "python3 scripts/check_live_pilot.py",
    live_arming: "/live-arm --confirm ARM_LIVE_TRADING",
  };
  return map[id] || "python3 scripts/check_go_live_gate.py";
}

function renderLiveNextActionsFromGate(gate) {
  if (!els.liveNextActionStatus) return;
  if (!gate) {
    els.liveNextActionStatus.textContent = "等待读取";
    els.liveNextActionSummary.textContent = "自动汇总当前阻塞项，并给出最多三条可执行动作。";
    els.liveNextActionList.innerHTML = "";
    return;
  }
  const blockers = gate.blocking_gates || [];
  const statusMap = {
    ready: "已通过",
    blocked: "仍有阻塞",
    locked: "实盘锁定",
  };
  els.liveNextActionStatus.textContent = gate.ready_for_live_order
    ? "可提交首单"
    : statusMap[gate.status] || gate.status || "待处理";
  els.liveNextActionSummary.textContent = gate.ready_for_live_order
    ? "所有门禁已过；只允许短时、小额、单笔实盘首单流程。"
    : blockers.length
      ? `优先处理前 ${fmt(Math.min(3, blockers.length))} 个阻塞项；详细命令可展开解除路线。`
      : "没有非武装阻塞；下一步检查短时授权和首单执行器。";
  els.liveNextActionList.innerHTML = blockers.length
    ? blockers.slice(0, 3).map((item, index) => `
        <article>
          <strong>${fmt(index + 1)}. ${escapeHtml(item.label || item.id || "阻塞项")}<span class="badge fail">阻塞</span></strong>
          <p>${escapeHtml(livePilotText(item.detail || "-"))}</p>
          <code>${escapeHtml(liveQuickCommandForGate(item.id))}</code>
        </article>
      `).join("")
    : `
      <article>
        <strong>检查短时授权<span class="badge warn">下一步</span></strong>
        <p>最终实盘检查通过后，使用短时武装窗口提交一笔受控首单。</p>
        <code>/live-arm --confirm ARM_LIVE_TRADING</code>
      </article>
      <article>
        <strong>首单执行器<span class="badge warn">复核</span></strong>
        <p>提交前再次检查最终门禁、风险、OMS 和确认短语。</p>
        <code>python3 scripts/check_live_pilot.py</code>
      </article>
    `;
}

function displayGoLiveGate(gate) {
  if (!gate?.summary_only || !lastFullGoLiveGate) return gate;
  return {
    ...lastFullGoLiveGate,
    ...gate,
    summary_only: false,
    gates: lastFullGoLiveGate.gates || [],
    blocking_gates: lastFullGoLiveGate.blocking_gates || [],
  };
}

function renderGoLiveGate(gate) {
  if (!gate) {
    els.liveGateStatus.textContent = "锁定中";
    els.liveGateSummary.textContent = "尚未读取准入状态";
    els.liveGateFacts.innerHTML = "";
    els.liveGateList.innerHTML = "";
    renderLiveNextActionsFromGate(null);
    if (els.overviewLiveStatus) {
      els.overviewLiveStatus.textContent = "锁定中";
      els.overviewLiveDetail.textContent = "未读取门禁状态";
    }
    renderLiveAttestation(null);
    return;
  }
  const statusMap = {
    ready: "已通过",
    blocked: "已阻塞",
    locked: "实盘锁定",
  };
  const blockers = gate.blocking_gates || [];
  const arming = gate.live_arming || {};
  renderLiveNextActionsFromGate(gate);
  els.liveGateStatus.textContent = statusMap[gate.status] || gate.status || "-";
  els.liveGateSummary.textContent = gate.ready_for_live_order
    ? "所有实盘前置条件已通过，live_guarded 可以执行真实订单。"
    : arming.armed
      ? `实盘已短时授权，剩余 ${fmt(arming.remaining_seconds)} 秒，入口额度 ${fmt(arming.remaining_orders)}/${fmt(arming.max_orders)}；仍有 ${fmt(blockers.length)} 个阻塞项。`
      : `仍有 ${fmt(blockers.length)} 个阻塞项；未通过并武装前 live_guarded 不会真实下单。`;
  if (els.overviewLiveStatus) {
    els.overviewLiveStatus.textContent = statusMap[gate.status] || gate.status || "-";
    els.overviewLiveDetail.textContent = gate.ready_for_live_order
      ? "满足真实订单条件"
      : arming.armed
        ? `已武装，剩余 ${fmt(arming.remaining_seconds)} 秒 / 阻塞 ${fmt(blockers.length)}`
        : `未武装 / 阻塞 ${fmt(blockers.length)}`;
  }
  els.liveGateFacts.innerHTML = `
    <article>
      <span>实盘模式</span>
      <strong>${gate.live_mode_enabled ? "已启用" : "未启用"}</strong>
    </article>
    <article>
      <span>可启用实盘</span>
      <strong>${gate.ready_to_enable_live ? "是" : "否"}</strong>
    </article>
    <article>
      <span>可真实下单</span>
      <strong>${gate.ready_for_live_order ? "是" : "否"}</strong>
    </article>
    <article>
      <span>短时授权</span>
      <strong>${arming.armed ? `已武装 ${fmt(arming.remaining_seconds)}s` : "未武装"}</strong>
    </article>
    <article>
      <span>入口额度</span>
      <strong>${fmt(arming.remaining_orders)}/${fmt(arming.max_orders)}</strong>
    </article>
    <article>
      <span>Testnet 门槛</span>
      <strong>${fmt(gate.min_testnet_drill_cycles)} 次</strong>
    </article>
    <article>
      <span>阻塞项</span>
      <strong>${fmt(blockers.length)}</strong>
    </article>
  `;
  els.armLiveGate.disabled = !gate.ready_to_arm_live;
  els.disarmLiveGate.disabled = !arming.armed;
  const attestationGate = (gate.gates || []).find((item) => item.id === "live_attestation");
  renderLiveAttestation((attestationGate?.evidence || {}).attestation);
  const gateStatusClass = {
    pass: "pass",
    warn: "warn",
    fail: "fail",
  };
  els.liveGateList.innerHTML = (gate.gates || [])
    .map((item) => `
      <article>
        <strong>${escapeHtml(item.label || item.id)}<span class="badge ${gateStatusClass[item.status] || "warn"}">${statusText(item.status)}</span></strong>
        <p>${escapeHtml(item.detail || "-")}</p>
        <span>${item.blocks_live_order ? "阻塞真实下单" : "不阻塞真实下单"} / ${item.required_for_live ? "实盘必需" : "辅助检查"}</span>
      </article>
    `)
    .join("");
}

function renderFinalLiveReady(status) {
  if (!els.finalLiveReady) return;
  if (!status) {
    els.finalLiveReady.innerHTML = "";
    return;
  }
  const failures = status.failures || [];
  const badge = status.ok ? "pass" : "fail";
  els.finalLiveReady.innerHTML = `
    <article>
      <strong>最终实盘检查 <span class="badge ${badge}">${status.ok ? "可执行" : "未就绪"}</span></strong>
      <p>${status.ok ? "当前环境、门禁、人工证据、AI 操作员和短时授权均满足真实订单条件。" : `仍有 ${fmt(failures.length)} 个阻塞原因，live_guarded 不会真实下单。`}</p>
      <span>环境 ${escapeHtml(status.app_env || "-")} / 模式 ${escapeHtml(status.exchange_mode || "-")} / 阻塞门禁 ${fmt((status.blocking_gates || []).length)}</span>
    </article>
    ${failures.slice(0, 8).map((failure) => `
      <article>
        <strong>阻塞项</strong>
        <p>${escapeHtml(failure)}</p>
      </article>
    `).join("")}
  `;
}

function livePilotText(value) {
  if (!value) return "-";
  return localizedText(value)
    .replaceAll("Resolve the listed final-live blockers before attempting a live pilot run.", "先处理下方最终实盘阻塞项，再尝试实盘首单。")
    .replaceAll("Arm live trading with ARM_LIVE_TRADING, then re-run the final live pilot check.", "先用 ARM_LIVE_TRADING 完成短时武装，再重新检查实盘首单执行器。")
    .replaceAll("POST /api/live-pilot/run with confirmation=LAUNCH_LIVE_PILOT to submit one live_guarded pilot run.", "可以提交实盘首单；请求必须带确认短语 LAUNCH_LIVE_PILOT。")
    .replaceAll("APP_ENV must be server.", "必须在 APP_ENV=server 的服务器环境运行。")
    .replaceAll("EXCHANGE_MODE must be live_guarded.", "交易模式必须切到实盘保护模式。")
    .replaceAll("go-live gate does not show live_guarded as enabled.", "实盘准入门禁尚未显示实盘保护模式已启用。")
    .replaceAll("go-live prerequisites are not complete enough to enable live mode.", "实盘前置条件还不足以启用实盘模式。")
    .replaceAll("go-live gate is not ready to arm live trading.", "实盘准入门禁尚未允许短时武装。")
    .replaceAll("final live readiness requires a currently armed live window.", "最终实盘检查需要一个仍在有效期内的短时武装窗口。")
    .replaceAll("live attestation is missing, incomplete, or expired.", "人工实盘证据缺失、不完整或已过期。")
    .replace(/blocking gates remain: ([^.]+)\./g, "仍有阻塞门禁：$1。")
    .replace(/go-live checklist is not all pass: ([^.]+)\./g, "准入清单仍未全部通过：$1。")
    .replace(/non-arming blockers remain: ([^.]+)\./g, "仍有非武装阻塞项：$1。")
    .replace(/Active run exists: ([^.]+)\./g, "仍有活动工作流：$1。")
    .replace(/Symbol ([A-Z0-9]+) is not in the risk whitelist\./g, "交易对 $1 不在风控白名单内。")
    .replaceAll("live_flags", "实盘开关")
    .replaceAll("deployment_profile", "服务器部署档案")
    .replaceAll("testnet_drill_cycles", "Testnet 连续演练")
    .replaceAll("live_arming", "短时武装")
    .replaceAll("live_attestation", "人工实盘证据");
}

function renderLivePilot(pilot) {
  if (!els.livePilotStatus) return;
  if (!pilot) {
    els.livePilotStatus.textContent = "未检查";
    els.livePilotSummary.textContent = "只在最终实盘检查、短时武装和确认短语同时满足时提交一次实盘保护模式工作流。";
    els.livePilotList.innerHTML = "";
    if (els.runLivePilot) els.runLivePilot.disabled = true;
    return;
  }
  const statusMap = {
    ready: "可提交",
    needs_arming: "需要武装",
    blocked: "已阻塞",
  };
  const badgeMap = {
    ready: "pass",
    needs_arming: "warn",
    blocked: "fail",
  };
  const failures = pilot.failures || [];
  const armed = pilot.armed_ready || {};
  const prearm = pilot.prearm_ready || {};
  els.livePilotStatus.textContent = statusMap[pilot.status] || pilot.status || "-";
  els.livePilotSummary.textContent = livePilotText(pilot.next_action);
  if (els.runLivePilot) {
    els.runLivePilot.disabled = !pilot.can_launch;
  }
  els.livePilotList.innerHTML = `
    <article>
      <strong>执行状态<span class="badge ${badgeMap[pilot.status] || "warn"}">${escapeHtml(statusMap[pilot.status] || pilot.status || "-")}</span></strong>
      <p>交易对 ${escapeHtml(pilot.symbol || "-")}；确认短语 ${escapeHtml(pilot.confirmation_phrase || "-")}；活动工作流 ${(pilot.active_runs || []).length} 个。</p>
    </article>
    <article>
      <strong>预武装检查<span class="badge ${prearm.ok ? "pass" : "fail"}">${prearm.ok ? "通过" : "未通过"}</span></strong>
      <p>${escapeHtml((prearm.failures || []).slice(0, 2).map(livePilotText).join("；") || "无非武装阻塞项。")}</p>
    </article>
    <article>
      <strong>已武装检查<span class="badge ${armed.ok ? "pass" : "fail"}">${armed.ok ? "通过" : "未通过"}</span></strong>
      <p>${escapeHtml((armed.failures || []).slice(0, 2).map(livePilotText).join("；") || "短时武装窗口满足。")}</p>
    </article>
    ${failures.slice(0, 8).map((failure) => `
      <article>
        <strong>阻塞项</strong>
        <p>${escapeHtml(livePilotText(failure))}</p>
      </article>
    `).join("")}
  `;
}

function renderLivePostflight(postflight) {
  if (!els.livePostflightStatus) return;
  if (!postflight) {
    els.livePostflightStatus.textContent = "未检查";
    els.livePostflightSummary.textContent = "提交首单后检查 OMS、告警、审计链、交易所快照和解除武装状态。";
    els.livePostflightList.innerHTML = "";
    return;
  }
  const statusMap = {
    pass: "通过",
    warn: "待处理",
    fail: "未通过",
  };
  const badgeMap = {
    pass: "pass",
    warn: "warn",
    fail: "fail",
  };
  const checks = postflight.checks || [];
  const actions = postflight.next_actions || [];
  const status = postflight.status || "warn";
  const orders = postflight.orders || [];
  const oms = postflight.oms || {};
  const alerts = postflight.alerts || {};
  const audit = postflight.audit_chain || {};
  const protection = postflight.protection_chain || {};
  const otherChecks = checks.filter((check) => check.id !== "live_protection_chain");
  let visibleChecks = otherChecks.filter((check) => check.status !== "pass").slice(0, 4);
  if (!visibleChecks.length) visibleChecks = otherChecks.slice(0, 4);
  const hiddenChecksCount = Math.max(otherChecks.length - visibleChecks.length, 0);
  const missingKinds = (protection.missing_kinds || []).map((kind) => ({
    stop_loss: "止损",
    take_profit: "止盈",
  }[kind] || kind));
  const childStatusText =
    Object.entries(protection.child_statuses || {})
      .map(([kind, value]) => `${kind === "stop_loss" ? "止损" : kind === "take_profit" ? "止盈" : kind}: ${value}`)
      .join(" / ") || "暂无子单";
  const protectionLead = protection.status === "fail" ? protection.detail : "";
  els.livePostflightStatus.textContent = statusMap[status] || status;
  els.livePostflightSummary.textContent =
    [protectionLead, ...actions].filter(Boolean).slice(0, 2).map(livePilotText).join("；") ||
    "实盘首单后验检查通过；继续按小额、短时、单笔预算扩大。";
  els.livePostflightList.innerHTML = `
    <article>
      <strong>复盘状态<span class="badge ${badgeMap[status] || "warn"}">${escapeHtml(statusMap[status] || status)}</span></strong>
      <p>交易对 ${escapeHtml(postflight.symbol || "-")}；运行 ${escapeHtml(postflight.run_id || "-")}；关联实盘订单 ${fmt(orders.length)} 个。</p>
    </article>
    <article class="postflight-focus">
      <strong>止损 / 止盈保护链<span class="badge ${badgeMap[protection.status] || "warn"}">${escapeHtml(statusMap[protection.status] || protection.status || "待检查")}</span></strong>
      <p>${escapeHtml(livePilotText(protection.detail || "等待首单后复盘保护单。"))}</p>
      <p>父单 ${escapeHtml(protection.parent_order_id || "-")}；子单 ${fmt(protection.child_count || 0)} 个；缺失 ${escapeHtml(missingKinds.join("、") || "无")}；孤儿 ${fmt(protection.orphan_child_count || 0)} 个。</p>
      <code>${escapeHtml(childStatusText)}</code>
    </article>
    <article>
      <strong>OMS / 告警 / 审计</strong>
      <p>待对账 ${fmt(oms.needs_reconcile || 0)}；未知状态 ${fmt(oms.unknown_venue_status || 0)}；活跃告警 ${fmt(alerts.active || 0)}；审计断链 ${fmt(audit.broken_count || 0)}。</p>
    </article>
    ${visibleChecks.map((check) => `
      <article>
        <strong>${escapeHtml(check.label || check.id || "检查项")}<span class="badge ${badgeMap[check.status] || "warn"}">${escapeHtml(statusMap[check.status] || check.status || "-")}</span></strong>
        <p>${escapeHtml(livePilotText(check.detail || "-"))}</p>
      </article>
    `).join("")}
    ${hiddenChecksCount ? `
      <article class="postflight-muted">
        <strong>已折叠通过项<span class="badge pass">${fmt(hiddenChecksCount)} 项</span></strong>
        <p>只保留阻塞、待处理和关键保护链路，减少页面滚动。</p>
      </article>
    ` : ""}
  `;
}

function renderLiveBlockerResolution(resolution) {
  if (!els.liveBlockerStatus) return;
  if (!resolution) {
    els.liveBlockerStatus.textContent = "未生成";
    els.liveBlockerSummary.textContent = "把当前实盘阻塞项翻译成服务器环境变量、命令和验收证据。";
    els.liveBlockerList.innerHTML = "";
    if (els.liveNextActionStatus) {
      els.liveNextActionStatus.textContent = "等待读取";
      els.liveNextActionSummary.textContent = "自动汇总当前阻塞项，并给出最多三条可执行动作。";
      els.liveNextActionList.innerHTML = "";
    }
    return;
  }
  const statusMap = {
    blocked: "仍有阻塞",
    ready_to_enable_live: "可启用实盘档案",
    ready_to_arm: "可短时武装",
    ready_for_live_order: "可提交首单",
  };
  const badgeMap = {
    blocked: "fail",
    ready_to_enable_live: "warn",
    ready_to_arm: "warn",
    ready_for_live_order: "pass",
  };
  const steps = resolution.steps || [];
  const latentChecks = resolution.latent_live_checks || [];
  const status = resolution.status || "blocked";
  els.liveBlockerStatus.textContent = statusMap[status] || status;
  els.liveBlockerSummary.textContent =
    livePilotText(resolution.next_action || "") ||
    `剩余 ${fmt((resolution.blocking_gates || []).length)} 个阻塞门禁。`;
  if (els.liveNextActionStatus) {
    const compactSteps = steps.length ? steps : latentChecks;
    els.liveNextActionStatus.textContent = statusMap[status] || status;
    els.liveNextActionSummary.textContent =
      livePilotText(resolution.next_action || "") ||
      `剩余 ${fmt((resolution.blocking_gates || []).length)} 个阻塞门禁。`;
    els.liveNextActionList.innerHTML = compactSteps.length
      ? compactSteps.slice(0, 3).map((step, index) => {
          const command = (step.commands || [])[0] || "";
          const envVars = (step.env_vars || []).slice(0, 3).join(" / ");
          const proof = (step.proof || [])[0] || "";
          return `
            <article>
              <strong>${fmt(index + 1)}. ${escapeHtml(step.label || step.id || "下一步")}<span class="badge ${step.phase === "current_blocker" ? "fail" : "warn"}">${step.phase === "current_blocker" ? "当前阻塞" : "启用后复核"}</span></strong>
              <p>${escapeHtml(livePilotText(step.detail || proof || "-"))}</p>
              ${command ? `<code>${escapeHtml(command)}</code>` : envVars ? `<code>${escapeHtml(envVars)}</code>` : ""}
            </article>
          `;
        }).join("")
      : `
        <article>
          <strong>没有非武装阻塞<span class="badge pass">可推进</span></strong>
          <p>${escapeHtml(livePilotText(resolution.next_action || "继续执行短时武装和首单流程。"))}</p>
        </article>
      `;
  }
  els.liveBlockerList.innerHTML = `
    <article>
      <strong>解除路线<span class="badge ${badgeMap[status] || "warn"}">${escapeHtml(statusMap[status] || status)}</span></strong>
      <p>环境 ${escapeHtml(resolution.app_env || "-")}；模式 ${escapeHtml(resolution.exchange_mode || "-")}；阻塞 ${escapeHtml((resolution.blocking_gates || []).join(", ") || "无")}。</p>
    </article>
    ${steps.map((step, index) => {
      const envVars = (step.env_vars || []).slice(0, 8).map((item) => `<code>${escapeHtml(item)}</code>`).join(" ");
      const commands = (step.commands || []).slice(0, 5).map((item) => `<li><code>${escapeHtml(item)}</code></li>`).join("");
      const proof = (step.proof || []).slice(0, 5).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
      return `
        <article>
          <strong>${fmt(index + 1)}. ${escapeHtml(step.label || step.id || "阻塞项")}<span class="badge ${step.status === "fail" ? "fail" : "warn"}">${escapeHtml(step.status || "pending")}</span></strong>
          <p>${escapeHtml(livePilotText(step.detail || "-"))}</p>
          ${envVars ? `<p>${envVars}</p>` : ""}
          ${commands ? `<ul>${commands}</ul>` : ""}
          ${proof ? `<p>验收证据</p><ul>${proof}</ul>` : ""}
        </article>
      `;
    }).join("")}
    ${latentChecks.length ? `
      <article>
        <strong>启用 live 后会立刻复核<span class="badge warn">${fmt(latentChecks.length)} 项</span></strong>
        <p>这些不是当前本地阻塞项，但切到 live_guarded 后会变成实盘前置证据，建议在服务器上提前准备。</p>
      </article>
      ${latentChecks.map((step) => {
        const commands = (step.commands || []).slice(0, 3).map((item) => `<li><code>${escapeHtml(item)}</code></li>`).join("");
        const proof = (step.proof || []).slice(0, 3).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
        return `
          <article>
            <strong>${escapeHtml(step.label || step.id || "预检项")}<span class="badge warn">${escapeHtml(step.status || "pending")}</span></strong>
            <p>${escapeHtml(livePilotText(step.detail || "-"))}</p>
            ${commands ? `<ul>${commands}</ul>` : ""}
            ${proof ? `<p>验收证据</p><ul>${proof}</ul>` : ""}
          </article>
        `;
      }).join("")}
    ` : ""}
    ${steps.length ? "" : `
      <article>
        <strong>没有非武装阻塞</strong>
        <p>${escapeHtml(livePilotText(resolution.next_action || "继续执行短时武装和首单流程。"))}</p>
      </article>
    `}
  `;
}

function renderServerLiveReadiness(status) {
  if (!els.serverLiveReadinessStatus) return;
  const value = status || {};
  const summary = value.last_summary || {};
  const blockers = summary.blocking_gates || [];
  const evidence = summary.evidence_paths || {};
  const evidenceLabels = {
    go_live_report_json: "准入 JSON",
    go_live_report_markdown: "准入报告",
    server_go_live_audit_json: "审计 JSON",
    server_go_live_audit_markdown: "审计报告",
    live_launch_plan_json: "上线计划 JSON",
    live_launch_plan_markdown: "上线计划",
    live_ops_handoff_json: "交接单 JSON",
    live_ops_handoff_markdown: "实盘交接单",
    server_bundle: "部署包",
    server_bundle_sha256: "部署包 SHA256",
    live_launch_kit: "上线套件",
    live_launch_kit_sha256: "上线套件 SHA256",
    live_env_pack: "环境模板包",
    live_env_pack_sha256: "环境模板包 SHA256",
    state_backup: "状态备份",
  };
  const statusMap = {
    idle: "未运行",
    running: "运行中",
    completed: "已完成",
    failed: "失败",
  };
  els.serverLiveReadinessStatus.textContent = statusMap[value.status] || value.status || "-";
  els.serverLiveReadinessStarted.textContent = value.started_at ? shortTime(value.started_at) : "-";
  els.serverLiveReadinessReport.textContent = value.last_report_path || summary.report_path || "-";
  els.serverLiveReadinessBlockers.textContent = Array.isArray(blockers)
    ? blockers.length
      ? blockers.join(", ")
      : summary.final_live_ready
        ? "无"
        : "-"
    : "-";
  if (els.serverLiveReadinessEvidence) {
    const rows = Object.entries(evidence)
      .map(([key, itemValue]) => `
        <article>
          <span>${escapeHtml(evidenceLabels[key] || key)}</span>
          <strong>${escapeHtml(itemValue ? String(itemValue) : "等待生成")}</strong>
        </article>
      `);
    els.serverLiveReadinessEvidence.innerHTML = rows.length
      ? rows.join("")
      : `<article><span>证据包</span><strong>${summary.report_path ? "等待生成明细" : "暂无"}</strong></article>`;
  }
  if (els.runServerLiveReadiness) {
    els.runServerLiveReadiness.disabled = Boolean(value.running);
  }
  if (els.cancelServerLiveReadiness) {
    els.cancelServerLiveReadiness.disabled = !value.running;
  }
}

function renderLiveEnvProfile(profile) {
  if (!els.liveEnvProfileStatus) return;
  const value = profile || {};
  const statusMap = {
    pass: "已通过",
    warn: "有警告",
    fail: "未通过",
  };
  const targetMap = {
    mvp_server: "MVP 服务器",
    testnet_validate: "Testnet 验证",
    testnet_place: "Testnet 下单",
    live_guarded: "实盘保护模式",
  };
  const status = value.status || "-";
  const missing = value.missing_required_vars || [];
  const nextActions = value.next_actions || [];
  els.liveEnvProfileStatus.textContent = statusMap[status] || status;
  els.liveEnvProfileStatus.style.color = status === "pass" ? "#10845b" : status === "warn" ? "#8a6400" : "#cf2e2e";
  els.liveEnvProfileTarget.textContent = targetMap[value.target] || value.target || "-";
  els.liveEnvProfileMissing.textContent = missing.length ? missing.slice(0, 4).join(", ") : "无";
  els.liveEnvProfileNext.textContent = nextActions.length ? nextActions[0] : "-";
  const importantChecks = (value.failed_checks || [])
    .concat(value.warnings || [])
    .slice(0, 8);
  const checks = importantChecks.length ? importantChecks : (value.checks || []).slice(0, 6);
  els.liveEnvProfileList.innerHTML = checks.length
    ? checks.map((item) => `
      <article>
        <strong>${escapeHtml(item.label || item.id || "-")}<span class="badge ${item.status === "pass" ? "pass" : item.status === "warn" ? "warn" : "fail"}">${statusText(item.status)}</span></strong>
        <p>${escapeHtml(item.detail || "-")}</p>
        <span>${escapeHtml((item.env_vars || []).join(", ") || "环境变量")}</span>
      </article>
    `).join("")
    : `<article><strong>环境剖面</strong><p>等待审计结果。</p></article>`;
}

function renderRiskCenter(risk, account) {
  if (!risk) {
    els.riskCenterStatus.textContent = "-";
    els.riskEmergency.textContent = "-";
    els.riskOpenPositions.textContent = "-";
    els.riskDailyPnl.textContent = "-";
    return;
  }
  els.riskCenterStatus.textContent = risk.emergency_stop ? "紧急停止中" : "受控运行";
  if (!riskDirty) {
    els.riskMaxLeverage.value = fmt(risk.max_leverage);
    els.riskMaxPosition.value = fmt((risk.max_position_pct || 0) * 100);
    els.riskMaxNotional.value = fmt(risk.max_order_notional_usdt);
    els.riskDailyLoss.value = fmt((risk.max_daily_loss_pct || 0) * 100);
    els.riskMaxOpen.value = fmt(risk.max_open_positions);
    els.riskLossStreak.value = fmt(risk.max_consecutive_losses);
    els.riskSymbols.value = (risk.allowed_symbols || []).join(",");
  }
  els.riskEmergency.textContent = risk.emergency_stop ? "开启" : "关闭";
  els.riskEmergency.style.color = risk.emergency_stop ? "#cf2e2e" : "#10845b";
  els.riskOpenPositions.textContent = `${account?.open_position_count || 0} / ${risk.max_open_positions}`;
  els.riskDailyPnl.textContent = `${fmt(risk.daily_realized_pnl_usdt || 0)} USDT`;
  const pnl = Number(risk.daily_realized_pnl_usdt || 0);
  els.riskDailyPnl.style.color = pnl > 0 ? "#10845b" : pnl < 0 ? "#cf2e2e" : "";
}

function renderMetrics(data) {
  const run = data.latest_run;
  els.systemStatus.textContent = data.system.emergency_stop ? "紧急停止" : "在线";
  els.systemStatus.style.borderColor = data.system.emergency_stop
    ? "#ffb4b4"
    : "rgba(255,255,255,.25)";
  els.systemStatus.dataset.status = data.system.emergency_stop ? "danger" : "ok";
  els.runStatus.textContent = run ? statusText(run.status) : "未启动";
  els.finalAction.textContent = sideText(run?.final_action);
  els.riskStatus.textContent = statusText(run?.risk_status);
  els.environment.textContent = `${data.system.environment === "local" ? "本地" : data.system.environment} / ${modeText(data.system.mode)}`;
  els.runId.textContent = run ? `运行 ${run.id}` : "无运行";
  document.querySelector(".state-card")?.setAttribute("data-status", data.system.emergency_stop ? "danger" : run?.status === "completed" ? "ok" : "neutral");
  document.querySelector(".action-card")?.setAttribute("data-status", run?.final_action === "buy" || run?.final_action === "sell" ? "active" : "neutral");
  document.querySelector(".risk-card")?.setAttribute("data-status", run?.risk_status === "rejected" ? "danger" : run?.risk_status === "approved" ? "ok" : "neutral");
  document.querySelector(".env-card")?.setAttribute("data-status", data.system.mode === "live" ? "danger" : data.system.mode?.includes("testnet") ? "active" : "neutral");
}

function money(value) {
  if (value === null || value === undefined || value === "") return "-";
  return `${fmt(value)} USDT`;
}

function renderAccount(account) {
  const data = account || {};
  els.accountEquity.textContent = money(data.equity_usdt);
  els.freeMargin.textContent = money(data.free_margin_usdt);
  els.unrealizedPnl.textContent = money(data.unrealized_pnl_usdt);
  els.grossExposure.textContent = money(data.gross_exposure_usdt);
  const pnl = Number(data.unrealized_pnl_usdt || 0);
  els.unrealizedPnl.style.color = pnl > 0 ? "#10845b" : pnl < 0 ? "#cf2e2e" : "";
  els.unrealizedPnl.closest(".metric")?.setAttribute("data-status", pnl > 0 ? "ok" : pnl < 0 ? "danger" : "neutral");
  els.accountEquity.closest(".metric")?.setAttribute("data-status", "active");
  els.freeMargin.closest(".metric")?.setAttribute("data-status", "ok");
  els.grossExposure.closest(".metric")?.setAttribute("data-status", "neutral");
}

function renderTimeline(events) {
  if (!events.length) {
    els.timeline.innerHTML =
      `<div class="empty" style="min-height: 360px">点击“启动一次分析”后，这里会显示每一步代理和风控记录</div>`;
    return;
  }
  const limit = 18;
  const visibleEvents = events.slice(-limit).reverse();
  const hiddenCount = Math.max(0, events.length - visibleEvents.length);
  const summary = hiddenCount
    ? `<div class="timeline-summary">显示最近 ${visibleEvents.length} 条关键事件，完整原始记录在“证据”标签中保留。</div>`
    : "";
  els.timeline.innerHTML = summary + visibleEvents
    .map(
      (event) => `
        <article class="event" data-kind="${event.kind}">
          <div class="event-time">${shortTime(event.ts)}<br />${kindText(event.kind)}</div>
          <div>
            <span class="event-actor">${actorText(event.actor)}</span>
            <p class="event-title">${event.title}</p>
            <p class="event-body">${localizedText(event.body)}</p>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderMarket(snapshot) {
  if (!snapshot) {
    els.marketSnapshot.innerHTML = `<div><dt>状态</dt><dd>等待数据</dd></div>`;
    return;
  }
  const labels = {
    symbol: "交易对",
    data_source: "数据源",
    fallback: "是否回退",
    mark_price: "标记价格",
    index_price: "指数价格",
    change_24h_pct: "24h 涨跌 %",
    realized_volatility_pct: "波动率 %",
    funding_rate_pct: "资金费率 %",
    open_interest_change_pct: "持仓量变化 %",
    open_interest_value_usdt: "持仓价值 USDT",
    long_short_ratio: "多空比",
    depth_imbalance: "深度不平衡",
    depth_bid_qty: "买盘深度",
    depth_ask_qty: "卖盘深度",
    quote_volume_usdt: "24h 成交额 USDT",
    liquidation_pressure: "清算压力",
    source_error: "回退原因",
  };
  els.marketSnapshot.innerHTML = Object.entries(labels)
    .filter(([key]) => snapshot[key] !== undefined && snapshot[key] !== null)
    .map(([key, label]) => `<div><dt>${label}</dt><dd>${marketValueText(key, snapshot[key])}</dd></div>`)
    .join("");
}

function marketValueText(key, value) {
  if (key === "data_source") return sourceText(value);
  if (key === "fallback") return boolText(Boolean(value));
  if (key === "liquidation_pressure") return sourceText(value);
  return fmt(value);
}

function renderResearch(research) {
  if (!research) {
    els.researchStatus.textContent = "等待运行";
    els.researchSummary.textContent = "启动一次分析后，这里会显示研究工件、证据缺口和执行边界。";
    els.researchProtocol.innerHTML = "";
    els.researchArtifacts.innerHTML = "";
    els.researchGuardrails.innerHTML = "";
    return;
  }
  els.researchStatus.textContent = statusText(research.status);
  els.researchSummary.textContent = localizedText(research.summary);
  const protocolLabels = {
    input_treatment: "输入处理",
    exchange_format: "交换格式",
    decision_memory: "决策记忆",
    human_review: "人工复核",
  };
  els.researchProtocol.innerHTML = Object.entries(protocolLabels)
    .map(([key, label]) => {
      const value = research.protocol?.[key] || "-";
      return `<article><span>${label}</span><strong>${localizedText(value)}</strong></article>`;
    })
    .join("");
  els.researchArtifacts.innerHTML = (research.artifacts || [])
    .map((artifact) => {
      const evidence = (artifact.evidence || []).map((item) => `<li>${localizedText(item)}</li>`).join("");
      const gaps = (artifact.gaps || []).length
        ? (artifact.gaps || []).map((item) => `<li>${localizedText(item)}</li>`).join("")
        : "<li>暂无缺口</li>";
      return `
        <article class="research-card">
          <div>
            <span class="event-actor">${localizedText(artifact.reference)}</span>
            <h3>${localizedText(artifact.role)}<span class="badge ${artifact.status === "ready" || artifact.status === "active" ? "pass" : artifact.status === "partial" ? "warn" : "fail"}">${statusText(artifact.status)}</span></h3>
          </div>
          <p class="event-body">${localizedText(artifact.summary)}</p>
          <div class="research-columns">
            <div><strong>证据</strong><ul>${evidence}</ul></div>
            <div><strong>缺口</strong><ul>${gaps}</ul></div>
          </div>
        </article>
      `;
    })
    .join("");
  els.researchGuardrails.innerHTML = `
    <strong>护栏</strong>
    <ul>${(research.guardrails || []).map((item) => `<li>${localizedText(item)}</li>`).join("")}</ul>
  `;
}

function planeText(plane) {
  const map = {
    research: "研究平面",
    control: "控制平面",
    execution: "执行平面",
    observability: "观测平面",
  };
  return map[plane] || plane || "-";
}

function architectureStatusText(status) {
  const map = {
    implemented: "已实现",
    partial: "部分实现",
    gap: "缺口",
    active: "生效中",
  };
  return map[status] || statusText(status);
}

function architectureBadge(status) {
  if (status === "implemented" || status === "active") return "pass";
  if (status === "partial") return "warn";
  return "fail";
}

function renderArchitecture(architecture) {
  if (!architecture) {
    els.architectureStatus.textContent = "-";
    els.architectureSummary.textContent = "";
    els.executiveSummary.innerHTML = "";
    els.projectDefaultTarget.innerHTML = "";
    els.projectAssumptionReasoning.textContent = "";
    els.assumptionDefaults.innerHTML = "";
    els.complianceTiers.innerHTML = "";
    els.exchangeSelection.innerHTML = "";
    els.anthropicReferencePremise.innerHTML = "";
    els.anthropicReferenceLayers.innerHTML = "";
    els.anthropicReferenceBoundaries.innerHTML = "";
    els.marketResearcherGuardrails.innerHTML = "";
    els.agentSdkCapabilities.innerHTML = "";
    els.tradingagentsPositioning.innerHTML = "";
    els.tradingagentsRoles.innerHTML = "";
    els.tradingagentsFlow.innerHTML = "";
    els.tradingagentsCommunication.innerHTML = "";
    els.tradingagentsRuntime.innerHTML = "";
    els.tradingagentsLimitations.innerHTML = "";
    els.referenceArchitecturePaths.innerHTML = "";
    els.referenceAbsorbPoints.innerHTML = "";
    els.referenceImplementationRule.innerHTML = "";
    els.layeredArchitectureSummary.innerHTML = "";
    els.layeredArchitecturePlanes.innerHTML = "";
    els.venueAdapterRule.innerHTML = "";
    els.strategyEngineSplit.innerHTML = "";
    els.architectureGraphNodes.innerHTML = "";
    els.architectureGraphEdges.innerHTML = "";
    els.architecturePrinciples.innerHTML = "";
    els.architecturePlanes.innerHTML = "";
    els.architectureComponents.innerHTML = "";
    els.moduleDefinitionSummary.textContent = "";
    els.moduleDefinitionTable.innerHTML = "";
    els.moduleMatrix.innerHTML = "";
    els.implementationNoteSummary.textContent = "";
    els.implementationNoteTable.innerHTML = "";
    els.implementationNotes.innerHTML = "";
    els.entitySummary.textContent = "";
    els.entityFocus.textContent = "";
    els.entityMermaid.textContent = "";
    els.entityList.innerHTML = "";
    els.entityRelationships.innerHTML = "";
    els.uiIaSummary.textContent = "";
    els.uiIaRoot.textContent = "";
    els.uiNavigationTree.textContent = "";
    els.uiNavigation.innerHTML = "";
    els.uiPageComponentSummary.textContent = "";
    els.uiPageComponents.innerHTML = "";
    els.uiTooling.innerHTML = "";
    els.interactionFlowSummary.textContent = "";
    els.interactionFlowSteps.innerHTML = "";
    els.mainLoopSteps.innerHTML = "";
    els.responsiveGuidance.innerHTML = "";
    els.chartGuidance.innerHTML = "";
    els.technicalSummary.textContent = "";
    els.technicalPrinciples.innerHTML = "";
    els.technicalStack.innerHTML = "";
    els.apiPriority.innerHTML = "";
    els.implementationRoadmap.innerHTML = "";
    els.scaleComparison.innerHTML = "";
    els.recommendedStart.innerHTML = "";
    els.riskBoundary.innerHTML = "";
    els.testingPrinciple.textContent = "";
    els.riskRegister.innerHTML = "";
    els.acceptanceMatrix.innerHTML = "";
    els.goLiveGates.innerHTML = "";
    return;
  }
  els.architectureStatus.textContent = "当前版本对照";
  els.architectureSummary.textContent = localizedText(architecture.summary);
  els.executiveSummary.innerHTML = (architecture.executive_summary || [])
    .map(
      (item) => `
        <article class="executive-card">
          <h3>${localizedText(item.title)}</h3>
          <p>${localizedText(item.summary)}</p>
          <p><span>当前 MVP</span>${localizedText(item.mvp_state)}</p>
          <p><span>生产规则</span>${localizedText(item.production_rule)}</p>
        </article>
      `,
    )
    .join("");
  const projectAssumptions = architecture.project_goals_assumptions || {};
  els.projectDefaultTarget.innerHTML = `
    <strong>首阶段默认目标</strong>
    <p>${localizedText(projectAssumptions.default_target)}</p>
  `;
  els.projectAssumptionReasoning.textContent = localizedText(projectAssumptions.reasoning);
  els.assumptionDefaults.innerHTML = (projectAssumptions.assumption_defaults || [])
    .map(
      (item) => `
        <tr>
          <td>${localizedText(item.item)}</td>
          <td>${localizedText(item.current_status)}</td>
          <td>${localizedText(item.options)}</td>
          <td>${localizedText(item.fit)}</td>
          <td>${localizedText(item.recommended_default)}</td>
        </tr>
      `,
    )
    .join("");
  els.complianceTiers.innerHTML = (projectAssumptions.compliance_tiers || [])
    .map(
      (tier) => `
        <article class="guidance-card">
          <h3>${localizedText(tier.tier)}</h3>
          <p><strong>关注点</strong>${localizedText(tier.focus)}</p>
          <p><strong>默认动作</strong>${localizedText(tier.default_action)}</p>
        </article>
      `,
    )
    .join("");
  els.exchangeSelection.innerHTML = (projectAssumptions.exchange_selection || [])
    .map(
      (venue) => `
        <article class="guidance-card">
          <h3>${localizedText(venue.venue)}<span>${localizedText(venue.phase)}</span></h3>
          <p><strong>选择理由</strong>${localizedText(venue.why)}</p>
          <p><strong>工程备注</strong>${localizedText(venue.engineering_notes)}</p>
        </article>
      `,
    )
    .join("");
  const anthropicReference = architecture.anthropic_reference_project || {};
  els.anthropicReferencePremise.innerHTML = `
    <strong>${localizedText(anthropicReference.title)}</strong>
    <p>${localizedText(anthropicReference.interpretation_premise)}</p>
    <p>${localizedText(anthropicReference.not_a_trading_terminal)}</p>
    <ul>${(anthropicReference.deployment_surfaces || []).map((item) => `<li>${localizedText(item)}</li>`).join("")}</ul>
  `;
  els.anthropicReferenceLayers.innerHTML = (anthropicReference.repository_layers || [])
    .map(
      (layer) => `
        <article class="guidance-card">
          <h3>${localizedText(layer.layer)}</h3>
          <p><strong>含义</strong>${localizedText(layer.meaning)}</p>
          <p><strong>MVP 映射</strong>${localizedText(layer.mvp_mapping)}</p>
        </article>
      `,
    )
    .join("");
  els.anthropicReferenceBoundaries.innerHTML = `
    <strong>边界契约</strong>
    <ul>${(anthropicReference.boundary_contract || []).map((item) => `<li>${localizedText(item)}</li>`).join("")}</ul>
  `;
  const marketResearcher = anthropicReference.market_researcher || {};
  els.marketResearcherGuardrails.innerHTML = `
    <strong>market-researcher 护栏</strong>
    <p>${localizedText(marketResearcher.workflow)}</p>
    <ul>${(marketResearcher.guardrails || []).map((item) => `<li>${localizedText(item)}</li>`).join("")}</ul>
  `;
  els.agentSdkCapabilities.innerHTML = (anthropicReference.agent_sdk_capabilities || [])
    .map(
      (item) => `
        <tr>
          <td>${localizedText(item.capability)}</td>
          <td>${localizedText(item.production_value)}</td>
          <td>${localizedText(item.mvp_boundary)}</td>
        </tr>
      `,
    )
    .join("");
  const tradingAgents = architecture.tradingagents_reference_project || {};
  const communication = tradingAgents.structured_communication || {};
  const runtime = tradingAgents.implementation_runtime || {};
  els.tradingagentsPositioning.innerHTML = `
    <strong>${localizedText(tradingAgents.title)}</strong>
    <p>${localizedText(tradingAgents.core_positioning)}</p>
    <p>${localizedText(tradingAgents.portfolio_manager_approval)}</p>
    <p>${localizedText(tradingAgents.borrow_do_not_copy)}</p>
  `;
  els.tradingagentsRoles.innerHTML = (tradingAgents.simulated_company_roles || [])
    .map(
      (role) => `
        <tr>
          <td>${localizedText(role.role)}</td>
          <td>${localizedText(role.team)}</td>
          <td>${localizedText(role.responsibility)}</td>
        </tr>
      `,
    )
    .join("");
  els.tradingagentsFlow.innerHTML = (tradingAgents.architecture_flow || [])
    .map((step, index) => `<span>${index + 1}. ${localizedText(step)}</span>`)
    .join("");
  els.tradingagentsCommunication.innerHTML = `
    <strong>通信协议</strong>
    <p>${localizedText(communication.why_it_matters)}</p>
    <p><strong>${localizedText(communication.protocol)}</strong></p>
    <ul>${(communication.preferred_outputs || []).map((item) => `<li>${localizedText(item)}</li>`).join("")}</ul>
    <p>${localizedText(communication.avoid)}</p>
    <p>${localizedText(communication.mvp_mapping)}</p>
  `;
  els.tradingagentsRuntime.innerHTML = `
    <strong>运行时与恢复</strong>
    <ul>
      <li>${localizedText(runtime.framework)}</li>
      <li>${localizedText(runtime.graph_call)}</li>
      <li>${localizedText(runtime.llm_provider_support)}</li>
      <li>${localizedText(runtime.decision_log)}</li>
      <li>${localizedText(runtime.checkpoint_resume)}</li>
      <li>${localizedText(runtime.mvp_mapping)}</li>
    </ul>
  `;
  els.tradingagentsLimitations.innerHTML = (tradingAgents.limitations || [])
    .map(
      (item) => `
        <article class="guidance-card">
          <h3>${localizedText(item.limitation)}</h3>
          <p>${localizedText(item.impact)}</p>
        </article>
      `,
    )
    .join("");
  const synthesis = architecture.reference_synthesis || {};
  els.referenceArchitecturePaths.innerHTML = (synthesis.architecture_paths || [])
    .map(
      (path) => `
        <article class="guidance-card">
          <h3>${localizedText(path.reference)}</h3>
          <ol>${(path.steps || []).map((step) => `<li>${localizedText(step)}</li>`).join("")}</ol>
        </article>
      `,
    )
    .join("");
  els.referenceAbsorbPoints.innerHTML = (synthesis.absorb_points || [])
    .map(
      (item) => `
        <article class="guidance-card">
          <h3>${localizedText(item.source)}</h3>
          <p>${localizedText(item.point)}</p>
        </article>
      `,
    )
    .join("");
  els.referenceImplementationRule.innerHTML = `
    <strong>${localizedText(synthesis.title)}</strong>
    <p>${localizedText(synthesis.implementation_rule)}</p>
  `;
  const layeredArchitecture = architecture.layered_architecture || {};
  const architectureGraph = layeredArchitecture.architecture_graph || {};
  const venueAdapterRule = layeredArchitecture.venue_adapter_rule || {};
  els.layeredArchitectureSummary.innerHTML = `
    <strong>${localizedText(layeredArchitecture.title)}</strong>
    <p>${localizedText(layeredArchitecture.summary)}</p>
    <p>${localizedText(layeredArchitecture.source_note)}</p>
    <p>${localizedText(layeredArchitecture.integration_statement)}</p>
  `;
  els.layeredArchitecturePlanes.innerHTML = (layeredArchitecture.planes || [])
    .map(
      (plane) => `
        <article class="architecture-card">
          <h3>${localizedText(plane.name)}</h3>
          <p><strong>允许范围</strong>${localizedText(plane.allowed)}</p>
          <p><strong>职责</strong>${localizedText(plane.responsibility)}</p>
          <p><strong>执行边界</strong>${localizedText(plane.execution_boundary)}</p>
        </article>
      `,
    )
    .join("");
  els.venueAdapterRule.innerHTML = `
    <strong>交易所适配规则</strong>
    <p>${localizedText(venueAdapterRule.summary)}</p>
    <ul>${(venueAdapterRule.api_differences || []).map((item) => `<li>${localizedText(item)}</li>`).join("")}</ul>
    <p>${localizedText(venueAdapterRule.production_requirement)}</p>
  `;
  els.strategyEngineSplit.innerHTML = (layeredArchitecture.strategy_engine_split || [])
    .map(
      (part) => `
        <article class="guidance-card">
          <h3>${localizedText(part.part)}<span>${localizedText(part.plane)}</span></h3>
          <p><strong>职责</strong>${localizedText(part.responsibility)}</p>
          <p><strong>输出</strong>${localizedText(part.output)}</p>
        </article>
      `,
    )
    .join("");
  els.architectureGraphNodes.innerHTML = (architectureGraph.nodes || [])
    .map(
      (node) => `
        <tr>
          <td>${localizedText(node.id)}</td>
          <td>${localizedText(node.label)}</td>
          <td>${planeText(node.plane)}</td>
        </tr>
      `,
    )
    .join("");
  els.architectureGraphEdges.innerHTML = (architectureGraph.edges || [])
    .map((edge) => `<span>${localizedText(edge.from)} -> ${localizedText(edge.to)}</span>`)
    .join("");
  els.architecturePrinciples.innerHTML = `
    <strong>吸收原则</strong>
    <ul>${(architecture.principles || []).map((item) => `<li>${localizedText(item)}</li>`).join("")}</ul>
  `;
  els.architecturePlanes.innerHTML = (architecture.planes || [])
    .map((plane) => {
      const implemented = (plane.implemented || []).map((item) => `<li>${localizedText(item)}</li>`).join("");
      const gaps = (plane.gaps || []).map((item) => `<li>${localizedText(item)}</li>`).join("");
      return `
        <article class="architecture-card">
          <h3>${localizedText(plane.name)}<span class="badge ${architectureBadge(plane.status)}">${architectureStatusText(plane.status)}</span></h3>
          <p class="event-body">${localizedText(plane.responsibility)}</p>
          <div class="research-columns">
            <div><strong>已有</strong><ul>${implemented}</ul></div>
            <div><strong>缺口</strong><ul>${gaps}</ul></div>
          </div>
        </article>
      `;
    })
    .join("");
  els.architectureComponents.innerHTML = (architecture.components || [])
    .map(
      (component) => `
        <tr>
          <td>${localizedText(component.label || component.name)}</td>
          <td>${planeText(component.plane)}</td>
          <td><span class="badge ${architectureBadge(component.status)}">${architectureStatusText(component.status)}</span></td>
          <td>${localizedText(component.detail)}</td>
        </tr>
      `,
    )
    .join("");
  const moduleDefinitionTable = architecture.module_definition_table || {};
  els.moduleDefinitionSummary.textContent = localizedText(moduleDefinitionTable.summary);
  els.moduleDefinitionTable.innerHTML = (moduleDefinitionTable.rows || [])
    .map(
      (row) => `
        <tr>
          <td>${localizedText(row.module)}</td>
          <td>${localizedText(row.responsibility)}</td>
          <td>${localizedText(row.production_note)}</td>
        </tr>
      `,
    )
    .join("");
  els.moduleMatrix.innerHTML = (architecture.module_matrix || [])
    .map(
      (module) => `
        <article class="module-card">
          <h3>${localizedText(module.module)}</h3>
          <p><strong>建议职责</strong>${localizedText(module.responsibility)}</p>
          <p><strong>生产化要点</strong>${localizedText(module.production_note)}</p>
          <p><strong>当前</strong>${localizedText(module.current)}</p>
          <p><strong>下一步</strong>${localizedText(module.required_next)}</p>
        </article>
      `,
    )
    .join("");
  const implementationNoteTable = architecture.implementation_note_table || {};
  els.implementationNoteSummary.textContent = localizedText(implementationNoteTable.summary);
  els.implementationNoteTable.innerHTML = (implementationNoteTable.rows || [])
    .map(
      (row) => `
        <tr>
          <td>${localizedText(row.topic)}</td>
          <td>${localizedText(row.basis)}</td>
          <td>${localizedText(row.recommendation)}</td>
        </tr>
      `,
    )
    .join("");
  els.implementationNotes.innerHTML = (architecture.implementation_notes || [])
    .map(
      (note) => `
        <tr>
          <td>${localizedText(note.topic)}</td>
          <td><span class="badge ${architectureBadge(note.status)}">${architectureStatusText(note.status)}</span></td>
          <td>${localizedText(note.basis)}</td>
          <td>${localizedText(note.current_control)}</td>
          <td>${localizedText(note.required_next)}</td>
          <td>${localizedText(note.recommendation)}</td>
        </tr>
      `,
    )
    .join("");
  const entityModel = architecture.entity_model || {};
  els.entitySummary.textContent = localizedText(entityModel.summary);
  els.entityFocus.textContent = localizedText(entityModel.focus);
  els.entityMermaid.textContent = entityModel.mermaid || "";
  els.entityList.innerHTML = (entityModel.entities || [])
    .map(
      (entity) => `
        <article class="entity-card">
          <h3>${localizedText(entity.name)}<span>${localizedText(entity.label)}</span></h3>
          <p>${localizedText(entity.current)}</p>
        </article>
      `,
    )
    .join("");
  els.entityRelationships.innerHTML = (entityModel.relationships || [])
    .map(
      (relationship) => `
        <tr>
          <td>${localizedText(relationship.from)}</td>
          <td><span class="relation-pill">${localizedText(relationship.relation)}</span></td>
          <td>${localizedText(relationship.to)}</td>
          <td>${localizedText(relationship.detail)}</td>
        </tr>
      `,
    )
    .join("");
  const uiIa = architecture.ui_information_architecture || {};
  els.uiIaSummary.textContent = localizedText(uiIa.summary);
  els.uiIaRoot.textContent = uiIa.root ? `根节点：${localizedText(uiIa.root)}` : "";
  els.uiNavigationTree.textContent = uiIa.navigation_tree || "";
  els.uiNavigation.innerHTML = (uiIa.navigation || [])
    .map((group) => {
      const children = (group.children || []).length
        ? `<ul>${(group.children || []).map((child) => `<li>${localizedText(child)}</li>`).join("")}</ul>`
        : "<ul><li>首屏状态总览</li></ul>";
      return `
        <article class="ui-nav-card">
          <h3>${localizedText(group.name)}</h3>
          ${children}
        </article>
      `;
    })
    .join("");
  const pageComponentTable = uiIa.page_component_table || {};
  const pageComponentRows = pageComponentTable.rows || uiIa.page_components || [];
  els.uiPageComponentSummary.textContent = localizedText(pageComponentTable.summary);
  els.uiPageComponents.innerHTML = pageComponentRows
    .map(
      (page) => `
        <tr>
          <td>${localizedText(page.page)}</td>
          <td>${localizedText(page.components)}</td>
          <td>${localizedText(page.design_focus)}</td>
        </tr>
      `,
    )
    .join("");
  els.uiTooling.innerHTML = `
    <strong>组件能力</strong>
    <ul>${(uiIa.component_tooling || []).map((tool) => `<li>${localizedText(tool)}</li>`).join("")}</ul>
  `;
  const flow = uiIa.interaction_flow || {};
  els.interactionFlowSummary.textContent = localizedText(flow.summary);
  els.interactionFlowSteps.innerHTML = (flow.steps || [])
    .map(
      (step, index) => `
        <article class="flow-step">
          <span>${index + 1}</span>
          <h3>${localizedText(step.name)}</h3>
          <p>${localizedText(step.current)}</p>
        </article>
      `,
    )
    .join("");
  els.mainLoopSteps.innerHTML = (flow.main_loop || [])
    .map(
      (step, index) => `
        <article class="flow-step loop-step">
          <span>${index + 1}</span>
          <h3>${localizedText(step.name)}</h3>
          <p>${localizedText(step.purpose)}</p>
        </article>
      `,
    )
    .join("");
  const responsive = uiIa.responsive_guidance || {};
  els.responsiveGuidance.innerHTML = [
    ["原则", responsive.principle],
    ["桌面端", responsive.desktop],
    ["移动端", responsive.mobile],
    ["事故处理", responsive.incident],
  ]
    .map(
      ([label, value]) => `
        <article class="guidance-card">
          <h3>${label}</h3>
          <p>${localizedText(value)}</p>
        </article>
      `,
    )
    .join("");
  const charts = uiIa.chart_guidance || {};
  const list = (items) => `<ul>${(items || []).map((item) => `<li>${localizedText(item)}</li>`).join("")}</ul>`;
  els.chartGuidance.innerHTML = [
    ["交易图", list(charts.trading_charts)],
    ["分析图", list(charts.analysis_charts)],
    ["工具映射", list(charts.tool_mapping)],
  ]
    .map(
      ([label, value]) => `
        <article class="guidance-card">
          <h3>${label}</h3>
          ${value}
        </article>
      `,
    )
    .join("");
  const technical = architecture.technical_implementation || {};
  els.technicalSummary.textContent = localizedText(technical.summary);
  els.technicalPrinciples.innerHTML = `
    <strong>技术原则</strong>
    <ul>${(technical.principles || []).map((item) => `<li>${localizedText(item)}</li>`).join("")}</ul>
  `;
  els.technicalStack.innerHTML = (technical.stack_layers || [])
    .map(
      (layer) => `
        <tr>
          <td>${localizedText(layer.layer)}</td>
          <td>${localizedText(layer.recommendation)}</td>
          <td>${localizedText(layer.preferred)}</td>
          <td>${localizedText(layer.note)}</td>
        </tr>
      `,
    )
    .join("");
  els.apiPriority.innerHTML = `
    <strong>第三方 API 优先级</strong>
    <ul>${(technical.api_priority || []).map((item) => `<li>${localizedText(item)}</li>`).join("")}</ul>
  `;
  els.implementationRoadmap.innerHTML = (technical.roadmap || [])
    .map(
      (stage) => `
        <tr>
          <td>${localizedText(stage.stage)}</td>
          <td>${localizedText(stage.goal)}</td>
          <td>${localizedText(stage.deliverables)}</td>
          <td>${localizedText(stage.team)}</td>
          <td>${localizedText(stage.timeline)}</td>
        </tr>
      `,
    )
    .join("");
  els.scaleComparison.innerHTML = (technical.scale_comparison || [])
    .map(
      (row) => `
        <tr>
          <td>${localizedText(row.dimension)}</td>
          <td>${localizedText(row.mvp)}</td>
          <td>${localizedText(row.standard)}</td>
          <td>${localizedText(row.enterprise)}</td>
        </tr>
      `,
    )
    .join("");
  els.recommendedStart.innerHTML = `
    <strong>推荐起步档</strong>
    <p>${localizedText(technical.recommended_start)}</p>
  `;
  els.riskBoundary.innerHTML = `
    <strong>风险边界</strong>
    <p>${localizedText(technical.risk_boundary)}</p>
  `;
  els.testingPrinciple.textContent = localizedText(technical.testing_principle);
  els.riskRegister.innerHTML = (technical.risk_register || [])
    .map(
      (item) => `
        <tr>
          <td>${localizedText(item.risk)}</td>
          <td>${localizedText(item.typical_manifestation)}</td>
          <td>${localizedText(item.mitigation)}</td>
        </tr>
      `,
    )
    .join("");
  els.acceptanceMatrix.innerHTML = (technical.acceptance_matrix || [])
    .map(
      (item) => `
        <tr>
          <td>${localizedText(item.category)}</td>
          <td>${localizedText(item.key_cases)}</td>
          <td>${localizedText(item.minimum_acceptance)}</td>
        </tr>
      `,
    )
    .join("");
  els.goLiveGates.innerHTML = `
    <strong>小额真仓硬门槛</strong>
    <ul>${(technical.go_live_gates || []).map((item) => `<li>${localizedText(item)}</li>`).join("")}</ul>
  `;
}

function renderIntent(intent) {
  if (!intent) {
    els.tradeIntent.className = "intent-box empty";
    els.tradeIntent.textContent = "等待交易代理输出";
    return;
  }
  els.tradeIntent.className = "intent-box";
  const rows = [
    ["方向", sideText(intent.side)],
    ["信心", intent.confidence],
    ["入场", intent.entry_price],
    ["止损", intent.stop_loss],
    ["止盈", intent.take_profit],
    ["杠杆", `${intent.leverage}x`],
    ["仓位", `${(intent.position_pct * 100).toFixed(1)}%`],
    ["周期", timeHorizonText(intent.time_horizon)],
    ["决策源", sourceText(intent.provider)],
    ["模型", modelText(intent.model)],
  ];
  els.tradeIntent.innerHTML = `
    <div class="intent-grid">
      ${rows
        .map(
          ([label, value]) =>
            `<div class="intent-item"><span>${label}</span><strong>${fmt(value)}</strong></div>`,
        )
        .join("")}
    </div>
    <p class="event-body" style="margin-top: 14px">${localizedText(intent.rationale)}</p>
  `;
}

function renderRisk(risk) {
  if (!risk) {
    els.riskChecks.className = "checks empty";
    els.riskChecks.textContent = "等待风控引擎输出";
    return;
  }
  els.riskChecks.className = "checks";
  els.riskChecks.innerHTML = risk.checks
    .map(
      (check) => `
        <div class="check">
          <strong>${riskCheckName(check.name)}<span class="badge ${check.status}">${statusText(check.status)}</span></strong>
          <span class="event-body">${localizedText(check.detail)}</span>
        </div>
      `,
    )
    .join("");
}

function renderOrders(orders) {
  if (!orders.length) {
    els.orders.innerHTML = `<tr><td colspan="15">暂无订单</td></tr>`;
    return;
  }
  els.orders.innerHTML = orders
    .map((order) => {
      const canCancel = [
        "testnet_submitted",
        "testnet_protection_submitted",
        "live_submitted",
        "live_protection_submitted",
        "pending_reconcile",
      ].includes(order.status);
      return `
        <tr>
          <td>${order.id}</td>
          <td>${order.client_order_id || order.id}</td>
          <td>${order.run_id}</td>
          <td>${order.symbol}</td>
          <td>${sideText(order.side)}</td>
          <td>${fmt(order.quantity)}</td>
          <td>${fmt(order.leverage)}x</td>
          <td>${fmt(order.entry_price)}</td>
          <td>${fmt(order.stop_loss)}</td>
          <td>${fmt(order.take_profit)}</td>
          <td>${orderStatusText(order.status)}</td>
          <td>${venueStatusText(order.venue_status)}</td>
          <td>${reconcileText(order.reconcile_status || "unchecked")}</td>
          <td>${localizedText(order.reconcile_note)}</td>
          <td>${
            canCancel
              ? `<button class="secondary compact cancel-order" data-order-id="${order.id}">撤单</button>`
              : "-"
          }</td>
        </tr>
      `;
    })
    .join("");
}

function renderOms(oms) {
  const data = oms || {};
  els.omsTotal.textContent = fmt(data.total_orders);
  els.omsReconciled.textContent = fmt(data.reconciled_orders);
  els.omsNeeds.textContent = fmt(data.needs_reconcile);
  els.omsUnknown.textContent = fmt(data.unknown_venue_status);
  const needs = Number(data.needs_reconcile || 0);
  const unknown = Number(data.unknown_venue_status || 0);
  els.omsNeeds.style.color = needs > 0 ? "#a76505" : "#10845b";
  els.omsUnknown.style.color = unknown > 0 ? "#cf2e2e" : "#10845b";
  if (els.overviewOmsStatus) {
    els.overviewOmsStatus.textContent = needs || unknown ? "需要对账" : "正常";
    els.overviewOmsDetail.textContent = `订单 ${fmt(data.total_orders)} / 已对账 ${fmt(data.reconciled_orders)} / 未知 ${fmt(unknown)}`;
  }
}

function renderPositions(positions, account) {
  const rows = positions || [];
  const summary = account || {};
  els.positionSummary.textContent = `${summary.open_position_count || 0} 笔持仓 / 保证金占用 ${fmt(summary.margin_usage_pct || 0)}%`;
  if (!rows.length) {
    els.positions.innerHTML = `<tr><td colspan="13">暂无持仓</td></tr>`;
    return;
  }
  els.positions.innerHTML = rows
    .map((position) => {
      const pnl = Number(
        position.status === "closed"
          ? position.realized_pnl_usdt || position.realized_pnl || 0
          : position.unrealized_pnl_usdt || 0,
      );
      const pnlColor = pnl > 0 ? "#10845b" : pnl < 0 ? "#cf2e2e" : "inherit";
      const action =
        position.status === "open"
          ? `<button class="secondary compact close-position" data-position-id="${position.id}">平仓</button>`
          : "-";
      return `
        <tr>
          <td>${position.id}</td>
          <td>${position.run_id}</td>
          <td>${position.symbol}</td>
          <td>${sideText(position.side)}</td>
          <td>${fmt(position.quantity)}</td>
          <td>${fmt(position.leverage)}x</td>
          <td>${fmt(position.entry_price)}</td>
          <td>${fmt(position.mark_price)}</td>
          <td>${fmt(position.used_margin_usdt)}</td>
          <td style="color: ${pnlColor}; font-weight: 800">${fmt(pnl)}</td>
          <td>${fmt(position.roe_pct)}%</td>
          <td>${orderStatusText(position.status)}</td>
          <td>${action}</td>
        </tr>
      `;
    })
    .join("");
}

function renderBacktest(backtests, trades) {
  const latest = (backtests || [])[0];
  if (!latest) {
    els.backtestId.textContent = "暂无回测";
    els.backtestReturn.textContent = "-";
    els.backtestWinRate.textContent = "-";
    els.backtestDrawdown.textContent = "-";
    els.backtestTradesCount.textContent = "-";
    els.backtestTrades.innerHTML = `<tr><td colspan="10">暂无回测交易</td></tr>`;
    return;
  }
  const metrics = latest.metrics || {};
  els.backtestId.textContent = `${latest.id} / ${latest.symbol} / ${latest.interval}`;
  els.backtestReturn.textContent = `${fmt(metrics.total_return_pct)}%`;
  els.backtestWinRate.textContent = `${fmt(metrics.win_rate_pct)}%`;
  els.backtestDrawdown.textContent = `${fmt(metrics.max_drawdown_pct)}%`;
  els.backtestTradesCount.textContent = fmt(metrics.trade_count);
  const ret = Number(metrics.total_return_pct || 0);
  els.backtestReturn.style.color = ret > 0 ? "#10845b" : ret < 0 ? "#cf2e2e" : "";

  const rows = trades || [];
  if (!rows.length) {
    els.backtestTrades.innerHTML = `<tr><td colspan="10">暂无回测交易</td></tr>`;
    return;
  }
  els.backtestTrades.innerHTML = rows
    .map((trade) => {
      const pnl = Number(trade.pnl_usdt || 0);
      const pnlColor = pnl > 0 ? "#10845b" : pnl < 0 ? "#cf2e2e" : "inherit";
      return `
        <tr>
          <td>${shortTime(trade.opened_at)}</td>
          <td>${shortTime(trade.closed_at)}</td>
          <td>${trade.symbol}</td>
          <td>${sideText(trade.side)}</td>
          <td>${fmt(trade.entry_price)}</td>
          <td>${fmt(trade.exit_price)}</td>
          <td>${fmt(trade.quantity)}</td>
          <td style="color: ${pnlColor}; font-weight: 800">${fmt(trade.pnl_usdt)}</td>
          <td>${fmt(trade.return_pct)}%</td>
          <td>${reasonText(trade.reason)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderComparison(comparison) {
  if (!comparison) {
    els.compareId.textContent = "暂无参数比较";
    els.compareResults.innerHTML = `<tr><td colspan="10">暂无参数结果</td></tr>`;
    return;
  }
  els.compareId.textContent = `${comparison.id} / ${comparison.symbol} / ${comparison.interval} / 已测试 ${comparison.tested_count} 组`;
  const rows = comparison.results || [];
  if (!rows.length) {
    els.compareResults.innerHTML = `<tr><td colspan="10">暂无参数结果</td></tr>`;
    return;
  }
  els.compareResults.innerHTML = rows
    .map((item, index) => {
      const metrics = item.metrics || {};
      const params = item.params || {};
      const ret = Number(metrics.total_return_pct || 0);
      const retColor = ret > 0 ? "#10845b" : ret < 0 ? "#cf2e2e" : "inherit";
      return `
        <tr>
          <td>${index + 1}</td>
          <td>${params.fast_ma}/${params.slow_ma}</td>
          <td>${fmt(params.stop_pct)}% / ${fmt(params.take_pct)}%</td>
          <td>${fmt(params.threshold_pct)}%</td>
          <td>${fmt(item.rank_score)}</td>
          <td style="color: ${retColor}; font-weight: 800">${fmt(metrics.total_return_pct)}%</td>
          <td>${fmt(metrics.max_drawdown_pct)}%</td>
          <td>${fmt(metrics.win_rate_pct)}%</td>
          <td>${fmt(metrics.trade_count)}</td>
          <td>${fmt(metrics.profit_factor)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderWalkforward(walkforward) {
  if (!walkforward) {
    els.walkforwardId.textContent = "暂无滚动验证";
    els.walkforwardReturn.textContent = "-";
    els.walkforwardPositive.textContent = "-";
    els.walkforwardDrawdown.textContent = "-";
    els.walkforwardTrades.textContent = "-";
    els.walkforwardFolds.innerHTML = `<tr><td colspan="8">暂无滚动验证折次</td></tr>`;
    return;
  }
  els.walkforwardId.textContent = `${walkforward.id} / ${walkforward.symbol} / ${walkforward.interval} / ${walkforward.fold_count} 折`;
  els.walkforwardReturn.textContent = `${fmt(walkforward.total_return_pct)}%`;
  els.walkforwardPositive.textContent = `${fmt(walkforward.positive_fold_rate_pct)}%`;
  els.walkforwardDrawdown.textContent = `${fmt(walkforward.max_fold_drawdown_pct)}%`;
  els.walkforwardTrades.textContent = fmt(walkforward.test_trade_count);
  const ret = Number(walkforward.total_return_pct || 0);
  els.walkforwardReturn.style.color = ret > 0 ? "#10845b" : ret < 0 ? "#cf2e2e" : "";

  const folds = walkforward.folds || [];
  if (!folds.length) {
    els.walkforwardFolds.innerHTML = `<tr><td colspan="8">暂无滚动验证折次</td></tr>`;
    return;
  }
  els.walkforwardFolds.innerHTML = folds
    .map((fold) => {
      const params = fold.selected_params || {};
      const train = fold.train_metrics || {};
      const test = fold.test_metrics || {};
      const testRet = Number(test.total_return_pct || 0);
      const retColor = testRet > 0 ? "#10845b" : testRet < 0 ? "#cf2e2e" : "inherit";
      return `
        <tr>
          <td>${fold.fold}</td>
          <td>${shortTime(fold.test_start)} - ${shortTime(fold.test_end)}</td>
          <td>${params.fast_ma}/${params.slow_ma} ${fmt(params.stop_pct)}%/${fmt(params.take_pct)}%</td>
          <td>${fmt(train.total_return_pct)}%</td>
          <td style="color: ${retColor}; font-weight: 800">${fmt(test.total_return_pct)}%</td>
          <td>${fmt(test.max_drawdown_pct)}%</td>
          <td>${fmt(test.win_rate_pct)}%</td>
          <td>${fmt(test.trade_count)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderEventAudit(events) {
  if (!events.length) return "暂无审计事件";
  return events
    .map((event, index) => {
      const parts = [
        `${index + 1}. ${shortTime(event.ts)} [${kindText(event.kind)}] ${actorText(event.actor)}`,
        `标题：${event.title}`,
        `说明：${localizedText(event.body)}`,
      ];
      return parts.join("\n");
    })
    .join("\n\n");
}

async function ensureArchitectureLoaded() {
  if (architectureLoaded || architectureLoading) return;
  architectureLoading = true;
  if (els.architectureStatus) {
    els.architectureStatus.textContent = "加载中";
  }
  try {
    const response = await fetch(architectureUrl, { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || response.statusText);
    renderArchitecture(data.architecture);
    architectureLoaded = true;
  } catch (error) {
    if (els.architectureStatus) {
      els.architectureStatus.textContent = "加载失败";
    }
    if (els.architectureSummary) {
      els.architectureSummary.textContent = String(error);
    }
  } finally {
    architectureLoading = false;
  }
}

async function ensureReadinessLoaded() {
  if (readinessLoading || Date.now() - readinessLoadedAt < 60000) return;
  readinessLoading = true;
  try {
    const response = await fetch(readinessUrl, { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || response.statusText);
    renderReadiness(data);
    readinessLoadedAt = Date.now();
  } catch (error) {
    if (els.readinessOverall) {
      els.readinessOverall.textContent = "加载失败";
    }
  } finally {
    readinessLoading = false;
  }
}

async function ensureGoLiveGateLoaded() {
  if (goLiveGateLoading || Date.now() - goLiveGateLoadedAt < 60000) return;
  goLiveGateLoading = true;
  try {
    const response = await fetch(goLiveGateUrl, { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || response.statusText);
    lastFullGoLiveGate = data.go_live_gate || null;
    renderGoLiveGate(displayGoLiveGate(data.go_live_gate));
    goLiveGateLoadedAt = Date.now();
  } catch (error) {
    if (els.liveGateStatus) {
      els.liveGateStatus.textContent = "加载失败";
    }
  } finally {
    goLiveGateLoading = false;
  }
}

async function refresh() {
  try {
    const response = await fetch(stateUrl, { cache: "no-store" });
    const data = await response.json();
    const events = data.events || [];
    renderConfig(data);
    renderReadiness(data.readiness);
    if (data.readiness?.summary_only) {
      ensureReadinessLoaded();
    }
    renderLocalReadiness(data.local_readiness);
    renderAuditChain(data.audit_chain);
    renderAlerts(data.alerts);
    renderExchangeRecovery(data.exchange_recovery);
    renderAiOperator(data.ai_operator || data.config?.ai_operator);
    renderScheduler(data.scheduler);
    renderTestnetDrill(data.testnet_drill);
    renderServerLiveReadiness(data.server_live_readiness);
    renderLiveEnvProfile(data.live_env_profile);
    renderGoLiveGate(displayGoLiveGate(data.go_live_gate));
    if (data.go_live_gate?.summary_only) {
      ensureGoLiveGateLoaded();
    }
    renderDesk(data);
    renderRiskCenter(data.risk, data.account);
    renderMetrics(data);
    renderAccount(data.account);
    renderTimeline(events);
    renderMarket(latestPayloadByActor(events, "Market Data"));
    renderResearch(data.research);
    if (data.architecture) {
      renderArchitecture(data.architecture);
      architectureLoaded = true;
    } else {
      ensureArchitectureLoaded();
    }
    renderIntent(latestPayloadByActor(events, "Trader Agent"));
    renderRisk(latestPayloadByActor(events, "Risk Engine"));
    renderPositions(data.positions || [], data.account || {});
    renderBacktest(data.backtests || [], data.backtest_trades || []);
    renderComparison(data.backtest_comparison);
    renderWalkforward(data.walkforward);
    renderOms(data.oms);
    renderOrders(data.orders || []);
    els.rawLog.textContent = renderEventAudit(events);
  } catch (error) {
    els.systemStatus.textContent = "离线";
    els.rawLog.textContent = String(error);
  }
}

async function postJson(url, body = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

async function runPanicStop(button) {
  const confirmation = window.prompt("事故停机会开启紧急停止、解除实盘武装、关闭调度/演练，并尝试撤销未终态 Binance 订单。输入 PANIC_STOP 确认。");
  if (confirmation === null) return;
  if (confirmation.trim() !== "PANIC_STOP") {
    alert("确认短语不正确，事故停机未执行。");
    return;
  }
  const reason = window.prompt("记录事故停机原因", "manual panic stop from dashboard") || "manual panic stop from dashboard";
  button.disabled = true;
  try {
    const result = await postJson("/api/panic-stop", {
      confirmation: "PANIC_STOP",
      reason,
      cancel_orders: true,
      cancel_exchange_open_orders: true,
      flatten_positions: false,
      reconcile: true,
    });
    const panic = result.panic_stop || {};
    const failed = (panic.cancel_failed || []).length;
    alert(`事故停机已执行。撤单失败 ${failed} 个；请检查 OMS 对账和告警中心。`);
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    button.disabled = false;
  }
}

async function sendAiOperatorMessage() {
  const message = els.aiOperatorInput.value.trim();
  if (!message) return;
  els.sendAiOperator.disabled = true;
  try {
    const result = await postJson("/api/ai-operator/chat", { message });
    els.aiOperatorInput.value = "";
    renderAiOperator(result);
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.sendAiOperator.disabled = false;
  }
}

els.sendAiOperator.addEventListener("click", sendAiOperatorMessage);

els.aiOperatorInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    sendAiOperatorMessage();
  }
});

document.querySelectorAll(".ai-command-chip").forEach((button) => {
  button.addEventListener("click", () => {
    els.aiOperatorInput.value = button.dataset.aiCommand || "";
    els.aiOperatorInput.focus();
  });
});

els.startRun.addEventListener("click", async () => {
  els.startRun.disabled = true;
  try {
    await postJson("/api/runs", {
      symbol: els.symbol.value,
      mode: els.mode.value,
    });
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    setTimeout(() => {
      els.startRun.disabled = false;
    }, 1600);
  }
});

els.stop.addEventListener("click", async () => {
  await postJson("/api/emergency-stop");
  await refresh();
});

els.panicStop.addEventListener("click", async () => {
  await runPanicStop(els.panicStop);
});

els.resetStop.addEventListener("click", async () => {
  await postJson("/api/reset-emergency-stop");
  await refresh();
});

[
  els.riskMaxLeverage,
  els.riskMaxPosition,
  els.riskMaxNotional,
  els.riskDailyLoss,
  els.riskMaxOpen,
  els.riskLossStreak,
  els.riskSymbols,
].forEach((control) => {
  control.addEventListener("change", () => {
    riskDirty = true;
  });
});

els.saveRisk.addEventListener("click", async () => {
  els.saveRisk.disabled = true;
  try {
    await postJson("/api/risk", {
      max_leverage: Number(els.riskMaxLeverage.value || 3),
      max_position_pct: Number(els.riskMaxPosition.value || 5) / 100,
      max_order_notional_usdt: Number(els.riskMaxNotional.value || 1000),
      max_daily_loss_pct: Number(els.riskDailyLoss.value || 3) / 100,
      max_open_positions: Number(els.riskMaxOpen.value || 8),
      max_consecutive_losses: Number(els.riskLossStreak.value || 3),
      allowed_symbols: els.riskSymbols.value,
    });
    riskDirty = false;
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.saveRisk.disabled = false;
  }
});

els.riskStop.addEventListener("click", async () => {
  await postJson("/api/emergency-stop");
  await refresh();
});

els.riskPanicStop.addEventListener("click", async () => {
  await runPanicStop(els.riskPanicStop);
});

els.riskReset.addEventListener("click", async () => {
  await postJson("/api/reset-emergency-stop");
  await refresh();
});

els.reconcileOrders.addEventListener("click", async () => {
  els.reconcileOrders.disabled = true;
  try {
    await postJson("/api/oms/reconcile");
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.reconcileOrders.disabled = false;
  }
});

els.runAlertCheck.addEventListener("click", async () => {
  els.runAlertCheck.disabled = true;
  try {
    await postJson("/api/alerts/check");
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.runAlertCheck.disabled = false;
  }
});

els.testAlertDelivery.addEventListener("click", async () => {
  els.testAlertDelivery.disabled = true;
  try {
    await postJson("/api/alerts/test-delivery");
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.testAlertDelivery.disabled = false;
  }
});

els.alertList.addEventListener("click", async (event) => {
  const ackButton = event.target.closest(".ack-alert");
  const resolveButton = event.target.closest(".resolve-alert");
  const button = ackButton || resolveButton;
  if (!button) return;
  button.disabled = true;
  const action = ackButton ? "ack" : "resolve";
  try {
    await postJson(`/api/alerts/${button.dataset.alertId}/${action}`);
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    button.disabled = false;
  }
});

els.runExchangeRecovery.addEventListener("click", async () => {
  els.runExchangeRecovery.disabled = true;
  try {
    await postJson("/api/exchange/recover");
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.runExchangeRecovery.disabled = false;
  }
});

els.syncExchangeAccount.addEventListener("click", async () => {
  els.syncExchangeAccount.disabled = true;
  try {
    await postJson("/api/exchange/account-sync", {
      mode: els.exchangeSyncMode.value,
    });
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.syncExchangeAccount.disabled = false;
  }
});

els.planFlattenPositions.addEventListener("click", async () => {
  els.planFlattenPositions.disabled = true;
  try {
    const result = await postJson("/api/exchange/flatten-positions", {
      mode: els.exchangeSyncMode.value,
      dry_run: true,
    });
    const flatten = result.flatten || {};
    alert(`平仓预案已生成：持仓 ${flatten.position_count || 0} 个，可平仓 ${flatten.planned_count || 0} 个，失败 ${flatten.failed_count || 0} 个。`);
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.planFlattenPositions.disabled = false;
  }
});

els.startUserStream.addEventListener("click", async () => {
  els.startUserStream.disabled = true;
  try {
    await postJson("/api/user-stream/start", {
      mode: els.exchangeSyncMode.value,
    });
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.startUserStream.disabled = false;
  }
});

els.keepaliveUserStream.addEventListener("click", async () => {
  els.keepaliveUserStream.disabled = true;
  try {
    await postJson("/api/user-stream/keepalive");
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.keepaliveUserStream.disabled = false;
  }
});

els.closeUserStream.addEventListener("click", async () => {
  els.closeUserStream.disabled = true;
  try {
    await postJson("/api/user-stream/close");
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.closeUserStream.disabled = false;
  }
});

els.orders.addEventListener("click", async (event) => {
  const button = event.target.closest(".cancel-order");
  if (!button) return;
  button.disabled = true;
  try {
    await postJson(`/api/orders/${button.dataset.orderId}/cancel`);
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    button.disabled = false;
  }
});

[
  els.schedulerEnabled,
  els.schedulerSymbol,
  els.schedulerInterval,
].forEach((control) => {
  control.addEventListener("change", () => {
    schedulerDirty = true;
  });
});

els.saveScheduler.addEventListener("click", async () => {
  els.saveScheduler.disabled = true;
  try {
    await postJson("/api/scheduler", {
      enabled: els.schedulerEnabled.checked,
      symbol: els.schedulerSymbol.value,
      mode: "paper",
      interval_minutes: Number(els.schedulerInterval.value || 15),
    });
    schedulerDirty = false;
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.saveScheduler.disabled = false;
  }
});

els.runSchedulerNow.addEventListener("click", async () => {
  els.runSchedulerNow.disabled = true;
  try {
    await postJson("/api/scheduler/run-now");
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    setTimeout(() => {
      els.runSchedulerNow.disabled = false;
    }, 1600);
  }
});

els.positions.addEventListener("click", async (event) => {
  const button = event.target.closest(".close-position");
  if (!button) return;
  button.disabled = true;
  try {
    await postJson(`/api/positions/${button.dataset.positionId}/close`, {
      reason: "manual_close_from_dashboard",
    });
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    button.disabled = false;
  }
});

[
  els.testnetDrillEnabled,
  els.testnetDrillSymbol,
  els.testnetDrillMode,
  els.testnetDrillInterval,
  els.testnetDrillTarget,
].forEach((control) => {
  control.addEventListener("change", () => {
    testnetDrillDirty = true;
  });
});

els.saveTestnetDrill.addEventListener("click", async () => {
  els.saveTestnetDrill.disabled = true;
  try {
    await postJson("/api/testnet-drill", {
      enabled: els.testnetDrillEnabled.checked,
      symbol: els.testnetDrillSymbol.value,
      mode: els.testnetDrillMode.value,
      interval_minutes: Number(els.testnetDrillInterval.value || 30),
      target_cycles: Number(els.testnetDrillTarget.value || 24),
    });
    testnetDrillDirty = false;
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.saveTestnetDrill.disabled = false;
  }
});

els.runTestnetDrillNow.addEventListener("click", async () => {
  els.runTestnetDrillNow.disabled = true;
  try {
    await postJson("/api/testnet-drill/run-now");
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    setTimeout(() => {
      els.runTestnetDrillNow.disabled = false;
    }, 1600);
  }
});

els.runServerLiveReadiness.addEventListener("click", async () => {
  els.runServerLiveReadiness.disabled = true;
  let started = false;
  try {
    const intervalSeconds = Math.max(1, Number(els.testnetDrillInterval.value || 1)) * 60;
    const result = await postJson("/api/server-live-readiness/run", {
      dry_run: false,
      run_testnet_drill: Boolean(els.serverLiveReadinessTestnet.checked),
      target_cycles: Number(els.testnetDrillTarget.value || 24),
      interval_seconds: intervalSeconds,
      timeout_seconds: 3600,
    });
    started = Boolean(result.server_live_readiness?.running);
    renderServerLiveReadiness(result.server_live_readiness);
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    if (!started) {
      els.runServerLiveReadiness.disabled = false;
    }
  }
});

els.cancelServerLiveReadiness.addEventListener("click", async () => {
  els.cancelServerLiveReadiness.disabled = true;
  try {
    const result = await postJson("/api/server-live-readiness/cancel", {
      reason: "manual_dashboard_cancel",
    });
    renderServerLiveReadiness(result.server_live_readiness);
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.cancelServerLiveReadiness.disabled = false;
  }
});

els.checkLiveEnvProfile.addEventListener("click", async () => {
  els.checkLiveEnvProfile.disabled = true;
  try {
    const response = await fetch("/api/live-env-profile?target=live_guarded", { cache: "no-store" });
    if (!response.ok) throw new Error(`环境审计失败：${response.status}`);
    const result = await response.json();
    renderLiveEnvProfile(result.live_env_profile);
  } catch (error) {
    alert(error.message);
  } finally {
    els.checkLiveEnvProfile.disabled = false;
  }
});

els.checkLiveGate.addEventListener("click", async () => {
  els.checkLiveGate.disabled = true;
  try {
    const result = await postJson("/api/go-live-gate/check");
    lastFullGoLiveGate = result.go_live_gate || null;
    renderGoLiveGate(displayGoLiveGate(result.go_live_gate));
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.checkLiveGate.disabled = false;
  }
});

els.exportGoLiveReport.addEventListener("click", async () => {
  els.exportGoLiveReport.disabled = true;
  try {
    const response = await fetch("/api/go-live-report", { cache: "no-store" });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || "导出准入报告失败");
    }
    const report = result.go_live_report || result;
    const stamp = new Date().toISOString().replaceAll(":", "").replaceAll(".", "");
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `go-live-report-${stamp}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  } catch (error) {
    alert(error.message);
  } finally {
    els.exportGoLiveReport.disabled = false;
  }
});

els.exportLiveLaunchPlan.addEventListener("click", async () => {
  els.exportLiveLaunchPlan.disabled = true;
  try {
    const response = await fetch("/api/live-launch-plan", { cache: "no-store" });
    if (!response.ok) throw new Error(`导出上线计划失败：${response.status}`);
    const payload = await response.json();
    const plan = payload.live_launch_plan || payload;
    const stamp = new Date().toISOString().replaceAll(":", "").replaceAll(".", "");
    const blob = new Blob([plan.markdown || JSON.stringify(plan, null, 2)], {
      type: plan.markdown ? "text/markdown" : "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `live-launch-plan-${stamp}.${plan.markdown ? "md" : "json"}`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    alert(error.message);
  } finally {
    els.exportLiveLaunchPlan.disabled = false;
  }
});

els.exportLiveOpsHandoff.addEventListener("click", async () => {
  els.exportLiveOpsHandoff.disabled = true;
  try {
    const response = await fetch("/api/live-ops-handoff?symbol=BTCUSDT", { cache: "no-store" });
    if (!response.ok) throw new Error(`导出实盘交接单失败：${response.status}`);
    const payload = await response.json();
    const handoff = payload.live_ops_handoff || payload;
    const stamp = new Date().toISOString().replaceAll(":", "").replaceAll(".", "");
    const blob = new Blob([handoff.markdown || JSON.stringify(handoff, null, 2)], {
      type: handoff.markdown ? "text/markdown" : "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `live-ops-handoff-${stamp}.${handoff.markdown ? "md" : "json"}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  } catch (error) {
    alert(error.message);
  } finally {
    els.exportLiveOpsHandoff.disabled = false;
  }
});

els.exportLiveLaunchKit.addEventListener("click", async () => {
  els.exportLiveLaunchKit.disabled = true;
  try {
    const response = await fetch("/api/live-launch-kit", { cache: "no-store" });
    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(result.error || "导出上线套件失败");
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const matched = disposition.match(/filename="([^"]+)"/);
    const filename =
      matched?.[1] ||
      `crypto-contract-ai-trader-live-launch-kit-${new Date().toISOString().replaceAll(":", "").replaceAll(".", "")}.zip`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  } catch (error) {
    alert(error.message);
  } finally {
    els.exportLiveLaunchKit.disabled = false;
  }
});

els.exportLiveEnvPack.addEventListener("click", async () => {
  els.exportLiveEnvPack.disabled = true;
  try {
    const response = await fetch("/api/live-env-pack", { cache: "no-store" });
    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(result.error || "导出环境模板失败");
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const matched = disposition.match(/filename="([^"]+)"/);
    const filename =
      matched?.[1] ||
      `crypto-contract-ai-trader-live-env-pack-${new Date().toISOString().replaceAll(":", "").replaceAll(".", "")}.zip`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  } catch (error) {
    alert(error.message);
  } finally {
    els.exportLiveEnvPack.disabled = false;
  }
});

els.exportServerBundle.addEventListener("click", async () => {
  els.exportServerBundle.disabled = true;
  try {
    const response = await fetch("/api/server-bundle", { cache: "no-store" });
    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(result.error || "导出部署包失败");
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const matched = disposition.match(/filename="([^"]+)"/);
    const filename =
      matched?.[1] ||
      `crypto-contract-ai-trader-server-bundle-${new Date().toISOString().replaceAll(":", "").replaceAll(".", "")}.zip`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  } catch (error) {
    alert(error.message);
  } finally {
    els.exportServerBundle.disabled = false;
  }
});

els.exportServerGoLiveAudit.addEventListener("click", async () => {
  els.exportServerGoLiveAudit.disabled = true;
  try {
    const response = await fetch("/api/server-go-live-audit", { cache: "no-store" });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || "导出服务器审计包失败");
    }
    const audit = result.server_go_live_audit || result;
    const stamp = new Date().toISOString().replaceAll(":", "").replaceAll(".", "");
    const blob = new Blob([JSON.stringify(audit, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `server-go-live-audit-${stamp}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  } catch (error) {
    alert(error.message);
  } finally {
    els.exportServerGoLiveAudit.disabled = false;
  }
});

els.checkFinalLiveReady.addEventListener("click", async () => {
  els.checkFinalLiveReady.disabled = true;
  try {
    const response = await fetch("/api/final-live-ready", { cache: "no-store" });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || "最终实盘检查失败");
    }
    renderFinalLiveReady(result.final_live_ready || result);
  } catch (error) {
    alert(error.message);
  } finally {
    els.checkFinalLiveReady.disabled = false;
  }
});

els.checkLivePilot.addEventListener("click", async () => {
  els.checkLivePilot.disabled = true;
  try {
    const symbol = encodeURIComponent(els.symbol.value || "BTCUSDT");
    const response = await fetch(`/api/live-pilot?symbol=${symbol}`, { cache: "no-store" });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || "实盘首单执行器检查失败");
    }
    renderLivePilot(result.live_pilot || result);
  } catch (error) {
    alert(error.message);
  } finally {
    els.checkLivePilot.disabled = false;
  }
});

els.checkLivePostflight.addEventListener("click", async () => {
  els.checkLivePostflight.disabled = true;
  try {
    const symbol = encodeURIComponent(els.symbol.value || "BTCUSDT");
    const response = await fetch(`/api/live-pilot-postflight?symbol=${symbol}`, { cache: "no-store" });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || "实盘首单复盘检查失败");
    }
    renderLivePostflight(result.live_pilot_postflight || result);
  } catch (error) {
    alert(error.message);
  } finally {
    els.checkLivePostflight.disabled = false;
  }
});

els.resolveLiveBlockers.addEventListener("click", async () => {
  els.resolveLiveBlockers.disabled = true;
  try {
    const symbol = encodeURIComponent(els.symbol.value || "BTCUSDT");
    const response = await fetch(`/api/live-blocker-resolution?symbol=${symbol}`, { cache: "no-store" });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || "实盘阻塞解除路线生成失败");
    }
    renderLiveBlockerResolution(result.live_blocker_resolution || result);
  } catch (error) {
    alert(error.message);
  } finally {
    els.resolveLiveBlockers.disabled = false;
  }
});

els.runLivePilot.addEventListener("click", async () => {
  els.runLivePilot.disabled = true;
  try {
    const result = await postJson("/api/live-pilot/run", {
      symbol: els.symbol.value || "BTCUSDT",
      confirmation: els.livePilotConfirmation.value,
    });
    els.livePilotConfirmation.value = "";
    renderLivePilot(result.live_pilot);
    await refresh();
    if (els.checkLivePostflight) {
      const symbol = encodeURIComponent(els.symbol.value || "BTCUSDT");
      const response = await fetch(`/api/live-pilot-postflight?symbol=${symbol}`, { cache: "no-store" });
      if (response.ok) {
        const postflight = await response.json();
        renderLivePostflight(postflight.live_pilot_postflight || postflight);
      }
    }
  } catch (error) {
    alert(error.message);
  } finally {
    els.runLivePilot.disabled = false;
  }
});

els.armLiveGate.addEventListener("click", async () => {
  els.armLiveGate.disabled = true;
  try {
    const result = await postJson("/api/live-arming/arm", {
      confirmation: els.liveArmConfirmation.value,
      ttl_minutes: Number(els.liveArmTtl.value || 10),
      reason: els.liveArmReason.value || "manual live arming",
      actor: "dashboard",
    });
    els.liveArmConfirmation.value = "";
    lastFullGoLiveGate = result.go_live_gate || lastFullGoLiveGate;
    renderGoLiveGate(displayGoLiveGate(result.go_live_gate));
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.armLiveGate.disabled = false;
  }
});

els.disarmLiveGate.addEventListener("click", async () => {
  els.disarmLiveGate.disabled = true;
  try {
    const result = await postJson("/api/live-arming/disarm", {
      reason: "manual dashboard disarm",
    });
    lastFullGoLiveGate = result.go_live_gate || lastFullGoLiveGate;
    renderGoLiveGate(displayGoLiveGate(result.go_live_gate));
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.disarmLiveGate.disabled = false;
  }
});

[
  els.attestWithdrawalDisabled,
  els.attestIpWhitelisted,
  els.attestJurisdictionOk,
  els.attestOffserverBackupCopied,
  els.attestPilotCapitalLimitOk,
  els.liveAttestationActor,
  els.liveAttestationNote,
  els.liveAttestationConfirmation,
].forEach((control) => {
  control.addEventListener("change", () => {
    liveAttestationDirty = true;
  });
  control.addEventListener("input", () => {
    liveAttestationDirty = true;
  });
});

els.saveLiveAttestation.addEventListener("click", async () => {
  els.saveLiveAttestation.disabled = true;
  try {
    const result = await postJson("/api/live-attestation", {
      confirmation: els.liveAttestationConfirmation.value,
      actor: els.liveAttestationActor.value || "dashboard",
      note: els.liveAttestationNote.value || "",
      accepted: {
        withdrawal_disabled: els.attestWithdrawalDisabled.checked,
        ip_whitelisted: els.attestIpWhitelisted.checked,
        jurisdiction_ok: els.attestJurisdictionOk.checked,
        offserver_backup_copied: els.attestOffserverBackupCopied.checked,
        pilot_capital_limit_ok: els.attestPilotCapitalLimitOk.checked,
      },
    });
    els.liveAttestationConfirmation.value = "";
    liveAttestationDirty = false;
    renderLiveAttestation(result.live_attestation);
    lastFullGoLiveGate = result.go_live_gate || lastFullGoLiveGate;
    renderGoLiveGate(displayGoLiveGate(result.go_live_gate));
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.saveLiveAttestation.disabled = false;
  }
});

els.clearLiveAttestation.addEventListener("click", async () => {
  els.clearLiveAttestation.disabled = true;
  try {
    const result = await postJson("/api/live-attestation/clear", {
      reason: "manual dashboard clear",
    });
    liveAttestationDirty = false;
    els.liveAttestationConfirmation.value = "";
    els.liveAttestationNote.value = "";
    renderLiveAttestation(result.live_attestation);
    lastFullGoLiveGate = result.go_live_gate || lastFullGoLiveGate;
    renderGoLiveGate(displayGoLiveGate(result.go_live_gate));
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.clearLiveAttestation.disabled = false;
  }
});

els.runBacktest.addEventListener("click", async () => {
  els.runBacktest.disabled = true;
  try {
    await postJson("/api/backtests", {
      symbol: els.backtestSymbol.value,
      interval: els.backtestInterval.value,
      bars: Number(els.backtestBars.value),
    });
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.runBacktest.disabled = false;
  }
});

els.runCompare.addEventListener("click", async () => {
  els.runCompare.disabled = true;
  try {
    await postJson("/api/backtests/compare", {
      symbol: els.backtestSymbol.value,
      interval: els.backtestInterval.value,
      bars: Number(els.backtestBars.value),
    });
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.runCompare.disabled = false;
  }
});

els.runWalkforward.addEventListener("click", async () => {
  els.runWalkforward.disabled = true;
  try {
    await postJson("/api/backtests/walkforward", {
      symbol: els.backtestSymbol.value,
      interval: els.backtestInterval.value,
      bars: Number(els.backtestBars.value),
    });
    await refresh();
  } catch (error) {
    alert(error.message);
  } finally {
    els.runWalkforward.disabled = false;
  }
});

initializeViewSwitcher();
initializeDeskActions();
refresh();
setInterval(refresh, 1200);
