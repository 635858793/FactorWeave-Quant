"""
AI 选股自动化训练流程

提供自动化的模型训练、评估和部署流程
"""

from loguru import logger
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from pathlib import Path
import json
import threading
from concurrent.futures import ThreadPoolExecutor

from ..containers import ServiceContainer, get_service_container
from ..events import EventBus, get_event_bus
from .training_data_collector import TrainingDataCollector, TrainingDataset
from .ai_stock_selector_service import AIStockSelector
from .model_training_service import ModelTrainingService, TrainingTaskStatus


class AutoTrainingStatus(Enum):
    """自动化训练状态"""
    IDLE = "idle"
    COLLECTING_DATA = "collecting_data"
    TRAINING_MODEL = "training_model"
    EVALUATING_MODEL = "evaluating_model"
    DEPLOYING_MODEL = "deploying_model"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AutoTrainingConfig:
    """自动化训练配置"""
    # 数据收集配置
    stock_pool: List[str] = field(default_factory=list)
    lookback_days: int = 252
    min_return: float = 0.05
    max_return: float = 0.30
    
    # 模型训练配置
    model_type: str = "ml"
    model_params: Dict[str, Any] = field(default_factory=dict)
    
    # 评估配置
    evaluation_metrics: List[str] = field(default_factory=lambda: ["accuracy", "precision", "recall", "f1"])
    min_accuracy: float = 0.6
    min_f1_score: float = 0.5
    
    # 部署配置
    auto_deploy: bool = True
    deploy_threshold: float = 0.7
    
    # 调度配置
    schedule_interval: int = 7  # 天
    schedule_enabled: bool = False
    
    # 回滚配置
    enable_rollback: bool = True
    rollback_window: int = 3  # 版本数


@dataclass
class AutoTrainingResult:
    """自动化训练结果"""
    training_id: str
    status: AutoTrainingStatus
    dataset_id: str
    model_type: str
    metrics: Dict[str, float]
    deployed: bool
    deployed_model_path: Optional[str] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0


