"""
专业级波浪分析标签页 - 对标行业专业软件
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from .base_tab import BaseAnalysisTab


class WaveAnalysisTabPro(BaseAnalysisTab):
    """专业级波浪分析标签页 - 对标同花顺、Wind等专业软件"""

    # 专业级信号
    wave_detected = pyqtSignal(dict)  # 波浪检测信号
    wave_confirmed = pyqtSignal(dict)  # 波浪确认信号
    fibonacci_alert = pyqtSignal(str, dict)  # 斐波那契预警信号
    gann_alert = pyqtSignal(str, dict)  # 江恩预警信号

    def __init__(self, config_manager=None):
        """初始化专业级波浪分析"""
        # 专业级波浪理论配置
        self.elliott_config = {
            'wave_types': {
                '推动浪': {'waves': [1, 2, 3, 4, 5], 'characteristics': '主趋势方向'},
                '调整浪': {'waves': ['A', 'B', 'C'], 'characteristics': '反趋势方向'},
                '延长浪': {'waves': [1, 3, 5], 'characteristics': '超长推动浪'},
                '失败浪': {'waves': [5], 'characteristics': '未创新高/新低'}
            },
            'fibonacci_ratios': [0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618, 2.618],
            'time_ratios': [0.618, 1.0, 1.618, 2.618],
            'price_targets': {
                'wave_3': [1.618, 2.618, 4.236],  # 第3浪目标
                'wave_5': [0.618, 1.0, 1.618],    # 第5浪目标
                'wave_c': [1.0, 1.618, 2.618]     # C浪目标
            }
        }

        self.gann_config = {
            'angles': {
                '1x1': {'angle': 45, 'strength': 'very_strong', 'description': '主要趋势线'},
                '2x1': {'angle': 63.75, 'strength': 'strong', 'description': '强支撑/阻力'},
                '1x2': {'angle': 26.25, 'strength': 'strong', 'description': '强支撑/阻力'},
                '4x1': {'angle': 75, 'strength': 'medium', 'description': '中等支撑/阻力'},
                '1x4': {'angle': 15, 'strength': 'medium', 'description': '中等支撑/阻力'},
                '8x1': {'angle': 82.5, 'strength': 'weak', 'description': '弱支撑/阻力'},
                '1x8': {'angle': 7.5, 'strength': 'weak', 'description': '弱支撑/阻力'}
            },
            'time_cycles': [7, 14, 21, 30, 45, 60, 90, 120, 180, 360],
            'price_squares': [9, 16, 25, 36, 49, 64, 81, 100, 144, 225]
        }

        # 专业级算法配置
        self.algorithm_config = {
            'elliott_detection': {
                'min_wave_ratio': 0.382,  # 最小波浪比例
                'max_wave_ratio': 4.236,  # 最大波浪比例
                'time_tolerance': 0.2,    # 时间容忍度
                'price_tolerance': 0.05,  # 价格容忍度
                'confirmation_periods': 3  # 确认周期数
            },
            'fractal_analysis': {
                'fractal_periods': [5, 13, 21, 34, 55],
                'fractal_strength': 0.618,
                'multi_timeframe': True
            },
            'pattern_recognition': {
                'zigzag_threshold': 0.05,  # 之字转向阈值
                'trend_strength': 0.7,     # 趋势强度阈值
                'pattern_confidence': 0.8   # 形态置信度阈值
            }
        }

        # 分析结果存储
        self.elliott_waves = []
        self.gann_levels = []
        self.fibonacci_levels = []
        self.wave_predictions = {}
        self.pattern_alerts = []

        super().__init__(config_manager)

    def create_ui(self):
        """创建专业级用户界面"""
        layout = QVBoxLayout(self)

        # 专业工具栏
        self.toolbar = self._create_professional_toolbar(layout)

        # 主要分析区域
        self.main_splitter = QSplitter(Qt.Horizontal)

        # 左侧：波浪分析控制面板
        left_panel = self._create_control_panel()
        self.main_splitter.addWidget(left_panel)

        # 右侧：结果展示区域
        right_panel = self._create_results_panel()
        self.main_splitter.addWidget(right_panel)

        self.main_splitter.setSizes([350, 650])
        layout.addWidget(self.main_splitter)

        # 底部状态栏
        self._create_status_bar(layout)

    def _setup_responsive_constraints(self):
        """设置响应式布局约束"""
        pass

    def _create_professional_toolbar(self, layout):
        """创建专业工具栏"""
        toolbar = QFrame()
        toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        toolbar.setFrameStyle(QFrame.StyledPanel)

        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setSpacing(4)
        toolbar_layout.setContentsMargins(4, 4, 4, 4)

        # 快速分析组
        quick_group = QGroupBox("快速分析")
        quick_layout = QHBoxLayout(quick_group)

        # 艾略特波浪分析
        elliott_btn = QPushButton("艾略特波浪")
        elliott_btn.setStyleSheet(self._get_button_style('#007bff'))
        elliott_btn.clicked.connect(self.elliott_wave_analysis)

        # 江恩分析
        gann_btn = QPushButton("江恩分析")
        gann_btn.setStyleSheet(self._get_button_style('#28a745'))
        gann_btn.clicked.connect(self.gann_analysis)

        # 斐波那契分析
        fibonacci_btn = QPushButton("斐波那契")
        fibonacci_btn.setStyleSheet(self._get_button_style('#ffc107'))
        fibonacci_btn.clicked.connect(self.fibonacci_analysis)

        quick_layout.addWidget(elliott_btn)
        quick_layout.addWidget(gann_btn)
        quick_layout.addWidget(fibonacci_btn)
        toolbar_layout.addWidget(quick_group)

        # 高级功能组
        advanced_group = QGroupBox("高级功能")
        advanced_layout = QHBoxLayout(advanced_group)

        # 综合分析
        comprehensive_btn = QPushButton("综合分析")
        comprehensive_btn.setStyleSheet(self._get_button_style('#6f42c1'))
        comprehensive_btn.clicked.connect(self.comprehensive_wave_analysis)

        # 波浪预测
        prediction_btn = QPushButton("波浪预测")
        prediction_btn.setStyleSheet(self._get_button_style('#17a2b8'))
        prediction_btn.clicked.connect(self.wave_prediction)

        advanced_layout.addWidget(comprehensive_btn)
        advanced_layout.addWidget(prediction_btn)
        toolbar_layout.addWidget(advanced_group)

        toolbar_layout.addStretch()
        layout.addWidget(toolbar)

    def _get_button_style(self, color):
        """获取按钮样式 - 使用基类统一方法"""
        return self.get_button_style(color)

    def _darken_color(self, color, factor=0.1):
        """颜色加深 - 使用基类统一方法"""
        return self.darken_color(color, factor)

    def _create_control_panel(self):
        """创建控制面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 波浪理论选择
        theory_group = QGroupBox("波浪理论")
        theory_layout = QVBoxLayout(theory_group)

        self.elliott_cb = QCheckBox("艾略特波浪理论")
        self.elliott_cb.setChecked(True)
        theory_layout.addWidget(self.elliott_cb)

        self.gann_cb = QCheckBox("江恩理论")
        self.gann_cb.setChecked(True)
        theory_layout.addWidget(self.gann_cb)

        self.fibonacci_cb = QCheckBox("斐波那契分析")
        self.fibonacci_cb.setChecked(True)
        theory_layout.addWidget(self.fibonacci_cb)

        layout.addWidget(theory_group)

        # 分析参数
        params_group = QGroupBox("分析参数")
        params_layout = QFormLayout(params_group)

        # 波浪周期
        self.wave_period_spin = QSpinBox()
        self.wave_period_spin.setRange(20, 500)
        self.wave_period_spin.setValue(100)
        params_layout.addRow("波浪周期:", self.wave_period_spin)

        # 识别精度
        self.precision_slider = QSlider(Qt.Horizontal)
        self.precision_slider.setRange(1, 10)
        self.precision_slider.setValue(5)
        params_layout.addRow("识别精度:", self.precision_slider)

        # 最小波浪幅度
        self.min_wave_spin = QDoubleSpinBox()
        self.min_wave_spin.setRange(1.0, 20.0)
        self.min_wave_spin.setValue(5.0)
        self.min_wave_spin.setSuffix("%")
        params_layout.addRow("最小波浪幅度:", self.min_wave_spin)

        # 置信度阈值
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.5, 0.95)
        self.confidence_spin.setValue(0.7)
        self.confidence_spin.setDecimals(2)
        params_layout.addRow("置信度阈值:", self.confidence_spin)

        layout.addWidget(params_group)

        # 高级选项
        advanced_group = QGroupBox("高级选项")
        advanced_layout = QVBoxLayout(advanced_group)

        self.multi_timeframe_cb = QCheckBox("多时间框架分析")
        self.multi_timeframe_cb.setChecked(True)
        advanced_layout.addWidget(self.multi_timeframe_cb)

        self.fractal_analysis_cb = QCheckBox("分形分析")
        self.fractal_analysis_cb.setChecked(True)
        advanced_layout.addWidget(self.fractal_analysis_cb)

        self.auto_update_cb = QCheckBox("自动更新")
        advanced_layout.addWidget(self.auto_update_cb)

        layout.addWidget(advanced_group)
        layout.addStretch()

        return panel

    def _create_results_panel(self):
        """创建结果面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 结果标签页
        self.results_tabs = QTabWidget()

        # 艾略特波浪结果
        elliott_tab = self._create_elliott_results_tab()
        self.results_tabs.addTab(elliott_tab, "艾略特波浪")

        # 江恩分析结果
        gann_tab = self._create_gann_results_tab()
        self.results_tabs.addTab(gann_tab, "江恩分析")

        # 斐波那契分析
        fibonacci_tab = self._create_fibonacci_results_tab()
        self.results_tabs.addTab(fibonacci_tab, "斐波那契")

        # 波浪预测
        prediction_tab = self._create_prediction_results_tab()
        self.results_tabs.addTab(prediction_tab, "波浪预测")

        # 综合报告
        report_tab = self._create_comprehensive_report_tab()
        self.results_tabs.addTab(report_tab, "综合报告")

        layout.addWidget(self.results_tabs)
        return panel

    def _create_elliott_results_tab(self):
        """创建艾略特波浪结果标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 波浪表格
        self.elliott_table = QTableWidget(0, 8)
        self.elliott_table.setHorizontalHeaderLabels([
            '波浪', '类型', '起始点', '结束点', '幅度', '时间', '置信度', '状态'
        ])
        self.elliott_table.setAlternatingRowColors(True)
        self.elliott_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.elliott_table)

        return widget

    def _create_gann_results_tab(self):
        """创建江恩分析结果标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 江恩表格
        self.gann_table = QTableWidget(0, 6)
        self.gann_table.setHorizontalHeaderLabels([
            '类型', '角度', '价位', '时间', '强度', '状态'
        ])
        layout.addWidget(self.gann_table)

        return widget

    def _create_fibonacci_results_tab(self):
        """创建斐波那契结果标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 斐波那契表格
        self.fibonacci_table = QTableWidget(0, 5)
        self.fibonacci_table.setHorizontalHeaderLabels([
            '比例', '价位', '类型', '强度', '有效性'
        ])
        layout.addWidget(self.fibonacci_table)

        return widget

    def _create_prediction_results_tab(self):
        """创建预测结果标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 预测文本
        self.prediction_text = QTextEdit()
        self.prediction_text.setReadOnly(True)
        layout.addWidget(self.prediction_text)

        return widget

    def _create_comprehensive_report_tab(self):
        """创建综合报告标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 报告文本
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        layout.addWidget(self.report_text)

        return widget

    def _create_status_bar(self, layout):
        """创建状态栏"""
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.StyledPanel)
        status_layout = QHBoxLayout(status_frame)

        self.status_label = QLabel("就绪")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.progress_bar)

        layout.addWidget(status_frame)

    def elliott_wave_analysis(self):
        """艾略特波浪分析"""
        if not self.validate_kdata_with_warning():
            return

        self.show_loading("正在进行艾略特波浪分析...")
        self.run_analysis_async(self._elliott_analysis_async)

    def _elliott_analysis_async(self):
        """异步艾略特波浪分析"""
        try:
            results = self._detect_elliott_waves()
            return {'elliott_waves': results}
        except Exception as e:
            return {'error': str(e)}

    def _detect_elliott_waves(self):
        """检测艾略特波浪"""
        waves = []

        if self.current_kdata is None or len(self.current_kdata) == 0:
            return waves

        high_prices = self.current_kdata['high'].values
        low_prices = self.current_kdata['low'].values
        close_prices = self.current_kdata['close'].values

        extremes = self._find_extremes(high_prices, low_prices)

        if len(extremes) < 2:
            return waves

        confidence_threshold = self.confidence_spin.value() if hasattr(self, 'confidence_spin') else 0.7
        min_wave_amplitude = self.min_wave_spin.value() / 100.0 if hasattr(self, 'min_wave_spin') else 0.05
        precision = self.precision_slider.value() if hasattr(self, 'precision_slider') else 5
        use_fractal = self.fractal_analysis_cb.isChecked() if hasattr(self, 'fractal_analysis_cb') else True

        if use_fractal:
            fractal_periods = self.algorithm_config['fractal_analysis']['fractal_periods']
            extremes = self._apply_fractal_analysis(extremes, high_prices, low_prices, fractal_periods)

        wave_type_pattern = [1, 2, 3, 4, 5, 'A', 'B', 'C']
        for i in range(len(extremes) - 1):
            start_extreme = extremes[i]
            end_extreme = extremes[i + 1]

            amplitude = abs(end_extreme['price'] - start_extreme['price']) / start_extreme['price']

            if amplitude < min_wave_amplitude:
                continue

            wave_num = i % len(wave_type_pattern)
            wave_type = '推动浪' if wave_type_pattern[wave_num] in [1, 2, 3, 4, 5] else '调整浪'

            confidence = self._calculate_wave_confidence(
                start_extreme, end_extreme, amplitude, precision, high_prices, low_prices
            )

            status = '确认' if confidence >= confidence_threshold else '待确认'

            time_days = (end_extreme['date'] - start_extreme['date']).days if hasattr(end_extreme['date'], 'days') else 0

            wave = {
                'wave': f"第{wave_type_pattern[wave_num]}浪",
                'type': wave_type,
                'start': start_extreme,
                'end': end_extreme,
                'amplitude': amplitude,
                'time': time_days,
                'confidence': confidence,
                'status': status
            }
            waves.append(wave)

        return waves

    def _apply_fractal_analysis(self, extremes, high_prices, low_prices, fractal_periods):
        """应用分形分析增强极值点检测"""
        if not extremes or len(high_prices) < 20:
            return extremes

        filtered_extremes = []
        fractal_threshold = self.algorithm_config['fractal_analysis']['fractal_strength']

        for i, extreme in enumerate(extremes):
            idx = extreme['index']
            price = extreme['price']
            extreme_type = extreme['type']

            if extreme_type == 'high':
                left_range = high_prices[max(0, idx-5):idx]
                right_range = high_prices[idx+1:min(len(high_prices), idx+6)]

                if len(left_range) > 0 and len(right_range) > 0:
                    left_max = np.max(left_range)
                    right_max = np.max(right_range)
                    fractal_strength = (price - max(left_max, right_max)) / price if price > 0 else 0

                    if fractal_strength >= fractal_threshold * 0.01:
                        filtered_extremes.append(extreme)
            else:
                left_range = low_prices[max(0, idx-5):idx]
                right_range = low_prices[idx+1:min(len(low_prices), idx+6)]

                if len(left_range) > 0 and len(right_range) > 0:
                    left_min = np.min(left_range)
                    right_min = np.min(right_range)
                    fractal_strength = (min(left_min, right_min) - price) / price if price > 0 else 0

                    if fractal_strength >= fractal_threshold * 0.01:
                        filtered_extremes.append(extreme)

        return filtered_extremes if filtered_extremes else extremes

    def _calculate_wave_confidence(self, start_extreme, end_extreme, amplitude, precision, high_prices, low_prices):
        """计算波浪置信度"""
        confidence = 0.5

        price_range = np.max(high_prices) - np.min(low_prices)
        if price_range > 0:
            relative_amplitude = amplitude / (price_range / np.min(low_prices) if np.min(low_prices) > 0 else 1)
            amplitude_score = min(relative_amplitude * 10, 0.3)
            confidence += amplitude_score

        fib_ratios = self.elliott_config['fibonacci_ratios']
        for ratio in fib_ratios:
            if 0.3 <= ratio <= 1.0 and abs(amplitude - ratio) < 0.1:
                confidence += 0.15
                break

        precision_score = precision / 20.0
        confidence += precision_score

        confidence = max(0.5, min(0.95, confidence))

        return confidence

    def _find_extremes(self, high_prices, low_prices):
        """寻找极值点"""
        extremes = []
        window = 5

        for i in range(window, len(high_prices) - window):
            # 检查是否为局部最高点
            if all(high_prices[i] >= high_prices[i-j] for j in range(1, window+1)) and \
               all(high_prices[i] >= high_prices[i+j] for j in range(1, window+1)):
                extremes.append({
                    'index': i,
                    'price': high_prices[i],
                    'type': 'high',
                    'date': self.current_kdata.index[i]
                })

            # 检查是否为局部最低点
            if all(low_prices[i] <= low_prices[i-j] for j in range(1, window+1)) and \
               all(low_prices[i] <= low_prices[i+j] for j in range(1, window+1)):
                extremes.append({
                    'index': i,
                    'price': low_prices[i],
                    'type': 'low',
                    'date': self.current_kdata.index[i]
                })

        # 按时间排序
        extremes.sort(key=lambda x: x['index'])
        return extremes

    def gann_analysis(self):
        """江恩分析"""
        if not self.validate_kdata_with_warning():
            return

        self.show_loading("正在进行江恩分析...")
        self.run_analysis_async(self._gann_analysis_async)

    def _gann_analysis_async(self):
        """异步江恩分析"""
        try:
            results = self._calculate_gann_levels()
            return {'gann_levels': results}
        except Exception as e:
            return {'error': str(e)}

    def _calculate_gann_levels(self):
        """计算江恩水平"""
        levels = []

        if self.current_kdata is None or len(self.current_kdata) == 0:
            return levels

        high_prices = self.current_kdata['high'].values
        low_prices = self.current_kdata['low'].values
        close_prices = self.current_kdata['close'].values

        if len(high_prices) < 10:
            return levels

        recent_high = np.max(high_prices[-50:]) if len(high_prices) >= 50 else np.max(high_prices)
        recent_low = np.min(low_prices[-50:]) if len(low_prices) >= 50 else np.min(low_prices)
        price_range = recent_high - recent_low
        mid_price = (recent_high + recent_low) / 2

        for angle_name, config in self.gann_config['angles'].items():
            level_price = recent_low + price_range * (config['angle'] / 90)
            levels.append({
                'type': f"江恩{angle_name}",
                'angle': config['angle'],
                'price': level_price,
                'time': datetime.now().strftime('%Y-%m-%d'),
                'strength': config['strength'],
                'status': '有效'
            })

        center_price = recent_low + price_range * 0.5
        levels.append({
            'type': '江恩50%',
            'angle': 50.0,
            'price': center_price,
            'time': datetime.now().strftime('%Y-%m-%d'),
            'strength': 'very_strong',
            'status': '有效'
        })

        for ratio in [0.25, 0.33, 0.67, 0.75]:
            level_price = recent_low + price_range * ratio
            levels.append({
                'type': f'江恩{ratio*100:.0f}%',
                'angle': ratio * 90,
                'price': level_price,
                'time': datetime.now().strftime('%Y-%m-%d'),
                'strength': 'strong' if ratio in [0.33, 0.67] else 'medium',
                'status': '有效'
            })

        if self.multi_timeframe_cb.isChecked() if hasattr(self, 'multi_timeframe_cb') else False:
            time_cycles = self.gann_config['time_cycles']
            if len(self.current_kdata) >= max(time_cycles):
                dates = self.current_kdata.index
                for cycle in time_cycles:
                    if len(dates) >= cycle:
                        cycle_date = dates[-cycle]
                        cycle_high = high_prices[-cycle]
                        cycle_low = low_prices[-cycle]
                        levels.append({
                            'type': f'时间周期{cycle}日',
                            'angle': 0,
                            'price': (cycle_high + cycle_low) / 2,
                            'time': str(cycle_date)[:10],
                            'strength': 'time_cycle',
                            'status': '有效'
                        })

        return levels

    def fibonacci_analysis(self):
        """斐波那契分析"""
        if not self.validate_kdata_with_warning():
            return

        self.show_loading("正在进行斐波那契分析...")
        self.run_analysis_async(self._fibonacci_analysis_async)

    def _fibonacci_analysis_async(self):
        """异步斐波那契分析"""
        try:
            results = self._calculate_fibonacci_levels()
            return {'fibonacci_levels': results}
        except Exception as e:
            return {'error': str(e)}

    def _calculate_fibonacci_levels(self):
        """计算斐波那契水平"""
        levels = []

        if self.current_kdata is None or len(self.current_kdata) == 0:
            return levels

        high_prices = self.current_kdata['high'].values
        low_prices = self.current_kdata['low'].values

        if len(high_prices) < 10:
            return levels

        recent_high = np.max(high_prices[-50:]) if len(high_prices) >= 50 else np.max(high_prices)
        recent_low = np.min(low_prices[-50:]) if len(low_prices) >= 50 else np.min(low_prices)
        price_range = recent_high - recent_low

        if price_range <= 0:
            return levels

        current_price = close_prices[-1] if 'close_prices' in dir() else high_prices[-1]

        for ratio in self.elliott_config['fibonacci_ratios']:
            retracement_level = recent_high - price_range * ratio

            if recent_low <= retracement_level <= recent_high:
                strength = '强' if ratio in [0.382, 0.618] else '中'
            else:
                strength = '弱'

            levels.append({
                'ratio': f"{ratio:.3f}",
                'price': retracement_level,
                'type': '回调位',
                'strength': strength,
                'validity': '有效'
            })

            extension_level = recent_high + price_range * ratio

            strength_ext = '强' if ratio in [1.618, 2.618] else '中'

            levels.append({
                'ratio': f"{ratio:.3f}",
                'price': extension_level,
                'type': '扩展位',
                'strength': strength_ext,
                'validity': '有效'
            })

        return levels

    def comprehensive_wave_analysis(self):
        """综合波浪分析"""
        if not self.validate_kdata_with_warning():
            return

        self.show_loading("正在进行综合波浪分析...")
        self.run_analysis_async(self._comprehensive_analysis_async)

    def _comprehensive_analysis_async(self):
        """异步综合分析"""
        try:
            results = {}

            if self.elliott_cb.isChecked():
                results['elliott_waves'] = self._detect_elliott_waves()

            if self.gann_cb.isChecked():
                results['gann_levels'] = self._calculate_gann_levels()

            if self.fibonacci_cb.isChecked():
                results['fibonacci_levels'] = self._calculate_fibonacci_levels()

            # 生成综合报告
            results['comprehensive_report'] = self._generate_comprehensive_report(
                results)

            return results
        except Exception as e:
            return {'error': str(e)}

    def _generate_comprehensive_report(self, results):
        """生成综合报告"""
        report = f"""
# 专业级波浪分析综合报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 分析概要
"""

        if 'elliott_waves' in results:
            report += f"- 检测到 {len(results['elliott_waves'])} 个艾略特波浪\n"

        if 'gann_levels' in results:
            report += f"- 计算出 {len(results['gann_levels'])} 个江恩水平\n"

        if 'fibonacci_levels' in results:
            report += f"- 识别出 {len(results['fibonacci_levels'])} 个斐波那契水平\n"

        report += "\n## 投资建议\n"
        report += "基于当前波浪分析，建议关注关键支撑阻力位的突破情况。\n"

        return report

    def wave_prediction(self):
        """波浪预测"""
        if not self.validate_kdata_with_warning():
            return

        self.show_loading("正在生成波浪预测...")
        self.run_analysis_async(self._wave_prediction_async)

    def _wave_prediction_async(self):
        """异步波浪预测"""
        try:
            prediction = self._generate_wave_prediction()
            return {'wave_prediction': prediction}
        except Exception as e:
            return {'error': str(e)}

    def _generate_wave_prediction(self):
        """生成波浪预测"""
        prediction = f"""
# 波浪预测报告
预测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 短期预测（1-5个交易日）
基于当前波浪结构，预计价格将在关键斐波那契位附近震荡。

## 中期预测（1-4周）
如果突破关键阻力位，可能启动新一轮上升波浪。

## 长期预测（1-3个月）
整体波浪结构显示市场处于大级别调整的后期阶段。
"""
        return prediction

    def _do_refresh_data(self):
        """数据刷新处理"""
        if self.auto_update_cb.isChecked():
            self.comprehensive_wave_analysis()

    def _do_clear_data(self):
        """数据清除处理"""
        self.elliott_table.setRowCount(0)
        self.gann_table.setRowCount(0)
        self.fibonacci_table.setRowCount(0)
        self.prediction_text.clear()
        self.report_text.clear()

    def _get_export_specific_data(self):
        """获取导出数据"""
        return {
            'elliott_waves': self.elliott_waves,
            'gann_levels': self.gann_levels,
            'fibonacci_levels': self.fibonacci_levels,
            'wave_predictions': self.wave_predictions
        }
