"""
FastAPI Dashboard Backend for Jira AI QA Orchestrator.
Exposes REST endpoints for ticket listing, context analysis, branch detection,
Jenkins automated deployment to testingpwa2, execution, and history.
"""

import os
import sys
from fastapi import FastAPI, Query, Body
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from database.db_manager import DatabaseManager
from modules.execution.orchestrator import ExecutionStateMachine
from modules.jira.jira_client import JiraClient
from modules.ai.context_analyzer import RequirementAnalyzer
from modules.planning.test_planner import TestPlanner
from modules.android.build_installer import BuildInstaller
from modules.deployment.jenkins_deployer import JenkinsDeployer

app = FastAPI(title="Jira AI QA Orchestrator")

db = DatabaseManager()
jira = JiraClient(mock_mode=True)
analyzer = RequirementAnalyzer()
planner = TestPlanner()
build_installer = BuildInstaller()
jenkins_deployer = JenkinsDeployer()
orchestrator = ExecutionStateMachine(db, mock_mode=True)

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "index.html")


@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    if os.path.exists(TEMPLATE_PATH):
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Jira AI QA Orchestrator UI</h1>"


@app.get("/api/tickets")
def get_tickets(live: bool = Query(True)):
    client = JiraClient(mock_mode=not live)
    tickets = client.get_assigned_tickets()
    for t in tickets:
        db.save_jira_ticket(t)
    return tickets


@app.get("/api/analyze/{ticket_key}")
def analyze_ticket(ticket_key: str, live: bool = Query(True)):
    client = JiraClient(mock_mode=not live)
    ticket = client.get_ticket_details(ticket_key)
    analysis = analyzer.analyze(ticket)
    plan = planner.generate_plan(ticket, analysis, environment="TESTING")
    build_info = build_installer.extract_build_info(ticket)
    branch_info = jenkins_deployer.extract_branch_info(ticket)
    return {
        "ticket": ticket,
        "analysis": analysis,
        "plan": plan,
        "build_info": build_info,
        "branch_info": branch_info
    }


@app.post("/api/deploy/{ticket_key}")
def deploy_branch(ticket_key: str, branch: str = Query(...), branch_type: str = Query("api"), target_env: str = Query("testingpwa2"), live: bool = Query(False)):
    """Triggers Jenkins deployment of the detected branch to the specified target server."""
    ticket = db.get_jira_ticket(ticket_key) or {}
    summary = ticket.get("summary", "").lower()
    desc = ticket.get("description", "").lower()
    
    is_bikedekho = (
        ticket_key.upper().startswith("BD") or 
        ticket_key.upper().startswith("BDCV") or 
        "bikedekho" in summary or 
        "bikedekho" in desc or 
        "bikedekho" in target_env.lower()
    )
    res = jenkins_deployer.trigger_deployment(
        branch_name=branch,
        branch_type=branch_type,
        target_env=target_env,
        is_bikedekho=is_bikedekho,
        mock_mode=not live
    )
    return res


@app.post("/api/execute/{ticket_key}")
def execute_ticket(
    ticket_key: str,
    env: str = Query("TESTING"),
    live: bool = Query(False),
    deploy_choice: Optional[str] = Query(None),
    target_server: Optional[str] = Query(None)
):
    exec_engine = ExecutionStateMachine(db, mock_mode=not live)
    result = exec_engine.run_full_orchestration(
        ticket_key=ticket_key,
        environment=env,
        deploy_choice=deploy_choice,
        target_server=target_server
    )
    return result


@app.post("/api/executions/{exec_id}/approve_bugs")
def approve_execution_bugs(exec_id: str, live: bool = Query(True)):
    """Human Approval Gate endpoint to create approved Testing Bugs in Jira and link to parent Task."""
    exec_engine = ExecutionStateMachine(db, mock_mode=not live)
    res = exec_engine.approve_and_create_bugs(exec_id)
    return res


@app.get("/api/executions")
def list_executions():
    return db.list_executions(limit=20)


@app.get("/api/health")
def health():
    return {
        "status": "ACTIVE",
        "mock_mode": True,
        "engine": "Deterministic",
        "jenkins": {
            "configured": True,
            "target_server": "testingpwa2.cardekho.com"
        }
    }
