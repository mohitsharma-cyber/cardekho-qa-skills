import pytest
import os
import sys

# Add root package to path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from modules.jira.jira_client import JiraClient


def test_mock_jira_tickets():
    client = JiraClient(mock_mode=True)
    tickets = client.get_assigned_tickets()
    assert len(tickets) >= 3
    assert any(t["key"] == "CD-123" for t in tickets)


def test_ticket_context_retrieval():
    client = JiraClient(mock_mode=True)
    ticket = client.get_ticket_details("CD-145")
    assert ticket["key"] == "CD-145"
    assert "Search filter" in ticket["summary"]
    assert ticket["acceptance_criteria"] != ""


def test_jira_comment_mock():
    client = JiraClient(mock_mode=True)
    ok = client.add_comment("CD-145", "Automated QA Test Comment")
    assert ok is True
