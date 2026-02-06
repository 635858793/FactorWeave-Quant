"""
形态识别模块
提供基础的形态识别功能
"""

from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from .pattern_base import BasePatternRecognizer, PatternResult, SignalType


class PatternRecognizer(BasePatternRecognizer):
    """基础形态识别器"""

    def __init__(self, config=None):
        """初始化形态识别器"""
        # 如果没有提供config，创建一个默认配置
        if config is None:
            from .pattern_base import PatternConfig, SignalType
            config = PatternConfig(
                id=1,
                name="基础形态识别器",
                english_name="BasicPatternRecognizer",
                category="candlestick",
                signal_type=SignalType.NEUTRAL,
                description="基础的K线形态识别器",
                min_periods=1,
                max_periods=10,
                confidence_threshold=0.5,
                algorithm_code="basic",
                parameters={},
                is_active=True
            )

        super().__init__(config)
        self.name = "基础形态识别器"
        self.version = "1.0.0"

    def recognize(self, kdata: pd.DataFrame) -> List[PatternResult]:
        """
        识别形态 - 实现抽象方法

        Args:
            kdata: K线数据，包含open, high, low, close, volume列

        Returns:
            形态识别结果列表
        """
        return self.recognize_patterns(kdata)

    def recognize_patterns(self, data: pd.DataFrame) -> List[PatternResult]:
        """
        识别形态

        Args:
            data: K线数据，包含open, high, low, close, volume列

        Returns:
            形态识别结果列表
        """
        results = []

        if data is None or data.empty:
            return results

        try:
            # 简单的形态识别示例
            # 这里可以添加更复杂的形态识别逻辑

            # 检测锤子线形态
            hammer_results = self._detect_hammer(data)
            results.extend(hammer_results)

            # 检测十字星形态
            doji_results = self._detect_doji(data)
            results.extend(doji_results)

        except Exception as e:
            # 记录错误但不中断程序
            print(f"形态识别过程中出现错误: {e}")

        return results

    def _detect_hammer(self, data: pd.DataFrame) -> List[PatternResult]:
        """检测锤子线形态"""
        results = []

        if len(data) < 1:
            return results

        try:
            # 从配置中获取参数，如果没有则使用默认值
            min_body_ratio = self.parameters.get('min_body_ratio', 0.1)
            shadow_ratio_threshold = self.parameters.get('shadow_ratio_threshold', 2.0)
            confidence_threshold = self.parameters.get('confidence_threshold', 0.7)

            for i in range(len(data)):
                row = data.iloc[i]
                open_price = row['open']
                high_price = row['high']
                low_price = row['low']
                close_price = row['close']

                # 锤子线的基本条件
                body = abs(close_price - open_price)
                upper_shadow = high_price - max(open_price, close_price)
                lower_shadow = min(open_price, close_price) - low_price

                # 使用配置参数判断
                if lower_shadow > shadow_ratio_threshold * body and upper_shadow < body * min_body_ratio:
                    result = PatternResult(
                        pattern_type="candlestick",
                        pattern_name="锤子线",
                        pattern_category="反转形态",
                        signal_type=SignalType.BUY,
                        confidence=confidence_threshold,
                        confidence_level="中等",
                        index=i,
                        datetime_val=None,
                        price=close_price,
                        start_index=i,
                        end_index=i,
                        extra_data={"description": "检测到锤子线形态，可能的买入信号"}
                    )
                    results.append(result)

        except Exception as e:
            print(f"锤子线检测错误: {e}")

        return results

    def _detect_doji(self, data: pd.DataFrame) -> List[PatternResult]:
        """检测十字星形态"""
        results = []

        if len(data) < 1:
            return results

        try:
            # 从配置中获取参数，如果没有则使用默认值
            body_ratio_threshold = self.parameters.get('body_ratio_threshold', 0.1)
            confidence_threshold = self.parameters.get('confidence_threshold', 0.6)

            for i in range(len(data)):
                row = data.iloc[i]
                open_price = row['open']
                high_price = row['high']
                low_price = row['low']
                close_price = row['close']

                # 十字星的基本条件
                body = abs(close_price - open_price)
                total_range = high_price - low_price

                # 使用配置参数判断
                if total_range > 0 and body / total_range < body_ratio_threshold:
                    result = PatternResult(
                        pattern_type="candlestick",
                        pattern_name="十字星",
                        pattern_category="反转形态",
                        signal_type=SignalType.NEUTRAL,
                        confidence=confidence_threshold,
                        confidence_level="中等",
                        index=i,
                        datetime_val=None,
                        price=close_price,
                        start_index=i,
                        end_index=i,
                        extra_data={"description": "检测到十字星形态，市场犹豫信号"}
                    )
                    results.append(result)

        except Exception as e:
            print(f"十字星检测错误: {e}")

        return results

    def get_supported_patterns(self) -> List[str]:
        """获取支持的形态列表"""
        return ["锤子线", "十字星"]

    def get_pattern_description(self, pattern_name: str) -> str:
        """获取形态描述"""
        descriptions = {
            "锤子线": "锤子线是一种看涨反转形态，特征是实体较小，下影线较长",
            "十字星": "十字星表示市场犹豫不决，开盘价和收盘价几乎相等"
        }
        return descriptions.get(pattern_name, "未知形态")


