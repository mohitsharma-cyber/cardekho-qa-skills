"""
Chat-Native AI QA Orchestrator for CarDekho and BikeDekho.
Provides 100% in-chat experience without any web dashboard or external app.
Handles natural commands, ticket selection, deployment gates, device coordination,
deterministic progress reporting, and human approval gates.
"""

import os
import re
import sys
import time
from typing import Any, Dict, List, Optional

from database.db_manager import DatabaseManager
from modules.execution.orchestrator import ExecutionStateMachine
from modules.jira.jira_client import JiraClient
from modules.deployment.jenkins_deployer import JenkinsDeployer
from modules.android.android_runner import AndroidRunner
from modules.environment.env_manager import EnvironmentManager


class ChatQAOrchestrator:
    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode
        self.db = DatabaseManager()
        self.jira = JiraClient(mock_mode=mock_mode)
        self.state_machine = ExecutionStateMachine(db=self.db, mock_mode=mock_mode)
        self.current_execution_id: Optional[str] = None
        self.last_result: Optional[Dict[str, Any]] = None
        self.pending_context: Optional[str] = None
        self.pending_ticket_key: Optional[str] = None
        self.pending_suggested_servers: List[str] = []

    def list_assigned_tickets(self, project: Optional[str] = None) -> str:
        """Fetches and formats assigned Jira tickets for chat display (Master Prompt Section 2 & 3)."""
        tickets = self.jira.get_assigned_tickets(project=project)
        if not tickets:
            return "No open Jira tickets are currently assigned to you."

        output = ["YOUR QA QUEUE — My Assigned Jira Tickets\n"]
        for i, t in enumerate(tickets, 1):
            key = t.get("key", "UNKNOWN")
            summary = t.get("summary", "")
            priority = t.get("priority", "Medium")
            status = t.get("status", "Open")
            issue_type = t.get("issue_type", "Task")

            # Determine brand
            sum_lower = summary.lower()
            if "[cd app]" in sum_lower or "cardekho" in sum_lower or key.startswith("DB2C"):
                brand = "CarDekho"
            elif "[bd app]" in sum_lower or "[zw app]" in sum_lower or "bikedekho" in sum_lower or key.startswith("BDCV"):
                brand = "BikeDekho"
            else:
                brand = "CarDekho"

            output.append(
                f"{i}. {key} — {summary}\n"
                f"   Type: {issue_type}\n"
                f"   Priority: {priority}\n"
                f"   Status: {status}\n"
                f"   Brand: {brand}\n"
            )

        output.append("👉 Which Jira ticket do you want to test? Select a ticket by typing its number (e.g. 1) or Jira ID (e.g. MB2C-1981).")
        return "\n".join(output)

    def run_ticket_testing(self, ticket_key: str, env: str = "TESTING",
                           target_server: Optional[str] = None,
                           deploy_choice: Optional[str] = None) -> Dict[str, Any]:
        """
        Runs the full chat-native orchestration lifecycle.
        Streams progress and formats deterministic results.
        """
        clean_key = ticket_key.strip().upper()
        print(f"\n[CHAT ORCHESTRATOR] Initiating QA testing for {clean_key} in {env}...")

        result = self.state_machine.run_full_orchestration(
            ticket_key=clean_key,
            environment=env,
            target_server=target_server,
            deploy_choice=deploy_choice
        )
        self.current_execution_id = result.get("execution_id")
        self.last_result = result
        return result

    def format_chat_report(self, result: Dict[str, Any]) -> str:
        """Formats orchestration result into clean, transparent markdown for chat adhering to Master Prompt."""
        status = result.get("overall_status", result.get("status", "UNKNOWN"))
        exec_id = result.get("execution_id", "")
        ticket_key = result.get("ticket_key", "")
        env = result.get("environment", "TESTING")
        metrics = result.get("metrics", {})

        # 0. Brand Identification Gate (Section 7)
        if status == "PROJECT_IDENTIFICATION_REQUIRED":
            self.pending_context = "PROJECT_IDENTIFICATION_REQUIRED"
            self.pending_ticket_key = ticket_key
            return (
                f"### 🛑 PROJECT IDENTIFICATION REQUIRED\n\n"
                f"Could not safely determine whether ticket `{ticket_key}` belongs to **CarDekho** or **BikeDekho**.\n\n"
                f"Please reply with the brand:\n"
                f"1. `CarDekho`\n"
                f"2. `BikeDekho`"
            )

        # 1. Step Validation Gate Interception (Clarification / Requirement Error / Blocked)
        if status in ["CLARIFICATION_REQUIRED", "REQUIREMENT_ERROR"]:
            step_val = result.get("step_validation", {})
            prob_step = step_val.get("problematic_step", {})
            issues = step_val.get("issues", [])
            affected = step_val.get("dependent_steps_affected", [])
            return (
                f"========================================================\n"
                f"JIRA STEP VALIDATION FAILED\n"
                f"========================================================\n"
                f"Jira:\n{ticket_key}\n\n"
                f"Step:\n{prob_step.get('action', 'N/A')}\n\n"
                f"Problem:\n" + "\n".join([f"- {iss}" for iss in issues]) + "\n\n"
                f"Expected State:\nMeasurable assertion criteria\n\n"
                f"Actual/Available State:\nAmbiguous or invalid step instruction\n\n"
                f"Dependent Steps:\n{affected if affected else 'None'}\n\n"
                f"Classification:\n{status}\n"
                f"========================================================\n\n"
                f"👉 Options:\n"
                f"1. Correct Jira ticket instructions and run `Test {ticket_key}` again.\n"
                f"2. Allow AI to reconstruct the test flow.\n"
                f"3. Stop testing."
            )

        # 2. Deployment Server Selection Gate (Section 10)
        if status == "WAITING_FOR_SERVER":
            self.pending_context = "WAITING_FOR_SERVER"
            self.pending_ticket_key = ticket_key
            servers = result.get("suggested_servers", ["testingapi2", "testingapi3"])
            self.pending_suggested_servers = servers
            server_options = "\n".join([f"   {i}. `{s}`" for i, s in enumerate(servers, 1)])
            return (
                f"### 🌿 Branch Detected: `{result.get('branch', 'N/A')}` (`{ticket_key}`)\n\n"
                f"Deployment is required for this Jira: `{ticket_key}`\n\n"
                f"**Kya ye branch already deploy hai ya Jenkins se deploy karni hai?**\n\n"
                f"1. 🚀 **Deploy via Jenkins** (Jenkins par build trigger karke test server par deploy karega)\n"
                f"2. ⚡ **Already Deployed** (Branch test server par pehle se deploy hai, direct testing shuru karega)\n\n"
                f"**Available Target Servers:**\n"
                f"{server_options}\n\n"
                f"👉 **Aap inme se koi bhi reply kar sakte hain:**\n"
                f"• `Deploy on testingapi2` (ya `Deploy 1`) ➔ Jenkins build trigger karega\n"
                f"• `Already deployed on testingapi2` (ya `Already 1`) ➔ Direct target server verify karke test karega\n"
                f"• Ya simply server number/naam reply karein (`1` ya `testingapi2`) ➔ Jenkins deploy trigger karega"
            )

        # 3. One QA Session Authorization Gate (Section 24)
        if status == "WAITING_FOR_SESSION_AUTHORIZATION":
            device = result.get("device", {})
            dev_model = device.get("model", "Android Device") if device else "Android Device"
            dev_serial = device.get("serial", "Connected Device") if device else "Connected Device"
            plan = result.get("plan", {})
            tc_count = len(plan.get("test_cases", [])) if plan else 4
            return (
                f"QA SESSION READY\n\n"
                f"Jira:\n{ticket_key}\n\n"
                f"Environment:\n{env}\n\n"
                f"Device:\n{dev_model} ({dev_serial})\n\n"
                f"Test Cases:\n{tc_count}\n\n"
                f"Normal QA actions:\n"
                f"Tap\n"
                f"Scroll\n"
                f"Swipe\n"
                f"Back\n"
                f"Type\n"
                f"Navigate\n"
                f"Screenshot\n\n"
                f"[START QA SESSION]\n\n"
                f"👉 To start autonomous execution, reply: `Allow QA session` or `Authorize session`."
            )

        # 4. If execution output contains master_report (Section 44)
        output_parts = []
        if result.get("master_report"):
            output_parts.append(result.get("master_report"))

        # Proposed bugs gate (Section 46 & 47)
        proposed_bugs = result.get("proposed_bugs", [])
        if proposed_bugs:
            output_parts.append("\n" + "="*60 + "\n")
            for bug in proposed_bugs:
                if bug.get("potential_duplicate"):
                    output_parts.append(f"⚠️ Possible Existing Bug Found: {bug.get('duplicate_matches')}\n")
                output_parts.append(bug.get("master_draft", QAReporter.format_master_bug_draft(bug)))
                output_parts.append("\n" + "-"*40 + "\n")

            output_parts.append(
                "👉 To approve and create bug in Jira, reply: `Approve bug`\n"
                "👉 To reject or link existing, reply: `Cancel bug`"
            )

        # QA Sign-off (Section 45)
        elif status == "PASSED" and result.get("master_signoff"):
            output_parts.append("\n" + "="*60 + "\n")
            output_parts.append(result.get("master_signoff"))

        return "\n".join(output_parts) if output_parts else f"QA Result: {status}"

    def handle_command(self, user_msg: str) -> str:
        """Dispatches natural chat commands adhering to Master Prompt."""
        raw_msg = user_msg.strip()
        msg = raw_msg.lower()

        # 1. Refresh Jira Queue (Section 4)
        if msg in ["refresh jira", "refresh queue", "refresh tickets"]:
            self.jira.refresh_queue()
            return "🔄 **Jira queue refreshed.**\n\n" + self.list_assigned_tickets()

        # 2. List / Start Jira Queue (Section 2 & 3)
        if any(cmd in msg for cmd in ["show my jira tickets", "start jira qa", "show my qa tickets", "start jira testing", "qa queue", "start qa", "list tickets"]):
            return self.list_assigned_tickets()

        # 3. Interactive Server Selection Response (Section 10)
        if self.pending_context == "WAITING_FOR_SERVER" and self.pending_ticket_key:
            deploy_choice = "deploy"  # default
            if any(w in msg for w in ["already", "pehle se", "deployed", "already_deployed"]):
                deploy_choice = "already_deployed"
            elif any(w in msg for w in ["deploy", "karni hai", "jenkins", "trigger"]):
                deploy_choice = "deploy"

            target_server = None
            server_match = re.search(r'\b(testingapi\d*|testingpwa\d*|staging)\b', msg)
            if server_match:
                target_server = server_match.group(1)
            elif raw_msg.isdigit():
                idx = int(raw_msg)
                if 1 <= idx <= len(self.pending_suggested_servers):
                    target_server = self.pending_suggested_servers[idx - 1]
            else:
                num_match = re.search(r'\b([1-9])\b', raw_msg)
                if num_match:
                    idx = int(num_match.group(1))
                    if 1 <= idx <= len(self.pending_suggested_servers):
                        target_server = self.pending_suggested_servers[idx - 1]

            if target_server:
                t_key = self.pending_ticket_key
                self.pending_context = None
                self.pending_ticket_key = None
                self.pending_suggested_servers = []
                res = self.run_ticket_testing(t_key, target_server=target_server, deploy_choice=deploy_choice)
                return self.format_chat_report(res)

        # 4. Interactive Brand Selection Response (Section 7)
        if self.pending_context == "PROJECT_IDENTIFICATION_REQUIRED" and self.pending_ticket_key:
            selected_brand = "BIKEDEKHO" if "bike" in msg or msg == "2" else ("CARDEKHO" if "car" in msg or msg == "1" else None)
            if selected_brand:
                t_key = self.pending_ticket_key
                self.pending_context = None
                self.pending_ticket_key = None
                res = self.run_ticket_testing(t_key)
                return self.format_chat_report(res)

        # 5. One QA Session Authorization (Section 24)
        if any(cmd in msg for cmd in ["allow qa session", "authorize session", "allow session", "approve session", "start qa session", "start session"]):
            if not self.current_execution_id:
                return "⚠️ No active QA execution waiting for session authorization."
            res = self.state_machine.authorize_qa_session(self.current_execution_id)
            return f"✅ **{res.get('message')}**\nProceeding with autonomous QA interaction on device."

        # 6. Stop / Pause Testing (Section 39)
        if any(cmd in msg for cmd in ["stop testing", "stop", "halt testing", "pause testing", "pause"]):
            self.state_machine.stop_execution()
            return "🛑 **Testing safely halted.** Execution state, completed tests, and evidence have been preserved."

        # 7. Resume Testing (Section 39)
        if any(cmd in msg for cmd in ["resume testing", "resume"]):
            self.state_machine.resume_execution()
            return "▶️ **Resuming testing** from the last safe checkpoint."

        # 8. Approve Bug (Section 46)
        if any(cmd in msg for cmd in ["approve bug", "create bug", "approve and create", "approve bugs", "approve & create bug"]):
            if not self.current_execution_id:
                return "⚠️ No active execution with proposed bugs found to approve."
            res = self.state_machine.approve_and_create_bugs(self.current_execution_id)
            if res.get("status") == "SUCCESS":
                created = res.get("created_bugs", [])
                lines = ["✅ **Testing Bug(s) successfully created in Jira:**\n"]
                for b in created:
                    lines.append(f"• **[{b['bug_key']}]** {b['summary']} (Linked to `{b['parent_task']}` via `Relates`)")
                return "\n".join(lines)
            return f"⚠️ Error creating bugs: {res.get('message')}"

        # 9. Cancel Bug
        if any(cmd in msg for cmd in ["cancel bug", "reject bug", "skip bug"]):
            return "🚫 **Testing Bug creation cancelled by user.** Defect was not logged to Jira."

        # 10. Post QA Sign-off (Section 45)
        if any(cmd in msg for cmd in ["post qa sign-off", "post sign-off", "post qa sign-off to jira", "update jira"]):
            if not self.last_result:
                return "⚠️ No completed test execution found to post sign-off."
            ticket_key = self.last_result.get("ticket_key")
            comment = self.last_result.get("jira_comment", "")
            ok = self.jira.add_comment(ticket_key, comment)
            if ok:
                return f"✅ **QA Sign-off comment successfully posted to Jira ticket `{ticket_key}`!**"
            return f"⚠️ Failed to post QA comment to Jira ticket `{ticket_key}`."

        # 11. Selection by Number (e.g., "1", "2") from Queue (Section 2)
        if raw_msg.isdigit():
            t = self.jira.get_ticket_from_queue(raw_msg)
            if t:
                key = t.get("key")
                summary = t.get("summary")
                print(f"\nSelected Jira:\n{key} — {summary}")
                res = self.run_ticket_testing(key)
                return f"Selected Jira:\n{key} — {summary}\n\n" + self.format_chat_report(res)

        # 12. Multiple Selection (e.g. "1, 2" or "MB2C-1974, MB2C-1981") (Section 5)
        if "," in raw_msg:
            parts = [p.strip() for p in raw_msg.split(",") if p.strip()]
            resolved_keys = []
            for p in parts:
                if p.isdigit():
                    t = self.jira.get_ticket_from_queue(p)
                    if t:
                        resolved_keys.append(t.get("key"))
                elif re.match(r'^[A-Z0-9]{2,8}-\d+$', p, re.IGNORECASE):
                    resolved_keys.append(p.upper())

            if len(resolved_keys) > 1:
                results_output = [f"**Processing {len(resolved_keys)} selected Jira tickets independently:**\n"]
                for k in resolved_keys:
                    results_output.append(f"\n{'='*50}\n**Executing Ticket {k}**\n{'='*50}")
                    r = self.run_ticket_testing(k)
                    results_output.append(self.format_chat_report(r))
                return "\n".join(results_output)

        # 13. Specific Ticket Key (e.g., "Test MB2C-1974" or "MB2C-1974", tolerant to MB@C typo)
        norm_key_msg = re.sub(r'MB@C', 'MB2C', user_msg, flags=re.IGNORECASE)
        ticket_match = re.search(r'\b([A-Z0-9]{2,8}-\d+)\b', norm_key_msg, re.IGNORECASE)
        if ticket_match:
            ticket_key = ticket_match.group(1).upper()
            server_match = re.search(r'\b(testingapi\d*|testingpwa\d*|staging)\b', msg)
            target_server = server_match.group(1) if server_match else None

            res = self.run_ticket_testing(ticket_key, target_server=target_server)
            return self.format_chat_report(res)

        # 14. Default Help
        return (
            "Available Chat QA Commands:\n"
            "• `Start QA` or `Show my Jira tickets` (Lists assigned QA queue)\n"
            "• `1` / `2` or `Test <TICKET-ID>` (Selects and analyzes ticket)\n"
            "• `Refresh Jira` (Re-fetches fresh tickets from Jira)\n"
            "• `Allow QA session` (Grants 1-time session authorization for Android QA interactions)\n"
            "• `Approve bug` (Creates proposed defect in Jira & links to parent via `Relates`)\n"
            "• `Post QA sign-off` (Comments sign-off on Jira ticket)\n"
            "• `Stop testing` / `Resume`"
        )

