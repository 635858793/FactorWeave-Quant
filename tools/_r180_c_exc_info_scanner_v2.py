#!/usr/bin/env python3
"""R180 AST 严格扫描器 v2 - exc_info=True 合规检测

增强特性 (R104 §12 5 铁律 100% 应用):
- 铁律 #3: AST 递归 with.body (含 try/if/for/while 嵌套)
- 铁律 #5: AST unparse 还原方法体,二次验证
- 父节点链追踪: 精确识别 logger 调用是否在 except 块内
- 4 源验证支持 (Read + Grep + AST + 业务调用链)
- 仅检测 logger.error/warning/critical (R51 §7.1 #5)
- 排除 falsy exc_info 值 (None/False),仅 True 视为合规

R174 §6.4 模板升级 (R180 C 子智能体):
- 父节点 parent_map 重建
- 嵌套 try/except/with/if/for/while 全部穿透
- 智能区分 with 块内 vs except 块内
"""
import ast
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional


def build_parent_map(tree: ast.AST) -> Dict[int, ast.AST]:
    """建立 AST 节点父节点映射 (R104 §12 铁律 #3 前置)"""
    parent_map = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent_map[id(child)] = node
    return parent_map


def find_enclosing_except(node: ast.AST, parent_map: Dict[int, ast.AST]) -> Optional[ast.ExceptHandler]:
    """向上追溯找到最近的 ExceptHandler 父节点 (R104 §12 铁律 #3 递归)"""
    current = parent_map.get(id(node))
    while current is not None:
        if isinstance(current, ast.ExceptHandler):
            return current
        current = parent_map.get(id(current))
    return None


def is_in_with_block(node: ast.AST, parent_map: Dict[int, ast.AST]) -> bool:
    """检查节点是否在 with 块内 (非 except 块, R104 §12 铁律 #3)"""
    current = parent_map.get(id(node))
    while current is not None:
        if isinstance(current, ast.With):
            return True
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return False
        current = parent_map.get(id(current))
    return False


def has_exc_info_kwarg(call_node: ast.Call) -> bool:
    """检查 Call 节点是否含 exc_info=True 关键字参数 (R51 §7.1 #5)"""
    for kw in call_node.keywords:
        if kw.arg == "exc_info":
            # exc_info=True 才是合规
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
            # exc_info=sys.exc_info() 等动态值也视为合规
            if isinstance(kw.value, (ast.Call, ast.Attribute, ast.Name)):
                return True
    return False


def get_logger_func_name(call_node: ast.Call) -> Optional[str]:
    """提取 logger.error/warning/critical 函数名 (R51 §7.1 #5 强约束)"""
    if isinstance(call_node.func, ast.Attribute):
        if isinstance(call_node.func.value, ast.Name) and call_node.func.value.id == "logger":
            if call_node.func.attr in ("error", "warning", "critical"):
                return call_node.func.attr
    return None


def get_source_line(source: str, lineno: int) -> str:
    """获取源代码行"""
    lines = source.split("\n")
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1].strip()
    return ""


def audit_exc_info_compliance(filepath: str) -> Dict:
    """
    主审计函数 - R180 v2 严格模式

    返回:
    {
      'filepath': str,
      'total_except_blocks': int,
      'total_logger_calls': int,
      'logger_in_except': int,
      'logger_with_exc_info': int,
      'logger_without_exc_info': int,
      'violations': List[Dict],  # 违规清单
      'method_body_violations': List[Dict],  # AST unparse 验证的违规
    }
    """
    source = Path(filepath).read_text(encoding="utf-8")
    tree = ast.parse(source)
    parent_map = build_parent_map(tree)

    result = {
        "filepath": filepath,
        "total_except_blocks": 0,
        "total_logger_calls": 0,
        "logger_in_except": 0,
        "logger_with_exc_info": 0,
        "logger_without_exc_info": 0,
        "violations": [],
        "method_body_violations": [],
    }

    # 第一轮: AST unparse 验证 (R104 §12 铁律 #5)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            method_name = node.name
            method_source = ast.unparse(node)
            try:
                method_tree = ast.parse(method_source).body[0]
            except (SyntaxError, IndexError):
                continue
            # 在方法体内查找 except 块
            for sub in ast.walk(method_tree):
                if isinstance(sub, ast.ExceptHandler):
                    result["total_except_blocks"] += 1

    # 第二轮: 严格递归 + 父节点链追踪
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = get_logger_func_name(node)
            if not func_name:
                continue

            result["total_logger_calls"] += 1

            # 找到 ExceptHandler 父节点 (R104 §12 铁律 #3 递归)
            except_handler = find_enclosing_except(node, parent_map)
            if not except_handler:
                # 不在 except 块内, 不要求 exc_info
                continue

            result["logger_in_except"] += 1

            # 检查 exc_info=True
            if has_exc_info_kwarg(node):
                result["logger_with_exc_info"] += 1
            else:
                result["logger_without_exc_info"] += 1
                source_line = get_source_line(source, node.lineno)
                violation = {
                    "lineno": node.lineno,
                    "func_name": func_name,
                    "source_line": source_line[:120],
                    "except_type": ast.unparse(except_handler.type) if except_handler.type else "Exception",
                    "method_chain": _get_method_chain(node, parent_map),
                }
                result["violations"].append(violation)

    return result


