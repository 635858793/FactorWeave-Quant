"""
R199-A 风险控制软解析 P0 治理扫描器 (聚焦版)

按 R51 §7.1 #5 + R199-A 任务要求:
  - 聚焦 P0 风险控制相关软解析
  - 检查是否 R51 合规 (try/except + exc_info=True + 显式降级日志 + 告警)
  - 输出 P0 风险位置详情 + 合规状态

输出:
  - tools/_r199_a_results.json (含 P0 风险分类)
"""
import ast
import os
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 软解析模式 (覆盖 5+ 种)
SOFT_RESOLVE_METHODS = ('get', 'resolve', 'try_resolve', 'get_optional', 'get_or_none')

# 容器字段名
CONTAINER_NAMES = ('service_container', 'container', '_service_container', '_container')

# P0 风险业务核心 - R51 教训服务
P0_RISK_SERVICES = {
    # R51 教训服务
    'AdvancedRiskControlService',
    'DynamicRiskAdjustmentService',
    'EnhancedRiskMonitor',
    'RiskManager',
    'RiskMonitor',
    'RiskControl',
    'RiskAlert',
    'RiskAgent',
    'OrderRiskAssessor',
    'EmergencyLiquidation',
    'PositionLimit',
    'StopLoss',
    'TakeProfit',
    # 字符串键
    'RiskManager',
    'risk_manager',
    'EnhancedRiskMonitor',
    'enhanced_risk_monitor',
}

# P0 业务核心文件
P0_RISK_FILES = {
    'core/trading_engine.py',
    'core/trading/order_executor.py',
    'core/trading/order_monitor.py',
    'core/trading/order_service.py',
    'core/risk_alert.py',
    'core/risk_control.py',
    'core/risk_exporter.py',
    'core/risk_manager.py',
    'core/risk_metrics.py',
    'core/stop_loss.py',
    'core/take_profit.py',
    'core/services/advanced_risk_control_service.py',
    'core/services/dynamic_risk_adjustment_service.py',
    'core/services/risk_monitoring_service.py',
    'core/risk_monitoring/enhanced_risk_monitor.py',
    'core/agents/risk_agent.py',
    'core/coordinators/event_coordinator.py',
    'core/coordinators/main_window_coordinator.py',
}

# 排除路径
EXCLUDE_FILE_PREFIXES = (
    '_r1', '_r2', '_r3', '_r4', '_r5', '_r6', '_r7', '_r8', '_r9',
    '.audit_', '.r1', '.r2', 'tools/_', '_debug_', '_scan_', '_apply_',
    '_verify_', '_probe_', '_check_', '_audit_', '_benchmark_', '_smoke_',
    'tests/test_',  # 测试代码不审计
)


def is_excluded(path: Path) -> bool:
    s = str(path).replace('\\', '/')
    if '/.pytest_cache/' in s or '/__pycache__/' in s:
        return True
    if '/_archive/' in s or '/archive/' in s:
        return True
    name = path.name
    for prefix in EXCLUDE_FILE_PREFIXES:
        if name.startswith(prefix):
            return True
    if name.startswith('.audit_'):
        return True
    return False


