# Antigravity Permission Security Hook for CarDekho QA Automation Workspace
# Enforces granular security policies at the PreToolUse lifecycle hook level.

import sys
import json
import re
import os

# Blocked file targets (credentials, secrets, private keys)
BLOCKED_FILE_REGEXES = [
    re.compile(r'(^|[/\\])\.env($|\..*)', re.I),
    re.compile(r'(^|[/\\]).*credentials.*\.json$', re.I),
    re.compile(r'(^|[/\\])jira_credentials\.json$', re.I),
    re.compile(r'(^|[/\\])id_rsa(\.pub)?$', re.I),
    re.compile(r'(^|[/\\])id_ed25519(\.pub)?$', re.I),
    re.compile(r'(^|[/\\]).*\.pem$', re.I),
    re.compile(r'(^|[/\\]).*\.key$', re.I),
]

# Command patterns that are hard blocked (Dangerous)
BLOCK_COMMAND_PATTERNS = [
    (re.compile(r'\b(rm|rmdir|del|Remove-Item)\b.*(-rf|-fr|-Recurse|/s\s+/q)\s*(\.|\*|[a-zA-Z]:[/\\]|/|\\)', re.I),
     'Recursive deletion of project root or system directories is blocked by security policy.'),
    (re.compile(r'\bgit\s+clean\s+-[xX]?[fF]', re.I),
     'Git force clean is blocked by security policy.'),
    (re.compile(r'\b(DROP\s+TABLE|DROP\s+DATABASE|TRUNCATE\s+TABLE)\b', re.I),
     'Destructive database operations (DROP/TRUNCATE) are strictly blocked.'),
    (re.compile(r'\bDELETE\s+FROM\s+\w+\s*(;|$)', re.I),
     'Unbounded DELETE statements without WHERE clause are strictly blocked.'),
    (re.compile(r'\b(cat|type|Get-Content|head|tail|more|less)\b.*(\.env|jira_credentials|credentials\.json|id_rsa|id_ed25519|\.pem|\.key)', re.I),
     'Attempting to read or exfiltrate secrets, tokens, or credentials is blocked.'),
    (re.compile(r'\b(curl|Invoke-RestMethod|Invoke-WebRequest)\b.*(-X\s*(DELETE|POST|PUT|PATCH)|--request\s*(DELETE|POST|PUT|PATCH)|-Method\s*(DELETE|POST|PUT|PATCH)).*(cardekho\.com|bikedekho\.com)', re.I),
     'Destructive production write/DELETE API requests are blocked.'),
    (re.compile(r'\b(curl|Invoke-RestMethod|Invoke-WebRequest)\b.*(cardekho\.com|bikedekho\.com).*(-X\s*(DELETE|POST|PUT|PATCH)|--request\s*(DELETE|POST|PUT|PATCH)|-Method\s*(DELETE|POST|PUT|PATCH))', re.I),
     'Destructive production write/DELETE API requests are blocked.'),
]

# Command patterns that require explicit user prompt (Ask)
ASK_COMMAND_PATTERNS = [
    (re.compile(r'^\s*(python|py|python3)(\.exe)?\s+(-c\b|--command\b)', re.I),
     'Arbitrary inline Python execution requires explicit user confirmation.'),
    (re.compile(r'^\s*(powershell|pwsh)(\.exe)?\s+(-[cC]ommand|-[eE]ncodedCommand|-c)\b', re.I),
     'Arbitrary inline PowerShell command execution requires explicit confirmation.'),
    (re.compile(r'^\s*cmd(\.exe)?\s+/[cC]\b', re.I),
     'Arbitrary inline cmd.exe execution requires explicit confirmation.'),
    (re.compile(r'\bgit\s+(reset|restore|clean|checkout)\b', re.I),
     'Git state-altering command (reset/restore/checkout) requires user confirmation.'),
    (re.compile(r'\b(del|rm|Remove-Item)\b(?!\s+.*[/\\](scratch|\.tempmediaStorage)[/\\])', re.I),
     'Deleting workspace files outside scratch directory requires user confirmation.'),
]

