"""
Flaky Test Detector for CarDekho & BikeDekho QA Orchestrator.
Tracks repeated scenario execution across runs (e.g. PASS -> PASS -> FAIL -> PASS -> FAIL).
Classifies intermittent failures as potentially flaky rather than immediately treating
them as product defects. Enforces a reproducibility requirement before defect confirmation.
"""

import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime
from .memory_manager import MemoryManager

logger = logging.getLogger(__name__)

class FlakyStatus(str, Enum):
    STABLE_PASS = "STABLE_PASS"
    STABLE_FAIL = "STABLE_FAIL"
    POTENTIALLY_FLAKY = "POTENTIALLY_FLAKY"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"

class TestExecutionRecord:
    def __init__(
        self,
        test_case_id: str,
        verdict: str,
        ticket: Optional[str] = None,
        environment: Optional[str] = None,
        device: Optional[str] = None,
        execution_time_ms: float = 0.0,
        error_message: Optional[str] = None,
        timestamp: Optional[str] = None
    ):
        self.test_case_id = test_case_id
        self.verdict = verdict.upper()
        self.ticket = ticket or "UNKNOWN"
        self.environment = environment or "testing"
        self.device = device or "device"
        self.execution_time_ms = execution_time_ms
        self.error_message = error_message
        self.timestamp = timestamp or datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_case_id": self.test_case_id,
            "verdict": self.verdict,
            "ticket": self.ticket,
            "environment": self.environment,
            "device": self.device,
            "execution_time_ms": self.execution_time_ms,
            "error_message": self.error_message,
            "timestamp": self.timestamp
        }

class FlakyDetector:
    """Detects and isolates flaky tests using run history and transitions."""

    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        self.memory_manager = memory_manager or MemoryManager()

    def record_execution(
        self,
        test_case_id: str,
        verdict: str,
        ticket: Optional[str] = None,
        environment: Optional[str] = None,
        device: Optional[str] = None,
        execution_time_ms: float = 0.0,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Appends execution record to runtime history and returns flakiness analysis."""
        rec = TestExecutionRecord(
            test_case_id=test_case_id,
            verdict=verdict,
            ticket=ticket,
            environment=environment,
            device=device,
            execution_time_ms=execution_time_ms,
            error_message=error_message
        )
        self.memory_manager.append_execution_history(rec.to_dict())
        return self.analyze_scenario(test_case_id)

    def analyze_scenario(self, test_case_id: str, window: int = 10) -> Dict[str, Any]:
        """
        Analyzes the last `window` runs for the test case to detect flakiness.
        Calculates pass/fail transition frequency.
        """
        history = self.memory_manager.get_execution_history()
        records = [r for r in history if r.get("test_case_id") == test_case_id]

        if not records:
            return {
                "test_case_id": test_case_id,
                "status": FlakyStatus.INSUFFICIENT_HISTORY.value,
                "flakiness_score": 0.0,
                "total_runs": 0,
                "verdict_sequence": [],
                "recommendation": "No historical data available."
            }

        recent = records[-window:]
        verdicts = [r.get("verdict", "").upper() for r in recent]
        total_runs = len(verdicts)

        if total_runs < 2:
            return {
                "test_case_id": test_case_id,
                "status": FlakyStatus.INSUFFICIENT_HISTORY.value,
                "flakiness_score": 0.0,
                "total_runs": total_runs,
                "verdict_sequence": verdicts,
                "recommendation": "Collect more runs to evaluate flakiness."
            }

        pass_count = verdicts.count("PASS")
        fail_count = verdicts.count("FAIL")

        # Count state transitions (e.g. PASS->FAIL or FAIL->PASS)
        transitions = 0
        for i in range(len(verdicts) - 1):
            if verdicts[i] != verdicts[i + 1]:
                transitions += 1

        # Evaluate flakiness
        if pass_count > 0 and fail_count > 0 and transitions >= 1:
            # Score scaled by transition rate
            score = round(min(1.0, (transitions / (total_runs - 1)) * 1.2), 2)
            status = FlakyStatus.POTENTIALLY_FLAKY
            recommendation = (
                f"Scenario shows intermittent results ({pass_count} PASS, {fail_count} FAIL, {transitions} flips). "
                "Classified as POTENTIALLY FLAKY. Require reproducibility before defect classification."
            )
        elif fail_count == total_runs:
            score = 0.0
            status = FlakyStatus.STABLE_FAIL
            recommendation = "Consistently failing across all runs. Confirmed reproducible failure."
        else:
            score = 0.0
            status = FlakyStatus.STABLE_PASS
            recommendation = "Consistently passing across all recent runs."

        return {
            "test_case_id": test_case_id,
            "status": status.value,
            "flakiness_score": score,
            "total_runs": total_runs,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "transitions": transitions,
            "verdict_sequence": verdicts,
            "recommendation": recommendation
        }

    def evaluate_reproducibility(
        self,
        test_case_id: str,
        consecutive_retry_verdicts: List[str]
    ) -> Dict[str, Any]:
        """
        Evaluates reproducibility requirement before defect creation.
        If all retry verdicts are FAIL, it is a confirmed reproducible defect.
        If retry results alternate or pass, it is classified as a flaky scenario.
        """
        clean_retries = [v.upper().strip() for v in consecutive_retry_verdicts]
        if not clean_retries:
            return {
                "is_reproducible": False,
                "classification": "UNCONFIRMED",
                "reason": "No retry verdicts provided."
            }

        all_failed = all(v == "FAIL" for v in clean_retries)
        any_passed = any(v == "PASS" for v in clean_retries)

        if all_failed and len(clean_retries) >= 2:
            return {
                "is_reproducible": True,
                "classification": "REPRODUCIBLE_DEFECT",
                "reason": f"Failure reproduced consistently in {len(clean_retries)}/{len(clean_retries)} retry attempts.",
                "action": "Proceed with standard defect card generation."
            }
        elif any_passed:
            return {
                "is_reproducible": False,
                "classification": "FLAKY_SCENARIO",
                "reason": f"Failure did not consistently reproduce ({clean_retries.count('PASS')} PASS out of {len(clean_retries)} retries).",
                "action": "Mark scenario as FLAKY. Do NOT file immediate product bug."
            }
        else:
            return {
                "is_reproducible": False,
                "classification": "INSUFFICIENT_RETRIES",
                "reason": "At least 2 consecutive retry runs required to confirm reproducibility.",
                "action": "Perform additional retry run."
            }
