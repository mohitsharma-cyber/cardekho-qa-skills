import json
import sys
from modules.jira.jira_client import JiraClient

ticket_key = sys.argv[1] if len(sys.argv) > 1 else 'MB2C-1998'
client = JiraClient()
issue = client.get_ticket_details(ticket_key)

print("=== TICKET KEY ===")
print(issue.get("key"))
print("=== SUMMARY ===")
print(issue.get("summary"))
print("=== STATUS ===")
print(issue.get("status"))
print("=== PRIORITY ===")
print(issue.get("priority"))
print("=== DESCRIPTION ===")
print(issue.get("description"))
print("=== ACCEPTANCE CRITERIA ===")
print(issue.get("acceptance_criteria"))
print("=== LABELS ===")
print(issue.get("labels"))
print("=== COMMENTS ===")
for c in issue.get("comments", []):
    print("AUTHOR:", c.get("author"))
    print("BODY:", c.get("body"))
    print("---")
print("=== LINKED ISSUES ===")
for l in issue.get("linked_issues", []):
    print(l)
