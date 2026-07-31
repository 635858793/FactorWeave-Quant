#!/usr/bin/env python3
"""R168-D 6 个 SYNTAX_ERROR 真事故验证脚本 (R104 §12 铁律 #1 R+1 round 二次验证)"""
import ast
import sys

FILES = [
    "core/agents/risk_agent.py",
    "core/risk_monitoring/enhanced_risk_monitor.py",
    "core/services/ai_selection_risk_control_service.py",
    "core/risk_alert.py",
    "core/trading/account_manager.py",
    "core/services/signal_trading_bridge.py",
]

def verify_syntax(path: str) -> tuple[str, str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        ast.parse(src, filename=path)
        return "OK", ""
    except SyntaxError as e:
        return "SYNTAX_ERROR", f"L{e.lineno}: {e.msg}"
    except Exception as e:
        return "ERROR", f"{type(e).__name__}: {e}"

print("=" * 80)
print("R168-D 6 个生产文件 SYNTAX_ERROR 真事故验证 (R+1 round 4 源 100% 命中)")
print("=" * 80)

ok_count = 0
err_count = 0
for f in FILES:
    status, msg = verify_syntax(f)
    if status == "OK":
        print(f"  [OK]  {f}")
        ok_count += 1
    else:
        print(f"  [ERR] {f} -> {msg}")
        err_count += 1

print("=" * 80)
print(f"统计: {ok_count}/6 OK, {err_count}/6 SYNTAX_ERROR")
print("=" * 80)
sys.exit(err_count)
