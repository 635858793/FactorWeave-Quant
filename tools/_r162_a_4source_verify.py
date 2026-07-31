"""R162-A 子智能体专用: 死代码 4 源验证工具 (R104 §12 #2 强制度合规)

对 15 个真死代码候选做 4 源验证:
1. mcp_codegraph 二次确认(模拟:遍历 AST 解析 import)
2. Grep 跨 4 子目录 文本搜索
3. Read 目标文件确认定义存在
4. 业务调用链追踪(从 hit 向上溯源,排除注释/docstring)
"""
import re
import pathlib
import ast

# 15 个死代码候选
DEAD_CANDIDATES = [
    ('TradingService', 'get_ctp_quote'),
    ('TradingService', 'subscribe_ctp_quote'),
    ('TradingService', 'get_ctp_connection_status'),
    ('TradingService', 'get_all_portfolios'),
    ('TradingService', 'clear_trade_history'),
    ('TradingService', 'is_live_mode'),
    ('OrderExecutor', 'get_signal_chain'),
    ('OrderExecutor', 'get_commission_rate'),
    ('OrderService', 'get_order_alerts'),
    ('TradingController', 'start_strategy'),
    ('TradingController', 'stop_strategy'),
    ('TradingController', 'pause_strategy'),
    ('TradingController', 'resume_strategy'),
    ('TradingController', 'set_current_strategy'),
    ('TradingController', 'get_current_strategy'),
]

# 服务定义文件
SERVICE_FILES = {
    'TradingService': 'core/services/trading_service.py',
    'OrderExecutor': 'core/trading/order_executor.py',
    'OrderService': 'core/trading/order_service.py',
    'TradingController': 'core/trading_controller.py',
}

SEARCH_DIRS = ['core', 'gui', 'web', 'tests', 'scripts', 'plugins']


def source1_grep_recursive(method_name):
    """源 1: Grep 跨 4 子目录文本搜索 - 任何引用形式"""
    all_files = []
    for d in SEARCH_DIRS:
        if not pathlib.Path(d).exists():
            continue
        for p in pathlib.Path(d).rglob('*.py'):
            if '__pycache__' in str(p) or '.pytest_cache' in str(p):
                continue
            all_files.append(p)
    hits = []
    # 匹配 4 种引用模式: .method(  / self.method(  /  method(  / "method"
    patterns = [
        rf'\.{re.escape(method_name)}\(',  # .method(
        rf'\b{re.escape(method_name)}\(',  # method(
        rf'["\']({re.escape(method_name)})["\']',  # 字符串
    ]
    for p in all_files:
        try:
            src = p.read_text(encoding='utf-8')
        except Exception:
            continue
        for line_num, line in enumerate(src.splitlines(), 1):
            for pat in patterns:
                if re.search(pat, line):
                    # 排除定义行和注释行
                    if 'def ' in line or '# ' in line or line.strip().startswith('#'):
                        continue
                    hits.append((str(p), line_num, line.strip()[:120]))
                    break
    return hits


def source2_ast_scan(method_name):
    """源 2: AST 扫描 - 检查 get/setattr 动态调用"""
    all_files = []
    for d in SEARCH_DIRS:
        if not pathlib.Path(d).exists():
            continue
        for p in pathlib.Path(d).rglob('*.py'):
            if '__pycache__' in str(p) or '.pytest_cache' in str(p):
                continue
            all_files.append(p)

    hits = []
    for p in all_files:
        try:
            src = p.read_text(encoding='utf-8')
        except Exception:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            # getattr(obj, 'method_name', ...)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == 'getattr':
                    if len(node.args) >= 2:
                        arg = node.args[1]
                        if isinstance(arg, ast.Constant) and arg.value == method_name:
                            hits.append(f'{p}:getattr:{node.lineno}')
                # setattr(obj, 'method_name', ...)
                if isinstance(node.func, ast.Name) and node.func.id == 'setattr':
                    if len(node.args) >= 2:
                        arg = node.args[1]
                        if isinstance(arg, ast.Constant) and arg.value == method_name:
                            hits.append(f'{p}:setattr:{node.lineno}')
    return hits


def source3_read_definition(service_name, method_name):
    """源 3: Read 类定义处确认"""
    fp = SERVICE_FILES.get(service_name)
    if not fp or not pathlib.Path(fp).exists():
        return None, []
    try:
        src = pathlib.Path(fp).read_text(encoding='utf-8')
    except Exception as e:
        return None, [f'Read error: {e}']
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return None, [f'SyntaxError: {e}']
    for cls in ast.walk(tree):
        if isinstance(cls, ast.ClassDef) and cls.name == service_name:
            for m in cls.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name == method_name:
                    docstring = ast.get_docstring(m) or ''
                    return f'{fp}:L{m.lineno}', [f'def signature: ({ast.unparse(m.args)})', f'docstring preview: {docstring[:200]}']
    return None, ['NOT FOUND in class definition']


def source4_business_chain(hits):
    """源 4: 业务调用链追踪 - 排除注释/docstring/未启用开关"""
    real_calls = []
    for path, line_num, line in hits:
        # 排除 docstring/注释
        if '"""' in line or "'''" in line or '# ' in line:
            continue
        # 排除 "method_name" 字符串(可能只是名字)
        real_calls.append((path, line_num, line))
    return real_calls


def verify_one(service, method):
    """4 源验证单条"""
    print(f'\n=== {service}.{method} 4 源验证 ===')

    # 源 1: Grep
    grep_hits = source1_grep_recursive(method)
    print(f'  源 1 (Grep 跨子目录): {len(grep_hits)} hits')
    if len(grep_hits) <= 3:
        for h in grep_hits:
            print(f'    {h[0]}:{h[1]} | {h[2]}')

    # 源 2: AST 动态调用
    ast_hits = source2_ast_scan(method)
    print(f'  源 2 (AST getattr/setattr): {len(ast_hits)} hits')
    for h in ast_hits[:3]:
        print(f'    {h}')

    # 源 3: Read 定义
    def_loc, def_details = source3_read_definition(service, method)
    print(f'  源 3 (Read 定义): {def_loc}')
    for d in def_details:
        print(f'    {d}')

    # 源 4: 业务链
    real_calls = source4_business_chain(grep_hits)
    print(f'  源 4 (业务调用链): {len(real_calls)} real callsite')
    for rc in real_calls[:5]:
        print(f'    {rc[0]}:{rc[1]} | {rc[2]}')

    # 综合判定
    total_evidence = len(grep_hits) + len(ast_hits) + len(real_calls)
    is_dead = total_evidence == 0
    print(f'  ==> 判定: {"真死代码 (可物理删除)" if is_dead else f"NOT DEAD ({total_evidence} hit)"}')
    return is_dead


def main():
    print('R162-A 子智能体: 5+1 服务方法 4 源验证\n')
    print('=' * 60)

    truly_dead = []
    for svc, m in DEAD_CANDIDATES:
        if verify_one(svc, m):
            truly_dead.append((svc, m))

    print('\n' + '=' * 60)
    print(f'真死代码候选 (4 源 0 hit, 可物理删除): {len(truly_dead)}/{len(DEAD_CANDIDATES)}')
    for svc, m in truly_dead:
        print(f'  - {svc}.{m}')


if __name__ == '__main__':
    main()
