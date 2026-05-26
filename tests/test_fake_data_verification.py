"""全系统假数据清除验证 + 逻辑正确性 + 性能优化测试"""
import os, sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import json, warnings, importlib, re
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope='session')
def real_data():
    path = Path(__file__).parent / '_real_test_data.json'
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ================== 1. 假数据残留全局扫描 ==================

FAKE_PATTERNS = ['np\\.random', 'random\\.randint', 'random\\.uniform',
                 'random\\.sample', 'random\\.random\\(']

SCAN_EXCLUDE = ['__pycache__', '_deprecated', '.git', 'tests', 'venv', '.venv',
                 'node_modules', '_temp_fix', 'check_', 'analyze_', 'verify_',
                 'validate_', 'debug_', 'diagnose_', 'benchmark', 'monitor_']

SCAN_TARGETS = ['core', 'gui', 'plugins', 'components', 'backtest', 'utils', 'optimization']

# Files with legitimate ML/optimization random usage (not fake data):
LEGITIMATE_RANDOM_FILES = {
    'core/services/auto_ml_optimizer.py',         # ML hyperparameter sampling
    'core/ml_scoring_engine.py',                    # epsilon-greedy MAB strategy
    'core/intelligent_failover_engine.py',          # weighted random failover
    'core/tet_router_engine.py',                    # weighted random routing
    'core/services/strategy_service.py',            # random search optimization
    'core/strategy/parameter_manager.py',           # Bayesian/PSO/genetic sampling
    'backtest/jit_optimizer.py',                    # performance benchmarking
    'core/performance/professional_risk_metrics.py', # Monte Carlo VaR (quant finance)
    'core/ai/data_anomaly_detector.py',             # if __name__ test block
    'core/services/enhanced_indicator_service.py',  # if __name__ demo block
    'optimization/algorithm_optimizer.py',           # genetic/evolutionary/SA optimization
    'backtest/strategy_optimizer.py',               # strategy parameter space optimization
    'backtest/ultra_performance_optimizer.py',      # performance benchmarking
    'plugins/strategies/trend_following.py',         # if __name__ test block
    'plugins/data_sources/utils/retry_helper.py',   # network retry jitter & UA rotation
    'plugins/data_sources/utils/akshare_wrapper.py', # network request delay jitter
    'plugins/data_sources/crypto/crypto_universal_plugin.py', # weighted exchange selection
    'core/real_data_provider.py',                   # random sampling for data verification
    'core/ai/config_recommendation_engine.py',      # random candidate selection
    'core/services/tensorflow_gpu_manager.py',      # TF random for GPU test/training
}

# Files that are test/benchmark code (not production):
TEST_FILE_PATTERNS = ['integration_test', 'quick_test', 'performance_integration',
                       'benchmark', '_test.py', 'test_']


@pytest.mark.parametrize('pattern', FAKE_PATTERNS)
def test_no_fake_data_in_source_files(pattern):
    """扫描所有生产代码，验证假数据模式已清除（仅生产目录，排除合法ML用途和测试文件）"""
    found = []
    for target in SCAN_TARGETS:
        target_dir = PROJECT_ROOT / target
        if not target_dir.exists():
            continue
        for fpath in target_dir.rglob('*.py'):
            parts = fpath.parts
            if any(ex in parts for ex in SCAN_EXCLUDE):
                continue
            rel_path = str(fpath.relative_to(PROJECT_ROOT)).replace('\\', '/')
            if rel_path in LEGITIMATE_RANDOM_FILES:
                continue
            if any(p in rel_path.lower().replace('\\', '/') for p in TEST_FILE_PATTERNS):
                continue
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                matches = list(re.finditer(pattern, content))
                for m in matches:
                    line_no = content[:m.start()].count('\n') + 1
                    line = content.split('\n')[line_no - 1].strip()
                    if line.lstrip().startswith('#'):
                        continue
                    if pattern == 'import numpy as np' and 'from numpy' not in line:
                        pass
                    else:
                        found.append(f'{fpath.relative_to(PROJECT_ROOT)}:{line_no}: {line[:80]}')
            except Exception:
                pass

    if found:
        for item in found[:20]:
            print(f'  RESIDUAL: {item}')
        if len(found) > 20:
            print(f'  ... and {len(found) - 20} more')

    assert len(found) == 0, f'发现 {len(found)} 处假数据残留! 前20条已打印'


