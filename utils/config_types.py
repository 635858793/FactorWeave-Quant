"""
Configuration Types Module

This module defines configuration-related data classes and types.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from .theme_types import Theme
from PyQt5.QtCore import QObject, pyqtSignal


@dataclass
class ThemeConfig:
    """Theme configuration settings"""
    theme: Theme = Theme.LIGHT
    name: str = "light"
    font_family: str = "Arial"
    font_size: int = 12
    theme_name: str = "default"  # 当前选中的主题名称（用于持久化）

    def __hash__(self):
        """Make ThemeConfig hashable by using theme name as hash"""
        return hash(self.theme.name)

    def __eq__(self, other):
        """Compare ThemeConfig objects by their theme"""
        if not isinstance(other, ThemeConfig):
            return NotImplemented
        return self.theme == other.theme

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary

        Returns:
            Dictionary representation of config
        """
        return {
            "theme": self.theme.name.lower(),
            "name": self.name,
            "font_family": self.font_family,
            "font_size": self.font_size,
            "theme_name": self.theme_name
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ThemeConfig':
        """Create config from dictionary

        Args:
            data: Dictionary containing config data

        Returns:
            ThemeConfig instance
        """
        return cls(
            theme=Theme.from_str(data.get("theme", "light")),
            name=data.get("name", "light"),
            font_family=data.get("font_family", "Arial"),
            font_size=data.get("font_size", 12),
            theme_name=data.get("theme_name", "default")
        )


@dataclass
class ChartConfig:
    """Chart display configuration"""
    show_grid: bool = True
    show_volume: bool = True
    show_ma: bool = True
    ma_periods: list[int] = field(default_factory=lambda: [5, 10, 20, 60])
    candlestick_width: float = 0.8
    chart_height: int = 600
    chart_width: int = 800
    auto_update: bool = True
    update_interval: int = 5
    default_period: str = "D"
    default_indicators: list[str] = field(
        default_factory=lambda: ["MA", "MACD", "RSI"])
    font_family: str = "Microsoft YaHei"
    font_size: int = 12

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary

        Returns:
            Dictionary representation of config
        """
        return {
            "show_grid": self.show_grid,
            "show_volume": self.show_volume,
            "show_ma": self.show_ma,
            "ma_periods": self.ma_periods,
            "candlestick_width": self.candlestick_width,
            "chart_height": self.chart_height,
            "chart_width": self.chart_width,
            "auto_update": self.auto_update,
            "update_interval": self.update_interval,
            "default_period": self.default_period,
            "default_indicators": self.default_indicators,
            "font_family": self.font_family,
            "font_size": self.font_size
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChartConfig':
        """Create config from dictionary

        Args:
            data: Dictionary containing config data

        Returns:
            ChartConfig instance
        """
        return cls(
            show_grid=data.get("show_grid", True),
            show_volume=data.get("show_volume", True),
            show_ma=data.get("show_ma", True),
            ma_periods=data.get("ma_periods", [5, 10, 20, 60]),
            candlestick_width=data.get("candlestick_width", 0.8),
            chart_height=data.get("chart_height", 600),
            chart_width=data.get("chart_width", 800),
            auto_update=data.get("auto_update", True),
            update_interval=data.get("update_interval", 5),
            default_period=data.get("default_period", "D"),
            default_indicators=data.get(
                "default_indicators", ["MA", "MACD", "RSI"]),
            font_family=data.get("font_family", "Microsoft YaHei"),
            font_size=data.get("font_size", 12)
        )


@dataclass
class TradingConfig:
    """Trading parameters configuration — 基于实测模拟交易的优化默认值"""
    default_symbol: str = "000001"
    default_period: str = "1d"
    auto_refresh: bool = True
    refresh_interval: int = 60
    trade_amount: float = 10000.0
    commission_rate: float = 0.0003
    slippage: float = 0.0001
    initial_cash: float = 500000.0
    position_ratio: float = 0.30
    single_stock_ratio: float = 0.15
    stop_loss: float = 0.05
    take_profit: float = 0.12
    trailing_stop: float = 0.03
    time_stop: int = 5
    max_positions: int = 5
    lot_size: int = 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "default_symbol": self.default_symbol,
            "default_period": self.default_period,
            "auto_refresh": self.auto_refresh,
            "refresh_interval": self.refresh_interval,
            "trade_amount": self.trade_amount,
            "commission_rate": self.commission_rate,
            "slippage": self.slippage,
            "initial_cash": self.initial_cash,
            "position_ratio": self.position_ratio,
            "single_stock_ratio": self.single_stock_ratio,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "trailing_stop": self.trailing_stop,
            "time_stop": self.time_stop,
            "max_positions": self.max_positions,
            "lot_size": self.lot_size,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradingConfig':
        return cls(
            default_symbol=data.get("default_symbol", "000001"),
            default_period=data.get("default_period", "1d"),
            auto_refresh=data.get("auto_refresh", True),
            refresh_interval=data.get("refresh_interval", 60),
            trade_amount=data.get("trade_amount", 10000.0),
            commission_rate=data.get("commission_rate", 0.0003),
            slippage=data.get("slippage", 0.0001),
            initial_cash=data.get("initial_cash", 500000.0),
            position_ratio=data.get("position_ratio", 0.30),
            single_stock_ratio=data.get("single_stock_ratio", 0.15),
            stop_loss=data.get("stop_loss", 0.05),
            take_profit=data.get("take_profit", 0.12),
            trailing_stop=data.get("trailing_stop", 0.03),
            time_stop=data.get("time_stop", 5),
            max_positions=data.get("max_positions", 5),
            lot_size=data.get("lot_size", 100),
        )


@dataclass
class AppConfig:
    """Application configuration container"""
    theme: ThemeConfig = field(default_factory=ThemeConfig)
    chart: ChartConfig = field(default_factory=ChartConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary

        Returns:
            Dictionary representation of config
        """
        return {
            "theme": self.theme.to_dict(),
            "chart": self.chart.to_dict(),
            "trading": self.trading.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        """Create config from dictionary

        Args:
            data: Dictionary containing config data

        Returns:
            AppConfig instance
        """
        theme_data = data.get("theme", {})
        chart_data = data.get("chart", {})
        trading_data = data.get("trading", {})

        return cls(
            theme=ThemeConfig.from_dict(theme_data),
            chart=ChartConfig.from_dict(chart_data),
            trading=TradingConfig.from_dict(trading_data)
        )


@dataclass
class DataConfig:
    """Data configuration"""
    enable_cache: bool = True
    max_cache_size: int = 1000
    auto_update: bool = True
    update_interval: int = 3600
    data_source: str = 'local'
    backup_enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary

        Returns:
            Dictionary representation of config
        """
        return {
            "enable_cache": self.enable_cache,
            "max_cache_size": self.max_cache_size,
            "auto_update": self.auto_update,
            "update_interval": self.update_interval,
            "data_source": self.data_source,
            "backup_enabled": self.backup_enabled
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataConfig':
        """Create config from dictionary

        Args:
            data: Dictionary containing config data

        Returns:
            DataConfig instance
        """
        return cls(
            enable_cache=data.get("enable_cache", True),
            max_cache_size=data.get("max_cache_size", 1000),
            auto_update=data.get("auto_update", True),
            update_interval=data.get("update_interval", 3600),
            data_source=data.get("data_source", 'local'),
            backup_enabled=data.get("backup_enabled", True)
        )


@dataclass
class UIConfig:
    """UI configuration"""
    font_size: int = 12
    language: str = 'zh_CN'
    show_tooltips: bool = True
    confirm_exit: bool = True
    layout: str = 'default'
    window_size: Dict[str, int] = None

    def __post_init__(self):
        if self.window_size is None:
            self.window_size = {'width': 1200, 'height': 800}

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary

        Returns:
            Dictionary representation of config
        """
        return {
            "font_size": self.font_size,
            "language": self.language,
            "show_tooltips": self.show_tooltips,
            "confirm_exit": self.confirm_exit,
            "layout": self.layout,
            "window_size": self.window_size
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UIConfig':
        """Create config from dictionary

        Args:
            data: Dictionary containing config data

        Returns:
            UIConfig instance
        """
        return cls(
            font_size=data.get("font_size", 12),
            language=data.get("language", 'zh_CN'),
            show_tooltips=data.get("show_tooltips", True),
            confirm_exit=data.get("confirm_exit", True),
            layout=data.get("layout", 'default'),
            window_size=data.get("window_size", {'width': 1200, 'height': 800})
        )


@dataclass
class LoggingConfig(QObject):
    """纯Loguru简化日志配置类 - 替代复杂的传统日志配置"""

    # 定义信号
    config_changed = pyqtSignal(object)  # 配置变更信号

    def __init__(self, **kwargs):
        """初始化简化的Loguru日志配置

        Args:
            **kwargs: 配置参数
        """
        super().__init__()

        # 简化为Loguru核心配置
        self.level = kwargs.get("level", "INFO")
        self.enable_console = kwargs.get("enable_console", True)
        self.enable_file = kwargs.get("enable_file", True)
        self.enable_async = kwargs.get("enable_async", True)
        self.log_directory = kwargs.get("log_directory", "logs")

        # Loguru特有配置
        self.rotation = kwargs.get("rotation", "100 MB")
        self.retention = kwargs.get("retention", "30 days")
        self.compression = kwargs.get("compression", "zip")
        self.backtrace = kwargs.get("backtrace", True)
        self.diagnose = kwargs.get("diagnose", True)

    def validate(self) -> tuple[bool, str]:
        """验证配置是否有效

        Returns:
            tuple[bool, str]: (是否有效, 错误信息)
        """
        # 验证日志级别
        valid_levels = ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]
        if self.level not in valid_levels:
            return False, f"无效的日志级别: {self.level}，必须是 {', '.join(valid_levels)} 之一"

        return True, "配置验证通过"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            配置字典
        """
        return {
            "level": self.level,
            "enable_console": self.enable_console,
            "enable_file": self.enable_file,
            "enable_async": self.enable_async,
            "log_directory": self.log_directory,
            "rotation": self.rotation,
            "retention": self.retention,
            "compression": self.compression,
            "backtrace": self.backtrace,
            "diagnose": self.diagnose
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LoggingConfig':
        """从字典创建配置

        Args:
            data: 配置字典

        Returns:
            LoggingConfig实例
        """
        return cls(**data)

    def emit_config_changed(self):
        """发射配置变更信号"""
        self.config_changed.emit(self)


class UIStyleConfig:
    """UI样式配置"""
    font_family: str = "Microsoft YaHei"  # 默认使用微软雅黑
    font_size: int = 10
    # ... existing code ...
