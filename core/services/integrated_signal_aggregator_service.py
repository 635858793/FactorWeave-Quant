from loguru import logger
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集成的智能信号聚合服务（TET模式）
使用TET统一数据框架获取多源数据，进行智能信号聚合分析
"""

import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import pandas as pd

from core.services.base_service import CacheableService, ConfigurableService
from core.services.unified_data_manager import UnifiedDataManager, get_unified_data_manager
from core.services.asset_service import AssetService
from core.plugin_types import AssetType, DataType
from core.tet_data_pipeline import StandardQuery
from gui.widgets.signal_aggregator import SignalAggregator, AggregatedAlert
from gui.widgets.signal_detectors.base_detector import SignalDetectorRegistry



class TETDataProvider:
    """基于TET框架的统一数据提供器"""

    def __init__(self, unified_data_manager: UnifiedDataManager, asset_service: AssetService):
        self.unified_data_manager = unified_data_manager
        self.asset_service = asset_service
        self.logger = logger.bind(module=self.__class__.__name__)
    async def get_multi_source_data(self, symbol: str, asset_type: AssetType = AssetType.STOCK_A) -> Dict[str, Any]:
        """
        通过TET框架获取多源数据
        包括K线数据、技术指标、基本面数据等
        """
        try:
            self.logger.info(f" 通过TET框架获取多源数据: {symbol}")

            # 并行获取多种数据类型
            tasks = []

            # 1. 历史K线数据
            tasks.append(self._get_historical_kline(symbol, asset_type))

            # 2. 实时行情数据
            tasks.append(self._get_realtime_quote(symbol, asset_type))

            # 3. 基本面数据（如果支持）
            if asset_type == AssetType.STOCK_A:
                tasks.append(self._get_fundamental_data(symbol, asset_type))

            # 4. 技术指标数据（基于K线计算）
            tasks.append(self._get_technical_indicators(symbol, asset_type))

            # 等待所有任务完成
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 整合结果
            multi_source_data = {
                'kline_data': results[0] if not isinstance(results[0], Exception) else pd.DataFrame(),
                'realtime_data': results[1] if not isinstance(results[1], Exception) else {},
                'fundamental_data': results[2] if len(results) > 2 and not isinstance(results[2], Exception) else {},
                'technical_indicators': results[3] if not isinstance(results[3], Exception) else {}
            }

            self.logger.info(f" TET多源数据获取完成: {symbol}")
            return multi_source_data

        except Exception as e:
            self.logger.error(f" TET多源数据获取失败: {symbol} - {e}")
            return {
                'kline_data': pd.DataFrame(),
                'realtime_data': {},
                'fundamental_data': {},
                'technical_indicators': {}
            }

    async def _get_historical_kline(self, symbol: str, asset_type: AssetType) -> pd.DataFrame:
        """获取历史K线数据"""
        try:
            loop = asyncio.get_event_loop()

            # 使用AssetService的TET模式API
            kdata = await loop.run_in_executor(
                None,
                self.asset_service.get_historical_data,
                symbol, asset_type, None, None, "D"
            )

            if kdata is not None and not kdata.empty:
                self.logger.info(f" TET K线数据获取成功: {symbol} | {len(kdata)} 条记录")
                return kdata
            else:
                self.logger.warning(f" TET K线数据为空: {symbol}")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f" TET K线数据获取失败: {symbol} - {e}")
            return pd.DataFrame()

    async def _get_realtime_quote(self, symbol: str, asset_type: AssetType) -> Dict[str, Any]:
        """获取实时行情数据"""
        try:
            loop = asyncio.get_event_loop()

            # 通过UnifiedDataManager的TET管道获取实时数据
            realtime_data = await loop.run_in_executor(
                None,
                self.unified_data_manager.get_asset_data,
                symbol, asset_type, DataType.REAL_TIME_QUOTE
            )

            if realtime_data is not None and not realtime_data.empty:
                # 转换为字典格式
                latest_quote = realtime_data.iloc[-1].to_dict()
                self.logger.info(f" TET实时行情获取成功: {symbol}")
                return latest_quote
            else:
                self.logger.warning(f" TET实时行情为空: {symbol}")
                return {}

        except Exception as e:
            self.logger.warning(f" TET实时行情获取失败: {symbol} - {e}")
            return {}

    async def _get_fundamental_data(self, symbol: str, asset_type: AssetType) -> Dict[str, Any]:
        """获取基本面数据"""
        try:
            if asset_type != AssetType.STOCK_A:
                return {}

            loop = asyncio.get_event_loop()

            # 通过TET管道获取基本面数据
            fundamental_df = await loop.run_in_executor(
                None,
                self.unified_data_manager.get_asset_data,
                symbol, asset_type, DataType.FUNDAMENTAL_DATA
            )

            if fundamental_df is not None and not fundamental_df.empty:
                # 转换为字典格式
                fundamental_data = fundamental_df.iloc[-1].to_dict()
                self.logger.info(f" TET基本面数据获取成功: {symbol}")
                return fundamental_data
            else:
                self.logger.warning(f" TET基本面数据为空: {symbol}")
                return {}

        except Exception as e:
            self.logger.warning(f" TET基本面数据获取失败: {symbol} - {e}")
            return {}

    async def _get_technical_indicators(self, symbol: str, asset_type: AssetType) -> Dict[str, Any]:
        """基于K线数据计算技术指标"""
        try:
            # 先获取K线数据
            kdata = await self._get_historical_kline(symbol, asset_type)

            if kdata.empty:
                return {}

            # 计算常用技术指标
            indicators = {}

            # RSI
            if 'close' in kdata.columns and len(kdata) >= 14:
                indicators['rsi'] = self._calculate_rsi(kdata['close'])

            # MACD
            if 'close' in kdata.columns and len(kdata) >= 26:
                macd_data = self._calculate_macd(kdata['close'])
                indicators['macd'] = macd_data

            # 移动平均线
            if 'close' in kdata.columns:
                indicators['ma'] = {
                    'ma5': self._calculate_ma(kdata['close'], 5),
                    'ma10': self._calculate_ma(kdata['close'], 10),
                    'ma20': self._calculate_ma(kdata['close'], 20)
                }

            # KDJ
            if all(col in kdata.columns for col in ['high', 'low', 'close']) and len(kdata) >= 9:
                kdj_data = self._calculate_kdj(kdata)
                indicators['kdj'] = kdj_data

            self.logger.info(f" 技术指标计算完成: {symbol} | {len(indicators)} 个指标")
            return indicators

        except Exception as e:
            self.logger.error(f" 技术指标计算失败: {symbol} - {e}")
            return {}

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """计算RSI"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return float(rsi.iloc[-1]) if not rsi.empty else 50.0
        except Exception:
            return 50.0

    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
        """计算MACD"""
        try:
            exp1 = prices.ewm(span=fast).mean()
            exp2 = prices.ewm(span=slow).mean()
            macd_line = exp1 - exp2
            signal_line = macd_line.ewm(span=signal).mean()
            histogram = macd_line - signal_line

            return {
                'dif': float(macd_line.iloc[-1]),
                'dea': float(signal_line.iloc[-1]),
                'histogram': float(histogram.iloc[-1])
            }
        except Exception:
            return {'dif': 0.0, 'dea': 0.0, 'histogram': 0.0}

    def _calculate_ma(self, prices: pd.Series, period: int) -> float:
        """计算移动平均线"""
        try:
            ma = prices.rolling(window=period).mean()
            return float(ma.iloc[-1]) if not ma.empty else 0.0
        except Exception:
            return 0.0

    def _calculate_kdj(self, kdata: pd.DataFrame, period: int = 9) -> Dict[str, float]:
        """计算KDJ"""
        try:
            high = kdata['high']
            low = kdata['low']
            close = kdata['close']

            lowest_low = low.rolling(window=period).min()
            highest_high = high.rolling(window=period).max()

            rsv = (close - lowest_low) / (highest_high - lowest_low) * 100

            k = rsv.ewm(com=2).mean()
            d = k.ewm(com=2).mean()
            j = 3 * k - 2 * d

            return {
                'k': float(k.iloc[-1]) if not k.empty else 50.0,
                'd': float(d.iloc[-1]) if not d.empty else 50.0,
                'j': float(j.iloc[-1]) if not j.empty else 50.0
            }
        except Exception:
            return {'k': 50.0, 'd': 50.0, 'j': 50.0}