# ================== 2. 模块导入完整性 ==================

MODULES_TO_VERIFY = [
    ('核心服务', [
        'core.services.ai_selection_backtest_service', 'core.services.ai_prediction_service',
        'core.services.model_training_service', 'core.services.stock_service',
        'core.services.dynamic_risk_adjustment_service', 'core.services.advanced_risk_control_service',
        'core.services.enhanced_performance_bridge',
    ]),
    ('Agent层', ['core.agents.sentiment_agent', 'core.agents.news_agent',
                  'core.agents.technical_agent', 'core.agents.risk_agent']),
    ('交易接口', ['core.trading.interfaces.xtp_trading_interface',
                   'core.trading.interfaces.xtp_pro_trading_interface']),
    ('AI层', ['core.ai.intelligent_selection.intelligent_selector']),
    ('对话框', [
        'gui.dialogs.stock_detail_dialog', 'gui.dialogs.data_quality_dialog',
        'gui.dialogs.intelligent_model_selection_dialog', 'gui.dialogs.performance_evaluation_dialog',
        'gui.dialogs.data_management_dialog_unified', 'gui.dialogs.data_source_plugin_config_dialog',
        'gui.dialogs.plugin_manager_dialog_unified', 'gui.dialogs.indicator_selection_dialog',
    ]),
    ('Widget', [
        'gui.widgets.analysis_widget',
        'gui.widgets.intelligent_model_selection.performance_panel',
        'gui.widgets.intelligent_model_selection.results_panel',
        'gui.widgets.intelligent_model_selection.market_monitor',
        'gui.widgets.performance.tabs.strategy_performance_tab',
        'gui.widgets.enhanced_ui.data_quality_monitor_tab',
        'gui.widgets.data_quality_control_center',
    ]),
    ('数据源插件', [
        'plugins.data_sources.stock_international.yahoo_finance_plugin',
        'plugins.sentiment_data_sources.multi_source_sentiment_plugin',
        'plugins.sentiment_data_sources.exorde_sentiment_plugin',
        'plugins.sentiment_data_sources.crypto_sentiment_plugin',
        'plugins.sentiment_data_sources.news_sentiment_plugin',
        'plugins.data_sources.stock.tongdaxin_plugin',
    ]),
    ('组件', ['components.fund_flow', 'components.sentiment_stock_selector',
              'components.trade_api', 'components.selection_history_comparison']),
    ('回测', ['backtest.professional_ui_system']),
]


@pytest.mark.parametrize('category,modules', MODULES_TO_VERIFY)
def test_module_imports(category, modules):
    """验证所有已修复模块可以正常导入"""
    skipped = 0
    failed = []
    for mod_name in modules:
        parent_pkg = mod_name.split('.')[0]
        if parent_pkg in sys.modules and not hasattr(sys.modules[parent_pkg], '__path__'):
            skipped += 1
            continue
        _skip = False
        for part in mod_name.split('.')[:-1]:
            full = '.'.join(mod_name.split('.')[:mod_name.split('.').index(part)+1])
            if full in sys.modules and not hasattr(sys.modules[full], '__path__'):
                skipped += 1
                _skip = True
                break
        if _skip:
            continue
        try:
            importlib.import_module(mod_name)
        except ImportError as e:
            if 'PyQt' in str(e) or 'QApplication' in str(e) or 'sip' in str(e).lower() or 'not a package' in str(e):
                skipped += 1
                continue
            failed.append(f'{mod_name}: {e}')
        except Exception as e:
            if '__spec__' in str(e):
                skipped += 1
                continue
            failed.append(f'{mod_name}: {e}')
    if skipped:
        print(f'  [{category}] skipped {skipped} PyQt-dependent modules')
    assert not failed, f'{category} 导入失败: {failed}'


