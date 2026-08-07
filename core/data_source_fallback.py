
# ============================================================
# DEPRECATED: 本模块整体已废弃（mock 兜底会干扰真实场景）。
# 真实数据源不可用时不再注入模拟数据，由上层显式报错或返回空数据。
# 保留函数签名以兼容潜在引用。
# ============================================================

# 数据源降级配置（已移除 "mock_data" 模拟兜底项）
DATA_SOURCE_FALLBACK = {
    "stock_list": [
        "local_cache",      # 优先使用本地缓存
        "duckdb",           # 其次使用DuckDB
    ],
    "realtime_quotes": [
        "local_cache",
    ],
    "kline_data": [
        "local_cache",
        "duckdb",
    ]
}

def get_fallback_stock_list():
    """获取降级股票列表 — DEPRECATED: 不再生成模拟股票数据，返回空数据"""
    import pandas as pd
    from loguru import logger

    logger.warning("DEPRECATED: get_fallback_stock_list 不再生成模拟股票列表，返回空数据")

    return pd.DataFrame(columns=['code', 'name', 'market', 'is_simulated'])

def get_fallback_realtime_quotes(codes):
    """获取降级实时行情 — DEPRECATED: 无真实降级数据源，返回空数据"""
    import pandas as pd

    return pd.DataFrame(columns=['code', 'name', 'price', 'change', 'change_pct', 'volume', 'amount'])
