from loguru import logger
"""
形态算法初始化脚本
将所有形态的算法代码存储到数据库中
"""

import sqlite3
import os
from typing import Dict, Any
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'factorweave_system.sqlite')

def init_pattern_algorithms():
    """初始化形态算法到数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 注：pattern_types 建表（unified_indicator_service / complete_database_init）均已含
    # algorithm_code/parameters 列，无需 ALTER TABLE

    # 定义所有形态的算法代码
    algorithms = {
        # 单根K线形态
        'hammer': {
            'code': '''
# 锤头线识别算法
max_process_length = min(len(kdata), 1000)
for i in range(max_process_length):
    k = kdata.iloc[i]
    
    # 计算各部分比例
    body_size = abs(k['close'] - k['open'])
    upper_shadow = k['high'] - max(k['open'], k['close'])
    lower_shadow = min(k['open'], k['close']) - k['low']
    total_range = k['high'] - k['low']
    
    if total_range == 0:
        continue
    
    body_ratio = body_size / total_range
    upper_ratio = upper_shadow / total_range
    lower_ratio = lower_shadow / total_range
    
    # 锤头线特征：小实体，几乎没有上影线，长下影线
    # R245: 阈值与 Track1 内置 _detect_hammer (pattern_recognition.py _detect_hammer) 统一:
    # 下影线 > 2.0 * 实体、上影线 < 0.2 * 实体 (原 absolute 区间式 lower_ratio>0.6 偏严, 偏离 TA-Lib ShadowVeryLong)
    if (body_ratio < 0.3 and upper_shadow < body_size * 0.2 and lower_shadow > 2.0 * body_size and total_range > 0):
        confidence = min(0.9, lower_ratio * 0.8 + (0.3 - body_ratio) * 0.5 + (0.1 - upper_ratio) * 0.3)
        
        datetime_val = str(kdata.iloc[i]['datetime']) if 'datetime' in kdata.columns else None
        
        result = create_result(
            pattern_type='hammer',
            signal_type=SignalType.BUY,
            confidence=confidence,
            index=i,
            price=k['close'],
            datetime_val=datetime_val,
            extra_data={
                'body_ratio': body_ratio,
                'upper_ratio': upper_ratio,
                'lower_ratio': lower_ratio
            }
        )
        results.append(result)
''',
            'parameters': '{"min_body_ratio": 0.3, "max_upper_shadow_ratio": 0.2, "min_lower_shadow_ratio": 2.0}'
        },

        'doji': {
            'code': '''
# 十字星识别算法
max_process_length = min(len(kdata), 1000)
prev_body_ratio = 0.0
for i in range(max_process_length):
    k = kdata.iloc[i]
    
    body_size = abs(k['close'] - k['open'])
    total_range = k['high'] - k['low']
    
    if total_range == 0:
        prev_body_ratio = 0.0
        continue
    
    body_ratio = body_size / total_range
    
    # 实体占比小于10%且前一根实体大于30%认为是十字星
    # R245: 与 Track1 内置 _detect_doji（pattern_recognition.py L494-499）统一，追加前一根上下文
    if body_ratio < 0.1 and (i == 0 or prev_body_ratio > 0.3):
        confidence = min(0.9, (0.1 - body_ratio) / 0.1 * 0.9 + 0.5)
        
        datetime_val = str(kdata.iloc[i]['datetime']) if 'datetime' in kdata.columns else None
        
        result = create_result(
            pattern_type='doji',
            signal_type=SignalType.NEUTRAL,
            confidence=confidence,
            index=i,
            price=(k['open'] + k['close']) / 2,
            datetime_val=datetime_val,
            extra_data={
                'body_ratio': body_ratio,
                'upper_shadow': k['high'] - max(k['open'], k['close']),
                'lower_shadow': min(k['open'], k['close']) - k['low']
            }
        )
        results.append(result)
    prev_body_ratio = body_ratio
''',
            'parameters': '{"max_body_ratio": 0.1, "min_prev_body_ratio": 0.3}'
        },

        'shooting_star': {
            'code': '''
# 流星线识别算法
max_process_length = min(len(kdata), 1000)
for i in range(max_process_length):
    k = kdata.iloc[i]
    
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
        
        datetime_val = str(kdata.iloc[i]['datetime']) if 'datetime' in kdata.columns else None
        
        result = create_result(
            pattern_type='shooting_star',
            signal_type=SignalType.SELL,
            confidence=confidence,
            index=i,
            price=k['close'],
            datetime_val=datetime_val,
            extra_data={
                'body_ratio': body_ratio,
                'upper_ratio': upper_ratio,
                'lower_ratio': lower_ratio
            }
        )
        results.append(result)
''',
            'parameters': '{"min_body_ratio": 0.3, "min_upper_ratio": 0.6, "max_lower_ratio": 0.1}'
        },

        'inverted_hammer': {
            'code': '''
# 倒锤头识别算法
max_process_length = min(len(kdata), 1000)
for i in range(max_process_length):
    k = kdata.iloc[i]
    
    body_size = abs(k['close'] - k['open'])
    upper_shadow = k['high'] - max(k['open'], k['close'])
    lower_shadow = min(k['open'], k['close']) - k['low']
    total_range = k['high'] - k['low']
    
    if total_range == 0:
        continue
    
    body_ratio = body_size / total_range
    upper_ratio = upper_shadow / total_range
    lower_ratio = lower_shadow / total_range
    
    # 倒锤头特征：小实体，长上影线，几乎没有下影线，在下跌趋势中
    if (body_ratio < 0.3 and upper_ratio > 0.6 and lower_ratio < 0.1):
        # 检查是否在下跌趋势中
        if i >= 5:
            recent_closes = [kdata.iloc[j]['close'] for j in range(max(0, i-5), i)]
            if len(recent_closes) >= 2 and recent_closes[-1] < recent_closes[0]:
                confidence = min(0.9, upper_ratio * 0.8 + (0.3 - body_ratio) * 0.5)
                
                datetime_val = str(kdata.iloc[i]['datetime']) if 'datetime' in kdata.columns else None
                
                result = create_result(
                    pattern_type='inverted_hammer',
                    signal_type=SignalType.BUY,
                    confidence=confidence,
                    index=i,
                    price=k['close'],
                    datetime_val=datetime_val,
                    extra_data={
                        'body_ratio': body_ratio,
                        'upper_ratio': upper_ratio,
                        'lower_ratio': lower_ratio
                    }
                )
                results.append(result)
''',
            'parameters': '{"min_body_ratio": 0.3, "min_upper_ratio": 0.6, "max_lower_ratio": 0.1, "trend_window": 5}'
        },

        'marubozu': {
            'code': '''
# 光头光脚线识别算法
max_process_length = min(len(kdata), 1000)
for i in range(max_process_length):
    k = kdata.iloc[i]
    
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
        signal_type = SignalType.BUY if is_bullish else SignalType.SELL
        confidence = min(0.9, body_ratio * 0.9 + (0.05 - max(upper_ratio, lower_ratio)) * 2)
        
        datetime_val = str(kdata.iloc[i]['datetime']) if 'datetime' in kdata.columns else None
        
        result = create_result(
            pattern_type='white_marubozu' if is_bullish else 'black_marubozu',
            signal_type=signal_type,
            confidence=confidence,
            index=i,
            price=k['close'],
            datetime_val=datetime_val,
            extra_data={
                'body_ratio': body_ratio,
                'upper_ratio': upper_ratio,
                'lower_ratio': lower_ratio,
                'is_bullish': is_bullish
            }
        )
        results.append(result)
''',
            'parameters': '{"min_body_ratio": 0.9, "max_shadow_ratio": 0.05}'
        },

        'spinning_top': {
            'code': '''
# 纺锤线识别算法
max_process_length = min(len(kdata), 1000)
for i in range(max_process_length):
    k = kdata.iloc[i]
    
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
        
        datetime_val = str(kdata.iloc[i]['datetime']) if 'datetime' in kdata.columns else None
        
        result = create_result(
            pattern_type='spinning_top',
            signal_type=SignalType.NEUTRAL,
            confidence=confidence,
            index=i,
            price=(k['open'] + k['close']) / 2,
            datetime_val=datetime_val,
            extra_data={
                'body_ratio': body_ratio,
                'upper_ratio': upper_ratio,
                'lower_ratio': lower_ratio
            }
        )
        results.append(result)
''',
            'parameters': '{"max_body_ratio": 0.3, "min_shadow_ratio": 0.2}'
        },

        # 双根K线形态
        'bullish_engulfing': {
            'code': '''
# 看涨吞没识别算法
max_process_length = min(len(kdata), 1000)
for i in range(1, max_process_length):
    k1 = kdata.iloc[i-1]  # 前一根
    k2 = kdata.iloc[i]    # 当前根
    
    # 第一根是阴线，第二根是阳线
    if k1['close'] < k1['open'] and k2['close'] > k2['open']:
        # 第二根完全吞没第一根
        if k2['open'] < k1['close'] and k2['close'] > k1['open']:
            # 计算吞没程度
            engulf_ratio = (k2['close'] - k2['open']) / (k1['open'] - k1['close'])
            confidence = min(0.9, 0.6 + engulf_ratio * 0.3)
            
            datetime_val = str(kdata.iloc[i]['datetime']) if 'datetime' in kdata.columns else None
            
            result = create_result(
                pattern_type='bullish_engulfing',
                signal_type=SignalType.BUY,
                confidence=confidence,
                index=i,
                price=k2['close'],
                datetime_val=datetime_val,
                start_index=i-1,
                end_index=i,
                extra_data={
                    'engulf_ratio': engulf_ratio,
                    'prev_candle': {'open': k1['open'], 'close': k1['close']},
                    'curr_candle': {'open': k2['open'], 'close': k2['close']}
                }
            )
            results.append(result)
''',
            'parameters': '{"min_engulf_ratio": 1.0}'
        },

        'bearish_engulfing': {
            'code': '''
# 看跌吞没识别算法
max_process_length = min(len(kdata), 1000)
for i in range(1, max_process_length):
    k1 = kdata.iloc[i-1]  # 前一根
    k2 = kdata.iloc[i]    # 当前根
    
    # 第一根是阳线，第二根是阴线
    if k1['close'] > k1['open'] and k2['close'] < k2['open']:
        # 第二根完全吞没第一根
        if k2['open'] > k1['close'] and k2['close'] < k1['open']:
            # 计算吞没程度
            engulf_ratio = (k2['open'] - k2['close']) / (k1['close'] - k1['open'])
            confidence = min(0.9, 0.6 + engulf_ratio * 0.3)
            
            datetime_val = str(kdata.iloc[i]['datetime']) if 'datetime' in kdata.columns else None
            
            result = create_result(
                pattern_type='bearish_engulfing',
                signal_type=SignalType.SELL,
                confidence=confidence,
                index=i,
                price=k2['close'],
                datetime_val=datetime_val,
                start_index=i-1,
                end_index=i,
                extra_data={
                    'engulf_ratio': engulf_ratio,
                    'prev_candle': {'open': k1['open'], 'close': k1['close']},
                    'curr_candle': {'open': k2['open'], 'close': k2['close']}
                }
            )
            results.append(result)
''',
            'parameters': '{"min_engulf_ratio": 1.0}'
        },

        'piercing_pattern': {
            'code': '''
# 刺透形态识别算法
max_process_length = min(len(kdata), 1000)
for i in range(1, max_process_length):
    k1 = kdata.iloc[i-1]  # 前一根
    k2 = kdata.iloc[i]    # 当前根
    
    # 第一根是阴线，第二根是阳线
    if k1['close'] < k1['open'] and k2['close'] > k2['open']:
        # 第二根开盘价低于第一根收盘价，但收盘价刺透第一根实体的一半以上
        k1_mid = (k1['open'] + k1['close']) / 2
        if k2['open'] < k1['close'] and k2['close'] > k1_mid:
            # 计算刺透程度
            pierce_ratio = (k2['close'] - k1['close']) / (k1['open'] - k1['close'])
            confidence = min(0.8, 0.5 + pierce_ratio * 0.3)
            
            datetime_val = str(kdata.iloc[i]['datetime']) if 'datetime' in kdata.columns else None
            
            result = create_result(
                pattern_type='piercing_pattern',
                signal_type=SignalType.BUY,
                confidence=confidence,
                index=i,
                price=k2['close'],
                datetime_val=datetime_val,
                start_index=i-1,
                end_index=i,
                extra_data={
                    'pierce_ratio': pierce_ratio,
                    'prev_candle': {'open': k1['open'], 'close': k1['close']},
                    'curr_candle': {'open': k2['open'], 'close': k2['close']}
                }
            )
            results.append(result)
''',
            'parameters': '{"min_pierce_ratio": 0.5}'
        },

        'dark_cloud_cover': {
            'code': '''
# 乌云盖顶识别算法
max_process_length = min(len(kdata), 1000)
for i in range(1, max_process_length):
    k1 = kdata.iloc[i-1]  # 前一根
    k2 = kdata.iloc[i]    # 当前根
    
    # 第一根是阳线，第二根是阴线
    if k1['close'] > k1['open'] and k2['close'] < k2['open']:
        # 第二根开盘价高于第一根收盘价，但收盘价覆盖第一根实体的一半以上
        k1_mid = (k1['open'] + k1['close']) / 2
        if k2['open'] > k1['close'] and k2['close'] < k1_mid:
            # 计算覆盖程度
            cover_ratio = (k1['close'] - k2['close']) / (k1['close'] - k1['open'])
            confidence = min(0.8, 0.5 + cover_ratio * 0.3)
            
            datetime_val = str(kdata.iloc[i]['datetime']) if 'datetime' in kdata.columns else None
            
            result = create_result(
                pattern_type='dark_cloud_cover',
                signal_type=SignalType.SELL,
                confidence=confidence,
                index=i,
                price=k2['close'],
                datetime_val=datetime_val,
                start_index=i-1,
                end_index=i,
                extra_data={
                    'cover_ratio': cover_ratio,
                    'prev_candle': {'open': k1['open'], 'close': k1['close']},
                    'curr_candle': {'open': k2['open'], 'close': k2['close']}
                }
            )
            results.append(result)
''',
            'parameters': '{"min_cover_ratio": 0.5}'
        },

        # 三根K线形态
        'three_white_soldiers': {
            'code': '''
# 三白兵识别算法
max_process_length = min(len(kdata), 1000)
for i in range(2, max_process_length):
    k0 = kdata.iloc[i-2]  # 前日
    k1 = kdata.iloc[i-1]  # 昨日
    k2 = kdata.iloc[i]    # 今日
    
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
    
    datetime_val = str(kdata.iloc[i]['datetime']) if 'datetime' in kdata.columns else None
    
    result = create_result(
        pattern_type='three_white_soldiers',
        signal_type=SignalType.BUY,
        confidence=confidence,
        index=i,
        price=k2['close'],
        datetime_val=datetime_val,
        start_index=i-2,
        end_index=i,
        extra_data={
            'start_price': k0['open'],
            'end_price': k2['close'],
            'total_gain': total_gain * 100,
            'body_ratios': [body_ratio_0, body_ratio_1, body_ratio_2],
            'upper_ratios': [upper_ratio_0, upper_ratio_1, upper_ratio_2]
        }
    )
    results.append(result)
''',
            'parameters': '{"min_body_ratio": 0.3, "max_upper_ratio": 0.4}'
        },

        'three_black_crows': {
            'code': '''
# 三只乌鸦识别算法 - 安全增强版
try:
    # 数据有效性检查
    if len(kdata) < 3:
        pass  # 数据不足，跳过
    else:
        # 限制处理范围，防止过大数据集导致性能问题
        max_process_length = min(len(kdata), 10000)
        
        for i in range(2, max_process_length):
            try:
                k0 = kdata.iloc[i-2]  # 前日
                k1 = kdata.iloc[i-1]  # 昨日
                k2 = kdata.iloc[i]    # 今日
                
                # 数据完整性检查
                required_fields = ['open', 'high', 'low', 'close']
                # R245: 原 all(... for field ...) genexpr 在 exec 分离命名空间下无法访问
                # 循环局部变量 k0/k1/k2 (NameError)，改为显式循环
                fields_ok = True
                for field in required_fields:
                    if field not in k0 or field not in k1 or field not in k2:
                        fields_ok = False
                        break
                if not fields_ok:
                    continue
                    
                # 价格有效性检查
                if any(pd.isna([k0['open'], k0['high'], k0['low'], k0['close'],
                               k1['open'], k1['high'], k1['low'], k1['close'],
                               k2['open'], k2['high'], k2['low'], k2['close']])):
                    continue
                
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
                
                datetime_val = str(kdata.iloc[i]['datetime']) if 'datetime' in kdata.columns else None
                
                result = create_result(
                    pattern_type='three_black_crows',
                    signal_type=SignalType.SELL,
                    confidence=confidence,
                    index=i,
                    price=k2['close'],
                    datetime_val=datetime_val,
                    start_index=i-2,
                    end_index=i,
                    extra_data={
                        'start_price': k0['open'],
                        'end_price': k2['close'],
                        'total_loss': total_loss * 100,
                        'body_ratios': [body_ratio_0, body_ratio_1, body_ratio_2],
                        'lower_ratios': [lower_ratio_0, lower_ratio_1, lower_ratio_2]
                    }
                )
                results.append(result)
                
                # 限制结果数量，防止内存问题
                if len(results) > 1000:
                    break
                    
            except Exception as inner_e:
                # 单个K线处理失败不影响整体
                continue
                
except Exception as e:
    # 整个算法失败，返回空结果
    pass
''',
            'parameters': '{"min_body_ratio": 0.3, "max_lower_ratio": 0.4}'
        },

        'morning_star': {
            'code': '''
# 早晨之星识别算法
max_process_length = min(len(kdata), 1000)
for i in range(2, max_process_length):
    k0 = kdata.iloc[i-2]  # 第一根
    k1 = kdata.iloc[i-1]  # 第二根（星线）
    k2 = kdata.iloc[i]    # 第三根
    
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
    
    datetime_val = str(kdata.iloc[i]['datetime']) if 'datetime' in kdata.columns else None
    
    result = create_result(
        pattern_type='morning_star',
        signal_type=SignalType.BUY,
        confidence=confidence,
        index=i,
        price=k2['close'],
        datetime_val=datetime_val,
        start_index=i-2,
        end_index=i,
        extra_data={
            'star_body_ratio': star_body_ratio,
            'penetration': penetration,
            'has_gaps': gap1 and gap2,
            'first_candle': {'open': k0['open'], 'close': k0['close']},
            'star_candle': {'open': k1['open'], 'close': k1['close']},
            'third_candle': {'open': k2['open'], 'close': k2['close']}
        }
    )
    results.append(result)
''',
            'parameters': '{"max_star_body_ratio": 0.3, "min_penetration": 0.5}'
        },

        'evening_star': {
            'code': '''
# 黄昏之星识别算法
max_process_length = min(len(kdata), 1000)
for i in range(2, max_process_length):
    k0 = kdata.iloc[i-2]  # 第一根
    k1 = kdata.iloc[i-1]  # 第二根（星线）
    k2 = kdata.iloc[i]    # 第三根
    
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
    
    datetime_val = str(kdata.iloc[i]['datetime']) if 'datetime' in kdata.columns else None
    
    result = create_result(
        pattern_type='evening_star',
        signal_type=SignalType.SELL,
        confidence=confidence,
        index=i,
        price=k2['close'],
        datetime_val=datetime_val,
        start_index=i-2,
        end_index=i,
        extra_data={
            'star_body_ratio': star_body_ratio,
            'penetration': penetration,
            'has_gaps': gap1 and gap2,
            'first_candle': {'open': k0['open'], 'close': k0['close']},
            'star_candle': {'open': k1['open'], 'close': k1['close']},
            'third_candle': {'open': k2['open'], 'close': k2['close']}
        }
    )
    results.append(result)
''',
            'parameters': '{"max_star_body_ratio": 0.3, "min_penetration": 0.5}'
        }
    }

    # 更新数据库中的算法代码（先确保形态记录存在，再写算法，避免依赖外部种子化脚本的执行次序）
    # 信号类型与 core/unified_indicator_service._SEED_PATTERNS 约定一致
    pattern_signal_types = {
        'hammer': 'buy', 'inverted_hammer': 'buy', 'bullish_engulfing': 'buy',
        'piercing_pattern': 'buy', 'three_white_soldiers': 'buy', 'morning_star': 'buy',
        'shooting_star': 'sell', 'hanging_man': 'sell', 'bearish_engulfing': 'sell',
        'dark_cloud_cover': 'sell', 'three_black_crows': 'sell', 'evening_star': 'sell',
    }
    for pattern_name, algorithm_data in algorithms.items():
        signal_type = pattern_signal_types.get(pattern_name, 'neutral')
        cursor.execute('''
            INSERT OR IGNORE INTO pattern_types 
            (name, english_name, category, signal_type, description) 
            VALUES (?, ?, ?, ?, ?)
        ''', (pattern_name, pattern_name, 'K线形态', signal_type, pattern_name))
        cursor.execute('''
            UPDATE pattern_types 
            SET algorithm_code = ?, parameters = ?
            WHERE english_name = ?
        ''', (algorithm_data['code'], algorithm_data['parameters'], pattern_name))

    conn.commit()
    conn.close()
    logger.info(f"成功初始化 {len(algorithms)} 个形态算法到数据库")

if __name__ == '__main__':
    init_pattern_algorithms()
