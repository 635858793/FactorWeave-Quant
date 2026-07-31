"""R202-B 验证脚本"""
import ast
import re
from pathlib import Path

# 1. 验证 orders.py 6 处端点
api_file = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\web\backend\api\v1\orders.py")
api_source = api_file.read_text(encoding="utf-8")
api_tree = ast.parse(api_source)

endpoints = ["get_orders", "get_order", "update_order", "cancel_order", "get_order_fills", "get_order_analysis"]
print("=== 6 处 API 端点 account_id 透传验证 ===")
for ep in endpoints:
    func = None
    for node in ast.walk(api_tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == ep:
            func = node
            break
    if not func:
        print(f"[FAIL] {ep}: 函数未找到")
        continue
    sig = ast.unparse(func.args)
    has_account_id = "account_id" in sig
    has_r202b = "[R202-B P0" in (ast.get_docstring(func) or "")
    body = ast.unparse(func)
    service_method = ep if ep != "get_order" else "get_order_by_id"
    has_pass = f"order_service.{service_method}" in body and "account_id=account_id" in body
    status = "OK" if (has_account_id and has_r202b and has_pass) else "FAIL"
    print(f"[{status}] {ep}: account_id={has_account_id}, R202-B P0 marker={has_r202b}, 透传 service={has_pass}")

# 2. 验证 OrderService 6 个方法签名
service_file = Path(r"d:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\web\backend\services\order_service.py")
service_source = service_file.read_text(encoding="utf-8")
service_tree = ast.parse(service_source)
print()
print("=== OrderService 6 个方法 account_id: str 签名验证 (R201-B) ===")
service_methods = ["get_orders", "get_order_by_id", "update_order", "cancel_order", "get_order_fills", "get_order_analysis"]
for m in service_methods:
    func = None
    for node in ast.walk(service_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == m:
            func = node
            break
    if not func:
        print(f"[FAIL] OrderService.{m}: 方法未找到")
        continue
    sig = ast.unparse(func.args)
    has = bool(re.search(r"account_id\s*:\s*(?:str|Optional\[str\])\s*=\s*None", sig))
    status = "OK" if has else "FAIL"
    print(f"[{status}] OrderService.{m}: account_id: str 签名存在={has}")

# 3. 验证 orders.py 中 [R202-B P0] 标记总数
markers = api_source.count("[R202-B P0")
print()
print(f"=== orders.py [R202-B P0] 标记总数: {markers} (期望 >= 12) ===")
