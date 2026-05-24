"""
模型训练服务

提供完整的模型训练管理功能，包括：
- 训练任务创建、执行、监控
- 模型评估
- 模型版本管理（完整功能）
"""

from dataclasses import dataclass
from loguru import logger
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
import json
import math
import pickle
from utils.safe_pickle import safe_loads
import shutil
import threading
from enum import Enum

from .base_service import BaseService
from ..containers import ServiceContainer, get_service_container
from ..events import EventBus, get_event_bus
from utils.imports import get_sklearn, np, pd, safe_import, sklearn_metrics


class TrainingTaskStatus(Enum):
    """训练任务状态"""
    PENDING = "pending"          # 待启动
    PREPARING = "preparing"      # 准备中
    TRAINING = "training"        # 训练中
    EVALUATING = "evaluating"    # 评估中
    COMPLETED = "completed"      # 已完成
    PAUSED = "paused"            # 已暂停
    FAILED = "failed"            # 已失败
    CANCELLED = "cancelled"       # 已取消


@dataclass
class IncrementalTrainingModel:
    """
    统一的增量训练模型封装，负责管理预处理器与基础估计器。
    """

    model_type: str
    estimator: Any
    is_classifier: bool
    is_incremental: bool
    classes: Optional[Any] = None
    imputer: Optional[Any] = None
    scaler: Optional[Any] = None
    trained_epochs: int = 0
    imputer_fitted: bool = False
    scaler_fitted: bool = False

    def __init__(self, model_type: str, estimator: Any, is_classifier: bool,
                 classes: Optional[Any] = None, imputer: Optional[Any] = None,
                 scaler: Optional[Any] = None, is_incremental: bool = True):
        """初始化模型封装器"""
        self.model_type = model_type
        self.estimator = estimator
        self.is_classifier = is_classifier
        self.is_incremental = is_incremental
        self.classes = classes
        self.imputer = imputer
        self.scaler = scaler
        self.trained_epochs = 0
        self.imputer_fitted = False
        self.scaler_fitted = False

    def _ensure_numpy(self, data: Any, dtype: Any = None) -> Any:
        if np is None:
            raise RuntimeError("NumPy不可用，无法执行模型训练")
        if data is None:
            raise ValueError("训练数据为空")
        array = np.asarray(data, dtype=dtype)
        if array.ndim == 1:
            array = array.reshape(-1, 1)
        return array

    def _prepare_features(self, features: Any, train_mode: bool = True) -> Any:
        X = self._ensure_numpy(features, dtype=np.float32)

        if self.imputer:
            if not self.imputer_fitted:
                if train_mode:
                    self.imputer.fit(X)
                    self.imputer_fitted = True
                else:
                    raise RuntimeError("Imputer尚未拟合，无法进行推理")
            X = self.imputer.transform(X)

        if self.scaler:
            if not self.scaler_fitted:
                if train_mode:
                    if self.is_incremental:
                        self.scaler.partial_fit(X)
                    else:
                        self.scaler.fit(X)
                    self.scaler_fitted = True
                else:
                    raise RuntimeError("Scaler尚未拟合，无法进行推理")
            elif train_mode:
                if self.is_incremental:
                    self.scaler.partial_fit(X)

            X = self.scaler.transform(X)

        return X

    def _prepare_targets(self, targets: Any) -> Any:
        target_dtype = np.int32 if self.is_classifier else np.float32
        y = self._ensure_numpy(targets, dtype=target_dtype).ravel()
        return y

    def fit(self, features: Any, targets: Any) -> float:
        """
        执行一次性完整训练（非增量），并返回该批次的损失指标。
        适用于不支持增量学习的模型（如RandomForest, XGBoost, LightGBM等）。
        """
        X = self._prepare_features(features, train_mode=True)
        y = self._prepare_targets(targets)

        if self.is_classifier:
            classes = self.classes
            if classes is None:
                classes = np.unique(y)
            self.estimator.fit(X, y)
        else:
            self.estimator.fit(X, y)

        self.trained_epochs += 1

        predictions = self.estimator.predict(X)
        if self.is_classifier:
            accuracy = float((predictions == y).mean())
            return max(0.0, 1.0 - accuracy)

        mse = float(np.mean((predictions - y) ** 2))
        return mse

    def partial_fit(self, features: Any, targets: Any) -> float:
        """
        对单个epoch执行训练，根据is_incremental选择增量或一次性训练方式。
        """
        if not self.is_incremental:
            return self.fit(features, targets)

        X = self._prepare_features(features, train_mode=True)
        y = self._prepare_targets(targets)

        if self.is_classifier:
            classes = self.classes
            if classes is None:
                classes = np.unique(y)

            if self.trained_epochs == 0:
                self.estimator.partial_fit(X, y, classes=classes)
            else:
                self.estimator.partial_fit(X, y)
        else:
            self.estimator.partial_fit(X, y)

        self.trained_epochs += 1

        predictions = self.estimator.predict(X)
        if self.is_classifier:
            accuracy = float((predictions == y).mean())
            return max(0.0, 1.0 - accuracy)

        mse = float(np.mean((predictions - y) ** 2))
        return mse

    def transform_features(self, features: Any) -> Any:
        """对推理阶段的特征进行转换（不再更新统计量）"""
        return self._prepare_features(features, train_mode=False)

    def predict(self, features: Any) -> Any:
        """使用训练好的模型进行预测"""
        X = self.transform_features(features)
        return self.estimator.predict(X)

    def predict_proba(self, features: Any) -> Optional[Any]:
        if not self.is_classifier:
            return None
        X = self.transform_features(features)
        if hasattr(self.estimator, "predict_proba"):
            return self.estimator.predict_proba(X)
        return None


