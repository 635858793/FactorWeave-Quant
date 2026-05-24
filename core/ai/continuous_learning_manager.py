"""
AI模型持续学习机制
实现AI模型的在线学习和持续优化，支持模型性能监控和自动更新
"""

from loguru import logger
import json
import pickle
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Callable, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import threading
import sqlite3
import os
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, Future
import queue

class LearningMode(Enum):
    """学习模式"""
    OFFLINE = "offline"          # 离线学习
    ONLINE = "online"           # 在线学习
    INCREMENTAL = "incremental"  # 增量学习
    FEDERATED = "federated"     # 联邦学习
    TRANSFER = "transfer"       # 迁移学习


class ModelStatus(Enum):
    """模型状态"""
    TRAINING = "training"
    READY = "ready"
    UPDATING = "updating"
    ERROR = "error"
    DEPRECATED = "deprecated"


class LearningTrigger(Enum):
    """学习触发器"""
    SCHEDULE = "schedule"        # 定时触发
    PERFORMANCE = "performance"  # 性能下降触发
    DATA_DRIFT = "data_drift"   # 数据漂移触发
    MANUAL = "manual"           # 手动触发
    THRESHOLD = "threshold"     # 阈值触发


@dataclass
class ModelMetrics:
    """模型性能指标"""
    model_id: str
    version: str
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    auc_score: Optional[float] = None
    mse: Optional[float] = None
    mae: Optional[float] = None
    custom_metrics: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    sample_count: int = 0
    training_time: Optional[float] = None
    inference_time: Optional[float] = None


@dataclass
class LearningTask:
    """学习任务"""
    task_id: str
    model_id: str
    learning_mode: LearningMode
    trigger: LearningTrigger
    data_source: str
    config: Dict[str, Any] = field(default_factory=dict)
    priority: int = 1  # 1-5, 5最高
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"
    progress: float = 0.0
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


@dataclass
class ModelVersion:
    """模型版本"""
    model_id: str
    version: str
    file_path: str
    metrics: ModelMetrics
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = False
    is_baseline: bool = False


