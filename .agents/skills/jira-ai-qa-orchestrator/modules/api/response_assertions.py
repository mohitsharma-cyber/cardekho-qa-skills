"""
Response Assertion Suite for API Validation in Jira AI QA Orchestrator.
Performs deterministic assertions across HTTP status codes, latency thresholds,
JSON schema keys, mandatory fields, null-safety, business logic values,
error payloads, and UI/API data consistency.
"""

from typing import Dict, Any, List, Optional, Union

class ResponseAssertions:
    """Deterministic assertions for API contract and data verification."""

    @staticmethod
    def assert_status_code(actual: int, expected: Union[int, List[int]]) -> Dict[str, Any]:
        expected_list = expected if isinstance(expected, list) else [expected]
        passed = actual in expected_list
        return {
            "assertion": "HTTP Status",
            "status": "PASS" if passed else "FAIL",
            "expected": expected,
            "actual": actual,
            "message": f"Expected status {expected}, received {actual}" if not passed else f"Status {actual} matched"
        }

    @staticmethod
    def assert_response_time(actual_ms: float, max_threshold_ms: float = 2000.0) -> Dict[str, Any]:
        passed = actual_ms <= max_threshold_ms
        return {
            "assertion": "Response Time",
            "status": "PASS" if passed else "FAIL",
            "threshold_ms": max_threshold_ms,
            "actual_ms": actual_ms,
            "message": f"Response time {actual_ms} ms within {max_threshold_ms} ms threshold" if passed else f"Slow response: {actual_ms} ms exceeded {max_threshold_ms} ms threshold"
        }

    @staticmethod
    def assert_schema_structure(response_data: Any, expected_keys: List[str]) -> Dict[str, Any]:
        if not isinstance(response_data, dict):
            return {
                "assertion": "Schema Structure",
                "status": "FAIL",
                "message": f"Malformed response: expected JSON object/dict, got {type(response_data).__name__}",
                "missing_keys": expected_keys
            }

        missing = [k for k in expected_keys if k not in response_data]
        passed = len(missing) == 0
        return {
            "assertion": "Schema Structure",
            "status": "PASS" if passed else "FAIL",
            "missing_keys": missing,
            "message": "All expected schema keys present" if passed else f"Schema missing keys: {', '.join(missing)}"
        }

    @staticmethod
    def assert_required_fields(response_data: Any, required_fields: List[str]) -> Dict[str, Any]:
        if not isinstance(response_data, dict):
            return {
                "assertion": "Required Fields",
                "status": "FAIL",
                "message": f"Cannot check fields: response is not a dict ({type(response_data).__name__})"
            }

        missing_fields = []
        for field in required_fields:
            # Support nested dot notation: 'data.pricing.rto'
            parts = field.split(".")
            curr = response_data
            found = True
            for p in parts:
                if isinstance(curr, dict) and p in curr:
                    curr = curr[p]
                else:
                    found = False
                    break
            if not found:
                missing_fields.append(field)

        passed = len(missing_fields) == 0
        return {
            "assertion": "Required Fields",
            "status": "PASS" if passed else "FAIL",
            "missing_fields": missing_fields,
            "message": "All required fields exist" if passed else f"Missing required fields: {', '.join(missing_fields)}"
        }

    @staticmethod
    def assert_null_handling(response_data: Any, non_nullable_fields: List[str]) -> Dict[str, Any]:
        if not isinstance(response_data, dict):
            return {
                "assertion": "Null Handling",
                "status": "FAIL",
                "message": "Response is not a JSON object"
            }

        null_violations = []
        for field in non_nullable_fields:
            parts = field.split(".")
            curr = response_data
            is_null = False
            for p in parts:
                if isinstance(curr, dict) and p in curr:
                    curr = curr[p]
                    if curr is None:
                        is_null = True
                        break
                else:
                    break
            if is_null:
                null_violations.append(field)

        passed = len(null_violations) == 0
        return {
            "assertion": "Null Handling",
            "status": "PASS" if passed else "FAIL",
            "null_violations": null_violations,
            "message": "Non-nullable fields contain valid values" if passed else f"Unexpected null in non-nullable fields: {', '.join(null_violations)}"
        }

    @staticmethod
    def assert_business_data(response_data: Any, field_path: str, expected_val: Any) -> Dict[str, Any]:
        parts = field_path.split(".")
        curr = response_data
        for p in parts:
            if isinstance(curr, dict) and p in curr:
                curr = curr[p]
            else:
                return {
                    "assertion": f"Business Data ({field_path})",
                    "status": "FAIL",
                    "message": f"Path '{field_path}' not found in response data",
                    "expected": expected_val,
                    "actual": None
                }

        # Value comparison
        passed = (curr == expected_val) or (str(curr).strip().lower() == str(expected_val).strip().lower())
        return {
            "assertion": f"Business Data ({field_path})",
            "status": "PASS" if passed else "FAIL",
            "expected": expected_val,
            "actual": curr,
            "message": f"Field '{field_path}' matched expected value" if passed else f"Mismatch in '{field_path}': expected '{expected_val}', got '{curr}'"
        }

    @staticmethod
    def assert_error_response(response_data: Any, expected_error_code: Optional[str] = None) -> Dict[str, Any]:
        if not isinstance(response_data, dict):
            return {
                "assertion": "Error Response",
                "status": "FAIL",
                "message": "Error response is not a valid JSON structure"
            }

        # Look for typical error keys: "error", "message", "status", "code"
        has_error = any(k in response_data for k in ["error", "errorMessage", "message", "errors", "code"])
        if not has_error:
            return {
                "assertion": "Error Response",
                "status": "FAIL",
                "message": "Response does not contain error structure or messages"
            }

        if expected_error_code:
            code_val = str(response_data.get("code") or response_data.get("errorCode") or response_data.get("status") or "")
            if expected_error_code.lower() not in code_val.lower():
                return {
                    "assertion": "Error Response",
                    "status": "FAIL",
                    "message": f"Error code mismatch: expected '{expected_error_code}', got '{code_val}'"
                }

        return {
            "assertion": "Error Response",
            "status": "PASS",
            "message": "Valid error response structure returned"
        }

    @staticmethod
    def assert_ui_api_consistency(api_value: Any, ui_value: Any, field_name: str) -> Dict[str, Any]:
        """
        Validates consistency between backend API response and UI rendered text.
        Handles numeric normalization (e.g. '19.20' vs '₹ 19.20 Lakh').
        """
        api_str = str(api_value).strip().lower()
        ui_str = str(ui_value).strip().lower()

        # Direct match or substring containment
        passed = (api_str == ui_str) or (api_str in ui_str) or (ui_str in api_str)

        # Normalize currency and commas
        clean_api = api_str.replace("₹", "").replace(",", "").replace("lakh", "").strip()
        clean_ui = ui_str.replace("₹", "").replace(",", "").replace("lakh", "").strip()
        if not passed and clean_api and clean_ui:
            passed = (clean_api in clean_ui) or (clean_ui in clean_api)

        return {
            "assertion": f"UI/API Consistency ({field_name})",
            "status": "PASS" if passed else "FAIL",
            "field": field_name,
            "api_value": api_value,
            "ui_value": ui_value,
            "message": f"UI matches API for '{field_name}'" if passed else f"UI/API mismatch for '{field_name}': API returned '{api_value}', UI displayed '{ui_value}'"
        }
