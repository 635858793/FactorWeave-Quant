# -*- coding: utf-8 -*-
"""
R251 验证脚本：通达信插件 60分钟线被静默降级为日线 bug 修复验证

验证内容（全部基于 AST 静态提取源码中的映射字典，不实例化插件）：
1. period_mapping 包含 '60min' 与 '1hour' 键，均映射为通达信 60 分钟周期码 3
2. period_map 中 '60m' 映射为 '60min'（不再产生 '1hour'，消除静默降级路径）
3. 一致性检查：period_map 的所有值都能被 period_mapping 识别（无遗漏键）
4. 端到端：get_kdata(freq='60m') 经两层映射最终频率码为 3（60分钟线），而非 9（日线）
5. capabilities.frequencies 已补全 ["1m","5m","15m","30m","60m","D","W","M"]
"""
import ast
from pathlib import Path

PLUGIN = (Path(__file__).resolve().parent.parent
          / "plugins" / "data_sources" / "stock" / "tongdaxin_plugin.py")


def extract_dict_assign(tree, func_name, target_name):
    """提取指定函数内、目标名为 target_name 的 dict 字面量赋值（递归搜索函数体内所有层级）。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for child in ast.walk(node):
                if (isinstance(child, ast.Assign)
                        and len(child.targets) == 1
                        and isinstance(child.targets[0], ast.Name)
                        and child.targets[0].id == target_name
                        and isinstance(child.value, ast.Dict)):
                    return {
                        ast.literal_eval(k): ast.literal_eval(v)
                        for k, v in zip(child.value.keys, child.value.values)
                    }
    raise AssertionError(f"未在 {func_name} 中找到 {target_name} 字典赋值")


def extract_frequencies(tree):
    """提取 plugin_info property 中 capabilities['frequencies'] 列表。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "plugin_info":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Dict):
                    for k, v in zip(sub.keys, sub.values):
                        if (isinstance(k, ast.Constant) and k.value == "frequencies"
                                and isinstance(v, ast.List)):
                            return [ast.literal_eval(e) for e in v.elts]
    raise AssertionError("未找到 capabilities['frequencies']")


def main():
    source = PLUGIN.read_text(encoding="utf-8")
    tree = ast.parse(source)

    period_map = extract_dict_assign(tree, "get_kdata", "period_map")
    period_mapping = extract_dict_assign(tree, "get_kline_data", "period_mapping")
    frequencies = extract_frequencies(tree)

    # 1) period_mapping 含 '60min' 与 '1hour'，均指向通达信 60 分钟周期码 3
    assert '60min' in period_mapping, "period_mapping 缺少 '60min' 键"
    assert period_mapping['60min'] == 3, \
        f"period_mapping['60min'] 应为 3，实际 {period_mapping['60min']}"
    assert '1hour' in period_mapping, "period_mapping 缺少 '1hour' 兼容键"
    assert period_mapping['1hour'] == 3, \
        f"period_mapping['1hour'] 应为 3，实际 {period_mapping['1hour']}"

    # 2) period_map 中 '60m' -> '60min'，不再产出 '1hour'
    assert period_map.get('60m') == '60min', \
        f"period_map['60m'] 应为 '60min'，实际 {period_map.get('60m')!r}"
    assert '1hour' not in period_map.values(), "period_map 仍会产出 '1hour'（静默降级路径存在）"

    # 3) 一致性：period_map 所有值均能被 period_mapping 识别
    missing = [v for v in period_map.values() if v not in period_mapping]
    assert not missing, f"period_map 的值无法被 period_mapping 识别: {missing}"

    # 4) 端到端：get_kdata(freq='60m') 最终频率码应为 3，而非默认 9（日线）
    period = period_map.get('60m', 'daily')
    tdx_code = period_mapping.get(period, 9)
    assert tdx_code == 3, \
        f"get_kdata('60m') 最终频率码应为 3（60分钟线），实际 {tdx_code}（9=日线）"

    # 其余声明频率不受影响
    for f in ('1m', '5m', '15m', '30m', 'D', 'W', 'M'):
        p = period_map.get(f, 'daily')
        assert p in period_mapping, f"频率 {f} -> {p} 无法被 period_mapping 识别"

    # 5) capabilities.frequencies 补全 W/M
    expected_freqs = ["1m", "5m", "15m", "30m", "60m", "D", "W", "M"]
    assert frequencies == expected_freqs, \
        f"capabilities.frequencies 应为 {expected_freqs}，实际 {frequencies}"

    print("ALL CHECKS PASSED")
    print(f"  period_map['60m']        = {period_map['60m']!r}")
    print(f"  period_mapping['60min']  = {period_mapping['60min']}")
    print(f"  period_mapping['1hour']  = {period_mapping['1hour']}")
    print(f"  get_kdata('60m') 最终频率码 = "
          f"{period_mapping[period_map['60m']]} (3=60分钟线, 9=日线)")
    print(f"  frequencies = {frequencies}")


if __name__ == "__main__":
    main()
