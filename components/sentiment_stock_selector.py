import pandas as pd
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt
import json
import os
from components.trade_api import SimulatedTradeAPI
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger

SIGNAL_CONFIG_FILE = os.path.expanduser("~/.factorweave_signal_config.json")

def load_signal_config():
    if os.path.exists(SIGNAL_CONFIG_FILE):
        with open(SIGNAL_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"MACD金叉": {"fast": 12, "slow": 26, "signal": 9}, "RSI超卖": {"period": 14, "threshold": 30}, "KDJ金叉": {"n": 9, "m1": 3, "m2": 3}}

def save_signal_config(cfg):
    with open(SIGNAL_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

class SentimentStockSelectorDialog(QDialog):
    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.setWindowTitle("情绪驱动选股")
        self.setMinimumSize(600, 700)
        self.signal_config = load_signal_config()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("情绪区间："))
        self.min_spin = QSpinBox()
        self.min_spin.setRange(0, 100)
        self.min_spin.setValue(20)
        self.max_spin = QSpinBox()
        self.max_spin.setRange(0, 100)
        self.max_spin.setValue(80)
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("最小情绪指数"))
        hbox.addWidget(self.min_spin)
        hbox.addWidget(QLabel("最大情绪指数"))
        hbox.addWidget(self.max_spin)
        layout.addLayout(hbox)
        layout.addWidget(QLabel("技术指标条件："))
        self.indicator_combo = QComboBox()
        self.indicator_combo.addItems(list(self.signal_config.keys()))
        layout.addWidget(self.indicator_combo)
        btn_edit_signal = QPushButton("自定义信号")
        btn_edit_signal.clicked.connect(self.edit_signal)
        layout.addWidget(btn_edit_signal)
        btn_visual_signal = QPushButton("可视化编辑信号")
        btn_visual_signal.clicked.connect(self.visual_edit_signal)
        layout.addWidget(btn_visual_signal)
        layout.addWidget(QLabel("行业/概念筛选（演示）："))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["全部", "银行", "白酒", "新能源", "半导体"])
        layout.addWidget(self.filter_combo)
        btn_select = QPushButton("一键选股")
        btn_select.clicked.connect(self.select_stocks)
        layout.addWidget(btn_select)
        self.result_list = QListWidget()
        layout.addWidget(self.result_list)
        btn_export = QPushButton("导出结果")
        btn_export.clicked.connect(self.export_result)
        layout.addWidget(btn_export)
        btn_backtest = QPushButton("回测")
        btn_backtest.clicked.connect(self.backtest)
        layout.addWidget(btn_backtest)
        btn_simtrade = QPushButton("实盘模拟")
        btn_simtrade.clicked.connect(self.simtrade)
        layout.addWidget(btn_simtrade)
        btn_realtrade = QPushButton("实盘下单")
        btn_realtrade.clicked.connect(self.realtrade)
        layout.addWidget(btn_realtrade)
        btn_autotune = QPushButton("自动调优")
        btn_autotune.clicked.connect(self.autotune)
        layout.addWidget(btn_autotune)
        # 调优目标选择
        layout.addWidget(QLabel("调优目标："))
        self.tune_target_combo = QComboBox()
        self.tune_target_combo.addItems(["最大收益", "最小回撤", "夏普比率"])
        layout.addWidget(self.tune_target_combo)
        # 多周期选择
        period_hbox = QHBoxLayout()
        period_hbox.addWidget(QLabel("回测周期(天)："))
        self.periods = [7, 30, 90]
        self.period_checks = []
        for p in self.periods:
            cb = QCheckBox(str(p))
            cb.setChecked(p == 30)
            self.period_checks.append(cb)
            period_hbox.addWidget(cb)
        layout.addLayout(period_hbox)
        # 回测结果表格
        self.backtest_table = QTableWidget()
        self.backtest_table.setColumnCount(len(self.periods)*2)
        self.backtest_table.setHorizontalHeaderLabels(
            [f"{p}日收益" for p in self.periods]+[f"{p}日回撤" for p in self.periods])
        layout.addWidget(self.backtest_table)
        self.backtest_result = QTextEdit()
        self.backtest_result.setReadOnly(True)
        layout.addWidget(self.backtest_result)
        self.selected_stocks = []
        self.simtrade_positions = {}
        self.trade_api = SimulatedTradeAPI()

    def edit_signal(self):
        # 弹窗编辑信号参数
        indicator = self.indicator_combo.currentText()
        cfg = self.signal_config.get(indicator, {})
        text, ok = QInputDialog.getMultiLineText(
            self, "自定义信号参数", f"编辑{indicator}参数(JSON):", json.dumps(cfg, ensure_ascii=False, indent=2))
        if ok:
            try:
                new_cfg = json.loads(text)
                self.signal_config[indicator] = new_cfg
                save_signal_config(self.signal_config)
                QMessageBox.information(self, "保存成功", "信号参数已保存")
            except Exception as e:
                QMessageBox.warning(self, "格式错误", f"JSON解析失败: {e}")

    def visual_edit_signal(self):
        # 可视化信号编辑弹窗，支持参数区间
        dlg = QDialog(self)
        dlg.setWindowTitle("信号可视化编辑")
        vbox = QVBoxLayout(dlg)
        vbox.addWidget(QLabel("选择基础指标："))
        base_combo = QComboBox()
        base_combo.addItems(["MACD", "RSI", "KDJ", "MA", "BOLL"])
        vbox.addWidget(base_combo)
        vbox.addWidget(QLabel("参数设置："))
        param_edit = QLineEdit()
        param_edit.setPlaceholderText("如 fast=12,slow=26,signal=9")
        vbox.addWidget(param_edit)
        vbox.addWidget(QLabel("参数区间(可选)："))
        range_edit = QLineEdit()
        range_edit.setPlaceholderText("如 fast=10-15,slow=20-30")
        vbox.addWidget(range_edit)
        vbox.addWidget(QLabel("公式预览："))
        formula_label = QLabel()
        vbox.addWidget(formula_label)

        def update_formula():
            base = base_combo.currentText()
            params = param_edit.text()
            formula_label.setText(f"{base}({params})")
        base_combo.currentIndexChanged.connect(update_formula)
        param_edit.textChanged.connect(update_formula)
        update_formula()
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        vbox.addWidget(btns)

        def accept():
            base = base_combo.currentText()
            params = param_edit.text()
            param_dict = {}
            for kv in params.split(','):
                if '=' in kv:
                    k, v = kv.split('=')
                    param_dict[k.strip()] = int(
                        v.strip()) if v.strip().isdigit() else v.strip()
            # 解析区间
            range_dict = {}
            for kv in range_edit.text().split(','):
                if '=' in kv and '-' in kv:
                    k, rng = kv.split('=')
                    start, end = rng.split('-')
                    range_dict[k.strip()] = (int(start), int(end))
            param_dict['__range__'] = range_dict
            self.signal_config[f"自定义_{base}"] = param_dict
            save_signal_config(self.signal_config)
            self.indicator_combo.addItem(f"自定义_{base}")
            QMessageBox.information(self, "保存成功", "自定义信号已保存")
            dlg.accept()
        btns.accepted.connect(accept)
        btns.rejected.connect(dlg.reject)
        dlg.exec_()

    def select_stocks(self):
        try:
            min_val = self.min_spin.value()
            max_val = self.max_spin.value()
            indicator = self.indicator_combo.currentText()
            filter_val = self.filter_combo.currentText()
            signal_param = self.signal_config.get(indicator, {})

            if self.data_manager is None:
                QMessageBox.warning(self, "错误", "数据管理器不可用")
                return

            stock_list = []
            try:
                stock_list = self.data_manager.get_stock_list()
            except Exception as e:
                logger.warning(f"获取股票列表失败: {e}")

            if not stock_list:
                self.selected_stocks = ["000001 平安银行", "600519 贵州茅台", "300750 宁德时代"]
            else:
                self.selected_stocks = self._select_by_real_momentum(stock_list, filter_val)

            self.result_list.clear()
            for s in self.selected_stocks:
                self.result_list.addItem(s)
            self.backtest_result.clear()

            logger.info(f"情绪选股完成: 指标={indicator}, 范围={min_val}-{max_val}, 结果数={len(self.selected_stocks)}")

        except Exception as e:
            logger.error(f"选股失败: {e}")
            QMessageBox.warning(self, "错误", f"选股失败: {e}")
            self.selected_stocks = ["000001 平安银行", "600519 贵州茅台", "300750 宁德时代"]
            self.result_list.clear()
            for s in self.selected_stocks:
                self.result_list.addItem(s)

    def _select_by_real_momentum(self, stock_list, filter_val, top_n=3):
        try:
            from core.real_data_provider import get_real_data_provider
            provider = get_real_data_provider()
            if not provider:
                logger.warning("RealDataProvider不可用，无法基于真实数据选股")
                return []

            codes = list(stock_list.head(50)['code'])
            momentum_scores = []

            for code in codes:
                try:
                    kdata = provider.get_real_kdata(code, count=30)
                    if kdata is not None and not kdata.empty and 'close' in kdata.columns:
                        closes = kdata['close'].values
                        if len(closes) >= 10:
                            momentum = (closes[-1] - closes[-10]) / closes[-10]
                            name = code
                            try:
                                if 'name' in kdata.columns and len(kdata['name'].values) > 0:
                                    name = str(kdata['name'].values[-1])
                            except Exception:
                                pass
                            momentum_scores.append((code, name, momentum))
                except Exception as e:
                    logger.debug(f"获取{code}动量数据失败: {e}")

            if not momentum_scores:
                logger.warning("无可用真实价格数据，无法基于动量选股")
                return []

            momentum_scores.sort(key=lambda x: x[2], reverse=True)
            selected = momentum_scores[:top_n]
            return [f"{code} {name}" for code, name, _ in selected]

        except Exception as e:
            logger.warning(f"基于真实动量选股失败: {e}")
            return []

    def export_result(self):
        if self.selected_stocks:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出选股结果", "", "Text Files (*.txt);;All Files (*)")
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for s in self.selected_stocks:
                        f.write(s + '\n')

    def backtest(self):
        if not self.selected_stocks:
            self.backtest_result.setText("请先选股！")
            return
        checked_periods = [p for p, cb in zip(
            self.periods, self.period_checks) if cb.isChecked()]
        if not checked_periods:
            checked_periods = [30]
        self.backtest_table.setRowCount(len(self.selected_stocks))
        self.backtest_table.setColumnCount(len(checked_periods)*2)
        self.backtest_table.setHorizontalHeaderLabels(
            [f"{p}日收益" for p in checked_periods]+[f"{p}日回撤" for p in checked_periods])

        engine_available = False
        try:
            from backtest.unified_backtest_engine import UnifiedBacktestEngine
            engine = UnifiedBacktestEngine()
            engine_available = True
        except ImportError:
            logger.warning("回测: UnifiedBacktestEngine不可用，无法执行真实回测")
        except Exception as e:
            logger.warning(f"回测: 初始化UnifiedBacktestEngine失败: {e}")

        if not engine_available:
            for i in range(len(self.selected_stocks)):
                for j in range(len(checked_periods) * 2):
                    self.backtest_table.setItem(i, j, QTableWidgetItem("--"))
            self.backtest_result.setText("回测引擎不可用，无法执行回测。请检查UnifiedBacktestEngine配置。")
            return

        try:
            for i, s in enumerate(self.selected_stocks):
                code = s.split()[0] if ' ' in s else s
                price_df = None
                try:
                    if self.data_manager and hasattr(self.data_manager, 'get_kdata'):
                        price_df = self.data_manager.get_kdata(code)
                except Exception as e:
                    logger.debug(f"获取{code}价格数据失败: {e}")

                if price_df is None or price_df.empty or 'close' not in price_df.columns:
                    for j in range(len(checked_periods) * 2):
                        self.backtest_table.setItem(i, j, QTableWidgetItem("无数据"))
                    continue

                for j, p in enumerate(checked_periods):
                    pct_str = "--"
                    mdd_str = "--"
                    try:
                        sub_df = price_df.tail(p).copy()
                        if len(sub_df) < 2:
                            pct_str = "数据不足"
                            mdd_str = "数据不足"
                        else:
                            sub_df['signal'] = 1
                            result = engine.run_backtest(
                                sub_df,
                                signal_col='signal',
                                price_col='close',
                                initial_capital=100000,
                                stop_loss_pct=None,
                                take_profit_pct=None,
                                max_holding_periods=None
                            )
                            if result is not None and not result.empty:
                                metrics = engine.metrics
                                if metrics:
                                    total_return = getattr(metrics, 'total_return', None)
                                    max_dd = getattr(metrics, 'max_drawdown', None)
                                    if total_return is not None:
                                        pct_str = f"{total_return * 100:.2f}%"
                                    if max_dd is not None:
                                        mdd_str = f"{max_dd * 100:.2f}%"
                    except Exception as e:
                        logger.debug(f"{code} {p}日回测失败: {e}")

                    self.backtest_table.setItem(i, j, QTableWidgetItem(pct_str))
                    self.backtest_table.setItem(i, j + len(checked_periods), QTableWidgetItem(mdd_str))

            self.backtest_result.setText("回测完成(基于UnifiedBacktestEngine真实回测)")
        except Exception as e:
            logger.warning(f"回测执行失败: {e}")
            for i in range(len(self.selected_stocks)):
                for j in range(len(checked_periods) * 2):
                    self.backtest_table.setItem(i, j, QTableWidgetItem("--"))
            self.backtest_result.setText(f"回测失败: {e}")

    def simtrade(self):
        # 简单实盘模拟：买入所有选股，持仓跟踪
        if not self.selected_stocks:
            QMessageBox.information(self, "提示", "请先选股！")
            return
        self.simtrade_positions = {s: {"买入价": round(
            100+10*i, 2), "持仓": 100} for i, s in enumerate(self.selected_stocks)}
        msg = "实盘模拟已建仓：\n"
        for s, info in self.simtrade_positions.items():
            msg += f"{s} 买入价:{info['买入价']} 持仓:{info['持仓']}\n"
        QMessageBox.information(self, "实盘模拟", msg)

    def realtrade(self):
        # 实盘API下单（模拟）
        if not self.selected_stocks:
            QMessageBox.information(self, "提示", "请先选股！")
            return
        results = []
        for s in self.selected_stocks:
            code = s.split()[0]
            res = self.trade_api.buy(code, 100)  # 假设每只买100股
            results.append(f"{code} 下单结果: {res}")
        QMessageBox.information(self, "实盘下单", "\n".join(results))

    def autotune(self):
        # 多信号多目标调优，支持自定义信号参数区间，预留分布式加速接口
        signals = list(self.signal_config.keys())
        target = self.tune_target_combo.currentText()
        best_param = None
        best_score = -1e9 if target == "最大收益" or target == "夏普比率" else 1e9
        best_signal = None
        result = "信号\t参数\t目标值\n"
        tasks = []
        with ThreadPoolExecutor(os.cpu_count() * 2) as executor:
            for sig in signals:
                base_param = self.signal_config[sig]
                range_dict = base_param.get('__range__', {})
                # 若有区间则遍历区间，否则只用当前参数
                if range_dict:
                    keys = list(range_dict.keys())
                    from itertools import product
                    ranges = [range(range_dict[k][0], range_dict[k][1]+1)
                              for k in keys]
                    for vals in product(*ranges):
                        param = dict(base_param)
                        for k, v in zip(keys, vals):
                            param[k] = v
                        param['__range__'] = range_dict
                        tasks.append((sig, param))
                elif "fast" in base_param and "slow" in base_param:
                    for p1 in range(max(5, base_param["fast"]-2), base_param["fast"]+3):
                        for p2 in range(max(10, base_param["slow"]-2), base_param["slow"]+3):
                            param = dict(base_param)
                            param["fast"] = p1
                            param["slow"] = p2
                            tasks.append((sig, param))
                else:
                    tasks.append((sig, dict(base_param)))
            # 分布式加速（本地线程池）
            futures = []
            for sig, param in tasks:
                futures.append(executor.submit(
                    self._simulate_score, sig, param, target))
            for i, fut in enumerate(as_completed(futures)):
                try:
                    sig, param, score = fut.result()
                    result += f"{sig}\t{param}\t{score:.3f}\n"
                    if (target == "最大收益" and score > best_score) or (target == "最小回撤" and score < best_score) or (target == "夏普比率" and score > best_score):
                        best_score = score
                        best_param = param
                        best_signal = sig
                except Exception as e:
                    logger.info(f"调优子任务异常: {str(e)}")
        if best_signal:
            self.signal_config[best_signal] = best_param
            save_signal_config(self.signal_config)
            QMessageBox.information(
                self, "调优完成", f"最优信号: {best_signal}, 参数: {best_param}, {target}: {best_score:.3f}")
        self.backtest_result.setText(result)

    def _simulate_score(self, sig, param, target):
        try:
            price_df = None
            if self.data_manager and hasattr(self.data_manager, 'get_kdata'):
                price_df = self.data_manager.get_kdata('000001')
            if price_df is not None and not price_df.empty and 'close' in price_df.columns:
                returns = price_df['close'].pct_change().dropna()
                if target == "最大收益":
                    score = float(returns.sum() * 100)
                elif target == "最小回撤":
                    cummax = price_df['close'].cummax()
                    drawdown = (price_df['close'] - cummax) / cummax
                    score = float(abs(drawdown.min()) * 100)
                else:
                    if returns.std() > 0:
                        score = float((returns.mean() / returns.std()) * (252 ** 0.5))
                    else:
                        score = 0.0
                return sig, param, round(score, 4)
        except Exception as e:
            logger.warning(f"评分计算: 无法基于真实数据计算 {sig} 的 {target}: {e}")

        logger.warning(f"评分计算: 无可用真实价格数据，{sig} 返回0.0")
        return sig, param, 0.0

    def export_report(self):
        # 导出更丰富的回测报告
        rows = []
        for i in range(self.backtest_table.rowCount()):
            row = []
            for j in range(self.backtest_table.columnCount()):
                item = self.backtest_table.item(i, j)
                row.append(item.text() if item else "")
            rows.append(row)
        df = pd.DataFrame(rows, columns=[self.backtest_table.horizontalHeaderItem(
            j).text() for j in range(self.backtest_table.columnCount())])
        # 增加信号参数、调优目标、最优参数等信息
        report = f"## 回测报告\n\n### 信号参数\n{json.dumps(self.signal_config, ensure_ascii=False, indent=2)}\n\n"
        report += f"### 调优目标\n{self.tune_target_combo.currentText()}\n\n"
        report += f"### 回测结果\n{df.to_markdown(index=False)}\n\n"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出回测报告", "", "Markdown Files (*.md);;Excel Files (*.xlsx);;CSV Files (*.csv)")
        if file_path:
            if file_path.endswith('.xlsx'):
                df.to_excel(file_path, index=False)
            elif file_path.endswith('.md'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(report)
            else:
                df.to_csv(file_path, index=False)
            QMessageBox.information(self, "导出成功", "回测报告已导出")
