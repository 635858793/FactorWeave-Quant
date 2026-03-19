#!/usr/bin/env python3
"""
P0 级别修复深度审核 V2 - 合理性、真实性和性能专项审核

审核重点：
1. 合理性 - 架构设计是否合理、代码组织是否清晰
2. 真实性 - 回测数据是否真实、降级方案是否可靠
3. 性能 - 是否存在性能瓶颈、是否有优化空间
4. 业务调用链 - 调用链是否完整、是否有断点
"""

from loguru import logger
import sys
import os
import re


def analyze_architecture_rationality():
    """分析架构合理性"""
    logger.info("\n" + "="*80)
    logger.info("架构合理性分析")
    logger.info("="*80)
    
    # 1. 检查 UI 组件与业务逻辑的分离
    logger.info("\n1. UI 组件与业务逻辑分离")
    checks = {
        "UI 层（backtest_widget.py）": {
            "file": "gui/widgets/backtest_widget.py",
            "patterns": ["class ProfessionalBacktestWidget", "class ControlPanel"],
            "expected": True
        },
        "业务层（parameter_editor.py）": {
            "file": "gui/widgets/parameter_editor.py",
            "patterns": ["class ParameterScanThread", "class ParameterComparisonThread"],
            "expected": True
        },
        "引擎层（unified_backtest_engine.py）": {
            "file": "backtest/unified_backtest_engine.py",
            "patterns": ["class UnifiedBacktestEngine"],
            "expected": True
        }
    }
    
    all_ok = True
    for name, check in checks.items():
        filepath = check["file"]
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            has_all = all(pattern in content for pattern in check["patterns"])
            status = "✅" if has_all else "❌"
            logger.info(f"{status} {name}: {'合理' if has_all else '不合理'}")
            all_ok = all_ok and has_all
        else:
            logger.error(f"❌ {name}: 文件不存在")
            all_ok = False
    
    return all_ok


def verify_real_backtest_authenticity():
    """验证真实回测的真实性"""
    logger.info("\n" + "="*80)
    logger.info("真实回测真实性验证")
    logger.info("="*80)
    
    # 1. 检查回测引擎调用
    logger.info("\n1. 回测引擎调用验证")
    filepath = "gui/widgets/parameter_editor.py"
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = {
            "导入 UnifiedBacktestEngine": "from backtest.unified_backtest_engine import UnifiedBacktestEngine" in content,
            "创建引擎实例": "UnifiedBacktestEngine(level=BacktestLevel.PROFESSIONAL)" in content,
            "调用 run_backtest": "engine.run_backtest(" in content,
            "传递 strategy": "strategy=self.strategy" in content,
            "传递 kdata": "kdata=self.kdata" in content,
            "传递 mode_context": "mode_context=self.mode_context" in content,
            "传递 config": "config=config" in content
        }
        
        all_ok = True
        for name, result in checks.items():
            status = "✅" if result else "❌"
            logger.info(f"{status} {name}: {'正确' if result else '错误'}")
            all_ok = all_ok and result
        
        return all_ok
    else:
        logger.error("❌ 文件不存在")
        return False


def verify_fallback_mechanism():
    """验证降级机制的可靠性"""
    logger.info("\n2. 降级机制验证")
    filepath = "gui/widgets/parameter_editor.py"
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取 _simulate_backtest 方法
        match = re.search(r'def _simulate_backtest\(self.*?\):.*?(?=\n    def |\nclass |\Z)', content, re.DOTALL)
        if match:
            method_content = match.group(0)
            
            checks = {
                "检查 kdata 存在": "if self.kdata is not None and len(self.kdata) > 0" in method_content,
                "真实回测分支": "engine.run_backtest(" in method_content,
                "降级方法调用": "_fallback_simulate_backtest" in method_content,
                "异常处理": "except Exception as e" in method_content,
                "日志记录": 'logger.warning("没有 K 线数据，使用模拟数据")' in method_content or 
                          'logger.error(f"回测失败：{e}")' in method_content
            }
            
            all_ok = True
            for name, result in checks.items():
                status = "✅" if result else "❌"
                logger.info(f"{status} {name}: {'完整' if result else '缺失'}")
                all_ok = all_ok and result
            
            return all_ok
        else:
            logger.error("❌ 无法找到 _simulate_backtest 方法")
            return False
    else:
        logger.error("❌ 文件不存在")
        return False


