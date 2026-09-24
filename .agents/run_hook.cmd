@echo off
if exist "%~dp0security\permission_hook.py" (
    python "%~dp0security\permission_hook.py"
) else if exist "%~dp0.agents\security\permission_hook.py" (
    python "%~dp0.agents\security\permission_hook.py"
) else (
    python "%CD%\.agents\security\permission_hook.py"
)
