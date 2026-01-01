from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd

from .plugin_types import PluginType
from .data_source_extensions import PluginInfo


class IIndicatorPluginV2(ABC):
    """
    指标插件 V2 标准接口

    统一插件元信息、初始化、配置与计算接口，便于与系统配置入库、UI动态表单、日志与度量对齐。
    """

    @abstractmethod
    def get_plugin_info(self) -> PluginInfo:
        """返回插件元信息（ID、名称、版本、作者、支持类型等）。"""
        pass

    def get_config_schema(self) -> Dict[str, Any]:
        """返回 JSON Schema，用于生成配置表单与参数校验。可选，默认空对象。"""
        return {"type": "object", "properties": {}, "additionalProperties": True}

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """可选：业务侧快速校验（JSON Schema 校验由上层完成）。"""
        return True

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化插件，合并配置并准备运行环境。"""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """关闭插件并释放资源。"""
        pass

    @abstractmethod
    def calculate(self, data: pd.DataFrame, **params) -> Dict[str, pd.Series]:
        """计算指标，返回包含若干序列的字典。"""
        pass
