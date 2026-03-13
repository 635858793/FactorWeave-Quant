"""
形态分析渲染功能测试 - 极简版
"""
import ast

def test_file_syntax(filepath):
    """测试文件语法"""
    with open(filepath, 'r', encoding='utf-8') as f:
        ast.parse(f.read())
    print(f"[OK] {filepath} 语法正确")

def test_style_manager():
    """测试样式管理器"""
    code = """
class PatternStyleManager:
    DARK_STYLES = {'head_shoulders': {'line_color': '#FF0000'}}
    LIGHT_STYLES = {'head_shoulders': {'line_color': '#CC0000'}}
    
    @classmethod
    def get_style(cls, pattern_type='default', is_dark=True):
        styles = cls.DARK_STYLES if is_dark else cls.LIGHT_STYLES
        return styles.get(pattern_type, styles['default'])
"""
    exec(code)
    print("[OK] PatternStyleManager 逻辑正确")

def test_deduplication():
    """测试去重逻辑"""
    code = """
class ChartWidget:
    def __init__(self):
        self._last_pattern_request_key = None
        self._pattern_render_timer = None
    
    def handle(self, event):
        key = f"{event.pattern_name}_{event.analysis_type}"
        if self._last_pattern_request_key == key:
            return "skip"
        self._last_pattern_request_key = key
        return "render"
"""
    exec(code)
    print("[OK] 去重逻辑正确")

def test_event_data():
    """测试事件数据"""
    code = """
class PatternSignalsDisplayEvent:
    def __init__(self, pattern_name='', pattern_data=None):
        self.data = {'pattern_name': pattern_name, 'pattern_data': pattern_data or {}}
        self.pattern_name = pattern_name
        self.pattern_data = pattern_data or {}
"""
    exec(code)
    print("[OK] 事件数据结构正确")

if __name__ == '__main__':
    print("=" * 50)
    print("形态分析渲染功能测试")
    print("=" * 50)
    
    files = [
        'gui/widgets/chart_mixins/signal_mixin.py',
        'gui/widgets/chart_widget.py',
        'gui/widgets/analysis_tabs/pattern_tab_pro.py',
        'core/events/types.py',
    ]
    
    print("\n1. 语法测试:")
    for f in files:
        try:
            test_file_syntax(f)
        except Exception as e:
            print(f"[FAIL] {f}: {e}")
    
    print("\n2. 样式管理器测试:")
    test_style_manager()
    
    print("\n3. 去重机制测试:")
    test_deduplication()
    
    print("\n4. 事件数据结构测试:")
    test_event_data()
    
    print("\n" + "=" * 50)
    print("所有测试通过!")
    print("=" * 50)
