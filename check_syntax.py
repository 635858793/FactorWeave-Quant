import ast
import os
import sys

def check_syntax_errors(directory):
    errors = []
    checked_count = 0
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        code = f.read()
                    ast.parse(code)
                    checked_count += 1
                except SyntaxError as e:
                    errors.append({
                        'file': filepath,
                        'line': e.lineno,
                        'message': str(e),
                        'text': e.text
                    })
                except Exception as e:
                    errors.append({
                        'file': filepath,
                        'line': 'N/A',
                        'message': f"读取错误: {str(e)}",
                        'text': 'N/A'
                    })
    
    return errors, checked_count

if __name__ == '__main__':
    directory = '.' if len(sys.argv) < 2 else sys.argv[1]
    errors, checked_count = check_syntax_errors(directory)
    
    print(f"检查了 {checked_count} 个Python文件")
    print(f"发现 {len(errors)} 个语法错误\n")
    
    if errors:
        for i, error in enumerate(errors, 1):
            print(f"错误 #{i}:")
            print(f"  文件: {error['file']}")
            print(f"  行号: {error['line']}")
            print(f"  消息: {error['message']}")
            if error['text']:
                print(f"  代码: {error['text'].strip()}")
            print()
        sys.exit(1)
    else:
        print("✓ 所有文件语法正确")
        sys.exit(0)
