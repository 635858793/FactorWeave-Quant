"""
AI 选股模型训练数据收集器

提供自动化的训练数据收集、预处理和管理功能
"""

from loguru import logger
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from pathlib import Path
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

from ..containers import ServiceContainer, get_service_container
from ..events import EventBus, get_event_bus
from .unified_data_manager import UnifiedDataManager
from .enhanced_indicator_service import EnhancedIndicatorService
from ..plugin_types import AssetType


@dataclass
class TrainingDataSample:
    """训练数据样本"""
    stock_code: str
    stock_name: str
    features: Dict[str, float]
    label: float  # 0 或 1，表示是否应该买入
    timestamp: datetime
    return_5d: float  # 5日收益率
    return_20d: float  # 20日收益率
    market_cap: float
    pe_ratio: float
    pb_ratio: float
    roe: float


@dataclass
class TrainingDataset:
    """训练数据集"""
    dataset_id: str
    name: str
    samples: List[TrainingDataSample]
    created_at: datetime
    updated_at: datetime
    feature_columns: List[str]
    label_column: str = "label"
    metadata: Dict[str, Any] = field(default_factory=dict)


class TrainingDataCollector:
    """训练数据收集器
    
    负责收集、预处理和管理训练数据
    """
    
    def __init__(
        self,
        service_container: Optional[ServiceContainer] = None,
        event_bus: Optional[EventBus] = None
    ):
        """初始化训练数据收集器
        
        Args:
            service_container: 服务容器
            event_bus: 事件总线
        """
        self._container = service_container or get_service_container()
        if not self._container:
            raise ValueError("无法获取服务容器，请确保服务容器已初始化")
        
        self._event_bus = event_bus or get_event_bus()
        
        # 解析核心依赖服务
        self._data_manager = self._container.resolve(UnifiedDataManager)
        self._indicator_service = self._container.resolve(EnhancedIndicatorService)
        
        # 线程池用于异步数据收集
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="Data_Collector")
        
        # 数据存储路径
        self._data_storage_path = Path("data/training_data")
        self._data_storage_path.mkdir(parents=True, exist_ok=True)
        
        # 缓存
        self._dataset_cache: Dict[str, TrainingDataset] = {}
        self._cache_ttl = timedelta(hours=1)
        
        logger.info("训练数据收集器初始化完成")
    
    async def collect_training_data(
        self,
        stock_codes: List[str],
        lookback_days: int = 252,
        min_return: float = 0.05,
        max_return: float = 0.30
    ) -> TrainingDataset:
        """收集训练数据
        
        Args:
            stock_codes: 股票代码列表
            lookback_days: 回溯天数（默认252天，约1年）
            min_return: 最小收益率阈值（用于标记正样本）
            max_return: 最大收益率阈值（用于标记正样本）
            
        Returns:
            训练数据集
        """
        import uuid
        dataset_id = str(uuid.uuid4())
        
        logger.info(f"开始收集训练数据: {len(stock_codes)} 只股票，回溯 {lookback_days} 天")
        
        samples = []
        feature_columns = set()
        
        # 并行收集股票数据
        tasks = []
        for stock_code in stock_codes:
            task = self._collect_stock_data(stock_code, lookback_days, min_return, max_return)
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"收集股票数据失败: {result}")
                continue
            
            if result:
                samples.append(result)
                feature_columns.update(result.features.keys())
        
        # 创建数据集
        dataset = TrainingDataset(
            dataset_id=dataset_id,
            name=f"训练数据集_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            samples=samples,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            feature_columns=list(feature_columns)
        )
        
        # 缓存数据集
        self._dataset_cache[dataset_id] = dataset
        
        # 保存到磁盘
        await self._save_dataset(dataset)
        
        logger.info(f"训练数据收集完成: {len(samples)} 个样本，{len(feature_columns)} 个特征")
        
        return dataset
    
    async def _collect_stock_data(
        self,
        stock_code: str,
        lookback_days: int,
        min_return: float,
        max_return: float
    ) -> Optional[TrainingDataSample]:
        """收集单只股票的数据
        
        Args:
            stock_code: 股票代码
            lookback_days: 回溯天数
            min_return: 最小收益率阈值
            max_return: 最大收益率阈值
            
        Returns:
            训练数据样本
        """
        try:
            # 获取股票名称
            stock_name = await self._get_stock_name(stock_code)
            
            # 获取价格数据
            data_request = {
                "symbol": stock_code,
                "asset_type": AssetType.STOCK_A,
                "data_type": "kdata",
                "period": "D",
                "time_range": lookback_days
            }
            
            price_data = await self._data_manager.get_data_async(**data_request)
            
            if price_data is None or price_data.empty or len(price_data) < 60:
                return None
            
            # 计算收益率
            returns_5d = price_data['close'].pct_change(5)
            returns_20d = price_data['close'].pct_change(20)
            
            # 标记标签（基于未来收益率）
            current_return_20d = returns_20d.iloc[-1] if not returns_20d.empty else 0
            
            if min_return <= current_return_20d <= max_return:
                label = 1.0  # 买入
            elif current_return_20d < -min_return:
                label = 0.0  # 不买入
            else:
                label = 0.0  # 不买入
            
            # 计算技术指标
            features = await self._calculate_features(price_data)
            
            # 获取基本面数据
            fundamental_data = await self._get_fundamental_data(stock_code)
            
            # 创建样本
            sample = TrainingDataSample(
                stock_code=stock_code,
                stock_name=stock_name,
                features=features,
                label=label,
                timestamp=datetime.now(),
                return_5d=float(returns_5d.iloc[-1]) if not returns_5d.empty else 0.0,
                return_20d=float(current_return_20d),
                market_cap=fundamental_data.get('market_cap', 0.0),
                pe_ratio=fundamental_data.get('pe_ratio', 0.0),
                pb_ratio=fundamental_data.get('pb_ratio', 0.0),
                roe=fundamental_data.get('roe', 0.0)
            )
            
            return sample
            
        except Exception as e:
            logger.warning(f"收集股票 {stock_code} 数据失败: {e}")
            return None
    
    async def _calculate_features(self, price_data: pd.DataFrame) -> Dict[str, float]:
        """计算技术指标特征
        
        Args:
            price_data: 价格数据
            
        Returns:
            特征字典
        """
        features = {}
        
        try:
            # 移动平均线
            sma_5 = price_data['close'].rolling(window=5).mean()
            sma_10 = price_data['close'].rolling(window=10).mean()
            sma_20 = price_data['close'].rolling(window=20).mean()
            sma_60 = price_data['close'].rolling(window=60).mean()
            
            current_price = float(price_data['close'].iloc[-1])
            
            features['price_sma5_ratio'] = current_price / float(sma_5.iloc[-1]) if not sma_5.empty else 1.0
            features['price_sma10_ratio'] = current_price / float(sma_10.iloc[-1]) if not sma_10.empty else 1.0
            features['price_sma20_ratio'] = current_price / float(sma_20.iloc[-1]) if not sma_20.empty else 1.0
            features['price_sma60_ratio'] = current_price / float(sma_60.iloc[-1]) if not sma_60.empty else 1.0
            
            # RSI
            rsi = self._calculate_rsi(price_data['close'], 14)
            if not rsi.empty:
                features['rsi_14'] = float(rsi.iloc[-1])
            
            # MACD
            macd_signal = self._calculate_macd_signal(price_data['close'])
            features['macd_signal'] = 1.0 if macd_signal == 'buy' else 0.0
            
            # 动量指标
            returns_5d = price_data['close'].pct_change(5)
            returns_10d = price_data['close'].pct_change(10)
            returns_20d = price_data['close'].pct_change(20)
            
            features['momentum_5d'] = float(returns_5d.iloc[-1]) if not returns_5d.empty else 0.0
            features['momentum_10d'] = float(returns_10d.iloc[-1]) if not returns_10d.empty else 0.0
            features['momentum_20d'] = float(returns_20d.iloc[-1]) if not returns_20d.empty else 0.0
            
            # 波动性
            returns = price_data['close'].pct_change().dropna()
            volatility_20d = returns.tail(20).std() * np.sqrt(252)
            volatility_60d = returns.tail(60).std() * np.sqrt(252)
            
            features['volatility_20d'] = float(volatility_20d)
            features['volatility_60d'] = float(volatility_60d)
            
            # 成交量指标
            if 'volume' in price_data.columns:
                volume_sma_20 = price_data['volume'].rolling(window=20).mean()
                current_volume = float(price_data['volume'].iloc[-1])
                features['volume_ratio'] = current_volume / float(volume_sma_20.iloc[-1]) if not volume_sma_20.empty else 1.0
            
            # 价格位置
            if len(price_data) >= 20:
                recent_high = price_data['close'].tail(20).max()
                recent_low = price_data['close'].tail(20).min()
                features['price_position'] = (current_price - recent_low) / (recent_high - recent_low) if recent_high > recent_low else 0.5
            
        except Exception as e:
            logger.warning(f"计算特征失败: {e}")
        
        return features
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_macd_signal(self, prices: pd.Series) -> str:
        """计算MACD信号"""
        try:
            if len(prices) < 26:
                return "hold"
            
            ema_12 = prices.ewm(span=12).mean()
            ema_26 = prices.ewm(span=26).mean()
            macd_line = ema_12 - ema_26
            
            if len(macd_line) < 9:
                return "hold"
            
            signal_line = macd_line.ewm(span=9).mean()
            macd_current = macd_line.iloc[-1]
            signal_current = signal_line.iloc[-1]
            
            if macd_current > signal_current:
                return "buy"
            else:
                return "sell"
        except Exception:
            return "hold"
    
    async def _get_stock_name(self, stock_code: str) -> str:
        """获取股票名称"""
        try:
            stock_info = await self._data_manager.get_stock_info(stock_code)
            if stock_info:
                return stock_info.get('name', stock_code)
            return stock_code
        except Exception:
            return stock_code
    
    async def _get_fundamental_data(self, stock_code: str) -> Dict[str, float]:
        """获取基本面数据"""
        try:
            fundamental_data = await self._data_manager.get_fundamental_data(stock_code)
            if fundamental_data:
                return {
                    'market_cap': float(fundamental_data.get('market_cap', 0.0)),
                    'pe_ratio': float(fundamental_data.get('pe_ratio', 0.0)),
                    'pb_ratio': float(fundamental_data.get('pb_ratio', 0.0)),
                    'roe': float(fundamental_data.get('roe', 0.0))
                }
            return {}
        except Exception:
            return {}
    
    async def _save_dataset(self, dataset: TrainingDataset) -> None:
        """保存数据集到磁盘"""
        try:
            # 转换为 DataFrame
            data_rows = []
            for sample in dataset.samples:
                row = {
                    'stock_code': sample.stock_code,
                    'stock_name': sample.stock_name,
                    'label': sample.label,
                    'timestamp': sample.timestamp.isoformat(),
                    'return_5d': sample.return_5d,
                    'return_20d': sample.return_20d,
                    'market_cap': sample.market_cap,
                    'pe_ratio': sample.pe_ratio,
                    'pb_ratio': sample.pb_ratio,
                    'roe': sample.roe
                }
                row.update(sample.features)
                data_rows.append(row)
            
            df = pd.DataFrame(data_rows)
            
            # 保存为 CSV
            file_path = self._data_storage_path / f"{dataset.dataset_id}.csv"
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            
            # 保存元数据
            metadata = {
                'dataset_id': dataset.dataset_id,
                'name': dataset.name,
                'created_at': dataset.created_at.isoformat(),
                'updated_at': dataset.updated_at.isoformat(),
                'feature_columns': dataset.feature_columns,
                'label_column': dataset.label_column,
                'num_samples': len(dataset.samples),
                'metadata': dataset.metadata
            }
            
            metadata_path = self._data_storage_path / f"{dataset.dataset_id}_metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            logger.info(f"数据集已保存: {file_path}")
            
        except Exception as e:
            logger.error(f"保存数据集失败: {e}")
    
    async def load_dataset(self, dataset_id: str) -> Optional[TrainingDataset]:
        """加载数据集
        
        Args:
            dataset_id: 数据集ID
            
        Returns:
            训练数据集
        """
        # 检查缓存
        if dataset_id in self._dataset_cache:
            return self._dataset_cache[dataset_id]
        
        try:
            # 加载元数据
            metadata_path = self._data_storage_path / f"{dataset_id}_metadata.json"
            if not metadata_path.exists():
                logger.warning(f"数据集元数据不存在: {dataset_id}")
                return None
            
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            # 加载数据
            file_path = self._data_storage_path / f"{dataset_id}.csv"
            if not file_path.exists():
                logger.warning(f"数据集文件不存在: {dataset_id}")
                return None
            
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            # 转换为样本
            samples = []
            for _, row in df.iterrows():
                features = {col: row[col] for col in metadata['feature_columns'] if col in row}
                
                sample = TrainingDataSample(
                    stock_code=row['stock_code'],
                    stock_name=row['stock_name'],
                    features=features,
                    label=row['label'],
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    return_5d=row['return_5d'],
                    return_20d=row['return_20d'],
                    market_cap=row['market_cap'],
                    pe_ratio=row['pe_ratio'],
                    pb_ratio=row['pb_ratio'],
                    roe=row['roe']
                )
                samples.append(sample)
            
            # 创建数据集
            dataset = TrainingDataset(
                dataset_id=metadata['dataset_id'],
                name=metadata['name'],
                samples=samples,
                created_at=datetime.fromisoformat(metadata['created_at']),
                updated_at=datetime.fromisoformat(metadata['updated_at']),
                feature_columns=metadata['feature_columns'],
                label_column=metadata['label_column'],
                metadata=metadata.get('metadata', {})
            )
            
            # 缓存数据集
            self._dataset_cache[dataset_id] = dataset
            
            logger.info(f"数据集已加载: {len(samples)} 个样本")
            
            return dataset
            
        except Exception as e:
            logger.error(f"加载数据集失败: {e}")
            return None
    
    def dataset_to_dataframe(self, dataset: TrainingDataset) -> Tuple[pd.DataFrame, pd.Series]:
        """将数据集转换为 DataFrame
        
        Args:
            dataset: 训练数据集
            
        Returns:
            (特征DataFrame, 标签Series)
        """
        data_rows = []
        labels = []
        
        for sample in dataset.samples:
            row = sample.features.copy()
            data_rows.append(row)
            labels.append(sample.label)
        
        X = pd.DataFrame(data_rows)
        y = pd.Series(labels)
        
        return X, y
    
    def get_dataset_statistics(self, dataset: TrainingDataset) -> Dict[str, Any]:
        """获取数据集统计信息
        
        Args:
            dataset: 训练数据集
            
        Returns:
            统计信息字典
        """
        labels = [sample.label for sample in dataset.samples]
        
        positive_count = sum(1 for label in labels if label == 1.0)
        negative_count = sum(1 for label in labels if label == 0.0)
        
        return {
            'total_samples': len(dataset.samples),
            'positive_samples': positive_count,
            'negative_samples': negative_count,
            'positive_ratio': positive_count / len(labels) if labels else 0.0,
            'negative_ratio': negative_count / len(labels) if labels else 0.0,
            'feature_count': len(dataset.feature_columns),
            'created_at': dataset.created_at.isoformat(),
            'updated_at': dataset.updated_at.isoformat()
        }
    
    def shutdown(self):
        """关闭数据收集器"""
        if self._executor:
            self._executor.shutdown(wait=True)
        logger.info("训练数据收集器已关闭")


# 便捷函数
def get_training_data_collector() -> Optional[TrainingDataCollector]:
    """获取训练数据收集器实例"""
    try:
        container = get_service_container()
        if container and container.is_registered(TrainingDataCollector):
            return container.resolve(TrainingDataCollector)
        return None
    except Exception as e:
        logger.error(f"获取训练数据收集器失败: {e}")
        return None
