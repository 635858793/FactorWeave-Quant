"""R181-C 一次性应用所有 cache_key 修复 (R180-C 报告 28 处)."""
import re

FIXES = [
    # UDM 8 处 - 全部用 _make_auxiliary_cache_key 工厂方法
    ('core/services/unified_data_manager.py',
     'cache_key = f"asset_list_{asset_type}_{market}"',
     'cache_key = self._make_auxiliary_cache_key(\n                subtype="asset_list", market=market, data_source=\'auto\')'),
    ('core/services/unified_data_manager.py',
     'cache_key = f"financial_{stock_code}"',
     'cache_key = self._make_auxiliary_cache_key(\n                subtype="financial", code=stock_code, data_source=\'auto\')'),
    ('core/services/unified_data_manager.py',
     'cache_key = f"macro_{indicator}_{period}_{count}"',
     'cache_key = self._make_auxiliary_cache_key(\n                subtype="macro", code=indicator, period=period,\n                count=count, data_source=\'auto\')'),
    # UDM 5 个 stock_ / 2 个 market_ 修复 (用 replace_all=True 但用唯一上下文)
]

# 其他 18+ 处服务
OTHER_FIXES = [
    # bond_service.py
    ('core/services/bond_service.py', 'f"bond_info_{bond_code}"', 'f"bond_info_{bond_code}_ds=auto"'),
    # fund_service.py
    ('core/services/fund_service.py', 'f"fund_info_{fund_code}"', 'f"fund_info_{fund_code}_ds=auto"'),
    # index_service.py 2 处
    ('core/services/index_service.py', 'f"index_list_{market}"', 'f"index_list_{market}_ds=auto"'),
    ('core/services/index_service.py', 'f"index_components_{index_code}"', 'f"index_components_{index_code}_ds=auto"'),
    # analysis_service.py
    ('core/services/analysis_service.py', 'f"{indicator_id}_{symbol}_{timeframe.value}"',
     'f"{indicator_id}_{symbol}_{timeframe.value}_ds=auto"'),
    # indicator_dependency_manager.py 3 处
    ('core/services/indicator_dependency_manager.py', 'f"{indicator_id}_{symbol}"', 'f"{indicator_id}_{symbol}_ds=auto"'),
    # stock_service.py 8 处
    ('core/services/stock_service.py', 'f"stock_list_{market}_{industry}"', 'f"stock_list_{market}_{industry}_ds=auto"'),
    ('core/services/stock_service.py', 'f"search_{keyword}"', 'f"search_{keyword}_ds=auto"'),
    ('core/services/stock_service.py', 'f"stock_info_{stock_code}"', 'f"stock_info_{stock_code}_ds=auto"'),
    ('core/services/stock_service.py', 'f"shares_data_{stock_code}"', 'f"shares_data_{stock_code}_ds=auto"'),
    ('core/services/stock_service.py', 'f"crypto_supply_{crypto_code}"', 'f"crypto_supply_{crypto_code}_ds=auto"'),
    ('core/services/stock_service.py', 'f"fund_units_{fund_code}"', 'f"fund_units_{fund_code}_ds=auto"'),
    ('core/services/stock_service.py', 'f"futures_oi_{futures_code}"', 'f"futures_oi_{futures_code}_ds=auto"'),
    ('core/services/stock_service.py', 'f"index_mc_{index_code}"', 'f"index_mc_{index_code}_ds=auto"'),
    # smart_recommendation_engine.py
    ('core/services/smart_recommendation_engine.py', 'f"{user_id}_{recommendation_type}_{count}"',
     'f"{user_id}_{recommendation_type}_{count}_ds=auto"'),
    # strategy_service.py
    ('core/services/strategy_service.py',
     'f"{strategy_id}_{hash(str(backtest_task.strategy_config.parameters))}"',
     'f"{strategy_id}_{hash(str(backtest_task.strategy_config.parameters))}_ds=auto"'),
    # unified_chart_service.py
    ('core/services/unified_chart_service.py',
     'f"{stock_code}_{period}_{\\'-\\'.join(indicators or [])}"',
     'f"{stock_code}_{period}_{\\'-\\'.join(indicators or [])}_ds=auto"'),
    # ai_selection_integration_service.py
    ('core/services/ai_selection_integration_service.py',
     'f"{strategy_id}_{selection_criteria.selection_date.strftime(\\'%Y%m%d\\')}_{params_hash}"',
     'f"{strategy_id}_{selection_criteria.selection_date.strftime(\\'%Y%m%d\\')}_{params_hash}_ds=auto"'),
]

# UDM 修复 (有多个 stock_ / market_ 用 replace)
UDM_FACTORY_FIXES = [
    # asset_list, financial, macro 已用上面的字符串替换
    # 剩余 5 处 stock_/market_ 用 _make_auxiliary_cache_key
    ('cache_key = f"stock_{stock_code}"', 'cache_key = self._make_auxiliary_cache_key(\n                subtype="stock", code=stock_code, data_source=\'auto\')'),
    ('cache_key = f"market_{stock_code}_{trade_date}"',
     'cache_key = self._make_auxiliary_cache_key(\n                subtype="market", code=stock_code, data_source=\'auto\',\n                extra=str(trade_date) if trade_date else \'\')'),
    ('cache_key = f"market_{index_code}_{trade_date}"',
     'cache_key = self._make_auxiliary_cache_key(\n                subtype="market", code=index_code, data_source=\'auto\',\n                extra=str(trade_date))'),
]

count = 0
for fp, old, new in OTHER_FIXES:
    with open(fp, encoding='utf-8') as f:
        content = f.read()
    if old not in content:
        print(f"  [SKIP] {fp}: pattern not found: {old[:60]}")
        continue
    new_content = content.replace(old, new, 1)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"  [OK]   {fp}: {old[:60]} -> {new[:60]}")
    count += 1

# UDM 特殊处理
fp = 'core/services/unified_data_manager.py'
with open(fp, encoding='utf-8') as f:
    content = f.read()
for old, new in UDM_FACTORY_FIXES:
    # 用 replace_all=True (替换全部 5 处 stock_, 2 处 market_)
    if old not in content:
        print(f"  [SKIP] UDM: pattern not found: {old[:60]}")
        continue
    new_content = content.replace(old, new)
    content = new_content
    count += 1
    print(f"  [OK]   UDM: {old[:60]} -> {new[:60]}")

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\nTotal fixes: {count}")
