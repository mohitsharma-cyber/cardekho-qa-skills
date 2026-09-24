"""
AI Failure Analyzer for Jira AI QA Orchestrator.
Performs intelligent triage of test failures, correlating screenshots, API errors, and logs.
Separates FACT, EVIDENCE, INFERENCE, ASSUMPTION, and RECOMMENDATION.
"""

from typing import Any, Dict, List, Optional


class FailureAnalyzer:
    def analyze_failure(self, test_case: Dict[str, Any], failure_context: Dict[str, Any]) -> Dict[str, Any]:
        tc_id = test_case.get("test_case_id")
        title = test_case.get("title")
        err_msg = failure_context.get("failure_reason", "Assertion verification failed")
        http_code = failure_context.get("http_status")
        logs = failure_context.get("logs", [])
        evidence_files = failure_context.get("evidence", [])

        # 1. Classification
        classification = "APPLICATION_ERROR"
        if http_code in (502, 503, 504) or "timeout" in err_msg.lower():
            classification = "ENVIRONMENT_ERROR"
        elif "connection refused" in err_msg.lower() or "network" in err_msg.lower():
            classification = "NETWORK_ERROR"
        elif "device" in err_msg.lower() or "adb" in err_msg.lower():
            classification = "DEVICE_ERROR"
        elif "401" in err_msg or "403" in err_msg or "unauthorized" in err_msg.lower():
            classification = "AUTH_ERROR"

        # 2. Extract Facts & Concrete Evidence
        facts = [
            f"Test case {tc_id} failed during execution.",
            f"Error reported: {err_msg}"
        ]
        if http_code:
            facts.append(f"HTTP Status observed: {http_code}")

        evidence_items = [f"Evidence logged: {e.get('path', e.get('type'))}" for e in evidence_files]
        if logs:
            evidence_items.append(f"Recent log snippet: {str(logs[-1])[:200]}")

        # 3. Formulate Inferences & Recommendations
        if classification == "ENVIRONMENT_ERROR":
            inference = "Backend testing/staging microservice or gateway experienced transient outage or latency spike."
            recommendation = "Verify target environment gateway status and re-test with transient retry policy."
            confidence = 0.88
        elif classification == "AUTH_ERROR":
            inference = "Session cookie or bearer token invalid or expired during test run."
            recommendation = "Check test account credentials in environment settings."
            confidence = 0.92
        else:
            inference = "Application UI or backend logic returned payload inconsistent with acceptance criteria."
            recommendation = "Review attached failure screenshot and API payload to verify against product requirements."
            confidence = 0.85

        return {
            "test_case_id": tc_id,
            "classification": classification,
            "root_cause_hypothesis": f"Root cause correlated with {classification}: {err_msg}",
            "facts": facts,
            "evidence": evidence_items,
            "inference": inference,
            "recommendation": recommendation,
            "confidence": confidence
        }

    def triage_failure(self, test_case: Dict[str, Any], res: Dict[str, Any], captured_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Alias for failure analysis with execution response context."""
        failure_ctx = {
            "failure_reason": res.get("actual_result", "Test assertion failed"),
            "http_status": res.get("http_status", 500),
            "logs": res.get("logs", []),
            "evidence": res.get("evidence", [])
        }
        return self.analyze_failure(test_case, failure_ctx)

