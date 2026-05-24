from loguru import logger
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Financial Modeling Prep (FMP) 情绪数据源插件
基于FMP API获取社交情绪和新闻情绪数据
"""

import requests
import os
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from core.plugin_types import PluginType, PluginCategory
from plugins.sentiment_data_sources.base_sentiment_plugin import BaseSentimentPlugin
from plugins.sentiment_data_sources.config_base import ConfigurablePlugin, PluginConfigField, create_config_file_path, validate_api_key, validate_number_range
from plugins.sentiment_data_source_interface import SentimentData, SentimentResponse

class FMPSentimentPlugin(BaseSentimentPlugin, ConfigurablePlugin):
    """FMP情绪数据源插件"""

    def __init__(self):
        BaseSentimentPlugin.__init__(self)
        ConfigurablePlugin.__init__(self)
        self._config_file = create_config_file_path("fmp_sentiment")

        # 联网查询地址配置（endpointhost字段）
        # FMP情绪插件不需要联网查询地址，直接使用API，设为空
        self.endpointhost = []

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "name": "FMP社交情绪插件",
            "version": "1.0.0",
            "author": "FactorWeave-Quant  Team",
            "email": "support@factorweave.com",
            "website": "https://financialmodelingprep.com",
            "license": "MIT",
            "description": "基于Financial Modeling Prep API获取社交情绪、新闻情绪和股票趋势数据",
            "plugin_type": PluginType.DATA_SOURCE,
            "category": PluginCategory.CORE,
            "dependencies": ["requests>=2.25.0"],
            "min_framework_version": "1.0.0",
            "max_framework_version": "2.0.0",
            "documentation_url": "https://site.financialmodelingprep.com/developer/docs",
            "tags": ["sentiment", "fmp", "social", "news", "api"]
        }

    def get_config_schema(self) -> List[PluginConfigField]:
        """获取配置模式定义"""
        return [
            # 基本设置
            PluginConfigField(
                name="enabled",
                display_name="启用插件",
                field_type="boolean",
                default_value=True,
                description="是否启用FMP情绪数据插件",
                group="基本设置"
            ),
            PluginConfigField(
                name="api_key",
                display_name="API密钥",
                field_type="string",
                default_value="",
                description="FMP API密钥（必需）- 免费账户每日250次请求。无API Key将无法获取数据。",
                required=True,
                placeholder="输入您的FMP API Key",
                group="基本设置"
            ),

            # 数据源设置
            PluginConfigField(
                name="symbols",
                display_name="监控股票",
                field_type="multiselect",
                default_value=["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"],
                description="需要获取情绪数据的股票代码列表",
                options=["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMZN", "META", "NFLX", "CRM", "ORCL"],
                group="数据源设置"
            ),
            PluginConfigField(
                name="max_symbols",
                display_name="最大股票数量",
                field_type="number",
                default_value=3,
                description="单次请求的最大股票数量（避免超出API限制）",
                min_value=1,
                max_value=10,
                group="数据源设置"
            ),
            PluginConfigField(
                name="data_weight",
                display_name="数据权重",
                field_type="number",
                default_value=0.25,
                description="FMP数据在综合情绪指数中的权重",
                min_value=0.0,
                max_value=1.0,
                group="数据源设置"
            ),

            # 请求设置
            PluginConfigField(
                name="request_timeout",
                display_name="请求超时",
                field_type="number",
                default_value=10,
                description="API请求超时时间（秒）",
                min_value=5,
                max_value=60,
                group="请求设置"
            ),
            PluginConfigField(
                name="retry_times",
                display_name="重试次数",
                field_type="number",
                default_value=3,
                description="API请求失败时的重试次数",
                min_value=0,
                max_value=10,
                group="请求设置"
            ),
            PluginConfigField(
                name="use_free_tier",
                display_name="使用免费模式",
                field_type="boolean",
                default_value=True,
                description="使用免费模式（需要API Key）",
                group="请求设置"
            ),

            # 情绪分析设置
            PluginConfigField(
                name="bullish_threshold",
                display_name="看多阈值",
                field_type="number",
                default_value=70.0,
                description="判断为看多情绪的阈值",
                min_value=50.0,
                max_value=90.0,
                group="情绪分析设置"
            ),
            PluginConfigField(
                name="bearish_threshold",
                display_name="看空阈值",
                field_type="number",
                default_value=30.0,
                description="判断为看空情绪的阈值",
                min_value=10.0,
                max_value=50.0,
                group="情绪分析设置"
            )
        ]

    def get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "enabled": True,
            "api_key": os.environ.get("FMP_API_KEY", ""),
            "symbols": ["AAPL", "MSFT", "GOOGL"],
            "max_symbols": 3,
            "data_weight": 0.25,
            "request_timeout": 10,
            "retry_times": 3,
            "use_free_tier": True,
            "bullish_threshold": 70.0,
            "bearish_threshold": 30.0
        }

    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        """验证配置"""
        try:
            # 验证API Key（如果提供）
            api_key = config.get("api_key", "")
            if api_key and api_key.strip():
                is_valid, msg = validate_api_key(api_key)
                if not is_valid:
                    return False, f"API Key验证失败: {msg}"

            # 验证股票数量
            max_symbols = config.get("max_symbols", 3)
            is_valid, msg = validate_number_range(max_symbols, 1, 10)
            if not is_valid:
                return False, f"最大股票数量: {msg}"

            # 验证权重
            data_weight = config.get("data_weight", 0.25)
            is_valid, msg = validate_number_range(data_weight, 0.0, 1.0)
            if not is_valid:
                return False, f"数据权重: {msg}"

            # 验证阈值
            bullish_threshold = config.get("bullish_threshold", 70.0)
            bearish_threshold = config.get("bearish_threshold", 30.0)

            if bullish_threshold <= bearish_threshold:
                return False, "看多阈值必须大于看空阈值"

            return True, "配置验证通过"

        except Exception as e:
            return False, f"配置验证异常: {str(e)}"

    def get_available_indicators(self) -> List[str]:
        """获取可用的情绪指标列表"""
        symbols = self.get_config("symbols", ["AAPL", "MSFT", "GOOGL"])
        max_symbols = self.get_config("max_symbols", 3)

        # 限制返回的指标数量
        limited_symbols = symbols[:max_symbols]
        return [f"{symbol}社交情绪" for symbol in limited_symbols]

    def is_properly_configured(self) -> bool:
        """检查插件是否已正确配置"""
        api_key = self.get_config("api_key", "")
        return bool(api_key.strip())

    def get_config_status_message(self) -> str:
        """获取配置状态消息"""
        if not self.is_properly_configured():
            return " 需要配置API Key才能获取真实数据"
        return " 配置正常"

    def _fetch_raw_sentiment_data(self, **kwargs) -> SentimentResponse:
        """获取FMP原始情绪数据"""
        if not self.is_enabled():
            return SentimentResponse(
                success=False,
                data=[],
                composite_score=50.0,
                error_message="FMP插件已禁用",
                data_quality="disabled",
                update_time=datetime.now()
            )

        try:
            self._safe_log("info", "开始获取FMP情绪数据...")
            sentiment_data = []

            # 获取配置
            api_key = self.get_config("api_key", "").strip()
            symbols = self.get_config("symbols", ["AAPL", "MSFT", "GOOGL"])
            max_symbols = self.get_config("max_symbols", 3)
            use_free_tier = self.get_config("use_free_tier", True)

            # 限制股票数量
            limited_symbols = symbols[:max_symbols]

            if api_key and not use_free_tier:
                # 使用真实API
                sentiment_data = self._fetch_real_fmp_data(api_key, limited_symbols)
            else:
                # 没有有效API Key，返回失败
                logger.warning("FMP情绪插件：未配置有效API Key，无法获取真实数据")
                return SentimentResponse(
                    success=False,
                    data=[],
                    composite_score=50.0,
                    error_message="FMP插件需要有效的API Key才能获取真实数据",
                    data_quality="unavailable",
                    update_time=datetime.now()
                )

            if sentiment_data:
                composite_score = self._calculate_fmp_composite_score(sentiment_data)
                self._safe_log("info", f"成功获取 {len(sentiment_data)} 项FMP情绪数据")

                return SentimentResponse(
                    success=True,
                    data=sentiment_data,
                    composite_score=composite_score,
                    data_quality="real",
                    update_time=datetime.now()
                )
            else:
                return SentimentResponse(
                    success=False,
                    data=[],
                    composite_score=50.0,
                    error_message="未获取到FMP情绪数据",
                    data_quality="unavailable",
                    update_time=datetime.now()
                )

        except Exception as e:
            self._safe_log("error", f"FMP数据获取失败: {str(e)}")
            return SentimentResponse(
                success=False,
                data=[],
                composite_score=50.0,
                error_message=f"FMP数据获取失败: {str(e)}",
                data_quality="error",
                update_time=datetime.now()
            )

    def _fetch_real_fmp_data(self, api_key: str, symbols: List[str]) -> List[SentimentData]:
        """获取真实FMP数据"""
        sentiment_data = []
        timeout = self.get_config("request_timeout", 10)
        retry_times = self.get_config("retry_times", 3)

        for symbol in symbols:
            for attempt in range(retry_times + 1):
                try:
                    # 调用真实的FMP API - 社交情绪数据
                    url = f"https://financialmodelingprep.com/api/v4/historical/social-sentiment?symbol={symbol}&apikey={api_key}"
                    response = requests.get(url, timeout=timeout)

                    if response.status_code == 200:
                        data = response.json()
                        if data and isinstance(data, list) and len(data) > 0:
                            # 处理真实API响应
                            latest_data = data[0]  # 获取最新数据

                            sentiment_score = latest_data.get('stocktwitsBullishPercent', 50.0)
                            if sentiment_score is None:
                                sentiment_score = 50.0

                            status = self._get_sentiment_status(sentiment_score)
                            signal = self._get_trading_signal(sentiment_score)

                            sentiment_item = SentimentData(
                                indicator_name=f"{symbol}社交情绪",
                                value=round(float(sentiment_score), 2),
                                status=status,
                                change=round(latest_data.get('change', 0.0), 2),
                                signal=signal,
                                suggestion=f"{symbol}社交媒体情绪{status}，建议{signal}",
                                timestamp=datetime.now(),
                                source="FMP-Real",
                                confidence=0.90,
                                metadata={
                                    'api_source': 'FMP',
                                    'symbol': symbol,
                                    'bullish_percent': sentiment_score,
                                    'bearish_percent': latest_data.get('stocktwitsBearishPercent', 50.0),
                                    'last_updated': latest_data.get('date', '')
                                }
                            )

                            sentiment_data.append(sentiment_item)
                            self._safe_log("info", f" 成功获取 {symbol} 的真实FMP数据")
                            break  # 成功获取，跳出重试循环
                        else:
                            self._safe_log("warning", f"FMP API返回空数据: {symbol}")
                            # 跳过该股票，不使用回退数据
                            break
                    elif response.status_code == 401:
                        self._safe_log("error", f"FMP API认证失败，API Key无效")
                        # 跳过该股票，不使用回退数据
                        break
                    elif response.status_code == 429:
                        self._safe_log("warning", f"FMP API请求限制，等待重试...")
                        if attempt < retry_times:
                            import time
                            time.sleep(2 ** attempt)  # 指数退避
                            continue
                        else:
                            # 超出重试次数，跳过该股票
                            self._safe_log("error", f"FMP API重试次数超限，跳过 {symbol}")
                            break
                    else:
                        self._safe_log("warning", f"FMP API请求失败，状态码: {response.status_code}")
                        if attempt == retry_times:
                            # 最后一次尝试失败，跳过该股票
                            self._safe_log("error", f"FMP API最终失败，跳过 {symbol}")

                except requests.exceptions.Timeout:
                    self._safe_log("warning", f"FMP API请求超时: {symbol} (尝试 {attempt + 1})")
                    if attempt == retry_times:
                        # 最后一次尝试失败，跳过该股票
                        self._safe_log("error", f"FMP API最终失败，跳过 {symbol}")

                except requests.exceptions.RequestException as e:
                    self._safe_log("warning", f"FMP API网络错误: {symbol} (尝试 {attempt + 1}): {e}")
                    if attempt == retry_times:
                        # 最后一次尝试失败，跳过该股票
                        self._safe_log("error", f"FMP API最终失败，跳过 {symbol}")

                except Exception as e:
                    self._safe_log("error", f"获取 {symbol} 数据异常 (尝试 {attempt + 1}): {e}")
                    if attempt == retry_times:
                        # 最后一次尝试失败，跳过该股票
                        self._safe_log("error", f"FMP API最终失败，跳过 {symbol}")

        return sentiment_data

    def _get_sentiment_status(self, score: float) -> str:
        """根据分数获取情绪状态"""
        bullish_threshold = self.get_config("bullish_threshold", 70.0)
        bearish_threshold = self.get_config("bearish_threshold", 30.0)

        if score >= bullish_threshold:
            return "强烈看多"
        elif score >= (bullish_threshold + bearish_threshold) / 2:
            return "轻微看多"
        elif score >= bearish_threshold:
            return "中性"
        else:
            return "看空"

    def _get_trading_signal(self, score: float) -> str:
        """根据分数获取交易信号"""
        bullish_threshold = self.get_config("bullish_threshold", 70.0)
        bearish_threshold = self.get_config("bearish_threshold", 30.0)

        if score >= bullish_threshold:
            return "买入"
        elif score >= (bullish_threshold + bearish_threshold) / 2:
            return "持有"
        elif score >= bearish_threshold:
            return "观望"
        else:
            return "减仓"

    def _calculate_fmp_composite_score(self, sentiment_data: List[SentimentData]) -> float:
        """计算FMP综合情绪指数"""
        if not sentiment_data:
            return 50.0

        total_score = sum(data.value * (data.confidence or 0.7) for data in sentiment_data)
        total_weight = sum(data.confidence or 0.7 for data in sentiment_data)

        if total_weight > 0:
            composite_score = total_score / total_weight
        else:
            composite_score = 50.0

        return max(0.0, min(100.0, round(composite_score, 2)))

# 插件工厂函数
def create_fmp_sentiment_plugin() -> FMPSentimentPlugin:
    """创建FMP情绪数据插件实例"""
    return FMPSentimentPlugin()

if __name__ == "__main__":
    # 测试插件
    plugin = create_fmp_sentiment_plugin()

    # 初始化
    plugin.initialize(None)

    # 加载配置
    plugin.load_config()

    # 获取配置UI模式
    ui_schema = plugin.get_config_ui_schema()
    logger.info(f"配置UI模式: {ui_schema}")

    # 获取数据
    response = plugin._fetch_raw_sentiment_data()

    logger.info(f"成功: {response.success}")
    logger.info(f"数据项: {len(response.data)}")
    logger.info(f"综合指数: {response.composite_score}")

    if response.data:
        for item in response.data:
            logger.info(f"- {item.indicator_name}: {item.value} ({item.status})")
