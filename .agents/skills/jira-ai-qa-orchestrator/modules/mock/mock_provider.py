"""
Mock Provider for Jira AI QA Orchestrator.
Provides realistic, deterministic mock responses for Jira, AI Analysis, Devices, Web, and APIs
without requiring live Jira or physical hardware.
"""

from typing import Any, Dict, List


class MockProvider:
    @staticmethod
    def get_assigned_tickets() -> List[Dict[str, Any]]:
        return [
            {
                "id": "TKT-101",
                "key": "CD-123",
                "summary": "Fix login session expiry handling and remember me persistence",
                "description": "Users report unexpected session timeouts when returning to the app after 24 hours. Remember me checkbox does not keep user logged in.",
                "acceptance_criteria": "1. Remember Me keeps token for 30 days.\n2. Inactive timeout displays friendly re-login modal.\n3. User credentials are encrypted.",
                "issue_type": "Bug",
                "priority": "High",
                "status": "Ready for Testing",
                "assignee": "mohit.sharma@girnarsoft.com",
                "reporter": "product.lead@girnarsoft.com",
                "project_key": "CD",
                "labels": ["auth", "session", "security"]
            },
            {
                "id": "TKT-102",
                "key": "CD-145",
                "summary": "Search filter price range slider reset issue on car model listing",
                "description": "On New Cars listing page, resetting the price range filter retains previous filter tags in the header and crashes detail navigation.",
                "acceptance_criteria": "1. Reset button restores slider to min/max.\n2. Filter chips are cleared.\n3. Model listing refreshes without page reload.",
                "issue_type": "Story",
                "priority": "Medium",
                "status": "Test Plan Ready",
                "assignee": "mohit.sharma@girnarsoft.com",
                "reporter": "frontend.dev@girnarsoft.com",
                "project_key": "CD",
                "labels": ["search", "filters", "ui-bug"]
            },
            {
                "id": "TKT-103",
                "key": "CD-167",
                "summary": "Compare details screen crashes on dual camera hardware devices",
                "description": "Opening 360 degree comparison view crashes on physical devices with dual camera hardware due to missing camera permission fallback.",
                "acceptance_criteria": "1. Camera permission prompted gracefully.\n2. If denied, fallback to static gallery view.\n3. No app crash.",
                "issue_type": "Prod Bug",
                "priority": "Critical",
                "status": "Testing",
                "assignee": "mohit.sharma@girnarsoft.com",
                "reporter": "qa.lead@girnarsoft.com",
                "project_key": "CD",
                "labels": ["camera", "permissions", "hardware", "device-required"]
            },
            {
                "id": "TKT-104",
                "key": "DB2C-9133",
                "summary": "App team requires an API to enable 'Report incorrect Price' in CarDekho App",
                "description": "App team requires an API to enable the feature 'Report incorrect Price' in APP.\nCD API Branch Name = DB2C-ReportIncorrect_App_pageType\nPlease deploy to testingpwa2.",
                "acceptance_criteria": "1. API returns 200 with correct fields.\n2. Payload handles empty price report.",
                "issue_type": "Story",
                "priority": "High",
                "status": "Ready for QA",
                "assignee": "mohit.sharma@girnarsoft.com",
                "reporter": "dev.lead@girnarsoft.com",
                "project_key": "DB2C",
                "labels": ["api", "cardekho", "price"]
            },
            {
                "id": "TKT-105",
                "key": "BDCV-5902",
                "summary": "BikeDekho model price card revision and specs revamp",
                "description": "BikeDekho bike model price card revamp.\nAPI branch: BDCV-5902_price_card_revamp\nPlease deploy to testing server and verify.",
                "acceptance_criteria": "1. Model price card correctly renders on BikeDekho.\n2. Variant dropdown updates on selection.",
                "issue_type": "Story",
                "priority": "High",
                "status": "Ready for QA",
                "assignee": "mohit.sharma@girnarsoft.com",
                "reporter": "bikedekho.dev@girnarsoft.com",
                "project_key": "BDCV",
                "labels": ["bikedekho", "api", "revamp"]
            }
        ]

    @staticmethod
    def get_ticket_details(key: str) -> Dict[str, Any]:
        tickets = MockProvider.get_assigned_tickets()
        for t in tickets:
            if t["key"] == key:
                return t
        # Fallback dynamic mock
        return {
            "id": f"TKT-{key}",
            "key": key,
            "summary": f"Mock Ticket Summary for {key}",
            "description": f"Detailed requirement description for {key}",
            "acceptance_criteria": "1. Standard expected behavior verified.\n2. Error state properly handled.",
            "issue_type": "Bug",
            "priority": "Medium",
            "status": "In Progress",
            "assignee": "mohit.sharma@girnarsoft.com",
            "reporter": "lead@girnarsoft.com",
            "project_key": key.split("-")[0] if "-" in key else "MB2C",
            "labels": ["automation"]
        }

    @staticmethod
    def get_ai_requirement_analysis(ticket: Dict[str, Any]) -> Dict[str, Any]:
        key = ticket.get("key", "")
        summary = ticket.get("summary", "")
        desc = ticket.get("description", "")
        is_device_req = "camera" in summary.lower() or "hardware" in summary.lower() or "device-required" in ticket.get("labels", [])

        return {
            "ticket_key": key,
            "scope": [
                f"Verify changes related to '{summary}'",
                "Validate UI elements and error message display",
                "Ensure business APIs return 200 OK with correct payload structure"
            ],
            "out_of_scope": [
                "Backend database migration performance",
                "Third-party advertising SDK telemetry"
            ],
            "functional_risks": [
                "State desynchronization on rapid user interaction",
                "Null pointer exception when API returns empty payload"
            ],
            "regression_risks": [
                "Impact on adjacent filters and search result pagination",
                "Impact on deep link routing"
            ],
            "dependencies": {
                "screens": ["Home", "Search Filter", "Model Overview"],
                "apis": ["/api/v1/search/filter", "/api/v1/user/session"],
                "feature_flags": ["NEW_SEARCH_UI_ENABLED"]
            },
            "ambiguities": [] if ticket.get("acceptance_criteria") else [
                "Acceptance criteria not explicitly stated in Jira ticket."
            ],
            "device_required": is_device_req,
            "device_requirement_reason": "Native camera hardware & OS permission prompt validation required." if is_device_req else "Web/PWA testing is fully sufficient."
        }

    @staticmethod
    def get_test_cases(ticket_key: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        is_device = analysis.get("device_required", False)
        return [
            {
                "test_case_id": f"{ticket_key}-TC-01",
                "ticket_key": ticket_key,
                "title": "Verify Happy Path behavior and valid response",
                "category": "DIRECT",
                "priority": "P0",
                "preconditions": "Application running on configured environment (TESTING/STAGING)",
                "test_data": '{"user_id": "test_user_qa", "query": "Maruti Brezza"}',
                "steps": [
                    {"step": 1, "action": "Navigate to target screen", "locator": "nav_menu"},
                    {"step": 2, "action": "Perform primary action", "locator": "primary_cta"},
                    {"step": 3, "action": "Validate result renders", "locator": "result_container"}
                ],
                "expected_result": "Screen updates properly and business API returns HTTP 200 with non-empty results.",
                "required_environment": "TESTING",
                "device_required": False,
                "api_required": True,
                "assertion_definition": {
                    "type": "STATUS_AND_ELEMENT",
                    "http_status": 200,
                    "element_selector": "result_container",
                    "expected_text": ""
                }
            },
            {
                "test_case_id": f"{ticket_key}-TC-02",
                "ticket_key": ticket_key,
                "title": "Verify Impacted Regression on Search and Filter Navigation",
                "category": "IMPACTED_REGRESSION",
                "priority": "P1",
                "preconditions": "Search screen active",
                "test_data": '{"filter_budget": "5-10L"}',
                "steps": [
                    {"step": 1, "action": "Open filter modal", "locator": "filter_button"},
                    {"step": 2, "action": "Apply price range", "locator": "price_slider"},
                    {"step": 3, "action": "Tap Apply", "locator": "apply_filters_btn"}
                ],
                "expected_result": "Listing updates with filtered models without console errors or crash.",
                "required_environment": "TESTING",
                "device_required": False,
                "api_required": True,
                "assertion_definition": {
                    "type": "ELEMENT_VISIBLE",
                    "element_selector": "model_card",
                    "min_count": 1
                }
            },
            {
                "test_case_id": f"{ticket_key}-TC-03",
                "ticket_key": ticket_key,
                "title": "Verify Device Native Permission / Hardware Handling" if is_device else "Verify Boundary and Error State Handling",
                "category": "DIRECT" if is_device else "EXTENDED_REGRESSION",
                "priority": "P1",
                "preconditions": "Device connected with USB debugging enabled" if is_device else "Network condition normal",
                "test_data": '{"permission": "CAMERA"}' if is_device else '{"invalid_input": "!@#$$%"}',
                "steps": [
                    {"step": 1, "action": "Trigger permission request" if is_device else "Enter boundary input", "locator": "hardware_trigger"},
                    {"step": 2, "action": "Observe system dialog and app recovery", "locator": "dialog_container"}
                ],
                "expected_result": "Application gracefully handles response without unexpected crashes.",
                "required_environment": "TESTING",
                "device_required": is_device,
                "api_required": False,
                "assertion_definition": {
                    "type": "NO_CRASH",
                    "expected_state": "ACTIVE"
                }
            }
        ]

    @staticmethod
    def get_mock_device() -> Dict[str, Any]:
        return {
            "serial": "MOCK_ADB_DEVICE_99",
            "brand": "Samsung",
            "model": "Galaxy S23 Ultra",
            "os_version": "14",
            "sdk_version": "34",
            "connection_status": "Connected",
            "usb_debugging": True,
            "appium_ready": True,
            "package_name": "com.cardekho.android.debug"
        }
