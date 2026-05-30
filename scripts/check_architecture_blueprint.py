from __future__ import annotations

import base64
import json
import os
import sys
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
HTTP_TIMEOUT_SECONDS = float(os.getenv("TRADER_HTTP_TIMEOUT_SECONDS", "20"))
AUTH_USER = os.getenv("TRADER_AUTH_USER", os.getenv("APP_BASIC_AUTH_USER", ""))
AUTH_PASSWORD = os.getenv("TRADER_AUTH_PASSWORD", os.getenv("APP_BASIC_AUTH_PASSWORD", ""))


def request_json(method: str, path: str) -> Any:
    headers = {"Accept": "application/json"}
    if AUTH_USER and AUTH_PASSWORD:
        token = base64.b64encode(f"{AUTH_USER}:{AUTH_PASSWORD}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    request = Request(f"{BASE_URL}{path}", headers=headers, method=method)
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def text_blob(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def main() -> int:
    try:
        state = request_json("GET", "/api/state?include_architecture=true")
        architecture = state.get("architecture") or {}
        if not architecture:
            return fail("state endpoint does not expose architecture blueprint")

        executive_summary = architecture.get("executive_summary") or []
        required_executive = {
            "研究层与执行层先切开": [
                "Anthropic financial-services",
                "TradingAgents",
                "LLM 负责研究、解释和信号候选",
                "确定性代码负责风控、下单、对账和结算",
                "AI_PROVIDER 默认保持 rules",
            ],
            "首版范围先小而闭环": [
                "单交易所、单账户或少量子账户",
                "先沙盒后小额实盘",
                "Binance Futures Testnet",
                "x-simulated-trading: 1",
                "Hyperliquid testnet API / WebSocket",
            ],
            "UI 是交易运营控制台": [
                "交易中台式控制台",
                "策略配置、回测、沙盒、实盘、告警、复盘、权限和密钥管理",
                "当前中文 UI 已展示",
                "移动端后续只保留状态、告警、紧急停机和仓位查看",
            ],
            "标准技术路线暂不前置重构": [
                "Python + FastAPI",
                "LangGraph 或 Anthropic Agent SDK",
                "PostgreSQL + TimescaleDB",
                "NATS JetStream",
                "Lightweight Charts、ECharts、Monaco Editor、xterm.js",
                "NautilusTrader",
                "vectorbt",
            ],
        }
        executive_by_title = {item.get("title"): item for item in executive_summary}
        missing_executive = sorted(set(required_executive) - set(executive_by_title))
        if missing_executive:
            return fail(f"missing executive summary cards: {missing_executive}")
        for title, phrases in required_executive.items():
            item_blob = text_blob(executive_by_title[title])
            for key in ["summary", "mvp_state", "production_rule"]:
                if not executive_by_title[title].get(key):
                    return fail(f"executive summary card {title} missing {key}")
            for phrase in phrases:
                if phrase not in item_blob:
                    return fail(f"executive summary card {title} missing phrase: {phrase}")

        project_assumptions = architecture.get("project_goals_assumptions") or {}
        default_target = project_assumptions.get("default_target", "")
        for phrase in [
            "1 到 5 名研究员/交易员",
            "1 家官方支持沙盒的合约交易所",
            "低到中频方向性或事件驱动策略",
            "LLM 输出必须先转成结构化信号",
            "确定性风控与下单链路",
        ]:
            if phrase not in default_target:
                return fail(f"project default target missing phrase: {phrase}")
        if "设计建议，不是官方要求" not in project_assumptions.get("reasoning", ""):
            return fail("project assumptions reasoning missing recommendation boundary")

        assumption_defaults = project_assumptions.get("assumption_defaults") or []
        required_assumptions = {
            "目标用户规模": ("个人自营；小团队内用；多团队/多租户", "小团队内用", "RBAC"),
            "支持的交易所": ("单一 CEX；多 CEX；CEX + DEX/链上永续", "单一 CEX", "撮合语义"),
            "策略复杂度": ("模板策略；多策略组合；做市/高频/统计套利", "模板策略", "库存风控"),
            "预算": ("MVP；标准；企业级", "标准偏 MVP", "KMS/HSM"),
            "合规要求": ("个人自营；团队内部工具；对外服务/SaaS", "团队内部工具", "KYC/AML"),
        }
        assumption_by_item = {item.get("item"): item for item in assumption_defaults}
        missing_assumptions = sorted(set(required_assumptions) - set(assumption_by_item))
        if missing_assumptions:
            return fail(f"missing project assumption defaults: {missing_assumptions}")
        for item_name, (options, recommended, fit_phrase) in required_assumptions.items():
            item = assumption_by_item[item_name]
            if item.get("current_status") != "未指定":
                return fail(f"project assumption {item_name} status must be 未指定")
            if item.get("options") != options:
                return fail(f"project assumption {item_name} options mismatch")
            if item.get("recommended_default") != recommended:
                return fail(f"project assumption {item_name} recommended default mismatch")
            if fit_phrase not in item.get("fit", ""):
                return fail(f"project assumption {item_name} fit missing {fit_phrase}")

        compliance_tiers = project_assumptions.get("compliance_tiers") or []
        required_compliance = {
            "个人或团队内部自营工具": "交易所条款、API 密钥安全、审计留痕与风险阈值",
            "多名用户使用的内部平台": "maker-checker、权限隔离、审批与留痕",
            "对外平台化或 SaaS 服务": "FATF 的 VASP AML/CFT 指引、MiCA 授权与披露要求",
        }
        compliance_by_tier = {item.get("tier"): item for item in compliance_tiers}
        missing_compliance = sorted(set(required_compliance) - set(compliance_by_tier))
        if missing_compliance:
            return fail(f"missing compliance tiers: {missing_compliance}")
        for tier, focus_phrase in required_compliance.items():
            item = compliance_by_tier[tier]
            if focus_phrase not in item.get("focus", ""):
                return fail(f"compliance tier {tier} missing focus phrase")
            if not item.get("default_action"):
                return fail(f"compliance tier {tier} missing default action")

        exchange_selection = project_assumptions.get("exchange_selection") or []
        required_venues = {
            "Binance U 本位": ["Futures testnet", "本地订单簿同步规则", "/fapi/v1/order/test"],
            "Bybit V5": ["orderLinkId", "速率限制头", "testnet 路径"],
            "OKX": ["x-simulated-trading: 1", "clOrdId", "expTime", "prevSeqId/seqId"],
            "Hyperliquid": ["testnet API", "testnet WebSocket", "API wallet", "nonce"],
        }
        venues_by_name = {item.get("venue"): item for item in exchange_selection}
        missing_venues = sorted(set(required_venues) - set(venues_by_name))
        if missing_venues:
            return fail(f"missing exchange selection venues: {missing_venues}")
        for venue, phrases in required_venues.items():
            item_blob = text_blob(venues_by_name[venue])
            for key in ["phase", "why", "engineering_notes"]:
                if not venues_by_name[venue].get(key):
                    return fail(f"exchange selection {venue} missing {key}")
            for phrase in phrases:
                if phrase not in item_blob:
                    return fail(f"exchange selection {venue} missing phrase {phrase}")

        anthropic_reference = architecture.get("anthropic_reference_project") or {}
        for phrase in [
            "不是一个面向加密合约自动交易的官方开源引擎",
            "anthropics/financial-services 官方金融服务代理模板",
            "Claude Agent SDK",
            "subagents",
            "tool use",
            "MCP 能力栈",
        ]:
            if phrase not in anthropic_reference.get("interpretation_premise", ""):
                return fail(f"Anthropic interpretation premise missing phrase: {phrase}")
        for phrase in ["不是现成的加密合约交易终端", "生产级 OMS/RMS", "人工复核边界"]:
            if phrase not in anthropic_reference.get("not_a_trading_terminal", ""):
                return fail(f"Anthropic non-terminal boundary missing phrase: {phrase}")

        repository_layers = anthropic_reference.get("repository_layers") or []
        required_layers = {
            "Agents": ["金融研究、分析、备忘录、对账草稿", "代理直接触碰订单执行"],
            "Skills / Commands": ["sector-overview", "competitive-analysis", "comps-analysis", "idea-generation"],
            "MCP Connectors": ["外部数据源", "权限和输入边界", "确定性服务端适配器"],
        }
        layers_by_name = {item.get("layer"): item for item in repository_layers}
        missing_layers = sorted(set(required_layers) - set(layers_by_name))
        if missing_layers:
            return fail(f"missing Anthropic repository layers: {missing_layers}")
        for layer, phrases in required_layers.items():
            item_blob = text_blob(layers_by_name[layer])
            for key in ["meaning", "mvp_mapping"]:
                if not layers_by_name[layer].get(key):
                    return fail(f"Anthropic layer {layer} missing {key}")
            for phrase in phrases:
                if phrase not in item_blob:
                    return fail(f"Anthropic layer {layer} missing phrase {phrase}")

        deployment_surfaces = anthropic_reference.get("deployment_surfaces") or []
        for phrase in [
            "Claude Cowork 插件",
            "Claude Managed Agents API",
            "managed-agent-cookbooks",
            "orchestrate.py",
            "leaf-worker subagents",
            "per-agent security notes",
        ]:
            if not any(phrase in item for item in deployment_surfaces):
                return fail(f"Anthropic deployment surfaces missing {phrase}")

        boundary_contract = anthropic_reference.get("boundary_contract") or []
        for phrase in [
            "模型、备忘录、研究笔记、对账草稿",
            "合格专业人员复核",
            "不做投资建议",
            "不执行交易",
            "不绑定风险",
            "不入账",
            "不做最终开户审批",
            "确定性系统负责执行与控制",
        ]:
            if not any(phrase in item for item in boundary_contract):
                return fail(f"Anthropic boundary contract missing {phrase}")

        market_researcher = anthropic_reference.get("market_researcher") or {}
        if "先界定研究范围" not in market_researcher.get("workflow", ""):
            return fail("market-researcher workflow missing scope definition")
        for phrase in ["sector-overview", "competitive-analysis", "comps-analysis", "idea-generation"]:
            if phrase not in market_researcher.get("workflow", ""):
                return fail(f"market-researcher workflow missing {phrase}")
        market_guardrails = market_researcher.get("guardrails") or []
        for phrase in [
            "不可信输入",
            "不能被执行",
            "每个数字都要引用来源",
            "CapIQ、FactSet 或 filing",
            "[UNSOURCED]",
            "分析师复核",
            "提示注入防御与证据链约束",
        ]:
            if not any(phrase in item for item in market_guardrails):
                return fail(f"market-researcher guardrails missing {phrase}")

        sdk_capabilities = anthropic_reference.get("agent_sdk_capabilities") or []
        required_sdk = {
            "agent loop 与 context management": ["可控循环", "SDK loop"],
            "subagents": ["context window", "system prompt", "工具权限", "独立权限控制"],
            "tool use strict: true": ["严格符合 schema", "TradeIntent"],
            "permissions allow/deny、hooks、runtime callback": ["PreToolUse", "PostToolUse", "subagent 启停", "允许、拒绝、改写或注入上下文"],
            "checkpointing": ["回滚工具写入的文件变更", "恢复点"],
            "OpenTelemetry monitoring": ["可观测链路", "OTEL 未接入"],
            "prompt caching": ["默认缓存寿命约 5 分钟", "降低成本和延迟"],
        }
        sdk_by_name = {item.get("capability"): item for item in sdk_capabilities}
        missing_sdk = sorted(set(required_sdk) - set(sdk_by_name))
        if missing_sdk:
            return fail(f"missing Agent SDK capabilities: {missing_sdk}")
        for capability, phrases in required_sdk.items():
            item_blob = text_blob(sdk_by_name[capability])
            for key in ["production_value", "mvp_boundary"]:
                if not sdk_by_name[capability].get(key):
                    return fail(f"Agent SDK capability {capability} missing {key}")
            for phrase in phrases:
                if phrase not in item_blob:
                    return fail(f"Agent SDK capability {capability} missing phrase {phrase}")

        tradingagents_reference = architecture.get("tradingagents_reference_project") or {}
        tradingagents_blob = text_blob(tradingagents_reference)
        for phrase in [
            "TradingAgents 参考项目拆解",
            "研究-辩论-决策-风控审批链路",
            "不是生产级加密合约 OMS/RMS",
        ]:
            if phrase not in tradingagents_blob:
                return fail(f"TradingAgents reference missing phrase: {phrase}")

        tradingagents_roles = tradingagents_reference.get("simulated_company_roles") or []
        required_tradingagents_roles = {
            "基本面分析师",
            "情绪分析师",
            "新闻分析师",
            "技术分析师",
            "研究员",
            "交易员",
            "风控经理",
        }
        found_tradingagents_roles = {role.get("role") for role in tradingagents_roles}
        missing_tradingagents_roles = sorted(required_tradingagents_roles - found_tradingagents_roles)
        if missing_tradingagents_roles:
            return fail(f"missing TradingAgents simulated company roles: {missing_tradingagents_roles}")
        for team in ["Analyst Team", "Researcher Team", "Trader Agents", "Risk Management Team"]:
            if team not in tradingagents_blob:
                return fail(f"TradingAgents reference missing team: {team}")
        for role in tradingagents_roles:
            for key in ["team", "responsibility"]:
                if not role.get(key):
                    return fail(f"TradingAgents role {role.get('role')} missing {key}")

        expected_tradingagents_flow = [
            "市场/新闻/社媒/基本面数据",
            "Analyst Team",
            "Bull / Bear Research Debate",
            "Trader",
            "Risk Team / Portfolio Manager",
            "Simulated Exchange / Decision Log / Checkpoint",
        ]
        if tradingagents_reference.get("architecture_flow") != expected_tradingagents_flow:
            return fail("TradingAgents architecture flow does not match the required six-step path")
        approval_text = tradingagents_reference.get("portfolio_manager_approval", "")
        for phrase in ["Portfolio Manager", "simulated exchange", "纸交易", "test order"]:
            if phrase not in approval_text:
                return fail(f"TradingAgents approval flow missing phrase: {phrase}")

        communication = tradingagents_reference.get("structured_communication") or {}
        communication_blob = text_blob(communication)
        for phrase in [
            "telephone effect",
            "structured communication protocol",
            "不可审计的自由文本长对话",
            "ResearchArtifact -> TradeIntent -> RiskCheck -> OMS/Executor",
        ]:
            if phrase not in communication_blob:
                return fail(f"TradingAgents structured communication missing phrase: {phrase}")
        required_outputs = {"结构化研究报告", "意见摘要", "置信度", "证据引用", "策略参数建议"}
        found_outputs = set(communication.get("preferred_outputs") or [])
        missing_outputs = sorted(required_outputs - found_outputs)
        if missing_outputs:
            return fail(f"TradingAgents preferred outputs missing: {missing_outputs}")

        runtime = tradingagents_reference.get("implementation_runtime") or {}
        runtime_blob = text_blob(runtime)
        for phrase in [
            "LangGraph",
            "TradingAgentsGraph().propagate()",
            "多家 LLM provider",
            "~/.tradingagents/memory/trading_memory.md",
            "同 ticker 分析",
            "checkpoint resume",
            "每个节点",
            "crash",
            "last successful node",
            "SQLite",
        ]:
            if phrase not in runtime_blob:
                return fail(f"TradingAgents runtime missing phrase: {phrase}")

        limitations = tradingagents_reference.get("limitations") or []
        limitations_blob = text_blob(limitations)
        for phrase in [
            "research purposes",
            "不构成投资建议",
            "模型、温度、时段和数据质量",
            "11 次 LLM 调用 + 20 多次工具调用",
            "3 个月回测",
            "cost/throughput/time consistency",
            "live crypto perpetual engine",
        ]:
            if phrase not in limitations_blob:
                return fail(f"TradingAgents limitations missing phrase: {phrase}")
        if "组织形态" not in tradingagents_reference.get("borrow_do_not_copy", ""):
            return fail("TradingAgents borrow/do-not-copy rule missing organization form")

        reference_synthesis = architecture.get("reference_synthesis") or {}
        synthesis_blob = text_blob(reference_synthesis)
        paths = reference_synthesis.get("architecture_paths") or []
        paths_by_reference = {path.get("reference"): path.get("steps") for path in paths}
        if paths_by_reference.get("TradingAgents 参考架构") != expected_tradingagents_flow:
            return fail("reference synthesis TradingAgents path does not match")
        expected_anthropic_path = [
            "用户请求 / 工作流触发",
            "Agent Plugin / Managed Agent",
            "Skills / Commands",
            "MCP Connectors",
            "研究工件",
            "人工签核",
        ]
        if paths_by_reference.get("Anthropic 参考架构") != expected_anthropic_path:
            return fail("reference synthesis Anthropic path does not match")
        for phrase in [
            "技能复用",
            "MCP 接入",
            "权限与 hook",
            "人工审核边界",
            "角色分工",
            "结构化报告",
            "辩论式研究",
            "checkpoint 恢复",
            "研究层和控制层",
            "不适合直接进入撮合热路径",
            "OMS、RMS、持仓结算、交易所对账、多用户 RBAC、审计不可抵赖、真仓故障恢复",
            "不能简单套壳",
            "上层研究与治理框架",
        ]:
            if phrase not in synthesis_blob:
                return fail(f"reference synthesis missing phrase: {phrase}")

        layered_architecture = architecture.get("layered_architecture") or {}
        layered_blob = text_blob(layered_architecture)
        for phrase in [
            "推荐的分层架构",
            "研究平面、控制平面、执行平面、观测平面四平面",
            "Anthropic Agent SDK / LangGraph / 多代理",
            "确定性、可重放、低延迟",
            "不是任何单一官方项目原样提供的图",
        ]:
            if phrase not in layered_blob:
                return fail(f"layered architecture missing phrase: {phrase}")

        layered_planes = layered_architecture.get("planes") or []
        required_layered_planes = {
            "研究平面": [
                "允许使用 Anthropic Agent SDK / LangGraph / 多代理",
                "结构化研究工件",
                "不直接下单",
            ],
            "控制平面": [
                "策略版本、审批、RBAC、配置发布",
                "live/testnet 开关",
            ],
            "执行平面": [
                "确定性、可重放、低延迟",
                "venue-specific adapter",
            ],
            "观测平面": [
                "日志、指标、告警与审计",
                "可验证证据链",
            ],
        }
        layered_planes_by_name = {plane.get("name"): plane for plane in layered_planes}
        missing_layered_planes = sorted(set(required_layered_planes) - set(layered_planes_by_name))
        if missing_layered_planes:
            return fail(f"missing layered architecture planes: {missing_layered_planes}")
        for name, phrases in required_layered_planes.items():
            plane_blob = text_blob(layered_planes_by_name[name])
            for phrase in phrases:
                if phrase not in plane_blob:
                    return fail(f"layered architecture plane {name} missing phrase: {phrase}")

        adapter_rule = layered_architecture.get("venue_adapter_rule") or {}
        adapter_blob = text_blob(adapter_rule)
        expected_adapter_differences = ["签名", "幂等字段", "速率限制", "订单簿同步", "模拟盘 header", "请求失效时间"]
        if adapter_rule.get("api_differences") != expected_adapter_differences:
            return fail("venue adapter differences do not match required API constraints")
        for phrase in ["不能只依赖统一抽象", "venue-specific adapter", "client order id/orderLinkId/clOrdId", "请求过期语义"]:
            if phrase not in adapter_blob:
                return fail(f"venue adapter rule missing phrase: {phrase}")

        graph = layered_architecture.get("architecture_graph") or {}
        graph_blob = text_blob(graph)
        expected_node_ids = {
            "UI",
            "API",
            "AUTH",
            "MD",
            "NORM",
            "BUS",
            "RESEARCH",
            "STRAT",
            "RISK",
            "OMS",
            "ADAPTER",
            "EX",
            "POS",
            "SETTLE",
            "BT",
            "AUDIT",
            "OBS",
            "DB",
            "TS",
            "OLAP",
            "CACHE",
        }
        graph_nodes = graph.get("nodes") or []
        found_node_ids = {node.get("id") for node in graph_nodes}
        if found_node_ids != expected_node_ids:
            return fail(f"architecture graph nodes mismatch: {sorted(expected_node_ids - found_node_ids)}")
        expected_edges = [
            ("UI", "API"),
            ("API", "AUTH"),
            ("API", "RESEARCH"),
            ("API", "BT"),
            ("API", "OMS"),
            ("API", "POS"),
            ("MD", "NORM"),
            ("NORM", "BUS"),
            ("BUS", "RESEARCH"),
            ("BUS", "STRAT"),
            ("RESEARCH", "STRAT"),
            ("STRAT", "RISK"),
            ("RISK", "OMS"),
            ("OMS", "ADAPTER"),
            ("ADAPTER", "EX"),
            ("EX", "OMS"),
            ("EX", "POS"),
            ("OMS", "AUDIT"),
            ("POS", "SETTLE"),
            ("SETTLE", "DB"),
            ("POS", "TS"),
            ("AUDIT", "OLAP"),
            ("BT", "OLAP"),
            ("API", "DB"),
            ("API", "CACHE"),
            ("BUS", "OBS"),
            ("OMS", "OBS"),
            ("POS", "OBS"),
        ]
        found_edges = [(edge.get("from"), edge.get("to")) for edge in graph.get("edges") or []]
        if found_edges != expected_edges:
            return fail("architecture graph edges do not match the required production graph")
        for phrase in [
            "flowchart LR",
            "UI --> API --> AUTH",
            "MD --> NORM --> BUS",
            "STRAT --> RISK --> OMS --> ADAPTER --> EX",
            "POS --> SETTLE --> DB",
            "BUS --> OBS",
        ]:
            if phrase not in graph_blob:
                return fail(f"architecture graph mermaid missing phrase: {phrase}")

        strategy_split = layered_architecture.get("strategy_engine_split") or []
        split_blob = text_blob(strategy_split)
        for phrase in [
            "研究型策略引擎",
            "从新闻、社媒、funding、盘口与技术指标中生成候选信号",
            "确定性策略运行时",
            "只接收结构化输入，输出明确的动作、仓位和条件",
        ]:
            if phrase not in split_blob:
                return fail(f"strategy engine split missing phrase: {phrase}")
        if len(layered_architecture.get("module_definitions") or []) != 10:
            return fail("layered architecture module definitions must mirror 10 key modules")
        if "Anthropic 的治理思路" not in layered_architecture.get("integration_statement", ""):
            return fail("layered architecture integration statement missing Anthropic governance")
        if "TradingAgents 的研究组织方式" not in layered_architecture.get("integration_statement", ""):
            return fail("layered architecture integration statement missing TradingAgents research organization")

        planes = architecture.get("planes") or []
        required_planes = {"研究平面", "控制平面", "执行平面", "观测平面"}
        found_planes = {plane.get("name") for plane in planes}
        missing_planes = sorted(required_planes - found_planes)
        if missing_planes:
            return fail(f"missing architecture planes: {missing_planes}")

        components = architecture.get("components") or []
        required_components = {
            "Web UI / Mobile Readonly",
            "API Gateway / BFF",
            "SSO / RBAC / Approval",
            "Market Data Ingest",
            "Normalizer / Sequencer",
            "Event Bus",
            "Agent Research Service",
            "Deterministic Strategy Runtime",
            "Risk Engine",
            "Order Management",
            "Exchange Adapters",
            "Exchange REST / WS",
            "Position & PnL Ledger",
            "Funding / Fee / Settlement",
            "Backtest / Replay",
            "Audit Log / Event Store",
            "Metrics / Logs / Alerts",
            "PostgreSQL",
            "TimescaleDB",
            "ClickHouse",
            "Redis",
        }
        found_components = {component.get("name") for component in components}
        missing_components = sorted(required_components - found_components)
        if missing_components:
            return fail(f"missing target components: {missing_components}")

        required_module_definition_rows = [
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
        ]
        module_definition_table = architecture.get("module_definition_table") or {}
        if module_definition_table.get("title") != "关键模块定义":
            return fail("module definition table title missing")
        if "参考项目和交易所文档" not in module_definition_table.get("summary", ""):
            return fail("module definition table summary missing reference/exchange grounding")
        if module_definition_table.get("rows") != required_module_definition_rows:
            return fail("module definition table rows do not exactly match the required module table")

        matrix = architecture.get("module_matrix") or []
        required_module_definitions = {
            row["module"]: (row["responsibility"], row["production_note"])
            for row in required_module_definition_rows
        }
        found_modules = {module.get("module") for module in matrix}
        missing_modules = sorted(set(required_module_definitions) - found_modules)
        if missing_modules:
            return fail(f"missing module definitions: {missing_modules}")
        matrix_by_name = {module.get("module"): module for module in matrix}
        for name, (responsibility, production_note) in required_module_definitions.items():
            module = matrix_by_name[name]
            if responsibility not in module.get("responsibility", ""):
                return fail(f"module {name} missing responsibility: {responsibility}")
            if production_note not in module.get("production_note", ""):
                return fail(f"module {name} missing production note: {production_note}")
            for key in ["current", "required_next"]:
                if not module.get(key):
                    return fail(f"module {name} missing {key}")

        required_implementation_note_rows = [
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
        ]
        implementation_note_table = architecture.get("implementation_note_table") or {}
        if implementation_note_table.get("title") != "自动交易系统实现注意事项":
            return fail("implementation note table title missing")
        if "testnet 或 live 前" not in implementation_note_table.get("summary", ""):
            return fail("implementation note table summary missing deployment gate context")
        if implementation_note_table.get("rows") != required_implementation_note_rows:
            return fail("implementation note table rows do not exactly match the required implementation notes")

        notes = architecture.get("implementation_notes") or []
        required_notes = {row["topic"] for row in required_implementation_note_rows}
        found_notes = {note.get("topic") for note in notes}
        missing_notes = sorted(required_notes - found_notes)
        if missing_notes:
            return fail(f"missing implementation notes: {missing_notes}")
        for note in notes:
            for key in ["basis", "recommendation", "current_control", "required_next"]:
                if not note.get(key):
                    return fail(f"implementation note {note.get('topic')} missing {key}")

        entity_model = architecture.get("entity_model") or {}
        if entity_model.get("title") != "关键数据流与实体关系":
            return fail("entity model title missing")
        for phrase in ["策略、订单、成交、仓位、风控规则与审计日志", "可回放、可解释、可核账"]:
            if phrase not in entity_model.get("summary", ""):
                return fail(f"entity model summary missing phrase: {phrase}")
            if phrase not in entity_model.get("focus", ""):
                return fail(f"entity model focus missing phrase: {phrase}")
        expected_er_mermaid = """erDiagram
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
    FILL ||--o{ AUDIT_LOG : recorded_in"""
        if entity_model.get("mermaid") != expected_er_mermaid:
            return fail("entity model mermaid ER diagram does not exactly match required graph")
        entities = entity_model.get("entities") or []
        required_entities = {
            "USER",
            "ACCOUNT",
            "API_KEY",
            "AUDIT_LOG",
            "STRATEGY_DEPLOYMENT",
            "ORDER",
            "POSITION",
            "RISK_RULE_BINDING",
            "STRATEGY",
            "STRATEGY_VERSION",
            "BACKTEST_RUN",
            "SIGNAL_EVENT",
            "FILL",
            "EXCHANGE_ORDER_REF",
            "SETTLEMENT_EVENT",
            "RISK_RULE",
            "RISK_CHECK_RESULT",
            "RESEARCH_ARTIFACT",
        }
        found_entities = {entity.get("name") for entity in entities}
        missing_entities = sorted(required_entities - found_entities)
        if missing_entities:
            return fail(f"missing entity model entries: {missing_entities}")
        for entity in entities:
            if not entity.get("label") or not entity.get("current"):
                return fail(f"entity {entity.get('name')} missing label/current")

        relationships = entity_model.get("relationships") or []
        required_relationships = {
            ("USER", "owns", "ACCOUNT"),
            ("USER", "manages", "API_KEY"),
            ("USER", "triggers", "AUDIT_LOG"),
            ("ACCOUNT", "runs", "STRATEGY_DEPLOYMENT"),
            ("ACCOUNT", "places", "ORDER"),
            ("ACCOUNT", "holds", "POSITION"),
            ("ACCOUNT", "uses", "RISK_RULE_BINDING"),
            ("STRATEGY", "has", "STRATEGY_VERSION"),
            ("STRATEGY_VERSION", "tested_by", "BACKTEST_RUN"),
            ("STRATEGY_VERSION", "emits", "SIGNAL_EVENT"),
            ("STRATEGY_DEPLOYMENT", "deploys", "STRATEGY_VERSION"),
            ("SIGNAL_EVENT", "may_create", "ORDER"),
            ("ORDER", "contains", "FILL"),
            ("ORDER", "maps_to", "EXCHANGE_ORDER_REF"),
            ("POSITION", "updated_by", "FILL"),
            ("POSITION", "settled_by", "SETTLEMENT_EVENT"),
            ("RISK_RULE", "applied_to", "RISK_RULE_BINDING"),
            ("ORDER", "checked_by", "RISK_CHECK_RESULT"),
            ("SIGNAL_EVENT", "explained_by", "RESEARCH_ARTIFACT"),
            ("ORDER", "recorded_in", "AUDIT_LOG"),
            ("FILL", "recorded_in", "AUDIT_LOG"),
        }
        found_relationships = {
            (item.get("from"), item.get("relation"), item.get("to"))
            for item in relationships
        }
        missing_relationships = sorted(required_relationships - found_relationships)
        if missing_relationships:
            return fail(f"missing entity relationships: {missing_relationships}")
        for relationship in relationships:
            if not relationship.get("detail"):
                return fail(f"relationship {relationship} missing detail")

        ui_ia = architecture.get("ui_information_architecture") or {}
        expected_navigation_tree = """工作台
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
   └─ 系统配置"""
        if ui_ia.get("title") != "控制台信息架构":
            return fail("UI information architecture title missing")
        if ui_ia.get("root") != "工作台":
            return fail("UI information architecture root must be 工作台")
        if ui_ia.get("navigation_tree") != expected_navigation_tree:
            return fail("UI information architecture tree does not exactly match required workbench tree")
        navigation = ui_ia.get("navigation") or []
        required_navigation = {
            "仪表盘": set(),
            "策略中心": {"策略列表", "策略编辑器", "参数集与版本", "发布审批", "研究工件与信号预览"},
            "回测与回放": {"任务列表", "结果对比", "交易明细", "事件回放"},
            "交易执行": {"订单簿", "当前委托", "成交流水", "仓位详情"},
            "风控中心": {"规则配置", "账户风险", "告警事件", "熔断与人工干预"},
            "数据与审计": {"行情健康", "日志检索", "审计视图", "指标看板"},
            "用户与系统": {"用户设置", "API 密钥管理", "角色与权限", "系统配置"},
        }
        navigation_by_name = {item.get("name"): set(item.get("children") or []) for item in navigation}
        missing_nav = sorted(set(required_navigation) - set(navigation_by_name))
        if missing_nav:
            return fail(f"missing UI navigation groups: {missing_nav}")
        for name, children in required_navigation.items():
            missing_children = sorted(children - navigation_by_name.get(name, set()))
            if missing_children:
                return fail(f"navigation group {name} missing children: {missing_children}")

        required_page_component_rows = [
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
        ]
        page_component_table = ui_ia.get("page_component_table") or {}
        if page_component_table.get("title") != "主要页面与组件":
            return fail("UI page component table title missing")
        if "精确验收表" not in page_component_table.get("summary", ""):
            return fail("UI page component table summary missing exact acceptance phrasing")
        if page_component_table.get("rows") != required_page_component_rows:
            return fail("UI page component table rows do not exactly match required page table")
        pages = ui_ia.get("page_components") or []
        if pages != required_page_component_rows:
            return fail("UI page components do not mirror the exact page component table")
        required_pages = {row["page"] for row in required_page_component_rows}
        found_pages = {page.get("page") for page in pages}
        missing_pages = sorted(required_pages - found_pages)
        if missing_pages:
            return fail(f"missing UI page components: {missing_pages}")
        for page in pages:
            for key in ["components", "design_focus"]:
                if not page.get(key):
                    return fail(f"UI page {page.get('page')} missing {key}")

        tooling = ui_ia.get("component_tooling") or []
        for tool in ["Monaco", "Lightweight Charts", "ECharts", "xterm.js"]:
            if not any(tool in item for item in tooling):
                return fail(f"UI tooling missing {tool}")

        flow = ui_ia.get("interaction_flow") or {}
        required_steps = [
            "创建策略草稿",
            "补充研究工件",
            "跑回测",
            "复核收益/风险/成交分布",
            "发布到 sandbox",
            "观察影子运行",
            "进入 live",
            "日志 / 审计 / 复盘",
        ]
        found_steps = [step.get("name") for step in flow.get("steps") or []]
        if found_steps != required_steps:
            return fail(f"interaction flow mismatch: {found_steps}")
        if "证据—参数—风险—发布" not in flow.get("summary", ""):
            return fail("interaction flow summary does not connect evidence, parameters, risk, and release")
        for step in flow.get("steps") or []:
            if not step.get("current"):
                return fail(f"interaction flow step {step.get('name')} missing current support")
        required_loop = [
            "策略草稿",
            "研究工件与结构化信号",
            "回测 / 回放",
            "审批 / 风控复核",
            "Sandbox 部署",
            "监控与对账",
            "小额 Live",
            "日志 / 审计 / 复盘",
        ]
        found_loop = [step.get("name") for step in flow.get("main_loop") or []]
        if found_loop != required_loop:
            return fail(f"main interaction loop mismatch: {found_loop}")
        for step in flow.get("main_loop") or []:
            if not step.get("purpose"):
                return fail(f"main loop step {step.get('name')} missing purpose")

        responsive = ui_ia.get("responsive_guidance") or {}
        for key, phrase in {
            "principle": "桌面优先、移动端降能力",
            "desktop": "12 栏栅格",
            "mobile": "不做完整策略编辑",
            "incident": "3 步内可达",
        }.items():
            if phrase not in responsive.get(key, ""):
                return fail(f"responsive guidance missing {phrase}")

        charts = ui_ia.get("chart_guidance") or {}
        for chart in ["K 线", "成交量", "盘口深度", "最新成交", "持仓均价/止盈止损线"]:
            if chart not in (charts.get("trading_charts") or []):
                return fail(f"trading chart guidance missing {chart}")
        for chart in ["权益曲线", "回撤曲线", "rolling Sharpe", "胜率/盈亏比分布", "滑点散点图", "账户/策略敞口堆叠图", "资金费时间线"]:
            if chart not in (charts.get("analysis_charts") or []):
                return fail(f"analysis chart guidance missing {chart}")
        for tool in ["Lightweight Charts", "ECharts"]:
            if not any(tool in item for item in (charts.get("tool_mapping") or [])):
                return fail(f"chart tool mapping missing {tool}")

        technical = architecture.get("technical_implementation") or {}
        stack_layers = technical.get("stack_layers") or []
        required_stack = {
            "研究代理编排": ("LangGraph / Anthropic Agent SDK", "是", "结构化信号"),
            "API / 控制面": ("FastAPI", "是", "Python"),
            "执行引擎": ("自研确定性运行时；标准/企业级可引入 NautilusTrader", "是", "热路径"),
            "前端框架": ("Next.js", "是", "控制台式"),
            "金融图表": ("Lightweight Charts", "是", "K 线"),
            "通用可视化": ("ECharts", "是", "热力图"),
            "策略编辑器": ("Monaco Editor", "是", "代码/DSL/JSON"),
            "日志终端": ("xterm.js", "可选", "在线 tail"),
            "OLTP 数据库": ("PostgreSQL", "是", "订单、仓位、用户、审批"),
            "时序数据库": ("TimescaleDB", "是", "K 线"),
            "分析数据库": ("ClickHouse", "标准起", "审计查询"),
            "消息总线": ("NATS JetStream", "是", "事件流"),
            "监控与告警": ("OTEL + Prometheus + Alertmanager", "是", "路由静默"),
            "回测工具": ("vectorbt / 自研事件回放", "是", "快速实验"),
            "参考型 bot/运维借鉴": ("Freqtrade", "可选", "WebUI"),
            "多交易所统一层": ("CCXT", "原型期", "补数据"),
        }
        stack_by_layer = {item.get("layer"): item for item in stack_layers}
        missing_stack = sorted(set(required_stack) - set(stack_by_layer))
        if missing_stack:
            return fail(f"missing technical stack layers: {missing_stack}")
        for layer, (recommendation, preferred, note_phrase) in required_stack.items():
            item = stack_by_layer[layer]
            if item.get("recommendation") != recommendation:
                return fail(f"stack layer {layer} recommendation mismatch: {item.get('recommendation')}")
            if item.get("preferred") != preferred:
                return fail(f"stack layer {layer} preferred mismatch: {item.get('preferred')}")
            if note_phrase not in item.get("note", ""):
                return fail(f"stack layer {layer} note missing {note_phrase}")

        api_priority = technical.get("api_priority") or []
        for phrase in ["官方交易所 REST/WS 文档与官方 SDK", "venue-specific adapter", "CCXT"]:
            if not any(phrase in item for item in api_priority):
                return fail(f"API priority missing {phrase}")

        roadmap = technical.get("roadmap") or []
        required_roadmap = {
            "架构定型": ("2–3 人", "2–3 周"),
            "单交易所闭环": ("4–6 人", "4–6 周"),
            "回测与回放": ("4–6 人", "3–5 周"),
            "控制台与告警": ("5–7 人", "4–6 周"),
            "小额实盘": ("5–8 人", "4–8 周"),
            "标准化扩展": ("7–12 人", "2–6 个月"),
        }
        roadmap_by_stage = {item.get("stage"): item for item in roadmap}
        missing_roadmap = sorted(set(required_roadmap) - set(roadmap_by_stage))
        if missing_roadmap:
            return fail(f"missing roadmap stages: {missing_roadmap}")
        for stage, (team, timeline) in required_roadmap.items():
            item = roadmap_by_stage[stage]
            if item.get("team") != team or item.get("timeline") != timeline:
                return fail(f"roadmap stage {stage} team/timeline mismatch")
            for key in ["goal", "deliverables"]:
                if not item.get(key):
                    return fail(f"roadmap stage {stage} missing {key}")

        scale_rows = technical.get("scale_comparison") or []
        required_dimensions = {
            "目标用户",
            "交易所范围",
            "策略范围",
            "关键功能",
            "UI 范围",
            "技术形态",
            "交付团队",
            "日历时间",
            "粗略预算",
            "适用场景",
        }
        found_dimensions = {item.get("dimension") for item in scale_rows}
        missing_dimensions = sorted(required_dimensions - found_dimensions)
        if missing_dimensions:
            return fail(f"missing scale comparison dimensions: {missing_dimensions}")
        for row in scale_rows:
            for key in ["mvp", "standard", "enterprise"]:
                if not row.get(key):
                    return fail(f"scale comparison {row.get('dimension')} missing {key}")
        if "MVP 分两期" not in technical.get("recommended_start", ""):
            return fail("recommended start missing MVP two-phase guidance")
        if "系统边界不清" not in technical.get("risk_boundary", ""):
            return fail("risk boundary missing system-boundary warning")
        if "正常路径 + 异常路径 + 恢复路径" not in technical.get("testing_principle", ""):
            return fail("testing principle missing normal/exception/recovery coverage")

        risk_register = technical.get("risk_register") or []
        required_risks = {
            "API 密钥泄露": "服务端签名",
            "重复下单": "reconcile before retry",
            "行情失真": "checksum",
            "时间漂移": "recvWindow/expTime/expiresAfter",
            "回测幻觉": "funding",
            "模型幻觉或被注入": "严格工具 schema",
            "合规误踩": "监管分类",
            "告警风暴": "分组、去重、静默",
            "运维恢复失败": "账本为权威源",
            "人为误操作": "二次确认",
        }
        risks_by_name = {item.get("risk"): item for item in risk_register}
        missing_risks = sorted(set(required_risks) - set(risks_by_name))
        if missing_risks:
            return fail(f"missing risk register items: {missing_risks}")
        for risk, mitigation_phrase in required_risks.items():
            item = risks_by_name[risk]
            for key in ["typical_manifestation", "mitigation"]:
                if not item.get(key):
                    return fail(f"risk register item {risk} missing {key}")
            if mitigation_phrase not in item.get("mitigation", ""):
                return fail(f"risk register item {risk} missing mitigation phrase {mitigation_phrase}")

        acceptance_matrix = technical.get("acceptance_matrix") or []
        required_acceptance = {
            "行情同步": "2 秒",
            "下单幂等": "最多在交易所生成 1 个有效挂单",
            "撤改单": "幽灵挂单",
            "风控前置": "绝不发单",
            "持仓与结算": "可复算",
            "回测与回放": "版本差异可解释",
            "故障恢复": "先对账再恢复",
            "权限控制": "无法执行 live 发布/查看 secret",
            "UI 可用性": "3 步内可达",
            "告警链路": "1 分钟内到达",
        }
        acceptance_by_category = {item.get("category"): item for item in acceptance_matrix}
        missing_acceptance = sorted(set(required_acceptance) - set(acceptance_by_category))
        if missing_acceptance:
            return fail(f"missing acceptance matrix items: {missing_acceptance}")
        for category, acceptance_phrase in required_acceptance.items():
            item = acceptance_by_category[category]
            for key in ["key_cases", "minimum_acceptance"]:
                if not item.get(key):
                    return fail(f"acceptance matrix item {category} missing {key}")
            if acceptance_phrase not in item.get("minimum_acceptance", ""):
                return fail(f"acceptance matrix item {category} missing phrase {acceptance_phrase}")

        required_gates = [
            "连续多日的沙盒与回放结果一致性达标。",
            "未知状态订单不出现重复开仓。",
            "盘口断链可自动恢复。",
            "持仓与账本可每日对平。",
            "关键告警可在 SLA 内到达。",
            "RBAC 与审计经演练验证通过。",
        ]
        go_live_gates = technical.get("go_live_gates") or []
        if go_live_gates != required_gates:
            return fail("go-live gates do not match the required hard gates")

        blob = text_blob(architecture)
        for phrase in [
            "技能复用",
            "Anthropic financial-services",
            "LLM 负责研究、解释和信号候选",
            "确定性代码负责风控、下单、对账和结算",
            "Binance Futures Testnet",
            "交易运营控制台",
            "项目目标与假设",
            "小团队内用",
            "团队内部工具",
            "maker-checker",
            "FATF 的 VASP AML/CFT",
            "x-simulated-trading: 1",
            "API wallet",
            "Anthropic 参考项目拆解",
            "anthropics/financial-services 官方金融服务代理模板",
            "Agents",
            "Skills / Commands",
            "MCP Connectors",
            "TradingAgents 参考项目拆解",
            "基本面分析师",
            "情绪分析师",
            "新闻分析师",
            "技术分析师",
            "研究员",
            "交易员",
            "风控经理",
            "telephone effect",
            "structured communication protocol",
            "TradingAgentsGraph().propagate()",
            "~/.tradingagents/memory/trading_memory.md",
            "11 次 LLM 调用 + 20 多次工具调用",
            "两类参考综合吸收点",
            "不能简单套壳",
            "上层研究与治理框架",
            "推荐的分层架构",
            "研究平面、控制平面、执行平面、观测平面四平面",
            "确定性、可重放、低延迟",
            "模拟盘 header",
            "请求失效时间",
            "Web UI / Mobile Readonly",
            "API Gateway / BFF",
            "Event Bus",
            "Position & PnL Ledger",
            "Funding / Fee / Settlement",
            "研究型策略引擎",
            "确定性策略运行时",
            "从新闻、社媒、funding、盘口与技术指标中生成候选信号",
            "关键模块定义",
            "维护策略 DSL、参数集、版本、因子与代理信号组合",
            "下单、改单、撤单、批量操作、生命周期状态机",
            "append-only；支持 correlation ID",
            "沙盒与实盘共用同一套数据模型与订单模型",
            "Claude Cowork 插件",
            "Claude Managed Agents API",
            "market-researcher",
            "CapIQ、FactSet 或 filing",
            "[UNSOURCED]",
            "tool use strict: true",
            "PreToolUse",
            "PostToolUse",
            "OpenTelemetry monitoring",
            "默认缓存寿命约 5 分钟",
            "MCP",
            "权限",
            "钩子",
            "人工审核",
            "角色分工",
            "结构化报告",
            "辩论式研究",
            "检查点恢复",
            "研究层和控制层",
            "撮合热路径",
            "venue-specific adapter",
            "签名",
            "幂等",
            "速率限制",
            "订单簿",
            "模拟盘",
            "请求失效时间",
            "多用户 RBAC",
            "不可抵赖审计",
            "真仓故障恢复",
            "HMAC/RSA",
            "recv_window",
            "trade/withdraw 权限",
            "14 天不活跃",
            "KMS/HSM",
            "signer service",
            "前端绝不接触 secret",
            "newClientOrderId",
            "orderLinkId",
            "clOrdId",
            "PENDING_RECON",
            "先查单 / 等私有 WS 回报",
            "X-Bapi-Limit",
            "418 IP ban",
            "per-venue、per-account、per-endpoint",
            "IOC",
            "FOK",
            "PostOnly",
            "Price Limit Mechanism",
            "可成交性模型",
            "lastUpdateId/U/u/pu",
            "canonical order-book engine",
            "checksum",
            "prevSeqId/seqId",
            "所有机器强制 NTP",
            "NTP",
            "expTime",
            "expiresAfter",
            "超时未处理",
            "真实盘口、资金费、部分成交、撤改单失败、延迟与限频",
            "策略运行态、订单态、持仓态、代理态分别做 checkpoint",
            "人工审批阈值",
            "simulated exchange",
            "checkpoint",
            "FATF",
            "MiCA",
            "replay",
            "sandbox",
            "策略发布前先过 replay，再过 sandbox，再进入小额 live",
            "自动交易系统实现注意事项",
            "erDiagram",
            "USER ||--o{ ACCOUNT : owns",
            "STRATEGY_DEPLOYMENT }o--|| STRATEGY_VERSION : deploys",
            "ORDER }o--|| EXCHANGE_ORDER_REF : maps_to",
            "SIGNAL_EVENT ||--o{ RESEARCH_ARTIFACT : explained_by",
            "工作台",
            "├─ 仪表盘",
            "├─ 策略中心",
            "│  └─ 研究工件与信号预览",
            "├─ 回测与回放",
            "├─ 交易执行",
            "├─ 风控中心",
            "├─ 数据与审计",
            "└─ 用户与系统",
            "   └─ 系统配置",
            "可回放、可解释、可核账",
            "策略、订单、成交、仓位、风控规则与审计日志",
            "面向交易运营和风控协作的控制台",
            "主要页面与组件",
            "首屏只放“需要动作”的信息，不堆技术细节",
            "把“研究解释”和“策略配置”并排展示，便于审阅",
            "尽量桌面端三栏布局，减少视线跳转",
            "不只显示仓位数量，要显示“为什么还在持有”",
            "审计视图要偏“证据链”，日志视图要偏“排障链”",
            "创建策略草稿",
            "小额 Live",
            "桌面优先、移动端降能力",
            "交易图",
            "分析图",
            "LangGraph",
            "Anthropic Agent SDK",
            "FastAPI",
            "Next.js",
            "PostgreSQL",
            "TimescaleDB",
            "NATS JetStream",
            "Prometheus + Alertmanager",
            "vectorbt",
            "Freqtrade",
            "NautilusTrader",
            "官方交易所 REST/WS 文档与官方 SDK",
            "架构定型",
            "单交易所闭环",
            "标准化扩展",
            "60–120 万",
            "500–1200 万以上",
            "正常路径 + 异常路径 + 恢复路径",
            "API 密钥泄露",
            "重复下单",
            "恢复先对账后恢复策略",
            "未知状态订单不出现重复开仓",
            "关键告警可在 SLA 内到达",
            "RBAC 与审计经演练验证通过",
        ]:
            if phrase not in blob:
                return fail(f"architecture blueprint missing phrase: {phrase}")

        status_counts: dict[str, int] = {}
        for component in components:
            status_counts[component.get("status", "unknown")] = status_counts.get(component.get("status", "unknown"), 0) + 1

        print(
            json.dumps(
                {
                    "executive_summary_cards": len(executive_summary),
                    "project_assumption_defaults": len(assumption_defaults),
                    "compliance_tiers": len(compliance_tiers),
                    "exchange_selection_venues": len(exchange_selection),
                    "anthropic_repository_layers": len(repository_layers),
                    "anthropic_boundary_items": len(boundary_contract),
                    "market_researcher_guardrails": len(market_guardrails),
                    "agent_sdk_capabilities": len(sdk_capabilities),
                    "tradingagents_roles": len(tradingagents_roles),
                    "tradingagents_flow_steps": len(tradingagents_reference.get("architecture_flow") or []),
                    "tradingagents_limitations": len(limitations),
                    "reference_synthesis_paths": len(paths),
                    "reference_absorb_points": len(reference_synthesis.get("absorb_points") or []),
                    "layered_architecture_planes": len(layered_planes),
                    "architecture_graph_nodes": len(graph_nodes),
                    "architecture_graph_edges": len(found_edges),
                    "strategy_engine_split_parts": len(strategy_split),
                    "module_definition_rows": len(module_definition_table.get("rows") or []),
                    "implementation_note_rows": len(implementation_note_table.get("rows") or []),
                    "planes": len(planes),
                    "components": len(components),
                    "modules": len(matrix),
                    "implementation_notes": len(notes),
                    "entities": len(entities),
                    "relationships": len(relationships),
                    "entity_mermaid_lines": len(entity_model.get("mermaid", "").splitlines()),
                    "ui_navigation_groups": len(navigation),
                    "ui_navigation_tree_lines": len(ui_ia.get("navigation_tree", "").splitlines()),
                    "ui_page_component_table_rows": len(page_component_table.get("rows") or []),
                    "ui_pages": len(pages),
                    "interaction_steps": len(found_steps),
                    "main_loop_steps": len(found_loop),
                    "technical_stack_layers": len(stack_layers),
                    "roadmap_stages": len(roadmap),
                    "scale_dimensions": len(scale_rows),
                    "risk_register_items": len(risk_register),
                    "acceptance_items": len(acceptance_matrix),
                    "go_live_gates": len(go_live_gates),
                    "status_counts": status_counts,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except HTTPError as exc:
        return fail(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (URLError, TimeoutError, OSError) as exc:
        return fail(f"could not reach {BASE_URL}: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
