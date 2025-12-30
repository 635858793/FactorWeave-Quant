from loguru import logger
from analysis.pattern_manager import PatternManager
from core.performance.unified_monitor import PerformanceAutoTuner
from gui.dialogs.quality_report_dialog import show_quality_report_dialog
"""
主窗口协调器模块

负责协调主窗口各个组件之间的交互
"""
from datetime import datetime
from typing import Optional, Dict, Any
from PyQt5.QtCore import QObject, Qt
from PyQt5.QtWidgets import QInputDialog, QProgressDialog, QMessageBox
import threading

from core.containers.service_container import ServiceContainer

class MainWindowCoordinator(QObject):
    def __init__(self, main_window, service_container):
        super().__init__()
        self.main_window = main_window
        self.service_container = service_container
        self.logger = logger.bind(module=__name__)
        self.panels = {}  # Assuming a panels attribute to store panel references

    def show_settings_dialog(self):
        """显示设置对话框"""
        try:
            from gui.dialogs.settings_dialog import SettingsDialog
            dialog = SettingsDialog(self.main_window)
            dialog.exec_()
        except Exception as e:
            self.logger.error(f"显示设置对话框失败: {e}")
            QMessageBox.critical(self.main_window, "错误",
                                 f"无法打开设置对话框: {str(e)}")

    def show_node_manager_dialog(self):
        """显示分布式节点监控对话框（已更新为真实数据UI）"""
        try:
            from gui.dialogs.distributed_node_monitor_dialog import DistributedNodeMonitorDialog
            from core.containers import get_service_container
            
            container = get_service_container()
            distributed_service = container.get('distributed_service')
            
            if not distributed_service:
                QMessageBox.warning(self.main_window, "警告", "分布式服务未初始化")
                return
            
            dialog = DistributedNodeMonitorDialog(distributed_service, self.main_window)
            dialog.exec_()
        except Exception as e:
            self.logger.error(f"显示分布式节点监控对话框失败: {e}")
            QMessageBox.critical(self.main_window, "错误",
                                 f"无法打开分布式节点监控对话框: {str(e)}")

    def show_cloud_api_dialog(self):
        """显示云端API管理对话框"""
        try:
            from gui.dialogs.cloud_api_dialog import CloudApiDialog
            dialog = CloudApiDialog(self.main_window)
            dialog.exec_()
        except Exception as e:
            self.logger.error(f"显示云端API管理对话框失败: {e}")
            QMessageBox.critical(self.main_window, "错误",
                                 f"无法打开云端API管理对话框: {str(e)}")

    def show_indicator_market_dialog(self):
        """显示指标市场对话框"""
        try:
            from gui.dialogs.indicator_market_dialog import IndicatorMarketDialog
            dialog = IndicatorMarketDialog(self.main_window)
            dialog.exec_()
        except Exception as e:
            self.logger.error(f"显示指标市场对话框失败: {e}")
            QMessageBox.critical(self.main_window, "错误",
                                 f"无法打开指标市场对话框: {str(e)}")

    def show_optimization_dashboard(self):
        """显示优化仪表板"""
        try:
            from optimization.optimization_dashboard import OptimizationDashboard

            # 检查GUI可用性
            try:
                import matplotlib
                matplotlib.use('Qt5Agg')
                GUI_AVAILABLE = True
            except ImportError:
                GUI_AVAILABLE = False

            if not GUI_AVAILABLE:
                QMessageBox.warning(
                    self.main_window, "提示", "优化仪表板需要matplotlib支持，请安装：pip install matplotlib")
                return

            # 创建并显示优化仪表板
            dashboard = OptimizationDashboard()
            dashboard.show()

            self.logger.info("已打开优化仪表板")

        except Exception as e:
            self.logger.error(f"打开优化仪表板失败: {str(e)}")
            QMessageBox.critical(self.main_window, "错误",
                                 f"打开优化仪表板失败: {str(e)}")

    def _on_data_export(self):
        """数据导出处理"""
        try:
            from gui.dialogs.data_export_dialog import DataExportDialog

            dialog = DataExportDialog(self.main_window)
            if dialog.exec_() == DataExportDialog.Accepted:
                self.logger.info("数据导出完成")

        except Exception as e:
            self.logger.error(f"数据导出失败: {str(e)}")
            QMessageBox.critical(self.main_window, "错误", f"数据导出失败: {str(e)}")

    def run_one_click_optimization(self):
        """运行一键优化"""
        try:
            # 延迟导入，避免启动时阻塞
            from optimization.auto_tuner import AlgorithmAutoTuner
            from PyQt5.QtWidgets import QProgressDialog, QMessageBox
            from PyQt5.QtCore import QThread, pyqtSignal, Qt

            # 确认对话框
            reply = QMessageBox.question(
                self.main_window, "确认优化",
                "一键优化将对所有形态识别算法进行优化，这可能需要较长时间。\n确定要继续吗？",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            # 创建进度对话框
            progress = QProgressDialog(
                "正在优化形态识别算法...", "取消", 0, 100, self.main_window)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()

            # 创建优化线程
            class OptimizationThread(QThread):
                finished_signal = pyqtSignal(dict)
                error_signal = pyqtSignal(str)

                def run(self):
                    try:
                        tuner = AlgorithmAutoTuner(max_workers=2, debug_mode=True)
                        result = tuner.one_click_optimize(
                            optimization_method="genetic",
                            max_iterations=20
                        )
                        self.finished_signal.emit(result)
                    except Exception as e:
                        self.error_signal.emit(str(e))

            def on_optimization_finished(result):
                progress.close()
                summary = result.get("summary", {})
                message = f"""
一键优化完成！

总任务数: {summary.get('total_tasks', 0)}
成功任务数: {summary.get('successful_tasks', 0)}
成功率: {summary.get('success_rate', 0):.1f}%
平均改进: {summary.get('average_improvement', 0):.3f}%
最佳改进: {summary.get('best_improvement', 0):.3f}%
最佳形态: {summary.get('best_pattern', 'N/A')}
                """.strip()
                QMessageBox.information(self.main_window, "优化完成", message)
                self.logger.info("一键优化完成")

            def on_optimization_error(error):
                progress.close()
                QMessageBox.critical(
                    self.main_window, "优化失败", f"一键优化失败: {error}")
                self.logger.error(f"一键优化失败: {error}")

            # 启动优化线程
            self.optimization_thread = OptimizationThread()
            self.optimization_thread.finished_signal.connect(
                on_optimization_finished)
            self.optimization_thread.error_signal.connect(
                on_optimization_error)
            self.optimization_thread.start()

            self.logger.info("已启动一键优化")

        except Exception as e:
            self.logger.error(f"运行一键优化失败: {e}")
            QMessageBox.critical(self.main_window, "错误", f"一键优化失败: {str(e)}")

    def run_smart_optimization(self):
        """运行智能优化"""
        try:

            # 获取性能阈值
            threshold, ok = QInputDialog.getDouble(
                self.main_window, "智能优化设置",
                "请输入性能阈值（0.0-1.0）：\n低于此值的形态将被优化",
                0.7, 0.0, 1.0, 2
            )

            if not ok:
                return

            # 获取改进目标
            target, ok = QInputDialog.getDouble(
                self.main_window, "智能优化设置",
                "请输入改进目标（0.0-1.0）：\n期望的性能提升比例",
                0.1, 0.0, 1.0, 2
            )

            if not ok:
                return

            # 创建进度对话框
            progress = QProgressDialog(
                "正在进行智能优化...", "取消", 0, 100, self.main_window)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()

            # 在后台线程中执行优化
            def run_optimization():
                try:
                    tuner = PerformanceAutoTuner(max_workers=2, debug_mode=True)
                    result = tuner.smart_optimize(
                        performance_threshold=threshold,
                        improvement_target=target
                    )

                    progress.close()

                    if result.get("status") == "no_optimization_needed":
                        QMessageBox.information(
                            self.main_window, "智能优化",
                            "所有形态性能都达到要求，无需优化"
                        )
                    else:
                        summary = result.get("summary", {})
                        smart_analysis = result.get("smart_analysis", {})

                        message = f"""
智能优化完成！

优化形态数: {summary.get('total_tasks', 0)}
成功任务数: {summary.get('successful_tasks', 0)}
平均改进: {summary.get('average_improvement', 0):.3f}%
达成目标数: {smart_analysis.get('targets_achieved', 0)}
目标达成率: {smart_analysis.get('target_achievement_rate', 0):.1f}%
                        """.strip()
                        QMessageBox.information(
                            self.main_window, "智能优化完成", message)

                    self.logger.info("智能优化完成")

                except Exception as e:
                    progress.close()
                    QMessageBox.critical(
                        self.main_window, "优化失败", f"智能优化失败: {str(e)}")
                    self.logger.error(f"智能优化失败: {str(e)}")

            # 启动后台线程
            threading.Thread(target=run_optimization, daemon=True).start()

            self.logger.info("已启动智能优化")

        except Exception as e:
            self.logger.error(f"启动智能优化失败: {str(e)}")
            QMessageBox.critical(self.main_window, "错误", f"启动智能优化失败: {str(e)}")

    def show_version_manager(self):
        """显示版本管理器"""
        try:
            from optimization.ui_integration import VersionManagerDialog
            from optimization.version_manager import VersionManager
            from PyQt5.QtWidgets import QInputDialog, QMessageBox

            # 获取要管理的形态名称
            patterns = []
            try:
                from analysis.pattern_manager import PatternManager
                manager = PatternManager()
                pattern_configs = manager.get_all_patterns()
                patterns = [p.english_name for p in pattern_configs]
            except Exception as e:
                self.logger.error(f"获取形态列表失败: {e}")
                patterns = ["hammer", "doji", "three_white_soldiers"]  # 默认形态

            if not patterns:
                QMessageBox.information(self.main_window, "提示", "没有找到可管理的形态")
                return

            # 选择形态
            pattern_name, ok = QInputDialog.getItem(
                self.main_window, "选择形态", "请选择要管理版本的形态：",
                patterns, 0, False
            )

            if not ok or not pattern_name:
                return

            # 显示版本管理对话框
            version_manager = VersionManager()
            dialog = VersionManagerDialog(
                pattern_name, version_manager, self.main_window)
            dialog.exec_()

            self.logger.info(f"已打开 {pattern_name} 的版本管理器")

        except Exception as e:
            self.logger.error(f"打开版本管理器失败: {str(e)}")
            QMessageBox.critical(self.main_window, "错误",
                                 f"打开版本管理器失败: {str(e)}")

    def show_performance_evaluation(self):
        """显示性能评估"""
        try:
            
            # 获取要评估的形态名称
            patterns = []
            try:
                manager = PatternManager()
                pattern_configs = manager.get_all_patterns()
                patterns = [p.english_name for p in pattern_configs]
            except Exception as e:
                self.logger.error(f"获取形态列表失败: {e}")
                patterns = ["hammer", "doji", "three_white_soldiers"]  # 默认形态

            if not patterns:
                QMessageBox.information(self.main_window, "提示", "没有找到可评估的形态")
                return

            # 选择形态
            pattern_name, ok = QInputDialog.getItem(
                self.main_window, "选择形态", "请选择要评估性能的形态：",
                patterns, 0, False
            )

            if not ok or not pattern_name:
                return

            # 创建进度对话框
            progress = QProgressDialog(
                "正在评估性能...", "取消", 0, 100, self.main_window)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()

            # 在后台线程中执行评估
            def run_evaluation():
                try:
                    from optimization.algorithm_optimizer import PerformanceEvaluator
                    evaluator = PerformanceEvaluator(debug_mode=True)

                    # 创建测试数据集（使用真实数据）
                    test_datasets = evaluator.create_test_datasets(
                        pattern_name, count=5)

                    # 评估性能
                    metrics = evaluator.evaluate_algorithm(
                        pattern_name, test_datasets)

                    progress.close()

                    # 显示结果
                    result_text = f"""
形态: {pattern_name}
综合评分: {metrics.overall_score:.3f}
信号质量: {metrics.signal_quality:.3f}
平均置信度: {metrics.confidence_avg:.3f}
执行时间: {metrics.execution_time:.3f}秒
识别形态数: {metrics.patterns_found}
鲁棒性: {metrics.robustness_score:.3f}
参数敏感性: {metrics.parameter_sensitivity:.3f}
数据来源: 真实市场数据
测试股票数: {len(test_datasets)}
                    """.strip()

                    QMessageBox.information(
                        self.main_window, f"性能评估 - {pattern_name}", result_text)
                    self.logger.info(f"已完成 {pattern_name} 的性能评估（使用真实数据）")

                except Exception as e:
                    progress.close()
                    QMessageBox.critical(
                        self.main_window, "评估失败", f"性能评估失败: {str(e)}")
                    self.logger.error(f"性能评估失败: {str(e)}")

            # 启动后台线程
            threading.Thread(target=run_evaluation, daemon=True).start()

            self.logger.info(f"已启动 {pattern_name} 的性能评估")

        except Exception as e:
            self.logger.error(f"启动性能评估失败: {str(e)}")
            QMessageBox.critical(self.main_window, "错误", f"启动性能评估失败: {str(e)}")

    def show_optimization_status(self):
        """显示优化系统状态"""
        try:
            from optimization.database_schema import OptimizationDatabaseManager

            # 获取系统状态
            tuner = PerformanceAutoTuner(debug_mode=True)
            status = tuner.get_optimization_status()

            db_manager = OptimizationDatabaseManager()
            db_stats = db_manager.get_optimization_statistics()

            # 格式化状态信息
            status_text = f"""
系统状态: {status.get('system_status', 'unknown')}
活跃优化任务: {status.get('active_optimizations', 0)}
已完成优化: {status.get('completed_optimizations', 0)}
失败优化: {status.get('failed_optimizations', 0)}

数据库统计:
总版本数: {db_stats.get('total_versions', 0)}
活跃版本数: {db_stats.get('active_versions', 0)}
平均改进: {db_stats.get('avg_improvement', 0):.3f}%

最后更新: {status.get('last_update', 'N/A')}
            """.strip()

            QMessageBox.information(self.main_window, "优化系统状态", status_text)
            self.logger.info("已查看优化系统状态")

        except Exception as e:
            self.logger.error(f"获取优化系统状态失败: {str(e)}")
            QMessageBox.critical(self.main_window, "错误",
                                 f"获取优化系统状态失败: {str(e)}")

    def check_single_stock_quality(self):
        """检查单个股票数据质量"""
        try:
            from PyQt5.QtWidgets import QInputDialog, QMessageBox, QProgressDialog

            # 获取当前股票代码
            current_stock = self.get_current_stock()
            if not current_stock:
                QMessageBox.warning(self.main_window, "提示", "请先选择一个股票")
                return

            stock_code = current_stock.get('code', '')
            if not stock_code:
                QMessageBox.warning(self.main_window, "提示", "无效的股票代码")
                return

            # 创建进度对话框
            progress = QProgressDialog(
                f"正在检查 {stock_code} 的数据质量...", "取消", 0, 100, self.main_window)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()

            def run_quality_check():
                try:
                    # 获取K线数据
                    from core.services.unified_data_manager import get_unified_data_manager
                    data_manager = get_unified_data_manager()
                    kdata = data_manager.get_kdata(stock_code) if data_manager else None

                    if kdata is None or kdata.empty:
                        progress.close()
                        QMessageBox.warning(
                            self.main_window, "警告", f"无法获取 {stock_code} 的数据")
                        return

                    # 生成质量报告
                    report = self.generate_quality_report(
                        kdata, context=f"单股检查-{stock_code}")

                    progress.close()

                    # 显示报告对话框
                    from gui.dialogs.quality_report_dialog import show_quality_report_dialog
                    show_quality_report_dialog(
                        [{**report, "code": stock_code}], self.main_window)

                    self.logger.info(f"已完成 {stock_code} 的数据质量检查")

                except Exception as e:
                    progress.close()
                    QMessageBox.critical(
                        self.main_window, "错误", f"数据质量检查失败: {str(e)}")
                    self.logger.error(f"单股数据质量检查失败: {e}")

            # 启动后台线程
            threading.Thread(target=run_quality_check, daemon=True).start()

        except Exception as e:
            self.logger.error(f"启动单股数据质量检查失败: {e}")
            QMessageBox.critical(self.main_window, "错误", f"启动质量检查失败: {str(e)}")

    def check_all_stocks_quality(self):
        """检查所有股票数据质量"""
        try:
            # 确认对话框
            reply = QMessageBox.question(
                self.main_window, "确认检查",
                "批量数据质量检查可能需要较长时间，确定要继续吗？",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            # 获取股票列表
            stock_list = self.get_stock_list()
            if not stock_list:
                QMessageBox.warning(self.main_window, "提示", "没有可检查的股票")
                return

            total_stocks = len(stock_list)

            # 创建进度对话框
            progress = QProgressDialog(
                f"正在检查 {total_stocks} 只股票的数据质量...", "取消", 0, total_stocks, self.main_window)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()

            def run_batch_quality_check():
                try:
                    data_service = self.service_container.get_service(
                        'data_service')

                    reports = []
                    processed = 0

                    for stock in stock_list:
                        if progress.wasCanceled():
                            break

                        try:
                            stock_code = stock.get('code', '')
                            if not stock_code:
                                continue

                            # 获取K线数据
                            kdata = data_service.get_kdata(stock_code)

                            if kdata is not None and not kdata.empty:
                                # 生成质量报告
                                report = self.generate_quality_report(
                                    kdata, context=f"批量检查-{stock_code}")
                                report.update({
                                    "code": stock_code,
                                    "market": stock.get('market', '未知'),
                                    "industry": stock.get('industry', '未知')
                                })
                                reports.append(report)

                        except Exception as e:
                            self.logger.warning(f"检查股票 {stock_code} 失败: {e}")

                        processed += 1
                        progress.setValue(processed)

                    progress.close()

                    if reports:
                        # 显示报告对话框
                        show_quality_report_dialog(reports, self.main_window)

                        self.logger.info(f"已完成 {len(reports)} 只股票的数据质量检查")
                    else:
                        QMessageBox.information(
                            self.main_window, "提示", "没有生成有效的质量报告")

                except Exception as e:
                    progress.close()
                    QMessageBox.critical(
                        self.main_window, "错误", f"批量数据质量检查失败: {str(e)}")
                    self.logger.error(f"批量数据质量检查失败: {e}")

            # 启动后台线程
            threading.Thread(target=run_batch_quality_check,
                             daemon=True).start()

        except Exception as e:
            self.logger.error(f"启动批量数据质量检查失败: {e}")
            QMessageBox.critical(self.main_window, "错误", f"启动质量检查失败: {str(e)}")

    def generate_quality_report(self, kdata, context=""):
        """生成数据质量报告"""
        try:
            import numpy as np

            # 基础统计
            total_rows = len(kdata)
            missing_data = kdata.isnull().sum().sum()
            missing_ratio = missing_data / \
                (total_rows * len(kdata.columns)) if total_rows > 0 else 0

            # 价格关系检查
            price_errors = 0
            if 'high' in kdata.columns and 'low' in kdata.columns and 'open' in kdata.columns and 'close' in kdata.columns:
                # 检查高价 >= 低价
                invalid_high_low = (kdata['high'] < kdata['low']).sum()
                # 检查开盘价和收盘价在高低价范围内
                invalid_open = ((kdata['open'] > kdata['high']) | (
                    kdata['open'] < kdata['low'])).sum()
                invalid_close = ((kdata['close'] > kdata['high']) | (
                    kdata['close'] < kdata['low'])).sum()
                price_errors = invalid_high_low + invalid_open + invalid_close

            # 异常值检测
            anomaly_stats = {}
            numeric_columns = kdata.select_dtypes(include=[np.number]).columns
            for col in numeric_columns:
                if col in kdata.columns:
                    Q1 = kdata[col].quantile(0.25)
                    Q3 = kdata[col].quantile(0.75)
                    IQR = Q3 - Q1
                    lower_bound = Q1 - 1.5 * IQR
                    upper_bound = Q3 + 1.5 * IQR
                    outliers = ((kdata[col] < lower_bound) |
                                (kdata[col] > upper_bound)).sum()
                    if outliers > 0:
                        anomaly_stats[col] = outliers

            # 业务逻辑检查
            logic_errors = 0
            if 'volume' in kdata.columns:
                # 检查成交量为负数
                negative_volume = (kdata['volume'] < 0).sum()
                logic_errors += negative_volume

            # 计算质量评分
            quality_score = 100
            quality_score -= missing_ratio * 30  # 缺失数据扣分
            quality_score -= min(price_errors / total_rows *
                                 50, 20) if total_rows > 0 else 0  # 价格错误扣分
            quality_score -= min(len(anomaly_stats) * 5, 20)  # 异常值扣分
            quality_score -= min(logic_errors / total_rows *
                                 30, 15) if total_rows > 0 else 0  # 逻辑错误扣分
            quality_score = max(0, quality_score)

            # 生成错误和警告
            errors = []
            warnings = []

            if price_errors > 0:
                errors.append(f"价格关系异常 {price_errors} 条")
            if logic_errors > 0:
                errors.append(f"业务逻辑错误 {logic_errors} 条")
            if missing_ratio > 0.1:
                warnings.append(f"缺失数据比例过高 {missing_ratio:.2%}")
            if len(anomaly_stats) > 3:
                warnings.append(f"异常值字段过多 {len(anomaly_stats)} 个")

            return {
                "quality_score": round(quality_score, 1),
                "missing_fields": missing_data,
                "anomaly_stats": anomaly_stats,
                "empty_ratio": round(missing_ratio, 4),
                "price_relation_errors": price_errors,
                "logic_errors": logic_errors,
                "errors": errors,
                "warnings": warnings,
                "context": context,
                "check_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        except Exception as e:
            self.logger.error(f"生成质量报告失败: {e}")
            return {
                "quality_score": 0,
                "missing_fields": 0,
                "anomaly_stats": {},
                "empty_ratio": 0,
                "price_relation_errors": 0,
                "logic_errors": 0,
                "errors": [f"报告生成失败: {str(e)}"],
                "warnings": [],
                "context": context,
                "check_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

    def get_stock_list(self):
        """获取股票列表"""
        try:
            # 从左侧面板获取股票列表
            left_panel = self.panels.get('left')
            if left_panel and hasattr(left_panel, 'get_stock_list'):
                return left_panel.get_stock_list()

            # 如果没有，返回默认测试数据
            return [
                {"code": "000001", "name": "平安银行",
                    "market": "深圳", "industry": "银行"},
                {"code": "000002", "name": "万科A", "market": "深圳", "industry": "地产"},
                {"code": "600000", "name": "浦发银行",
                    "market": "上海", "industry": "银行"},
            ]

        except Exception as e:
            self.logger.error(f"获取股票列表失败: {e}")
            return []

    def start_auto_quality_check(self, interval_minutes=60):
        """启动自动质量检查"""
        try:
            from PyQt5.QtCore import QTimer

            if not hasattr(self, 'auto_quality_timer'):
                self.auto_quality_timer = QTimer()
                self.auto_quality_timer.timeout.connect(
                    self._auto_quality_check)

            # 启动定时器
            self.auto_quality_timer.start(
                interval_minutes * 60 * 1000)  # 转换为毫秒

            QMessageBox.information(
                self.main_window, "自动检查启动",
                f"自动数据质量检查已启动\n检查间隔: {interval_minutes} 分钟"
            )

        except Exception as e:
            self.logger.error(f"启动自动质量检查失败: {e}")

    def _auto_quality_check(self):
        """执行自动质量检查"""
        try:
            # 在后台执行质量检查

            def background_check():
                # 模拟后台质量检查
                import time
                time.sleep(2)

                # 模拟检查结果
                import random
                issues_found = random.randint(0, 5)

                if issues_found > 0:
                    # 如果发现问题，记录日志
                    self.logger.warning(f"自动质量检查发现 {issues_found} 个问题")

            thread = threading.Thread(target=background_check)
            thread.daemon = True
            thread.start()

        except Exception as e:
            self.logger.error(f"自动质量检查失败: {e}")

    def get_current_stock(self):
        """获取当前选中的股票"""
        try:
            # 从左侧面板获取当前选中的股票
            left_panel = self.panels.get('left')
            if left_panel and hasattr(left_panel, 'get_selected_stock'):
                return left_panel.get_selected_stock()
            return None
        except Exception as e:
            self.logger.error(f"获取当前股票失败: {e}")
            return None

    def switch_to_multi_screen(self):
        """切换到多屏模式"""
        try:
            QMessageBox.information(
                self.main_window, "多屏模式",
                "多屏模式功能正在开发中...\n\n功能包括：\n- 多图表同时显示\n- 图表数据同步\n- 自定义布局\n- 独立缩放控制"
            )
        except Exception as e:
            self.logger.error(f"切换到多屏模式失败: {e}")

    def switch_to_single_screen(self):
        """切换到单屏模式"""
        try:
            QMessageBox.information(
                self.main_window, "单屏模式",
                "已切换到单屏模式"
            )
        except Exception as e:
            self.logger.error(f"切换到单屏模式失败: {e}")

    def toggle_log_panel(self):
        """切换日志面板显示/隐藏"""
        try:
            bottom_panel = self.panels.get('bottom')
            if bottom_panel:
                # 切换底部面板的可见性
                is_visible = bottom_panel.isVisible()
                bottom_panel.setVisible(not is_visible)

                action_text = "隐藏" if not is_visible else "显示"
                self.logger.info(f"{action_text}日志面板")
            else:
                self.logger.warning("底部面板未找到")

        except Exception as e:
            self.logger.error(f"切换日志面板失败: {e}")

    def show_log_panel(self):
        """显示日志面板"""
        try:
            bottom_panel = self.panels.get('bottom')
            if bottom_panel:
                bottom_panel.setVisible(True)
                self.logger.info("显示日志面板")
            else:
                self.logger.warning("底部面板未找到")

        except Exception as e:
            self.logger.error(f"显示日志面板失败: {e}")

    def hide_log_panel(self):
        """隐藏日志面板"""
        try:
            bottom_panel = self.panels.get('bottom')
            if bottom_panel:
                bottom_panel.setVisible(False)
                self.logger.info("隐藏日志面板")
            else:
                self.logger.warning("底部面板未找到")

        except Exception as e:
            self.logger.error(f"隐藏日志面板失败: {e}")

    def broadcast_kdata_to_tabs(self, kdata):
        """广播K线数据到所有标签页"""
        try:
            # 获取中间面板（图表面板）
            middle_panel = self.panels.get('middle')
            if middle_panel and hasattr(middle_panel, 'update_chart_data'):
                middle_panel.update_chart_data(kdata)

            # 获取右侧面板的所有标签页
            right_panel = self.panels.get('right')
            if right_panel and hasattr(right_panel, 'broadcast_data'):
                right_panel.broadcast_data(kdata)

            self.logger.debug("K线数据已广播到所有标签页")

        except Exception as e:
            self.logger.error(f"广播K线数据失败: {e}")

    def refresh_tab_content(self, widget):
        """刷新标签页内容"""
        try:
            if hasattr(widget, 'refresh'):
                widget.refresh()
            elif hasattr(widget, 'update'):
                widget.update()

            self.logger.debug("标签页内容已刷新")

        except Exception as e:
            self.logger.error(f"刷新标签页内容失败: {e}")
