"""
Reference Jira Resolver for CarDekho & BikeDekho QA Orchestration.
Detects Reference Jira IDs from ticket summaries, descriptions, and issue links.
Fetches reference tickets and extracts comprehensive implementation context.
Enforces strict anti-guesswork: if reference is missing or inaccessible,
reports deterministic statuses rather than hallucinating details.
"""

import re
from typing import Dict, Any, List, Optional
from ..jira.jira_client import JiraClient

REFERENCE_KEYWORDS = [
    r"reference\s*(?:jira|ticket|task|issue)?\s*[:=\-]\s*([A-Z0-9]+-[0-9]+)",
    r"ref\s*(?:jira|ticket|task)?\s*[:=\-]\s*([A-Z0-9]+-[0-9]+)",
    r"(?:same as|parity with|refer|reference to|based on|see)\s*(?:jira|ticket|task)?\s*[:=\-]?\s*([A-Z0-9]+-[0-9]+)",
    r"\[([A-Z0-9]+-[0-9]+)\]\s*(?:implementation|reference)",
    r"parent\s*[:=\-]\s*([A-Z0-9]+-[0-9]+)"
]

class ReferenceJiraResolver:
    """Detects, fetches, and extracts implementation context from Reference Jira tickets."""

    def __init__(self, jira_client: Optional[JiraClient] = None):
        self.jira_client = jira_client or JiraClient()

    def detect_reference_jira_id(
        self,
        summary: str = "",
        description: str = "",
        issuelinks: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[str]:
        """
        Scans summary, description, and issue links for explicit Reference Jira keys.
        Returns the first validated Reference Jira ID or None.
        """
        text = f"{summary or ''}\n{description or ''}"

        # 1. Check explicit keyword patterns in text
        for pattern in REFERENCE_KEYWORDS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                ref_key = match.group(1).upper()
                return ref_key

        # 2. Check issue links for reference-like relationships
        issuelinks = issuelinks or []
        for link in issuelinks:
            relationship = str(link.get("relationship", "")).lower()
            key = link.get("key") or (link.get("outwardIssue") or link.get("inwardIssue") or {}).get("key")
            if not key:
                continue

            # Prioritize links explicitly denoting reference or cloning
            if any(rel in relationship for rel in ["reference", "relates", "cloners", "is cloned by", "causes"]):
                return str(key).upper()

        return None

    def fetch_reference_jira(self, ref_key: Optional[str]) -> Dict[str, Any]:
        """
        Fetches full reference issue context via JiraClient.
        Returns structured telemetry: FETCHED, MISSING_ID, or INACCESSIBLE.
        """
        if not ref_key or not str(ref_key).strip():
            return {
                "status": "MISSING_ID",
                "reference_id": None,
                "error": "No Reference Jira ID provided or detected."
            }

        clean_key = str(ref_key).strip().upper()

        try:
            details = self.jira_client.get_ticket_details(clean_key)
            if not details or details.get("error") or not details.get("key"):
                return {
                    "status": "INACCESSIBLE",
                    "reference_id": clean_key,
                    "error": f"Reference Jira {clean_key} could not be accessed, does not exist, or returned 404/403."
                }

            # Extract relevant implementation assets
            desc = details.get("description", "")
            ac = details.get("acceptance_criteria") or []
            comments = details.get("comments") or []
            attachments = details.get("attachments") or []
            
            screenshots = [
                att for att in attachments
                if any(att.get("filename", "").lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"])
            ]

            return {
                "status": "FETCHED",
                "reference_id": clean_key,
                "summary": details.get("summary", ""),
                "description": desc,
                "acceptance_criteria": ac,
                "comments": comments,
                "attachments": attachments,
                "screenshots": screenshots,
                "linked_issues": details.get("linked_issues", []),
                "issue_type": details.get("issue_type", "Task"),
                "raw_ticket": details
            }
        except Exception as e:
            return {
                "status": "INACCESSIBLE",
                "reference_id": clean_key,
                "error": f"Failed to fetch Reference Jira {clean_key} due to network/client error: {e}"
            }
