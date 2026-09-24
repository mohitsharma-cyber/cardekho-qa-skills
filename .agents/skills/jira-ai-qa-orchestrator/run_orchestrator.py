"""
Unified Entry Point for Jira AI QA Orchestrator.
Supports CLI automation, Web UI server, and Skill integration.
"""

import argparse
import os
import sys

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure local package resolution
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from database.db_manager import DatabaseManager
from modules.execution.orchestrator import ExecutionStateMachine
from modules.jira.jira_client import JiraClient


def run_cli(ticket_key: str, env: str = "TESTING", target_server: str = None, mock_mode: bool = True):
    print(f"\n{'='*65}")
    print("🚀 JIRA AI QA ORCHESTRATOR - EXECUTION ENGINE")
    print(f"{'='*65}")
    print(f"Target Ticket: {ticket_key}")
    print(f"Environment:   {env}")
    if target_server:
        print(f"Target Server: {target_server}")
    print(f"Mode:          {'MOCK / DEMO' if mock_mode else 'LIVE PRODUCTION-SAFE'}")
    print(f"{'='*65}\n")

    db = DatabaseManager()
    state_machine = ExecutionStateMachine(db=db, mock_mode=mock_mode)

    result = state_machine.run_full_orchestration(ticket_key=ticket_key, environment=env, target_server=target_server)

    print(f"\n{'='*65}")
    print("📊 FINAL QA SIGN-OFF RESULT")
    print(f"{'='*65}")
    print(f"Execution ID:   {result['execution_id']}")
    print(f"Overall Result: {result['overall_status']}")
    print(f"Total Tests:    {result['metrics']['generated']}")
    print(f"Passed:         {result['metrics']['passed']}")
    print(f"Failed:         {result['metrics']['failed']}")
    print(f"Blocked:        {result['metrics']['blocked']}")
    print(f"{'='*65}")
    print("\n[JIRA REPORT MARKUP]:")
    print(result.get("jira_comment", ""))


def run_web(port: int = 8080):
    import uvicorn
    print(f"Starting Jira AI QA Orchestrator Web Dashboard at http://127.0.0.1:{port}...")
    from web_ui.app import app
    uvicorn.run(app, host="127.0.0.1", port=port)


def main():
    parser = argparse.ArgumentParser(description="Jira AI QA Orchestrator - Automated Test Planning & Execution")
    parser.add_argument("--ticket", help="Target Jira ticket key (e.g. CD-123, MB2C-1985, BDCV-5902)")
    parser.add_argument("--env", default="TESTING", choices=["TESTING", "STAGING"], help="Target test environment")
    parser.add_argument("--target-server", help="Specific deployment target server for branch (e.g. testingpwa2, testingpwa1, bikedekhotesting)")
    parser.add_argument("--live", action="store_true", help="Run in Live mode (connects to physical devices/Jira)")
    parser.add_argument("--mock", action="store_true", default=True, help="Run in Mock mode (default)")
    parser.add_argument("--web", action="store_true", help="Launch the Web QA Dashboard")
    parser.add_argument("--port", type=int, default=8080, help="Web Dashboard port")
    parser.add_argument("--list", action="store_true", help="List assigned Jira tickets")
    parser.add_argument("--approve-bugs", help="Approve and create proposed Testing Bugs in Jira for an execution ID")
    parser.add_argument("--chat-cmd", help="Execute natural language chat command (e.g. 'Show my Jira tickets', 'Test MB2C-1974')")

    args = parser.parse_args()

    mock_mode = not args.live

    if args.web:
        run_web(args.port)
    elif args.chat_cmd:
        from modules.execution.chat_orchestrator import ChatQAOrchestrator
        orchestrator = ChatQAOrchestrator(mock_mode=mock_mode)
        resp = orchestrator.handle_command(args.chat_cmd)
        print(resp)
    elif args.approve_bugs:
        db = DatabaseManager()
        state_machine = ExecutionStateMachine(db=db, mock_mode=mock_mode)
        res = state_machine.approve_and_create_bugs(args.approve_bugs)
        print(f"\n[APPROVAL RESULT]: {res}")
    elif args.list:
        from modules.execution.chat_orchestrator import ChatQAOrchestrator
        orchestrator = ChatQAOrchestrator(mock_mode=mock_mode)
        print(orchestrator.list_assigned_tickets())
    elif args.ticket:
        run_cli(args.ticket, env=args.env, target_server=args.target_server, mock_mode=mock_mode)
    else:
        # Default action: run demonstration ticket
        print("No ticket specified. Running default demonstration scenario on 'CD-145'...")
        run_cli("CD-145", env="TESTING", target_server=args.target_server, mock_mode=True)


if __name__ == "__main__":
    main()
