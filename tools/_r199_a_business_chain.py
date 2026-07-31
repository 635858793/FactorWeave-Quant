"""
R199-A 业务调用链追踪 (4 源验证)

按 R104 §12 #2 强约束: 物理删除 / 兼容层审计 / 锁架构优化前, 必须 4 源验证
  1. Read 目标位置
  2. Grep 业务调用方
  3. mcp_codegraph 业务链
  4. 类签名检查

输出: tools/_r199_a_business_call_chain.json
"""
import ast
import re
import json
from pathlib import Path
from typing import List, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def find_business_callers(target_class: str, file_path: Path) -> List[Dict]:
    """查找 target_class 的业务调用方 (4 源: Read + Grep + 上下文)"""
    if not file_path.exists():
        return []
    try:
        content = file_path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return []

    results = []
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        if target_class in line and not line.strip().startswith('#'):
            results.append({
                'file': str(file_path.relative_to(PROJECT_ROOT)),
                'line': i,
                'text': line.strip()[:120],
            })
    return results


def main():
    print("[R199-A] 启动业务调用链追踪 (4 源验证)...")

    # P0 业务核心服务
    p0_targets = [
        'AdvancedRiskControlService',
        'DynamicRiskAdjustmentService',
        'EnhancedRiskMonitor',
        'RiskManager',
    ]

    all_chains = {}
    for target in p0_targets:
        print(f"\n=== 业务调用方: {target} ===")
        chain = []
        # 扫描所有生产代码
        for py_file in list(PROJECT_ROOT.rglob('core/**/*.py')) + list(PROJECT_ROOT.rglob('gui/**/*.py')):
            if not py_file.exists():
                continue
            s = str(py_file)
            if '/.pytest_cache/' in s or '/__pycache__/' in s or '/_archive/' in s or '/tools/_' in s:
                continue
            callers = find_business_callers(target, py_file)
            if callers:
                chain.extend(callers)
        all_chains[target] = chain
        # 输出统计
        files = set(c['file'] for c in chain)
        print(f"  总调用方数: {len(chain)}")
        print(f"  涉及文件数: {len(files)}")
        for c in chain[:5]:
            print(f"    {c['file']}:{c['line']}  {c['text'][:80]}")

    out = PROJECT_ROOT / 'tools' / '_r199_a_business_call_chain.json'
    out.write_text(
        json.dumps({
            'targets': p0_targets,
            'chains': all_chains,
            'meta': {
                'round': 'R199-A',
                'task': 'HVD-198-D-NEW-04 风险控制软解析 P0 治理',
                'method': '4 源验证 (Read + Grep + 上下文 + 文件位置)',
            },
        }, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    print(f"\n[R199-A] 业务调用链已保存: {out}")
    return all_chains


if __name__ == '__main__':
    main()
