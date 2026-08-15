"""
形态识别模块
提供基础的形态识别功能
"""

import re
import ast
import hashlib
import builtins as _builtins
from loguru import logger
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from loguru import logger

from .pattern_base import (
    BasePatternRecognizer, PatternResult, SignalType, find_local_extremes,
)

ALLOWED_AST_NODES = frozenset({
    ast.Module,
    ast.Expr,
    ast.Assign,
    ast.AugAssign,
    ast.For,
    ast.If,
    ast.Continue,
    ast.Break,
    ast.Pass,
    ast.Try,
    ast.ExceptHandler,
    ast.Return,
    ast.Raise,
    ast.Name,
    ast.Constant,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.IfExp,
    ast.Call,
    ast.Subscript,
    ast.Slice,
    ast.Attribute,
    ast.List,
    ast.Dict,
    ast.Tuple,
    ast.GeneratorExp,
    ast.ListComp,  # R245: inverted_hammer code 使用列表推导式，此前缺此项导致 Track2 被 AST 拒绝
    ast.comprehension,
    ast.keyword,
    ast.Load,
    ast.Store,
    ast.Del,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.Pow,
    ast.FloorDiv,
    ast.MatMult,
    ast.And,
    ast.Or,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.Gt,
    ast.LtE,
    ast.GtE,
    ast.Is,
    ast.IsNot,
    ast.In,
    ast.NotIn,
    ast.Not,
    ast.USub,
    ast.UAdd,
    ast.Invert,
    ast.BitAnd,
    ast.BitOr,
    ast.BitXor,
    ast.LShift,
    ast.RShift,
})

ALLOWED_BUILTIN_NAMES = frozenset({
    'abs', 'all', 'any', 'bool', 'dict', 'enumerate',
    'Exception',  # R245: three_black_crows code 使用 except Exception，此前缺失导致 Track2 失败
    'False', 'float', 'int', 'len', 'list',
    'max', 'min', 'None', 'print', 'range',
    'round', 'sorted', 'str', 'sum', 'True',
    'tuple', 'zip',
})

_ALGO_CACHE = {}

# R245/R246: 内置形态检测方法的分发表。键 = PatternConfig.english_name（小写），值 = PatternRecognizer 方法名。
# R246: 扩展至 23 键 —— 14 个 K 线形态（镜像 db/init_pattern_algorithms.py Track2 算法，含 hammer/doji）
# + hanging_man + 8 个反转/持续形态。recognize_patterns 中 Track1 分发表优先于 Track2 exec，
# 与 DB algorithm_code 状态无关（DB 残留旧代码也不执行）。仅未注册的自定义形态走 exec 沙箱。
_DETECT_DISPATCH = {
    # K 线形态（14 个，R246 自 Track2 迁移 + hammer/doji 原生）
    'hammer': '_detect_hammer',
    'hanging_man': '_detect_hanging_man',
    'doji': '_detect_doji',
    'shooting_star': '_detect_shooting_star',
    'inverted_hammer': '_detect_inverted_hammer',
    'marubozu': '_detect_marubozu',
    'spinning_top': '_detect_spinning_top',
    'bullish_engulfing': '_detect_bullish_engulfing',
    'bearish_engulfing': '_detect_bearish_engulfing',
    'piercing_pattern': '_detect_piercing_pattern',
    'dark_cloud_cover': '_detect_dark_cloud_cover',
    'three_white_soldiers': '_detect_three_white_soldiers',
    'three_black_crows': '_detect_three_black_crows',
    'morning_star': '_detect_morning_star',
    'evening_star': '_detect_evening_star',
    # 反转/持续形态（8 个，R245 迁移）
    'double_top': '_detect_double_top',
    'head_shoulders_top': '_detect_head_shoulders_top',
    'triple_top': '_detect_triple_top',
    'double_bottom': '_detect_double_bottom',
    'head_shoulders_bottom': '_detect_head_shoulders_bottom',
    'triple_bottom': '_detect_triple_bottom',
    'ascending_triangle': '_detect_ascending_triangle',
    'descending_triangle': '_detect_descending_triangle',
}


def _merge_adjacent_extremes(indices: List[int], values: np.ndarray,
                             min_gap: int = 4, is_peak: bool = True) -> List[int]:
    """合并间距过近的极值点索引。

    find_local_extremes 使用 >=/<= 条件，平顶/平台会产出相邻重复点（如
    [16, 17] 同为最高点），导致头肩顶/三重顶等形态的相邻 3 极值间距检查
    (h-l)<4 全部被跳过。此处将间距 < min_gap 的相邻点合并：峰保留更高值、
    谷保留更低值的索引。
    """
    if not indices:
        return []
    merged = [indices[0]]
    for idx in indices[1:]:
        if idx - merged[-1] < min_gap:
            last = merged[-1]
            if (values[idx] > values[last]) if is_peak else (values[idx] < values[last]):
                merged[-1] = idx
        else:
            merged.append(idx)
    return merged


def _noop_print(*args, **kwargs):
    pass


