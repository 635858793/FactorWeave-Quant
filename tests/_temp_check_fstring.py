import ast
import sys
sys.path.insert(0, 'tools')
from keyword_test_template import extract_string_value
code = '''
logger.warning(f"[R51-FIX] asset type error (symbol={symbol}): {asset_exc}")
'''
tree = ast.parse(code)
for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        first_arg = node.args[0]
        if isinstance(first_arg, ast.JoinedStr):
            print('JoinedStr values:')
            for v in first_arg.values:
                print(f'  type={type(v).__name__}, value={getattr(v, "value", None)!r}')
        result = extract_string_value(first_arg)
        print(f'extract_string_value result: {result!r}')
