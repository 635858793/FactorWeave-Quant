"""
数据质量检查对话框模块
"""
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from typing import Optional, Dict, Any, List
from loguru import logger
import pandas as pd
import numpy as np
from datetime import datetime

from .base_dialog import BaseDialog
from core.real_data_provider import get_real_data_provider

logger = logger

class DataQualityDialog(BaseDialog):
    """数据质量检查对话框"""

    def __init__(self, parent=None, stock_code: str = None):
        self.parent_window = parent
        self.stock_code = stock_code
        super().__init__(
            parent,
            title="数据质量检查",
            min_size=(800, 600),
            settings_key="DataQualityDialog"
        )
        self.setup_ui()

    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)

        # 创建工具栏
        toolbar_layout = QHBoxLayout()

        # 股票选择
        stock_label = QLabel("股票代码:")
        self.stock_combo = QComboBox()
        self.stock_combo.setEditable(True)
        if hasattr(self.parent_window, 'stock_service'):
            # 加载股票列表
            stocks = self.parent_window.stock_service.get_stock_list()
            for stock in stocks[:100]:  # 限制显示数量
                self.stock_combo.addItem(
                    f"{stock['code']} - {stock['name']}", stock['code'])

        # 检查类型
        type_label = QLabel("检查类型:")
        self.check_type_combo = QComboBox()
        self.check_type_combo.addItems(["单股票检查", "批量检查", "全市场检查"])

        # 按钮
        self.check_button = QPushButton("开始检查")
        self.export_button = QPushButton("导出报告")
        self.export_button.setEnabled(False)

        toolbar_layout.addWidget(stock_label)
        toolbar_layout.addWidget(self.stock_combo)
        toolbar_layout.addWidget(type_label)
        toolbar_layout.addWidget(self.check_type_combo)
        toolbar_layout.addWidget(self.check_button)
        toolbar_layout.addWidget(self.export_button)
        toolbar_layout.addStretch()

        layout.addLayout(toolbar_layout)

        # 创建结果显示区域
        self.result_widget = QTabWidget()

        # 质量概览选项卡
        self.overview_tab = self.create_overview_tab()
        self.result_widget.addTab(self.overview_tab, "质量概览")

        # 详细报告选项卡
        self.detail_tab = self.create_detail_tab()
        self.result_widget.addTab(self.detail_tab, "详细报告")

        # 数据图表选项卡
        self.chart_tab = self.create_chart_tab()
        self.result_widget.addTab(self.chart_tab, "数据图表")

        layout.addWidget(self.result_widget)

        # 连接信号
        self.check_button.clicked.connect(self.start_quality_check)
        self.export_button.clicked.connect(self.export_report)
        self.check_type_combo.currentTextChanged.connect(
            self.on_check_type_changed)

        # 如果指定了股票代码，设置默认值
        if self.stock_code:
            self.stock_combo.setCurrentText(self.stock_code)

    def create_overview_tab(self):
        """创建质量概览选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 质量得分显示
        score_layout = QHBoxLayout()

        self.quality_score_label = QLabel("质量得分: --")
        self.quality_score_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #007bff;
                padding: 10px;
                border: 2px solid #007bff;
                border-radius: 10px;
                background-color: #f8f9fa;
            }
        """)

        score_layout.addWidget(self.quality_score_label)
        score_layout.addStretch()

        layout.addLayout(score_layout)

        # 质量指标表格
        self.overview_table = QTableWidget()
        self.overview_table.setColumnCount(3)
        self.overview_table.setHorizontalHeaderLabels(["质量指标", "检查结果", "状态"])
        self.overview_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.overview_table)

        return widget

    def create_detail_tab(self):
        """创建详细报告选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 详细报告文本
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self.detail_text)

        return widget

    def create_chart_tab(self):
        """创建数据图表选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 图表占位符
        self.chart_label = QLabel("数据图表将在检查完成后显示")
        self.chart_label.setAlignment(Qt.AlignCenter)
        self.chart_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #6c757d;
                padding: 50px;
                border: 2px dashed #dee2e6;
                border-radius: 10px;
            }
        """)
        layout.addWidget(self.chart_label)

        return widget

    def on_check_type_changed(self, check_type: str):
        """检查类型改变时的处理"""
        if check_type == "单股票检查":
            self.stock_combo.setEnabled(True)
        else:
            self.stock_combo.setEnabled(False)

    def start_quality_check(self):
        """开始质量检查"""
        try:
            check_type = self.check_type_combo.currentText()

            if check_type == "单股票检查":
                stock_code = self.stock_combo.currentData() or self.stock_combo.currentText()
                if not stock_code:
                    QMessageBox.warning(self, "提示", "请选择股票")
                    return
                self.check_single_stock(stock_code)
            elif check_type == "批量检查":
                self.check_batch_stocks()
            else:  # 全市场检查
                self.check_all_stocks()

        except Exception as e:
            logger.error(f"质量检查失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"质量检查失败: {str(e)}")

    def check_single_stock(self, stock_code: str):
        try:
            progress = QProgressDialog("正在检查数据质量...", "取消", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()

            kdata = None
            if hasattr(self.parent_window, 'stock_service'):
                try:
                    kdata = self.parent_window.stock_service.get_stock_data(stock_code)
                except Exception as e:
                    logger.warning(f"stock_service获取数据失败: {e}")

            if kdata is None or (hasattr(kdata, 'empty') and kdata.empty) or (isinstance(kdata, (list, tuple)) and len(kdata) == 0):
                progress.setLabelText("正在从数据源获取真实数据...")
                kdata = self._fetch_real_kdata(stock_code)

            if kdata is None:
                QMessageBox.warning(self, "提示", f"无法获取股票 {stock_code} 的真实数据，数据源不可用")
                progress.close()
                return

            if hasattr(kdata, 'empty') and kdata.empty:
                QMessageBox.warning(self, "提示", f"股票 {stock_code} 暂无数据")
                progress.close()
                return

            progress.setValue(30)

            report = self.generate_quality_report(kdata, stock_code)

            progress.setValue(70)

            self.update_quality_display(report)

            progress.setValue(100)
            progress.close()

            self.export_button.setEnabled(True)
            self.current_report = report

        except Exception as e:
            logger.error(f"单股票质量检查失败: {str(e)}")
            if 'progress' in locals():
                progress.close()
            raise

    def check_batch_stocks(self):
        stocks_to_check = []
        if hasattr(self.parent_window, 'stock_service'):
            try:
                all_stocks = self.parent_window.stock_service.get_stock_list()
                stocks_to_check = all_stocks[:10]
            except Exception:
                stocks_to_check = []

        if not stocks_to_check:
            try:
                provider = get_real_data_provider()
                real_stocks = provider.get_real_stock_list(limit=10)
                stocks_to_check = [{'code': code, 'name': code} for code in real_stocks]
            except Exception as e:
                logger.warning(f"无法获取股票列表: {e}")

        if not stocks_to_check:
            QMessageBox.warning(self, "提示", "无法获取股票列表，请检查数据源")
            return

        progress = QProgressDialog(
            f"正在批量检查 {len(stocks_to_check)} 只股票...", "取消", 0, len(stocks_to_check), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()

        batch_reports = []
        for i, stock in enumerate(stocks_to_check):
            if progress.wasCanceled():
                break

            stock_code = stock['code']
            progress.setLabelText(f"正在检查 {stock_code} - {stock.get('name', stock_code)}")

            try:
                kdata = self._fetch_real_kdata(stock_code)
                if kdata is not None and not kdata.empty:
                    report = self.generate_quality_report(kdata, stock_code)
                    batch_reports.append(report)
                else:
                    logger.warning(f"股票 {stock_code} 无数据，跳过质量检查")
            except Exception as e:
                logger.warning(f"检查股票 {stock_code} 失败: {str(e)}")

            progress.setValue(i + 1)

        progress.close()

        if batch_reports:
            self.update_batch_display(batch_reports)
            self.export_button.setEnabled(True)
            self.current_report = {"type": "batch", "reports": batch_reports}
        else:
            QMessageBox.warning(self, "提示", "所有股票均无可用数据，无法生成质量报告")

    def check_all_stocks(self):
        """检查全市场股票数据质量"""
        reply = QMessageBox.question(
            self, "确认检查",
            "全市场检查将对所有股票进行数据质量检查，这可能需要较长时间。\n确定要继续吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 这里实现全市场检查逻辑
            QMessageBox.information(self, "提示", "全市场检查功能正在开发中...")

    def _fetch_real_kdata(self, stock_code: str) -> Optional[pd.DataFrame]:
        try:
            provider = get_real_data_provider()
            kdata = provider.get_real_kdata(code=stock_code, freq='D', count=250)
            if kdata is not None and not kdata.empty:
                return kdata
            return None
        except Exception as e:
            logger.warning(f"获取真实K线数据失败 {stock_code}: {e}")
            return None

    def generate_quality_report(self, kdata: pd.DataFrame, stock_code: str) -> Dict[str, Any]:
        report = {
            'stock_code': stock_code,
            'check_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_count': len(kdata),
            'quality_score': 0,
            'checks': []
        }

        total_score = 0
        max_score = 0

        missing_count = int(kdata.isnull().sum().sum())
        completeness_score = max(0, 100 - (missing_count / max(len(kdata), 1) * 100))
        total_score += completeness_score
        max_score += 100

        report['checks'].append({
            'name': '数据完整性',
            'score': completeness_score,
            'status': '良好' if completeness_score > 95 else '需要注意' if completeness_score > 80 else '较差',
            'details': f'缺失数据点: {missing_count}'
        })

        if 'close' in kdata.columns:
            price_changes = kdata['close'].pct_change().dropna()
            extreme_changes = abs(price_changes) > 0.2
            price_score = max(0, 100 - (extreme_changes.sum() / max(len(price_changes), 1) * 100 * 10))
            total_score += price_score
            max_score += 100

            report['checks'].append({
                'name': '价格合理性',
                'score': price_score,
                'status': '良好' if price_score > 90 else '需要注意' if price_score > 70 else '较差',
                'details': f'异常变动天数: {extreme_changes.sum()}'
            })

        if 'volume' in kdata.columns:
            volume_data = kdata['volume'].dropna()
            if len(volume_data) >= 20:
                vol_mean = float(volume_data.mean())
                vol_std = float(volume_data.std())
                if vol_mean > 0:
                    cv = vol_std / vol_mean
                    if cv < 0.1:
                        volume_score = max(0, 100 - 80)
                        vol_status = '较差'
                        vol_details = f'成交量变异系数过低({cv:.2f})，数据可能异常'
                        data_limited = True
                    elif cv < 0.5:
                        volume_score = max(0, 100 - 30)
                        vol_status = '需要注意'
                        vol_details = f'成交量变异系数偏低({cv:.2f})'
                    elif cv > 5.0:
                        volume_score = max(0, 100 - 40)
                        vol_status = '需要注意'
                        vol_details = f'成交量变异系数偏高({cv:.2f})'
                    else:
                        volume_score = 100
                        vol_status = '良好'
                        vol_details = f'成交量变异系数合理({cv:.2f})'
                else:
                    volume_score = 50
                    vol_status = '较差'
                    vol_details = '成交量均值为零，数据异常'
                    data_limited = True
            else:
                volume_score = 60
                vol_status = '需要注意'
                vol_details = f'成交量数据不足(仅{len(volume_data)}条)'
                data_limited = True

            total_score += volume_score
            max_score += 100

            report['checks'].append({
                'name': '交易量合理性',
                'score': volume_score,
                'status': vol_status,
                'details': vol_details
            })

        date_col = None
        if 'date' in kdata.columns:
            date_col = 'date'
        elif 'datetime' in kdata.columns:
            date_col = 'datetime'
        elif isinstance(kdata.index, pd.DatetimeIndex):
            date_col = '_index_date'
            kdata = kdata.copy()
            kdata['_index_date'] = kdata.index

        if date_col:
            date_gaps = pd.to_datetime(kdata[date_col]).diff().dt.days
            large_gaps = int((date_gaps > 7).sum())
            continuity_score = max(0, 100 - (large_gaps / max(len(kdata), 1) * 100 * 5))
            total_score += continuity_score
            max_score += 100

            report['checks'].append({
                'name': '时间连续性',
                'score': continuity_score,
                'status': '良好' if continuity_score > 95 else '需要注意' if continuity_score > 80 else '较差',
                'details': f'大间隔天数: {large_gaps}'
            })

        report['quality_score'] = round(total_score / max_score * 100, 2) if max_score > 0 else 0

        return report

    def update_quality_display(self, report: Dict[str, Any]):
        """更新质量显示"""
        # 更新质量得分
        score = report['quality_score']
        color = "#28a745" if score > 90 else "#ffc107" if score > 70 else "#dc3545"
        self.quality_score_label.setText(f"质量得分: {score:.1f}")
        self.quality_score_label.setStyleSheet(f"""
            QLabel {{
                font-size: 24px;
                font-weight: bold;
                color: {color};
                padding: 10px;
                border: 2px solid {color};
                border-radius: 10px;
                background-color: #f8f9fa;
            }}
        """)

        # 更新概览表格
        self.overview_table.setRowCount(len(report['checks']))
        for i, check in enumerate(report['checks']):
            self.overview_table.setItem(i, 0, QTableWidgetItem(check['name']))
            self.overview_table.setItem(
                i, 1, QTableWidgetItem(f"{check['score']:.1f}"))
            self.overview_table.setItem(
                i, 2, QTableWidgetItem(check['status']))

        # 更新详细报告
        detail_text = f"""