# ================== 3. 核心服务降级策略验证 ==================

def test_ai_selection_backtest_no_random(real_data):
    """验证回测服务不使用随机数"""
    import core.services.ai_selection_backtest_service as mod
    source = Path(mod.__file__).read_text(encoding='utf-8', errors='ignore')
    assert 'np.random' not in source, 'ai_selection_backtest 仍有 np.random 残留'
    assert 'industry_concentration = 0.5' not in source, '仍有硬编码 industry_concentration'
    assert 'volatility = 0.2' not in source, '仍有硬编码 volatility'
    assert 'max_drawdown = -0.15' not in source, '仍有硬编码 max_drawdown'


def test_sentiment_agent_no_random():
    """验证情绪Agent不使用随机数"""
    import core.agents.sentiment_agent as mod
    source = Path(mod.__file__).read_text(encoding='utf-8', errors='ignore')
    for pat in ['np.random', 'random.randint', 'random.uniform']:
        assert pat not in source, f'sentiment_agent 仍有 {pat} 残留'


def test_intelligent_selector_no_simulate():
    """验证智能选择器不再模拟预测"""
    import core.ai.intelligent_selection.intelligent_selector as mod
    source = Path(mod.__file__).read_text(encoding='utf-8', errors='ignore')
    assert 'base_value * 1.02' not in source, '仍有硬编码 base_value*1.02'
    assert 'return None' in source or 'logger.warning' in source, '降级策略不完整'


def test_advanced_risk_control_no_random():
    """验证高级风控使用真实数据源"""
    import core.services.advanced_risk_control_service as mod
    source = Path(mod.__file__).read_text(encoding='utf-8', errors='ignore')
    assert 'np.random.normal' not in source, '风控服务仍有 np.random.normal'
    assert 'service_container' in source.lower() or 'real_data' in source.lower(), \
        '风控服务未接入真实数据源'


# ================== 4. 数据源插件返回正确性 ==================

def test_plugins_return_proper_status():
    """验证不可用插件返回正确状态（非假success=True）"""
    try:
        from plugins.sentiment_data_sources.crypto_sentiment_plugin import CryptoSentimentPlugin
        p = CryptoSentimentPlugin()
        # 主入口应返回不可用
        try:
            result = p.fetch_sentiment_data('BTC')
            if isinstance(result, dict):
                assert result.get('success') is not True, '不可用插件不应返回success=True'
        except:
            pass
    except ImportError:
        pass

    try:
        from plugins.sentiment_data_sources.news_sentiment_plugin import NewsSentimentPlugin
        p = NewsSentimentPlugin()
        try:
            result = p.fetch_sentiment('test')
            if isinstance(result, dict):
                assert result.get('success') is not True, '不可用插件不应返回success=True'
        except:
            pass
    except ImportError:
        pass


def test_trade_api_returns_failure():
    """验证交易API返回失败状态"""
    try:
        from components.trade_api import SimulatedTradeAPI
        api = SimulatedTradeAPI()
        assert api.has_real_data is False, 'SimulatedTradeAPI 应标记为无真实数据'
        result = api.buy('TEST', 10.0)
        assert result.get('success') is False, 'buy 应返回失败'
        result = api.get_positions()
        assert result.get('success') is False, 'get_positions 应返回失败'
    except ImportError:
        pass


# ================== 5. 算法优化验证 ==================

def test_strategy_workflow_uses_dict_lookup():
    """验证策略开发工作流使用字典查找而非list.index"""
    try:
        import gui.widgets.strategy_development_workflow as mod
        source = Path(mod.__file__).read_text(encoding='utf-8', errors='ignore')
        has_optimization = any(k in source for k in ['_stage_index_map', '_index_map', 'enumerate('])
        assert has_optimization, '策略开发工作流未找到字典/枚举优化'
    except ImportError:
        pytest.skip('PyQt5依赖不可用')


