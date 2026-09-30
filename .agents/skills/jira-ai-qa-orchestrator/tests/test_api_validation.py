"""
Tests for API Validation Engine (Phase 3).
Validates:
- 2xx successful responses
- 4xx client errors
- 5xx server errors
- Timeout handling
- Malformed non-JSON responses
- Missing required fields
- Null field violations
- UI/API data mismatch
- Conditional execution logic
- Evidence capture with sensitive token redaction
"""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock
import requests

skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if skill_root not in sys.path:
    sys.path.insert(0, skill_root)

from modules.api.api_client import ApiClient
from modules.api.api_validator import ApiValidator
from modules.api.response_assertions import ResponseAssertions
from modules.api.api_capture import ApiEvidenceCapture


@pytest.fixture
def validator():
    return ApiValidator()


@pytest.fixture
def assertions():
    return ResponseAssertions()


@pytest.fixture
def evidence_capture(tmp_path):
    return ApiEvidenceCapture(evidence_dir=str(tmp_path))


def test_2xx_successful_response_validation(validator):
    """200 OK response with schema and required fields passes validation."""
    response = {
        "status_code": 200,
        "response_time_ms": 342.0,
        "is_json": True,
        "data": {
            "model": "Creta",
            "variant": "SX (O)",
            "pricing": {"ex_showroom": 1700000, "rto": 150000, "on_road": 1920000}
        }
    }

    result = validator.validate_api_response(
        response_result=response,
        expected_status=200,
        max_latency_ms=1000.0,
        required_fields=["model", "pricing.on_road"],
        expected_schema_keys=["model", "variant", "pricing"],
        expected_business_data={"model": "Creta"}
    )

    assert result["overall_status"] == "PASS"
    assert result["status_code"] == 200
    assert result["schema_status"] == "PASS"
    assert result["required_fields_status"] == "PASS"
    assert "API Status: 200" in result["formatted_summary"]
    assert "Schema: PASS" in result["formatted_summary"]


def test_4xx_client_error_validation(validator, assertions):
    """400 / 404 client errors are validated with error structure assertions."""
    response = {
        "status_code": 404,
        "response_time_ms": 120.0,
        "is_json": True,
        "data": {
            "error": "Model not found",
            "code": "RESOURCE_NOT_FOUND",
            "status": 404
        }
    }

    status_res = assertions.assert_status_code(response["status_code"], expected=404)
    assert status_res["status"] == "PASS"

    err_res = assertions.assert_error_response(response["data"], expected_error_code="RESOURCE_NOT_FOUND")
    assert err_res["status"] == "PASS"


def test_5xx_server_error_validation(validator, assertions):
    """500 / 503 server error triggers failure against 200 expectation."""
    response = {
        "status_code": 500,
        "response_time_ms": 1500.0,
        "is_json": True,
        "data": {"error": "Internal Server Error"}
    }

    result = validator.validate_api_response(response, expected_status=200)
    assert result["overall_status"] == "FAIL"
    assert result["status_code"] == 500
    assert any("Expected status 200" in d["message"] for d in result["discrepancies"])


@patch("requests.request")
def test_timeout_handling(mock_request):
    """Request timeout is caught, sets status 408, and reports cleanly."""
    mock_request.side_effect = requests.exceptions.Timeout("Connection timed out after 5.0s")

    client = ApiClient(default_timeout=5.0)
    res = client.get("https://testingpwa1.cardekho.com/api/v1/price")

    assert res["status_code"] == 408
    assert "timed out" in res["error"]
    assert res["is_json"] is False


def test_malformed_response(validator, assertions):
    """Non-JSON or malformed payload fails schema structure assertion."""
    response = {
        "status_code": 200,
        "response_time_ms": 110.0,
        "is_json": False,
        "data": "<html><body>502 Bad Gateway</body></html>"
    }

    schema_res = assertions.assert_schema_structure(response["data"], expected_keys=["model", "price"])
    assert schema_res["status"] == "FAIL"
    assert "Malformed response" in schema_res["message"]


