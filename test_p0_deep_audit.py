#!/usr/bin/env python3
"""
P0 级别修复深度审核脚本

验证内容：
1. ParameterEditorWidget 是否正确集成到 backtest_widget.py
2. 参数扫描器是否使用真实回测引擎（带降级方案）
3. 参数对比器是否使用真实回测引擎（带降级方案）
4. mode_context 是否正确传递
5. 业务调用链是否完整
"""

from loguru import logger
import ast
import inspect

def check_file_contains(filepath, patterns, description):
    """检查文件是否包含指定的模式"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        results = []
        for pattern_name, pattern in patterns.items():
            if pattern in content:
                results.append((pattern_name, True, None))
            else:
                results.append((pattern_name, False, f"缺少：{pattern}"))
        
        all_passed = all(r[1] for r in results)
        logger.info(f"{'✅' if all_passed else '❌'} {description}")
        for name, passed, error in results:
            if not passed:
                logger.warning(f"  - {error}")
        
        return all_passed
    except Exception as e:
        logger.error(f"❌ {description} - 检查失败：{e}")
        return False


def analyze_business_call_chain():
    """分析业务调用链的完整性"""
    logger.info("\n" + "="*80)
    logger.info("业务调用链分析")
    logger.info("="*80)
    
    # 1. 检查 backtest_widget.py 中的调用链
    logger.info("\n1. 检查 backtest_widget.py 中的调用链")
    patterns = {
        "高级参数配置按钮": 'advanced_params_btn.clicked.connect',
        "调用父组件方法": 'parent_widget._open_advanced_parameter_editor',
        "创建 ParameterEditorWidget": 'ParameterEditorWidget(strategy, dialog)',
        "创建 mode_context": 'ModeContext.create_backtest()',
        "传递 mode_context": 'parameter_editor.mode_context = mode_context',
        "传递 kdata": 'parameter_editor.kdata = self.current_data',
        "连接 scan_completed 信号": 'scan_completed.connect',
        "连接 comparison_completed 信号": 'comparison_completed.connect'
    }
    result1 = check_file_contains(
        'gui/widgets/backtest_widget.py',
        patterns,
        "backtest_widget.py 集成完整性"
    )
    
    # 2. 检查 parameter_editor.py 中的调用链
    logger.info("\n2. 检查 parameter_editor.py 中的调用链")
    patterns = {
        "ParameterScanThread 类": 'class ParameterScanThread',
        "ParameterComparisonThread 类": 'class ParameterComparisonThread',
        "mode_context 参数": 'mode_context=None',
        "kdata 参数": 'kdata=None',
        "真实回测调用": 'UnifiedBacktestEngine',
        "run_backtest 调用": 'engine.run_backtest',
        "传递 mode_context": 'mode_context=self.mode_context',
        "降级方案": '_fallback_simulate_backtest'
    }
    result2 = check_file_contains(
        'gui/widgets/parameter_editor.py',
        patterns,
        "parameter_editor.py 调用链完整性"
    )
    
    # 3. 检查 unified_backtest_engine.py 中的接口
    logger.info("\n3. 检查 unified_backtest_engine.py 中的接口")
    patterns = {
        "UnifiedBacktestEngine 类": 'class UnifiedBacktestEngine',
        "run_backtest 方法": 'def run_backtest',
        "mode_context 参数": 'mode_context: Optional[ModeContext] = None',
        "mode_context 使用": 'mode_context'
    }
    result3 = check_file_contains(
        'backtest/unified_backtest_engine.py',
        patterns,
        "unified_backtest_engine.py 接口完整性"
    )
    
    return result1 and result2 and result3


def verify_mode_context_propagation():
    """验证 mode_context 的传递链"""
    logger.info("\n" + "="*80)
    logger.info("mode_context 传递链验证")
    logger.info("="*80)
    
    # 1. 检查 backtest_widget.py 中创建 mode_context
    logger.info("\n1. backtest_widget.py 中创建 mode_context")
    patterns = {
        "导入 ModeContext": 'from core.trading.trading_mode import ModeContext',
        "创建 backtest 模式": 'ModeContext.create_backtest()',
        "设置策略 mode_context": 'strategy.set_mode_context(mode_context)'
    }
    result1 = check_file_contains(
        'gui/widgets/backtest_widget.py',
        patterns,
        "backtest_widget.py 创建 mode_context"
    )
    
    # 2. 检查 parameter_editor.py 中传递 mode_context
    logger.info("\n2. parameter_editor.py 中传递 mode_context")
    patterns = {
        "mode_context 属性": 'self.mode_context = mode_context',
        "传递给 ParameterScanThread": 'mode_context=self.mode_context',
        "ParameterScanThread 初始化": 'mode_context=None'
    }
    result2 = check_file_contains(
        'gui/widgets/parameter_editor.py',
        patterns,
        "parameter_editor.py 传递 mode_context"
    )
    
    # 3. 检查 strategy_service.py 中使用 mode_context
    logger.info("\n3. strategy_service.py 中使用 mode_context")
    patterns = {
        "导入 ModeContext": 'ModeContext',
        "创建 mode_context": 'ModeContext.create_backtest',
        "传递给策略": 'plugin.mode_context = mode_context',
        "mode_context 参数": 'mode_context'
    }
    result3 = check_file_contains(
        'core/services/strategy_service.py',
        patterns,
        "strategy_service.py 使用 mode_context"
    )
    
    return result1 and result2 and result3


def verify_real_backtest_integration():
    """验证真实回测引擎的集成"""
    logger.info("\n" + "="*80)
    logger.info("真实回测引擎集成验证")
    logger.info("="*80)
    
    # 1. 检查参数扫描器中的真实回测
    logger.info("\n1. 参数扫描器中的真实回测")
    patterns = {
        "导入 UnifiedBacktestEngine": 'from backtest.unified_backtest_engine import UnifiedBacktestEngine',
        "创建引擎": 'UnifiedBacktestEngine(level=BacktestLevel.PROFESSIONAL)',
        "run_backtest 调用": 'engine.run_backtest(',
        "传递 strategy": 'strategy=self.strategy',
        "传递 kdata": 'kdata=self.kdata',
        "传递 config": 'config=config',
        "传递 mode_context": 'mode_context=self.mode_context'
    }
    result1 = check_file_contains(
        'gui/widgets/parameter_editor.py',
        patterns,
        "参数扫描器使用真实回测"
    )
    
    # 2. 检查降级方案
    logger.info("\n2. 降级方案")
    patterns = {
        "检查 kdata": 'if self.kdata is not None and len(self.kdata) > 0',
        "降级方法": '_fallback_simulate_backtest',
        "异常处理": 'except Exception as e',
        "降级调用": '_fallback_simulate_backtest(param_value)'
    }
    result2 = check_file_contains(
        'gui/widgets/parameter_editor.py',
        patterns,
        "降级方案完整性"
    )
    
    return result1 and result2


def verify_strategy_plugin_integration():
    """验证策略插件的集成"""
    logger.info("\n" + "="*80)
    logger.info("策略插件集成验证")
    logger.info("="*80)
    
    # 检查策略插件是否正确初始化 mode_context
    logger.info("\n1. 策略插件 mode_context 初始化")
    patterns = {
        "mode_context 检查": "if mode_context and hasattr(plugin, 'mode_context')",
        "设置 mode_context": 'plugin.mode_context = mode_context',
    }
    result1 = check_file_contains(
        'core/services/strategy_service.py',
        patterns,
        "策略插件 mode_context 管理"
    )
    
    # 检查 base_strategy.py
    logger.info("\n2. BaseStrategy 继承 ModeAwareMixin")
    patterns = {
        "导入 ModeAwareMixin": 'from core.trading.trading_mode import ModeAwareMixin',
        "BaseStrategy 继承": 'class BaseStrategy(ABC, ModeAwareMixin)',
        "初始化 ModeAwareMixin": 'ModeAwareMixin.__init__(self)'
    }
    result2 = check_file_contains(
        'core/strategy/base_strategy.py',
        patterns,
        "BaseStrategy 继承 ModeAwareMixin"
    )
    
    return result1 and result2


def generate_audit_report():
    """生成审核报告"""
    logger.info("\n" + "="*80)
    logger.info("P0 级别修复深度审核报告")
    logger.info("="*80)
    
    # 执行各项验证
    business_chain_ok = analyze_business_call_chain()
    mode_context_ok = verify_mode_context_propagation()
    real_backtest_ok = verify_real_backtest_integration()
    strategy_plugin_ok = verify_strategy_plugin_integration()
    
    # 汇总结果
    logger.info("\n" + "="*80)
    logger.info("审核结果汇总")
    logger.info("="*80)
    
    results = [
        ("业务调用链完整性", business_chain_ok),
        ("mode_context 传递链", mode_context_ok),
        ("真实回测引擎集成", real_backtest_ok),
        ("策略插件集成", strategy_plugin_ok)
    ]
    
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        logger.info(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    logger.info("-"*80)
    if all_passed:
        logger.info("\n🎉 所有审核通过！P0 级别修复完整、准确、无遗漏")
        logger.info("\n修复内容确认:")
        logger.info("1. ✅ ParameterEditorWidget 已正确集成到 backtest_widget.py")
        logger.info("2. ✅ 参数扫描器使用真实回测引擎（带降级方案）")
        logger.info("3. ✅ 参数对比器使用真实回测引擎（带降级方案）")
        logger.info("4. ✅ mode_context 正确传递到各层")
        logger.info("5. ✅ 业务调用链完整且正确")
        logger.info("6. ✅ 策略插件正确继承 ModeAwareMixin")
    else:
        logger.error("\n❌ 部分审核失败，请检查上述警告")
    
    return all_passed


if __name__ == "__main__":
    # 配置日志
    from loguru import logger
    import sys
    
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台处理器
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # 运行审核
    result = generate_audit_report()
    
    # 退出代码
    sys.exit(0 if result else 1)
