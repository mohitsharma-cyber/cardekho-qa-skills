"""
API Evidence Capture & Storage Engine for Jira AI QA Orchestrator.
Records structured API execution evidence mapped to Jira tickets and test cases.
Enforces strict redaction of sensitive credentials, tokens, and PII.
"""

import time
import os
import json
from typing import Dict, Any, List, Optional
from .network_capture import NetworkCapture

EVIDENCE_FILE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reports")

class ApiEvidenceCapture:
    """Manages sanitized API evidence logs for Jira tickets and test runs."""

    def __init__(self, evidence_dir: Optional[str] = None):
        self.evidence_dir = evidence_dir or EVIDENCE_FILE_DIR
        self.redactor = NetworkCapture()
        self.evidence_records: List[Dict[str, Any]] = []

    def record_evidence(
        self,
        jira_ticket: str,
        test_case: str,
        endpoint: str,
        status_code: int,
        response_time_ms: float,
        validation_result: Dict[str, Any],
        request_headers: Optional[Dict[str, str]] = None,
        request_payload: Optional[Any] = None,
        response_payload: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Creates and stores a sanitized API test record:
        - Jira ticket
        - test case
        - endpoint
        - timestamp
        - status
        - response time
        - validation result
        Does NOT log sensitive tokens or passwords.
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # Strict redaction
        clean_headers = self.redactor.redact_data(request_headers) if request_headers else {}
        clean_req = self.redactor.redact_data(request_payload) if request_payload else None
        clean_resp = self.redactor.redact_data(response_payload) if response_payload else None

        record = {
            "jira_ticket": jira_ticket,
            "test_case": test_case,
            "endpoint": endpoint,
            "timestamp": timestamp,
            "status_code": status_code,
            "response_time_ms": round(response_time_ms, 2),
            "validation_result": {
                "overall_status": validation_result.get("overall_status", "N/A"),
                "schema_status": validation_result.get("schema_status", "N/A"),
                "required_fields_status": validation_result.get("required_fields_status", "N/A"),
                "ui_api_data_match": validation_result.get("ui_api_data_match", "N/A"),
                "formatted_summary": validation_result.get("formatted_summary", "")
            },
            "sanitized_request_headers": clean_headers,
            "sanitized_request_payload": clean_req,
            "sanitized_response_payload": clean_resp,
            "is_sanitized": True
        }

        self.evidence_records.append(record)
        self._persist_evidence()
        return record

    def get_evidence_for_ticket(self, jira_ticket: str) -> List[Dict[str, Any]]:
        """Retrieves all API evidence entries for a specific Jira ticket."""
        return [r for r in self.evidence_records if r.get("jira_ticket") == jira_ticket]

    def _persist_evidence(self):
        try:
            os.makedirs(self.evidence_dir, exist_ok=True)
            file_path = os.path.join(self.evidence_dir, "api_evidence.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.evidence_records, f, indent=2)
        except Exception as e:
            print(f"[WARN] Failed to persist API evidence: {e}")
