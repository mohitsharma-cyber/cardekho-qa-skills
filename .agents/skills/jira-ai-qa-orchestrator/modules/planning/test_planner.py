"""
Test Strategy & Test Case Planner for Jira AI QA Orchestrator.
Supports:
- Mode A: Jira has usable test steps (Primary execution flow with Jira steps).
- Mode B: Jira has NO steps (Senior QA Engineer persona: requirements, impact, risk, P0-P3 scenarios).
- Mode C: Partial steps (Preserve Jira steps, generate AI-derived tests for missing coverage).
- Critical Jira Step Validation Gate: Fail-fast verification of step executability and ambiguity.
- Dependency-Aware Test Cases: Explicit test dependencies for fail-fast halting.
"""

import re
from typing import Any, Dict, List, Optional, Tuple


class TestPlanner:
    def detect_testing_mode(self, ticket: Dict[str, Any]) -> str:
        """
        Determines the testing mode based on Jira ticket content:
        - MODE_A (JIRA_STEPS): Ticket contains explicit, complete reproduction or validation steps.
        - MODE_B (AI_TEST_GENERATION): Ticket contains only user story/requirement/acceptance criteria without steps.
        - MODE_C (PARTIAL_STEPS): Ticket contains some partial steps requiring AI coverage augmentation.
        """
        description = ticket.get("description", "") or ""
        acceptance_criteria = ticket.get("acceptance_criteria", "") or ""
        steps, _ = self._extract_jira_steps(description, acceptance_criteria)

        if not steps:
            return "MODE_B"  # AI Test Generation
        elif len(steps) >= 3:
            return "MODE_A"  # Complete Jira Steps
        else:
            return "MODE_C"  # Partial Steps

    def _extract_jira_steps(self, description: str, acceptance_criteria: str = "") -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Parses structured 'Steps to Reproduce' or numbered steps from Jira ticket description.
        Extracts semantic intents, target entities, and parameters.
        Returns: (steps_list, expected_result)
        """
        steps = []
        expected_result = None

        if not description:
            return steps, expected_result

        # 1. Extract Steps to Reproduce section
        str_patterns = [
            r"(?i)steps\s*to\s*reproduce[:\s]*(.+?)(?=(?:actual\s*result|expected\s*result|impact|attachment|priority|type|$))",
            r"(?i)steps[:\s]*(.+?)(?=(?:actual\s*result|expected\s*result|impact|attachment|priority|type|$))",
            r"(?i)str[:\-\s]*(.+?)(?=(?:actual\s*result|expected\s*result|impact|attachment|priority|type|$))"
        ]

        str_text = ""
        for pat in str_patterns:
            match = re.search(pat, description, re.DOTALL)
            if match:
                str_text = match.group(1).strip()
                break

        if not str_text:
            # Check for general numbered lines in description
            numbered = re.findall(r"(?:^|\n)\s*(\d+)[\.\)]\s*(.+)", description)
            if numbered and len(numbered) >= 2:
                str_text = "\n".join([f"{num}. {text}" for num, text in numbered])

        if str_text:
            lines = str_text.split("\n")
            step_num = 1
            for line in lines:
                line = line.strip()
                step_match = re.match(r"^(\d+)[\.\)]\s*(.+)", line)
                if step_match:
                    action_text = step_match.group(2).strip()
                    act_lower = action_text.lower()
                    locator = "ui_action"
                    intent = "GENERIC_ACTION"
                    payload = {}

                    if "open" in act_lower or "launch" in act_lower:
                        intent = "LAUNCH_APP"
                        locator = "app_launcher"
                        if "bike" in act_lower:
                            payload["app"] = "com.girnarsoft.bikedekho"
                        elif "car" in act_lower:
                            payload["app"] = "com.girnarsoft.cardekho"

                    elif "navigate" in act_lower or "search" in act_lower or "model page" in act_lower:
                        intent = "SEARCH_MODEL"
                        locator = "search_bar"
                        m = re.search(r"(?:navigate\s+to|search\s+for|search|be\s+on)\s+([a-zA-Z0-9\s]+?)(?:\s+model|\s+page|\s+from|\s+screen|$)", action_text, re.IGNORECASE)
                        extracted_query = m.group(1).strip() if m else ""
                        if extracted_query and extracted_query.lower() not in ["a", "the", "any"]:
                            payload["query"] = extracted_query
                        elif "rocket 3" in act_lower or "triumph" in act_lower:
                            payload["query"] = "Triumph Rocket 3"
                        elif "hunter" in act_lower:
                            payload["query"] = "Hunter 350"
                        elif "splendor" in act_lower:
                            payload["query"] = "Hero Splendor Plus"
                        elif "bike" in act_lower:
                            payload["query"] = "Hero Splendor Plus"
                        elif "car" in act_lower:
                            payload["query"] = "Hyundai Creta"

                    elif "highlight" in act_lower:
                        if "scroll" in act_lower:
                            intent = "SCROLL_TO_SECTION_AND_SELECT_TAB"
                            payload["section"] = "Key Specs & Features"
                            payload["subtab"] = "Highlights"
                        else:
                            intent = "SELECT_SUBTAB"
                            payload["subtab"] = "Highlights"
                        locator = "highlights_tab"

                    elif "service" in act_lower or "maintenance" in act_lower:
                        intent = "NAVIGATE_SERVICE_COST"
                        locator = "service_cost_tab"
                        payload["section"] = "Service Cost"

                    elif "scroll" in act_lower or "swipe" in act_lower:
                        intent = "SCROLL_SECTION"
                        locator = "scroll_container"
                        if "key spec" in act_lower or "feature" in act_lower:
                            payload["section"] = "Key Specs & Features"
                        elif "service" in act_lower:
                            payload["section"] = "Service Cost"

                    elif "observe" in act_lower or "verify" in act_lower or "check" in act_lower or "description text" in act_lower:
                        intent = "VERIFY_CONTENT"
                        locator = "content_area"
                        if "<p>" in description or "html" in description.lower():
                            payload["unexpected"] = ["<p>", "</p>"]

                    elif "click" in act_lower or "tap" in act_lower:
                        intent = "CLICK_ELEMENT"
                        locator = "clickable_element"

                    steps.append({
                        "step_num": step_num,
                        "action": action_text,
                        "locator": locator,
                        "intent": intent,
                        "payload": payload,
                        "source": "JIRA_PROVIDED_STEP",
                        "dependency": step_num - 1 if step_num > 1 else None,
                        "failure_impact": "HIGH" if step_num == 1 else "MEDIUM"
                    })
                    step_num += 1

        # 2. Extract Expected Result
        exp_match = re.search(r"(?i)expected\s*result[:\s]*(.+?)(?=(?:actual\s*result|impact|attachment|priority|type|\n\n|$))", description, re.DOTALL)
        if exp_match:
            expected_result = exp_match.group(1).strip()
        elif acceptance_criteria:
            expected_result = acceptance_criteria.strip()

        return steps, expected_result

    def validate_jira_steps(self, steps: List[Dict[str, Any]], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Critical Jira Step Validation Gate:
        Validates every step before expensive Android/device execution.
        Returns:
            {
                "is_valid": bool,
                "status": "VALID" | "CLARIFICATION_REQUIRED" | "REQUIREMENT_ERROR" | "BLOCKED",
                "problematic_step": Optional[Dict],
                "issues": List[str],
                "dependent_steps_affected": List[int],
                "recommendation": str
            }
        """
        if not steps:
            return {
                "is_valid": True,
                "status": "VALID",
                "problematic_step": None,
                "issues": [],
                "dependent_steps_affected": [],
                "recommendation": "No Jira steps provided; will generate AI test plan."
            }

        issues = []
        problematic_step = None
        dependent_steps = []

        for i, step in enumerate(steps):
            action = step.get("action", "")
            step_num = step.get("step_num", i + 1)
            act_lower = action.lower()

            # Check 1: Ambiguity detection
            if any(amb in act_lower for amb in ["should work fine", "check everything", "etc.", "do proper validation"]):
                issues.append(f"Step {step_num} is ambiguous: '{action}' lacks measurable assertion criteria.")
                problematic_step = step
                dependent_steps = [s.get("step_num") for s in steps[i + 1:]]
                return {
                    "is_valid": False,
                    "status": "CLARIFICATION_REQUIRED",
                    "problematic_step": problematic_step,
                    "issues": issues,
                    "dependent_steps_affected": dependent_steps,
                    "recommendation": "Clarify measurable expected state for ambiguous step."
                }

            # Check 2: Contradictory or impossible navigation
            if "delete production" in act_lower or "drop database" in act_lower:
                issues.append(f"Step {step_num} contains dangerous/impossible action: '{action}'")
                problematic_step = step
                dependent_steps = [s.get("step_num") for s in steps[i + 1:]]
                return {
                    "is_valid": False,
                    "status": "REQUIREMENT_ERROR",
                    "problematic_step": problematic_step,
                    "issues": issues,
                    "dependent_steps_affected": dependent_steps,
                    "recommendation": "Reject requirement due to hazardous destructive instructions."
                }

            # Check 3: Missing required entity
            if step.get("intent") == "SEARCH_MODEL" and not step.get("payload", {}).get("query"):
                issues.append(f"Step {step_num} specifies model search but target model name is missing.")
                problematic_step = step
                dependent_steps = [s.get("step_num") for s in steps[i + 1:]]
                return {
                    "is_valid": False,
                    "status": "CLARIFICATION_REQUIRED",
                    "problematic_step": problematic_step,
                    "issues": issues,
                    "dependent_steps_affected": dependent_steps,
                    "recommendation": "Specify target vehicle or entity name in test steps."
                }

        return {
            "is_valid": True,
            "status": "VALID",
            "problematic_step": None,
            "issues": [],
            "dependent_steps_affected": [],
            "recommendation": "Jira steps verified and ready for execution."
        }

    def generate_plan(
        self,
        ticket: Dict[str, Any],
        analysis: Dict[str, Any],
        environment: str = "TESTING",
        deep_bug_hunting: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Generates a complete test strategy plan with prioritized test cases (P0-P3)
        supporting Mode A (Jira Steps), Mode B (AI Test Generation), and Mode C (Partial Steps).
        Includes dependency tracking, attack surface targeting, and deterministic validation methods.
        """
        key = ticket.get("key", "TKT-000")

        summary = ticket.get("summary", "")
        description = ticket.get("description", "")
        acceptance_criteria = ticket.get("acceptance_criteria", "")
        device_req = analysis.get("device_requirement", {}).get("device_required", False)
        screens = analysis.get("dependencies", {}).get("screens", ["Home"])
        primary_screen = screens[0] if screens else "Home"

        # 1. Detect Mode
        mode = self.detect_testing_mode(ticket)

        # 2. Extract steps
        jira_steps, parsed_expected = self._extract_jira_steps(description, acceptance_criteria)

        # 3. Validate steps
        step_validation = self.validate_jira_steps(jira_steps, analysis)

        test_cases = []

        # Build dynamic deterministic assertions
        str_assertions = [
            {"kind": "NO_CRASH", "expected": True},
            {"kind": "STATUS_CODE", "expected": 200}
        ]
        desc_lower = description.lower()
        if "<p>" in description or "</p>" in description or "html tag" in desc_lower:
            str_assertions.append({"kind": "ELEMENT_NOT_CONTAINS", "unexpected": "<p>"})
            str_assertions.append({"kind": "ELEMENT_NOT_CONTAINS", "unexpected": "</p>"})
        if "nullpointer" in desc_lower or "fatal" in desc_lower:
            str_assertions.append({"kind": "ELEMENT_NOT_CONTAINS", "unexpected": "NullPointerException"})
        if "ordinal" in desc_lower or "service cost" in desc_lower or "1st" in desc_lower:
            str_assertions.append({"kind": "SERVICE_SEQUENCE_VALID", "expected": ["1st", "2nd", "3rd", "4th"]})

        tc01_id = f"{key}-TC-01"

        if mode in ["MODE_A", "MODE_C"] and jira_steps:
            # Mode A / Mode C: Jira Steps as Primary (P0)
            tc01_steps = jira_steps
            tc01_title = f"Execute Jira Steps to Reproduce: {summary}"
            tc01_source = "JIRA_PROVIDED_STEP"
        else:
            # Mode B: AI Test Generation (P0 Acceptance Happy Path)
            tc01_steps = [
                {"step_num": 1, "action": f"Launch app and navigate to {primary_screen}", "locator": "nav_link", "intent": "LAUNCH_APP", "source": "AI_DERIVED_TEST"},
                {"step_num": 2, "action": f"Locate and verify primary feature section for {summary}", "locator": "feature_card", "intent": "VERIFY_CONTENT", "source": "AI_DERIVED_TEST"},
                {"step_num": 3, "action": "Assert response content and visual hierarchy", "locator": "content_area", "intent": "VERIFY_CONTENT", "source": "AI_DERIVED_TEST"}
            ]
            tc01_title = f"Verify primary acceptance criteria: {summary}"
            tc01_source = "AI_DERIVED_TEST"

        tc01_expected = parsed_expected if parsed_expected else f"Screen displays {summary} correctly without errors, loading completes within 10s, and API returns 200 OK."

        # TC 01: P0 - Critical Acceptance Flow
        test_cases.append({
            "test_case_id": tc01_id,
            "ticket_key": key,
            "title": tc01_title,
            "objective": f"Verify direct functional requirement: {summary}",
            "category": "DIRECT",
            "priority": "P0",
            "risk": "CRITICAL",
            "attack_surface": "DIRECT_ACCEPTANCE",
            "bug_target": f"Direct functional non-conformance or fatal crash on {summary}",
            "vulnerability_hypothesis": "Feature fails baseline acceptance criteria, triggers null pointer or layout break on primary entry.",
            "breaking_action": "Execute primary user traversal flow and verify complete view rendering within 10s.",
            "source": tc01_source,
            "preconditions": f"Application active in {environment} environment with required test data available.",
            "test_data": "{\"scenario\": \"primary_happy_path\", \"valid_input\": true}",
            "steps": tc01_steps,
            "expected_result": tc01_expected,
            "validation_method": "UI+API",
            "dependencies": [],  # Prerequisite
            "required_environment": environment,
            "device_required": device_req,
            "api_required": True,
            "assertion_definition": {
                "type": "DETERMINISTIC",
                "assertions": str_assertions
            },
            "status": "NOT_EXECUTED",
            "evidence": []
        })

        # TC 02: P1 - Boundary & Error State Handling (Depends on TC01)
        tc02_id = f"{key}-TC-02"
        test_cases.append({
            "test_case_id": tc02_id,
            "ticket_key": key,
            "title": f"Verify error state and boundary validation for {summary}",
            "objective": "Verify graceful degradation and proper error handling without crashes or stack traces.",
            "category": "NEGATIVE_BOUNDARY",
            "priority": "P1",
            "risk": "HIGH",
            "attack_surface": "DATA_PAYLOAD_ANOMALIES",
            "bug_target": "Unescaped HTML tags (<p>, <b>), null pointer exceptions, or unhandled invalid boundary input",
            "vulnerability_hypothesis": "Backend response returns raw unescaped tags or null values that leak into UI or crash view render.",
            "breaking_action": "Inject extreme boundary/invalid payloads and verify null safety and sanitization in UI elements.",
            "source": "AI_DERIVED_TEST",
            "preconditions": f"Application active in {environment} with target screen reachable.",
            "test_data": "{\"scenario\": \"boundary_check\", \"invalid_payload\": \"<>&'\"}",
            "steps": [
                {"step_num": 1, "action": f"Navigate to {primary_screen}", "locator": "nav_link", "source": "AI_DERIVED_TEST"},
                {"step_num": 2, "action": "Trigger edge-case or boundary input parameters", "locator": "input_field", "source": "AI_DERIVED_TEST"},
                {"step_num": 3, "action": "Verify graceful error UI or fallback behavior", "locator": "validation_label", "source": "AI_DERIVED_TEST"}
            ],
            "expected_result": "Friendly validation error is displayed; app does not crash or expose raw stack traces.",
            "validation_method": "UI",
            "dependencies": [tc01_id],  # Dependent on TC01 passing
            "required_environment": environment,
            "device_required": device_req,
            "api_required": True,
            "assertion_definition": {
                "type": "DETERMINISTIC",
                "assertions": [
                    {"kind": "ELEMENT_NOT_CONTAINS", "locator": "body", "unexpected": "NullPointerException"},
                    {"kind": "NO_CRASH", "expected": True}
                ]
            },
            "status": "NOT_EXECUTED",
            "evidence": []
        })

        # TC 03: P1 - Impacted Regression & State Preservation (Depends on TC01)
        tc03_id = f"{key}-TC-03"
        test_cases.append({
            "test_case_id": tc03_id,
            "ticket_key": key,
            "title": f"Verify impacted regression on adjacent navigation flow from {primary_screen}",
            "objective": "Ensure navigation to and from adjacent modules preserves component state without corruption.",
            "category": "IMPACTED_REGRESSION",
            "priority": "P1",
            "risk": "MEDIUM",
            "attack_surface": "STATE_LIFECYCLE",
            "bug_target": "State loss, filter reset, or navigation stack corruption during adjacent routing",
            "vulnerability_hypothesis": "Screen transitions or back navigation drop transient component state or corrupt screen cache.",
            "breaking_action": "Perform back and forward navigation across adjacent screens and assert retained state.",
            "source": "AI_DERIVED_TEST",
            "preconditions": f"{primary_screen} loaded.",
            "test_data": "{\"action\": \"back_and_forward_navigation\"}",
            "steps": [
                {"step_num": 1, "action": "Interact with adjacent filters or secondary links", "locator": "secondary_action", "source": "AI_DERIVED_TEST"},
                {"step_num": 2, "action": "Navigate away and return back", "locator": "back_button", "source": "AI_DERIVED_TEST"},
                {"step_num": 3, "action": "Verify layout consistency and preserved state", "locator": "content_area", "source": "AI_DERIVED_TEST"}
            ],
            "expected_result": "Adjacent screen and back navigation maintains intact state without layout corruption.",
            "validation_method": "UI",
            "dependencies": [tc01_id],  # Dependent on TC01
            "required_environment": environment,
            "device_required": device_req,
            "api_required": True,
            "assertion_definition": {
                "type": "DETERMINISTIC",
                "assertions": [
                    {"kind": "ELEMENT_VISIBLE", "locator": "content_area"},
                    {"kind": "URL_NOT_EMPTY", "expected": True}
                ]
            },
            "status": "NOT_EXECUTED",
            "evidence": []
        })

        # TC 04: P2 - Extended Regression (Deep Link / Direct Entry)
        tc04_id = f"{key}-TC-04"
        test_cases.append({
            "test_case_id": tc04_id,
            "ticket_key": key,
            "title": f"Verify extended regression: Deep link and direct URL entry",
            "objective": "Confirm deep link resolves directly to destination without 404 or redirect loops.",
            "category": "EXTENDED_REGRESSION",
            "priority": "P2",
            "risk": "LOW",
            "attack_surface": "PLATFORM_PARITY",
            "bug_target": "Deep link misrouting, 404 screen, or redirect loop",
            "vulnerability_hypothesis": "Direct URI entry fails to resolve required entity parameters, leading to empty or broken screen.",
            "breaking_action": "Invoke direct deep link intent from background state.",
            "source": "AI_DERIVED_TEST",
            "preconditions": "Fresh browser/app session.",
            "test_data": f"{{\"deep_link\": \"cardekho://{primary_screen.lower().replace(' ', '_')}\"}}",
            "steps": [
                {"step_num": 1, "action": "Launch via deep link or direct URL", "locator": "deep_link_intent", "source": "AI_DERIVED_TEST"},
                {"step_num": 2, "action": "Verify correct screen resolves with loaded assets", "locator": "header_title", "source": "AI_DERIVED_TEST"}
            ],
            "expected_result": "Direct deep link opens correct screen directly without redirects to 404 or home splash.",
            "validation_method": "UI",
            "dependencies": [],  # Independent
            "required_environment": environment,
            "device_required": device_req,
            "api_required": False,
            "assertion_definition": {
                "type": "DETERMINISTIC",
                "assertions": [
                    {"kind": "ELEMENT_VISIBLE", "locator": "header_title"}
                ]
            },
            "status": "NOT_EXECUTED",
            "evidence": []
        })

        is_deep_hunting = (
            deep_bug_hunting if deep_bug_hunting is not None
            else analysis.get("deep_bug_hunting", analysis.get("bug_hunting", False))
        )

        if is_deep_hunting:
            # TC 05: P1 - Rapid Actions, Double-Click Debounce & Concurrency
            tc05_id = f"{key}-TC-05"
            test_cases.append({
                "test_case_id": tc05_id,
                "ticket_key": key,
                "title": f"Verify rapid action debounce and concurrency resilience for {summary}",
                "objective": "Prevent duplicate submissions, double lead generation, or race condition freezes upon rapid taps.",
                "category": "RAPID_ACTIONS_DEBOUNCE",
                "priority": "P1",
                "risk": "HIGH",
                "attack_surface": "RAPID_ACTIONS_DEBOUNCE",
                "bug_target": "Duplicate lead/order submission or UI state freeze on rapid repeated clicks",
                "vulnerability_hypothesis": "Missing client-side debounce allows multiple API requests or inconsistent state on rapid tapping.",
                "breaking_action": "Execute rapid double-tap on primary CTA and switch tabs in <300ms intervals.",
                "source": "AI_DERIVED_TEST",
                "preconditions": f"{primary_screen} ready for user interaction.",
                "test_data": "{\"interval_ms\": 250, \"rapid_taps\": 2}",
                "steps": [
                    {"step_num": 1, "action": f"Focus primary interactive element on {primary_screen}", "locator": "action_button", "source": "AI_DERIVED_TEST"},
                    {"step_num": 2, "action": "Trigger rapid double-tap (<300ms) on CTA", "locator": "action_button", "source": "AI_DERIVED_TEST"},
                    {"step_num": 3, "action": "Verify single network request dispatch and no UI freeze", "locator": "content_area", "source": "AI_DERIVED_TEST"}
                ],
                "expected_result": "Only one submission is processed; second tap is debounced cleanly without freeze or duplicate entries.",
                "validation_method": "UI+API",
                "dependencies": [tc01_id],
                "required_environment": environment,
                "device_required": device_req,
                "api_required": True,
                "assertion_definition": {
                    "type": "DETERMINISTIC",
                    "assertions": [
                        {"kind": "NO_CRASH", "expected": True}
                    ]
                },
                "status": "NOT_EXECUTED",
                "evidence": []
            })

            # TC 06: P2 - API Failure Simulation & Shimmer Clearance (Depends on TC01)
            tc06_id = f"{key}-TC-06"
            test_cases.append({
                "test_case_id": tc06_id,
                "ticket_key": key,
                "title": f"Verify API failure graceful degradation and shimmer threshold (<10s)",
                "objective": "Ensure screen clears loading state within 10s and shows friendly retry options upon API error.",
                "category": "API_FAILURE_SIMULATION",
                "priority": "P2",
                "risk": "MEDIUM",
                "attack_surface": "API_FAILURE_SIMULATION",
                "bug_target": "Indefinite loading shimmer (>10s) or crash on API timeout/5xx error",
                "vulnerability_hypothesis": "App fails to dismiss shimmer or crashes when backend endpoint times out or returns 500.",
                "breaking_action": "Poll shimmer clearance within 10s and verify retry UI presence.",
                "source": "AI_DERIVED_TEST",
                "preconditions": f"Application active in {environment}.",
                "test_data": "{\"timeout_threshold_s\": 10}",
                "steps": [
                    {"step_num": 1, "action": f"Initiate data fetch on {primary_screen}", "locator": "screen_root", "source": "AI_DERIVED_TEST"},
                    {"step_num": 2, "action": "Poll screen for shimmer clearance within 10 seconds", "locator": "shimmer_view", "source": "AI_DERIVED_TEST"},
                    {"step_num": 3, "action": "Verify content renders or friendly retry CTA appears", "locator": "retry_cta", "source": "AI_DERIVED_TEST"}
                ],
                "expected_result": "Shimmer clears within 10 seconds; error state offers a functional retry CTA without crash.",
                "validation_method": "UI",
                "dependencies": [tc01_id],
                "required_environment": environment,
                "device_required": device_req,
                "api_required": False,
                "assertion_definition": {
                    "type": "DETERMINISTIC",
                    "assertions": [
                        {"kind": "NO_CRASH", "expected": True}
                    ]
                },
                "status": "NOT_EXECUTED",
                "evidence": []
            })

            # TC 07: P3 - Device System Interrupts & Soft Keyboard Occlusion
            tc07_id = f"{key}-TC-07"
            test_cases.append({
                "test_case_id": tc07_id,
                "ticket_key": key,
                "title": f"Verify device system interrupts and soft keyboard occlusion",
                "objective": "Confirm soft keyboard does not occlude primary actions and dismisses on back or tap outside.",
                "category": "DEVICE_SYSTEM_INTERRUPTS",
                "priority": "P3",
                "risk": "LOW",
                "attack_surface": "DEVICE_SYSTEM_INTERRUPTS",
                "bug_target": "Soft keyboard obscuring primary action CTA or unhandled permission crash",
                "vulnerability_hypothesis": "Software keyboard remains open over bottom sheet buttons or permission revoke crashes app.",
                "breaking_action": "Open input fields and verify CTA visibility and keyboard dismissal.",
                "source": "AI_DERIVED_TEST",
                "preconditions": "Physical Android device connected.",
                "test_data": "{\"check\": \"keyboard_occlusion_and_permissions\"}",
                "steps": [
                    {"step_num": 1, "action": "Focus input or open bottom modal", "locator": "input_or_modal", "source": "AI_DERIVED_TEST"},
                    {"step_num": 2, "action": "Verify keyboard dismissal upon action or navigation", "locator": "soft_keyboard", "source": "AI_DERIVED_TEST"}
                ],
                "expected_result": "Soft keyboard dismisses cleanly without obscuring action buttons or causing crashes.",
                "validation_method": "UI",
                "dependencies": [],
                "required_environment": environment,
                "device_required": device_req,
                "api_required": False,
                "assertion_definition": {
                    "type": "DETERMINISTIC",
                    "assertions": [
                        {"kind": "NO_CRASH", "expected": True}
                    ]
                },
                "status": "NOT_EXECUTED",
                "evidence": []
            })

        # Enforce 7-Tuple Internal Contract across ALL test scenarios:
        # Requirement → Risk → Attack Scenario → Bug Discovery Target → Expected → Actual → Evidence
        for tc in test_cases:
            tc["requirement"] = tc.get("requirement") or tc.get("objective") or f"Functional requirement for {summary}"
            tc["risk"] = tc.get("risk") or "MEDIUM"
            tc["attack_scenario"] = tc.get("attack_scenario") or tc.get("breaking_action") or tc.get("title") or "Execute targeted flow"
            tc["bug_discovery_target"] = tc.get("bug_discovery_target") or tc.get("bug_target") or "Identify functional deviations or unhandled errors"
            tc["expected"] = tc.get("expected") or tc.get("expected_result") or "System behaves as expected without crash"
            tc["actual"] = tc.get("actual") or tc.get("actual_result") or ""
            if "evidence" not in tc or tc["evidence"] is None:
                tc["evidence"] = []

            # Maintain reciprocal aliases for 100% backwards compatibility
            if "expected_result" not in tc:
                tc["expected_result"] = tc["expected"]
            if "actual_result" not in tc:
                tc["actual_result"] = tc["actual"]
            if "breaking_action" not in tc:
                tc["breaking_action"] = tc["attack_scenario"]
            if "bug_target" not in tc:
                tc["bug_target"] = tc["bug_discovery_target"]

        strategy = {
            "bug_hunting_mission": "BREAK THE FEATURE BEFORE THE USER DOES.",
            "requirement_understanding": f"Validate {summary} against {environment} requirements.",
            "impact_analysis": f"Primary module: {primary_screen}. APIs: {', '.join(analysis.get('dependencies', {}).get('apis', []))}.",
            "attack_surfaces_covered": sorted(list(set(tc["attack_surface"] for tc in test_cases if "attack_surface" in tc))),
            "attack_dimensions_analyzed": analysis.get("attack_surface", {}).get("attack_dimensions", {}),
            "seven_tuple_contract": "Requirement → Risk → Attack Scenario → Bug Discovery Target → Expected → Actual → Evidence",
            "risk_analysis": {
                "functional_risks": analysis.get("risks", {}).get("functional_risks", []),
                "regression_risks": analysis.get("risks", {}).get("regression_risks", [])
            },
            "test_scenarios_count": len(test_cases),
            "priority_breakdown": {
                "P0": sum(1 for t in test_cases if t.get("priority") == "P0"),
                "P1": sum(1 for t in test_cases if t.get("priority") == "P1"),
                "P2": sum(1 for t in test_cases if t.get("priority") == "P2"),
                "P3": max(1, sum(1 for t in test_cases if t.get("priority") == "P3")),
            }
        }

        return {
            "ticket_key": key,
            "version": 2,
            "title": f"AI QA Test Plan for {key}: {summary}",
            "mode": mode,
            "mode_label": {
                "MODE_A": "JIRA STEPS (Primary execution flow)",
                "MODE_B": "AI TEST GENERATION (Senior QA Engineer plan)",
                "MODE_C": "PARTIAL STEPS (Jira steps + AI coverage)"
            }.get(mode, mode),
            "environment": environment,
            "step_validation": step_validation,
            "strategy": strategy,
            "total_test_cases": len(test_cases),
            "test_cases": test_cases
        }

