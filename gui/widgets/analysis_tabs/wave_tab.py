from loguru import logger
"""
波浪分析标签页 - 专业版升级
"""
import json
from typing import Dict, Any, List, Optional
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QColor, QKeySequence
from .wave_tab_pro import WaveAnalysisTabPro
from datetime import datetime

class WaveAnalysisTab(WaveAnalysisTabPro):
    """波浪分析标签页 - 继承专业版功能，保持向后兼容"""

    def __init__(self, config_manager=None):
        """初始化波浪分析标签页"""
        super().__init__(config_manager)

        # 保持向后兼容的属性
        self.wave_results = []
        self.wave_statistics = {}

        # 连接信号以保持兼容性
        self.analysis_completed.connect(self._on_analysis_completed)

        # R252-G6: 连接错误信号到警告展示，避免分析异常静默
        self.error_occurred.connect(self.show_warning)

    def _on_analysis_completed(self, results):
        """分析完成处理 - 兼容原有接口"""
        try:
            self.hide_loading()
            self.status_label.setText("分析完成")

            if 'error' in results:
                self.error_occurred.emit(results['error'])
                return

            # 更新显示
            self._update_wave_display(results)

            # 发射兼容信号
            if 'elliott_waves' in results:
                self.wave_analysis_completed.emit(results)

        except Exception as e:
            logger.error(f"分析完成处理失败: {e}")

    def _update_wave_display(self, results):
        """更新波浪显示"""
        # 更新艾略特波浪表格
        if 'elliott_waves' in results:
            self._update_elliott_table(results['elliott_waves'])

        # 更新江恩表格
        if 'gann_levels' in results:
            self._update_gann_table(results['gann_levels'])

        # 更新斐波那契表格
        if 'fibonacci_levels' in results:
            self._update_fibonacci_table(results['fibonacci_levels'])

        # 更新预测显示
        if 'wave_prediction' in results:
            self.prediction_text.setText(results['wave_prediction'])

        # 更新综合报告
        if 'comprehensive_report' in results:
            self.report_text.setText(results['comprehensive_report'])

    def _update_elliott_table(self, waves):
        """更新艾略特波浪表格"""
        column_keys = ['wave', 'type', 'start_date', 'end_date',
                       'amplitude', 'time', 'confidence', 'status']

        # 预处理数据
        processed_waves = []
        for wave in waves:
            processed_wave = {
                'wave': str(wave.get('wave', '')),
                'type': str(wave.get('type', '')),
                'start_date': str(wave.get('start', {}).get('date', '')),
                'end_date': str(wave.get('end', {}).get('date', '')),
                'amplitude': f"{wave.get('amplitude', 0)*100:.2f}%",
                'time': str(wave.get('time', '')),
                'confidence': f"{wave.get('confidence', 0):.2f}",
                'status': str(wave.get('status', ''))
            }
            processed_waves.append(processed_wave)

        self.update_table_data(
            self.elliott_table, processed_waves, column_keys)

    def _update_gann_table(self, levels):
        """更新江恩表格"""
        column_keys = ['type', 'angle', 'price', 'time', 'strength', 'status']

        # 预处理数据
        processed_levels = []
        for level in levels:
            processed_level = {
                'type': str(level.get('type', '')),
                'angle': f"{level.get('angle', 0):.1f}°",
                'price': f"{level.get('price', 0):.2f}",
                'time': str(level.get('time', '')),
                'strength': str(level.get('strength', '')),
                'status': str(level.get('status', ''))
            }
            processed_levels.append(processed_level)

        self.update_table_data(self.gann_table, processed_levels, column_keys)

    def _update_fibonacci_table(self, levels):
        """更新斐波那契表格"""
        column_keys = ['ratio', 'price', 'type', 'strength', 'validity']

        # 预处理数据
        processed_levels = []
        for level in levels:
            processed_level = {
                'ratio': str(level.get('ratio', '')),
                'price': f"{level.get('price', 0):.2f}",
                'type': str(level.get('type', '')),
                'strength': str(level.get('strength', '')),
                'validity': str(level.get('validity', ''))
            }
            processed_levels.append(processed_level)

        self.update_table_data(self.fibonacci_table,
                               processed_levels, column_keys)

    # 保持向后兼容的方法
    def analyze_wave(self):
        """执行波浪分析 - 兼容原接口"""
        self.comprehensive_wave_analysis()

    def analyze_elliott_waves(self, period, sensitivity, min_wave, use_fibonacci):
        """分析艾略特波浪 - 兼容原接口"""
        self.elliott_wave_analysis()

    def analyze_gann(self, period, sensitivity):
        """分析江恩理论 - 兼容原接口"""
        self.gann_analysis()

    def analyze_support_resistance(self, period, sensitivity):
        """分析支撑阻力位 - 兼容原接口"""
        self.fibonacci_analysis()

    def clear_wave(self):
        """清除波浪 - 兼容原接口"""
        self._do_clear_data()

    def update_wave_display(self):
        """更新波浪显示 - 兼容原接口"""
        # 如果有最新的分析结果，更新显示
        if hasattr(self, 'latest_results') and self.latest_results:
            self._update_wave_display(self.latest_results)

    def update_wave_statistics(self):
        """更新波浪统计 - 兼容原接口"""
        # 计算统计信息
        self.wave_statistics = {
            'elliott_count': len(self.elliott_waves),
            'gann_count': len(self.gann_levels),
            'fibonacci_count': len(self.fibonacci_levels),
            'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def export_wave_analysis(self):
        """导出波浪分析 - 兼容原接口"""
        self.export_results()

    def find_extremes(self, high_prices, low_prices, window):
        """寻找极值点 - 兼容原接口"""
        return self._find_extremes(high_prices, low_prices)

    def count_tests(self, prices, level, tolerance):
        """计算测试次数 - 兼容原接口"""
        count = 0
        for price in prices:
            if abs(price - level) / level <= tolerance:
                count += 1
        return count

    def refresh_data(self):
        """刷新数据 - 兼容原接口"""
        self._do_refresh_data()

    def clear_data(self):
        """清除数据 - 兼容原接口"""
        self._do_clear_data()

    # 向后兼容的信号
    wave_analysis_completed = pyqtSignal(dict)
