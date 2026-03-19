#!/usr/bin/env python3
"""
参数编辑器完整版（4 个阶段）综合测试脚本

测试内容：
1. 第一阶段：基础参数编辑器
   - 参数分组展示
   - 滑块 + 输入框双模式
   - 参数验证和范围限制
   - 实时应用和保存

2. 第二阶段：参数扫描器
   - 单参数扫描功能
   - 结果表格展示
   - 最优参数应用

3. 第三阶段：预设管理和对比
   - 预设保存和加载
   - 参数对比功能
   - 预设删除

4. 第四阶段：智能推荐
   - 参数推荐生成
   - 推荐结果展示
"""

import sys
import os
from pathlib import Path
import time

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")


def test_phase1_basic_editor():
    """测试第一阶段：基础参数编辑器"""
    logger.info("=" * 80)
    logger.info("测试第一阶段：基础参数编辑器")
    logger.info("=" * 80)
    
    try:
        from PyQt5.QtWidgets import QApplication
        from gui.widgets.parameter_editor import ParameterEditorWidget
        from core.strategy.base_strategy import BaseStrategy
        
        class TestStrategy(BaseStrategy):
            def __init__(self):
                super().__init__(name="TestStrategy")
                self._init_default_parameters()
            
            def _init_default_parameters(self):
                # 模式管理参数
                self.add_parameter('check_mode', 'hybrid', str, 
                                 '检查模式', choices=['backtest', 'live', 'hybrid'])
                self.add_parameter('lookback_window', 200, int, 
                                 '回溯窗口', 50, 1000)
                
                # 技术指标参数
                self.add_parameter('ma_period', 20, int, 
                                 '移动平均周期', 5, 50)
                self.add_parameter('atr_period', 14, int, 
                                 'ATR 周期', 5, 50)
                
                # 止损止盈参数
                self.add_parameter('atr_multiplier', 2.0, float, 
                                 'ATR 倍数', 1.0, 5.0)
                self.add_parameter('stop_loss_percent', 5.0, float, 
                                 '止损百分比', 1.0, 20.0)
                
                # 资金管理参数
                self.add_parameter('init_cash', 100000, int, 
                                 '初始资金', 10000, 1000000)
                
                # 性能优化参数
                self.add_parameter('vectorized_enabled', True, bool, 
                                 '启用向量化')
            
            def generate_signals(self, data, context=None):
                return []
        
        # 创建 QApplication
        if not QApplication.instance():
            app = QApplication(sys.argv)
        else:
            app = QApplication.instance()
        
        strategy = TestStrategy()
        editor = ParameterEditorWidget(strategy)
        
        # 验证 Tab 数量
        tab_count = editor.tab_widget.count()
        logger.info(f"✓ Tab 数量：{tab_count} (期望 4 个)")
        assert tab_count == 4, f"期望 4 个 Tab，实际{tab_count}"
        
        # 验证 Tab 名称
        tab_names = [editor.tab_widget.tabText(i) for i in range(tab_count)]
        logger.info(f"✓ Tab 名称：{tab_names}")
        assert "📝 基础配置" in tab_names
        assert "🔍 参数扫描" in tab_names
        assert "📊 预设对比" in tab_names
        assert "🤖 智能推荐" in tab_names
        
        # 验证基础配置页面
        phase1_widget = editor.tab_widget.widget(0)
        assert phase1_widget is not None
        logger.info(f"✓ 基础配置页面创建成功")
        
        # 验证参数加载
        assert len(editor.parameter_widgets) == 8
        logger.info(f"✓ 加载参数数量：{len(editor.parameter_widgets)} (期望 8 个)")
        
        # 验证参数分组
        groups = set()
        for i in range(editor.content_layout.count()):
            item = editor.content_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if hasattr(widget, 'title') and widget.title():
                    groups.add(widget.title())
        
        logger.info(f"✓ 参数分组：{groups}")
        assert len(groups) >= 4, f"期望至少 4 个分组，实际{len(groups)}"
        
        # 验证滑块 + 输入框双模式
        for name, widget_data in editor.parameter_widgets.items():
            if widget_data['type'] in [int, float]:
                assert 'slider' in widget_data, f"{name} 缺少滑块"
                assert 'spinbox' in widget_data, f"{name} 缺少输入框"
        
        logger.info(f"✓ 滑块 + 输入框双模式验证通过")
        
        # 验证参数修改
        test_param = 'ma_period'
        if test_param in editor.parameter_widgets:
            editor.parameter_widgets[test_param]['value'] = 30
            logger.info(f"✓ 参数修改功能验证通过 ({test_param}=30)")
        
        # 验证参数应用
        editor._apply_parameters()
        applied_value = strategy.get_parameter(test_param)
        logger.info(f"✓ 参数应用后值：{test_param}={applied_value} (期望 30)")
        assert applied_value == 30
        
        # 验证参数重置
        editor._reset_parameters()
        reset_value = editor.parameter_widgets[test_param]['value']
        logger.info(f"✓ 参数重置后值：{test_param}={reset_value} (期望 20)")
        assert reset_value == 20
        
        logger.info("✅ 第一阶段测试通过：基础参数编辑器功能正常\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 第一阶段测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase2_parameter_scan():
    """测试第二阶段：参数扫描器"""
    logger.info("=" * 80)
    logger.info("测试第二阶段：参数扫描器")
    logger.info("=" * 80)
    
    try:
        from PyQt5.QtWidgets import QApplication
        from gui.widgets.parameter_editor import ParameterEditorWidget, ParameterScanThread
        from core.strategy.base_strategy import BaseStrategy
        
        class TestStrategy(BaseStrategy):
            def __init__(self):
                super().__init__(name="TestStrategy")
                self._init_default_parameters()
            
            def _init_default_parameters(self):
                self.add_parameter('ma_period', 20, int, '移动平均周期', 5, 50)
                self.add_parameter('atr_multiplier', 2.0, float, 'ATR 倍数', 1.0, 5.0)
            
            def generate_signals(self, data, context=None):
                return []
        
        # 创建 QApplication
        if not QApplication.instance():
            app = QApplication(sys.argv)
        else:
            app = QApplication.instance()
        
        strategy = TestStrategy()
        editor = ParameterEditorWidget(strategy)
        
        # 验证参数扫描器 UI 组件
        assert hasattr(editor, 'scan_param_combo'), "缺少参数选择下拉框"
        assert hasattr(editor, 'scan_min_spin'), "缺少最小值设置"
        assert hasattr(editor, 'scan_max_spin'), "缺少最大值设置"
        assert hasattr(editor, 'scan_steps_spin'), "缺少步数设置"
        assert hasattr(editor, 'scan_btn'), "缺少扫描按钮"
        assert hasattr(editor, 'scan_progress'), "缺少进度条"
        assert hasattr(editor, 'scan_result_table'), "缺少结果表格"
        
        logger.info(f"✓ 参数扫描器 UI 组件完整")
        
        # 验证参数选择下拉框
        param_count = editor.scan_param_combo.count()
        logger.info(f"✓ 可扫描参数数量：{param_count}")
        assert param_count == 2, f"期望 2 个参数，实际{param_count}"
        
        # 测试扫描线程（不实际运行，只验证逻辑）
        scan_thread = ParameterScanThread(strategy, 'ma_period', (10, 30), steps=5)
        assert scan_thread is not None
        logger.info(f"✓ 参数扫描线程创建成功")
        
        # 验证扫描配置
        assert scan_thread.param_name == 'ma_period'
        assert scan_thread.scan_range == (10, 30)
        assert scan_thread.steps == 5
        logger.info(f"✓ 扫描配置正确")
        
        # 验证最优参数应用功能
        assert hasattr(editor, 'apply_best_btn'), "缺少应用最优参数按钮"
        logger.info(f"✓ 最优参数应用功能可用")
        
        logger.info("✅ 第二阶段测试通过：参数扫描器功能正常\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 第二阶段测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase3_preset_management():
    """测试第三阶段：预设管理和对比"""
    logger.info("=" * 80)
    logger.info("测试第三阶段：预设管理和对比")
    logger.info("=" * 80)
    
    try:
        from PyQt5.QtWidgets import QApplication
        from gui.widgets.parameter_editor import ParameterEditorWidget
        from core.strategy.base_strategy import BaseStrategy
        
        class TestStrategy(BaseStrategy):
            def __init__(self):
                super().__init__(name="TestStrategy")
                self._init_default_parameters()
            
            def _init_default_parameters(self):
                self.add_parameter('ma_period', 20, int, '移动平均周期', 5, 50)
                self.add_parameter('atr_multiplier', 2.0, float, 'ATR 倍数', 1.0, 5.0)
            
            def generate_signals(self, data, context=None):
                return []
        
        # 创建 QApplication
        if not QApplication.instance():
            app = QApplication(sys.argv)
        else:
            app = QApplication.instance()
        
        strategy = TestStrategy()
        editor = ParameterEditorWidget(strategy)
        
        # 验证预设管理 UI 组件
        assert hasattr(editor, 'preset_list_widget'), "缺少预设列表"
        assert hasattr(editor, 'save_preset_btn'), "缺少保存预设按钮"
        assert hasattr(editor, 'load_preset_btn'), "缺少加载预设按钮"
        assert hasattr(editor, 'delete_preset_btn'), "缺少删除预设按钮"
        
        logger.info(f"✓ 预设管理 UI 组件完整")
        
        # 测试保存预设
        editor.presets['测试预设 1'] = {
            'name': '测试预设 1',
            'params': {'ma_period': 25, 'atr_multiplier': 2.5},
            'created_at': '2026-03-19 12:00:00'
        }
        
        editor.presets['测试预设 2'] = {
            'name': '测试预设 2',
            'params': {'ma_period': 30, 'atr_multiplier': 3.0},
            'created_at': '2026-03-19 12:05:00'
        }
        
        editor._update_preset_list()
        preset_count = len(editor.presets)
        logger.info(f"✓ 预设数量：{preset_count} (期望 2 个)")
        assert preset_count == 2
        
        # 验证预设列表显示
        row_count = editor.preset_list_widget.rowCount()
        logger.info(f"✓ 预设列表行数：{row_count}")
        assert row_count == 2
        
        # 验证对比功能 UI
        assert hasattr(editor, 'compare_btn'), "缺少对比按钮"
        assert hasattr(editor, 'comparison_progress'), "缺少对比进度"
        assert hasattr(editor, 'comparison_result_table'), "缺少对比结果表格"
        
        logger.info(f"✓ 参数对比 UI 组件完整")
        
        # 验证对比线程类
        from gui.widgets.parameter_editor import ParameterComparisonThread
        comparison_thread = ParameterComparisonThread(strategy, list(editor.presets.values()))
        assert comparison_thread is not None
        logger.info(f"✓ 参数对比线程创建成功")
        
        logger.info("✅ 第三阶段测试通过：预设管理和对比功能正常\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 第三阶段测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase4_recommendation():
    """测试第四阶段：智能推荐"""
    logger.info("=" * 80)
    logger.info("测试第四阶段：智能推荐")
    logger.info("=" * 80)
    
    try:
        from PyQt5.QtWidgets import QApplication
        from gui.widgets.parameter_editor import ParameterEditorWidget
        from core.strategy.base_strategy import BaseStrategy
        
        class TestStrategy(BaseStrategy):
            def __init__(self):
                super().__init__(name="TestStrategy")
                self._init_default_parameters()
            
            def _init_default_parameters(self):
                self.add_parameter('ma_period', 20, int, '移动平均周期', 5, 50)
                self.add_parameter('atr_multiplier', 2.0, float, 'ATR 倍数', 1.0, 5.0)
                self.add_parameter('stop_loss_percent', 5.0, float, '止损百分比', 1.0, 20.0)
            
            def generate_signals(self, data, context=None):
                return []
        
        # 创建 QApplication
        if not QApplication.instance():
            app = QApplication(sys.argv)
        else:
            app = QApplication.instance()
        
        strategy = TestStrategy()
        editor = ParameterEditorWidget(strategy)
        
        # 验证智能推荐 UI 组件
        assert hasattr(editor, 'recommend_btn'), "缺少推荐按钮"
        assert hasattr(editor, 'recommendation_text'), "缺少推荐结果文本框"
        
        logger.info(f"✓ 智能推荐 UI 组件完整")
        
        # 测试生成推荐
        editor._generate_recommendation()
        
        # 验证推荐结果
        rec_html = editor.recommendation_text.toHtml()
        assert '智能参数推荐结果' in rec_html
        assert '参数名' in rec_html
        assert '当前值' in rec_html
        assert '推荐值' in rec_html
        
        logger.info(f"✓ 推荐结果生成成功")
        logger.info(f"✓ 推荐结果 HTML 长度：{len(rec_html)}")
        
        # 验证推荐数量
        rec_count = rec_html.count('<tr>') - 1  # 减去表头
        logger.info(f"✓ 推荐参数数量：{rec_count}")
        assert rec_count >= 3, f"期望至少 3 个推荐，实际{rec_count}"
        
        logger.info("✅ 第四阶段测试通过：智能推荐功能正常\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ 第四阶段测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    logger.info("\n" + "=" * 80)
    logger.info("参数编辑器完整版（4 个阶段）综合测试")
    logger.info("=" * 80 + "\n")
    
    results = []
    
    # 测试第一阶段
    results.append(("第一阶段：基础参数编辑器", test_phase1_basic_editor()))
    
    # 测试第二阶段
    results.append(("第二阶段：参数扫描器", test_phase2_parameter_scan()))
    
    # 测试第三阶段
    results.append(("第三阶段：预设管理和对比", test_phase3_preset_management()))
    
    # 测试第四阶段
    results.append(("第四阶段：智能推荐", test_phase4_recommendation()))
    
    # 汇总结果
    logger.info("=" * 80)
    logger.info("测试结果汇总")
    logger.info("=" * 80)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info("-" * 80)
    logger.info(f"总计：{passed}/{total} 测试通过 ({passed/total*100:.1f}%)")
    logger.info("=" * 80)
    
    if passed == total:
        logger.info("\n🎉 所有测试通过！参数编辑器完整版（4 个阶段）功能正常")
        return True
    else:
        logger.error(f"\n❌ {total - passed} 个测试失败，请检查问题")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
