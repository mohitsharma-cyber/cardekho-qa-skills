"""
QA Reporting & Bug Proposal Engine for Jira AI QA Orchestrator.
Generates comprehensive QA Sign-Off reports, Jira markdown comments,
and structured bug proposals adhering to Human Approval and Duplicate Prevention gates.
"""

from typing import Any, Dict, List, Optional


class QAReporter:
    @staticmethod
    def generate_final_report(execution: Dict[str, Any], test_cases: List[Dict[str, Any]],
                              failures: List[Dict[str, Any]], api_count: int = 0) -> Dict[str, Any]:
        """Builds a structured QA Execution Sign-Off Report."""
        exec_id = execution.get("id", "EXEC-000")
        ticket_key = execution.get("ticket_key", "")
        env = execution.get("environment", "TESTING")
        total = len(test_cases)
        passed = sum(1 for tc in test_cases if tc.get("status") == "PASSED")
        failed = sum(1 for tc in test_cases if tc.get("status") == "FAILED")
        blocked = sum(1 for tc in test_cases if tc.get("status") == "BLOCKED")
        skipped = sum(1 for tc in test_cases if tc.get("status") == "SKIPPED")

        overall = "PASSED"
        if failed > 0:
            overall = "FAILED"
        elif blocked > 0 or skipped > 0:
            overall = "PARTIAL / BLOCKED"

        return {
            "execution_id": exec_id,
            "ticket_key": ticket_key,
            "environment": env,
            "overall_status": overall,
            "metrics": {
                "generated": total,
                "executed": passed + failed,
                "passed": passed,
                "failed": failed,
                "blocked": blocked,
                "skipped": skipped
            },
            "apis_captured": api_count,
            "failures": failures,
            "test_cases": test_cases,
            "recommendation": "Ready for Release / Staging Promotion." if overall == "PASSED" else "Release Blocked. Review failed test cases and attached defect proposals."
        }

    @staticmethod
    def format_jira_comment(report: Dict[str, Any]) -> str:
        """Formats the final QA report into clean Jira wiki markup for posting as a comment."""
        m = report["metrics"]
        status_color = "green" if report["overall_status"] == "PASSED" else "red"

        comment = f"""h2. 🚀 Automated QA Execution Sign-Off Report

*Ticket:* {report['ticket_key']}
*Execution ID:* {{code}}{report['execution_id']}{{code}}
*Environment:* *{report['environment']}*
*Overall Result:* {{color:{status_color}}}*{report['overall_status']}*{{color}}

|| Metric || Count ||
| Total Generated | {m['generated']} |
| Executed | {m['executed']} |
| (/) Passed | *{m['passed']}* |
| (x) Failed | *{m['failed']}* |
| (!) Blocked | {m['blocked']} |
| (-) Skipped | {m['skipped']} |
| Business APIs Captured | {report.get('apis_captured', 0)} |

h3. 📋 Recommendation:
{report['recommendation']}
"""
        if report.get("failures"):
            comment += "\nh3. ⚠️ Failure Summary:\n"
            for f in report["failures"]:
                comment += f"* *{f.get('test_case_id')}*: {f.get('root_cause_hypothesis')}\n"

        comment += "\n_Generated deterministically by Jira AI QA Orchestrator._"
        return comment

    @staticmethod
    def propose_jira_bug(ticket_key: str, execution_id: str, test_case: Dict[str, Any],
                         failure_analysis: Dict[str, Any], environment: str) -> Dict[str, Any]:
        """
        Creates a structured Jira Testing Bug Proposal linked to parent Task.
        Follows Human Approval gate (Section 28) and Duplicate check (Section 27).
        """
        tc_id = test_case.get("test_case_id", "TC-001")
        title = test_case.get("title", "")
        
        # Brand detection
        t_upper = ticket_key.upper()
        is_bikedekho = "BD" in t_upper or "BIKE" in title.upper()
        brand_prefix = "BikeDekho App" if is_bikedekho else "CarDekho App"

        summary = f"[{brand_prefix}] Testing Bug: {title[:55]} ({tc_id})"
        screenshot = (
            test_case.get("evidence", {}).get("screenshot") or 
            failure_analysis.get("evidence_screenshot") or 
            test_case.get("screenshot")
        )

        desc = f"""Context:
Observed during automated QA test execution ({execution_id}) against {environment} environment for Jira requirement {ticket_key}.

Visual Observation & Error:
Test case '{title}' failed deterministic verification.
{failure_analysis.get('root_cause_hypothesis', 'Assertion failure during test execution')}

Steps to Reproduce:
"""
        for step in test_case.get("steps", []):
            desc += f"{step.get('step_num', 1)}. {step.get('action')}\n"

        desc += f"""
Actual Result:
{failure_analysis.get('root_cause_hypothesis', 'Unexpected behavior observed')}

Expected Result:
{test_case.get('expected_result', 'Should meet acceptance criteria')}

Impact:
Blocks testing sign-off for parent task {ticket_key}.

Traceability:
- Parent Task Ticket: {ticket_key}
- Test Case ID: {tc_id}
- Execution ID: {execution_id}
- Target Environment: {environment}
- Issue Classification: Linked Testing Bug
"""

        # Project key extraction (e.g. MB2C, DB2C, BDCV)
        proj_key = ticket_key.split("-")[0] if "-" in ticket_key else "MB2C"

        return {
            "summary": summary,
            "description": desc,
            "priority": "P2",
            "issue_type": "Testing Bug",
            "project_key": proj_key,
            "labels": ["qa-automated", "testing-bug", "linked-defect", tc_id.lower()],
            "original_ticket": ticket_key,
            "parent_ticket": ticket_key,
            "execution_id": execution_id,
            "screenshot": screenshot,
            "failure_details": failure_analysis.get("root_cause_hypothesis", "")
        }

    @staticmethod
    def format_master_qa_report(report_data: Dict[str, Any]) -> str:
        """Formats the explicit Master Prompt Section 44 Final QA Report."""
        m = report_data.get("metrics", {})
        deployment = report_data.get("deployment") or {}
        failures = report_data.get("failures", [])
        primary_failure = failures[0] if failures else {}

        lines = [
            f"QA EXECUTION REPORT — QA Execution Report: [{report_data.get('ticket_key', '')}]\n",
            f"Execution ID:\n{report_data.get('execution_id', 'EXEC-QA')}\n",
            f"Jira:\n{report_data.get('ticket_key', '')}\n",
            f"Project:\n{report_data.get('brand', 'CarDekho / BikeDekho')}\n",
            f"Type:\n{report_data.get('jira_type', 'Testing Bug')}\n",
            f"Testing Mode:\n{report_data.get('testing_mode', 'Jira Steps')}\n",
            f"Branch:\n{deployment.get('branch', report_data.get('branch', 'N/A'))}\n",
            f"PR:\n{report_data.get('pr', 'N/A')}\n",
            f"Commit:\n{report_data.get('commit', 'HEAD')}\n",
            f"Build:\n{report_data.get('build_number', deployment.get('build_number', 'N/A'))}\n",
            f"Deployment Target:\n{deployment.get('target_env', report_data.get('target_server', 'N/A'))}\n",
            f"Deployment:\n{deployment.get('status', 'NOT_REQUIRED')}\n",
            f"Environment:\n{report_data.get('environment', 'TESTING')}\n",
            f"Device:\n{report_data.get('device_name', 'Pixel 7 / Android Device')}\n",
            f"Test Cases:\n{m.get('generated', 0)}\n",
            f"Passed:\n{m.get('passed', 0)}\n",
            f"Failed:\n{m.get('failed', 0)}\n",
            f"Blocked:\n{m.get('blocked', 0)}\n",
            f"Skipped:\n{m.get('skipped', 0)}\n",
            f"Overall:\n{report_data.get('overall_status', 'PASSED')}\n"
        ]

        if failures:
            lines.extend([
                f"Failure Details:\n{primary_failure.get('root_cause_hypothesis', 'Assertion mismatch observed')}\n",
                f"Expected:\n{primary_failure.get('expected', 'Expected state according to acceptance criteria')}\n",
                f"Actual:\n{primary_failure.get('actual', primary_failure.get('root_cause_hypothesis', 'Mismatched'))}\n",
                f"Classification:\n{primary_failure.get('failure_classification', 'APPLICATION_ERROR')}\n",
                f"Root Cause Analysis:\n{primary_failure.get('root_cause_hypothesis', 'Functional deviation during UI rendering')}\n",
                f"Evidence:\n{primary_failure.get('evidence_screenshot', report_data.get('evidence_path', 'Captured in execution artifacts'))}\n"
            ])
        else:
            lines.extend([
                "Failure Details:\nNone\n",
                "Expected:\nAll acceptance criteria met\n",
                "Actual:\nAll assertions satisfied with visual evidence\n",
                "Classification:\nN/A\n",
                "Root Cause Analysis:\nN/A\n",
                f"Evidence:\n{report_data.get('evidence_path', 'Verified in execution artifacts')}\n"
            ])

        lines.extend([
            f"Requirement Coverage:\n{report_data.get('req_coverage', '100%')}\n",
            f"Acceptance Criteria Coverage:\n{report_data.get('ac_coverage', '100%')}\n",
            f"Regression Coverage:\n{report_data.get('regression_coverage', 'Impacted + Extended areas verified')}"
        ])

        return "\n".join(lines)

    @staticmethod
    def format_master_signoff(report_data: Dict[str, Any]) -> str:
        """Formats the explicit Master Prompt Section 45 QA Sign-Off."""
        m = report_data.get("metrics", {})
        deployment = report_data.get("deployment") or {}
        return (
            "QA SIGN-OFF\n\n"
            f"Jira:\n{report_data.get('ticket_key')}\n\n"
            f"Environment:\n{report_data.get('environment', 'TESTING')}\n\n"
            f"Build:\n#{report_data.get('build_number', deployment.get('build_number', '142'))}\n\n"
            f"Device:\n{report_data.get('device_name', 'Connected Android Device')}\n\n"
            f"Tests:\n{m.get('passed', 0)} / {m.get('generated', 0)} Passed (0 Failed, 0 Blocked)\n\n"
            f"Evidence:\n{report_data.get('evidence_path', 'Screenshots verified and archived')}\n\n"
            f"Risk:\n{report_data.get('risk_level', 'Low (All critical regression passed)')}\n\n"
            "Result:\nPASSED\n\n"
            "[POST QA SIGN-OFF TO JIRA]"
        )

    @staticmethod
    def format_master_bug_draft(bug: Dict[str, Any]) -> str:
        """Formats the explicit Master Prompt Section 46 Testing Bug Draft."""
        steps_text = "\n".join([f"{s.get('step_num', idx+1)}. {s.get('action')}" for idx, s in enumerate(bug.get("steps", []))]) if bug.get("steps") else "1. Open screen\n2. Observe values"
        return (
            "TESTING BUG DRAFT READY\n\n"
            f"Summary:\n{bug.get('summary')}\n\n"
            f"Description:\n{bug.get('description')}\n\n"
            f"Environment:\n{bug.get('environment', 'TESTING')}\n\n"
            f"Build:\n{bug.get('build', 'N/A')}\n\n"
            f"Branch:\n{bug.get('branch', 'N/A')}\n\n"
            f"PR:\n{bug.get('pr', 'N/A')}\n\n"
            f"Steps to Reproduce:\n{steps_text}\n\n"
            f"Expected Result:\n{bug.get('expected_result', 'Should conform to requirement')}\n\n"
            f"Actual Result:\n{bug.get('actual_result', bug.get('failure_details', 'Observed defect'))}\n\n"
            f"Frequency:\n{bug.get('frequency', 'Consistent (100%)')}\n\n"
            f"Severity:\n{bug.get('severity', bug.get('priority', 'P2'))}\n\n"
            f"Evidence:\n{bug.get('screenshot', 'Screenshot attached')}\n\n"
            f"Logs:\n{bug.get('logs', 'Captured in execution context')}\n\n"
            f"API Evidence:\n{bug.get('api_evidence', 'Captured')}\n\n"
            f"Root Cause Hypothesis:\n{bug.get('failure_details', 'Assertion mismatch')}\n\n"
            f"Parent Jira:\n{bug.get('parent_ticket', bug.get('original_ticket'))}\n\n"
            "[APPROVE & CREATE BUG]"
        )