class ModelTrainingService(BaseService):
    """模型训练服务"""

    def __init__(self, service_container: Optional[ServiceContainer] = None,
                 event_bus: Optional[EventBus] = None):
        """
        初始化模型训练服务

        Args:
            service_container: 服务容器
            event_bus: 事件总线
        """
        super().__init__(event_bus)
        self._service_container = service_container or get_service_container()

        # 训练任务管理
        self._training_tasks: Dict[str, Dict[str, Any]] = {}
        self._task_lock = threading.RLock()

        # 模型版本管理
        self._model_versions: Dict[str, Dict[str, Any]] = {}
        self._version_lock = threading.RLock()

        # 训练线程管理
        self._training_threads: Dict[str, Any] = {}
        self._thread_lock = threading.RLock()

        # 训练日志管理
        self._training_logs: List[Dict[str, Any]] = []
        self._training_lock = threading.RLock()

        # 数据库服务（延迟获取）
        self._database_service = None

        # 机器学习依赖缓存
        self._ml_dependencies: Optional[Dict[str, Any]] = None

        # 模型存储路径
        self._model_storage_path = Path("models/trained")
        self._checkpoint_storage_path = Path("models/checkpoints")
        self._model_storage_path.mkdir(parents=True, exist_ok=True)
        self._checkpoint_storage_path.mkdir(parents=True, exist_ok=True)

        # 训练元数据存储
        self._metadata_storage_path = Path("data/training_metadata")
        self._metadata_storage_path.mkdir(parents=True, exist_ok=True)

        logger.info("ModelTrainingService initialized")

    def _do_initialize(self) -> None:
        """执行具体的初始化逻辑"""
        try:
            logger.info("Initializing ModelTrainingService...")

            # 获取数据库服务（可选）
            try:
                from .database_service import DatabaseService
                if self._service_container.is_registered(DatabaseService):
                    self._database_service = self._service_container.resolve(DatabaseService)
                    logger.info("DatabaseService已注册并已获取")
                else:
                    logger.warning("DatabaseService未在容器中注册，将使用直接数据库连接")
            except Exception as e:
                logger.warning(f"无法获取DatabaseService: {e}，将使用直接数据库连接")

            # 初始化数据库表
            self._initialize_database_tables()

            # 加载现有任务和版本
            self._load_existing_tasks()
            self._load_existing_versions()

            logger.info("ModelTrainingService initialized successfully")

        except Exception as e:
            logger.error(f"ModelTrainingService初始化失败: {e}")
            raise

    def _initialize_database_tables(self) -> None:
        """初始化数据库表结构"""
        try:
            if self._database_service:
                # 表已由DatabaseService统一创建，无需重复创建
                logger.info("模型训练相关表已由DatabaseService统一管理")
            else:
                logger.warning("DatabaseService不可用，但表结构应在初始化时已创建")

            logger.info("数据库表初始化完成")
        except Exception as e:
            logger.error(f"数据库表初始化失败: {e}")
            raise

    def _load_existing_tasks(self) -> None:
        """加载现有的训练任务"""
        try:
            if self._database_service:
                with self._database_service.get_connection("strategy_sqlite") as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM training_tasks")
                    rows = cursor.fetchall()

                    for row in rows:
                        task_id = row[0]
                        self._training_tasks[task_id] = {
                            'task_id': task_id,
                            'task_name': row[1],
                            'task_description': row[2],
                            'model_type': row[3],
                            'status': row[4],
                            'config': json.loads(row[5]) if row[5] else {},
                            'progress': row[6] or 0.0,
                            'error_message': row[7],
                            'created_at': row[8],
                            'updated_at': row[9],
                            'started_at': row[10],
                            'completed_at': row[11],
                            'training_metadata': self._load_training_metadata(task_id)
                        }
            logger.info(f"加载了 {len(self._training_tasks)} 个现有训练任务")
        except Exception as e:
            logger.error(f"加载现有训练任务失败: {e}")
            raise

    def _get_metadata_file(self, task_id: str) -> Path:
        return self._metadata_storage_path / f"{task_id}.json"

    def _persist_training_metadata(self, task_id: str, metadata: Dict[str, Any]) -> None:
        try:
            metadata_path = self._get_metadata_file(task_id)
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存训练元数据失败({task_id}): {e}")

    def _load_training_metadata(self, task_id: str) -> Dict[str, Any]:
        try:
            metadata_path = self._get_metadata_file(task_id)
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"加载训练元数据失败({task_id}): {e}")
        return {
            'val_history': [],
            'best_val_loss': None,
            'best_epoch': None
        }

    def _load_existing_versions(self) -> None:
        """加载现有的模型版本"""
        try:
            if self._database_service:
                with self._database_service.get_connection("strategy_sqlite") as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM model_versions")
                    rows = cursor.fetchall()

                    for row in rows:
                        version_id = row[0]
                        self._model_versions[version_id] = {
                            'version_id': version_id,
                            'version_number': row[1],
                            'model_type': row[2],
                            'model_file_path': row[3],
                            'training_task_id': row[4],
                            'performance_metrics': json.loads(row[5]) if row[5] else {},
                            'config': json.loads(row[6]) if row[6] else {},
                            'is_current': bool(row[7]),
                            'created_at': row[8],
                            'created_by': row[9],
                            'description': row[10]
                        }
                        metrics = self._model_versions[version_id]['performance_metrics']
                        training_meta = metrics.get('training_metadata') if isinstance(metrics, dict) else {}
                        if not training_meta and isinstance(metrics, dict):
                            validation_curve = metrics.get('validation_curve', [])
                            if validation_curve:
                                training_meta = {'val_history': validation_curve}
                        self._model_versions[version_id]['training_metadata'] = training_meta or {}
                        metrics = self._model_versions[version_id]['performance_metrics']
                        training_meta = metrics.get('training_metadata') if isinstance(metrics, dict) else {}
                        if not training_meta and isinstance(metrics, dict):
                            validation_curve = metrics.get('validation_curve', [])
                            if validation_curve:
                                training_meta = {'val_history': validation_curve}
                        self._model_versions[version_id]['training_metadata'] = training_meta or {}

            logger.info(f"加载了 {len(self._model_versions)} 个现有模型版本")
        except Exception as e:
            logger.error(f"加载现有模型版本失败: {e}")
            raise

    def create_training_task(self, task_name: str, model_type: str,
                             config: Dict[str, Any],
                             task_description: str = "") -> str:
        """
        创建训练任务

        Args:
            task_name: 任务名称
            model_type: 模型类型
            config: 训练配置
            task_description: 任务描述

        Returns:
            任务ID
        """
        try:
            import uuid
            task_id = str(uuid.uuid4())

            task_data = {
                'task_id': task_id,
                'task_name': task_name,
                'task_description': task_description,
                'model_type': model_type,
                'status': TrainingTaskStatus.PENDING.value,
                'config': config,
                'progress': 0.0,
                'error_message': None,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'started_at': None,
                'completed_at': None,
                'training_metadata': self._load_training_metadata(task_id)
            }

            with self._task_lock:
                self._training_tasks[task_id] = task_data

            # 保存到数据库
            self._save_task_to_database(task_data)

            # 发布事件
            self._event_bus.publish("training.task.created", task_id=task_id, task_name=task_name)

            logger.info(f"创建训练任务成功: {task_id} - {task_name}")
            return task_id

        except Exception as e:
            logger.error(f"创建训练任务失败: {e}")
            raise

    def _save_task_to_database(self, task_data: Dict[str, Any]) -> None:
        """保存任务到数据库"""
        try:
            if self._database_service:
                with self._database_service.get_connection("strategy_sqlite") as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO training_tasks 
                        (task_id, task_name, task_description, model_type, status, 
                         config_json, progress, error_message, created_at, updated_at,
                         started_at, completed_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        task_data['task_id'],
                        task_data['task_name'],
                        task_data['task_description'],
                        task_data['model_type'],
                        task_data['status'],
                        json.dumps(task_data['config']),
                        task_data['progress'],
                        task_data['error_message'],
                        task_data['created_at'],
                        task_data['updated_at'],
                        task_data['started_at'],
                        task_data['completed_at']
                    ))
                    conn.commit()
        except Exception as e:
            logger.error(f"保存任务到数据库失败: {e}")
            raise

    def get_training_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取训练任务信息

        Args:
            task_id: 任务ID

        Returns:
            任务信息字典，如果不存在返回None
        """
        with self._task_lock:
            return self._training_tasks.get(task_id)

    def get_all_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取所有训练任务

        Args:
            status: 可选的状态筛选

        Returns:
            任务列表
        """
        with self._task_lock:
            tasks = list(self._training_tasks.values())
            if status:
                tasks = [t for t in tasks if t['status'] == status]
            return tasks

    def update_task_status(self, task_id: str, status: TrainingTaskStatus,
                           progress: Optional[float] = None,
                           error_message: Optional[str] = None) -> None:
        """
        更新任务状态

        Args:
            task_id: 任务ID
            status: 新状态
            progress: 进度（0-100）
            error_message: 错误信息
        """
        try:
            with self._task_lock:
                if task_id not in self._training_tasks:
                    raise ValueError(f"任务不存在: {task_id}")

                task = self._training_tasks[task_id]
                task['status'] = status.value
                task['updated_at'] = datetime.now().isoformat()

                if progress is not None:
                    task['progress'] = progress

                if error_message:
                    task['error_message'] = error_message

                if status == TrainingTaskStatus.TRAINING and not task['started_at']:
                    task['started_at'] = datetime.now().isoformat()

                if status in [TrainingTaskStatus.COMPLETED, TrainingTaskStatus.FAILED, TrainingTaskStatus.CANCELLED]:
                    task['completed_at'] = datetime.now().isoformat()

            # 更新数据库
            self._save_task_to_database(task)

            # 发布事件
            self._event_bus.publish("training.task.status_changed",
                                    task_id=task_id,
                                    status=status.value,
                                    progress=progress)

            logger.debug(f"更新任务状态: {task_id} -> {status.value}")

        except Exception as e:
            logger.error(f"更新任务状态失败: {e}")
            raise

    def create_model_version(self, version_number: str, model_type: str,
                             model_file_path: str, training_task_id: Optional[str] = None,
                             performance_metrics: Optional[Dict[str, Any]] = None,
                             config: Optional[Dict[str, Any]] = None,
                             description: str = "",
                             training_metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        创建模型版本

        Args:
            version_number: 版本号
            model_type: 模型类型
            model_file_path: 模型文件路径
            training_task_id: 关联的训练任务ID
            performance_metrics: 性能指标
            config: 模型配置
            description: 版本描述

        Returns:
            版本ID
        """
        try:
            import uuid
            version_id = str(uuid.uuid4())

            metrics_payload = performance_metrics or {}
            if training_metadata:
                metrics_payload.setdefault('training_metadata', training_metadata)
                metrics_payload.setdefault('validation_curve', training_metadata.get('val_history', []))

            version_data = {
                'version_id': version_id,
                'version_number': version_number,
                'model_type': model_type,
                'model_file_path': str(model_file_path),
                'training_task_id': training_task_id,
                'performance_metrics': metrics_payload,
                'config': config or {},
                'is_current': False,
                'created_at': datetime.now().isoformat(),
                'created_by': None,  # 可以后续添加用户信息
                'description': description,
                'training_metadata': training_metadata or {}
            }

            with self._version_lock:
                # 检查版本号是否已存在
                for v in self._model_versions.values():
                    if v['version_number'] == version_number:
                        raise ValueError(f"版本号已存在: {version_number}")

                self._model_versions[version_id] = version_data

            # 保存到数据库
            self._save_version_to_database(version_data)

            # 发布事件
            self._event_bus.publish("model.version.created",
                                    version_id=version_id,
                                    version_number=version_number)

            logger.info(f"创建模型版本成功: {version_id} - {version_number}")
            return version_id

        except Exception as e:
            logger.error(f"创建模型版本失败: {e}")
            raise

    def _save_version_to_database(self, version_data: Dict[str, Any]) -> None:
        """保存版本到数据库"""
        try:
            if self._database_service:
                with self._database_service.get_connection("strategy_sqlite") as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO model_versions 
                        (version_id, version_number, model_type, model_file_path,
                         training_task_id, performance_metrics_json, config_json,
                         is_current, created_at, created_by, description)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        version_data['version_id'],
                        version_data['version_number'],
                        version_data['model_type'],
                        version_data['model_file_path'],
                        version_data['training_task_id'],
                        json.dumps(version_data['performance_metrics']),
                        json.dumps(version_data['config']),
                        1 if version_data['is_current'] else 0,
                        version_data['created_at'],
                        version_data['created_by'],
                        version_data['description']
                    ))
                    conn.commit()
        except Exception as e:
            logger.error(f"保存版本到数据库失败: {e}")
            raise

    def get_model_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """
        获取模型版本信息

        Args:
            version_id: 版本ID

        Returns:
            版本信息字典，如果不存在返回None
        """
        with self._version_lock:
            return self._model_versions.get(version_id)

    def get_all_versions(self, model_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取所有模型版本

        Args:
            model_type: 可选的模型类型筛选

        Returns:
            版本列表
        """
        with self._version_lock:
            versions = list(self._model_versions.values())
            if model_type:
                versions = [v for v in versions if v['model_type'] == model_type]
            return versions

    def set_current_version(self, version_id: str) -> None:
        """
        设置当前版本

        Args:
            version_id: 版本ID
        """
        try:
            with self._version_lock:
                if version_id not in self._model_versions:
                    raise ValueError(f"版本不存在: {version_id}")

                # 取消所有版本的当前标记
                for v in self._model_versions.values():
                    v['is_current'] = False

                # 设置新版本为当前
                self._model_versions[version_id]['is_current'] = True

                # 更新数据库
                self._update_version_current_flag(version_id, True)

            # 发布事件
            self._event_bus.publish("model.version.current_changed",
                                    version_id=version_id)

            logger.info(f"设置当前版本: {version_id}")
            self._activate_model_file(version_id)

        except Exception as e:
            logger.error(f"设置当前版本失败: {e}")
            raise

    def _update_version_current_flag(self, version_id: str, is_current: bool) -> None:
        """更新版本的当前标记"""
        try:
            if self._database_service:
                with self._database_service.get_connection("strategy_sqlite") as conn:
                    cursor = conn.cursor()
                    # 先取消所有版本的当前标记
                    cursor.execute("UPDATE model_versions SET is_current = 0")
                    # 设置指定版本为当前
                    cursor.execute("UPDATE model_versions SET is_current = ? WHERE version_id = ?",
                                   (1 if is_current else 0, version_id))
                    conn.commit()
        except Exception as e:
            logger.error(f"更新版本当前标记失败: {e}")
            raise

    def _activate_model_file(self, version_id: str) -> None:
        """将指定版本的模型文件激活到统一加载路径"""
        try:
            version = self._model_versions.get(version_id)
            if not version:
                return

            source_path = Path(version['model_file_path'])
            if not source_path.exists():
                logger.warning(f"激活模型失败，文件不存在: {source_path}")
                return

            active_dir = self._model_storage_path / "active"
            active_dir.mkdir(parents=True, exist_ok=True)
            dest_path = active_dir / f"{version['model_type']}.pkl"
            shutil.copy2(source_path, dest_path)
            logger.info(f"已激活模型文件: {dest_path}")
        except Exception as e:
            logger.warning(f"激活模型文件失败: {e}")

    def compare_versions(self, version_id1: str, version_id2: str) -> Dict[str, Any]:
        """
        对比两个模型版本

        Args:
            version_id1: 版本1 ID
            version_id2: 版本2 ID

        Returns:
            对比结果字典
        """
        try:
            with self._version_lock:
                v1 = self._model_versions.get(version_id1)
                v2 = self._model_versions.get(version_id2)

                if not v1 or not v2:
                    raise ValueError("版本不存在")

            comparison = {
                'version1': v1,
                'version2': v2,
                'differences': {}
            }

            # 对比性能指标
            metrics1 = v1.get('performance_metrics', {})
            metrics2 = v2.get('performance_metrics', {})

            comparison['differences']['performance'] = {
                'version1': metrics1,
                'version2': metrics2
            }

            # 对比配置
            config1 = v1.get('config', {})
            config2 = v2.get('config', {})

            comparison['differences']['config'] = {
                'version1': config1,
                'version2': config2
            }

            logger.info(f"版本对比完成: {version_id1} vs {version_id2}")
            return comparison

        except Exception as e:
            logger.error(f"版本对比失败: {e}")
            raise

    def rollback_to_version(self, version_id: str) -> None:
        """
        回滚到指定版本

        Args:
            version_id: 目标版本ID
        """
        try:
            with self._version_lock:
                if version_id not in self._model_versions:
                    raise ValueError(f"版本不存在: {version_id}")

            # 设置为目标版本为当前版本
            self.set_current_version(version_id)

            # 发布事件
            self._event_bus.publish("model.version.rolled_back",
                                    version_id=version_id)

            logger.info(f"回滚到版本: {version_id}")

        except Exception as e:
            logger.error(f"版本回滚失败: {e}")
            raise

    def log_training_event(self, task_id: str, log_level: str,
                           log_message: str, log_data: Optional[Dict[str, Any]] = None) -> None:
        """
        记录训练日志

        Args:
            task_id: 任务ID
            log_level: 日志级别
            log_message: 日志消息
            log_data: 日志数据
        """
        try:
            log_entry = {
                'training_task_id': task_id,
                'log_level': log_level,
                'log_message': log_message,
                'log_data': log_data
            }
            with self._training_lock:
                self._training_logs.append(log_entry)
                if len(self._training_logs) > 1000:
                    self._training_logs.pop(0)
            if self._database_service:
                with self._database_service.get_connection("strategy_sqlite") as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO training_logs (training_task_id, log_level, log_message, log_data_json) VALUES (?, ?, ?, ?)", (task_id, log_level, log_message, json.dumps(log_data)))
                    conn.commit()
        except Exception as e:
            logger.error(f"记录训练日志失败: {e}")
            raise

    def start_training(self, task_id: str) -> bool:
        """
        启动训练任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功启动
        """
        try:
            with self._task_lock:
                if task_id not in self._training_tasks:
                    raise ValueError(f"任务不存在: {task_id}")

                task = self._training_tasks[task_id]
                if task['status'] != TrainingTaskStatus.PENDING.value:
                    raise ValueError(f"任务状态不允许启动: {task['status']}")

                # 更新状态为准备中
                self.update_task_status(task_id, TrainingTaskStatus.PREPARING, progress=0.0)

            # 在后台线程中执行训练
            training_thread = threading.Thread(
                target=self._execute_training,
                args=(task_id,),
                daemon=True
            )

            with self._thread_lock:
                self._training_threads[task_id] = training_thread

            training_thread.start()

            logger.info(f"训练任务启动成功: {task_id}")
            return True

        except Exception as e:
            logger.error(f"启动训练任务失败: {e}")
            self.update_task_status(task_id, TrainingTaskStatus.FAILED,
                                    error_message=str(e))
            return False

    def _execute_training(self, task_id: str) -> None:
        """
        执行训练任务（在后台线程中运行）

        Args:
            task_id: 任务ID
        """
        try:
            task = self.get_training_task(task_id)
            if not task:
                raise ValueError(f"任务不存在: {task_id}")

            model_type = task['model_type']
            config = task['config']
            task_metadata = task.setdefault('training_metadata', self._load_training_metadata(task_id))
            task_metadata.setdefault('val_history', [])
            task_metadata.setdefault('best_val_loss', None)
            task_metadata.setdefault('best_epoch', None)
            task_metadata.setdefault('latest_val_loss', None)

            # 更新状态为训练中
            self.update_task_status(task_id, TrainingTaskStatus.TRAINING, progress=5.0)
            self.log_training_event(task_id, "INFO", "开始训练任务")

            # 准备训练数据
            self.log_training_event(task_id, "INFO", "准备训练数据...")
            training_data = self._prepare_training_data(model_type, config)
            self.update_task_status(task_id, TrainingTaskStatus.TRAINING, progress=15.0)

            # 初始化模型
            self.log_training_event(task_id, "INFO", "初始化模型...")
            model = self._initialize_model(model_type, config)
            self.update_task_status(task_id, TrainingTaskStatus.TRAINING, progress=20.0)

            split_data = self._split_training_validation(
                training_data.get('features', np.array([])),
                training_data.get('targets', np.array([])),
                training_data.get('future_returns', np.array([])),
                config
            )
            training_data.update(split_data)
            training_data['training_metadata'] = task_metadata

            train_dataset = {
                'features': training_data.get('train_features'),
                'targets': training_data.get('train_targets')
            }

            best_val_loss = float('inf')
            best_model_state: Optional[bytes] = None
            patience = int(config.get('early_stopping_patience', 5))
            min_delta = float(config.get('early_stopping_min_delta', 1e-4))
            patience_counter = 0
            best_epoch = -1

            # 执行训练循环
            self.log_training_event(task_id, "INFO", "开始训练循环...")
            epochs = config.get('epochs', 10)
            batch_size = config.get('batch_size', 32)

            for epoch in range(epochs):
                if self._should_stop_training(task_id):
                    self.update_task_status(task_id, TrainingTaskStatus.CANCELLED)
                    return

                # 训练一个epoch
                loss = self._train_epoch(model, train_dataset, epoch, batch_size, config)

                # 更新进度
                progress = 20.0 + (epoch + 1) / epochs * 60.0
                self.update_task_status(task_id, TrainingTaskStatus.TRAINING, progress=progress)

                # 记录训练日志
                self.log_training_event(task_id, "INFO", f"Epoch {epoch+1}/{epochs} 完成, Loss: {loss:.4f}",
                                        {'epoch': epoch+1, 'loss': loss})

                # 发布进度事件
                self._event_bus.publish("training.progress_updated",
                                        task_id=task_id,
                                        progress=progress,
                                        epoch=epoch+1,
                                        loss=loss)

                # 验证集监控与早停
                val_loss = self._compute_validation_loss(
                    model,
                    training_data.get('val_features'),
                    training_data.get('val_targets')
                )

                if val_loss is not None:
                    with self._task_lock:
                        task_ref = self._training_tasks.get(task_id, {})
                        metadata = task_ref.setdefault('training_metadata', {})
                        metadata.update({
                            'latest_val_loss': val_loss,
                            'best_val_loss': min(best_val_loss, val_loss),
                            'last_epoch': epoch + 1
                        })
                        history = metadata.setdefault('val_history', [])
                        history.append({
                            'epoch': epoch + 1,
                            'loss': val_loss,
                            'timestamp': datetime.now().isoformat()
                        })

                    improvement = best_val_loss - val_loss
                    if improvement > min_delta:
                        best_val_loss = val_loss
                        best_model_state = pickle.dumps(model)
                        best_epoch = epoch + 1
                        metadata['best_val_loss'] = best_val_loss
                        metadata['best_epoch'] = best_epoch
                        patience_counter = 0
                    else:
                        patience_counter += 1
                        if patience_counter >= patience:
                            self.log_training_event(
                                task_id, "INFO",
                                f"触发早停: patience={patience}, best_epoch={best_epoch or epoch+1}"
                            )
                            break

                    metadata['updated_at'] = datetime.now().isoformat()
                    self._persist_training_metadata(task_id, metadata)

            # 评估模型
            self.update_task_status(task_id, TrainingTaskStatus.EVALUATING, progress=85.0)
            self.log_training_event(task_id, "INFO", "开始模型评估...")

            # Restore best model if needed
            if best_model_state:
                try:
                    model = safe_loads(best_model_state)
                    self.log_training_event(task_id, "INFO", f"加载最佳模型状态(验证Loss={best_val_loss:.6f})")
                except Exception as restore_err:
                    logger.warning(f"恢复最佳模型失败: {restore_err}")
            if best_val_loss < float('inf'):
                task_metadata['best_val_loss'] = best_val_loss
                task_metadata['best_epoch'] = best_epoch
                self._persist_training_metadata(task_id, task_metadata)

            metrics = self.evaluate_model(task_id, model, training_data, config)

            # 保存模型
            self.log_training_event(task_id, "INFO", "保存模型...")
            model_path = self.save_model(task_id, model, model_type, metrics, config)
            self.update_task_status(task_id, TrainingTaskStatus.TRAINING, progress=95.0)

            # 创建模型版本
            version_number = f"{model_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            version_id = self.create_model_version(
                version_number=version_number,
                model_type=model_type,
                model_file_path=model_path,
                training_task_id=task_id,
                performance_metrics=metrics,
                config=config,
                description=f"训练任务 {task['task_name']} 生成的模型",
                training_metadata=task_metadata
            )

            # 完成任务
            self.update_task_status(task_id, TrainingTaskStatus.COMPLETED, progress=100.0)
            self.log_training_event(task_id, "INFO", f"训练任务完成，模型版本: {version_id}")

        except Exception as e:
            logger.error(f"执行训练任务失败: {task_id}, {e}")
            self.update_task_status(task_id, TrainingTaskStatus.FAILED,
                                    error_message=str(e))
            self.log_training_event(task_id, "ERROR", f"训练失败: {str(e)}")

    def _should_stop_training(self, task_id: str) -> bool:
        """检查是否应该停止训练"""
        task = self.get_training_task(task_id)
        if not task:
            return True
        return task['status'] in [TrainingTaskStatus.CANCELLED.value,
                                  TrainingTaskStatus.FAILED.value]

    def _prepare_training_data(self, model_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        准备训练数据：优先使用真实K线数据，不足时生成合成样本。
        """
        try:
            if np is None or pd is None:
                raise ImportError("NumPy/Pandas 未安装，无法构建训练数据集")

            data_config = config.get('data', {})
            symbol = data_config.get('symbol')
            start_date = data_config.get('start_date')
            end_date = data_config.get('end_date')
            horizon = max(1, int(config.get('prediction_horizon', data_config.get('prediction_horizon', 5))))
            min_samples = max(int(config.get('min_samples', 256)), horizon * 3)

            df = None
            if symbol:
                try:
                    from .unified_data_manager import UnifiedDataManager
                    data_manager = self._service_container.resolve(UnifiedDataManager)
                    if data_manager:
                        # 使用get_kdata_from_source方法，支持start_date和end_date参数
                        kdata = data_manager.get_kdata_from_source(
                            stock_code=symbol,
                            start_date=start_date,
                            end_date=end_date,
                            period='D'  # 默认使用日线数据
                        )
                        df = self._convert_to_dataframe(kdata)
                        if df is not None and not df.empty:
                            logger.info(f"成功获取{symbol}的K线数据，记录数: {len(df)}")
                        else:
                            logger.warning(f"获取{symbol}的K线数据为空")
                except Exception as data_err:
                    logger.error(f"从数据管理器获取数据失败: {data_err}", exc_info=True)

            if df is None or len(df.index) < min_samples:
                if symbol:
                    logger.warning(
                        f"获取K线数据失败或数据量不足 "
                        f"(当前:{len(df.index) if df is not None else 0}条, 需要:{min_samples}条) "
                        f"- 符号:{symbol}, 日期范围:{start_date}至{end_date}，"
                        f"真实数据不足，无法训练 {model_type} 模型")
                else:
                    logger.warning(
                        f"未提供股票代码(symbol)，无法获取真实K线数据，"
                        f"无法训练 {model_type} 模型。请在训练配置中提供'data.symbol'参数。")
                empty_features = np.empty((0, 0))
                empty_targets = np.array([])
                return {
                    'kdata': None,
                    'symbol': symbol,
                    'features': empty_features,
                    'targets': empty_targets,
                    'future_returns': empty_targets,
                    'source': 'insufficient_data'
                }

            features, targets, future_returns = self._build_training_matrices(df, model_type, config, horizon)
            return {
                'kdata': df,
                'symbol': symbol,
                'features': features,
                'targets': targets,
                'future_returns': future_returns,
                'source': 'historical'
            }

        except Exception as e:
            logger.error(f"准备训练数据失败: {e}")
            empty_features = np.empty((0, 0)) if np is not None else []
            empty_targets = np.array([]) if np is not None else []
            empty_returns = np.array([]) if np is not None else []
            return {'kdata': None, 'features': empty_features, 'targets': empty_targets,
                    'future_returns': empty_returns, 'source': 'error'}

    def _build_training_matrices(self, df: 'pd.DataFrame', model_type: str,
                                 config: Dict[str, Any], horizon: int) -> Tuple[Any, Any, Any]:
        if pd is None or np is None:
            raise ImportError("NumPy/Pandas 未安装")

        feature_frame = self._extract_features(df, model_type, horizon)
        target_series, future_return_series = self._extract_targets(df, model_type, horizon, config)

        min_len = min(len(feature_frame), len(target_series), len(future_return_series))
        if min_len <= 0:
            raise ValueError("训练样本数量不足，无法训练模型")

        # 对齐特征与目标
        feature_frame = feature_frame.tail(min_len)
        target_series = target_series.tail(min_len)
        future_return_series = future_return_series.tail(min_len)

        features = feature_frame.to_numpy(dtype=np.float32)
        targets = target_series.to_numpy()
        future_returns = future_return_series.to_numpy(dtype=np.float32)
        return features, targets, future_returns

    def _convert_to_dataframe(self, kdata: Any) -> Optional['pd.DataFrame']:
        """将多种K线数据结构转换为标准DataFrame"""
        if pd is None or kdata is None:
            return None

        if isinstance(kdata, pd.DataFrame):
            df = kdata.copy()
        else:
            try:
                df = pd.DataFrame(kdata)
            except Exception:
                return None

        if df.empty:
            return None

        df.columns = [str(col).lower() for col in df.columns]
        required_cols = {'open', 'high', 'low', 'close'}
        if not required_cols.issubset(set(df.columns)):
            logger.warning(f"K线数据缺少必要列: {required_cols - set(df.columns)}")
            return None

        if 'volume' not in df.columns:
            df['volume'] = 0.0

        time_col = next((col for col in ['datetime', 'date', 'time', 'timestamp'] if col in df.columns), None)
        if time_col:
            df = df.sort_values(time_col)

        df = df.reset_index(drop=True)
        return df

    def _generate_synthetic_training_data(self, model_type: str, config: Dict[str, Any]) -> Tuple[Any, Any]:
        logger.warning(f"真实数据不可用，无法为 {model_type} 生成训练数据，返回空结果")
        if np is None:
            return [], []
        return np.empty((0, 0)), np.array([])

    def _split_training_validation(self, features: Any, targets: Any, future_returns: Any,
                                   config: Dict[str, Any]) -> Dict[str, Any]:
        """顺序划分训练/验证集，避免未来信息泄露"""
        if np is None:
            raise RuntimeError("NumPy不可用，无法划分训练/验证集")

        total = len(features)
        if total == 0:
            return {
                'train_features': np.empty((0, 0)),
                'train_targets': np.array([]),
                'train_future_returns': np.array([]),
                'val_features': np.empty((0, 0)),
                'val_targets': np.array([]),
                'val_future_returns': np.array([])
            }

        validation_ratio = float(config.get('validation_ratio', 0.2))
        validation_ratio = min(max(validation_ratio, 0.05), 0.4)
        val_size = max(1, int(total * validation_ratio))
        train_size = max(1, total - val_size)

        train_features = features[:train_size]
        train_targets = targets[:train_size]
        train_future_returns = future_returns[:train_size]

        val_features = features[train_size:]
        val_targets = targets[train_size:]
        val_future_returns = future_returns[train_size:]

        return {
            'train_features': train_features,
            'train_targets': train_targets,
            'train_future_returns': train_future_returns,
            'val_features': val_features,
            'val_targets': val_targets,
            'val_future_returns': val_future_returns
        }

    def _compute_validation_loss(self, model: Any, val_features: Any, val_targets: Any) -> Optional[float]:
        """计算验证集损失，用于早停"""
        if val_features is None or val_targets is None:
            return None
        if len(val_features) == 0 or len(val_targets) == 0:
            return None
        if not isinstance(model, IncrementalTrainingModel):
            return None

        try:
            predictions = model.predict(val_features)
            if model.is_classifier:
                accuracy = float((predictions == val_targets).mean())
                return max(0.0, 1.0 - accuracy)
            mse = float(np.mean((predictions - val_targets) ** 2))
            return mse
        except Exception as e:
            logger.warning(f"计算验证损失失败: {e}")
            return None

    def _calculate_cost_adjusted_metrics(self, model: Any, features: Any,
                                         future_returns: Any, config: Dict[str, Any]) -> Dict[str, Any]:
        """根据交易成本模拟调整后的收益指标"""
        if not isinstance(model, IncrementalTrainingModel):
            return {}
        if features is None or future_returns is None:
            return {}
        if len(features) == 0 or len(future_returns) == 0:
            return {}

        try:
            cost_per_trade = float(config.get('cost_per_trade', 0.0005))
            predictions = model.predict(features)
            returns_array = np.asarray(future_returns, dtype=np.float32)
            signals = np.asarray(predictions).astype(np.float32)

            if model.is_classifier:
                gross_returns = float(np.mean(signals * returns_array))
                trade_changes = np.abs(np.diff(signals, prepend=signals[0]))
            else:
                signal_directions = np.sign(signals)
                gross_returns = float(np.mean(signal_directions * returns_array))
                trade_changes = np.abs(np.diff(signal_directions, prepend=signal_directions[0]))

            avg_trades = float(np.mean(trade_changes))
            total_cost = cost_per_trade * float(np.sum(trade_changes))
            net_return = gross_returns - total_cost

            return {
                'gross_return': gross_returns,
                'net_return': net_return,
                'avg_trades_per_step': avg_trades,
                'cost_per_trade': cost_per_trade
            }
        except Exception as e:
            logger.warning(f"成本模型评估失败: {e}")
            return {}

    def _compute_signal_returns(self, model: IncrementalTrainingModel,
                                predictions: Any, future_returns: Any) -> np.ndarray:
        returns_array = np.asarray(future_returns, dtype=np.float32)
        if len(returns_array) == 0:
            return returns_array

        if model.is_classifier:
            signal = np.asarray(predictions, dtype=np.float32)
        else:
            signal = np.sign(np.asarray(predictions, dtype=np.float32))

        if len(signal) != len(returns_array):
            min_len = min(len(signal), len(returns_array))
            signal = signal[:min_len]
            returns_array = returns_array[:min_len]

        return signal * returns_array

    def _compute_walkforward_statistics(self, signal_returns: np.ndarray) -> Dict[str, float]:
        if signal_returns is None or len(signal_returns) == 0:
            return {}

        cumulative = np.cumsum(signal_returns)
        total_return = float(cumulative[-1]) if len(cumulative) else 0.0
        mean_return = float(np.mean(signal_returns))
        std_return = float(np.std(signal_returns))
        sharpe = 0.0
        if std_return > 1e-9:
            sharpe = float((mean_return / std_return) * math.sqrt(len(signal_returns)))

        peak = np.maximum.accumulate(cumulative)
        drawdown = cumulative - peak
        max_drawdown = float(drawdown.min()) if len(drawdown) else 0.0
        win_rate = float((signal_returns > 0).mean())

        return {
            'total_return': total_return,
            'sharpe': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate
        }

    def _extract_features(self, df: 'pd.DataFrame', model_type: str, horizon: int) -> 'pd.DataFrame':
        """基于K线数据提取通用技术指标特征"""
        try:
            if pd is None or np is None:
                raise ImportError("缺少Pandas或NumPy，无法提取特征")

            close = df['close'].astype(float)
            volume = df['volume'].astype(float).replace(0, np.nan)
            high = df['high'].astype(float)
            low = df['low'].astype(float)
            open_price = df['open'].astype(float)

            feature_frame = pd.DataFrame(index=df.index)
            feature_frame['return_1'] = close.pct_change().fillna(0)
            feature_frame['return_5'] = close.pct_change(5).fillna(0)
            feature_frame['momentum_10'] = close.pct_change(10).fillna(0)
            feature_frame['price_change'] = close.diff().fillna(0)
            feature_frame['high_low_spread'] = ((high - low) / close.replace(0, np.nan)).fillna(0)
            feature_frame['close_open_ratio'] = ((close - open_price) / open_price.replace(0, np.nan)).fillna(0)
            feature_frame['volatility_5'] = close.pct_change().rolling(5).std().fillna(0)
            feature_frame['volatility_20'] = close.pct_change().rolling(20).std().fillna(0)
            feature_frame['sma_ratio_5_20'] = (close.rolling(5).mean() / (close.rolling(20).mean() + 1e-9)).fillna(1.0)
            feature_frame['ema_ratio_12_26'] = (close.ewm(span=12).mean() / (close.ewm(span=26).mean() + 1e-9)).fillna(1.0)
            feature_frame['volume_zscore'] = ((volume - volume.rolling(20).mean()) /
                                              (volume.rolling(20).std() + 1e-9)).fillna(0)
            feature_frame['volume_acceleration'] = volume.pct_change().fillna(0)
            feature_frame['bollinger_width'] = ((close.rolling(20).std() * 2) / close.replace(0, np.nan)).fillna(0)
            true_ranges = pd.concat([
                (high - low).abs(),
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs()
            ], axis=1)
            feature_frame['avg_true_range'] = true_ranges.max(axis=1).fillna(0)

            if horizon > 0:
                feature_frame = feature_frame.iloc[:-horizon]

            feature_frame = feature_frame.replace([np.inf, -np.inf], 0).fillna(0)
            return feature_frame

        except Exception as e:
            logger.error(f"提取特征失败: {e}")
            return pd.DataFrame() if pd is not None else []

    def _extract_targets(self, df: 'pd.DataFrame', model_type: str, horizon: int,
                         config: Dict[str, Any]) -> Tuple['pd.Series', 'pd.Series']:
        """根据模型类型生成训练目标与实际收益"""
        try:
            if pd is None or np is None:
                raise ImportError("缺少Pandas或NumPy，无法计算目标")

            if horizon >= len(df):
                raise ValueError(f"数据长度不足，无法生成预测视窗({horizon})")

            close = df['close'].astype(float)
            future_close = close.shift(-horizon)
            future_return = ((future_close - close) / close.replace(0, np.nan)).fillna(0)

            aligned_future_return = future_return.iloc[:-horizon].fillna(0)

            if model_type == 'price':
                target = (future_close - close).iloc[:-horizon].fillna(0)
            else:
                threshold = float(config.get('classification_threshold', 0.003))
                labels = np.where(future_return > threshold, 1,
                                  np.where(future_return < -threshold, -1, 0))
                target = pd.Series(labels, index=df.index).iloc[:-horizon].fillna(0).astype(int)

            return target, aligned_future_return.astype(float)

        except Exception as e:
            logger.error(f"提取目标失败: {e}")
            empty_series = pd.Series(dtype=float) if pd is not None else []
            return empty_series, empty_series

    def _ensure_ml_dependencies(self) -> Dict[str, Any]:
        """按需加载scikit-learn组件和高级ML算法"""
        if self._ml_dependencies is not None:
            return self._ml_dependencies

        sklearn_modules = get_sklearn()
        if not sklearn_modules:
            raise ImportError("scikit-learn 未安装，无法初始化模型")

        linear_model = sklearn_modules.get('linear_model')
        preprocessing = sklearn_modules.get('preprocessing')
        ensemble = sklearn_modules.get('ensemble')
        svm_module = sklearn_modules.get('svm')
        impute_module = safe_import('sklearn.impute', required=False)
        
        xgboost = safe_import('xgboost', required=False)
        lightgbm = safe_import('lightgbm', required=False)

        dependencies = {
            'SGDClassifier': getattr(linear_model, 'SGDClassifier', None) if linear_model else None,
            'SGDRegressor': getattr(linear_model, 'SGDRegressor', None) if linear_model else None,
            'StandardScaler': getattr(preprocessing, 'StandardScaler', None) if preprocessing else None,
            'SimpleImputer': getattr(impute_module, 'SimpleImputer', None) if impute_module else None,
            'RandomForestClassifier': getattr(ensemble, 'RandomForestClassifier', None) if ensemble else None,
            'RandomForestRegressor': getattr(ensemble, 'RandomForestRegressor', None) if ensemble else None,
            'GradientBoostingClassifier': getattr(ensemble, 'GradientBoostingClassifier', None) if ensemble else None,
            'GradientBoostingRegressor': getattr(ensemble, 'GradientBoostingRegressor', None) if ensemble else None,
            'SVC': getattr(svm_module, 'SVC', None) if svm_module else None,
            'SVR': getattr(svm_module, 'SVR', None) if svm_module else None,
            'XGBClassifier': xgboost.XGBClassifier if xgboost else None,
            'XGBRegressor': xgboost.XGBRegressor if xgboost else None,
            'LGBMClassifier': lightgbm.LGBMClassifier if lightgbm else None,
            'LGBMRegressor': lightgbm.LGBMRegressor if lightgbm else None,
        }

        required = ['SGDClassifier', 'SGDRegressor', 'StandardScaler', 'SimpleImputer']
        missing = [name for name in required if dependencies.get(name) is None]
        if missing:
            raise ImportError(f"缺少必要的scikit-learn组件: {', '.join(missing)}")

        self._ml_dependencies = dependencies
        logger.info(f"ML依赖加载完成，可用算法: {[k for k,v in dependencies.items() if v is not None]}")
        return dependencies

    def _initialize_model(self, model_type: str, config: Dict[str, Any]):
        """
        初始化模型 - 支持多种算法

        Args:
            model_type: 模型类型
            config: 模型配置

        Returns:
            初始化的模型对象
        """
        try:
            dependencies = self._ensure_ml_dependencies()
            random_state = int(config.get('seed', 42))
            algorithm = config.get('algorithm', 'sgd')
            
            classifier_types = {"pattern", "trend", "sentiment", "risk", "volatility"}
            regressor_types = {"price"}
            
            is_classifier = model_type in classifier_types
            is_regressor = model_type in regressor_types
            
            if algorithm == 'xgboost':
                if is_classifier:
                    estimator = dependencies['XGBClassifier'](
                        n_estimators=config.get('n_estimators', 100),
                        max_depth=config.get('max_depth', 6),
                        learning_rate=config.get('learning_rate', 0.1),
                        random_state=random_state,
                        use_label_encoder=False,
                        eval_metric='logloss',
                        n_jobs=config.get('n_jobs', -1),
                        tree_method='hist'
                    )
                    classes = config.get('classes', [-1, 0, 1])
                    if np is not None:
                        classes = np.array(classes, dtype=np.int32)
                    model = IncrementalTrainingModel(
                        model_type=model_type,
                        estimator=estimator,
                        is_classifier=True,
                        classes=classes,
                        imputer=dependencies['SimpleImputer'](strategy='median'),
                        scaler=dependencies['StandardScaler'](),
                        is_incremental=False
                    )
                    logger.info(f"{model_type} 模型初始化完成（XGBoost分类器）")
                    return model
                else:
                    estimator = dependencies['XGBRegressor'](
                        n_estimators=config.get('n_estimators', 100),
                        max_depth=config.get('max_depth', 6),
                        learning_rate=config.get('learning_rate', 0.1),
                        random_state=random_state,
                        n_jobs=config.get('n_jobs', -1),
                        tree_method='hist'
                    )
                    model = IncrementalTrainingModel(
                        model_type=model_type,
                        estimator=estimator,
                        is_classifier=False,
                        imputer=dependencies['SimpleImputer'](strategy='median'),
                        scaler=dependencies['StandardScaler'](),
                        is_incremental=False
                    )
                    logger.info(f"{model_type} 模型初始化完成（XGBoost回归器）")
                    return model
            
            if algorithm == 'lightgbm':
                if is_classifier:
                    estimator = dependencies['LGBMClassifier'](
                        n_estimators=config.get('n_estimators', 100),
                        max_depth=config.get('max_depth', 6),
                        learning_rate=config.get('learning_rate', 0.1),
                        random_state=random_state,
                        verbose=-1
                    )
                    classes = config.get('classes', [-1, 0, 1])
                    if np is not None:
                        classes = np.array(classes, dtype=np.int32)
                    model = IncrementalTrainingModel(
                        model_type=model_type,
                        estimator=estimator,
                        is_classifier=True,
                        classes=classes,
                        imputer=dependencies['SimpleImputer'](strategy='median'),
                        scaler=dependencies['StandardScaler'](),
                        is_incremental=False
                    )
                    logger.info(f"{model_type} 模型初始化完成（LightGBM分类器）")
                    return model
                else:
                    estimator = dependencies['LGBMRegressor'](
                        n_estimators=config.get('n_estimators', 100),
                        max_depth=config.get('max_depth', 6),
                        learning_rate=config.get('learning_rate', 0.1),
                        random_state=random_state,
                        verbose=-1,
                        n_jobs=config.get('n_jobs', -1)
                    )
                    model = IncrementalTrainingModel(
                        model_type=model_type,
                        estimator=estimator,
                        is_classifier=False,
                        imputer=dependencies['SimpleImputer'](strategy='median'),
                        scaler=dependencies['StandardScaler'](),
                        is_incremental=False
                    )
                    logger.info(f"{model_type} 模型初始化完成（LightGBM回归器）")
                    return model
            
            if algorithm == 'random_forest':
                if is_classifier:
                    estimator = dependencies['RandomForestClassifier'](
                        n_estimators=config.get('n_estimators', 100),
                        max_depth=config.get('max_depth', 10),
                        random_state=random_state,
                        n_jobs=-1
                    )
                    classes = config.get('classes', [-1, 0, 1])
                    if np is not None:
                        classes = np.array(classes, dtype=np.int32)
                    model = IncrementalTrainingModel(
                        model_type=model_type,
                        estimator=estimator,
                        is_classifier=True,
                        classes=classes,
                        imputer=dependencies['SimpleImputer'](strategy='median'),
                        scaler=dependencies['StandardScaler'](),
                        is_incremental=False
                    )
                    logger.info(f"{model_type} 模型初始化完成（随机森林分类器）")
                    return model
                else:
                    estimator = dependencies['RandomForestRegressor'](
                        n_estimators=config.get('n_estimators', 100),
                        max_depth=config.get('max_depth', 10),
                        random_state=random_state,
                        n_jobs=config.get('n_jobs', -1)
                    )
                    model = IncrementalTrainingModel(
                        model_type=model_type,
                        estimator=estimator,
                        is_classifier=False,
                        imputer=dependencies['SimpleImputer'](strategy='median'),
                        scaler=dependencies['StandardScaler'](),
                        is_incremental=False
                    )
                    logger.info(f"{model_type} 模型初始化完成（随机森林回归器）")
                    return model
            
            if algorithm == 'gradient_boosting':
                if is_classifier:
                    estimator = dependencies['GradientBoostingClassifier'](
                        n_estimators=config.get('n_estimators', 100),
                        max_depth=config.get('max_depth', 5),
                        learning_rate=config.get('learning_rate', 0.1),
                        random_state=random_state,
                        n_iter_no_change=config.get('n_iter_no_change', 10),
                        validation_fraction=config.get('validation_fraction', 0.1)
                    )
                    classes = config.get('classes', [-1, 0, 1])
                    if np is not None:
                        classes = np.array(classes, dtype=np.int32)
                    model = IncrementalTrainingModel(
                        model_type=model_type,
                        estimator=estimator,
                        is_classifier=True,
                        classes=classes,
                        imputer=dependencies['SimpleImputer'](strategy='median'),
                        scaler=dependencies['StandardScaler'](),
                        is_incremental=False
                    )
                    logger.info(f"{model_type} 模型初始化完成（梯度提升分类器）")
                    return model
                else:
                    estimator = dependencies['GradientBoostingRegressor'](
                        n_estimators=config.get('n_estimators', 100),
                        max_depth=config.get('max_depth', 5),
                        learning_rate=config.get('learning_rate', 0.1),
                        random_state=random_state,
                        n_iter_no_change=config.get('n_iter_no_change', 10),
                        validation_fraction=config.get('validation_fraction', 0.1)
                    )
                    model = IncrementalTrainingModel(
                        model_type=model_type,
                        estimator=estimator,
                        is_classifier=False,
                        imputer=dependencies['SimpleImputer'](strategy='median'),
                        scaler=dependencies['StandardScaler'](),
                        is_incremental=False
                    )
                    logger.info(f"{model_type} 模型初始化完成（梯度提升回归器）")
                    return model
            
            if algorithm == 'svm':
                if is_classifier:
                    estimator = dependencies['SVC'](
                        kernel=config.get('kernel', 'rbf'),
                        C=config.get('C', 1.0),
                        gamma=config.get('gamma', 'scale'),
                        random_state=random_state,
                        probability=True,
                        cache_size=config.get('cache_size', 500)
                    )
                    classes = config.get('classes', [-1, 0, 1])
                    if np is not None:
                        classes = np.array(classes, dtype=np.int32)
                    model = IncrementalTrainingModel(
                        model_type=model_type,
                        estimator=estimator,
                        is_classifier=True,
                        classes=classes,
                        imputer=dependencies['SimpleImputer'](strategy='median'),
                        scaler=dependencies['StandardScaler'](),
                        is_incremental=False
                    )
                    logger.info(f"{model_type} 模型初始化完成（SVM分类器）")
                    return model
                else:
                    estimator = dependencies['SVR'](
                        kernel=config.get('kernel', 'rbf'),
                        C=config.get('C', 1.0),
                        gamma=config.get('gamma', 'scale'),
                        cache_size=config.get('cache_size', 500)
                    )
                    model = IncrementalTrainingModel(
                        model_type=model_type,
                        estimator=estimator,
                        is_classifier=False,
                        imputer=dependencies['SimpleImputer'](strategy='median'),
                        scaler=dependencies['StandardScaler'](),
                        is_incremental=False
                    )
                    logger.info(f"{model_type} 模型初始化完成（SVM回归器）")
                    return model
            
            if algorithm == 'sgd' or algorithm == 'linear':
                alpha = float(config.get('alpha', 1e-4))
                learning_rate = float(config.get('learning_rate', 0.01))
                
                if is_classifier:
                    sgd_classifier = dependencies['SGDClassifier']
                    if not sgd_classifier:
                        raise ImportError("SGDClassifier 不可用")

                    estimator = sgd_classifier(
                        loss=config.get('loss', 'log_loss'),
                        penalty=config.get('penalty', 'l2'),
                        alpha=alpha,
                        learning_rate=config.get('sgd_schedule', 'constant'),
                        eta0=learning_rate,
                        random_state=random_state,
                        max_iter=1,
                        warm_start=True
                    )

                    classes = config.get('classes', [-1, 0, 1])
                    if np is not None:
                        classes = np.array(classes, dtype=np.int32)

                    model = IncrementalTrainingModel(
                        model_type=model_type,
                        estimator=estimator,
                        is_classifier=True,
                        classes=classes,
                        imputer=dependencies['SimpleImputer'](strategy='median'),
                        scaler=dependencies['StandardScaler'](),
                        is_incremental=True
                    )
                    logger.info(f"{model_type} 模型初始化完成（SGD分类器）")
                    return model

                if is_regressor:
                    sgd_regressor = dependencies['SGDRegressor']
                    if not sgd_regressor:
                        raise ImportError("SGDRegressor 不可用")

                    estimator = sgd_regressor(
                        loss=config.get('loss', 'squared_error'),
                        penalty=config.get('penalty', 'l2'),
                        alpha=alpha,
                        learning_rate=config.get('sgd_schedule', 'invscaling'),
                        eta0=learning_rate,
                        random_state=random_state,
                        max_iter=1,
                        warm_start=True
                    )

                    model = IncrementalTrainingModel(
                        model_type=model_type,
                        estimator=estimator,
                        is_classifier=False,
                        imputer=dependencies['SimpleImputer'](strategy='median'),
                        scaler=dependencies['StandardScaler'](),
                        is_incremental=True
                    )
                    logger.info(f"{model_type} 模型初始化完成（SGD回归器）")
                    return model

            raise ValueError(f"不支持的算法类型: {algorithm}，支持的算法: sgd, xgboost, lightgbm, random_forest, gradient_boosting, svm")

        except Exception as e:
            logger.error(f"初始化模型失败: {e}")
            raise

    def _train_epoch(self, model, training_data: Dict[str, Any], epoch: int,
                     batch_size: int, config: Dict[str, Any]) -> float:
        """
        训练一个epoch
        """
        try:
            features = training_data.get('features')
            targets = training_data.get('targets')

            if isinstance(model, IncrementalTrainingModel):
                if features is None or targets is None or len(features) == 0:
                    raise ValueError("训练数据为空，无法执行增量训练")

                losses: List[float] = []
                for batch_features, batch_targets in self._iterate_batches(features, targets, batch_size):
                    batch_loss = model.partial_fit(batch_features, batch_targets)
                    losses.append(batch_loss)

                if not losses:
                    return 1.0

                if np is not None:
                    return float(np.mean(losses))
                return sum(losses) / len(losses)

            logger.warning(f"模型未迁移到增量训练，无法计算真实损失。请迁移模型以获取准确结果。")
            return None

        except Exception as e:
            logger.error(f"训练epoch失败: {e}")
            return 1.0

    def _iterate_batches(self, features: Any, targets: Any, batch_size: int):
        """将训练数据按批次迭代输出"""
        if batch_size <= 0:
            batch_size = 32

        if np is not None:
            feature_array = np.asarray(features)
            target_array = np.asarray(targets)
        else:
            feature_array = features
            target_array = targets

        total = len(feature_array)
        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            yield feature_array[start:end], target_array[start:end]

    def evaluate_model(self, task_id: str, model, training_data: Dict[str, Any],
                       config: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估模型

        Args:
            task_id: 任务ID
            model: 模型对象
            training_data: 训练数据
            config: 评估配置

        Returns:
            评估指标字典
        """
        try:
            self.log_training_event(task_id, "INFO", "开始模型评估")
            evaluation_features = training_data.get('val_features')
            evaluation_targets = training_data.get('val_targets')
            evaluation_returns = training_data.get('val_future_returns')

            if evaluation_features is None or len(evaluation_features) == 0:
                evaluation_features = training_data.get('train_features')
                evaluation_targets = training_data.get('train_targets')
                evaluation_returns = training_data.get('train_future_returns')

            metrics: Dict[str, Any] = {
                'evaluated_at': datetime.now().isoformat(),
                'validation_samples': int(len(evaluation_features) if evaluation_features is not None else 0),
                'training_source': training_data.get('source')
            }

            if isinstance(model, IncrementalTrainingModel) and evaluation_features is not None:
                predictions = model.predict(evaluation_features)

                if model.is_classifier and sklearn_metrics:
                    accuracy_fn = getattr(sklearn_metrics, 'accuracy_score', None)
                    precision_fn = getattr(sklearn_metrics, 'precision_score', None)
                    recall_fn = getattr(sklearn_metrics, 'recall_score', None)
                    f1_fn = getattr(sklearn_metrics, 'f1_score', None)

                    if accuracy_fn:
                        metrics['accuracy'] = float(accuracy_fn(evaluation_targets, predictions))
                    if precision_fn:
                        metrics['precision'] = float(precision_fn(evaluation_targets, predictions, average='macro', zero_division=0))
                    if recall_fn:
                        metrics['recall'] = float(recall_fn(evaluation_targets, predictions, average='macro', zero_division=0))
                    if f1_fn:
                        metrics['f1_score'] = float(f1_fn(evaluation_targets, predictions, average='macro', zero_division=0))
                elif not model.is_classifier and sklearn_metrics:
                    mse_fn = getattr(sklearn_metrics, 'mean_squared_error', None)
                    mae_fn = getattr(sklearn_metrics, 'mean_absolute_error', None)
                    if mse_fn:
                        metrics['mse'] = float(mse_fn(evaluation_targets, predictions))
                    if mae_fn:
                        metrics['mae'] = float(mae_fn(evaluation_targets, predictions))

                cost_metrics = self._calculate_cost_adjusted_metrics(
                    model,
                    evaluation_features,
                    evaluation_returns,
                    config
                )
                metrics.update(cost_metrics)
                if evaluation_returns is not None and len(evaluation_returns) == len(predictions):
                    walk_returns = self._compute_signal_returns(model, predictions, evaluation_returns)
                    walk_metrics = self._compute_walkforward_statistics(walk_returns)
                    if walk_metrics:
                        metrics['walk_forward'] = walk_metrics
            else:
                metrics.update({
                    'accuracy': 0.0,
                    'precision': 0.0,
                    'recall': 0.0
                })

            metadata = training_data.get('training_metadata') or {}
            if metadata:
                metrics['validation_curve'] = metadata.get('val_history', [])
                metrics['best_val_loss'] = metadata.get('best_val_loss')

            self.log_training_event(task_id, "INFO", f"模型评估完成: {metrics}")
            return metrics

        except Exception as e:
            logger.error(f"评估模型失败: {e}")
            return {
                'accuracy': 0.0,
                'error': str(e),
                'evaluated_at': datetime.now().isoformat()
            }

    def save_model(self, task_id: str, model, model_type: str,
                   metrics: Dict[str, Any], config: Dict[str, Any]) -> str:
        """
        保存模型

        Args:
            task_id: 任务ID
            model: 模型对象
            model_type: 模型类型
            metrics: 性能指标
            config: 模型配置

        Returns:
            模型文件路径
        """
        try:
            # 生成模型文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            model_filename = f"{model_type}_{task_id}_{timestamp}.pkl"
            model_path = self._model_storage_path / model_filename

            # 这里应该保存实际的模型
            # 目前只保存元数据
            model_metadata = {
                'model_type': model_type,
                'task_id': task_id,
                'metrics': metrics,
                'config': config,
                'saved_at': datetime.now().isoformat()
            }

            with open(model_path, 'wb') as f:
                pickle.dump({
                    'model': model,
                    'metadata': model_metadata
                }, f)

            self.log_training_event(task_id, "INFO", f"模型已保存: {model_path}")
            return str(model_path)

        except Exception as e:
            logger.error(f"保存模型失败: {e}")
            raise

    def cancel_training(self, task_id: str) -> bool:
        """
        取消训练任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功取消
        """
        try:
            with self._task_lock:
                if task_id not in self._training_tasks:
                    raise ValueError(f"任务不存在: {task_id}")

                task = self._training_tasks[task_id]
                if task['status'] not in [TrainingTaskStatus.PENDING.value,
                                          TrainingTaskStatus.PREPARING.value,
                                          TrainingTaskStatus.TRAINING.value]:
                    raise ValueError(f"任务状态不允许取消: {task['status']}")

            # 更新状态
            self.update_task_status(task_id, TrainingTaskStatus.CANCELLED)
            self.log_training_event(task_id, "INFO", "训练任务已取消")

            logger.info(f"训练任务已取消: {task_id}")
            return True

        except Exception as e:
            logger.error(f"取消训练任务失败: {e}")
            return False

    def delete_training_task(self, task_id: str) -> bool:
        """
        删除训练任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功删除
        """
        try:
            with self._task_lock:
                if task_id not in self._training_tasks:
                    raise ValueError(f"任务不存在: {task_id}")

                task = self._training_tasks[task_id]
                if task['status'] == TrainingTaskStatus.TRAINING.value:
                    raise ValueError("训练中的任务不能删除，请先取消")

                del self._training_tasks[task_id]

            # 从数据库删除
            if self._database_service:
                try:
                    with self._database_service.get_connection("strategy_sqlite") as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM training_tasks WHERE task_id = ?", (task_id,))
                        cursor.execute("DELETE FROM training_logs WHERE training_task_id = ?", (task_id,))
                        conn.commit()
                except Exception as db_err:
                    logger.warning(f"从数据库删除任务失败: {db_err}")

            self._event_bus.publish("training.task.deleted", task_id=task_id)

            logger.info(f"训练任务已删除: {task_id}")
            return True

        except Exception as e:
            logger.error(f"删除训练任务失败: {e}")
            return False

    def get_training_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取训练进度

        Args:
            task_id: 任务ID

        Returns:
            进度信息字典
        """
        task = self.get_training_task(task_id)
        if not task:
            return None

        return {
            'task_id': task_id,
            'status': task['status'],
            'progress': task['progress'],
            'error_message': task.get('error_message'),
            'started_at': task.get('started_at'),
            'updated_at': task.get('updated_at')
        }

    def get_training_logs(self, task_id: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        """
        获取训练日志

        Args:
            task_id: 可选的任务ID，用于筛选
            limit: 返回的最大日志条数

        Returns:
            日志列表，按时间倒序
        """
        try:
            query = """
                SELECT training_task_id, log_level, log_message, log_data_json, created_at
                FROM training_logs
            """
            params: List[Any] = []
            if task_id:
                query += " WHERE training_task_id = ?"
                params.append(task_id)
            query += " ORDER BY log_id DESC LIMIT ?"
            params.append(limit)

            if self._database_service:
                with self._database_service.get_connection("strategy_sqlite") as conn:
                    cursor = conn.cursor()
                    cursor.execute(query, tuple(params))
                    rows = cursor.fetchall()
            else:
                logger.error("DatabaseService不可用，无法获取训练日志")
                return []

            logs: List[Dict[str, Any]] = []
            for row in rows:
                logs.append({
                    'training_task_id': row[0],
                    'log_level': row[1],
                    'log_message': row[2],
                    'log_data': json.loads(row[3]) if row[3] else None,
                    'created_at': row[4]
                })
            return logs
        except Exception as e:
            logger.error(f"获取训练日志失败: {e}")
            return []