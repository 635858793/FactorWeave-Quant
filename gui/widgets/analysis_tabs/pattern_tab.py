import traceback
from loguru import logger
"""
形态分析标签页 - 专业版升级
"""
import json
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Optional
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QColor, QKeySequence
from .pattern_tab_pro import PatternAnalysisTabPro


class PatternAnalysisTab(PatternAnalysisTabPro):
    """形态分析标签页 - 继承专业版功能，保持向后兼容"""

    def __init__(self, config_manager=None, event_bus=None):
        """初始化形态分析标签页"""
        super().__init__(config_manager, event_bus=event_bus)

        # 保持向后兼容的属性
        self._all_pattern_signals = []

        # 连接信号以保持兼容性
        self.analysis_completed.connect(self._on_analysis_completed)

    def _on_analysis_completed(self, results):
        """分析完成处理 - 兼容原有接口"""
        try:
            self.hide_loading()
            self.status_label.setText("分析完成")

            if 'error' in results:
                self.error_occurred.emit(results['error'])
                return

            # 更新显示
            self._update_results_display(results)

            # 发射兼容信号
            if 'patterns' in results:
                for i, pattern in enumerate(results['patterns']):
                    self.pattern_selected.emit(i)

        except Exception as e:
            logger.error(f"分析完成处理失败: {e}")

    # 保持向后兼容的方法
    def identify_patterns(self):
        """识别形态 - 兼容原接口"""
        self.one_click_analysis()

    def auto_identify_patterns(self):
        """自动识别形态 - 兼容原接口"""
        self.one_click_analysis()

    def clear_patterns(self):
        """清除形态 - 兼容原接口"""
        self.patterns_table.setRowCount(0)
        self.prediction_text.clear()
        self.stats_text.clear()
        self.backtest_text.clear()
        self._all_pattern_signals.clear()

    def refresh_data(self):
        """刷新数据 - 兼容原接口"""
        self._do_refresh_data()

    def clear_data(self):
        """清除数据 - 兼容原接口"""
        self.clear_patterns()

    # 原有的兼容方法
    def apply_confidence_preset(self, preset_text):
        """应用置信度预设"""
        presets = {
            "高置信度(0.8+)": 0.8,
            "中置信度(0.5+)": 0.5,
            "低置信度(0.3+)": 0.3,
            "全部(0.0+)": 0.0
        }
        if preset_text in presets:
            self.min_confidence.setValue(presets[preset_text])

    def apply_time_preset(self, preset_text):
        """应用时间预设"""
        # 这里可以根据需要实现时间范围设置
        pass

    def toggle_auto_refresh(self, state):
        """切换自动刷新"""
        self.realtime_cb.setChecked(state == Qt.Checked)

    def apply_pattern_filter(self):
        """应用形态筛选"""
        # 重新执行分析以应用筛选条件
        if self.current_kdata is not None:
            self.one_click_analysis()

    def show_pattern_config_dialog(self):
        """显示形态配置对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("形态识别配置")
        dialog.setModal(True)
        dialog.resize(500, 400)

        layout = QVBoxLayout(dialog)

        # 基本设置
        basic_group = QGroupBox("基本设置")
        basic_layout = QFormLayout(basic_group)

        # 灵敏度设置
        sensitivity_slider = QSlider(Qt.Horizontal)
        sensitivity_slider.setRange(1, 10)
        sensitivity_slider.setValue(self.sensitivity_slider.value())
        basic_layout.addRow("识别灵敏度:", sensitivity_slider)

        # 最小置信度
        min_conf_spin = QDoubleSpinBox()
        min_conf_spin.setRange(0.0, 1.0)
        min_conf_spin.setSingleStep(0.1)
        min_conf_spin.setValue(self.min_confidence.value())
        basic_layout.addRow("最小置信度:", min_conf_spin)

        layout.addWidget(basic_group)

        # 高级设置
        advanced_group = QGroupBox("高级设置")
        advanced_layout = QVBoxLayout(advanced_group)

        ml_cb = QCheckBox("启用机器学习预测")
        ml_cb.setChecked(self.enable_ml_cb.isChecked())
        advanced_layout.addWidget(ml_cb)

        alerts_cb = QCheckBox("启用形态预警")
        alerts_cb.setChecked(self.enable_alerts_cb.isChecked())
        advanced_layout.addWidget(alerts_cb)

        layout.addWidget(advanced_group)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec_() == QDialog.Accepted:
            # 应用设置
            self.sensitivity_slider.setValue(sensitivity_slider.value())
            self.min_confidence.setValue(min_conf_spin.value())
            self.enable_ml_cb.setChecked(ml_cb.isChecked())
            self.enable_alerts_cb.setChecked(alerts_cb.isChecked())

    def show_pattern_statistics_dialog(self):
        """显示形态统计对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("形态统计分析")
        dialog.setModal(True)
        dialog.resize(600, 500)

        layout = QVBoxLayout(dialog)

        # 统计文本
        stats_text = QTextEdit()
        stats_text.setReadOnly(True)
        stats_text.setText(self.stats_text.toPlainText())
        layout.addWidget(stats_text)

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec_()

    def export_pattern_results(self):
        """导出形态结果"""
        self.export_patterns()

    def _on_pattern_table_selection_changed(self):
        """形态表格选择变化"""
        current_row = self.patterns_table.currentRow()
        if current_row >= 0:
            self.pattern_selected.emit(current_row)

    def show_pattern_context_menu(self, position):
        """显示形态右键菜单"""
        if self.patterns_table.itemAt(position) is None:
            return

        menu = QMenu(self)

        # 查看详情
        detail_action = menu.addAction("查看详情")
        detail_action.triggered.connect(self.show_pattern_detail)

        # 导出选中
        export_action = menu.addAction("导出选中")
        export_action.triggered.connect(self.export_selected_pattern)

        menu.exec_(self.patterns_table.mapToGlobal(position))

    def show_pattern_detail(self):
        """显示形态详情"""
        current_row = self.patterns_table.currentRow()
        if current_row < 0:
            return

        # 获取选中形态信息
        pattern_name = self.patterns_table.item(current_row, 0).text()
        confidence = self.patterns_table.item(current_row, 2).text()
        success_rate = self.patterns_table.item(current_row, 3).text()

        detail_dialog = QDialog(self)
        detail_dialog.setWindowTitle(f"形态详情 - {pattern_name}")
        detail_dialog.setModal(True)
        detail_dialog.resize(500, 400)

        layout = QVBoxLayout(detail_dialog)

        # 详情文本
        detail_text = QTextEdit()
        detail_text.setReadOnly(True)
        detail_text.setText(f"""
形态名称: {pattern_name}
置信度: {confidence}
历史成功率: {success_rate}

形态描述:
{self._get_pattern_description(pattern_name)}

操作建议:
{self._get_pattern_advice(pattern_name)}
        """)
        layout.addWidget(detail_text)

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(detail_dialog.accept)
        layout.addWidget(close_btn)

        detail_dialog.exec_()

    def _get_pattern_description(self, pattern_name):
        """获取形态描述"""
        descriptions = {
            '头肩顶': '头肩顶是一种经典的反转形态，由三个峰组成，中间的峰最高，两边的峰相对较低且大致等高。',
            '头肩底': '头肩底是头肩顶的倒置形态，是一种看涨的反转信号。',
            '双顶': '双顶形态由两个相近的高点组成，是一种看跌的反转信号。',
            '双底': '双底形态由两个相近的低点组成，是一种看涨的反转信号。',
            # 可以添加更多形态描述
        }
        return descriptions.get(pattern_name, '暂无详细描述')

    def _get_pattern_advice(self, pattern_name):
        """获取形态建议"""
        if '顶' in pattern_name:
            return '建议逢高减仓，注意风险控制。'
        elif '底' in pattern_name:
            return '可考虑逢低建仓，但需确认突破有效性。'
        else:
            return '密切关注后续走势，等待明确信号。'

    def export_selected_pattern(self):
        """导出选中形态"""
        current_row = self.patterns_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "请先选择要导出的形态")
            return

        # 实现导出逻辑
        QMessageBox.information(self, "提示", "导出功能开发中...")

    def export_patterns(self):
        """导出形态 - 实现基本导出功能"""
        if self.patterns_table.rowCount() == 0:
            QMessageBox.warning(self, "警告", "没有可导出的形态数据")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "导出形态分析结果",
            f"pattern_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON files (*.json)"
        )

        if filename:
            try:
                # 收集表格数据
                patterns_data = []
                for row in range(self.patterns_table.rowCount()):
                    pattern = {}
                    headers = ['形态名称', '类型', '置信度', '成功率', '风险等级',
                               '开始时间', '结束时间', '价格变化', '预期目标', '操作建议']

                    for col, header in enumerate(headers):
                        item = self.patterns_table.item(row, col)
                        pattern[header] = item.text() if item else ""

                    patterns_data.append(pattern)

                # 导出数据
                export_data = {
                    'export_time': datetime.now().isoformat(),
                    'data_type': '形态分析',
                    'total_patterns': len(patterns_data),
                    'patterns': patterns_data
                }

                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)

                QMessageBox.information(self, "成功", f"形态分析结果已导出到: {filename}")

            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

    def start_prediction(self):
        """开始预测 - 兼容接口"""
        self.ai_prediction()

    def start_backtest(self):
        """开始回测 - 增强版错误处理"""
        try:
            logger.info("用户点击开始回测按钮")

            # 验证K线数据
            if not self.validate_kdata_with_warning():
                error_msg = "请先加载有效的K线数据"
                logger.warning(f" 回测失败: {error_msg}")
                return

            # 检查回测周期设置
            if not hasattr(self, 'backtest_period'):
                error_msg = "回测周期设置组件未找到，请重新初始化界面"
                logger.error(f" {error_msg}")
                QMessageBox.critical(self, "错误", error_msg)
                return

            period = self.backtest_period.value()
            logger.info(f" K线数据验证通过，开始{period}天回测")

            # 检查是否已有形态数据
            patterns = self._get_real_patterns()
            if not patterns:
                QMessageBox.warning(self, "提示", "未找到形态数据，请先执行形态识别")
                return

            logger.info(f" 形态数据准备完成，将回测 {len(patterns)} 个形态")

            # 检查并清理旧的回测线程
            if hasattr(self, '_backtest_worker') and self._backtest_worker is not None:
                if self._backtest_worker.isRunning():
                    logger.warning("检测到正在运行的回测线程，正在停止...")
                    self._backtest_worker.quit()
                    self._backtest_worker.wait(3000)
                self._backtest_worker.deleteLater()

            # 创建异步回测工作线程
            from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker

            class BacktestWorker(QThread):
                """回测工作线程"""
                backtest_completed = pyqtSignal(dict)
                backtest_error = pyqtSignal(str)

                def __init__(self, parent_tab, patterns, period):
                    super().__init__()
                    self.parent_tab = parent_tab
                    self.patterns = patterns
                    self.period = period
                    self._mutex = QMutex()

                def run(self):
                    """在后台线程执行回测"""
                    try:
                        with QMutexLocker(self._mutex):
                            logger.info("=== 异步回测线程开始执行 ===")

                            # 第一步：基于形态生成交易信号
                            logger.info("开始生成交易信号...")
                            signal_data = self.parent_tab._generate_trading_signals_from_patterns(self.patterns, self.period)
                            if signal_data is None or signal_data.empty:
                                self.backtest_error.emit('无法生成有效的交易信号')
                                return

                            # 第二步：使用专业回测引擎
                            logger.info("启动专业回测引擎...")
                            from backtest.unified_backtest_engine import UnifiedBacktestEngine, BacktestLevel

                            engine = UnifiedBacktestEngine(backtest_level=BacktestLevel.PROFESSIONAL)

                            # 运行回测
                            backtest_results = engine.run_backtest(
                                data=signal_data,
                                signal_col='signal',
                                price_col='close',
                                initial_capital=100000,
                                position_size=0.8,
                                commission_pct=0.0003,
                                slippage_pct=0.001
                            )

                            # 提取关键指标
                            risk_metrics = backtest_results.get('risk_metrics', {})
                            performance_summary = backtest_results.get('performance_summary', {})

                            # 统计形态效果
                            pattern_stats = self.parent_tab._calculate_pattern_effectiveness(self.patterns, signal_data)

                            # 构建标准化回测结果
                            final_results = {
                                'period': self.period,
                                'total_signals': len([p for p in self.patterns if p.get('signal_type') != 'neutral']),
                                'successful_signals': pattern_stats.get('successful_count', 0),
                                'success_rate': pattern_stats.get('success_rate', 0.0),
                                'avg_return': risk_metrics.get('总收益率', 0.0),
                                'max_drawdown': abs(risk_metrics.get('最大回撤', 0.0)),
                                'sharpe_ratio': risk_metrics.get('夏普比率', 0.0),
                                'total_patterns': len(self.patterns),
                                'pattern_breakdown': pattern_stats.get('pattern_breakdown', {}),
                                'generated_time': datetime.now().isoformat(),
                                'backtest_method': 'professional_engine',
                                'data_quality': 'real_pattern_recognition'
                            }

                            # 保存回测结果到 BacktestResultManager
                            try:
                                from core.services.backtest_result_manager import BacktestResult
                                import time

                                backtest_result = BacktestResult(
                                    stock_code=getattr(self.parent_tab, 'stock_code', ''),
                                    stock_name=getattr(self.parent_tab, 'stock_name', ''),
                                    strategy_name='形态识别策略',
                                    backtest_time=time.time(),
                                    backtest_results=final_results,
                                    trades=backtest_results.get('trades', []),
                                    duration=backtest_results.get('duration', 0),
                                    is_professional=True
                                )

                                if hasattr(self.parent_tab, 'backtest_result_manager'):
                                    self.parent_tab.backtest_result_manager.add_result(backtest_result)
                                    logger.info(f"回测结果已保存到 BacktestResultManager")

                            except Exception as save_error:
                                logger.warning(f"保存回测结果失败: {save_error}")

                            logger.info("=== 异步回测线程执行完成 ===")

                            # 发送结果
                            self.backtest_completed.emit(final_results)

                    except Exception as e:
                        logger.error(f"回测执行失败: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        self.backtest_error.emit(str(e))

            # 显示加载状态
            self.show_loading("正在执行历史回测...")

            # 创建并启动工作线程
            self._backtest_worker = BacktestWorker(self, patterns, period)
            self._backtest_worker.backtest_completed.connect(self._on_backtest_completed)
            self._backtest_worker.backtest_error.connect(self._on_backtest_error)

            logger.info("异步回测已启动")

        except Exception as e:
            error_msg = f"启动回测失败: {str(e)}"
            logger.error(f" {error_msg}")
            import traceback
            logger.error(traceback.format_exc())

            # 隐藏加载状态
            self.hide_loading()
            QMessageBox.critical(self, "错误", error_msg)

    def _backtest_async(self):
        """异步回测 - 基于真实形态识别的专业回测"""
        try:
            # 记录异步执行开始
            if True:  # 使用Loguru日志
                logger.info("=== 异步回测线程开始执行 ===")
            else:
                logger.info("[Pattern]  === 异步回测线程开始执行 ===")

            # 获取回测参数
            period = self.backtest_period.value()
            if True:  # 使用Loguru日志
                logger.info(f" 回测周期: {period}天")

            # 第一步：获取真实形态识别结果
            if True:  # 使用Loguru日志
                logger.info("开始真实形态识别...")

            patterns = self._get_real_patterns()
            if not patterns:
                return {'error': '未发现任何形态，无法进行回测'}

            if True:  # 使用Loguru日志
                logger.info(f" 发现 {len(patterns)} 个形态")

            # 第二步：基于形态生成交易信号
            if True:  # 使用Loguru日志
                logger.info("开始生成交易信号...")

            signal_data = self._generate_trading_signals_from_patterns(patterns, period)
            if signal_data is None or signal_data.empty:
                return {'error': '无法生成有效的交易信号'}

            # 第三步：使用专业回测引擎
            if True:  # 使用Loguru日志
                logger.info("启动专业回测引擎...")

            try:
                from backtest.unified_backtest_engine import UnifiedBacktestEngine, BacktestLevel

                # 创建专业级回测引擎
                engine = UnifiedBacktestEngine(backtest_level=BacktestLevel.PROFESSIONAL)

                # 运行回测
                backtest_results = engine.run_backtest(
                    data=signal_data,
                    signal_col='signal',
                    price_col='close',
                    initial_capital=100000,
                    position_size=0.8,
                    commission_pct=0.0003,
                    slippage_pct=0.001
                )

                # 提取关键指标
                risk_metrics = backtest_results.get('risk_metrics', {})
                performance_summary = backtest_results.get('performance_summary', {})

                # 统计形态效果
                pattern_stats = self._calculate_pattern_effectiveness(patterns, signal_data)

                # 构建标准化回测结果
                final_results = {
                    'period': period,
                    'total_signals': len([p for p in patterns if p.get('signal_type') != 'neutral']),
                    'successful_signals': pattern_stats.get('successful_count', 0),
                    'success_rate': pattern_stats.get('success_rate', 0.0),
                    'avg_return': risk_metrics.get('总收益率', 0.0),
                    'max_drawdown': abs(risk_metrics.get('最大回撤', 0.0)),
                    'sharpe_ratio': risk_metrics.get('夏普比率', 0.0),
                    'total_patterns': len(patterns),
                    'pattern_breakdown': pattern_stats.get('pattern_breakdown', {}),
                    'generated_time': datetime.now().isoformat(),
                    'backtest_method': 'professional_engine',
                    'data_quality': 'real_pattern_recognition'
                }

                # 保存回测结果到 BacktestResultManager
                try:
                    from core.services.backtest_result_manager import BacktestResult
                    import time
                    
                    backtest_result = BacktestResult(
                        stock_code=getattr(self, 'stock_code', ''),
                        stock_name=getattr(self, 'stock_name', ''),
                        strategy_name='形态识别策略',
                        backtest_time=time.time(),
                        backtest_results=final_results,
                        trades=backtest_results.get('trades', []),
                        duration=backtest_results.get('duration', 0),
                        is_professional=True
                    )
                    
                    if hasattr(self, 'backtest_result_manager'):
                        self.backtest_result_manager.add_result(backtest_result)
                        logger.info(f"回测结果已保存到 BacktestResultManager")
                except Exception as save_error:
                    logger.warning(f"保存回测结果失败: {save_error}")

                if True:  # 使用Loguru日志
                    logger.info(f" 专业回测完成: {final_results['total_signals']}个信号，成功率{final_results['success_rate']:.2%}")

                return {'backtest': final_results}

            except ImportError as e:
                if True:  # 使用Loguru日志
                    logger.warning(f" 专业回测引擎不可用，使用简化回测: {e}")

                # 降级到简化回测
                simplified_results = self._run_simplified_backtest(patterns, signal_data, period)
                return {'backtest': simplified_results}

        except Exception as e:
            error_msg = f"异步回测执行失败: {str(e)}"
            if True:  # 使用Loguru日志
                logger.error(f" {error_msg}")
                logger.error(traceback.format_exc())
            else:
                logger.info(f"[Pattern]  {error_msg}")

            return {'error': error_msg}

    def _get_real_patterns(self):
        """获取真实形态识别结果"""
        try:
            # 检查是否已有分析结果
            if hasattr(self, 'analysis_results') and self.analysis_results:
                patterns = self.analysis_results.get('patterns', [])
                if patterns:
                    logger.info(f"使用已保存的分析结果，形态数量: {len(patterns)}")
                    return patterns

            # 尝试从表格获取
            if hasattr(self, 'patterns_table') and self.patterns_table.rowCount() > 0:
                patterns = self._extract_patterns_from_table()
                if patterns:
                    logger.info(f"从表格提取形态数据，数量: {len(patterns)}")
                    return patterns

            # 优化：不再在主线程执行实时形态识别
            # 如果没有形态数据，返回空列表，提示用户先执行形态识别
            logger.warning("未找到形态数据，请先执行形态识别")
            return []

        except Exception as e:
            logger.error(f" 获取真实形态失败: {e}")
            return []

    def _generate_trading_signals_from_patterns(self, patterns, period):
        """基于形态生成交易信号"""
        try:
            if not patterns:
                return None

            # 获取最近period天的数据
            if len(self.current_kdata) > period:
                data = self.current_kdata.tail(period).copy()
            else:
                data = self.current_kdata.copy()

            # 初始化信号列
            data['signal'] = 0

            # 保存原始数据的索引，用于索引映射
            original_indices = self.current_kdata.index.tolist()
            truncated_indices = data.index.tolist()

            # 创建索引映射：原始索引 -> 截断后索引
            index_mapping = {orig_idx: trunc_idx for trunc_idx, orig_idx in enumerate(truncated_indices)}

            # 为每个形态生成信号
            for pattern in patterns:
                try:
                    # 获取形态信息
                    signal_type = pattern.get('signal_type', 'neutral')
                    confidence = pattern.get('confidence', 0.0)
                    pattern_index = pattern.get('index', 0)

                    # 转换信号类型
                    if signal_type.lower() in ['buy', 'bullish', '买入']:
                        signal_value = 1
                    elif signal_type.lower() in ['sell', 'bearish', '卖出']:
                        signal_value = -1
                    else:
                        signal_value = 0

                    # 基于置信度调整信号强度
                    if confidence >= 0.7:
                        signal_value *= 1.0  # 高置信度
                    elif confidence >= 0.5:
                        signal_value *= 0.8  # 中置信度
                    else:
                        signal_value *= 0.6  # 低置信度

                    # 应用信号到相应位置（使用索引映射）
                    if pattern_index in index_mapping:
                        mapped_index = index_mapping[pattern_index]
                        if 0 <= mapped_index < len(data):
                            data.iloc[mapped_index, data.columns.get_loc('signal')] = signal_value

                except Exception as e:
                    if True:  # 使用Loguru日志
                        logger.warning(f" 处理形态信号失败: {e}")
                    continue

            if True:  # 使用Loguru日志
                signal_count = len(data[data['signal'] != 0])
                logger.info(f" 生成 {signal_count} 个交易信号")

            return data

        except Exception as e:
            if True:  # 使用Loguru日志
                logger.error(f" 生成交易信号失败: {e}")
            return None

    def _calculate_pattern_effectiveness(self, patterns, signal_data):
        """计算形态有效性统计 - 基于真实价格变动"""
        try:
            if not patterns or signal_data is None or signal_data.empty:
                return {'successful_count': 0, 'success_rate': 0.0, 'pattern_breakdown': {}}

            pattern_breakdown = {}
            successful_count = 0
            total_valid_patterns = 0

            # 获取信号数据的索引映射
            original_indices = self.current_kdata.index.tolist() if hasattr(self, 'current_kdata') and self.current_kdata is not None else []
            truncated_indices = signal_data.index.tolist()
            index_mapping = {orig_idx: trunc_idx for trunc_idx, orig_idx in enumerate(truncated_indices)}

            for pattern in patterns:
                pattern_type = pattern.get('pattern_type', pattern.get('name', 'unknown'))
                signal_type = pattern.get('signal_type', 'neutral')
                confidence = pattern.get('confidence', 0.0)
                pattern_index = pattern.get('index', 0)

                if signal_type.lower() == 'neutral':
                    continue

                total_valid_patterns += 1

                # 基于真实价格变动评估形态有效性
                is_successful = False

                # 检查形态索引是否在信号数据中
                if pattern_index in index_mapping:
                    mapped_index = index_mapping[pattern_index]
                    
                    # 确保有足够的数据来评估形态效果
                    if mapped_index + 5 < len(signal_data):
                        # 获取形态出现时的价格
                        entry_price = signal_data.iloc[mapped_index]['close']
                        
                        # 获取5个交易日后的价格
                        exit_price = signal_data.iloc[mapped_index + 5]['close']
                        
                        # 计算价格变动
                        price_change = (exit_price - entry_price) / entry_price
                        
                        # 根据信号类型判断是否成功
                        if signal_type.lower() in ['buy', 'bullish', '买入']:
                            # 买入信号：价格上涨为成功
                            is_successful = price_change > 0
                        elif signal_type.lower() in ['sell', 'bearish', '卖出']:
                            # 卖出信号：价格下跌为成功
                            is_successful = price_change < 0

                if is_successful:
                    successful_count += 1

                # 统计各形态类型效果
                if pattern_type not in pattern_breakdown:
                    pattern_breakdown[pattern_type] = {
                        'count': 0, 'successful': 0, 'avg_confidence': 0.0
                    }

                pattern_breakdown[pattern_type]['count'] += 1
                if is_successful:
                    pattern_breakdown[pattern_type]['successful'] += 1
                pattern_breakdown[pattern_type]['avg_confidence'] += confidence

            # 计算平均置信度
            for pattern_type in pattern_breakdown:
                count = pattern_breakdown[pattern_type]['count']
                if count > 0:
                    pattern_breakdown[pattern_type]['avg_confidence'] /= count

            success_rate = successful_count / total_valid_patterns if total_valid_patterns > 0 else 0.0

            return {
                'successful_count': successful_count,
                'success_rate': success_rate,
                'pattern_breakdown': pattern_breakdown,
                'total_valid_patterns': total_valid_patterns
            }

        except Exception as e:
            if True:  # 使用Loguru日志
                logger.error(f" 计算形态有效性失败: {e}")
            return {'successful_count': 0, 'success_rate': 0.0, 'pattern_breakdown': {}}

    def _run_simplified_backtest(self, patterns, signal_data, period):
        """简化回测逻辑（当专业引擎不可用时）"""
        try:
            if True:  # 使用Loguru日志
                logger.info("运行简化回测...")

            # 计算基础统计
            pattern_stats = self._calculate_pattern_effectiveness(patterns, signal_data)

            # 基于真实数据计算收益
            if signal_data is None or signal_data.empty:
                # 如果没有信号数据，使用默认值
                avg_return = 0.0
                max_drawdown = 0.0
                sharpe_ratio = 0.0
            else:
                # 计算实际收益
                returns = []
                peak_value = 0
                max_drawdown = 0
                
                # 模拟交易：基于信号计算收益
                position = 0  # 0: 空仓, 1: 多头, -1: 空头
                entry_price = 0
                total_return = 0
                
                for i in range(len(signal_data)):
                    signal = signal_data.iloc[i]['signal']
                    price = signal_data.iloc[i]['close']
                    
                    # 处理信号
                    if signal != 0 and position == 0:
                        # 开仓
                        position = signal
                        entry_price = price
                    elif signal == 0 and position != 0:
                        # 平仓
                        if position > 0:
                            trade_return = (price - entry_price) / entry_price
                        else:
                            trade_return = (entry_price - price) / entry_price
                        returns.append(trade_return)
                        total_return += trade_return
                        position = 0
                    
                    # 计算最大回撤
                    if total_return > peak_value:
                        peak_value = total_return
                    drawdown = peak_value - total_return
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown
                
                # 计算平均收益
                avg_return = np.mean(returns) if returns else 0.0
                
                # 计算夏普比率
                if returns:
                    sharpe_ratio = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0.0
                else:
                    sharpe_ratio = 0.0

            simplified_results = {
                'period': period,
                'total_signals': pattern_stats.get('total_valid_patterns', 0),
                'successful_signals': pattern_stats.get('successful_count', 0),
                'success_rate': pattern_stats.get('success_rate', 0.0),
                'avg_return': avg_return,
                'max_drawdown': max_drawdown,
                'sharpe_ratio': sharpe_ratio,
                'total_patterns': len(patterns),
                'pattern_breakdown': pattern_stats.get('pattern_breakdown', {}),
                'generated_time': datetime.now().isoformat(),
                'backtest_method': 'simplified',
                'data_quality': 'real_pattern_recognition'
            }

            # 保存简化回测结果到 BacktestResultManager
            try:
                from core.services.backtest_result_manager import BacktestResult
                import time
                
                backtest_result = BacktestResult(
                    stock_code=getattr(self, 'stock_code', ''),
                    stock_name=getattr(self, 'stock_name', ''),
                    strategy_name='形态识别策略（简化版）',
                    backtest_time=time.time(),
                    backtest_results=simplified_results,
                    trades=[],
                    duration=0,
                    is_professional=False
                )
                
                if hasattr(self, 'backtest_result_manager'):
                    self.backtest_result_manager.add_result(backtest_result)
                    logger.info(f"简化回测结果已保存到 BacktestResultManager")
            except Exception as save_error:
                logger.warning(f"保存简化回测结果失败: {save_error}")

            return simplified_results

        except Exception as e:
            if True:  # 使用Loguru日志
                logger.error(f" 简化回测失败: {e}")
            raise

    def _extract_patterns_from_table(self):
        """从表格提取形态数据"""
        try:
            patterns = []
            for row in range(self.patterns_table.rowCount()):
                try:
                    pattern = {
                        'pattern_type': self.patterns_table.item(row, 0).text() if self.patterns_table.item(row, 0) else '',
                        'signal_type': self.patterns_table.item(row, 1).text() if self.patterns_table.item(row, 1) else 'neutral',
                        'confidence': float(self.patterns_table.item(row, 2).text().replace('%', '')) / 100 if self.patterns_table.item(row, 2) else 0.0,
                        'index': row,  # 使用行索引作为位置
                        'name': self.patterns_table.item(row, 0).text() if self.patterns_table.item(row, 0) else f'pattern_{row}'
                    }
                    patterns.append(pattern)
                except (ValueError, AttributeError) as e:
                    if True:  # 使用Loguru日志
                        logger.warning(f" 跳过无效行 {row}: {e}")
                    continue

            return patterns

        except Exception as e:
            if True:  # 使用Loguru日志
                logger.error(f" 提取表格形态失败: {e}")
            return []

    def _update_backtest_display(self, backtest_results):
        """更新回测显示 - 真实数据增强版"""
        try:
            if True:  # 使用Loguru日志
                logger.info("开始更新回测显示")

            # 确保有backtest_text组件
            if not hasattr(self, 'backtest_text'):
                if True:  # 使用Loguru日志
                    logger.error("backtest_text组件不存在")
                return

            # 格式化显示文本
            generated_time = backtest_results.get('generated_time')
            if generated_time:
                try:
                    dt = datetime.fromisoformat(generated_time.replace('Z', '+00:00'))
                    time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    time_str = generated_time
            else:
                time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 获取回测方法和数据质量信息
            backtest_method = backtest_results.get('backtest_method', 'unknown')
            data_quality = backtest_results.get('data_quality', 'unknown')
            total_patterns = backtest_results.get('total_patterns', 0)
            pattern_breakdown = backtest_results.get('pattern_breakdown', {})

            # 构建基础报告
            text = f"""
 历史回测报告（基于真实形态识别）
=====================================

 基础指标:
 回测周期: {backtest_results.get('period', 'N/A')} 天
 识别形态: {total_patterns} 个
 有效信号: {backtest_results.get('total_signals', 0)} 个
 成功信号: {backtest_results.get('successful_signals', 0)} 个
 成功率: {backtest_results.get('success_rate', 0):.2%}

 收益指标:
 平均收益: {backtest_results.get('avg_return', 0):+.2%}
 最大回撤: {backtest_results.get('max_drawdown', 0):.2%}
 夏普比率: {backtest_results.get('sharpe_ratio', 0):.2f}

 数据质量:
 回测引擎: {self._get_method_description(backtest_method)}
 数据来源: {self._get_quality_description(data_quality)}
"""

            # 添加形态分析详情
            if pattern_breakdown:
                text += "\n 形态分析详情:\n"
                for pattern_type, stats in pattern_breakdown.items():
                    if stats['count'] > 0:
                        success_rate = stats['successful'] / stats['count']
                        avg_conf = stats['avg_confidence']
                        text += f" {pattern_type}: {stats['count']}个 (成功率{success_rate:.1%}, 平均置信度{avg_conf:.1%})\n"

            text += f"\n[TIME] 生成时间: {time_str}"

            self.backtest_text.setText(text)

            if True:  # 使用Loguru日志
                logger.info("回测显示更新完成")

        except Exception as e:
            error_msg = f"更新回测显示失败: {str(e)}"
            if True:  # 使用Loguru日志
                logger.error(f" {error_msg}")
                logger.error(traceback.format_exc())
            else:
                logger.info(f"[Pattern]  {error_msg}")

    def _get_method_description(self, method):
        """获取回测方法描述"""
        descriptions = {
            'professional_engine': '专业引擎回测',
            'simplified': '简化回测',
            'unknown': '未知方法'
        }
        return descriptions.get(method, method)

    def _get_quality_description(self, quality):
        """获取数据质量描述"""
        descriptions = {
            'real_pattern_recognition': '真实形态识别',
            'simulated': '模拟数据',
            'unknown': '未知来源'
        }
        return descriptions.get(quality, quality)

    def _on_backtest_completed(self, results):
        """处理回测完成"""
        try:
            self.hide_loading()

            if 'error' in results:
                QMessageBox.warning(self, "回测失败", results['error'])
                return

            logger.info(f"回测完成，结果: {results}")

            # 更新显示
            self._update_results_display(results)

            # 发射完成信号
            self.analysis_completed.emit(results)

        except Exception as e:
            logger.error(f"处理回测结果失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _on_backtest_error(self, error_msg):
        """处理回测错误"""
        try:
            self.hide_loading()
            logger.error(f"回测执行失败: {error_msg}")
            QMessageBox.critical(self, "回测错误", f"回测执行失败: {error_msg}")

        except Exception as e:
            logger.error(f"处理回测错误失败: {e}")

    def _update_results_display(self, results):
        """更新结果显示 - 重写以支持回测"""
        try:
            if True:  # 使用Loguru日志
                logger.info(f" 开始更新结果显示，结果类型: {list(results.keys()) if isinstance(results, dict) else type(results)}")

            # 处理回测结果
            if isinstance(results, dict) and 'backtest' in results:
                if True:  # 使用Loguru日志
                    logger.info("检测到回测结果，开始更新回测显示")
                self._update_backtest_display(results['backtest'])

            # 调用父类方法处理其他结果
            super()._update_results_display(results)

        except Exception as e:
            if True:  # 使用Loguru日志
                logger.error(f" 更新结果显示失败: {e}")
                logger.error(traceback.format_exc())
            else:
                logger.info(f"[Pattern]  更新结果显示失败: {e}")

    # 使用父类PatternAnalysisTabPro的优化版本_update_predictions_display方法
    # 不再重写此方法，确保使用最新的优化版本

    def _update_statistics_display(self, stats):
        """更新统计显示 - 修复版"""
        try:
            if not hasattr(self, 'stats_text'):
                logger.warning("对象没有stats_text属性")
                return

            text = f"""
 统计分析报告
================

总体统计:
- 形态总数: {stats.get('total_patterns', 0)} 个
- 买入信号: {stats.get('buy_patterns', 0)} 个
- 卖出信号: {stats.get('sell_patterns', 0)} 个
- 中性信号: {stats.get('neutral_patterns', 0)} 个

置信度分布:
- 高置信度: {stats.get('confidence_stats', {}).get('high_confidence', 0)} 个
- 中置信度: {stats.get('confidence_stats', {}).get('medium_confidence', 0)} 个
- 低置信度: {stats.get('confidence_stats', {}).get('low_confidence', 0)} 个

平均置信度: {stats.get('confidence_stats', {}).get('average', 0):.2%}
"""

            self.stats_text.setText(text)

        except Exception as e:
            logger.error(f"更新统计显示失败: {e}")
            logger.error(traceback.format_exc())

    def _process_alerts(self, alerts):
        """处理预警 - 最终修复版"""
        try:
            # 检查alerts参数
            if not alerts:
                return

            # 发送预警信号
            if hasattr(self, 'pattern_alert'):
                for alert in alerts:
                    self.pattern_alert.emit(alert['type'], alert)
        except Exception as e:
            logger.error(f"处理预警失败: {e}")
            logger.error(traceback.format_exc())

            # 此处不再引用results变量

    def _update_backtest_display_safe(self, results):
        """安全地更新回测显示"""
        if 'backtest' in results:
            self._update_backtest_display(results['backtest'])
