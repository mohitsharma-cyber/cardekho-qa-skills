import pytest
import os
import sys

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from database.db_manager import DatabaseManager
from modules.execution.orchestrator import ExecutionStateMachine


def test_end_to_end_mock_orchestration():
    db = DatabaseManager()
    sm = ExecutionStateMachine(db=db, mock_mode=True)

    result = sm.run_full_orchestration(ticket_key="CD-145", environment="TESTING")

    assert result is not None
    assert "execution_id" in result
    assert result["overall_status"] == "PASSED"
    assert result["metrics"]["generated"] == 4
    assert result["metrics"]["passed"] == 4
    assert result["metrics"]["failed"] == 0

    # Verify database persistence
    exec_row = db.get_execution(result["execution_id"])
    assert exec_row is not None
    assert exec_row["ticket_key"] == "CD-145"
    assert exec_row["overall_result"] == "PASSED"

    # Verify audit trail
    audit_logs = db.get_audit_logs(execution_id=result["execution_id"])
    assert len(audit_logs) >= 5
    assert any("TICKET_SELECTED" in log["action"] for log in audit_logs)
    assert any("COMPLETED" in log["action"] for log in audit_logs)
