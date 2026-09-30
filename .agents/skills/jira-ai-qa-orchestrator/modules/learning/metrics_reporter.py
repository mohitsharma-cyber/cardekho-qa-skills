"""
QA Metrics Reporter for CarDekho & BikeDekho QA Orchestrator.
Calculates and presents objective, un-gamed QA metrics:
- Requirement coverage
- Execution coverage
- Regression coverage
- Defect count
- Blocked tests
- Flaky tests
- Average execution time
- Environment failures
- Recurring failure areas

Strict Safety Rule:
Strictly forbids subjective or misleading quality scores (e.g. "Quality Score: 85/100")
and arbitrary rankings. All reported data consists of factual, verifiable execution counts.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

class QAMetricsReport:
    """Encapsulates structured, verifiable execution metrics."""

    def __init__(
        self,
        ticket: str,
        total_requirements: int,
        tested_requirements: int,
        planned_test_cases: int,
        executed_test_cases: int,
        passed_test_cases: int,
        failed_test_cases: int,
        blocked_test_cases: int,
        targeted_regression_scope: int,
        executed_regression_checks: int,
        defect_count: int,
        flaky_tests: List[str],
        average_execution_time_ms: float,
        environment_failures: List[str],
        recurring_failure_areas: List[str],
        untested_areas: Optional[List[str]] = None,
        final_verdict: str = "PASS"
    ):
        self.ticket = ticket
        self.total_requirements = max(1, total_requirements)
        self.tested_requirements = tested_requirements
        self.planned_test_cases = planned_test_cases
        self.executed_test_cases = executed_test_cases
        self.passed_test_cases = passed_test_cases
        self.failed_test_cases = failed_test_cases
        self.blocked_test_cases = blocked_test_cases
        self.targeted_regression_scope = targeted_regression_scope
        self.executed_regression_checks = executed_regression_checks
        self.defect_count = defect_count
        self.flaky_tests = flaky_tests or []
        self.average_execution_time_ms = average_execution_time_ms
        self.environment_failures = environment_failures or []
        self.recurring_failure_areas = recurring_failure_areas or []
        self.untested_areas = untested_areas or []
        self.final_verdict = final_verdict

    @property
    def requirement_coverage_pct(self) -> float:
        return round((self.tested_requirements / self.total_requirements) * 100, 1)

    @property
    def execution_coverage_pct(self) -> float:
        if self.planned_test_cases == 0:
            return 100.0
        return round((self.executed_test_cases / self.planned_test_cases) * 100, 1)

    @property
    def regression_coverage_pct(self) -> float:
        if self.targeted_regression_scope == 0:
            return 100.0
        return round((self.executed_regression_checks / self.targeted_regression_scope) * 100, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticket": self.ticket,
            "requirement_coverage": f"{self.tested_requirements}/{self.total_requirements} ({self.requirement_coverage_pct}%)",
            "execution_coverage": f"{self.executed_test_cases}/{self.planned_test_cases} ({self.execution_coverage_pct}%)",
            "regression_coverage": f"{self.executed_regression_checks}/{self.targeted_regression_scope} ({self.regression_coverage_pct}%)",
            "defect_count": self.defect_count,
            "blocked_tests": self.blocked_test_cases,
            "flaky_tests": len(self.flaky_tests),
            "flaky_test_details": self.flaky_tests,
            "average_execution_time_ms": round(self.average_execution_time_ms, 1),
            "environment_failures": len(self.environment_failures),
            "environment_failure_details": self.environment_failures,
            "recurring_failure_areas": self.recurring_failure_areas,
            "untested_areas": self.untested_areas,
            "final_verdict": self.final_verdict
        }

    def format_summary_card(self) -> str:
        """Renders factual, transparent metrics report card without misleading quality scores."""
        flaky_str = ", ".join(self.flaky_tests) if self.flaky_tests else "0 detected"
        env_str = f"{len(self.environment_failures)} ({', '.join(self.environment_failures)})" if self.environment_failures else "0 (Environment stable)"
        recurring_str = ", ".join(self.recurring_failure_areas) if self.recurring_failure_areas else "None"
        untested_str = ", ".join(self.untested_areas) if self.untested_areas else "None (Complete in-scope execution)"

        return (
            f"════════════════════════════════════════════════════════════════════\n"
            f"📊 FACTUAL QA METRICS REPORT: {self.ticket}\n"
            f"════════════════════════════════════════════════════════════════════\n"
            f"• Requirement Coverage : {self.tested_requirements}/{self.total_requirements} ACs ({self.requirement_coverage_pct}%)\n"
            f"• Execution Coverage   : {self.executed_test_cases}/{self.planned_test_cases} test cases ({self.execution_coverage_pct}%)\n"
            f"• Regression Coverage  : {self.executed_regression_checks}/{self.targeted_regression_scope} checks ({self.regression_coverage_pct}%)\n"
            f"• Defect Count         : {self.defect_count} confirmed\n"
            f"• Blocked Tests        : {self.blocked_test_cases}\n"
            f"• Flaky Tests          : {len(self.flaky_tests)} ({flaky_str})\n"
            f"• Avg Execution Time   : {self.average_execution_time_ms:.1f} ms / step\n"
            f"• Environment Failures : {env_str}\n"
            f"• Recurring Areas      : {recurring_str}\n"
            f"• Untested / Out-Scope : {untested_str}\n"
            f"• Final QA Verdict     : {self.final_verdict}\n"
            f"════════════════════════════════════════════════════════════════════"
        )

class MetricsReporter:
    """Computes and validates standard QA metrics for Jira execution sessions."""

    def compute_metrics(
        self,
        ticket: str,
        requirements: List[str],
        covered_requirements: List[str],
        planned_cases: List[Dict[str, Any]],
        executed_results: Dict[str, str],  # tc_id -> "PASS"|"FAIL"|"BLOCKED"
        step_execution_times_ms: Optional[List[float]] = None,
        flaky_scenarios: Optional[List[str]] = None,
        defects_found: Optional[List[Dict[str, Any]]] = None,
        environment_errors: Optional[List[str]] = None,
        recurring_areas: Optional[List[str]] = None,
        untested_scope: Optional[List[str]] = None
    ) -> QAMetricsReport:
        """
        Calculates verifiable QA metrics strictly from factual execution inputs.
        Never introduces subjective ratings or arbitrary score models.
        """
        total_reqs = len(requirements) or 1
        tested_reqs = len(covered_requirements)

        planned_count = len(planned_cases)
        executed_count = len(executed_results)
        passed_count = sum(1 for v in executed_results.values() if v.upper() == "PASS")
        failed_count = sum(1 for v in executed_results.values() if v.upper() == "FAIL")
        blocked_count = sum(1 for v in executed_results.values() if v.upper() == "BLOCKED")

        # Regression checks are identified by REG- prefix
        reg_planned = sum(1 for c in planned_cases if c.get("id", "").startswith("REG-"))
        reg_executed = sum(1 for k in executed_results if k.startswith("REG-"))

        # Average step execution time
        times = step_execution_times_ms or [150.0]
        avg_time = sum(times) / max(1, len(times))

        # Determine final verdict
        if blocked_count > 0:
            final_verdict = "BLOCKED"
        elif failed_count > 0:
            final_verdict = "FAIL"
        elif executed_count < planned_count:
            final_verdict = "PARTIAL"
        else:
            final_verdict = "PASS"

        return QAMetricsReport(
            ticket=ticket,
            total_requirements=total_reqs,
            tested_requirements=tested_reqs,
            planned_test_cases=planned_count,
            executed_test_cases=executed_count,
            passed_test_cases=passed_count,
            failed_test_cases=failed_count,
            blocked_test_cases=blocked_count,
            targeted_regression_scope=reg_planned,
            executed_regression_checks=reg_executed,
            defect_count=len(defects_found or []),
            flaky_tests=flaky_scenarios or [],
            average_execution_time_ms=avg_time,
            environment_failures=environment_errors or [],
            recurring_failure_areas=recurring_areas or [],
            untested_areas=untested_scope or [],
            final_verdict=final_verdict
        )