def _validate_ast(code: str) -> None:
    try:
        tree = ast.parse(code, mode='exec')
    except SyntaxError as e:
        raise ValueError(f"算法代码语法错误: {e}")

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("算法代码不允许使用import语句")

        if isinstance(node, ast.Attribute):
            if isinstance(node.attr, str) and node.attr.startswith('__'):
                raise ValueError(f"算法代码不允许访问双下划线属性: {node.attr}")

        if type(node) not in ALLOWED_AST_NODES:
            raise ValueError(f"算法代码包含不支持的语法结构: {type(node).__name__}")


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

            # R246: Track1 优先 —— 23 个内置形态走 _DETECT_DISPATCH（与 DB algorithm_code 状态无关，
            # DB 残留旧 Track2 代码也不执行）。仅未注册的自定义形态回落到 Track2 exec 沙箱。
            pattern_key = (getattr(self.config, 'english_name', '') or '').strip().lower()
            dispatch_method = _DETECT_DISPATCH.get(pattern_key)

            if dispatch_method and hasattr(self, dispatch_method):
                if self.debug_mode:
                    logger.info(f"[recognize_patterns] 使用内置识别器（Track1），检测形态: {pattern_key}")
                for detect_dict in getattr(self, dispatch_method)(data):
                    result = self._convert_dict_to_pattern_result(detect_dict, data)
                    if result:
                        results.append(result)
                algorithm_executed = True
            elif hasattr(self.config, 'algorithm_code') and self.config.algorithm_code:
                algorithm_code = self.config.algorithm_code.strip()
                if algorithm_code and algorithm_code != 'basic':
                    if self.debug_mode:
                        logger.debug(f"[recognize_patterns] 开始执行算法: {self.config.name}")
                    try:
                        results = self._execute_algorithm_code(algorithm_code, data)
                        algorithm_executed = True
                        if self.debug_mode:
                            logger.debug(f"[recognize_patterns] 执行算法代码成功，检测到 {len(results)} 个形态: {self.config.name}")
                    except Exception as e:
                        if self.debug_mode:
                            logger.warning(f"[recognize_patterns] 执行算法代码失败: {e}，回退到默认识别")
                        import traceback
                        if self.debug_mode:
                            traceback.print_exc()

            if not algorithm_executed:
                # 未知形态（未注册且无算法代码）回退到 hammer/doji 默认行为
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
                except Exception:
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

            # R245 修复: 白名单加入中文全角标点 (：，。（）、；·—…“”‘’)
            # 原因: 多个 algorithm_code 的注释含全角标点，此前会被误判为非法字符而静默跳过执行。
            # 全角标点无 Python 语法意义（仅出现在注释/字符串中），放开不引入注入风险。
            if not re.match(r'^[\s\w\d.,;:()\[\]{}\+\-*/%=<>!&|@\'\"#\n：，。（）、；·—…“”‘’]*$', algorithm_code):
                logger.warning("算法代码包含非法字符，跳过执行")
                return []

            _validate_ast(algorithm_code)

            code_hash = hashlib.sha256(algorithm_code.encode('utf-8')).hexdigest()
            if code_hash not in _ALGO_CACHE:
                _ALGO_CACHE[code_hash] = compile(algorithm_code, '<pattern_algorithm>', 'exec')

            restricted_builtins = {}
            for name in ALLOWED_BUILTIN_NAMES:
                if name == 'print':
                    restricted_builtins[name] = _noop_print
                elif name in ('True', 'False', 'None'):
                    restricted_builtins[name] = getattr(_builtins, name)
                else:
                    restricted_builtins[name] = getattr(_builtins, name)

            exec(_ALGO_CACHE[code_hash], {"__builtins__": restricted_builtins}, local_vars)

            # R245 修复: local_vars['results'] 与外层 results 是同一对象，for 循环内
            # results.append(r) 会无限追加导致死循环（Track2 检出 >=1 形态即卡死）。
            # 此处复制为独立列表再遍历。
            raw_results = list(local_vars.get('results', []))
            
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
                        logger.debug(f"[趋势过滤] {r.pattern_name} 在位置 {r.index} 被过滤: {reason}")
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
                        logger.debug(f"[趋势过滤] {r.get('pattern_name', 'unknown')} 在位置 {r.get('index', 0)} 被过滤: {reason}")

        except Exception as e:
            if self.debug_mode:
                logger.warning(f"[_execute_algorithm_code] 执行算法失败: {e}")
            raise

        return results

    def _convert_dict_to_pattern_result(self, data: dict, kdata: pd.DataFrame = None) -> Optional[PatternResult]:
        """将字典转换为PatternResult对象，并应用智能信号计算"""
        try:
            base_signal = SignalType.from_string(data.get('signal_type', 'neutral'))
            
            if kdata is not None and 'index' in data:
                try:
                    if self._signal_calculator is None:
                        from analysis.intelligent_signal_calculator_optimized import create_intelligent_signal_calculator
                        self._signal_calculator = create_intelligent_signal_calculator()

                    calculator = self._signal_calculator
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
                        logger.debug(f"[智能信号] {pattern_name}: {base_signal.value} -> {final_signal.value} "
                              f"(置信度: {confidence:.2f} -> {adjusted_confidence:.2f})")
                        logger.debug(f"  原因: {reason}")
                    
                    signal_type = final_signal
                    confidence = adjusted_confidence
                    
                    if 'extra_data' not in data:
                        data['extra_data'] = {}
                    data['extra_data']['signal_reason'] = reason
                    
                except Exception as e:
                    if self.debug_mode:
                        logger.warning(f"[智能信号计算失败] 使用原始信号: {e}")
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
                logger.warning(f"[_convert_dict_to_pattern_result] 转换失败: {e}")
            return None

    def _detect_hammer(self, data: pd.DataFrame) -> List[dict]:
        """检测锤头线形态（买入信号）— R246: 镜像 Track2 hammer 算法（init_pattern_algorithms.py L26-67），
        公式化置信度 + extra_data，仅输出看涨方向（上吊线由 _detect_hanging_man 独立输出，避免锤头配置误带上吊线信号）"""
        results = []

        if data is None or data.empty:
            return results

        try:
            has_datetime = 'datetime' in data.columns
            for i in range(len(data)):
                k = data.iloc[i]

                body_size = abs(k['close'] - k['open'])
                upper_shadow = k['high'] - max(k['open'], k['close'])
                lower_shadow = min(k['open'], k['close']) - k['low']
                total_range = k['high'] - k['low']

                if total_range == 0:
                    continue

                body_ratio = body_size / total_range
                upper_ratio = upper_shadow / total_range
                lower_ratio = lower_shadow / total_range

                # 锤头线特征：小实体，几乎没有上影线，长下影线（与 Track2 R245 阈值一致）
                if (body_ratio < 0.3 and upper_shadow < body_size * 0.2
                        and lower_shadow > 2.0 * body_size and total_range > 0):
                    confidence = min(0.9, lower_ratio * 0.8 + (0.3 - body_ratio) * 0.5 + (0.1 - upper_ratio) * 0.3)
                    results.append({
                        'pattern_type': 'hammer',
                        'pattern_name': '锤头线',
                        'pattern_category': 'K线形态',
                        'signal_type': 'buy',
                        'confidence': confidence,
                        'index': int(i),
                        'datetime_val': str(k['datetime']) if has_datetime else None,
                        'price': float(k['close']),
                        'start_index': int(i),
                        'end_index': int(i),
                        'extra_data': {
                            'body_ratio': float(body_ratio),
                            'upper_ratio': float(upper_ratio),
                            'lower_ratio': float(lower_ratio)
                        },
                        'description': '检测到锤头线形态，潜在的反转买入信号'
                    })
        except Exception as e:
            logger.warning(f"锤头线检测错误: {e}")

        return results

    def _detect_doji(self, data: pd.DataFrame) -> List[dict]:
        """检测十字星形态（中性信号）— R246: 镜像 Track2 doji 算法（init_pattern_algorithms.py L71-111），
        含前一根实体上下文；恒 NEUTRAL（与 _SEED_PATTERNS 的 doji 信号约定一致）"""
        results = []

        if data is None or data.empty:
            return results

        try:
            has_datetime = 'datetime' in data.columns
            prev_body_ratio = 0.0
            for i in range(len(data)):
                k = data.iloc[i]

                body_size = abs(k['close'] - k['open'])
                total_range = k['high'] - k['low']

                if total_range == 0:
                    prev_body_ratio = 0.0
                    continue

                body_ratio = body_size / total_range

                # 实体占比小于10%且前一根实体大于30%认为是十字星（含 i==0 无前一根的放行，与 Track2 一致）
                if body_ratio < 0.1 and (i == 0 or prev_body_ratio > 0.3):
                    confidence = min(0.9, (0.1 - body_ratio) / 0.1 * 0.9 + 0.5)
                    results.append({
                        'pattern_type': 'doji',
                        'pattern_name': '十字星',
                        'pattern_category': 'K线形态',
                        'signal_type': 'neutral',
                        'confidence': confidence,
                        'index': int(i),
                        'datetime_val': str(k['datetime']) if has_datetime else None,
                        'price': float((k['open'] + k['close']) / 2),
                        'start_index': int(i),
                        'end_index': int(i),
                        'extra_data': {
                            'body_ratio': float(body_ratio),
                            'upper_shadow': float(k['high'] - max(k['open'], k['close'])),
                            'lower_shadow': float(min(k['open'], k['close']) - k['low'])
                        },
                        'description': '检测到十字星形态，市场犹豫信号'
                    })
                prev_body_ratio = body_ratio
        except Exception as e:
            logger.warning(f"十字星检测错误: {e}")

        return results

    # ==================== R245/R246: 内置形态检测（Track1） ====================
    # R246: 14 个 K 线形态自 Track2（db/init_pattern_algorithms.py exec 算法）迁移为原生 _detect_* 方法，
    # 逐行镜像 Track2 语义（条件/置信度公式/extra_data/index/start/end），规避 exec 沙箱 8 项历史缺陷。
    # 其余 9 个反转/持续形态为 R245 迁移。输出 dict 与 _convert_dict_to_pattern_result 同构。

    def _detect_hanging_man(self, data: pd.DataFrame) -> List[dict]:
        """检测上吊线形态（卖出信号）— R246: 锤头线同型检测独立输出看跌方向
        （原复用 _detect_hammer 过滤 sell，锤头线改造为仅输出 buy 后独立实现，避免 hammer 配置误带上吊线信号）"""
        results = []

        if data is None or data.empty:
            return results

        try:
            has_datetime = 'datetime' in data.columns
            for i in range(len(data)):
                k = data.iloc[i]

                body_size = abs(k['close'] - k['open'])
                upper_shadow = k['high'] - max(k['open'], k['close'])
                lower_shadow = min(k['open'], k['close']) - k['low']
                total_range = k['high'] - k['low']

                if total_range == 0:
                    continue

                body_ratio = body_size / total_range
                upper_ratio = upper_shadow / total_range
                lower_ratio = lower_shadow / total_range

                # 与锤头线同型（小实体、短上影、长下影），信号取看跌
                if (body_ratio < 0.3 and upper_shadow < body_size * 0.2
                        and lower_shadow > 2.0 * body_size and total_range > 0):
                    confidence = min(0.9, lower_ratio * 0.8 + (0.3 - body_ratio) * 0.5 + (0.1 - upper_ratio) * 0.3)
                    results.append({
                        'pattern_type': 'hanging_man',
                        'pattern_name': '上吊线',
                        'pattern_category': 'K线形态',
                        'signal_type': 'sell',
                        'confidence': confidence,
                        'index': int(i),
                        'datetime_val': str(k['datetime']) if has_datetime else None,
                        'price': float(k['close']),
                        'start_index': int(i),
                        'end_index': int(i),
                        'extra_data': {
                            'body_ratio': float(body_ratio),
                            'upper_ratio': float(upper_ratio),
                            'lower_ratio': float(lower_ratio)
                        },
                        'description': '检测到上吊线形态，潜在的反转卖出信号'
                    })
        except Exception as e:
            logger.warning(f"上吊线检测错误: {e}")

        return results

    def _detect_shooting_star(self, data: pd.DataFrame) -> List[dict]:
        """检测射击之星（卖出信号）— R246: 镜像 Track2 shooting_star（init_pattern_algorithms.py L114-155）"""
        results = []

        if data is None or data.empty:
            return results

        try:
            has_datetime = 'datetime' in data.columns
            for i in range(len(data)):
                k = data.iloc[i]

                body_size = abs(k['close'] - k['open'])
                upper_shadow = k['high'] - max(k['open'], k['close'])
                lower_shadow = min(k['open'], k['close']) - k['low']
                total_range = k['high'] - k['low']

                if total_range == 0:
                    continue

                body_ratio = body_size / total_range
                upper_ratio = upper_shadow / total_range
                lower_ratio = lower_shadow / total_range

                # 流星线特征：小实体，长上影线，几乎没有下影线
                if (body_ratio < 0.3 and upper_ratio > 0.6 and lower_ratio < 0.1):
                    confidence = min(0.9, upper_ratio * 0.8 + (0.3 - body_ratio) * 0.5 + (0.1 - lower_ratio) * 0.3)
                    results.append({
                        'pattern_type': 'shooting_star',
                        'pattern_name': '射击之星',
                        'pattern_category': 'K线形态',
                        'signal_type': 'sell',
                        'confidence': confidence,
                        'index': int(i),
                        'datetime_val': str(k['datetime']) if has_datetime else None,
                        'price': float(k['close']),
                        'start_index': int(i),
                        'end_index': int(i),
                        'extra_data': {
                            'body_ratio': float(body_ratio),
                            'upper_ratio': float(upper_ratio),
                            'lower_ratio': float(lower_ratio)
                        },
                        'description': '检测到射击之星形态，潜在的反转卖出信号'
                    })
        except Exception as e:
            logger.warning(f"射击之星检测错误: {e}")

        return results

    def _detect_inverted_hammer(self, data: pd.DataFrame) -> List[dict]:
        """检测倒锤头线（买入信号）— R246: 镜像 Track2 inverted_hammer（init_pattern_algorithms.py L157-202），
        含前 5 根收盘价下跌趋势前提"""
        results = []

        if data is None or data.empty:
            return results

        try:
            has_datetime = 'datetime' in data.columns
            for i in range(len(data)):
                k = data.iloc[i]

                body_size = abs(k['close'] - k['open'])
                upper_shadow = k['high'] - max(k['open'], k['close'])
                lower_shadow = min(k['open'], k['close']) - k['low']
                total_range = k['high'] - k['low']

                if total_range == 0:
                    continue

                body_ratio = body_size / total_range
                upper_ratio = upper_shadow / total_range
                lower_ratio = lower_shadow / total_range

                # 倒锤头特征：小实体，长上影线，几乎没有下影线，且在下跌趋势中（前 5 根收盘走低）
                if (body_ratio < 0.3 and upper_ratio > 0.6 and lower_ratio < 0.1):
                    if i >= 5:
                        recent_closes = [float(data.iloc[j]['close']) for j in range(max(0, i - 5), i)]
                        if len(recent_closes) >= 2 and recent_closes[-1] < recent_closes[0]:
                            confidence = min(0.9, upper_ratio * 0.8 + (0.3 - body_ratio) * 0.5)
                            results.append({
                                'pattern_type': 'inverted_hammer',
                                'pattern_name': '倒锤头线',
                                'pattern_category': 'K线形态',
                                'signal_type': 'buy',
                                'confidence': confidence,
                                'index': int(i),
                                'datetime_val': str(k['datetime']) if has_datetime else None,
                                'price': float(k['close']),
                                'start_index': int(i),
                                'end_index': int(i),
                                'extra_data': {
                                    'body_ratio': float(body_ratio),
                                    'upper_ratio': float(upper_ratio),
                                    'lower_ratio': float(lower_ratio)
                                },
                                'description': '检测到倒锤头线形态，潜在的反转买入信号'
                            })
        except Exception as e:
            logger.warning(f"倒锤头线检测错误: {e}")

        return results

    def _detect_marubozu(self, data: pd.DataFrame) -> List[dict]:
        """检测光头光脚线 — R246: 镜像 Track2 marubozu（init_pattern_algorithms.py L204-248）；
        按阳/阴线输出 white_marubozu/black_marubozu 与 buy/sell 信号"""
        results = []

        if data is None or data.empty:
            return results

        try:
            has_datetime = 'datetime' in data.columns
            for i in range(len(data)):
                k = data.iloc[i]

                body_size = abs(k['close'] - k['open'])
                upper_shadow = k['high'] - max(k['open'], k['close'])
                lower_shadow = min(k['open'], k['close']) - k['low']
                total_range = k['high'] - k['low']

                if total_range == 0:
                    continue

                body_ratio = body_size / total_range
                upper_ratio = upper_shadow / total_range
                lower_ratio = lower_shadow / total_range

                # 光头光脚线特征：实体占比很大，上下影线很短
                if (body_ratio > 0.9 and upper_ratio < 0.05 and lower_ratio < 0.05):
                    is_bullish = k['close'] > k['open']
                    signal_type = 'buy' if is_bullish else 'sell'
                    confidence = min(0.9, body_ratio * 0.9 + (0.05 - max(upper_ratio, lower_ratio)) * 2)
                    results.append({
                        'pattern_type': 'white_marubozu' if is_bullish else 'black_marubozu',
                        'pattern_name': '光头光脚',
                        'pattern_category': 'K线形态',
                        'signal_type': signal_type,
                        'confidence': confidence,
                        'index': int(i),
                        'datetime_val': str(k['datetime']) if has_datetime else None,
                        'price': float(k['close']),
                        'start_index': int(i),
                        'end_index': int(i),
                        'extra_data': {
                            'body_ratio': float(body_ratio),
                            'upper_ratio': float(upper_ratio),
                            'lower_ratio': float(lower_ratio),
                            'is_bullish': is_bullish
                        },
                        'description': '检测到光头光脚线形态'
                    })
        except Exception as e:
            logger.warning(f"光头光脚线检测错误: {e}")

        return results

    def _detect_spinning_top(self, data: pd.DataFrame) -> List[dict]:
        """检测纺锤线（中性信号）— R246: 镜像 Track2 spinning_top（init_pattern_algorithms.py L250-291）"""
        results = []

        if data is None or data.empty:
            return results

        try:
            has_datetime = 'datetime' in data.columns
            for i in range(len(data)):
                k = data.iloc[i]

                body_size = abs(k['close'] - k['open'])
                upper_shadow = k['high'] - max(k['open'], k['close'])
                lower_shadow = min(k['open'], k['close']) - k['low']
                total_range = k['high'] - k['low']

                if total_range == 0:
                    continue

                body_ratio = body_size / total_range
                upper_ratio = upper_shadow / total_range
                lower_ratio = lower_shadow / total_range

                # 纺锤线特征：小实体，上下影线都较长
                if (body_ratio < 0.3 and upper_ratio > 0.2 and lower_ratio > 0.2):
                    confidence = min(0.8, (0.3 - body_ratio) * 1.5 + min(upper_ratio, lower_ratio) * 0.5)
                    results.append({
                        'pattern_type': 'spinning_top',
                        'pattern_name': '纺锤线',
                        'pattern_category': 'K线形态',
                        'signal_type': 'neutral',
                        'confidence': confidence,
                        'index': int(i),
                        'datetime_val': str(k['datetime']) if has_datetime else None,
                        'price': float((k['open'] + k['close']) / 2),
                        'start_index': int(i),
                        'end_index': int(i),
                        'extra_data': {
                            'body_ratio': float(body_ratio),
                            'upper_ratio': float(upper_ratio),
                            'lower_ratio': float(lower_ratio)
                        },
                        'description': '检测到纺锤线形态，市场犹豫信号'
                    })
        except Exception as e:
            logger.warning(f"纺锤线检测错误: {e}")

        return results

    def _detect_bullish_engulfing(self, data: pd.DataFrame) -> List[dict]:
        """检测看涨吞没 — R246: 镜像 Track2 bullish_engulfing（init_pattern_algorithms.py L294-330）"""
        results = []

        if data is None or len(data) < 2:
            return results

        try:
            has_datetime = 'datetime' in data.columns
            for i in range(1, len(data)):
                k1 = data.iloc[i - 1]  # 前一根
                k2 = data.iloc[i]      # 当前根

                # 第一根是阴线，第二根是阳线，且第二根完全吞没第一根
                if k1['close'] < k1['open'] and k2['close'] > k2['open']:
                    if k2['open'] < k1['close'] and k2['close'] > k1['open']:
                        engulf_ratio = (k2['close'] - k2['open']) / (k1['open'] - k1['close'])
                        confidence = min(0.9, 0.6 + engulf_ratio * 0.3)
                        results.append({
                            'pattern_type': 'bullish_engulfing',
                            'pattern_name': '看涨吞没',
                            'pattern_category': 'K线形态',
                            'signal_type': 'buy',
                            'confidence': confidence,
                            'index': int(i),
                            'datetime_val': str(k2['datetime']) if has_datetime else None,
                            'price': float(k2['close']),
                            'start_index': int(i - 1),
                            'end_index': int(i),
                            'extra_data': {
                                'engulf_ratio': float(engulf_ratio),
                                'prev_candle': {'open': float(k1['open']), 'close': float(k1['close'])},
                                'curr_candle': {'open': float(k2['open']), 'close': float(k2['close'])}
                            },
                            'description': '检测到看涨吞没形态，潜在的反转买入信号'
                        })
        except Exception as e:
            logger.warning(f"看涨吞没检测错误: {e}")

        return results

    def _detect_bearish_engulfing(self, data: pd.DataFrame) -> List[dict]:
        """检测看跌吞没 — R246: 镜像 Track2 bearish_engulfing（init_pattern_algorithms.py L332-368）"""
        results = []

        if data is None or len(data) < 2:
            return results

        try:
            has_datetime = 'datetime' in data.columns
            for i in range(1, len(data)):
                k1 = data.iloc[i - 1]  # 前一根
                k2 = data.iloc[i]      # 当前根

                # 第一根是阳线，第二根是阴线，且第二根完全吞没第一根
                if k1['close'] > k1['open'] and k2['close'] < k2['open']:
                    if k2['open'] > k1['close'] and k2['close'] < k1['open']:
                        engulf_ratio = (k2['open'] - k2['close']) / (k1['close'] - k1['open'])
                        confidence = min(0.9, 0.6 + engulf_ratio * 0.3)
                        results.append({
                            'pattern_type': 'bearish_engulfing',
                            'pattern_name': '看跌吞没',
                            'pattern_category': 'K线形态',
                            'signal_type': 'sell',
                            'confidence': confidence,
                            'index': int(i),
                            'datetime_val': str(k2['datetime']) if has_datetime else None,
                            'price': float(k2['close']),
                            'start_index': int(i - 1),
                            'end_index': int(i),
                            'extra_data': {
                                'engulf_ratio': float(engulf_ratio),
                                'prev_candle': {'open': float(k1['open']), 'close': float(k1['close'])},
                                'curr_candle': {'open': float(k2['open']), 'close': float(k2['close'])}
                            },
                            'description': '检测到看跌吞没形态，潜在的反转卖出信号'
                        })
        except Exception as e:
            logger.warning(f"看跌吞没检测错误: {e}")

        return results

    def _detect_piercing_pattern(self, data: pd.DataFrame) -> List[dict]:
        """检测刺透形态 — R246: 镜像 Track2 piercing_pattern（init_pattern_algorithms.py L370-407）"""
        results = []

        if data is None or len(data) < 2:
            return results

        try:
            has_datetime = 'datetime' in data.columns
            for i in range(1, len(data)):
                k1 = data.iloc[i - 1]  # 前一根
                k2 = data.iloc[i]      # 当前根

                # 第一根是阴线，第二根是阳线，且收盘价刺透第一根实体的一半以上
                if k1['close'] < k1['open'] and k2['close'] > k2['open']:
                    k1_mid = (k1['open'] + k1['close']) / 2
                    if k2['open'] < k1['close'] and k2['close'] > k1_mid:
                        pierce_ratio = (k2['close'] - k1['close']) / (k1['open'] - k1['close'])
                        confidence = min(0.8, 0.5 + pierce_ratio * 0.3)
                        results.append({
                            'pattern_type': 'piercing_pattern',
                            'pattern_name': '刺透形态',
                            'pattern_category': 'K线形态',
                            'signal_type': 'buy',
                            'confidence': confidence,
                            'index': int(i),
                            'datetime_val': str(k2['datetime']) if has_datetime else None,
                            'price': float(k2['close']),
                            'start_index': int(i - 1),
                            'end_index': int(i),
                            'extra_data': {
                                'pierce_ratio': float(pierce_ratio),
                                'prev_candle': {'open': float(k1['open']), 'close': float(k1['close'])},
                                'curr_candle': {'open': float(k2['open']), 'close': float(k2['close'])}
                            },
                            'description': '检测到刺透形态，潜在的反转买入信号'
                        })
        except Exception as e:
            logger.warning(f"刺透形态检测错误: {e}")

        return results

    def _detect_dark_cloud_cover(self, data: pd.DataFrame) -> List[dict]:
        """检测乌云盖顶 — R246: 镜像 Track2 dark_cloud_cover（init_pattern_algorithms.py L409-446）"""
        results = []

        if data is None or len(data) < 2:
            return results

        try:
            has_datetime = 'datetime' in data.columns
            for i in range(1, len(data)):
                k1 = data.iloc[i - 1]  # 前一根
                k2 = data.iloc[i]      # 当前根

                # 第一根是阳线，第二根是阴线，且收盘价覆盖第一根实体的一半以上
                if k1['close'] > k1['open'] and k2['close'] < k2['open']:
                    k1_mid = (k1['open'] + k1['close']) / 2
                    if k2['open'] > k1['close'] and k2['close'] < k1_mid:
                        cover_ratio = (k1['close'] - k2['close']) / (k1['close'] - k1['open'])
                        confidence = min(0.8, 0.5 + cover_ratio * 0.3)
                        results.append({
                            'pattern_type': 'dark_cloud_cover',
                            'pattern_name': '乌云盖顶',
                            'pattern_category': 'K线形态',
                            'signal_type': 'sell',
                            'confidence': confidence,
                            'index': int(i),
                            'datetime_val': str(k2['datetime']) if has_datetime else None,
                            'price': float(k2['close']),
                            'start_index': int(i - 1),
                            'end_index': int(i),
                            'extra_data': {
                                'cover_ratio': float(cover_ratio),
                                'prev_candle': {'open': float(k1['open']), 'close': float(k1['close'])},
                                'curr_candle': {'open': float(k2['open']), 'close': float(k2['close'])}
                            },
                            'description': '检测到乌云盖顶形态，潜在的反转卖出信号'
                        })
        except Exception as e:
            logger.warning(f"乌云盖顶检测错误: {e}")

        return results

    def _detect_three_white_soldiers(self, data: pd.DataFrame) -> List[dict]:
        """检测三白兵 — R246: 镜像 Track2 three_white_soldiers（init_pattern_algorithms.py L449-540）"""
        results = []

        if data is None or len(data) < 3:
            return results

        try:
            has_datetime = 'datetime' in data.columns
            for i in range(2, len(data)):
                k0 = data.iloc[i - 2]  # 前日
                k1 = data.iloc[i - 1]  # 昨日
                k2 = data.iloc[i]      # 今日

                # 三根都是阳线
                is_bullish_0 = k0['close'] > k0['open']
                is_bullish_1 = k1['close'] > k1['open']
                is_bullish_2 = k2['close'] > k2['open']

                if not (is_bullish_0 and is_bullish_1 and is_bullish_2):
                    continue

                # 收盘价逐步上升
                close_ascending = k1['close'] > k0['close'] and k2['close'] > k1['close']
                if not close_ascending:
                    continue

                # 开盘价逐步上升
                open_ascending = k1['open'] > k0['open'] and k2['open'] > k1['open']
                if not open_ascending:
                    continue

                # 实体相对较大
                body_0 = abs(k0['close'] - k0['open'])
                body_1 = abs(k1['close'] - k1['open'])
                body_2 = abs(k2['close'] - k2['open'])

                range_0 = k0['high'] - k0['low']
                range_1 = k1['high'] - k1['low']
                range_2 = k2['high'] - k2['low']

                body_ratio_0 = body_0 / range_0 if range_0 > 0 else 0
                body_ratio_1 = body_1 / range_1 if range_1 > 0 else 0
                body_ratio_2 = body_2 / range_2 if range_2 > 0 else 0

                min_body_ratio = 0.3
                if not (body_ratio_0 > min_body_ratio and body_ratio_1 > min_body_ratio and body_ratio_2 > min_body_ratio):
                    continue

                # 上影线相对较短
                upper_shadow_0 = k0['high'] - k0['close']
                upper_shadow_1 = k1['high'] - k1['close']
                upper_shadow_2 = k2['high'] - k2['close']

                upper_ratio_0 = upper_shadow_0 / range_0 if range_0 > 0 else 0
                upper_ratio_1 = upper_shadow_1 / range_1 if range_1 > 0 else 0
                upper_ratio_2 = upper_shadow_2 / range_2 if range_2 > 0 else 0

                max_upper_ratio = 0.4
                if not (upper_ratio_0 < max_upper_ratio and upper_ratio_1 < max_upper_ratio and upper_ratio_2 < max_upper_ratio):
                    continue

                # 计算置信度
                base_confidence = 0.6
                avg_body_ratio = (body_ratio_0 + body_ratio_1 + body_ratio_2) / 3
                body_score = min(0.2, (avg_body_ratio - 0.3) * 0.5)
                avg_upper_ratio = (upper_ratio_0 + upper_ratio_1 + upper_ratio_2) / 3
                upper_score = min(0.1, (0.4 - avg_upper_ratio) * 0.25)
                total_gain = (k2['close'] - k0['open']) / k0['open']
                gain_score = min(0.1, total_gain * 2)

                confidence = base_confidence + body_score + upper_score + gain_score
                confidence = min(0.95, max(0.5, confidence))

                results.append({
                    'pattern_type': 'three_white_soldiers',
                    'pattern_name': '三白兵',
                    'pattern_category': 'K线形态',
                    'signal_type': 'buy',
                    'confidence': confidence,
                    'index': int(i),
                    'datetime_val': str(k2['datetime']) if has_datetime else None,
                    'price': float(k2['close']),
                    'start_index': int(i - 2),
                    'end_index': int(i),
                    'extra_data': {
                        'start_price': float(k0['open']),
                        'end_price': float(k2['close']),
                        'total_gain': float(total_gain * 100),
                        'body_ratios': [float(body_ratio_0), float(body_ratio_1), float(body_ratio_2)],
                        'upper_ratios': [float(upper_ratio_0), float(upper_ratio_1), float(upper_ratio_2)]
                    },
                    'description': '检测到三白兵形态，潜在的看涨持续信号'
                })
        except Exception as e:
            logger.warning(f"三白兵检测错误: {e}")

        return results

    def _detect_three_black_crows(self, data: pd.DataFrame) -> List[dict]:
        """检测三黑鸦 — R246: 镜像 Track2 three_black_crows（init_pattern_algorithms.py L542-680），
        含 range/下影线校验与结果上限保护"""
        results = []

        if data is None or len(data) < 3:
            return results

        try:
            has_datetime = 'datetime' in data.columns
            for i in range(2, len(data)):
                k0 = data.iloc[i - 2]  # 前日
                k1 = data.iloc[i - 1]  # 昨日
                k2 = data.iloc[i]      # 今日

                # 三根都是阴线
                is_bearish_0 = k0['close'] < k0['open']
                is_bearish_1 = k1['close'] < k1['open']
                is_bearish_2 = k2['close'] < k2['open']

                if not (is_bearish_0 and is_bearish_1 and is_bearish_2):
                    continue

                # 收盘价逐步下降
                close_descending = k1['close'] < k0['close'] and k2['close'] < k1['close']
                if not close_descending:
                    continue

                # 开盘价逐步下降
                open_descending = k1['open'] < k0['open'] and k2['open'] < k1['open']
                if not open_descending:
                    continue

                # 实体相对较大
                body_0 = abs(k0['close'] - k0['open'])
                body_1 = abs(k1['close'] - k1['open'])
                body_2 = abs(k2['close'] - k2['open'])

                range_0 = k0['high'] - k0['low']
                range_1 = k1['high'] - k1['low']
                range_2 = k2['high'] - k2['low']

                # 防止除零错误
                if range_0 <= 0 or range_1 <= 0 or range_2 <= 0:
                    continue

                body_ratio_0 = body_0 / range_0
                body_ratio_1 = body_1 / range_1
                body_ratio_2 = body_2 / range_2

                min_body_ratio = 0.3
                if not (body_ratio_0 > min_body_ratio and body_ratio_1 > min_body_ratio and body_ratio_2 > min_body_ratio):
                    continue

                # 下影线相对较短
                lower_shadow_0 = k0['close'] - k0['low']
                lower_shadow_1 = k1['close'] - k1['low']
                lower_shadow_2 = k2['close'] - k2['low']

                lower_ratio_0 = lower_shadow_0 / range_0
                lower_ratio_1 = lower_shadow_1 / range_1
                lower_ratio_2 = lower_shadow_2 / range_2

                max_lower_ratio = 0.4
                if not (lower_ratio_0 < max_lower_ratio and lower_ratio_1 < max_lower_ratio and lower_ratio_2 < max_lower_ratio):
                    continue

                # 计算置信度
                base_confidence = 0.6
                avg_body_ratio = (body_ratio_0 + body_ratio_1 + body_ratio_2) / 3
                body_score = min(0.2, (avg_body_ratio - 0.3) * 0.5)
                avg_lower_ratio = (lower_ratio_0 + lower_ratio_1 + lower_ratio_2) / 3
                lower_score = min(0.1, (0.4 - avg_lower_ratio) * 0.25)

                # 防止除零错误
                if k0['open'] <= 0:
                    continue

                total_loss = (k0['open'] - k2['close']) / k0['open']
                loss_score = min(0.1, total_loss * 2)

                confidence = base_confidence + body_score + lower_score + loss_score
                confidence = min(0.95, max(0.5, confidence))

                results.append({
                    'pattern_type': 'three_black_crows',
                    'pattern_name': '三黑鸦',
                    'pattern_category': 'K线形态',
                    'signal_type': 'sell',
                    'confidence': confidence,
                    'index': int(i),
                    'datetime_val': str(k2['datetime']) if has_datetime else None,
                    'price': float(k2['close']),
                    'start_index': int(i - 2),
                    'end_index': int(i),
                    'extra_data': {
                        'start_price': float(k0['open']),
                        'end_price': float(k2['close']),
                        'total_loss': float(total_loss * 100),
                        'body_ratios': [float(body_ratio_0), float(body_ratio_1), float(body_ratio_2)],
                        'lower_ratios': [float(lower_ratio_0), float(lower_ratio_1), float(lower_ratio_2)]
                    },
                    'description': '检测到三黑鸦形态，潜在的看跌持续信号'
                })

                # 限制结果数量，防止内存问题（与 Track2 一致）
                if len(results) > 1000:
                    break
        except Exception as e:
            logger.warning(f"三黑鸦检测错误: {e}")

        return results

    def _detect_morning_star(self, data: pd.DataFrame) -> List[dict]:
        """检测早晨之星 — R246: 镜像 Track2 morning_star（init_pattern_algorithms.py L682-747）"""
        results = []

        if data is None or len(data) < 3:
            return results

        try:
            has_datetime = 'datetime' in data.columns
            for i in range(2, len(data)):
                k0 = data.iloc[i - 2]  # 第一根
                k1 = data.iloc[i - 1]  # 第二根（星线）
                k2 = data.iloc[i]      # 第三根

                # 第一根是阴线，第三根是阳线
                if not (k0['close'] < k0['open'] and k2['close'] > k2['open']):
                    continue

                # 第二根是小实体（星线）
                star_body = abs(k1['close'] - k1['open'])
                star_range = k1['high'] - k1['low']
                star_body_ratio = star_body / star_range if star_range > 0 else 0

                if star_body_ratio > 0.3:  # 星线实体应该较小
                    continue

                # 检查跳空
                gap1 = k1['high'] < k0['close']  # 第一个跳空
                gap2 = k1['high'] < k2['open']   # 第二个跳空

                if not (gap1 or gap2):  # 至少有一个跳空
                    continue

                # 第三根阳线应该深入第一根阴线实体
                penetration = (k2['close'] - k0['close']) / (k0['open'] - k0['close'])
                if penetration < 0.5:
                    continue

                # 计算置信度
                base_confidence = 0.7
                gap_score = 0.1 if (gap1 and gap2) else 0.05
                star_score = (0.3 - star_body_ratio) * 0.3
                penetration_score = min(0.15, penetration * 0.15)

                confidence = base_confidence + gap_score + star_score + penetration_score
                confidence = min(0.95, confidence)

                results.append({
                    'pattern_type': 'morning_star',
                    'pattern_name': '早晨之星',
                    'pattern_category': 'K线形态',
                    'signal_type': 'buy',
                    'confidence': confidence,
                    'index': int(i),
                    'datetime_val': str(k2['datetime']) if has_datetime else None,
                    'price': float(k2['close']),
                    'start_index': int(i - 2),
                    'end_index': int(i),
                    'extra_data': {
                        'star_body_ratio': float(star_body_ratio),
                        'penetration': float(penetration),
                        'has_gaps': gap1 and gap2,
                        'first_candle': {'open': float(k0['open']), 'close': float(k0['close'])},
                        'star_candle': {'open': float(k1['open']), 'close': float(k1['close'])},
                        'third_candle': {'open': float(k2['open']), 'close': float(k2['close'])}
                    },
                    'description': '检测到早晨之星形态，潜在的反转买入信号'
                })
        except Exception as e:
            logger.warning(f"早晨之星检测错误: {e}")

        return results

    def _detect_evening_star(self, data: pd.DataFrame) -> List[dict]:
        """检测黄昏之星 — R246: 镜像 Track2 evening_star（init_pattern_algorithms.py L749-814）"""
        results = []

        if data is None or len(data) < 3:
            return results

        try:
            has_datetime = 'datetime' in data.columns
            for i in range(2, len(data)):
                k0 = data.iloc[i - 2]  # 第一根
                k1 = data.iloc[i - 1]  # 第二根（星线）
                k2 = data.iloc[i]      # 第三根

                # 第一根是阳线，第三根是阴线
                if not (k0['close'] > k0['open'] and k2['close'] < k2['open']):
                    continue

                # 第二根是小实体（星线）
                star_body = abs(k1['close'] - k1['open'])
                star_range = k1['high'] - k1['low']
                star_body_ratio = star_body / star_range if star_range > 0 else 0

                if star_body_ratio > 0.3:  # 星线实体应该较小
                    continue

                # 检查跳空
                gap1 = k1['low'] > k0['close']  # 第一个跳空
                gap2 = k1['low'] > k2['open']   # 第二个跳空

                if not (gap1 or gap2):  # 至少有一个跳空
                    continue

                # 第三根阴线应该深入第一根阳线实体
                penetration = (k0['close'] - k2['close']) / (k0['close'] - k0['open'])
                if penetration < 0.5:
                    continue

                # 计算置信度
                base_confidence = 0.7
                gap_score = 0.1 if (gap1 and gap2) else 0.05
                star_score = (0.3 - star_body_ratio) * 0.3
                penetration_score = min(0.15, penetration * 0.15)

                confidence = base_confidence + gap_score + star_score + penetration_score
                confidence = min(0.95, confidence)

                results.append({
                    'pattern_type': 'evening_star',
                    'pattern_name': '黄昏之星',
                    'pattern_category': 'K线形态',
                    'signal_type': 'sell',
                    'confidence': confidence,
                    'index': int(i),
                    'datetime_val': str(k2['datetime']) if has_datetime else None,
                    'price': float(k2['close']),
                    'start_index': int(i - 2),
                    'end_index': int(i),
                    'extra_data': {
                        'star_body_ratio': float(star_body_ratio),
                        'penetration': float(penetration),
                        'has_gaps': gap1 and gap2,
                        'first_candle': {'open': float(k0['open']), 'close': float(k0['close'])},
                        'star_candle': {'open': float(k1['open']), 'close': float(k1['close'])},
                        'third_candle': {'open': float(k2['open']), 'close': float(k2['close'])}
                    },
                    'description': '检测到黄昏之星形态，潜在的反转卖出信号'
                })
        except Exception as e:
            logger.warning(f"黄昏之星检测错误: {e}")

        return results

    def _detect_double_top(self, data: pd.DataFrame) -> List[dict]:
        """检测双重顶形态 - 两个相近高点 + 颈线跌破（标准看跌反转）"""
        results = []
        if len(data) < 15:
            return results
        try:
            highs = data['high'].values.astype(np.float64)
            lows = data['low'].values.astype(np.float64)
            closes = data['close'].values.astype(np.float64)

            peaks, _ = find_local_extremes(highs, window=3)
            avg_price = float(np.mean(closes))
            tolerance = avg_price * 0.03

            for i in range(len(peaks) - 1):
                p1 = peaks[i]
                for j in range(i + 1, len(peaks)):
                    p2 = peaks[j]
                    if p2 - p1 < 5:
                        continue
                    if abs(highs[p1] - highs[p2]) > tolerance:
                        continue
                    neckline = float(np.min(lows[p1:p2 + 1]))
                    if neckline >= min(highs[p1], highs[p2]):
                        continue
                    for idx in range(p2 + 1, len(closes)):
                        if closes[idx] < neckline * 0.99:
                            results.append({
                                'pattern_type': 'chart_pattern',
                                'pattern_name': '双重顶',
                                'pattern_category': '反转形态',
                                'signal_type': 'sell',
                                'confidence': 0.75,
                                'index': int(idx),
                                'datetime_val': None,
                                'price': float(closes[idx]),
                                'start_index': int(p1),
                                'end_index': int(idx),
                                'description': '检测到双重顶形态，潜在的反转卖出信号'
                            })
                            break
                    break
        except Exception as e:
            logger.warning(f"双重顶检测错误: {e}")
        return results

    def _detect_double_bottom(self, data: pd.DataFrame) -> List[dict]:
        """检测双重底形态 - 两个相近低点 + 颈线突破（标准看涨反转，镜像 double_top）"""
        results = []
        if len(data) < 15:
            return results
        try:
            highs = data['high'].values.astype(np.float64)
            lows = data['low'].values.astype(np.float64)
            closes = data['close'].values.astype(np.float64)

            _, troughs = find_local_extremes(lows, window=3)
            avg_price = float(np.mean(closes))
            tolerance = avg_price * 0.03

            for i in range(len(troughs) - 1):
                t1 = troughs[i]
                for j in range(i + 1, len(troughs)):
                    t2 = troughs[j]
                    if t2 - t1 < 5:
                        continue
                    if abs(lows[t1] - lows[t2]) > tolerance:
                        continue
                    neckline = float(np.max(highs[t1:t2 + 1]))
                    if neckline <= max(lows[t1], lows[t2]):
                        continue
                    for idx in range(t2 + 1, len(closes)):
                        if closes[idx] > neckline * 1.01:
                            results.append({
                                'pattern_type': 'chart_pattern',
                                'pattern_name': '双重底',
                                'pattern_category': '反转形态',
                                'signal_type': 'buy',
                                'confidence': 0.75,
                                'index': int(idx),
                                'datetime_val': None,
                                'price': float(closes[idx]),
                                'start_index': int(t1),
                                'end_index': int(idx),
                                'description': '检测到双重底形态，潜在的反转买入信号'
                            })
                            break
                    break
        except Exception as e:
            logger.warning(f"双重底检测错误: {e}")
        return results

    def _detect_head_shoulders_top(self, data: pd.DataFrame) -> List[dict]:
        """检测头肩顶形态 - 左肩/头部/右肩 + 颈线跌破（最可靠看跌反转）"""
        results = []
        if len(data) < 20:
            return results
        try:
            highs = data['high'].values.astype(np.float64)
            lows = data['low'].values.astype(np.float64)
            closes = data['close'].values.astype(np.float64)

            peaks, _ = find_local_extremes(highs, window=3)
            peaks = _merge_adjacent_extremes(peaks, highs, min_gap=4, is_peak=True)
            avg_price = float(np.mean(closes))
            tolerance = avg_price * 0.05

            for i in range(len(peaks) - 2):
                l, h, r = peaks[i], peaks[i + 1], peaks[i + 2]
                if not (l < h < r) or (h - l) < 4 or (r - h) < 4:
                    continue
                head_h, left_h, right_h = highs[h], highs[l], highs[r]
                if not (head_h > left_h and head_h > right_h):
                    continue
                if abs(left_h - right_h) > tolerance:
                    continue
                if (head_h - max(left_h, right_h)) < avg_price * 0.03:
                    continue
                neckline = float(min(np.min(lows[l:h + 1]), np.min(lows[h:r + 1])))
                if neckline >= head_h:
                    continue
                for idx in range(r + 1, len(closes)):
                    if closes[idx] < neckline * 0.99:
                        results.append({
                            'pattern_type': 'chart_pattern',
                            'pattern_name': '头肩顶',
                            'pattern_category': '反转形态',
                            'signal_type': 'sell',
                            'confidence': 0.8,
                            'index': int(idx),
                            'datetime_val': None,
                            'price': float(closes[idx]),
                            'start_index': int(l),
                            'end_index': int(idx),
                            'description': '检测到头肩顶形态，强烈的反转卖出信号'
                        })
                        break
                break
        except Exception as e:
            logger.warning(f"头肩顶检测错误: {e}")
        return results

    def _detect_head_shoulders_bottom(self, data: pd.DataFrame) -> List[dict]:
        """检测头肩底形态 - 左肩/头部/右肩 + 颈线突破（最可靠看涨反转，镜像 head_shoulders_top）"""
        results = []
        if len(data) < 20:
            return results
        try:
            highs = data['high'].values.astype(np.float64)
            lows = data['low'].values.astype(np.float64)
            closes = data['close'].values.astype(np.float64)

            _, troughs = find_local_extremes(lows, window=3)
            troughs = _merge_adjacent_extremes(troughs, lows, min_gap=4, is_peak=False)
            avg_price = float(np.mean(closes))
            tolerance = avg_price * 0.05

            for i in range(len(troughs) - 2):
                l, h, r = troughs[i], troughs[i + 1], troughs[i + 2]
                if not (l < h < r) or (h - l) < 4 or (r - h) < 4:
                    continue
                head_l, left_l, right_l = lows[h], lows[l], lows[r]
                if not (head_l < left_l and head_l < right_l):
                    continue
                if abs(left_l - right_l) > tolerance:
                    continue
                if (min(left_l, right_l) - head_l) < avg_price * 0.03:
                    continue
                neckline = float(max(np.max(highs[l:h + 1]), np.max(highs[h:r + 1])))
                if neckline <= head_l:
                    continue
                for idx in range(r + 1, len(closes)):
                    if closes[idx] > neckline * 1.01:
                        results.append({
                            'pattern_type': 'chart_pattern',
                            'pattern_name': '头肩底',
                            'pattern_category': '反转形态',
                            'signal_type': 'buy',
                            'confidence': 0.8,
                            'index': int(idx),
                            'datetime_val': None,
                            'price': float(closes[idx]),
                            'start_index': int(l),
                            'end_index': int(idx),
                            'description': '检测到头肩底形态，强烈的反转买入信号'
                        })
                        break
                break
        except Exception as e:
            logger.warning(f"头肩底检测错误: {e}")
        return results

    def _detect_triple_top(self, data: pd.DataFrame) -> List[dict]:
        """检测三重顶形态 - 三个相近高点 + 颈线跌破"""
        results = []
        if len(data) < 25:
            return results
        try:
            highs = data['high'].values.astype(np.float64)
            lows = data['low'].values.astype(np.float64)
            closes = data['close'].values.astype(np.float64)

            peaks, _ = find_local_extremes(highs, window=3)
            peaks = _merge_adjacent_extremes(peaks, highs, min_gap=4, is_peak=True)
            avg_price = float(np.mean(closes))
            tolerance = avg_price * 0.04

            for i in range(len(peaks) - 2):
                p1, p2, p3 = peaks[i], peaks[i + 1], peaks[i + 2]
                if not (p1 < p2 < p3) or (p2 - p1) < 4 or (p3 - p2) < 4:
                    continue
                if abs(highs[p1] - highs[p2]) > tolerance:
                    continue
                if abs(highs[p2] - highs[p3]) > tolerance:
                    continue
                neckline = float(min(np.min(lows[p1:p2 + 1]), np.min(lows[p2:p3 + 1])))
                if neckline >= min(highs[p1], highs[p3]):
                    continue
                for idx in range(p3 + 1, len(closes)):
                    if closes[idx] < neckline * 0.99:
                        results.append({
                            'pattern_type': 'chart_pattern',
                            'pattern_name': '三重顶',
                            'pattern_category': '反转形态',
                            'signal_type': 'sell',
                            'confidence': 0.7,
                            'index': int(idx),
                            'datetime_val': None,
                            'price': float(closes[idx]),
                            'start_index': int(p1),
                            'end_index': int(idx),
                            'description': '检测到三重顶形态，强烈的看跌反转信号'
                        })
                        break
                break
        except Exception as e:
            logger.warning(f"三重顶检测错误: {e}")
        return results

    def _detect_triple_bottom(self, data: pd.DataFrame) -> List[dict]:
        """检测三重底形态 - 三个相近低点 + 颈线突破（镜像 triple_top）"""
        results = []
        if len(data) < 25:
            return results
        try:
            highs = data['high'].values.astype(np.float64)
            lows = data['low'].values.astype(np.float64)
            closes = data['close'].values.astype(np.float64)

            _, troughs = find_local_extremes(lows, window=3)
            troughs = _merge_adjacent_extremes(troughs, lows, min_gap=4, is_peak=False)
            avg_price = float(np.mean(closes))
            tolerance = avg_price * 0.04

            for i in range(len(troughs) - 2):
                t1, t2, t3 = troughs[i], troughs[i + 1], troughs[i + 2]
                if not (t1 < t2 < t3) or (t2 - t1) < 4 or (t3 - t2) < 4:
                    continue
                if abs(lows[t1] - lows[t2]) > tolerance:
                    continue
                if abs(lows[t2] - lows[t3]) > tolerance:
                    continue
                neckline = float(max(np.max(highs[t1:t2 + 1]), np.max(highs[t2:t3 + 1])))
                if neckline <= max(lows[t1], lows[t3]):
                    continue
                for idx in range(t3 + 1, len(closes)):
                    if closes[idx] > neckline * 1.01:
                        results.append({
                            'pattern_type': 'chart_pattern',
                            'pattern_name': '三重底',
                            'pattern_category': '反转形态',
                            'signal_type': 'buy',
                            'confidence': 0.7,
                            'index': int(idx),
                            'datetime_val': None,
                            'price': float(closes[idx]),
                            'start_index': int(t1),
                            'end_index': int(idx),
                            'description': '检测到三重底形态，强烈的看涨反转信号'
                        })
                        break
                break
        except Exception as e:
            logger.warning(f"三重底检测错误: {e}")
        return results

    def _detect_ascending_triangle(self, data: pd.DataFrame) -> List[dict]:
        """检测上升三角形 - 水平上沿阻力 + 抬高低点 + 向上突破（看涨持续）"""
        results = []
        min_len = 10
        if len(data) < min_len + 1:
            return results
        try:
            highs = data['high'].values.astype(np.float64)
            lows = data['low'].values.astype(np.float64)
            closes = data['close'].values.astype(np.float64)

            # R245 修复：窗口取 [i-min_len, i)（不含当前根），否则突破点自身 high 抬高
            # resistance，导致 closes[i] > resistance*1.01 恒不成立
            for i in range(min_len, len(closes)):
                window_highs = highs[i - min_len:i]
                window_lows = lows[i - min_len:i]
                resistance = float(np.max(window_highs))
                # 上沿水平：窗口高点振幅 < 均价 5%
                if (resistance - float(np.min(window_highs))) > float(np.mean(window_highs)) * 0.05:
                    continue
                # 低点抬高：后半段最低 > 前半段最低
                if float(np.min(window_lows[min_len // 2:])) <= float(np.min(window_lows[:min_len // 2])):
                    continue
                # 确认向上突破
                if closes[i] > resistance * 1.01:
                    results.append({
                        'pattern_type': 'chart_pattern',
                        'pattern_name': '上升三角形',
                        'pattern_category': '持续形态',
                        'signal_type': 'buy',
                        'confidence': 0.7,
                        'index': int(i),
                        'datetime_val': None,
                        'price': float(closes[i]),
                        'start_index': int(i - min_len),
                        'end_index': int(i),
                        'description': '检测到上升三角形形态，价格将继续上涨'
                    })
        except Exception as e:
            logger.warning(f"上升三角形检测错误: {e}")
        return results

    def _detect_descending_triangle(self, data: pd.DataFrame) -> List[dict]:
        """检测下降三角形 - 水平下沿支撑 + 降低高点 + 向下突破（看跌持续，镜像 ascending）"""
        results = []
        min_len = 10
        if len(data) < min_len + 1:
            return results
        try:
            highs = data['high'].values.astype(np.float64)
            lows = data['low'].values.astype(np.float64)
            closes = data['close'].values.astype(np.float64)

            for i in range(min_len, len(closes)):
                window_highs = highs[i - min_len:i]
                window_lows = lows[i - min_len:i]
                support = float(np.min(window_lows))
                # 下沿水平：窗口低点振幅 < 均价 5%
                if (float(np.max(window_lows)) - support) > float(np.mean(window_highs)) * 0.05:
                    continue
                # 高点降低：后半段最高 < 前半段最高
                if float(np.max(window_highs[min_len // 2:])) >= float(np.max(window_highs[:min_len // 2])):
                    continue
                # 确认向下突破
                if closes[i] < support * 0.99:
                    results.append({
                        'pattern_type': 'chart_pattern',
                        'pattern_name': '下降三角形',
                        'pattern_category': '持续形态',
                        'signal_type': 'sell',
                        'confidence': 0.7,
                        'index': int(i),
                        'datetime_val': None,
                        'price': float(closes[i]),
                        'start_index': int(i - min_len),
                        'end_index': int(i),
                        'description': '检测到下降三角形形态，价格将继续下跌'
                    })
        except Exception as e:
            logger.warning(f"下降三角形检测错误: {e}")
        return results

    def get_supported_patterns(self) -> List[str]:
        """获取支持的形态列表（R246: 23 个内置形态英文键 + 中文显示名）"""
        return list(_DETECT_DISPATCH.keys()) + [
            "锤头线", "十字星", "上吊线", "射击之星", "倒锤头线", "光头光脚", "纺锤线",
            "看涨吞没", "看跌吞没", "刺透形态", "乌云盖顶", "三白兵", "三黑鸦",
            "早晨之星", "黄昏之星", "双重顶", "双重底", "头肩顶", "头肩底",
            "三重顶", "三重底", "上升三角形", "下降三角形",
        ]

    def get_pattern_description(self, pattern_name: str) -> str:
        """获取形态描述"""
        descriptions = {
            "锤子线": "锤子线是一种看涨反转形态，特征是实体较小，下影线较长",
            "十字星": "十字星表示市场犹豫不决，开盘价和收盘价几乎相等",
            "上吊线": "上吊线是看跌反转信号，出现在上升趋势的顶部，实体小且下影线长",
            "双重顶": "双重顶是看跌反转形态，价格形成两个相近高点后向下突破",
            "双重底": "双重底是看涨反转形态，价格形成两个相近低点后向上突破",
            "头肩顶": "头肩顶是最可靠的看跌反转形态，由左肩、头部、右肩三个高点组成",
            "头肩底": "头肩底是最可靠的看涨反转形态，由左肩、头部、右肩三个低点组成",
            "三重顶": "三重顶由三个相近的高点组成，是强烈的看跌信号",
            "三重底": "三重底由三个相近的低点组成，是强烈的看涨信号",
            "上升三角形": "上升三角形是看涨的持续形态，表示价格将继续上涨",
            "下降三角形": "下降三角形是看跌的持续形态，表示价格将继续下跌",
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

        # 懒加载信号计算器
        self._signal_calculator = None

    def recognize(self, kdata: pd.DataFrame) -> List[PatternResult]:
        """
        增强版形态识别 - 包含更多形态和置信度评估

        Args:
            kdata: K线数据

        Returns:
            形态识别结果列表
        """
        if self.debug_mode:
            logger.debug(f"开始增强版形态识别，数据量: {len(kdata)}")

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
            logger.debug(f"识别完成，发现 {len(enhanced_results)} 个形态")

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
                logger.warning(f"调整置信度失败: {e}")
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
                    logger.debug(f"[identify_patterns] 没有找到可用的形态配置")
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
                            logger.debug(f"[identify_patterns] 无法通过工厂创建识别器，使用基础识别器: {e}")
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
                        logger.debug(f"[identify_patterns] 识别形态 {config.name} 时出错: {e}")
                    continue
            
            # 按置信度排序
            all_results.sort(key=lambda x: x.confidence if hasattr(x, 'confidence') else 0, reverse=True)
            
            # 信号去重：同一位置只保留最高置信度的信号
            all_results = self._deduplicate_signals(all_results)
            
            if self.debug_mode:
                logger.debug(f"[identify_patterns] 识别完成，发现 {len(all_results)} 个形态（去重后）")
            
            return all_results
            
        except Exception as e:
            if self.debug_mode:
                logger.warning(f"[identify_patterns] 形态识别失败: {e}")
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
                logger.debug(f"[去重] 跳过 {skipped_name} 在位置 {idx}，距离上次信号不足 {min_gap} 根K线")
        
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
