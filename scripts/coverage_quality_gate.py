#!/usr/bin/env python
"""
测试覆盖率质量门禁脚本
检查各模块覆盖率是否达到最低要求
"""

import subprocess
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple

MIN_COVERAGE_THRESHOLD = 80.0
MODULE_THRESHOLDS = {
    'core/trading': 85.0,
    'core/services': 80.0,
    'core/data': 85.0,
    'core/metrics': 75.0,
    'core/importdata': 80.0,
    'core/utils': 70.0,
    'backtest': 75.0,
    'web': 80.0,
}

COVERAGE_FILE = 'coverage.json'
REPORT_FILE = 'coverage_quality_gate_report.json'


def run_coverage_report() -> bool:
    """运行覆盖率报告生成"""
    print("=" * 60)
    print("生成测试覆盖率报告...")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            [
                'pytest', 'tests/',
                '--cov=core',
                '--cov-report=term-missing',
                '--cov-report=json',
                f'--cov-report=html:htmlcov',
                '--cov-branch',
                '-v'
            ],
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        if result.returncode != 0:
            print(f"测试执行失败: {result.stderr}")
            return False
        
        return True
    except Exception as e:
        print(f"运行覆盖率报告失败: {e}")
        return False


def parse_coverage_json(coverage_file: str) -> Dict:
    """解析覆盖率JSON报告"""
    try:
        with open(coverage_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"覆盖率报告文件未找到: {coverage_file}")
        return {}
    except json.JSONDecodeError as e:
        print(f"解析覆盖率报告失败: {e}")
        return {}


def get_module_coverage(coverage_data: Dict, module_path: str) -> Tuple[float, int, int]:
    """获取指定模块的覆盖率"""
    try:
        totals = coverage_data.get('totals', {})
        node_totals = totals.get('node_totals', {})
        
        covered = node_totals.get('covered_lines', 0)
        n_lines = node_totals.get('n_lines', 0)
        
        if n_lines > 0:
            coverage = (covered / n_lines) * 100
            return coverage, covered, n_lines
        
        return 0.0, 0, 0
    except Exception as e:
        print(f"获取模块覆盖率失败: {e}")
        return 0.0, 0, 0


def check_quality_gate(coverage_data: Dict) -> Tuple[bool, List[Dict]]:
    """检查质量门禁"""
    results = []
    passed = True
    
    totals = coverage_data.get('totals', {})
    n_files = totals.get('n_files', 0)
    covered_lines = totals.get('covered_lines', 0)
    n_lines = totals.get('n_lines', 0)
    
    overall_coverage = (covered_lines / n_lines * 100) if n_lines > 0 else 0.0
    
    result = {
        'name': '整体覆盖率',
        'coverage': overall_coverage,
        'threshold': MIN_COVERAGE_THRESHOLD,
        'status': 'PASS' if overall_coverage >= MIN_COVERAGE_THRESHOLD else 'FAIL',
        'details': f'覆盖行数: {covered_lines}/{n_lines} ({n_files} 个文件)'
    }
    results.append(result)
    
    if overall_coverage < MIN_COVERAGE_THRESHOLD:
        passed = False
    
    print("\n" + "=" * 60)
    print("模块级覆盖率检查")
    print("=" * 60)
    print(f"{'模块':<25} {'覆盖率':>10} {'阈值':>10} {'状态':>8}")
    print("-" * 60)
    
    for module, threshold in MODULE_THRESHOLDS.items():
        module_coverage, covered, n_lines = get_module_coverage(coverage_data, module)
        
        status = 'PASS' if module_coverage >= threshold else 'FAIL'
        if status == 'FAIL':
            passed = False
        
        print(f"{module:<25} {module_coverage:>9.1f}% {threshold:>9.1f}% {status:>8}")
        
        results.append({
            'name': module,
            'coverage': module_coverage,
            'threshold': threshold,
            'status': status,
            'details': f'覆盖行数: {covered}/{n_lines}'
        })
    
    return passed, results


def generate_summary_report(all_results: List[Dict], output_file: str):
    """生成汇总报告"""
    report = {
        'timestamp': subprocess.run(
            ['date', '+%Y-%m-%d %H:%M:%S'],
            capture_output=True,
            text=True
        ).stdout.strip(),
        'python_version': subprocess.run(
            ['python', '--version'],
            capture_output=True,
            text=True
        ).stdout.strip(),
        'results': all_results,
        'summary': {
            'total_checks': len(all_results),
            'passed': sum(1 for r in all_results if r['status'] == 'PASS'),
            'failed': sum(1 for r in all_results if r['status'] == 'FAIL'),
            'overall_status': 'PASS' if all(r['status'] == 'PASS' for r in all_results) else 'FAIL'
        }
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n质量门禁报告已生成: {output_file}")


def main():
    """主函数"""
    print("=" * 60)
    print("Hikyuu UI 测试覆盖率质量门禁")
    print("=" * 60)
    print(f"最低覆盖率要求: {MIN_COVERAGE_THRESHOLD}%")
    print()
    
    if not run_coverage_report():
        sys.exit(1)
    
    coverage_data = parse_coverage_json(COVERAGE_FILE)
    if not coverage_data:
        print("无法解析覆盖率数据，质量门禁检查失败")
        sys.exit(1)
    
    passed, results = check_quality_gate(coverage_data)
    generate_summary_report(results, REPORT_FILE)
    
    print("\n" + "=" * 60)
    print("质量门禁检查结果")
    print("=" * 60)
    
    if passed:
        print("✓ 所有覆盖率检查通过!")
        print(f"✓ 整体覆盖率达标: {results[0]['coverage']:.1f}%")
    else:
        print("✗ 部分覆盖率检查未通过")
        failed_modules = [r['name'] for r in results if r['status'] == 'FAIL' and r['name'] != '整体覆盖率']
        if failed_modules:
            print(f"  未达标的模块: {', '.join(failed_modules)}")
    
    print("=" * 60)
    
    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
