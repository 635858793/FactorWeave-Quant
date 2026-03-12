# -*- coding: utf-8 -*-
"""
特征工程自动化模块
自动生成和选择技术指标特征
"""
from typing import Dict, Any, Optional, List, Tuple
from loguru import logger
import numpy as np
from dataclasses import dataclass
from enum import Enum
import pandas as pd


class FeatureType(Enum):
    MOMENTUM = "momentum"
    TREND = "trend"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    PATTERN = "pattern"
    CUSTOM = "custom"


@dataclass
class FeatureConfig:
    """特征配置"""
    name: str
    type: FeatureType
    enabled: bool = True
    params: Dict[str, Any] = None


class FeatureEngineer:
    """特征工程引擎"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.selected_features: List[str] = []
        self.feature_importance: Dict[str, float] = {}
        
        self._momentum_features = [
            'rsi', 'momentum', 'roc', 'stochastic_k', 'stochastic_d',
            'trix', 'cci', 'williams_r', 'mfi'
        ]
        
        self._trend_features = [
            'ma5', 'ma10', 'ma20', 'ma60', 'ma120', 'ma250',
            'ema12', 'ema26', 'ema50', 'macd', 'macd_signal', 'macd_hist',
            'adx', 'plus_di', 'minus_di', 'aroon_up', 'aroon_down', 'aroon_osc'
        ]
        
        self._volatility_features = [
            'atr', 'bb_upper', 'bb_lower', 'bb_width', 'stddev',
            'historical_volatility', 'keltner_upper', 'keltner_lower'
        ]
        
        self._volume_features = [
            'volume_ma5', 'volume_ma20', 'volume_ratio', 'obv', 'vwap',
            'ad', 'mfi_volume', 'cmf'
        ]
    
    def generate_features(
        self, 
        data: pd.DataFrame,
        feature_types: Optional[List[FeatureType]] = None
    ) -> pd.DataFrame:
        """
        自动生成技术指标特征
        
        Args:
            data: 包含 OHLCV 数据的 DataFrame
            feature_types: 要生成的特征类型列表
            
        Returns:
            包含新特征的 DataFrame
        """
        if feature_types is None:
            feature_types = [FeatureType.MOMENTUM, FeatureType.TREND, FeatureType.VOLATILITY, FeatureType.VOLUME]
        
        df = data.copy()
        
        required_cols = ['high', 'low', 'close', 'open', 'volume']
        if not all(col in df.columns for col in required_cols):
            logger.warning(f"数据缺少必要列，需要: {required_cols}")
            return df
        
        for feature_type in feature_types:
            if feature_type == FeatureType.MOMENTUM:
                df = self._add_momentum_features(df)
            elif feature_type == FeatureType.TREND:
                df = self._add_trend_features(df)
            elif feature_type == FeatureType.VOLATILITY:
                df = self._add_volatility_features(df)
            elif feature_type == FeatureType.VOLUME:
                df = self._add_volume_features(df)
        
        df = self._clean_infinite_na(df)
        
        logger.info(f"特征生成完成，共 {len(df.columns)} 个特征")
        return df
    
    def _add_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加动量特征"""
        close = df['close']
        high = df['high']
        low = df['low']
        
        period_rsi = self.config.get('rsi_period', 14)
        df['rsi'] = self._calculate_rsi(close, period_rsi)
        
        df['momentum'] = close.pct_change(periods=10)
        
        df['roc'] = ((close - close.shift(10)) / close.shift(10)) * 100
        
        low_min = low.rolling(window=14).min()
        high_max = high.rolling(window=14).max()
        df['stochastic_k'] = 100 * (close - low_min) / (high_max - low_min)
        df['stochastic_d'] = df['stochastic_k'].rolling(window=3).mean()
        
        period_trix = self.config.get('trix_period', 15)
        ema1 = close.ewm(span=period_trix).mean()
        ema2 = ema1.ewm(span=period_trix).mean()
        ema3 = ema2.ewm(span=period_trix).mean()
        df['trix'] = ((ema3 - ema3.shift(1)) / ema3.shift(1)) * 100
        
        period_cci = self.config.get('cci_period', 20)
        tp = (high + low + close) / 3
        sma_tp = tp.rolling(window=period_cci).mean()
        mad = tp.rolling(window=period_cci).apply(lambda x: np.abs(x - x.mean()).mean())
        df['cci'] = (tp - sma_tp) / (0.015 * mad + 1e-10)
        
        df['williams_r'] = -100 * (high.rolling(window=14).max() - close) / (high.rolling(window=14).max() - low.rolling(window=14).min() + 1e-10)
        
        period_mfi = self.config.get('mfi_period', 14)
        typical_price = (high + low + close) / 3
        money_flow = typical_price * df['volume']
        positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0)
        negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0)
        positive_sum = positive_flow.rolling(window=period_mfi).sum()
        negative_sum = negative_flow.rolling(window=period_mfi).sum()
        mfi = 100 - (100 / (1 + positive_sum / (negative_sum + 1e-10)))
        df['mfi'] = mfi
        
        return df
    
    def _add_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加趋势特征"""
        close = df['close']
        
        for period in [5, 10, 20, 60, 120, 250]:
            df[f'ma{period}'] = close.rolling(window=period).mean()
        
        for period in [12, 26, 50]:
            df[f'ema{period}'] = close.ewm(span=period, adjust=False).mean()
        
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        period_adx = self.config.get('adx_period', 14)
        high = df['high']
        low = df['low']
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = tr1.combine_max(tr2).combine_max(tr3)
        
        atr = tr.rolling(window=period_adx).mean()
        
        plus_di = 100 * (plus_dm.rolling(window=period_adx).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period_adx).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        df['adx'] = dx.rolling(window=period_adx).mean()
        df['plus_di'] = plus_di
        df['minus_di'] = minus_di
        
        period_aroon = 25
        df['aroon_up'] = high.rolling(window=period_aroon + 1).apply(lambda x: float(np.argmax(x)) / period_aroon * 100, raw=True)
        df['aroon_down'] = low.rolling(window=period_aroon + 1).apply(lambda x: float(np.argmin(x)) / period_aroon * 100, raw=True)
        df['aroon_osc'] = df['aroon_up'] - df['aroon_down']
        
        return df
    
    def _add_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加波动率特征"""
        close = df['close']
        high = df['high']
        low = df['low']
        
        period_atr = self.config.get('atr_period', 14)
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = tr1.combine_max(tr2).combine_max(tr3)
        df['atr'] = tr.rolling(window=period_atr).mean()
        
        period_bb = 20
        bb_std = close.rolling(window=period_bb).std()
        bb_ma = close.rolling(window=period_bb).mean()
        df['bb_upper'] = bb_ma + 2 * bb_std
        df['bb_lower'] = bb_ma - 2 * bb_std
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / bb_ma
        
        df['stddev'] = close.rolling(window=20).std()
        
        df['historical_volatility'] = close.pct_change().rolling(window=20).std() * np.sqrt(252)
        
        period_kc = 20
        kc_ma = close.rolling(window=period_kc).mean()
        kc_atr = df['atr']
        df['keltner_upper'] = kc_ma + 2 * kc_atr
        df['keltner_lower'] = kc_ma - 2 * kc_atr
        
        return df
    
    def _add_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加成交量特征"""
        close = df['close']
        volume = df['volume']
        high = df['high']
        low = df['low']
        
        df['volume_ma5'] = volume.rolling(window=5).mean()
        df['volume_ma20'] = volume.rolling(window=20).mean()
        df['volume_ratio'] = volume / df['volume_ma20']
        
        df['obv'] = (np.sign(close.diff()) * volume).fillna(0).cumsum()
        
        typical_price = (high + low + close) / 3
        df['vwap'] = (typical_price * volume).cumsum() / volume.cumsum()
        
        money_flow = typical_price * volume
        mf_diff = money_flow.diff()
        positive_flow = mf_diff.where(mf_diff > 0, 0)
        negative_flow = -mf_diff.where(mf_diff < 0, 0)
        df['ad'] = (positive_flow.rolling(window=1).sum() - negative_flow.rolling(window=1).sum()).cumsum()
        
        period_cmf = 20
        df['cmf'] = (positive_flow.rolling(window=period_cmf).sum() / volume.rolling(window=period_cmf).sum() -
                    negative_flow.rolling(window=period_cmf).sum() / volume.rolling(window=period_cmf).sum())
        
        return df
    
    def _calculate_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _clean_infinite_na(self, df: pd.DataFrame) -> pd.DataFrame:
        """清理无穷值和NA"""
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.fillna(method='ffill').fillna(method='bfill').fillna(0)
        return df
    
    def select_features(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        method: str = "importance",
        n_features: int = 50
    ) -> List[str]:
        """
        特征选择
        
        Args:
            X: 特征数据
            y: 目标变量
            method: 选择方法 ('importance', 'correlation', 'mutual_info')
            n_features: 选择特征数量
            
        Returns:
            选中的特征列表
        """
        if method == "importance":
            selected = self._select_by_importance(X, y, n_features)
        elif method == "correlation":
            selected = self._select_by_correlation(X, y, n_features)
        elif method == "mutual_info":
            selected = self._select_by_mutual_info(X, y, n_features)
        else:
            logger.warning(f"未知特征选择方法: {method}，返回所有特征")
            selected = list(X.columns)
        
        self.selected_features = selected
        logger.info(f"特征选择完成，选中 {len(selected)} 个特征")
        return selected
    
    def _select_by_importance(self, X: pd.DataFrame, y: pd.Series, n: int) -> List[str]:
        """基于特征重要性选择"""
        from sklearn.ensemble import RandomForestClassifier
        
        try:
            rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
            rf.fit(X.fillna(0), y)
            
            importances = pd.Series(rf.feature_importances_, index=X.columns)
            importances = importances.sort_values(ascending=False)
            
            self.feature_importance = importances.to_dict()
            
            return list(importances.head(n).index)
        except Exception as e:
            logger.warning(f"特征重要性计算失败: {e}")
            return list(X.columns[:n])
    
    def _select_by_correlation(self, X: pd.DataFrame, y: pd.Series, n: int) -> List[str]:
        """基于与目标相关性选择"""
        correlations = X.corrwith(y).abs().sort_values(ascending=False)
        self.feature_importance = correlations.to_dict()
        return list(correlations.head(n).index)
    
    def _select_by_mutual_info(self, X: pd.DataFrame, y: pd.Series, n: int) -> List[str]:
        """基于互信息选择"""
        from sklearn.feature_selection import mutual_info_classif
        
        try:
            mi_scores = mutual_info_classif(X.fillna(0), y, random_state=42)
            mi_series = pd.Series(mi_scores, index=X.columns).sort_values(ascending=False)
            self.feature_importance = mi_series.to_dict()
            return list(mi_series.head(n).index)
        except Exception as e:
            logger.warning(f"互信息计算失败: {e}")
            return list(X.columns[:n])
    
    def get_feature_names(self, feature_types: Optional[List[FeatureType]] = None) -> List[str]:
        """获取所有可用特征名"""
        if feature_types is None:
            feature_types = [FeatureType.MOMENTUM, FeatureType.TREND, FeatureType.VOLATILITY, FeatureType.VOLUME]
        
        all_features = []
        for ft in feature_types:
            if ft == FeatureType.MOMENTUM:
                all_features.extend(self._momentum_features)
            elif ft == FeatureType.TREND:
                all_features.extend(self._trend_features)
            elif ft == FeatureType.VOLATILITY:
                all_features.extend(self._volatility_features)
            elif ft == FeatureType.VOLUME:
                all_features.extend(self._volume_features)
        
        return all_features


def create_feature_engineer(config: Optional[Dict[str, Any]] = None) -> FeatureEngineer:
    """创建特征工程引擎工厂函数"""
    return FeatureEngineer(config)
