"""
Evidence Manager for Jira AI QA Orchestrator.
Central orchestrator for all 4 evidence types:
1. screenshot
2. logcat
3. api_response
4. execution_log

Every evidence item maintains full traceability:
- ticket
- test case
- step
- timestamp
- device
- Android version
- build
- environment
- result

Enforces mandatory capture for:
- failures
- blockers
- defects
- important assertions
While strictly suppressing redundant screenshots during fast-mode routine traversal.
"""

import os
import json
import time
from typing import Dict, Any, List, Optional
from .screenshot_manager import ScreenshotManager
from .log_manager import LogManager
from ..api.network_capture import NetworkCapture

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reports", "evidence")

class EvidenceManager:
    """Manages creation, aggregation, and querying of test execution evidence."""

    def __init__(self, evidence_dir: Optional[str] = None):
        self.evidence_dir = evidence_dir or REPORTS_DIR
        self.screenshot_mgr = ScreenshotManager(os.path.join(self.evidence_dir, "screenshots"))
        self.log_mgr = LogManager(os.path.join(self.evidence_dir, "logs"))
        self.redactor = NetworkCapture()
        self.evidence_store: List[Dict[str, Any]] = []

    def record_screenshot(
        self,
        ticket: str,
        test_case: str,
        step: str,
        device: str,
        android_version: str,
        build: str,
        environment: str,
        result: str,
        is_fast_mode: bool = False,
        is_mandatory: bool = False,
        adb_serial: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Records a screenshot with all 9 metadata fields."""
        item = self.screenshot_mgr.capture_screenshot(
            ticket=ticket,
            test_case=test_case,
            step=step,
            device=device,
            android_version=android_version,
            build=build,
            environment=environment,
            result=result,
            is_fast_mode=is_fast_mode,
            is_mandatory=is_mandatory,
            adb_serial=adb_serial
        )
        if item:
            self.evidence_store.append(item)
            self._save_manifest()
        return item

    def record_logcat(
        self,
        ticket: str,
        test_case: str,
        step: str,
        device: str,
        android_version: str,
        build: str,
        environment: str,
        result: str,
        adb_serial: Optional[str] = None,
        lines: int = 100
    ) -> Dict[str, Any]:
        """Records logcat buffer with all 9 metadata fields."""
        item = self.log_mgr.capture_logcat(
            ticket=ticket,
            test_case=test_case,
            step=step,
            device=device,
            android_version=android_version,
            build=build,
            environment=environment,
            result=result,
            adb_serial=adb_serial,
            lines=lines
        )
        self.evidence_store.append(item)
        self._save_manifest()
        return item

    def record_api_response(
        self,
        ticket: str,
        test_case: str,
        step: str,
        device: str,
        android_version: str,
        build: str,
        environment: str,
        result: str,
        endpoint: str,
        status_code: int,
        response_time_ms: float,
        response_payload: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Records API response telemetry with all 9 metadata fields."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        clean_resp = self.redactor.redact_data(response_payload) if response_payload else None

        item = {
            "evidence_type": "api_response",
            "ticket": ticket,
            "test_case": test_case,
            "step": step,
            "timestamp": timestamp,
            "device": device,
            "android_version": android_version,
            "build": build,
            "environment": environment,
            "result": result.upper(),
            "endpoint": endpoint,
            "status_code": status_code,
            "response_time_ms": response_time_ms,
            "sanitized_response": clean_resp,
            "is_sanitized": True
        }
        self.evidence_store.append(item)
        self._save_manifest()
        return item

    def record_execution_log(
        self,
        ticket: str,
        test_case: str,
        step: str,
        device: str,
        android_version: str,
        build: str,
        environment: str,
        result: str,
        message: str
    ) -> Dict[str, Any]:
        """Records step execution log with all 9 metadata fields."""
        item = self.log_mgr.record_execution_log(
            ticket=ticket,
            test_case=test_case,
            step=step,
            device=device,
            android_version=android_version,
            build=build,
            environment=environment,
            result=result,
            log_message=message
        )
        self.evidence_store.append(item)
        self._save_manifest()
        return item

    def capture_mandatory_failure_evidence(
        self,
        ticket: str,
        test_case: str,
        step: str,
        device: str,
        android_version: str,
        build: str,
        environment: str,
        error_message: str,
        adb_serial: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Guarantees capture of screenshot, logcat, and execution log on failure/blocker/defect.
        """
        scr = self.record_screenshot(
            ticket=ticket,
            test_case=test_case,
            step=step,
            device=device,
            android_version=android_version,
            build=build,
            environment=environment,
            result="FAIL",
            is_mandatory=True,
            adb_serial=adb_serial
        )
        logcat = self.record_logcat(
            ticket=ticket,
            test_case=test_case,
            step=step,
            device=device,
            android_version=android_version,
            build=build,
            environment=environment,
            result="FAIL",
            adb_serial=adb_serial
        )
        exec_log = self.record_execution_log(
            ticket=ticket,
            test_case=test_case,
            step=step,
            device=device,
            android_version=android_version,
            build=build,
            environment=environment,
            result="FAIL",
            message=error_message
        )
        return {
            "screenshot": scr,
            "logcat": logcat,
            "execution_log": exec_log
        }

    def get_evidence_for_ticket(self, ticket: str) -> List[Dict[str, Any]]:
        """Filters evidence items by ticket."""
        return [e for e in self.evidence_store if e.get("ticket") == ticket]

    def _save_manifest(self):
        try:
            os.makedirs(self.evidence_dir, exist_ok=True)
            manifest_path = os.path.join(self.evidence_dir, "evidence_manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(self.evidence_store, f, indent=2)
        except Exception as e:
            print(f"[WARN] Failed to save evidence manifest: {e}")
