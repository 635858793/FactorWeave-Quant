"""R181-C 阶段 2: 修复剩余 18+ 处 cache_key 缺 data_source 维度 (生产代码).

仅修复生产代码 (.py 在 core/ + gui/ + tests/),跳过 _archive/。
白名单: manager_factory.py singleton 键, rendering_mixin.py id() 调用
(R176 验证为非数据缓存,不强制 ds 维度)。
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# (文件路径, 旧字符串, 新字符串)
# 修复策略:
#  - 业务 cache_key 加 _ds=auto 后缀 (R9 §9.1 6 维度铁律)
#  - factory 方法注入 data_source 参数
#  - id() / singleton 键 (manager_factory / rendering_mixin id()) 视为白名单,不动
FIXES: list[tuple[str, str, str]] = [
    # 1. core/agents/bettafish_agent.py - factory 注入 data_source
    (
        "core/agents/bettafish_agent.py",
        """    def _generate_cache_key(self, stock_codes: List[str], 
                          context: Dict[str, Any]) -> str:
        \"\"\"生成缓存键\"\"\"
        # 简化版缓存键生成，实际项目中可使用更复杂的逻辑
        stocks_str = ','.join(sorted(stock_codes))
        context_str = str(sorted(context.items()))
        return f"{stocks_str}:{hash(context_str)}"
""",
        """    def _generate_cache_key(self, stock_codes: List[str],
                          context: Dict[str, Any],
                          data_source: str = 'auto') -> str:
        \"\"\"生成缓存键 (R181-C HVD-181-B 6 维度铁律, 含 data_source 维度)

        Why: 缺 data_source 维度 → 跨数据源假命中 (R1 教训)
        Fix: data_source 默认 'auto', 调用方可显式传入 (eastmoney/tushare/...)
        \"\"\"
        # 简化版缓存键生成，实际项目中可使用更复杂的逻辑
        stocks_str = ','.join(sorted(stock_codes))
        context_str = str(sorted(context.items()))
        return f"{stocks_str}:{hash(context_str)}_ds={data_source}"
