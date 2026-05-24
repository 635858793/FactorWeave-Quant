from loguru import logger
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exorde 情绪数据源插件
基于Exorde API获取27种情绪分析数据
"""

import requests
import os
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json  # Added for json.JSONDecodeError

from core.plugin_types import PluginType, PluginCategory
from plugins.sentiment_data_sources.base_sentiment_plugin import BaseSentimentPlugin
from plugins.sentiment_data_sources.config_base import ConfigurablePlugin, PluginConfigField, create_config_file_path, validate_api_key, validate_number_range
from plugins.sentiment_data_source_interface import SentimentData, SentimentResponse

class ExordeSentimentPlugin(BaseSentimentPlugin, ConfigurablePlugin):
    """Exorde情绪数据源插件"""

    has_real_data = False

    def __init__(self):
        BaseSentimentPlugin.__init__(self)
        ConfigurablePlugin.__init__(self)
        self._config_file = create_config_file_path("exorde_sentiment")

        # 27种情绪类型
        self.emotions = [
            'love', 'joy', 'optimism', 'trust', 'anticipation', 'surprise',
            'fear', 'anger', 'sadness', 'disgust', 'pessimism', 'anxiety',
            'approval', 'caring', 'curiosity', 'desire', 'excitement', 'gratitude',
            'grief', 'nervousness', 'pride', 'realization', 'relief', 'remorse',
            'admiration', 'amusement', 'confusion'
        ]

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "name": "Exorde情绪光谱插件",
            "version": "1.0.0",
            "author": "FactorWeave-Quant  Team",
            "email": "support@factorweave.com",
            "website": "https://developers.exorde.io",
            "license": "MIT",
            "description": "基于Exorde API获取27种情绪分析数据，提供全面的市场情绪光谱分析",
            "plugin_type": PluginType.DATA_SOURCE,
            "category": PluginCategory.CORE,
            "dependencies": ["requests>=2.25.0"],
            "min_framework_version": "1.0.0",
            "max_framework_version": "2.0.0",
            "documentation_url": "https://developers.exorde.io",
            "tags": ["sentiment", "exorde", "emotion", "27emotions", "api"]
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
                description="是否启用Exorde情绪数据插件",
                group="基本设置"
            ),
            PluginConfigField(
                name="api_key",
                display_name="API密钥",
                field_type="string",
                default_value="",
                description="Exorde API密钥（免费1000 credits）",
                required=False,
                placeholder="输入您的Exorde API Key",
                group="基本设置"
            ),

            # 情绪分析设置
            PluginConfigField(
                name="primary_emotions",
                display_name="主要情绪",
                field_type="multiselect",
                default_value=["love", "joy", "optimism", "fear", "anger", "sadness"],
                description="重点分析的情绪类型",
                options=["love", "joy", "optimism", "trust", "anticipation", "surprise",
                         "fear", "anger", "sadness", "disgust", "pessimism", "anxiety"],
                group="情绪分析设置"
            ),
            PluginConfigField(
                name="emotion_threshold",
                display_name="情绪阈值",
                field_type="number",
                default_value=0.3,
                description="情绪强度阈值（0-1），低于此值的情绪将被忽略",
                min_value=0.0,
                max_value=1.0,
                group="情绪分析设置"
            ),
            PluginConfigField(
                name="data_weight",
                display_name="数据权重",
                field_type="number",
                default_value=0.20,
                description="Exorde数据在综合情绪指数中的权重",
                min_value=0.0,
                max_value=1.0,
                group="情绪分析设置"
            ),

            # 数据源设置
            PluginConfigField(
                name="topics",
                display_name="监控主题",
                field_type="multiselect",
                default_value=["stock market", "trading", "investment"],
                description="需要监控的主题关键词",
                options=["stock market", "trading", "investment", "crypto", "finance",
                         "economy", "nasdaq", "sp500", "bitcoin"],
                group="数据源设置"
            ),
            PluginConfigField(
                name="languages",
                display_name="分析语言",
                field_type="multiselect",
                default_value=["en", "zh"],
                description="情绪分析的语言范围",
                options=["en", "zh", "es", "fr", "de", "ja", "ko", "ru"],
                group="数据源设置"
            ),
            PluginConfigField(
                name="time_range",
                display_name="时间范围",
                field_type="select",
                default_value="1h",
                description="情绪数据的时间范围",
                options=["15m", "1h", "4h", "24h", "7d"],
                group="数据源设置"
            ),

            # 请求设置
            PluginConfigField(
                name="request_timeout",
                display_name="请求超时",
                field_type="number",
                default_value=15,
                description="API请求超时时间（秒）",
                min_value=5,
                max_value=60,
                group="请求设置"
            ),
            PluginConfigField(
                name="use_free_tier",
                display_name="使用免费模式",
                field_type="boolean",
                default_value=True,
                description="使用免费模式（无API Key时生成模拟数据）",
                group="请求设置"
            ),
            PluginConfigField(
                name="emotion_weighting_strategy",
                display_name="情绪权重策略",
                field_type="select",
                default_value="balanced",
                description="情绪权重分配策略",
                options=["balanced", "positive_focused", "negative_focused", "custom"],
                group="高级设置"
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
            )
        ]

    def get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "enabled": True,
            "api_key": os.environ.get("EXORDE_API_KEY", ""),
            "primary_emotions": ["love", "joy", "optimism", "fear", "anger", "sadness"],
            "emotion_threshold": 0.3,
            "data_weight": 0.20,
            "topics": ["stock market", "trading", "investment"],
            "languages": ["en", "zh"],
            "time_range": "1h",
            "request_timeout": 15,
            "use_free_tier": True,
            "emotion_weighting_strategy": "balanced",
            "retry_times": 3
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

            # 验证情绪阈值
            emotion_threshold = config.get("emotion_threshold", 0.3)
            is_valid, msg = validate_number_range(emotion_threshold, 0.0, 1.0)
            if not is_valid:
                return False, f"情绪阈值: {msg}"

            # 验证数据权重
            data_weight = config.get("data_weight", 0.20)
            is_valid, msg = validate_number_range(data_weight, 0.0, 1.0)
            if not is_valid:
                return False, f"数据权重: {msg}"

            # 验证主要情绪列表
            primary_emotions = config.get("primary_emotions", [])
            if not primary_emotions:
                return False, "至少需要选择一种主要情绪"

            for emotion in primary_emotions:
                if emotion not in self.emotions:
                    return False, f"无效的情绪类型: {emotion}"

            return True, "配置验证通过"

        except Exception as e:
            return False, f"配置验证异常: {str(e)}"

    def get_available_indicators(self) -> List[str]:
        """获取可用的情绪指标列表"""
        return ["市场情绪光谱", "主导情绪分析", "情绪强度指数"]

    def _fetch_raw_sentiment_data(self, **kwargs) -> SentimentResponse:
        """获取Exorde原始情绪数据"""
        if not self.is_enabled():
            return SentimentResponse(
                success=False,
                data=[],
                composite_score=50.0,
                error_message="Exorde插件已禁用",
                data_quality="disabled",
                update_time=datetime.now()
            )

        try:
            self._safe_log("info", "开始获取Exorde情绪数据...")

            # 获取配置
            api_key = self.get_config("api_key", "").strip()
            use_free_tier = self.get_config("use_free_tier", True)

            if api_key and not use_free_tier:
                # 使用真实API
                sentiment_data = self._fetch_real_exorde_data(api_key)
            else:
                # 使用模拟数据
                sentiment_data = self._fetch_simulated_exorde_data()

            if sentiment_data:
                composite_score = self._calculate_exorde_composite_score(sentiment_data)
                self._safe_log("info", f"成功获取 {len(sentiment_data)} 项Exorde情绪数据")

                return SentimentResponse(
                    success=True,
                    data=sentiment_data,
                    composite_score=composite_score,
                    data_quality="real" if api_key and not use_free_tier else "simulated",
                    update_time=datetime.now()
                )
            else:
                return SentimentResponse(
                    success=False,
                    data=[],
                    composite_score=50.0,
                    error_message="未获取到Exorde情绪数据",
                    data_quality="unavailable",
                    update_time=datetime.now()
                )

        except Exception as e:
            self._safe_log("error", f"Exorde数据获取失败: {str(e)}")
            return SentimentResponse(
                success=False,
                data=[],
                composite_score=50.0,
                error_message=f"Exorde数据获取失败: {str(e)}",
                data_quality="error",
                update_time=datetime.now()
            )

    def _fetch_real_exorde_data(self, api_key: str) -> List[SentimentData]:
        sentiment_data = []
        timeout = self.get_config("request_timeout", 15)
        topics = self.get_config("topics", ["stock market"])
        time_range = self.get_config("time_range", "1h")
        retry_times = self.get_config("retry_times", 3)

        for attempt in range(retry_times + 1):
            try:
                url = "https://api.exorde.io/sentiment"
                params = {
                    "api_key": api_key,
                    "topics": ",".join(topics),
                    "time_range": time_range,
                    "format": "json"
                }

                headers = {
                    'User-Agent': 'FactorWeave-Quant /1.0',
                    'Accept': 'application/json',
                    'Authorization': f'Bearer {api_key}'
                }

                response = requests.get(url, params=params, headers=headers, timeout=timeout)

                if response.status_code == 200:
                    data = response.json()
                    if data and 'sentiment_data' in data:
                        for item in data['sentiment_data']:
                            emotion_scores = {
                                'joy': item.get('joy', 0.0),
                                'anger': item.get('anger', 0.0),
                                'fear': item.get('fear', 0.0),
                                'sadness': item.get('sadness', 0.0),
                                'surprise': item.get('surprise', 0.0),
                                'disgust': item.get('disgust', 0.0),
                                'trust': item.get('trust', 0.0),
                                'anticipation': item.get('anticipation', 0.0)
                            }

                            sentiment_items = self._create_sentiment_data_from_emotions(emotion_scores, "Exorde-Real")
                            sentiment_data.extend(sentiment_items)

                        self._safe_log("info", f"成功获取Exorde真实数据，包含{len(sentiment_data)}个指标")
                        break
                    else:
                        self._safe_log("warning", "Exorde API返回空数据或格式错误，当前无可用数据")
                        if attempt == retry_times:
                            logger.warning("Exorde情绪数据: API返回空数据，不生成模拟数据")

                elif response.status_code == 401:
                    self._safe_log("error", "Exorde API认证失败，API Key无效，当前无可用数据")
                    logger.warning("Exorde情绪数据: API认证失败，不生成模拟数据")
                    break

                elif response.status_code == 429:
                    self._safe_log("warning", f"Exorde API请求限制，等待重试... (尝试 {attempt + 1})")
                    if attempt < retry_times:
                        import time
                        time.sleep(3 ** attempt)
                        continue
                    else:
                        logger.warning("Exorde情绪数据: API请求限制超次，不生成模拟数据")
                        break

                elif response.status_code == 404:
                    self._safe_log("warning", "Exorde API端点不存在，可能API已更新，当前无可用数据")
                    logger.warning("Exorde情绪数据: API端点不存在，不生成模拟数据")
                    break

                else:
                    self._safe_log("warning", f"Exorde API请求失败，状态码: {response.status_code}")
                    if attempt == retry_times:
                        logger.warning("Exorde情绪数据: API请求最终失败，不生成模拟数据")

            except requests.exceptions.Timeout:
                self._safe_log("warning", f"Exorde API请求超时 (尝试 {attempt + 1})")
                if attempt == retry_times:
                    logger.warning("Exorde情绪数据: API请求超时，不生成模拟数据")

            except requests.exceptions.ConnectionError:
                self._safe_log("warning", f"Exorde API连接错误 (尝试 {attempt + 1})")
                if attempt == retry_times:
                    logger.warning("Exorde情绪数据: API连接错误，不生成模拟数据")

            except requests.exceptions.RequestException as e:
                self._safe_log("warning", f"Exorde API网络错误 (尝试 {attempt + 1}): {e}")
                if attempt == retry_times:
                    logger.warning("Exorde情绪数据: API网络错误，不生成模拟数据")

            except json.JSONDecodeError:
                self._safe_log("warning", f"Exorde API响应JSON解析失败 (尝试 {attempt + 1})")
                if attempt == retry_times:
                    logger.warning("Exorde情绪数据: API响应JSON解析失败，不生成模拟数据")

            except Exception as e:
                self._safe_log("error", f"Exorde API调用异常 (尝试 {attempt + 1}): {e}")
                if attempt == retry_times:
                    logger.warning("Exorde情绪数据: API调用异常，不生成模拟数据")

        return sentiment_data

    def _fetch_simulated_exorde_data(self) -> List[SentimentData]:
        """当API不可用时的降级处理 - 返回空数据而不是模拟数据"""
        self._safe_log("warning", "Exorde API不可用，无法获取情感数据")
        return []

    def _generate_emotion_spectrum(self) -> Dict[str, float]:
        logger.warning("Exorde情绪插件: 当前无真实API配置，无法生成情绪光谱数据")
        return {}

    def _create_sentiment_data_from_emotions(self, emotion_scores: Dict[str, float], source: str) -> List[SentimentData]:
        if not emotion_scores:
            logger.warning(f"Exorde情绪数据: emotion_scores为空(source={source})，无法创建情绪数据")
            return []

        sentiment_data = []
        emotion_threshold = self.get_config("emotion_threshold", 0.3)

        dominant_emotion = max(emotion_scores, key=emotion_scores.get)
        dominant_score = emotion_scores[dominant_emotion] * 100

        status, signal = self._get_emotion_status_signal(dominant_emotion, dominant_score)

        spectrum_data = SentimentData(
            indicator_name="市场情绪光谱",
            value=round(dominant_score, 2),
            status=f"{status}({dominant_emotion})",
            change=0.0,
            signal=signal,
            suggestion=f"市场主导情绪为{dominant_emotion}({dominant_score:.1f}%)，建议{signal}",
            timestamp=datetime.now(),
            source=source,
            confidence=0.75
        )
        sentiment_data.append(spectrum_data)

        strong_emotions = {k: v for k, v in emotion_scores.items() if v >= emotion_threshold}
        if len(strong_emotions) > 1:
            strong_emotion_score = np.mean(list(strong_emotions.values())) * 100

            intensity_data = SentimentData(
                indicator_name="情绪强度指数",
                value=round(strong_emotion_score, 2),
                status=f"检测到{len(strong_emotions)}种强情绪",
                change=0.0,
                signal="情绪波动" if len(strong_emotions) >= 4 else "情绪稳定",
                suggestion=f"市场情绪复杂度: {len(strong_emotions)}种强情绪",
                timestamp=datetime.now(),
                source=source,
                confidence=0.70
            )
            sentiment_data.append(intensity_data)

        return sentiment_data

    def _get_emotion_status_signal(self, emotion: str, score: float) -> tuple[str, str]:
        """根据情绪类型和分数获取状态和信号"""
        positive_emotions = {'love', 'joy', 'optimism', 'trust', 'anticipation', 'surprise',
                             'approval', 'caring', 'excitement', 'gratitude', 'pride', 'relief', 'admiration', 'amusement'}
        negative_emotions = {'fear', 'anger', 'sadness', 'disgust', 'pessimism', 'anxiety',
                             'grief', 'nervousness', 'remorse', 'confusion'}

        if emotion in positive_emotions:
            if score >= 80:
                return "极度乐观", "强烈买入"
            elif score >= 60:
                return "乐观", "买入"
            else:
                return "轻微乐观", "持有"
        elif emotion in negative_emotions:
            if score >= 80:
                return "极度悲观", "强烈卖出"
            elif score >= 60:
                return "悲观", "减仓"
            else:
                return "轻微悲观", "谨慎"
        else:
            return "中性", "观望"

    def _calculate_exorde_composite_score(self, sentiment_data: List[SentimentData]) -> float:
        """计算Exorde综合情绪指数"""
        if not sentiment_data:
            return 50.0

        strategy = self.get_config("emotion_weighting_strategy", "balanced")

        total_score = 0.0
        total_weight = 0.0

        for data in sentiment_data:
            weight = 1.0
            confidence = data.confidence or 0.7

            # 根据策略调整权重
            if strategy == "positive_focused" and "乐观" in data.status:
                weight = 1.5
            elif strategy == "negative_focused" and "悲观" in data.status:
                weight = 1.5

            adjusted_weight = weight * confidence
            total_score += data.value * adjusted_weight
            total_weight += adjusted_weight

        if total_weight > 0:
            composite_score = total_score / total_weight
        else:
            composite_score = 50.0

        return max(0.0, min(100.0, round(composite_score, 2)))

# 插件工厂函数
def create_exorde_sentiment_plugin() -> ExordeSentimentPlugin:
    """创建Exorde情绪数据插件实例"""
    return ExordeSentimentPlugin()

if __name__ == "__main__":
    # 测试插件
    plugin = create_exorde_sentiment_plugin()

    # 初始化
    plugin.initialize(None)

    # 加载配置
    plugin.load_config()

    # 测试情绪生成
    emotions = plugin._generate_emotion_spectrum()
    logger.info(f"情绪光谱: {emotions}")

    # 获取数据
    response = plugin._fetch_raw_sentiment_data()

    logger.info(f"成功: {response.success}")
    logger.info(f"数据项: {len(response.data)}")
    logger.info(f"综合指数: {response.composite_score}")

    if response.data:
        for item in response.data:
            logger.info(f"- {item.indicator_name}: {item.value} ({item.status})")