class IntegratedSignalAggregatorService(CacheableService, ConfigurableService):
    """
    集成的智能信号聚合服务（TET模式）

    信号聚合规则:
    - 优先级排序: 时间维度(最新信号) > 信号强度 > 信号源可信度
    - 去重策略: 同一资产+同一信号类型+5分钟内视为重复
    - 冲突处理: 看涨/看跌信号同时存在时，以信号强度较高者为准
    - 权重分配: 趋势类信号(0.35) > 反转类信号(0.25) > 成交量类(0.20) > 综合类(0.20)
    """

    def __init__(self):
        CacheableService.__init__(self, namespace='signal_aggregator')
        ConfigurableService.__init__(self)

        # TET框架组件
        self.unified_data_manager: Optional[UnifiedDataManager] = None
        self.asset_service: Optional[AssetService] = None

        # 数据提供器
        self.tet_data_provider: Optional[TETDataProvider] = None

        # 信号聚合器
        self.signal_aggregator = SignalAggregator()
        self.detector_registry = SignalDetectorRegistry()

        # 缓存
        self.cache_ttl = 300  # 5分钟缓存

    async def initialize(self):
        """初始化服务"""
        try:
            logger.info("初始化智能信号聚合服务（TET模式）...")

            # 获取统一数据管理器
            self.unified_data_manager = get_unified_data_manager()
            if not self.unified_data_manager:
                raise RuntimeError("UnifiedDataManager未注册")

            # 验证TET模式是否启用
            if not self.unified_data_manager.tet_enabled:
                logger.warning("TET模式未启用，尝试初始化...")
                self.unified_data_manager._initialize_tet_pipeline()

            if not self.unified_data_manager.tet_enabled:
                raise RuntimeError("TET数据管道未启用")

            # 获取资产服务
            from core.containers import get_service_container
            container = get_service_container()
            if container:
                try:
                    self.asset_service = container.resolve(AssetService)
                    logger.info("AssetService注入成功")
                except Exception as e:
                    logger.warning(f" AssetService注入失败: {e}")
                    # 创建默认实例
                    self.asset_service = AssetService()
            else:
                self.asset_service = AssetService()

            # 初始化TET数据提供器
            self.tet_data_provider = TETDataProvider(
                self.unified_data_manager,
                self.asset_service
            )

            logger.info("智能信号聚合服务（TET模式）初始化完成")

        except Exception as e:
            logger.error(f" 服务初始化失败: {e}")
            raise

    async def analyze_stock_signals(self, symbol: str, asset_type: AssetType = AssetType.STOCK_A) -> List[AggregatedAlert]:
        """分析股票信号（TET模式）"""
        try:
            logger.info(f" 开始TET模式信号分析: {symbol}")

            # 检查缓存
            cache_key = f"tet_signals_{symbol}_{asset_type.value}"
            cached_result = self.get_cached_data(cache_key)
            if cached_result is not None:
                logger.info(f" 使用缓存的TET信号分析结果: {symbol}")
                return cached_result

            # 通过TET框架获取多源数据
            if not self.tet_data_provider:
                raise RuntimeError("TET数据提供器未初始化")

            multi_source_data = await self.tet_data_provider.get_multi_source_data(symbol, asset_type)

            # 提取各类数据
            kdata = multi_source_data.get('kline_data', pd.DataFrame())
            realtime_data = multi_source_data.get('realtime_data', {})
            fundamental_data = multi_source_data.get('fundamental_data', {})
            technical_indicators = multi_source_data.get('technical_indicators', {})

            # 构造情绪数据（从实时数据中提取或使用默认值）
            sentiment_data = self._extract_sentiment_data(realtime_data, fundamental_data)

            # 执行信号聚合
            alerts = self.signal_aggregator.process_data(
                kdata=kdata,
                technical_indicators=technical_indicators,
                sentiment_data=sentiment_data,
                fundamental_data=fundamental_data
            )

            # 缓存结果
            self.cache_data(cache_key, alerts, ttl=self.cache_ttl)

            logger.info(f" TET模式信号分析完成: {symbol} | 生成 {len(alerts)} 个警报")
            return alerts

        except Exception as e:
            logger.error(f" TET模式信号分析失败: {symbol} - {e}")
            return []

    def _extract_sentiment_data(self, realtime_data: Dict[str, Any], fundamental_data: Dict[str, Any]) -> Dict[str, Any]:
        """从实时和基本面数据中提取情绪指标"""
        sentiment_data = {}

        try:
            # 从实时数据计算简单情绪指标
            if 'change_percent' in realtime_data:
                change_pct = float(realtime_data['change_percent'])
                # 将涨跌幅转换为恐贪指数（简化版）
                if change_pct > 5:
                    fear_greed = 80  # 贪婪
                elif change_pct > 2:
                    fear_greed = 65  # 乐观
                elif change_pct < -5:
                    fear_greed = 20  # 恐惧
                elif change_pct < -2:
                    fear_greed = 35  # 悲观
                else:
                    fear_greed = 50  # 中性

                sentiment_data['fear_greed_index'] = fear_greed

            # 从成交量数据估算资金流向
            if 'volume' in realtime_data and 'change_percent' in realtime_data:
                volume = float(realtime_data.get('volume', 0))
                change_pct = float(realtime_data.get('change_percent', 0))

                # 简化的资金流向计算
                if volume > 0 and change_pct > 0:
                    money_flow = min(0.8, volume / 10000000 * 0.1)  # 正向资金流
                elif volume > 0 and change_pct < 0:
                    money_flow = max(-0.8, -volume / 10000000 * 0.1)  # 负向资金流
                else:
                    money_flow = 0.0

                sentiment_data['money_flow'] = money_flow

            # 设置默认值
            sentiment_data.setdefault('fear_greed_index', 50)
            sentiment_data.setdefault('news_sentiment', 0.5)
            sentiment_data.setdefault('money_flow', 0.0)
            sentiment_data.setdefault('vix_index', 20)

        except Exception as e:
            logger.warning(f" 情绪数据提取失败: {e}")
            # 返回默认情绪数据
            sentiment_data = {
                'fear_greed_index': 50,
                'news_sentiment': 0.5,
                'money_flow': 0.0,
                'vix_index': 20
            }

        return sentiment_data

    def get_signal_statistics(self, symbol: str = None) -> Dict[str, Any]:
        """获取信号统计信息"""
        try:
            stats = self.signal_aggregator.get_signal_statistics()

            if symbol:
                stats['symbol'] = symbol
                stats['data_source'] = 'TET Pipeline'

            # 添加TET状态信息
            if self.unified_data_manager:
                stats['tet_enabled'] = self.unified_data_manager.tet_enabled
                if hasattr(self.unified_data_manager, 'tet_pipeline'):
                    stats['tet_pipeline_available'] = True

            # 添加检测器统计
            detector_info = self.detector_registry.get_registry_info()
            stats.update(detector_info)

            return stats

        except Exception as e:
            logger.error(f" 获取信号统计失败: {e}")
            return {}

    def set_signal_weights(self, weights: Dict[str, float]):
        """设置信号权重"""
        try:
            self.signal_aggregator.signal_weights.update(weights)
            logger.info(f" 信号权重已更新: {weights}")
        except Exception as e:
            logger.error(f" 设置信号权重失败: {e}")

    def add_custom_detector(self, name: str, detector):
        """添加自定义信号检测器"""
        try:
            self.detector_registry.register_detector(name, detector)
            logger.info(f" 自定义检测器 {name} 已注册")
        except Exception as e:
            logger.error(f" 注册自定义检测器失败: {e}")