# Command patterns that are trusted QA automation operations (Allow)
ALLOW_COMMAND_PATTERNS = [
    re.compile(r'^\s*pytest\b', re.I),
    re.compile(r'^\s*(python|py|python3)(\.exe)?\s+(-m\s+)?(pytest|unittest)\b', re.I),
    # Allow python script execution with or without quotes, with spaces in path
    re.compile(r'^\s*(python|py|python3)(\.exe)?\s+(-u\s+)?("([^"]+\.py)"|[^\s"]+\.py)(\s+.*)?$', re.I),
    re.compile(r'^\s*adb(\.exe)?\s+devices(\s+-l)?\s*$', re.I),
    re.compile(r'^\s*adb(\.exe)?\s+logcat\b', re.I),
    re.compile(r'^\s*adb(\.exe)?\s+screencap\b', re.I),
    re.compile(r'^\s*adb(\.exe)?\s+uiautomator\b', re.I),
    re.compile(r'^\s*adb(\.exe)?\s+shell\s+(dumpsys|getprop|input|am|pm|screencap|uiautomator|settings|wm|cmd)\b', re.I),
    re.compile(r'^\s*adb(\.exe)?\s+(forward|reverse|install|uninstall|pull|push|reconnect)\b', re.I),
    re.compile(r'^\s*git\s+(status|diff|log|show|branch|rev-parse|remote)\b', re.I),
    re.compile(r'^\s*(npm|npm\.cmd)\s+(start|test|run|list|ci|install)\b', re.I),
    re.compile(r'^\s*uvicorn\b', re.I),
]

def evaluate_tool_call(tool_name, args):
    # 1. Block access to sensitive files
    for key in ['TargetFile', 'AbsolutePath', 'SearchPath']:
        target = args.get(key)
        if target:
            norm = target.replace('\\', '/')
            for pat in BLOCKED_FILE_REGEXES:
                if pat.search(norm):
                    return {
                        'decision': 'deny',
                        'reason': f'Access to sensitive file "{target}" is blocked by QA security policy.'
                    }

    # 2. Inspect run_command CommandLine
    if tool_name == 'run_command':
        cmd = (args.get('CommandLine') or '').strip()

        # Hard blocks
        for pat, reason in BLOCK_COMMAND_PATTERNS:
            if pat.search(cmd):
                return {'decision': 'deny', 'reason': reason}

        # Risky commands requiring explicit user prompt
        for pat, reason in ASK_COMMAND_PATTERNS:
            if pat.search(cmd):
                return {'decision': 'ask', 'reason': reason}

        # Trusted QA operations
        for pat in ALLOW_COMMAND_PATTERNS:
            if pat.search(cmd):
                return {
                    'decision': 'allow',
                    'reason': f'Trusted CarDekho QA operation auto-allowed: {cmd[:60]}'
                }

        # Unrecognized commands require confirmation
        return {
            'decision': 'ask',
            'reason': f'Command "{cmd[:60]}" is not in the trusted QA allowlist. Asking for approval.'
        }

    # 3. Read-only inspection tools
    if tool_name in ['view_file', 'grep_search', 'find_by_name', 'list_dir', 'read_url_content']:
        return {
            'decision': 'allow',
            'reason': f'Read-only inspection tool "{tool_name}" auto-allowed.'
        }

    # 4. Modifying tools
    if tool_name in ['write_to_file', 'replace_file_content']:
        target = (args.get('TargetFile') or '').replace('\\', '/')
        if '/scratch/' in target or '/.tempmediaStorage/' in target or target.endswith('.tmp'):
            return {
                'decision': 'allow',
                'reason': f'Writing to temporary scratch/test artifact auto-allowed: {target}'
            }
        return {
            'decision': 'ask',
            'reason': f'Modifying workspace source file requires confirmation: {target}'
        }

    return {'decision': 'ask', 'reason': f'Tool "{tool_name}" requires confirmation.'}

def main():
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({'decision': 'allow', 'reason': 'Empty input, allowing.'}))
            return

        payload = json.loads(raw_input)
        tool_call = payload.get('toolCall') or payload.get('tool_call') or {}
        tool_name = tool_call.get('name') or ''
        args = tool_call.get('args') or {}

        result = evaluate_tool_call(tool_name, args)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({'decision': 'ask', 'reason': f'Security hook evaluation error: {str(e)}'}))

if __name__ == '__main__':
    main()
