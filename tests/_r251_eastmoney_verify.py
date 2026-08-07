#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R251 东方财富插件频率映射修复验证

覆盖：
1. eastmoney_plugin.py（静态 AST 断言）
   - get_kdata 内 freq_map 含 5m/15m/30m/60m 缩写键（映射到 5min/15min/30min/60min）及 d/w/m 小写键
   - 两处 capabilities 'frequencies' 统一为 ["1m","5m","15m","30m","60m","D","W","M"]
   - plugin_info 属性 capabilities 'supported_frequencies' 补全为 8 周期
   - get_kline_data 内 period_mapping 完整
2. eastmoney_unified_plugin.py（mock session.get 运行时验证）
   - get_kdata('D') -> klt=101, get_kdata('1m') -> klt=1, get_kdata('60m') -> klt=60
   - 额外: 'W'/'M'/'5m'/'daily'/'m' 等映射

运行: python tests/_r251_eastmoney_verify.py
"""
import sys
import os
import ast
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock  # noqa: E402

from core.plugin_types import AssetType  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN1 = os.path.join(BASE, 'plugins', 'data_sources', 'stock', 'eastmoney_plugin.py')
PLUGIN2 = os.path.join(BASE, 'plugins', 'data_sources', 'eastmoney_unified_plugin.py')

FAILURES = []


def check(name, ok, detail=''):
    status = 'PASS' if ok else 'FAIL'
    print(f'[{status}] {name}' + (f' - {detail}' if detail and not ok else ''))
    if not ok:
        FAILURES.append(f'{name}: {detail}')


def load_ast(path):
    with open(path, 'r', encoding='utf-8') as f:
        return ast.parse(f.read())


def find_dict_assign(tree, var_name):
    """在 AST 中查找形如 var_name = {...} 的字典字面量"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == var_name and isinstance(node.value, ast.Dict):
                    try:
                        return {ast.literal_eval(k): ast.literal_eval(v)
                                for k, v in zip(node.value.keys, node.value.values)}
                    except Exception:
                        return None
    return None


def find_capabilities_dicts(tree):
    """提取 AST 中所有含 'frequencies' 或 'supported_frequencies' 键的 dict 字面量"""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            mapping = {}
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    if isinstance(v, ast.List):
                        items = []
                        for e in v.elts:
                            try:
                                items.append(ast.literal_eval(e))
                            except Exception:
                                items.append(None)
                        mapping[k.value] = items
            if mapping:
                found.append(mapping)
    return found


def test_eastmoney_plugin_static():
    print('\n===== 1) eastmoney_plugin.py 静态断言 =====')
    tree = load_ast(PLUGIN1)

    freq_map = find_dict_assign(tree, 'freq_map')
    check('freq_map 存在', freq_map is not None)
    if freq_map is not None:
        for abbr, long_name in [('5m', '5min'), ('15m', '15min'), ('30m', '30min'), ('60m', '60min')]:
            check(f"freq_map['{abbr}'] == '{long_name}'",
                  freq_map.get(abbr) == long_name, f"实际: {freq_map.get(abbr)}")
        for abbr, long_name in [('d', 'daily'), ('w', 'weekly'), ('m', 'monthly')]:
            check(f"freq_map['{abbr}'] == '{long_name}'",
                  freq_map.get(abbr) == long_name, f"实际: {freq_map.get(abbr)}")
        for key in ['D', 'W', 'M', '1m', '1min', '5min', '15min', '30min', '60min', 'daily', 'weekly', 'monthly']:
            check(f'freq_map 保留键 {key}', key in freq_map)

    period_mapping = find_dict_assign(tree, 'period_mapping')
    check('period_mapping 存在', period_mapping is not None)
    if period_mapping is not None:
        expected_pm = {'1min': '1', '5min': '5', '15min': '15', '30min': '30',
                       '60min': '60', 'daily': '101', 'weekly': '102', 'monthly': '103'}
        check('period_mapping 完整', period_mapping == expected_pm, f'实际: {period_mapping}')

    caps = find_capabilities_dicts(tree)
    freq_lists = [c['frequencies'] for c in caps if 'frequencies' in c]
    check('capabilities frequencies 声明共 3 处（get_plugin_info x2 + plugin_info 等）',
          len(freq_lists) == 3, f'实际数量: {len(freq_lists)}')
    expected_freqs = ['1m', '5m', '15m', '30m', '60m', 'D', 'W', 'M']
    for i, fl in enumerate(freq_lists):
        check(f'frequencies[{i}] == 8 周期标准格式', fl == expected_freqs, f'实际: {fl}')
        check(f'frequencies[{i}] 含 W/M', 'W' in fl and 'M' in fl, f'实际: {fl}')

    sup_freq_lists = [c['supported_frequencies'] for c in caps if 'supported_frequencies' in c]
    check('supported_frequencies 出现 1 处', len(sup_freq_lists) == 1, f'实际数量: {len(sup_freq_lists)}')
    if sup_freq_lists:
        expected_sf = ['1min', '5min', '15min', '30min', '60min', 'daily', 'weekly', 'monthly']
        check('supported_frequencies 补全为 8 周期', sup_freq_lists[0] == expected_sf, f'实际: {sup_freq_lists[0]}')


class MockResponse:
    """模拟 requests.Response"""
    def __init__(self, payload=None):
        self.status_code = 200
        self._payload = payload if payload is not None else {'data': {'klines': []}}

    def json(self):
        return self._payload


def test_eastmoney_unified_mock():
    print('\n===== 2) eastmoney_unified_plugin.py mock 验证 =====')
    from plugins.data_sources.eastmoney_unified_plugin import EastmoneyUnifiedPlugin

    plugin = EastmoneyUnifiedPlugin()
    mock_get = MagicMock(return_value=MockResponse())
    plugin.session.get = mock_get

    start, end = datetime(2026, 1, 1), datetime(2026, 12, 31)
    cases = [
        # (period 入参, 期望 klt)
        ('D', '101'),
        ('d', '101'),
        ('W', '102'),
        ('w', '102'),
        ('M', '103'),
        ('m', '103'),
        ('1m', '1'),
        ('5m', '5'),
        ('15m', '15'),
        ('30m', '30'),
        ('60m', '60'),
        ('1min', '1'),
        ('60min', '60'),
        ('daily', '101'),
        ('weekly', '102'),
        ('monthly', '103'),
    ]

    for period, expected_klt in cases:
        mock_get.reset_mock()
        plugin.get_kdata('600000', period, start, end, AssetType.STOCK_A)
        assert mock_get.called, f'period={period}: session.get 未被调用'
        _, kwargs = mock_get.call_args
        actual_klt = kwargs.get('params', {}).get('klt')
        check(f"get_kdata('{period}') -> klt={expected_klt}", actual_klt == expected_klt,
              f'实际 klt={actual_klt}')

    # 未知周期回退日线
    mock_get.reset_mock()
    plugin.get_kdata('600000', 'unknown_period', start, end, AssetType.STOCK_A)
    _, kwargs = mock_get.call_args
    actual_klt = kwargs.get('params', {}).get('klt')
    check("get_kdata('unknown_period') 回退 klt=101", actual_klt == '101', f'实际 klt={actual_klt}')


def main():
    test_eastmoney_plugin_static()
    test_eastmoney_unified_mock()

    print('\n===== 汇总 =====')
    if FAILURES:
        print(f'FAILED: {len(FAILURES)} 项未通过')
        for f in FAILURES:
            print(f'  - {f}')
        sys.exit(1)
    print('ALL PASS')


if __name__ == '__main__':
    main()
