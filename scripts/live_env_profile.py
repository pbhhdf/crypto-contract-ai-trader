from __future__ import annotations

import argparse
import sys
from pathlib import Path



ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.live_env_profile import build_live_env_profile, dumps_report, merged_env  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit the server/live environment profile without printing secrets."
    )
    parser.add_argument(
        "--env-file",
        default=str(ROOT_DIR / ".env"),
        help="Environment file to inspect. File values override the current process by default.",
    )
    parser.add_argument(
        "--prefer-process-env",
        action="store_true",
        help="Let current process environment override values from --env-file.",
    )
    parser.add_argument(
        "--target",
        choices=["mvp_server", "testnet_validate", "testnet_place", "live_guarded"],
        default="live_guarded",
        help="Highest deployment stage to audit.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when the selected target has failing checks.",
    )
    args = parser.parse_args()

    env_file = Path(args.env_file).resolve()
    env = merged_env(env_file if env_file.exists() else None, prefer_process_env=args.prefer_process_env)
    source = f"env_file:{env_file}" if env_file.exists() else "process_env"
    report = build_live_env_profile(env, target=args.target, source=source)
    print(dumps_report(report))
    return 1 if args.strict and not report.get("ok") else 0


if __name__ == "__main__":
    raise SystemExit(main())
