"""
形态识别模块
提供基础的形态识别功能
"""

from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
import logging

from .pattern_base import BasePatternRecognizer, PatternResult, SignalType

logger = logging.getLogger(__name__)


class PatternRecognizer(BasePatternRecognizer):
    """基础形态识别器"""

    def __init__(self, config=None, debug_mode=False):
        """初始化形态识别器"""
        self.debug_mode = debug_mode
        
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
            algorithm_executed = False

            if hasattr(self.config, 'algorithm_code') and self.config.algorithm_code:
                algorithm_code = self.config.algorithm_code.strip()
                if algorithm_code and algorithm_code != 'basic':
                    if self.debug_mode:
                        print(f"[recognize_patterns] 开始执行算法: {self.config.name}")
                    try:
                        results = self._execute_algorithm_code(algorithm_code, data)
                        algorithm_executed = True
                        if self.debug_mode:
                            print(f"[recognize_patterns] 执行算法代码成功，检测到 {len(results)} 个形态: {self.config.name}")
                    except Exception as e:
                        if self.debug_mode:
                            print(f"[recognize_patterns] 执行算法代码失败: {e}，回退到默认识别")
                        import traceback
                        if self.debug_mode:
                            traceback.print_exc()

            if not algorithm_executed:
                if self.debug_mode:
                    logger.info(f"[recognize_patterns] 使用默认识别器，检测形态: 锤子线, 十字星")

                hammer_dicts = self._detect_hammer(data)
                logger.debug(f"[recognize_patterns] 锤子线检测结果: {len(hammer_dicts)} 个")
                for hammer_dict in hammer_dicts:
                    result = self._convert_dict_to_pattern_result(hammer_dict, data)
                    if result:
                        logger.debug(f"[recognize_patterns] 添加锤子线结果: signal={result.signal_type.value}, confidence={result.confidence:.2f}")
                        results.append(result)

                doji_dicts = self._detect_doji(data)
                logger.debug(f"[recognize_patterns] 十字星检测结果: {len(doji_dicts)} 个")
                for doji_dict in doji_dicts:
                    result = self._convert_dict_to_pattern_result(doji_dict, data)
                    if result:
                        logger.debug(f"[recognize_patterns] 添加十字星结果: signal={result.signal_type.value}, confidence={result.confidence:.2f}")
                        results.append(result)

        except Exception as e:
            logger.error(f"形态识别过程中出现错误: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return results

    def _execute_algorithm_code(self, algorithm_code: str, data: pd.DataFrame) -> List[PatternResult]:
        """
        执行存储在数据库中的算法代码

        Args:
            algorithm_code: 存储的Python算法代码
            data: K线数据

        Returns:
            形态识别结果列表
        """
        results = []

        try:
            kdata = data.copy()
            
            trend = self.analyze_trend(kdata)

            def get_datetime_val(kdata, index):
                """获取指定索引的日期时间字符串"""
                try:
                    if hasattr(kdata, 'index') and index < len(kdata):
                        if hasattr(kdata.index, '__getitem__'):
                            return str(kdata.index[index])
                        elif 'datetime' in kdata.columns and index < len(kdata):
                            return str(kdata.iloc[index]['datetime'])
                    return None
                except:
                    return None

            try:
                from scipy import signal as scipy_signal
                has_scipy = True
            except ImportError:
                has_scipy = False

            local_vars = {
                'kdata': kdata,
                'results': results,
                'pd': pd,
                'np': np,
                'scipy_signal': scipy_signal if has_scipy else None,
                'PatternResult': PatternResult,
                'SignalType': SignalType,
                'create_result': self.create_result,
                'get_datetime_val': get_datetime_val,
                'trend': trend,
                'analyze_trend': self.analyze_trend,
                'is_trend_compatible': self.is_trend_compatible,
            }

            exec(algorithm_code, {}, local_vars)

            raw_results = local_vars.get('results', [])
            
            for r in raw_results:
                if isinstance(r, PatternResult):
                    signal_str = r.signal_type.value if hasattr(r.signal_type, 'value') else str(r.signal_type)
                    compatible, reason, confidence_adjust = self.is_trend_compatible(signal_str, trend)
                    
                    if compatible:
                        r.confidence = min(1.0, r.confidence * confidence_adjust)
                        r.confidence_level = self.calculate_confidence_level(r.confidence)
                        if not hasattr(r, '_trend_reason') or r._trend_reason is None:
                            r._trend_reason = reason
                        results.append(r)
                    elif self.debug_mode:
                        print(f"[趋势过滤] {r.pattern_name} 在位置 {r.index} 被过滤: {reason}")
                elif isinstance(r, dict):
                    signal_str = r.get('signal_type', 'neutral')
                    
                    compatible, reason, confidence_adjust = self.is_trend_compatible(signal_str, trend)
                    
                    r['_trend_compatible'] = compatible
                    r['_trend_reason'] = reason
                    r['_confidence_adjust'] = confidence_adjust
                    
                    if compatible:
                        result = self._convert_dict_to_pattern_result(r, kdata)
                        if result:
                            result.confidence = min(1.0, result.confidence * confidence_adjust)
                            result.confidence_level = self.calculate_confidence_level(result.confidence)
                            results.append(result)
                    elif self.debug_mode:
                        print(f"[趋势过滤] {r.get('pattern_name', 'unknown')} 在位置 {r.get('index', 0)} 被过滤: {reason}")

        except Exception as e:
            if self.debug_mode:
                print(f"[_execute_algorithm_code] 执行算法失败: {e}")
            raise

        return results

    def _convert_dict_to_pattern_result(self, data: dict, kdata: pd.DataFrame = None) -> Optional[PatternResult]:
        """将字典转换为PatternResult对象，并应用智能信号计算"""
        try:
            base_signal = SignalType.from_string(data.get('signal_type', 'neutral'))
            
            if kdata is not None and 'index' in data:
                try:
                    from analysis.intelligent_signal_calculator_optimized import create_intelligent_signal_calculator
                    
                    calculator = create_intelligent_signal_calculator()
                    index = data.get('index', 0)
                    confidence = data.get('confidence', 0.5)
                    pattern_name = data.get('pattern_name', self.config.name)
                    pattern_category = data.get('pattern_category', self.config.category)
                    
                    final_signal, adjusted_confidence, reason = calculator.calculate_signal(
                        pattern_name=pattern_name,
                        pattern_category=pattern_category,
                        base_signal=base_signal,
                        kdata=kdata,
                        index=index,
                        confidence=confidence,
                        trend_info=None
                    )
                    
                    if self.debug_mode:
                        print(f"[智能信号] {pattern_name}: {base_signal.value} -> {final_signal.value} "
                              f"(置信度: {confidence:.2f} -> {adjusted_confidence:.2f})")
                        print(f"  原因: {reason}")
                    
                    signal_type = final_signal
                    confidence = adjusted_confidence
                    
                    if 'extra_data' not in data:
                        data['extra_data'] = {}
                    data['extra_data']['signal_reason'] = reason
                    
                except Exception as e:
                    if self.debug_mode:
                        print(f"[智能信号计算失败] 使用原始信号: {e}")
                    signal_type = base_signal
                    confidence = data.get('confidence', 0.5)
            else:
                signal_type = base_signal
                confidence = data.get('confidence', 0.5)
            
            return PatternResult(
                pattern_type=data.get('pattern_type', 'unknown'),
                pattern_name=data.get('pattern_name', self.config.name),
                pattern_category=data.get('pattern_category', self.config.category),
                signal_type=signal_type,
                confidence=confidence,
                confidence_level=self.calculate_confidence_level(confidence),
                index=data.get('index', 0),
                datetime_val=data.get('datetime_val'),
                price=data.get('price', 0.0),
                start_index=data.get('start_index', data.get('index', 0)),
                end_index=data.get('end_index', data.get('index', 0)),
                extra_data=data.get('extra_data', data)
            )
        except Exception as e:
            if self.debug_mode:
                print(f"[_convert_dict_to_pattern_result] 转换失败: {e}")
            return None

    def _detect_hammer(self, data: pd.DataFrame) -> List[dict]:
        """检测锤子线和上吊线形态 - 返回字典列表以支持智能信号计算"""
        results = []

        if len(data) < 2:
            return results

        try:
            min_body_ratio = self.parameters.get('min_body_ratio', 0.1)
            shadow_ratio_threshold = self.parameters.get('shadow_ratio_threshold', 2.0)
            confidence_threshold = self.parameters.get('confidence_threshold', 0.7)

            for i in range(len(data)):
                row = data.iloc[i]
                open_price = row['open']
                high_price = row['high']
                low_price = row['low']
                close_price = row['close']

                body = abs(close_price - open_price)
                upper_shadow = high_price - max(open_price, close_price)
                lower_shadow = min(open_price, close_price) - low_price
                total_range = high_price - low_price

                if total_range <= 0:
                    continue

                body_ratio = body / total_range if total_range > 0 else 0
                
                is_small_body = body_ratio < 0.3
                has_long_lower_shadow = lower_shadow > shadow_ratio_threshold * body
                has_small_upper_shadow = upper_shadow < body * 0.2
                
                is_hammer_shape = has_long_lower_shadow and has_small_upper_shadow and is_small_body
                
                if not is_hammer_shape:
                    continue
                
                if i < 1:
                    continue
                
                prev_data = data.iloc[max(0, i-1):i]
                if len(prev_data) > 0:
                    prev_close = prev_data['close'].iloc[-1]
                    prev_avg = data.iloc[max(0, i-5):i]['close'].mean() if i >= 5 else data['close'].mean()
                else:
                    prev_close = close_price
                    prev_avg = close_price
                
                is_bullish = close_price > open_price
                
                if is_bullish:
                    results.append({
                        'pattern_type': 'candlestick',
                        'pattern_name': '锤子线',
                        'pattern_category': '反转形态',
                        'signal_type': 'buy',
                        'confidence': confidence_threshold,
                        'index': i,
                        'datetime_val': None,
                        'price': float(close_price),
                        'start_index': i,
                        'end_index': i,
                        'description': '检测到锤子线形态，潜在的反转买入信号'
                    })
                else:
                    results.append({
                        'pattern_type': 'candlestick',
                        'pattern_name': '上吊线',
                        'pattern_category': '反转形态',
                        'signal_type': 'sell',
                        'confidence': confidence_threshold * 0.9,
                        'index': i,
                        'datetime_val': None,
                        'price': float(close_price),
                        'start_index': i,
                        'end_index': i,
                        'description': '检测到上吊线形态，潜在的反转卖出信号'
                    })

        except Exception as e:
            print(f"锤子线检测错误: {e}")

        return results

    def _detect_doji(self, data: pd.DataFrame) -> List[dict]:
        """检测十字星形态 - 返回字典列表以支持智能信号计算"""
        results = []

        if len(data) < 2:
            return results

        try:
            body_ratio_threshold = self.parameters.get('body_ratio_threshold', 0.1)
            confidence_threshold = self.parameters.get('confidence_threshold', 0.6)

            for i in range(len(data)):
                if i < 1:
                    continue
                    
                row = data.iloc[i]
                prev_row = data.iloc[i-1]
                open_price = row['open']
                high_price = row['high']
                low_price = row['low']
                close_price = row['close']

                body = abs(close_price - open_price)
                total_range = high_price - low_price

                if total_range <= 0 or body / total_range >= body_ratio_threshold:
                    continue
                
                prev_close = prev_row['close']
                prev_open = prev_row['open']
                prev_body = abs(prev_close - prev_open)
                prev_body_ratio = prev_body / (prev_row['high'] - prev_row['low']) if (prev_row['high'] - prev_row['low']) > 0 else 1.0
                
                if prev_body_ratio > 0.3:
                    if close_price > prev_close and close_price > open_price:
                        results.append({
                            'pattern_type': 'candlestick',
                            'pattern_name': '十字星',
                            'pattern_category': '反转形态',
                            'signal_type': 'buy',
                            'confidence': confidence_threshold,
                            'index': i,
                            'datetime_val': None,
                            'price': float(close_price),
                            'start_index': i,
                            'end_index': i,
                            'description': '检测到十字星形态，看涨反转信号'
                        })
                    elif close_price < prev_close and close_price < open_price:
                        results.append({
                            'pattern_type': 'candlestick',
                            'pattern_name': '十字星',
                            'pattern_category': '反转形态',
                            'signal_type': 'sell',
                            'confidence': confidence_threshold,
                            'index': i,
                            'datetime_val': None,
                            'price': float(close_price),
                            'start_index': i,
                            'end_index': i,
                            'description': '检测到十字星形态，看跌反转信号'
                        })
                    else:
                        results.append({
                            'pattern_type': 'candlestick',
                            'pattern_name': '十字星',
                            'pattern_category': '反转形态',
                            'signal_type': 'neutral',
                            'confidence': confidence_threshold * 0.8,
                            'index': i,
                            'datetime_val': None,
                            'price': float(close_price),
                            'start_index': i,
                            'end_index': i,
                            'description': '检测到十字星形态，市场犹豫信号'
                        })

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

        # 增强处理 - 保留智能信号计算器的结果
        enhanced_results = []
        for result in basic_results:
            # 基于智能信号计算器的置信度进行调整，而不是覆盖
            adjusted_confidence = self._adjust_confidence(result, kdata)
            result.confidence = adjusted_confidence

            # 添加到历史记录
            self.pattern_history.append(result)

            enhanced_results.append(result)

        if self.debug_mode:
            print(f"识别完成，发现 {len(enhanced_results)} 个形态")

        return enhanced_results

    def _adjust_confidence(self, pattern_result: PatternResult, kdata: pd.DataFrame) -> float:
        """
        调整形态置信度 - 基于智能信号计算器的结果进行微调
        
        注意：此方法不应该完全覆盖置信度，而是基于成交量等因素进行微调
        """
        try:
            # 保留智能信号计算器的置信度作为基础
            base_confidence = pattern_result.confidence
            
            # 根据成交量进行微调（仅作为辅助因素）
            if len(kdata) > 0 and 'volume' in kdata.columns:
                volume_factor = min(kdata['volume'].iloc[-1] / kdata['volume'].mean(), 1.2)  # 限制最大调整幅度
                adjusted_confidence = base_confidence * volume_factor
            else:
                adjusted_confidence = base_confidence
            
            # 限制在0-1范围内
            return min(max(adjusted_confidence, 0.1), 1.0)

        except Exception as e:
            if self.debug_mode:
                print(f"调整置信度失败: {e}")
            return pattern_result.confidence  # 返回原始置信度

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
            logger.info(f"[identify_patterns] 开始查找形态配置，pattern_types={pattern_types}")
            
            if pattern_types:
                # 如果指定了形态类型，只识别这些类型
                pattern_configs = []
                for pattern_type in pattern_types:
                    config = pattern_manager.get_pattern_config(pattern_type)
                    logger.info(f"[identify_patterns] 查找 {pattern_type}: {'找到' if config else '未找到'}")
                    if config:
                        pattern_configs.append(config)
            else:
                # 识别所有激活的形态
                pattern_configs = pattern_manager.get_pattern_configs(active_only=True)
            
            logger.info(f"[identify_patterns] 找到 {len(pattern_configs)} 个形态配置")
            
            if not pattern_configs:
                logger.warning(f"[identify_patterns] 没有找到可用的形态配置，pattern_types={pattern_types}")
                if self.debug_mode:
                    print(f"[identify_patterns] 没有找到可用的形态配置")
                return []
            
            # 执行形态识别
            all_results = []
            
            for config in pattern_configs:
                try:
                    threshold = confidence_threshold
                    
                    # 尝试使用 PatternAlgorithmFactory 创建识别器
                    recognizer = None
                    try:
                        from analysis.pattern_base import PatternAlgorithmFactory
                        recognizer = PatternAlgorithmFactory.create(config)
                    except (ValueError, AttributeError) as e:
                        # 如果工厂无法创建识别器，使用基础识别器
                        if self.debug_mode:
                            print(f"[identify_patterns] 无法通过工厂创建识别器，使用基础识别器: {e}")
                        recognizer = PatternRecognizer(config, debug_mode=self.debug_mode)
                    
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
            
            # 信号去重：同一位置只保留最高置信度的信号
            all_results = self._deduplicate_signals(all_results)
            
            if self.debug_mode:
                print(f"[identify_patterns] 识别完成，发现 {len(all_results)} 个形态（去重后）")
            
            return all_results
            
        except Exception as e:
            if self.debug_mode:
                print(f"[identify_patterns] 形态识别失败: {e}")
            # 如果 PatternManager 不可用，回退到基础识别方法
            return self.recognize(kdata)

    def _deduplicate_signals(self, results: List[PatternResult], min_gap: int = 3) -> List[PatternResult]:
        """
        信号去重：同一位置只保留最高置信度的信号，相邻位置保留间距
        
        Args:
            results: 形态识别结果列表
            min_gap: 相邻信号最小间距（K线根数），默认3根
            
        Returns:
            去重后的结果列表
        """
        if not results:
            return results
        
        # 第一步：同一位置只保留最高置信度的信号
        position_map = {}
        for r in results:
            idx = r.index if hasattr(r, 'index') else 0
            if idx not in position_map:
                position_map[idx] = r
            else:
                existing_conf = position_map[idx].confidence if hasattr(position_map[idx], 'confidence') else 0
                new_conf = r.confidence if hasattr(r, 'confidence') else 0
                if new_conf > existing_conf:
                    position_map[idx] = r
        
        # 第二步：相邻信号最小间距过滤
        sorted_results = sorted(position_map.values(), key=lambda x: x.index if hasattr(x, 'index') else 0)
        
        deduplicated = []
        last_kept_index = -min_gap  # 确保第一个信号不被跳过
        
        for r in sorted_results:
            idx = r.index if hasattr(r, 'index') else 0
            if idx - last_kept_index >= min_gap:
                deduplicated.append(r)
                last_kept_index = idx
            elif self.debug_mode:
                skipped_name = r.pattern_name if hasattr(r, 'pattern_name') else 'unknown'
                print(f"[去重] 跳过 {skipped_name} 在位置 {idx}，距离上次信号不足 {min_gap} 根K线")
        
        return deduplicated

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