class DataDriftDetector:
    """数据漂移检测器"""

    def __init__(self, window_size: int = 1000, threshold: float = 0.1):
        self.window_size = window_size
        self.threshold = threshold
        self.reference_data = deque(maxlen=window_size)
        self.current_data = deque(maxlen=window_size)
        self._lock = threading.Lock()

    def add_reference_sample(self, sample: Dict[str, Any]):
        """添加参考样本"""
        with self._lock:
            self.reference_data.append(sample)

    def add_current_sample(self, sample: Dict[str, Any]):
        """添加当前样本"""
        with self._lock:
            self.current_data.append(sample)

    def detect_drift(self) -> Dict[str, Any]:
        """检测数据漂移"""
        try:
            if len(self.reference_data) < 100 or len(self.current_data) < 100:
                return {
                    'drift_detected': False,
                    'drift_score': 0.0,
                    'reason': 'insufficient_data'
                }

            # 转换为DataFrame进行分析
            ref_df = pd.DataFrame(list(self.reference_data))
            cur_df = pd.DataFrame(list(self.current_data))

            # 确保列一致
            common_columns = set(ref_df.columns) & set(cur_df.columns)
            if not common_columns:
                return {
                    'drift_detected': False,
                    'drift_score': 0.0,
                    'reason': 'no_common_features'
                }

            ref_df = ref_df[list(common_columns)]
            cur_df = cur_df[list(common_columns)]

            # 计算统计差异
            drift_scores = {}

            for column in common_columns:
                if pd.api.types.is_numeric_dtype(ref_df[column]):
                    # 数值型特征：使用KS检验
                    drift_score = self._ks_test(ref_df[column], cur_df[column])
                else:
                    # 分类型特征：使用卡方检验
                    drift_score = self._chi_square_test(ref_df[column], cur_df[column])

                drift_scores[column] = drift_score

            # 计算总体漂移分数
            overall_drift_score = np.mean(list(drift_scores.values()))
            drift_detected = overall_drift_score > self.threshold

            return {
                'drift_detected': drift_detected,
                'drift_score': overall_drift_score,
                'feature_drift_scores': drift_scores,
                'threshold': self.threshold,
                'sample_sizes': {
                    'reference': len(self.reference_data),
                    'current': len(self.current_data)
                }
            }

        except Exception as e:
            logger.error(f"数据漂移检测失败: {e}")
            return {
                'drift_detected': False,
                'drift_score': 0.0,
                'error': str(e)
            }

    def _ks_test(self, ref_data: pd.Series, cur_data: pd.Series) -> float:
        """Kolmogorov-Smirnov检验"""
        try:
            from scipy import stats
            statistic, p_value = stats.ks_2samp(ref_data.dropna(), cur_data.dropna())
            return statistic
        except ImportError:
            # 如果没有scipy，使用简化的统计差异
            ref_mean = ref_data.mean()
            cur_mean = cur_data.mean()
            ref_std = ref_data.std()
            cur_std = cur_data.std()

            mean_diff = abs(ref_mean - cur_mean) / (ref_std + 1e-8)
            std_diff = abs(ref_std - cur_std) / (ref_std + 1e-8)

            return (mean_diff + std_diff) / 2

    def _chi_square_test(self, ref_data: pd.Series, cur_data: pd.Series) -> float:
        """卡方检验"""
        try:
            # 计算频率分布
            ref_counts = ref_data.value_counts(normalize=True)
            cur_counts = cur_data.value_counts(normalize=True)

            # 对齐索引
            all_categories = set(ref_counts.index) | set(cur_counts.index)

            ref_freq = [ref_counts.get(cat, 0) for cat in all_categories]
            cur_freq = [cur_counts.get(cat, 0) for cat in all_categories]

            # 计算卡方统计量
            chi_square = sum((r - c) ** 2 / (r + 1e-8) for r, c in zip(ref_freq, cur_freq))
            return chi_square / len(all_categories)

        except Exception as e:
            logger.error(f"卡方检验失败: {e}")
            return 0.0


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.metrics_history = defaultdict(lambda: deque(maxlen=window_size))
        self.baseline_metrics = {}
        self._lock = threading.Lock()

    def record_metrics(self, model_id: str, metrics: ModelMetrics):
        """记录模型性能指标"""
        with self._lock:
            self.metrics_history[model_id].append(metrics)

    def set_baseline(self, model_id: str, metrics: ModelMetrics):
        """设置基线性能"""
        self.baseline_metrics[model_id] = metrics

    def check_performance_degradation(self, model_id: str, threshold: float = 0.05) -> Dict[str, Any]:
        """检查性能退化"""
        try:
            if model_id not in self.metrics_history or len(self.metrics_history[model_id]) < 10:
                return {
                    'degradation_detected': False,
                    'reason': 'insufficient_data'
                }

            recent_metrics = list(self.metrics_history[model_id])[-10:]  # 最近10次
            baseline = self.baseline_metrics.get(model_id)

            if not baseline:
                # 使用历史最佳作为基线
                all_metrics = list(self.metrics_history[model_id])
                baseline = max(all_metrics, key=lambda x: x.accuracy)
                self.baseline_metrics[model_id] = baseline

            # 计算性能变化
            recent_accuracy = np.mean([m.accuracy for m in recent_metrics])
            baseline_accuracy = baseline.accuracy

            accuracy_drop = baseline_accuracy - recent_accuracy
            degradation_detected = accuracy_drop > threshold

            # 计算其他指标的变化
            metrics_comparison = {
                'accuracy': {
                    'baseline': baseline_accuracy,
                    'recent': recent_accuracy,
                    'change': -accuracy_drop
                },
                'precision': {
                    'baseline': baseline.precision,
                    'recent': np.mean([m.precision for m in recent_metrics]),
                    'change': np.mean([m.precision for m in recent_metrics]) - baseline.precision
                },
                'recall': {
                    'baseline': baseline.recall,
                    'recent': np.mean([m.recall for m in recent_metrics]),
                    'change': np.mean([m.recall for m in recent_metrics]) - baseline.recall
                }
            }

            return {
                'degradation_detected': degradation_detected,
                'accuracy_drop': accuracy_drop,
                'threshold': threshold,
                'metrics_comparison': metrics_comparison,
                'sample_count': len(recent_metrics)
            }

        except Exception as e:
            logger.error(f"性能退化检查失败: {e}")
            return {
                'degradation_detected': False,
                'error': str(e)
            }

    def get_performance_trend(self, model_id: str) -> Dict[str, Any]:
        """获取性能趋势"""
        try:
            if model_id not in self.metrics_history:
                return {}

            metrics_list = list(self.metrics_history[model_id])
            if len(metrics_list) < 5:
                return {'trend': 'insufficient_data'}

            # 计算趋势
            accuracies = [m.accuracy for m in metrics_list]

            # 简单线性趋势
            x = np.arange(len(accuracies))
            slope = np.polyfit(x, accuracies, 1)[0]

            if slope > 0.001:
                trend = 'improving'
            elif slope < -0.001:
                trend = 'declining'
            else:
                trend = 'stable'

            return {
                'trend': trend,
                'slope': slope,
                'recent_accuracy': accuracies[-1],
                'best_accuracy': max(accuracies),
                'worst_accuracy': min(accuracies),
                'variance': np.var(accuracies),
                'sample_count': len(accuracies)
            }

        except Exception as e:
            logger.error(f"获取性能趋势失败: {e}")
            return {'error': str(e)}


