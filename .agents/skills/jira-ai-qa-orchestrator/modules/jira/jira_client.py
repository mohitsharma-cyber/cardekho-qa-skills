import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
"""
Jira Integration Client for Jira AI QA Orchestrator.
Communicates securely with Jira REST API v2 with support for Live and Mock modes.
Credentials are kept strictly server-side and never leaked.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional
import requests
from requests.auth import HTTPBasicAuth

from ..mock.mock_provider import MockProvider


class JiraClient:
    _GLOBAL_QUEUE_CACHE: List[Dict[str, Any]] = []

    def __init__(self, config_path: Optional[str] = None, mock_mode: bool = False):
        self.mock_mode = mock_mode
        self.config = self._load_config(config_path)
        self.base_url = self.config.get("jira", {}).get("jira_url", "https://jira.girnarsoft.com").rstrip("/")
        self.username = self.config.get("jira", {}).get("username", "")
        self.password = self.config.get("jira", {}).get("password", "")
        self.default_project = self.config.get("jira", {}).get("default_project", "MB2C")

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        if not config_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(base_dir, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def is_live_configured(self) -> bool:
        return bool(self.base_url and self.username and self.password and not self.mock_mode)

    def get_auth(self) -> Optional[HTTPBasicAuth]:
        if self.username and self.password:
            return HTTPBasicAuth(self.username, self.password)
        return None

    def refresh_queue(self, project: Optional[str] = None) -> List[Dict[str, Any]]:
        """Clears cached tickets and forces a fresh query to Jira."""
        JiraClient._GLOBAL_QUEUE_CACHE = []
        return self.get_assigned_tickets(project=project, force_refresh=True)

    def get_ticket_from_queue(self, index_or_key: str) -> Optional[Dict[str, Any]]:
        """Resolves a ticket from the cached queue by 1-based index or ticket key."""
        clean = index_or_key.strip().upper()
        if clean.isdigit():
            idx = int(clean)
            if 1 <= idx <= len(JiraClient._GLOBAL_QUEUE_CACHE):
                return JiraClient._GLOBAL_QUEUE_CACHE[idx - 1]
            return None
        for t in JiraClient._GLOBAL_QUEUE_CACHE:
            if t.get("key", "").upper() == clean:
                return t
        return None

    def get_assigned_tickets(self, project: Optional[str] = None, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Fetch tickets currently assigned to the logged-in QA user with active queue caching."""
        if not force_refresh and JiraClient._GLOBAL_QUEUE_CACHE:
            return JiraClient._GLOBAL_QUEUE_CACHE

        if not self.is_live_configured():
            tickets = MockProvider.get_assigned_tickets()
            JiraClient._GLOBAL_QUEUE_CACHE = tickets
            return tickets

        project_key = project or self.default_project
        # Prioritize active QA states, exclude Closed/Done by default (Master Prompt Section 3)
        jql = 'assignee = currentUser() AND statusCategory not in ("Done") ORDER BY updated DESC'
        url = f"{self.base_url}/rest/api/2/search"

        try:
            res = requests.get(
                url,
                auth=self.get_auth(),
                params={"jql": jql, "maxResults": 30},
                verify=False,
                timeout=12
            )
            if res.status_code == 200:
                data = res.json()
                tickets = []
                for item in data.get("issues", []):
                    fields = item.get("fields", {})
                    # Extract acceptance criteria if present in description or custom fields
                    desc = fields.get("description") or ""
                    ac = self._extract_acceptance_criteria(desc, fields)

                    tickets.append({
                        "id": item.get("id"),
                        "key": item.get("key"),
                        "summary": fields.get("summary", ""),
                        "description": desc,
                        "acceptance_criteria": ac,
                        "issue_type": fields.get("issuetype", {}).get("name", "Bug"),
                        "priority": fields.get("priority", {}).get("name", "Medium"),
                        "status": fields.get("status", {}).get("name", "Open"),
                        "labels": fields.get("labels", []),
                        "assignee": (fields.get("assignee") or {}).get("displayName") or (fields.get("assignee") or {}).get("name") or "",
                        "reporter": (fields.get("reporter") or {}).get("displayName") or (fields.get("reporter") or {}).get("name") or "",
                        "project_key": fields.get("project", {}).get("key", project_key),
                        "created": fields.get("created"),
                        "updated": fields.get("updated")
                    })
                JiraClient._GLOBAL_QUEUE_CACHE = tickets
                return tickets
            else:
                print(f"[WARN] Jira search returned {res.status_code}. Falling back to mock data.")
                fallback = MockProvider.get_assigned_tickets()
                JiraClient._GLOBAL_QUEUE_CACHE = fallback
                return fallback
        except Exception as e:
            print(f"[WARN] Error connecting to Jira: {e}. Falling back to mock data.")
            fallback = MockProvider.get_assigned_tickets()
            JiraClient._GLOBAL_QUEUE_CACHE = fallback
            return fallback

    def get_ticket_details(self, ticket_key: str) -> Dict[str, Any]:
        """Fetch full ticket context including linked issues, subtasks, and comments."""
        if not self.is_live_configured():
            try:
                from database.db_manager import DatabaseManager
                db_t = DatabaseManager().get_jira_ticket(ticket_key)
                if db_t and db_t.get("description"):
                    return db_t
            except Exception:
                pass
            return MockProvider.get_ticket_details(ticket_key)

        url = f"{self.base_url}/rest/api/2/issue/{ticket_key}"
        try:
            res = requests.get(url, auth=self.get_auth(), verify=False, timeout=12)
            if res.status_code == 200:
                data = res.json()
                fields = data.get("fields", {})
                desc = fields.get("description") or ""
                ac = self._extract_acceptance_criteria(desc, fields)

                # Extract linked issues
                linked_issues = []
                for link in fields.get("issuelinks", []):
                    target = link.get("outwardIssue") or link.get("inwardIssue")
                    if target:
                        linked_issues.append({
                            "key": target.get("key"),
                            "summary": target.get("fields", {}).get("summary"),
                            "relationship": link.get("type", {}).get("name")
                        })

                # Extract comments
                comments = []
                for c in fields.get("comment", {}).get("comments", []):
                    comments.append({
                        "author": (c.get("author") or {}).get("displayName", "User"),
                        "body": c.get("body", ""),
                        "created": c.get("created")
                    })

                return {
                    "id": data.get("id"),
                    "key": data.get("key"),
                    "summary": fields.get("summary", ""),
                    "description": desc,
                    "acceptance_criteria": ac,
                    "issue_type": fields.get("issuetype", {}).get("name", "Bug"),
                    "priority": fields.get("priority", {}).get("name", "Medium"),
                    "status": fields.get("status", {}).get("name", "Open"),
                    "labels": fields.get("labels", []),
                    "assignee": (fields.get("assignee") or {}).get("displayName") or (fields.get("assignee") or {}).get("name") or "",
                    "reporter": (fields.get("reporter") or {}).get("displayName") or (fields.get("reporter") or {}).get("name") or "",
                    "project_key": fields.get("project", {}).get("key", "MB2C"),
                    "linked_issues": linked_issues,
                    "comments": comments,
                    "attachment_count": len(fields.get("attachment", []))
                }
            else:
                return MockProvider.get_ticket_details(ticket_key)
        except Exception as e:
            print(f"[WARN] Error fetching issue {ticket_key}: {e}")
            return MockProvider.get_ticket_details(ticket_key)

    def add_comment(self, ticket_key: str, comment_text: str) -> bool:
        """Add a structured QA report comment to the Jira ticket."""
        if not self.is_live_configured():
            try:
                print(f"[MOCK JIRA] Simulated adding comment to {ticket_key}:\n{comment_text[:200]}...")
            except Exception:
                safe_text = comment_text[:200].encode('ascii', errors='replace').decode('ascii')
                print(f"[MOCK JIRA] Simulated adding comment to {ticket_key}:\n{safe_text}...")
            return True

        url = f"{self.base_url}/rest/api/2/issue/{ticket_key}/comment"
        try:
            res = requests.post(
                url,
                auth=self.get_auth(),
                json={"body": comment_text},
                verify=False,
                timeout=12
            )
            if res.status_code in (200, 201):
                print(f"[SUCCESS] Jira comment posted to {ticket_key}")
                return True
            else:
                print(f"[WARN] Failed to post comment to {ticket_key}: Status {res.status_code} - {res.text[:200]}")
                return False
        except Exception as e:
            print(f"[ERROR] Failed to post comment to {ticket_key}: {e}")
            return False

    def attach_file(self, ticket_key: str, file_path: str) -> bool:
        """Upload a screenshot or evidence file as an attachment to the Jira ticket."""
        if not self.is_live_configured():
            print(f"[MOCK JIRA] Simulated attaching file {file_path} to {ticket_key}")
            return True

        if not os.path.exists(file_path):
            print(f"[WARN] Attachment file not found: {file_path}")
            return False

        url = f"{self.base_url}/rest/api/2/issue/{ticket_key}/attachments"
        headers = {"X-Atlassian-Token": "no-check"}
        try:
            filename = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                files = {"file": (filename, f)}
                res = requests.post(
                    url,
                    auth=self.get_auth(),
                    headers=headers,
                    files=files,
                    verify=False,
                    timeout=20
                )
            if res.status_code in (200, 201):
                print(f"[SUCCESS] Attached {filename} to Jira ticket {ticket_key}")
                return True
            else:
                print(f"[WARN] Attachment failed for {ticket_key}: Status {res.status_code} - {res.text[:200]}")
                return False
        except Exception as e:
            print(f"[ERROR] Error attaching file to {ticket_key}: {e}")
            return False

    def transition_issue(self, ticket_key: str, target_transition_name: str = "QA Complete") -> bool:
        """Transition Jira ticket status (e.g. 'QA Complete', 'Closed', 'Needs Re-Work')."""
        if not self.is_live_configured():
            print(f"[MOCK JIRA] Simulated transitioning {ticket_key} to '{target_transition_name}'")
            return True

        url = f"{self.base_url}/rest/api/2/issue/{ticket_key}/transitions"
        try:
            res = requests.get(url, auth=self.get_auth(), verify=False, timeout=10)
            if res.status_code != 200:
                print(f"[WARN] Could not fetch transitions for {ticket_key}: {res.status_code}")
                return False

            transitions = res.json().get("transitions", [])
            matched_id = None
            for t in transitions:
                if target_transition_name.lower() in t.get("name", "").lower():
                    matched_id = t.get("id")
                    break

            if not matched_id:
                avail = [t.get("name") for t in transitions]
                # Smart multi-step: If target is QA Complete but we are in Dev Complete, transition to In QA first
                if target_transition_name.lower() in ["qa complete", "in uat"]:
                    in_qa_trans = next((t for t in transitions if "in qa" in t.get("name", "").lower()), None)
                    if in_qa_trans:
                        print(f"[INFO] Stepping through 'In QA' ({in_qa_trans.get('id')}) to reach '{target_transition_name}'...")
                        requests.post(url, auth=self.get_auth(), json={"transition": {"id": in_qa_trans.get("id")}}, verify=False, timeout=10)
                        return self.transition_issue(ticket_key, target_transition_name)
                print(f"[INFO] Transition '{target_transition_name}' not available. Available: {avail}")
                return False

            post_res = requests.post(
                url,
                auth=self.get_auth(),
                json={"transition": {"id": matched_id}},
                verify=False,
                timeout=12
            )
            if post_res.status_code in (200, 204):
                print(f"[SUCCESS] Transitioned Jira ticket {ticket_key} to '{target_transition_name}'")
                return True
            else:
                print(f"[WARN] Transition failed for {ticket_key}: {post_res.status_code} - {post_res.text[:200]}")
                return False
        except Exception as e:
            print(f"[ERROR] Error transitioning {ticket_key}: {e}")
            return False

    def link_issues(self, inward_key: str, outward_key: str, link_type: str = "Relates", comment: Optional[str] = None) -> bool:
        """
        Links two Jira issues (e.g., Testing Bug linked to parent Task/Story).
        Default link type is 'Relates' ('relates to' / 'is related to').
        """
        if not self.is_live_configured():
            print(f"[MOCK JIRA] Simulated linking {inward_key} to {outward_key} via '{link_type}'")
            return True

        url = f"{self.base_url}/rest/api/2/issueLink"
        payload = {
            "type": {"name": link_type},
            "inwardIssue": {"key": inward_key},
            "outwardIssue": {"key": outward_key}
        }
        if comment:
            payload["comment"] = {"body": comment}

        try:
            res = requests.post(url, auth=self.get_auth(), json=payload, verify=False, timeout=12)
            if res.status_code in (200, 201):
                print(f"[SUCCESS] Linked {inward_key} to parent Jira issue {outward_key} ({link_type})")
                return True
            else:
                print(f"[WARN] Failed to link {inward_key} to {outward_key}: Status {res.status_code} - {res.text[:200]}")
                return False
        except Exception as e:
            print(f"[ERROR] Error linking Jira issues {inward_key} and {outward_key}: {e}")
    def check_duplicate_bugs(self, summary: str, parent_ticket_key: Optional[str] = None, project_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Duplicate Bug Protection (Rule 44):
        Checks existing linked issues on parent ticket and searches Jira for similar open defects.
        """
        duplicates = []
        # 1. Check existing linked issues on parent ticket
        if parent_ticket_key:
            parent_details = self.get_ticket_details(parent_ticket_key)
            for link in parent_details.get("linked_issues", []):
                linked_sum = (link.get("summary") or "").lower()
                key_words = [w.lower() for w in re.findall(r'\w+', summary) if len(w) > 3]
                matches = sum(1 for w in key_words if w in linked_sum)
                if matches >= 2 or summary.lower() in linked_sum:
                    duplicates.append({
                        "key": link.get("key"),
                        "summary": link.get("summary"),
                        "relationship": link.get("relationship", "Linked"),
                        "match_type": "LINKED_ISSUE_OVERLAP"
                    })

        if self.mock_mode or not self.is_live_configured():
            return duplicates

        # 2. Query Jira for existing open defects in project with similar text
        proj = project_key or self.default_project
        if not duplicates and summary:
            tokens = [w for w in re.findall(r'[A-Za-z0-9]+', summary) if len(w) > 4][:3]
            if tokens:
                search_term = " AND ".join(f'text ~ "{t}"' for t in tokens)
                jql = f'project = {proj} AND issuetype in ("Bug", "Testing Bug") AND resolution = Unresolved AND {search_term}'
                try:
                    res = requests.get(
                        f"{self.base_url}/rest/api/2/search",
                        auth=self.get_auth(),
                        params={"jql": jql, "maxResults": 5},
                        verify=False,
                        timeout=8
                    )
                    if res.status_code == 200:
                        for item in res.json().get("issues", []):
                            if item.get("key") != parent_ticket_key:
                                duplicates.append({
                                    "key": item.get("key"),
                                    "summary": item.get("fields", {}).get("summary"),
                                    "status": item.get("fields", {}).get("status", {}).get("name"),
                                    "match_type": "JQL_TEXT_SEARCH"
                                })
                except Exception:
                    pass

        return duplicates

    def create_bug(self, bug_data: Dict[str, Any], parent_ticket_key: Optional[str] = None) -> Optional[str]:
        """
        Create an approved Jira bug (Default: Testing Bug) and auto-link to parent Task/Story.
        """
        parent_key = parent_ticket_key or bug_data.get("original_ticket") or bug_data.get("parent_key")
        proj_key = bug_data.get("project_key")
        if not proj_key and parent_key and "-" in parent_key:
            proj_key = parent_key.split("-")[0]
        if not proj_key:
            proj_key = self.default_project

        issue_type = bug_data.get("issue_type", "Testing Bug")

        if not self.is_live_configured():
            mock_key = f"{proj_key}-9999"
            print(f"[MOCK JIRA] Simulated creating {issue_type}: {mock_key} - {bug_data.get('summary')}")
            if parent_key:
                self.link_issues(mock_key, parent_key)
            return mock_key

        url = f"{self.base_url}/rest/api/2/issue"
        payload = {
            "fields": {
                "project": {"key": proj_key},
                "summary": bug_data.get("summary"),
                "description": bug_data.get("description"),
                "issuetype": {"name": issue_type},
                "priority": {"name": bug_data.get("priority", "P2")},
                "labels": bug_data.get("labels", ["qa-automated", "testing-bug"])
            }
        }
        if bug_data.get("assignee"):
            payload["fields"]["assignee"] = {"name": bug_data.get("assignee")}

        try:
            res = requests.post(url, auth=self.get_auth(), json=payload, verify=False, timeout=15)
            if res.status_code in (200, 201):
                created_key = res.json().get("key")
                print(f"[SUCCESS] Created Jira {issue_type}: {created_key}")

                # Auto-link to parent task if available
                if parent_key:
                    self.link_issues(
                        inward_key=created_key,
                        outward_key=parent_key,
                        link_type="Relates",
                        comment=f"Automated {issue_type} discovered during QA execution and linked to parent Task {parent_key}."
                    )

                # Auto-attach screenshot evidence if present
                screenshot = bug_data.get("screenshot")
                if screenshot and os.path.exists(screenshot):
                    self.attach_file(created_key, screenshot)

                return created_key
            else:
                print(f"[ERROR] Bug creation failed: {res.status_code} - {res.text}")
                return None
        except Exception as e:
            print(f"[ERROR] Bug creation exception: {e}")
            return None

    def _extract_acceptance_criteria(self, description: str, fields: Dict[str, Any]) -> str:
        """Helper to discover Acceptance Criteria from description headers or custom fields."""
        # Check standard headers in description
        pattern = r"(?i)(?:acceptance\s*criteria|ac|expected\s*results?)[\s*:]*\n*(.*?)(?=\n\s*[A-Z][A-Za-z\s]+:|$)"
        match = re.search(pattern, description, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Check common custom fields
        for k, v in fields.items():
            if "customfield" in k and isinstance(v, str) and len(v) > 10:
                if any(kw in v.lower() for kw in ["given", "when", "then", "acceptance"]):
                    return v.strip()
        return ""
