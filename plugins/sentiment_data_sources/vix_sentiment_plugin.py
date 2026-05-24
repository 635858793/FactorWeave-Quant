from loguru import logger
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIX恐慌指数插件
基于VIX波动率指数分析市场恐慌情绪
"""

import numpy as np
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from core.plugin_types import PluginType, PluginCategory
from plugins.sentiment_data_sources.base_sentiment_plugin import BaseSentimentPlugin
from plugins.sentiment_data_sources.config_base import ConfigurablePlugin, PluginConfigField, create_config_file_path, validate_number_range
from plugins.sentiment_data_source_interface import SentimentData, SentimentResponse

import requests

class VIXSentimentPlugin(BaseSentimentPlugin, ConfigurablePlugin):
    """VIX恐慌指数插件"""

    def __init__(self):
        BaseSentimentPlugin.__init__(self)
        ConfigurablePlugin.__init__(self)
        self._config_file = create_config_file_path("vix_sentiment")

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "name": "VIX恐慌指数插件",
            "version": "1.0.0",
            "author": "FactorWeave-Quant  Team",
            "email": "support@factorweave.com",
            "website": "https://github.com/factorweave/FactorWeave-Quant ",
            "license": "MIT",
            "description": "基于VIX波动率指数分析市场恐慌情绪，提供市场风险偏好度量",
            "plugin_type": PluginType.DATA_SOURCE,
            "category": PluginCategory.CORE,
            "dependencies": [],
            "min_framework_version": "1.0.0",
            "max_framework_version": "2.0.0",
            "documentation_url": "",
            "tags": ["sentiment", "vix", "volatility", "fear", "market"]
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
                description="是否启用VIX恐慌指数插件",
                group="基本设置"
            ),

            # VIX阈值设置
            PluginConfigField(
                name="extreme_calm_threshold",
                display_name="极度平静阈值",
                field_type="number",
                default_value=12.0,
                description="VIX极度平静阈值",
                min_value=5.0,
                max_value=20.0,
                group="VIX阈值设置"
            ),
            PluginConfigField(
                name="calm_threshold",
                display_name="相对平静阈值",
                field_type="number",
                default_value=20.0,
                description="VIX相对平静阈值",
                min_value=15.0,
                max_value=30.0,
                group="VIX阈值设置"
            ),
            PluginConfigField(
                name="moderate_fear_threshold",
                display_name="适度恐慌阈值",
                field_type="number",
                default_value=30.0,
                description="VIX适度恐慌阈值",
                min_value=25.0,
                max_value=40.0,
                group="VIX阈值设置"
            ),
            PluginConfigField(
                name="high_fear_threshold",
                display_name="高度恐慌阈值",
                field_type="number",
                default_value=40.0,
                description="VIX高度恐慌阈值",
                min_value=35.0,
                max_value=60.0,
                group="VIX阈值设置"
            ),

            # 数据源设置
            PluginConfigField(
                name="vix_source",
                display_name="VIX数据源",
                field_type="select",
                default_value="yahoo_finance",
                description="选择VIX数据的获取来源。推荐Yahoo Finance（免费），AlphaVantage需要API Key",
                options=["yahoo_finance", "alpha_vantage"],
                group="数据源设置"
            ),
            PluginConfigField(
                name="alpha_vantage_api_key",
                display_name="AlphaVantage API密钥",
                field_type="string",
                default_value="",
                description="AlphaVantage API密钥（仅在选择AlphaVantage数据源时必需）",
                required=False,
                placeholder="输入您的AlphaVantage API Key",
                group="数据源设置"
            ),
            PluginConfigField(
                name="retry_times",
                display_name="API重试次数",
                field_type="number",
                default_value=3,
                description="API请求失败时的重试次数",
                min_value=0,
                max_value=10,
                group="请求设置"
            ),
            PluginConfigField(
                name="request_timeout",
                display_name="请求超时时间",
                field_type="number",
                default_value=10,
                description="API请求超时时间（秒）",
                min_value=5,
                max_value=60,
                group="请求设置"
            ),
            PluginConfigField(
                name="update_interval",
                display_name="更新间隔",
                field_type="number",
                default_value=15,
                description="VIX数据更新间隔（分钟）",
                min_value=1,
                max_value=240,
                group="数据源设置"
            ),
            PluginConfigField(
                name="historical_days",
                display_name="历史数据天数",
                field_type="number",
                default_value=30,
                description="用于趋势分析的历史数据天数",
                min_value=7,
                max_value=365,
                group="数据源设置"
            ),
            PluginConfigField(
                name="data_weight",
                display_name="数据权重",
                field_type="number",
                default_value=0.25,
                description="VIX数据在综合情绪指数中的权重",
                min_value=0.0,
                max_value=1.0,
                group="数据源设置"
            ),

            # 分析设置
            PluginConfigField(
                name="enable_trend_analysis",
                display_name="启用趋势分析",
                field_type="boolean",
                default_value=True,
                description="是否启用VIX趋势分析",
                group="分析设置"
            ),
            PluginConfigField(
                name="enable_percentile_analysis",
                display_name="启用百分位分析",
                field_type="boolean",
                default_value=True,
                description="是否启用VIX历史百分位分析",
                group="分析设置"
            ),
            PluginConfigField(
                name="smoothing_factor",
                display_name="平滑因子",
                field_type="number",
                default_value=0.3,
                description="VIX数据平滑处理因子",
                min_value=0.1,
                max_value=1.0,
                group="分析设置"
            ),

            # 情绪转换设置
            PluginConfigField(
                name="invert_sentiment",
                display_name="反转情绪",
                field_type="boolean",
                default_value=True,
                description="将VIX恐慌指数反转为乐观指数（VIX越低，情绪越乐观）",
                group="情绪转换设置"
            ),
            PluginConfigField(
                name="sentiment_scale",
                display_name="情绪缩放",
                field_type="select",
                default_value="logarithmic",
                description="情绪值缩放方式",
                options=["linear", "logarithmic", "exponential", "custom"],
                group="情绪转换设置"
            ),

            # 高级设置
            PluginConfigField(
                name="volatility_adjustment",
                display_name="波动率调整",
                field_type="boolean",
                default_value=True,
                description="是否根据市场波动率调整VIX权重",
                group="高级设置"
            ),
            PluginConfigField(
                name="market_hours_only",
                display_name="仅交易时间",
                field_type="boolean",
                default_value=False,
                description="是否仅在交易时间更新VIX数据",
                group="高级设置"
            )
        ]

    def get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "enabled": True,
            "extreme_calm_threshold": 12.0,
            "calm_threshold": 20.0,
            "moderate_fear_threshold": 30.0,
            "high_fear_threshold": 40.0,
            "vix_source": "yahoo_finance",
            "alpha_vantage_api_key": os.environ.get("ALPHA_VANTAGE_API_KEY", ""),
            "retry_times": 3,
            "request_timeout": 10,
            "update_interval": 15,
            "historical_days": 30,
            "data_weight": 0.25,
            "enable_trend_analysis": True,
            "enable_percentile_analysis": True,
            "smoothing_factor": 0.3,
            "invert_sentiment": True,
            "sentiment_scale": "logarithmic",
            "volatility_adjustment": True,
            "market_hours_only": False
        }

    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        """验证配置"""
        try:
            # 验证阈值递增关系
            extreme_calm = config.get("extreme_calm_threshold", 12.0)
            calm = config.get("calm_threshold", 20.0)
            moderate_fear = config.get("moderate_fear_threshold", 30.0)
            high_fear = config.get("high_fear_threshold", 40.0)

            if not (extreme_calm < calm < moderate_fear < high_fear):
                return False, "VIX阈值必须递增：极度平静 < 相对平静 < 适度恐慌 < 高度恐慌"

            # 验证数据权重
            data_weight = config.get("data_weight", 0.25)
            is_valid, msg = validate_number_range(data_weight, 0.0, 1.0)
            if not is_valid:
                return False, f"数据权重: {msg}"

            # 验证平滑因子
            smoothing_factor = config.get("smoothing_factor", 0.3)
            is_valid, msg = validate_number_range(smoothing_factor, 0.1, 1.0)
            if not is_valid:
                return False, f"平滑因子: {msg}"

            # 验证更新间隔
            update_interval = config.get("update_interval", 15)
            is_valid, msg = validate_number_range(update_interval, 1, 240)
            if not is_valid:
                return False, f"更新间隔: {msg}"

            # 验证历史数据天数
            historical_days = config.get("historical_days", 30)
            is_valid, msg = validate_number_range(historical_days, 7, 365)
            if not is_valid:
                return False, f"历史数据天数: {msg}"

            return True, "配置验证通过"

        except Exception as e:
            return False, f"配置验证异常: {str(e)}"

    def get_available_indicators(self) -> List[str]:
        """获取可用的情绪指标列表"""
        indicators = ["市场恐慌指数"]

        if self.get_config("enable_trend_analysis", True):
            indicators.append("VIX趋势指数")

        if self.get_config("enable_percentile_analysis", True):
            indicators.append("VIX历史百分位")

        return indicators

    def is_properly_configured(self) -> bool:
        """检查插件是否已正确配置"""
        vix_source = self.get_config("vix_source", "yahoo_finance")
        if vix_source == "alpha_vantage":
            api_key = self.get_config("alpha_vantage_api_key", "")
            return bool(api_key.strip())
        return True  # Yahoo Finance不需要API Key

    def get_config_status_message(self) -> str:
        """获取配置状态消息"""
        vix_source = self.get_config("vix_source", "yahoo_finance")
        if vix_source == "alpha_vantage":
            if not self.is_properly_configured():
                return " 使用AlphaVantage需要配置API Key"
            return " AlphaVantage配置正常"
        return " 使用Yahoo Finance（免费）"

    def _fetch_raw_sentiment_data(self, **kwargs) -> SentimentResponse:
        """获取VIX原始情绪数据"""
        if not self.is_enabled():
            return SentimentResponse(
                success=False,
                data=[],
                composite_score=50.0,
                error_message="VIX恐慌指数插件已禁用",
                data_quality="disabled",
                update_time=datetime.now()
            )

        try:
            self._safe_log("info", "开始获取VIX恐慌指数数据...")
            logger.warning("VIX情绪插件：尝试获取真实API数据，如API不可用将无法返回数据")

            # 获取配置
            vix_source = self.get_config("vix_source", "yahoo_finance")
            market_hours_only = self.get_config("market_hours_only", False)

            # 检查是否在交易时间（如果启用）
            if market_hours_only and not self._is_market_hours():
                self._safe_log("info", "非交易时间，跳过VIX数据更新")
                return SentimentResponse(
                    success=False,
                    data=[],
                    composite_score=50.0,
                    error_message="非交易时间",
                    data_quality="skipped",
                    update_time=datetime.now()
                )

            sentiment_data = []

            if vix_source == "yahoo_finance":
                # 使用Yahoo Finance获取真实VIX数据
                vix_data = self._fetch_real_vix_data_yahoo()
                if vix_data:
                    sentiment_data.extend(vix_data)
            elif vix_source == "alpha_vantage":
                # 使用AlphaVantage获取真实VIX数据
                api_key = self.get_config("alpha_vantage_api_key", "")
                if api_key:
                    vix_data = self._fetch_real_vix_data_alphavantage(api_key)
                    if vix_data:
                        sentiment_data.extend(vix_data)
                else:
                    self._safe_log("error", "AlphaVantage API Key未配置，无法获取数据")
                    return SentimentResponse(
                        success=False,
                        data=[],
                        composite_score=50.0,
                        error_message="AlphaVantage API Key未配置",
                        data_quality="unavailable",
                        update_time=datetime.now()
                    )

            if sentiment_data:
                composite_score = self._calculate_vix_composite_score(sentiment_data)
                self._safe_log("info", f"成功获取 {len(sentiment_data)} 项VIX情绪数据")

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
                    error_message="未获取到VIX数据",
                    data_quality="unavailable",
                    update_time=datetime.now()
                )

        except Exception as e:
            self._safe_log("error", f"VIX数据获取失败: {str(e)}")
            return SentimentResponse(
                success=False,
                data=[],
                composite_score=50.0,
                error_message=f"VIX数据获取失败: {str(e)}",
                data_quality="error",
                update_time=datetime.now()
            )

    def _fetch_real_vix_data_yahoo(self) -> List[SentimentData]:
        """使用Yahoo Finance获取真实VIX数据"""
        sentiment_data = []
        timeout = self.get_config("request_timeout", 10)
        retry_times = self.get_config("retry_times", 3)

        for attempt in range(retry_times + 1):
            try:
                # Yahoo Finance API for VIX (^VIX)
                import time
                import random

                # Yahoo Finance实时数据API
                url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
                params = {
                    'interval': '1d',
                    'range': '1d'
                }

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }

                response = requests.get(url, params=params, headers=headers, timeout=timeout)

                if response.status_code == 200:
                    data = response.json()
                    if data.get('chart') and data['chart']['result']:
                        result = data['chart']['result'][0]
                        meta = result.get('meta', {})

                        current_price = meta.get('regularMarketPrice')
                        previous_close = meta.get('previousClose')

                        if current_price:
                            vix_value = float(current_price)
                            change = float(current_price - previous_close) if previous_close else 0.0

                            # 基础VIX指标
                            vix_sentiment = self._convert_vix_to_sentiment(vix_value)
                            vix_status = self._get_vix_status(vix_value)
                            vix_signal = self._get_vix_signal(vix_value)

                            main_indicator = SentimentData(
                                indicator_name="市场恐慌指数",
                                value=round(vix_sentiment, 2),
                                status=vix_status,
                                change=round(change, 2),
                                signal=vix_signal,
                                suggestion=f"VIX当前{vix_value:.2f}，市场情绪{vix_status}",
                                timestamp=datetime.now(),
                                source="VIX-Yahoo",
                                confidence=0.95,
                                metadata={
                                    'raw_vix': vix_value,
                                    'previous_close': previous_close,
                                    'data_source': 'Yahoo Finance'
                                }
                            )
                            sentiment_data.append(main_indicator)

                            # 添加趋势分析
                            if self.get_config("enable_trend_analysis", True):
                                trend_data = self._calculate_vix_trend(vix_value)
                                if trend_data:
                                    sentiment_data.append(trend_data)

                            # 添加百分位分析
                            if self.get_config("enable_percentile_analysis", True):
                                percentile_data = self._calculate_vix_percentile(vix_value)
                                if percentile_data:
                                    sentiment_data.append(percentile_data)

                            self._safe_log("info", f" 成功获取Yahoo Finance VIX数据: {vix_value:.2f}")
                            break
                        else:
                            self._safe_log("warning", "Yahoo Finance返回的VIX数据格式异常")
                    else:
                        self._safe_log("warning", "Yahoo Finance返回空VIX数据")

                elif response.status_code == 429:
                    self._safe_log("warning", f"Yahoo Finance请求限制，等待重试... (尝试 {attempt + 1})")
                    if attempt < retry_times:
                        time.sleep(2 ** attempt)
                        continue
                else:
                    self._safe_log("warning", f"Yahoo Finance请求失败，状态码: {response.status_code}")

            except requests.exceptions.Timeout:
                self._safe_log("warning", f"Yahoo Finance请求超时 (尝试 {attempt + 1})")
            except requests.exceptions.RequestException as e:
                self._safe_log("warning", f"Yahoo Finance网络错误 (尝试 {attempt + 1}): {e}")
            except Exception as e:
                self._safe_log("error", f"Yahoo Finance数据解析错误 (尝试 {attempt + 1}): {e}")

            # 如果是最后一次尝试失败，记录错误
            if attempt == retry_times:
                self._safe_log("error", "Yahoo Finance VIX数据获取失败")

        return sentiment_data

    def _fetch_real_vix_data_alphavantage(self, api_key: str) -> List[SentimentData]:
        """使用AlphaVantage获取真实VIX数据"""
        sentiment_data = []
        timeout = self.get_config("request_timeout", 10)
        retry_times = self.get_config("retry_times", 3)

        for attempt in range(retry_times + 1):
            try:
                # AlphaVantage API for VIX
                url = "https://www.alphavantage.co/query"
                params = {
                    'function': 'GLOBAL_QUOTE',
                    'symbol': 'VIX',
                    'apikey': api_key
                }

                response = requests.get(url, params=params, timeout=timeout)

                if response.status_code == 200:
                    data = response.json()
                    if 'Global Quote' in data:
                        quote = data['Global Quote']
                        price = quote.get('05. price')
                        change = quote.get('09. change')

                        if price:
                            vix_value = float(price)
                            change_value = float(change) if change else 0.0

                            # 基础VIX指标
                            vix_sentiment = self._convert_vix_to_sentiment(vix_value)
                            vix_status = self._get_vix_status(vix_value)
                            vix_signal = self._get_vix_signal(vix_value)

                            main_indicator = SentimentData(
                                indicator_name="市场恐慌指数",
                                value=round(vix_sentiment, 2),
                                status=vix_status,
                                change=round(change_value, 2),
                                signal=vix_signal,
                                suggestion=f"VIX当前{vix_value:.2f}，市场情绪{vix_status}",
                                timestamp=datetime.now(),
                                source="VIX-AlphaVantage",
                                confidence=0.90,
                                metadata={
                                    'raw_vix': vix_value,
                                    'data_source': 'AlphaVantage'
                                }
                            )
                            sentiment_data.append(main_indicator)

                            self._safe_log("info", f" 成功获取AlphaVantage VIX数据: {vix_value:.2f}")
                            break
                        else:
                            self._safe_log("warning", "AlphaVantage返回的VIX数据格式异常")
                    elif 'Error Message' in data:
                        self._safe_log("error", f"AlphaVantage API错误: {data['Error Message']}")
                        break
                    elif 'Note' in data:
                        self._safe_log("warning", f"AlphaVantage API限制: {data['Note']}")
                        if attempt < retry_times:
                            time.sleep(10)  # API限制等待更长时间
                            continue
                        break
                else:
                    self._safe_log("warning", f"AlphaVantage请求失败，状态码: {response.status_code}")

            except Exception as e:
                self._safe_log("error", f"AlphaVantage数据获取错误 (尝试 {attempt + 1}): {e}")

            # 如果是最后一次尝试失败，记录错误
            if attempt == retry_times:
                self._safe_log("error", "AlphaVantage VIX数据获取失败")

        return sentiment_data

    def _get_vix_status(self, vix_value: float) -> str:
        """根据VIX值获取恐慌状态"""
        extreme_calm = self.get_config("extreme_calm_threshold", 12.0)
        calm = self.get_config("calm_threshold", 20.0)
        moderate_fear = self.get_config("moderate_fear_threshold", 30.0)
        high_fear = self.get_config("high_fear_threshold", 40.0)

        if vix_value <= extreme_calm:
            return "极度平静"
        elif vix_value <= calm:
            return "相对平静"
        elif vix_value <= moderate_fear:
            return "适度紧张"
        elif vix_value <= high_fear:
            return "高度恐慌"
        else:
            return "极度恐慌"

    def _get_vix_signal(self, vix_value: float) -> str:
        """根据VIX值获取交易信号"""
        extreme_calm = self.get_config("extreme_calm_threshold", 12.0)
        calm = self.get_config("calm_threshold", 20.0)
        moderate_fear = self.get_config("moderate_fear_threshold", 30.0)
        high_fear = self.get_config("high_fear_threshold", 40.0)

        if vix_value <= extreme_calm:
            return "高风险偏好"
        elif vix_value <= calm:
            return "正常交易"
        elif vix_value <= moderate_fear:
            return "谨慎交易"
        elif vix_value <= high_fear:
            return "防御为主"
        else:
            return "现金为王"

    def _convert_vix_to_sentiment(self, vix_value: float) -> float:
        """将VIX值转换为情绪分数"""
        invert_sentiment = self.get_config("invert_sentiment", True)
        sentiment_scale = self.get_config("sentiment_scale", "logarithmic")

        if sentiment_scale == "logarithmic":
            # 对数缩放，VIX 10-40 映射到情绪 20-80
            if vix_value <= 10:
                raw_sentiment = 80
            elif vix_value >= 40:
                raw_sentiment = 20
            else:
                # 对数映射
                normalized_vix = (vix_value - 10) / 30  # 0-1
                log_factor = 1 - np.log(1 + normalized_vix * 9) / np.log(10)  # 对数反转
                raw_sentiment = 20 + log_factor * 60
        elif sentiment_scale == "exponential":
            # 指数缩放
            normalized_vix = max(0, min(1, (vix_value - 5) / 75))
            raw_sentiment = 100 * np.exp(-3 * normalized_vix)
        elif sentiment_scale == "linear":
            # 线性缩放
            raw_sentiment = max(0, min(100, 100 - (vix_value - 5) * 100 / 75))
        else:
            # 自定义缩放（可以根据需要扩展）
            raw_sentiment = max(0, min(100, 90 - vix_value * 1.5))

        if not invert_sentiment:
            # 如果不反转，直接返回恐慌程度
            raw_sentiment = 100 - raw_sentiment

        return max(0, min(100, raw_sentiment))

    def _calculate_vix_trend(self, current_vix: float) -> Optional[SentimentData]:
        """计算VIX趋势"""
        try:
            # 没有真实历史数据，无法计算趋势
            self._safe_log("info", "VIX趋势分析需要真实历史数据")
            return None
        except Exception as e:
            self._safe_log("error", f"VIX趋势计算失败: {e}")
            return None

    def _calculate_vix_percentile(self, current_vix: float) -> Optional[SentimentData]:
        """计算VIX历史百分位"""
        try:
            # 没有真实历史数据，无法计算百分位
            self._safe_log("info", "VIX百分位分析需要真实历史数据")
            return None
        except Exception as e:
            self._safe_log("error", f"VIX百分位计算失败: {e}")
            return None

    def _is_market_hours(self) -> bool:
        """检查是否在市场交易时间"""
        now = datetime.now()
        # 简单检查：周一到周五，9:30-16:00 (美东时间的简化版)
        if now.weekday() >= 5:  # 周末
            return False

        hour = now.hour
        return 9 <= hour <= 16  # 简化的交易时间检查

    def _calculate_vix_composite_score(self, sentiment_data: List[SentimentData]) -> float:
        """计算VIX综合情绪指数"""
        if not sentiment_data:
            return 50.0

        volatility_adjustment = self.get_config("volatility_adjustment", True)

        total_score = 0.0
        total_weight = 0.0

        for data in sentiment_data:
            weight = 1.0
            confidence = data.confidence or 0.8

            # 根据指标类型调整权重
            if "恐慌指数" in data.indicator_name:
                weight = 1.5  # 主要指标权重更高
            elif "趋势" in data.indicator_name:
                weight = 1.2
            elif "百分位" in data.indicator_name:
                weight = 1.0

            # 波动率调整
            if volatility_adjustment and "趋势" in data.indicator_name:
                # 根据变化幅度调整权重
                change_magnitude = abs(data.change or 0)
                volatility_factor = 1 + min(0.5, change_magnitude / 10)
                weight *= volatility_factor

            adjusted_weight = weight * confidence
            total_score += data.value * adjusted_weight
            total_weight += adjusted_weight

        if total_weight > 0:
            composite_score = total_score / total_weight
        else:
            composite_score = 50.0

        return max(0.0, min(100.0, round(composite_score, 2)))

# 插件工厂函数
def create_vix_sentiment_plugin() -> VIXSentimentPlugin:
    """创建VIX恐慌指数插件实例"""
    return VIXSentimentPlugin()

if __name__ == "__main__":
    # 测试插件
    plugin = create_vix_sentiment_plugin()

    # 初始化
    plugin.initialize(None)

    # 加载配置
    plugin.load_config()

    # 获取数据
    response = plugin._fetch_raw_sentiment_data()

    logger.info(f"成功: {response.success}")
    logger.info(f"数据项: {len(response.data)}")
    logger.info(f"综合指数: {response.composite_score}")

    if response.data:
        for item in response.data:
            logger.info(f"- {item.indicator_name}: {item.value} ({item.status})")