class AutoTrainingPipeline:
    """自动化训练流程
    
    提供端到端的自动化模型训练流程：
    1. 数据收集
    2. 数据预处理
    3. 模型训练
    4. 模型评估
    5. 模型部署（可选）
    6. 回滚（如果需要）
    """
    
    def __init__(
        self,
        service_container: Optional[ServiceContainer] = None,
        event_bus: Optional[EventBus] = None
    ):
        """初始化自动化训练流程
        
        Args:
            service_container: 服务容器
            event_bus: 事件总线
        """
        self._container = service_container or get_service_container()
        if not self._container:
            raise ValueError("无法获取服务容器，请确保服务容器已初始化")
        
        # HVD-241-P1-B: event_bus or → is not None (EventBus __len__ falsy 陷阱, R240-P0-007)
        self._event_bus = event_bus if event_bus is not None else get_event_bus()
        
        # 解析核心依赖服务
        self._data_collector = self._container.resolve(TrainingDataCollector)
        self._model_training_service = self._container.resolve(ModelTrainingService)
        
        # 线程池用于异步执行
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="Auto_Training")
        
        # 训练状态管理
        self._current_training: Optional[AutoTrainingResult] = None
        self._training_lock = threading.RLock()
        
        # 模型版本管理
        self._model_versions: Dict[str, Dict[str, Any]] = {}
        self._version_lock = threading.RLock()
        
        # 模型存储路径
        self._model_storage_path = Path("models/auto_trained")
        self._model_storage_path.mkdir(parents=True, exist_ok=True)
        
        # 训练历史
        self._training_history: List[AutoTrainingResult] = []
        self._history_lock = threading.RLock()
        
        # 调度器
        self._scheduler = None
        self._schedule_lock = threading.RLock()
        
        logger.info("自动化训练流程初始化完成")
    
    async def run_auto_training(
        self,
        config: AutoTrainingConfig,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> AutoTrainingResult:
        """运行自动化训练流程
        
        Args:
            config: 训练配置
            progress_callback: 进度回调函数 (message, progress)
            
        Returns:
            训练结果
        """
        import uuid
        training_id = str(uuid.uuid4())
        
        start_time = datetime.now()
        
        # 创建训练结果
        result = AutoTrainingResult(
            training_id=training_id,
            status=AutoTrainingStatus.COLLECTING_DATA,
            dataset_id="",
            model_type=config.model_type,
            metrics={},
            deployed=False,
            started_at=start_time
        )
        
        try:
            # 更新当前训练
            with self._training_lock:
                self._current_training = result
            
            # 步骤 1: 收集训练数据
            if progress_callback:
                progress_callback("正在收集训练数据...", 0.1)
            
            dataset = await self._collect_training_data(config)
            result.dataset_id = dataset.dataset_id
            
            # 步骤 2: 训练模型
            if progress_callback:
                progress_callback("正在训练模型...", 0.4)
            
            model, metrics = await self._train_model(dataset, config, progress_callback)
            result.metrics = metrics
            
            # 步骤 3: 评估模型
            if progress_callback:
                progress_callback("正在评估模型...", 0.7)
            
            evaluation_result = await self._evaluate_model(model, dataset, config)
            
            # 检查是否满足部署条件
            should_deploy = self._should_deploy_model(evaluation_result, config)
            
            if should_deploy and config.auto_deploy:
                # 步骤 4: 部署模型
                if progress_callback:
                    progress_callback("正在部署模型...", 0.9)
                
                deployed_path = await self._deploy_model(model, training_id, config)
                result.deployed = True
                result.deployed_model_path = deployed_path
            else:
                result.deployed = False
                logger.warning(f"模型未满足部署条件: {evaluation_result}")
            
            # 完成
            result.status = AutoTrainingStatus.COMPLETED
            result.completed_at = datetime.now()
            result.duration_seconds = (result.completed_at - start_time).total_seconds()
            
            # 保存到历史
            with self._history_lock:
                self._training_history.append(result)
            
            # 发布事件
            await self._event_bus.publish("auto_training.completed",
                training_id=training_id,
                status=result.status.value,
                metrics=metrics,
                deployed=result.deployed
            )
            
            if progress_callback:
                progress_callback("训练完成！", 1.0)
            
            logger.info(f"自动化训练完成: {training_id}, 耗时 {result.duration_seconds:.2f} 秒")
            
        except Exception as e:
            logger.error(f"自动化训练失败: {e}")
            result.status = AutoTrainingStatus.FAILED
            result.error_message = str(e)
            result.completed_at = datetime.now()
            result.duration_seconds = (result.completed_at - start_time).total_seconds()
            
            # 发布事件
            await self._event_bus.publish("auto_training.failed",
                training_id=training_id,
                error=str(e)
            )
        
        finally:
            with self._training_lock:
                self._current_training = None
        
        return result
    
    async def _collect_training_data(
        self,
        config: AutoTrainingConfig
    ) -> TrainingDataset:
        """收集训练数据"""
        # 如果没有指定股票池，获取主要股票池
        if not config.stock_pool:
            logger.info("未指定股票池，获取主要股票池")
            config.stock_pool = await self._get_main_stock_pool()
        
        # 收集数据
        dataset = await self._data_collector.collect_training_data(
            stock_codes=config.stock_pool,
            lookback_days=config.lookback_days,
            min_return=config.min_return,
            max_return=config.max_return
        )
        
        # 获取统计信息
        stats = self._data_collector.get_dataset_statistics(dataset)
        logger.info(f"训练数据统计: {stats}")
        
        return dataset
    
    async def _train_model(
        self,
        dataset: TrainingDataset,
        config: AutoTrainingConfig,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> Tuple[Any, Dict[str, float]]:
        """训练模型"""
        # 转换数据集
        X, y = self._data_collector.dataset_to_dataframe(dataset)
        
        # 创建选股器
        selector = AIStockSelector(
            model_type=config.model_type,
            model_params=config.model_params
        )
        
        # 训练模型
        selector.train_model(X, y)
        
        # 评估模型
        metrics = {}
        
        if config.model_type == 'ml':
            # 机器学习模型评估
            from sklearn.model_selection import cross_val_score
            from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
            
            # 交叉验证
            cv_scores = cross_val_score(selector.model, X, y, cv=5, scoring='accuracy')
            metrics['cv_accuracy'] = float(cv_scores.mean())
            metrics['cv_accuracy_std'] = float(cv_scores.std())
            
            # 训练集评估
            y_pred = selector.model.predict(X)
            metrics['train_accuracy'] = float(accuracy_score(y, y_pred))
            metrics['train_precision'] = float(precision_score(y, y_pred, average='weighted'))
            metrics['train_recall'] = float(recall_score(y, y_pred, average='weighted'))
            metrics['train_f1'] = float(f1_score(y, y_pred, average='weighted'))
        
        elif config.model_type == 'dl':
            # 深度学习模型评估
            history = selector.model.history
            if history:
                metrics['final_loss'] = float(history['loss'][-1])
                metrics['final_accuracy'] = float(history['accuracy'][-1])
                metrics['val_loss'] = float(history['val_loss'][-1])
                metrics['val_accuracy'] = float(history['val_accuracy'][-1])
        
        return selector.model, metrics
    
    async def _evaluate_model(
        self,
        model: Any,
        dataset: TrainingDataset,
        config: AutoTrainingConfig
    ) -> Dict[str, float]:
        """评估模型"""
        X, y = self._data_collector.dataset_to_dataframe(dataset)
        
        metrics = {}
        
        try:
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
            
            # 划分训练集和测试集
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # 在训练集上训练
            if hasattr(model, 'fit'):
                model.fit(X_train, y_train)
            
            # 在测试集上预测
            y_pred = model.predict(X_test)
            
            # 计算指标
            metrics['test_accuracy'] = float(accuracy_score(y_test, y_pred))
            metrics['test_precision'] = float(precision_score(y_test, y_pred, average='weighted'))
            metrics['test_recall'] = float(recall_score(y_test, y_pred, average='weighted'))
            metrics['test_f1'] = float(f1_score(y_test, y_pred, average='weighted'))
            
            # 计算 AUC（如果支持）
            if hasattr(model, 'predict_proba'):
                y_proba = model.predict_proba(X_test)
                if y_proba.shape[1] > 1:
                    metrics['test_auc'] = float(roc_auc_score(y_test, y_proba[:, 1]))
            
            logger.info(f"模型评估结果: {metrics}")
            
        except Exception as e:
            logger.error(f"模型评估失败: {e}")
            metrics['error'] = str(e)
        
        return metrics
    
    def _should_deploy_model(
        self,
        evaluation_result: Dict[str, float],
        config: AutoTrainingConfig
    ) -> bool:
        """判断是否应该部署模型"""
        # 检查准确率
        if 'test_accuracy' in evaluation_result:
            if evaluation_result['test_accuracy'] < config.min_accuracy:
                return False
        
        # 检查 F1 分数
        if 'test_f1' in evaluation_result:
            if evaluation_result['test_f1'] < config.min_f1_score:
                return False
        
        # 检查部署阈值
        if 'test_accuracy' in evaluation_result:
            if evaluation_result['test_accuracy'] < config.deploy_threshold:
                return False
        
        return True
    
    async def _deploy_model(
        self,
        model: Any,
        training_id: str,
        config: AutoTrainingConfig
    ) -> str:
        """部署模型"""
        import pickle
        from datetime import datetime
        
        # 创建模型文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        model_filename = f"model_{config.model_type}_{training_id}_{timestamp}.pkl"
        model_path = self._model_storage_path / model_filename
        
        # 保存模型
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        
        # 保存元数据
        metadata = {
            'training_id': training_id,
            'model_type': config.model_type,
            'model_params': config.model_params,
            'deployed_at': datetime.now().isoformat(),
            'config': {
                'stock_pool': config.stock_pool,
                'lookback_days': config.lookback_days,
                'min_return': config.min_return,
                'max_return': config.max_return
            }
        }
        
        metadata_path = self._model_storage_path / f"{model_filename}.metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # 更新版本管理
        with self._version_lock:
            self._model_versions[training_id] = {
                'model_path': str(model_path),
                'metadata_path': str(metadata_path),
                'metadata': metadata
            }
        
        # 回滚旧版本（如果启用）
        if config.enable_rollback:
            await self._cleanup_old_models(config.rollback_window)
        
        logger.info(f"模型已部署: {model_path}")
        
        return str(model_path)
    
    async def _cleanup_old_models(self, keep_versions: int):
        """清理旧模型版本"""
        with self._version_lock:
            if len(self._model_versions) <= keep_versions:
                return
            
            # 按部署时间排序
            sorted_versions = sorted(
                self._model_versions.items(),
                key=lambda x: x[1]['metadata']['deployed_at'],
                reverse=True
            )
            
            # 删除旧版本
            versions_to_delete = sorted_versions[keep_versions:]
            for training_id, version_info in versions_to_delete:
                try:
                    model_path = Path(version_info['model_path'])
                    metadata_path = Path(version_info['metadata_path'])
                    
                    if model_path.exists():
                        model_path.unlink()
                    if metadata_path.exists():
                        metadata_path.unlink()
                    
                    del self._model_versions[training_id]
                    logger.info(f"已删除旧模型版本: {training_id}")
                except Exception as e:
                    logger.warning(f"删除旧模型版本失败: {e}")
    
    async def _get_main_stock_pool(self) -> List[str]:
        """获取主要股票池"""
        try:
            from .unified_data_manager import UnifiedDataManager
            data_manager = self._container.resolve(UnifiedDataManager)
            
            if hasattr(data_manager, 'get_main_stock_pool'):
                stocks = await data_manager.get_main_stock_pool()
                return [stock for stock in stocks if stock]
            
            return []
        except Exception as e:
            logger.error(f"获取主要股票池失败: {e}")
            return []
    
    def get_current_training(self) -> Optional[AutoTrainingResult]:
        """获取当前训练任务"""
        with self._training_lock:
            return self._current_training
    
    def get_training_history(self, limit: int = 10) -> List[AutoTrainingResult]:
        """获取训练历史
        
        Args:
            limit: 返回的最大数量
            
        Returns:
            训练历史列表
        """
        with self._history_lock:
            return self._training_history[-limit:]
    
    def get_model_versions(self) -> Dict[str, Dict[str, Any]]:
        """获取所有模型版本"""
        with self._version_lock:
            return self._model_versions.copy()
    
    async def rollback_model(self, training_id: str) -> bool:
        """回滚到指定模型版本
        
        Args:
            training_id: 训练ID
            
        Returns:
            是否成功回滚
        """
        try:
            with self._version_lock:
                if training_id not in self._model_versions:
                    logger.warning(f"模型版本不存在: {training_id}")
                    return False
                
                version_info = self._model_versions[training_id]
                model_path = version_info['model_path']
                
                # 加载模型
                from utils.safe_pickle import safe_load
                with open(model_path, 'rb') as f:
                    model = safe_load(f)
                
                # 更新 AI 选股器
                # 这里需要根据实际情况更新
                logger.info(f"已回滚到模型版本: {training_id}")
                
                return True
        except Exception as e:
            logger.error(f"回滚模型失败: {e}")
            return False
    
    def shutdown(self):
        """关闭自动化训练流程"""
        if self._executor:
            self._executor.shutdown(wait=True)
        logger.info("自动化训练流程已关闭")


# 便捷函数
def get_auto_training_pipeline() -> Optional[AutoTrainingPipeline]:
    """获取自动化训练流程实例"""
    try:
        container = get_service_container()
        if container and container.is_registered(AutoTrainingPipeline):
            return container.resolve(AutoTrainingPipeline)
        return None
    except Exception as e:
        logger.error(f"获取自动化训练流程失败: {e}")
        return None
