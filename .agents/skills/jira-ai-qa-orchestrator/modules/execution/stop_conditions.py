"""
Execution Stop Conditions Engine for Jira AI QA Orchestrator.
Intercepts critical execution blockers (build missing, install failed, app launch failed,
environment unreachable, device disconnected).
Immediately halts dependent execution, marks affected scenarios BLOCKED,
and strictly prevents any blocked test from being converted to PASS.
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Tuple

class StopReason(str, Enum):
    BUILD_UNAVAILABLE = "BUILD_UNAVAILABLE"
    INSTALLATION_FAILED = "INSTALLATION_FAILED"
    APP_LAUNCH_FAILED = "APP_LAUNCH_FAILED"
    ENVIRONMENT_UNAVAILABLE = "ENVIRONMENT_UNAVAILABLE"
    CRITICAL_DEPENDENCY_UNAVAILABLE = "CRITICAL_DEPENDENCY_UNAVAILABLE"
    DEVICE_DISCONNECTED = "DEVICE_DISCONNECTED"

class StopConditionTriggered(Exception):
    """Raised when an unrecoverable pre-execution or runtime condition halts testing."""
    def __init__(self, reason: StopReason, message: str, evidence: Optional[str] = None):
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.evidence = evidence

class StopConditionManager:
    """Manages pre-flight health gates and cascades BLOCKED status across dependent tests."""

    def __init__(self):
        self.active_stop: Optional[StopReason] = None
        self.stop_details: Optional[str] = None
        self.evidence_path: Optional[str] = None

    def evaluate_preflight(
        self,
        device_connected: bool,
        build_available: bool,
        app_installed: bool,
        app_launch_ok: bool,
        env_reachable: bool
    ) -> Tuple[bool, Optional[StopReason], Optional[str]]:
        """
        Evaluates essential pre-requisites in strict priority order.
        Returns (is_ok, reason, message).
        """
        if not device_connected:
            return False, StopReason.DEVICE_DISCONNECTED, "No physical Android device authorized/connected via ADB."
        if not build_available:
            return False, StopReason.BUILD_UNAVAILABLE, "Target Jenkins build or APK artifact is not available/failed deployment."
        if not app_installed:
            return False, StopReason.INSTALLATION_FAILED, "Target application package is not installed on the device."
        if not app_launch_ok:
            return False, StopReason.APP_LAUNCH_FAILED, "Target application failed to launch or crashed on startup."
        if not env_reachable:
            return False, StopReason.ENVIRONMENT_UNAVAILABLE, "Target server environment is unreachable or returning 5xx."

        return True, None, None

    def apply_stop_condition(
        self,
        reason: StopReason,
        message: str,
        test_cases: List[Dict[str, Any]],
        evidence: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Marks all dependent test cases as BLOCKED.
        Guarantees that blocked tests are NEVER converted into PASS.
        """
        self.active_stop = reason
        self.stop_details = message
        self.evidence_path = evidence

        blocked_cases = []
        for tc in test_cases:
            case_copy = dict(tc)
            # Enforce permanent BLOCKED status
            case_copy["status"] = "BLOCKED"
            case_copy["block_reason"] = reason.value
            case_copy["block_message"] = message
            case_copy["evidence"] = evidence
            blocked_cases.append(case_copy)

        return blocked_cases

    def can_transition_to_pass(self, current_status: str) -> bool:
        """
        Strict safety gate:
        BLOCKED tests can NEVER be transitioned directly to PASS.
        """
        if current_status == "BLOCKED":
            return False
        return True

    def get_stop_summary(self) -> Dict[str, Any]:
        """Returns structured stop condition telemetry for QA reporting."""
        return {
            "has_stopped": self.active_stop is not None,
            "stop_reason": self.active_stop.value if self.active_stop else None,
            "message": self.stop_details,
            "evidence": self.evidence_path
        }
