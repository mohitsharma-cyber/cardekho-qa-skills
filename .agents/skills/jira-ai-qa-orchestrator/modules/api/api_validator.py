"""
API Validator Engine for Jira AI QA Orchestrator.
Evaluates end-to-end API test results, verifies contract invariants,
formats human-readable validation summaries, and determines conditional execution.
"""

from typing import Dict, Any, List, Optional, Tuple
from .response_assertions import ResponseAssertions

API_CHANGE_KEYWORDS = [
    "api", "endpoint", "payload", "json", "request", "response",
    "http", "rest", "backend", "swagger", "post", "get", "put",
    "/v1/", "/v2/", "/api/", "contract", "schema"
]

DATA_INTEGRITY_KEYWORDS = [
    "price", "orp", "calculation", "formula", "tax", "rto", "insurance",
    "specs", "specification", "features", "mileage", "emi"
]

class ApiValidator:
    """Coordinates API contract validation, UI consistency checks, and execution gating."""

    def __init__(self):
        self.assertions = ResponseAssertions()

    @staticmethod
    def should_execute_api_testing(
        ticket_data: Dict[str, Any],
        risk_profile: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        """
        Determines whether API testing should run conditionally.
        API testing is NOT run for every Jira (e.g. bypassed for UI-only changes).
        Runs when:
        - ticket changes API behavior
        - feature depends on API
        - data integrity is relevant
        - Reference/WAP comparison requires API validation
        - risk engine determines API testing is required
        """
        summary = str(ticket_data.get("summary", "")).lower()
        description = str(ticket_data.get("description", "")).lower()
        full_text = f"{summary}\n{description}"

        # 1. UI-only check: if ticket is strictly UI-only, bypass API testing
        if risk_profile and risk_profile.get("is_ui_only"):
            return False, "Bypassed: Ticket is classified as UI-only cosmetic change."

        # 2. Risk engine requirement check
        if risk_profile:
            required_cats = risk_profile.get("required_categories", [])
            if "api_data" in required_cats or risk_profile.get("api_dependencies"):
                return True, "Triggered by Risk Engine: 'api_data' required category or API dependencies detected."

        # 3. Explicit API behavior change
        if any(kw in full_text for kw in API_CHANGE_KEYWORDS):
            return True, "Triggered: Ticket description or summary explicitly touches backend API endpoints."

        # 4. Data integrity relevance (pricing/EMI/specifications)
        if any(kw in full_text for kw in DATA_INTEGRITY_KEYWORDS):
            return True, "Triggered: Data integrity verification required for pricing/specifications calculations."

        # 5. Reference or WAP comparison requiring API consistency
        if "wap" in full_text or "mweb" in full_text or "reference" in full_text:
            return True, "Triggered: Reference/WAP comparison requires parity with backend API contract."

        return False, "Bypassed: No API dependencies or data integrity requirements detected."

    def validate_api_response(
        self,
        response_result: Dict[str, Any],
        expected_status: int = 200,
        max_latency_ms: float = 2000.0,
        required_fields: Optional[List[str]] = None,
        expected_schema_keys: Optional[List[str]] = None,
        non_nullable_fields: Optional[List[str]] = None,
        expected_business_data: Optional[Dict[str, Any]] = None,
        ui_rendered_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes comprehensive validation across status, latency, schema, fields, nulls,
        business logic, and UI consistency.
        """
        status_code = response_result.get("status_code", 0)
        resp_time_ms = response_result.get("response_time_ms", 0.0)
        data = response_result.get("data")
        is_json = response_result.get("is_json", False)

        assertion_results = []

        # 1. Status Code
        assertion_results.append(self.assertions.assert_status_code(status_code, expected_status))

        # 2. Response Time
        assertion_results.append(self.assertions.assert_response_time(resp_time_ms, max_latency_ms))

        # 3. Schema Structure (if expected)
        schema_status = "N/A"
        if expected_schema_keys:
            schema_res = self.assertions.assert_schema_structure(data, expected_schema_keys)
            assertion_results.append(schema_res)
            schema_status = schema_res["status"]
        elif is_json and isinstance(data, dict):
            schema_status = "PASS"

        # 4. Required Fields
        req_fields_status = "N/A"
        if required_fields:
            rf_res = self.assertions.assert_required_fields(data, required_fields)
            assertion_results.append(rf_res)
            req_fields_status = rf_res["status"]

        # 5. Null Handling
        if non_nullable_fields:
            assertion_results.append(self.assertions.assert_null_handling(data, non_nullable_fields))

        # 6. Business Data
        if expected_business_data:
            for path, exp_val in expected_business_data.items():
                assertion_results.append(self.assertions.assert_business_data(data, path, exp_val))

        # 7. UI/API Consistency
        ui_match_status = "N/A"
        if ui_rendered_data and isinstance(data, dict):
            ui_passes = []
            for field, ui_val in ui_rendered_data.items():
                # Extract value from API data
                api_val = data.get(field)
                match_res = self.assertions.assert_ui_api_consistency(api_val, ui_val, field)
                assertion_results.append(match_res)
                ui_passes.append(match_res["status"] == "PASS")
            ui_match_status = "PASS" if all(ui_passes) else "FAIL"

        # Overall Status
        all_passed = all(a["status"] == "PASS" for a in assertion_results)
        overall_status = "PASS" if all_passed else "FAIL"

        # Formatted Summary Card
        formatted_card = (
            f"API Status: {status_code}\n"
            f"Response Time: {int(resp_time_ms)} ms\n"
            f"Schema: {schema_status}\n"
            f"Required Fields: {req_fields_status}\n"
            f"UI/API Data Match: {ui_match_status}"
        )

        return {
            "overall_status": overall_status,
            "status_code": status_code,
            "response_time_ms": resp_time_ms,
            "schema_status": schema_status,
            "required_fields_status": req_fields_status,
            "ui_api_data_match": ui_match_status,
            "formatted_summary": formatted_card,
            "assertions": assertion_results,
            "discrepancies": [a for a in assertion_results if a["status"] == "FAIL"]
        }
