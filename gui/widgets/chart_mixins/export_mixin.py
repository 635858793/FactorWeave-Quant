from loguru import logger
"""
导出功能Mixin - 处理图表导出、数据导出和剪贴板操作
"""
from typing import Optional, List, Dict, Any, Tuple
import io
import json
import pandas as pd
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QApplication
from PyQt5.QtGui import QPixmap

class ExportMixin:
    """导出功能Mixin类 - 负责图表导出、数据导出和剪贴板操作"""

    def save_chart_image(self):
        """保存图表为图片"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存图表", "", "PNG Files (*.png);;JPEG Files (*.jpg);;PDF Files (*.pdf)")
            if file_path:
                self.figure.savefig(file_path)
                logger.info(f"图表已保存到: {file_path}")
        except Exception as e:
            logger.error(f"保存图表失败: {str(e)}")

    def export_kline_and_indicators(self):
        """导出K线和指标数据"""
        try:
            if self.current_kdata is None or self.current_kdata.empty:
                QMessageBox.warning(self, "提示", "当前无K线数据可导出！")
                return
            df = self.current_kdata.copy()
            # 合并所有已绘制指标（假设指标已添加为df列）
            # 可扩展：遍历self.active_indicators，合并指标数据
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出K线/指标数据", "", "CSV Files (*.csv)")
            if file_path:
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
                logger.info(f"K线/指标数据已导出到: {file_path}")
        except Exception as e:
            logger.error(f"导出K线/指标数据失败: {str(e)}")

    def copy_chart_to_clipboard(self):
        """复制图表到剪贴板"""
        try:
            buf = io.BytesIO()
            self.figure.savefig(buf, format='png')
            buf.seek(0)
            pixmap = QPixmap()
            pixmap.loadFromData(buf.read(), 'PNG')
            QApplication.clipboard().setPixmap(pixmap)
            logger.info("图表已复制到剪贴板")
        except Exception as e:
            logger.error(f"复制图表到剪贴板失败: {str(e)}")

    def trigger_stat_dialog(self):
        """触发统计对话框 - 统计当前缩放区间或鼠标选区"""
        try:
            if self.current_kdata is None or self.current_kdata.empty:
                QMessageBox.warning(self, "提示", "当前无K线数据可统计！")
                return
            # 取当前X轴可见范围
            xlim = self.price_ax.get_xlim()
            start_idx = int(max(0, round(xlim[0])))
            end_idx = int(min(len(self.current_kdata)-1, round(xlim[1])))
            self.request_stat_dialog.emit((start_idx, end_idx))
        except Exception as e:
            logger.error(f"区间统计失败: {str(e)}")

    def export_chart_data(self, format_type: str = "csv") -> bool:
        """导出图表数据

        Args:
            format_type: 导出格式，支持 "csv", "json", "excel"

        Returns:
            bool: 导出是否成功
        """
        try:
            if self.current_kdata is None or self.current_kdata.empty:
                QMessageBox.warning(self, "提示", "当前无数据可导出！")
                return False

            # 准备导出数据
            export_data = self.current_kdata.copy()

            # 添加指标数据（如果有）
            if hasattr(self, 'active_indicators') and self.active_indicators:
                for indicator in self.active_indicators:
                    name = indicator.get('name', '')
                    if name and hasattr(self, f'_indicator_{name.lower()}_data'):
                        indicator_data = getattr(
                            self, f'_indicator_{name.lower()}_data')
                        if isinstance(indicator_data, dict):
                            for key, series in indicator_data.items():
                                export_data[f"{name}_{key}"] = series
                        else:
                            export_data[name] = indicator_data

            # 根据格式选择文件对话框
            if format_type == "csv":
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "导出CSV数据", "", "CSV Files (*.csv)")
                if file_path:
                    export_data.to_csv(file_path, index=True,
                                       encoding='utf-8-sig')
            elif format_type == "json":
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "导出JSON数据", "", "JSON Files (*.json)")
                if file_path:
                    export_data.to_json(
                        file_path, orient='index', date_format='iso')
            elif format_type == "excel":
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "导出Excel数据", "", "Excel Files (*.xlsx)")
                if file_path:
                    export_data.to_excel(file_path, index=True)
            else:
                QMessageBox.warning(self, "错误", f"不支持的导出格式: {format_type}")
                return False

            if file_path:
                logger.info(f"数据已导出到: {file_path}")
                return True
            return False

        except Exception as e:
            logger.error(f"导出数据失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")
            return False

    def export_signals_data(self) -> bool:
        """导出信号数据

        Returns:
            bool: 导出是否成功
        """
        try:
            if not hasattr(self, 'current_signals') or not self.current_signals:
                QMessageBox.warning(self, "提示", "当前无信号数据可导出！")
                return False

            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出信号数据", "", "CSV Files (*.csv);;JSON Files (*.json)")

            if not file_path:
                return False

            signals_df = pd.DataFrame(self.current_signals)

            if file_path.endswith('.csv'):
                signals_df.to_csv(file_path, index=False, encoding='utf-8-sig')
            elif file_path.endswith('.json'):
                signals_df.to_json(
                    file_path, orient='records', date_format='iso')

            logger.info(f"信号数据已导出到: {file_path}")
            return True

        except Exception as e:
            logger.error(f"导出信号数据失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"导出信号数据失败: {str(e)}")
            return False

    def export_pattern_data(self) -> bool:
        """导出形态数据

        Returns:
            bool: 导出是否成功
        """
        try:
            if not hasattr(self, '_pattern_info') or not self._pattern_info:
                QMessageBox.warning(self, "提示", "当前无形态数据可导出！")
                return False

            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出形态数据", "", "CSV Files (*.csv);;JSON Files (*.json)")

            if not file_path:
                return False

            # 将形态信息转换为DataFrame
            pattern_data = []
            for idx, info in self._pattern_info.items():
                pattern_data.append({
                    'index': idx,
                    'pattern_name': info.get('pattern_name', ''),
                    'signal': info.get('signal', ''),
                    'signal_cn': info.get('signal_cn', ''),
                    'confidence': info.get('confidence', 0),
                    'price': info.get('price', 0),
                    'datetime': info.get('datetime', '')
                })

            patterns_df = pd.DataFrame(pattern_data)

            if file_path.endswith('.csv'):
                patterns_df.to_csv(file_path, index=False,
                                   encoding='utf-8-sig')
            elif file_path.endswith('.json'):
                patterns_df.to_json(
                    file_path, orient='records', date_format='iso')

            logger.info(f"形态数据已导出到: {file_path}")
            return True

        except Exception as e:
            logger.error(f"导出形态数据失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"导出形态数据失败: {str(e)}")
            return False

    def save_chart_as_template(self) -> bool:
        """保存图表为模板

        Returns:
            bool: 保存是否成功
        """
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存图表模板", "", "Template Files (*.json)")

            if not file_path:
                return False

            # 收集图表配置信息
            template_data = {
                'chart_type': getattr(self, 'chart_type', 'candlestick'),
                'period': getattr(self, 'current_period', 'D'),
                'indicators': getattr(self, 'active_indicators', []),
                'theme': self.theme_manager.get_current_theme_name() if hasattr(self, 'theme_manager') else 'default',
                'zoom_level': getattr(self, '_zoom_level', 1.0),
                'crosshair_enabled': getattr(self, 'crosshair_enabled', True),
                'style_config': self._get_chart_style() if hasattr(self, '_get_chart_style') else {}
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(template_data, f, indent=2, ensure_ascii=False)

            logger.info(f"图表模板已保存到: {file_path}")
            return True

        except Exception as e:
            logger.error(f"保存图表模板失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"保存模板失败: {str(e)}")
            return False

    def load_chart_template(self) -> bool:
        """加载图表模板

        Returns:
            bool: 加载是否成功
        """
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "加载图表模板", "", "Template Files (*.json)")

            if not file_path:
                return False

            with open(file_path, 'r', encoding='utf-8') as f:
                template_data = json.load(f)

            # 应用模板配置
            if 'period' in template_data:
                self.current_period = template_data['period']

            if 'indicators' in template_data:
                self.active_indicators = template_data['indicators']

            if 'theme' in template_data and hasattr(self, 'theme_manager'):
                self.theme_manager.set_theme(template_data['theme'])

            if 'zoom_level' in template_data:
                self._zoom_level = template_data['zoom_level']

            if 'crosshair_enabled' in template_data:
                self.crosshair_enabled = template_data['crosshair_enabled']

            # 重新绘制图表（R267: 使用完整数据源）
            if hasattr(self, 'current_kdata') and self.current_kdata is not None:
                self.update_chart({'kdata': self._get_render_kdata() if hasattr(self, '_get_render_kdata') else self.current_kdata})

            logger.info(f"图表模板已加载: {file_path}")
            return True

        except Exception as e:
            logger.error(f"加载图表模板失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"加载模板失败: {str(e)}")
            return False

    def export_chart_report(self) -> bool:
        """导出图表分析报告

        Returns:
            bool: 导出是否成功
        """
        try:
            if self.current_kdata is None or self.current_kdata.empty:
                QMessageBox.warning(self, "提示", "当前无数据可生成报告！")
                return False

            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出分析报告", "", "HTML Files (*.html);;PDF Files (*.pdf)")

            if not file_path:
                return False

            # 生成报告数据
            report_data = self._generate_chart_report_data()

            if file_path.endswith('.html'):
                self._export_html_report(file_path, report_data)
            elif file_path.endswith('.pdf'):
                self._export_pdf_report(file_path, report_data)

            logger.info(f"分析报告已导出到: {file_path}")
            return True

        except Exception as e:
            logger.error(f"导出分析报告失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"导出报告失败: {str(e)}")
            return False

    def _generate_chart_report_data(self) -> dict:
        """生成图表报告数据"""
        try:
            kdata = self.current_kdata
            report_data = {
                'basic_info': {
                    'period': getattr(self, 'current_period', 'D'),
                    'total_bars': len(kdata),
                    'date_range': f"{kdata.index[0]} 至 {kdata.index[-1]}",
                    'price_range': f"{kdata['low'].min():.2f} - {kdata['high'].max():.2f}"
                },
                'price_statistics': {
                    'open_avg': kdata['open'].mean(),
                    'close_avg': kdata['close'].mean(),
                    'high_max': kdata['high'].max(),
                    'low_min': kdata['low'].min(),
                    'volume_avg': kdata['volume'].mean() if 'volume' in kdata.columns else 0
                },
                'indicators': [],
                'signals': getattr(self, 'current_signals', []),
                'patterns': getattr(self, '_pattern_info', {})
            }

            # 添加指标信息
            if hasattr(self, 'active_indicators'):
                for indicator in self.active_indicators:
                    report_data['indicators'].append({
                        'name': indicator.get('name', ''),
                        'params': indicator.get('params', {}),
                        'group': indicator.get('group', '')
                    })

            return report_data

        except Exception as e:
            logger.error(f"生成报告数据失败: {str(e)}")
            return {}

    def _export_html_report(self, file_path: str, report_data: dict):
        """导出HTML格式报告"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>图表分析报告</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 10px; }}
                .section {{ margin: 20px 0; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>图表分析报告</h1>
                <p>生成时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="section">
                <h2>基本信息</h2>
                <p>周期: {report_data['basic_info']['period']}</p>
                <p>K线数量: {report_data['basic_info']['total_bars']}</p>
                <p>时间范围: {report_data['basic_info']['date_range']}</p>
                <p>价格范围: {report_data['basic_info']['price_range']}</p>
            </div>
            
            <div class="section">
                <h2>价格统计</h2>
                <table>
                    <tr><th>指标</th><th>数值</th></tr>
                    <tr><td>平均开盘价</td><td>{report_data['price_statistics']['open_avg']:.2f}</td></tr>
                    <tr><td>平均收盘价</td><td>{report_data['price_statistics']['close_avg']:.2f}</td></tr>
                    <tr><td>最高价</td><td>{report_data['price_statistics']['high_max']:.2f}</td></tr>
                    <tr><td>最低价</td><td>{report_data['price_statistics']['low_min']:.2f}</td></tr>
                    <tr><td>平均成交量</td><td>{report_data['price_statistics']['volume_avg']:.0f}</td></tr>
                </table>
            </div>
            
            <div class="section">
                <h2>技术指标</h2>
                <ul>
                    {"".join([f"<li>{ind['name']} - {ind['params']}</li>" for ind in report_data['indicators']])}
                </ul>
            </div>
            
            <div class="section">
                <h2>信号统计</h2>
                <p>信号总数: {len(report_data['signals'])}</p>
            </div>
        </body>
        </html>
        """

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def _export_pdf_report(self, file_path: str, report_data: dict):
        """导出PDF格式报告"""
        # 这里可以使用reportlab或其他PDF库生成PDF
        # 为简化，先转换为HTML再保存
        html_path = file_path.replace('.pdf', '_temp.html')
        self._export_html_report(html_path, report_data)

        # 提示用户使用浏览器打印为PDF
        QMessageBox.information(self, "提示",
                                f"已生成HTML报告: {html_path}\n"
                                "请使用浏览器打开并打印为PDF格式。")