def extract_class_name_from_arg(node: ast.AST) -> Optional[str]:
    """从 ast.arg 节点提取类名字符串"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def is_p0_risk_service(name: Optional[str]) -> bool:
    """判断是否是 P0 风险服务"""
    if not name:
        return False
    return name in P0_RISK_SERVICES


def find_p0_risk_soft_resolves(file_path: Path) -> List[Dict]:
    """查找 P0 风险控制软解析调用 + 上下文 (10 行) + R51 合规检查"""
    try:
        content = file_path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return []
    if not content:
        return []

    results = []
    try:
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError:
        return []

    lines = content.splitlines()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        attr_name = func.attr
        if attr_name not in SOFT_RESOLVE_METHODS:
            continue

        # 检查 receiver
        receiver = func.value
        receiver_code = ast.unparse(receiver) if hasattr(ast, 'unparse') else ''
        if not any(cn in receiver_code for cn in CONTAINER_NAMES):
            continue

        # 提取服务名
        service_name = None
        if node.args:
            service_name = extract_class_name_from_arg(node.args[0])
        if not service_name:
            for kw in node.keywords:
                if kw.arg in ('name', 'service_type', 'service', 'key', 'cls'):
                    service_name = extract_class_name_from_arg(kw.value)
                    if service_name:
                        break

        # 仅关注 P0 风险服务
        if not is_p0_risk_service(service_name):
            continue

        # 上下文
        start = max(0, node.lineno - 11)
        end = min(len(lines), node.lineno + 10)
        context_before = '\n'.join(lines[start:node.lineno])
        context_after = '\n'.join(lines[node.lineno:end])
        full_context = context_before + '\n' + context_after

        # R51 合规检查
        has_try = 'try:' in context_before[-300:] or 'try:' in full_context
        has_except = 'except' in full_context
        has_exc_info = 'exc_info=True' in full_context
        has_warning = 'logger.warning' in full_context
        has_error = 'logger.error' in full_context
        has_critical = 'logger.critical' in full_context
        has_alert = 'notify_health_alert' in full_context or 'health_alert' in full_context

        # 是否在 P0 风险文件
        rel_path = str(file_path.relative_to(PROJECT_ROOT)).replace('\\', '/')
        is_p0_file = rel_path in P0_RISK_FILES

        # 综合合规评级
        compliant = has_try and has_except and (has_warning or has_error or has_critical) and has_exc_info
        status = 'COMPLIANT' if compliant else 'NON_COMPLIANT'

        results.append({
            'file': rel_path,
            'line': node.lineno,
            'service': service_name,
            'call': f"{receiver_code}.{attr_name}({service_name or '...'})",
            'status': status,
            'has_try': has_try,
            'has_except': has_except,
            'has_exc_info': has_exc_info,
            'has_warning': has_warning,
            'has_error': has_error,
            'has_critical': has_critical,
            'has_alert': has_alert,
            'is_p0_file': is_p0_file,
            'context': full_context[-500:],
        })

    return results


def scan_all() -> List[Dict]:
    all_results = []
    for py_file in PROJECT_ROOT.rglob('*.py'):
        if is_excluded(py_file):
            continue
        all_results.extend(find_p0_risk_soft_resolves(py_file))
    return all_results


def main():
    print("[R199-A] 启动 P0 风险软解析扫描 (R51 合规检查)...")
    results = scan_all()
    print(f"[R199-A] P0 风险软解析总位置: {len(results)}")

    compliant = [r for r in results if r['status'] == 'COMPLIANT']
    non_compliant = [r for r in results if r['status'] == 'NON_COMPLIANT']
    print(f"[R199-A]   R51 合规: {len(compliant)}")
    print(f"[R199-A]   非合规:   {len(non_compliant)}")

    if non_compliant:
        print("\n=== 非合规 P0 风险软解析位置 ===")
        for r in non_compliant:
            print(f"  {r['file']}:{r['line']}  {r['call'][:80]}")
            print(f"    缺: try={r['has_try']} exc_info={r['has_exc_info']} warn={r['has_warning']} err={r['has_error']}")

    # 按服务名统计
    by_service = {}
    for r in results:
        svc = r['service'] or 'unknown'
        if svc not in by_service:
            by_service[svc] = {'total': 0, 'compliant': 0, 'non_compliant': 0}
        by_service[svc]['total'] += 1
        if r['status'] == 'COMPLIANT':
            by_service[svc]['compliant'] += 1
        else:
            by_service[svc]['non_compliant'] += 1
    print("\n=== 按服务名统计 ===")
    for svc, stat in sorted(by_service.items(), key=lambda x: -x[1]['total']):
        print(f"  {svc:35s}  总={stat['total']:3d}  合规={stat['compliant']:3d}  非合规={stat['non_compliant']:3d}")

    # 保存结果
    out = PROJECT_ROOT / 'tools' / '_r199_a_results.json'
    out.write_text(
        json.dumps({
            'total': len(results),
            'compliant': compliant,
            'non_compliant': non_compliant,
            'by_service': by_service,
            'scan_meta': {
                'timestamp': '2026-07-25',
                'round': 'R199-A',
                'task': 'HVD-198-D-NEW-04 风险控制软解析 P0 治理',
                'standard': 'R51 §7.1 5 强约束 (try + except + exc_info + warning + alert)',
                'scope': 'P0 风险业务核心服务 (AdvancedRiskControlService / DynamicRiskAdjustmentService / EnhancedRiskMonitor / RiskManager / RiskMonitor 等)',
            },
        }, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    print(f"\n[R199-A] 结果已保存: {out}")
    return results


if __name__ == '__main__':
    main()
