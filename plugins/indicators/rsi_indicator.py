"""
RSI指标插件示例（V2 接口）

- 不再使用旧装饰器/旧接口
- 使用 V2 接口：core.indicator_strategy_extensions.IIndicatorPluginV2
- 配置以 JSON 统一管理
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from PyQt5.QtWidgets import QWidget, QFormLayout, QSpinBox, QDoubleSpinBox

from core.indicator_strategy_extensions import IIndicatorPluginV2
from core.data_source_extensions import PluginInfo
from core.plugin_types import PluginType

class RSIIndicatorPlugin(IIndicatorPluginV2):
    """RSI 指标插件（V2）"""

    def __init__(self):
        self._config: Dict[str, Any] = {
            'period': 14,
            'overbought_level': 70.0,
            'oversold_level': 30.0
        }
        self._initialized: bool = False
        self.plugin_type = PluginType.INDICATOR

    def get_plugin_info(self) -> PluginInfo:
        return PluginInfo(
            id="indicator.rsi",
            name="RSI指标",
            version="2.0.0",
            description="相对强弱指标(RSI)，用于判断超买超卖状态",
            author="FactorWeave 团队",
            supported_asset_types=[],
            supported_data_types=[],
            capabilities={
                "indicators": ["RSI"],
                "parameters": ["period", "overbought_level", "oversold_level"],
                "signal_types": ["overbought", "oversold", "neutral"],
                "real_time_support": True
            }
        )

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'period': {'type': 'integer', 'minimum': 2, 'maximum': 100, 'default': 14, 'title': 'RSI周期'},
                'overbought_level': {'type': 'number', 'minimum': 50.0, 'maximum': 90.0, 'default': 70.0, 'title': '超买水平'},
                'oversold_level': {'type': 'number', 'minimum': 10.0, 'maximum': 50.0, 'default': 30.0, 'title': '超卖水平'}
            },
            'required': ['period', 'overbought_level', 'oversold_level'],
            'additionalProperties': False
        }

    def validate_config(self, config: Dict[str, Any]) -> bool:
        try:
            period = int(config.get('period', 14))
            overbought = float(config.get('overbought_level', 70.0))
            oversold = float(config.get('oversold_level', 30.0))
            if not (2 <= period <= 100):
                return False
            if not (50.0 <= overbought <= 90.0):
                return False
            if not (10.0 <= oversold <= 50.0):
                return False
            if overbought <= oversold:
                return False
            return True
        except Exception:
            return False

    def initialize(self, config: Dict[str, Any]) -> bool:
        try:
            merged = {**self._config, **(config or {})}
            if not self.validate_config(merged):
                return False
            self._config = merged
            self._initialized = True
            return True
        except Exception:
            return False

    def shutdown(self) -> None:
        self._initialized = False

    def calculate(self, data: pd.DataFrame, **params) -> Dict[str, pd.Series]:
        if not self._initialized:
            raise RuntimeError("RSI 指标未初始化")
        period = int(params.get('period', self._config['period']))
        if period < 2:
            raise ValueError("RSI周期必须大于等于2")
        if len(data) < period + 1:
            raise ValueError(f"数据长度不足，需要至少{period + 1}个数据点")

        close_prices = data['close']
        price_changes = close_prices.diff()
        gains = price_changes.where(price_changes > 0, 0)
        losses = -price_changes.where(price_changes < 0, 0)
        avg_gain = gains.ewm(alpha=1.0 / period, adjust=False).mean()
        avg_loss = losses.ewm(alpha=1.0 / period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.inf)
        rsi = 100 - (100 / (1 + rs))
        rsi = rsi.fillna(50)
        return {'rsi': rsi}

    def create_config_widget(self, parent: Optional[QWidget] = None) -> QWidget:
        widget = QWidget(parent)
        layout = QFormLayout(widget)
        period_spinbox = QSpinBox()
        period_spinbox.setRange(2, 100)
        period_spinbox.setValue(self._config['period'])
        overbought_spinbox = QDoubleSpinBox()
        overbought_spinbox.setRange(50.0, 90.0)
        overbought_spinbox.setSingleStep(1.0)
        overbought_spinbox.setValue(self._config['overbought_level'])
        oversold_spinbox = QDoubleSpinBox()
        oversold_spinbox.setRange(10.0, 50.0)
        oversold_spinbox.setSingleStep(1.0)
        oversold_spinbox.setValue(self._config['oversold_level'])
        layout.addRow("RSI周期:", period_spinbox)
        layout.addRow("超买水平:", overbought_spinbox)
        layout.addRow("超卖水平:", oversold_spinbox)

        def on_change():
            new_cfg = {
                'period': period_spinbox.value(),
                'overbought_level': overbought_spinbox.value(),
                'oversold_level': oversold_spinbox.value()
            }
            if self.validate_config(new_cfg):
                self._config.update(new_cfg)
        period_spinbox.valueChanged.connect(on_change)
        overbought_spinbox.valueChanged.connect(on_change)
        oversold_spinbox.valueChanged.connect(on_change)
        return widget
