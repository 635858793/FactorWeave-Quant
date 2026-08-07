"""
tools/indicator_metadata_audit.py
R237-A-001 HVD-32 9 指标元数据一致性 CI 检查工具

> **生成日期**: 2026-08-01
> **项目类型**: P1 实施 (R237-A-001 HVD-32)
> **强约束应用**: R6 §6.1 (8 铁律) + R104 §12 (5 铁律) + R231 §13 (4 铁律)

**功能**:
- AST 扫描 `core/unified_indicator_service.py` 的 `supported_params` 块
- 与 9 指标白名单 (MA, MACD, RSI, KDJ, AD, AROON, DEMA, TEMA, NATR) 比对
- 输出报告: 缺失/正确/覆盖率
- `--fail-on-missing` 选项: 缺失时 exit 1
- 跨平台 (Windows/Linux/macOS)

**用法**:
```bash
python tools/indicator_metadata_audit.py --indicators "MA,MACD,RSI,KDJ,AD,AROON,DEMA,TEMA,NATR"
python tools/indicator_metadata_audit.py --indicators "MA,AROON" --fail-on-missing  # 测试 fail
```
"""
import argparse
import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# 项目根目录
ROOT = Path(__file__).parent.parent
INDICATOR_PATH = ROOT / "core" / "unified_indicator_service.py"

# 9 指标默认白名单
DEFAULT_INDICATORS = "MA,MACD,RSI,KDJ,AD,AROON,DEMA,TEMA,NATR"

# 默认 timeperiod 标准值
DEFAULT_TIMEPERIOD = {
    'MA': 30,
    'MACD': None,  # MACD 用 fastperiod/slowperiod/signalperiod
    'RSI': 14,
    'KDJ': None,  # KDJ 用 n/m1/m2 (E 套自实现)
    'AD': None,   # AD 不需要参数
    'AROON': 14,
    'DEMA': 30,
    'TEMA': 30,
    'NATR': 14,
}


def extract_supported_params(file_path: Path) -> Dict[str, List[str]]:
    """
    从 unified_indicator_service.py AST 提取 supported_params 字典

    Args:
        file_path: unified_indicator_service.py 路径

    Returns:
        {指标名: [参数列表]} 字典
    """
    if not file_path.exists():
        return {}

    tree = ast.parse(file_path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for stmt in ast.walk(node):
            if not isinstance(stmt, ast.Assign):
                continue
            for target in stmt.targets:
                target_id = getattr(target, 'id', None)
                if target_id != 'supported_params':
                    continue
                if not isinstance(stmt.value, ast.Dict):
                    continue
                result = {}
                for key_node, val_node in zip(stmt.value.keys, stmt.value.values):
                    if isinstance(key_node, ast.Constant) and isinstance(val_node, ast.List):
                        indicator_name = key_node.value
                        params = [el.value for el in val_node.elts if isinstance(el, ast.Constant)]
                        result[indicator_name] = params
                return result
    return {}


def audit_indicators(
    expected: List[str],
    actual: Dict[str, List[str]],
) -> Tuple[List[str], List[str], float]:
    """
    审计 9 指标元数据

    Args:
        expected: 期望指标列表
        actual: 实际 supported_params 字典

    Returns:
        (missing, passed, coverage_rate) 三元组
    """
    missing = []
    passed = []
    for ind in expected:
        if ind in actual:
            passed.append(ind)
        else:
            missing.append(ind)
    coverage_rate = len(passed) / len(expected) if expected else 1.0
    return missing, passed, coverage_rate


def main():
    parser = argparse.ArgumentParser(
        description="HVD-32 9 指标元数据一致性 CI 检查工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--indicators",
        default=DEFAULT_INDICATORS,
        help=f"指标白名单 (逗号分隔), 默认: {DEFAULT_INDICATORS}",
    )
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="缺失指标时 exit 1 (CI 拦截)",
    )
    parser.add_argument(
        "--indicator-path",
        default=str(INDICATOR_PATH),
        help="unified_indicator_service.py 路径",
    )
    args = parser.parse_args()

    expected = [s.strip() for s in args.indicators.split(",") if s.strip()]
    indicator_path = Path(args.indicator_path)

    print(f"=== HVD-32 9 指标元数据一致性检查 ===")
    print(f"指标白名单 ({len(expected)}): {', '.join(expected)}")
    print(f"扫描文件: {indicator_path}")
    print()

    actual = extract_supported_params(indicator_path)
    if not actual:
        print(f"[ERROR] 未能在 {indicator_path} 中找到 supported_params 字典")
        return 1

    missing, passed, coverage_rate = audit_indicators(expected, actual)

    print(f"--- 审计结果 ---")
    print(f"通过: {len(passed)}/{len(expected)} ({coverage_rate:.1%})")
    print()
    print(f"通过指标 ({len(passed)}):")
    for ind in passed:
        params = actual.get(ind, [])
        default_tp = DEFAULT_TIMEPERIOD.get(ind)
        default_info = f" (默认 timeperiod={default_tp})" if default_tp else ""
        print(f"  [PASS] {ind}: {params}{default_info}")

    if missing:
        print()
        print(f"缺失指标 ({len(missing)}):")
        for ind in missing:
            default_tp = DEFAULT_TIMEPERIOD.get(ind, 'N/A')
            print(f"  [MISS] {ind}: 应在 supported_params 中, 默认 timeperiod={default_tp}")
        print()
        print(f"[FAIL] 覆盖率 {coverage_rate:.1%} < 100%")
        if args.fail_on_missing:
            return 1
        return 0
    else:
        print()
        print(f"[OK] 9 指标元数据 100% 完整")
        return 0


if __name__ == "__main__":
    sys.exit(main())