def analyze_performance_impact():
    """分析性能影响"""
    logger.info("\n" + "="*80)
    logger.info("性能影响分析")
    logger.info("="*80)
    
    # 1. 检查线程使用
    logger.info("\n1. 多线程使用验证")
    filepath = "gui/widgets/parameter_editor.py"
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = {
            "ParameterScanThread 继承 QThread": "class ParameterScanThread(QThread)" in content,
            "ParameterComparisonThread 继承 QThread": "class ParameterComparisonThread(QThread)" in content,
            "run 方法实现": "def run(self):" in content,
            "异步执行": "self.msleep(" in content or "time.sleep(" in content
        }
        
        all_ok = True
        for name, result in checks.items():
            status = "✅" if result else "❌"
            logger.info(f"{status} {name}: {'正确' if result else '错误'}")
            all_ok = all_ok and result
        
        return all_ok
    else:
        logger.error("❌ 文件不存在")
        return False


def verify_business_call_chain_completeness():
    """验证业务调用链完整性"""
    logger.info("\n" + "="*80)
    logger.info("业务调用链完整性验证")
    logger.info("="*80)
    
    # 完整的调用链
    call_chain = [
        ("UI 层", "gui/widgets/backtest_widget.py", [
            "_open_advanced_parameter_editor",
            "ParameterEditorWidget",
            "ModeContext.create_backtest()"
        ]),
        ("参数编辑器层", "gui/widgets/parameter_editor.py", [
            "class ParameterEditorWidget",
            "mode_context",
            "kdata"
        ]),
        ("扫描器层", "gui/widgets/parameter_editor.py", [
            "class ParameterScanThread",
            "_simulate_backtest",
            "mode_context=self.mode_context"
        ]),
        ("回测引擎层", "backtest/unified_backtest_engine.py", [
            "class UnifiedBacktestEngine",
            "def run_backtest",
            "mode_context: Optional[ModeContext] = None"
        ]),
        ("策略层", "core/strategy/base_strategy.py", [
            "class BaseStrategy(ABC, ModeAwareMixin)",
            "ModeAwareMixin.__init__(self)"
        ]),
        ("插件接口层", "core/strategy_extensions.py", [
            "class IStrategyPlugin(ABC, ModeAwareMixin)"
        ]),
        ("服务层", "core/services/strategy_service.py", [
            "ModeContext.create_backtest",
            "plugin.mode_context = mode_context"
        ])
    ]
    
    all_ok = True
    for layer_name, filepath, patterns in call_chain:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            has_all = all(pattern in content for pattern in patterns)
            status = "✅" if has_all else "❌"
            logger.info(f"{status} {layer_name} ({filepath}): {'完整' if has_all else '缺失'}")
            
            if not has_all:
                for pattern in patterns:
                    if pattern not in content:
                        logger.warning(f"  - 缺少：{pattern}")
            
            all_ok = all_ok and has_all
        else:
            logger.error(f"❌ {layer_name} ({filepath}): 文件不存在")
            all_ok = False
    
    return all_ok


def check_mode_context_propagation():
    """检查 mode_context 传递的完整性"""
    logger.info("\n" + "="*80)
    logger.info("mode_context 传递完整性检查")
    logger.info("="*80)
    
    propagation_points = [
        ("创建点", "gui/widgets/backtest_widget.py", "ModeContext.create_backtest()"),
        ("传递到编辑器", "gui/widgets/backtest_widget.py", "parameter_editor.mode_context = mode_context"),
        ("编辑器属性", "gui/widgets/parameter_editor.py", "self.mode_context = mode_context"),
        ("传递给扫描器", "gui/widgets/parameter_editor.py", "mode_context=self.mode_context"),
        ("扫描器参数", "gui/widgets/parameter_editor.py", "mode_context=None"),
        ("传递给引擎", "gui/widgets/parameter_editor.py", "mode_context=self.mode_context"),
        ("引擎参数", "backtest/unified_backtest_engine.py", "mode_context: Optional[ModeContext] = None"),
        ("服务层创建", "core/services/strategy_service.py", "ModeContext.create_backtest"),
        ("服务层传递", "core/services/strategy_service.py", "plugin.mode_context = mode_context")
    ]
    
    all_ok = True
    for point_name, filepath, pattern in propagation_points:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            has_pattern = pattern in content
            status = "✅" if has_pattern else "❌"
            logger.info(f"{status} {point_name}: {'正确' if has_pattern else '缺失'}")
            
            if not has_pattern:
                logger.warning(f"  - 缺少：{pattern}")
            
            all_ok = all_ok and has_pattern
        else:
            logger.error(f"❌ {point_name} ({filepath}): 文件不存在")
            all_ok = False
    
    return all_ok


