from loguru import logger
"""
技术分析标签页 - 增强版
"""
import time
import traceback
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QColor, QKeySequence, QFont
from .base_tab import BaseAnalysisTab
from core.indicator_service import (
    calculate_indicator, get_all_indicators_metadata, get_indicator_metadata, get_indicator_categories, get_talib_category
)
from core.indicator_adapter import (
    get_all_indicators_by_category, get_indicator_english_name, get_indicator_params_config,
    get_talib_indicator_list, get_talib_chinese_name, get_indicator_category_by_name
)
from datetime import datetime
import json
from core.indicator_service import IndicatorService

class BatchCalculateWorker(QThread):
    """后台批量计算工作线程"""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(list, float, int, int)
    error = pyqtSignal(str)
    
    def __init__(self, indicators: List[str], kdata: pd.DataFrame, params_map: Dict, parent=None):
        super().__init__(parent)
        self.indicators = indicators
        self.kdata = kdata
        self.params_map = params_map
        self._is_cancelled = False
    
    def run(self):
        try:
            from core.containers import get_service_container
            container = get_service_container()
            service = container.resolve(IndicatorService)
            
            start_time = time.time()
            self.progress.emit(10, "正在初始化批量计算...")
            
            self.progress.emit(20, f"正在计算 {len(self.indicators)} 个指标...")
            
            batch_result = service.batch_calculate_indicators(
                self.indicators,
                self.kdata.copy(),
                {name: self.params_map.get(name, {}) for name in self.indicators}
            )
            
            if self._is_cancelled:
                return
            
            self.progress.emit(60, "正在提取计算结果...")
            
            processed_results = {}
            calculated_count = 0
            error_count = 0
            
            if batch_result is not None and not batch_result.empty:
                for indicator_name in self.indicators:
                    try:
                        processed_result = self._extract_indicator_from_batch(
                            indicator_name, batch_result
                        )
                        
                        if processed_result and processed_result.get('values'):
                            processed_results[indicator_name] = processed_result
                            calculated_count += 1
                        else:
                            error_count += 1
                    except Exception as e:
                        error_count += 1
            else:
                error_count = len(self.indicators)
            
            self.progress.emit(80, "正在准备表格数据...")
            
            table_rows = self._prepare_table_rows(processed_results)
            
            self.progress.emit(95, "计算完成...")
            
            end_time = time.time()
            calculation_time = end_time - start_time
            
            self.finished.emit(table_rows, calculation_time, calculated_count, error_count)
            
        except Exception as e:
            self.error.emit(str(e))
    
    def cancel(self):
        self._is_cancelled = True
    
    def _extract_indicator_from_batch(self, indicator_name: str, batch_result: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """从批量计算结果中提取单个指标的结果"""
        try:
            english_name = get_indicator_english_name(indicator_name)
            english_lower = english_name.lower() if english_name else indicator_name.lower()
            
            processed = {
                "name": indicator_name,
                "timestamp": datetime.now(),
                "values": {},
                "signals": [],
                "summary": {}
            }
            
            original_columns = {'open', 'high', 'low', 'close', 'volume', 'date', 'datetime'}
            
            for col in batch_result.columns:
                col_lower = col.lower()
                if col_lower not in original_columns:
                    if english_lower in col_lower or col_lower.startswith(english_lower[:3]):
                        col_data = batch_result[col]
                        if isinstance(col_data, pd.Series):
                            valid_data = col_data.dropna()
                            if len(valid_data) > 0:
                                processed["values"][col] = col_data
            
            if not processed["values"]:
                for col in batch_result.columns:
                    col_lower = col.lower()
                    if col_lower not in original_columns:
                        col_data = batch_result[col]
                        if isinstance(col_data, pd.Series):
                            valid_data = col_data.dropna()
                            if len(valid_data) > 0:
                                processed["values"][col] = col_data
            
            if processed["values"]:
                summary_stats = {}
                for col_name, col_data in processed["values"].items():
                    if pd.api.types.is_numeric_dtype(col_data):
                        valid_data = col_data.dropna()
                        if len(valid_data) > 0:
                            summary_stats[col_name] = {
                                'mean': float(valid_data.mean()),
                                'std': float(valid_data.std()),
                                'min': float(valid_data.min()),
                                'max': float(valid_data.max()),
                                'last': float(valid_data.iloc[-1]),
                                'count': len(valid_data)
                            }
                processed["summary"] = summary_stats
            
            return processed
            
        except Exception as e:
            return None
    
    def _prepare_table_rows(self, processed_results: Dict) -> List[Dict]:
        """在后台线程准备表格行数据"""
        table_rows = []
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        for indicator_name, result in processed_results.items():
            values = result.get("values", {})
            summary = result.get("summary", {})
            
            if not values:
                table_rows.append({
                    'time': current_time,
                    'name': indicator_name,
                    'value': "无数据",
                    'signal': "",
                    'strength': "",
                    'trend': "",
                    'advice': "计算完成但无返回值",
                    'note': "请检查参数设置"
                })
                continue
            
            for value_name, value_data in values.items():
                try:
                    current_value, trend_info, strength_info = self._analyze_value_data(value_data)
                    
                    if current_value is not None:
                        display_name = self._get_display_name(indicator_name, value_name)
                        value_str = self._format_value(current_value)
                        signal_info, advice = self._generate_signal_advice(
                            indicator_name, value_name, current_value, trend_info)
                        
                        note = f"周期: {len(value_data) if hasattr(value_data, '__len__') else 'N/A'}"
                        
                        table_rows.append({
                            'time': current_time,
                            'name': display_name,
                            'value': value_str,
                            'signal': signal_info,
                            'strength': strength_info,
                            'trend': trend_info,
                            'advice': advice,
                            'note': note
                        })
                except Exception as e:
                    table_rows.append({
                        'time': current_time,
                        'name': f"{indicator_name}-{value_name}",
                        'value': "错误",
                        'signal': "",
                        'strength': "",
                        'trend': "",
                        'advice': str(e),
                        'note': ""
                    })
        
        return table_rows
    
    def _analyze_value_data(self, value_data) -> Tuple[Any, str, str]:
        """分析数值数据，返回(当前值, 趋势, 强度)"""
        current_value = None
        trend_info = ""
        strength_info = ""
        
        if isinstance(value_data, np.ndarray):
            if len(value_data) > 0 and np.issubdtype(value_data.dtype, np.number):
                valid_indices = ~np.isnan(value_data)
                if np.any(valid_indices):
                    valid_data = value_data[valid_indices]
                    current_value = valid_data[-1]
                    
                    if len(valid_data) >= 2:
                        if valid_data[-1] > valid_data[-2]:
                            trend_info = "上升 ↑"
                        elif valid_data[-1] < valid_data[-2]:
                            trend_info = "下降 ↓"
                        else:
                            trend_info = "持平 →"
                        
                        if valid_data[-2] != 0:
                            change_pct = abs((valid_data[-1] - valid_data[-2]) / valid_data[-2] * 100)
                            if change_pct > 5:
                                strength_info = "强"
                            elif change_pct > 2:
                                strength_info = "中"
                            else:
                                strength_info = "弱"
        
        elif isinstance(value_data, pd.Series):
            if len(value_data) > 0:
                valid_data = value_data.dropna()
                if len(valid_data) > 0:
                    current_value = valid_data.iloc[-1]
                    
                    if pd.api.types.is_numeric_dtype(valid_data) and len(valid_data) >= 2:
                        prev_value = valid_data.iloc[-2]
                        if valid_data.iloc[-1] > prev_value:
                            trend_info = "上升 ↑"
                        elif valid_data.iloc[-1] < prev_value:
                            trend_info = "下降 ↓"
                        else:
                            trend_info = "持平 →"
                        
                        if prev_value != 0:
                            change_pct = abs((valid_data.iloc[-1] - prev_value) / prev_value * 100)
                            if change_pct > 5:
                                strength_info = "强"
                            elif change_pct > 2:
                                strength_info = "中"
                            else:
                                strength_info = "弱"
        
        elif isinstance(value_data, (int, float)):
            if not np.isnan(value_data):
                current_value = value_data
                if abs(current_value) > 50:
                    strength_info = "强"
                elif abs(current_value) > 20:
                    strength_info = "中"
                else:
                    strength_info = "弱"
        
        return current_value, trend_info, strength_info
    
    def _get_display_name(self, indicator_name: str, value_name: str) -> str:
        """获取显示名称"""
        if value_name == "main" or value_name == indicator_name:
            return indicator_name
        
        name_mappings = {
            "MACD指标": {"MACD_1": "MACD线", "MACD_2": "信号线", "MACD_3": "柱状图"},
            "布林带": {"BBANDS_1": "上轨", "BBANDS_2": "中轨", "BBANDS_3": "下轨"},
            "随机指标": {"STOCH_1": "%K线", "STOCH_2": "%D线"},
            "KDJ指标": {"STOCH_1": "K值", "STOCH_2": "D值", "STOCH_3": "J值"},
        }
        
        if indicator_name in name_mappings and value_name in name_mappings[indicator_name]:
            return f"{indicator_name}-{name_mappings[indicator_name][value_name]}"
        return f"{indicator_name}-{value_name}"
    
    def _format_value(self, value) -> str:
        """格式化数值显示"""
        try:
            if isinstance(value, (int, float)):
                if abs(value) >= 1000000:
                    return f"{value/1000000:.2f}M"
                elif abs(value) >= 1000:
                    return f"{value/1000:.2f}K"
                elif abs(value) >= 1:
                    return f"{value:.2f}"
                else:
                    return f"{value:.4f}"
            return str(value)
        except Exception:
            return str(value)
    
    def _generate_signal_advice(self, indicator_name: str, value_name: str, 
                                 current_value: float, trend_info: str) -> Tuple[str, str]:
        """生成信号和建议"""
        signal_info = ""
        advice = "N/A"
        
        indicator_lower = indicator_name.lower()
        
        if 'rsi' in indicator_lower:
            if current_value > 80:
                signal_info = "超买"
                advice = "考虑卖出"
            elif current_value < 20:
                signal_info = "超卖"
                advice = "考虑买入"
            else:
                signal_info = "中性"
                advice = "观望"
        
        elif 'macd' in indicator_lower:
            if trend_info == "上升 ↑":
                signal_info = "多头"
                advice = "趋势向上"
            elif trend_info == "下降 ↓":
                signal_info = "空头"
                advice = "趋势向下"
            else:
                signal_info = "震荡"
                advice = "方向不明"
        
        elif 'kdj' in indicator_lower or 'stoch' in indicator_lower:
            if current_value > 80:
                signal_info = "超买"
                advice = "注意回调"
            elif current_value < 20:
                signal_info = "超卖"
                advice = "可能反弹"
            else:
                signal_info = "正常"
                advice = "观望"
        
        else:
            if trend_info == "上升 ↑":
                signal_info = "上升"
                advice = "关注"
            elif trend_info == "下降 ↓":
                signal_info = "下降"
                advice = "谨慎"
            else:
                signal_info = "平稳"
                advice = "N/A"
        
        return signal_info, advice


class TechnicalAnalysisTab(BaseAnalysisTab):
    """技术分析标签页 - 增强版"""

    indicator_calculated = pyqtSignal(str, dict)

    def __init__(self, config_manager=None):
        """初始化技术分析标签页"""
        self.indicator_cache = {}
        self.indicator_results = {}
        self.batch_indicators = []
        self.auto_calculate = True
        self._calculation_worker = None

        super().__init__(config_manager)

    def _setup_responsive_constraints(self):
        """使用统一的响应式约束系统注册组件"""
        # 从create_ui保存的组件引用中注册
        if hasattr(self, 'control_group'):
            self._register_responsive_component('control_group', self.control_group)
        if hasattr(self, 'category_combo'):
            self._register_responsive_component('combo', self.category_combo)
        if hasattr(self, 'indicator_combo'):
            self._register_responsive_component('combo', self.indicator_combo)
        if hasattr(self, 'calc_btn'):
            self._register_responsive_component('button', self.calc_btn)
        if hasattr(self, 'clear_indicators_btn'):
            self._register_responsive_component('button', self.clear_indicators_btn)
        if hasattr(self, 'cache_btn'):
            self._register_responsive_component('button', self.cache_btn)

    def create_ui(self):
        """创建用户界面 - 修复版，解决UI重叠问题"""
        layout = QVBoxLayout(self)
        layout.setSpacing(2)

        # 指标选择和控制区域
        self.control_group = QGroupBox("指标控制")
        self.control_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        control_layout = QHBoxLayout(self.control_group)
        control_layout.setSpacing(2)

        # 左侧：指标选择 - 更紧凑的布局
        indicator_card = QFrame()
        indicator_card.setFrameStyle(QFrame.StyledPanel)
        indicator_layout = QVBoxLayout(indicator_card)
        indicator_layout.setSpacing(4)
        indicator_layout.setContentsMargins(6, 6, 6, 6)

        # 指标分类选择 - 紧凑布局
        category_layout = QHBoxLayout()
        category_layout.setSpacing(4)
        category_layout.addWidget(QLabel("分类:"))
        self.category_combo = QComboBox()
        # self.category_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        category_indicators = get_all_indicators_by_category(use_chinese=True)
        categories = ["全部"] + list(category_indicators.keys())
        self.category_combo.addItems(categories)
        self.category_combo.currentTextChanged.connect(self.on_category_changed)
        category_layout.addWidget(self.category_combo)
        indicator_layout.addLayout(category_layout)

        # 指标选择组合框 - 显示所有ta-lib指标
        self.indicator_combo = QComboBox()
        # self.indicator_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.indicator_combo.setEditable(False)
        self.indicator_combo.setInsertPolicy(QComboBox.NoInsert)
        self.populate_indicators("全部")
        self.indicator_combo.currentTextChanged.connect(self.on_indicator_changed)
        self.indicator_combo.setToolTip("选择要计算的技术指标，支持搜索")
        indicator_layout.addWidget(self.indicator_combo)

        # 批量选择 - 水平紧凑布局
        batch_layout = QHBoxLayout()
        batch_layout.setSpacing(6)
        self.batch_checkbox = QCheckBox("批量计算")
        self.batch_checkbox.setToolTip("选择多个指标进行批量计算")
        self.batch_checkbox.stateChanged.connect(self.toggle_batch_mode)

        self.auto_calc_checkbox = QCheckBox("自动计算")
        self.auto_calc_checkbox.setChecked(True)
        self.auto_calc_checkbox.setToolTip("数据更新时自动重新计算指标")
        self.auto_calc_checkbox.stateChanged.connect(self.toggle_auto_calculate)

        batch_layout.addWidget(self.batch_checkbox)
        batch_layout.addWidget(self.auto_calc_checkbox)
        batch_layout.addStretch()
        indicator_layout.addLayout(batch_layout)

        # 计算按钮 - 紧凑布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)

        calc_btn = QPushButton("计算指标")
        calc_btn.setStyleSheet(
            "QPushButton { background-color: #007bff; color: white; font-weight: bold; padding: 4px 8px; height: 20px; }")
        calc_btn.clicked.connect(self.calculate_indicators)
        calc_btn.setToolTip("根据当前设置计算选定的技术指标\n快捷键：Ctrl+Enter")

        clear_indicators_btn = QPushButton("清除")
        clear_indicators_btn.setStyleSheet(
            "QPushButton { background-color: #6c757d; color: white; font-weight: bold; padding: 4px 8px; height: 20px; }")
        clear_indicators_btn.clicked.connect(self.clear_indicators)
        clear_indicators_btn.setToolTip("清除所有已计算的技术指标")

        # 新增：缓存管理按钮
        cache_btn = QPushButton("清缓存")
        cache_btn.setStyleSheet(
            "QPushButton { background-color: #ffc107; color: black; font-weight: bold; padding: 4px 8px; height: 20px; }")
        cache_btn.clicked.connect(self.clear_cache)
        cache_btn.setToolTip("清除指标计算缓存")

        button_layout.addWidget(calc_btn)
        button_layout.addWidget(clear_indicators_btn)
        button_layout.addWidget(cache_btn)
        indicator_layout.addLayout(button_layout)

        control_layout.addWidget(indicator_card, stretch=2)

        # 右侧：动态参数设置 - 使用统一响应式约束
        params_card = QFrame()
        params_card.setFrameStyle(QFrame.StyledPanel)

        # 使用滚动区域来确保所有参数都能显示
        params_scroll_area = QScrollArea()
        params_scroll_area.setWidgetResizable(True)
        params_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        params_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        params_scroll_area.setFrameStyle(QFrame.NoFrame)

        # 参数容器
        params_container = QWidget()
        self.params_layout = QVBoxLayout(params_container)
        self.params_layout.setSpacing(3)
        self.params_layout.setContentsMargins(6, 6, 6, 6)

        # 参数预设 - 紧凑布局
        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(4)
        preset_layout.addWidget(QLabel("预设:"))
        self.preset_combo = QComboBox()
        self.preset_combo.setFixedWidth(100)
        self.preset_combo.addItems(["自定义", "短期交易", "中期投资", "长期投资"])
        self.preset_combo.currentTextChanged.connect(self.apply_preset_params)
        preset_layout.addWidget(self.preset_combo)
        preset_layout.addStretch()
        self.params_layout.addLayout(preset_layout)

        # 动态参数区域
        self.dynamic_params_widget = QWidget()
        self.dynamic_params_layout = QVBoxLayout(self.dynamic_params_widget)
        self.dynamic_params_layout.setSpacing(2)
        self.dynamic_params_layout.setContentsMargins(0, 0, 0, 0)
        self.params_layout.addWidget(self.dynamic_params_widget)

        # 参数信息显示区域 - 使用统一约束
        info_group = QGroupBox("参数信息")
        info_layout = QVBoxLayout(info_group)
        info_layout.setContentsMargins(4, 4, 4, 4)

        self.param_info_label = QLabel("选择指标后显示参数说明")
        self.param_info_label.setWordWrap(True)
        info_layout.addWidget(self.param_info_label)

        self.params_layout.addWidget(info_group)
        self.params_layout.addStretch()

        # 设置滚动区域
        params_scroll_area.setWidget(params_container)

        # 将滚动区域添加到主卡片
        params_card_layout = QVBoxLayout(params_card)
        params_card_layout.setContentsMargins(2, 2, 2, 2)
        params_card_layout.addWidget(params_scroll_area)

        # 参数控件字典
        self.param_controls = {}

        # 初始化参数界面
        if self.indicator_combo.count() > 0:
            if not self.indicator_combo.currentText():
                self.indicator_combo.setCurrentIndex(0)
            current_indicator = self.indicator_combo.currentText()
            if current_indicator:
                self.update_parameter_interface(current_indicator)
        else:
            self.update_parameter_interface()

        control_layout.addWidget(params_card, stretch=3)
        layout.addWidget(self.control_group)

        # 结果显示区域 - 使用伸缩布局
        results_group = QGroupBox("计算结果")
        results_layout = QVBoxLayout(results_group)
        results_layout.setSpacing(6)

        # 统计信息和控制按钮 - 顶部工具栏
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(4)

        # 统计信息
        self.stats_label = QLabel("统计信息: 无数据")
        self.stats_label.setStyleSheet("QLabel { font-weight: bold; color: #495057; }")
        toolbar_layout.addWidget(self.stats_label)

        self.performance_label = QLabel("性能: 无统计")
        self.performance_label.setStyleSheet("QLabel { font-weight: bold; color: #6c757d; }")
        toolbar_layout.addWidget(self.performance_label)

        toolbar_layout.addStretch()

        # 筛选控制按钮 - 减少按钮数量以节省空间
        filter_group = QWidget()
        filter_layout = QHBoxLayout(filter_group)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(4)

        # 高级筛选按钮
        self.advanced_filter_btn = QPushButton("筛选")
        self.advanced_filter_btn.clicked.connect(self.show_advanced_filter_dialog)

        # 清除筛选按钮
        self.clear_filter_btn = QPushButton("清除")
        self.clear_filter_btn.clicked.connect(self.clear_table_filters)
        self.clear_filter_btn.setEnabled(False)

        filter_layout.addWidget(self.advanced_filter_btn)
        filter_layout.addWidget(self.clear_filter_btn)

        # 筛选状态标签
        self.filter_status_label = QLabel("")
        # self.filter_status_label.setStyleSheet("QLabel { color: #28a745; font-weight: bold; font-size: 11px; }")
        filter_layout.addWidget(self.filter_status_label)

        toolbar_layout.addWidget(filter_group)
        results_layout.addLayout(toolbar_layout)

        # 结果表格 - 使用伸缩布局，让表格占用剩余空间
        self.technical_table = QTableWidget(0, 8)
        self.technical_table.setHorizontalHeaderLabels([
            '日期', '指标', '数值', '信号', '强度', '趋势', '建议', '备注'
        ])
        self.technical_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.technical_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.technical_table.setAlternatingRowColors(True)
        self.technical_table.setSortingEnabled(True)

        # 设置列宽
        header = self.technical_table.horizontalHeader()
        header.setStretchLastSection(True)

        # 设置行高
        self.technical_table.verticalHeader().setDefaultSectionSize(30)  # 减少行高
        self.technical_table.verticalHeader().setVisible(False)

        results_layout.addWidget(self.technical_table, stretch=1)  # 表格占用剩余空间

        # 导出按钮 - 使用统一约束
        export_group = self.create_export_section()
        results_layout.addWidget(export_group)

        layout.addWidget(results_group, stretch=1)  # 结果区域占用剩余空间

    def populate_indicators(self, category: str):
        """根据分类填充指标选择框 - 增强版，整合形态数据"""
        self.indicator_combo.clear()

        try:
            # 获取统一指标服务实例
            unified_service = None
            if category == "全部":
                # 获取所有技术指标
                indicators = []
                try:
                    categories = get_all_indicators_by_category(use_chinese=True)
                    for cat, inds in categories.items():
                        if isinstance(inds, list):
                            indicators.extend(inds)

                    # 添加形态数据
                    from core.unified_indicator_service import get_unified_service
                    unified_service = get_unified_service()
                    patterns = unified_service.get_all_patterns()
                    for pattern in patterns:
                        pattern_name = pattern.get('name', pattern.get('english_name', ''))
                        if pattern_name and pattern_name not in indicators:
                            indicators.append(pattern_name)

                    indicators.sort()
                    logger.info(f"加载所有指标和形态，共 {len(indicators)} 个")
                except Exception as e:
                    logger.error(f"获取所有指标失败: {e}")
                    indicators = ["MA", "MACD", "RSI", "KDJ", "BOLL"]
            elif category == "形态识别" or "形态" in category:
                # 专门获取形态数据
                try:
                    from core.unified_indicator_service import get_unified_service
                    unified_service = get_unified_service()
                    patterns = unified_service.get_all_patterns()
                    indicators = []
                    for pattern in patterns:
                        pattern_name = pattern.get('name', pattern.get('english_name', ''))
                        if pattern_name:
                            indicators.append(pattern_name)

                    indicators.sort()
                    logger.info(f"加载形态数据，共 {len(indicators)} 个形态")

                    if not indicators:
                        # 如果没有形态数据，添加一些默认形态提示
                        indicators = ["锤头线", "十字星", "吞没形态", "三白兵"]
                        logger.warning("数据库中没有形态数据，使用默认形态列表")
                except Exception as e:
                    logger.error(f"获取形态数据失败: {e}")
                    indicators = ["锤头线", "十字星", "吞没形态"]
            else:
                # 获取特定分类的技术指标
                try:
                    categories = get_all_indicators_by_category(use_chinese=True)
                    indicators = categories.get(category, [])
                    if isinstance(indicators, list):
                        indicators.sort()
                    else:
                        indicators = []

                    # 检查是否需要添加该分类的形态数据
                    if category in ["趋势分析", "震荡指标", "成交量指标"]:
                        try:
                            patterns = unified_service.get_patterns_by_category(category)
                            for pattern in patterns:
                                pattern_name = pattern.get('name', pattern.get('english_name', ''))
                                if pattern_name:
                                    indicators.append(pattern_name)
                        except Exception as e:
                            logger.error(f"获取分类 {category} 的形态数据失败: {e}")

                    logger.info(f"加载分类 {category} 的指标，共 {len(indicators)} 个")
                except Exception as e:
                    logger.error(f"获取分类指标失败: {e}")
                    indicators = []

            # 添加指标到组合框
            if indicators:
                self.indicator_combo.addItems(indicators)
                self.indicator_combo.setCurrentIndex(0)
            else:
                logger.warning(f"分类 {category} 没有可用的指标")

        except Exception as e:
            logger.error(f"填充指标列表失败: {str(e)}")
            # 添加一些基本指标作为备选
            self.indicator_combo.addItems(["MA", "MACD", "RSI", "KDJ", "BOLL"])

    def on_category_changed(self, category: str):
        """分类改变时更新指标列表"""
        self.populate_indicators(category)
        if self.indicator_combo.count() > 0:
            self.indicator_combo.setCurrentIndex(0)
            # 手动触发指标变化处理，确保参数界面更新
            current_indicator = self.indicator_combo.currentText()
            if current_indicator:
                self.on_indicator_changed(current_indicator)

    def on_indicator_changed(self, indicator_name: str):
        """指标改变时更新参数界面"""
        if not indicator_name:
            return

        # 更新参数界面
        self.update_parameter_interface(indicator_name)

        # 更新工具提示
        english_name = get_indicator_english_name(indicator_name)
        config = get_indicator_params_config(english_name)

        # 添加空值检查
        if config is None:
            # 如果没有配置，创建一个默认的配置
            config = {
                "inputs": ["close"],
                "params": {},
                "description": f"指标: {indicator_name}"
            }

        inputs = config.get("inputs", ["close"])

        tooltip = f"指标: {indicator_name}\n"
        tooltip += f"英文名: {english_name}\n"
        tooltip += f"输入数据: {', '.join(inputs)}\n"

        if config.get("params"):
            tooltip += "参数:\n"
            for param_name, param_config in config["params"].items():
                tooltip += f"  {param_name}: {param_config.get('desc', '')}\n"

        self.indicator_combo.setToolTip(tooltip)

        # 发射信号通知父组件
        try:
            if hasattr(self, 'parent_widget') and self.parent_widget:
                self.parent_widget.indicator_changed.emit(indicator_name)
        except Exception as e:
            logger.error(f"指标变更处理失败: {e}")

    def update_parameter_interface(self, indicator_name: str = None):
        """更新参数设置界面 - 紧凑专业版，带参数信息显示"""
        # 清除现有参数控件
        for i in reversed(range(self.dynamic_params_layout.count())):
            child = self.dynamic_params_layout.itemAt(i).widget()
            if child:
                child.setParent(None)

        self.param_controls.clear()

        if not indicator_name:
            indicator_name = self.indicator_combo.currentText()

        if not indicator_name:
            # 更新参数信息显示
            if hasattr(self, 'param_info_label'):
                self.param_info_label.setText("请选择一个指标查看参数设置")
            return

        logger.info(f"更新参数界面: {indicator_name}")

        try:
            # 检查是否是形态指标 - 通过数据库查询判断
            from core.unified_indicator_service import get_unified_service
            unified_service = get_unified_service()
            patterns = unified_service.get_all_patterns()
            pattern_names = [p.get('name', p.get('english_name', '')) for p in patterns]

            if indicator_name in pattern_names:
                self._setup_pattern_parameters(indicator_name)
                return

            # 获取指标的英文名称和配置
            english_name = get_indicator_english_name(indicator_name)
            config = get_indicator_params_config(english_name)

            if not config or not config.get("params"):
                logger.warning(f"指标 {indicator_name} 无参数配置")
                if hasattr(self, 'param_info_label'):
                    self.param_info_label.setText(f"指标 {indicator_name} 无需设置参数")
                return

            # 更新参数信息显示
            info_text = f"指标: {indicator_name} ({english_name})\n"
            info_text += f"输入数据: {', '.join(config.get('inputs', ['close']))}\n"
            info_text += f"输出数量: {len(config.get('outputs', []))}"

            if hasattr(self, 'param_info_label'):
                self.param_info_label.setText(info_text)

            logger.info(f"指标 {indicator_name} 参数配置: {list(config['params'].keys())}")

            # 创建参数控件 - 紧凑布局
            for param_name, param_config in config["params"].items():
                param_widget = QWidget()
                param_layout = QHBoxLayout(param_widget)
                param_layout.setSpacing(4)
                param_layout.setContentsMargins(4, 2, 4, 2)

                # 参数标签 - 紧凑
                param_label = QLabel(f"{param_config.get('desc', param_name)}:")
                param_label.setMinimumWidth(80)
                param_label.setMaximumWidth(120)
                # param_label.setStyleSheet(
                #     "QLabel { font-size: 11px; color: #212529; }")
                param_layout.addWidget(param_label)

                # 参数控件 - 紧凑
                if param_name in ["matype", "fastmatype", "slowmatype", "signalmatype", "slowk_matype", "slowd_matype", "fastd_matype"]:
                    # MA类型选择
                    control = QComboBox()
                    control.setMinimumHeight(20)
                    control.setMaximumHeight(32)
                    ma_types = ["SMA", "EMA", "WMA", "DEMA",
                                "TEMA", "TRIMA", "KAMA", "MAMA", "T3"]
                    control.addItems(ma_types)
                    control.setCurrentIndex(param_config.get("default", 0))
                    control.setStyleSheet(
                        "QComboBox { font-size: 11px; padding: 2px; }")
                elif isinstance(param_config.get("default"), float):
                    # 浮点数参数
                    control = QDoubleSpinBox()
                    control.setMinimumHeight(20)
                    control.setMaximumHeight(32)
                    control.setRange(param_config.get("min", 0.0),
                                     param_config.get("max", 100.0))
                    control.setValue(param_config.get("default", 1.0))
                    control.setSingleStep(0.01)
                    control.setDecimals(3)

                else:
                    # 整数参数
                    control = QSpinBox()
                    control.setMinimumHeight(20)
                    control.setMaximumHeight(32)
                    control.setRange(param_config.get("min", 1),
                                     param_config.get("max", 1000))
                    control.setValue(param_config.get("default", 14))


                # 添加工具提示
                tooltip = param_config.get("desc", param_name)
                if param_config.get("range"):
                    tooltip += f"\n范围: {param_config['range']}"
                control.setToolTip(tooltip)

                param_layout.addWidget(control)

                # 保存控件引用
                self.param_controls[param_name] = control

                # 添加到布局
                self.dynamic_params_layout.addWidget(param_widget)

            logger.info(f"已创建 {len(self.param_controls)} 个参数控件")

        except Exception as e:
            logger.error(f"更新参数界面失败: {str(e)}")
            if hasattr(self, 'param_info_label'):
                self.param_info_label.setText(f"参数界面更新失败: {str(e)}")

    def _setup_pattern_parameters(self, pattern_indicator_name: str):
        """设置形态指标的参数"""
        try:
            pattern_name = pattern_indicator_name  # 直接使用指标名称，无需移除前缀

            # 获取统一指标服务实例
            from core.unified_indicator_service import get_unified_service
            unified_service = get_unified_service()
            # 尝试获取形态配置
            pattern_config = None
            patterns = unified_service.get_all_patterns()
            for pattern in patterns:
                if pattern.get('name') == pattern_name or pattern.get('english_name') == pattern_name:
                    pattern_config = pattern
                    break

            if pattern_config:
                # 更新参数信息显示
                info_text = f"形态: {pattern_name}\n"
                info_text += f"类别: {pattern_config.get('category', '未知')}\n"
                info_text += f"信号类型: {pattern_config.get('signal_type', '未知')}\n"
                info_text += f"描述: {pattern_config.get('description', '无描述')}"

                if hasattr(self, 'param_info_label'):
                    self.param_info_label.setText(info_text)

                # 创建形态参数控件
                parameters = pattern_config.get('parameters', {})
                if parameters:
                    for param_name, param_value in parameters.items():
                        param_widget = QWidget()
                        param_layout = QHBoxLayout(param_widget)
                        param_layout.setSpacing(4)
                        param_layout.setContentsMargins(4, 2, 4, 2)

                        # 参数标签
                        param_label = QLabel(f"{param_name}:")
                        param_label.setMinimumWidth(80)
                        # param_label.setStyleSheet("QLabel { font-size: 11px; color: #212529; }")
                        param_layout.addWidget(param_label)

                        # 参数控件
                        if isinstance(param_value, float):
                            control = QDoubleSpinBox()
                            control.setMinimumHeight(20)
                            control.setMaximumHeight(32)
                            control.setRange(0.0, 1.0)
                            control.setValue(param_value)
                            control.setSingleStep(0.01)
                            control.setDecimals(3)
                        else:
                            control = QSpinBox()
                            control.setMinimumHeight(20)
                            control.setMaximumHeight(32)
                            control.setRange(1, 100)
                            control.setValue(int(param_value) if isinstance(param_value, (int, str)) else 14)

                        param_layout.addWidget(control)
                        self.param_controls[param_name] = control
                        self.dynamic_params_layout.addWidget(param_widget)
                else:
                    # 添加默认的形态参数
                    self._add_default_pattern_params()
            else:
                # 没有找到形态配置，使用默认参数
                if hasattr(self, 'param_info_label'):
                    self.param_info_label.setText(f"形态: {pattern_name}\n使用默认参数设置")
                self._add_default_pattern_params()

        except Exception as e:
            logger.error(f"设置形态参数失败: {str(e)}")
            if hasattr(self, 'param_info_label'):
                self.param_info_label.setText(f"形态参数设置失败: {str(e)}")

    def _add_default_pattern_params(self):
        """添加默认的形态参数"""
        default_params = {
            "置信度阈值": {"type": "float", "default": 0.6, "min": 0.1, "max": 1.0},
            "最小周期": {"type": "int", "default": 5, "min": 1, "max": 50},
            "最大周期": {"type": "int", "default": 30, "min": 5, "max": 100}
        }

        for param_name, param_config in default_params.items():
            param_widget = QWidget()
            param_layout = QHBoxLayout(param_widget)
            param_layout.setSpacing(4)
            param_layout.setContentsMargins(4, 2, 4, 2)

            # 参数标签
            param_label = QLabel(f"{param_name}:")
            param_label.setMinimumWidth(80)
            # param_label.setStyleSheet("QLabel { font-size: 11px; color: #212529; }")
            param_layout.addWidget(param_label)

            # 参数控件
            if param_config["type"] == "float":
                control = QDoubleSpinBox()
                control.setMaximumHeight(24)
                control.setRange(param_config["min"], param_config["max"])
                control.setValue(param_config["default"])
                control.setSingleStep(0.01)
                control.setDecimals(3)
            else:
                control = QSpinBox()
                control.setMaximumHeight(24)
                control.setRange(param_config["min"], param_config["max"])
                control.setValue(param_config["default"])

            param_layout.addWidget(control)
            self.param_controls[param_name] = control
            self.dynamic_params_layout.addWidget(param_widget)

    def get_current_params(self) -> dict:
        """获取当前参数设置 - 修复版，区分形态参数和技术指标参数"""
        params = {}
        current_indicator = self.indicator_combo.currentText()

        try:
            # 如果是形态指标，只返回形态相关参数
            from core.unified_indicator_service import get_unified_service
            unified_service = get_unified_service()
            patterns = unified_service.get_all_patterns()
            pattern_names = [p.get('name', p.get('english_name', '')) for p in patterns]

            if current_indicator and current_indicator in pattern_names:
                for param_name, control in self.param_controls.items():
                    if param_name in ["置信度阈值", "最小周期", "最大周期"]:
                        if hasattr(control, 'value'):
                            params[param_name] = control.value()
                        elif hasattr(control, 'currentText'):
                            params[param_name] = control.currentText()
                        else:
                            params[param_name] = str(control.text()) if hasattr(control, 'text') else ""
            else:
                # 技术指标参数 - 只包含TA-Lib支持的参数
                valid_talib_params = {
                    'timeperiod', 'timeperiod1', 'timeperiod2', 'timeperiod3',
                    'fastperiod', 'slowperiod', 'signalperiod',
                    'fastk_period', 'slowk_period', 'slowk_matype',
                    'slowd_period', 'slowd_matype',
                    'matype', 'fastmatype', 'slowmatype', 'signalmatype',
                    'nbdevup', 'nbdevdn', 'multiplier', 'acceleration', 'maximum'
                }

                for param_name, control in self.param_controls.items():
                    try:
                        # 转换参数名称到TA-Lib格式
                        talib_param_name = self._convert_to_talib_param_name(param_name)

                        # 只包含TA-Lib支持的参数
                        if talib_param_name in valid_talib_params:
                            if hasattr(control, 'value'):
                                params[talib_param_name] = control.value()
                            elif hasattr(control, 'currentText'):
                                # MA类型参数需要转换为数字
                                if 'matype' in talib_param_name.lower():
                                    ma_type_map = {"SMA": 0, "EMA": 1, "WMA": 2, "DEMA": 3,
                                                   "TEMA": 4, "TRIMA": 5, "KAMA": 6, "MAMA": 7, "T3": 8}
                                    params[talib_param_name] = ma_type_map.get(control.currentText(), 0)
                                else:
                                    params[talib_param_name] = control.currentText()
                            else:
                                text_value = str(control.text()) if hasattr(control, 'text') else ""
                                if text_value.isdigit():
                                    params[talib_param_name] = int(text_value)
                                else:
                                    try:
                                        params[talib_param_name] = float(text_value)
                                    except ValueError:
                                        params[talib_param_name] = text_value
                    except Exception as e:
                        logger.warning(f"处理参数 {param_name} 时出错: {e}")
                        continue

            logger.info(f"获取到参数: {params}")
            return params

        except Exception as e:
            logger.error(f"获取参数时出错: {str(e)}")
            return {}

    def _convert_to_talib_param_name(self, param_name: str) -> str:
        """将UI参数名称转换为TA-Lib参数名称"""
        # 参数名称映射
        param_mapping = {
            "周期": "timeperiod",
            "快线周期": "fastperiod",
            "慢线周期": "slowperiod",
            "信号线周期": "signalperiod",
            "K值周期": "fastk_period",
            "D值周期": "slowd_period",
            "MA类型": "matype",
            "快线MA类型": "fastmatype",
            "慢线MA类型": "slowmatype",
            "信号MA类型": "signalmatype",
            "上轨偏差": "nbdevup",
            "下轨偏差": "nbdevdn",
            "乘数": "multiplier"
        }

        # 首先尝试直接映射
        if param_name in param_mapping:
            return param_mapping[param_name]

        # 如果没有找到映射，返回原名称（可能已经是TA-Lib格式）
        return param_name

    def apply_preset_params(self, preset: str):
        """应用参数预设"""
        if preset == "自定义":
            return

        # 根据预设调整参数
        multipliers = {
            "短期交易": 0.5,
            "中期投资": 1.0,
            "长期投资": 2.0
        }

        multiplier = multipliers.get(preset, 1.0)

        for param_name, control in self.param_controls.items():
            if "period" in param_name.lower() and isinstance(control, QSpinBox):
                # 调整周期参数
                default_value = control.value()
                new_value = max(1, int(default_value * multiplier))
                control.setValue(min(new_value, control.maximum()))

    def update_param_preview(self):
        """更新参数预览"""
        try:
            if hasattr(self, 'param_preview_label') and hasattr(self, 'param_controls'):
                current_params = self.get_current_params()
                if current_params:
                    preview_text = "当前参数: " + \
                        ", ".join(
                            [f"{k}={v}" for k, v in current_params.items()])
                else:
                    preview_text = "当前参数: 无"
                self.param_preview_label.setText(preview_text)
        except Exception as e:
            # 静默处理预览更新错误
            pass

    def on_param_changed(self):
        """参数变化时的回调"""
        try:
            # 更新参数预览
            self.update_param_preview()

            # 如果启用自动计算，延迟计算指标
            if hasattr(self, 'auto_calc_checkbox') and self.auto_calc_checkbox.isChecked():
                # 使用定时器延迟计算，避免频繁计算
                if hasattr(self, '_param_change_timer'):
                    self._param_change_timer.stop()
                else:
                    self._param_change_timer = QTimer()
                    self._param_change_timer.setSingleShot(True)
                    self._param_change_timer.timeout.connect(
                        self.calculate_indicators)

                self._param_change_timer.start(1000)  # 1秒延迟
        except Exception as e:
            # 静默处理参数变化错误
            pass

    def reset_param(self, control, default_value):
        """重置参数到默认值"""
        try:
            if isinstance(control, QComboBox):
                control.setCurrentIndex(
                    default_value if isinstance(default_value, int) else 0)
            elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
                control.setValue(
                    default_value if default_value is not None else 0)
        except Exception as e:
            # 静默处理重置错误
            pass

    def _do_refresh_data(self):
        """实际的数据刷新逻辑"""
        if self.auto_calculate and self.current_kdata is not None:
            self.calculate_indicators()

    def _do_clear_data(self):
        """实际的数据清除逻辑"""
        self.technical_table.setRowCount(0)
        self.indicator_results.clear()
        self.stats_label.setText("统计信息: 无数据")
        self.performance_label.setText("性能: 无统计")

    def toggle_batch_mode(self, state):
        """切换批量计算模式"""
        if state == Qt.Checked:
            # 启用批量模式，显示多选对话框
            self.show_batch_selection_dialog()
        else:
            self.batch_indicators.clear()

    def show_batch_selection_dialog(self):
        """显示批量选择对话框 - 使用表格形式展示ta-lib指标"""
        dialog = QDialog(self)
        dialog.setWindowTitle("批量指标选择")
        dialog.setModal(True)
        dialog.resize(800, 600)

        layout = QVBoxLayout(dialog)

        # 顶部筛选区域
        filter_group = QGroupBox("筛选选项")
        filter_layout = QHBoxLayout(filter_group)

        # 分类筛选
        filter_layout.addWidget(QLabel("分类筛选:"))
        self.category_filter_combo = QComboBox()
        categories = [
            "全部"] + list(get_all_indicators_by_category(use_chinese=True).keys())
        self.category_filter_combo.addItems(categories)
        self.category_filter_combo.currentTextChanged.connect(
            self.filter_indicators_table)
        filter_layout.addWidget(self.category_filter_combo)

        # 搜索框
        filter_layout.addWidget(QLabel("搜索:"))
        self.search_line_edit = QLineEdit()
        self.search_line_edit.setPlaceholderText("输入指标名称进行搜索...")
        self.search_line_edit.textChanged.connect(self.filter_indicators_table)
        filter_layout.addWidget(self.search_line_edit)

        layout.addWidget(filter_group)

        # 指标表格
        self.indicators_table = QTableWidget()
        self.indicators_table.verticalHeader().setVisible(False)
        self.indicators_table.setColumnCount(4)
        self.indicators_table.setHorizontalHeaderLabels(
            ["选择", "中文名称", "英文名称", "分类"])

        # 设置表格属性
        self.indicators_table.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        self.indicators_table.setAlternatingRowColors(True)
        self.indicators_table.setSortingEnabled(True)

        # 设置列宽
        header = self.indicators_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # 选择列固定宽度
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # 中文名称自适应
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # 英文名称自适应
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 分类列适应内容
        self.indicators_table.setColumnWidth(0, 60)

        # 填充指标数据
        self.populate_indicators_table()

        layout.addWidget(self.indicators_table)

        # 统计信息
        self.selection_stats_label = QLabel("已选择: 0 个指标")
        self.selection_stats_label.setStyleSheet(
            "QLabel { font-weight: bold; color: #007bff; }")
        layout.addWidget(self.selection_stats_label)

        # 按钮区域
        btn_layout = QHBoxLayout()

        # 左侧按钮组
        left_btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("全选")
        select_all_btn.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; }")
        select_all_btn.clicked.connect(
            lambda: self.select_all_indicators_table(True))

        clear_all_btn = QPushButton("清除")
        clear_all_btn.setStyleSheet(
            "QPushButton { background-color: #6c757d; color: white; }")
        clear_all_btn.clicked.connect(
            lambda: self.select_all_indicators_table(False))

        # 常用指标快选
        common_btn = QPushButton("常用指标")
        common_btn.setStyleSheet(
            "QPushButton { background-color: #ffc107; color: black; }")
        common_btn.clicked.connect(self.select_common_indicators)

        left_btn_layout.addWidget(select_all_btn)
        left_btn_layout.addWidget(clear_all_btn)
        left_btn_layout.addWidget(common_btn)
        left_btn_layout.addStretch()

        # 右侧按钮组
        right_btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        ok_btn.setStyleSheet(
            "QPushButton { background-color: #007bff; color: white; font-weight: bold; }")
        ok_btn.clicked.connect(
            lambda: self.apply_batch_selection_table(dialog))

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(
            "QPushButton { background-color: #dc3545; color: white; }")
        cancel_btn.clicked.connect(dialog.reject)

        right_btn_layout.addWidget(ok_btn)
        right_btn_layout.addWidget(cancel_btn)

        btn_layout.addLayout(left_btn_layout)
        btn_layout.addLayout(right_btn_layout)
        layout.addLayout(btn_layout)

        dialog.exec_()

    def populate_indicators_table(self):
        """填充指标表格数据"""
        try:
            # 获取统一指标服务的所有指标（包括形态类）
            from core.unified_indicator_service import get_unified_service
            unified_service = get_unified_service()
            # 获取技术指标
            all_indicators_data = unified_service.get_all_indicators()
            # 获取形态数据
            all_patterns_data = unified_service.get_all_patterns()

            if not all_indicators_data and not all_patterns_data:
                self.show_library_warning("统一指标系统", "指标计算")
                return

            # 创建指标数据列表
            self.indicator_data = []

            # 处理技术指标
            for indicator_metadata in all_indicators_data:
                display_name = indicator_metadata.get('display_name', indicator_metadata.get('name', ''))
                # 修复英文名称字段映射 - 统一指标服务中英文名称存储在 'name' 字段
                english_name = indicator_metadata.get('name', indicator_metadata.get('english_name', ''))
                # 修复分类字段映射 - 优先使用 category_display_name，然后是 category_name
                category = (indicator_metadata.get('category_display_name') or
                            indicator_metadata.get('category_name') or
                            indicator_metadata.get('category', '未分类'))

                self.indicator_data.append({
                    'english_name': english_name,
                    'chinese_name': display_name,
                    'category': category,
                    'selected': False
                })

            # 处理形态数据
            for pattern_metadata in all_patterns_data:
                # 形态的显示名称和英文名称
                display_name = pattern_metadata.get('name', pattern_metadata.get('english_name', ''))
                english_name = pattern_metadata.get('english_name', pattern_metadata.get('name', ''))
                # 形态分类处理
                category = (pattern_metadata.get('category_display_name') or
                            pattern_metadata.get('category_name') or
                            pattern_metadata.get('category', '形态类'))

                # 如果分类仍为空，设置默认分类
                if not category or category == '未分类':
                    category = '形态类'

                self.indicator_data.append({
                    'english_name': english_name,
                    'chinese_name': display_name,  # 移除形态前缀
                    'category': category,
                    'selected': False
                })

            # 按中文名称排序
            self.indicator_data.sort(key=lambda x: x['chinese_name'])

            # 填充表格
            self.update_indicators_table()

            logger.info(f"成功加载 {len(all_indicators_data)} 个技术指标和 {len(all_patterns_data)} 个形态")

        except Exception as e:
            logger.error(f"填充指标表格失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"填充指标表格失败: {str(e)}")

            # 如果统一服务失败，回退到TA-Lib指标
            try:
                all_indicators = get_talib_indicator_list()
                if all_indicators:
                    self.indicator_data = []
                    for english_name in all_indicators:
                        chinese_name = get_talib_chinese_name(english_name)
                        category = get_indicator_category_by_name(english_name)
                        self.indicator_data.append({
                            'english_name': english_name,
                            'chinese_name': chinese_name,
                            'category': category,
                            'selected': False
                        })
                    self.indicator_data.sort(key=lambda x: x['chinese_name'])
                    self.update_indicators_table()
            except Exception as fallback_e:
                logger.error(f"回退到TA-Lib也失败: {str(fallback_e)}")
                QMessageBox.critical(self, "错误", f"无法加载任何指标: {str(fallback_e)}")

    def update_indicators_table(self, filtered_data=None):
        """更新指标表格显示"""
        try:
            data_to_show = filtered_data if filtered_data is not None else self.indicator_data

            self.indicators_table.setRowCount(len(data_to_show))

            for row, indicator in enumerate(data_to_show):
                # 选择列 - 复选框
                checkbox = QCheckBox()
                checkbox.setChecked(indicator['selected'])
                checkbox.stateChanged.connect(self.update_selection_stats)
                # 存储指标数据到复选框
                checkbox.setProperty('indicator_data', indicator)
                self.indicators_table.setCellWidget(row, 0, checkbox)

                # 中文名称
                chinese_item = QTableWidgetItem(indicator['chinese_name'])
                chinese_item.setFlags(
                    chinese_item.flags() & ~Qt.ItemIsEditable)
                self.indicators_table.setItem(row, 1, chinese_item)

                # 英文名称
                english_item = QTableWidgetItem(indicator['english_name'])
                english_item.setFlags(
                    english_item.flags() & ~Qt.ItemIsEditable)
                self.indicators_table.setItem(row, 2, english_item)

                # 分类
                category_item = QTableWidgetItem(indicator['category'])
                category_item.setFlags(
                    category_item.flags() & ~Qt.ItemIsEditable)
                self.indicators_table.setItem(row, 3, category_item)

                # 设置行高
                self.indicators_table.setRowHeight(row, 30)

            # 更新统计信息
            self.update_selection_stats()

        except Exception as e:
            logger.error(f"更新指标表格失败: {str(e)}")

    def filter_indicators_table(self):
        """根据分类和搜索条件筛选指标表格"""
        try:
            if not hasattr(self, 'indicator_data'):
                return

            category_filter = self.category_filter_combo.currentText()
            search_text = self.search_line_edit.text().lower()

            filtered_data = []

            for indicator in self.indicator_data:
                # 分类筛选
                if category_filter != "全部" and indicator['category'] != category_filter:
                    continue

                # 搜索筛选
                if search_text:
                    if (search_text not in indicator['chinese_name'].lower() and
                            search_text not in indicator['english_name'].lower()):
                        continue

                filtered_data.append(indicator)

            self.update_indicators_table(filtered_data)

        except Exception as e:
            logger.error(f"筛选指标表格失败: {str(e)}")

    def select_all_indicators_table(self, select: bool):
        """全选/清除表格中的所有指标"""
        try:
            for row in range(self.indicators_table.rowCount()):
                checkbox = self.indicators_table.cellWidget(row, 0)
                if checkbox:
                    checkbox.setChecked(select)
                    # 更新原始数据
                    indicator_data = checkbox.property('indicator_data')
                    if indicator_data:
                        indicator_data['selected'] = select

            self.update_selection_stats()

        except Exception as e:
            logger.error(f"全选/清除指标失败: {str(e)}")

    def select_common_indicators(self):
        """选择常用指标"""
        try:
            # 定义常用指标的英文名称
            common_indicators = [
                "MA", "EMA", "MACD", "RSI", "STOCH",
                "BBANDS", "ATR", "OBV", "CCI", "ADX"
            ]

            for row in range(self.indicators_table.rowCount()):
                checkbox = self.indicators_table.cellWidget(row, 0)
                if checkbox:
                    indicator_data = checkbox.property('indicator_data')
                    if indicator_data and indicator_data['english_name'] in common_indicators:
                        checkbox.setChecked(True)
                        indicator_data['selected'] = True

            self.update_selection_stats()

        except Exception as e:
            logger.error(f"选择常用指标失败: {str(e)}")

    def update_selection_stats(self):
        """更新选择统计信息"""
        try:
            selected_count = 0
            for row in range(self.indicators_table.rowCount()):
                checkbox = self.indicators_table.cellWidget(row, 0)
                if checkbox and checkbox.isChecked():
                    selected_count += 1

            # 只有在对话框打开时才更新统计标签
            if hasattr(self, 'selection_stats_label'):
                self.selection_stats_label.setText(
                    f"已选择: {selected_count} 个指标")

        except Exception as e:
            logger.error(f"更新选择统计失败: {str(e)}")

    def apply_batch_selection_table(self, dialog):
        """应用表格中的批量选择"""
        try:
            selected_indicators = []

            for row in range(self.indicators_table.rowCount()):
                checkbox = self.indicators_table.cellWidget(row, 0)
                if checkbox and checkbox.isChecked():
                    indicator_data = checkbox.property('indicator_data')
                    if indicator_data:
                        # 使用中文名称作为显示名称
                        selected_indicators.append(
                            indicator_data['chinese_name'])

            if not selected_indicators:
                QMessageBox.warning(dialog, "提示", "请至少选择一个指标")
                return

            self.batch_indicators = selected_indicators
            dialog.accept()

            # 显示选择结果
            QMessageBox.information(
                dialog,
                "选择完成",
                f"已选择 {len(selected_indicators)} 个指标进行批量计算:\n" +
                "\n".join(selected_indicators[:10]) +
                (f"\n... 还有 {len(selected_indicators) - 10} 个指标" if len(
                    selected_indicators) > 10 else "")
            )

        except Exception as e:
            logger.error(f"应用批量选择失败: {str(e)}")
            QMessageBox.critical(dialog, "错误", f"应用选择失败: {str(e)}")

    def select_all_indicators(self, select: bool):
        """全选/清除所有指标 - 保持向后兼容"""
        if hasattr(self, 'batch_checkboxes'):
            # 旧版本的复选框方式
            for checkbox in self.batch_checkboxes.values():
                checkbox.setChecked(select)
        else:
            # 新版本的表格方式
            self.select_all_indicators_table(select)

    def toggle_auto_calculate(self, state):
        """切换自动计算"""
        self.auto_calculate = state == Qt.Checked

    def _validate_kdata(self, kdata) -> bool:
        """验证K线数据的有效性 - 已移至BaseAnalysisTab统一实现"""
        # 此函数已在BaseAnalysisTab中统一实现，无需重复定义
        # 调用父类的统一验证方法
        return super()._validate_kdata(kdata)

    def calculate_indicators(self):
        """技术指标分析 - 增强版（异步批量计算）"""
        try:
            logger.info("开始计算技术指标...")

            if not self._validate_kdata(self.current_kdata):
                logger.warning("无有效K线数据，无法进行技术分析")
                QMessageBox.warning(self, "提示", "无有效K线数据，无法进行技术分析\n请先加载股票数据")
                return

            logger.info(f"K线数据验证通过，数据长度: {len(self.current_kdata)}")

            self.technical_table.setRowCount(0)
            self.indicator_results.clear()

            indicators_to_calculate = []
            if self.batch_checkbox.isChecked() and self.batch_indicators:
                indicators_to_calculate = self.batch_indicators
                logger.info(f"批量计算模式，选择了 {len(self.batch_indicators)} 个指标")
            else:
                current_indicator = self.indicator_combo.currentText()
                if current_indicator:
                    indicators_to_calculate = [current_indicator]
                    logger.info(f"单个指标计算模式，选择指标: {current_indicator}")

            if not indicators_to_calculate:
                QMessageBox.warning(self, "提示", "请选择要计算的指标")
                return

            self._indicators_to_calculate = indicators_to_calculate
            self._start_time = time.time()

            if len(indicators_to_calculate) > 3:
                self._start_batch_calculation_async(indicators_to_calculate)
            else:
                self._calculate_indicators_sync(indicators_to_calculate)

        except Exception as e:
            self.hide_loading()
            error_msg = f"技术指标计算过程出错: {str(e)}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)

    def _start_batch_calculation_async(self, indicators: List[str]):
        """启动异步批量计算"""
        if self._calculation_worker and self._calculation_worker.isRunning():
            self._calculation_worker.cancel()
            self._calculation_worker.wait()

        params_map = {}
        for indicator_name in indicators:
            params_map[indicator_name] = self._get_indicator_params(indicator_name)

        self.show_loading("正在初始化批量计算...")
        
        self._calculation_worker = BatchCalculateWorker(
            indicators, 
            self.current_kdata.copy(), 
            params_map,
            self
        )
        self._calculation_worker.progress.connect(self._on_batch_progress)
        self._calculation_worker.finished.connect(self._on_batch_finished)
        self._calculation_worker.error.connect(self._on_batch_error)
        self._calculation_worker.start()

    def _on_batch_progress(self, progress: int, message: str):
        """批量计算进度回调"""
        self.update_loading_progress(message, progress)

    def _on_batch_finished(self, table_rows: list, calculation_time: float, calculated_count: int, error_count: int):
        """批量计算完成回调 - 直接使用后台线程准备好的表格数据"""
        try:
            self.update_loading_progress("正在更新表格...", 98)
            
            self.technical_table.setUpdatesEnabled(False)
            self.technical_table.setSortingEnabled(False)
            
            try:
                start_row = self.technical_table.rowCount()
                self.technical_table.setRowCount(start_row + len(table_rows))
                
                for i, row_data in enumerate(table_rows):
                    row = start_row + i
                    
                    self.technical_table.setItem(row, 0, QTableWidgetItem(row_data['time']))
                    self.technical_table.setItem(row, 1, QTableWidgetItem(row_data['name']))
                    self.technical_table.setItem(row, 2, QTableWidgetItem(row_data['value']))
                    self.technical_table.setItem(row, 3, QTableWidgetItem(row_data['signal']))
                    self.technical_table.setItem(row, 4, QTableWidgetItem(row_data['strength']))
                    self.technical_table.setItem(row, 5, QTableWidgetItem(row_data['trend']))
                    self.technical_table.setItem(row, 6, QTableWidgetItem(row_data['advice']))
                    self.technical_table.setItem(row, 7, QTableWidgetItem(row_data['note']))
                    
                    self._set_row_color(row, row_data['signal'])
                
            finally:
                self.technical_table.setSortingEnabled(True)
                self.technical_table.setUpdatesEnabled(True)
            
            self._finish_calculation(calculated_count, error_count, calculation_time)
            
        except Exception as e:
            logger.error(f"处理批量计算结果失败: {e}")
            self._finish_calculation(0, len(self._indicators_to_calculate), calculation_time)

    def _on_batch_error(self, error_msg: str):
        """批量计算错误回调"""
        logger.error(f"批量计算失败: {error_msg}")
        self._calculate_indicators_sync(self._indicators_to_calculate)

    def _calculate_indicators_sync(self, indicators: List[str]):
        """同步计算指标（用于少量指标或回退）"""
        self.show_loading("正在计算技术指标...")
        start_time = time.time()
        
        total_indicators = len(indicators)
        calculated_count = 0
        error_count = 0

        for i, indicator_name in enumerate(indicators):
            try:
                progress = int((i / total_indicators) * 100)
                self.update_loading_progress(f"正在计算 {indicator_name}...", progress)
                
                result = self._calculate_single_indicator_with_params(indicator_name)
                if result is not None and result.get('values'):
                    self.indicator_results[indicator_name] = result
                    calculated_count += 1
                    self._add_indicator_to_table(indicator_name, result)
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f"计算指标 {indicator_name} 时出错: {str(e)}")

        calculation_time = time.time() - start_time
        self._finish_calculation(calculated_count, error_count, calculation_time)

    def _finish_calculation(self, calculated_count: int, error_count: int, calculation_time: float):
        """完成计算，更新UI"""
        total_indicators = len(self._indicators_to_calculate) if hasattr(self, '_indicators_to_calculate') else (calculated_count + error_count)
        
        stats_text = f"统计信息: 已计算 {calculated_count}/{total_indicators} 个指标"
        if error_count > 0:
            stats_text += f"，失败 {error_count} 个"

        self.stats_label.setText(stats_text)
        self.stats_label.setStyleSheet("QLabel { font-weight: bold; color: #495057; }")

        self.performance_label.setText(f"性能: 计算耗时 {calculation_time:.2f}秒")

        self.hide_loading()

        logger.info(f"计算完成！成功: {calculated_count}，错误: {error_count}")

        if calculated_count > 0:
            self.indicator_calculated.emit("batch", self.indicator_results)
            self.technical_table.viewport().update()
            self.technical_table.repaint()

            if self.technical_table.rowCount() > 0:
                self.technical_table.scrollToTop()
                self.technical_table.selectRow(0)
        else:
            error_msg = "没有成功计算任何指标，请检查：\n1. 数据是否有效\n2. 参数设置是否正确\n3. ta-lib库是否正确安装"
            self.error_occurred.emit(error_msg)

    def _get_indicator_params(self, indicator_name: str) -> Dict[str, Any]:
        """获取指定指标的参数"""
        try:
            english_name = get_indicator_english_name(indicator_name)
            if not english_name:
                return {}
            
            params_config = get_indicator_params_config(english_name)
            if not params_config:
                return {}

            params = {}
            # R245 修复：get_indicator_params_config 返回顶层 dict（name/display_name/description/params），
            # 参数列表在 params_config['params'] 中（原代码遍历顶层键 → 恒空 dict，参数 UI 读取失效）
            indicator_params = params_config.get('params', {}) or {}
            for param_name, param_info in indicator_params.items():
                if param_name in self.param_controls:
                    control = self.param_controls[param_name]
                    if isinstance(control, QSpinBox):
                        params[param_name] = control.value()
                    elif isinstance(control, QDoubleSpinBox):
                        params[param_name] = control.value()
                    elif isinstance(control, QComboBox):
                        params[param_name] = control.currentText()
            
            return params
        except Exception as e:
            logger.debug(f"指标 {indicator_name} 无参数配置: {e}")
            return {}

    def _extract_indicator_from_batch(self, indicator_name: str, batch_result: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """从批量计算结果中提取单个指标的结果"""
        try:
            english_name = get_indicator_english_name(indicator_name)
            english_lower = english_name.lower() if english_name else indicator_name.lower()
            
            processed = {
                "name": indicator_name,
                "timestamp": datetime.now(),
                "values": {},
                "signals": [],
                "summary": {}
            }
            
            original_columns = {'open', 'high', 'low', 'close', 'volume', 'date', 'datetime'}
            
            for col in batch_result.columns:
                col_lower = col.lower()
                if col_lower not in original_columns:
                    if english_lower in col_lower or col_lower.startswith(english_lower[:3]):
                        col_data = batch_result[col]
                        if isinstance(col_data, pd.Series):
                            valid_data = col_data.dropna()
                            if len(valid_data) > 0:
                                processed["values"][col] = col_data
            
            if not processed["values"]:
                for col in batch_result.columns:
                    col_lower = col.lower()
                    if col_lower not in original_columns:
                        col_data = batch_result[col]
                        if isinstance(col_data, pd.Series):
                            valid_data = col_data.dropna()
                            if len(valid_data) > 0:
                                processed["values"][col] = col_data
            
            if processed["values"]:
                summary_stats = {}
                for col_name, col_data in processed["values"].items():
                    if pd.api.types.is_numeric_dtype(col_data):
                        valid_data = col_data.dropna()
                        if len(valid_data) > 0:
                            summary_stats[col_name] = {
                                'mean': float(valid_data.mean()),
                                'std': float(valid_data.std()),
                                'min': float(valid_data.min()),
                                'max': float(valid_data.max()),
                                'last': float(valid_data.iloc[-1]),
                                'count': len(valid_data)
                            }
                processed["summary"] = summary_stats
            
            return processed
            
        except Exception as e:
            logger.error(f"从批量结果提取指标 {indicator_name} 失败: {e}")
            return None

    def _calculate_single_indicator_with_params(self, indicator_name: str) -> Optional[Dict[str, Any]]:
        """计算单个指标，包含参数处理和错误处理"""
        try:
            if self.current_kdata is None or self.current_kdata.empty:
                logger.error(f"无法计算指标 {indicator_name}: 当前K线数据为空")
                return None

            # 获取参数
            params = self.get_current_params()
            logger.info(f"计算指标 {indicator_name}，参数: {params}")

            # 统一通过IndicatorService计算
            result_df = calculate_indicator(indicator_name, self.current_kdata, **params)

            # 处理结果 - calculate_indicator返回的是DataFrame
            if result_df is None or result_df.empty:
                logger.warning(f"指标 {indicator_name} 计算结果为空")
                return None

            # 转换DataFrame结果为字典格式以适配显示逻辑
            processed_result = self._process_dataframe_result(indicator_name, result_df)

            logger.info(f"指标 {indicator_name} 计算完成，结果列数: {len(processed_result.get('values', {}))}")

            return processed_result

        except Exception as e:
            error_msg = f"计算指标 {indicator_name} 失败: {str(e)}"
            logger.error(error_msg)
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            self.error_occurred.emit(error_msg)
            return None

    def _process_dataframe_result(self, indicator_name: str, result_df: pd.DataFrame) -> Dict[str, Any]:
        """处理DataFrame结果，转换为统一的字典格式"""
        try:
            # 首先清理DataFrame中的重复字符串
            result_df = self._clean_dataframe_strings(result_df, indicator_name)
            
            processed = {
                "name": indicator_name,
                "timestamp": datetime.now(),
                "values": {},
                "signals": [],
                "summary": {}
            }

            # 改进的列名过滤逻辑 - 更精确地识别新增列
            original_columns = {'open', 'high', 'low', 'close', 'volume', 'date', 'datetime'}
            new_columns = []
            
            # 第一轮：直接排除原始OHLCV列
            for col in result_df.columns:
                col_lower = col.lower().strip()
                if col_lower not in original_columns:
                    new_columns.append(col)
            
            logger.info(f"指标 {indicator_name} 候选列: {new_columns}")

            # 第二轮：精确匹配和分类处理
            indicator_lower = indicator_name.lower().strip()
            
            for col in new_columns:
                if col in result_df.columns:
                    col_data = result_df[col]
                    if isinstance(col_data, pd.Series):
                        # 去除NaN值
                        valid_data = col_data.dropna()
                        if len(valid_data) > 0:
                            # 标准化列名映射
                            standardized_col = self._standardize_column_name(col, indicator_name)
                            processed["values"][standardized_col] = col_data
                            logger.info(f"添加列 {col} -> {standardized_col}，有效数据点: {len(valid_data)}")
                        else:
                            logger.warning(f"列 {col} 无有效数据")

            # 第三轮：对于没有匹配到的列，尝试模糊匹配
            if not processed["values"]:
                for col in result_df.columns:
                    if any(keyword in col.lower() for keyword in [indicator_lower, 'sma', 'ema', 'rsi', 'macd', 'bbands', 'stoch']):
                        col_data = result_df[col]
                        if isinstance(col_data, pd.Series):
                            valid_data = col_data.dropna()
                            if len(valid_data) > 0:
                                standardized_col = self._standardize_column_name(col, indicator_name)
                                processed["values"][standardized_col] = col_data
                                logger.info(f"模糊匹配添加列 {col} -> {standardized_col}")

            # 根本性修复：确保summary_stats始终被初始化
            summary_stats = {}  # 移至if语句外部，确保总是被初始化
            
            # 生成改进的统计摘要
            if processed["values"]:
                # 计算更详细的统计信息
                for col_name, col_data in processed["values"].items():
                    if isinstance(col_data, pd.Series) and len(col_data) > 0:
                        # 仅当整列都是数值时才计算统计量
                        if pd.api.types.is_numeric_dtype(col_data):
                            valid_data = col_data.dropna()
                            if len(valid_data) > 0:
                                summary_stats[col_name] = {
                                    'mean': float(valid_data.mean()),
                                    'std': float(valid_data.std()),
                                    'min': float(valid_data.min()),
                                    'max': float(valid_data.max()),
                                    'last': float(valid_data.iloc[-1]),
                                    'count': len(valid_data)
                                }
                        else:
                            # 非数值列仅记录计数
                            summary_stats[col_name] = {
                                'mean': None,
                                'std': None,
                                'min': None,
                                'max': None,
                                'last': str(col_data.iloc[-1]) if len(col_data) > 0 else None,
                                'count': len(col_data.dropna())
                            }
            else:
                logger.warning(f"指标 {indicator_name} 未产生有效结果列，统计摘要将为空")
                
            # 根本性修复：确保summary总是存在，避免调用方出现NoneType错误
            processed["summary"] = {
                "columns_count": len(processed["values"]),
                "data_points": len(result_df),
                "calculation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "statistics": summary_stats  # 现在summary_stats总是被初始化，不会为None
            }

            return processed

        except Exception as e:
            logger.error(f"处理DataFrame结果失败: {str(e)}")
            # 根本性修复：确保错误情况下也返回有效的summary结构
            return {
                "name": indicator_name,
                "timestamp": datetime.now(),
                "values": {},
                "signals": [],
                "summary": {
                    "columns_count": 0,
                    "data_points": 0,
                    "calculation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "statistics": {},  # 确保error情况下也返回有效的statistics
                    "error": str(e)
                },
                "error": str(e)
            }
    
    def _clean_dataframe_strings(self, df: pd.DataFrame, indicator_name: str) -> pd.DataFrame:
        """清理DataFrame中的重复字符串，处理数据质量问题"""
        try:
            logger.debug(f"开始清理指标 {indicator_name} 的DataFrame字符串数据...")
            
            # 复制DataFrame以避免修改原始数据
            cleaned_df = df.copy()
            repeat_string_count = 0
            
            # 检查每一列中的字符串数据
            for col in cleaned_df.columns:
                if cleaned_df[col].dtype == 'object':
                    # 检查字符串列中的重复模式
                    repeat_mask = cleaned_df[col].astype(str).apply(self._is_repeat_string)
                    if repeat_mask.any():
                        repeat_count = repeat_mask.sum()
                        repeat_string_count += repeat_count
                        
                        # 记录检测到的重复字符串
                        repeat_strings = cleaned_df.loc[repeat_mask, col].unique()
                        logger.warning(f"指标 {indicator_name} 列 {col} 检测到 {repeat_count} 个重复字符串: {[s[:20] + '...' if len(str(s)) > 20 else s for s in repeat_strings[:3]]}")
                        
                        # 将重复字符串替换为NaN
                        cleaned_df.loc[repeat_mask, col] = np.nan
                        
                        logger.debug(f"已清理列 {col} 中的 {repeat_count} 个重复字符串")
            
            if repeat_string_count > 0:
                logger.info(f"指标 {indicator_name} DataFrame清理完成: 共清理 {repeat_string_count} 个重复字符串")
            else:
                logger.debug(f"指标 {indicator_name} DataFrame无需清理: 未检测到重复字符串")
                
            return cleaned_df
            
        except Exception as e:
            logger.error(f"清理DataFrame字符串失败: {e}")
            return df
    
    def _is_repeat_string(self, value: Any) -> bool:
        """检测是否为重复字符串模式"""
        try:
            if not isinstance(value, str):
                return False
                
            # 如果字符串长度小于等于10，不是重复模式
            if len(value) <= 10:
                return False
            
            # 检查是否为基础字符串的重复模式
            # 尝试找到最短的重复单元
            for i in range(1, min(len(value), 20)):
                unit = value[:i]
                if len(value) % len(unit) == 0:
                    repeated = unit * (len(value) // len(unit))
                    if value == repeated:
                        logger.debug(f"检测到重复字符串模式: 单元='{unit}', 长度={i}, 重复次数={len(value) // i}")
                        return True
            
            return False
            
        except Exception as e:
            logger.debug(f"重复字符串检测失败: {e}")
            return False
    
    def _standardize_column_name(self, original_col: str, indicator_name: str) -> str:
        """标准化列名映射，确保正确的显示"""
        # 常见指标的列名映射
        mappings = {
            # MACD相关
            'macd': 'MACD_1',
            'signal': 'MACD_2', 
            'histogram': 'MACD_3',
            'macd_1': 'MACD_1',
            'macd_2': 'MACD_2',
            'macd_3': 'MACD_3',
            
            # 布林带相关
            'upper': 'BBANDS_1',
            'middle': 'BBANDS_2', 
            'lower': 'BBANDS_3',
            'bb_upper': 'BBANDS_1',
            'bb_middle': 'BBANDS_2',
            'bb_lower': 'BBANDS_3',
            
            # 随机指标相关
            'slowk': 'STOCH_1',
            'slowd': 'STOCH_2',
            'fastk': 'STOCHF_1',
            'fastd': 'STOCHF_2',
            
            # KDJ指标
            'kdj_k': 'KDJ_1',
            'kdj_d': 'KDJ_2',
            'kdj_j': 'KDJ_3',
            
            # 移动平均线
            'sma': f'{indicator_name}_SMA',
            'ema': f'{indicator_name}_EMA',
            
            # RSI
            'rsi': 'RSI_1'
        }
        
        col_lower = original_col.lower()
        
        # 直接映射
        if col_lower in mappings:
            return mappings[col_lower]
        
        # 模糊匹配
        for key, value in mappings.items():
            if key in col_lower:
                return value
        
        # 如果没有匹配到，返回原始列名，但确保大写格式
        return original_col.upper() if original_col.islower() else original_col

    def _process_indicator_result(self, indicator_name: str, result: Any) -> Dict[str, Any]:
        """处理指标计算结果"""
        try:
            processed = {
                "name": indicator_name,
                "timestamp": datetime.now(),
                "values": {},
                "signals": [],
                "summary": {}
            }

            # 处理不同类型的结果
            if isinstance(result, pd.DataFrame):
                # DataFrame结果（如MACD、STOCH等多输出指标）
                for col in result.columns:
                    processed["values"][col] = result[col].values
            elif isinstance(result, pd.Series):
                # Series结果（如RSI、MA等单输出指标）
                processed["values"]["main"] = result.values
            elif isinstance(result, tuple):
                # 元组结果（旧版本兼容）
                output_names = self._get_indicator_output_names(indicator_name)
                for i, value in enumerate(result):
                    if i < len(output_names):
                        if isinstance(value, (pd.Series, pd.DataFrame)):
                            processed["values"][output_names[i]] = value.values
                        else:
                            processed["values"][output_names[i]] = value
                    else:
                        processed["values"][f"output_{i}"] = value
            elif isinstance(result, np.ndarray):
                # 数组结果
                processed["values"]["main"] = result
            else:
                # 其他类型
                logger.warning(f"未知的结果类型: {type(result)}")
                processed["values"]["main"] = result

            # 生成信号分析
            processed["signals"] = self._generate_signals(
                indicator_name, processed["values"])

            # 生成摘要统计
            processed["summary"] = self._generate_summary(processed["values"])

            return processed

        except Exception as e:
            logger.error(f"处理指标结果时出错: {str(e)}")
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return {"name": indicator_name, "error": str(e)}

    def _get_indicator_output_names(self, indicator_name: str) -> List[str]:
        """获取指标的输出名称"""
        english_name = get_indicator_english_name(indicator_name)

        # 定义常见指标的输出名称
        output_names_map = {
            "MACD": ["macd", "signal", "histogram"],
            "STOCH": ["slowk", "slowd"],
            "STOCHF": ["fastk", "fastd"],
            "STOCHRSI": ["fastk", "fastd"],
            "BBANDS": ["upper", "middle", "lower"],
            "AROON": ["aroondown", "aroonup"],
            "HT_PHASOR": ["inphase", "quadrature"],
            "HT_SINE": ["sine", "leadsine"],
            "MINMAX": ["min", "max"],
            "MINMAXINDEX": ["minidx", "maxidx"],
        }

        return output_names_map.get(english_name, ["main"])

    def _generate_signals(self, indicator_name: str, values: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成交易信号"""
        signals = []
        try:
            # 根据指标类型生成不同的信号
            english_name = get_indicator_english_name(indicator_name)

            if english_name == "RSI" and "main" in values:
                rsi_values = values["main"]
                if len(rsi_values) > 0:
                    latest_rsi = rsi_values[-1]
                    if not np.isnan(latest_rsi):
                        if latest_rsi > 70:
                            signals.append(
                                {"type": "sell", "strength": "strong", "reason": f"RSI超买({latest_rsi:.2f})"})
                        elif latest_rsi < 30:
                            signals.append(
                                {"type": "buy", "strength": "strong", "reason": f"RSI超卖({latest_rsi:.2f})"})
                        elif latest_rsi > 50:
                            signals.append(
                                {"type": "neutral", "strength": "weak", "reason": f"RSI偏强({latest_rsi:.2f})"})
                        else:
                            signals.append(
                                {"type": "neutral", "strength": "weak", "reason": f"RSI偏弱({latest_rsi:.2f})"})

            elif english_name == "MACD" and all(k in values for k in ["MACD_1", "MACD_2"]):
                macd_line = values["MACD_1"]
                signal_line = values["MACD_2"]
                if len(macd_line) > 1 and len(signal_line) > 1:
                    if macd_line[-1] > signal_line[-1] and macd_line[-2] <= signal_line[-2]:
                        signals.append(
                            {"type": "buy", "strength": "medium", "reason": "MACD金叉"})
                    elif macd_line[-1] < signal_line[-1] and macd_line[-2] >= signal_line[-2]:
                        signals.append(
                            {"type": "sell", "strength": "medium", "reason": "MACD死叉"})
                    elif macd_line[-1] > signal_line[-1]:
                        signals.append(
                            {"type": "buy", "strength": "weak", "reason": "MACD多头"})
                    else:
                        signals.append(
                            {"type": "sell", "strength": "weak", "reason": "MACD空头"})

            elif english_name == "STOCH" and all(k in values for k in ["STOCH_1", "STOCH_2"]):
                k_values = values["STOCH_1"]
                d_values = values["STOCH_2"]
                if len(k_values) > 0 and len(d_values) > 0:
                    latest_k = k_values[-1]
                    latest_d = d_values[-1]
                    if not np.isnan(latest_k) and not np.isnan(latest_d):
                        if latest_k > 80 and latest_d > 80:
                            signals.append({"type": "sell", "strength": "strong",
                                           "reason": f"KDJ超买(K:{latest_k:.1f},D:{latest_d:.1f})"})
                        elif latest_k < 20 and latest_d < 20:
                            signals.append(
                                {"type": "buy", "strength": "strong", "reason": f"KDJ超卖(K:{latest_k:.1f},D:{latest_d:.1f})"})
                        elif len(k_values) > 1 and len(d_values) > 1:
                            if k_values[-1] > d_values[-1] and k_values[-2] <= d_values[-2]:
                                signals.append(
                                    {"type": "buy", "strength": "medium", "reason": "KDJ金叉"})
                            elif k_values[-1] < d_values[-1] and k_values[-2] >= d_values[-2]:
                                signals.append(
                                    {"type": "sell", "strength": "medium", "reason": "KDJ死叉"})

            elif english_name == "BBANDS" and all(k in values for k in ["BBANDS_1", "BBANDS_2", "BBANDS_3"]):
                upper = values["BBANDS_1"]
                middle = values["BBANDS_2"]
                lower = values["BBANDS_3"]
                if len(upper) > 0 and len(middle) > 0 and len(lower) > 0:
                    # 需要当前价格来判断布林带信号，这里使用中轨作为参考
                    current_price = middle[-1]  # 假设当前价格接近中轨
                    upper_val = upper[-1]
                    lower_val = lower[-1]
                    if not np.isnan(current_price):
                        if current_price >= upper_val:
                            signals.append(
                                {"type": "sell", "strength": "medium", "reason": "触及布林上轨"})
                        elif current_price <= lower_val:
                            signals.append(
                                {"type": "buy", "strength": "medium", "reason": "触及布林下轨"})
                        else:
                            signals.append(
                                {"type": "neutral", "strength": "weak", "reason": "布林带中轨区间"})

            elif english_name == "CCI" and "main" in values:
                cci_values = values["main"]
                if len(cci_values) > 0:
                    latest_cci = cci_values[-1]
                    if not np.isnan(latest_cci):
                        if latest_cci > 100:
                            signals.append(
                                {"type": "sell", "strength": "medium", "reason": f"CCI超买({latest_cci:.1f})"})
                        elif latest_cci < -100:
                            signals.append(
                                {"type": "buy", "strength": "medium", "reason": f"CCI超卖({latest_cci:.1f})"})
                        else:
                            signals.append(
                                {"type": "neutral", "strength": "weak", "reason": f"CCI正常({latest_cci:.1f})"})

            elif english_name == "ADX" and "main" in values:
                adx_values = values["main"]
                if len(adx_values) > 0:
                    latest_adx = adx_values[-1]
                    if not np.isnan(latest_adx):
                        if latest_adx > 25:
                            signals.append(
                                {"type": "neutral", "strength": "strong", "reason": f"趋势强劲(ADX:{latest_adx:.1f})"})
                        elif latest_adx > 20:
                            signals.append(
                                {"type": "neutral", "strength": "medium", "reason": f"趋势中等(ADX:{latest_adx:.1f})"})
                        else:
                            signals.append(
                                {"type": "neutral", "strength": "weak", "reason": f"趋势微弱(ADX:{latest_adx:.1f})"})

            elif english_name in ["MA", "EMA", "SMA"] and "main" in values:
                ma_values = values["main"]
                if len(ma_values) > 1:
                    current_ma = ma_values[-1]
                    prev_ma = ma_values[-2]
                    if not np.isnan(current_ma) and not np.isnan(prev_ma):
                        if current_ma > prev_ma:
                            signals.append(
                                {"type": "buy", "strength": "weak", "reason": f"均线上升({current_ma:.2f})"})
                        elif current_ma < prev_ma:
                            signals.append(
                                {"type": "sell", "strength": "weak", "reason": f"均线下降({current_ma:.2f})"})
                        else:
                            signals.append(
                                {"type": "neutral", "strength": "weak", "reason": f"均线平稳({current_ma:.2f})"})

            elif english_name == "ATR" and "main" in values:
                atr_values = values["main"]
                if len(atr_values) > 0:
                    latest_atr = atr_values[-1]
                    if not np.isnan(latest_atr):
                        # ATR主要用于衡量波动性
                        if len(atr_values) > 20:
                            avg_atr = np.mean(atr_values[-20:])
                            if latest_atr > avg_atr * 1.5:
                                signals.append(
                                    {"type": "neutral", "strength": "strong", "reason": f"波动性高(ATR:{latest_atr:.3f})"})
                            elif latest_atr < avg_atr * 0.5:
                                signals.append(
                                    {"type": "neutral", "strength": "weak", "reason": f"波动性低(ATR:{latest_atr:.3f})"})
                            else:
                                signals.append(
                                    {"type": "neutral", "strength": "medium", "reason": f"波动性正常(ATR:{latest_atr:.3f})"})
                        else:
                            signals.append(
                                {"type": "neutral", "strength": "medium", "reason": f"波动性正常(ATR:{latest_atr:.3f})"})

            elif english_name == "OBV" and "main" in values:
                obv_values = values["main"]
                if len(obv_values) > 1:
                    current_obv = obv_values[-1]
                    prev_obv = obv_values[-2]
                    if not np.isnan(current_obv) and not np.isnan(prev_obv):
                        if current_obv > prev_obv:
                            signals.append(
                                {"type": "buy", "strength": "weak", "reason": f"成交量上升"})
                        elif current_obv < prev_obv:
                            signals.append(
                                {"type": "sell", "strength": "weak", "reason": f"成交量下降"})
                        else:
                            signals.append(
                                {"type": "neutral", "strength": "weak", "reason": f"成交量平稳"})

            # 如果没有生成任何信号，提供默认信号
            if not signals:
                signals.append(
                    {"type": "neutral", "strength": "weak", "reason": "无明确信号"})

        except Exception as e:
            logger.error(f"生成信号时出错: {str(e)}")
            signals.append(
                {"type": "neutral", "strength": "weak", "reason": "信号计算错误"})

        return signals

    def _generate_summary(self, values: Dict[str, Any]) -> Dict[str, Any]:
        """生成指标摘要统计"""
        summary = {}
        try:
            for name, data in values.items():
                if isinstance(data, np.ndarray) and len(data) > 0:
                    valid_data = data[~np.isnan(data)]
                    if len(valid_data) > 0:
                        summary[name] = {
                            "current": float(data[-1]) if not np.isnan(data[-1]) else None,
                            "mean": float(np.mean(valid_data)),
                            "std": float(np.std(valid_data)),
                            "min": float(np.min(valid_data)),
                            "max": float(np.max(valid_data)),
                            "count": len(valid_data)
                        }
        except Exception as e:
            logger.error(f"生成摘要时出错: {str(e)}")

        return summary

    def _add_indicator_to_table(self, indicator_name: str, result: Dict[str, Any]):
        """将指标结果添加到表格 - 优化版：批量插入，减少list()调用"""
        try:
            # 性能优化：减少list()调用，使用len()和直接迭代
            logger.debug(f"开始添加指标 {indicator_name} 到表格")
            if isinstance(result, dict):
                logger.debug(f"结果类型: {type(result)}, 结果键数量: {len(result)}")
            else:
                logger.debug(f"结果类型: {type(result)}")

            # 临时禁用排序，避免添加数据时的显示问题
            sorting_enabled = self.technical_table.isSortingEnabled()
            self.technical_table.setSortingEnabled(False)

            if "error" in result:
                # 错误情况
                row = self.technical_table.rowCount()
                self.technical_table.insertRow(row)
                self.technical_table.setItem(row, 0, QTableWidgetItem(
                    datetime.now().strftime("%Y-%m-%d %H:%M")))
                self.technical_table.setItem(
                    row, 1, QTableWidgetItem(indicator_name))
                self.technical_table.setItem(row, 2, QTableWidgetItem("计算错误"))
                self.technical_table.setItem(row, 3, QTableWidgetItem(""))
                self.technical_table.setItem(row, 4, QTableWidgetItem(""))
                self.technical_table.setItem(row, 5, QTableWidgetItem(""))
                self.technical_table.setItem(row, 6, QTableWidgetItem(""))
                self.technical_table.setItem(
                    row, 7, QTableWidgetItem(result["error"]))
                logger.warning(
                    f"指标 {indicator_name} 计算错误: {result['error']}")
                # 恢复排序设置
                self.technical_table.setSortingEnabled(sorting_enabled)
                return

            # 正常结果处理
            values = result.get("values", {})
            signals = result.get("signals", [])
            summary = result.get("summary", {})

            # 性能优化：减少list()调用
            logger.debug(f"指标 {indicator_name} 的值数量: {len(values)}")
            # if logger.level <= 10:  # DEBUG级别才记录详细信息
            #     logger.debug(f"值的键: {tuple(values.keys())}")

            # 处理不同的结果格式
            if not values:
                # 如果values为空，尝试从result中直接提取数据
                if isinstance(result, dict):
                    # 检查是否有numpy数组或pandas数据
                    for key, value in result.items():
                        if key not in ['error', 'performance', 'summary', 'signals']:
                            if isinstance(value, (np.ndarray, pd.Series, pd.DataFrame)):
                                values[key] = value
                            elif isinstance(value, (int, float)) and not np.isnan(value):
                                values[key] = value

                    # 性能优化：减少list()调用
                    logger.debug(f"从结果中提取的值数量: {len(values)}")
                    # if logger.level <= 10:  # DEBUG级别才记录详细信息
                    #     logger.debug(f"值的键: {tuple(values.keys())}")

            if not values:
                # 仍然没有数据，添加一个提示行
                row = self.technical_table.rowCount()
                self.technical_table.insertRow(row)
                self.technical_table.setItem(row, 0, QTableWidgetItem(
                    datetime.now().strftime("%Y-%m-%d %H:%M")))
                self.technical_table.setItem(row, 1, QTableWidgetItem(indicator_name))
                self.technical_table.setItem(row, 2, QTableWidgetItem("无数据"))
                self.technical_table.setItem(row, 3, QTableWidgetItem(""))
                self.technical_table.setItem(row, 4, QTableWidgetItem(""))
                self.technical_table.setItem(row, 5, QTableWidgetItem(""))
                self.technical_table.setItem(row, 6, QTableWidgetItem("计算完成但无返回值"))
                self.technical_table.setItem(row, 7, QTableWidgetItem("请检查参数设置"))

                logger.warning(f"指标 {indicator_name} 计算完成但无有效数据")
                self.technical_table.setSortingEnabled(sorting_enabled)
                return

            # 性能优化：批量准备数据，然后一次性插入
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            rows_data = []  # 批量收集所有行数据

            for value_name, value_data in values.items():
                logger.debug(f"处理值 {value_name}, 数据类型: {type(value_data)}")

                # 提取当前值和趋势信息
                current_value = None
                trend_info = ""
                signal_info = ""
                strength_info = ""
                advice = "N/A"  # 初始化advice变量，避免未定义错误

                try:
                    # 处理不同类型的数据
                    if isinstance(value_data, np.ndarray):
                        if len(value_data) > 0:
                            # 检查数据类型 - 只对数值型数据进行处理
                            if np.issubdtype(value_data.dtype, np.number):
                                # 获取最后几个有效值来分析趋势
                                valid_indices = ~np.isnan(value_data)
                                if np.any(valid_indices):
                                    valid_data = value_data[valid_indices]
                                    current_value = valid_data[-1]

                                    # 分析趋势
                                    if len(valid_data) >= 2:
                                        if valid_data[-1] > valid_data[-2]:
                                            trend_info = "上升 ↑"
                                        elif valid_data[-1] < valid_data[-2]:
                                            trend_info = "下降 ↓"
                                        else:
                                            trend_info = "持平 →"

                                        # 计算强度（变化幅度）
                                        if valid_data[-2] != 0:
                                            change_pct = abs((valid_data[-1] - valid_data[-2]) / valid_data[-2] * 100)
                                            if change_pct > 5:
                                                strength_info = "强"
                                            elif change_pct > 2:
                                                strength_info = "中"
                                            else:
                                                strength_info = "弱"
                            else:
                                # 对于非数值型数组，只取最后一个值
                                if len(value_data) > 0:
                                    current_value = value_data[-1]
                                    trend_info = "N/A"
                                    strength_info = "N/A"

                    elif isinstance(value_data, pd.Series):
                        if len(value_data) > 0:
                            # 获取最后几个有效值
                            valid_data = value_data.dropna()
                            if len(valid_data) > 0:
                                current_value = valid_data.iloc[-1]

                                # 检查数据类型 - 只对数值型数据进行趋势和强度分析
                                if pd.api.types.is_numeric_dtype(valid_data):
                                    # 分析趋势和强度
                                    if len(valid_data) >= 2:
                                        prev_value = valid_data.iloc[-2]
                                        if valid_data.iloc[-1] > prev_value:
                                            trend_info = "上升 ↑"
                                        elif valid_data.iloc[-1] < prev_value:
                                            trend_info = "下降 ↓"
                                        else:
                                            trend_info = "持平 →"

                                        # 计算强度（变化幅度）
                                        if prev_value != 0:
                                            change_pct = abs((valid_data.iloc[-1] - prev_value) / prev_value * 100)
                                            if change_pct > 5:
                                                strength_info = "强"
                                            elif change_pct > 2:
                                                strength_info = "中"
                                            else:
                                                strength_info = "弱"
                                else:
                                    # 对于非数值型数据（如字符串），不进行趋势和强度分析
                                    trend_info = "N/A"
                                    strength_info = "N/A"

                    elif isinstance(value_data, pd.DataFrame):
                        if len(value_data) > 0:
                            # 取第一列的最后一个有效值
                            first_col = value_data.iloc[:, 0].dropna()
                            if len(first_col) > 0:
                                current_value = first_col.iloc[-1]

                                # 检查数据类型 - 只对数值型数据进行趋势和强度分析
                                if pd.api.types.is_numeric_dtype(first_col):
                                    # 分析趋势和强度
                                    if len(first_col) >= 2:
                                        prev_value = first_col.iloc[-2]
                                        if current_value > prev_value:
                                            trend_info = "上升 ↑"
                                        elif current_value < prev_value:
                                            trend_info = "下降 ↓"
                                        else:
                                            trend_info = "持平 →"

                                        # 计算强度
                                        if prev_value != 0:
                                            change_pct = abs((current_value - prev_value) / prev_value * 100)
                                            if change_pct > 5:
                                                strength_info = "强"
                                            elif change_pct > 2:
                                                strength_info = "中"
                                            else:
                                                strength_info = "弱"
                                else:
                                    # 对于非数值型数据，不进行趋势和强度分析
                                    trend_info = "N/A"
                                    strength_info = "N/A"

                    elif isinstance(value_data, (int, float)):
                        if not np.isnan(value_data):
                            current_value = value_data
                            # 对于单一数值，设置默认强度
                            if abs(current_value) > 50:
                                strength_info = "强"
                            elif abs(current_value) > 20:
                                strength_info = "中"
                            else:
                                strength_info = "弱"

                    # 生成信号建议
                    if current_value is not None and isinstance(current_value, (int, float)):
                        signal_info, advice = self._generate_signal_advice(indicator_name, value_name, current_value, trend_info)

                except Exception as e:
                    logger.error(f"处理数据时出错: {str(e)}")
                    current_value = "错误"

                logger.debug(f"提取的当前值: {current_value}")

                # 性能优化：收集数据而不是立即插入
                if current_value is not None:
                    # 指标名称 - 改进显示逻辑
                    display_name = self._get_display_name(indicator_name, value_name)

                    # 数值 - 格式化显示
                    value_str = self._format_value(current_value)

                    # 备注 - 添加更多信息
                    note = f"周期: {len(value_data) if hasattr(value_data, '__len__') else 'N/A'}"
                    if summary:
                        note += f", 均值: {summary.get('mean', 'N/A')}"

                    # 收集行数据
                    rows_data.append({
                        'time': current_time,
                        'name': display_name,
                        'value': value_str,
                        'signal': signal_info,
                        'strength': strength_info,
                        'trend': trend_info,
                        'advice': advice,
                        'note': note
                    })

            # 性能优化：批量插入所有行
            if rows_data:
                start_row = self.technical_table.rowCount()
                self.technical_table.setRowCount(start_row + len(rows_data))

                for i, row_data in enumerate(rows_data):
                    row = start_row + i

                    # 批量设置单元格
                    self.technical_table.setItem(row, 0, QTableWidgetItem(row_data['time']))
                    self.technical_table.setItem(row, 1, QTableWidgetItem(row_data['name']))
                    self.technical_table.setItem(row, 2, QTableWidgetItem(row_data['value']))
                    self.technical_table.setItem(row, 3, QTableWidgetItem(row_data['signal']))
                    self.technical_table.setItem(row, 4, QTableWidgetItem(row_data['strength']))
                    self.technical_table.setItem(row, 5, QTableWidgetItem(row_data['trend']))
                    self.technical_table.setItem(row, 6, QTableWidgetItem(row_data['advice']))
                    self.technical_table.setItem(row, 7, QTableWidgetItem(row_data['note']))

                    # 设置行颜色（基于信号类型）
                    self._set_row_color(row, row_data['signal'])

                logger.debug(f"批量插入 {len(rows_data)} 行数据完成")

            # 恢复排序设置
            self.technical_table.setSortingEnabled(sorting_enabled)

            # 自动调整列宽
            self.technical_table.resizeColumnsToContents()

        except Exception as e:
            logger.error(f"添加指标到表格失败: {str(e)}")
            logger.error(f"详细错误: {traceback.format_exc()}")

            # 恢复排序设置
            if 'sorting_enabled' in locals():
                self.technical_table.setSortingEnabled(sorting_enabled)

    def _get_display_name(self, indicator_name: str, value_name: str) -> str:
        """获取显示名称"""
        if value_name == "main" or value_name == indicator_name:
            return indicator_name

        # 为多输出指标提供更专业的名称
        name_mappings = {
            "MACD指标": {"MACD_1": "MACD线", "MACD_2": "信号线", "MACD_3": "柱状图"},
            "布林带": {"BBANDS_1": "上轨", "BBANDS_2": "中轨", "BBANDS_3": "下轨"},
            "随机指标": {"STOCH_1": "%K线", "STOCH_2": "%D线"},
            "KDJ指标": {"STOCH_1": "K值", "STOCH_2": "D值", "STOCH_3": "J值"},
            "威廉指标": {"WILLR_1": "%R值"}
        }

        if indicator_name in name_mappings and value_name in name_mappings[indicator_name]:
            return f"{indicator_name}-{name_mappings[indicator_name][value_name]}"
        else:
            return f"{indicator_name}-{value_name}"

    def _format_value(self, value) -> str:
        """格式化数值显示 - 精确版：确保精度和正确性"""
        try:
            # 处理None和空值
            if value is None:
                return "--"
            
            # 检查是否为数值类型
            if isinstance(value, (int, float)):
                # 处理特殊情况
                if np.isnan(value):
                    return "--"
                if np.isinf(value):
                    return "∞" if value > 0 else "-∞"
                
                # 转换为浮点数
                float_value = float(value)
                
                # 特殊情况处理
                if float_value == 0:
                    return "0.00"
                
                # 根据数值大小选择合适的精度
                abs_value = abs(float_value)
                
                # 对于极小数值，保留更多精度但避免过多小数位
                if abs_value < 0.0001:
                    # 使用8位小数，然后智能清理尾随零
                    formatted = f"{float_value:.8f}"
                    # 移除尾随的零，但保留至少3位有效数字
                    if '.' in formatted:
                        # 先移除尾随零
                        formatted = formatted.rstrip('0')
                        # 如果移除后只有小数点，添加一个零
                        if formatted.endswith('.'):
                            formatted += '0'
                    return formatted
                elif abs_value < 0.01:
                    # 使用6位小数
                    return f"{float_value:.6f}".rstrip('0').rstrip('.') if not float_value.is_integer() else f"{int(float_value)}"
                elif abs_value < 1:
                    # 使用4位小数
                    return f"{float_value:.4f}".rstrip('0').rstrip('.') if not float_value.is_integer() else f"{int(float_value)}"
                elif abs_value < 10:
                    # 使用3位小数
                    return f"{float_value:.3f}".rstrip('0').rstrip('.') if not float_value.is_integer() else f"{int(float_value)}"
                elif abs_value < 100:
                    # 使用2位小数
                    return f"{float_value:.2f}".rstrip('0').rstrip('.') if not float_value.is_integer() else f"{int(float_value)}"
                elif abs_value < 1000:
                    # 使用1位小数
                    return f"{float_value:.1f}".rstrip('0').rstrip('.') if not float_value.is_integer() else f"{int(float_value)}"
                else:
                    # 对于大数值，使用千分位分隔符，去掉小数部分
                    return f"{float_value:,.0f}"
                    
            else:
                # 非数值类型直接转换
                return str(value)
                
        except (ValueError, TypeError) as e:
            logger.warning(f"格式化数值时出错: {value} -> {str(e)}")
            return "--"

    def _generate_signal_advice(self, indicator_name: str, value_name: str, current_value: float, trend: str) -> tuple:
        """生成信号和建议"""
        signal = ""
        advice = ""

        try:
            # 确保current_value是数值类型
            if not isinstance(current_value, (int, float)):
                logger.warning(f"当前值不是数值类型: {type(current_value)}, 值: {current_value}")
                return "数据类型错误", "无法分析"

            # 检查是否为NaN
            if np.isnan(current_value):
                return "数据无效", "无法分析"

            # 基于指标类型生成信号
            if "RSI" in indicator_name:
                if current_value > 70:
                    signal = "超买"
                    advice = "考虑卖出"
                elif current_value < 30:
                    signal = "超卖"
                    advice = "考虑买入"
                else:
                    signal = "中性"
                    advice = "观望"

            elif "MACD" in indicator_name:
                # 使用标准化的列名匹配
                if any(keyword in value_name.upper() for keyword in ["MACD_3", "HISTOGRAM", "柱状图"]):
                    if current_value > 0:
                        signal = "多头"
                        advice = "看涨"
                    elif current_value < 0:
                        signal = "空头"
                        advice = "看跌"
                    else:
                        signal = "中性"
                        advice = "观望"
                elif any(keyword in value_name.upper() for keyword in ["MACD_1", "MACD"]):
                    # MACD主线
                    if current_value > 0:
                        signal = "看涨"
                        advice = "关注买入机会"
                    else:
                        signal = "看跌"
                        advice = "注意风险"
                elif any(keyword in value_name.upper() for keyword in ["MACD_2", "SIGNAL"]):
                    # 信号线
                    if "上升" in trend:
                        signal = "看涨"
                        advice = "持有/买入"
                    elif "下降" in trend:
                        signal = "看跌"
                        advice = "观望/卖出"
                    else:
                        signal = "中性"
                        advice = "观望"
                else:
                    # 默认MACD处理
                    if "上升" in trend:
                        signal = "看涨"
                        advice = "关注买入机会"
                    elif "下降" in trend:
                        signal = "看跌"
                        advice = "注意风险"
                    else:
                        signal = "中性"
                        advice = "观望"

            elif "KDJ" in indicator_name or "随机指标" in indicator_name:
                if current_value > 80:
                    signal = "超买"
                    advice = "考虑卖出"
                elif current_value < 20:
                    signal = "超卖"
                    advice = "考虑买入"
                else:
                    signal = "中性"
                    advice = "观望"

            elif "形态" in indicator_name:
                signal = "形态信号"
                advice = "参考形态分析"

            else:
                # 通用信号生成
                if "上升" in trend:
                    signal = "看涨"
                    advice = "关注买入机会"
                elif "下降" in trend:
                    signal = "看跌"
                    advice = "注意风险"
                else:
                    signal = "中性"
                    advice = "观望"

        except Exception as e:
            logger.error(f"生成信号建议时出错: {str(e)}")
            signal = "未知"
            advice = "需要分析"

        return signal, advice

    def _set_row_color(self, row: int, signal: str):
        """根据信号设置行颜色 - 增强版"""
        try:
            # 获取趋势信息用于更精确的颜色设置
            trend_item = self.technical_table.item(row, 5)  # 趋势列
            trend_info = trend_item.text() if trend_item else ""

            # 获取强度信息
            strength_item = self.technical_table.item(row, 4)  # 强度列
            strength_info = strength_item.text() if strength_item else ""

            # 根据信号类型和趋势确定颜色
            if "超买" in signal or "看跌" in signal or "下降" in trend_info:
                if "强" in strength_info:
                    color = QColor(200, 255, 200)  # 深绿色
                else:
                    color = QColor(230, 255, 230)  # 浅绿色

            elif "超卖" in signal or "看涨" in signal or "上升" in trend_info:
                if "强" in strength_info:
                    color = QColor(255, 200, 200)  # 深红色
                else:
                    color = QColor(255, 230, 230)  # 浅红色
            elif "中性" in signal or "持平" in trend_info:
                color = QColor(248, 249, 250)  # 浅灰色
            elif "形态" in signal:
                color = QColor(255, 248, 220)  # 浅黄色（形态信号）
            else:
                return  # 使用默认颜色

            # 应用颜色到整行
            for col in range(self.technical_table.columnCount()):
                item = self.technical_table.item(row, col)
                if item:
                    item.setBackground(color)

                    # 为特定列设置文字颜色
                    if col == 3:  # 信号列
                        if "看涨" in signal or "超卖" in signal:
                            item.setForeground(QColor(220, 20, 60))  # 红色文字
                        elif "看跌" in signal or "超买" in signal:
                            item.setForeground(QColor(0, 128, 0))  # 绿色文字

                    elif col == 5:  # 趋势列
                        if "上升" in trend_info:
                            item.setForeground(QColor(220, 20, 60))  # 红色文字

                        elif "下降" in trend_info:
                            item.setForeground(QColor(0, 128, 0))  # 绿色文字

        except Exception as e:
            logger.error(f"设置行颜色失败: {str(e)}")

    def clear_cache(self):
        """清除缓存"""
        self.indicator_cache.clear()
        logger.info("指标缓存已清除")
        QMessageBox.information(self, "提示", "指标缓存已清除")

    def clear_indicators(self):
        """清除指标"""
        self._do_clear_data()
        logger.info("技术指标已清除")

    def _get_export_specific_data(self) -> Optional[Dict[str, Any]]:
        """获取技术分析特定的导出数据"""
        return {
            'analysis_type': 'technical_indicators',
            'indicator_results': self.indicator_results,
            'current_parameters': self.get_current_params(),
            'batch_mode': self.batch_checkbox.isChecked(),
            'auto_calculate': self.auto_calculate,
            'cache_size': len(self.indicator_cache),
            'selected_indicator': self.indicator_combo.currentText(),
            'selected_category': self.category_combo.currentText(),
            'batch_indicators': self.batch_indicators,
            'table_data': self._get_table_data() if hasattr(self, 'technical_table') else None
        }

    def _get_table_data(self) -> List[Dict[str, Any]]:
        """获取表格数据用于导出"""
        try:
            if not hasattr(self, 'technical_table') or self.technical_table.rowCount() == 0:
                return []

            table_data = []
            headers = []

            # 获取表头
            for col in range(self.technical_table.columnCount()):
                header_item = self.technical_table.horizontalHeaderItem(col)
                headers.append(header_item.text()
                               if header_item else f"Column_{col}")

            # 获取数据行
            for row in range(self.technical_table.rowCount()):
                row_data = {}
                for col in range(self.technical_table.columnCount()):
                    item = self.technical_table.item(row, col)
                    row_data[headers[col]] = item.text() if item else ""
                table_data.append(row_data)

            return table_data

        except Exception as e:
            logger.error(f"获取表格数据失败: {e}")
            return []

    def export_technical_data(self):
        """导出技术分析数据 - 使用统一的导出接口"""
        try:
            if not hasattr(self, 'technical_table') or self.technical_table.rowCount() == 0:
                self.show_no_data_warning("技术分析数据")
                return

            format_type = self.export_format_combo.currentText().lower()

            # 获取保存文件路径
            from PyQt5.QtWidgets import QFileDialog

            file_extensions = {
                'excel': ('Excel files (*.xlsx)', '.xlsx'),
                'csv': ('CSV files (*.csv)', '.csv'),
                'json': ('JSON files (*.json)', '.json')
            }

            if format_type not in file_extensions:
                QMessageBox.warning(self, "错误", f"不支持的导出格式: {format_type}")
                return

            ext_desc, ext = file_extensions[format_type]
            default_filename = f"technical_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"

            filename, _ = QFileDialog.getSaveFileName(
                self, "导出技术分析数据", default_filename, ext_desc)
            if not filename:
                return

            # 使用基类的统一导出功能
            if format_type == 'json':
                success = self.export_to_file(filename, 'json')
            elif format_type == 'csv':
                success = self.export_to_file(filename, 'csv')
            elif format_type == 'excel':
                # Excel需要特殊处理
                success = self._export_to_excel_enhanced(filename)
            else:
                success = False

            if success:
                QMessageBox.information(self, "成功", f"技术分析数据已导出到: {filename}")
            else:
                QMessageBox.critical(self, "错误", "导出失败，请检查文件路径和权限")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

    def _export_to_excel_enhanced(self, filename: str) -> bool:
        """增强版Excel导出"""
        try:

            # 获取完整的导出数据
            export_data = self.export_data('excel')
            if not export_data:
                return False

            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                # 导出技术指标表格数据
                table_data = export_data.get(
                    'specific_data', {}).get('table_data', [])
                if table_data:
                    df_indicators = pd.DataFrame(table_data)
                    df_indicators.to_excel(
                        writer, sheet_name='技术指标', index=False)

                # 导出元数据
                metadata = export_data.get('metadata', {})
                df_meta = pd.DataFrame([metadata])
                df_meta.to_excel(writer, sheet_name='元数据', index=False)

                # 导出性能统计
                perf_stats = export_data.get('performance_stats', {})
                if perf_stats:
                    df_perf = pd.DataFrame([perf_stats])
                    df_perf.to_excel(writer, sheet_name='性能统计', index=False)

                # 导出数据统计（如果有）
                data_stats = export_data.get('data_statistics', {})
                if data_stats:
                    df_stats = pd.DataFrame(data_stats)
                    df_stats.to_excel(writer, sheet_name='数据统计', index=False)

            return True

        except ImportError:
            # 如果没有pandas，回退到CSV
            csv_filename = filename.replace('.xlsx', '.csv')
            return self.export_to_file(csv_filename, 'csv')
        except Exception as e:
            logger.error(f"Excel导出失败: {e}")
            return False

    def apply_batch_selection(self, dialog):
        """应用批量选择 - 保持向后兼容"""
        if hasattr(self, 'batch_checkboxes'):
            # 旧版本的复选框方式
            self.batch_indicators = [
                indicator for indicator, checkbox in self.batch_checkboxes.items()
                if checkbox.isChecked()
            ]
            dialog.accept()
        else:
            # 新版本的表格方式
            self.apply_batch_selection_table(dialog)

    def show_loading(self, message="正在分析..."):
        """显示加载状态 - 本地实现"""
        self.is_loading = True

        # 禁用计算按钮
        if hasattr(self, 'calc_btn'):
            self.calc_btn.setEnabled(False)
            self.calc_btn.setText("计算中...")

        # 更新状态标签
        if hasattr(self, 'stats_label'):
            self.stats_label.setText(f"状态: {message}")
            self.stats_label.setStyleSheet(
                "QLabel { font-weight: bold; color: #007bff; }")

        # 设置鼠标为等待状态
        self.setCursor(Qt.WaitCursor)

        # 强制刷新界面
        QApplication.processEvents()

        logger.debug(f"{self.__class__.__name__}: {message}")

    def hide_loading(self):
        """隐藏加载状态 - 本地实现"""
        self.is_loading = False

        # 恢复计算按钮
        if hasattr(self, 'calc_btn'):
            self.calc_btn.setEnabled(True)
            self.calc_btn.setText("计算指标")

        # 恢复鼠标状态
        self.setCursor(Qt.ArrowCursor)

        # 强制刷新界面
        QApplication.processEvents()

    def update_loading_progress(self, message: str, progress: int = 0):
        """更新加载进度 - 本地实现"""
        if hasattr(self, 'stats_label'):
            self.stats_label.setText(f"状态: {message} ({progress}%)")

        # 强制刷新界面
        QApplication.processEvents()

    def _get_bold_font(self):
        """获取粗体字体"""
        font = QFont()
        font.setBold(True)
        return font

    def create_export_section(self):
        """创建导出功能区域"""
        export_group = QGroupBox("数据导出")
        export_layout = QHBoxLayout(export_group)

        # 导出格式选择
        export_layout.addWidget(QLabel("导出格式:"))
        self.export_format_combo = QComboBox()
        self.export_format_combo.setFixedWidth(60)
        self.export_format_combo.addItems(["Excel", "CSV", "JSON"])
        export_layout.addWidget(self.export_format_combo)

        # 导出按钮
        export_btn = QPushButton("导出技术分析结果")
        export_btn.setStyleSheet(
            "QPushButton { background-color: #17a2b8; color: white; }")
        export_btn.clicked.connect(self.export_technical_data)
        export_layout.addWidget(export_btn)

        export_layout.addStretch()
        return export_group

    def update_analysis(self, analysis_data: Dict[str, Any]):
        """更新分析数据 - 为与RightPanel兼容而添加的方法

        Args:
            analysis_data: 包含技术分析数据的字典
        """
        try:
            # 如果分析数据中包含技术指标信息，可以在这里处理
            technical_indicators = analysis_data.get('technical_indicators', {})

            if technical_indicators:
                logger.info("收到分析数据，技术指标数据已更新")
                # 这里可以根据需要处理预计算的技术指标数据
                # 例如：显示在状态栏或进行其他处理
                indicator_count = len(technical_indicators)
                self.update_status(f"收到 {indicator_count} 个预计算指标")
            else:
                logger.debug("分析数据中未包含技术指标")

        except Exception as e:
            logger.error(f"更新分析数据失败: {e}")

    def set_kdata(self, kdata):
        """重写set_kdata方法，自动更新股票信息"""
        try:
            # 调用父类方法
            super().set_kdata(kdata)

        except Exception as e:
            logger.error(f"设置K线数据时出错: {str(e)}")

    def on_data_update(self, stock_data: Dict[str, Any]) -> None:
        """处理数据更新事件"""
        try:
            # 删除更新股票信息的调用
            if self.auto_calc_checkbox.isChecked():
                self.calculate_indicators()
        except Exception as e:
            logger.error(f"数据更新处理失败: {e}")

    def show_advanced_filter_dialog(self):
        """显示高级筛选对话框"""
        dialog = AdvancedFilterDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            filters = dialog.get_activate_filters()
            if filters:
                self.apply_table_filters(filters)
                self.clear_filter_btn.setEnabled(True)
            else:
                self.clear_table_filters()

    def show_batch_filter_dialog(self):
        """显示指标选股高级筛选对话框"""
        try:
            from gui.dialogs.batch_filter_dialog import CompactAdvancedFilterDialog

            # 获取当前表格的列配置
            columns_config = self._get_table_columns_config()

            dialog = CompactAdvancedFilterDialog(self, columns_config)
            dialog.filters_applied.connect(self.apply_compact_filters)

            if dialog.exec_() == QDialog.Accepted:
                filters = dialog.get_active_filters()
                if filters:
                    self.apply_table_filters(filters)
                    filter_count = len(filters)
                    self.filter_status_label.setText(f"已应用 {filter_count} 个筛选条件")
                    self.clear_filter_btn.setEnabled(True)
                else:
                    self.clear_table_filters()
        except Exception as e:
            logger.error(f"显示紧凑型筛选对话框失败: {e}")
            QMessageBox.warning(self, "错误", f"无法打开高级筛选对话框:\n{str(e)}")

    def _get_table_columns_config(self):
        """获取当前表格的列配置"""
        columns = []
        for i in range(self.technical_table.columnCount()):
            header_item = self.technical_table.horizontalHeaderItem(i)
            if header_item:
                columns.append(header_item.text())

        # 根据列名确定筛选类型
        config = {}
        for col in columns:
            if col == '日期':
                config[col] = {'type': 'date', 'label': '日期'}
            elif col in ['数值', '强度']:
                config[col] = {'type': 'numeric', 'label': col}
            elif col == '信号':
                config[col] = {
                    'type': 'selection',
                    'label': '信号',
                    'options': ['超买', '超卖', '看涨', '看跌', '中性', '形态信号']
                }
            elif col == '趋势':
                config[col] = {
                    'type': 'selection',
                    'label': '趋势',
                    'options': ['上升 ↑', '下降 ↓', '持平 →', 'N/A']
                }
            else:
                config[col] = {'type': 'text', 'label': col}

        return config

    def apply_compact_filters(self, filters):
        """应用指标选股筛选条件"""
        try:
            if filters:
                self.apply_table_filters(filters)
                filter_count = len(filters)
                self.filter_status_label.setText(f"已应用 {filter_count} 个筛选条件")
                self.clear_filter_btn.setEnabled(True)
            else:
                self.clear_table_filters()
        except Exception as e:
            logger.error(f"应用筛选条件失败: {e}")

    def apply_table_filters(self, filters: Dict[str, Any]):
        """应用指标选股筛选条件到表格"""
        try:
            if not hasattr(self, 'technical_table') or self.technical_table.rowCount() == 0:
                return

            active_filters = []
            hidden_rows = 0

            # 遍历所有行
            for row in range(self.technical_table.rowCount()):
                should_hide = False

                # 检查每个筛选条件
                for column_name, filter_config in filters.items():
                    if not filter_config.get('enabled', False):
                        continue

                    column_index = self._get_column_index_by_name(column_name)
                    if column_index == -1:
                        continue

                    item = self.technical_table.item(row, column_index)
                    if not item:
                        continue

                    cell_value = item.text()
                    filter_type = filter_config.get('type', 'text')

                    # 根据筛选类型进行检查
                    if filter_type == 'text':
                        pattern = filter_config.get('value', '').lower()
                        if pattern and pattern not in cell_value.lower():
                            should_hide = True
                            break
                    elif filter_type == 'numeric':
                        try:
                            numeric_value = float(cell_value.replace(',', ''))
                            min_val = filter_config.get('min_value')
                            max_val = filter_config.get('max_value')
                            if min_val is not None and numeric_value < min_val:
                                should_hide = True
                                break
                            if max_val is not None and numeric_value > max_val:
                                should_hide = True
                                break
                        except (ValueError, TypeError):
                            # 非数值数据，如果设置了数值筛选，则隐藏
                            should_hide = True
                            break
                    elif filter_type == 'selection':
                        selected_values = filter_config.get('selected_values', [])
                        if selected_values and cell_value not in selected_values:
                            should_hide = True
                            break
                    elif filter_type == 'date':
                        # 日期筛选逻辑
                        try:
                            cell_date = datetime.strptime(cell_value, "%Y-%m-%d %H:%M")
                            start_date = filter_config.get('start_date')
                            end_date = filter_config.get('end_date')
                            if start_date and cell_date < start_date:
                                should_hide = True
                                break
                            if end_date and cell_date > end_date:
                                should_hide = True
                                break
                        except (ValueError, TypeError):
                            should_hide = True
                            break

                # 隐藏或显示行
                self.technical_table.setRowHidden(row, should_hide)
                if should_hide:
                    hidden_rows += 1

            # 记录活跃的筛选条件
            for column_name, filter_config in filters.items():
                if filter_config.get('enabled', False):
                    active_filters.append(column_name)

            # 更新UI状态
            if active_filters:
                visible_rows = self.technical_table.rowCount() - hidden_rows
                self.filter_status_label.setText(f"筛选中: {len(active_filters)}个条件, 显示{visible_rows}行")
                self.clear_filter_btn.setEnabled(True)
            else:
                self.filter_status_label.setText("")
                self.clear_filter_btn.setEnabled(False)

        except Exception as e:
            logger.error(f"应用指标选股筛选失败: {str(e)}")

    def clear_table_filters(self):
        """清除所有筛选条件"""
        try:
            # 显示所有行
            for row in range(self.technical_table.rowCount()):
                self.technical_table.setRowHidden(row, False)

            # 重置UI状态
            self.filter_status_label.setText("")
            self.clear_filter_btn.setEnabled(False)

        except Exception as e:
            logger.error(f"清除筛选失败: {str(e)}")

    def _get_column_index_by_name(self, column_name: str) -> int:
        """根据列名获取列索引"""
        headers = ['日期', '指标', '数值', '信号', '强度', '趋势', '建议', '备注']
        try:
            return headers.index(column_name)
        except ValueError:
            return -1


class AdvancedFilterDialog(QDialog):
    """高级筛选对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("高级筛选")
        self.setModal(True)
        self.resize(600, 500)
        self.filters = {}
        self.create_ui()

    def create_ui(self):
        """创建筛选对话框UI"""
        layout = QVBoxLayout(self)

        # 说明文字
        info_label = QLabel("设置多列筛选条件，支持AND逻辑组合。")
        info_label.setStyleSheet("QLabel { color: #6c757d; font-style: italic; }")
        layout.addWidget(info_label)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 筛选条件容器
        filter_widget = QWidget()
        self.filter_layout = QVBoxLayout(filter_widget)

        # 定义列信息
        self.column_configs = {
            '日期': {'type': 'date', 'label': '日期时间'},
            '指标': {'type': 'text', 'label': '指标名称'},
            '数值': {'type': 'numeric', 'label': '数值'},
            '信号': {'type': 'selection', 'label': '信号', 'options': ['超买', '超卖', '看涨', '看跌', '中性', '形态信号']},
            '强度': {'type': 'selection', 'label': '强度', 'options': ['强', '中', '弱', 'N/A']},
            '趋势': {'type': 'selection', 'label': '趋势', 'options': ['上升 ↑', '下降 ↓', '持平 →', 'N/A']},
            '建议': {'type': 'text', 'label': '交易建议'},
            '备注': {'type': 'text', 'label': '备注信息'}
        }

        # 为每列创建筛选控件
        for column_name, config in self.column_configs.items():
            self.create_filter_group(column_name, config)

        scroll.setWidget(filter_widget)
        layout.addWidget(scroll)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        # 重置按钮
        reset_btn = QPushButton("重置")
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #545b62;
            }
        """)
        reset_btn.clicked.connect(self.reset_filters)
        btn_layout.addWidget(reset_btn)

        # 确定按钮
        ok_btn = QPushButton("应用筛选")
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def create_filter_group(self, column_name: str, config: Dict[str, Any]):
        """为指定列创建筛选组"""
        group = QGroupBox(config['label'])
        group.setCheckable(True)
        group.setChecked(False)
        group_layout = QVBoxLayout(group)

        filter_type = config['type']
        filter_controls = {}

        if filter_type == 'text':
            # 文本筛选
            text_edit = QLineEdit()
            text_edit.setPlaceholderText(f"输入{config['label']}关键词...")
            group_layout.addWidget(text_edit)
            filter_controls['text_input'] = text_edit

        elif filter_type == 'numeric':
            # 数值范围筛选
            range_layout = QHBoxLayout()

            range_layout.addWidget(QLabel("最小值:"))
            min_input = QLineEdit()
            min_input.setPlaceholderText("留空表示无限制")
            range_layout.addWidget(min_input)

            range_layout.addWidget(QLabel("最大值:"))
            max_input = QLineEdit()
            max_input.setPlaceholderText("留空表示无限制")
            range_layout.addWidget(max_input)

            group_layout.addLayout(range_layout)
            filter_controls['min_input'] = min_input
            filter_controls['max_input'] = max_input

        elif filter_type == 'selection':
            # 选择列表筛选
            options = config.get('options', [])
            list_widget = QListWidget()
            list_widget.setSelectionMode(QAbstractItemView.MultiSelection)
            for option in options:
                item = QListWidgetItem(option)
                list_widget.addItem(item)
            group_layout.addWidget(list_widget)
            filter_controls['list_widget'] = list_widget

        elif filter_type == 'date':
            # 日期范围筛选
            date_layout = QGridLayout()

            date_layout.addWidget(QLabel("开始日期:"), 0, 0)
            start_date = QDateTimeEdit()
            start_date.setCalendarPopup(True)
            start_date.setDateTime(QDateTime.currentDateTime().addDays(-30))
            date_layout.addWidget(start_date, 0, 1)

            date_layout.addWidget(QLabel("结束日期:"), 1, 0)
            end_date = QDateTimeEdit()
            end_date.setCalendarPopup(True)
            end_date.setDateTime(QDateTime.currentDateTime())
            date_layout.addWidget(end_date, 1, 1)

            group_layout.addLayout(date_layout)
            filter_controls['start_date'] = start_date
            filter_controls['end_date'] = end_date

        # 存储筛选控件
        self.filters[column_name] = {
            'group': group,
            'type': filter_type,
            'controls': filter_controls
        }

        self.filter_layout.addWidget(group)

    def get_activate_filters(self) -> Dict[str, Any]:
        """获取当前的筛选设置"""
        active_filters = {}

        for column_name, filter_info in self.filters.items():
            group = filter_info['group']
            filter_type = filter_info['type']
            controls = filter_info['controls']

            if not group.isChecked():
                continue

            filter_config = {
                'enabled': True,
                'type': filter_type
            }

            if filter_type == 'text':
                text_value = controls['text_input'].text().strip()
                if text_value:
                    filter_config['value'] = text_value

            elif filter_type == 'numeric':
                min_text = controls['min_input'].text().strip()
                max_text = controls['max_input'].text().strip()

                try:
                    if min_text:
                        filter_config['min_value'] = float(min_text)
                    if max_text:
                        filter_config['max_value'] = float(max_text)
                except ValueError:
                    continue

            elif filter_type == 'selection':
                list_widget = controls['list_widget']
                selected_items = []
                for i in range(list_widget.count()):
                    item = list_widget.item(i)
                    if item.isSelected():
                        selected_items.append(item.text())

                if selected_items:
                    filter_config['selected_values'] = selected_items

            elif filter_type == 'date':
                start_date = controls['start_date'].dateTime().toPyDateTime()
                end_date = controls['end_date'].dateTime().toPyDateTime()
                filter_config['start_date'] = start_date
                filter_config['end_date'] = end_date

            # 只有当筛选条件有效时才添加
            if len(filter_config) > 2:  # enabled和type之外还有其他条件
                active_filters[column_name] = filter_config

        return active_filters

    def reset_filters(self):
        """重置所有筛选条件"""
        for filter_info in self.filters.values():
            group = filter_info['group']
            group.setChecked(False)

            filter_type = filter_info['type']
            controls = filter_info['controls']

            if filter_type == 'text':
                controls['text_input'].clear()
            elif filter_type == 'numeric':
                controls['min_input'].clear()
                controls['max_input'].clear()
            elif filter_type == 'selection':
                list_widget = controls['list_widget']
                list_widget.clearSelection()
            elif filter_type == 'date':
                controls['start_date'].setDateTime(QDateTime.currentDateTime().addDays(-30))
                controls['end_date'].setDateTime(QDateTime.currentDateTime())

    def resizeEvent(self, event):
        """窗口大小改变事件处理 - 使用基类统一响应式系统"""
        super().resizeEvent(event)

    def _update_responsive_layout(self):
        """更新响应式布局 - 已集成到基类统一系统"""
        pass