class ModelVersionManager:
    """模型版本管理器"""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or self._get_default_storage_path()
        self.versions = {}  # model_id -> List[ModelVersion]
        self.active_versions = {}  # model_id -> version
        self._lock = threading.Lock()
        self._load_versions()

    def _get_default_storage_path(self) -> str:
        """获取默认存储路径"""
        app_data_dir = Path.home() / ".FactorWeave-Quant" / "model_versions"
        app_data_dir.mkdir(parents=True, exist_ok=True)
        return str(app_data_dir)

    def _load_versions(self):
        """加载版本信息"""
        try:
            versions_file = Path(self.storage_path) / "versions.json"
            if versions_file.exists():
                with open(versions_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for model_id, version_list in data.items():
                    self.versions[model_id] = []
                    for v_data in version_list:
                        # 重建ModelVersion对象
                        metrics_data = v_data['metrics']
                        metrics = ModelMetrics(
                            model_id=metrics_data['model_id'],
                            version=metrics_data['version'],
                            accuracy=metrics_data['accuracy'],
                            precision=metrics_data['precision'],
                            recall=metrics_data['recall'],
                            f1_score=metrics_data['f1_score'],
                            auc_score=metrics_data.get('auc_score'),
                            mse=metrics_data.get('mse'),
                            mae=metrics_data.get('mae'),
                            custom_metrics=metrics_data.get('custom_metrics', {}),
                            timestamp=datetime.fromisoformat(metrics_data['timestamp']),
                            sample_count=metrics_data.get('sample_count', 0),
                            training_time=metrics_data.get('training_time'),
                            inference_time=metrics_data.get('inference_time')
                        )

                        version = ModelVersion(
                            model_id=v_data['model_id'],
                            version=v_data['version'],
                            file_path=v_data['file_path'],
                            metrics=metrics,
                            config=v_data.get('config', {}),
                            metadata=v_data.get('metadata', {}),
                            created_at=datetime.fromisoformat(v_data['created_at']),
                            is_active=v_data.get('is_active', False),
                            is_baseline=v_data.get('is_baseline', False)
                        )

                        self.versions[model_id].append(version)

                        if version.is_active:
                            self.active_versions[model_id] = version.version

                logger.info(f"已加载 {len(self.versions)} 个模型的版本信息")

        except Exception as e:
            logger.error(f"加载版本信息失败: {e}")

    def _save_versions(self):
        """保存版本信息"""
        try:
            versions_file = Path(self.storage_path) / "versions.json"

            # 转换为可序列化的格式
            data = {}
            for model_id, version_list in self.versions.items():
                data[model_id] = []
                for version in version_list:
                    version_data = {
                        'model_id': version.model_id,
                        'version': version.version,
                        'file_path': version.file_path,
                        'metrics': {
                            'model_id': version.metrics.model_id,
                            'version': version.metrics.version,
                            'accuracy': version.metrics.accuracy,
                            'precision': version.metrics.precision,
                            'recall': version.metrics.recall,
                            'f1_score': version.metrics.f1_score,
                            'auc_score': version.metrics.auc_score,
                            'mse': version.metrics.mse,
                            'mae': version.metrics.mae,
                            'custom_metrics': version.metrics.custom_metrics,
                            'timestamp': version.metrics.timestamp.isoformat(),
                            'sample_count': version.metrics.sample_count,
                            'training_time': version.metrics.training_time,
                            'inference_time': version.metrics.inference_time
                        },
                        'config': version.config,
                        'metadata': version.metadata,
                        'created_at': version.created_at.isoformat(),
                        'is_active': version.is_active,
                        'is_baseline': version.is_baseline
                    }
                    data[model_id].append(version_data)

            with open(versions_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"保存版本信息失败: {e}")

    def add_version(self, version: ModelVersion) -> bool:
        """添加新版本"""
        try:
            with self._lock:
                if version.model_id not in self.versions:
                    self.versions[version.model_id] = []

                self.versions[version.model_id].append(version)

                # 如果是活跃版本，更新活跃版本映射
                if version.is_active:
                    # 取消其他版本的活跃状态
                    for v in self.versions[version.model_id]:
                        if v.version != version.version:
                            v.is_active = False

                    self.active_versions[version.model_id] = version.version

                self._save_versions()
                return True

        except Exception as e:
            logger.error(f"添加模型版本失败: {e}")
            return False

    def get_active_version(self, model_id: str) -> Optional[ModelVersion]:
        """获取活跃版本"""
        if model_id not in self.versions:
            return None

        active_version_id = self.active_versions.get(model_id)
        if not active_version_id:
            return None

        for version in self.versions[model_id]:
            if version.version == active_version_id:
                return version

        return None

    def get_best_version(self, model_id: str, metric: str = 'accuracy') -> Optional[ModelVersion]:
        """获取最佳版本"""
        if model_id not in self.versions:
            return None

        versions = self.versions[model_id]
        if not versions:
            return None

        # 根据指定指标选择最佳版本
        if metric == 'accuracy':
            return max(versions, key=lambda v: v.metrics.accuracy)
        elif metric == 'f1_score':
            return max(versions, key=lambda v: v.metrics.f1_score)
        elif metric == 'precision':
            return max(versions, key=lambda v: v.metrics.precision)
        elif metric == 'recall':
            return max(versions, key=lambda v: v.metrics.recall)
        else:
            return versions[-1]  # 返回最新版本

    def activate_version(self, model_id: str, version_id: str) -> bool:
        """激活指定版本"""
        try:
            with self._lock:
                if model_id not in self.versions:
                    return False

                # 找到目标版本
                target_version = None
                for version in self.versions[model_id]:
                    if version.version == version_id:
                        target_version = version
                        break

                if not target_version:
                    return False

                # 取消所有版本的活跃状态
                for version in self.versions[model_id]:
                    version.is_active = False

                # 激活目标版本
                target_version.is_active = True
                self.active_versions[model_id] = version_id

                self._save_versions()
                return True

        except Exception as e:
            logger.error(f"激活模型版本失败: {e}")
            return False

    def get_version_history(self, model_id: str) -> List[ModelVersion]:
        """获取版本历史"""
        return self.versions.get(model_id, [])

    def cleanup_old_versions(self, model_id: str, keep_count: int = 5) -> int:
        """清理旧版本"""
        try:
            if model_id not in self.versions:
                return 0

            versions = self.versions[model_id]
            if len(versions) <= keep_count:
                return 0

            # 按创建时间排序，保留最新的版本
            versions.sort(key=lambda v: v.created_at, reverse=True)

            # 保留活跃版本和基线版本
            to_keep = []
            to_remove = []

            for version in versions:
                if version.is_active or version.is_baseline or len(to_keep) < keep_count:
                    to_keep.append(version)
                else:
                    to_remove.append(version)

            # 删除文件
            removed_count = 0
            for version in to_remove:
                try:
                    if os.path.exists(version.file_path):
                        os.remove(version.file_path)
                    removed_count += 1
                except Exception as e:
                    logger.error(f"删除模型文件失败 {version.file_path}: {e}")

            # 更新版本列表
            self.versions[model_id] = to_keep
            self._save_versions()

            return removed_count

        except Exception as e:
            logger.error(f"清理旧版本失败: {e}")
            return 0


class ContinuousLearningManager:
    """持续学习管理器主类"""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or self._get_default_storage_path()

        # 核心组件
        self.drift_detector = DataDriftDetector()
        self.performance_monitor = PerformanceMonitor()
        self.version_manager = ModelVersionManager(self.storage_path)

        # 学习任务管理
        self.learning_tasks = queue.PriorityQueue()
        self.active_tasks = {}
        self.task_executor = ThreadPoolExecutor(max_workers=2)

        # 配置
        self.config = {
            'drift_threshold': 0.1,
            'performance_threshold': 0.05,
            'learning_schedule': '0 2 * * *',  # 每天凌晨2点
            'max_concurrent_tasks': 2,
            'model_retention_count': 5,
            'auto_activation': True
        }

        # 状态
        self.is_running = False
        self.scheduler_thread = None
        self._lock = threading.Lock()

        logger.info("持续学习管理器已初始化")

    def _get_default_storage_path(self) -> str:
        """获取默认存储路径"""
        app_data_dir = Path.home() / ".FactorWeave-Quant" / "continuous_learning"
        app_data_dir.mkdir(parents=True, exist_ok=True)
        return str(app_data_dir)

    def start(self):
        """启动持续学习服务"""
        try:
            if self.is_running:
                logger.warning("持续学习服务已在运行")
                return

            self.is_running = True

            # 启动调度器线程
            self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self.scheduler_thread.start()

            logger.info("持续学习服务已启动")

        except Exception as e:
            logger.error(f"启动持续学习服务失败: {e}")

    def stop(self):
        """停止持续学习服务"""
        try:
            self.is_running = False

            if self.scheduler_thread:
                self.scheduler_thread.join(timeout=5)

            # 停止任务执行器
            self.task_executor.shutdown(wait=True)

            logger.info("持续学习服务已停止")

        except Exception as e:
            logger.error(f"停止持续学习服务失败: {e}")

    def add_training_sample(self, model_id: str, sample: Dict[str, Any], is_reference: bool = False):
        """添加训练样本"""
        try:
            if is_reference:
                self.drift_detector.add_reference_sample(sample)
            else:
                self.drift_detector.add_current_sample(sample)

            # 检查是否需要触发学习
            self._check_learning_triggers(model_id)

        except Exception as e:
            logger.error(f"添加训练样本失败: {e}")

    def record_prediction_metrics(self, model_id: str, metrics: ModelMetrics):
        """记录预测性能指标"""
        try:
            self.performance_monitor.record_metrics(model_id, metrics)

            # 检查性能退化
            degradation_result = self.performance_monitor.check_performance_degradation(model_id)

            if degradation_result.get('degradation_detected', False):
                logger.warning(f"检测到模型 {model_id} 性能退化: {degradation_result}")

                # 触发重训练
                self.trigger_learning(
                    model_id=model_id,
                    trigger=LearningTrigger.PERFORMANCE,
                    priority=4,
                    config={'reason': 'performance_degradation', 'details': degradation_result}
                )

        except Exception as e:
            logger.error(f"记录预测性能指标失败: {e}")

    def trigger_learning(self, model_id: str, trigger: LearningTrigger,
                         learning_mode: LearningMode = LearningMode.INCREMENTAL,
                         priority: int = 1, config: Optional[Dict[str, Any]] = None) -> str:
        """触发学习任务"""
        try:
            task_id = self._generate_task_id(model_id)

            task = LearningTask(
                task_id=task_id,
                model_id=model_id,
                learning_mode=learning_mode,
                trigger=trigger,
                data_source="continuous_learning",
                config=config or {},
                priority=priority
            )

            # 添加到任务队列（优先级队列，数字越小优先级越高）
            self.learning_tasks.put((6 - priority, task))

            logger.info(f"已触发学习任务: {task_id} (模型: {model_id}, 触发器: {trigger.value})")

            return task_id

        except Exception as e:
            logger.error(f"触发学习任务失败: {e}")
            return ""

    def get_model_status(self, model_id: str) -> Dict[str, Any]:
        """获取模型状态"""
        try:
            # 获取活跃版本
            active_version = self.version_manager.get_active_version(model_id)

            # 获取性能趋势
            performance_trend = self.performance_monitor.get_performance_trend(model_id)

            # 检查数据漂移
            drift_result = self.drift_detector.detect_drift()

            # 检查性能退化
            degradation_result = self.performance_monitor.check_performance_degradation(model_id)

            # 获取版本历史
            version_history = self.version_manager.get_version_history(model_id)

            return {
                'model_id': model_id,
                'active_version': active_version.version if active_version else None,
                'total_versions': len(version_history),
                'performance_trend': performance_trend,
                'drift_status': drift_result,
                'degradation_status': degradation_result,
                'last_training': version_history[-1].created_at.isoformat() if version_history else None,
                'active_tasks': [task_id for task_id, task in self.active_tasks.items() if task.model_id == model_id],
                'status': self._determine_model_status(model_id)
            }

        except Exception as e:
            logger.error(f"获取模型状态失败: {e}")
            return {'error': str(e)}

    def _scheduler_loop(self):
        """调度器循环"""
        while self.is_running:
            try:
                # 处理学习任务
                self._process_learning_tasks()

                # 定期检查
                self._periodic_checks()

                # 休眠
                time.sleep(60)  # 每分钟检查一次

            except Exception as e:
                logger.error(f"调度器循环错误: {e}")
                time.sleep(60)

    def _process_learning_tasks(self):
        """处理学习任务"""
        try:
            # 检查是否有可用的执行器
            if len(self.active_tasks) >= self.config['max_concurrent_tasks']:
                return

            # 从队列获取任务
            if not self.learning_tasks.empty():
                try:
                    priority, task = self.learning_tasks.get_nowait()

                    # 提交任务执行
                    future = self.task_executor.submit(self._execute_learning_task, task)
                    self.active_tasks[task.task_id] = task

                    # 设置完成回调
                    future.add_done_callback(lambda f: self._on_task_completed(task.task_id, f))

                    logger.info(f"开始执行学习任务: {task.task_id}")

                except queue.Empty:
                    pass

        except Exception as e:
            logger.error(f"处理学习任务失败: {e}")

    def _execute_learning_task(self, task: LearningTask) -> Dict[str, Any]:
        """执行学习任务"""
        try:
            task.started_at = datetime.now()
            task.status = "running"

            logger.info(f"执行学习任务: {task.task_id} (模型: {task.model_id})")

            result = self._compute_baseline_training(task)

            task.completed_at = datetime.now()
            task.status = "completed"
            task.progress = 1.0
            task.result = result

            # 如果训练成功，创建新版本
            if result.get('success', False):
                self._create_new_model_version(task, result)

            return result

        except Exception as e:
            logger.error(f"执行学习任务失败: {e}")
            task.status = "failed"
            task.error_message = str(e)
            return {'success': False, 'error': str(e)}

    def _compute_baseline_training(self, task: LearningTask) -> Dict[str, Any]:
        """检查是否可以执行训练（需要真实数据源支持）"""
        try:
            logger.warning(
                f"持续学习管理器无法执行真实模型训练：缺少真实训练数据源。"
                f"模型ID: {task.model_id}, 触发: {task.trigger.value}"
            )

            current_version = self.version_manager.get_best_version(task.model_id)
            if current_version:
                logger.info(
                    f"模型 {task.model_id} 当前最佳版本: {current_version.version}, "
                    f"准确率: {current_version.metrics.accuracy:.4f}。跳过训练，保持当前版本。"
                )
            else:
                logger.warning(
                    f"模型 {task.model_id} 没有现有版本，且无训练数据可用，无法创建新版本。"
                )

            task.progress = 1.0
            return {
                'success': False,
                'error': '缺少真实训练数据源，无法执行模型训练',
                'learning_mode': task.learning_mode.value,
                'training_skipped': True
            }

        except Exception as e:
            logger.error(f"训练准备失败: {e}")
            return {'success': False, 'error': str(e)}

    def _create_new_model_version(self, task: LearningTask, result: Dict[str, Any]):
        """创建新模型版本"""
        try:
            metrics = result['metrics']

            # 生成模型文件路径
            model_dir = Path(self.storage_path) / "models" / task.model_id
            model_dir.mkdir(parents=True, exist_ok=True)
            model_file = model_dir / f"model_{metrics.version}.pkl"

            model_data = {
                'model_id': task.model_id,
                'version': metrics.version,
                'training_config': task.config,
                'metrics': asdict(metrics),
                'created_at': datetime.now().isoformat()
            }

            with open(model_file, 'wb') as f:
                pickle.dump(model_data, f)

            # 创建版本记录
            version = ModelVersion(
                model_id=task.model_id,
                version=metrics.version,
                file_path=str(model_file),
                metrics=metrics,
                config=task.config,
                metadata={
                    'learning_mode': task.learning_mode.value,
                    'trigger': task.trigger.value,
                    'task_id': task.task_id
                },
                is_active=False,  # 新版本默认不激活
                is_baseline=False
            )

            # 添加版本
            self.version_manager.add_version(version)

            # 如果启用自动激活且性能更好，则激活新版本
            if self.config.get('auto_activation', True):
                current_active = self.version_manager.get_active_version(task.model_id)
                if not current_active or metrics.accuracy > current_active.metrics.accuracy:
                    self.version_manager.activate_version(task.model_id, metrics.version)
                    logger.info(f"自动激活新版本: {task.model_id} v{metrics.version}")

            # 清理旧版本
            removed_count = self.version_manager.cleanup_old_versions(
                task.model_id,
                self.config.get('model_retention_count', 5)
            )

            if removed_count > 0:
                logger.info(f"清理了 {removed_count} 个旧版本")

        except Exception as e:
            logger.error(f"创建新模型版本失败: {e}")

    def _on_task_completed(self, task_id: str, future: Future):
        """任务完成回调"""
        try:
            result = future.result()

            # 从活跃任务中移除
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                del self.active_tasks[task_id]

                if result.get('success', False):
                    logger.info(f"学习任务完成: {task_id} (模型: {task.model_id})")
                else:
                    logger.error(f"学习任务失败: {task_id} - {result.get('error', 'Unknown error')}")

        except Exception as e:
            logger.error(f"任务完成回调失败: {e}")

    def _periodic_checks(self):
        """定期检查"""
        try:
            # 检查所有模型的数据漂移和性能退化
            for model_id in self.version_manager.versions.keys():
                self._check_learning_triggers(model_id)

        except Exception as e:
            logger.error(f"定期检查失败: {e}")

    def _check_learning_triggers(self, model_id: str):
        """检查学习触发条件"""
        try:
            # 检查数据漂移
            drift_result = self.drift_detector.detect_drift()
            if drift_result.get('drift_detected', False):
                logger.info(f"检测到数据漂移: {model_id}")
                self.trigger_learning(
                    model_id=model_id,
                    trigger=LearningTrigger.DATA_DRIFT,
                    priority=3,
                    config={'drift_result': drift_result}
                )

            # 性能退化检查在record_prediction_metrics中处理

        except Exception as e:
            logger.error(f"检查学习触发条件失败: {e}")

    def _determine_model_status(self, model_id: str) -> str:
        """确定模型状态"""
        try:
            # 检查是否有活跃任务
            active_task_count = sum(1 for task in self.active_tasks.values() if task.model_id == model_id)
            if active_task_count > 0:
                return ModelStatus.TRAINING.value

            # 检查是否有活跃版本
            active_version = self.version_manager.get_active_version(model_id)
            if not active_version:
                return ModelStatus.ERROR.value

            # 检查性能状态
            degradation_result = self.performance_monitor.check_performance_degradation(model_id)
            if degradation_result.get('degradation_detected', False):
                return ModelStatus.DEPRECATED.value

            return ModelStatus.READY.value

        except Exception as e:
            logger.error(f"确定模型状态失败: {e}")
            return ModelStatus.ERROR.value

    def _generate_task_id(self, model_id: str) -> str:
        """生成任务ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{model_id}_task_{timestamp}"

    def _generate_version_id(self) -> str:
        """生成版本ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"v_{timestamp}"

    def get_learning_statistics(self) -> Dict[str, Any]:
        """获取学习统计信息"""
        try:
            total_models = len(self.version_manager.versions)
            total_versions = sum(len(versions) for versions in self.version_manager.versions.values())
            active_tasks = len(self.active_tasks)
            pending_tasks = self.learning_tasks.qsize()

            # 计算平均性能提升
            performance_improvements = []
            for model_id, versions in self.version_manager.versions.items():
                if len(versions) > 1:
                    sorted_versions = sorted(versions, key=lambda v: v.created_at)
                    latest = sorted_versions[-1]
                    baseline = sorted_versions[0]
                    improvement = latest.metrics.accuracy - baseline.metrics.accuracy
                    performance_improvements.append(improvement)

            avg_improvement = np.mean(performance_improvements) if performance_improvements else 0.0

            return {
                'total_models': total_models,
                'total_versions': total_versions,
                'active_tasks': active_tasks,
                'pending_tasks': pending_tasks,
                'average_performance_improvement': avg_improvement,
                'service_status': 'running' if self.is_running else 'stopped',
                'config': self.config
            }

        except Exception as e:
            logger.error(f"获取学习统计信息失败: {e}")
            return {'error': str(e)}


# 全局实例
continuous_learning_manager = None


def get_continuous_learning_manager(storage_path: Optional[str] = None) -> ContinuousLearningManager:
    """获取持续学习管理器实例"""
    global continuous_learning_manager

    if continuous_learning_manager is None:
        continuous_learning_manager = ContinuousLearningManager(storage_path)

    return continuous_learning_manager


def start_continuous_learning():
    """启动持续学习服务的便捷函数"""
    manager = get_continuous_learning_manager()
    manager.start()


def stop_continuous_learning():
    """停止持续学习服务的便捷函数"""
    manager = get_continuous_learning_manager()
    manager.stop()
