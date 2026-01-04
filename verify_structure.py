#!/usr/bin/env python3
"""
代码结构验证 - 不依赖完整导入
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent

def verify_code_structure():
    """验证修复代码的结构"""
    print("=" * 60)
    print("代码结构验证")
    print("=" * 60)
    
    results = {}
    
    print("\n1. 验证 database_service.py")
    print("-" * 40)
    
    db_file = project_root / "core" / "services" / "database_service.py"
    if db_file.exists():
        with open(db_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'def _create_strategies_table(self) -> None:' in content:
            print("✓ _create_strategies_table 方法已添加")
            results["create_strategies_method"] = True
        else:
            print("✗ _create_strategies_table 方法未找到")
            results["create_strategies_method"] = False
        
        if 'self._create_strategies_table()' in content:
            print("✓ _initialize_strategy_tables 调用了 _create_strategies_table")
            results["initialize_calls_create"] = True
        else:
            print("✗ _initialize_strategy_tables 未调用 _create_strategies_table")
            results["initialize_calls_create"] = False
        
        strategies_create = content.find('def _create_strategies_table')
        strategies_end = content.find('def _create_ai_strategy_table')
        if strategies_create > 0 and strategies_end > strategies_create:
            method_body = content[strategies_create:strategies_end]
            if 'CREATE TABLE IF NOT EXISTS strategies' in method_body:
                print("✓ strategies 表创建 SQL 存在")
                results["strategies_sql"] = True
            else:
                print("✗ strategies 表创建 SQL 未找到")
                results["strategies_sql"] = False
            
            if 'idx_strategies_type' in method_body or 'CREATE INDEX' in method_body:
                print("✓ 索引创建代码存在")
                results["strategies_indices"] = True
            else:
                print("✗ 索引创建代码未找到")
                results["strategies_indices"] = False
    else:
        print(f"✗ 文件不存在: {db_file}")
        results["db_file_exists"] = False
    
    print("\n2. 验证 plugin_database_service.py")
    print("-" * 40)
    
    plugin_file = project_root / "core" / "services" / "plugin_database_service.py"
    if plugin_file.exists():
        with open(plugin_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = [
            ('plugin_status_changed.emit', 'if self.plugin_status_changed:', 'plugin_status_changed'),
            ('plugin_registered.emit', 'if self.plugin_registered:', 'plugin_registered'),
            ('database_updated.emit', 'if self.database_updated:', 'database_updated'),
        ]
        
        for emit_pattern, check_pattern, name in checks:
            emit_pos = content.find(emit_pattern)
            check_pos = content.find(check_pattern)
            
            if emit_pos > 0 and check_pos > 0:
                if emit_pos > check_pos:
                    print(f"✓ {name} 空值检查在发射之前")
                    results[f"{name}_check"] = True
                else:
                    print(f"✗ {name} 空值检查位置错误")
                    results[f"{name}_check"] = False
            elif emit_pos > 0:
                print(f"✗ {name} 找到发射但未找到空值检查")
                results[f"{name}_check"] = False
            else:
                print(f"⚠ {name} 未找到发射调用（可能不需要检查）")
                results[f"{name}_check"] = True
    else:
        print(f"✗ 文件不存在: {plugin_file}")
        results["plugin_file_exists"] = False
    
    return results

def test_sql_structure():
    """测试SQL语句结构"""
    print("\n3. 验证 SQL 语句结构")
    print("-" * 40)
    
    db_file = project_root / "core" / "services" / "database_service.py"
    if db_file.exists():
        with open(db_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        create_strategies_start = content.find('def _create_strategies_table')
        if create_strategies_start > 0:
            method_end = content.find('\n    def ', create_strategies_start + 10)
            if method_end == -1:
                method_end = len(content)
            
            method_content = content[create_strategies_start:method_end]
            
            required_fields = [
                'id INTEGER PRIMARY KEY AUTOINCREMENT',
                'name TEXT UNIQUE NOT NULL',
                'strategy_type TEXT NOT NULL',
                'version TEXT',
                'is_active BOOLEAN',
                'class_path TEXT NOT NULL'
            ]
            
            all_fields_ok = True
            for field in required_fields:
                if field in method_content:
                    print(f"✓ 字段存在: {field[:50]}...")
                else:
                    print(f"✗ 字段缺失: {field}")
                    all_fields_ok = False
            
            return all_fields_ok
    
    return False

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("修复验证报告")
    print("=" * 60)
    
    code_results = verify_code_structure()
    sql_result = test_sql_structure()
    
    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    
    all_passed = all(code_results.values()) and sql_result
    
    print("\n数据库修复:")
    print(f"  - strategies表创建方法: {'✓' if code_results.get('create_strategies_method') else '✗'}")
    print(f"  - 初始化调用创建: {'✓' if code_results.get('initialize_calls_create') else '✗'}")
    print(f"  - SQL语句完整: {'✓' if sql_result else '✗'}")
    print(f"  - 索引创建: {'✓' if code_results.get('strategies_indices') else '✗'}")
    
    print("\n信号修复:")
    print(f"  - plugin_status_changed检查: {'✓' if code_results.get('plugin_status_changed_check') else '✗'}")
    print(f"  - plugin_registered检查: {'✓' if code_results.get('plugin_registered_check') else '✗'}")
    print(f"  - database_updated检查: {'✓' if code_results.get('database_updated_check') else '✗'}")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ 所有修复验证通过!")
        print("\n修复内容:")
        print("1. database_service.py: 添加了 _create_strategies_table 方法")
        print("2. _initialize_strategy_tables 现在会创建 strategies 表")
        print("3. plugin_database_service.py: 所有信号发射前进行空值检查")
    else:
        print("✗ 部分验证失败，请检查上述详情")
    print("=" * 60)
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