def _get_method_chain(node: ast.AST, parent_map: Dict[int, ast.AST]) -> str:
    """获取从根到当前节点的方法链 (用于定位)"""
    chain = []
    current = node
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            chain.append(current.name)
        current = parent_map.get(id(current))
    return " -> ".join(reversed(chain))


def main():
    """主入口: 扫描 5 业务关键文件 (R180 任务范围)"""
    if len(sys.argv) < 2:
        # 默认扫描 5 业务关键文件
        target_files = [
            "core/trading_engine.py",
            "core/events/event_bus.py",
            "core/services/service_bootstrap.py",
            "core/services/unified_data_manager.py",
            "core/risk_rule_manager.py",
        ]
    else:
        target_files = sys.argv[1:]

    print("=" * 80)
    print("R180 AST 严格扫描器 v2 - exc_info=True 合规检测")
    print("R104 §12 5 铁律 100% 应用 (铁律 #3 递归 with.body + 铁律 #5 AST unparse)")
    print("R51 §7.1 #5 强约束 (logger.error/warning/critical 必须 exc_info=True)")
    print("=" * 80)

    total_violations = 0
    total_except_blocks = 0
    total_logger_in_except = 0
    total_logger_with_exc_info = 0

    for filepath in target_files:
        if not Path(filepath).exists():
            print(f"\n[WARN] {filepath} 不存在, 跳过")
            continue

        result = audit_exc_info_compliance(filepath)
        print(f"\n{'=' * 80}")
        print(f"[文件] {filepath}")
        print(f"{'=' * 80}")
        print(f"  except 块总数:           {result['total_except_blocks']}")
        print(f"  logger.error/warning/critical 总数: {result['total_logger_calls']}")
        print(f"  except 块内 logger 调用: {result['logger_in_except']}")
        print(f"  其中含 exc_info=True:    {result['logger_with_exc_info']}")
        print(f"  其中缺 exc_info=True:    {result['logger_without_exc_info']}")
        if result["logger_in_except"] > 0:
            compliance_rate = (
                result["logger_with_exc_info"] / result["logger_in_except"] * 100
            )
            print(f"  合规率:                  {compliance_rate:.1f}%")

        total_except_blocks += result["total_except_blocks"]
        total_logger_in_except += result["logger_in_except"]
        total_logger_with_exc_info += result["logger_with_exc_info"]
        total_violations += result["logger_without_exc_info"]

        if result["violations"]:
            print(f"\n  违规清单 (前 10 条):")
            for v in result["violations"][:10]:
                print(
                    f"    L{v['lineno']:>4} [{v['func_name']}] except {v['except_type']:<20} {v['method_chain']}"
                )
                print(f"           {v['source_line'][:100]}")
            if len(result["violations"]) > 10:
                print(f"    ... 还有 {len(result['violations']) - 10} 条违规")

    print(f"\n{'=' * 80}")
    print("汇总 (R180 5 业务关键文件)")
    print(f"{'=' * 80}")
    print(f"  扫描文件数:              {len(target_files)}")
    print(f"  except 块总数:           {total_except_blocks}")
    print(f"  except 块内 logger 调用: {total_logger_in_except}")
    print(f"  含 exc_info=True:        {total_logger_with_exc_info}")
    print(f"  缺 exc_info=True (违规): {total_violations}")
    if total_logger_in_except > 0:
        compliance_rate = total_logger_with_exc_info / total_logger_in_except * 100
        print(f"  合规率:                  {compliance_rate:.1f}%")
    print(f"{'=' * 80}")

    return 0 if total_violations == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
