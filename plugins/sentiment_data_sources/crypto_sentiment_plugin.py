from loguru import logger
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
加密货币情绪分析插件
基于加密货币Fear & Greed指数和市场数据分析情绪
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from core.plugin_types import PluginType, PluginCategory
from plugins.sentiment_data_sources.base_sentiment_plugin import BaseSentimentPlugin
from plugins.sentiment_data_sources.config_base import ConfigurablePlugin, PluginConfigField, create_config_file_path, validate_number_range
from plugins.sentiment_data_source_interface import SentimentData, SentimentResponse

# 此插件当前无真实数据源，所有fetch方法均不可用
# 需要对接真实加密货币API（如Alternative.me Fear & Greed Index API）后启用
class CryptoSentimentPlugin(BaseSentimentPlugin, ConfigurablePlugin):
    """加密货币情绪分析插件"""

    def __init__(self):
        BaseSentimentPlugin.__init__(self)
        ConfigurablePlugin.__init__(self)
        self._config_file = create_config_file_path("crypto_sentiment")

        self.endpointhost = []

        self.supported_cryptos = [
            "BTC", "ETH", "BNB", "ADA", "XRP", "DOT", "LINK", "LTC",
            "BCH", "XLM", "DOGE", "UNI", "AAVE", "MATIC", "SOL"
        ]

    @property
    def has_real_data(self) -> bool:
        return False

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "name": "加密货币情绪插件",
            "version": "1.0.0",
            "author": "FactorWeave-Quant  Team",
            "email": "support@factorweave.com",
             "website": "https://github.com/factorweave/FactorWeave-Quant ",
            "license": "MIT",
            "description": "基于加密货币Fear & Greed指数和市场数据分析整体市场情绪",
            "plugin_type": PluginType.DATA_SOURCE,
            "category": PluginCategory.CORE,
            "dependencies": [],
            "min_framework_version": "1.0.0",
             "max_framework_version": "2.0.0",
            "documentation_url": "",
            "tags": ["sentiment", "crypto", "bitcoin", "fear_greed", "market"]
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
                description="是否启用加密货币情绪分析插件",
                group="基本设置"
            ),

            # 加密货币设置
            PluginConfigField(
                name="monitored_cryptos",
                display_name="监控币种",
                field_type="multiselect",
                default_value=["BTC", "ETH", "BNB"],
                description="需要监控的加密货币种类",
                options=self.supported_cryptos,
                group="加密货币设置"
            ),
            PluginConfigField(
                name="crypto_weights",
                display_name="币种权重",
                field_type="string",
                default_value="BTC:0.5,ETH:0.3,BNB:0.2",
                description="各币种在情绪分析中的权重（格式：币种:权重,币种:权重）",
                placeholder="BTC:0.5,ETH:0.3,BNB:0.2",
                group="加密货币设置"
            ),
            PluginConfigField(
                name="include_altcoins",
                display_name="包含山寨币",
                field_type="boolean",
                default_value=True,
                description="是否包含山寨币情绪分析",
                group="加密货币设置"
            ),

            # Fear & Greed 设置
            PluginConfigField(
                name="fear_greed_source",
                display_name="恐贪指数源",
                field_type="select",
                default_value="alternative_me",
                description="Fear & Greed指数数据源",
                options=["alternative_me", "simulated", "custom"],
                group="Fear & Greed设置"
            ),
            PluginConfigField(
                name="extreme_fear_threshold",
                display_name="极度恐惧阈值",
                field_type="number",
                default_value=25,
                description="极度恐惧状态的阈值",
                min_value=0,
                max_value=40,
                group="Fear & Greed设置"
            ),
            PluginConfigField(
                name="fear_threshold",
                display_name="恐惧阈值",
                field_type="number",
                default_value=45,
                description="恐惧状态的阈值",
                min_value=20,
                max_value=60,
                group="Fear & Greed设置"
            ),
            PluginConfigField(
                name="greed_threshold",
                display_name="贪婪阈值",
                field_type="number",
                default_value=75,
                description="贪婪状态的阈值",
                min_value=60,
                max_value=90,
                group="Fear & Greed设置"
            ),
            PluginConfigField(
                name="extreme_greed_threshold",
                display_name="极度贪婪阈值",
                field_type="number",
                default_value=90,
                description="极度贪婪状态的阈值",
                min_value=80,
                max_value=100,
                group="Fear & Greed设置"
            ),

            # 市场影响设置
            PluginConfigField(
                name="traditional_market_impact",
                display_name="传统市场影响度",
                field_type="number",
                default_value=0.3,
                description="加密货币对传统市场情绪的影响权重",
                min_value=0.0,
                max_value=1.0,
                group="市场影响设置"
            ),
            PluginConfigField(
                name="correlation_adjustment",
                display_name="相关性调整",
                field_type="boolean",
                default_value=True,
                description="是否根据与传统市场的相关性调整权重",
                group="市场影响设置"
            ),
            PluginConfigField(
                name="data_weight",
                display_name="数据权重",
                field_type="number",
                default_value=0.15,
                description="加密货币数据在综合情绪指数中的权重",
                min_value=0.0,
                max_value=1.0,
                group="市场影响设置"
            ),

            # 分析设置
            PluginConfigField(
                name="enable_dominance_analysis",
                display_name="启用主导地位分析",
                field_type="boolean",
                default_value=True,
                description="是否启用比特币主导地位分析",
                group="分析设置"
            ),
            PluginConfigField(
                name="enable_volatility_analysis",
                display_name="启用波动率分析",
                field_type="boolean",
                default_value=True,
                description="是否启用加密货币波动率分析",
                group="分析设置"
            ),
            PluginConfigField(
                name="sentiment_smoothing",
                display_name="情绪平滑",
                field_type="number",
                default_value=0.2,
                description="情绪数据平滑处理系数",
                min_value=0.0,
                max_value=1.0,
                group="分析设置"
            ),

            # 更新设置
            PluginConfigField(
                name="update_interval",
                display_name="更新间隔",
                field_type="number",
                default_value=60,
                description="数据更新间隔（分钟）",
                min_value=5,
                max_value=1440,
                group="更新设置"
            ),
            PluginConfigField(
                name="cache_duration",
                display_name="缓存时长",
                field_type="number",
                default_value=30,
                description="数据缓存时长（分钟）",
                min_value=5,
                max_value=240,
                group="更新设置"
            ),

            # 高级设置
            PluginConfigField(
                name="defi_sentiment_weight",
                display_name="DeFi情绪权重",
                field_type="number",
                default_value=0.1,
                description="DeFi市场情绪在分析中的权重",
                min_value=0.0,
                max_value=0.5,
                group="高级设置"
            ),
            PluginConfigField(
                name="nft_sentiment_weight",
                display_name="NFT情绪权重",
                field_type="number",
                default_value=0.05,
                description="NFT市场情绪在分析中的权重",
                min_value=0.0,
                max_value=0.3,
                group="高级设置"
            )
        ]

    def get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "enabled": True,
            "monitored_cryptos": ["BTC", "ETH", "BNB"],
            "crypto_weights": "BTC:0.5,ETH:0.3,BNB:0.2",
            "include_altcoins": True,
            "fear_greed_source": "alternative_me",
            "extreme_fear_threshold": 25,
            "fear_threshold": 45,
            "greed_threshold": 75,
            "extreme_greed_threshold": 90,
            "traditional_market_impact": 0.3,
            "correlation_adjustment": True,
            "data_weight": 0.15,
            "enable_dominance_analysis": True,
            "enable_volatility_analysis": True,
            "sentiment_smoothing": 0.2,
            "update_interval": 60,
            "cache_duration": 30,
            "defi_sentiment_weight": 0.1,
            "nft_sentiment_weight": 0.05
        }

    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        """验证配置"""
        try:
            # 验证阈值递增关系
            extreme_fear = config.get("extreme_fear_threshold", 25)
            fear = config.get("fear_threshold", 45)
            greed = config.get("greed_threshold", 75)
            extreme_greed = config.get("extreme_greed_threshold", 90)

            if not (extreme_fear < fear < greed < extreme_greed):
                return False, "Fear & Greed阈值必须递增：极度恐惧 < 恐惧 < 贪婪 < 极度贪婪"

            # 验证权重配置
            weights_str = config.get("crypto_weights", "")
            try:
                self._parse_crypto_weights(weights_str)
            except Exception as e:
                return False, f"币种权重格式错误: {str(e)}"

            # 验证各项权重范围
            weight_fields = [
                ("traditional_market_impact", "传统市场影响度"),
                ("data_weight", "数据权重"),
                ("sentiment_smoothing", "情绪平滑"),
                ("defi_sentiment_weight", "DeFi情绪权重"),
                ("nft_sentiment_weight", "NFT情绪权重")
            ]

            for field, display_name in weight_fields:
                value = config.get(field, 0)
                is_valid, msg = validate_number_range(value, 0.0, 1.0)
                if not is_valid:
                    return False, f"{display_name}: {msg}"

            # 验证监控币种
            monitored_cryptos = config.get("monitored_cryptos", [])
            if not monitored_cryptos:
                return False, "至少需要监控一种加密货币"

            for crypto in monitored_cryptos:
                if crypto not in self.supported_cryptos:
                    return False, f"不支持的加密货币: {crypto}"

            return True, "配置验证通过"

        except Exception as e:
            return False, f"配置验证异常: {str(e)}"

    def get_available_indicators(self) -> List[str]:
        """获取可用的情绪指标列表"""
        indicators = ["加密货币Fear&Greed指数"]

        if self.get_config("enable_dominance_analysis", True):
            indicators.append("比特币主导地位")

        if self.get_config("enable_volatility_analysis", True):
            indicators.append("加密市场波动率")

        if self.get_config("defi_sentiment_weight", 0.1) > 0:
            indicators.append("DeFi市场情绪")

        if self.get_config("nft_sentiment_weight", 0.05) > 0:
            indicators.append("NFT市场情绪")

        return indicators

    def _fetch_raw_sentiment_data(self, **kwargs) -> SentimentResponse:
        if not self.is_enabled():
            return SentimentResponse(
                success=False,
                data=[],
                composite_score=50.0,
                error_message="加密货币情绪插件已禁用",
                data_quality="disabled",
                update_time=datetime.now()
            )

        return SentimentResponse(
            success=False,
            data=[],
            composite_score=50.0,
            error_message="加密货币情绪数据源不可用：当前无真实API数据源，需要配置Alternative.me Fear & Greed Index API或其他加密货币数据源后启用",
            data_quality="unavailable",
            update_time=datetime.now()
        )

    def _fetch_fear_greed_data(self) -> Optional[SentimentData]:
        self._safe_log("warning", "Fear & Greed数据不可用：当前无真实API数据源")
        return None

    def _fetch_btc_dominance_data(self) -> Optional[SentimentData]:
        self._safe_log("warning", "BTC主导地位数据不可用：当前无真实API数据源")
        return None

    def _fetch_crypto_volatility_data(self) -> Optional[SentimentData]:
        self._safe_log("warning", "加密市场波动率数据不可用：当前无真实API数据源")
        return None

    def _fetch_defi_sentiment_data(self) -> Optional[SentimentData]:
        self._safe_log("warning", "DeFi情绪数据不可用：当前无真实API数据源")
        return None

    def _fetch_nft_sentiment_data(self) -> Optional[SentimentData]:
        self._safe_log("warning", "NFT情绪数据不可用：当前无真实API数据源")
        return None

    def _get_fear_greed_status(self, index: float) -> str:
        """根据Fear & Greed指数获取状态"""
        extreme_fear = self.get_config("extreme_fear_threshold", 25)
        fear = self.get_config("fear_threshold", 45)
        greed = self.get_config("greed_threshold", 75)
        extreme_greed = self.get_config("extreme_greed_threshold", 90)

        if index <= extreme_fear:
            return "极度恐惧"
        elif index <= fear:
            return "恐惧"
        elif index < greed:
            return "中性"
        elif index < extreme_greed:
            return "贪婪"
        else:
            return "极度贪婪"

    def _get_fear_greed_signal(self, index: float) -> str:
        """根据Fear & Greed指数获取信号"""
        extreme_fear = self.get_config("extreme_fear_threshold", 25)
        fear = self.get_config("fear_threshold", 45)
        greed = self.get_config("greed_threshold", 75)
        extreme_greed = self.get_config("extreme_greed_threshold", 90)

        if index <= extreme_fear:
            return "抄底机会"
        elif index <= fear:
            return "谨慎买入"
        elif index < greed:
            return "持有观望"
        elif index < extreme_greed:
            return "获利了结"
        else:
            return "高位减仓"

    def _parse_crypto_weights(self, weights_str: str) -> Dict[str, float]:
        """解析加密货币权重配置"""
        weights = {}

        if not weights_str:
            return weights

        for item in weights_str.split(","):
            if ":" in item:
                crypto, weight_str = item.split(":", 1)
                crypto = crypto.strip().upper()
                try:
                    weight = float(weight_str.strip())
                    if 0 <= weight <= 1:
                        weights[crypto] = weight
                    else:
                        raise ValueError(f"权重值必须在0-1之间: {weight}")
                except ValueError as e:
                    raise ValueError(f"无效的权重值 '{weight_str}': {e}")
            else:
                raise ValueError(f"权重格式错误: {item}")

        return weights

    def _calculate_crypto_composite_score(self, sentiment_data: List[SentimentData]) -> float:
        """计算加密货币综合情绪指数"""
        if not sentiment_data:
            return 50.0

        try:
            correlation_adjustment = self.get_config("correlation_adjustment", True)
            traditional_impact = self.get_config("traditional_market_impact", 0.3)

            total_score = 0.0
            total_weight = 0.0

            for data in sentiment_data:
                weight = 1.0
                confidence = data.confidence or 0.7

                # 根据指标类型调整权重
                if "Fear&Greed" in data.indicator_name:
                    weight = 2.0  # 主要指标
                elif "主导地位" in data.indicator_name:
                    weight = 1.5
                elif "波动率" in data.indicator_name:
                    weight = 1.2
                elif "DeFi" in data.indicator_name:
                    weight = self.get_config("defi_sentiment_weight", 0.1) * 10
                elif "NFT" in data.indicator_name:
                    weight = self.get_config("nft_sentiment_weight", 0.05) * 20

                # 相关性调整
                if correlation_adjustment:
                    correlation_factor = 1.0
                    weight *= correlation_factor

                # 传统市场影响调整
                if traditional_impact > 0:
                    impact_adjustment = 1.0
                    weight *= impact_adjustment

                adjusted_weight = weight * confidence
                total_score += data.value * adjusted_weight
                total_weight += adjusted_weight

            if total_weight > 0:
                composite_score = total_score / total_weight
            else:
                composite_score = 50.0

            return max(0.0, min(100.0, round(composite_score, 2)))

        except Exception as e:
            self._safe_log("warning", f"计算加密货币综合指数失败: {e}")
            # 使用简单平均作为备选
            avg_score = sum(data.value for data in sentiment_data) / len(sentiment_data)
            return max(0.0, min(100.0, round(avg_score, 2)))

# 插件工厂函数
def create_crypto_sentiment_plugin() -> CryptoSentimentPlugin:
    """创建加密货币情绪分析插件实例"""
    return CryptoSentimentPlugin()

if __name__ == "__main__":
    # 测试插件
    plugin = create_crypto_sentiment_plugin()

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
