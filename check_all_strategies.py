#!/usr/bin/env python3
"""
策略信号生成全面检查脚本

检查所有策略是否存在"只检查最后 N 个点"的问题
验证策略的信号生成逻辑是否正确、完整
"""

import os
import re
import sys
import ast
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, level=logging.INFO, format="{time:HH:mm:ss.SSS} | {level} | {message}")


class StrategyChecker:
    """策略检查器"""
    
    def __init__(self):
        self.strategies_found = []
        self.issues_found = []
        self.check_results = []
    
    def find_strategy_files(self, root_dir: str) -> List[str]:
        """查找所有策略文件"""
        strategy_files = []
        
        # 策略文件模式
        patterns = [
            '*strategy*.py',
            '*_strategy.py',
            'strategy_*.py',
        ]
        
        root_path = Path(root_dir)
        
        # 搜索特定目录
        target_dirs = [
            root_path / 'plugins' / 'strategies',
            root_path / 'core' / 'strategy',
            root_path / 'examples' / 'strategies',
            root_path / 'strategies',
        ]
        
        for target_dir in target_dirs:
            if target_dir.exists():
                for py_file in target_dir.glob('*.py'):
                    if 'strategy' in py_file.name.lower() and not py_file.name.startswith('test_'):
                        strategy_files.append(str(py_file))
        
        self.strategies_found = strategy_files
        logger.info(f"找到 {len(strategy_files)} 个策略文件")
        
        return strategy_files
    
    def check_start_idx_pattern(self, file_path: str) -> Optional[Dict]:
        """检查文件中的 start_idx 计算模式"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            issues = []
            
            # 检查是否有 "len(data) - N" 的模式
            pattern = r'start_idx\s*=\s*.*max\s*\(\s*\d+\s*,\s*len\s*\(\s*data\s*\)\s*-\s*(\d+)\s*\)'
            matches = re.finditer(pattern, content)
            
            for match in matches:
                lookback = int(match.group(1))
                line_num = content[:match.start()].count('\n') + 1
                
                issues.append({
                    'type': 'FIXED_LOOKBACK',
                    'severity': 'HIGH',
                    'description': f'使用固定回溯窗口：只检查最后 {lookback} 个点',
                    'line': line_num,
                    'code': match.group(0),
                    'suggestion': f'建议：根据数据总量动态调整，或使用第一个有效索引'
                })
            
            # 检查是否有 range(start_idx, len(data)) 但 start_idx 计算有问题
            if 'range(start_idx, len(data))' in content or 'range(start_idx, total_bars)' in content:
                # 检查 start_idx 是否从固定偏移计算
                fixed_offset_pattern = r'start_idx\s*=\s*max\s*\(\s*(\d+)\s*,\s*len\s*\(\s*data\s*\)\s*-\s*(\d+)\s*\)'
                fixed_matches = re.finditer(fixed_offset_pattern, content)
                
                for match in fixed_matches:
                    min_idx = int(match.group(1))
                    lookback = int(match.group(2))
                    line_num = content[:match.start()].count('\n') + 1
                    
                    issues.append({
                        'type': 'POTENTIAL_ISSUE',
                        'severity': 'MEDIUM',
                        'description': f'起始索引计算：max({min_idx}, len(data) - {lookback})',
                        'line': line_num,
                        'code': match.group(0),
                        'suggestion': '验证是否应该检查所有有效数据点'
                    })
            
            return {
                'file': file_path,
                'issues': issues,
                'has_issues': len(issues) > 0
            }
            
        except Exception as e:
            logger.error(f"检查文件 {file_path} 失败：{e}")
            return None
    
    def check_signal_generation_logic(self, file_path: str) -> Optional[Dict]:
        """检查信号生成逻辑的完整性"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            issues = []
            
            # 检查是否从索引 0 或固定索引开始
            range_patterns = [
                r'for\s+i\s+in\s+range\s*\(\s*(\d+)\s*,\s*len\s*\(',
                r'for\s+i\s+in\s+range\s*\(\s*start_idx\s*,\s*len\s*\(',
            ]
            
            for pattern in range_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    start_value = match.group(1) if match.lastindex >= 1 else None
                    line_num = content[:match.start()].count('\n') + 1
                    
                    if start_value and start_value.isdigit() and int(start_value) > 50:
                        issues.append({
                            'type': 'LATE_START',
                            'severity': 'MEDIUM',
                            'description': f'从索引 {start_value} 开始检查，可能错过早期信号',
                            'line': line_num,
                            'code': match.group(0),
                            'suggestion': '考虑从指标有效的第一个点开始检查'
                        })
            
            # 检查是否有数据量限制
            min_data_pattern = r'if\s+len\s*\(\s*data\s*\)\s*<\s*(\d+)\s*:'
            matches = re.finditer(min_data_pattern, content)
            
            for match in matches:
                min_required = int(match.group(1))
                line_num = content[:match.start()].count('\n') + 1
                
                if min_required > 100:
                    issues.append({
                        'type': 'HIGH_MIN_DATA',
                        'severity': 'LOW',
                        'description': f'要求至少 {min_required} 个数据点',
                        'line': line_num,
                        'code': match.group(0),
                        'suggestion': '验证是否需要如此高的最小数据量'
                    })
            
            return {
                'file': file_path,
                'issues': issues,
                'has_issues': len(issues) > 0
            }
            
        except Exception as e:
            logger.error(f"检查信号生成逻辑失败 {file_path}: {e}")
            return None
    
    def generate_test_data(self, total_bars: int = 243, seed: int = 42) -> pd.DataFrame:
        """生成标准测试数据"""
        np.random.seed(seed)
        dates = pd.date_range(start='2023-01-01', periods=total_bars, freq='D')
        close = 100 + np.cumsum(np.random.randn(total_bars))
        
        data = pd.DataFrame({
            'open': close * (1 + np.random.randn(total_bars) * 0.01),
            'high': close * (1 + np.abs(np.random.randn(total_bars) * 0.02)),
            'low': close * (1 - np.abs(np.random.randn(total_bars) * 0.02)),
            'close': close,
            'volume': np.random.randint(1000, 10000, total_bars)
        }, index=dates)
        
        return data
    
    def test_strategy_with_data(self, file_path: str) -> Dict:
        """使用测试数据验证策略"""
        try:
            # 生成测试数据
            test_data = self.generate_test_data(243)
            
            result = {
                'file': file_path,
                'can_test': False,
                'signals_generated': 0,
                'early_signals': 0,
                'issues': []
            }
            
            # 尝试导入和测试策略
            # 注意：这里只是静态检查，不实际执行
            
            # 检查文件中是否有 generate_signals 方法
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'def generate_signals' in content:
                result['can_test'] = True
                
                # 检查信号生成是否使用了完整的检查范围
                if 'range(start_idx, len(data))' in content:
                    # 检查 start_idx 的计算
                    if 'len(data) - 100' in content or 'len(data) - 200' in content:
                        result['issues'].append({
                            'type': 'LIMITED_RANGE',
                            'description': '信号检查范围受限'
                        })
            
            return result
            
        except Exception as e:
            logger.error(f"测试策略 {file_path} 失败：{e}")
            return {
                'file': file_path,
                'can_test': False,
                'error': str(e)
            }
    
    def run_comprehensive_check(self, root_dir: str = None):
        """运行全面检查"""
        if root_dir is None:
            root_dir = Path(__file__).parent
        
        logger.info("="*80)
        logger.info("开始策略全面检查")
        logger.info("="*80)
        
        # 1. 查找所有策略文件
        strategy_files = self.find_strategy_files(str(root_dir))
        
        # 2. 检查每个文件的 start_idx 模式
        logger.info("\n检查 start_idx 计算模式...")
        for file_path in strategy_files:
            result = self.check_start_idx_pattern(file_path)
            if result and result['has_issues']:
                self.issues_found.extend([
                    {'file': file_path, **issue}
                    for issue in result['issues']
                ])
            self.check_results.append(result)
        
        # 3. 检查信号生成逻辑
        logger.info("\n检查信号生成逻辑...")
        for file_path in strategy_files:
            result = self.check_signal_generation_logic(file_path)
            if result and result['has_issues']:
                self.issues_found.extend([
                    {'file': file_path, **issue}
                    for issue in result['issues']
                ])
        
        # 4. 输出结果
        self.print_results()
        
        return {
            'total_files': len(strategy_files),
            'files_with_issues': len(set([i['file'] for i in self.issues_found])),
            'total_issues': len(self.issues_found),
            'issues': self.issues_found
        }
    
    def print_results(self):
        """打印检查结果"""
        print("\n" + "="*80)
        print("策略检查结果汇总")
        print("="*80)
        
        if not self.issues_found:
            print("\n✅ 未发现明显问题！")
        else:
            print(f"\n⚠️ 发现 {len(self.issues_found)} 个潜在问题：\n")
            
            # 按严重程度分组
            high_severity = [i for i in self.issues_found if i.get('severity') == 'HIGH']
            medium_severity = [i for i in self.issues_found if i.get('severity') == 'MEDIUM']
            low_severity = [i for i in self.issues_found if i.get('severity') == 'LOW']
            
            if high_severity:
                print(f"\n🔴 高严重程度 ({len(high_severity)}个):")
                for issue in high_severity:
                    print(f"  - {issue['file']}")
                    print(f"    问题：{issue['description']}")
                    print(f"    建议：{issue['suggestion']}")
            
            if medium_severity:
                print(f"\n🟡 中等严重程度 ({len(medium_severity)}个):")
                for issue in medium_severity:
                    print(f"  - {issue['file']}")
                    print(f"    问题：{issue['description']}")
                    print(f"    建议：{issue['suggestion']}")
            
            if low_severity:
                print(f"\n🟢 低严重程度 ({len(low_severity)}个):")
                for issue in low_severity:
                    print(f"  - {issue['file']}")
                    print(f"    问题：{issue['description']}")
                    print(f"    建议：{issue['suggestion']}")
        
        print("\n" + "="*80)
        print(f"检查完成：{len(self.check_results)} 个文件，{len(self.issues_found)} 个问题")
        print("="*80)


def main():
    """主函数"""
    print("\n" + "="*80)
    print("策略信号生成全面检查脚本")
    print("检查所有策略是否存在'只检查最后 N 个点'的问题")
    print("="*80)
    
    checker = StrategyChecker()
    results = checker.run_comprehensive_check()
    
    # 保存检查结果
    output_file = Path(__file__).parent / 'strategy_check_results.json'
    import json
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n检查结果已保存到：{output_file}")
    
    # 返回退出码
    if results['total_issues'] > 0:
        print(f"\n⚠️ 发现 {results['total_issues']} 个问题，请检查上述报告")
        sys.exit(1)
    else:
        print("\n✅ 所有策略检查通过！")
        sys.exit(0)


if __name__ == "__main__":
    main()
