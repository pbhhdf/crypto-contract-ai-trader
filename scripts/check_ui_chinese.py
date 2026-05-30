from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT_DIR / "app" / "static" / "index.html"
APP_JS_PATH = ROOT_DIR / "app" / "static" / "app.js"

ALLOWED_TOKENS = {
    "AI",
    "API",
    "OMS",
    "PnL",
    "ROE",
    "USDT",
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "OpenAI",
    "Binance",
    "Testnet",
    "ID",
    "MVP",
    "list",
    "read",
    "write",
    "append",
}

DENIED_VISIBLE_SNIPPETS = [
    "Local paper-trading control room",
    "Deployment Readiness",
    "Checking",
    "Scheduler",
    "Enabled",
    "Interval minutes",
    "Save Schedule",
    "Run Now",
    "Last Run",
    "Next Run",
    "Paper Equity",
    "Risk Center",
    "Backtest Lab",
    "No backtest yet",
    "Run Backtest",
    "Compare Params",
    "Walk Forward",
    "Parameter Leaderboard",
    "Walk-forward Validation",
    "Paper Positions",
    "No open positions",
    "OMS Reconciliation",
    "Reconcile Orders",
    "Total Orders",
    "Needs Review",
    "Unknown Venue",
]


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.texts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if text:
            self.texts.append(text)


def english_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text)
    return [token for token in tokens if token not in ALLOWED_TOKENS]


def fail(message: str) -> int:
    print(f"FAILED: {message}", file=sys.stderr)
    return 1


def main() -> int:
    html = INDEX_PATH.read_text(encoding="utf-8")
    app_js = APP_JS_PATH.read_text(encoding="utf-8")
    parser = VisibleTextParser()
    parser.feed(html)

    visible_issues = [
        text
        for text in parser.texts
        if english_tokens(text)
    ]
    if visible_issues:
        return fail(f"visible UI still has non-technical English: {visible_issues[:12]}")

    denied_hits = [
        snippet
        for snippet in DENIED_VISIBLE_SNIPPETS
        if snippet in html
    ]
    if denied_hits:
        return fail(f"static HTML still contains old English snippets: {denied_hits}")

    js_output_denied = [
        '"No backtest yet"',
        '"No comparison yet"',
        '"No walk-forward yet"',
        '"Paused"',
        '"Enabled"',
        'textContent = risk.emergency_stop ? "Guarded"',
        'textContent = risk.emergency_stop ? "Emergency stop"',
        '"No backtest trades"',
        '"No parameter results"',
        '"No walk-forward folds"',
    ]
    js_hits = [snippet for snippet in js_output_denied if snippet in app_js]
    if js_hits:
        return fail(f"app.js still contains old visible English output: {js_hits}")

    print(
        {
            "ok": True,
            "visible_text_count": len(parser.texts),
            "checked_files": [str(INDEX_PATH), str(APP_JS_PATH)],
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
