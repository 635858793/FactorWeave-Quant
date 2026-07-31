#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test if ai_selection_risk_control_service.py has syntax error"""
import ast
import sys

sys.stdout.reconfigure(encoding='utf-8')

try:
    with open(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\core\services\ai_selection_risk_control_service.py', encoding='utf-8') as f:
        src = f.read()
    ast.parse(src)
    with open(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\_r192_syntax_check.txt', 'w', encoding='utf-8') as f:
        f.write("OK: File parses correctly\n")
except SyntaxError as e:
    with open(r'd:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\_r192_syntax_check.txt', 'w', encoding='utf-8') as f:
        f.write(f"SYNTAX ERROR: line {e.lineno}, col {e.offset}: {e.msg}\n")
        f.write(f"  text: {e.text}\n")
        # Show problematic line
        lines = src.split('\n')
        if e.lineno and e.lineno <= len(lines):
            f.write(f"  L{e.lineno}: {lines[e.lineno-1]}\n")
print("DONE")
