"""
Defect Intelligence & Analysis Engine for Jira AI QA Orchestrator.
When a test failure occurs:
1. Validates failure reproduction.
2. Associates captured evidence.
3. Analyzes Probable Layer (UI, API, Backend, Data, Configuration, Environment).
4. Checks for duplicate Jira defects.
5. Generates the structured Bug Card.

CRITICAL SAFETY MANDATE:
Never create Jira Testing Bug automatically.
Always presents the Bug Card in chat and awaits explicit user approval.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from .severity_classifier import SeverityClassifier
from .duplicate_detector import DuplicateDetector

class DefectClassification(str, Enum):
    REAL_DEFECT = "REAL_DEFECT"
    EXPECTED_BEHAVIOR = "EXPECTED_BEHAVIOR"
    ENVIRONMENT_DATA_ISSUE = "ENVIRONMENT_DATA_ISSUE"
    DUPLICATE = "DUPLICATE"
    UNCONFIRMED_ISSUE = "UNCONFIRMED_ISSUE"
    BLOCKED_SCENARIO = "BLOCKED_SCENARIO"

class DefectAnalyzer:
    """Performs root-cause layer analysis, formats Bug Cards, and enforces approval gates."""

    def __init__(self, duplicate_detector: Optional[DuplicateDetector] = None):
        self.duplicate_detector = duplicate_detector or DuplicateDetector()
        self.classifier = SeverityClassifier()

    def validate_defect_reproducibility(
        self,
        failure_context: Dict[str, Any],
        retry_results: Optional[List[bool]] = None
    ) -> Dict[str, Any]:
        """
        Validates defect reproducibility to filter out transient flakes vs deterministic bugs.
        retry_results: list of booleans where True indicates failure was reproduced, False passed.
        """
        if retry_results is not None and len(retry_results) > 0:
            reproduced_count = sum(1 for r in retry_results if r)
            total_runs = len(retry_results)
            repro_rate = (reproduced_count / total_runs) * 100.0
            is_reproducible = reproduced_count >= 1
            is_deterministic = repro_rate == 100.0
        else:
            repro_rate = 100.0
            is_reproducible = True
            is_deterministic = True

        return {
            "is_reproducible": is_reproducible,
            "is_deterministic": is_deterministic,
            "reproducibility_rate": repro_rate,
            "reproducibility_label": f"{int(repro_rate)}% ({'Deterministic' if is_deterministic else 'Intermittent'})"
        }

    def analyze_failure(
        self,
        ticket: str,
        test_case_id: str,
        summary: str,
        steps: List[str],
        expected: str,
        actual: str,
        environment: str = "TESTING",
        device: str = "Connected Android Device",
        build: str = "#142",
        evidence_path: Optional[str] = None,
        error_message: str = "",
        logcat_snippet: str = "",
        api_status: Optional[int] = None,
        parent_ticket_key: Optional[str] = None,
        existing_bugs: Optional[List[Dict[str, Any]]] = None,
        attack_surface: Optional[str] = None,
        bug_target: Optional[str] = None,
        retry_results: Optional[List[bool]] = None
    ) -> Dict[str, Any]:
        """
        Executes failure analysis, identifies probable layer, validates reproducibility,
        checks duplicates, classifies defect, and generates the structured Bug Card.
        """
        # 1. Deduce Probable Layer
        probable_layer = self._determine_probable_layer(
            error_message=error_message,
            logcat_snippet=logcat_snippet,
            api_status=api_status,
            actual=actual
        )

        # 2. Determine Severity & Suggested Priority
        severity, priority_sug = self.classifier.classify(
            summary=summary,
            error_message=error_message,
            logcat_snippet=logcat_snippet,
            probable_layer=probable_layer
        )

        # 3. Check Duplicate Defects
        dup_result = self.duplicate_detector.check_duplicate(
            summary=summary,
            parent_ticket_key=parent_ticket_key or ticket,
            existing_bugs=existing_bugs
        )

        # 4. Validate Reproducibility (Stage 2: Reproduce)
        failure_ctx = {
            "test_case_id": test_case_id,
            "error_message": error_message,
            "probable_layer": probable_layer
        }
        reproducibility = self.validate_defect_reproducibility(failure_ctx, retry_results=retry_results)

        # 5. Classify Defect State (Stage 4: Classify)
        actual_lower = actual.lower().strip()
        expected_lower = expected.lower().strip()
        is_expected = (
            "expected behavior" in actual_lower or
            "as designed" in actual_lower or
            "working as intended" in actual_lower or
            (expected_lower and expected_lower == actual_lower)
        )

        if is_expected:
            classification = DefectClassification.EXPECTED_BEHAVIOR.value
        elif dup_result.get("is_duplicate", False) or dup_result.get("has_duplicate", False):
            classification = DefectClassification.DUPLICATE.value
        elif probable_layer in ["Environment", "Configuration"]:
            classification = DefectClassification.ENVIRONMENT_DATA_ISSUE.value
        elif not reproducibility["is_reproducible"]:
            classification = DefectClassification.UNCONFIRMED_ISSUE.value
        else:
            classification = DefectClassification.REAL_DEFECT.value

        # Filter out expected behavior and unconfirmed/unverified observations
        is_reportable_defect = classification in [
            DefectClassification.REAL_DEFECT.value,
            DefectClassification.ENVIRONMENT_DATA_ISSUE.value
        ]
        requires_user_approval = is_reportable_defect  # Never prompt user to log non-defects

        # 6. Format Numbered Steps
        formatted_steps = "\n".join([f"   {i+1}. {s}" for i, s in enumerate(steps)]) if steps else "   1. Open feature and trigger flow"

        # 7. Build Standard Bug Card (Stage 7: Bug Card)
        evidence_str = evidence_path if evidence_path else "Screenshots & logs stored in reports/evidence"
        bug_card_lines = [
            f"Summary: {summary}",
            f"Classification: {classification}",
            f"Reportable Defect: {'YES' if is_reportable_defect else 'NO'}",
            f"Environment: {environment}",
            f"Device: {device}",
            f"Build: {build}"
        ]
        if attack_surface:
            bug_card_lines.append(f"Attack Surface: {attack_surface}")
        if bug_target:
            bug_card_lines.append(f"Bug Target: {bug_target}")
        bug_card_lines.extend([
            f"Reproducibility: {reproducibility['reproducibility_label']}",
            f"Steps:\n{formatted_steps}",
            f"Expected: {expected}",
            f"Actual: {actual}",
            f"Evidence: {evidence_str}",
            f"Probable Layer: {probable_layer}",
            f"Severity/Priority suggestion: {severity} / {priority_sug}"
        ])
        bug_card_text = "\n".join(bug_card_lines)

        approval_prompt = (
            f"Found defect during testing: '{summary}'.\n"
            f"Kya is bug ko Jira mein 'Testing Bug' create karke parent ticket {parent_ticket_key or ticket} se link karna hai? (Approve / Reject / Edit)"
            if requires_user_approval else
            f"Observation classified as {classification}. No Jira Testing Bug required."
        )

        anomaly_lifecycle = {
            "stage_1_detect": {
                "ticket": ticket,
                "test_case_id": test_case_id,
                "summary": summary,
                "symptom": actual
            },
            "stage_2_reproduce": reproducibility,
            "stage_3_investigate": {
                "probable_layer": probable_layer,
                "severity": severity,
                "priority_suggestion": priority_sug
            },
            "stage_4_classify": {
                "classification": classification,
                "is_reportable_defect": is_reportable_defect
            },
            "stage_5_duplicate_check": dup_result,
            "stage_6_evidence": {
                "evidence_path": evidence_str,
                "logcat_snippet": logcat_snippet,
                "error_message": error_message
            },
            "stage_7_bug_card": {
                "bug_card_text": bug_card_text,
                "requires_user_approval": requires_user_approval
            },
            "lifecycle_pipeline": "Detect → Reproduce → Investigate → Classify → Duplicate Check → Evidence → Bug Card"
        }

        return {
            "ticket": ticket,
            "test_case_id": test_case_id,
            "summary": summary,
            "environment": environment,
            "device": device,
            "build": build,
            "steps": steps,
            "expected": expected,
            "actual": actual,
            "evidence": evidence_str,
            "probable_layer": probable_layer,
            "severity": severity,
            "priority_suggestion": priority_sug,
            "duplicate_check": dup_result,
            "bug_card": bug_card_text,
            "reproducibility": reproducibility,
            "classification": classification,
            "is_reportable_defect": is_reportable_defect,
            "attack_surface": attack_surface,
            "bug_target": bug_target,
            "requires_user_approval": requires_user_approval,
            "approval_prompt": approval_prompt,
            "anomaly_lifecycle": anomaly_lifecycle
        }

    def process_anomaly(self, anomaly_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the formal 7-step anomaly verification pipeline:
        Detect → Reproduce → Investigate → Classify → Duplicate Check → Evidence → Bug Card
        """
        return self.analyze_failure(
            ticket=anomaly_context.get("ticket", "UNKNOWN"),
            test_case_id=anomaly_context.get("test_case_id", "TC-00"),
            summary=anomaly_context.get("summary", "Unexpected anomaly detected"),
            steps=anomaly_context.get("steps", []),
            expected=anomaly_context.get("expected", "Expected valid state"),
            actual=anomaly_context.get("actual", "Observed anomaly"),
            environment=anomaly_context.get("environment", "TESTING"),
            device=anomaly_context.get("device", "Connected Android Device"),
            build=anomaly_context.get("build", "#142"),
            evidence_path=anomaly_context.get("evidence_path"),
            error_message=anomaly_context.get("error_message", ""),
            logcat_snippet=anomaly_context.get("logcat_snippet", ""),
            api_status=anomaly_context.get("api_status"),
            parent_ticket_key=anomaly_context.get("parent_ticket_key"),
            existing_bugs=anomaly_context.get("existing_bugs"),
            attack_surface=anomaly_context.get("attack_surface"),
            bug_target=anomaly_context.get("bug_target"),
            retry_results=anomaly_context.get("retry_results")
        )


    def _determine_probable_layer(
        self,
        error_message: str,
        logcat_snippet: str,
        api_status: Optional[int],
        actual: str
    ) -> str:
        """
        Pinpoints the failure origin layer:
        UI, API, Backend, Data, Configuration, Environment.
        """
        combined = f"{error_message} {logcat_snippet} {actual}".lower()

        # Environment issues
        if "device offline" in combined or "connection refused" in combined or "adb not responding" in combined:
            return "Environment"

        # Configuration issues
        if "wrong base url" in combined or "mismatched server" in combined or "environment mismatch" in combined:
            return "Configuration"

        # Backend issues
        if (api_status and api_status >= 500) or "internal server error" in combined or "sql" in combined:
            return "Backend"

        # API contract issues
        if (api_status and 400 <= api_status < 500) or "schema missing" in combined or "api timeout" in combined:
            return "API"

        # Data integrity issues (calculations, prices, formulas)
        if "price mismatch" in combined or "calculation" in combined or "mismatched rto" in combined or "tax mismatch" in combined:
            return "Data"

        # Default: UI rendering / interaction issues
        return "UI"
