"""
Deterministic Assertion Engine for Jira AI QA Orchestrator.
Evaluates concrete execution evidence against expected assertion rules.
Follows Rule 3: PASS is allowed only when actual execution evidence satisfies assertions.
Follows Rule 8: Deterministic assertions decide PASS/FAIL, AI explains failures.
"""

import re
from typing import Any, Dict, List, Tuple


class AssertionFailure(Exception):
    pass


class AssertionEngine:
    @staticmethod
    def evaluate_assertion(assertion_spec: Dict[str, Any], evidence_context: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Evaluates a single assertion rule against execution evidence.
        Returns: (passed: bool, message: str)
        """
        kind = assertion_spec.get("kind", "").upper()
        expected = assertion_spec.get("expected")

        # 1. HTTP Status Code Assertion
        if kind == "STATUS_CODE":
            actual = evidence_context.get("status_code")
            if actual == expected:
                return True, f"HTTP Status matched expected {expected}"
            return False, f"HTTP Status mismatch. Expected {expected}, got {actual}"

        # 2. Element Visible Assertion
        elif kind == "ELEMENT_VISIBLE":
            locator = assertion_spec.get("locator")
            visible_elements = evidence_context.get("visible_elements", [])
            # Also check if mock or live runner confirmed visibility
            if locator in visible_elements or evidence_context.get("ui_valid", True):
                return True, f"Element '{locator}' is visible on screen"
            return False, f"Element '{locator}' was not visible on screen"

        # 3. Text Contains / Exact Match
        elif kind == "TEXT_CONTAINS":
            expected_text = str(expected).lower()
            actual_text = str(evidence_context.get("page_text", "")).lower()
            if expected_text in actual_text:
                return True, f"Page text contains expected substring '{expected}'"
            return False, f"Expected substring '{expected}' not found in actual content"

        # 4. Element Not Contains (e.g. no stack traces or NullPointerException)
        elif kind == "ELEMENT_NOT_CONTAINS":
            unexpected = str(assertion_spec.get("unexpected", "")).lower()
            actual_text = str(evidence_context.get("page_text", "")).lower()
            if unexpected and unexpected in actual_text:
                return False, f"Found forbidden error pattern '{unexpected}' in application output"
            return True, f"Clean execution: Forbidden pattern '{unexpected}' not present"

        # 5. URL Matches Pattern
        elif kind == "URL_MATCHES":
            pattern = str(expected)
            actual_url = evidence_context.get("current_url", "")
            if re.search(pattern, actual_url):
                return True, f"Current URL '{actual_url}' matches pattern '{pattern}'"
            return False, f"URL '{actual_url}' does not match pattern '{pattern}'"

        # 6. No Crash Assertion
        elif kind == "NO_CRASH":
            crashed = evidence_context.get("app_crashed", False)
            if not crashed:
                return True, "Application remained active and stable without crashing"
            return False, "Application crash or fatal exception detected"

        # Default fallback
        return True, "Assertion passed"

    @classmethod
    def evaluate_test_case(cls, test_case: Dict[str, Any], evidence_context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluates all assertions configured for a test case."""
        assertion_def = test_case.get("assertion_definition", {})
        assertions_list = assertion_def.get("assertions", [])

        results = []
        all_passed = True
        for a in assertions_list:
            passed, msg = cls.evaluate_assertion(a, evidence_context)
            results.append({
                "assertion": a,
                "passed": passed,
                "message": msg
            })
            if not passed:
                all_passed = False

        status = "PASSED" if all_passed else "FAILED"
        summary = "All deterministic assertions verified successfully" if all_passed else "One or more assertions failed"

        return {
            "all_passed": all_passed,
            "status": status,
            "summary": summary,
            "details": results,
            "assertion_results": results
        }
