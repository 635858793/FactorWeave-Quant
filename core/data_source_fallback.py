
# 数据源降级配置
DATA_SOURCE_FALLBACK = {
    "stock_list": [
        "local_cache",      # 优先使用本地缓存
        "duckdb",          # 其次使用DuckDB
        "mock_data"        # 最后使用模拟数据
    ],
    "realtime_quotes": [
        "local_cache",
        "mock_data"
    ],
    "kline_data": [
        "local_cache", 
        "duckdb",
        "mock_data"
    ]
}

def get_fallback_stock_list():
    """获取降级股票列表 — 仅供紧急降级使用，不反映真实市场数据"""
    import pandas as pd
    from loguru import logger

    logger.warning("正在使用降级模拟股票列表！请检查数据源连接是否正常。")

    stock_codes = []

    for i in range(600000, 600100):
        stock_codes.append(f"{i:06d}.SH")

    for i in range(1, 100):
        stock_codes.append(f"{i:06d}.SZ")

    df = pd.DataFrame({
        'code': stock_codes,
        'name': [f'[模拟]股票{i:04d}' for i in range(len(stock_codes))],
        'market': ['SH' if code.endswith('.SH') else 'SZ' for code in stock_codes],
        'is_simulated': True
    })

    return df

def get_fallback_realtime_quotes(codes):
    """获取降级实时行情"""
    import pandas as pd

    return pd.DataFrame(columns=['code', 'name', 'price', 'change', 'change_pct', 'volume', 'amount'])
