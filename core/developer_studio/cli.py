# ==============================================================================
# core/developer_studio/cli.py — Headless CLI Runner for Developer Studio Agent
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""Provides headless command-line execution for the Developer Studio agent,
enabling non-interactive CI automation and external project integration.

Usage:
    python -m core.developer_studio.cli --goal "Fix broken import in core/paths.py"
    python -m core.developer_studio.cli --goal "Analyze dependencies" --profile read_only
"""

import argparse
import json
import sys
import time
from pathlib import Path

from core.developer_studio.admin_agent import stream_admin_agent_turn
from core.developer_studio.tool_policy import ToolPolicy


def main() -> int:
    parser = argparse.ArgumentParser(description="Sigma Studio Developer Agent Headless CLI")
    parser.add_argument("--goal", "-g", required=True, help="Goal or instruction for the developer agent")
    parser.add_argument("--workspace", "-w", default=".", help="Workspace root directory")
    parser.add_argument("--provider", "-p", default=None, help="AI Provider (sigma_engine, openai, anthropic, etc.)")
    parser.add_argument("--model", "-m", default=None, help="Model name")
    parser.add_argument("--max-turns", "-t", type=int, default=25, help="Maximum number of turns")
    parser.add_argument("--profile", default="autonomous", choices=["autonomous", "read_only", "plan_only"],
                        help="Security and execution profile")
    parser.add_argument("--json", action="store_true", help="Output raw JSON events")
    args = parser.parse_args()

    workspace_path = str(Path(args.workspace).resolve())
    policy = ToolPolicy.for_profile(args.profile)
    allowed = list(policy.visible_tools()) if policy.restricted else None

    print(f"\033[96m[Sigma CLI]\033[0m Avvio agente su '{workspace_path}'")
    print(f"\033[96m[Sigma CLI]\033[0m Obiettivo: {args.goal}")
    print(f"\033[96m[Sigma CLI]\033[0m Profilo: {args.profile} | Provider: {args.provider or 'default'}\n")

    messages = [{"role": "user", "content": args.goal}]
    success = False
    turn_count = 0

    try:
        gen = stream_admin_agent_turn(
            messages=messages,
            workspace_root=workspace_path,
            provider=args.provider,
            model_name=args.model,
            max_turns=args.max_turns,
            allowed_tools=allowed,
            policy_label=policy.label,
        )

        for event in gen:
            e_type = event.get("type")

            if args.json:
                print(json.dumps(event, default=str))
                continue

            if e_type == "token":
                sys.stdout.write(event.get("token", ""))
                sys.stdout.flush()
            elif e_type == "thought":
                # Print reasoning in dim style
                sys.stdout.write(f"\033[90m{event.get('token', '')}\033[0m")
                sys.stdout.flush()
            elif e_type == "status":
                print(f"\n\033[93m[Status]\033[0m {event.get('text')}")
            elif e_type == "tool_call":
                print(f"\n\033[94m[Tool Call]\033[0m {event.get('tool')}: {json.dumps(event.get('params', {}))[:120]}")
            elif e_type == "tool_result":
                res = event.get("result", {})
                ok = res.get("success", False)
                sym = "\033[92m✔\033[0m" if ok else "\033[91m✖\033[0m"
                print(f"{sym} [Tool Result] {event.get('tool')}: {'OK' if ok else res.get('error', 'failed')[:100]}")
            elif e_type == "turn_end":
                turn_count += 1
            elif e_type == "complete" or (e_type == "done" and event.get("success")):
                success = True
            elif e_type == "error":
                print(f"\n\033[91m[Error]\033[0m {event.get('message') or event.get('error')}")

    except KeyboardInterrupt:
        print("\n\033[91m[Sigma CLI]\033[0m Interrotto dall'utente.")
        return 130
    except Exception as ex:
        print(f"\n\033[91m[Sigma CLI Fatal Error]\033[0m {ex}")
        return 1

    print(f"\n\n\033[96m[Sigma CLI]\033[0m Run completato in {turn_count} turni. Esito: {'\033[92mSUCCESSO\033[0m' if success else '\033[93mTERMINATO\033[0m'}")
    return 0 if success else 0


if __name__ == "__main__":
    sys.exit(main())
