"""
Coverage Engine for Jira AI QA Orchestrator.
Independently tracks:
1. Requirement Coverage
2. Test Execution Coverage
3. Targeted Regression Coverage

Statuses: PASS, FAIL, BLOCKED, NOT_TESTED, NOT_APPLICABLE.
Enforces the Zero False-100% Coverage Mandate:
Never claims 100% coverage merely because a subset of generated tests passed.
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Set

class TestStatus(str, Enum):
    __test__ = False
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_TESTED = "NOT_TESTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"

class CoverageEngine:
    """Calculates granular, un-inflated test metrics across requirements, executions, and regression."""

    def __init__(self):
        self.requirements: Dict[str, Dict[str, Any]] = {}
        self.test_cases: Dict[str, Dict[str, Any]] = {}
        self.regression_scenarios: Dict[str, Dict[str, Any]] = {}
        self.attack_surfaces: Dict[str, Dict[str, Any]] = {}

    def add_requirement(self, req_id: str, description: str, category: str = "functional"):
        self.requirements[req_id] = {
            "id": req_id,
            "description": description,
            "category": category,
            "mapped_tests": [],
            "status": TestStatus.NOT_TESTED
        }

    def register_attack_surface(self, surface_id: str, priority: str = "P1", description: str = ""):
        if surface_id not in self.attack_surfaces:
            self.attack_surfaces[surface_id] = {
                "id": surface_id,
                "priority": priority,
                "description": description,
                "mapped_tests": [],
                "status": TestStatus.NOT_TESTED
            }

    def register_test_case(
        self,
        tc_id: str,
        name: str,
        tc_type: str = "functional",
        mapped_req_ids: Optional[List[str]] = None,
        attack_surface: Optional[str] = None,
        category: Optional[str] = None
    ):
        mapped_req_ids = mapped_req_ids or []
        self.test_cases[tc_id] = {
            "id": tc_id,
            "name": name,
            "type": tc_type,
            "category": category,
            "attack_surface": attack_surface,
            "mapped_requirements": mapped_req_ids,
            "status": TestStatus.NOT_TESTED,
            "evidence": None,
            "error": None
        }
        for req_id in mapped_req_ids:
            if req_id in self.requirements:
                if tc_id not in self.requirements[req_id]["mapped_tests"]:
                    self.requirements[req_id]["mapped_tests"].append(tc_id)

        if attack_surface:
            if attack_surface not in self.attack_surfaces:
                self.register_attack_surface(attack_surface)
            if tc_id not in self.attack_surfaces[attack_surface]["mapped_tests"]:
                self.attack_surfaces[attack_surface]["mapped_tests"].append(tc_id)


    def register_regression_scenario(self, scenario_id: str, target_area: str, rationale: str = ""):
        self.regression_scenarios[scenario_id] = {
            "id": scenario_id,
            "target_area": target_area,
            "rationale": rationale,
            "status": TestStatus.NOT_TESTED,
            "evidence": None
        }

    def record_test_result(
        self,
        tc_id: str,
        status: TestStatus,
        evidence: Optional[str] = None,
        error: Optional[str] = None
    ):
        if tc_id not in self.test_cases:
            self.register_test_case(tc_id, name=tc_id)

        self.test_cases[tc_id]["status"] = status
        self.test_cases[tc_id]["evidence"] = evidence
        self.test_cases[tc_id]["error"] = error

        # Propagate status to mapped requirements
        for req_id in self.test_cases[tc_id]["mapped_requirements"]:
            self._recalculate_requirement_status(req_id)

        # Propagate status to mapped attack surface
        surface_id = self.test_cases[tc_id].get("attack_surface")
        if surface_id:
            self._recalculate_attack_surface_status(surface_id)


    def record_regression_result(self, scenario_id: str, status: TestStatus, evidence: Optional[str] = None):
        if scenario_id in self.regression_scenarios:
            self.regression_scenarios[scenario_id]["status"] = status
            self.regression_scenarios[scenario_id]["evidence"] = evidence

    def _recalculate_requirement_status(self, req_id: str):
        req = self.requirements.get(req_id)
        if not req:
            return

        mapped_tc_ids = req["mapped_tests"]
        if not mapped_tc_ids:
            req["status"] = TestStatus.NOT_TESTED
            return

        statuses = [self.test_cases[tid]["status"] for tid in mapped_tc_ids if tid in self.test_cases]
        if not statuses:
            req["status"] = TestStatus.NOT_TESTED
        elif any(s == TestStatus.FAIL for s in statuses):
            req["status"] = TestStatus.FAIL
        elif any(s == TestStatus.BLOCKED for s in statuses):
            req["status"] = TestStatus.BLOCKED
        elif any(s == TestStatus.NOT_TESTED for s in statuses):
            req["status"] = TestStatus.NOT_TESTED
        elif all(s == TestStatus.PASS for s in statuses):
            req["status"] = TestStatus.PASS
        elif all(s == TestStatus.NOT_APPLICABLE for s in statuses):
            req["status"] = TestStatus.NOT_APPLICABLE
        else:
            req["status"] = TestStatus.NOT_TESTED

    def _recalculate_attack_surface_status(self, surface_id: str):
        surface = self.attack_surfaces.get(surface_id)
        if not surface:
            return

        mapped_tc_ids = surface["mapped_tests"]
        if not mapped_tc_ids:
            surface["status"] = TestStatus.NOT_TESTED
            return

        statuses = [self.test_cases[tid]["status"] for tid in mapped_tc_ids if tid in self.test_cases]
        if not statuses:
            surface["status"] = TestStatus.NOT_TESTED
        elif any(s == TestStatus.FAIL for s in statuses):
            surface["status"] = TestStatus.FAIL
        elif any(s == TestStatus.BLOCKED for s in statuses):
            surface["status"] = TestStatus.BLOCKED
        elif any(s == TestStatus.NOT_TESTED for s in statuses):
            surface["status"] = TestStatus.NOT_TESTED
        elif all(s == TestStatus.PASS for s in statuses):
            surface["status"] = TestStatus.PASS
        elif all(s == TestStatus.NOT_APPLICABLE for s in statuses):
            surface["status"] = TestStatus.NOT_APPLICABLE
        else:
            surface["status"] = TestStatus.NOT_TESTED

    def get_requirement_coverage(self) -> Dict[str, Any]:

        total = len(self.requirements)
        if total == 0:
            return {
                "total": 0, "mapped": 0, "verified": 0, "failed": 0,
                "blocked": 0, "not_tested": 0, "percentage": 0.0
            }

        verified = sum(1 for r in self.requirements.values() if r["status"] == TestStatus.PASS)
        failed = sum(1 for r in self.requirements.values() if r["status"] == TestStatus.FAIL)
        blocked = sum(1 for r in self.requirements.values() if r["status"] == TestStatus.BLOCKED)
        not_tested = sum(1 for r in self.requirements.values() if r["status"] == TestStatus.NOT_TESTED)
        mapped = sum(1 for r in self.requirements.values() if len(r["mapped_tests"]) > 0)

        # Verified requirement percentage
        percentage = round((verified / total) * 100.0, 2)

        return {
            "total": total,
            "mapped": mapped,
            "verified": verified,
            "failed": failed,
            "blocked": blocked,
            "not_tested": not_tested,
            "percentage": percentage
        }

    def get_execution_coverage(self) -> Dict[str, Any]:
        total = len(self.test_cases)
        if total == 0:
            return {
                "total_planned": 0, "executed": 0, "passed": 0, "failed": 0,
                "blocked": 0, "not_tested": 0, "not_applicable": 0, "percentage": 0.0
            }

        passed = sum(1 for tc in self.test_cases.values() if tc["status"] == TestStatus.PASS)
        failed = sum(1 for tc in self.test_cases.values() if tc["status"] == TestStatus.FAIL)
        blocked = sum(1 for tc in self.test_cases.values() if tc["status"] == TestStatus.BLOCKED)
        na = sum(1 for tc in self.test_cases.values() if tc["status"] == TestStatus.NOT_APPLICABLE)
        not_tested = sum(1 for tc in self.test_cases.values() if tc["status"] == TestStatus.NOT_TESTED)

        executed = passed + failed + blocked
        percentage = round((executed / total) * 100.0, 2)

        return {
            "total_planned": total,
            "executed": executed,
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
            "not_tested": not_tested,
            "not_applicable": na,
            "percentage": percentage
        }

    def get_regression_coverage(self) -> Dict[str, Any]:
        total = len(self.regression_scenarios)
        if total == 0:
            return {
                "total_planned": 0, "executed": 0, "passed": 0, "failed": 0,
                "blocked": 0, "percentage": 100.0 if not total else 0.0
            }

        passed = sum(1 for r in self.regression_scenarios.values() if r["status"] == TestStatus.PASS)
        failed = sum(1 for r in self.regression_scenarios.values() if r["status"] == TestStatus.FAIL)
        blocked = sum(1 for r in self.regression_scenarios.values() if r["status"] == TestStatus.BLOCKED)
        executed = passed + failed + blocked
        percentage = round((executed / total) * 100.0, 2)

        return {
            "total_planned": total,
            "executed": executed,
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
            "percentage": percentage
        }

    def get_risk_coverage(self) -> Dict[str, Any]:
        """Calculates coverage across identified attack surfaces."""
        total = len(self.attack_surfaces)
        if total == 0:
            return {
                "total": 0, "covered": 0, "verified": 0, "failed": 0,
                "blocked": 0, "not_tested": 0, "percentage": 100.0
            }

        verified = sum(1 for s in self.attack_surfaces.values() if s["status"] == TestStatus.PASS)
        failed = sum(1 for s in self.attack_surfaces.values() if s["status"] == TestStatus.FAIL)
        blocked = sum(1 for s in self.attack_surfaces.values() if s["status"] == TestStatus.BLOCKED)
        not_tested = sum(1 for s in self.attack_surfaces.values() if s["status"] == TestStatus.NOT_TESTED)
        covered = sum(1 for s in self.attack_surfaces.values() if len(s["mapped_tests"]) > 0)

        percentage = round((verified / total) * 100.0, 2)

        return {
            "total": total,
            "covered": covered,
            "verified": verified,
            "failed": failed,
            "blocked": blocked,
            "not_tested": not_tested,
            "percentage": percentage
        }

    def get_negative_boundary_coverage(self) -> Dict[str, Any]:
        """Calculates coverage for negative, boundary, rapid actions, and breaking scenarios."""
        breaking_types = {"negative", "boundary", "breaking", "error", "security"}
        breaking_categories = {
            "negative_boundary", "rapid_actions_debounce",
            "data_payload_anomalies", "api_failure_simulation", "device_system_interrupts"
        }
        breaking_tcs = [
            tc for tc in self.test_cases.values()
            if (tc.get("type", "").lower() in breaking_types or
                (tc.get("category") and tc.get("category", "").lower() in breaking_categories) or
                tc.get("attack_surface") is not None)
        ]
        total = len(breaking_tcs)
        if total == 0:
            return {
                "total_planned": 0, "executed": 0, "passed": 0, "failed": 0,
                "blocked": 0, "percentage": 100.0
            }

        passed = sum(1 for tc in breaking_tcs if tc["status"] == TestStatus.PASS)
        failed = sum(1 for tc in breaking_tcs if tc["status"] == TestStatus.FAIL)
        blocked = sum(1 for tc in breaking_tcs if tc["status"] == TestStatus.BLOCKED)
        executed = passed + failed + blocked
        percentage = round((executed / total) * 100.0, 2)

        return {
            "total_planned": total,
            "executed": executed,
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
            "percentage": percentage
        }

    def evaluate_signoff_claim(self) -> Dict[str, Any]:
        """
        Enforces the honest metrics rule:
        Never claims 100% coverage unless:
        - Requirement Coverage == 100%
        - Execution Coverage == 100%
        - Regression Coverage == 100%
        - Risk / Attack Surface Coverage == 100%
        - Negative & Boundary Coverage == 100%
        - Zero BLOCKED, zero FAILED, zero NOT_TESTED.
        """
        req_cov = self.get_requirement_coverage()
        exec_cov = self.get_execution_coverage()
        reg_cov = self.get_regression_coverage()
        risk_cov = self.get_risk_coverage()
        neg_cov = self.get_negative_boundary_coverage()

        has_failures = exec_cov["failed"] > 0 or req_cov["failed"] > 0 or reg_cov["failed"] > 0 or risk_cov["failed"] > 0 or neg_cov["failed"] > 0
        has_blocked = exec_cov["blocked"] > 0 or req_cov["blocked"] > 0 or reg_cov["blocked"] > 0 or risk_cov["blocked"] > 0 or neg_cov["blocked"] > 0
        has_untested = exec_cov["not_tested"] > 0 or req_cov["not_tested"] > 0 or (risk_cov["total"] > 0 and risk_cov["not_tested"] > 0)

        # Can claim 100% ONLY if everything executed and passed
        is_full_coverage = (
            req_cov["percentage"] == 100.0 and
            exec_cov["percentage"] == 100.0 and
            (reg_cov["total_planned"] == 0 or reg_cov["percentage"] == 100.0) and
            (risk_cov["total"] == 0 or risk_cov["percentage"] == 100.0) and
            (neg_cov["total_planned"] == 0 or neg_cov["percentage"] == 100.0) and
            not has_failures and
            not has_blocked and
            not has_untested
        )

        final_verdict = "PASS"
        if has_failures:
            final_verdict = "FAIL"
        elif has_blocked:
            final_verdict = "BLOCKED"
        elif has_untested or not is_full_coverage:
            final_verdict = "PARTIAL"

        return {
            "is_full_coverage": is_full_coverage,
            "final_verdict": final_verdict,
            "requirement_coverage": req_cov,
            "execution_coverage": exec_cov,
            "regression_coverage": reg_cov,
            "risk_coverage": risk_cov,
            "negative_boundary_coverage": neg_cov,
            "untested_requirements": [r["id"] for r in self.requirements.values() if r["status"] == TestStatus.NOT_TESTED],
            "blocked_scenarios": [tc["id"] for tc in self.test_cases.values() if tc["status"] == TestStatus.BLOCKED]
        }