def test_missing_field_detection(assertions):
    """Missing required nested field is detected and flagged."""
    data = {
        "model": "Creta",
        "pricing": {"ex_showroom": 1700000}
        # missing 'pricing.rto'
    }

    res = assertions.assert_required_fields(data, required_fields=["model", "pricing.rto"])
    assert res["status"] == "FAIL"
    assert "pricing.rto" in res["missing_fields"]


def test_null_field_handling(assertions):
    """Unexpected null in non-nullable field is flagged."""
    data = {
        "model": "Creta",
        "price": None  # Unexpected null
    }

    res = assertions.assert_null_handling(data, non_nullable_fields=["model", "price"])
    assert res["status"] == "FAIL"
    assert "price" in res["null_violations"]


def test_ui_api_mismatch_detection(validator, assertions):
    """UI displaying different value than backend API fails consistency assertion."""
    api_val = "1920000"
    ui_val = "₹ 18.50 Lakh"

    res = assertions.assert_ui_api_consistency(api_val, ui_val, field_name="on_road_price")
    assert res["status"] == "FAIL"
    assert "UI/API mismatch" in res["message"]

    # Conversely, matching normalized currency passes
    ui_match = "₹ 19.20 Lakh"
    res_match = assertions.assert_ui_api_consistency("19.20", ui_match, field_name="on_road_price")
    assert res_match["status"] == "PASS"


def test_conditional_execution_rules():
    """API testing runs conditionally; bypassed for UI-only and triggered for API/pricing."""
    # UI-only ticket: bypassed
    should_run, reason = ApiValidator.should_execute_api_testing(
        ticket_data={"summary": "Change button color", "description": "Update button styling from blue to orange"},
        risk_profile={"is_ui_only": True}
    )
    assert should_run is False
    assert "Bypassed" in reason

    # API endpoint ticket: triggered
    should_run_api, reason_api = ApiValidator.should_execute_api_testing(
        ticket_data={"summary": "Update /api/v1/price endpoint schema", "description": "Change RTO payload format"}
    )
    assert should_run_api is True
    assert "Triggered" in reason_api

    # Pricing calculation ticket: triggered
    should_run_data, reason_data = ApiValidator.should_execute_api_testing(
        ticket_data={"summary": "Fix On Road Price calculation for Creta", "description": "Ensure accurate tax calculation"}
    )
    assert should_run_data is True
    assert "Triggered" in reason_data


def test_evidence_capture_redaction(evidence_capture):
    """Evidence is stored with ticket context and redacts sensitive tokens and passwords."""
    validation_res = {
        "overall_status": "PASS",
        "schema_status": "PASS",
        "required_fields_status": "PASS",
        "ui_api_data_match": "PASS",
        "formatted_summary": "API Status: 200\nResponse Time: 342 ms"
    }

    record = evidence_capture.record_evidence(
        jira_ticket="MB2C-7777",
        test_case="TC-01",
        endpoint="https://testingpwa1.cardekho.com/api/v1/auth/login",
        status_code=200,
        response_time_ms=342.0,
        validation_result=validation_res,
        request_headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsIn...", "User-Agent": "MobileApp"},
        request_payload={"username": "qa_user", "password": "SuperSecretPassword123!", "otp": "999999"}
    )

    assert record["jira_ticket"] == "MB2C-7777"
    assert record["test_case"] == "TC-01"
    assert record["status_code"] == 200
    assert record["is_sanitized"] is True

    # Validate strict redaction
    assert record["sanitized_request_headers"]["Authorization"] == "[REDACTED_SECRET]"
    assert record["sanitized_request_payload"]["password"] == "[REDACTED_SECRET]"
    assert record["sanitized_request_payload"]["otp"] == "[REDACTED_SECRET]"
    assert record["sanitized_request_payload"]["username"] == "qa_user"

    # Validate retrieval
    retrieved = evidence_capture.get_evidence_for_ticket("MB2C-7777")
    assert len(retrieved) == 1
    assert retrieved[0]["endpoint"] == "https://testingpwa1.cardekho.com/api/v1/auth/login"