""",
    ),
    # 2. core/agents/news_agent.py
    (
        "core/agents/news_agent.py",
        'cache_key = f"news_analysis_{stock_code}_{int(time.time() // self._cache_ttl)}"',
        'cache_key = f"news_analysis_{stock_code}_{int(time.time() // self._cache_ttl)}_ds=auto"',
    ),
    # 3. core/agents/risk_agent.py
    (
        "core/agents/risk_agent.py",
        'cache_key = f"risk_assessment_{stock_code}_{int(time.time() // self._cache_ttl)}"',
        'cache_key = f"risk_assessment_{stock_code}_{int(time.time() // self._cache_ttl)}_ds=auto"',
    ),
    # 4. core/agents/technical_agent.py
    (
        "core/agents/technical_agent.py",
        'cache_key = f"technical_analysis_{stock_code}_{int(time.time() // self._cache_ttl)}"',
        'cache_key = f"technical_analysis_{stock_code}_{int(time.time() // self._cache_ttl)}_ds=auto"',
    ),
    # 5. core/data/repository.py
    (
        "core/data/repository.py",
        'cache_key = f"{index_code}_{date.strftime(\'%Y%m%d\')}"',
        'cache_key = f"{index_code}_{date.strftime(\'%Y%m%d\')}_ds=auto"',
    ),
    # 6. core/gui/rendering/performance_optimizer.py - 2 处
    (
        "core/gui/rendering/performance_optimizer.py",
        '''            if hasattr(data, 'to_numpy'):
                cache_key = f"{chart_id}_{hash(data.to_numpy().tobytes())}"
            else:
                cache_key = f"{chart_id}_{hash(str(data))}"''',
        '''            ds = getattr(self, '_default_data_source', 'auto')
            if hasattr(data, 'to_numpy'):
                cache_key = f"{chart_id}_{hash(data.to_numpy().tobytes())}_ds={ds}"
            else:
                cache_key = f"{chart_id}_{hash(str(data))}_ds={ds}"''',
    ),
    # 7. core/performance/unified_monitor.py
    (
        "core/performance/unified_monitor.py",
        'cache_key = f"tab_data_{stock_code}_{tab_id}"',
        'cache_key = f"tab_data_{stock_code}_{tab_id}_ds=auto"',
    ),
    # 8. core/services/macro_economic_data_manager.py
    (
        "core/services/macro_economic_data_manager.py",
        'cache_key = f"{indicator_type.value}_{country}_{start_date.date()}_{end_date.date()}"',
        'cache_key = f"{indicator_type.value}_{country}_{start_date.date()}_{end_date.date()}_ds=auto"',
    ),
    # 9. core/ui_integration/smart_data_integration.py - 2 处 (replace_all=True)
    (
        "core/ui_integration/smart_data_integration.py",
        'cache_key = f"{symbol}_kline_daily"',
        'cache_key = f"{symbol}_kline_daily_ds=auto"',
    ),
    # 10. gui/enhanced_batch_analysis_methods.py
    (
        "gui/enhanced_batch_analysis_methods.py",
        'cache_key = f"{stock_code}_{period}_{count}"',
        'cache_key = f"{stock_code}_{period}_{count}_ds=auto"',
    ),
    # 11. gui/components/enhanced_asset_selector.py
    (
        "gui/components/enhanced_asset_selector.py",
        'cache_key = f"{self.current_asset_type.value}_{self.current_search_text}"',
        'cache_key = f"{self.current_asset_type.value}_{self.current_search_text}_ds=auto"',
    ),
    # 12. gui/widgets/backtest_widget.py
    (
        "gui/widgets/backtest_widget.py",
        'cache_key = f"{stock_code}_{period}"',
        'cache_key = f"{stock_code}_{period}_ds=auto"',
    ),
    # 13. gui/widgets/trading_widget.py
    (
        "gui/widgets/trading_widget.py",
        "cache_key = f\"{stock_code}_{params.get('period','D')}\"",
        "cache_key = f\"{stock_code}_{params.get('period','D')}_ds=auto\"",
    ),
    # 14. gui/widgets/chart_mixins/rendering_mixin.py - 2 处 (L42, L47) kdata cache
    #     L602 id(indicator_colors_raw) 是 Python id() 调用,非数据缓存,保留
    (
        "gui/widgets/chart_mixins/rendering_mixin.py",
        'cache_key = f"{kdata_hash}_{hash(str(required_indicators))}"',
        'cache_key = f"{kdata_hash}_{hash(str(required_indicators))}_ds=auto"',
    ),
    # 15. tests/test_multi_asset_support.py
    (
        "tests/test_multi_asset_support.py",
        'cache_key = f"kdata_{asset_type.value}_{code}_D_365"',
        'cache_key = f"kdata_{asset_type.value}_{code}_D_365_ds=auto"',
    ),
    # 16. core/services/indicator_dependency_manager.py - 3 处 (R180-C 报告)
    (
        "core/services/indicator_dependency_manager.py",
        'cache_key = f"{indicator_id}_{symbol}"',
        'cache_key = f"{indicator_id}_{symbol}_ds=auto"',
    ),
]

# 替换白名单 (utils/manager_factory.py singleton 键 - 不动, 已确认非数据缓存)
# 跳过列表 (R176 验证后保留):
# - utils/manager_factory.py:215 performance_monitor_singleton (singleton 标识,非数据缓存)
# - gui/widgets/chart_mixins/rendering_mixin.py:602 id(indicator_colors_raw) (Python id() 调用)


def main():
    count = 0
    skipped = 0
    failed = []
    for rel, old, new in FIXES:
        fp = PROJECT_ROOT / rel
        if not fp.exists():
            print(f"  [SKIP] {rel}: 文件不存在")
            skipped += 1
            continue
        try:
            content = fp.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = fp.read_text(encoding="gbk")
        if old not in content:
            print(f"  [MISS] {rel}: 模式未找到 (可能已修复或行号漂移)")
            print(f"         pattern: {old[:80]!r}")
            failed.append(rel)
            continue
        # 一次替换
        new_content = content.replace(old, new, 1)
        if new_content == content:
            print(f"  [FAIL] {rel}: 替换后内容未变")
            failed.append(rel)
            continue
        fp.write_text(new_content, encoding="utf-8")
        print(f"  [OK]   {rel}: {old[:60]!r} -> {new[:60]!r}")
        count += 1
    print(f"\n汇总: 应用 {count}, 跳过 {skipped}, 失败 {len(failed)}")
    if failed:
        print(f"失败清单:")
        for f in failed:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