数据质量检查报告
==================

股票代码: {report['stock_code']}
检查时间: {report['check_time']}
数据记录数: {report['data_count']}
总体质量得分: {report['quality_score']:.2f}

详细检查结果:
"""

        for check in report['checks']:
            detail_text += f"""
{check['name']}:
  得分: {check['score']:.2f}
  状态: {check['status']}
  详情: {check['details']}
"""

        self.detail_text.setPlainText(detail_text)

    def update_batch_display(self, reports: List[Dict[str, Any]]):
        """更新批量检查显示"""
        # 计算平均得分
        avg_score = np.mean([r['quality_score'] for r in reports])

        color = "#28a745" if avg_score > 90 else "#ffc107" if avg_score > 70 else "#dc3545"
        self.quality_score_label.setText(f"平均质量得分: {avg_score:.1f}")
        self.quality_score_label.setStyleSheet(f"""
            QLabel {{
                font-size: 24px;
                font-weight: bold;
                color: {color};
                padding: 10px;
                border: 2px solid {color};
                border-radius: 10px;
                background-color: #f8f9fa;
            }}
        """)

        # 更新概览表格显示批量结果
        self.overview_table.setRowCount(len(reports))
        self.overview_table.setColumnCount(4)
        self.overview_table.setHorizontalHeaderLabels(
            ["股票代码", "质量得分", "状态", "问题数"])

        for i, report in enumerate(reports):
            score = report['quality_score']
            status = "优秀" if score > 90 else "良好" if score > 70 else "需要改进"
            problem_count = sum(
                1 for check in report['checks'] if check['score'] < 80)

            self.overview_table.setItem(
                i, 0, QTableWidgetItem(report['stock_code']))
            self.overview_table.setItem(i, 1, QTableWidgetItem(f"{score:.1f}"))
            self.overview_table.setItem(i, 2, QTableWidgetItem(status))
            self.overview_table.setItem(
                i, 3, QTableWidgetItem(str(problem_count)))

        # 更新详细报告
        detail_text = f"""
批量数据质量检查报告
==================

检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
检查股票数: {len(reports)}
平均质量得分: {avg_score:.2f}

各股票详细结果:
"""

        for report in reports:
            detail_text += f"""
{report['stock_code']} - 得分: {report['quality_score']:.2f}
"""

        self.detail_text.setPlainText(detail_text)

    def export_report(self):
        """导出质量报告"""
        try:
            if not hasattr(self, 'current_report'):
                QMessageBox.warning(self, "提示", "没有可导出的报告")
                return

            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出质量报告",
                f"质量报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "文本文件 (*.txt);;Excel文件 (*.xlsx)"
            )

            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.detail_text.toPlainText())

                QMessageBox.information(self, "导出成功", f"报告已导出到: {file_path}")

        except Exception as e:
            logger.error(f"导出报告失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"导出报告失败: {str(e)}")