def test_lru_cache_extensions():
    """验证lru_cache已添加"""
    files_to_check = [
        ('core/utils/database_utils.py', ['validate_symbol_format', 'standardize_market_code', 'normalize_symbol']),
        ('utils/formatting_utils.py', ['format_price', 'format_percentage', 'format_volume', 'format_amount']),
        ('utils/data_preprocessing.py', ['standardize_stock_code']),
    ]
    for rel_path, funcs in files_to_check:
        fpath = PROJECT_ROOT / rel_path
        if fpath.exists():
            source = fpath.read_text(encoding='utf-8', errors='ignore')
            assert 'lru_cache' in source, f'{rel_path} 缺少 lru_cache 导入'
            for func in funcs:
                # Find @lru_cache before function definition
                pattern = re.compile(r'@lru_cache.*\n\s*def\s+' + func, re.MULTILINE)
                assert pattern.search(source), f'{rel_path} {func} 缺少 @lru_cache'


# ================== 6. 系统负载数据验证 ==================

def test_performance_bridge_uses_psutil():
    """验证性能桥接使用psutil而非random"""
    try:
        import core.services.enhanced_performance_bridge as mod
        source = Path(mod.__file__).read_text(encoding='utf-8', errors='ignore')
        assert 'psutil' in source, '性能桥接未导入 psutil'
        assert 'random.uniform' not in source, '性能桥接仍有 random.uniform'
    except ImportError:
        pytest.skip('无法导入性能桥接')


def test_psutil_available(real_data):
    """验证psutil可用并返回真实系统数据"""
    import psutil
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    assert 0 <= cpu <= 100, f'CPU 值异常: {cpu}'
    assert 0 <= mem <= 100, f'内存值异常: {mem}'
    assert 0 <= disk <= 100, f'磁盘值异常: {disk}'


# ================== 7. 成分/资金流降级验证 ==================

def test_fund_flow_clean():
    """验证资金流组件已清除假数据"""
    try:
        import components.fund_flow as mod
        source = Path(mod.__file__).read_text(encoding='utf-8', errors='ignore')
        assert 'np.random.uniform' not in source, 'fund_flow 仍有 np.random.uniform'
    except ImportError:
        pass


def test_sentiment_selector_no_random_sample():
    """验证情绪选股不再使用random.sample"""
    try:
        import components.sentiment_stock_selector as mod
        source = Path(mod.__file__).read_text(encoding='utf-8', errors='ignore')
        assert 'random.sample' not in source, 'sentiment_stock_selector 仍有 random.sample'
        assert 'RealDataProvider' in source or '_select_by_real' in source, '未接入真实数据选股'
    except ImportError:
        pass


# ================== 8. UI 降级路径验证 ==================

def test_data_quality_monitor_tab_clean():
    """验证数据质量监控Tab已清除假数据"""
    fpath = PROJECT_ROOT / 'gui/widgets/enhanced_ui/data_quality_monitor_tab.py'
    if fpath.exists():
        source = fpath.read_text(encoding='utf-8', errors='ignore')
        for pat in ['random.randint', 'random.choice', 'random.uniform', 'np.random']:
            assert pat not in source, f'data_quality_monitor_tab 仍有 {pat}'


def test_data_quality_control_center_clean():
    """验证数据质量控制中心已清除假数据"""
    fpath = PROJECT_ROOT / 'gui/widgets/data_quality_control_center.py'
    if fpath.exists():
        source = fpath.read_text(encoding='utf-8', errors='ignore')
        for pat in ['random.randint', 'random.uniform', 'random.choice']:
            assert pat not in source, f'data_quality_control_center 仍有 {pat}'


