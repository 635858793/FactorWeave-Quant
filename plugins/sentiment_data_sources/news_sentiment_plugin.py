from loguru import logger
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新闻情绪分析插件
基于新闻文本分析获取市场情绪数据
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from core.plugin_types import PluginType, PluginCategory
from plugins.sentiment_data_sources.base_sentiment_plugin import BaseSentimentPlugin
from plugins.sentiment_data_sources.config_base import ConfigurablePlugin, PluginConfigField, create_config_file_path, validate_number_range
from plugins.sentiment_data_source_interface import SentimentData, SentimentResponse

# 此插件当前无真实数据源，所有分析方法均不可用
# 需要对接真实新闻API（如NewsAPI、Alpha Vantage News等）后启用
class NewsSentimentPlugin(BaseSentimentPlugin, ConfigurablePlugin):
    """新闻情绪分析插件"""

    def __init__(self):
        BaseSentimentPlugin.__init__(self)
        ConfigurablePlugin.__init__(self)
        self._config_file = create_config_file_path("news_sentiment")

        self.news_sources = [
            "财经新闻", "分析师报告", "公司公告", "行业资讯",
            "政策解读", "市场评论", "研究报告", "券商研报"
        ]

    @property
    def has_real_data(self) -> bool:
        return False

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "name": "新闻情绪分析插件",
            "version": "1.0.0",
            "author": "FactorWeave-Quant  Team",
            "email": "support@factorweave.com",
             "website": "https://github.com/factorweave/FactorWeave-Quant ",
            "license": "MIT",
            "description": "基于新闻文本分析获取市场情绪数据，支持多种新闻源和自定义情绪算法",
            "plugin_type": PluginType.DATA_SOURCE,
            "category": PluginCategory.CORE,
            "dependencies": [],
            "min_framework_version": "1.0.0",
             "max_framework_version": "2.0.0",
            "documentation_url": "",
            "tags": ["sentiment", "news", "analysis", "nlp"]
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
                description="是否启用新闻情绪分析插件",
                group="基本设置"
            ),

            # 新闻源设置
            PluginConfigField(
                name="active_sources",
                display_name="活跃新闻源",
                field_type="multiselect",
                default_value=["财经新闻", "分析师报告", "公司公告"],
                description="需要分析的新闻源类型",
                options=self.news_sources,
                group="新闻源设置"
            ),
            PluginConfigField(
                name="source_weights",
                display_name="新闻源权重",
                field_type="string",
                default_value="财经新闻:0.3,分析师报告:0.4,公司公告:0.3",
                description="各新闻源的权重配置（格式：源名:权重,源名:权重）",
                placeholder="财经新闻:0.3,分析师报告:0.4,公司公告:0.3",
                group="新闻源设置"
            ),
            PluginConfigField(
                name="update_interval",
                display_name="更新间隔",
                field_type="number",
                default_value=30,
                description="新闻情绪更新间隔（分钟）",
                min_value=5,
                max_value=360,
                group="新闻源设置"
            ),

            # 情绪分析设置
            PluginConfigField(
                name="sentiment_algorithm",
                display_name="情绪算法",
                field_type="select",
                default_value="hybrid",
                description="情绪分析算法类型",
                options=["simple", "weighted", "hybrid", "advanced"],
                group="情绪分析设置"
            ),
            PluginConfigField(
                name="positive_threshold",
                display_name="正面阈值",
                field_type="number",
                default_value=65.0,
                description="判断为正面情绪的阈值",
                min_value=50.0,
                max_value=90.0,
                group="情绪分析设置"
            ),
            PluginConfigField(
                name="negative_threshold",
                display_name="负面阈值",
                field_type="number",
                default_value=35.0,
                description="判断为负面情绪的阈值",
                min_value=10.0,
                max_value=50.0,
                group="情绪分析设置"
            ),
            PluginConfigField(
                name="data_weight",
                display_name="数据权重",
                field_type="number",
                default_value=0.15,
                description="新闻数据在综合情绪指数中的权重",
                min_value=0.0,
                max_value=1.0,
                group="情绪分析设置"
            ),

            # 关键词设置
            PluginConfigField(
                name="positive_keywords",
                display_name="正面关键词",
                field_type="string",
                default_value="利好,上涨,增长,突破,看好,买入,推荐,强势",
                description="正面情绪关键词（逗号分隔）",
                placeholder="利好,上涨,增长,突破,看好,买入,推荐,强势",
                group="关键词设置"
            ),
            PluginConfigField(
                name="negative_keywords",
                display_name="负面关键词",
                field_type="string",
                default_value="利空,下跌,风险,调整,看空,卖出,谨慎,弱势",
                description="负面情绪关键词（逗号分隔）",
                placeholder="利空,下跌,风险,调整,看空,卖出,谨慎,弱势",
                group="关键词设置"
            ),
            PluginConfigField(
                name="filter_keywords",
                display_name="过滤关键词",
                field_type="string",
                default_value="广告,推广,免责,声明",
                description="需要过滤的关键词（逗号分隔）",
                placeholder="广告,推广,免责,声明",
                group="关键词设置"
            ),

            # 高级设置
            PluginConfigField(
                name="min_confidence",
                display_name="最小置信度",
                field_type="number",
                default_value=0.6,
                description="情绪分析结果的最小置信度要求",
                min_value=0.1,
                max_value=1.0,
                group="高级设置"
            ),
            PluginConfigField(
                name="enable_trend_analysis",
                display_name="启用趋势分析",
                field_type="boolean",
                default_value=True,
                description="是否启用新闻情绪趋势分析",
                group="高级设置"
            )
        ]

    def get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "enabled": True,
            "active_sources": ["财经新闻", "分析师报告", "公司公告"],
            "source_weights": "财经新闻:0.3,分析师报告:0.4,公司公告:0.3",
            "update_interval": 30,
            "sentiment_algorithm": "hybrid",
            "positive_threshold": 65.0,
            "negative_threshold": 35.0,
            "data_weight": 0.15,
            "positive_keywords": "利好,上涨,增长,突破,看好,买入,推荐,强势",
            "negative_keywords": "利空,下跌,风险,调整,看空,卖出,谨慎,弱势",
            "filter_keywords": "广告,推广,免责,声明",
            "min_confidence": 0.6,
            "enable_trend_analysis": True
        }

    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        """验证配置"""
        try:
            # 验证阈值
            positive_threshold = config.get("positive_threshold", 65.0)
            negative_threshold = config.get("negative_threshold", 35.0)

            if positive_threshold <= negative_threshold:
                return False, "正面阈值必须大于负面阈值"

            # 验证数据权重
            data_weight = config.get("data_weight", 0.15)
            is_valid, msg = validate_number_range(data_weight, 0.0, 1.0)
            if not is_valid:
                return False, f"数据权重: {msg}"

            # 验证置信度
            min_confidence = config.get("min_confidence", 0.6)
            is_valid, msg = validate_number_range(min_confidence, 0.1, 1.0)
            if not is_valid:
                return False, f"最小置信度: {msg}"

            # 验证更新间隔
            update_interval = config.get("update_interval", 30)
            is_valid, msg = validate_number_range(update_interval, 5, 360)
            if not is_valid:
                return False, f"更新间隔: {msg}"

            # 验证权重配置格式
            source_weights = config.get("source_weights", "")
            try:
                self._parse_source_weights(source_weights)
            except Exception as e:
                return False, f"新闻源权重格式错误: {str(e)}"

            return True, "配置验证通过"

        except Exception as e:
            return False, f"配置验证异常: {str(e)}"

    def get_available_indicators(self) -> List[str]:
        """获取可用的情绪指标列表"""
        active_sources = self.get_config("active_sources", ["财经新闻", "分析师报告", "公司公告"])
        indicators = [f"{source}情绪" for source in active_sources]

        if self.get_config("enable_trend_analysis", True):
            indicators.append("新闻情绪趋势")

        return indicators

    def _fetch_raw_sentiment_data(self, **kwargs) -> SentimentResponse:
        return SentimentResponse(
            success=False,
            data=[],
            composite_score=50.0,
            error_message="新闻情绪数据源不可用：当前无真实新闻API数据源，需要配置NewsAPI、Alpha Vantage News等新闻数据源后启用",
            data_quality="unavailable",
            update_time=datetime.now()
        )

    def _analyze_news_source_sentiment(self, source: str, algorithm: str) -> Optional[SentimentData]:
        logger.warning(f"新闻情绪分析不可用：当前无真实新闻API数据源，无法分析 {source} 情绪")
        return None

    def _apply_keyword_weighting(self, base_score: float, source: str) -> float:
        return base_score

    def _apply_hybrid_analysis(self, base_score: float, source: str) -> float:
        return base_score

    def _apply_advanced_analysis(self, base_score: float, source: str) -> float:
        return base_score

    def _get_news_sentiment_status(self, score: float) -> str:
        """根据分数获取新闻情绪状态"""
        positive_threshold = self.get_config("positive_threshold", 65.0)
        negative_threshold = self.get_config("negative_threshold", 35.0)

        if score >= positive_threshold:
            return "积极正面"
        elif score >= (positive_threshold + negative_threshold) / 2:
            return "温和正面"
        elif score >= negative_threshold:
            return "中性"
        else:
            return "负面"

    def _get_news_sentiment_signal(self, score: float) -> str:
        """根据分数获取新闻情绪信号"""
        positive_threshold = self.get_config("positive_threshold", 65.0)
        negative_threshold = self.get_config("negative_threshold", 35.0)

        if score >= positive_threshold:
            return "利好"
        elif score >= (positive_threshold + negative_threshold) / 2:
            return "轻微利好"
        elif score >= negative_threshold:
            return "无明显影响"
        else:
            return "利空"

    def _calculate_confidence(self, score: float, source: str, algorithm: str) -> float:
        base_confidence = 0.7

        if source == "分析师报告":
            base_confidence = 0.8
        elif source == "公司公告":
            base_confidence = 0.75
        elif source == "财经新闻":
            base_confidence = 0.7

        if algorithm == "advanced":
            base_confidence += 0.05
        elif algorithm == "hybrid":
            base_confidence += 0.03

        return max(0.1, min(1.0, base_confidence))

    def _calculate_sentiment_trend(self, sentiment_data: List[SentimentData]) -> Optional[SentimentData]:
        return None

    def _parse_source_weights(self, weights_str: str) -> Dict[str, float]:
        """解析新闻源权重配置"""
        weights = {}

        if not weights_str:
            return weights

        for item in weights_str.split(","):
            if ":" in item:
                source, weight_str = item.split(":", 1)
                source = source.strip()
                try:
                    weight = float(weight_str.strip())
                    if 0 <= weight <= 1:
                        weights[source] = weight
                    else:
                        raise ValueError(f"权重值必须在0-1之间: {weight}")
                except ValueError as e:
                    raise ValueError(f"无效的权重值 '{weight_str}': {e}")
            else:
                raise ValueError(f"权重格式错误: {item}")

        return weights

    def _calculate_news_composite_score(self, sentiment_data: List[SentimentData]) -> float:
        """计算新闻综合情绪指数"""
        if not sentiment_data:
            return 50.0

        try:
            # 获取权重配置
            weights_config = self.get_config("source_weights", "")
            source_weights = self._parse_source_weights(weights_config)

            total_score = 0.0
            total_weight = 0.0

            for data in sentiment_data:
                # 从源名称提取权重
                source_name = data.source.replace("新闻-", "").replace("趋势分析", "")
                weight = source_weights.get(source_name, 0.1)

                confidence = data.confidence or 0.7
                adjusted_weight = weight * confidence

                total_score += data.value * adjusted_weight
                total_weight += adjusted_weight

            if total_weight > 0:
                composite_score = total_score / total_weight
            else:
                composite_score = 50.0

            return max(0.0, min(100.0, round(composite_score, 2)))

        except Exception as e:
            self._safe_log("warning", f"计算新闻综合指数失败: {e}")
            # 使用简单平均作为备选
            avg_score = sum(data.value for data in sentiment_data) / len(sentiment_data)
            return max(0.0, min(100.0, round(avg_score, 2)))

# 插件工厂函数
def create_news_sentiment_plugin() -> NewsSentimentPlugin:
    """创建新闻情绪分析插件实例"""
    return NewsSentimentPlugin()

if __name__ == "__main__":
    # 测试插件
    plugin = create_news_sentiment_plugin()

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
