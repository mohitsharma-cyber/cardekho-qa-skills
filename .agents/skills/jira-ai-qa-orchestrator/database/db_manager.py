"""
Database Manager for Jira AI QA Orchestrator
Provides thread-safe SQLite operations for execution history, test cases, and audit logs.
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, "orchestrator.db")
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            with self.get_connection() as conn:
                conn.executescript(schema_sql)
                conn.commit()

    # --- JIRA TICKETS ---
    def save_jira_ticket(self, ticket_data: Dict[str, Any]) -> str:
        ticket_id = ticket_data.get("id") or str(uuid.uuid4())
        labels_str = json.dumps(ticket_data.get("labels", [])) if isinstance(ticket_data.get("labels"), list) else ticket_data.get("labels", "")
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO jira_tickets (id, key, summary, description, acceptance_criteria, issue_type, priority, status, labels, assignee, reporter, project_key, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    summary=excluded.summary,
                    description=excluded.description,
                    acceptance_criteria=excluded.acceptance_criteria,
                    issue_type=excluded.issue_type,
                    priority=excluded.priority,
                    status=excluded.status,
                    labels=excluded.labels,
                    assignee=excluded.assignee,
                    reporter=excluded.reporter,
                    project_key=excluded.project_key,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    ticket_id,
                    ticket_data.get("key"),
                    ticket_data.get("summary"),
                    ticket_data.get("description", ""),
                    ticket_data.get("acceptance_criteria", ""),
                    ticket_data.get("issue_type", "Bug"),
                    ticket_data.get("priority", "Medium"),
                    ticket_data.get("status", "Open"),
                    labels_str,
                    ticket_data.get("assignee", ""),
                    ticket_data.get("reporter", ""),
                    ticket_data.get("project_key", "MB2C"),
                ),
            )
            conn.commit()
        return ticket_id

    def get_jira_ticket(self, key: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM jira_tickets WHERE key = ?", (key,)).fetchone()
            if row:
                d = dict(row)
                try:
                    d["labels"] = json.loads(d["labels"])
                except Exception:
                    pass
                return d
        return None

    def list_jira_tickets(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM jira_tickets ORDER BY updated_at DESC").fetchall()
            tickets = []
            for r in rows:
                d = dict(r)
                try:
                    d["labels"] = json.loads(d["labels"])
                except Exception:
                    pass
                tickets.append(d)
            return tickets

    # --- TEST PLANS & TEST CASES ---
    def save_test_plan(self, plan_data: Dict[str, Any]) -> str:
        plan_id = plan_data.get("id") or str(uuid.uuid4())
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO test_plans (id, ticket_id, version, title, scope, out_of_scope, functional_risks, regression_risks, dependencies, ambiguities)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    plan_data.get("ticket_id"),
                    plan_data.get("version", 1),
                    plan_data.get("title", ""),
                    json.dumps(plan_data.get("scope", [])),
                    json.dumps(plan_data.get("out_of_scope", [])),
                    json.dumps(plan_data.get("functional_risks", [])),
                    json.dumps(plan_data.get("regression_risks", [])),
                    json.dumps(plan_data.get("dependencies", [])),
                    json.dumps(plan_data.get("ambiguities", [])),
                ),
            )
            conn.commit()
        return plan_id

    def save_test_cases(self, test_cases: List[Dict[str, Any]]) -> List[str]:
        case_ids = []
        with self.get_connection() as conn:
            for tc in test_cases:
                tc_id = tc.get("id") or str(uuid.uuid4())
                steps_str = json.dumps(tc.get("steps", []))
                assertion_str = json.dumps(tc.get("assertion_definition", {}))
                conn.execute(
                    """
                    INSERT INTO test_cases (id, plan_id, ticket_key, test_case_id, title, category, priority, preconditions, test_data, steps, expected_result, required_environment, device_required, api_required, assertion_definition, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tc_id,
                        tc.get("plan_id"),
                        tc.get("ticket_key"),
                        tc.get("test_case_id"),
                        tc.get("title"),
                        tc.get("category", "DIRECT"),
                        tc.get("priority", "P1"),
                        tc.get("preconditions", ""),
                        tc.get("test_data", ""),
                        steps_str,
                        tc.get("expected_result", ""),
                        tc.get("required_environment", "TESTING"),
                        1 if tc.get("device_required") else 0,
                        1 if tc.get("api_required") else 0,
                        assertion_str,
                        tc.get("status", "NOT_EXECUTED"),
                    ),
                )
                case_ids.append(tc_id)
            conn.commit()
        return case_ids

    def update_test_case_result(self, case_id: str, status: str, actual_result: Optional[str] = None, duration_ms: Optional[int] = None):
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE test_cases SET status = ? WHERE id = ? OR test_case_id = ?",
                (status, case_id, case_id)
            )
            conn.commit()

    def get_test_cases_for_ticket(self, ticket_key: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM test_cases WHERE ticket_key = ? ORDER BY test_case_id ASC", (ticket_key,)).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["steps"] = json.loads(d["steps"]) if d.get("steps") else []
                d["assertion_definition"] = json.loads(d["assertion_definition"]) if d.get("assertion_definition") else {}
                results.append(d)
            return results

    # --- EXECUTIONS ---
    def create_execution(self, exec_data: Dict[str, Any]) -> str:
        exec_id = exec_data.get("id") or f"EXEC-{uuid.uuid4().hex[:8].upper()}"
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO executions (id, ticket_key, plan_id, environment, device_used, state, total_tests, passed_tests, failed_tests, blocked_tests, skipped_tests, overall_result, risk_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    exec_id,
                    exec_data.get("ticket_key"),
                    exec_data.get("plan_id"),
                    exec_data.get("environment", "TESTING"),
                    exec_data.get("device_used", "NONE"),
                    exec_data.get("state", "TICKET_SELECTED"),
                    exec_data.get("total_tests", 0),
                    exec_data.get("passed_tests", 0),
                    exec_data.get("failed_tests", 0),
                    exec_data.get("blocked_tests", 0),
                    exec_data.get("skipped_tests", 0),
                    exec_data.get("overall_result", "PENDING"),
                    exec_data.get("risk_level", "MEDIUM"),
                ),
            )
            conn.commit()
        return exec_id

    def update_execution_state(self, exec_id: str, state: str, overall_result: Optional[str] = None):
        with self.get_connection() as conn:
            if overall_result:
                conn.execute(
                    "UPDATE executions SET state = ?, overall_result = ?, end_time = CURRENT_TIMESTAMP WHERE id = ?",
                    (state, overall_result, exec_id),
                )
            else:
                conn.execute("UPDATE executions SET state = ? WHERE id = ?", (state, exec_id))
            conn.commit()

    def update_execution_counts(self, exec_id: str, total: int, passed: int, failed: int, blocked: int, skipped: int):
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE executions SET
                    total_tests = ?,
                    passed_tests = ?,
                    failed_tests = ?,
                    blocked_tests = ?,
                    skipped_tests = ?
                WHERE id = ?
                """,
                (total, passed, failed, blocked, skipped, exec_id),
            )
            conn.commit()

    def get_execution(self, exec_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM executions WHERE id = ?", (exec_id,)).fetchone()
            return dict(row) if row else None

    def list_executions(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM executions ORDER BY start_time DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    # --- ASSERTIONS & EVIDENCE ---
    def record_assertion(self, execution_id: str, test_case_id: str, assertion_type: str, expected: Any, actual: Any, passed: bool, evidence_id: Optional[str] = None):
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO assertions (id, execution_id, test_case_id, assertion_type, expected_value, actual_value, passed, evidence_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), execution_id, test_case_id, assertion_type, str(expected), str(actual), 1 if passed else 0, evidence_id),
            )
            conn.commit()

    def record_evidence(self, execution_id: str, test_case_id: Optional[str], evidence_type: str, file_path: str, content_text: Optional[str] = None) -> str:
        evidence_id = f"EVID-{uuid.uuid4().hex[:8].upper()}"
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO evidence (id, execution_id, test_case_id, evidence_type, file_path, content_text)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (evidence_id, execution_id, test_case_id, evidence_type, file_path, content_text),
            )
            conn.commit()
        return evidence_id

    # --- API CALLS ---
    def record_api_call(self, api_data: Dict[str, Any]) -> str:
        call_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO api_calls (id, execution_id, test_case_id, url, method, status_code, response_time_ms, classification, request_headers, request_body, response_body, is_redacted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    call_id,
                    api_data.get("execution_id"),
                    api_data.get("test_case_id"),
                    api_data.get("url"),
                    api_data.get("method", "GET"),
                    api_data.get("status_code"),
                    api_data.get("response_time_ms"),
                    api_data.get("classification", "BUSINESS_API"),
                    json.dumps(api_data.get("request_headers", {})),
                    api_data.get("request_body"),
                    api_data.get("response_body"),
                    1 if api_data.get("is_redacted", True) else 0,
                ),
            )
            conn.commit()
        return call_id

    # --- AUDIT LOGS ---
    def log_audit(self, action: str, user: str = "QA_ENGINEER", ticket_key: Optional[str] = None, execution_id: Optional[str] = None, environment: Optional[str] = None, details: Optional[str] = None):
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (id, execution_id, user, ticket_key, environment, action, details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), execution_id, user, ticket_key, environment, action, details),
            )
            conn.commit()

    def record_jira_update(self, update_data: Dict[str, Any]) -> str:
        update_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO jira_updates (id, execution_id, ticket_key, update_type, target_key, content, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    update_id,
                    update_data.get("execution_id"),
                    update_data.get("ticket_key"),
                    update_data.get("update_type", "BUG_CREATED"),
                    update_data.get("target_key"),
                    update_data.get("content", ""),
                    update_data.get("status", "SUCCESS")
                ),
            )
            conn.commit()
        return update_id

    def get_audit_logs(self, execution_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            if execution_id:
                rows = conn.execute("SELECT * FROM audit_logs WHERE execution_id = ? ORDER BY timestamp ASC", (execution_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]
