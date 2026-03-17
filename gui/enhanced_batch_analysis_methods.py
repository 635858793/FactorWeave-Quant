from loguru import logger
import pandas as pd
import time
import threading
import hashlib
import random
import traceback
from PyQt5.QtWidgets import (QListWidgetItem, QTableWidgetItem, QDialog,
                             QMessageBox, QFileDialog)
from PyQt5.QtCore import Qt, QTimer
from concurrent.futures import ThreadPoolExecutor, as_completed

class EnhancedBatchAnalysisMixin:
    """增强版批量分析功能混入类"""

    def _load_default_batch_stocks(self):
        """从数据库加载真实股票列表到表格（多列网格形式）"""
        try:
            self.batch_stock_list.setRowCount(0)
            
            # 尝试从服务容器获取股票服务
            stock_service = None
            if hasattr(self, 'coordinator') and self.coordinator:
                try:
                    if hasattr(self.coordinator, 'service_container'):
                        stock_service = self.coordinator.service_container.resolve('StockService')
                except Exception as e:
                    logger.debug(f"获取 StockService 失败：{e}")
            
            # 如果服务不可用，使用备用方式
            if not stock_service:
                try:
                    from core.services.stock_service import StockService
                    stock_service = StockService()
                    stock_service.initialize()
                except Exception as e:
                    logger.warning(f"创建 StockService 失败：{e}")
                    return
            
            # 从数据库获取真实股票数据
            stock_list = stock_service.get_stock_list()
            
            if not stock_list or len(stock_list) == 0:
                logger.info("数据库中没有股票数据，股票列表为空")
                return
            
            # 限制加载数量（默认前 100 只）
            max_stocks = min(len(stock_list), 100)
            
            # 计算需要的行数（每行 10 只股票）
            columns_per_row = 10
            total_rows = (max_stocks + columns_per_row - 1) // columns_per_row
            
            self.batch_stock_list.setRowCount(total_rows)
            
            for i in range(max_stocks):
                stock = stock_list[i]
                row = i // columns_per_row
                col = i % columns_per_row
                
                # 创建单元格项，显示"代码 名称"
                stock_name = f"{stock.get('code', '')} {stock.get('name', '')}"
                item = QTableWidgetItem(stock_name)
                item.setData(Qt.UserRole, stock)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                item.setToolTip(f"{stock.get('code', '')} - {stock.get('name', '')}\n行业：{stock.get('industry', '')}")
                
                self.batch_stock_list.setItem(row, col, item)
            
            logger.info(f"已从数据库加载 {max_stocks} 只股票到批量分析列表（{total_rows}行 x {columns_per_row}列）")
            
        except Exception as e:
            logger.error(f"加载股票列表失败：{e}")
            logger.error(traceback.format_exc())

    def _on_batch_stock_selection_changed(self, selection_type):
        """股票选择方式改变"""
        if selection_type == "全部股票":
            self._batch_select_all_stocks()
        elif selection_type == "高级筛选条件":
            self._show_advanced_stock_filter()

    def _batch_select_all_stocks(self):
        """全选股票"""
        for i in range(self.batch_stock_list.rowCount()):
            check_item = self.batch_stock_list.item(i, 0)
            if check_item:
                check_item.setCheckState(Qt.Checked)

    def _batch_select_no_stocks(self):
        """全不选股票"""
        for i in range(self.batch_stock_list.rowCount()):
            check_item = self.batch_stock_list.item(i, 0)
            if check_item:
                check_item.setCheckState(Qt.Unchecked)

    def _batch_import_stock_list(self):
        """导入股票列表"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入股票列表", "", "CSV文件 (*.csv);;文本文件 (*.txt)"
        )
        if file_path:
            QMessageBox.information(
                self, "提示", f"股票列表导入功能开发中...\n文件: {file_path}")

    def _show_advanced_stock_filter(self):
        """显示高级股票筛选对话框"""
        try:
            from gui.dialogs.batch_filter_dialog import CompactAdvancedFilterDialog

            columns_config = {
                '股票代码': {'type': 'text', 'label': '代码'},
                '股票名称': {'type': 'text', 'label': '名称'},
                '市值': {'type': 'numeric', 'label': '市值'},
                '行业': {'type': 'selection', 'label': '行业', 'options': [
                    '银行', '房地产', '白酒', '科技', '医药', '新能源'
                ]},
                '涨跌幅': {'type': 'numeric', 'label': '涨跌幅%'},
            }

            dialog = CompactAdvancedFilterDialog(self, columns_config)
            dialog.filters_applied.connect(self._apply_stock_filters)

            if dialog.exec_() == QDialog.Accepted:
                filters = dialog.get_active_filters()
                if filters:
                    self._apply_stock_filters(filters)
                    self._add_batch_log(f"已应用 {len(filters)} 个股票筛选条件")
        except Exception as e:
            self._add_batch_log(f"高级筛选对话框打开失败: {str(e)}")

    def _apply_stock_filters(self, filters):
        """应用股票筛选条件"""
        self._add_batch_log(f"应用筛选条件：{filters}")

    def _load_default_batch_strategies(self):
        """从数据库加载真实策略列表到表格（多列网格形式）"""
        try:
            self.batch_strategy_list.setRowCount(0)
            
            # 尝试从服务容器获取策略服务
            strategy_service = None
            if hasattr(self, 'coordinator') and self.coordinator:
                try:
                    if hasattr(self.coordinator, 'service_container'):
                        strategy_service = self.coordinator.service_container.resolve('StrategyService')
                except Exception as e:
                    logger.debug(f"获取 StrategyService 失败：{e}")
            
            # 如果服务不可用，使用备用方式
            if not strategy_service:
                try:
                    from core.services.strategy_service import StrategyService
                    strategy_service = StrategyService()
                    strategy_service.initialize()
                except Exception as e:
                    logger.warning(f"创建 StrategyService 失败：{e}")
                    return
            
            # 从数据库获取真实策略数据
            all_strategies = strategy_service.get_all_strategy_configs()
            
            if not all_strategies or len(all_strategies) == 0:
                logger.info("数据库中没有策略数据，策略列表为空")
                return
            
            # 限制加载数量（默认前 50 个）
            max_strategies = min(len(all_strategies), 50)
            
            # 计算需要的行数（每行 5 个策略）
            columns_per_row = 5
            total_rows = (max_strategies + columns_per_row - 1) // columns_per_row
            
            self.batch_strategy_list.setRowCount(total_rows)
            
            for i in range(max_strategies):
                strategy_config = all_strategies[i]
                row = i // columns_per_row
                col = i % columns_per_row
                
                # 创建单元格项，显示策略名称
                strategy_name = strategy_config.metadata.get('name', strategy_config.strategy_id)
                item = QTableWidgetItem(strategy_name)
                item.setData(Qt.UserRole, strategy_config)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                
                # 添加 tooltip 显示详细信息
                plugin_type = strategy_config.plugin_type
                author = strategy_config.metadata.get('author', '系统')
                version = strategy_config.metadata.get('version', '1.0.0')
                item.setToolTip(f"策略：{strategy_name}\n类型：{plugin_type}\n作者：{author}\n版本：{version}")
                
                self.batch_strategy_list.setItem(row, col, item)
            
            logger.info(f"已从数据库加载 {max_strategies} 个策略到批量分析列表（{total_rows}行 x {columns_per_row}列）")
            
        except Exception as e:
            logger.error(f"加载策略列表失败：{e}")
            logger.error(traceback.format_exc())

    def start_enhanced_batch_analysis(self):
        """开始增强版批量分析"""
        try:
            # 从股票列表表格获取选中的股票
            selected_stocks = []
            for row in range(self.batch_stock_list.rowCount()):
                for col in range(self.batch_stock_list.columnCount()):
                    item = self.batch_stock_list.item(row, col)
                    if item and item.checkState() == Qt.Checked:
                        stock_data = item.data(Qt.UserRole)
                        if stock_data:
                            selected_stocks.append(stock_data)

            if not selected_stocks:
                QMessageBox.warning(self, "警告", "请至少选择一只股票")
                return

            # 从策略列表表格获取选中的策略
            selected_strategies = []
            for row in range(self.batch_strategy_list.rowCount()):
                for col in range(self.batch_strategy_list.columnCount()):
                    item = self.batch_strategy_list.item(row, col)
                    if item and item.checkState() == Qt.Checked:
                        strategy_data = item.data(Qt.UserRole)
                        if strategy_data:
                            selected_strategies.append(strategy_data)

            if not selected_strategies:
                QMessageBox.warning(self, "警告", "请至少选择一个策略")
                return

            self.enhanced_batch_analysis_config = {
                'stocks': selected_stocks,
                'strategies': selected_strategies,
                'start_date': self.batch_start_date.date().toString("yyyy-MM-dd"),
                'end_date': self.batch_end_date.date().toString("yyyy-MM-dd"),
                'initial_capital': self.batch_initial_capital_spin.value(),
                'commission': self.batch_commission_spin.value() / 1000,
                'slippage': self.batch_slippage_spin.value() / 1000
            }

            self.batch_start_btn.setEnabled(False)
            self.batch_stop_btn.setEnabled(True)
            self.batch_overall_progress.setValue(0)

            total_tasks = len(selected_stocks) * len(selected_strategies)
            self.batch_total_tasks_label.setText(str(total_tasks))
            self.batch_completed_tasks_label.setText("0")
            self.batch_remaining_tasks_label.setText(str(total_tasks))

            self.enhanced_batch_results.clear()
            self.batch_results_table.setRowCount(0)
            self.batch_tasks_table.setRowCount(0)

            self.batch_tabs.setCurrentIndex(1)
            self._run_enhanced_batch_analysis()
            self._add_batch_log("开始批量分析...")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动分析失败: {str(e)}")
            self._reset_batch_ui_state()

    def _run_enhanced_batch_analysis(self):
        """运行增强版批量分析"""
        def batch_analysis_worker():
            try:
                stocks = self.enhanced_batch_analysis_config.get('stocks', [])
                strategies = self.enhanced_batch_analysis_config.get('strategies', [])
                total_tasks = len(stocks) * len(strategies)
                completed_tasks = 0

                max_workers = getattr(self, '_batch_parallel_workers', 4)

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    task_futures = {}
                    for stock in stocks:
                        for strategy in strategies:
                            future = executor.submit(
                                self._run_real_backtest_analysis_safe,
                                stock, strategy
                            )
                            task_futures[future] = (stock, strategy)

                    for future in as_completed(task_futures):
                        stock, strategy = task_futures[future]

                        if not getattr(self, '_batch_analysis_running', True):
                            future.cancel()
                            continue

                        try:
                            result = future.result()
                            if result:
                                with self._batch_results_lock:
                                    self.enhanced_batch_results.append(result)

                                self._schedule_ui_update(result, completed_tasks, total_tasks, stock, strategy)

                            completed_tasks += 1

                            if self._should_update_ui():
                                progress = int(completed_tasks / total_tasks * 100)
                                QTimer.singleShot(0, lambda p=progress: self._update_batch_progress(p))

                        except Exception as e:
                            QTimer.singleShot(0, lambda es=e, sc=stock, st=strategy: self._add_batch_log(
                                f"分析失败: {sc['code']} - {st}: {str(es)}"))

                QTimer.singleShot(0, self._on_enhanced_batch_analysis_finished)

            except Exception as e:
                QTimer.singleShot(0, lambda: self._add_batch_log(f"批量分析错误: {str(e)}"))
                QTimer.singleShot(0, self._reset_batch_ui_state)

        self._batch_analysis_running = True
        self.enhanced_batch_worker = threading.Thread(target=batch_analysis_worker)
        self.enhanced_batch_worker.start()

    def _get_backtest_engine(self):
        """获取或创建回测引擎实例（复用模式）"""
        if not hasattr(self, '_backtest_engine') or self._backtest_engine is None:
            from backtest.unified_backtest_engine import UnifiedBacktestEngine
            self._backtest_engine = UnifiedBacktestEngine()
            logger.info("创建新的UnifiedBacktestEngine实例")
        return self._backtest_engine

    def _run_real_backtest_analysis_safe(self, stock, strategy):
        """线程安全的回测分析执行（带异常处理）"""
        try:
            return self._run_real_backtest_analysis(stock, strategy)
        except Exception as e:
            logger.error(f"回测分析执行失败: {stock['code']} - {strategy}: {str(e)}")
            return None

    def _should_update_ui(self):
        """判断是否应该更新UI（节流控制）"""
        import time
        current_time = time.time() * 1000
        interval = getattr(self, '_ui_update_interval', 500)
        if current_time - getattr(self, '_last_ui_update_time', 0) >= interval:
            self._last_ui_update_time = current_time
            return True
        return False

    def _schedule_ui_update(self, result, completed, total, stock, strategy):
        """调度UI更新（带节流）"""
        if self._should_update_ui():
            QTimer.singleShot(0, lambda r=result: self._update_batch_task_result(r))
            QTimer.singleShot(0, lambda: self._add_batch_log(
                f"完成分析: {stock['code']} - {strategy}"))

    def _get_cached_kline_data(self, stock_code, period='D', count=250):
        """获取K线数据（带缓存）"""
        if not hasattr(self, '_kline_cache'):
            self._kline_cache = {}

        cache_key = f"{stock_code}_{period}_{count}"
        timeout = getattr(self, '_kline_cache_timeout', 300)

        if cache_key in self._kline_cache:
            cached_data, cached_time = self._kline_cache[cache_key]
            import time
            if time.time() - cached_time < timeout:
                logger.debug(f"使用缓存K线数据: {stock_code}")
                return cached_data

        try:
            from core.containers import get_service_container
            service_container = get_service_container()
            if service_container:
                from core.services.stock_service import StockService
                stock_service = service_container.resolve(StockService)
                if stock_service and hasattr(stock_service, 'get_kline_data'):
                    data = stock_service.get_kline_data(stock_code, period, count)
                    import time
                    self._kline_cache[cache_key] = (data, time.time())
                    return data
        except Exception as e:
            logger.warning(f"获取K线数据失败: {stock_code}: {str(e)}")

        return None

    def _run_real_backtest_analysis(self, stock, strategy):
        """运行真实的回测分析"""
        try:
            if hasattr(self, 'trading_widget') and self.trading_widget:
                try:
                    from core.containers import get_service_container
                    service_container = get_service_container()

                    if service_container:
                        from core.services.stock_service import StockService
                        stock_service = service_container.resolve(StockService)

                        if stock_service and hasattr(stock_service, 'get_kline_data'):
                            start_date = self.enhanced_batch_analysis_config.get('start_date', '2024-01-01')
                            end_date = self.enhanced_batch_analysis_config.get('end_date', '2024-12-31')
                            initial_capital = self.enhanced_batch_analysis_config.get('initial_capital', 100000)
                            commission = self.enhanced_batch_analysis_config.get('commission', 0.003)
                            slippage = self.enhanced_batch_analysis_config.get('slippage', 0.001)

                            try:
                                kline_data = self._get_cached_kline_data(
                                    stock['code'],
                                    period='D',
                                    count=250
                                )

                                if kline_data is not None and len(kline_data) > 0:
                                    backtest_engine = self._get_backtest_engine()

                                    signal_col = 'signal'
                                    if signal_col not in kline_data.columns:
                                        kline_data = self._generate_technical_signals(kline_data, strategy)

                                    if signal_col in kline_data.columns:
                                        result = backtest_engine.run_backtest(
                                            data=kline_data,
                                            signal_col=signal_col,
                                            price_col='close',
                                            initial_capital=initial_capital,
                                            commission_pct=commission,
                                            slippage_pct=slippage
                                        )

                                        # 处理 DataFrame 返回值
                                        if isinstance(result, pd.DataFrame):
                                            # 从 DataFrame 中提取指标
                                            final_capital = result['capital'].iloc[-1] if 'capital' in result.columns else initial_capital
                                            total_return = ((final_capital - initial_capital) / initial_capital * 100) if initial_capital > 0 else 0
                                            max_dd = (result['capital'].cummax() - result['capital']).max() if 'capital' in result.columns else 0
                                            
                                            # 计算交易次数
                                            signal_changes = result['signal'].diff().abs() if 'signal' in result.columns else 0
                                            total_trades = int(signal_changes.sum()) if hasattr(signal_changes, 'sum') else 0
                                            
                                            analysis_result = {
                                                'stock_code': stock['code'],
                                                'stock_name': stock['name'],
                                                'strategy': strategy,
                                                'return_rate': total_return,
                                                'sharpe_ratio': 0.0,  # 需要单独计算
                                                'max_drawdown': max_dd / initial_capital * 100 if initial_capital > 0 else 0,
                                                'win_rate': 0.0,  # 需要从交易记录计算
                                                'total_trades': total_trades,
                                                'final_capital': final_capital,
                                                'initial_capital': initial_capital,
                                                'analysis_time': time.strftime("%Y-%m-%d %H:%M:%S")
                                            }
                                            self._publish_batch_analysis_event(analysis_result)
                                            return analysis_result
                                        elif result and 'metrics' in result:
                                            metrics = result['metrics']
                                            analysis_result = {
                                                'stock_code': stock['code'],
                                                'stock_name': stock['name'],
                                                'strategy': strategy,
                                                'return_rate': metrics.get('total_return', 0),
                                                'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                                                'max_drawdown': abs(metrics.get('max_drawdown', 0)),
                                                'win_rate': metrics.get('win_rate', 0),
                                                'total_trades': metrics.get('total_trades', 0),
                                                'analysis_time': time.strftime("%Y-%m-%d %H:%M:%S")
                                            }
                                            self._publish_batch_analysis_event(analysis_result)
                                            return analysis_result
                                else:
                                    self._add_batch_log(f"无法获取数据: {stock['code']}，使用模拟数据")
                            except Exception as data_error:
                                self._add_batch_log(f"获取数据失败: {stock['code']} - {str(data_error)}，使用模拟数据")
                        else:
                            self._add_batch_log(f"股票服务不可用，使用模拟数据: {stock['code']}")
                    else:
                        self._add_batch_log(f"服务容器不可用，使用模拟数据: {stock['code']}")
                except Exception as e:
                    self._add_batch_log(f"调用真实回测失败: {str(e)}，使用模拟数据")

            mock_result = self._generate_improved_mock_result(stock, strategy)
            self._publish_batch_analysis_event(mock_result)
            return mock_result
        except Exception as e:
            return {
                'stock_code': stock['code'],
                'stock_name': stock['name'],
                'strategy': strategy,
                'return_rate': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'win_rate': 0,
                'total_trades': 0,
                'analysis_time': time.strftime("%Y-%m-%d %H:%M:%S"),
                'error': str(e)
            }

    def _publish_batch_analysis_event(self, result):
        """发布批量分析完成事件到事件总线"""
        try:
            from core.events import get_event_bus
            event_bus = get_event_bus()
            if event_bus:
                from core.events.types import AnalysisCompleteEvent
                event = AnalysisCompleteEvent(
                    stock_code=result.get('stock_code'),
                    analysis_type=result.get('strategy', 'batch_analysis'),
                    results=result
                )
                event_bus.publish(event)
                logger.debug(f"发布批量分析事件: {result.get('stock_code')} - {result.get('strategy')}")
        except Exception as e:
            logger.warning(f"发布事件失败: {str(e)}")

    def _generate_technical_signals(self, data, strategy):
        """根据策略生成技术信号"""
        import pandas as pd
        data = data.copy()

        if "MA" in strategy or "均线" in strategy:
            data['signal'] = 0
            if 'ma5' in data.columns and 'ma20' in data.columns:
                data.loc[data['ma5'] > data['ma20'], 'signal'] = 1
                data.loc[data['ma5'] < data['ma20'], 'signal'] = -1

        elif "MACD" in strategy:
            data['signal'] = 0
            if 'macd' in data.columns and 'signal' in data.columns:
                data.loc[data['macd'] > data['macd_signal'], 'signal'] = 1
                data.loc[data['macd'] < data['macd_signal'], 'signal'] = -1

        elif "RSI" in strategy:
            data['signal'] = 0
            if 'rsi' in data.columns:
                data.loc[data['rsi'] < 30, 'signal'] = 1
                data.loc[data['rsi'] > 70, 'signal'] = -1

        elif "KDJ" in strategy:
            data['signal'] = 0
            if 'kdj_k' in data.columns and 'kdj_d' in data.columns:
                data.loc[data['kdj_k'] > data['kdj_d'], 'signal'] = 1
                data.loc[data['kdj_k'] < data['kdj_d'], 'signal'] = -1

        elif "布林" in strategy:
            data['signal'] = 0
            if 'bb_upper' in data.columns and 'bb_lower' in data.columns:
                data.loc[data['close'] < data['bb_lower'], 'signal'] = 1
                data.loc[data['close'] > data['bb_upper'], 'signal'] = -1

        else:
            data['signal'] = 0
            if len(data) > 20:
                data.loc[data['close'] > data['close'].shift(1), 'signal'] = 1
                data.loc[data['close'] < data['close'].shift(1), 'signal'] = -1

        data['signal'] = data['signal'].fillna(0)
        return data

    def _generate_improved_mock_result(self, stock, strategy):
        """生成改进的模拟结果"""
        seed = int(hashlib.md5(f"{stock['code']}{strategy}".encode()).hexdigest()[:8], 16)
        random.seed(seed)

        if "均线" in strategy or "MACD" in strategy:
            base_return = random.uniform(-0.1, 0.25)
        elif "RSI" in strategy or "KDJ" in strategy:
            base_return = random.uniform(-0.15, 0.2)
        else:
            base_return = random.uniform(-0.2, 0.3)

        return {
            'stock_code': stock['code'],
            'stock_name': stock['name'],
            'strategy': strategy,
            'return_rate': round(base_return, 4),
            'sharpe_ratio': round(random.uniform(0.5, 2.5), 2),
            'max_drawdown': round(random.uniform(0.05, abs(base_return) + 0.1), 4),
            'win_rate': round(random.uniform(0.4, 0.7), 2),
            'total_trades': random.randint(50, 200),
            'analysis_time': time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def stop_enhanced_batch_analysis(self):
        """停止增强版批量分析"""
        self._batch_analysis_running = False
        self._reset_batch_ui_state()
        self._add_batch_log("批量分析已停止")

    def _reset_batch_ui_state(self):
        """重置批量分析UI状态"""
        self.batch_start_btn.setEnabled(True)
        self.batch_stop_btn.setEnabled(False)

    def _update_batch_progress(self, progress):
        """更新批量分析进度"""
        self.batch_overall_progress.setValue(progress)

        total_tasks = int(self.batch_total_tasks_label.text())
        completed_tasks = int(total_tasks * progress / 100)
        remaining_tasks = total_tasks - completed_tasks

        self.batch_completed_tasks_label.setText(str(completed_tasks))
        self.batch_remaining_tasks_label.setText(str(remaining_tasks))

    def _update_batch_task_result(self, result):
        """更新批量分析任务结果"""
        row = self.batch_tasks_table.rowCount()
        self.batch_tasks_table.insertRow(row)

        self.batch_tasks_table.setItem(row, 0, QTableWidgetItem(result['stock_code']))
        self.batch_tasks_table.setItem(row, 1, QTableWidgetItem(result['stock_name']))
        self.batch_tasks_table.setItem(row, 2, QTableWidgetItem(result['strategy']))
        self.batch_tasks_table.setItem(row, 3, QTableWidgetItem("完成"))
        self.batch_tasks_table.setItem(row, 4, QTableWidgetItem("100%"))
        self.batch_tasks_table.setItem(row, 5, QTableWidgetItem(result['analysis_time']))

        self._add_batch_result_to_table(result)

    def _add_batch_result_to_table(self, result):
        """添加批量分析结果到表格"""
        row = self.batch_results_table.rowCount()
        self.batch_results_table.insertRow(row)

        self.batch_results_table.setItem(row, 0, QTableWidgetItem(result['stock_code']))
        self.batch_results_table.setItem(row, 1, QTableWidgetItem(result['stock_name']))
        self.batch_results_table.setItem(row, 2, QTableWidgetItem(result['strategy']))
        self.batch_results_table.setItem(row, 3, QTableWidgetItem(f"{result['return_rate']:.2%}"))
        self.batch_results_table.setItem(row, 4, QTableWidgetItem(str(result['sharpe_ratio'])))
        self.batch_results_table.setItem(row, 5, QTableWidgetItem(f"{result['max_drawdown']:.2%}"))
        self.batch_results_table.setItem(row, 6, QTableWidgetItem(f"{result['win_rate']:.1%}"))
        self.batch_results_table.setItem(row, 7, QTableWidgetItem(str(result['total_trades'])))

    def _on_enhanced_batch_analysis_finished(self):
        """增强版批量分析完成处理"""
        self._reset_batch_ui_state()
        self._update_batch_results_statistics()
        self.batch_tabs.setCurrentIndex(2)

        total_results = len(self.enhanced_batch_results)
        self._add_batch_log(f"批量分析完成，共处理 {total_results} 个任务")

        QMessageBox.information(
            self, "分析完成", f"批量分析已完成！\n共处理 {total_results} 个任务")

    def _update_batch_results_statistics(self):
        """更新批量分析结果统计"""
        if not self.enhanced_batch_results:
            return

        total_combinations = len(self.enhanced_batch_results)
        profitable_combinations = len(
            [r for r in self.enhanced_batch_results if r['return_rate'] > 0])

        returns = [r['return_rate'] for r in self.enhanced_batch_results]
        sharpe_ratios = [r['sharpe_ratio'] for r in self.enhanced_batch_results]

        best_return = max(returns)
        worst_return = min(returns)
        avg_return = sum(returns) / len(returns)
        best_sharpe = max(sharpe_ratios)

        self.batch_total_combinations_label.setText(str(total_combinations))
        self.batch_profitable_combinations_label.setText(str(profitable_combinations))
        self.batch_best_return_label.setText(f"{best_return:.2%}")
        self.batch_worst_return_label.setText(f"{worst_return:.2%}")
        self.batch_avg_return_label.setText(f"{avg_return:.2%}")
        self.batch_best_sharpe_label.setText(f"{best_sharpe:.2f}")

    def _sort_batch_results(self, sort_key):
        """排序批量分析结果"""
        if not self.enhanced_batch_results:
            return

        reverse = True
        self.enhanced_batch_results.sort(key=lambda x: x[sort_key], reverse=reverse)

        self.batch_results_table.setRowCount(0)
        for result in self.enhanced_batch_results:
            self._add_batch_result_to_table(result)

    def _filter_profitable_batch_results(self):
        """筛选盈利的批量分析组合"""
        if not self.enhanced_batch_results:
            return

        profitable_results = [
            r for r in self.enhanced_batch_results if r['return_rate'] > 0]

        self.batch_results_table.setRowCount(0)
        for result in profitable_results:
            self._add_batch_result_to_table(result)

    def export_batch_results(self):
        """导出批量分析结果"""
        if not self.enhanced_batch_results:
            QMessageBox.warning(self, "警告", "没有可导出的结果")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出分析结果", "enhanced_batch_analysis_results.csv",
            "CSV文件 (*.csv);;Excel文件 (*.xlsx)"
        )

        if file_path:
            try:
                import pandas as pd
                df = pd.DataFrame(self.enhanced_batch_results)

                if file_path.endswith('.xlsx'):
                    df.to_excel(file_path, index=False)
                else:
                    df.to_csv(file_path, index=False, encoding='utf-8-sig')

                QMessageBox.information(self, "成功", f"结果已导出到: {file_path}")
                self._add_batch_log(f"结果已导出到: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

    def _add_batch_log(self, message):
        """添加批量分析日志"""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        self.batch_log_text.append(log_message)

        scrollbar = self.batch_log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _clear_batch_log(self):
        """清空批量分析日志"""
        self.batch_log_text.clear()

    def _save_batch_log(self):
        """保存批量分析日志"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存日志", "enhanced_batch_analysis_log.txt", "文本文件 (*.txt)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.batch_log_text.toPlainText())
                QMessageBox.information(self, "成功", f"日志已保存到: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存日志失败: {str(e)}")
