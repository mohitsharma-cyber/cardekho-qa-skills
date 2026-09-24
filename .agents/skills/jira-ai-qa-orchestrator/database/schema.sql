-- SQLite Database Schema for Jira AI QA Orchestrator

CREATE TABLE IF NOT EXISTS jira_tickets (
    id TEXT PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    summary TEXT NOT NULL,
    description TEXT,
    acceptance_criteria TEXT,
    issue_type TEXT,
    priority TEXT,
    status TEXT,
    labels TEXT,
    assignee TEXT,
    reporter TEXT,
    project_key TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS test_plans (
    id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    title TEXT,
    scope TEXT,
    out_of_scope TEXT,
    functional_risks TEXT,
    regression_risks TEXT,
    dependencies TEXT,
    ambiguities TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(ticket_id) REFERENCES jira_tickets(id)
);

CREATE TABLE IF NOT EXISTS test_cases (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    ticket_key TEXT NOT NULL,
    test_case_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL, -- DIRECT, IMPACTED_REGRESSION, EXTENDED_REGRESSION
    priority TEXT NOT NULL, -- P0, P1, P2, P3
    preconditions TEXT,
    test_data TEXT,
    steps TEXT NOT NULL, -- JSON array of steps
    expected_result TEXT NOT NULL,
    required_environment TEXT DEFAULT 'TESTING',
    device_required BOOLEAN DEFAULT 0,
    api_required BOOLEAN DEFAULT 0,
    assertion_definition TEXT NOT NULL, -- JSON string
    status TEXT DEFAULT 'NOT_EXECUTED', -- NOT_EXECUTED, RUNNING, PASSED, FAILED, BLOCKED, SKIPPED
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(plan_id) REFERENCES test_plans(id)
);

CREATE TABLE IF NOT EXISTS executions (
    id TEXT PRIMARY KEY, -- EXEC-UUID
    ticket_key TEXT NOT NULL,
    plan_id TEXT,
    environment TEXT NOT NULL, -- TESTING, STAGING
    device_used TEXT,
    state TEXT NOT NULL, -- State machine state
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    total_tests INTEGER DEFAULT 0,
    passed_tests INTEGER DEFAULT 0,
    failed_tests INTEGER DEFAULT 0,
    blocked_tests INTEGER DEFAULT 0,
    skipped_tests INTEGER DEFAULT 0,
    overall_result TEXT DEFAULT 'PENDING', -- PASSED, FAILED, BLOCKED, PARTIAL
    risk_level TEXT DEFAULT 'MEDIUM',
    jira_updated BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS execution_steps (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    test_case_id TEXT NOT NULL,
    step_number INTEGER NOT NULL,
    action TEXT NOT NULL,
    locator TEXT,
    input_value TEXT,
    expected TEXT,
    actual TEXT,
    status TEXT NOT NULL, -- PASSED, FAILED, BLOCKED
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(execution_id) REFERENCES executions(id)
);

CREATE TABLE IF NOT EXISTS assertions (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    test_case_id TEXT NOT NULL,
    assertion_type TEXT NOT NULL, -- STATUS_CODE, ELEMENT_VISIBLE, TEXT_MATCH, URL_MATCH, JSON_PATH
    expected_value TEXT NOT NULL,
    actual_value TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    evidence_id TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(execution_id) REFERENCES executions(id)
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    test_case_id TEXT,
    evidence_type TEXT NOT NULL, -- SCREENSHOT, API_LOG, CONSOLE_LOG, HAR, DEVICE_LOG
    file_path TEXT NOT NULL,
    content_text TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(execution_id) REFERENCES executions(id)
);

CREATE TABLE IF NOT EXISTS api_calls (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    test_case_id TEXT,
    url TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER,
    response_time_ms INTEGER,
    classification TEXT NOT NULL, -- BUSINESS_API, ANALYTICS, THIRD_PARTY, STATIC_ASSET, UNKNOWN
    request_headers TEXT,
    request_body TEXT,
    response_body TEXT,
    is_redacted BOOLEAN DEFAULT 1,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(execution_id) REFERENCES executions(id)
);

CREATE TABLE IF NOT EXISTS device_sessions (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    serial TEXT NOT NULL,
    model TEXT,
    brand TEXT,
    os_version TEXT,
    sdk_version TEXT,
    package_name TEXT,
    appium_port INTEGER,
    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(execution_id) REFERENCES executions(id)
);

CREATE TABLE IF NOT EXISTS failure_analyses (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    test_case_id TEXT NOT NULL,
    classification TEXT NOT NULL, -- APPLICATION_ERROR, ENVIRONMENT_ERROR, NETWORK_ERROR, DEVICE_ERROR, AUTH_ERROR
    root_cause TEXT NOT NULL,
    facts TEXT NOT NULL,
    evidence TEXT NOT NULL,
    inference TEXT,
    recommendation TEXT,
    confidence REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(execution_id) REFERENCES executions(id)
);

CREATE TABLE IF NOT EXISTS jira_updates (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    ticket_key TEXT NOT NULL,
    update_type TEXT NOT NULL, -- COMMENT, BUG_CREATED
    target_key TEXT,
    content TEXT NOT NULL,
    status TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(execution_id) REFERENCES executions(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    execution_id TEXT,
    user TEXT NOT NULL,
    ticket_key TEXT,
    environment TEXT,
    action TEXT NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS environment_profiles (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    base_url TEXT NOT NULL,
    base_api_url TEXT,
    my_account_url TEXT,
    ask_ai_url TEXT,
    is_production BOOLEAN DEFAULT 0,
    blocked BOOLEAN DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
