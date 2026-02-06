"""
Python语法检查脚本

检查多资产类型AI选股系统的所有新创建文件的语法正确性。

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-19
"""

import sys
import py_compile
from pathlib import Path
from typing import List, Tuple

def check_file_syntax(file_path: Path) -> Tuple[bool, str]:
    """检查单个文件的语法
    
    Args:
        file_path: 文件路径
        
    Returns:
        Tuple[bool, str]: (是否成功, 错误信息)
    """
    try:
        py_compile.compile(str(file_path), doraise=True)
        return True, ""
    except py_compile.PyCompileError as e:
        return False, str(e)
    except Exception as e:
        return False, f"未知错误: {e}"

def check_directory_syntax(directory: Path, pattern: str = "*.py") -> List[Tuple[Path, bool, str]]:
    """检查目录下所有匹配的文件
    
    Args:
        directory: 目录路径
        pattern: 文件匹配模式
        
    Returns:
        List[Tuple[Path, bool, str]]: 检查结果列表
    """
    results = []
    
    for file_path in directory.rglob(pattern):
        if file_path.is_file():
            success, error = check_file_syntax(file_path)
            results.append((file_path, success, error))
    
    return results

def main():
    """主函数"""
    print("=" * 80)
    print("Python语法检查")
    print("=" * 80)
    
    # 定义需要检查的目录
    project_root = Path(__file__).parent.parent
    
    directories_to_check = [
        project_root / "core" / "fundamental_data",
        project_root / "core" / "selection_strategies",
        project_root / "tests",
        project_root / "scripts"
    ]
    
    all_results = []
    
    for directory in directories_to_check:
        if not directory.exists():
            print(f"\n⚠️  目录不存在: {directory}")
            continue
        
        print(f"\n检查目录: {directory}")
        print("-" * 80)
        
        results = check_directory_syntax(directory)
        all_results.extend(results)
        
        # 统计结果
        success_count = sum(1 for _, success, _ in results if success)
        fail_count = len(results) - success_count
        
        print(f"✅ 成功: {success_count} 个文件")
        print(f"❌ 失败: {fail_count} 个文件")
        
        # 显示失败的文件
        for file_path, success, error in results:
            if not success:
                print(f"\n❌ {file_path}")
                print(f"   错误: {error}")
    
    # 汇总报告
    print("\n" + "=" * 80)
    print("汇总报告")
    print("=" * 80)
    
    total_files = len(all_results)
    total_success = sum(1 for _, success, _ in all_results if success)
    total_fail = total_files - total_success
    
    print(f"总文件数: {total_files}")
    print(f"✅ 成功: {total_success}")
    print(f"❌ 失败: {total_fail}")
    
    if total_fail == 0:
        print("\n🎉 所有文件语法检查通过！")
        return 0
    else:
        print(f"\n⚠️  有 {total_fail} 个文件存在语法错误")
        return 1

if __name__ == "__main__":
    sys.exit(main())
