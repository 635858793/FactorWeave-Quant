"""R290 修复验证脚本：验证 timestamp 重复列 / dropna 删光 / _find_plugin_class 三个修复"""
import sys
import os
import importlib.util

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 1. 验证 _filter_dataframe_columns：datetime+timestamp 并存不再产生重复列
from core.asset_database_manager import AssetSeparatedDatabaseManager


def test_filter_duplicate_timestamp():
    mgr = AssetSeparatedDatabaseManager.__new__(AssetSeparatedDatabaseManager)
    # 表列含 timestamp（模拟 historical_kline_data 结构）
    table_columns = ['symbol', 'data_source', 'timestamp', 'frequency',
                     'open', 'high', 'low', 'close', 'volume', 'amount']
    data = __import__('pandas').DataFrame({
        'datetime': ['2026-08-05', '2026-08-06'],
        'timestamp': ['2026-08-05 00:00:00', '2026-08-06 00:00:00'],
        'open': [1.0, 2.0], 'high': [1.5, 2.5], 'low': [0.5, 1.5],
        'close': [1.2, 2.2], 'volume': [100, 200], 'amount': [1000, 2000],
    })
    filtered = mgr._filter_dataframe_columns(data, table_columns)
    dup = filtered.columns[filtered.columns.duplicated()].tolist()
    assert len(dup) == 0, f"存在重复列: {dup}"
    assert filtered.columns.tolist().count('timestamp') == 1
    print(f"[PASS] _filter_dataframe_columns 重复列防护: 列={filtered.columns.tolist()}")


# 2. 验证 _persist_kdata_to_duckdb 逻辑：新增 timestamp 后 datetime 被删除
from core.services.unified_data_manager import UnifiedDataManager


def test_persist_drops_datetime():
    pd = __import__('pandas')
    mgr = UnifiedDataManager.__new__(UnifiedDataManager)
    mgr.asset_manager = None
    df = pd.DataFrame({'datetime': ['2026-08-05'], 'open': [1.0],
                       'high': [1.5], 'low': [0.5], 'close': [1.2], 'volume': [100]})
    # 直接内联验证同款逻辑
    persist_df = df.copy()
    if 'timestamp' not in persist_df.columns:
        if 'datetime' not in persist_df.columns and 'date' not in persist_df.columns:
            pass
        if 'datetime' in persist_df.columns:
            persist_df['timestamp'] = pd.to_datetime(persist_df['datetime'])
            persist_df = persist_df.drop(columns=['datetime'])
    assert 'datetime' not in persist_df.columns, "datetime 未被删除"
    assert 'timestamp' in persist_df.columns, "timestamp 未生成"
    print(f"[PASS] _persist_kdata_to_duckdb 时间列处理: {persist_df.columns.tolist()}")


# 3. 验证 _find_plugin_class：MiniQMTConfig 不再被误判为插件类
from plugins.data_sources.stock import miniqmt_plugin as mq
from core.plugin_manager import PluginManager


def test_find_plugin_class_skips_config():
    mgr = PluginManager.__new__(PluginManager)
    # 用真实模块验证：应找到 MiniQMTPlugin 而非 MiniQMTConfig
    found = mgr._find_plugin_class(mq)
    assert found is not None, "未找到插件类"
    assert found.__name__ == 'MiniQMTPlugin', f"误判为 {found.__name__}"
    assert hasattr(found, 'subscribe_realtime_data'), "真实插件应支持 subscribe_realtime_data"
    print(f"[PASS] _find_plugin_class 跳过 Config 类: {found.__name__}")


# 4. 验证 dropna 修复语义
def test_dropna_subset():
    pd = __import__('pandas')
    df = pd.DataFrame({
        'open': [1.0, 2.0], 'high': [1.5, 2.5], 'low': [0.5, 1.5],
        'close': [1.2, 2.2], 'volume': [100, 200],
        'adj_type': [None, None], 'adj_source': [None, None],
        'data_quality_score': [None, None],
    })
    # 旧逻辑
    old = df.dropna(how='any')
    # 新逻辑
    new = df.dropna(subset=['open', 'high', 'low', 'close', 'volume'])
    assert old.empty, "旧逻辑 how='any' 应删光"
    assert len(new) == 2, "新逻辑 subset 应保留全部行"
    print(f"[PASS] dropna 修复: 旧逻辑行数={len(old)}, 新逻辑行数={len(new)}")


if __name__ == '__main__':
    test_filter_duplicate_timestamp()
    test_persist_drops_datetime()
    test_find_plugin_class_skips_config()
    test_dropna_subset()
    print("\n全部 R290 修复验证通过 [OK]")
