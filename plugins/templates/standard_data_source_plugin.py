"""
标准数据源插件模板

为FactorWeave-Quant系统提供标准化的数据源插件开发模板，
确保所有数据源插件都遵循统一的接口规范和最佳实践。

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-17
"""

import pandas as pd
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from loguru import logger
from core.data_source_extensions import IDataSourcePlugin, PluginInfo, HealthCheckResult, ConnectionInfo
from core.plugin_types import AssetType, DataType, PluginType


@dataclass
class PluginConfig:
    """插件配置基类"""
    api_endpoint: str = ""
    api_key: Optional[str] = None
    timeout: int = 30
    retry_count: int = 3
    rate_limit_requests: int = 100
    rate_limit_period: int = 60  # 秒
    enable_cache: bool = True
    cache_ttl: int = 300  # 秒

    # 数据源特定配置
    supported_markets: List[str] = field(default_factory=lambda: ["SH", "SZ"])
    supported_frequencies: List[str] = field(default_factory=lambda: ["1m", "5m", "15m", "30m", "60m", "D", "W", "M"])

    # 质量控制配置
    min_data_quality_score: float = 0.8
    enable_data_validation: bool = True
    enable_anomaly_detection: bool = True


class StandardDataSourcePlugin(IDataSourcePlugin, ABC):
    """
    标准数据源插件基类

    提供数据源插件的标准实现框架，包括：
    1. 连接管理
    2. 数据获取标准化
    3. 错误处理
    4. 性能监控
    5. 数据质量验证
    """

    def __init__(self, plugin_id: str, plugin_name: str, config: PluginConfig = None):
        """
        初始化标准数据源插件

        Args:
            plugin_id: 插件唯一标识
            plugin_name: 插件显示名称
            config: 插件配置
        """
        self.plugin_id = plugin_id
        self.plugin_name = plugin_name
        self.config = config or PluginConfig()

        # 连接状态
        self._is_connected = False
        self._connection_info = None
        self._last_connection_time = None

        # 连接验证防抖 (R259: R247 "数据级验证 + 30s 防抖" 下沉基类)
        # 默认钩子 _test_connection() 回退标志位, 行为与纯标志位一致; 子类可覆写为数据级验证
        self._connection_verify_interval = timedelta(seconds=30)
        self._last_connection_verify_time = None

        # 性能统计
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_response_time": 0.0,
            "last_request_time": None
        }

        # 健康状态
        self._last_health_check = None
        self._health_check_interval = timedelta(minutes=5)

        # 数据质量监控
        self._quality_stats = {
            "avg_quality_score": 1.0,
            "anomaly_count": 0,
            "validation_failures": 0
        }

        # 日志器
        self.logger = logger.bind(plugin=plugin_id)

        self.logger.info(f"标准数据源插件初始化: {plugin_name}")

    @property
    def plugin_info(self) -> PluginInfo:
        """获取插件信息"""
        return PluginInfo(
            id=self.plugin_id,
            name=self.plugin_name,
            version=self.get_version(),
            description=self.get_description(),
            author=self.get_author(),
            supported_asset_types=self.get_supported_asset_types(),
            supported_data_types=self.get_supported_data_types(),
            capabilities={
                **self.get_capabilities(),
                'plugin_type': PluginType.DATA_SOURCE,
                'priority': self.get_priority(),
                'weight': self.get_weight()
            }
        )

    # 抽象方法 - 子类必须实现
    @abstractmethod
    def get_version(self) -> str:
        """获取插件版本"""
        pass

    @abstractmethod
    def get_description(self) -> str:
        """获取插件描述"""
        pass

    @abstractmethod
    def get_author(self) -> str:
        """获取插件作者"""
        pass

    @abstractmethod
    def get_supported_asset_types(self) -> List[AssetType]:
        """获取支持的资产类型"""
        pass

    @abstractmethod
    def get_supported_data_types(self) -> List[DataType]:
        """获取支持的数据类型"""
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """获取插件能力"""
        pass

    @abstractmethod
    def _internal_connect(self, **kwargs) -> bool:
        """内部连接实现 - 子类实现具体连接逻辑"""
        pass

    @abstractmethod
    def _internal_disconnect(self) -> bool:
        """内部断开连接实现 - 子类实现具体断开逻辑"""
        pass

    @abstractmethod
    def _internal_get_asset_list(self, asset_type: AssetType, market: str = None) -> List[Dict[str, Any]]:
        """内部获取资产列表实现"""
        pass

    @abstractmethod
    def _internal_get_kdata(self, symbol: str, freq: str = "D",
                            start_date: str = None, end_date: str = None,
                            count: int = None) -> pd.DataFrame:
        """内部获取K线数据实现"""
        pass

    @abstractmethod
    def _internal_get_real_time_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """内部获取实时行情实现"""
        pass

    # 可选实现的方法
    def get_priority(self) -> int:
        """获取插件优先级 (数值越小优先级越高)"""
        return 50

    def get_weight(self) -> float:
        """获取插件权重"""
        return 1.0

    def get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "api_endpoint": self.config.api_endpoint,
            "timeout": self.config.timeout,
            "retry_count": self.config.retry_count,
            "rate_limit_requests": self.config.rate_limit_requests,
            "rate_limit_period": self.config.rate_limit_period,
            "enable_cache": self.config.enable_cache,
            "cache_ttl": self.config.cache_ttl,
            "supported_markets": self.config.supported_markets,
            "supported_frequencies": self.config.supported_frequencies
        }

    # IDataSourcePlugin接口实现
    def connect(self, **kwargs) -> bool:
        """连接数据源"""
        try:
            self.logger.info(f"尝试连接数据源: {self.plugin_name}")

            # 调用子类的具体连接实现
            result = self._internal_connect(**kwargs)

            if result:
                self._is_connected = True
                self._last_connection_time = datetime.now()
                self._last_connection_verify_time = self._last_connection_time
                self._connection_info = self._create_connection_info()
                self.logger.info(f"数据源连接成功: {self.plugin_name}")
            else:
                self._is_connected = False
                self.logger.error(f"数据源连接失败: {self.plugin_name}")

            return result

        except Exception as e:
            self._is_connected = False
            self.logger.error(f"数据源连接异常: {self.plugin_name} - {e}")
            return False

    def disconnect(self) -> bool:
        """断开数据源连接"""
        try:
            self.logger.info(f"断开数据源连接: {self.plugin_name}")

            result = self._internal_disconnect()

            if result:
                self._is_connected = False
                self._last_connection_verify_time = None
                self._connection_info = None
                self.logger.info(f"数据源断开成功: {self.plugin_name}")
            else:
                self.logger.error(f"数据源断开失败: {self.plugin_name}")

            return result

        except Exception as e:
            self.logger.error(f"数据源断开异常: {self.plugin_name} - {e}")
            return False

    def is_connected(self) -> bool:
        """检查连接状态

        R259 下沉: 30s 防抖 + 可插拔数据级验证钩子 _test_connection()。
        默认钩子回退标志位, 行为与纯标志位一致; 子类覆写钩子后启用真实取数验证。
        """
        if not self._is_connected:
            return False
        now = datetime.now()
        if self._last_connection_verify_time is not None:
            if now - self._last_connection_verify_time < self._connection_verify_interval:
                return True
        try:
            verified = self._test_connection()
        except Exception:
            self.logger.error(f"连接验证异常: {self.plugin_name}", exc_info=True)
            verified = False
        if verified:
            self._last_connection_verify_time = now
        else:
            self._is_connected = False
        return verified

    def _test_connection(self) -> bool:
        """连接可用性验证钩子; 默认回退标志位 (子类覆写为数据级验证)"""
        return self._is_connected

    def get_connection_info(self) -> ConnectionInfo:
        """获取连接信息"""
        return self._connection_info or ConnectionInfo(
            is_connected=self._is_connected,
            connection_time=self._last_connection_time,
            last_activity=getattr(self, '_last_activity', None),
            connection_params={
                'endpoint': self.config.api_endpoint,
                'plugin_id': self.plugin_id
            }
        )

    def health_check(self) -> HealthCheckResult:
        """健康检查"""
        try:
            current_time = datetime.now()

            # 检查是否需要进行健康检查
            if (self._last_health_check and
                    current_time - self._last_health_check < self._health_check_interval):
                # 使用缓存的健康检查结果
                return self._create_cached_health_result()

            # 执行实际健康检查
            health_result = self._perform_health_check()
            self._last_health_check = current_time

            return health_result

        except Exception as e:
            self.logger.error(f"健康检查异常: {self.plugin_name} - {e}")
            return HealthCheckResult(
                is_healthy=False,
                message=f"健康检查异常: {str(e)}",
                details={"error": str(e), "timestamp": datetime.now()}
            )

    def get_asset_list(self, asset_type: AssetType, market: str = None) -> List[Dict[str, Any]]:
        """获取资产列表"""
        return self._execute_with_monitoring(
            "get_asset_list",
            self._internal_get_asset_list,
            asset_type=asset_type,
            market=market
        )

    def get_kdata(self, symbol: str, freq: str = "D", start_date: str = None,
                  end_date: str = None, count: int = None) -> pd.DataFrame:
        """获取K线数据"""
        return self._execute_with_monitoring(
            "get_kdata",
            self._internal_get_kdata,
            symbol=symbol,
            freq=freq,
            start_date=start_date,
            end_date=end_date,
            count=count
        )

    def get_real_time_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """获取实时行情"""
        return self._execute_with_monitoring(
            "get_real_time_quotes",
            self._internal_get_real_time_quotes,
            symbols=symbols
        )

    def update_config(self, config: Dict[str, Any]) -> bool:
        """更新插件配置"""
        try:
            # 更新配置
            for key, value in config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
                    self.logger.debug(f"配置已更新: {key} = {value}")

            self.logger.info(f"插件配置更新成功: {self.plugin_name}")
            return True

        except Exception as e:
            self.logger.error(f"插件配置更新失败: {self.plugin_name} - {e}")
            return False

    # 辅助方法
    def _execute_with_monitoring(self, method_name: str, method_func, **kwargs):
        """带监控的方法执行"""
        start_time = datetime.now()
        self._stats["total_requests"] += 1
        self._stats["last_request_time"] = start_time

        try:
            # 检查连接状态
            if not self.is_connected():
                raise RuntimeError(f"数据源未连接: {self.plugin_name}")

            # 执行方法
            result = method_func(**kwargs)

            # 数据质量验证
            if self.config.enable_data_validation:
                quality_score = self._validate_data_quality(result)
                self._update_quality_stats(quality_score, True)

            # 更新成功统计
            execution_time = (datetime.now() - start_time).total_seconds()
            self._stats["successful_requests"] += 1
            self._update_avg_response_time(execution_time)

            self.logger.debug(f"方法执行成功: {method_name}, 用时: {execution_time:.3f}s")

            return result

        except Exception as e:
            # 更新失败统计
            execution_time = (datetime.now() - start_time).total_seconds()
            self._stats["failed_requests"] += 1
            self._update_avg_response_time(execution_time)

            if self.config.enable_data_validation:
                self._update_quality_stats(0.0, False)

            self.logger.error(f"方法执行失败: {method_name} - {e}")
            raise

    def _validate_data_quality(self, data: Any) -> float:
        """验证数据质量"""
        try:
            if data is None:
                return 0.0

            if isinstance(data, pd.DataFrame):
                return self._validate_dataframe_quality(data)
            elif isinstance(data, list):
                return self._validate_list_quality(data)
            else:
                return 0.8  # 默认质量分数

        except Exception as e:
            self.logger.warning(f"数据质量验证失败: {e}")
            return 0.5

    def _validate_dataframe_quality(self, df: pd.DataFrame) -> float:
        """验证DataFrame质量"""
        if df.empty:
            return 0.0

        # 计算完整性分数
        total_cells = df.shape[0] * df.shape[1]
        null_cells = df.isnull().sum().sum()
        completeness_score = 1.0 - (null_cells / total_cells) if total_cells > 0 else 0.0

        # 检查数据类型一致性
        consistency_score = 0.9  # 简化评估

        # 异常值检测
        anomaly_score = 0.1 if self._detect_anomalies(df) else 0.0

        # 综合质量分数
        quality_score = (completeness_score * 0.5 +
                         consistency_score * 0.3 +
                         (1 - anomaly_score) * 0.2)

        return max(0.0, min(1.0, quality_score))

    def _validate_list_quality(self, data: List) -> float:
        """验证列表质量"""
        if not data:
            return 0.0

        # 计算非空元素比例
        non_none_count = sum(1 for item in data if item is not None)
        completeness_score = non_none_count / len(data)

        return completeness_score * 0.8 + 0.2

    def _detect_anomalies(self, df: pd.DataFrame) -> bool:
        """简单的异常检测"""
        if not self.config.enable_anomaly_detection:
            return False

        try:
            # 检查数值列的异常值
            numeric_columns = df.select_dtypes(include=['number']).columns
            for col in numeric_columns:
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR

                outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)]
                if len(outliers) > 0.1 * len(df):  # 超过10%的异常值
                    return True

            return False

        except Exception:
            return False

    def _update_quality_stats(self, quality_score: float, success: bool) -> None:
        """更新质量统计"""
        if success:
            # 使用指数移动平均更新平均质量分数
            alpha = 0.1
            self._quality_stats["avg_quality_score"] = (
                alpha * quality_score + (1 - alpha) * self._quality_stats["avg_quality_score"]
            )
        else:
            self._quality_stats["validation_failures"] += 1

        if quality_score < self.config.min_data_quality_score:
            self._quality_stats["anomaly_count"] += 1

    def _update_avg_response_time(self, response_time: float) -> None:
        """更新平均响应时间"""
        if self._stats["total_requests"] == 1:
            self._stats["avg_response_time"] = response_time
        else:
            # 使用指数移动平均
            alpha = 0.1
            self._stats["avg_response_time"] = (
                alpha * response_time + (1 - alpha) * self._stats["avg_response_time"]
            )

    def _create_connection_info(self) -> ConnectionInfo:
        """创建连接信息"""
        return ConnectionInfo(
            is_connected=self._is_connected,
            connection_time=self._last_connection_time,
            last_activity=getattr(self, '_last_activity', None),
            connection_params={
                'endpoint': self.config.api_endpoint,
                'plugin_id': self.plugin_id,
                'plugin_name': self.plugin_name,
                'config': self.get_default_config()
            }
        )

    def _perform_health_check(self) -> HealthCheckResult:
        """执行健康检查"""
        health_issues = []

        try:
            # 检查连接状态
            if not self.is_connected():
                health_issues.append("数据源未连接")

            # 检查最近请求成功率
            if self._stats["total_requests"] > 10:
                success_rate = self._stats["successful_requests"] / self._stats["total_requests"]
                if success_rate < 0.8:
                    health_issues.append(f"成功率过低: {success_rate:.2%}")

            # 检查平均响应时间
            if self._stats["avg_response_time"] > self.config.timeout * 0.8:
                health_issues.append(f"响应时间过长: {self._stats['avg_response_time']:.2f}s")

            # 检查数据质量
            if self._quality_stats["avg_quality_score"] < self.config.min_data_quality_score:
                health_issues.append(f"数据质量不达标: {self._quality_stats['avg_quality_score']:.2f}")

            is_healthy = len(health_issues) == 0
            message = "健康" if is_healthy else f"发现问题: {', '.join(health_issues)}"

            return HealthCheckResult(
                is_healthy=is_healthy,
                message=message,
                details={
                    "connection_status": self.is_connected(),
                    "stats": self._stats.copy(),
                    "quality_stats": self._quality_stats.copy(),
                    "issues": health_issues,
                    "check_time": datetime.now()
                }
            )

        except Exception as e:
            return HealthCheckResult(
                is_healthy=False,
                message=f"健康检查执行失败: {str(e)}",
                details={"error": str(e)}
            )

    def _create_cached_health_result(self) -> HealthCheckResult:
        """创建缓存的健康检查结果"""
        return HealthCheckResult(
            is_healthy=self.is_connected(),
            message="使用缓存的健康检查结果",
            details={
                "cached": True,
                "connection_status": self.is_connected(),
                "last_check": self._last_health_check
            }
        )

    # 统计信息相关方法
    def get_stats(self) -> Dict[str, Any]:
        """获取插件统计信息"""
        return {
            "performance": self._stats.copy(),
            "quality": self._quality_stats.copy(),
            "connection": {
                "is_connected": self.is_connected(),
                "last_connection_time": self._last_connection_time
            },
            "config": self.get_default_config()
        }

    def reset_stats(self) -> None:
        """重置统计信息"""
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_response_time": 0.0,
            "last_request_time": None
        }

        self._quality_stats = {
            "avg_quality_score": 1.0,
            "anomaly_count": 0,
            "validation_failures": 0
        }

        self.logger.info(f"插件统计信息已重置: {self.plugin_name}")


class PluginValidationError(Exception):
    """插件验证错误"""
    pass


class PluginConnectionError(Exception):
    """插件连接错误"""
    pass


class PluginDataQualityError(Exception):
    """插件数据质量错误"""
    pass