class EnhancedPatternRecognizer(PatternRecognizer):
    """增强版形态识别器"""

    def __init__(self, config=None, debug_mode=False):
        """初始化增强版形态识别器"""
        super().__init__(config)
        self.debug_mode = debug_mode
        self.name = "增强版形态识别器"
        self.version = "2.0.0"

        # 增强功能
        self.confidence_scores = {}
        self.pattern_history = []

    def recognize(self, kdata: pd.DataFrame) -> List[PatternResult]:
        """
        增强版形态识别 - 包含更多形态和置信度评估

        Args:
            kdata: K线数据

        Returns:
            形态识别结果列表
        """
        if self.debug_mode:
            print(f"开始增强版形态识别，数据量: {len(kdata)}")

        # 调用基础识别方法
        basic_results = super().recognize(kdata)

        # 增强处理
        enhanced_results = []
        for result in basic_results:
            # 计算置信度分数
            confidence = self._calculate_confidence(result, kdata)
            result.confidence = confidence

            # 添加到历史记录
            self.pattern_history.append(result)

            enhanced_results.append(result)

        if self.debug_mode:
            print(f"识别完成，发现 {len(enhanced_results)} 个形态")

        return enhanced_results

    def _calculate_confidence(self, pattern_result: PatternResult, kdata: pd.DataFrame) -> float:
        """计算形态置信度"""
        try:
            # 基础置信度
            base_confidence = 0.5

            # 根据成交量调整
            if len(kdata) > 0:
                volume_factor = min(kdata['volume'].iloc[-1] / kdata['volume'].mean(), 2.0)
                base_confidence *= volume_factor

            # 限制在0-1范围内
            return min(max(base_confidence, 0.0), 1.0)

        except Exception as e:
            if self.debug_mode:
                print(f"计算置信度失败: {e}")
            return 0.5

    def identify_patterns(self, kdata: pd.DataFrame, 
                         confidence_threshold: float = 0.5,
                         pattern_types: Optional[List[str]] = None) -> List[PatternResult]:
        """
        识别形态 - 兼容接口方法
        
        Args:
            kdata: K线数据
            confidence_threshold: 置信度阈值
            pattern_types: 要识别的形态类型列表，None表示识别所有类型
            
        Returns:
            形态识别结果列表
        """
        try:
            # 使用 PatternManager 进行形态识别
            from analysis.pattern_manager import PatternManager
            
            pattern_manager = PatternManager()
            
            # 获取要识别的形态配置
            if pattern_types:
                # 如果指定了形态类型，只识别这些类型
                pattern_configs = []
                for pattern_type in pattern_types:
                    config = pattern_manager.get_pattern_config(pattern_type)
                    if config:
                        pattern_configs.append(config)
            else:
                # 识别所有激活的形态
                pattern_configs = pattern_manager.get_pattern_configs(active_only=True)
            
            if not pattern_configs:
                if self.debug_mode:
                    print(f"[identify_patterns] 没有找到可用的形态配置")
                return []
            
            # 执行形态识别
            all_results = []
            
            for config in pattern_configs:
                try:
                    # 使用配置的置信度阈值或传入的阈值
                    threshold = max(config.confidence_threshold, confidence_threshold)
                    
                    # 尝试使用 PatternAlgorithmFactory 创建识别器
                    recognizer = None
                    try:
                        from analysis.pattern_base import PatternAlgorithmFactory
                        recognizer = PatternAlgorithmFactory.create(config)
                    except (ValueError, AttributeError) as e:
                        # 如果工厂无法创建识别器，使用基础识别器
                        if self.debug_mode:
                            print(f"[identify_patterns] 无法通过工厂创建识别器，使用基础识别器: {e}")
                        recognizer = PatternRecognizer(config)
                    
                    # 验证数据
                    if not recognizer.validate_data(kdata):
                        continue
                    
                    # 识别形态
                    results = recognizer.recognize(kdata)
                    
                    # 过滤置信度
                    filtered_results = [
                        r for r in results 
                        if hasattr(r, 'confidence') and r.confidence >= threshold
                    ]
                    
                    all_results.extend(filtered_results)
                    
                except Exception as e:
                    if self.debug_mode:
                        print(f"[identify_patterns] 识别形态 {config.name} 时出错: {e}")
                    continue
            
            # 按置信度排序
            all_results.sort(key=lambda x: x.confidence if hasattr(x, 'confidence') else 0, reverse=True)
            
            if self.debug_mode:
                print(f"[identify_patterns] 识别完成，发现 {len(all_results)} 个形态")
            
            return all_results
            
        except Exception as e:
            if self.debug_mode:
                print(f"[identify_patterns] 形态识别失败: {e}")
            # 如果 PatternManager 不可用，回退到基础识别方法
            return self.recognize(kdata)

    def get_pattern_statistics(self) -> Dict[str, Any]:
        """获取形态统计信息"""
        if not self.pattern_history:
            return {}

        stats = {
            'total_patterns': len(self.pattern_history),
            'pattern_types': {},
            'avg_confidence': 0.0
        }

        # 统计各类形态数量
        for pattern in self.pattern_history:
            pattern_name = pattern.pattern_name
            if pattern_name not in stats['pattern_types']:
                stats['pattern_types'][pattern_name] = 0
            stats['pattern_types'][pattern_name] += 1

        # 计算平均置信度
        if self.pattern_history:
            total_confidence = sum(p.confidence for p in self.pattern_history if hasattr(p, 'confidence'))
            stats['avg_confidence'] = total_confidence / len(self.pattern_history)

        return stats


# 兼容性函数
def get_performance_monitor():
    """获取性能监控器（兼容性函数）"""
    return None


def get_pattern_cache():
    """获取形态缓存（兼容性函数）"""
    return {}


def get_pattern_recognizer_info():
    """获取形态识别器信息（兼容性函数）"""
    return {
        'name': 'EnhancedPatternRecognizer',
        'version': '2.0.0',
        'supported_patterns': ['锤子线', '十字星']
    }