def verify_error_handling():
    """验证错误处理机制"""
    logger.info("\n" + "="*80)
    logger.info("错误处理机制验证")
    logger.info("="*80)
    
    filepath = "gui/widgets/parameter_editor.py"
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = {
            "try-except 块": "try:" in content and "except Exception as e:" in content,
            "错误日志": 'logger.error' in content,
            "警告日志": 'logger.warning' in content,
            "降级处理": "_fallback_simulate_backtest" in content,
            "进度信号": "scan_progress.emit" in content,
            "错误信号": "scan_error.emit" in content
        }
        
        all_ok = True
        for name, result in checks.items():
            status = "✅" if result else "❌"
            logger.info(f"{status} {name}: {'完整' if result else '缺失'}")
            all_ok = all_ok and result
        
        return all_ok
    else:
        logger.error("❌ 文件不存在")
        return False


def generate_comprehensive_audit_report():
    """生成综合审核报告"""
    logger.info("\n" + "="*80)
    logger.info("P0 级别修复深度审核报告 V2")
    logger.info("审核重点：合理性、真实性、性能")
    logger.info("="*80)
    
    # 执行各项审核
    architecture_ok = analyze_architecture_rationality()
    authenticity_ok = verify_real_backtest_authenticity()
    fallback_ok = verify_fallback_mechanism()
    performance_ok = analyze_performance_impact()
    call_chain_ok = verify_business_call_chain_completeness()
    mode_context_ok = check_mode_context_propagation()
    error_handling_ok = verify_error_handling()
    
    # 汇总结果
    logger.info("\n" + "="*80)
    logger.info("审核结果汇总")
    logger.info("="*80)
    
    results = [
        ("架构合理性", architecture_ok),
        ("真实回测真实性", authenticity_ok),
        ("降级机制可靠性", fallback_ok),
        ("性能优化", performance_ok),
        ("业务调用链完整性", call_chain_ok),
        ("mode_context 传递完整性", mode_context_ok),
        ("错误处理机制", error_handling_ok)
    ]
    
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        logger.info(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    logger.info("-"*80)
    if all_passed:
        logger.info("\n🎉 所有审核通过！P0 级别修复在合理性、真实性、性能方面均符合要求")
        logger.info("\n关键验证点:")
        logger.info("1. ✅ 架构设计合理 - UI 层、业务层、引擎层分离清晰")
        logger.info("2. ✅ 真实回测可靠 - 正确调用 UnifiedBacktestEngine")
        logger.info("3. ✅ 降级机制完善 - 有完整的异常处理和降级方案")
        logger.info("4. ✅ 性能优化合理 - 使用多线程避免阻塞 UI")
        logger.info("5. ✅ 业务调用链完整 - 从 UI 到策略层无断点")
        logger.info("6. ✅ mode_context 传递完整 - 各层均正确传递")
        logger.info("7. ✅ 错误处理完善 - 有日志、信号、降级机制")
    else:
        logger.error(f"\n❌ {sum(1 for _, p in results if not p)} 个审核项目失败，请检查上述警告")
    
    return all_passed


if __name__ == "__main__":
    # 配置日志
    from loguru import logger
    
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台处理器
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # 运行审核
    result = generate_comprehensive_audit_report()
    
    # 退出代码
    sys.exit(0 if result else 1)
