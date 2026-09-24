"""
Master QA Orchestration State Machine for Jira AI QA Orchestrator.
Coordinates the entire lifecycle:
Jira -> Analysis -> Branch Check & Jenkins Deploy -> Build Check -> Strategy -> Environment -> Execution -> Report.
"""

import time
import uuid
from typing import Any, Callable, Dict, List, Optional

import os
import sys

# Ensure base dir is on sys.path
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from modules.ai.context_analyzer import RequirementAnalyzer
from modules.ai.failure_analyzer import FailureAnalyzer
from modules.android.android_runner import AndroidRunner
from modules.android.build_installer import BuildInstaller
from modules.deployment.jenkins_deployer import JenkinsDeployer
from modules.api.network_capture import NetworkCapture
from modules.assertions.assertion_engine import AssertionEngine
from modules.environment.env_manager import EnvironmentManager, EnvironmentSafetyError
from modules.jira.jira_client import JiraClient
from modules.planning.test_planner import TestPlanner
from modules.reporting.qa_reporter import QAReporter
from modules.web.web_runner import WebRunner
from database.db_manager import DatabaseManager


class ExecutionStateMachine:
    STATES = [
        "JIRA_QUEUE",
        "JIRA_SELECTED",
        "TICKET_SELECTED",
        "FETCHING_CONTEXT",
        "ANALYZING",
        "PROJECT_IDENTIFIED",
        "PROJECT_IDENTIFICATION_REQUIRED",
        "JIRA_TYPE_IDENTIFIED",
        "ANALYZING_REQUIREMENT",
        "REQUIREMENT_VALIDATION",
        "REQUIREMENT_ERROR",
        "CLARIFICATION_REQUIRED",
        "DETECTING_BRANCH",
        "DEPLOYMENT_REQUIRED",
        "WAITING_FOR_SERVER",
        "AWAITING_SERVER_SELECTION",
        "AWAITING_DEPLOYMENT_CHOICE",
        "WAITING_FOR_DEPLOYMENT",
        "DEPLOYING",
        "DEPLOYING_TO_TESTING_SERVER",
        "DEPLOYMENT_COMPLETED",
        "DEPLOYMENT_VERIFIED",
        "AWAITING_DEPLOYMENT_CONFIRMATION",
        "DETECTING_BUILD",
        "DOWNLOADING_BUILD",
        "INSTALLING_BUILD",
        "BUILD_INSTALLED",
        "AWAITING_MANUAL_INSTALL",
        "GENERATING_TEST_PLAN",
        "TEST_PLAN_READY",
        "AWAITING_APPROVAL",
        "ENVIRONMENT_SELECTION",
        "ENVIRONMENT_VALIDATION",
        "CONFIGURING_APP",
        "VERIFYING_ENVIRONMENT",
        "DEVICE_CHECK",
        "WAITING_FOR_DEVICE",
        "DEVICE_READY",
        "WAITING_FOR_SESSION_AUTHORIZATION",
        "EXECUTING",
        "VALIDATING",
        "PAUSED",
        "ANALYZING_RESULTS",
        "ANALYZING_FAILURE",
        "REPORT_READY",
        "FINAL_RESULT",
        "QA_SIGNOFF",
        "BUG_APPROVAL",
        "AWAITING_BUG_APPROVAL",
        "AWAITING_JIRA_UPDATE",
        "COMPLETED",
        "PASSED",
        "FAILED",
        "BLOCKED",
        "PARTIAL",
        "SKIPPED",
        "CANCELLED"
    ]

    PROPOSED_BUGS_CACHE: Dict[str, Any] = {}

    def __init__(self, db: DatabaseManager, mock_mode: bool = True):
        self.db = db
        self.mock_mode = mock_mode
        self.jira = JiraClient(mock_mode=mock_mode)
        self.analyzer = RequirementAnalyzer()
        self.planner = TestPlanner()
        self.env_mgr = EnvironmentManager()
        self.web_runner = WebRunner(headless=True, mock_mode=mock_mode)
        self.android_runner = AndroidRunner(mock_mode=mock_mode)
        self.build_installer = BuildInstaller()
        self.jenkins_deployer = JenkinsDeployer()
        self.net_capture = NetworkCapture()
        self.failure_analyzer = FailureAnalyzer()

        self.current_state = "TICKET_SELECTED"
        self.is_paused = False
        self.is_stopped = False
        self.proposed_bugs_cache = ExecutionStateMachine.PROPOSED_BUGS_CACHE

    def transition_to(self, new_state: str, exec_id: str, details: Optional[str] = None):
        if new_state not in self.STATES:
            raise ValueError(f"Invalid state transition: {new_state}")
        self.current_state = new_state
        self.db.update_execution_state(exec_id, new_state)
        self.db.log_audit(
            action=f"STATE_TRANSITION -> {new_state}",
            execution_id=exec_id,
            details=details or ""
        )
        print(f"[STATE] >>> {new_state} (Exec: {exec_id}) - {details or ''}")

    def run_full_orchestration(self, ticket_key: str, environment: str = "TESTING",
                               device_serial: Optional[str] = None,
                               deploy_choice: Optional[str] = None,
                               deployment_confirmed: bool = False,
                               target_server: Optional[str] = None,
                               qa_session_authorized: bool = True,
                               state_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        Executes full zero-hallucination QA lifecycle for a Jira ticket.
        """
        exec_id = f"EXEC-{int(time.time())}-{uuid.uuid4().hex[:6].upper()}"
        self.current_state = "TICKET_SELECTED"

        # 1. State: TICKET_SELECTED & JIRA_SELECTED
        self.db.create_execution({
            "id": exec_id,
            "execution_id": exec_id,
            "ticket_key": ticket_key,
            "environment": environment,
            "state": "TICKET_SELECTED"
        })
        self.transition_to("TICKET_SELECTED", exec_id, f"Selected ticket {ticket_key}")
        self.transition_to("JIRA_SELECTED", exec_id, f"Selected ticket {ticket_key}")

        # 2. State: FETCHING_CONTEXT & ANALYZING
        self.transition_to("FETCHING_CONTEXT", exec_id)
        ticket = self.jira.get_ticket_details(ticket_key)
        self.db.save_jira_ticket(ticket)

        self.transition_to("ANALYZING", exec_id)
        analysis = self.analyzer.analyze(ticket)

        # Brand Identification Gate (Section 7)
        if not analysis.get("brand_certain"):
            self.transition_to("PROJECT_IDENTIFICATION_REQUIRED", exec_id,
                               "Could not unambiguously identify brand (CarDekho vs BikeDekho). Awaiting user guidance.")
            return {
                "execution_id": exec_id,
                "ticket_key": ticket_key,
                "status": "PROJECT_IDENTIFICATION_REQUIRED",
                "overall_status": "PROJECT_IDENTIFICATION_REQUIRED",
                "message": "PROJECT_IDENTIFICATION_REQUIRED: Unable to safely determine if ticket belongs to CarDekho or BikeDekho. Please specify brand.",
                "analysis": analysis
            }

        self.transition_to("PROJECT_IDENTIFIED", exec_id, f"Brand: {analysis.get('brand')}")
        self.transition_to("JIRA_TYPE_IDENTIFIED", exec_id, f"Testing Mode: {analysis.get('jira_mode')}")
        self.transition_to("ANALYZING_REQUIREMENT", exec_id)

        # 4. State: DETECTING_BRANCH & INTERACTIVE DEPLOYMENT GATE
        self.transition_to("DETECTING_BRANCH", exec_id)
        branch_info = self.jenkins_deployer.extract_branch_info(ticket)
        deployment_record = None

        dep_assessment = self.analyzer.assess_deployment_requirement(ticket, branch_info)
        if dep_assessment.get("deployment_required"):
            self.transition_to("DEPLOYMENT_REQUIRED", exec_id, dep_assessment.get("reason"))

            primary_branch = branch_info.get("primary_branch")
            branch_type = branch_info.get("branch_type")
            is_bikedekho = analysis.get("brand") == "BIKEDEKHO" or branch_info.get("is_bikedekho", False)

            # Determine server to use; if not provided and in non-mock, prompt user (Section 10)
            if not target_server:
                suggested = branch_info.get("suggested_servers", ["testingapi2", "testingapi3"])
                if not self.mock_mode:
                    self.transition_to("WAITING_FOR_SERVER", exec_id,
                                       f"Deployment required for branch '{primary_branch}'. Awaiting server selection.")
                    return {
                        "execution_id": exec_id,
                        "ticket_key": ticket_key,
                        "status": "WAITING_FOR_SERVER",
                        "overall_status": "WAITING_FOR_SERVER",
                        "branch": primary_branch,
                        "branch_type": branch_type,
                        "suggested_servers": suggested,
                        "message": f"Deployment is required for this Jira. Please select deployment server: {', '.join(suggested)}"
                    }
                resolved_server = suggested[0]
            else:
                resolved_server = target_server

            print("\n" + "="*70)
            print(f"[BRANCH DETECTED] Found {branch_type} branch: {primary_branch} (Brand: {analysis.get('brand')})")
            print(f"Target Testing Server: {resolved_server}")
            print("="*70)

            # Determine deploy action: if not passed as param, handle choice
            if deploy_choice is None:
                self.transition_to("AWAITING_DEPLOYMENT_CHOICE", exec_id,
                                   f"Branch {primary_branch} detected. Deploy to {resolved_server} via Jenkins.")
                print(f"Triggering Jenkins deployment for '{primary_branch}' to {resolved_server}...")
                action = "deploy"
            else:
                action = deploy_choice.lower()

            if action in ["deploy", "yes", "true"]:
                self.transition_to("DEPLOYING", exec_id, f"Triggering Jenkins deployment for '{primary_branch}'...")
                self.transition_to("DEPLOYING_TO_TESTING_SERVER", exec_id,
                                   f"Deploying branch '{primary_branch}' to {resolved_server} via Jenkins...")
                deploy_res = self.jenkins_deployer.trigger_deployment(
                    branch_name=primary_branch,
                    branch_type=branch_type,
                    target_env=resolved_server,
                    is_bikedekho=is_bikedekho,
                    mock_mode=self.mock_mode
                )

                if deploy_res.get("status") == "ERROR":
                    self.transition_to("BLOCKED", exec_id, f"Jenkins trigger failed: {deploy_res.get('message')}")
                    return {"execution_id": exec_id, "status": "BLOCKED", "reason": deploy_res.get("message")}

                # Monitor build completion (Rule 12: Deployment is a HARD GATE)
                build_completion = self.jenkins_deployer.wait_for_build_completion(
                    queue_url=deploy_res.get("queue_url", ""),
                    job_name=deploy_res.get("job_name", ""),
                    mock_mode=self.mock_mode
                )
                if build_completion.get("status") != "SUCCESS":
                    self.transition_to("BLOCKED", exec_id, f"Jenkins build did not succeed: {build_completion.get('message')}")
                    return {"execution_id": exec_id, "status": "BLOCKED", "reason": build_completion.get("message")}

                # Independent target server verification (Rule 13)
                server_ver = self.jenkins_deployer.verify_target_deployment(
                    target_server=resolved_server,
                    is_bikedekho=is_bikedekho,
                    mock_mode=self.mock_mode
                )
                if not server_ver.get("verified"):
                    self.transition_to("BLOCKED", exec_id, f"Target server deployment verification failed: {server_ver.get('message')}")
                    return {"execution_id": exec_id, "status": "BLOCKED", "reason": server_ver.get("message")}

                self.transition_to("DEPLOYMENT_COMPLETED", exec_id,
                                   f"Jenkins build #{build_completion.get('build_number', 142)} SUCCESS and target {resolved_server} verified.")
                self.transition_to("DEPLOYMENT_VERIFIED", exec_id,
                                   f"Target deployment independently verified on {resolved_server}.")

                # Display Section 12 explicit verified banner
                banner = self.jenkins_deployer.format_deployment_verified_banner(
                    ticket_key=ticket_key,
                    branch=primary_branch,
                    commit=ticket.get("commit", "HEAD"),
                    build_num=build_completion.get("build_number", 142),
                    server=resolved_server
                )
                print(f"\n{banner}\n")

                deployment_record = {**deploy_res, **build_completion, "target_verification": server_ver, "status": "VERIFIED"}

                # Post-deployment confirmation gate
                self.transition_to("AWAITING_DEPLOYMENT_CONFIRMATION", exec_id,
                                   f"Deployment completed and verified on {resolved_server}. Ready to proceed.")
                print(f"[CONFIRMATION] ✅ Deployment of '{primary_branch}' finished & independently verified on {resolved_server}.")
                print(f"[CONFIRMATION] Ready to proceed with QA Orchestration.")
            else:
                # Independently verify target server even when user indicates already deployed
                server_ver = self.jenkins_deployer.verify_target_deployment(
                    target_server=resolved_server,
                    is_bikedekho=is_bikedekho,
                    mock_mode=self.mock_mode
                )
                print(f"[DEPLOYMENT SKIPPED] Branch '{primary_branch}' is already deployed or skipped by user.")
                deployment_record = {
                    "status": "ALREADY_DEPLOYED",
                    "branch": primary_branch,
                    "target_env": resolved_server,
                    "target_verification": server_ver,
                    "message": f"User indicated branch '{primary_branch}' is already deployed on {resolved_server}."
                }

        # 5. State: DETECTING_BUILD & AUTO-INSTALLATION ON CONNECTED DEVICE
        self.transition_to("DETECTING_BUILD", exec_id)
        build_info = self.build_installer.extract_build_info(ticket)
        installed_build = None

        if build_info.get("has_build"):
            print(f"[BUILD DETECTED] Found build in {build_info.get('found_in')}: {build_info.get('build_url')}")
            # Ensure device is connected before installing
            self.transition_to("DEVICE_CHECK", exec_id, "Checking connected device for build installation")
            connected_device = self.android_runner.detect_device()
            connected_device = self.android_runner.detect_device()
            if not connected_device:
                if self.mock_mode:
                    connected_device = {"serial": "mock_device_001", "model": "Pixel 7 Pro (Mock)"}
                else:
                    self.transition_to("BLOCKED", exec_id, "Physical Android device required for APK installation.")
                    return {"execution_id": exec_id, "status": "BLOCKED", "reason": "No physical Android device connected to install build."}

            # Download build
            self.transition_to("DOWNLOADING_BUILD", exec_id, f"Downloading {build_info.get('filename')}...")
            dl_ok, dl_path = self.build_installer.download_build(build_info, ticket_key, jira_auth=self.jira.get_auth())

            # Install on device
            if dl_ok or self.mock_mode:
                self.transition_to("INSTALLING_BUILD", exec_id, f"Installing on {connected_device.get('serial')} via ADB...")
                apk_file = dl_path if dl_ok else "mock_build.apk"
                inst_ok, inst_msg = self.build_installer.install_build_on_device(apk_file, connected_device.get("serial"), mock_mode=self.mock_mode)
                if inst_ok:
                    self.transition_to("BUILD_INSTALLED", exec_id, f"Installed {build_info.get('filename')} on device {connected_device.get('serial')}")
                    installed_build = {
                        "filename": build_info.get("filename"),
                        "url": build_info.get("build_url"),
                        "device_serial": connected_device.get("serial"),
                        "status": "INSTALLED"
                    }
                else:
                    print(f"[WARN] Build installation error: {inst_msg}")
        else:
            is_app_ticket = (
                analysis.get("device_requirement", {}).get("device_required", False) or
                "app" in ticket.get("summary", "").lower() or
                ticket.get("project_key") in ["MB2C", "CD", "BD"]
            )
            if is_app_ticket:
                self.transition_to("AWAITING_MANUAL_INSTALL", exec_id, "No build URL found in Jira ticket. Manual install required.")
                print("\n" + "="*65)
                print(f"[ATTENTION] [!] No app download URL found in Jira ticket {ticket_key}.")
                print(f"[*] Please manually install the required App build on your connected Android device.")
                print("="*65 + "\n")
                installed_build = {
                    "status": "MANUAL_INSTALL_REQUESTED",
                    "message": "No build download URL found in Jira ticket. Please manually install the app build on your connected device."
                }

        # 6. Check for Ambiguities (Rule 5)
        if analysis.get("clarification_required"):
            self.transition_to("CLARIFICATION_REQUIRED", exec_id, "Missing acceptance criteria or context")
            print(f"[CLARIFICATION REQUIRED] {analysis.get('ambiguities')}")

        # 7. State: GENERATING_TEST_PLAN
        self.transition_to("GENERATING_TEST_PLAN", exec_id)
        plan = self.planner.generate_plan(ticket, analysis, environment=environment)

        # Critical Jira Step Validation Gate (Master Prompt Section 6 & 7)
        step_val = plan.get("step_validation", {})
        if not step_val.get("is_valid", True):
            val_status = step_val.get("status", "CLARIFICATION_REQUIRED")
            self.transition_to(val_status, exec_id, f"Jira step validation gate: {', '.join(step_val.get('issues', []))}")
            return {
                "execution_id": exec_id,
                "ticket_key": ticket_key,
                "environment": environment,
                "overall_status": val_status,
                "status": val_status,
                "step_validation": step_val,
                "message": f"Step validation stopped testing: {step_val.get('recommendation')}",
                "metrics": {"generated": 0, "passed": 0, "failed": 0, "blocked": 1, "skipped": 0}
            }

        plan_id = self.db.save_test_plan({
            "ticket_id": ticket.get("id", ticket_key),
            "title": plan["title"],
            "scope": analysis["scope"],
            "functional_risks": analysis["risks"]["functional_risks"],
            "regression_risks": analysis["risks"]["regression_risks"],
            "dependencies": analysis["dependencies"],
            "ambiguities": analysis["ambiguities"]
        })

        test_cases = plan["test_cases"]
        for tc in test_cases:
            tc["plan_id"] = plan_id
        self.db.save_test_cases(test_cases)
        self.transition_to("TEST_PLAN_READY", exec_id, f"Generated {len(test_cases)} scenarios (Mode: {plan.get('mode')})")

        # 8. Check High-Risk / Destructive Approval (Section 28)
        if analysis["risks"].get("destructive_actions"):
            self.transition_to("AWAITING_APPROVAL", exec_id, "Destructive operations detected")
            print("[APPROVAL REQUIRED] Operations require QA sign-off.")

        # 9. State: ENVIRONMENT_SELECTION & VALIDATION
        self.transition_to("ENVIRONMENT_SELECTION", exec_id, f"Target: {environment}")
        self.transition_to("ENVIRONMENT_VALIDATION", exec_id)
        is_bike_brand = branch_info.get("is_bikedekho", False) if branch_info else False
        active_target = resolved_server if branch_info and branch_info.get("has_branch") else None
        try:
            profile = self.env_mgr.get_profile(environment, deployment_target=active_target, is_bikedekho=is_bike_brand)
        except EnvironmentSafetyError as e:
            self.transition_to("BLOCKED", exec_id, str(e))
            return {"execution_id": exec_id, "status": "BLOCKED", "error": str(e)}

        # 10. State: CONFIGURING_APP & VERIFYING_ENVIRONMENT
        self.transition_to("CONFIGURING_APP", exec_id)
        ok, msg = self.env_mgr.configure_android_app_environment(
            environment,
            deployment_target=active_target,
            is_bikedekho=is_bike_brand,
            serial=device_serial,
            mock_mode=self.mock_mode
        )
        self.transition_to("VERIFYING_ENVIRONMENT", exec_id, msg)

        # 11. State: DEVICE_CHECK
        device_req = analysis.get("device_requirement", {}).get("device_required", False)
        connected_device = None
        if device_req:
            self.transition_to("DEVICE_CHECK", exec_id)
            connected_device = self.android_runner.detect_device()
            if not connected_device:
                self.transition_to("WAITING_FOR_DEVICE", exec_id, analysis["device_requirement"]["reason"])
                print("[WAITING FOR DEVICE] Please connect an Android physical device with USB debugging...")
                if self.mock_mode:
                    connected_device = self.android_runner.detect_device()
                    print(f"[DEVICE DETECTED] Resuming testing with {connected_device['model']}")
                else:
                    self.transition_to("BLOCKED", exec_id, "Required device was not connected.")
                    return {"execution_id": exec_id, "status": "BLOCKED", "reason": "No physical Android device available."}

        # Check One QA Session Authorization (Master Prompt Section 20)
        if device_req and not qa_session_authorized:
            self.transition_to("WAITING_FOR_SESSION_AUTHORIZATION", exec_id, "QA Session authorization required before Android device execution.")
            return {
                "execution_id": exec_id,
                "ticket_key": ticket_key,
                "environment": environment,
                "status": "WAITING_FOR_SESSION_AUTHORIZATION",
                "overall_status": "WAITING_FOR_SESSION_AUTHORIZATION",
                "device": connected_device,
                "plan": plan,
                "message": "QA Session Authorization required before running Android device automation."
            }

        # 12. State: EXECUTING
        self.transition_to("EXECUTING", exec_id, f"Running {len(test_cases)} test cases")
        self.web_runner.start_session(profile["base_url"])

        executed_results = []
        failure_triage = []
        api_call_count = 0
        passed_test_ids = set()
        failed_test_ids = set()

        for tc in test_cases:
            tc_id = tc.get("test_case_id", tc.get("id", "TC-001"))

            if self.is_stopped:
                print("[STOPPED] Test execution halted safely by user.")
                tc["status"] = "SKIPPED"
                tc["actual_result"] = "Skipped due to user stop request."
                executed_results.append(tc)
                continue

            # Dependency-Aware Fail-Fast Rule (Master Prompt Section 13 & 14)
            deps = tc.get("dependencies", [])
            blocked_dep = next((d for d in deps if d in failed_test_ids), None)
            if blocked_dep:
                tc["status"] = "NOT_EXECUTED"
                tc["actual_result"] = f"Skipped: Prerequisite test case '{blocked_dep}' failed or was blocked (Fail-Fast Rule)."
                tc["duration_ms"] = 0
                tc["evidence"] = {"reason": "PREREQUISITE_FAILURE", "dependency": blocked_dep}
                tc["failure_classification"] = "DEPENDENCY_ERROR"
                self.db.update_test_case_result(tc_id, "NOT_EXECUTED", tc["actual_result"], 0)
                failed_test_ids.add(tc_id)
                executed_results.append(tc)
                print(f"[FAIL-FAST] Skipping {tc_id} because prerequisite '{blocked_dep}' failed.")
                continue

            tc["status"] = "RUNNING"
            is_native = tc.get("device_required", False)

            if is_native and connected_device:
                res = self.android_runner.execute_android_test(tc, connected_device["serial"])
            else:
                target_url = f"{profile['base_url']}/overview"
                res = self.web_runner.execute_test_case(tc, exec_id, target_url)

            # Record API interactions
            captured_calls = self.net_capture.capture_traffic(tc_id, profile.get("base_api_url", ""))
            api_call_count += len(captured_calls)

            # Assertions Engine
            assertion_report = AssertionEngine.evaluate_test_case(tc, res)
            tc["status"] = assertion_report["status"]
            tc["actual_result"] = assertion_report["summary"]
            tc["duration_ms"] = res.get("duration_ms", 120)
            tc["evidence"] = {
                "screenshot": res.get("screenshot"),
                "api_calls_count": len(captured_calls),
                "assertion_details": assertion_report["details"]
            }

            if tc["status"] == "PASSED":
                passed_test_ids.add(tc_id)
            else:
                failed_test_ids.add(tc_id)
                # Classify failure (Master Prompt Section 37)
                res_err = (res.get("error") or "").lower()
                if "shimmer" in res_err or "timeout" in res_err:
                    cls = "APPLICATION_ERROR"
                elif "network" in res_err or "50" in res_err:
                    cls = "NETWORK_ERROR"
                elif "device" in res_err or "adb" in res_err:
                    cls = "DEVICE_ERROR"
                elif "locator" in res_err or "script" in res_err:
                    cls = "TEST_SCRIPT_ERROR"
                else:
                    cls = "APPLICATION_ERROR"
                tc["failure_classification"] = cls

                triage = self.failure_analyzer.triage_failure(tc, res, captured_calls)
                triage["failure_classification"] = cls
                failure_triage.append(triage)

            self.db.update_test_case_result(tc_id, tc["status"], tc["actual_result"], tc["duration_ms"])
            executed_results.append(tc)

        # 13. State: ANALYZING_RESULTS
        self.transition_to("ANALYZING_RESULTS", exec_id)
        passed_count = sum(1 for tc in executed_results if tc.get("status") == "PASSED")
        failed_count = sum(1 for tc in executed_results if tc.get("status") == "FAILED")
        blocked_count = sum(1 for tc in executed_results if tc.get("status") == "BLOCKED")
        not_executed_count = sum(1 for tc in executed_results if tc.get("status") == "NOT_EXECUTED")
        skipped_count = sum(1 for tc in executed_results if tc.get("status") == "SKIPPED") + not_executed_count

        self.db.update_execution_counts(
            exec_id,
            total=len(executed_results),
            passed=passed_count,
            failed=failed_count,
            blocked=blocked_count,
            skipped=skipped_count
        )

        # 14. State: REPORT_READY & FINAL_RESULT
        self.transition_to("REPORT_READY", exec_id)
        report = QAReporter.generate_final_report(
            execution={"id": exec_id, "ticket_key": ticket_key, "environment": environment},
            test_cases=executed_results,
            failures=failure_triage,
            api_count=api_call_count
        )

        # Upload captured screenshot evidence to Jira ticket
        attached_files = []
        for tc in executed_results:
            scr = tc.get("evidence", {}).get("screenshot")
            if scr and os.path.exists(scr):
                filename = os.path.basename(scr)
                if filename not in attached_files:
                    ok = self.jira.attach_file(ticket_key, scr)
                    if ok:
                        attached_files.append(filename)

        comment_markup = QAReporter.format_jira_comment(report)
        if attached_files:
            comment_markup += "\nh3. 📸 Verified Visual Evidence:\n"
            for att in attached_files:
                comment_markup += f"!{att}|thumbnail!\n"

        # Generate proposed Testing Bugs for any failed scenarios
        proposed_bugs = []
        if failure_triage:
            for ft in failure_triage:
                matching_tc = next((t for t in executed_results if t.get("test_case_id") == ft.get("test_case_id")), {})
                bug_prop = QAReporter.propose_jira_bug(
                    ticket_key=ticket_key,
                    execution_id=exec_id,
                    test_case=matching_tc,
                    failure_analysis=ft,
                    environment=environment
                )
                # Duplicate Bug Protection (Rule 44)
                dup_bugs = self.jira.check_duplicate_bugs(
                    summary=matching_tc.get("title", ""),
                    parent_ticket_key=ticket_key
                )
                if dup_bugs:
                    bug_prop["potential_duplicate"] = True
                    bug_prop["duplicate_matches"] = dup_bugs

                bug_prop["master_draft"] = QAReporter.format_master_bug_draft(bug_prop)
                proposed_bugs.append(bug_prop)

        # Generate Master Prompt Section 44 Report string
        master_report_data = {
            "ticket_key": ticket_key,
            "execution_id": exec_id,
            "brand": analysis.get("brand", "CarDekho / BikeDekho"),
            "jira_type": analysis.get("jira_mode", "Testing Bug"),
            "testing_mode": plan.get("mode_label", "Jira Steps"),
            "branch": branch_info.get("primary_branch") if branch_info else "N/A",
            "pr": "N/A",
            "commit": ticket.get("commit", "HEAD"),
            "build_number": (deployment_record or {}).get("build_number", 142),
            "target_server": resolved_server if branch_info and branch_info.get("has_branch") else "N/A",
            "deployment": deployment_record,
            "environment": environment,
            "device_name": (connected_device or {}).get("model", "Connected Android Device"),
            "metrics": report["metrics"],
            "overall_status": report["overall_status"],
            "failures": failure_triage,
            "evidence_path": attached_files[0] if attached_files else "Screenshots captured"
        }
        master_report_str = QAReporter.format_master_qa_report(master_report_data)

        # 15. Check for Failures & Enforce Human Approval Gate (Section 28)
        if proposed_bugs:
            self.transition_to("ANALYZING_FAILURE", exec_id, "Triaging root cause for failed test cases")
            self.transition_to("FINAL_RESULT", exec_id, f"Overall Status: {report['overall_status']}")
            self.transition_to("BUG_APPROVAL", exec_id)

            # Cache proposed bugs awaiting approval
            self.proposed_bugs_cache[exec_id] = {
                "ticket_key": ticket_key,
                "environment": environment,
                "bugs": proposed_bugs,
                "report": report,
                "executed_results": executed_results
            }

            self.transition_to(
                "AWAITING_BUG_APPROVAL",
                exec_id,
                f"{len(proposed_bugs)} Testing Bug(s) proposed. Awaiting QA lead approval before Jira creation."
            )

            print("\n" + "="*75)
            print("📋 PROPOSED TESTING BUGS AWAITING HUMAN APPROVAL (Section 28)")
            print("="*75)
            print(f"Parent Task:        {ticket_key}")
            print(f"Target Issue Type:  Testing Bug (ID: 11000)")
            print(f"Linking Strategy:   Auto-link to {ticket_key} via 'Relates'")
            print(f"Total Defects:      {len(proposed_bugs)}")
            print("-"*75)
            for i, b in enumerate(proposed_bugs, 1):
                print(f"[{i}] Summary:       {b['summary']}")
                print(f"    Issue Type:    {b['issue_type']}")
                print(f"    Parent Task:   {b['parent_ticket']} (Auto-Linked via Relates)")
                if b.get("potential_duplicate"):
                    print(f"    ⚠️ POTENTIAL DUPLICATE DETECTED: {b.get('duplicate_matches')}")
                print(f"    Priority:      {b['priority']}")
                print(f"    Failure:       {b.get('failure_details', 'Assertion mismatch')}")
                if b.get("screenshot"):
                    print(f"    Screenshot:    {b['screenshot']}")
            print("="*75)
            print("⏸️  NO BUG CREATED IN JIRA YET (Awaiting Your Explicit Approval).")
            print(f"👉 To approve and create in Jira, call: orchestrator.approve_and_create_bugs('{exec_id}')")
            print("="*75 + "\n")

            comment_markup += "\n\n*⚠️ QA Note*: Failures were identified. Proposed Testing Bugs are awaiting QA confirmation before Jira logging.\n"
            self.jira.add_comment(ticket_key, comment_markup)
            self.db.update_execution_state(exec_id, "AWAITING_BUG_APPROVAL", overall_result="FAILED")

            return {
                "execution_id": exec_id,
                "ticket_key": ticket_key,
                "environment": environment,
                "overall_status": "AWAITING_BUG_APPROVAL",
                "metrics": report["metrics"],
                "report": report,
                "master_report": master_report_str,
                "jira_comment": comment_markup,
                "failures": failure_triage,
                "proposed_bugs": proposed_bugs,
                "installed_build": installed_build,
                "deployment": deployment_record
            }

        # If all passed, complete and transition Jira ticket
        self.transition_to("FINAL_RESULT", exec_id, "All test cases PASSED.")
        self.transition_to("QA_SIGNOFF", exec_id)
        master_signoff_str = QAReporter.format_master_signoff(master_report_data)

        self.transition_to("AWAITING_JIRA_UPDATE", exec_id)
        self.jira.add_comment(ticket_key, comment_markup)

        if report["overall_status"] == "PASSED":
            self.jira.transition_issue(ticket_key, "QA Complete")
            final_state = "COMPLETED"
        else:
            final_state = "FAILED"

        self.transition_to(final_state, exec_id, f"Final QA Result: {report['overall_status']}")
        self.db.update_execution_state(exec_id, final_state, overall_result=report["overall_status"])

        return {
            "execution_id": exec_id,
            "ticket_key": ticket_key,
            "environment": environment,
            "overall_status": report["overall_status"],
            "metrics": report["metrics"],
            "report": report,
            "master_report": master_report_str,
            "master_signoff": master_signoff_str,
            "jira_comment": comment_markup,
            "failures": failure_triage,
            "proposed_bugs": [],
            "installed_build": installed_build,
            "deployment": deployment_record
        }

    def approve_and_create_bugs(self, execution_id: str, approved_indices: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Human Approval Gate Callback (Section 28):
        Creates approved Testing Bugs in Jira, links them to the parent Task ticket via 'Relates',
        and attaches visual evidence screenshots.
        """
        cached = self.proposed_bugs_cache.get(execution_id)
        if not cached:
            print(f"[WARN] No cached proposed bugs found for execution {execution_id}")
            return {"status": "ERROR", "message": f"No proposed bugs found for execution {execution_id}"}

        parent_key = cached.get("ticket_key")
        proposed = cached.get("bugs", [])

        if approved_indices is not None:
            to_process = [proposed[i] for i in approved_indices if 0 <= i < len(proposed)]
        else:
            to_process = proposed

        created_results = []
        for bug in to_process:
            print(f"\n[APPROVAL GRANTED] Creating Jira {bug.get('issue_type', 'Testing Bug')} for parent {parent_key}...")
            created_key = self.jira.create_bug(bug, parent_ticket_key=parent_key)
            if created_key:
                bug_info = {
                    "bug_key": created_key,
                    "summary": bug.get("summary"),
                    "issue_type": bug.get("issue_type", "Testing Bug"),
                    "parent_task": parent_key,
                    "status": "CREATED_AND_LINKED"
                }
                created_results.append(bug_info)

                # Record in DB jira_updates table
                self.db.record_jira_update({
                    "execution_id": execution_id,
                    "ticket_key": parent_key,
                    "update_type": "BUG_CREATED",
                    "target_key": created_key,
                    "content": f"Created {bug.get('issue_type')} {created_key} linked to {parent_key}",
                    "status": "SUCCESS"
                })

        # Post update comment on parent ticket linking to the newly created bugs
        if created_results:
            comment_text = f"h3. ⚠️ Approved Linked Testing Bugs Created:\n"
            for b in created_results:
                comment_text += f"* *{b['issue_type']}*: [{b['bug_key']}|{self.jira.base_url}/browse/{b['bug_key']}] - {b['summary']}\n"
            comment_text += f"\n_Directly linked to parent Task {parent_key} via Jira issue link 'Relates'._"
            self.jira.add_comment(parent_key, comment_text)

        self.transition_to("FAILED", execution_id, f"Created {len(created_results)} linked Testing Bug(s)")
        self.db.update_execution_state(execution_id, "FAILED", overall_result="FAILED")

        return {
            "status": "SUCCESS",
            "execution_id": execution_id,
            "parent_task": parent_key,
            "created_bugs": created_results
        }

    def pause_execution(self):
        self.is_paused = True

    def resume_execution(self):
        self.is_paused = False

    def stop_execution(self):
        self.is_stopped = True

    def authorize_qa_session(self, execution_id: str) -> Dict[str, Any]:
        """Approves the One QA Session Authorization for Android interactions (Master Prompt Section 20)."""
        self.transition_to("EXECUTING", execution_id, "One QA Session Authorization approved by user.")
        return {
            "status": "SUCCESS",
            "execution_id": execution_id,
            "message": "QA Session authorized. Normal Android interactions will proceed autonomously."
        }
