import os
import re

def check_specific_files():
    """检查特定修复的文件"""
    files_to_check = [
        'core/akshare_data_source.py',
        'core/business/portfolio_manager.py',
        'core/risk_exporter.py',
        'core/trading_system.py',
        'examples/data_access_best_practices.py',
        'examples/sector_fund_flow_example.py',
        'visualization/risk_visualizer.py',
        'visualization/visualization.py'
    ]
    
    issues = []
    
    for filepath in files_to_check:
        if not os.path.exists(filepath):
            continue
            
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        # 检查重复的pass语句
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # 检查连续的pass
            if stripped == 'pass' and i < len(lines):
                next_line = lines[i].strip() if i < len(lines) else ''
                if next_line == 'pass':
                    issues.append({
                        'file': filepath,
                        'line': i,
                        'type': '连续的pass语句',
                        'code': line
                    })
        
        # 检查重复的导入
        imports = []
        import_pattern = re.compile(r'^from\s+(\S+)\s+import')
        for i, line in enumerate(lines, 1):
            match = import_pattern.match(line)
            if match:
                module = match.group(1)
                # 检查是否是真正的重复（忽略不同的导入项）
                if module in imports and not line.strip().endswith('('):
                    issues.append({
                        'file': filepath,
                        'line': i,
                        'type': '重复的导入',
                        'code': line
                    })
                imports.append(module)
    
    return issues

if __name__ == '__main__':
    issues = check_specific_files()
    
    if issues:
        print("=== 发现的代码质量问题 ===\n")
        for issue in issues:
            print(f"文件: {issue['file']}")
            print(f"行号: {issue['line']}")
            print(f"类型: {issue['type']}")
            print(f"代码: {issue['code']}")
            print()
        print(f"总计: {len(issues)} 个问题")
    else:
        print("✓ 没有发现代码质量问题")