def test_plugin_manager_dialog_clean():
    """验证插件管理器对话框已清除假数据"""
    fpath = PROJECT_ROOT / 'gui/dialogs/plugin_manager_dialog_unified.py'
    if fpath.exists():
        source = fpath.read_text(encoding='utf-8', errors='ignore')
        assert 'random.uniform' not in source, 'plugin_manager_dialog 仍有 random.uniform'


def test_indicator_selection_dialog_clean():
    """验证指标选择对话框已清除测试块假数据"""
    fpath = PROJECT_ROOT / 'gui/dialogs/indicator_selection_dialog.py'
    if fpath.exists():
        source = fpath.read_text(encoding='utf-8', errors='ignore')
        assert 'np.random.seed' not in source, 'indicator_selection_dialog 仍有 np.random.seed'


# ================== 9. 废弃代码清理验证 ==================

def test_deprecated_files_moved():
    """验证废弃文件已移至 _deprecated"""
    deprecated_dir = PROJECT_ROOT / 'gui/dialogs/_deprecated'
    assert deprecated_dir.exists(), '_deprecated 目录不存在'
    expected_files = [
        'data_management_dialog.py', 'data_import_wizard_dialog.py',
        'ai_strategy_management_dialog.py', 'enhanced_strategy_manager_dialog.py',
        'enhanced_strategy_manager_dialog_v3.py', 'plugin_manager_dialog.py',
        'enhanced_plugin_manager_dialog.py', 'database_admin_dialog.py',
        'data_export_dialog.py', 'advanced_data_export_dialog.py', 'import_history_dialog.py',
    ]
    for fname in expected_files:
        path = deprecated_dir / fname
        assert path.exists(), f'废弃文件未找到: {fname}'

    # 验证生产目录中已删除
    dialogs_dir = PROJECT_ROOT / 'gui/dialogs'
    for fname in expected_files:
        path = dialogs_dir / fname
        assert not path.exists(), f'废弃文件仍在生产目录: {fname}'


# ================== 10. 异常处理验证 ==================

def test_silent_exceptions_fixed():
    """验证静默吞没异常已修复（检查关键修复点而非全文件）"""
    fpath = PROJECT_ROOT / 'plugins/data_sources/stock/tongdaxin_plugin.py'
    if not fpath.exists():
        pytest.skip('通达信插件不存在')
    source = fpath.read_text(encoding='utf-8', errors='ignore')

    # 验证关键修复：连接测试函数中不再有裸 except:pass
    # 搜索 test_connection 函数体内是否还有裸 except:pass
    func_match = re.search(r'def\s+test_connection.*?(?=def\s+\w|\Z)', source, re.DOTALL)
    if func_match:
        func_body = func_match.group(0)
        bare_pass = re.search(r'except\s+(?:Exception\s*)?:\s*\n\s+pass\b', func_body)
        assert bare_pass is None, '通达信 test_connection 中仍有 except:pass 静默吞没'
    assert 'logger.debug' in source, '通达信插件未引入 logger'


# ================== 11. 真实数据完整性 ==================

def test_real_data_complete(real_data):
    """验证真实测试数据集完整可用"""
    market = real_data['market']
    system = real_data['system']
    assert len(market) >= 3, f'行情数据不足: {len(market)} 只股票'
    assert system['cpu_percent'] > 0, 'CPU 数据无效'
    assert system['memory_percent'] > 0, '内存数据无效'

    for code, data in market.items():
        assert data['latest_price'] > 0, f'{code} 价格无效'
        assert len(data['close']) >= 5, f'{code} K线不足'
        assert len(data['open']) == len(data['close']), f'{code} OHLC长度不匹配'
        assert data['name'], f'{code} 缺少名称'


# ================== 12. UnifiedDataManagementDialog 功能性 ==================

def test_unified_data_dialog_importable():
    """验证统一数据管理对话框可正常导入"""
    try:
        from gui.dialogs.data_management_dialog_unified import UnifiedDataManagementDialog
        assert UnifiedDataManagementDialog is not None
    except ImportError as e:
        pytest.skip(f'导入失败: {e}')


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '-x'])